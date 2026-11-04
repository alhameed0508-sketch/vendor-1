# Deployment runbook

## Before deployment

1. Record change ticket, release commit, image digest, model version, rule
   version, schema version, owner, approver, and rollback owner.
2. Provision secrets externally. Do not apply `secrets.yaml`.
3. Pin production image tags to immutable digests; never deploy `latest`.
4. Confirm TLS, private networking, firewall policy, backup encryption, and
   retention settings.
5. Validate model artifact checksum and approval record.
6. Refresh approved watchlists and record source timestamp/checksum.
7. Run backend/frontend tests, dependency audits, image scanning, and manifest
   policy checks.

## Deploy

```bash
kubectl apply -k infra/k8s/base
kubectl -n mulecatch rollout status deployment/backend
kubectl -n mulecatch rollout status deployment/frontend
```

The base expects a pre-existing `mulecatch-secrets` Secret. The checked-in
single-node data-store manifests are development/reference infrastructure and
intentionally fail the production transport validator. A production overlay
must point the application at bank-operated TLS-enabled PostgreSQL, Neo4j,
Redis, and Kafka services and mount the corresponding CA/client material.

## Verify

- `/health` returns HTTP 200.
- `/ready` returns HTTP 200 and every required dependency is `ok`.
- Authentication rejects missing/invalid tokens.
- An authorized test event is consumed once.
- The alert records the approved model and rule versions.
- Audit integrity returns `valid: true`.
- Metrics are reachable only from the monitoring network.
- No synthetic/demo banner, data, or fallback is present.

## Rollback

1. Stop or pause ingest if the release can generate incorrect decisions.
2. Roll back application images to the last approved immutable digest.
3. Do not reverse an irreversible schema migration without a tested script.
4. Replay Kafka only after idempotency and offset ownership are confirmed.
5. Reconcile alert counts, offsets, audit-chain head, and database records.
6. Record impact, affected decisions, customer remediation, and incident owner.

## Backup and recovery

- PostgreSQL: encrypted point-in-time recovery with restore tests.
- Neo4j: consistent encrypted backups with restore tests.
- Kafka: replicated topics and retention exceeding recovery requirements.
- Audit: export hash-chain head to protected/WORM storage on an approved
  schedule.
- Model/rules: immutable artifact registry with checksums and approvals.

## Operational alerts

Page an operator for:

- `/ready` failure
- Kafka consumer stopped or repeated errors
- offset/consumer lag above the approved threshold
- database pool exhaustion
- audit-chain verification failure
- watchlist age above policy
- model/rule version mismatch
- elevated authentication failures
- P99 latency or alert-volume anomaly
