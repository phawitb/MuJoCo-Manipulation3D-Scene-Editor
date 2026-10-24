import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  expect: { timeout: 15000 },
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1600, height: 1000 },
    launchOptions: {
      channel: process.env.PLAYWRIGHT_CHROMIUM ? undefined : "chrome",
      args: ["--enable-webgl", "--use-gl=angle", "--use-angle=metal"],
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
