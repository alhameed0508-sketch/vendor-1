// Login and home across real phone sizes: nothing spills sideways, taps are big enough, inputs do not zoom iOS.
const { test, expect } = require('@playwright/test');
const { signInAsGuest } = require('./helpers');

const PHONES = [
  { name: 'iPhone SE (320)', width: 320, height: 568 },
  { name: 'Galaxy S (360)', width: 360, height: 740 },
  { name: 'iPhone mini (375)', width: 375, height: 667 },
  { name: 'iPhone 14 (390)', width: 390, height: 844 },
  { name: 'Pixel (412)', width: 412, height: 915 },
  { name: 'iPhone Max (430)', width: 430, height: 932 },
  { name: 'landscape (844x390)', width: 844, height: 390 },
  { name: 'landscape small (667x320)', width: 667, height: 320 },
];
const MIN_TAP = 40;

const overflow = page => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

// Visible buttons, links and inputs smaller than MIN_TAP in either direction.
const smallTargets = (page, scope) => page.evaluate(({ scope, min }) => {
  const root = document.querySelector(scope) || document.body;
  return [...root.querySelectorAll('button, a[href], input, select')]
    .filter(el => el.offsetParent !== null)
    .map(el => ({ el, r: el.getBoundingClientRect() }))
    .filter(({ r }) => r.width > 0 && (r.height < min || r.width < min))
    .map(({ el, r }) => `${el.tagName.toLowerCase()}.${el.className || el.getAttribute('aria-label') || ''} ${Math.round(r.width)}x${Math.round(r.height)}`);
}, { scope, min: MIN_TAP });

for (const phone of PHONES) {
  test.describe(phone.name, () => {
    test.use({ viewport: { width: phone.width, height: phone.height }, isMobile: true, hasTouch: true });

    test('login: no sideways scroll, the form is reachable, taps are big', async ({ page }) => {
      await page.goto('/login');
      await expect(page.getByRole('heading', { name: 'Sign In to MuleCatch' })).toBeVisible();
      expect(await overflow(page)).toBe(0);
      const submit = page.getByRole('button', { name: /^Sign In/ });
      await submit.scrollIntoViewIfNeeded();
      await expect(submit).toBeInViewport();
      expect(await smallTargets(page, '.lg-form')).toEqual([]);
      const fontSize = await page.locator('#login-username').evaluate(el => parseFloat(getComputedStyle(el).fontSize));
      expect(fontSize).toBeGreaterThanOrEqual(16);
    });

    test('home: no sideways scroll, cards and filters fit', async ({ page }) => {
      await signInAsGuest(page);
      await expect(page.locator('.premium-card', { hasText: 'Total Flagged' })).toBeVisible();
      await expect(page.locator('.loading')).toBeHidden({ timeout: 45_000 });
      expect(await overflow(page)).toBe(0);
      const cards = await page.locator('.premium-card').evaluateAll(els => els.map(el => el.getBoundingClientRect()));
      for (const r of cards) expect(r.right).toBeLessThanOrEqual(phone.width);
      expect(await smallTargets(page, '.dash-filters')).toEqual([]);
    });
  });
}
