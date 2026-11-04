# Spec: stream-api (branch `stream-api`)

Goal: server-sent events that replay payments through `RealtimeScorer` for the live demo.

- Add `GET /api/v1/score/stream` in `backend/api/v1/routes/score.py` (SSE, demo mode only; 409 in production like the benchmark routes).
- Replay a held-out slice of synthetic payments (seeded, labels stripped via `services/realtime_demo.strip_labels`) at a configurable rate.
- Each event: `{payment, decision, case_id, ring_members, risk_score, latency_ms}`.
- Keep labels server-side to maintain counters `payments`, `flagged`, `genuine_flagged`, `mule_flagged`. Send counters in each event. Never send `role` or other label fields.
- Tests first: event shape, no label fields in any event, 409 outside demo mode.
- Do not change `RealtimeScorer` behaviour or `ENDPOINT_EVIDENCE_MIN`.
- Replay is trusted ingest: call `score_payment(payment, commit=True)`. The public `POST /score` uses `commit=False` and must stay read-only.
