# Session record: login and home redesign, phones, CI, master

Date: 2026-11-02. Branch: `buildx-integrated` (the production source). Production: https://mulecatch.vercel.app.

This file records what was decided and done in one working session, so the next session can continue without the chat history.

## 1. What was asked, in order

1. Look at Shahid's pull request (PR #1, "Frontend UI Redesign", branch `frontend-only`) and bring its login page and home page into the project.
2. Make both pages work on all phones.
3. Push to `master` once verified.
4. Look at the two backend test errors and the PR conflicts, then fix the CI errors.
5. Close PR #1 and protect `master`.
6. Use Shahid's design exactly as he built it, integrated so it fits the project.
7. Save this context in the docs (this file).

## 2. What is on `master` and production

| Commit | What it did |
|---|---|
| `0ca3672` | Alert detail shows "Alert not found" instead of crashing when the alert no longer exists. |
| `35959e8` | First, adapted version of the PR's login and home page (later replaced, see below). |
| `ff79de3`, `d3c712e` | Playwright specs for login and home, 44px touch targets, a phone-size matrix test. |
| `1998120` | Merge of `origin/master` (kept our login page). |
| `c152778` | Ruff import-order fix. |
| `60d8042` | Ruff format on 14 files, PyJWT 2.15.0, fpdf2 2.8.8, so CI passes. |
| `acc2283` | Shahid's login and alert-queue design as he built it (on the branch and deployed, not yet on `master` when this was written). |

## 3. The redesign: decisions

The first pass adapted the PR heavily (new copy, own graphic, own CSS). The user then asked for the design exactly as built. The second pass therefore takes his two files and changes only what the project needs.

**Taken as built:** the two-panel login (hero, typewriter taglines, network graphic, form), the alert queue (premium cards, segmented filters, sortable table, j/k keyboard navigation), his Remember session checkbox and his Forgot Password pop-up, and his Severity and Status filter lists.

**Changed from his version, on purpose:**

| Change | Reason |
|---|---|
| Badges "AES-256 Encrypted", "ISO 27001 Certified", "RBI AML Compliant" and the footer "MuleCatch Intelligence Inc." replaced with true labels (role-based access, JWT sessions, hash-chained evidence, RBI complaint deadlines) | The product cannot back those claims, and they would hurt a pitch to banks. |
| Raw colours (`#10B981`, `#FFF`, `rgba(...)`) replaced with tokens | A guard test forbids raw colours in JS. The page also follows the emerald theme, not his blue. |
| Guest login added | A project feature his version lacked. |
| Alert links through `alertPath`, limits and thresholds from `config`, money through `formatAmount` | The project's own helpers: safe navigation, one rupee format. |
| Labels tied to inputs, `aria-label` on the eye toggle, `role="alert"` on the error | Accessibility, and the tests find fields by label. |
| `·` replaced by `|`, font weight 800 replaced by 700 | Project rules: no middle dots, only the loaded Plex weights. |
| Phone layer in `login/Login.css` and `App.css` | His layout is built for desktop. The layer hides the hero below 960px, shows a short brand row, puts the stat cards two across, stacks the filters, and sets 44px touch targets under `pointer: coarse`. |

His own CSS rules (`premium-card`, `meta-label`, `data-value`, `segmented-control`, `segmented-btn`, `enterprise-table`) were copied into `App.css` with hover rules behind `@media (hover: hover)`.

Files removed because the new version replaced them: `LoginHero.js`, `HeroGraphic.js`, `useTypewriter.js` and its test, `FilterGroup.js`. `StatCard.js` went back to its earlier form.

Not taken from the PR: the sidebar and light-theme changes, the hackathon pages (judge view, splash and others), and the `gsap` background.

## 4. Phones

The matrix test is `e2e/tests/phones.spec.js`. It checks login and home at 320, 360, 375, 390, 412 and 430 wide, plus two landscape sizes, for sideways scroll, tap targets of at least 40px, and a 16px input font (stops iOS zoom). Tap sizes are keyed to `pointer: coarse`, not width, because a phone in landscape is wider than 768px.

The matrix runs only against production (or a build with auth on). Locally the backend runs with auth off, so `/login` redirects into the app.

## 5. CI

CI (`.github/workflows/ci.yml`) runs on push to `master`: `backend-lint` (ruff check and ruff format), `backend-test`, `frontend-test`, `security-scan` (pip-audit).

| Failure | Cause | Fix |
|---|---|---|
| `backend-lint` | `ruff format --check` flagged 14 files | `ruff format backend/ models/` |
| `security-scan` | PyJWT 2.13.0 and fpdf2 2.8.3 had known vulnerabilities | PyJWT 2.15.0, fpdf2 2.8.8 in `backend/requirements.txt` |
| Local `test_focal_loss.py` and `test_gnn_directed.py` errors | The local venv has no `torch`. CI installs it. | None needed. Those tests pass in CI. |

Before pushing, run: `ruff check backend/ models/`, `ruff format --check backend/ models/`, and `pip-audit -r backend/requirements.txt` (use a throwaway venv).

## 6. GitHub state

- PR #1 (Shahid) is closed with a note pointing to where its design landed. The `frontend-only` branch is untouched.
- `master` is protected: no force-push, no deletion, required checks `backend-lint`, `backend-test`, `frontend-test`, `security-scan`. Admins are not enforced, so direct pushes by the owner still work. Pull requests and reviews are not required.
- Merging `origin/master` into `buildx-integrated` needs care. `git merge -X ours` still pulls in non-conflicting hunks from the other side, so restore the file explicitly with `git checkout HEAD^1 -- <file>` and amend.

## 7. Deploy flow

1. `git archive HEAD | tar -x -C <scratch>/deploy`
2. Copy `.vercel/project.json` into `<scratch>/deploy/.vercel/`.
3. `cd <scratch>/deploy && vercel deploy --prod --yes` (needs the sandbox off).
4. Smoke test: `/health` returns 200, alerts without a token return 401, guest login returns 200.
5. Run the Playwright suite from `e2e/` against production.

Do not pipe `vercel deploy` through `head`. Demo passwords are only in Vercel env and `~/Documents/mulecatch/vercel-demo-logins.txt` (mode 600). Never put them in source or docs.

## 8. Known gotchas

- Alert IDs are random on every pipeline run. A persisted fraud complaint can point to an alert that no longer exists after a restart or serverless cold start. The API then answers 404 with the error envelope, and the alert detail page now says "Alert not found".
- A cold production server can take several seconds to load the first alerts. E2E specs wait for the loader to disappear before reading the table.
- `pkill -f "uvicorn api.app"` kills the shell that runs it. Use `pkill -f "[u]vicorn api.app"` or stop the task.
- The frontend guard tests forbid raw colours in JS, unguarded `:hover` in `App.css`, font weights above 700, and low-contrast accent colours. Run `CI=true npx craco test --watchAll=false` in `frontend/` before committing.

## 9. Open items when this was written

- Run the Playwright suite and the phone matrix against production for `acc2283`, and look at the pages in a browser.
- Push `acc2283` and this file to `master` once that passes, then check the CI run.
- Decide whether to restore his original badge text, his blue palette, or the "False positive" and "STR filed" filters. Each was a deliberate change, listed in section 3.
- Optional: a pitch deck for selling the complaint desk to banks.
