const { expect } = require('@playwright/test');

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
  await page.getByPlaceholder('Enter username').fill(username);
  await page.getByPlaceholder('Enter password').fill(passwordFor(username));
  await page.locator('form button[type=submit]').click();
  await expect(page).not.toHaveURL(/\/login/);
}

async function apiToken(request, username) {
  const res = await request.post('/api/v1/auth/login', { data: { username, password: passwordFor(username) } });
  expect(res.ok(), `API sign-in as ${username}`).toBeTruthy();
  return (await res.json()).data.access_token;
}

module.exports = { apiToken, signIn, signInAsGuest };
