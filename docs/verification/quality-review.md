# Collector maintainability review

Reviewed 2026-11-03 using `thermo-nuclear-code-quality-review`. Scope: the fixed `.wrangler/verification/change.patch`, actual implementation/configuration/tests, implementation plan and test audit. Initial baseline consists of the two documents preserved in `/tmp/ztm-implementation-baseline`; this directory is not a Git repository.

**Verdict: no blocking maintainability findings.** One low-priority operational maintenance issue follows.

## Finding

**P3 — Config filename promises JSONC, but the command wrapper requires strict JSON.** `scripts/workers.mjs:13` uses `JSON.parse` on `wrangler.jsonc`. Adding a comment or trailing comma during an otherwise valid JSONC configuration edit makes all three wrapper actions fail before Wrangler runs. The checked-in configuration works because it currently contains strict JSON. Prefer renaming it to `wrangler.json` and updating references, or explicitly support JSONC in the wrapper. This does not block the current implementation.

## Structural assessment

- The 146-line handler has two clear responsibilities: one bounded source capture and one scheduled round. The three sources share the same capture path; no feed-specific branching or test-only production seam exists.
- Parallel captures isolate failures and preserve successful siblings. Building one manifest after they settle is direct; snapshot/manifest atomicity is unavailable through this API, and the documented metadata fallback is proportionate.
- The 42-line operator script derives stop configuration from the active configuration and attempts every environment. Its sequential deployments retain readable failure reporting; adding orchestration or generated configuration layers would increase complexity here.
- Result fields accumulate as transfer/storage stages succeed. Their optionality represents partial failure evidence; a more elaborate state model is not justified by a concrete maintenance problem in this implementation.
- No large-file growth, scattered feature checks, duplicate production helpers, or clear restructuring that would remove substantial complexity was found.

## Evidence and limits

Inspected source, tests, configuration, operator script, scoped patch, plan and test audit. Recomputed SHA-256 for every file in the supplied state manifest: all 14 matched. Inspected the retained smoke output showing one passing test in 58.04 seconds; the test audit records the 13 workerd tests, typecheck, all three build/stop dry-runs and nine full-size gzip round trips. This review does not claim an independent rerun of those commands.

No code was changed, no agents were spawned, and no deployment occurred. Runtime correctness and production CPU, cron delivery and account state remain outside this maintainability verdict.

## Reviewed content identifiers

- Change patch SHA-256: `e834f0b36ca9158e7600408d60b1b3303e6366e17765407a1e2d50e976115163`
- State manifest SHA-256: `1bd214b17cf95f61a87055f4e60832b816705375ad0c544a8f5313e7c1a88818`
- `src/index.ts`: `0f9bcc90b148f4acbc4461d8bca2cac996d5d77d5a784c1544099e1561172113`
- `scripts/workers.mjs`: `f40df58a1c761820f698c03db6dfe42bc07d4b576c3d8b6c95669d4a87ea4d88`
- `wrangler.jsonc`: `50d59136f60d6eefc0fa88f72770258d614837bcc6dfff349d470ceecfd98eb3`
- `tests/collector.test.ts`: `9df9d7055f0591442fbf1ff6f671f733633a04628449a9bb8f15ad507c1013cc`
- `package.json`: `be9944b54ffd9853fa875b5be43ef85a3e172bd1b1ca0c15d6d04aeec6a58775`
- `package-lock.json`: `5a19ac31f1e069cc052a6a04a7e0ddcbaa3cae7f8679e4e017491b71fb23cc66`

The remaining eight reviewed hashes are retained in `.wrangler/verification/state.json`, identified above. This report is additional review evidence and is not part of that earlier manifest.


## Scoped re-review and final disposition

Reviewed the targeted repairs on 2026-11-03. **P3 resolved; no remaining maintainability findings.** The configuration is now `wrangler.json`, and the operator script, Vitest configuration, README and plan reference that filename. The file contents are unchanged; the rename removes the format ambiguity without adding a parser or dependency.

The adjacent changes preserve the existing structure: `redirect: "manual"` feeds redirects into the existing non-200 failure path; native `Request` construction in the primary fixture stub restores platform option validation; the existing HTTP failure/recovery table now covers 302 and 503. No production injection interface or duplicate test layer was introduced. The Node range `^22.12.0 || >=24.0.0` agrees across the manifest, lockfile and README, and fits the installed Vite, Vitest and Wrangler engine requirements.

Recomputed all 14 current state hashes: all matched. Inspected the refreshed test-audit evidence recording `npm run check` exit 0 with types and 14 workerd tests passing, and all three build plus all three stop dry-runs exiting 0. Per the scoped re-review request, these commands were not rerun. The earlier production-runtime limits still apply.

Final patch SHA-256: `9227c1fa5b4ba9baca159a44030bb9edbbb5c09a35ade0f3c1c72578af00afe4`. Final state manifest SHA-256: `3f320839d5a192fb5f355b461c9ccb14f5bb2bc477706733481b536ab43141f0`. The following content identifiers supersede the earlier reviewed identifiers:

```json
{
  ".gitignore": "7f82761e010af25bd82cb776d051c9096f2001c08da00ee8fa01dd6cadb68cfd",
  "package.json": "6420a1f319659153c5030a5b88c63eb8f6060a5536cd5ec885ff7de5287fe51c",
  "package-lock.json": "82c91d08651d11d36957d8bee57281aa68ab1790f5715c9ee90563017b8775bf",
  "tsconfig.json": "33b9f18838a67242ec865319c7a5709815b502a194f51121ede0bf438572666b",
  "vitest.config.ts": "735316089029eca531beb9ab8da7bcfd3ccab88383a767663be9e1da14bbaee8",
  "src/index.ts": "be8add37b1a7bb9f4c2c9faf3c3120fe8e47e71815c925231520b5aaf95a35d0",
  "tests/collector.test.ts": "213a65d56a7a1bed5ab68ff33ea73a10e2d47a25131acbca833809e54d946a52",
  "scripts/workers.mjs": "b3546c5f7d5261c3e62ebf019cf4fa96464ecebbe9a3bf7b2836b1277f74263a",
  "README.md": "0a6afadf8ca31f1dfe90839833f3b246f90ce5ac2c17d4ee8dc9240d0dacb12d",
  "ztm-poc-handoff.md": "9a8b90f4548df80afa13d62a667163ad38419cd70dd3821337784a7f962f6fdb",
  "ztm-platform-research.md": "584dabdb7e56177870ccae31903e7818990f7ea62dc0e75304bf2ac5c434c22c",
  "docs/plans/0001-continuous-collector.md": "d55e7cfd8d8dbe94df23b53c539ea9792904b8a6ef6c78303df3301bba5bc7cf",
  "docs/verification/test-audit.md": "a0ca53dc7fe2d1fafdf6f4a61ee8e1dab6d633a212feb5e092f5fd11706c3fc1",
  "wrangler.json": "50d59136f60d6eefc0fa88f72770258d614837bcc6dfff349d470ceecfd98eb3"
}
```
