# Netrava IntentLock: implementation plan

Written 11 Nov 2026 from `NETRAVA_INTENTLOCK_RECONSTRUCTION.md` and an audit of this checkout.
Status when written: Phase 0 done. Since then the submission build (section 7) has been implemented and deployed, and the earlier MuleCatch files were removed from this repository; sections 2 and 3 describe the repository as it was before that.

## 1. Summary

1. **The spec's core chain is the right product.** Intent, confirmed mandate, quote, policy check, PayPal order, buyer approval, server-side recheck, capture, verified webhook, receipt. This plan keeps it.
2. **The hackathon closes in about 40 hours.** Listing sites give 12 Nov 2026, 12:00 PM Pacific, which is 13 Nov, 1:30 AM IST. PayPal's own post says "through Nov 12" with no time. The Devpost rules page blocked automated reading, so please confirm the time there.
3. **So there are two horizons.** Horizon 1 is a submission build that fits the deadline (section 7). Horizon 2 turns it into something a company can buy (section 8). Horizon 1 is built on the seams Horizon 2 needs, so nothing is thrown away.
4. **Main change to the spec: IntentLock becomes its own package and its own app**, not new routes inside the MuleCatch app. Reasons are in section 4, item 1.
5. **Eight things are needed from you** before building starts (section 9). The first three block the PayPal work.

## 2. Phase 0 results

| Check | Result |
|---|---|
| Checkout inspected | `alhameed0508-sketch/buildx`, commit `57ee36f` (same as `buildx/railway`, the deployed branch) |
| Spec's inspected repo | `Shahid-2705/mulecatch@backup-shahid-ui`. Not available here, so it was not inspected. If it has UI work you want, say so. |
| Working copy | Moved out of the temp folder to `mule catch/netrava-intentlock`. The temp copy had lost 32 empty `__init__.py` files to Windows temp cleanup. |
| Branch | `paypal-intentlock`, local only |
| Backup | Tag `mulecatch-baseline-2026-11-11` on `57ee36f`. `master` and `railway` are untouched. |
| Baseline tests | 1,049 passed, 5 skipped in 39 s. Two test files (`test_focal_loss.py`, `test_gnn_directed.py`) could not be imported because `torch` is not installed locally, so they were left out. |
| App start | Not started in a browser in this phase. The test suite builds the FastAPI app in-process and passes. |
| Size of the existing app | 368 Python files, 178 frontend source files, 76 test files, 25 API routers, 23 React routes. All of it is the bank product. |
| Write access | Push remote is `buildx` only. Nothing pushed. |

## 3. Migration report

### Reuse (copy the pattern into the new package; these are small, generic files)

| Existing file | Use |
|---|---|
| `backend/core/response.py`, `error_handlers.py`, `exceptions.py` | Response envelope and error handling |
| `backend/middleware/security_headers.py` | Security headers |
| `backend/core/rate_limiter.py` | Rate limits on parse, checkout, finalize, webhook |
| `backend/repositories/pg_audit_repository.py` | Hash-chained, append-only audit log with an advisory lock. This is the model for `audit_events`. |
| `railway/serve.py`, `railway/Dockerfile` | One container serving the API and the React build, with start-up safety checks |
| `frontend/` build setup (CRA + craco), `components/ui`, `ErrorBoundary`, `ThemeContext` | UI base |
| `d3` (already installed) | Purchase provenance graph. No Cytoscape needed. |

### Extend

| Existing | Change needed |
|---|---|
| `backend/genai/` (Gemini, OpenAI, Anthropic providers) | `generate()` returns free text only. Add a structured-output call validated by Pydantic. The `TemplateProvider` fallback must not be reachable from IntentLock: the spec forbids a silent mock. |
| `.gitignore` | Line 67 (`.env*`) also ignores `.env.example`, which is why none is tracked. Add an exception. |

### Replace

| Existing | Why |
|---|---|
| `backend/api/app.py` app factory | Imports the Kafka consumer at load, wires the detection pipeline, and starts feed threads. A payments process should not carry that. |
| `backend/core/config.py` | Defaults include a bank name and IFSC, `JWT_SECRET=change_me_before_deployment`, `AUTH_ENABLED=false`, `GENAI_ENABLED=false`. New settings class with no insecure defaults. |
| `infra/database/init.sql` + `metadata.create_all` | No migrations exist. IntentLock tables get Alembic migrations. |
| `infra/security/auth.py` roles (guest, investigator, supervisor, admin) | Bank roles. New roles: buyer, merchant admin, platform admin. |
| `frontend/src/App.js` routes and sidebar | All 23 routes are bank screens. Replaced by the four IntentLock screens. |
| `README.md`, `PRODUCT.md` | Describe the bank product. |

### Isolate (stays in the repo, never imported by IntentLock)

Detection pipeline, rules, GNN and models (`backend/detection`, `models/`, `backend/fraud_modules`, `backend/intelligence`, `backend/return_fraud`), CBS and UPI ingestion, STR and FIU compliance, all existing routers and repositories, live feeds.

### Remove from the product build (files stay in git history and on `master`)

Kafka, Redis, Neo4j, Prometheus, Grafana, LDAP, the ML libraries, the bank-specific design-system folder, bank documents under `docs/`. Removing files from the branch needs your approval, so the first step only leaves them out of the new image.

### Problems found

- No `LICENSE` file and no `.env.example`.
- Two import roots (`core...` and `backend.infra...`) are both on `PYTHONPATH`, so one module can load twice under two names. A payments service should have one root.
- The Railway image installs the root `requirements.txt`, which has no PostgreSQL driver and no GenAI SDK. The deployed app is in-memory today.
- The local virtual environment is also in the temp folder. A new one is needed inside this folder.

## 4. Changes I recommend to the spec

1. **Own package, own app.** `intentlock/` with its own settings, app factory, requirements (about 9 packages instead of 30+) and Dockerfile. A test fails the build if `intentlock/` imports anything from the legacy tree. This gives a small image, a fast start, a clean licence boundary, and a folder that can move to its own repo in one step. The spec's "reuse the app factory and extend the v1 router" would put the whole bank stack inside the payment process.
2. **Split payment state from webhook state.** The spec makes `WEBHOOK_RECONCILED` a step before `RECEIPT_CREATED`. Sandbox webhooks can arrive minutes late. Keep `state` (ends at `CAPTURED`) and a separate `reconciliation_status` (`PENDING`, `VERIFIED`, `MISMATCH`). The receipt is issued at capture and shows the webhook status as it changes.
3. **Make the decision table deterministic.** The spec has rows such as "BLOCK / REAUTHORISE". Proposed rule: breaking a limit the buyer set (budget, seller, condition, category, minimum spec, expiry, payee) is `BLOCK`. A change to what the buyer approved that they could approve again (quantity, currency, substitution, final order differs from quote) is `REAUTHORISE`. Missing or unknown data is `REVIEW`. When several rules fire, the order is `BLOCK`, then `REAUTHORISE`, then `REVIEW`, then `ALLOW`.
4. **Scenario C can be real, not simulated.** PayPal allows an order to be patched while it is `CREATED` or `APPROVED`. A demo-only operator script patches the amount after buyer approval, and finalize then refuses to capture. Guarded by `DEMO_TOOLS=true`, off by default.
5. **No Neo4j.** The provenance graph is built from PostgreSQL rows and drawn with d3. The spec allows this, and it removes a database from what you have to run and sell.
6. **A manual mandate form next to the AI parser.** If the model is down or unsure, the buyer fills the same structured form by hand, and the mandate records `source: manual`. This is a real path, not a mock, and enterprise buyers will ask for it.
7. **Tenant column from the first migration.** Every table carries `tenant_id`, and `tenants` and `api_keys` tables exist with one seeded tenant. It costs minutes now and a rewrite later.
8. **A payment-provider interface.** `create_order`, `get_order`, `capture`, `verify_webhook`, with PayPal as the first adapter. Other providers become additions, not rewrites.
9. **Sign the receipt, not only hash it.** For submission: SHA-256 hash plus an HMAC signature with a key ID. For the product: an Ed25519 signature with a published public key, so a third party can verify a receipt without our secret.
10. **Money by currency exponent.** A small table (USD 2, JPY 0, KWD 3) and rejection of unknown currencies. Only USD is enabled.

## 5. What makes it a product someone buys

### 5.1 Who pays, and for what

The four screens in the spec are a demo storefront. The thing a company buys is the layer behind them.

| | |
|---|---|
| Customer | A company that lets an AI assistant prepare purchases and takes payment for them: AI shopping apps, merchants adding an assistant to their store, marketplaces. |
| Their problem | The assistant can buy the wrong thing, and the company cannot show what the buyer actually authorised. |
| What they get | An API that refuses to capture outside the confirmed mandate, and a signed receipt linking instruction, mandate, checks and payment. |
| How it is billed | Per verified purchase is the natural unit. Usage is metered from day one. No price is set in this plan. |
| First segment to test | Merchants on PayPal that are adding an AI assistant, because the PayPal adapter exists first. This is a guess until customers confirm it (5.4). |

### 5.2 Product surfaces

1. **REST API** (the spec's contract, plus API keys and an `Idempotency-Key` header on every POST).
2. **Confirmation widget**: a small embeddable page where the buyer reviews and confirms the mandate.
3. **Console** for the customer's team: mandates, evaluations, refused captures with the failed rule, receipts, API keys, webhook status.
4. **Outbound webhooks** to the customer (`mandate.confirmed`, `purchase.refused`, `capture.completed`).
5. **Reference storefront**: the four screens from the spec, used as the live demo and as sample code.

### 5.3 Where it sits in the market

- **AP2** (Google-led) defines an Intent Mandate and a Cart Mandate backed by verifiable credentials. Secondary sources disagree on the exact mandate names between versions, so the field mapping must be checked against the official spec.
- **PayPal Agent Ready** is access-by-request: PayPal's developer docs (updated 14 Oct 2026) ask merchants to contact PayPal through a form. The spec is right not to depend on it.
- These carry the buyer's authorisation between agent, merchant and network. IntentLock does a different job: it enforces that authorisation at the moment of capture inside the merchant's own checkout, and keeps the evidence. It works today with ordinary PayPal checkout.
- **Risk:** payment providers may build enforcement in. The defensible parts are the evidence record, working across providers, and policy the customer can configure.
- Mandate fields should map cleanly to AP2 so a signed AP2 mandate can be exported or accepted later.

### 5.4 What is not known yet

No customer has been asked. Before building past milestone M1, talk to about ten companies in the first segment and learn: do they see wrong purchases today, who owns the problem, would they put a third party in the capture path, and what proof their disputes team accepts.

## 6. Target layout

```text
intentlock/                  backend package, single import root
  domain/                    Pydantic models: mandate, offer, quote, checks, receipt
  policy/                    pure rules, no I/O, versioned (engine.py, rules.py)
  services/                  mandate, catalogue, quote, checkout, webhook, receipt, audit, metering
  payments/                  provider interface + paypal.py (OAuth, orders, capture, webhook verify)
  ai/                        intent parser, read-only explanation tools
  db/                        SQLAlchemy models, session, alembic/
  api/                       thin routes, auth, error envelope
  settings.py, app.py
  tests/                     unit (SQLite), integration (PostgreSQL), sandbox (live PayPal)
frontend/src/intentlock/     Intent Studio, Discovery, Execution Monitor, Receipt, console
deploy/                      Dockerfile, .env.example
docs/intentlock/             this plan, phase reports, API reference
```

Tests run on SQLite for speed and on PostgreSQL for locking and constraints. JSON columns use `JSONB` on PostgreSQL only.

## 7. Horizon 1: the submission build

Hours are estimates of focused work. The total is about 22 hours inside a 40-hour window, so it is tight and the cut line matters.

| # | Work | Hours | Done when | Needs |
|---|---|---|---|---|
| 1 | Package skeleton, settings, app, health, models, first migration, new venv | 2 | App boots, migration applies, health returns OK | Decision 1 |
| 2 | Mandate schema, canonical hash, confirm and version; policy engine | 3 | 10 rule tests from spec 15.1 pass; a confirmed version cannot change | nothing |
| 3 | Demo catalogue (valid item plus traps: over budget, wrong seller, used, missing spec, injected text), quote, evaluate | 2 | Scenario B refuses with a named rule and creates no PayPal order | nothing |
| 4 | PayPal: OAuth cache, create order, retrieve, the 10 finalize checks, capture, timeout reconciliation | 4 | Scenario A captures in Sandbox; changed amount, payee and currency do not; double finalize makes one capture | Decision 2 |
| 5 | Four React screens with the PayPal JS SDK | 4 | A buyer completes Scenario A and B in the browser | Row 4 |
| 6 | Webhook verify, dedupe, receipt, audit timeline | 2 | A real Sandbox event is verified once and shown on the receipt | Decision 4 |
| 7 | AI intent parser, clarification, injection test | 2 | Spec 15.4 tests pass; injected catalogue text changes nothing | Decision 3 |
| 8 | Deploy with HTTPS and PostgreSQL, README, licence, `.env.example` | 2 | Public URL runs Scenario A | Decisions 4, 5, 6 |
| 9 | Demo video and submission | 1 to 2 | Submitted with buffer | all |

**Order if two people work:** one takes rows 2, 3, 4 and 6 (backend), the other takes rows 5 and 9 (frontend and video) against the API contract in spec section 12.

**Cut line.** If the PayPal capture is not working by Thursday 12 Nov, 12:00 IST, drop in this order: provenance graph, AI explanation tools, Channel3, AG Grid, Scenario C, then the AI parser (the manual form remains). Never drop real capture, the refused purchase, or labels on anything simulated.

**Sponsor prizes** (optional, only after rows 1 to 6): Channel3 catalogue search, an AG Grid ledger in the console, deployment on Render. Each adds a dependency or a platform, so each needs your yes.

**Submission checklist** (from listing sites, to confirm on Devpost): public repo, open-source licence, working demo URL or run steps, public video (one source says under three minutes), and a note on what changed after 1 Oct 2026 because this started from an existing project.

## 8. Horizon 2: from submission to something sold

Durations are estimates.

| Milestone | Scope | Done when |
|---|---|---|
| **M1 Pilot-ready** (2 to 3 weeks) | API keys per tenant, per-tenant PayPal credentials encrypted at rest, console v1, background reconciliation job, structured logs with correlation IDs, Ed25519 receipts with a public verify endpoint, data retention settings, load and failure tests | A second company can be onboarded without a code change, and every capture is traceable from one ID |
| **M2 Design partners** (4 to 8 weeks) | Confirmation widget, outbound webhooks, usage metering, policy settings per tenant, quickstart docs and sandbox keys, refund flow, ten customer interviews | Two or three companies run it in their sandbox and one runs live traffic |
| **M3 Sellable v1** (about a quarter) | Second payment provider, AP2 mandate import and export, passkey-signed buyer confirmation, SSO and roles for the console, uptime target and status page, security review, privacy documents, billing | A signed contract, and a security questionnaire answered without gaps |
| **M4 Scale** | Multi-region, policy packs per vertical, analytics on refused purchases, partner channel | Driven by customer demand |

## 9. Decisions and inputs needed

1. **Go-ahead to add dependencies and create the schema.** `alembic`, a PostgreSQL driver, and the SDK for the chosen AI provider. The schema is new tables only; no existing table changes.
2. **PayPal Sandbox credentials.** A REST app client ID and secret from a Sandbox business account, and a Sandbox personal (buyer) account. Put them in `netrava-intentlock/.env`, which is git-ignored. Do not paste them in chat.
3. **AI provider and key.** The existing code supports Gemini, OpenAI and Anthropic. Use whichever key you have.
4. **Where to deploy.** Railway with a PostgreSQL service (already familiar), or Render (sponsor prize). The webhook needs a public HTTPS URL either way.
5. **Which repo is submitted.** A branch of `buildx`, or a new public repo holding only IntentLock. I recommend the new repo: the legacy tree carries a bank's name in config defaults and design files, and a clean history shows the new work. This changes the standing rule to push only to `buildx`, so it is your call.
6. **Licence.** The rules appear to require an open-source licence. Every contributor to copied code must agree. MIT or Apache-2.0 both work. Note the trade-off: a permissive licence lets others reuse the core of a product you plan to sell.
7. **Who builds the frontend.** If your friend does, they can start from spec section 12 today.
8. **Later:** a trademark check on "Netrava" and "IntentLock", and PayPal's brand-use rules for marketing.

## 10. Risks

| Risk | Handling |
|---|---|
| Time | Rows 2 and 3 need no credentials and can start now; cut line in section 7 |
| Sandbox webhooks are late, or simulator events fail signature verification | Use real Sandbox events, not the simulator; the receipt does not wait for the webhook (section 4, item 2). The simulator point is from memory and will be checked in row 6. |
| Existing-project rule | Explain the post-1-Oct changes in the submission; a new repo makes this plain |
| The AI misreads the request | The buyer confirms the structured mandate; the engine, not the model, decides |
| Overclaiming | Say "does not capture outside the mandate for purchases routed through IntentLock". No claims about fraud, disputes won, or production readiness. |
| Personal data | Store the instruction text and IDs only; no card data reaches our servers because PayPal's SDK handles it |
| Payment providers ship this natively | Section 5.3 |

## 11. Sources

- PayPal AI Hackathon announcement: https://developer.paypal.com/community/blog/PayPal_AI_Hackathon
- Deadline time and submission items (listing sites, not the official rules): https://www.startupgrantsindia.com/paypal-ai-hackathon-2026 and https://internshala.com/competitions/?p=13021
- PayPal update-order (patch allowed in `CREATED` or `APPROVED`): https://developer.paypal.com/docs/api/orders/v2/orders-patch
- PayPal agentic commerce overview (access by request): https://developer.paypal.com/docsai/growth/agentic-commerce/overview
- AP2 overview (secondary): https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/concepts/protocols/ap2/ ; official site to check: https://ap2-protocol.org/
