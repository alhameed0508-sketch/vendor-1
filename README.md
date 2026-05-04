# MuleCatch — Explainable Graph Intelligence for Mule Account Detection

> **IOB Hackathon Submission** · Built for Indian Overseas Bank

---

## What It Does

MuleCatch detects mule account networks by analysing **network topology** rather than individual transactions.

**Traditional AML sees rows. MuleCatch sees network topology.**

Criminal smurfing networks stay invisible to rule-based systems by keeping each transaction below ₹50,000. MuleCatch maps the full "social network of money" — accounts, devices, IP addresses — and identifies the cluster as a whole.

---

## Architecture

```
UPI Stream / CBS Logs
        │
        ▼
  [Kafka Queue]
        │
        ▼
  [Ingest Layer]  ── parses & validates
        │
        ▼
  [Neo4j Graph DB]  ── nodes: accounts, devices, IPs
        │            ── edges: transactions, shared fingerprints
        ▼
  ┌─────────────────────────────────────┐
  │     Three-Layer Detection Stack     │
  │  Layer 1: Rule Engine (fast)        │
  │  Layer 2: Smurf-Weighting Algo      │
  │  Layer 3: Louvain Community Detect  │
  │  Layer 4: GNN Scoring (optional)    │
  └─────────────────────────────────────┘
        │
        ▼
  [Alert + Subgraph]
        │
        ▼
  [Investigator Dashboard]
        │
        ▼
  [STR Export → FIU-IND]
```

---

## Key Features

| Feature | Details |
|---|---|
| Network topology detection | Louvain community detection on transaction graph |
| Smurf-weighting algorithm | Temporal velocity, amount ceiling, fan-out, rhythm scoring |
| Explainable alerts | Reason codes + visual subgraph for every alert |
| On-premise deployment | No data leaves IOB's environment |
| Sub-60s latency | Real-time detection pipeline |
| FIU-compatible STR export | RBI AML/CFT compliance built-in |
| Active learning | Investigator feedback improves model over time |
| No CBS changes | Parallel overlay — zero risk to core banking |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- 4GB RAM minimum

### Run the full stack

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your own NEO4J_PASSWORD and JWT_SECRET

# 2. Start all services
docker compose up -d --build

# 3. Wait for Neo4j + Kafka to become healthy
docker compose ps   # All services should show "healthy"

# 4. Seed the graph with synthetic data
docker compose run --rm seed

# 5. Open the dashboard
open http://localhost:3000

# 6. API docs
open http://localhost:8000/docs
```

### Run without Docker (dev mode)

```bash
# Backend
cd backend
pip install -r requirements.txt
PYTHONPATH=.. uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install --legacy-peer-deps
npm start
```

### Run tests

```bash
cd backend
PYTHONPATH=.. python -m pytest tests/ -v
```

### Production deployment

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## Project Structure

```
mulecatch/
├── backend/
│   ├── api/main.py              # FastAPI application (14+ endpoints)
│   ├── detection/pipeline.py    # 4-layer detection orchestrator
│   ├── graph_engine/
│   │   ├── neo4j_client.py      # Full Neo4j CRUD client
│   │   └── persistence.py       # Persistence abstraction (Neo4j + in-memory fallback)
│   ├── middleware/auth.py       # JWT auth + RBAC dependency injection
│   ├── ingest/
│   │   ├── cbs_parser.py        # CBS/UPI log parser
│   │   ├── kafka_consumer.py    # Real-time transaction consumer
│   │   └── kafka_producer.py    # Test data producer
│   ├── compliance/              # FIU STR generation
│   └── tests/                   # Pipeline + integration tests
├── frontend/src/
│   ├── investigator_dashboard/  # Alert queue
│   ├── alert_detail/            # Graph viz + case file + GNN scores
│   ├── roi_dashboard/           # KPI metrics + feedback stats
│   ├── compliance_portal/       # STR filing interface
│   └── graph_viz/               # D3 force-directed network graph
├── models/
│   ├── temporal_weighting/      # Smurf-weighting algorithm (5 signals)
│   ├── community_detection/     # Louvain implementation
│   ├── gnn/                     # GraphSAGE model (with graceful fallback)
│   └── active_learning/         # Investigator feedback loop + threshold tuning
├── data/
│   ├── synthetic/generator.py   # Mule cluster data generator
│   └── seed_graph.py            # Neo4j seeder
└── infra/
    ├── security/                # RBAC, audit logging (w/ rotation), TLS config
    └── certs/                   # Self-signed cert generation for demo
```

---

## Detection Logic

### Smurf-Weighting Algorithm (5 signals)

| Signal | Weight | Description |
|---|---|---|
| Velocity burst | 25% | > N transactions in 60-minute window |
| Amount ceiling | 25% | Amounts clustered just below ₹50,000 |
| Fan-out ratio | 20% | One account pushing to many recipients |
| Temporal rhythm | 15% | Regular intervals → bot-like automation |
| Rapid consolidation | 15% | Received then immediately re-sent |

### Louvain Community Detection

Builds a weighted graph where:
- **Edges** = transaction volume between accounts
- **Extra weight** added for shared device fingerprints
- Louvain partitions into communities; communities are scored for suspicion

### Reason Codes

Every alert ships with specific reason codes (RC01–RC05, CC01–CC04) that explain exactly why it was flagged — satisfying RBI's requirement for explainable, auditable decisions.

---

## KPI Claims (Methodology)

| Metric | Value | Methodology |
|---|---|---|
| Investigation time reduction | 75% | Baseline 4h manual → 1h with curated case file |
| False positive reduction | 40% | Synthetic dataset validation vs. rule-only baseline |
| Manpower saving | ₹Y lakh | FTEs freed × ₹500/hr fully-loaded cost |
| Fraud prevented | ₹X crore | Sum of flagged cluster transaction volumes |

---

## Deployment Model (PSB-Targeted)

- **No CBS changes** — reads from CBS/UPI logs via secure API/Kafka
- **On-premise** — all data stays within IOB's network perimeter
- **Encrypted** — TLS in transit, AES at rest
- **RBAC** — Investigator / Supervisor / Admin / ReadOnly roles
- **Audit trail** — every action logged (JSONL) for RBI compliance
- **Horizontally scalable** — add Neo4j nodes to handle peak load

---

## Monetisation

| Phase | Model |
|---|---|
| Pilot | Zero cost · limited scope · joint R&D |
| Pay-for-Value | X% of verified fraud losses prevented |
| Partnership | Co-development + cross-bank federated intelligence |

---

## Future Roadmap

1. **Cross-bank federated learning** — SMPC-based nation-wide threat intelligence
2. **API-first B2B platform** — embed MuleCatch intelligence in fintech partners
3. **Real-time CBS integration** — sub-5s alert generation via CDC streaming

---

*Built with: Python · FastAPI · Neo4j · GraphSAGE · Louvain · React · D3 · Kafka*