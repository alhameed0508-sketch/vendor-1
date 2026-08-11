# MuleCatch — Delta Register

**The gap between this codebase and a production AML control, recorded without softening.**

---

## Document control

| Field | Value |
|---|---|
| Purpose | Every gap, defect, absence, contradiction and unvalidated claim found while documenting the architecture, with severity and ownership |
| Audience | Pilot steering committee, internal audit, engineering leadership, model risk |
| Built from | All 12 forensic code inventories and all 11 documents in this set |
| Codebase | `master` @ `a7b05bf` |
| Method | Every row was verified in source. Language is deliberately direct: "absent" not "limited"; "never called" not "underused" |
| Related | [README](README.md) · [Executive summary](00-EXECUTIVE-SUMMARY.md) · every document `01`–`12` |

**Severity.** `CRITICAL` — wrong results, or a control that does not do what it claims.
`HIGH` — materially blocks a pilot or fails an audit question. `MEDIUM` — real defect, contained impact.
`LOW` — correctness or hygiene.

---

## Summary

**73 rows. 14 CRITICAL. 26 block a pilot.**

The distribution is the useful signal. Very few rows are architectural — the design is sound. The
overwhelming majority are **integration defects**: code that exists and is not reached, or two pieces of
code that disagree about a key name. Eight rows are one-line fixes and between them close four
user-visible features and two control gaps.

Three themes account for most of the CRITICAL rows:

1. **Producer/consumer key mismatches** silently void working features — six instances.
2. **`lru_cache` singletons holding mutable state** make the declared replica count produce wrong results.
3. **The audit chain omits exactly the events it exists to protect** — authentication and the whole STR lifecycle.

---

## A. Integration gaps — code that exists but nothing reaches, and features broken in integration

| # | Gap | Where | Current state | Required for | Severity | Blocks pilot? |
|---|---|---|---|---|---|---|
| A1 | SHAP panel renders every bar at zero width. Frontend reads flat `item.shap_value`; API returns nested per-account `shap_values`. **The only payload matching the UI is the error stub** | [ExplainabilityPanel.js:418-431](../../frontend/src/explainability/ExplainabilityPanel.js#L418-L431) vs [alert_service.py:559-565](../../backend/services/alert_service.py#L559-L565) | Feature dead | Explainability of an adverse decision | CRITICAL | Yes |
| A2 | `mule_type` is structurally always `None`. `classify_cluster` emits `cluster_classification`; narrative reads `classification` | [mule_classifier.py:353-355](../../backend/detection/mule_classifier.py#L353-L355) vs [narrative_generator.py:96-98](../../backend/explainability/narrative_generator.py#L96-L98) | Two UI badges never render | Complicit vs exploited distinction | CRITICAL | Yes |
| A3 | Regulatory explanation report is never in any response the UI reads; the fields it expects do not exist in the generator output | [ExplainabilityPanel.js:401](../../frontend/src/explainability/ExplainabilityPanel.js#L401) vs [shap_explainer.py:477-495](../../models/explainability/shap_explainer.py#L477-L495) | Panel never renders | Regulatory explainability | CRITICAL | Yes |
| A4 | Onboarding graph cross-check returns all zeros. App links devices to `:Account`; seeder links to `:Transaction`; the query matches the `:Account` pattern | [neo4j_client.py:238](../../backend/graph_engine/neo4j_client.py#L238) vs [seed_graph.py:90](../../data/seed_graph.py#L90) | Onboarding risk scored with graph signal absent, emitted as if run | Onboarding risk assessment | CRITICAL | Yes |
| A5 | STR PDF executive summary never prints. Reads `executive_summary`; key is `executive_brief` | [str_pdf.py:150,157](../../backend/api/str_pdf.py#L150) vs [narrative_generator.py:33](../../backend/explainability/narrative_generator.py#L33) | PDF section empty | STR quality | HIGH | No |
| A6 | STR PDF mule-classification always prints N/A. Reads `mule_type`, `type_confidence`, `sophistication_level`; the last two exist nowhere except `str_pdf.py` | [str_pdf.py:179-185](../../backend/api/str_pdf.py#L179-L185) | PDF section empty | STR quality | HIGH | No |
| A7 | Entire Neo4j graph write API has zero callers: `create_account`, `create_transaction`, `create_transactions_batch`, `link_shared_device`, `link_devices_batch`, `link_shared_ip`, `link_ips_batch` | [neo4j_client.py:89-181](../../backend/graph_engine/neo4j_client.py#L89-L181), [:374-426](../../backend/graph_engine/neo4j_client.py#L374-L426) | Transaction graph never persisted | Graph investigation, multi-hop tracing | CRITICAL | Yes |
| A8 | `ensure_indexes` never invoked. No Neo4j index or constraint is ever created; `alert_id` uniqueness unenforced | [neo4j_client.py:488](../../backend/graph_engine/neo4j_client.py#L488) | Unindexed alert reads | Performance, data integrity | HIGH | Yes |
| A9 | Neo4j read/traversal API has zero callers: `get_account_subgraph`, `get_cluster_subgraph`, `get_community_members`, `get_recent_transactions` | [neo4j_client.py:289-354](../../backend/graph_engine/neo4j_client.py#L289-L354) | Subgraph evidence not served from the graph | Investigation evidence | HIGH | No |
| A10 | `:Transaction` node is orphaned — no relationship ever connects it to `:Account` | [neo4j_client.py:126-157](../../backend/graph_engine/neo4j_client.py#L126-L157) | Schema defect; wiring the write path would create an unqueryable graph | Graph correctness | HIGH | Yes |
| A11 | Eleven `models/` packages reachable only from an uninjected `deps.py` provider: drift detector, typology classifier, response orchestrator, propensity scorer, scam victim detector, dual risk engine, FRI, Jan Dhan, crypto/gaming, UPI compliance, alert priority scorer | [deps.py:454-567](../../backend/api/deps.py#L454-L567) | Entire India-specific signal set and the priority model are unreachable | Claimed capability | CRITICAL | Yes |
| A12 | Two investigation agents have no route: `CaseAssemblyAgent`, `NarrativeAgent` | [deps.py:531-545](../../backend/api/deps.py#L531-L545) | Unreachable | — | MEDIUM | No |
| A13 | `GET /api/v1/device/stats` unreachable — shadowed by `GET /api/v1/device/{account_id}` registered earlier | [device.py:68](../../backend/api/v1/routes/device.py#L68) | Dead endpoint | — | MEDIUM | No |
| A14 | `PgSTRRepository` and `PgEscalationRepository` raise on their approve and resolve paths. The PostgreSQL configuration — the one a bank deploys — has broken STR approval | [pg_str_repository.py:33](../../backend/repositories/pg_str_repository.py#L33), [pg_escalation_repository.py:24](../../backend/repositories/pg_escalation_repository.py#L24) | Production-shaped path broken while tests pass on the in-memory variant | STR workflow | CRITICAL | Yes |
| A15 | `AlertRepository` and `DatasetRepository` have no PostgreSQL variant. The primary business object has no relational durability | [deps.py:178-180](../../backend/api/deps.py#L178-L180), [:213-215](../../backend/api/deps.py#L213-L215) | Alerts persist only to Neo4j-or-memory plus Redis | Durability | HIGH | Yes |
| A16 | `SlowAPIMiddleware` never installed; `default_limits` inert. Eight endpoints have no rate limit | [rate_limiter.py:24](../../backend/core/rate_limiter.py#L24) | Unthrottled endpoints incl. all ROI routes and `/ingest/stream` | Availability | HIGH | Yes |
| A17 | Rate limits key on `request.client.host` with uvicorn running without `--proxy-headers`. Behind nginx all callers share one bucket | [Dockerfile:60-65](../../backend/Dockerfile#L60-L65) | Limits do not isolate callers | Availability | HIGH | Yes |
| A18 | `paginated_response` is dead code — no endpoint paginates | [response.py:25-47](../../backend/core/response.py#L25-L47) | List endpoints return unbounded collections | Scale | HIGH | No |
| A19 | No endpoint declares `response_model`; OpenAPI documents no response bodies | `backend/api/**` | Contract unusable for integrators | Integration | MEDIUM | No |
| A20 | `ServiceUnavailableError` mapped to 503 but never raised | [error_handlers.py:25-32](../../backend/core/error_handlers.py#L25-L32) | Dead mapping | — | LOW | No |
| A21 | Three `escalations` columns never written: `resolved_action`, `resolution_notes` (service sends `supervisor_notes`), `user_id` | [init.sql:50-53](../../infra/database/init.sql#L50-L53) | Schema promises a supervisor-resolution trail the app does not record | Audit | HIGH | No |
| A22 | Three GenAI settings declared and never read: `genai_temperature`, `genai_max_tokens`, `genai_timeout_seconds` | [config.py:107-109](../../backend/core/config.py#L107-L109) | LLM call less configurable than it appears | Governance | MEDIUM | No |
| A23 | `/api/v1/run-detection` never called by the frontend and gated to demo mode only | [detection.py:30-34](../../backend/api/v1/routes/detection.py#L30-L34) | Manual detection unavailable in production | Operations | MEDIUM | No |
| A24 | `VALID_STATUSES` declared and never referenced | [str_repository.py:16](../../backend/repositories/str_repository.py#L16) | Only the transition table enforces state | — | LOW | No |

---

## B. Detection and model gaps

| # | Gap | Where | Current state | Required for | Severity | Blocks pilot? |
|---|---|---|---|---|---|---|
| B1 | Five rules name a time window the code never computes: R02 "in 24h", R11 "rapid", R13 "in 24h", R17 "rate doubling", R19 "within hours". None reads a timestamp | [pipeline.py:299-300](../../backend/detection/pipeline.py#L299-L300), [:371-379](../../backend/detection/pipeline.py#L371-L379), [:393-399](../../backend/detection/pipeline.py#L393-L399), [:426-430](../../backend/detection/pipeline.py#L426-L430), [:453-464](../../backend/detection/pipeline.py#L453-L464) | **Reason codes reaching investigators and STR narratives describe analysis that did not occur.** Rule outcome depends on batch cut, not behaviour | Regulatory defensibility | CRITICAL | Yes |
| B2 | R17 is a functional duplicate of R02. `avg_monthly=10`, factor 2 reduces to `outgoing > 20` | [pipeline.py:428-430](../../backend/detection/pipeline.py#L428-L430) | One behaviour double-counted | Scoring integrity | HIGH | No |
| B3 | R15 docstring claims a fraud-pattern watchlist; implementation is a bare digit-ratio heuristic with no lookup | [pipeline.py:410-416](../../backend/detection/pipeline.py#L410-L416) | Legitimate numeric handles fire | False positives | HIGH | No |
| B4 | R16 docstring claims a self-use check that is not implemented | [pipeline.py:420-423](../../backend/detection/pipeline.py#L420-L423) | Rule is weaker than described | Accuracy | MEDIUM | No |
| B5 | R11 infers bank identity from the first four characters of the recipient account id | [pipeline.py:379](../../backend/detection/pipeline.py#L379) | Meaningless against real account numbers | Cross-bank layering | HIGH | Yes |
| B6 | R17 uses a fixed `avg_monthly = 10` instead of a per-customer baseline | [pipeline.py:428](../../backend/detection/pipeline.py#L428) | Not a behavioural baseline | Accuracy | HIGH | No |
| B7 | Ensemble weights 50/30/20 are expert constants — not fitted, not segment-specific, output not probability-calibrated | [pipeline.py:1058-1118](../../backend/detection/pipeline.py#L1058-L1118) | Score is a ranking, not a probability | Model approval | CRITICAL | Yes |
| B8 | The rule engine contributes no weight to the ranking score | Same | 20 regulatory red flags do not affect ranking | Scoring design | MEDIUM | No |
| B9 | No rule threshold is configurable; all are code literals | [config.py:84-85](../../backend/core/config.py#L84-L85) | A committee-approved threshold change requires a deployment | Threshold governance | HIGH | Yes |
| B10 | 19 of 20 rules have no test. Only R01 is directly tested | `test_pipeline.py:137-155` | The layer producing regulatory justification is the least verified | Assurance | HIGH | Yes |
| B11 | Active-learning thresholds are computed and never read by the pipeline | [feedback_loop.py:27](../../models/active_learning/feedback_loop.py#L27) | The learning loop is open | Continuous learning claim | HIGH | No |
| B12 | `DriftDetector` has no caller outside its own test | [drift_detector.py:35](../../models/active_learning/drift_detector.py#L35) | No drift monitoring | Model monitoring | HIGH | No |
| B13 | Community-level alerting misses the isolated single-use mule; no account-level track exists | [05](05-GRAPH-LAYER.md) §3 | Structural blind spot | Coverage | CRITICAL | Yes |
| B14 | The analysed graph has no memory — a ring spanning two batches is analysed as two fragments | [05](05-GRAPH-LAYER.md) §4 | Bounds what the strongest layer can see | Detection quality | CRITICAL | Yes |
| B15 | Consolidation signal is suppressed to zero when a receive→forward pattern splits across batches | [smurf_weighting.py:226-246](../../models/temporal_weighting/smurf_weighting.py#L226-L246) | Evadable by pacing | Detection quality | HIGH | Yes |
| B16 | Two different SHAP modules with different feature sets and weights; neither marked authoritative | [shap_explainer.py:158](../../backend/explainability/shap_explainer.py#L158) vs [shap_explainer.py:349](../../models/explainability/shap_explainer.py#L349) | Two explanations of one alert can disagree | Retrospective reconstruction | CRITICAL | Yes |
| B17 | No GNNExplainer. SHAP explains a surrogate over engineered features, so subgraph-level attribution — the form this architecture needs — does not exist | [06](06-AI-AND-EXPLAINABILITY.md) §7 | Cannot explain "bridges two clusters" | Explainability | HIGH | No |
| B18 | GNN fallback is silent. Score shape is identical whether from a trained GNN or a heuristic | [pipeline.py:493](../../backend/detection/pipeline.py#L493) | Silent capability degradation | Model governance | HIGH | Yes |
| B19 | Reason codes are f-strings; no structured `{code, description, evidence}` and no triggering evidence | [pipeline.py:287](../../backend/detection/pipeline.py#L287) | Investigator sees that R07 fired, not which senders caused it | Investigation quality | HIGH | No |
| B20 | Rule evaluation is O(accounts × rules × transactions); most helpers rescan the full transaction list | [pipeline.py:281-293](../../backend/detection/pipeline.py#L281-L293) | First compute wall at bank volume | Scale | MEDIUM | No |
| B21 | Class docstring claims 19 behavioural indicators; 20 are defined | [pipeline.py:170](../../backend/detection/pipeline.py#L170) | Documentation defect | Accuracy | LOW | No |
| B22 | No PR-AUC, calibration, segment analysis or capacity analysis, though the model card lists all four as required | [MODEL_CARD.md](../MODEL_CARD.md) | Model unvalidated | Model approval | CRITICAL | Yes |
| B23 | Benchmark predictions are set membership, not a threshold sweep. No PR curve, no operating point | `runner.py:136-139` | Reported precision/recall is one arbitrary point | Model approval | HIGH | Yes |
| B24 | Synthetic generator seeds the global RNG once at import, so repeated runs diverge | [generator.py:15](../../data/synthetic/generator.py#L15) | Two identical-parameter runs gave mean F1 0.4158 and 0.2291 | Reproducibility | HIGH | Yes |
| B25 | σ(F1) 0.28–0.36 is computed by the harness and never surfaced in the UI | `runner.py:386-391` | Instability invisible to viewers | Transparency | MEDIUM | No |
| B26 | Five of ten cross-validation folds detected nothing (TP 0, F1 0.0) | [benchmark_results.json](../../data/benchmark_results.json) | Very low sensitivity on split data | Model approval | CRITICAL | Yes |
| B27 | Four benchmark runs flagged every legitimate account (`true_negatives: 0`) | Same | Unusable false-positive behaviour in those configurations | Model approval | HIGH | Yes |
| B28 | No metric on labelled real data exists anywhere | [SAMPLE_DATASET_VALIDATION.md](../SAMPLE_DATASET_VALIDATION.md) | Real-world accuracy unknown | Model approval | CRITICAL | Yes |
| B29 | Alert prioritisation is severity banding; the priority model is unreachable | [deps.py:550](../../backend/api/deps.py#L550) | Claimed capability unavailable | Triage quality | MEDIUM | No |

---

## C. Streaming and state gaps

| # | Gap | Where | Current state | Required for | Severity | Blocks pilot? |
|---|---|---|---|---|---|---|
| C1 | `replicas: 2` with process-local singleton detection state produces **incorrect** results — each replica sees a fraction of device events | [backend-deployment.yaml:10](../../infra/k8s/base/backend-deployment.yaml#L10) + [deps.py](../../backend/api/deps.py) | Shared-device detection depends on which pod took the traffic | Correctness | CRITICAL | Yes |
| C2 | No dead-letter topic. Verified by repo-wide search | [kafka_consumer.py](../../backend/ingest/kafka_consumer.py) | A bad message has no quarantine path | Reliability | HIGH | Yes |
| C3 | No schema registry, no Avro/Protobuf, no message version field | Same | Ad-hoc JSON contract | Reliability | HIGH | Yes |
| C4 | No event-time semantics. Processing time used throughout; missing timestamps backfilled with wall-clock now | [cbs_parser.py:22](../../backend/ingest/cbs_parser.py#L22) | Event ordering destroyed | Detection correctness | CRITICAL | Yes |
| C5 | No watermarks. Zero matches repo-wide | — | No lateness handling possible | Detection correctness | HIGH | Yes |
| C6 | No late-arrival handling | [kafka_consumer.py](../../backend/ingest/kafka_consumer.py) | Out-of-order records treated as fresh | Detection correctness | HIGH | Yes |
| C7 | No durable rolling feature state. `RollingPropensityScorer` history is an unbounded in-process dict with no eviction | [rolling_scorer.py:66](../../models/propensity/rolling_scorer.py#L66) | State lost on restart; unbounded growth | Reliability | HIGH | Yes |
| C8 | `PropensityStore.get_top_risk` sorts only the in-memory dict and never scans Redis | [propensity_store.py:93-100](../../backend/cache/propensity_store.py#L93-L100) | Top-risk view empty after restart | Operations | MEDIUM | No |
| C9 | `DeviceProfiler` state is process-local, unbounded, and shared across tenants via `lru_cache` | [deps.py:462-466](../../backend/api/deps.py#L462-L466) | Memory growth; cross-contamination | Reliability | HIGH | Yes |
| C10 | Detection runs synchronously inside the Kafka consumer thread; no queue, no worker pool | [kafka_consumer.py](../../backend/ingest/kafka_consumer.py) | Consumer lag is a direct function of detection latency | Throughput | HIGH | No |
| C11 | Only flow control is `max_poll_records=100`; no backpressure mechanism | Same | Unmanaged load | Reliability | MEDIUM | No |
| C12 | Kafka replication factor 1, 24-hour retention, no topic-provisioning job | [docker-compose.yml](../../docker-compose.yml) | No broker redundancy; 1-day replay window | Reliability | HIGH | Yes |
| C13 | No incremental/periodic split — community detection runs per batch, never over full history | [05](05-GRAPH-LAYER.md) §4 | Cross-batch rings invisible | Detection quality | CRITICAL | Yes |

---

## D. Security gaps

| # | Gap | Where | Current state | Required for | Severity | Blocks pilot? |
|---|---|---|---|---|---|---|
| D1 | Authentication **fails open** outside `ENV=production`. Default `auth_enabled=False`; bypass grants ADMIN to every caller | [config.py:32](../../backend/core/config.py#L32), [auth.py:50-60](../../backend/middleware/auth.py#L50-L60), [production_validator.py:49-53](../../backend/core/production_validator.py#L49-L53) | Staging, UAT and pilot run wide open by default | Any real data | CRITICAL | Yes |
| D2 | `/internal/metrics` has no auth and is publicly proxied by nginx, contradicting its own comment and [PRODUCTION_READINESS.md:26](../PRODUCTION_READINESS.md#L26) | [app.py:187-194](../../backend/api/app.py#L187-L194), [nginx.prod.conf:103-106](../../frontend/nginx.prod.conf#L103-L106) | Telemetry disclosed to anonymous callers | Confidentiality | CRITICAL | Yes |
| D3 | `AUDITOR` is a phantom role — in `READ_ROLES`, absent from `ROLE_PERMISSIONS`, resolves to an empty permission list | [auth.py:106](../../backend/middleware/auth.py#L106) | The internal-audit role can read nothing | Auditability | HIGH | Yes |
| D4 | Four permissions declared and never enforced: `config:read`, `config:write`, `alerts:delete`, `str:approve` | [auth.py:73-77](../../infra/security/auth.py#L73-L77) | Two authorisation mechanisms; the expressive one is dead | Access control | MEDIUM | No |
| D5 | Token revocation absent. A JWT stays valid until expiry regardless of logout or `is_active=false` | [09](09-SECURITY-ARCHITECTURE.md) §3.2 | Stolen session unrevocable | Access control | HIGH | Yes |
| D6 | No role gating in the UI — `ProtectedRoute` checks authentication only | [ProtectedRoute.js:9-36](../../frontend/src/auth/ProtectedRoute.js#L9-L36) | Capability disclosure | Usability, disclosure | MEDIUM | No |
| D7 | Default-role inconsistency: `READONLY` under `require_permission`, empty string under `require_role` | [auth.py:89](../../backend/middleware/auth.py#L89), [:105](../../backend/middleware/auth.py#L105) | Two guards disagree about one token | Access control | MEDIUM | No |
| D8 | `POST /api/v1/ingest/seed` gated only on being authenticated — a READONLY token can inject transactions into the pipeline | [ingest.py:98](../../backend/api/v1/routes/ingest.py#L98) | Privilege gap | Integrity | HIGH | Yes |
| D9 | No field-level encryption or tokenisation for any PII — no pgcrypto, no KMS, no vault | [init.sql](../../infra/database/init.sql) | Breach exposes data directly | Confidentiality | HIGH | Yes |
| D10 | Full name and postal address stored plaintext (rapidfuzz requires cleartext) | [init.sql:107,110](../../infra/database/init.sql#L107) | Most identifying attributes unprotected | Confidentiality | HIGH | Yes |
| D11 | No mTLS on any boundary; nginx→backend is plaintext HTTP | [09](09-SECURITY-ARCHITECTURE.md) §5 | Unauthenticated internal transport | Confidentiality | HIGH | Yes |
| D12 | No `NetworkPolicy` in any of the 16 Kubernetes manifests | [infra/k8s/base/](../../infra/k8s/base/) | One compromised pod reaches all four datastores | Segmentation | HIGH | Yes |
| D13 | Kafka defaults to `PLAINTEXT` | [config.py:25](../../backend/core/config.py#L25) | Unencrypted event transport | Confidentiality | HIGH | Yes |
| D14 | No secret scanning and no SAST in CI (no gitleaks, no bandit) | [ci.yml](../../.github/workflows/ci.yml) | Secrets and code flaws unscanned | Assurance | HIGH | Yes |
| D15 | `security-scan` is **not** in `docker-build.needs` — an image can publish while the scan fails | [ci.yml:133](../../.github/workflows/ci.yml#L133) | Control does not gate the release path | Assurance | CRITICAL | Yes |
| D16 | Committed plaintext development secrets in CI config and Compose | [ci.yml:41,185-186](../../.github/workflows/ci.yml#L41), [docker-compose.yml](../../docker-compose.yml) | Credentials in source history | Hygiene | MEDIUM | No |
| D17 | No secrets manager or KMS integration; documented as an external prerequisite only | [kustomization.yaml](../../infra/k8s/base/kustomization.yaml) | Manual secret provisioning | Key management | HIGH | Yes |
| D18 | `.env.production.example` would fail the production validator — non-TLS Redis, no PostgreSQL `sslmode`, Kafka `PLAINTEXT`, `MODEL_VERSION=unvalidated-dev` | `.env.production.example` | The shipped production template cannot start | Operations | MEDIUM | No |
| D19 | Unhandled 500s raised in `ServerErrorMiddleware` sit outside audit, metrics, security-header and CORS middleware | [app.py:76-202](../../backend/api/app.py#L76-L202) | The most serious failures are unrecorded | Auditability | HIGH | Yes |
| D20 | No `ResourceQuota`, `LimitRange`, or Pod Security Admission labels | [infra/k8s/base/](../../infra/k8s/base/) | No namespace-level guardrails | Containment | MEDIUM | No |
| D21 | LDAP transport defaults to plaintext `ldap://`; client passes no TLS object and has no certificate validation configuration | [ldap_client.py:43](../../infra/ldap/ldap_client.py#L43) | Credentials in clear if enabled without `ldaps://` | Confidentiality | MEDIUM | No |

---

## E. Audit and compliance gaps

| # | Gap | Where | Current state | Required for | Severity | Blocks pilot? |
|---|---|---|---|---|---|---|
| E1 | **The entire STR lifecycle is unchained** — create, approve, submit, acknowledge produce no audit record | [str_service.py](../../backend/services/str_service.py) | No tamper-evident record of who filed a report | PMLA record-keeping | CRITICAL | Yes |
| E2 | **The approver of record is the literal `'demo_user'`** — the authenticated principal is never used | [CompliancePortal.js:30,130](../../frontend/src/compliance_portal/CompliancePortal.js#L30) | Separation of duties enforced in the request, lost in the record | Maker-checker | CRITICAL | Yes |
| E3 | Authentication events unchained — login, logout, token refresh | [auth.py](../../backend/api/v1/routes/auth.py) | No access trail | Auditability | HIGH | Yes |
| E4 | CSV upload, screening, onboarding, benchmark and detection runs unchained | [09](09-SECURITY-ARCHITECTURE.md) §6 | Partial audit coverage | Auditability | HIGH | No |
| E5 | Audit chain has no external anchor; any principal able to write can recompute it | [03](03-DATA-ARCHITECTURE.md) §7 | Tamper-evident, not tamper-proof | Evidentiary weight | HIGH | Yes |
| E6 | Application role retains `UPDATE`/`DELETE` on `audit_logs`; append-only not enforced at the database | [init.sql:29-38](../../infra/database/init.sql#L29-L38) | Chain relies on application discipline | Auditability | HIGH | Yes |
| E7 | **No foreign key exists anywhere in the schema.** An audit or escalation row can reference a non-existent alert | [init.sql](../../infra/database/init.sql) | Referential integrity unenforced for evidentiary records | Record-keeping | HIGH | Yes |
| E8 | All indexes exist only in `init.sql`, a container entrypoint script. A deployment bootstrapped by `ensure_tables()` gets none — including `idx_audit_ts`, read on every audit write | [init.sql:26-167](../../infra/database/init.sql#L26) | Audit write path degrades as the table grows | Performance | HIGH | Yes |
| E9 | FINGate/FIU-IND transmission entirely simulated; reference minted from a local UUID; no endpoint, credential or certificate setting exists | [str_service.py:83](../../backend/services/str_service.py#L83) | No regulatory filing capability | Reporting obligation | CRITICAL | Yes |
| E10 | No FIU-IND schema conformance evidence exists in the repository | — | Conformance unverified | Reporting obligation | HIGH | Yes |
| E11 | `READY_FOR_SUBMISSION → DRAFT` is legal in the transition table but no service method or route implements it. An approved STR cannot be withdrawn | [str_repository.py:18](../../backend/repositories/str_repository.py#L18) | No correction path | Governance | HIGH | Yes |
| E12 | API response and persisted STR never share an identifier — generator returns `STR_XXXXXXXX`, service mints `STR-XXXXXXXXXX` | [str_service.py:32](../../backend/services/str_service.py#L32) | A caller cannot retrieve what it created | Correctness | HIGH | No |
| E13 | Generator reports `READY_FOR_SUBMISSION` while the repository forces `DRAFT` | [str_repository.py:34](../../backend/repositories/str_repository.py#L34) | Client believes a report is approved when it is not | Correctness | HIGH | No |
| E14 | `str-export` creates STR drafts as a side effect, in a loop | [compliance.py:43-57](../../backend/api/v1/routes/compliance.py#L43-L57) | An export silently generates regulatory drafts | Governance | MEDIUM | No |
| E15 | STR submission requires `ADMIN`, conflating a technical administrator with a regulatory filing officer | [compliance.py:153](../../backend/api/v1/routes/compliance.py#L153) | Wrong role model for a bank | Governance | MEDIUM | No |
| E16 | No retention, archival, deletion or legal-hold policy in code or configuration | — | Statutory retention unmanaged | PMLA retention | HIGH | Yes |
| E17 | `bias_assessment` does not exist anywhere in the repository, though the UI reads a field of that name | [06](06-AI-AND-EXPLAINABILITY.md) §4 | No fairness assessment | Responsible AI | HIGH | No |
| E18 | No customer grievance, unfreeze or remediation path; the customer is not an actor | [01](01-CONTEXT-AND-SCOPE.md) §2 | No remediation for a wrongly restricted account | Customer fairness | HIGH | Yes |
| E19 | Alert context leaves the bank perimeter to an external LLM provider; no data-residency decision recorded | [backend/genai/](../../backend/genai/) | Unresolved residency question | Data protection | HIGH | Yes |
| E20 | No shadow mode — detection cannot run without surfacing output | [08](08-PLATFORM-AND-DEPLOYMENT.md) §6 | Blocks the parallel-run study that would validate the detector | Model validation | CRITICAL | Yes |

---

## F. Availability and recovery gaps

| # | Gap | Where | Current state | Severity | Blocks pilot? |
|---|---|---|---|---|---|
| F1 | **PostgreSQL has no backup path** — and it holds the audit chain and every STR | — | Total loss risk for statutory records | CRITICAL | Yes |
| F2 | Neo4j backup script exists with **no cron, CronJob or scheduler anywhere** | [neo4j_backup.sh](../../infra/backup/neo4j_backup.sh) | Backup never runs | HIGH | Yes |
| F3 | No Redis persistence configured, though Redis holds the cross-worker alert list | [docker-compose.yml](../../docker-compose.yml) | Alert visibility lost on restart | HIGH | No |
| F4 | No restore ever exercised; no documented restore path | — | Recovery unproven | HIGH | Yes |
| F5 | RPO and RTO undefined | — | `TARGET — UNVALIDATED` | HIGH | Yes |
| F6 | All datastores single-instance; no PostgreSQL replication, Neo4j cluster or Redis Sentinel | [infra/k8s/base/](../../infra/k8s/base/) | No datastore HA | HIGH | No |
| F7 | No `startupProbe`; liveness `initialDelaySeconds: 45` with a torch/shap cold start risks a restart loop | [backend-deployment.yaml](../../infra/k8s/base/backend-deployment.yaml) | Slow boot may never succeed | MEDIUM | No |
| F8 | No HPA or autoscaling in any manifest | Same | Manual scaling only | LOW | No |
| F9 | No Kustomize overlays; `base` only, differentiated by ConfigMap content alone | [infra/k8s/base/](../../infra/k8s/base/) | No per-environment manifests | MEDIUM | No |
| F10 | Compose `deploy.resources` limits are Swarm-only and do not constrain `docker compose up` | [docker-compose.yml](../../docker-compose.yml) | Limits decorative in development | LOW | No |
| F11 | Only one Grafana dashboard, covering API performance — no detection-quality, queue-depth or model-fallback panels; no alerting rules | [infra/monitoring/](../../infra/monitoring/) | Detection health unobservable | MEDIUM | No |
| F12 | `integration-test` runs **after** `docker-build`, so integration failures are found post-artifact | [ci.yml:176-177](../../.github/workflows/ci.yml#L176-L177) | Late feedback | LOW | No |

---

## G. `TARGET — UNVALIDATED` figures and documentation contradictions

| # | Claim | Where asserted | Verdict | What would validate it |
|---|---|---|---|---|
| G1 | "75% investigation time reduction" | **A database column default** at [init.sql:127](../../infra/database/init.sql#L127), surfaced via the ROI dashboard | **CONTRADICTED** — it is a default, not a measurement | A time-and-motion study against the incumbent process |
| G2 | "40% false positive reduction" | Project documentation | **UNSUBSTANTIATED** | Real-data FP measurement against the bank's rule baseline |
| G3 | "Internal metrics no longer publicly exposed" | [PRODUCTION_READINESS.md:26](../PRODUCTION_READINESS.md#L26) | **CONTRADICTED** — the ingress was hardened, nginx was not | Remove the nginx location block |
| G4 | "FIU-IND v2.1 compatible" | Project documentation | **UNSUBSTANTIATED** | Conformance testing against the current published schema |
| G5 | "19 behavioural patterns aligned with RBI/RBIH MuleHunter" | [pipeline.py:170](../../backend/detection/pipeline.py#L170) | **CONTRADICTED** — 20 rules are defined | Correct the docstring; publish a rule-to-indicator mapping |
| G6 | "Green CI" | Project documentation | Previously **CONTRADICTED** (lint was failing on ~101 findings, since fixed); the residual contradiction is D15 — `security-scan` does not gate the build | Add `security-scan` to `docker-build.needs` |
| G7 | Best-case benchmark figures quoted without spread | [benchmark_results.json](../../data/benchmark_results.json) | **Misleading if quoted singly** — σ(F1) is 0.28–0.36 and 5 of 10 folds found nothing | Report ranges and standard deviations; add a PR curve |
| G8 | Any throughput, latency, TPS, RPO or RTO figure | Nowhere sourced | `TARGET — UNVALIDATED` | Load testing and a recovery exercise |
| G9 | "Production-ready" | Project documentation | **Readiness is the bank's judgement, not the repository's** | The gates in §H |

---

## H. External evidence gates — cannot be closed by source code

| Gate | Evidence required | Who must supply it | Blocks |
|---|---|---|---|
| Detector validation | De-identified labelled historical data; defined mule-label and disposition taxonomy; time-based splits | Bank | Model approval, pilot |
| Operating point | Approved thresholds tied to an alert-capacity and false-positive budget | Bank risk committee | Production use |
| Independent validation | Validation report from a function independent of the build | Bank model risk | Production use |
| Baseline comparison | Alert overlap and volume versus the incumbent rule engine | Bank + shadow mode (E20) | Business case |
| Regulatory filing | Reporting-entity credentials; schema conformance; submission, rejection and acknowledgement acceptance testing | Bank + FIU-IND | Reporting capability |
| FRI integration | Live endpoint access and credentials | Bank + RBI | India-specific signals |
| Identity | Bank IAM/LDAP integration and group mapping | Bank | Production auth |
| Secrets and certificates | Production secret provisioning, KMS, TLS certificates | Bank | Production deployment |
| Security assurance | Penetration test and remediation evidence | Bank + external tester | Production use |
| Resilience | Backup and restore exercise with agreed RPO/RTO | Bank | Production use |
| Data residency | Decision on external LLM egress (E19) | Bank legal and DPO | Pilot |
| Approval to operate | Legal, compliance, security and model-risk sign-off | Bank | Production use |

---

## The eight one-line fixes

Verified as single-line or near-single-line changes, closing a disproportionate share of this register.

| Fix | Closes | Effect |
|---|---|---|
| Rename `classification`/`reasoning` → `cluster_classification`/`cluster_reasoning` in the narrative reader | A2 | Restores mule typology, two UI badges, and the narrative paragraph |
| Flatten the `/shap` response, or map nested→flat in the panel | A1 | Restores SHAP attribution rendering |
| Rename `executive_summary` → `executive_brief` in `str_pdf.py` | A5 | Restores the STR PDF executive summary |
| Add `security-scan` to `docker-build.needs` | D15 | Makes the security gate actually gate |
| Delete the `/internal/metrics` location block from `nginx.prod.conf` | D2, G3 | Removes the public telemetry exposure |
| Call `ensure_indexes()` from the application lifespan | A8 | Creates the Neo4j constraint and three indexes |
| Set `replicas: 1` until detection state is externalised | C1 | Removes the correctness defect |
| Add an `AUDITOR` entry to `ROLE_PERMISSIONS` | D3 | Makes the internal-audit role usable |

Two further changes are small but not one-line, and are the highest-value security work available:
**chain the STR lifecycle into the audit hash chain** (E1) and **use the authenticated principal for
`approved_by`** (E2). Together they convert the filing workflow from procedurally correct to
evidentially sound.
