// Read-only journeys through the Fraud Complaint Desk. Safe to run against prod.
const fs = require('node:fs');
const { test, expect } = require('@playwright/test');
const { signIn, signInAsGuest } = require('./helpers');

const SIM_SWAP_CASE = '/complaints/FC-2027-000101';
const SHARED_OTP_CASE = '/complaints/FC-2027-000102';
const overflow = page => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

test.describe('as a guest', () => {
  test.beforeEach(async ({ page }) => signInAsGuest(page));

  test('the sidebar opens the desk with its RBI counts', async ({ page }) => {
    await page.getByRole('link', { name: 'Fraud complaints' }).click();
    await expect(page).toHaveURL(/\/complaints$/);
    await expect(page.getByRole('heading', { name: 'Fraud complaints' })).toBeVisible();
    await expect(page.getByText('Compensation to pay')).toBeVisible();
    await expect(page.getByText('₹21,250')).toBeVisible();
    // most urgent first: the overdue case leads the list
    await expect(page.locator('a[href^="/complaints/FC-"]').first()).toHaveAttribute('href', '/complaints/FC-2027-000105');
    await expect(page.getByText('3 days overdue')).toBeVisible();
  });

  test('a case shows its live workflow, mule link and recommendation', async ({ page }) => {
    await page.goto(SIM_SWAP_CASE);
    await expect(page.getByRole('heading', { level: 1, name: 'Kavitha Raman' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Live workflow' })).toBeVisible();
    await expect(page.getByText('Hash chain intact')).toBeVisible();
    await expect(page.locator('.fc-big', { hasText: 'Customer pays nothing' })).toBeVisible();
    await expect(page.getByText('Sign in as bank staff to add evidence here.')).toBeVisible();
    await expect(page.getByRole('button', { name: /Evidence pack/ })).toHaveCount(0);

    // The mule beneficiary links to a real MuleCatch alert.
    const muleLink = page.getByRole('link', { name: /MuleCatch alert ALT_/ });
    const alertId = (await muleLink.textContent()).match(/ALT_\w+/)[0];
    await muleLink.click();
    await expect(page).toHaveURL(new RegExp(`/alert/${alertId}$`));
    await expect(page.getByText(alertId).first()).toBeVisible();
  });

  test('replay and the scrubber step through the evidence', async ({ page }) => {
    await page.goto(SIM_SWAP_CASE);
    await page.getByRole('button', { name: 'Replay the case' }).click();
    await expect(page.getByText(/Step 1 of 6/)).toBeVisible();
    await expect(page.getByText(/Step 2 of 6/)).toBeVisible();
    await page.getByRole('button', { name: 'Pause' }).click();

    await page.getByLabel('Step through the evidence').fill('3');
    await expect(page.getByText('Step 3 of 6')).toBeVisible();
    await expect(page.locator('.fc-events > li')).toHaveCount(3);

    await page.getByLabel('Step through the evidence').fill('6');
    await expect(page.getByText('Live', { exact: true })).toBeVisible();
    await expect(page.locator('.fc-events > li')).toHaveCount(6);
  });
});

test.describe('as bank staff', () => {
  test('an investigator downloads the evidence pack as a PDF', async ({ page }) => {
    await signIn(page, 'investigator');
    await page.goto(SHARED_OTP_CASE);
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: /Evidence pack \(PDF\)/ }).click(),
    ]);
    expect(download.suggestedFilename()).toBe('FC-2027-000102_evidence_pack.pdf');
    const head = fs.readFileSync(await download.path()).subarray(0, 5).toString();
    expect(head).toBe('%PDF-');
  });

  test('an admin signs in through the form and sees the decision form', async ({ page }) => {
    await signIn(page, 'admin');
    await page.goto('/complaints/FC-2027-000107');
    await expect(page.getByRole('heading', { level: 1, name: 'Lakshmi Narayanan' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Record decision' })).toBeVisible();
  });
});

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

  test('the desk and a case fit the screen', async ({ page }) => {
    await signInAsGuest(page);
    await page.goto('/complaints');
    await expect(page.getByText('Compensation to pay')).toBeVisible();
    expect(await overflow(page)).toBe(0);
    await page.goto(SIM_SWAP_CASE);
    await expect(page.getByRole('heading', { name: 'Live workflow' })).toBeVisible();
    expect(await overflow(page)).toBe(0);
  });
});
