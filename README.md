# Netrava IntentLock

**Purchase intent integrity for AI commerce.** An AI assistant may recommend and prepare a purchase. IntentLock checks that the final order stays inside what the buyer confirmed, and the backend asks PayPal to capture only if it does.

Built for the PayPal AI Hackathon 2026. PayPal runs in **Sandbox**: no real money moves. The product catalogue is **synthetic**.

## The problem

A payment can be technically valid and still not be what the buyer asked an AI agent to do. The agent can pick a different model, go over budget once tax and shipping are added, choose a seller the buyer did not approve, or be steered by text hidden in a product description. Today the merchant cannot show what the buyer actually authorised.

## What IntentLock does

1. The buyer describes a purchase. The AI turns it into a **draft mandate**: product, condition, quantity, specifications, budget, seller rule, expiry.
2. The buyer reviews the exact terms and **confirms**. The confirmed version is hashed (SHA-256) and can never be edited; a change makes a new version that must be confirmed again.
3. A product is proposed, by the buyer or by the AI assistant. The server builds the **quote** and a **deterministic policy engine** checks it rule by rule: `ALLOW`, `BLOCK`, `REAUTHORISE` or `REVIEW`.
4. Only on `ALLOW` does the server create a **PayPal order** from the stored quote.
5. The buyer approves in PayPal. The server then **fetches the order from PayPal again** and re-checks order ID, approval status, payee, currency, amount, line item, mandate status and the full policy.
6. Only if every check passes does the server **capture**. Otherwise nothing is captured and the failed rule is shown.
7. A verified **PayPal webhook** is reconciled against the capture, and a **receipt** links instruction, mandate, checks, PayPal order, capture and audit trail.

## What the AI does, and does not do

| The AI may | The AI may not |
|---|---|
| Draft a mandate from the buyer's words | Confirm or change a mandate |
| Ask for missing information | Decide or override a policy result |
| Propose a product from the catalogue | Set an amount, currency or payee |
| Explain stored records in plain language | Call PayPal, capture, refund, or mark anything paid |

Model output is validated by code before use. Catalogue descriptions are passed to the model as quoted, untrusted data and are never passed to the explanation step. If the model is unavailable the buyer fills in the same form by hand; there is no mock AI. These measures reduce the risk of prompt injection; they do not make a model immune to it. The payment decision does not depend on the model at all.

## Architecture

A modular monolith: one FastAPI process that also serves the React build.

```text
React (4 screens) ──HTTPS/JSON──> FastAPI  intentlock/api
                                   ├─ services/   mandates, catalogue, purchases, checkout, webhooks, receipts, audit
                                   ├─ policy/     pure rule engine (no I/O, versioned)
                                   ├─ payments/   provider interface + PayPal adapter
                                   ├─ ai/         model client, intent parser, proposer, explainer
                                   └─ db/         SQLAlchemy models + Alembic migrations
                                          │
                              PostgreSQL (source of truth)        PayPal REST (OAuth, Orders v2, webhooks)
```

- **PostgreSQL is the source of truth.** The provenance graph is derived from its rows; there is no separate graph database.
- **Fail closed.** If the order cannot be retrieved, a rule cannot be evaluated or the engine errors, nothing is captured.
- **Idempotency.** Order creation and capture each use a stored `PayPal-Request-Id`. A lost capture response is reconciled with PayPal before any retry.
- **Audit trail.** Append-only and hash-chained; every row carries the hash of the one before it.
- Every table has a `tenant_id`, and payments go through a provider interface, so more merchants and providers can be added without a rewrite.

## Run it locally

Requires Python 3.12 and Node 20.

```bash
python -m venv .venv
.venv/Scripts/pip install -r intentlock/requirements-dev.txt      # macOS/Linux: .venv/bin/pip
cp .env.example .env                                              # then fill in the values
cd frontend && npm ci --legacy-peer-deps && npm run build && cd ..
.venv/Scripts/python -m uvicorn intentlock.main:app --port 8000
```

Open http://localhost:8000. Migrations run at start-up. With `DATABASE_URL` empty a local SQLite file is used and the app says so on every page; that is for trying it out only.

Docker: `docker build -f intentlock/Dockerfile -t intentlock . && docker run --env-file .env -p 8000:8000 intentlock`

### Settings

See `.env.example`. The ones that matter:

| Variable | Purpose |
|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | REST app credentials from a Sandbox business account. Required; the app refuses to start without them. |
| `PAYPAL_ENV` | `sandbox` (default) or `live` |
| `PAYPAL_WEBHOOK_ID` | Needed to verify webhooks. Without it webhooks are refused. |
| `DATABASE_URL` | PostgreSQL URL. Required when `APP_ENV=production`. |
| `SESSION_SECRET` | 32+ characters. Required when `APP_ENV=production`. |
| `GENAI_PROVIDER`, `GENAI_API_KEY`, `GENAI_MODEL` | AI drafting. Gemini is the implemented provider. Optional: without a key the manual form is used. |
| `DEMO_TOOLS` | `true` shows the "change the PayPal order" button for Scenario C. Off by default. |

### PayPal Sandbox setup

1. At developer.paypal.com, open **Apps & Credentials** in Sandbox mode and create a REST app. Copy the client ID and secret into `.env`.
2. Under **Testing Tools → Sandbox Accounts**, note the email and password of a **Personal** (buyer) account. Use it to approve payments in the checkout.
3. After deploying to a public HTTPS address, add a webhook on the app with the URL `https://<your-host>/api/v1/paypal/webhooks` and these events: `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.DENIED`, `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.REFUNDED`. Put the webhook ID in `PAYPAL_WEBHOOK_ID`.

## Tests

```bash
.venv/Scripts/python -m pytest
```

78 tests: every policy rule, the purchase flow, order tampering, lost capture responses, duplicate requests, webhook verification and ordering, mandate immutability, access control, and the limits on the AI. They run against an in-memory database and a fake payment provider that behaves like PayPal Orders v2.

### What has been run against the real PayPal Sandbox

| Verified live | |
|---|---|
| OAuth token | |
| Order creation from the stored quote | |
| Same request ID returns the same order | |
| Order retrieval; payee and amount read back | |
| Capture before buyer approval is refused by PayPal (`ORDER_NOT_APPROVED`) | |
| Changing an order's amount after creation (used by Scenario C) | |
| Buyer approval, capture and a signature-verified webhook on the deployed site (done by hand by the team) | |

## Demo scenarios

| | Steps | Expected |
|---|---|---|
| **A. Valid purchase** | Use the first example request, confirm, select *Aster Book 14*, pay with the Sandbox buyer | Captured; receipt issued |
| **B. Policy violation** | Same mandate; check *Orion 14 Pro* or *Vega 15* | `BLOCK` with the failed rule; no PayPal order is created |
| **C. Order changed after approval** | Set `DEMO_TOOLS=true`; on the checkout press the demo button, then approve in PayPal | Final verification fails on `ORDER_AMOUNT`; nothing is captured |
| **D. Prompt injection** | *Orion 14 Pro*'s description tells AI assistants to ignore the budget | The mandate is unchanged and the decision is still `BLOCK` |
| **E. Duplicates** | Press "Check now" twice; PayPal retries a webhook | One capture, one processed event |

## Known limitations

- IntentLock controls only purchases routed through an application that integrates it. It cannot intercept other PayPal payments or agents working outside this integration.
- One merchant, one purchase unit per order, USD, and a controlled demo catalogue. No marketplace payouts.
- PayPal is the payment record. Product specifications are verified against the catalogue and the stored quote, not against PayPal.
- A receipt hash is a tamper-evident fingerprint and an HMAC signature from this service. It is not a legal digital signature or proof of the buyer's identity.
- The buyer session is a signed cookie created on first visit. There are no user accounts yet.
- Rate limiting is in-process, so it assumes one server instance.
- Not production-certified. No claims are made about fraud detection or dispute outcomes.

## Licence

MIT. See `LICENSE`.

## More

The implementation plan, migration report and product roadmap are in `docs/intentlock/IMPLEMENTATION_PLAN.md`.
