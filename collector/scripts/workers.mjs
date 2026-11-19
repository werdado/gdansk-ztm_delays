import { spawnSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const [action, ...options] = process.argv.slice(2);
if (!["build", "deploy", "stop"].includes(action) || options.some((option) => option !== "--dry-run")) {
  throw new Error("Usage: node scripts/workers.mjs build|deploy|stop [--dry-run]");
}

const dryRun = action === "build" || options.includes("--dry-run");
const config = JSON.parse(await readFile(join(root, "wrangler.json"), "utf8"));
let configPath = join(root, "wrangler.json");

if (action === "stop") {
  // Deploy the same code with collection disabled and every cron removed. Never touch R2 objects.
  config.main = resolve(root, config.main);
  delete config.$schema;
  for (const environment of [config, ...Object.values(config.env)]) {
    environment.triggers = { crons: [] };
    environment.vars.ENABLED = "false";
  }
  await mkdir(join(root, ".wrangler"), { recursive: true });
  configPath = join(root, ".wrangler", "stopped.json");
  await writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`);
}

for (const environment of Object.keys(config.env)) {
  console.log(`${dryRun ? "Check" : "Apply"} ${action}: ${config.env[environment].name}`);
  const args = [join(root, "node_modules/wrangler/bin/wrangler.js"), "deploy", "--config", configPath, "--env", environment];
  if (dryRun) args.push("--dry-run", "--outdir", join(root, "dist", action === "stop" ? "stopped" : "active", environment));
  const result = spawnSync(process.execPath, args, {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, WRANGLER_SEND_METRICS: "false", WRANGLER_LOG_PATH: join(root, ".wrangler", "logs") },
  });
  if (result.error || result.status !== 0) {
    console.error(`Failed ${action}: ${environment}`, result.error?.message ?? result.signal ?? result.status);
    process.exitCode = 1;
  }
}
