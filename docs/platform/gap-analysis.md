# MuleCatch platform: gap analysis

Phase 1 of 7. Read-only audit of buildx master at `c8f3e70`. No product code was changed.

Status words are used strictly:

- **Implemented**: the code exists, is reachable from a route or page, and is covered by tests.
- **Partial**: some of it exists, or it exists but needs data this repo does not have.
- **Planned**: nothing exists. It is a design target only.

Claims marked *(per docs, not re-verified)* come from `docs/architecture/` and were not re-run in this phase.

## Baseline

| Check | Result |
|---|---|
| `pytest backend/tests` (excluding `test_focal_loss.py` and `test_gnn_directed.py`, which need torch) | 787 passed, 5 skipped |
| `ruff check backend models` | All checks passed |
| `ruff format --check backend models` | 258 files already formatted |

## Target architecture (three diagrams) against the repo

### Diagram 1: ten-layer architecture

| Layer | Target | Honest status | What exists | What is missing |
|---|---|---|---|---|
| 1 Banking institutions | Public and private banks | Planned | Nothing. No institution concept in routes, services, repositories or `infra/database/init.sql`. | Institution model, tenant id on every record. |
| 2 Data sources | CBS, LMS, LOS, UPI switch, KYC, payment APIs, AML/EWS, I4C | Partial | CBS file import (`data_adapters/mule_csv_adapter.py`, `ingest/cbs_parser.py`), optional Kafka consumer and producer, a fraud complaint desk, UNSC watchlist fetch. | Connectors for LMS, LOS, UPI switch, KYC, I4C. Treat as Planned. |
| 3 Ingestion | Connectors, streaming, batch upload, API gateway, validation, dedupe, normalisation, tokenisation | Partial | Batch upload, FastAPI as gateway, row-level validation and duplicate rejection (`detection/validation.py`), canonical normalisation in the CBS adapter, hashing of identifiers in `entity_resolution_service.py`. | Bank-specific connectors, a general tokenisation step. The API does not yet return `last_rejections`. |
| 4 Event processing and data foundation | Event bus, feature store, event store, relationship graph, warehouse | Partial | Optional Kafka (`KAFKA_ENABLED`), in-process networkx graph, optional Neo4j. | No feature store, no warehouse, no durable event store. Neo4j's write API for accounts and transactions has no callers *(per docs)*. |
| 5 Three detection modules | A Loan, B UPI and transaction, C Mule | A Planned (sanctions check Partial), B Partial, C Implemented | C: rules R01–R20, smurf scoring, Louvain, centrality, anomaly, typology. B: velocity (R17), split payments (R14), shared device (R18), UPI handle pattern (R15, needs `upi_id`), device routes. A: `ScreeningService` can screen a name against the watchlist. | A: no loan data, no loan rules, no disbursement or fund-diversion logic. B: no new-beneficiary logic, no UPI-specific detector. The IBM AMLworld sample has no UPI handle, device or IP fields, so R15, R18 and R13 cannot fire on it. |
| 6 Common intelligence engine | Rules, ML anomaly, graph, correlation, explainable scoring (Critical / High / Medium / Low) | Partial | `RuleEngine`, PyOD anomaly, Louvain and centrality, typology classifier, explanations. | No cross-module alert correlation. `classify_risk_level` returns HIGH, MEDIUM and LOW only; there is no CRITICAL level. |
| 7 Response and investigation | Alert manager, intervention gateway, case management, assignment and approval, outcome | Partial | Alerts and live stream, escalation (PENDING to APPROVE or REJECT), immutable `CaseFile`, a separate fraud complaint case flow (OPEN to RESOLVED with a recorded decision), disposition feedback. | No intervention gateway. Two unconnected case concepts. No assignment. No Confirmed / False positive / Unresolved outcome set. STR submission is simulated *(per docs)*. |
| 8 Role-based application | Investigator, supervisor, regional management, bank admin, permission-aware views | Partial | Roles ADMIN, SUPERVISOR, INVESTIGATOR, READONLY, GUEST with permission strings (`infra/security/auth.py`). | No office, region or branch scoping. No regional management role. Dashboards are not permission-scoped. |
| 9 Mule Chat | Chat with permission-filtered retrieval | Partial | `genai_capabilities/chat.py` and alert analysis, triage and explanation capabilities. | Retrieval is not filtered by user permission. |
| 10 Security and governance | Audit trail, RBAC and ABAC, SSO and MFA, case scoping, secrets, model monitoring | Partial | SHA-256 hash-chained audit log with `verify_integrity`, JWT auth, RBAC, `production_validator`. | ABAC and case scoping, SSO and MFA, model monitoring wiring. The audit chain does not cover the STR workflow or logins *(per docs)*. |

### Diagram 2: institution hierarchy and permission evaluation

Status: **Planned**. The repo has global roles only.

Target model: platform, then institution (public or private), then bank administration and regional or zonal or business offices, then branches or departments, then assigned employees, then authorised cases. The permission decision is a function of three inputs: case assignment, institution and office, and user role.

### Diagram 3: sequence from bank event to explained alert

| Step | Status |
|---|---|
| Bank system sends an event, ingestion validates, normalises and de-duplicates | Partial (batch and optional Kafka, not a live bank connector) |
| Event processor, detection engine, mule network check, risk scoring, alert creation | Implemented for the mule path, in one process |
| Investigator is notified | Implemented (live stream) |
| Investigator opens the alert and reviews evidence | Implemented |
| Authorised hold or verification request sent to the bank, result returned | Planned. No bank system is connected, so this can only be a clearly labelled simulated adapter. |
| Mule Chat checks user permissions before explaining | Planned (see layer 9) |

## The seven product areas from the brief against the repo

| Area | Status | Reuse |
|---|---|---|
| Mule detection | Implemented | `DetectionPipeline`, graph, classifier |
| UPI and digital payment fraud | Partial | R14, R15, R17, R18, `realtime_scorer`, device routes, CBS `channel` field |
| Loan fraud | Planned | `ScreeningService` for borrower sanction checks only |
| Identity and account-opening fraud | Partial | `EntityResolutionService` (exact id plus fuzzy name and address, threshold 0.55), `OnboardingService`, onboarding and identity tables |
| Transaction and AML intelligence | Partial | R06, R12, R14, structuring and pass-through rules, STR service |
| Central investigation | Partial | `CaseAssemblyAgent`, `EscalationService`, `AuditService`, complaints case flow |
| Unified entity intelligence | Planned | Entity resolution is the only building block |

## Findings that change the plan

1. **Two case systems.** Alert cases (`CaseFile`, escalations) and fraud complaints (OPEN, decision) do not share a model. The investigation phase must put one workflow in front of both instead of building a third.
2. **No tenant or office data anywhere.** Diagram 2 needs a new data model before any permission-aware screen can be honest. This is a schema change and needs your approval before it touches Postgres.
3. **The demo data cannot exercise most of Diagram 1.** The IBM AMLworld sample has no loans, UPI handles, devices or IPs, and the detector alerts on none of it. The platform must show zeros and "no data" honestly.
4. **Risk levels differ.** The diagram shows four levels; the code has three.
5. **Return-fraud and complaints pages are outside the diagrams.** They stay behind the existing `EXTRA_PAGES_ENABLED` flag and out of the new main navigation.
6. **Name clash.** A Python package called `platform` would shadow the standard library. New backend code goes in `backend/fraud_modules/` and `backend/access/`; new frontend code goes in `frontend/src/shell/`.
