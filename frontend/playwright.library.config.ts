import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";
import base from "./playwright.config";

process.env.SO101_LIBRARY_E2E = "1";
export default defineConfig({
  ...base,
  testMatch: ["import-library.spec.ts", "package-import.spec.ts"],
  use: { ...base.use, baseURL: "http://127.0.0.1:18865" },
  webServer: {
    command: ".venv/bin/python -m backend.tests.library_browser_server",
    cwd: fileURLToPath(new URL("..", import.meta.url)),
    url: "http://127.0.0.1:18865/api/health",
    reuseExistingServer: false,
  },
});
