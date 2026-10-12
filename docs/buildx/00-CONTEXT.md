# BuildX 2026: session context (read this first in a new chat)

Last updated: 2026-10-12. Hand-off note so a new session can continue the
BuildX hackathon work without re-doing the audit.

## 1. The hackathon

| Item | Fact | Source |
|---|---|---|
| Event | BuildX Hackathon 2026, AIC T-Hub × B.S. Abdur Rahman Crescent Institute of Science and Technology | https://www.t-hub.co/buildx-hackathon |
| Dates | **Conflicting on the official page:** 4–5 Nov 2026 (36 h) *and* 13–14 Oct 2026 (48 h). **Unconfirmed**; user was told to email the organisers | Official page |
| Registration | Zoho form; opens 30 Sep 2026, last date 1 Nov 2026; ₹1200 per team; team 2–4 (or 2–5) | Official page |
| Prizes | ₹50k / ₹25k / ₹15k | Official page |
| Rules on pre-built code, datasets, judging criteria | **Not published.** Ask organisers before relying on existing code | Official page |
| Problem statements PDF | Saved at `~/Documents/Hackathons/BuildX-2026/BuildX-2026-Industry-Problem-Statements.pdf` | Organiser PDF |

### Chosen problem statement (verbatim)

> **Banking, Financial Services & FinTech: Detect Payment Fraud in Real Time.**
> As digital payments grow, fraud patterns are becoming increasingly dynamic.
> At the same time, excessive fraud alerts can disrupt genuine customers.
> Develop a real-time fraud detection solution that can identify suspicious
> transactions while minimising false alerts for genuine customers.
> *Machine Learning • Fraud Analytics • APIs • Real-Time Systems*

## 2. What was submitted on the registration form

The form had one **100-character** field ("Few lines about Idea / Startup").
Text chosen (97 characters):

> **MuleCatch: real-time AI that traces each payment to catch whole mule rings, not genuine customers**

Status of submission: the user was preparing to paste this; not confirmed as submitted.

## 3. The pitch, as agreed

| Element | Agreed wording / position |
|---|---|
| Tagline | "One payment reveals the whole scam ring: real-time AI that flags fraud, not genuine customers" |
| Core idea | Score each payment **in real time** in the context of the account network. Flag payments flowing into mule rings. Group the ring into **one explainable case**. Genuine customers with one unusual payment are not falsely alerted |
| Differentiator | Others score single accounts or transactions; MuleCatch makes the **whole ring** the unit of investigation **and measures how many genuine customers get pulled in** |
| Bonus angle ("golden hour") | From one victim's reported payment (1930 helpline / I4C CFCFRMS), follow money forward hop by hop to show the whole ring and which accounts still hold funds. **Not built yet**; secondary, because the challenge asks for proactive real-time detection |
| Responsible AI | Never auto-blocks. Human decides; hash-chained audit trail. Suspicion ≠ verdict. RBI July 2024 fraud directions require natural justice before classifying fraud |
| Positioning | Complements RBI's MuleHunter.AI (23 banks by Dec 2025), not a replacement. First customers: small finance, cooperative and payments banks (hypothesis) |
| Headline result (synthetic data only) | About **5 ring-level cases covered 90 % of mule accounts vs 200+ reviews** with the rules baseline |

### Honesty rules the user agreed to
- Always say "synthetic data" next to results.
- Never say the system "stops", "blocks" or "recovers money"; say it "flags" and "helps banks act faster".
- Never claim a bank partnership (no Indian Overseas Bank references) and never claim "83 % accuracy" or "production-ready".
- "Real time" today = about 1.3 s per 2,000-transaction batch. A per-payment live scoring API is the main thing to build at the hackathon.

## 4. Key audit findings (details in 01 and 05)

| Finding | Where |
|---|---|
| 417 backend tests pass; 68 % coverage; frontend and Docker stack not verified | 01 §1.1 |
| GNN uses label field `high_risk` as a feature (leakage) → removed from demo path | `models/gnn/gnn_model.py:334` |
| UI shows ground-truth `role` (MULE/SOURCE/AGGREGATOR) | `pipeline.py:851`, `AlertDetail.js`, `AlertQueue.js` |
| UI silently falls back to hard-coded fake alerts when the API fails | `frontend/src/alert_queue/AlertQueue.js:35` |
| The 20 rules are no better than random on synthetic data; several fire more on legit accounts | 05 §7.3 |
| Simple graph + temporal method (AP 0.929 hardened) beats the full 7-layer pipeline (0.867) and is ≈15× faster | 05 §7.3 |
| Shipped alerts flag ≈70 % of legit accounts (one 89-account all-legit "cluster") | 05 §7.3 |
| Purity-weighted case ranking: 5 cases to 90 % recall, 0 genuine accounts exposed (vs 150 as shipped) | 05 §7.4; implemented only in the evaluation harness |
| Latency superlinear: 2k txns 1.3 s, 10k txns 99 s | 05 §7.5 |
| 5 of 11 malformed-input types crash the pipeline | 05 §7.6 |
| 11 dependency providers unreachable from any route | 01 §1.2 |

## 5. Next actions (in order)

1. Email organisers: confirm dates, whether pre-existing code is allowed, allowed datasets, judging criteria.
2. Backlog #1–4 (01 §1.4): strip label fields + structural roles; remove fake UI fallback; purity-weighted case ranking in product; evaluation page.
3. Build the **live per-payment scoring API** (`POST /api/v1/transactions`) with account-indexed rules so latency is real-time.
4. Optional: "trace from one payment" view (golden-hour feature).
5. Run the harness on IBM AMLworld (Kaggle) for independent evidence.
6. 3–5 analyst conversations to validate the user need.

## 6. File map

| File | Contents |
|---|---|
| `docs/buildx/README.md` | Index of all 15 deliverables + verdict |
| `01-repository-audit.md` | Component table, cross-cutting issues, prioritised backlog |
| `02-problem-and-customer.md` | Refined problem, sourced evidence, stakeholder map, validation plan |
| `03-differentiation.md` | Competitors (MuleHunter, Clari5, BioCatch, Feedzai, Quantexa) and the chosen differentiator |
| `04-architecture.md` | Current vs target architecture, schemas, API contracts, build order |
| `05-evaluation.md` | Measured results and limitations |
| `06-mvp-and-test-plan.md` | MVP scope, investigator flow, acceptance tests |
| `07-business-and-impact.md` | Business model, blank-formula ROI, risk assessment |
| `08-execution-demo-pitch.md` | Schedule, demo script, pitch outline, go/no-go (**GO, simplified scope**) |
| `scripts/evaluation/evaluate_detectors.py` | Leakage-controlled benchmark → `evaluation_results.json` |
| `scripts/evaluation/robustness_and_scale.py` | Malformed-input and latency probe → `robustness_scale_results.json` |

Environment note: this machine has only Python 3.14; pinned numpy/pandas don't
install on it, so the audit used a scratch venv with pins relaxed and without
torch. Node and Docker are not installed.

Uncommitted at time of writing: `docs/buildx/`, `scripts/evaluation/`,
`HARDCODED_VALUES_AUDIT.md`, modified `data/benchmark_results.json`.
