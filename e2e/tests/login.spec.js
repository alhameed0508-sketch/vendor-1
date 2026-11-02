// The login page and the home page behind it. Read-only, so safe on production.
const { test, expect } = require('@playwright/test');
const { signInAsGuest } = require('./helpers');

const overflow = page => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
const filterGroup = (page, name) => page.getByRole('group', { name });

test.describe('login page', () => {
  test('the hero says what the product does, beside the sign-in form', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { level: 1, name: 'Trace mule accounts. Close fraud complaints on time.' })).toBeVisible();
    await expect(page.getByRole('img', { name: /three source accounts feed one aggregator/ })).toBeVisible();
    await expect(page.getByRole('list', { name: 'What MuleCatch gives you' })).toContainText('Hash-chained evidence');
    await expect(page.getByRole('heading', { name: 'Sign in to MuleCatch' })).toBeVisible();
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

  test('"Forgot password?" answers on the page', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: 'Forgot password?' }).click();
    await expect(page.getByRole('note')).toHaveText('Password resets go through your bank administrator.');
  });

  test.describe('on a phone', () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

    test('the form fits, and a short brand line replaces the hero', async ({ page }) => {
      await page.goto('/login');
      await expect(page.getByRole('heading', { name: 'Sign in to MuleCatch' })).toBeVisible();
      await expect(page.getByRole('heading', { level: 1 })).toBeHidden();
      await expect(page.locator('.login-brand--compact')).toBeVisible();
      expect(await overflow(page)).toBe(0);
    });
  });
});

test.describe('home page', () => {
  test('a guest sees the alert cards, and the filters narrow the table', async ({ page }) => {
    await signInAsGuest(page);
    await expect(page.getByRole('heading', { level: 1, name: 'Alerts' })).toBeVisible();
    for (const label of ['Critical', 'High severity', 'Open cases', 'Total flagged']) {
      await expect(page.locator('.stat-card', { hasText: label }).first()).toBeVisible();
    }

    // A cold server can take a while to score the first alerts.
    await expect(page.locator('.loading')).toBeHidden({ timeout: 45_000 });
    await filterGroup(page, 'Severity').getByRole('button', { name: 'High', exact: true }).click();
    await expect(filterGroup(page, 'Severity').getByRole('button', { name: 'High', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('tbody tr .col-sev .badge').first()).toBeVisible();
    const badges = await page.locator('tbody tr .col-sev .badge').allTextContents();
    expect(new Set(badges)).toEqual(new Set(['HIGH']));
  });

  test.describe('on a phone', () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

    test('the cards and filters fit the screen', async ({ page }) => {
      await signInAsGuest(page);
      await expect(page.locator('.stat-card', { hasText: 'Total flagged' })).toBeVisible();
      expect(await overflow(page)).toBe(0);
    });
  });
});
