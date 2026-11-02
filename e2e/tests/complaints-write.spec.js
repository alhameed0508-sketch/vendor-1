// The full case lifecycle. It creates a case, so run it only where demo data may change.
const { test, expect } = require('@playwright/test');
const { apiToken, signIn } = require('./helpers');

test.skip(process.env.E2E_ALLOW_WRITES !== '1', 'Creates a case: set E2E_ALLOW_WRITES=1 on a local or staging app');

async function createCase(request, token) {
  const res = await request.post('/api/v1/complaints', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      customer_name: `E2E Customer ${Date.now()}`,
      account: 'AC_E2E_0001',
      channel: 'UPI',
      amount: 18000,
      occurred_at: '2027-02-27T10:00:00+05:30',
      reported_at: '2027-02-27T12:00:00+05:30',
      description: 'Created by the e2e suite',
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()).data;
}

const chainStage = page => page.locator('.fc-stage', { hasText: 'Evidence chain' });

test('partner evidence appears live, staff add evidence, a supervisor decides', async ({ browser, request }) => {
  const token = await apiToken(request, 'investigator');
  const created = await createCase(request, token);
  const casePath = `/complaints/${created.complaint_id}`;

  const investigator = await browser.newPage();
  await signIn(investigator, 'investigator');
  await investigator.goto(casePath);
  await expect(investigator.getByRole('heading', { level: 1, name: created.customer_name })).toBeVisible();
  await expect(chainStage(investigator)).toContainText('1 item');

  // A courier posts through the API while the page is open: it arrives without a reload.
  const posted = await request.post(`/api/v1${casePath}/evidence`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { source: 'COURIER', kind: 'delivery_confirmed', at: '2027-02-27T11:00:00+05:30',
            summary: 'E2E: courier delivery confirmed with OTP' },
  });
  expect(posted.ok(), await posted.text()).toBeTruthy();
  await expect(investigator.locator('.fc-events')).toContainText('E2E: courier delivery confirmed with OTP',
    { timeout: 15_000 });
  await expect(chainStage(investigator)).toContainText('2 items');

  // Staff add evidence through the form.
  await investigator.getByLabel('Summary', { exact: true }).fill('E2E: branch confirmed the login device');
  await investigator.getByRole('button', { name: 'Add to the chain' }).click();
  await expect(investigator.locator('.fc-events')).toContainText('E2E: branch confirmed the login device');
  await expect(chainStage(investigator)).toContainText('3 items');
  await expect(investigator.getByText('A supervisor records the decision. Sign in as one to decide this case.'))
    .toBeVisible();

  // A supervisor records the decision; the case closes to new evidence.
  const supervisor = await browser.newPage();
  await signIn(supervisor, 'supervisor');
  await supervisor.goto(casePath);
  await supervisor.getByLabel('Reasons', { exact: true }).fill('E2E: evidence reviewed');
  await supervisor.getByRole('button', { name: 'Record decision' }).click();
  await expect(supervisor.getByText(/^By supervisor/)).toBeVisible();
  await expect(supervisor.getByText('Within the time limit')).toBeVisible();
  await expect(supervisor.getByRole('heading', { name: 'Add evidence' })).toHaveCount(0);
});
