import { defineConfig, devices } from "@playwright/test";

const rootDir = process.cwd();
const apiPort = Number(process.env.E2E_API_PORT || 18020);
const webPort = Number(process.env.E2E_WEB_PORT || 15175);
const baseURL = process.env.E2E_BASE_URL || `http://127.0.0.1:${webPort}`;
const reuseExistingServer = process.env.E2E_REUSE_SERVER === "1";
const python = process.env.E2E_PYTHON || `${rootDir}/backend/.venv/bin/python`;
const browserChannel = process.env.E2E_BROWSER_CHANNEL || "chrome";

const webServer = reuseExistingServer
  ? undefined
  : [
      {
        command: `${python} tests/e2e/support/start_api.py`,
        cwd: rootDir,
        url: `http://127.0.0.1:${apiPort}/health`,
        timeout: 120_000,
        reuseExistingServer: false,
        env: {
          ...process.env,
          E2E_API_PORT: String(apiPort),
          E2E_WEB_PORT: String(webPort)
        }
      },
      {
        command: `npm --prefix apps/desktop run dev -- --host 127.0.0.1 --port ${webPort} --strictPort`,
        cwd: rootDir,
        url: baseURL,
        timeout: 120_000,
        reuseExistingServer: false,
        env: {
          ...process.env,
          VITE_API_PROXY_TARGET: `http://127.0.0.1:${apiPort}`
        }
      }
    ];

export default defineConfig({
  testDir: "./specs",
  outputDir: "../artifacts/test-results",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/playwright-report", open: "never" }]
  ],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  webServer,
  projects: [
    {
      name: "desktop-chrome",
      use: { ...devices["Desktop Chrome"], channel: browserChannel }
    }
  ]
});
