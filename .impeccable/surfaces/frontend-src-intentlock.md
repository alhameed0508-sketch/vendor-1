---
version: 1
slug: "frontend-src-intentlock"
primary_target: "frontend/src/intentlock"
related_targets: []
---

# IntentLock merchant console

Scope: the whole web app under frontend/src/intentlock (dashboard, ledger, mandates, checkouts, receipts, rules, integrations, demo, and the buyer purchase flow inside the shell). Mode: Operate.
Audience and job: the merchant's team reviews every AI-agent purchase across buyers; first question is what was stopped and why. Judges open it with no login. Store-wide totals, charts and rows are shown without typed request text or emails; links open only the viewer's own records.

## Direction contract

THESIS: The console is the merchant's reconciliation book for agent purchases: every proposal is an entry, refusals are posted in red with the rule as the memo, and the dashboard reconciles proposals to captures. It refuses the KPI-tile-grid-plus-cards dashboard.

OWN-WORLD: Bookcloth-green sidebar; pale ledger-paper ground with hairline column rules; blue-black ink; red ink and parenthesised amounts for refusals; double rule under totals; small-caps column heads; serif statement headings, workhorse sans for UI, tabular figures everywhere; panels divided by hairline seams, no drop shadows. State colours: green captured, red block, amber reauthorise, blue review.

STORY: The visitor reads that most agent purchases were stopped before money moved and which rules did it, trusts that the rules (not the AI) decided, and opens an entry to see its checks, PayPal order, capture and receipt.

FIRST VIEWPORT: Left rail: Monitor (Dashboard, Ledger), Purchases (New purchase, Mandates, Checkouts, Receipts), Controls (Rules), System (Integrations, Demo). Top bar: title, period, Sandbox status, New purchase. Lead: the reconciliation statement (checked, less stopped in red, allowed, captured, verified) beside "why stopped" rule bars; below, decisions per day and the latest ledger entries.

FORM: Reconciliation ledger, candidate 1 on the ordered list (chosen by the user as the pick card); seed:6d6354885829ed20. Raises kept: hairline seams instead of shadows (dark console); every entry carries a sequential reference IL-0001 (catalog numbering); ledger header names the range in view (lexicon guide words).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
