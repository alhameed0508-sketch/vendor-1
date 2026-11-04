// Browser tests for MuleCatch. E2E_BASE_URL picks the app: the local dev server by default, or prod.
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1, // the demo backend is one shared in-memory store
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'report' }]],
  outputDir: 'results',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    // E2E_CHROMIUM reuses an installed Chromium instead of `npx playwright install chromium`
    launchOptions: process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {},
  },
  projects: [{ name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
});
