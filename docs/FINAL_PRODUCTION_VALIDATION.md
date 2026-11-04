# Final verification and production validation

Validation date: 2026-07-26  
Environment: Windows host, Python 3.12, Node 20, Docker Compose reference stack  
Verdict: **production-engineered candidate; not bank production-approved**

This report records the final repository, API, UI, container, dependency, and
sample-data verification. The complete local reference stack is operational.
External model, regulatory, security, and bank-infrastructure approvals listed
below remain mandatory before a real production launch.

## Automated verification

| Check | Result |
|---|---|
| Python source compilation | 202 files, 0 failures |
| Python lint | Pass |
| Backend tests | 492 passed |
| Frontend tests | 86 passed across 8 suites |
| Frontend optimized build | Pass |
| OpenAPI contract | 71 paths, 73 operations, 0 duplicate operation IDs |
| Docker backend image | Pass; non-root UID/GID 1001 |
| Backend process model | One Uvicorn worker per container |
| Docker Compose render | Pass |
| Kubernetes Kustomize render | Pass |
| Git whitespace/error check | Pass |
| Python dependency audit | No known vulnerabilities |
| npm high-severity audit gate | Pass |
| npm complete audit | 2 moderate React Router advisories; see residual risks |

The source-only line-coverage measurement, excluding test files, is 58.82%
(5,883 of 10,002 statements). Coverage is concentrated on the active detection
path:

| Area | Line coverage |
|---|---:|
| Detection pipeline | 90.99% |
| Supplied CSV adapter | 96.06% |
| Benchmark engine/API | 46.42% |
| Repository layer | 34.46% |
| Service layer | 51.66% |
| Model packages | 55.68% |

The test count is not represented as “every function is tested.” Optional
provider and prototype modules, including external LLM providers, some
India/scam/propensity models, and several PostgreSQL repository adapters, have
limited or no isolated unit coverage. Their production-facing integration
paths were checked where they are wired into the Compose runtime, but the
coverage gap remains measurable technical debt.

## Exact supplied-data end-to-end test

Input: `Sample Mule account data.csv`  
Size: 536,535 bytes  
SHA-256:
`CB570B25BC7FD65D815994EEDE93471F3892944F3022EFA68B2A899F9013A7C5`

The file was uploaded through the real multipart HTTP API in both an isolated
production image and the complete Compose stack.

| Result | Observed |
|---|---:|
| Source rows | 2,000 |
| Required fields | 13/13 |
| Accounts/customers | 19/19 |
| Unique transaction IDs | 2,000 |
| Normalized transactions | 1,946 |
| Inferred internal links | 54 |
| External-counterparty transactions | 1,892 |
| Alerts | 4, all critical |
| Community sizes | 4, 4, 5, 6 |
| Classifications | 10 complicit, 9 exploited |
| Pre-processing anomaly flags | 36 |
| Full alert graph payloads | Present |
| Upload/detection time in full stack | 43.24 seconds |

Twenty repeated preview requests returned the identical
`loaded=true, accounts=19, transactions=1946, alerts=4` result. The uploaded
dataset and all four full alert graph payloads remained available after a
backend container restart.

All five Model Benchmark controls were also exercised over real HTTP:
Synthetic, Adversarial, Cross-Validation, Comparison, and Full Evaluation.
Every action returned HTTP 200, and all saved result types were retrievable.

The input has no ground-truth mule labels, all rows share one timestamp, and
debit/credit legs do not share a stable transaction reference. The API
therefore correctly reports:

- `GROUND_TRUTH_LABELS_ABSENT`
- `TIMESTAMP_VARIETY_LOW`
- `TRAN_ID_LINKAGE_UNAVAILABLE`
- `DEBIT_CREDIT_IMBALANCE`
- linkage strategy `AMOUNT_DATE_INFERENCE`, confidence `LOW`

The observed alerts prove end-to-end execution and suspicious-pattern
detection. They do not establish production precision, recall, or
false-positive performance.

## Full-stack integration and resilience

The reference stack was rebuilt and started with PostgreSQL, Neo4j, Redis,
Kafka, backend, frontend, Prometheus, and Grafana. The strict `/ready` endpoint
returned HTTP 200 with Neo4j, PostgreSQL, Redis, and Kafka all `ok`.

Integration-only failures discovered and corrected during this run:

1. Uploaded datasets and alerts were process-local under multiple workers.
   Dataset and full alert payload persistence now use shared Redis/Neo4j
   contracts, and the container uses one worker with horizontal scaling.
2. Neo4j could not restart after an abrupt host shutdown because its PID file
   survived in the writable container layer. Its run directory is now
   ephemeral, and restart recovery passed.
3. Redis readiness called a nonexistent wrapper method. A guarded live
   `ping()` contract and test were added.
4. PostgreSQL imports collided with the root infrastructure package only in
   the packaged container. Production database imports are now unambiguous.
5. Development mode incorrectly converted failed dependency readiness into
   HTTP 200. `/ready` now reports real dependency state in every environment.
6. PostgreSQL additive schema setup could race across replicas and did not
   always commit. It now runs in one transaction under a PostgreSQL advisory
   lock.
7. Frontend health used IPv6 `localhost` while nginx listened on IPv4. The
   image and Compose probes now use `127.0.0.1`.
8. Frontend CSP allowed `unsafe-eval`. The deployed response now restricts
   scripts to `'self'`.
9. Benchmark results targeted a read-only data mount. Their path is now
   configurable and Compose writes them to the log volume.
10. Alert list/detail caches could span detection generations and return a
    listed alert that no longer existed. Current alert reads now come from the
    shared repository, while derived caches are scoped to model/timestamp
    generation.
11. Local tests could attach to a running developer stack. Test infrastructure
    endpoints are now pinned before application imports, making the 492-test
    run deterministic while Compose is active.

The final isolated-container shutdown completed cleanly with exit code 0,
`OOMKilled=false`, and explicit application-shutdown completion. The Neo4j
restart and backend reconnection tests both passed. The local Neo4j reference
memory allocation was reduced to avoid starving the backend in a constrained
Docker Desktop environment.

The live Compose stack had Kafka ingestion enabled during the resilience run.
After the frozen CSV snapshot and its restart assertion passed, subsequent
Kafka events correctly advanced the shared dataset. Exact CSV figures above
refer to the controlled snapshot, not to the later continuously mutating
streaming state.

## Time, audit, migration, and CI controls

- Application and model timestamp creation uses timezone-aware UTC values.
- PostgreSQL timestamp columns use `DateTime(timezone=True)`.
- STR PDF/report timestamps explicitly render UTC.
- The audit hash-chain migration is serialized and rejects partially migrated
  mixed hash state for operator review.
- Additive schema setup is transactional and cluster-serialized.
- CI runs lint, backend tests with coverage, frontend tests/build, Python and
  npm dependency audits, immutable image builds, and a Compose smoke test.
- Compose and Kubernetes manifests render successfully.
- Production startup rejects placeholder secrets, disabled authentication,
  plaintext data transports, unapproved model versions, and missing durable
  PostgreSQL configuration.

## Residual risks and mandatory go-live gates

The repository must not be described as production approved until all of the
following have dated evidence and named approvers:

1. Time-split validation on representative, de-identified bank data with
   confirmed outcomes; precision, recall, PR-AUC, calibration, segment
   fairness, and daily alert-capacity acceptance.
2. Independent model-risk validation and AML/compliance approval.
3. Bank IAM, HSM/secret manager, TLS certificates, private routes, managed
   high-availability PostgreSQL/Neo4j/Redis/Kafka, backup restore, and disaster
   recovery tests.
4. FIU-IND/FINGate schema, packaging, rejection, submission, and
   acknowledgement acceptance testing.
5. Penetration testing, privacy impact assessment, retention approval, load
   and soak testing, failover testing, and operational runbooks exercised by
   the responsible teams.
6. Upgrade or vendor remediation for the two moderate React Router advisories.
   The current client-side exposure is reduced by encoding untrusted alert IDs
   and rejecting external/backslash navigation; the SSR hydration advisory is
   not reachable in this client-rendered SPA. The dependency advisory remains
   open until a tested React Router 7 migration.
7. Increased automated coverage for optional provider, India/scam/propensity,
   and PostgreSQL adapter modules before those capabilities are enabled.

The checked-in Kubernetes base is deliberately a non-deployable production
template: placeholder secrets and plaintext reference-service settings are
rejected by the production validator. A bank-approved TLS overlay and external
secret provisioning are required.
