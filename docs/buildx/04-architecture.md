# 5. Current versus target architecture (Phase D)

## 5.1 Current architecture (as built)

```text
CSV upload ─┐                       ┌─ Neo4j (graph persistence, optional)
Kafka ──────┼─► DetectionPipeline ──┼─ Postgres (alerts, audit, STR, users; optional)
/ingest/seed┘   7 layers:           ├─ Redis (cache/state; optional)
                1 rules R01–R20     └─ in-memory fallbacks
                2 smurf, baseline, semantics, device, Markov
                3 Louvain + centrality + PyOD anomaly
                4 GNN (torch) or LightGBM/heuristic
                5 LLM triage (can move risk_score)
                6 explanations ("SHAP" approximation)
                7 typology classifier + narrative
                        │
                        ▼
FastAPI: 20 route modules (alerts, feedback, escalations, compliance/STR,
onboarding, screening, GenAI, ROI, KPI, benchmark, device, graph, ingest…)
                        │
                        ▼
React (CRA): 10 pages, cytoscape + d3 + recharts + gsap + framer-motion
Infra: docker-compose (≈8 services), k8s manifests, Prometheus, Grafana
```

About 35k lines across backend, models and frontend; 11 dependency providers
unreachable from any route.

## 5.2 Target architecture (MVP)

```text
 Transaction file (CSV/JSON)  or  micro-batch POST /api/v1/transactions
        │
        ▼
 1. Validate & normalise      mule_csv_adapter (keep) + label-field stripping (new)
        │
        ▼
 2. Build graph               networkx in-process (keep); Neo4j optional, off by default
        │
        ▼
 3. Detect                    A. rules baseline (recalibrated)          ← shown for comparison
                              B. smurf/temporal scores + Louvain communities
        │
        ▼
 4. Rank cases                case score = community risk × mean member evidence (new)
                              reason codes + per-member contributions
        │
        ▼
 5. Investigation case        queue → case view (network, path, timeline, evidence)
        │
        ▼
 6. Human disposition         NO_FURTHER_ACTION | SUSPICION_CONFIRMED_ESCALATED (+ reason)
    + audit hash chain        (keep audit_service)
        │
        ▼
 7. Evaluate & report         scripts/evaluation/* → docs/buildx/*.json; case report export
```

Runtime for the demo: **one FastAPI process + SQLite/in-memory store + React
build served statically.** No Kafka, Neo4j, Redis, Grafana or LLM calls are
needed to prove the core value.

## 5.3 Keep / refine / defer / remove

| Keep | Refine | Defer (branch / roadmap) | Remove from MVP path |
|---|---|---|---|
| CSV adapter + validation warnings | Rule set (drop non-discriminating rules, per-account index) | Kafka streaming | GNN scoring (leakage; no measured gain) |
| Smurf/temporal scoring | Case ranking (purity weighting) | Neo4j persistence | LLM risk adjustment (non-auditable) |
| Louvain communities + centrality | Disposition vocabulary | Postgres (keep code; SQLite/in-memory for demo) | Silent demo-data fallback in UI |
| Explanation text + contributions | Node role → structural role | Redis, Prometheus/Grafana, k8s | Ground-truth `role` display |
| Alerts API, audit chain, auth | Benchmark page → evaluation report | GenAI copilot/chat, India detectors, scam engines | "83 % accuracy" claims |
| Alert queue + detail + subgraph UI | STR export → case report export | Onboarding risk, UNSC screening, ROI dashboard | |

## 5.4 Data schemas (MVP)

**Transaction (input, after normalisation)**

| Field | Type | Required | Notes |
|---|---|---|---|
| `txn_id` | string | yes | unique; duplicates rejected |
| `from_account`, `to_account` | string | yes | `from != to` |
| `amount` | decimal > 0 | yes | INR |
| `timestamp` | ISO-8601 with timezone | yes | |
| `channel` | enum UPI/IMPS/NEFT/RTGS/CASH/OTHER | no | |
| `device_id`, `ip_address` | string | no | used only when supplied |

**Account (optional master data):** `account_id`, `account_age_days`,
`kyc_status`, `bank`, `city`. **Forbidden at the detector boundary:** `role`,
`high_risk`, `is_suspicious`, `pattern`, `cluster_id`, `label`. These are
removed and kept only in the evaluation harness.

**Case (output)**

```json
{
  "case_id": "CASE-…",
  "rank": 1,
  "case_score": 0.81,
  "community_risk": 0.93,
  "member_evidence_mean": 0.87,
  "accounts": [{"account_id": "…", "structural_role": "collector|intermediary|sender",
                "evidence_score": 0.9, "reason_codes": ["…"]}],
  "transactions": ["txn_id", "…"],
  "timeline": {"first_seen": "…", "last_seen": "…"},
  "reasons": ["Funds from 1 source split into 41 payments < ₹50k within 3 h", "…"],
  "status": "NEW",
  "model_version": "…", "rule_version": "…"
}
```

**Disposition (input):** `{status, reason (required), notes}`. Every change
appends an audit record `{actor, timestamp, from_status, to_status, reason,
prev_hash, hash}`.

## 5.5 API contracts (MVP)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/csv-upload/upload` → `/analyze` | Existing: validate file, run detection |
| POST | `/api/v1/transactions` | New, optional: micro-batch ingest (≤ 5k rows) for the "real-time" demo |
| GET | `/api/v1/alerts?status=&limit=` | Ranked case queue (existing endpoint, case fields added) |
| GET | `/api/v1/alerts/{id}` · `/subgraph` · `/explanation` | Case view (existing) |
| PATCH | `/api/v1/alerts/{id}` | Disposition with mandatory reason (refined) |
| GET | `/api/v1/audit?alert_id=` | Audit history (existing route) |
| GET | `/api/v1/alerts/{id}/report` | New: case report export (Markdown/PDF) |
| GET | `/api/v1/evaluation/latest` | New: serve `docs/buildx/evaluation_results.json` to the UI |

## 5.6 Implementation order

1. Label stripping at the boundary and structural roles (backlog #1)
2. UI offline state replacing silent fallback (#2)
3. Purity-weighted case ranking behind a config flag, with tests (#3)
4. Evaluation endpoint + page reading the harness output (#4)
5. Disposition vocabulary + mandatory reason (#7)
6. Rule recalibration with per-class hit-rate report (#5)
7. Case report export (#10)
8. Feature-flag the non-core pages (#11)

## 5.7 Testing strategy

| Layer | Tests |
|---|---|
| Unit | Label stripping; case score function; structural role derivation; each kept rule on fixtures |
| Property | Detector output is invariant to adding or removing label fields |
| Integration | Upload → analyze → queue → disposition → audit chain verifies |
| Evaluation regression | CI job runs a 3-seed version of the harness; fails if hardened-scenario AP or genuine-exposure regress beyond tolerance |
| E2E (Playwright) | Login → queue → open case → record disposition → export report |
| Robustness | Malformed batches return 4xx with reasons, never 500 |

## 5.8 Deployment and fallback

| Mode | How | When |
|---|---|---|
| Primary | Laptop: `uvicorn` + static React build, preloaded demo dataset | On stage |
| Backup 1 | Same, on a second laptop | Primary fails |
| Backup 2 | Recorded 2-minute screen capture of the full flow | Venue Wi-Fi or hardware failure |
| Never | Silent fallback to fabricated alerts | — |

**Decision:** Collapse to a single-process MVP; keep heavy infrastructure on a
branch. **Next action:** steps 1–4 of 5.6.
