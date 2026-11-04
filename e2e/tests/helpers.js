const { expect } = require('@playwright/test');

// E2E_API_URL points API calls at a backend other than the page's own origin (a local dev stack on other ports).
const API = process.env.E2E_API_URL || '';

// Passwords come from the environment only, never from this repo.
function passwordFor(username) {
  const password = process.env[`E2E_${username.toUpperCase()}_PASSWORD`];
  if (!password) throw new Error(`Set E2E_${username.toUpperCase()}_PASSWORD to sign in as ${username}`);
  return password;
}

async function signInAsGuest(page) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'View as guest' }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

async function signIn(page, username) {
  await page.goto('/login');
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Password', { exact: true }).fill(passwordFor(username));
  await page.locator('form button[type=submit]').click();
  await expect(page).not.toHaveURL(/\/login/);
}

async function apiToken(request, username) {
  const res = await request.post(`${API}/api/v1/auth/login`, { data: { username, password: passwordFor(username) } });
  expect(res.ok(), `API sign-in as ${username}`).toBeTruthy();
  return (await res.json()).data.access_token;
}

module.exports = { API, apiToken, signIn, signInAsGuest };
