# MuleCatch browser tests

Playwright tests for the login page, the home page and the Fraud Complaint Desk. They live in their own folder so the frontend build is untouched.

## Run

```bash
cd e2e
npm install
npx playwright install chromium   # or set E2E_CHROMIUM to an installed Chromium
E2E_BASE_URL=https://mulecatch.vercel.app \
E2E_INVESTIGATOR_PASSWORD=... E2E_SUPERVISOR_PASSWORD=... E2E_ADMIN_PASSWORD=... \
npx playwright test
```

| Variable | Meaning |
|---|---|
| `E2E_BASE_URL` | App to test. Default `http://localhost:3000` |
| `E2E_INVESTIGATOR_PASSWORD`, `E2E_SUPERVISOR_PASSWORD`, `E2E_ADMIN_PASSWORD` | Demo logins. Read from the environment only, never stored in the repo |
| `E2E_ALLOW_WRITES` | Set to `1` to run the lifecycle test, which creates a case. Never set it against production |
| `E2E_CHROMIUM` | Path of an installed Chromium |

## Tests

| File | Covers | Safe on production |
|---|---|---|
| `tests/login.spec.js` | Login hero and form, wrong-login alert, forgot-password note, home page cards and filters, phone widths | Yes, read-only (one failed sign-in as a user that does not exist) |
| `tests/complaints.spec.js` | Desk counts, case page, mule link, replay and scrubber, PDF pack, admin sign-in, phone width | Yes, read-only |
| `tests/complaints-write.spec.js` | New case, partner evidence arriving live, evidence added in the form, supervisor decision | No |

## Local app

Start the backend with `AUTH_ENABLED=true`. Without it the login page is skipped and the role tests cannot sign in. The local demo logins are the development defaults in `infra/security/auth.py`.
