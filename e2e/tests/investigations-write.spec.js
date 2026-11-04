// The analyst journey: alert, investigation, outcome, simulated hold, audit trail. It creates an investigation, so run it only where demo data may change.
const { test, expect } = require('@playwright/test');
const { API, apiToken, signIn } = require('./helpers');

test.skip(process.env.E2E_ALLOW_WRITES !== '1', 'Creates an investigation: set E2E_ALLOW_WRITES=1 on a local or staging app');

const card = (page, caseId) => page.locator('article.investigation', { hasText: caseId });

test('an alert goes from New to Resolved with an outcome, and the audit chain still verifies', async ({ page, request }) => {
  const supervisorToken = await apiToken(request, 'supervisor');
  const headers = { Authorization: `Bearer ${supervisorToken}` };

  const alerts = await request.get(`${API}/api/v1/alerts?limit=1`, { headers });
  expect(alerts.ok(), await alerts.text()).toBeTruthy();
  const alertId = (await alerts.json()).data.alerts[0].alert_id;

  await signIn(page, 'investigator');
  await page.getByRole('link', { name: 'Investigations' }).first().click();
  await expect(page).toHaveURL(/\/investigations$/);

  await page.getByLabel('Case ID').fill(alertId);
  await page.getByRole('button', { name: 'Open investigation' }).click();
  const item = card(page, alertId);
  await expect(item.getByText('New', { exact: true })).toBeVisible();

  // Only the next legal step is offered, so Resolved is not on the card yet.
  await expect(item.getByRole('button', { name: 'Resolved' })).toHaveCount(0);
  await item.getByRole('button', { name: 'Under review' }).click();
  await item.getByRole('button', { name: 'Investigating' }).click();

  // Resolving needs an outcome first.
  await expect(item.getByRole('button', { name: 'Resolved' })).toBeDisabled();
  await item.getByLabel('Outcome').selectOption('FALSE_POSITIVE');
  await item.getByRole('button', { name: 'Resolved' }).click();
  await expect(item.getByText('Resolved', { exact: true })).toBeVisible();
  await expect(item).toContainText('false positive');

  // The hold is recorded only, and the page says so.
  await item.getByLabel('Account').fill('E2E-ACCOUNT');
  await item.getByRole('button', { name: 'Request hold' }).click();
  await expect(item.getByText('SIMULATED: no bank system connected')).toBeVisible();

  // Every step above is in the audit trail, and the hash chain is intact.
  const log = await request.get(`${API}/api/v1/audit-log?alert_id=${alertId}`, { headers });
  const actions = (await log.json()).data.map(e => e.action);
  expect(actions).toEqual(expect.arrayContaining([
    'INVESTIGATION_OPENED', 'INVESTIGATION_UNDER_REVIEW', 'INVESTIGATION_INVESTIGATING',
    'INVESTIGATION_RESOLVED', 'INTERVENTION_REQUESTED',
  ]));
  const integrity = await request.get(`${API}/api/v1/audit-log/integrity`, { headers });
  expect((await integrity.json()).data.valid).toBe(true);
});
