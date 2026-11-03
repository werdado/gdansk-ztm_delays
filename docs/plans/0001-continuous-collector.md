# Continuous ZTM Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continuously collect all three ZTM feeds every 20 seconds into a shared R2 bucket as lossless gzip objects.

**Architecture:** One TypeScript scheduled handler deployed as three named Workers with offsets 0, 20 and 40 seconds relative to the following UTC minute. Each invocation independently fetches all three sources, stores complete compressed responses and an outcome manifest. Collection has no end date or object expiry.

**Tech Stack:** Cloudflare Workers, native CompressionStream, R2 bindings, Wrangler, TypeScript, Vitest running in workerd.

**Decision sources:** `ztm-poc-handoff.md`, `ztm-platform-research.md`, and the user's latest instructions: three delayed Workers, gzip, one R2 bucket, continuous collection until manually stopped. The latter supersedes the original ten-day stop.

## Outcome and verification

1. Real local Workers runtime and R2 binding: decompressed objects exactly equal the input JSON/protobuf bytes, including whitespace and binary values. No payload parsing, filtering or deduplication.
2. Scheduled handler: floor the cron timestamp to its UTC minute, advance one minute, then add the configured offset. Production manifests showed that cron timestamps have different seconds for each Worker; directly adding offsets clusters captures. Early execution waits; invocations a full slot (20 seconds) late record a skipped slot rather than burst-fetching old data. Record the supplied cron time, handler entry, and actual fetch times separately.
3. Failure isolation: HTTP/network/body/storage failures cannot suppress other sources. Persist per-source outcomes; incomplete responses never become successful snapshots. Independent attempts use unique keys, including repeated invocations of one slot.
4. Runtime bounds: 15-second source transfer deadline, 16 MiB uncompressed cap per source, parallel fetches of three sources. A failed attempt is recorded; next scheduled collection continues normally. No indefinite retries or day limit.
5. Deployment: three distinct Worker names, shared private R2 bucket, no public HTTP trigger; explicit build, deploy and stop commands. Stop removes schedules and keeps bucket objects. No account subscription changes are automated.

## Design review

Light, single coupled slice; manual execution under subagent-driven-development's tightly-coupled-task exception. Workspace contains two documents and is not a Git repository, so no worktree or baseline commit exists. Preserve baseline documents separately for review. Remote deployment requires a usable Cloudflare account; local tests cannot establish production CPU usage or cron punctuality.

## Global Constraints

- Fetch `https://ckan2.multimediagdansk.pl/gtfs-rt`, `https://ckan2.multimediagdansk.pl/gpsPositions?v=2`, and `https://ckan2.multimediagdansk.pl/departures` in every round.
- Run continuously; the user will turn collection off. No ten-day cutoff and no object expiry.
- Gzip all fetched successful payloads without rewriting their contents. Store source, nominal slot, actual fetch times, response headers, outcome and byte counts.
- Use three minute cron schedules, with offsets `0`, `20`, `40`; shared bucket `ztm-archive` and workers `ztm-collector-00`, `ztm-collector-20`, `ztm-collector-40`.
- Preserve independent responses even when upstream data has not changed. Record failures rather than substituting empty/zero data.

## Review Focus

- Slow/truncated/non-200 responses, gzip correctness, failed R2 puts, overlapping or duplicate invocations, invalid offset configuration, and a late cron after its slot expired.
- Native compression and R2 calls must run through workerd in tests. Mock only upstream transport and the clock, plus an explicit R2 failure test; no production test-only injection interface.
- Deployment commands must select all three environments and stop them without deleting data. Production CPU and real cron timing remain remote validation items.

### Task 1: Continuous capture and operational commands

**Status:** Complete — local implementation and verification; deployment remains with the user.
**Outcome and acceptance:** Criteria 1–5 above, with no stop date.
**Decision context:** Latest user instruction takes precedence over the historical ten-day PoC.
**Files:** `src/index.ts`, `tests/collector.test.ts`, `wrangler.json`, `vitest.config.ts`, `tsconfig.json`, `package.json`, lockfile, `scripts/workers.mjs`, `README.md`; update handoff to record continuous collection.
**Interfaces:** Export default `scheduled(controller: ScheduledController, env: Env): Promise<void>`; `Env` contains `ARCHIVE: R2Bucket`, `OFFSET_SECONDS: string`, `ENABLED: string`. Wrangler environments `tick00`, `tick20`, `tick40` supply offsets and the shared binding. Object paths use `snapshots/<source>/<UTC-date>/<slot>/<attempt>.<pb|json>.gz`; manifests use `runs/<UTC-date>/<slot>/<attempt>.json`.

- [x] Add integration tests through the scheduled handler for byte recovery/metadata, slot delays, late slots, independent duplicate writes, source failure followed by recovery, body size/deadline and storage failure.
- [x] Run `npm test`; establish initial failing evidence before implementing the handler (13 failures against an empty handler).
- [x] Implement handler, bounded gzip capture and per-round manifest; add all three configs and build/deploy/stop script.
- [x] Run `npm run check` and `npm run build`; require all tests, types and three deploy dry-runs to pass. Also checked all three stop dry-runs.
- [x] Inspect a real-feed local smoke run without writing to remote R2; retain evidence and limits. Final experiment passed with three compiled Workers, real delays, nine byte-exact gzip round-trips and three manifests.
- [x] Complete test audit and independent correctness/maintainability reviews; resolve findings. Corrected unsupported redirect mode with a native Request regression, renamed configuration to strict JSON and aligned Node requirements. Both final Standards and Spec reviews verified the repaired state with no remaining findings.
- [x] Deliver verified files and deployment state. No Git commit: this directory is not a repository. Nothing deployed; operator commands are in README.

## Execution record

Final evidence: `docs/verification/final-evidence.md`; test audit and all independent review reports are adjacent. The final normal suite has 14 passing tests and a passing typecheck; all three active and all three stopped build dry-runs pass. Full-size smoke passed again after the redirect repair in 58.33 seconds. Review artifact/state are retained under `.wrangler/verification`; this completion record is an evidence-only update after review and does not change implementation, configuration, tests or agreed behavior.
