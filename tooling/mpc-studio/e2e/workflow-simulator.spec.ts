import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

async function waitForEngineReady(page: import('@playwright/test').Page) {
  await expect(page.getByText('Local Engine Live')).toBeVisible({ timeout: 60_000 });
}

test.describe('Workflow simulator', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForEngineReady(page);
    await page.getByRole('button', { name: 'Workflow Engine' }).click();
  });

  test('supports step/run/back/reset controls', async ({ page }) => {
    await expect(page.getByText('Workflow Simulator')).toBeVisible();

    await page.getByRole('button', { name: /^STEP$/i }).click();
    await expect(page.getByText('No transitions executed yet.')).toBeHidden({ timeout: 10_000 });

    await page.getByRole('button', { name: /^BACK$/i }).click();
    await page.getByRole('button', { name: /^RESET$/i }).click();

    await page.getByRole('button', { name: /^RUN$/i }).click();
    await expect(page.getByText(/\[run\]\s+allow\s+-\s+Processed/i)).toBeVisible({ timeout: 20_000 });
  });

  test('blocks simulation when permission is disabled', async ({ page }) => {
    const simulateCheckbox = page.getByRole('checkbox', { name: /^simulate$/i });
    await simulateCheckbox.uncheck();

    await page.getByRole('button', { name: /^STEP$/i }).click();
    await expect(
      page.locator('.text-red-400').filter({ hasText: "Permission denied for action 'simulate'." }).first(),
    ).toBeVisible();
  });

  test('enforces tenant isolation for existing run context', async ({ page }) => {
    await page.getByRole('button', { name: /^STEP$/i }).click();
    await expect(page.getByText('No transitions executed yet.')).toBeHidden({ timeout: 10_000 });

    const tenantInput = page.getByPlaceholder('tenantId');
    await tenantInput.fill('tenant-other');
    await page.getByRole('button', { name: /^STEP$/i }).click();

    await expect(
      page
        .locator('.text-red-400')
        .filter({ hasText: 'TENANT_CONTEXT_MISMATCH: Existing run belongs to a different tenant.' })
        .first(),
    ).toBeVisible();
  });

  test('returns payload-size limit error when context is too large', async ({ page }) => {
    const limitInputs = page.locator('input[type="number"]');
    await limitInputs.nth(1).fill('5');

    const contextEditor = page.locator('textarea').nth(0);
    await contextEditor.fill('{"veryLong":"payload"}');
    await page.getByRole('button', { name: /^STEP$/i }).click();

    await expect(
      page.locator('.text-red-300.font-mono').filter({ hasText: /WORKFLOW_PAYLOAD_TOO_LARGE/i }).first(),
    ).toBeVisible();
    await expect(page.getByText(/Reduce context payload size/i)).toBeVisible();
  });

  test('returns event-name limit error when event is too long', async ({ page }) => {
    const limitInputs = page.locator('input[type="number"]');
    await limitInputs.nth(2).fill('3');

    const eventInput = page.getByPlaceholder('single step event');
    await eventInput.fill('begin');
    await page.getByRole('button', { name: /^STEP$/i }).click();

    await expect(
      page.locator('.text-red-300.font-mono').filter({ hasText: /EVENT_NAME_TOO_LONG/i }).first(),
    ).toBeVisible();
  });

  test('records audit events and supports trace export', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download');

    await page.getByRole('button', { name: /^STEP$/i }).click();
    await page.getByRole('button', { name: /^EXPORT$/i }).click();

    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^workflow-trace-.*\.json$/i);

    await expect(page.getByText(/\[step\] allow/i)).toBeVisible();
    await expect(page.getByText(/\[export\] allow/i)).toBeVisible();
  });

  test('redacts sensitive strings in exported trace payload', async ({ page }) => {
    const eventInput = page.getByPlaceholder('single step event');
    await eventInput.fill('user@example.com token-skABCDEF12345');
    await page.getByRole('button', { name: /^STEP$/i }).click();

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /^EXPORT$/i }).click();
    const download = await downloadPromise;
    const filePath = await download.path();
    expect(filePath).toBeTruthy();
    const content = await readFile(filePath as string, 'utf8');
    expect(content).toContain('[REDACTED_EMAIL]');
    expect(content).toContain('[REDACTED_TOKEN]');
    expect(content).not.toContain('user@example.com');
    expect(content).not.toContain('token-skABCDEF12345');
  });

  test('saves and restores trace snapshots', async ({ page }) => {
    await page.getByRole('button', { name: /^STEP$/i }).click();
    await expect(page.getByText('No transitions executed yet.')).toBeHidden({ timeout: 10_000 });

    const snapshotNameInput = page.getByPlaceholder('snapshot name (optional)');
    await snapshotNameInput.fill('baseline-step');
    await page
      .getByRole('heading', { name: 'Trace Snapshots' })
      .locator('..')
      .getByRole('button', { name: /^SAVE$/i })
      .click();

    await expect(
      page.getByRole('button', { name: /baseline-step/i }).first(),
    ).toBeVisible();
    await page.getByRole('button', { name: /^RESET$/i }).click();
    await page.getByRole('button', { name: /baseline-step/i }).click();

    await expect(page.getByText(/\[restore\] allow/i)).toBeVisible();
    await expect(page.getByText('No transitions executed yet.')).toBeHidden();
  });
});
