# MuleCatch

MuleCatch is an explainable graph-intelligence platform for detecting and
investigating mule accounts. It combines deterministic AML indicators,
behavioral and temporal profiling, device intelligence, graph-community
detection, optional learned scoring, sanctions screening, investigation
workflows, and Suspicious Transaction Report preparation.

## Readiness statement

The repository is engineered as a production candidate, not a certified
bank-production release. Deployment is blocked by startup validation until
durable services, strong secrets, authentication, streaming ingestion, and
approved model/rule versions are configured. Final go-live additionally
requires bank-labelled validation data, security testing, FIU-IND filing
validation, and institutional approvals.

See:

- [Production readiness and external gates](docs/PRODUCTION_READINESS.md)
- [Deployment runbook](docs/DEPLOYMENT_RUNBOOK.md)
- [Model card](docs/MODEL_CARD.md)
- [Regulatory control matrix](docs/REGULATORY_CONTROL_MATRIX.md)

## Architecture

```text
CBS / UPI / approved batch feeds
             |
             v
      Kafka ingest layer
   (manual offset commit, replay guard)
             |
             v
  Rules + temporal + behavioral + device
             |
             v
   Louvain graph communities + optional GNN
             |
             v
 Explainable, versioned alert and subgraph
             |
      +------+------+
      |             |
 Investigator    STR workflow
 workflow        and audit chain
```

Runtime services:

- FastAPI API
- React investigator interface
- PostgreSQL operational persistence
- Neo4j investigation graph
- Redis cache/state
- Kafka transaction ingestion
- Prometheus and Grafana monitoring

## Implemented controls

- Onboarding mule-risk assessment
- UNSC watchlist screening with controlled refresh
- Twenty deterministic behavioral indicators
- Smurf/structuring and rapid-consolidation scoring
- Behavioral baseline and Markov lifecycle analysis
- Device and shared-infrastructure risk
- Louvain community detection and centrality
- Optional GraphSAGE or lightweight fallback scoring
- SHAP-style feature explanations and reason codes
- Alert triage, escalation, notes, and subgraph investigation
- STR draft/approval/submission-state workflow
- Role-based access and rate limiting
- Tamper-evident audit hash chain
- Strict production readiness and secret validation
- Model and rule version attribution on alerts

## Local development

```bash
cp .env.example .env
docker compose up -d --build
docker compose --profile seed run --rm seed
```

Open:

- Application: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`
- Liveness: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/ready`

Development mode intentionally supports synthetic data and in-memory
fallbacks. These behaviors are rejected or disabled in production mode.

## Tests

```bash
python -m pytest backend/tests -q
cd frontend
npm test -- --watchAll=false
npm run build
```

CI performs linting, backend/frontend tests, builds, dependency audits,
container builds, and a Compose smoke test. High-severity dependency findings
are build-blocking.

## Production deployment

Do not deploy from the example configuration unchanged.

Required minimum actions:

1. Provision `mulecatch-secrets` using the institution's secret manager.
2. Set an approved `MODEL_VERSION` and governed `RULE_VERSION`.
3. Configure PostgreSQL, Neo4j, Redis, Kafka, TLS, CORS, and authentication.
4. Load approved model artifacts and watchlists.
5. Execute the validation and rollback procedures in the runbook.
6. Complete every external gate in `docs/PRODUCTION_READINESS.md`.

Kubernetes intentionally does not create the application Secret. The
`infra/k8s/base/secrets.yaml` file is an unapplied example only.

## Important limitations

- FRI integration has a safe interface but the live government API adapter is
  not implemented without an institutional endpoint and credentials.
- FIU/FINGate submission is represented as a controlled workflow; actual
  portal submission and acknowledgement exchange require reporting-entity
  credentials and schema acceptance testing.
- Synthetic and PaySim results are development evidence, not proof of bank
  production effectiveness.
- The `/benchmarks` workspace provides five executable evaluation programs:
  synthetic, adversarial holdout, deterministic cross-validation,
  configuration comparison, and a combined full evaluation. See
  [Model benchmark programs](docs/MODEL_BENCHMARKS.md).
- No automated model decision should directly freeze or close an account
  without the bank's approved policy, human review, and applicable legal
  process.

## Technology

Python, FastAPI, React, Neo4j, PostgreSQL, Redis, Kafka, NetworkX,
PyTorch/PyTorch Geometric, PyOD, RapidFuzz, Docker, Kubernetes, Prometheus,
and Grafana.

See [open-source integrations](docs/OPEN_SOURCE_INTEGRATIONS.md) for adopted
GitHub projects, license/decision guardrails, and deliberately deferred
bank-scale components.
