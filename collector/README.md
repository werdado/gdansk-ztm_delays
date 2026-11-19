# ZTM collector

Three Cloudflare Workers collect the full Gdańsk ZTM feeds approximately every 20 seconds and save the original response bytes as gzip files in one private R2 bucket. Collection continues until you stop it. There is no end date and no object expiration.

| Worker / Wrangler environment | Minute offset |
|---|---:|
| `ztm-collector-00` / `tick00` | 0 seconds |
| `ztm-collector-20` / `tick20` | 20 seconds |
| `ztm-collector-40` / `tick40` | 40 seconds |

All three use `* * * * *`. Cloudflare can assign each cron a different second within the minute. Each invocation targets the **following UTC minute** at `:00`, `:20`, or `:40`, then fetches these sources in parallel:

- `https://ckan2.multimediagdansk.pl/gtfs-rt`
- `https://ckan2.multimediagdansk.pl/gpsPositions?v=2`
- `https://ckan2.multimediagdansk.pl/departures`

Payloads are never parsed, filtered, rewritten, or deduplicated. Both JSON feeds and protobuf are compressed. No additional GTFS-RT feeds or periodic static GTFS downloads are requested.

For example, cron events at `17:14:14.289`, `17:14:01.341`, and `17:14:38.552` target `17:15:00`, `17:15:20`, and `17:15:40`. Anchoring to the following minute gives the invocations time to reach their slots; adding offsets directly to the cron timestamps would cluster captures. Initial collection can wait up to 100 seconds after the first cron event. Waiting invocations can overlap across minutes, and each owns one target slot.

## Local verification

Use Node.js 24 or newer and npm. Node.js 22.12+ on the 22.x release line is also supported.

```sh
npm ci
npm run check
npm run build
npm run stop -- --dry-run
```

Tests execute the scheduled handler, native gzip compression and a local R2 binding in Cloudflare's workerd runtime. They replace upstream HTTP responses and advance the clock to exercise failure and scheduling behavior. Build and stop dry-runs bundle all three Worker configurations without deploying anything.

## Deploy

Deployment is a manual operator action. No subscription upgrade or deployment occurs during local verification.

1. Authenticate with `npx wrangler login` and verify the account with `npx wrangler whoami`.
2. If you have multiple accounts, set `CLOUDFLARE_ACCOUNT_ID` to the intended account ID in your shell. Enable R2 on that account.
3. Create a Standard storage bucket once:

   ```sh
   npx wrangler r2 bucket create ztm-archive
   ```

   If you use another name, change every `bucket_name` in `wrangler.json` to that same name. Keep the bucket private and do not add expiration rules.

4. Deploy all three Workers:

   ```sh
   npm run deploy
   ```

5. Inspect each Worker's aggregate metrics and the R2 `runs/` manifests. Look for `status: complete`, three source results with `status: stored`, and populated `snapshots/` and `runs/` prefixes. Check CPU time and actual `fetchedAt` intervals in production before leaving collection unattended. Local tests do not measure production CPU limits or cron delivery timing.

Stored Worker logging is disabled by the shared `observability.enabled: false` setting, inherited by all three environments. Aggregate Worker metrics remain available, and R2 manifests contain each round's results. This stops new log ingestion after deployment; previously counted events and other Workers' usage remain on the account. For an on-demand debugging session, use `npx wrangler tail --env tick00` (or `tick20` / `tick40`). See [Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/) and [metrics](https://developers.cloudflare.com/workers/observability/metrics-and-analytics/).

Workers Paid is recommended for compression: Free allows only 10 ms of CPU per invocation, including cron. Paid minute cron allows 30 seconds. The configuration does not select or change your billing plan. See [Workers limits](https://developers.cloudflare.com/workers/platform/limits/).

The deployment script attempts all three environments and returns nonzero if any fail. Deployments are separate operations: inspect the output if deployment or stopping fails partway through.

## Stop and resume

```sh
npm run stop
```

This deploys all three Workers with `ENABLED=false` and removes their cron schedules. It does not delete or modify archived objects. Already running invocations can finish; cron changes can take up to 15 minutes to propagate. The disabled handler makes no new source requests when invoked. [Cron propagation](https://developers.cloudflare.com/workers/configuration/cron-triggers/)

Run `npm run deploy` to resume. The checked-in configuration remains enabled. Alternatively, disable `ENABLED` on all three Workers and remove all three schedules in the Cloudflare dashboard; a later deployment from this directory will restore the checked-in settings.

## Archive layout

```text
snapshots/gtfs-rt/2026-11-03/2026-11-03T14:00:20.000Z/<attempt-id>.pb.gz
snapshots/gps/2026-11-03/2026-11-03T14:00:20.000Z/<attempt-id>.json.gz
snapshots/departures/2026-11-03/2026-11-03T14:00:20.000Z/<attempt-id>.json.gz
runs/2026-11-03/2026-11-03T14:00:20.000Z/<attempt-id>.json
```

Keys contain the nominal slot in UTC and a unique invocation ID. A repeated invocation preserves a separate observation. Actual fetch start, body receipt and storage completion times are recorded separately. No assumption is made that the three feeds represent the same source timestamp.

Manifests also record `cronScheduledAt` (Cloudflare's supplied timestamp) and `invokedAt` (handler entry), separately from `scheduledFor` (the target slot) and `startedAt` (collection start). Compare these fields when diagnosing delivery delays or timer drift.

Each manifest records source URLs, HTTP status and response headers, raw/compressed sizes, successful object keys, and failures. Snapshot custom metadata also retains source URL, acquisition time, scheduled slot and original content type, so it remains interpretable if writing the manifest fails. A process interruption can leave a snapshot without a manifest; compare object keys/metadata, expected slot coverage, and Worker metrics when auditing completeness.

Gzip objects have `Content-Type: application/gzip` and no HTTP `Content-Encoding`, so downloading them returns the archive bytes. Decompress with:

```sh
gzip -dc snapshot.json.gz > snapshot.json
gzip -dc snapshot.pb.gz > snapshot.pb
```

## Failure and timing behavior

- A source must return HTTP 200 and a nonempty body. HTTP errors, redirects, interrupted transfers and empty bodies become manifest errors; the other sources still run.
- Source fetch and body consumption have a 15-second deadline. A source is capped at 16 MiB before compression, including responses without `Content-Length`. This bounds memory; a larger feed is recorded as an error, never silently truncated.
- Only the compressed result is buffered for R2's known-length upload requirement. R2 writes have the platform's own execution limits, not the source transfer deadline.
- Failed invocations report an error after the available results and manifest have been written. Automatic invocation retries are disabled because a later fetch cannot reconstruct a missed observation; the next slot collects fresh data.
- Cron is approximate. A run arriving less than 20 seconds late collects immediately and records the actual time. At 20 seconds late or more it writes a `slot_expired` manifest without sending catch-up requests.
- Full Worker failures (CPU limit, process interruption, R2 outage) can prevent a manifest. Worker error metrics and expected slot coverage are needed to detect those gaps; stored exception details are unavailable with logging disabled. No alerting service is configured.

With three sources plus one manifest per round, normal usage is 17,280 R2 writes/day, or about 518,400 in 30 days. The measured snapshot suggested about 1.63 GB/day after gzip, but feed size changes throughout the day. Both collection and retained storage grow indefinitely until you decide otherwise. See [platform research](ztm-platform-research.md) for measured sizes and pricing; its ten-day calculations are historical sizing examples.
