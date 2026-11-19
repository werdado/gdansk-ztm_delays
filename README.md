# ZTM Gdańsk – delay analysis

Two independent projects that form a pipeline:

| Folder | What it does |
|---|---|
| [`collector/`](collector/README.md) | Cloudflare Workers (TypeScript) that archive the ZTM Gdańsk feeds roughly every 20 seconds into a private R2 bucket. |
| [`report/`](report/AGENTS.md) | Python tooling (`report/src`, see its [README](report/src/README.md)) that turns the local GPS archive into a static, interactive HTML report of delays. Generated output goes to `report/outputs/`. |

`data/` is a git-ignored local folder for the downloaded archive.
