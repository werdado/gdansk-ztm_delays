import { env } from "cloudflare:workers";
import { createScheduledController } from "cloudflare:test";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, { type Env as CollectorEnv } from "../src/index";

declare global {
  namespace Cloudflare {
    interface Env extends CollectorEnv {}
  }
}

const minute = Date.parse("2026-11-03T14:00:00.000Z");
const fixtures = new Map<string, Uint8Array>([
  ["https://ckan2.multimediagdansk.pl/gtfs-rt", new Uint8Array([10, 3, 255, 0, 128, 13])],
  ["https://ckan2.multimediagdansk.pl/gpsPositions?v=2", new TextEncoder().encode('{ "vehicles": [], "extra": "Gdańsk" }\n')],
  ["https://ckan2.multimediagdansk.pl/departures", new TextEncoder().encode('{ "123": { "departures": [] } }\n')],
]);

function goodResponse(url: string): Response {
  const bytes = fixtures.get(url);
  if (!bytes) throw new Error(`Unexpected upstream: ${url}`);
  return new Response(bytes, {
    headers: { "content-type": url.endsWith("gtfs-rt") ? "application/x-protobuf" : "application/json", "last-modified": "Tue, 03 Nov 2026 13:59:59 GMT" },
  });
}

function run(offset = "0", scheduledTime = minute - 60000, enabled = "true") {
  return worker.scheduled(createScheduledController({ scheduledTime: new Date(scheduledTime), cron: "* * * * *" }), {
    ...env, OFFSET_SECONDS: offset, ENABLED: enabled,
  });
}

async function manifests() {
  const listed = await env.ARCHIVE.list({ prefix: "runs/" });
  return Promise.all(listed.objects.map(async ({ key }) => (await env.ARCHIVE.get(key))!.json<any>()));
}

beforeEach(async () => {
  const previous = await env.ARCHIVE.list();
  if (previous.objects.length) await env.ARCHIVE.delete(previous.objects.map(({ key }) => key));
  vi.spyOn(Date, "now").mockReturnValue(minute);
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    // Keep the runtime's RequestInit validation even though transport is replaced.
    const request = new Request(url, init);
    return goodResponse(request.url);
  }));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("scheduled collection in Workers with R2", () => {
  it("archives exact source bytes as gzip with acquisition metadata", async () => {
    await run();
    const [manifest] = await manifests();
    expect(manifest).toMatchObject({ status: "complete", scheduledFor: "2026-11-03T14:00:00.000Z" });
    expect(manifest.sources).toHaveLength(3);
    for (const result of manifest.sources) {
      expect(result).toMatchObject({ status: "stored", httpStatus: 200, fetchedAt: "2026-11-03T14:00:00.000Z" });
      const object = await env.ARCHIVE.get(result.key);
      expect(object).not.toBeNull();
      expect(object!.httpMetadata?.contentType).toBe("application/gzip");
      expect(object!.httpMetadata?.contentEncoding).toBeUndefined();
      expect(object!.customMetadata).toMatchObject({ sourceUrl: result.url, fetchedAt: result.fetchedAt });
      const bytes = new Uint8Array(await new Response(object!.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer());
      expect(bytes).toEqual(fixtures.get(result.url));
      expect(result.rawBytes).toBe(bytes.length);
      expect(result.gzipBytes).toBe(object!.size);
      expect(result.headers["last-modified"]).toBe("Tue, 03 Nov 2026 13:59:59 GMT");
    }
  });

  it.each([
    [0, 0], [20, 0], [40, 0],
    // Cron phases inferred from the 2026-11-03 production R2 manifests.
    [0, 14289], [20, 1341], [40, 38552],
    [0, 59999], [20, 59999], [40, 59999],
  ])("targets next-minute offset %i despite cron phase %i ms", async (offset, phase) => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
    const cronTime = minute - 60000 + phase;
    const invokedAt = cronTime + 1000;
    const expectedTarget = minute + offset * 1000;
    vi.setSystemTime(invokedAt);
    const pending = run(String(offset), cronTime);
    const delay = expectedTarget - invokedAt;
    if (delay > 0) {
      await vi.advanceTimersByTimeAsync(delay - 1);
      expect(fetch).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(1);
    }
    await pending;
    const [manifest] = await manifests();
    expect(manifest).toMatchObject({
      status: "complete",
      scheduledFor: new Date(expectedTarget).toISOString(),
      cronScheduledAt: new Date(cronTime).toISOString(),
      invokedAt: new Date(invokedAt).toISOString(),
    });
    expect(manifest.sources).toHaveLength(3);
    expect(manifest.sources.map((source: any) => source.fetchedAt)).toEqual(
      Array(3).fill(new Date(Math.max(expectedTarget, invokedAt)).toISOString()),
    );
  });

  it("records a missed slot without making stale catch-up requests", async () => {
    vi.mocked(Date.now).mockReturnValue(minute + 20000);
    await run();
    expect(fetch).not.toHaveBeenCalled();
    expect(await manifests()).toEqual([expect.objectContaining({ status: "skipped", reason: "slot_expired" })]);
  });

  it("keeps duplicate slot attempts in different objects", async () => {
    await Promise.all([run(), run()]);
    const objects = await env.ARCHIVE.list({ prefix: "snapshots/" });
    expect(objects.objects).toHaveLength(6);
    expect(await manifests()).toHaveLength(2);
  });

  it.each([302, 503])("retains healthy sources on HTTP %i and recovers at the next slot", async (httpStatus) => {
    vi.mocked(fetch).mockImplementation(async (url) => String(url).endsWith("departures") ? new Response("unavailable", { status: httpStatus }) : goodResponse(String(url)));
    await expect(run()).rejects.toThrow();
    const [failed] = await manifests();
    expect(failed.status).toBe("partial");
    expect(failed.sources.filter((source: any) => source.status === "stored")).toHaveLength(2);
    expect(failed.sources.find((source: any) => source.source === "departures")).toMatchObject({ status: "error", httpStatus });
    vi.mocked(fetch).mockImplementation(async (url) => goodResponse(String(url)));
    vi.mocked(Date.now).mockReturnValue(minute + 60000);
    await run("0", minute);
    expect((await manifests()).map((manifest) => manifest.status)).toEqual(["partial", "complete"]);
  });

  it("never archives a truncated body as a successful gzip snapshot", async () => {
    vi.mocked(fetch).mockImplementation(async (url) => String(url).endsWith("departures")
      ? new Response(new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array([1, 2])); controller.error(new Error("connection lost")); } }))
      : goodResponse(String(url)));
    await expect(run()).rejects.toThrow();
    expect((await env.ARCHIVE.list({ prefix: "snapshots/departures/" })).objects).toHaveLength(0);
    const [manifest] = await manifests();
    expect(manifest.sources.find((source: any) => source.source === "departures")).toMatchObject({ status: "error" });
  });

  it("bounds streamed responses even without Content-Length", async () => {
    vi.mocked(fetch).mockImplementation(async (url) => String(url).endsWith("departures")
      ? new Response(new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(16 * 1024 * 1024 + 1)); controller.close(); } }))
      : goodResponse(String(url)));
    await expect(run()).rejects.toThrow();
    const [manifest] = await manifests();
    expect(manifest.sources.find((source: any) => source.source === "departures").error).toMatch(/size|large|limit/i);
    expect((await env.ARCHIVE.list({ prefix: "snapshots/departures/" })).objects).toHaveLength(0);
  });

  it("aborts a body that stalls after headers and preserves the other sources", async () => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(minute);
    vi.mocked(fetch).mockImplementation(async (url, init) => String(url).endsWith("departures")
      ? new Response(new ReadableStream({ start(controller) { init!.signal!.addEventListener("abort", () => controller.error(init!.signal!.reason), { once: true }); } }))
      : goodResponse(String(url)));
    const pending = expect(run()).rejects.toThrow();
    await vi.advanceTimersByTimeAsync(15000);
    await pending;
    const [manifest] = await manifests();
    expect(manifest.sources.filter((source: any) => source.status === "stored")).toHaveLength(2);
    expect(manifest.sources.find((source: any) => source.source === "departures")).toMatchObject({ status: "error" });
  });

  it("records R2 write failure independently of healthy captures", async () => {
    const originalPut = env.ARCHIVE.put.bind(env.ARCHIVE);
    vi.spyOn(env.ARCHIVE, "put").mockImplementation(((key: string, value: any, options: any) => {
      if (key.startsWith("snapshots/gps/")) return Promise.reject(new Error("R2 unavailable"));
      return originalPut(key, value, options);
    }) as typeof env.ARCHIVE.put);
    await expect(run()).rejects.toThrow();
    const [manifest] = await manifests();
    expect(manifest.sources.find((source: any) => source.source === "gps")).toMatchObject({ status: "error", error: "R2 unavailable" });
    expect(manifest.sources.filter((source: any) => source.status === "stored")).toHaveLength(2);
  });

  it("does no work when manually disabled, with no date cutoff", async () => {
    await run("0", minute - 60000, "false");
    expect(fetch).not.toHaveBeenCalled();
    expect((await env.ARCHIVE.list()).objects).toHaveLength(0);
    const future = Date.parse("2030-01-01T00:00:00.000Z");
    vi.mocked(Date.now).mockReturnValue(future);
    await run("0", future - 60000);
    expect((await manifests())[0].status).toBe("complete");
  });

  it("rejects invalid offsets before fetching", async () => {
    await expect(run("21")).rejects.toThrow(/offset/i);
    expect(fetch).not.toHaveBeenCalled();
  });
});
