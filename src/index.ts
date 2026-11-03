export interface Env {
  ARCHIVE: R2Bucket;
  OFFSET_SECONDS: string;
  ENABLED: string;
}

const sources = [
  { id: "gtfs-rt", url: "https://ckan2.multimediagdansk.pl/gtfs-rt", extension: "pb" },
  { id: "gps", url: "https://ckan2.multimediagdansk.pl/gpsPositions?v=2", extension: "json" },
  { id: "departures", url: "https://ckan2.multimediagdansk.pl/departures", extension: "json" },
] as const;

const slotMilliseconds = 20_000;
const minuteMilliseconds = 60_000;
const transferTimeoutMilliseconds = 15_000;
const maximumSourceBytes = 16 * 1024 * 1024;

interface SourceResult {
  source: string;
  url: string;
  status: "stored" | "error";
  fetchedAt: string;
  receivedAt?: string;
  storedAt?: string;
  httpStatus?: number;
  headers?: Record<string, string>;
  rawBytes?: number;
  gzipBytes?: number;
  key?: string;
  error?: string;
}

function nowIso(): string {
  return new Date(Date.now()).toISOString();
}

async function capture(
  source: (typeof sources)[number],
  archive: R2Bucket,
  scheduledFor: string,
  attemptId: string,
): Promise<SourceResult> {
  const result: SourceResult = {
    source: source.id,
    url: source.url,
    status: "error",
    fetchedAt: nowIso(),
  };
  const abort = new AbortController();
  const timeout = setTimeout(() => abort.abort(new DOMException("Source transfer timed out", "TimeoutError")), transferTimeoutMilliseconds);

  try {
    const response = await fetch(source.url, {
      headers: { "Accept-Encoding": "identity" },
      cache: "no-store",
      redirect: "manual",
      signal: abort.signal,
    });
    result.httpStatus = response.status;
    result.headers = Object.fromEntries(response.headers);
    if (response.status !== 200 || !response.body) {
      await response.body?.cancel();
      throw new Error(`Expected HTTP 200 with a body; received ${response.status}`);
    }
    if (Number(response.headers.get("content-length")) > maximumSourceBytes) {
      await response.body.cancel();
      throw new Error(`Source exceeds ${maximumSourceBytes}-byte size limit`);
    }

    let rawBytes = 0;
    const bounded = response.body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        rawBytes += chunk.byteLength;
        if (rawBytes > maximumSourceBytes) throw new Error(`Source exceeds ${maximumSourceBytes}-byte size limit`);
        controller.enqueue(chunk);
      },
    }));
    // R2 needs a known length. Buffer only the gzip result, never parsed JSON or protobuf.
    const compressed = await new Response(bounded.pipeThrough(new CompressionStream("gzip"))).arrayBuffer();
    clearTimeout(timeout);
    if (rawBytes === 0) throw new Error("Source returned an empty body");
    result.receivedAt = nowIso();
    result.rawBytes = rawBytes;
    result.gzipBytes = compressed.byteLength;
    const key = `snapshots/${source.id}/${scheduledFor.slice(0, 10)}/${scheduledFor}/${attemptId}.${source.extension}.gz`;
    await archive.put(key, compressed, {
      httpMetadata: { contentType: "application/gzip" },
      customMetadata: {
        sourceUrl: source.url,
        scheduledFor,
        fetchedAt: result.fetchedAt,
        receivedAt: result.receivedAt,
        sourceContentType: response.headers.get("content-type") ?? "",
        rawBytes: String(rawBytes),
        attemptId,
      },
    });
    result.key = key;
    result.storedAt = nowIso();
    result.status = "stored";
  } catch (error) {
    abort.abort();
    result.error = error instanceof Error ? error.message : String(error);
    console.error(JSON.stringify({ event: "source_failed", scheduledFor, attemptId, ...result }));
  } finally {
    clearTimeout(timeout);
  }
  return result;
}

export default {
  async scheduled(controller: ScheduledController, env: Env): Promise<void> {
    if (env.ENABLED === "false") return;
    if (env.ENABLED !== "true") throw new Error("ENABLED must be true or false");
    if (!["0", "20", "40"].includes(env.OFFSET_SECONDS)) throw new Error("Invalid offset: expected 0, 20 or 40 seconds");
    if (!Number.isFinite(controller.scheduledTime)) throw new Error("Invalid scheduled time");

    // A retried invocation cannot recover a past observation. The next cron is a fresh attempt.
    controller.noRetry();
    const invokedAt = nowIso();
    // Cron timestamps have a per-Worker phase within the minute. Use the next
    // UTC minute so each invocation can wait for a shared :00/:20/:40 grid.
    const nextMinute = (Math.floor(controller.scheduledTime / minuteMilliseconds) + 1) * minuteMilliseconds;
    const target = nextMinute + Number(env.OFFSET_SECONDS) * 1000;
    const delay = target - Date.now();
    if (delay > 0) await new Promise<void>((resolve) => setTimeout(resolve, delay));

    const scheduledFor = new Date(target).toISOString();
    const attemptId = crypto.randomUUID();
    const startedAt = nowIso();
    const late = Date.now() >= target + slotMilliseconds;
    const results = late ? [] : await Promise.all(sources.map((source) => capture(source, env.ARCHIVE, scheduledFor, attemptId)));
    const status = late ? "skipped" : results.every((result) => result.status === "stored") ? "complete" : "partial";
    const manifest = {
      schemaVersion: 1,
      attemptId,
      cronScheduledAt: new Date(controller.scheduledTime).toISOString(),
      invokedAt,
      scheduledFor,
      offsetSeconds: Number(env.OFFSET_SECONDS),
      startedAt,
      completedAt: nowIso(),
      status,
      ...(late ? { reason: "slot_expired" } : {}),
      sources: results,
    };
    await env.ARCHIVE.put(`runs/${scheduledFor.slice(0, 10)}/${scheduledFor}/${attemptId}.json`, JSON.stringify(manifest), {
      httpMetadata: { contentType: "application/json" },
    });
    console.log(JSON.stringify({ event: "collection_finished", ...manifest }));
    if (status === "partial") throw new Error(`Collection ${attemptId} has failed sources; see its R2 manifest`);
  },
} satisfies ExportedHandler<Env>;
