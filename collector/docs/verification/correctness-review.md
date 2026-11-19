# Collector correctness review

Reviewed the fixed change package against the two-document baseline, using the thermo-nuclear-review skill. Scope: handler, runtime tests, operator script, configuration, dependency/runtime requirements, README and changed handoff text. No code or remote resources were changed by this review.

**Outcome: no remaining findings after the repair reviewed below.**

## Finding

**P1 — Unsupported redirect mode prevents every source request** (`src/index.ts:55`, initial reviewed state).

The collector passes `redirect: "error"` to `fetch`. Workers supports only `follow` and `manual`; constructing the request throws before network activity. Every source therefore becomes an error and no snapshots are collected. The existing tests and full-size smoke replace global `fetch`, so they bypass this native request validation. [Cloudflare Request documentation](https://developers.cloudflare.com/workers/runtime-apis/request/)

Independent reproduction in the installed workerd runtime, through a minimal local Miniflare Worker: `new Request("https://example.com/", { redirect: "error" })` returned `TypeError: Invalid redirect value, must be one of "follow" or "manual"`. The same probe accepted the collector's complete options with `redirect: "manual"`. These probes made no upstream requests.

Recommended `manual`; the existing HTTP-200 check then rejects redirect responses. Also recommended validating the actual options with native `Request` in the upstream test stub so this platform incompatibility cannot be hidden again. This finding is resolved as recorded below.

No additional credible security or correctness finding was identified. Traced offset scheduling, expired slots, unique attempt keys, byte-preserving compression, stream size/deadline failures, independent source/R2 outcomes, manifest failure behavior, and all-three-environment deployment/stop handling.

## Evidence and limits

Inspected all 13 runtime tests and the retained full-size smoke experiment/output. Existing evidence reports passing type checks, tests, three build dry-runs, three stop dry-runs, and nine gzip round trips with three manifests. Those checks were not rerun during the initial review. The native request probe above adds coverage absent from that evidence.

The handler's awaited delays fit Cloudflare's documented 15-minute cron wall-time allowance; minute cron CPU limits remain separate. [Workers limits](https://developers.cloudflare.com/workers/platform/limits/)

No deployment, cloud CPU measurement, account/bucket inspection or real cron reliability validation was performed. Private bucket settings and absence of remote retention rules remain operator responsibilities. This workspace has no Git repository or PR discussion to inspect.

## Reviewed state

All 14 files matched `.wrangler/verification/state.json` at initial review. SHA-256 anchors:

| Artifact | SHA-256 |
|---|---|
| Initial state manifest | `1bd214b17cf95f61a87055f4e60832b816705375ad0c544a8f5313e7c1a88818` |
| Initial change patch | `e834f0b36ca9158e7600408d60b1b3303e6366e17765407a1e2d50e976115163` |
| `src/index.ts` | `0f9bcc90b148f4acbc4461d8bca2cac996d5d77d5a784c1544099e1561172113` |
| `scripts/workers.mjs` | `f40df58a1c761820f698c03db6dfe42bc07d4b576c3d8b6c95669d4a87ea4d88` |
| `wrangler.jsonc` | `50d59136f60d6eefc0fa88f72770258d614837bcc6dfff349d470ceecfd98eb3` |
| `tests/collector.test.ts` | `9df9d7055f0591442fbf1ff6f671f733633a04628449a9bb8f15ad507c1013cc` |

## Repair verification

Inspected the refreshed patch and changed files. Production uses `redirect: "manual"`; the primary archival fixture constructs a native `Request` from the actual fetch options, and the existing failure/recovery table now covers HTTP 302 and 503. The recorded regression failed against the old code, then `npm run check` passed type checking and 14 workerd tests. All three build and all three stop dry-runs were refreshed successfully. The independent native runtime probe also accepted `manual` with the complete request options. **P1 resolved.**

Also checked the configuration rename to `wrangler.json`, all consumers, and the narrowed Node engine range against the installed Vite/Vitest requirements. Configuration contents and collection behavior are unchanged. No new finding. The refreshed full-size smoke was still running when this scoped repair review finished; its result belongs in the test audit.

All 14 hashes matched the repair state manifest. SHA-256 anchors for this reviewed repair:

| Artifact | SHA-256 |
|---|---|
| Repair state manifest | `3f320839d5a192fb5f355b461c9ccb14f5bb2bc477706733481b536ab43141f0` |
| Repair change patch | `9227c1fa5b4ba9baca159a44030bb9edbbb5c09a35ade0f3c1c72578af00afe4` |
| `src/index.ts` | `be8add37b1a7bb9f4c2c9faf3c3120fe8e47e71815c925231520b5aaf95a35d0` |
| `scripts/workers.mjs` | `b3546c5f7d5261c3e62ebf019cf4fa96464ecebbe9a3bf7b2836b1277f74263a` |
| `wrangler.json` | `50d59136f60d6eefc0fa88f72770258d614837bcc6dfff349d470ceecfd98eb3` |
| `tests/collector.test.ts` | `213a65d56a7a1bed5ab68ff33ea73a10e2d47a25131acbca833809e54d946a52` |
