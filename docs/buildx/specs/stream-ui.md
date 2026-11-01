# Spec: stream-ui (branch `stream-ui`)

Goal: live screen where a ring visibly forms. Depends on `stream-api` event shape (see its spec); mock the events until it lands.

- New folder `frontend/src/live_stream/`, route in `App.js`.
- Force graph of accounts. On `FLAG`, highlight `ring_members` and open a case card (case id, reasons, risk score).
- Counters: payments, flagged, genuine flagged, p95 latency.
- Visible label: "Synthetic data". Wording: "flags / routes to human review", never "blocks".
- If the stream fails: show an error state. No fake data fallback.
- Ring must be visible within 30 s of opening the page. Check readable at projector size.
- Frontend build is broken locally (`ajv` error): fix or work around before relying on `npm run build`.
