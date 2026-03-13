import { defineConfig, devices } from '@playwright/test';

/**
 * Gate C — Browser smoke test suite for MPC Studio.
 *
 * Pyodide boots asynchronously and can take up to ~30 s on a cold start;
 * the per-test timeout is set to 90 s to accommodate both the engine boot
 * and the 350 ms validation debounce.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 30_000 },

  /* Fail the whole run if any spec has errors — keep Gate C binary. */
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,

  reporter: [['list'], ['html', { open: 'never' }]],

  use: {
    baseURL: 'http://localhost:5173',
    /* Keep traces on first retry so CI can download artefacts. */
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
