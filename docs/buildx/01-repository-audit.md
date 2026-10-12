# 1. Repository audit (Phase A)

Audit date: 2026-10-12. Commit audited: `8ec8e36` (master) plus two uncommitted
changes (`data/benchmark_results.json`, `HARDCODED_VALUES_AUDIT.md`).

## 1.1 What was actually run

| Check | How | Result |
|---|---|---|
| Backend unit/integration tests | `pytest backend/tests` in a Python 3.14 venv with version pins relaxed (pinned numpy 1.26 / pandas 2.1 do not build on 3.14); torch not installed | **417 passed, 5 skipped**; 2 torch-only modules not collected (`test_focal_loss.py`, `test_gnn_directed.py`) |
| Coverage | `pytest --cov=.` | **68 %** line coverage (target in house rules: 80 %) |
| Lint (CI scope) | `ruff check backend/ models/` + `ruff format --check` | Pass |
| Lint (whole repo) | `ruff check .` | 22 errors in `scripts/`, `data/`, `infra/` (outside CI scope) |
| Leakage-controlled evaluation | new `scripts/evaluation/evaluate_detectors.py` | See [05-evaluation.md](05-evaluation.md) |
| Robustness and scaling probe | new `scripts/evaluation/robustness_and_scale.py` | See [05-evaluation.md](05-evaluation.md) |
| Frontend build / tests | Not run: Node is not on PATH and `node_modules` is absent | **Unverified** |
| Docker Compose stack (Neo4j, Kafka, Redis, Postgres, Prometheus, Grafana) | Not run: Docker is not installed on this machine | **Unverified** |

## 1.2 Component table

Status key: **IT** implemented and tested · **IU** implemented, unverified ·
**PI** partially implemented · **PO** planned only · **MB** missing or broken.

| Component | Current implementation | Status | Defect or gap | Business importance | Recommended action |
|---|---|---|---|---|---|
| CSV ingestion + validation | `data_adapters/mule_csv_adapter.py` (598 lines), `/csv-upload` routes; warnings for missing labels, low timestamp variety, unlinkable legs | IT | Debit/credit legs are joined by amount+date inference when no shared reference exists (LOW confidence, documented) | High: the only realistic way a judge or pilot bank gives you data | **Keep**; make it the primary demo input |
| Kafka streaming ingest | producer/consumer with manual commit and replay guard | IU (42 % coverage) | Needs a broker; not exercised in tests end to end | Low for a 36 h demo | **Defer**; keep code, demo with batch/micro-batch |
| Rule engine (R01–R20) | `detection/pipeline.py` lambdas over full transaction list | IT (unit) / **MB (efficacy)** | On the project's own synthetic data the rules fire **more on legitimate accounts than mules** (R11 91 % vs 8 %, R07 64 % vs 0 %, R16 58 % vs 0 %). Each rule scans every transaction per account (O(accounts × transactions)) | High: rules are the explainable baseline banks already trust | **Refine**: recalibrate or drop non-discriminating rules; index transactions by account |
| Temporal smurf weighting | `models/temporal_weighting/smurf_weighting.py` | IT | Designed alongside the synthetic generator (circularity risk) | High: strongest single signal measured | **Keep** |
| Louvain community detection + centrality | `models/community_detection/louvain_detector.py` | IT | Background legitimate traffic can form one large community that is flagged as a "mule cluster" (an 89-account all-legitimate alert observed at risk 0.738) | High: creates the case unit | **Refine**: add member-evidence (purity) weighting before alerting |
| Score fusion (risk_score) | ~40 hand-set weights/boosts/caps in `DetectionPipeline` | IU | No calibration; weights not learned or validated; `HARDCODED_VALUES_AUDIT.md` lists 50 such constants | High | **Simplify**: fewer, documented, calibrated components |
| GNN (GraphSAGE) | `models/gnn/gnn_model.py` | PI | **Label leakage**: uses `high_risk` as a node feature (`gnn_model.py:334`), a field the generator sets only for mule source/aggregator accounts. Trains on the data it then scores if no saved model exists. torch absent from requirements file | Low: not shown to beat simpler methods | **Remove from demo path**; fix leakage before any future use |
| Lightweight scorer (LightGBM/heuristic) | `models/gnn/lightweight_scorer.py` | IT | Untrained in practice → heuristic fallback | Low | Keep as fallback only |
| Unsupervised anomaly (PyOD) | `models/anomaly/unsupervised_scorer.py` | IT | Supporting signal only | Medium | Keep |
| Device / IP profiling | `models/device/device_profiler.py` | IT | Real banks rarely share device data with AML teams; availability is a pilot question | Medium | Keep, mark data-dependent |
| Markov lifecycle, semantics, baseline | `models/temporal/…`, `models/semantics/…`, `models/behavioral/…` | IT | Small capped boosts; contribution unmeasured | Low | **Defer** or ablate |
| India-specific detectors (Jan Dhan, crypto-gaming, UPI compliance, FRI), scam victim/dual-risk, propensity, response orchestrator, priority scorer, case assembler, narrative agent | `models/india/*`, `models/scam/*`, etc. | **MB (unreachable)** | 11 dependency providers in `api/deps.py` are never referenced by any route (verified with grep) | None in current product | **Remove from MVP scope**; archive on a branch |
| Explanations | rule text + permutation "SHAP-style" importance (`shap` not installed → approximation) + narrative templates | IT | Calling permutation importance "SHAP" overstates it | High: investigators need reasons | **Keep**, rename to "feature contributions" |
| GenAI triage / copilot (Gemini, OpenAI, Anthropic) | `genai/*`, `services/genai_capabilities/*` | PI (copilot 17 % coverage) | LLM can shift `risk_score` by `confidence_adjustment` (pipeline line ~700) — a model output altering a regulated score with no audit of the prompt | Low for MVP; risk for trust | **Disable in demo**; never let an LLM change scores |
| Alert queue + detail + disposition | `/alerts` GET/PATCH, statuses `OPEN/UNDER_REVIEW/RESOLVED/FALSE_POSITIVE`, audit log on update | IT (API) / IU (UI) | Disposition vocabulary lacks "suspicion confirmed → escalate"; UI **silently falls back to hard-coded demo alerts** when the API fails (`AlertQueue.js:35`, includes invented `sar_filing_probability: 0.92`) | High | **Refine** vocabulary; replace silent fallback with an explicit "backend offline" state |
| Ground-truth roles in UI | Nodes display `role` = SOURCE/MULE/AGGREGATOR | **MB** | `role` is copied from the input record (`pipeline.py:851`) — on synthetic data the UI shows the answer key; on real data it shows "UNKNOWN" | High: a judge noticing this destroys credibility | **Fix**: derive a *structural* role (sender/intermediary/collector) from the graph |
| Audit hash chain | `services/audit_service.py`, `pg_audit_repository.py` | IT | — | High (regulatory) | Keep |
| STR draft/PDF | `compliance/*`, `api/str_pdf.py` | IU (0 % coverage on PDF) | Default reporting entity hard-coded to a real bank name | Medium | Keep as "export case report"; use a neutral "Demo Bank" |
| Onboarding risk, UNSC screening | routes + services | IT / IU (fetcher 0 %) | Not part of the payment-fraud challenge | Low | **Defer** (hide from demo) |
| ROI dashboard | `/roi`, `kpi_service.py` | IU | Reads `hours_saved`, `fraud_prevented_inr` from DB tables with no measured source | Medium | **Replace** with the transparent ROI calculator in [07-business-impact.md](07-business-impact.md) |
| Benchmarks page + API | `/benchmark/*`, `benchmark/runner.py` | IT | Passes records **with label fields** to the pipeline; no baseline comparison | High | **Replace** with the leakage-controlled harness |
| Auth / RBAC / rate limiting / security headers | JWT, LDAP option, `slowapi` | IT | `AUTH_ENABLED=false` in dev env files (fine locally) | Medium | Keep; enable for the demo login |
| Infra (k8s, Prometheus, Grafana, prod compose) | `infra/` | PO / IU | Not needed to prove value | Low | **Defer** |

## 1.3 Cross-cutting findings

| Type | Finding |
|---|---|
| Duplicate functionality | Two SHAP explainers (`backend/explainability/shap_explainer.py` 327 lines and `models/explainability/shap_explainer.py` 638 lines); two mule classifiers (`backend/detection/mule_classifier.py`, `models/typology/mule_classifier.py`); two user-store modules in different trees (`infra/database/user_db.py`, `backend/infra/database/pg_user_db.py`), likely overlapping; two `RESEARCH_REPORT.md` (root and `docs/`) |
| Contradictory documents | `VALIDATION_REPORT.md` says "No hardcoded values detected"; `HARDCODED_VALUES_AUDIT.md` (same day) lists 50. `V2_IMPROVEMENT_SUMMARY.md` claims "83 % accuracy" from **6 accounts**, after tuning thresholds on those same 6 accounts — this is in-sample and must not be presented as a result |
| Unnecessary dependencies (for the MVP) | Neo4j, Kafka, Redis, Postgres, Prometheus, Grafana, three LLM SDKs, LDAP, torch-geometric, shap, gsap + framer-motion + d3 + cytoscape + recharts in the frontend |
| Fragile integration points | `backend/models` and `backend/data` are symlinks (break on Windows, yet `scripts/start-dev.bat` exists); pinned numpy/pandas do not install on Python ≥ 3.13; torch is installed out of band |
| Inconsistent schemas | Synthetic records carry label fields (`role`, `high_risk`, `cluster_id`, `is_suspicious`, `pattern`) in the same dicts the detectors read; CSV path uses CBS columns; AlertNode mixes label (`role`) and feature fields |
| Security & privacy | No secrets committed (checked history of `.env`); dev `.env` files hold weak dev defaults and are git-ignored; LLM features would send account data to third-party APIs if enabled; a real bank's name (Indian Overseas Bank) is the hard-coded default reporting entity, which could be read as an implied partnership |
| Scalability | Rule engine is O(accounts × transactions); measured pipeline latency in [05-evaluation.md](05-evaluation.md) |
| Clutter | 8 empty `.tmp-pytest-*` folders; three report files in repo root instead of `docs/` |

## 1.4 Prioritised engineering backlog

Priority: **P0** = blocks a credible demo · **P1** = needed for the core claim ·
**P2** = valuable if time permits · **P3** = defer.

| # | P | Item | Why | Done when |
|---|---|---|---|---|
| 1 | P0 | Strip label fields at the ingestion boundary; derive structural roles from the graph | Leakage into GNN features and the UI | A test asserts detectors never see `role/high_risk/is_suspicious/pattern/cluster_id` |
| 2 | P0 | Replace the UI's silent demo-data fallback with an explicit offline state | Fake results on a judge's screen | Killing the backend shows "Backend unavailable", not alerts |
| 3 | P0 | Weight case ranking by member evidence (case purity) | Removes the large all-legitimate case; measured effect in 05 | Evaluation shows legitimate accounts exposed drops on hardened data |
| 4 | P0 | Make `evaluate_detectors.py` the benchmark of record; retire in-sample "83 %" claims | Credibility | `docs/buildx/evaluation_results.json` regenerated by one command |
| 5 | P1 | Recalibrate or remove rules that do not discriminate; index transactions per account | Rules currently anti-correlated with mules on synthetic data | Each kept rule has documented hit rates per class |
| 6 | P1 | Disable GNN and LLM score adjustment in the demo path | Unvalidated and non-auditable | Pipeline config flag; tests pass |
| 7 | P1 | Disposition vocabulary: `NEW → IN_REVIEW → {NO_FURTHER_ACTION, SUSPICION_CONFIRMED_ESCALATED}` with mandatory reason | Separates suspicion from verified outcome | API + UI + audit entries |
| 8 | P1 | Independent dataset run (IBM AMLworld HI-Small, Kaggle) | Synthetic circularity | Results table added to 05 |
| 9 | P1 | Python 3.12 lockfile / container that actually installs | Reproducible setup for judges | `make demo` works on a clean machine |
| 10 | P2 | Investigation report export (case PDF/Markdown) with evidence and disposition history | Phase F step 9 | Exported file contains audit trail |
| 11 | P2 | Hide non-core pages (onboarding, screening, ROI, India map, compliance portal) behind a feature flag | Focus | Demo sidebar shows Queue, Case, Evaluation only |
| 12 | P2 | Raise coverage on `case`, `alert_service`, `csv_upload` to ≥ 80 % | House standard | Coverage report |
| 13 | P3 | Kafka, Neo4j, k8s, Grafana, LDAP, GenAI copilot, India-specific detectors | Not needed to prove value | Kept on a branch, documented as roadmap |
| 14 | P3 | Tidy: delete `.tmp-pytest-*`, move root reports to `docs/`, resolve duplicate modules, fix 22 out-of-scope ruff errors | Hygiene | Clean `git status`, single source per module |

**Decision:** The foundation is usable. Do **not** rebuild. Cut scope hard,
fix the two credibility defects (label leakage, fake fallback) and make the
evaluation honest. **Next action:** backlog items 1–4.
