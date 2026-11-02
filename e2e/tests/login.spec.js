// The login page and the home page behind it. Read-only, so safe on production.
const { test, expect } = require('@playwright/test');
const { signInAsGuest } = require('./helpers');

const overflow = page => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
const filterGroup = (page, name) => page.getByRole('group', { name });

test.describe('login page', () => {
  test('the hero says what the product does, beside the sign-in form', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByText('Enterprise Financial Intelligence')).toBeVisible();
    await expect(page.locator('.lg-hero svg')).toBeVisible();
    await expect(page.locator('.lg-hero')).toContainText('Hash-chained evidence');
    await expect(page.getByRole('heading', { name: 'Sign In to MuleCatch' })).toBeVisible();
    expect(await overflow(page)).toBe(0);
  });

  test('Sign In waits for both fields, and a wrong login shows an alert', async ({ page }) => {
    await page.goto('/login');
    const submit = page.getByRole('button', { name: /^Sign In/ });
    await expect(submit).toBeDisabled();
    await page.getByLabel('Username', { exact: true }).fill('e2e-nobody');
    await expect(submit).toBeDisabled();
    await page.getByLabel('Password', { exact: true }).fill('not-a-real-password');
    await expect(submit).toBeEnabled();
    await submit.click();
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('"Forgot Password?" points to the administrator', async ({ page }) => {
    await page.goto('/login');
    const dialog = page.waitForEvent('dialog');
    await page.getByRole('button', { name: 'Forgot Password?' }).click();
    const popup = await dialog;
    expect(popup.message()).toContain('contact your FIU Security Administrator');
    await popup.dismiss();
  });

  test.describe('on a phone', () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

    test('the form fits, and a short brand line replaces the hero', async ({ page }) => {
      await page.goto('/login');
      await expect(page.getByRole('heading', { name: 'Sign In to MuleCatch' })).toBeVisible();
      await expect(page.locator('.lg-hero')).toBeHidden();
      await expect(page.locator('.lg-mobile-brand')).toBeVisible();
      expect(await overflow(page)).toBe(0);
    });
  });
});

test.describe('home page', () => {
  test('a guest sees the alert cards, and the filters narrow the table', async ({ page }) => {
    await signInAsGuest(page);
    await expect(page.getByRole('heading', { level: 1, name: 'Alert Queue' })).toBeVisible();
    for (const label of ['Critical', 'High Severity', 'Open Cases', 'Total Flagged']) {
      await expect(page.locator('.premium-card', { hasText: label }).first()).toBeVisible();
    }

    // A cold server can take a while to score the first alerts.
    await expect(page.locator('.loading')).toBeHidden({ timeout: 45_000 });
    await filterGroup(page, 'Severity').getByRole('button', { name: 'HIGH', exact: true }).click();
    await expect(filterGroup(page, 'Severity').getByRole('button', { name: 'HIGH', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('tbody tr .col-sev .badge').first()).toBeVisible();
    const badges = await page.locator('tbody tr .col-sev .badge').allTextContents();
    expect(new Set(badges)).toEqual(new Set(['HIGH']));
  });

  test.describe('on a phone', () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

    test('the cards and filters fit the screen', async ({ page }) => {
      await signInAsGuest(page);
      await expect(page.locator('.premium-card', { hasText: 'Total Flagged' })).toBeVisible();
      expect(await overflow(page)).toBe(0);
    });
  });
});
