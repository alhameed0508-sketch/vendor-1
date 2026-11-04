# Unified risk engine API (`/api/v1/risk`)

The unified engine scores one payment in the context of the customer, the device session, the payee and the
mule network, and returns a 0–100 score, a band and the reasons. The mule-detection core
(`services/realtime_scorer.py`, `detection/ring_decision.py`) stays the centre. Its ring map is one of the
four engines, and its alert queue and complaint register feed the other three. Design:
[SYSTEM_DESIGN.md](SYSTEM_DESIGN.md). Evaluation: [RISK_ENGINE_EVALUATION.md](RISK_ENGINE_EVALUATION.md).

**Nothing here blocks a customer.** `STEP_UP` means extra verification (payee name shown, PIN re-entry, scam
warning). `REVIEW` holds the payment for a person, as the bank's policy allows. `DECLINE` exists in the
configuration but is switched off.

All responses use the platform envelope `{"success": true, "data": …}`. Errors use
`{"success": false, "error": {"code", "message", "details"}}`.

## Roles

| Endpoint | ADMIN | SUPERVISOR | INVESTIGATOR | AUDITOR | GUEST (demo only) |
|---|---|---|---|---|---|
| `POST /risk/events` (commit) | ✓ | | | | |
| `POST /risk/assess` (what-if) | ✓ | ✓ | ✓ | | |
| `POST /risk/decisions/{id}/feedback` | ✓ | ✓ | ✓ | | |
| Every `GET`, `POST /risk/scenarios/{name}/run` | ✓ | ✓ | ✓ | ✓ | ✓ |

Guest tokens are refused outside demo mode (`ENV=production`), so in production the read endpoints are staff-only.

## The payment event

```json
{
  "txn_id": "UPI-20261104-000123",
  "from_account": "CUST-1042",
  "to_account": "PAYEE-77",
  "amount": 85000,
  "timestamp": "2026-11-04T15:40:00+05:30",
  "session": {
    "session_id": "S-9f2", "device_id": "DEV-a1", "ip": "49.36.10.20", "city": "Pune",
    "lat": 18.52, "lon": 73.86, "typing_ms_per_char": 210, "remote_access": false,
    "device_flags": [], "auth_events": [{"type": "password_reset", "at": "2026-11-04T15:25:00+05:30"}]
  },
  "context": {
    "channel": "UPI_PUSH", "beneficiary_added_at": "2026-11-04T15:34:00+05:30", "on_call": true,
    "note": "kyc update", "app_switch_count": 6, "amount_pasted": true, "backspace_count": 0,
    "payee_name": ""
  }
}
```

Only the first five fields are required. Every session and context field is optional: an engine without the
data it needs says so (`data_available: false`) and contributes nothing. It never guesses. Timestamps must
be ISO-8601. Payer and payee must differ, and the amount must be positive.

## Endpoints

### `POST /risk/events`: trusted ingest (commit)
Scores the payment, then commits it to the customer's profile, the device log and the mule ring window.
- **Idempotent on `txn_id`.** Re-sending the same payment returns the original decision and changes nothing.
- **409** if the same `txn_id` arrives with a different payer, payee, amount or timestamp.
- Non-approved decisions are written to PostgreSQL (`risk_decisions`) through a write-behind queue when
  `POSTGRES_URL` is set.

### `POST /risk/assess`: what-if for staff
Same scoring and explanation, with nothing committed. A what-if never records its `txn_id`, so it can't
block or pre-empt the real payment arriving later through `/risk/events`.

### Decision object (both of the above)

| Field | Meaning |
|---|---|
| `score`, `band` | 0–100 and APPROVE / STEP_UP / REVIEW (bands from `RISK_STEP_UP_AT`, `RISK_REVIEW_AT`) |
| `confidence` | how much history the customer has (0–1); a thin baseline cannot hold a payment |
| `engines` | each engine's score (noisy-OR of its reasons after familiarity dampening) |
| `reasons[]` | `code`, `text`, `strength`, `kind` (`decisive`, `strong`, `weak`, `familiarity`), `engine`, `dampened` |
| `contributions` | exact log-odds contribution of each model feature |
| `explanation` | `summary`, `action`, `model` (version, probability, raw score, features, log-odds), per-engine detail, `familiarity`, `corroborating_engines`, `false_positive_controls` (what was capped and why), `personal_limit` |
| `source` | `ingest`, `api` (what-if), `synthetic` (demo traffic), `scenario`, `live` |
| `label` | ground truth, **only** for `synthetic` and `scenario` sources (from the simulator); never used for scoring |
| `latency_ms`, `model_version`, `committed`, `outcome*` | as named |

Reason codes: MN01–MN03 (mule network, core), SD01–SD10 (session & device), BI01–BI10 (payment intent &
payee), BH01–BH04 (behaviour), FC01–FC03 (familiarity, calming). The full table is in SYSTEM_DESIGN.md §6.3.

### `GET /risk/decisions?limit=&band=&min_score=&source=`
Recent decisions (summary form, top three reasons), newest first, plus the store `sequence` number.

### `GET /risk/decisions/{decision_id}`
One decision in full. **404** if unknown or aged out of memory (the PostgreSQL log keeps non-approved ones).

### `POST /risk/decisions/{decision_id}/feedback`
`{"outcome": "CONFIRMED_FRAUD" | "FALSE_ALERT", "note": "…"}`. Written to the tamper-evident audit chain
(`RISK_DECISION_FEEDBACK`).
- `FALSE_ALERT` adds the payee, device and city to the customer's trusted sets, so the same false alert does
  not repeat.
- `CONFIRMED_FRAUD` adds the payee to the known-fraud registry (BI01, decisive) for every customer.

### `GET /risk/metrics`
Band counts by source, engine activity, top reason codes, score histogram, hourly bands, measured decision
latency (p50/p95), analyst outcomes, and `synthetic_labelled`. That last block holds genuine-interrupted
rate, fraud-caught rate and REVIEW precision, computed **only** from labelled synthetic events. It also
returns the demo-traffic state.

### `GET /risk/stream?source=demo|live&limit=`
Server-sent events. Read with `fetch` so the token stays in the `Authorization` header.
- `source=demo`: tails the shared engine's synthetic background traffic (demo mode only; **409** otherwise).
  Each event carries `provenance.provider = "MuleCatch journey simulator"`.
- `source=live`: **real public Bitcoin payments** from mempool.space, scored by a *private* engine that never
  touches the shared one. Each event carries `provenance.url` (the transaction on mempool.space),
  `observed_at` and the INR rate used. These payments have no session, device or customer data, so only the
  mule, payee and behaviour engines can speak. There is no ground truth: a hold is a lead, not a measured
  catch. Available in demo mode or with `LIVE_FEED_ENABLED=true`. A provider outage ends the stream with an
  `event: error` frame.

### `GET /risk/scenarios`, `POST /risk/scenarios/{name}/run`
The brief's worked cases, replayed on an isolated engine with synthetic history:
`customer_a_vs_b`, `app_scam_mule_payee`, `stolen_credentials_trusted_device`, `genuine_traveller`,
`festival_shopping`. Each scenario states its intended band before it runs, and the response reports
`matched_expectation`.

### `GET /risk/feeds`
Provenance of every external source. For the Tor exit list (torproject.org) and Spamhaus DROP it gives the
URL, fetch time, entry count, origin (download or last-good disk cache), staleness (> 24 h) and last error.
It also covers the live payment provider, the UN sanctions list (existing screening module), the complaint
register and the alert queue.

### `GET /risk/evaluation`
The latest offline evaluation summary (`backend/intelligence/model/evaluation_summary.json`): synthetic,
time-separated, with the design targets kept separate from the results. **404** if it was never run.

### `GET /risk/config`
Model (version, weights, training provenance), bands and false-positive settings, ring-map status, profile
counts, known-fraud registry size, demo-traffic state.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `RISK_STEP_UP_AT` / `RISK_REVIEW_AT` | 40 / 70 | band thresholds |
| `RISK_MODEL_PATH` | built-in | a reviewed model JSON; otherwise `intelligence/model/risk_model.json` if present, else the hand-set prior |
| `RISK_DEMO_TRAFFIC` / `RISK_DEMO_RATE` | true / 2.0 | synthetic background traffic in demo mode (pauses after 10 min without viewers) |
| `THREAT_FEEDS_ENABLED` | true | download the Tor exit list and Spamhaus DROP every 6 h |
| `THREAT_FEEDS_CACHE` | `data/threat_feeds_cache.json` | last good copy, used when a download fails |
| `LIVE_FEED_ENABLED` | false | allow `source=live` outside demo mode |

## Example

```bash
curl -s -X POST "$API/api/v1/risk/assess" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"txn_id":"T-1","from_account":"CUST-1","to_account":"NEW-SELLER","amount":80000,
       "timestamp":"2026-11-04T10:20:00+05:30","context":{"beneficiary_added_at":"2026-11-04T10:08:00+05:30"}}'
```
