# Collector test audit

Scope: new continuous collector, its runtime tests, Wrangler configuration and operator scripts. Initial workspace had only `ztm-poc-handoff.md` and `ztm-platform-research.md`, preserved in `/tmp/ztm-implementation-baseline`; this is not a Git repository. The reviewed code/content hashes are in `state.json` next to the review package under `.wrangler/verification`.

Agreement: three minute-scheduled Workers at 0/20/40 seconds; all three complete source payloads gzip-compressed into shared R2; continuous collection until manual stop; no automatic retention policy. Latest user instruction limits work to implementation and local tests; user owns deployment.

## Retained contracts

| Observable contract | Primary proof | Credible regression |
|---|---|---|
| Exact JSON/protobuf bytes recovered from stored gzip, metadata and counts match | Scheduled handler → native CompressionStream → local R2 → DecompressionStream | Parsing/reserializing JSON, corrupting binary, wrong HTTP encoding, premature success |
| Offsets use scheduled minute, not completion of previous work | Clock-controlled handler table for 0/20/40; checks no fetch before target | Delay based on invocation start adds drift; no wait fires early |
| Expired slots are visible and don't burst-fetch | 20-second-late handler writes skipped manifest | Old invocation fetches current data pretending to be historical |
| Duplicate slot invocations preserve separate observations | Two concurrent invocations produce six snapshots and two manifests | Slot-only keys overwrite captures |
| A failed source doesn't suppress healthy sources; next round recovers | HTTP 503, then healthy next minute through real R2 | Promise rejection cancels the complete round or poisons subsequent runs |
| Truncated/oversized bodies aren't archived as successful | Erroring stream and >16 MiB stream without Content-Length | Partial body saved as valid gzip, cap enforced only on headers |
| Deadline extends through stalled response body | Fake clock plus abort-aware upstream stream | Timer cleared after headers, leaving body consumption unbounded |
| R2 snapshot failure remains local to the source | One R2 put fault with other writes delegated to actual local R2 | Missing snapshot reported as stored or sibling writes skipped |
| Manual disabled mode and no calendar cutoff | Disabled handler creates no objects, enabled 2030 run succeeds | Stop doesn't stop source traffic; original ten-day limit remains |
| Invalid offset rejected before fetching | Offset 21 rejected at public handler | Misconfigured worker silently polls at unintended interval |

There are no exported test-only functions or injected production clocks/transports. Only public scheduled handler and R2 objects are asserted. Upstream network and clock are controlled at the platform boundary; one test deliberately fails an R2 operation. Size/timeout/storage tests represent different failures and do not duplicate the HTTP-error recovery case.

## Evidence

- Initial `npm test` against empty scheduled handler: exit 1, all 13 tests failed due to absent behavior; establishes a failing baseline.
- `npm run check`: exit 0; TypeScript check passed, 13 tests passed in workerd (2026-11-03, 15:09 Europe/Madrid).
- `npm run build`: exit 0; all three Wrangler dry-run bundles succeeded with the shared `ztm-archive` binding, offsets 0/20/40 and `ENABLED=true`.
- `npm run stop -- --dry-run`: exit 0; all three bundles succeeded with `ENABLED=false`. Generated stop config contains empty cron arrays and unchanged bucket bindings; source config stays enabled.
- Full-size smoke experiment: exit 0, one integration test passed in 58.04 seconds. Loaded all three compiled bundles, used real 0/20/40-second waits and one shared local R2 binding, and verified all nine decompressed snapshots against the 4,492,569-byte combined live-source sample. Three complete manifests plus nine snapshots were present. The source data came from captured GET responses, not new network calls during this test. Retained experiment and output: `.wrangler/verification/smoke-test.ts`, `smoke-passed.log`; fixture data is local/ignored.
- Native gzip/cancellation test initially exposed an unhandled rejection when both the fetch and stream pipe used the same abort signal. Fetch already owns body cancellation; removing the redundant pipe abort eliminated the unhandled rejection. The stalled-body test remains and passes.

## Limits

Local R2 and workerd do not establish cloud delivery reliability, CPU billing/limits, or account access. Upstream test transport is mocked; saved live-response samples are used in an additional local smoke experiment. Remote deployment, billing changes, live schedules and remote storage are excluded at the user's instruction.

## Review repair and refreshed evidence

- Correctness P1 accepted: Workers rejects `redirect: "error"`. The main archival test now constructs a native `Request` using the collector's real options before returning fixture bytes. With the old code, the focused test failed with `Invalid redirect value` for all three sources (exit 1, 2026-11-03 15:18:34 Europe/Madrid). Changed production mode to `manual`; HTTP status checking continues to reject redirects without following them. Expanded the existing HTTP-error recovery table to include 302 alongside 503.
- `npm run check` after repair: exit 0, types pass and **14 tests pass**, no unhandled errors (15:18:58 Europe/Madrid).
- Maintainability P3 accepted: renamed `wrangler.jsonc` to `wrangler.json`, updating all configuration consumers, since the operator script intentionally uses strict JSON. Wrangler's installed implementation recognizes `wrangler.json` as a default configuration filename.
- Dependency contract corrected: Node range is `^22.12.0 || >=24.0.0`, matching the Vite/Vitest requirements; package lock and README agree.
- `npm run build` and `npm run stop -- --dry-run` after these changes: exit 0, all six Worker/environment bundles pass. They reference `wrangler.json`; active bindings are enabled, stopped bindings disabled.

These repairs do not add production test seams. The main archive test remains the primary owner of source-byte and platform request-option compatibility, with 302 handled in the existing error recovery table.
