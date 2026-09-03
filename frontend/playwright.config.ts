import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:8877",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "../.venv/bin/python ../tests/serve_browser.py",
    url: "http://127.0.0.1:8877/api/auth/status",
    reuseExistingServer: false,
    timeout: 30000,
  },
  reporter: "list",
});
