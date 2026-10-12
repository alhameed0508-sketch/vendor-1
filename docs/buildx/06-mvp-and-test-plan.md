# 6, 8, 11. Implementation backlog, MVP specification, test plan and acceptance criteria (Phases F and H)

The prioritised engineering backlog (deliverable 6) is in
[01-repository-audit.md §1.4](01-repository-audit.md#14-prioritised-engineering-backlog).
This file defines the MVP that backlog delivers, and how to accept it.

## 8.1 MVP: one reliable workflow

> Load a transaction file → MuleCatch builds the graph, scores accounts,
> groups them into ranked cases → an investigator opens the top case, sees the
> ring, the money path, the timeline and the reasons → records a decision with
> a reason → the decision is in a tamper-evident audit log → a case report is
> exported. A separate page shows the measured comparison against the rules
> baseline.

## 8.2 Capability classification

| Capability | Class | Exists today? | Work |
|---|---|---|---|
| Reproducible ingestion (CSV + bundled synthetic dataset with fixed seed) | **Essential** | Yes (CSV adapter, generator) | Add label stripping; seed the demo dataset |
| Graph construction | **Essential** | Yes | — |
| Baseline detector (rules) | **Essential** | Yes | Recalibrate; expose as the comparison |
| Proposed detector (smurf + Louvain + purity-ranked cases) | **Essential** | Partly | Add purity weighting |
| Evidence-backed risk scoring (reasons + member contributions) | **Essential** | Yes | Rename "SHAP" to "feature contributions" |
| Case queue → case view → disposition → audit | **Essential** | Yes (API tested, UI unverified) | Disposition vocabulary; remove fake fallback; structural roles |
| Documented evaluation | **Essential** | **Done in this audit** | Surface in UI |
| Repeatable demo script | **Essential** | **Done**: [08-execution-demo-pitch.md](08-execution-demo-pitch.md) | Rehearse |
| README: setup, data, limitations, results | **Essential** | Partly | Rewrite top section |
| Case report export | Valuable if time permits | STR PDF exists | Retitle and add audit trail |
| Micro-batch "real-time" endpoint + live queue update (SSE exists) | Valuable if time permits | SSE hook exists | Small |
| Timed analyst study (account view vs case view) | Valuable if time permits | — | Needs 4–6 volunteers |
| AMLworld independent evaluation | Valuable if time permits (before the event) | — | Adapter + run |
| Kafka, Neo4j, Redis, Grafana, k8s, LDAP, GenAI, India/scam detectors, onboarding, screening, ROI dashboard | Deferred | Yes | Feature-flag off |

## 9. Investigator experience (Phase F)

| Step | Screen element | Source today | Change |
|---|---|---|---|
| 1 Prioritised cases | Queue: rank, case score, #accounts, total ₹, time window, top 2 reasons | `AlertQueue.js` | Show case score as **"suspicion score (not a verdict)"** |
| 2 Open case | Route `/alert/:id` | `AlertDetail.js` | — |
| 3 Network + money path | Cytoscape subgraph; highlight largest-value path source → collector | `NetworkGraph.js`, `/subgraph` | Colour by **structural role** (sender / intermediary / collector), not ground truth |
| 4 Timeline + signals | `TimelineSlider.js`; per-member evidence bars | Exists | — |
| 5 Why prioritised | Plain-language reasons, then community risk × member evidence | `/explanation` | Show both factors of the case score |
| 6 Evidence | Transaction table filtered to the case | Partly | Add table |
| 7 Disposition | `NO_FURTHER_ACTION` / `SUSPICION_CONFIRMED_ESCALATED`, reason required | `PATCH /alerts/{id}` | New vocabulary |
| 8 Audit history | Hash-chained list in the case | `/audit` | Render in case |
| 9 Export | Case report | STR PDF | Retitle |

Remove from the demo navigation: India map, ROI dashboard, compliance portal,
onboarding, screening, GenAI chat, command palette.

Label rules on screen: the case score is "suspicion", model confidence is
shown separately, and only a human disposition can say "confirmed". No button
blocks or freezes an account.

## 11. Test plan and acceptance criteria

| ID | Area | Test | Acceptance criterion |
|---|---|---|---|
| T1 | Leakage | Run detectors on a dataset with and without label fields | Identical scores; CI test |
| T2 | Ingestion | Upload `Sample Mule account data.csv` and the demo CSV | HTTP 200; warnings listed; no crash |
| T3 | Malformed input | Non-numeric amount, missing timestamp, missing counterparty, self-transfer, duplicate IDs | API returns 4xx with a row-level reason or skips the row with a warning; **never 500** (see probe results in 05) |
| T4 | Detection regression | `evaluate_detectors.py` (3-seed CI variant) | Hardened AP for the proposed method ≥ the value committed in `evaluation_results.json` minus 0.03 |
| T5 | Genuine-customer protection | Workload metric on hardened scenario | Median legitimate accounts exposed to reach 90 % recall ≤ the rules baseline's |
| T6 | Workflow | Upload → queue → open → disposition → audit | Audit chain verifies; disposition requires a reason |
| T7 | UI honesty | Stop backend, load queue | Explicit "backend unavailable" state; zero fabricated alerts |
| T8 | Roles | Synthetic data with `role` present | UI shows structural roles only |
| T9 | Latency | Demo dataset (≈2k transactions) | Upload-to-queue ≤ 5 s on the demo laptop (pipeline median 1.0 s measured) |
| T10 | E2E | Playwright: login → case → disposition → export | Passes 5 consecutive runs |
| T11 | Coverage | `pytest --cov` | ≥ 80 % on changed modules |
| T12 | Security | No secrets in repo; auth enabled for demo; LLM calls disabled | Checklist signed |

**Decision:** The MVP is the existing alert workflow with the gaps fixed.
Nothing new needs to be invented. **Next action:** T1, T7 and T8 first; they
protect credibility.
