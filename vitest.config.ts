import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [cloudflareTest({ wrangler: { configPath: "./wrangler.json" } })],
  test: { include: ["tests/**/*.test.ts"], testTimeout: 10000 },
});
