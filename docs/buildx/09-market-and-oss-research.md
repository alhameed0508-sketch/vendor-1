# 09 – Market and open-source research

Research date: 2026-11-02. Scope: open-source mule/fraud projects, datasets and papers, hackathon outcomes, graph-UI practice, Indian regulation, and production architecture.

**Source quality warning.** Most findings come from search snippets, vendor blogs and news summaries, not from primary documents. Items marked *(unverified)* were not confirmed against a primary source. Several fetches of primary sources failed (RBI HaRBInger page returned a bot-check; the Spade PDF was binary and was not read). Do not quote numbers from this file in the pitch without opening the source first.

## 1. Executive summary

| Finding | Implication for MuleCatch |
|---|---|
| No open-source project combines per-payment scoring, ring-level explanation and an analyst review UI. | The "per-payment flag with a named ring and reasons" demo is differentiated. |
| The closest mule-specific OSS (`mule-hunt`, MIT) reports weak metrics and says it is research-only. | Honest synthetic-data caveats are the norm, not a weakness. |
| IBM's AMLworld paper finds both GNNs and gradient-boosted trees work, and precision is low at very low illicit rates. | Our 24% synthetic prevalence flatters precision. Say so. |
| Real-time fraud stacks use Kafka → Flink → feature store → model → rules with a sub-100 ms budget. | Our scorer re-runs Louvain per payment (p50 about 165 ms, p95 about 264 ms on the synthetic eval). It meets a demo, not a bank latency budget. Incremental updates are the main engineering gap. |
| Indian regulators already run shared-signal infrastructure (DoT FRI, MuleHunter.AI at 23+ banks). | Position MuleCatch as a complement that adds ring-level evidence and reviewer workflow, never as a replacement. |
| RBI fraud rules require notice and a reasoned order before fraud classification. | "Route to human review" is the correct framing. Never say "blocks". |

## 2. Open-source landscape

Licence and activity were read with `gh api` on 2026-11-02 unless noted.

| Project | Licence | Stars | What it is | Borrow or avoid |
|---|---|---|---|---|
| `IBM/Multi-GNN` | Apache-2.0 | 126 | GNN training for AML on AMLworld (GIN, GAT, PNA, RGCN; edge features, reverse message passing, ego IDs, port numbering) | Borrow ideas for a future learned scorer. Reverse message passing and port numbering suit directed money flow. Not needed for the demo. |
| `IBM/AMLSim` | Apache-2.0 | 412 | AML transaction simulator | Possible second synthetic source to reduce circularity. |
| `tirrenotechnologies/tirreno` | **AGPL-3.0** | 1,560 | PHP/PostgreSQL fraud platform: rules, risk scores, review queue, entity pages, field audit trail | Copy ideas only (entity page, audit trail, rule + score split). **Do not copy code**: AGPL would force us to open the whole service. |
| `pygod-team/pygod` | BSD-2-Clause | 1,500 | Graph outlier detection | Baselines for the evaluation table. Last push 2024-11. |
| `yzhao062/pyod` | BSD-2-Clause | 10k | Tabular outlier detection | Baselines only. |
| `safe-graph/DGFraud` | Apache-2.0 | n/a | Graph fraud models | Stale since 2022. Skip. |
| `mule-hunt` (PyPI) | MIT | n/a | UPI ring-detection research package: GCN/GraphSAGE/GATv2, GNNExplainer, isotonic calibration, risk bands, cold-start fallback, PSI drift monitoring | Borrow the *product* ideas (calibration, bands, cold start, drift). Its own numbers are weak (GraphSAGE AP 0.079; AP 0.009 at 50k accounts). |
| `Rupali-2507/MULE_HUNTER`, `Victor-Kipruto-Rop/mpesa_safaricom-fraud_anomaly_detection`, `Atrangi-Coders/Financial-Forensics-Engine`, `Width-Risk-Comliance-Database/txgraph` | none stated | 11–34 | Hackathon-style repos (GraphSAGE + JA3; Kafka/Flink; muling web app; React/Sigma/ReactFlow graph components) | No licence means no reuse. Read for ideas only. |

Curated lists worth scanning later *(licences not checked)*: `safe-graph/graph-fraud-detection-papers`, `benedekrozemberczki/awesome-fraud-detection-papers`.

## 3. Datasets, papers and winning approaches

| Source | Takeaway |
|---|---|
| IBM AMLworld (NeurIPS 2023, arXiv 2306.16424) | Realistic synthetic AML data with known laundering patterns. Use as an external benchmark. Precision falls at very low illicit rates. |
| Kaggle IEEE-CIS Fraud (Chris Deotte's team won) | Winning work was feature engineering (client-ID reconstruction from device and time fields, aggregations) plus gradient boosting, not exotic models. Lesson: shared-entity grouping beats model novelty. *(from NVIDIA write-up; not re-read)* |
| PaySim, ULB credit card, Fraud Dataset Benchmark | Standard baselines. Not graph-rich. |
| Spade (VLDB 2024) | Incremental dense-subgraph fraud detection for evolving graphs, reported in a production setting. **The PDF was not read.** Open it before citing any latency number. Relevant to our incremental-update gap. |
| Neo4j mule-mitigation whitepaper | Track PageRank and betweenness over time per account, compare with a per-customer baseline, watch the ratio of high- to low-centrality counterparties. Time-evolving centrality is a cheap extra signal. |

**Hackathon outcomes (thin evidence).**

- No Devpost winner was confirmed. One hit (`devpost.com/software/syndicateai`) was not verified.
- Bank of India CyberShield, mule-detection track: IIIT Delhi "weAreWinners" first, IIIT Bangalore "Vijaya" second (₹3 lakh), PES University third; 72 prototypes presented, 18 finalists. The article gives no detail on what the teams built.
- RBI HaRBInger 2024: a mule-detection winner called Satark reportedly fused device, profile and external data across banks *(unverified, primary page blocked)*.
- Pattern across Indian events: shortlisted prototypes were judged live. A working per-payment demo with visible reasons is the realistic edge.

## 4. Feature ideas, ranked for MuleCatch

Ranked by judge impact against build cost, given the existing scorer and `/live` stream.

| # | Feature | Source of idea | Effort | Notes |
|---|---|---|---|---|
| 1 | Risk bands (low / review / high) with a calibrated score | `mule-hunt` | S | Replace the raw 0–1 score on screen with a band. Keep the number in the detail view. |
| 2 | Case card: ring members, money-flow timeline, top reasons, "route to human review" | tirreno, graph-UI practice | M | Mostly assembled data. The `/live` UI shows the stream. The case card makes it a product. |
| 3 | Expand-on-demand subgraph (click account, show neighbours) | graph-UI practice | M | Fits the existing deterministic layout. |
| 4 | Reviewer feedback loop (confirm / dismiss, stored, used for threshold review) | production practice | S–M | Backend already has feedback routes. Wire to the case card. |
| 5 | Cold-start fallback ("not enough history, using rules only") | `mule-hunt` | S | One honest line in the UI when an account has no history. |
| 6 | Drift monitor (PSI on score distribution) | `mule-hunt` | M | Credible for the production story. Not needed for the demo. |
| 7 | Centrality-trend signal (PageRank / betweenness over time) | Neo4j | M–L | Adds an independent signal. Only with time to evaluate it. |
| 8 | Shared device / IP edges | RBI-style cross-signal fusion, Sift/Sardine | L | Needs data we do not have. Mention as roadmap. |
| 9 | Natural-justice workflow (notice, 21-day response window, reasoned order record) | RBI Master Directions | M | Strong differentiator on the compliance side. Build as a status model, not a legal engine. |

## 5. Frontend and visual recommendations

Evidence is mostly vendor and opinion material. No independent benchmarks were found.

| Topic | Recommendation |
|---|---|
| Interaction pattern | Search → show context → expand on demand. Pair the graph with an attribute panel, a timeline, and a drill-down to raw payments. |
| Clutter control | Group ring members into one combo node; expand on click. |
| Risk over time | Show a small per-entity score trend in the case card. |
| Library choice | Current hand-laid SVG layout is fine for the demo (few hundred nodes). If we need more: **Sigma.js** (MIT, WebGL, about 100k nodes) for the main graph, **Cytoscape.js** (MIT) if we want built-in graph analysis. Skip React Flow for the graph view (built for editors; SVG slows after about 1k nodes). `react-force-graph` (MIT) is a quick alternative. Avoid `d3-force` alone (last push 2023). |
| Licences checked | sigma.js MIT, Cytoscape.js MIT, xyflow MIT, cosmos.gl MIT, react-force-graph MIT, AntV G6 MIT, ECharts Apache-2.0. All safe to depend on. |
| Honesty in the UI | Show a persistent "synthetic data" badge and a counter of genuine payments flagged. Already in the stream counters. |
| Coordination | The UI redesign is owned by the other session. Visual changes to shared files (`index.css`, `Sidebar`, `components/ui`) wait for it. |

## 6. Regulatory context (India)

| Item | Status | Confidence |
|---|---|---|
| DoT Financial Fraud Risk Indicator (FRI), launched May 2025 | Classifies a mobile number as Medium / High / Very High risk. Shared with banks and UPI apps for real-time use. RBI advisory of 2025-06-30 reportedly tells regulated entities to integrate it. | Medium (news summaries) |
| MuleHunter.AI (RBI Innovation Hub) | 23 banks as of 2025-12-10 per an RTI reply; some reports say 26. | Medium |
| RBI Master Directions on Fraud Risk Management (July 2024) | Show-cause notice with at least 21 days to respond before classifying fraud. A 2026 Supreme Court ruling reportedly requires notice, disclosure, written reply and reasoned order, not a personal hearing. | Medium. Read the Directions before building the workflow. |
| RBI FREE-AI report (2025-08-13) | 26 recommendations in six pillars: explainability, risk-based AI audit, board-approved AI policy, disclosures, grievance redressal. | Medium (secondary summaries) |
| 1930 helpline, I4C, CFCFRMS | **Not researched.** The search returned nothing. | None |
| NPCI AI risk scoring pilot | One blog mentions it. | Low |

Pitch implications: explainability, audit trail and human review are regulatory expectations, so they are selling points. Do not claim partnerships or coverage of FRI/MuleHunter.AI data.

## 7. Production-readiness checklist

Current state is a hackathon-grade scorer with real security hardening. Honest gaps:

| Area | Today | Needed for production |
|---|---|---|
| Ingest | Rolling window in memory | Kafka (or equivalent) topic, idempotent consumer, persistent store |
| Latency | Full Louvain re-run per payment; p50 about 165 ms, p95 about 264 ms (window about 5k payments, synthetic) | Incremental community updates (Spade-style) and a per-call time budget; target well under 100 ms |
| Features | Computed from window | Feature store (Redis) with 5–10 ms lookups |
| State safety | Public API read-only (`commit=False`), `txn_id` collision rules | Same, plus signed ingest path |
| Auth | JWT on API; stream via `fetch` and Authorization header | `useAlertStream` still sends `?token=` in the URL. Fix. |
| Rate limits | 120/min score, 20/min stream | Per-tenant limits, abuse monitoring |
| Evaluation | Synthetic data only, calibrated on seeds 0–2, tested on 100–119 | External benchmark (AMLworld), then bank-supplied labelled data under an agreement |
| Calibration | Hand-chosen gates | Isotonic calibration and risk bands |
| Drift | None | PSI monitor on scores and inputs |
| Audit | Alert audit routes exist | Immutable decision log with model/gate version |
| Governance | None | Board-approved AI policy, periodic independent audit (FREE-AI) |
| Known leak | GNN label leakage at `models/gnn/gnn_model.py:334` | Fix before the GNN path is ever used |

## 8. Recommended next steps

1. Land the current branches in the order recorded in `00-CONTEXT.md` §9.
2. Add risk bands and the case card (items 1, 2, 5 above). Smallest change with the biggest demo effect.
3. Read the Spade paper and the RBI Master Directions directly before quoting either.
4. Run the AMLworld benchmark once, as a second synthetic source, to reduce circularity.
5. Do not claim production readiness, bank partnerships or real-data accuracy.

## 9. Gaps in this research

- Kaggle and Elliptic winner write-ups were not read in depth.
- NPCI, 1930, I4C and CFCFRMS were not covered.
- Case-management OSS (NeoDash, Jube, Linkurious) was not examined.
- No Devpost winner was verified.
- Graph-latency benchmarks for streaming mule detection were not found.
