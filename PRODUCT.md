# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary: the merchant's team** (confirmed 12 Nov 2026). Store operators at a company that lets AI assistants prepare purchases and takes payment through PayPal. They watch every agent purchase across all buyers: what was proposed, what the rules allowed or refused, what was paid, and whether PayPal confirmed it.
- **Secondary: the buyer.** Sets the purchase terms (the mandate), confirms them, and pays in PayPal. Their flow lives inside the console.
- **Evaluators:** hackathon judges and prospective customers who open the live site without an account and must understand the product quickly.

## Product Purpose

An AI assistant may recommend and prepare a purchase; IntentLock makes sure the payment is captured only if the final PayPal order stays inside what the buyer confirmed. Success: no capture outside a confirmed mandate, and a record both sides can read showing why each purchase was allowed or refused.

## Positioning

Other agent-payment controls mostly cap how much and where an agent spends. IntentLock checks what is being bought (specification, condition, seller, substitution, total including tax and shipping), re-checks the real PayPal order after the buyer approves and before capture, and names the rule that refused a purchase. The decision is made by fixed rules, never by the model.

## Operating Context

- Purchase lifecycle: request → draft mandate → buyer confirms and locks it → product proposed (by buyer or agent) → server quote → rule check → PayPal order → buyer approval → re-fetch and final check → capture → signature-verified webhook → receipt.
- The merchant's first question on the dashboard (confirmed): **what was stopped and why** — how many proposals were outside the mandate, which rules caught them, and the value kept from being captured.
- Public demo: no merchant login. The dashboard shows store-wide totals, charts and recent rows from all visitors, without typed request text or emails; links open only the viewer's own records (confirmed).

## Capabilities and Constraints

- Deterministic rule engine with stable rule IDs and a version (`intentlock-policy-2026.11.1`); decisions ALLOW, BLOCK, REAUTHORISE, REVIEW.
- PayPal Sandbox only: Orders v2 create, retrieve, capture; JS SDK approval; verified webhooks.
- Gemini drafts mandates, proposes products and explains records; it never decides.
- PostgreSQL is the source of truth; hash-chained audit log; HMAC-signed receipts with read-only share links.
- One merchant, USD, synthetic demo catalogue (12 products).
- No new frontend dependencies without the owner's approval; charts are drawn in SVG.

## Brand Commitments

- Name: **Netrava IntentLock**. Tagline in use: "Purchase intent integrity for AI commerce".
- Voice: plain language; a failed check is "outside your mandate", never "fraud detected".

## Evidence on Hand

- One real buyer-approved PayPal Sandbox capture with a verified webhook on the live site (done by the team, 11–12 Nov 2026).
- 85 automated tests. No customers, pilots, testimonials or production figures exist; none may be implied.

## Product Principles

1. The rules decide; the AI drafts, proposes and explains.
2. Fail closed: anything unverifiable means no capture.
3. Every refusal names its rule, what the mandate says and what was found.
4. Label what is synthetic or simulated wherever it appears.
