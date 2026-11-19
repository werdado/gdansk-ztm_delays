# Cron spacing correction — 2026-11-03

The user reported clustered timestamps in `ztm-archive` and requested a bucket inspection. Cloud access was read-only; deployment remains the user's responsibility.

## Production evidence

Read 17 run manifests under `runs/2026-11-03/2026-11-03T17:1` using the Cloudflare R2 Objects API. They cover 17:14–17:19 UTC. All report `complete`, with all three source results marked `stored`. There are three runs per full minute from 17:15 onward. This is uneven spacing, not excess total collection rounds in that sample.

For 17:16 UTC:

| Worker offset | Object's nominal slot | Actual fetch start |
|---|---|---|
| 0 | 17:16:14.289 | 17:16:15.212 |
| 40 | 17:16:18.552 | 17:16:18.552 |
| 20 | 17:16:21.341 | 17:16:21.341 |

The next fetch started at 17:17:15.341, a 54-second gap after the preceding fetch. Subtracting each configured offset from its nominal slot reveals the supplied cron phases: `:14.289` for offset 0, `:01.341` for offset 20, and `:38.552` of the preceding minute for offset 40. The implementation incorrectly assumed that the supplied cron time was on a minute boundary.

Raw list and manifests are retained locally in `.wrangler/verification/r2-inspection/`. No remote objects, schedules, or deployments were changed. The temporary authentication header was removed after reads. This inspection checked manifests; it did not download and decompress the production snapshots.

## Correction

Normalize the supplied cron timestamp to its UTC minute and target the following minute at the configured offset. Using a future minute gives each Worker time to reach the shared `:00/:20/:40` grid. Merely flooring to the current minute would leave some targets already in the past. Every invocation still owns one slot and runs the same three parallel fetches.

The longest planned wait is 100 seconds, within the scheduled handler's wall-time limit. Waiting invocations can overlap. Actual collection remains subject to delivery and timer delays; the existing 20-second expiry guard remains. New `cronScheduledAt` and `invokedAt` manifest fields make those delays visible. No fixed-duration stop condition was added.

## Test audit and verification

Scope is the correction relative to `.wrangler/verification/scheduling-fix/base/`, not the original implementation. This workspace has no Git repository. The patch and SHA-256 identifiers are retained beside that baseline.

- Extended the existing scheduling table, its primary owner, to cover minute-aligned cron events, the three production phases, and events at the minute's last millisecond delivered in the next minute. The public scheduled handler, outbound fetch boundary, and native local R2 manifests are exercised; no test-only production seams were introduced.
- The protected contract is collection at the following minute's offset, with no fetch before that target and accurate recorded times. A credible regression is the former direct addition of the offset. The original table missed nonzero seconds in `scheduledTime`.
- Updated existing test inputs to represent the preceding cron minute, preserving coverage for expiry, HTTP errors and recovery, duplicate invocations, manual stop, no end date, lossless gzip, and transfer/storage failures.
- Red regression: `npm test -- --testNamePattern 'targets next-minute'`, exit 1, nine cases failed against the old handler. Eight failed because fetching occurred before the target; the last-millisecond/offset-zero case exposed the wrong slot and missing diagnostic fields. Log: `.wrangler/verification/scheduling-fix/red-regression.log`.
- Green: `npm run check`, exit 0, TypeScript and all 20 workerd tests passed. Log: `.wrangler/verification/scheduling-fix/check.log`.
- An earlier redirected test command could not start workerd because the sandbox denied its local listening socket; it ran no tests and is not regression evidence. The direct approved npm command above ran successfully.

Test audit: no blocking findings or redundant proof added. The test transport and clock are controlled; gzip and R2 use workerd. This establishes local scheduling behavior, not production punctuality or CPU consumption. Production validation requires the user's redeployment and subsequent comparison of `scheduledFor` with `fetchedAt`.
