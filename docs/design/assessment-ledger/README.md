# Assessment ledger: approved design (triage lanes)

Open `index.html` in a browser. It renders the synthetic sample from `GET /api/v1/csv-upload/ledger`
(`data.js` is a saved copy of that response) inside a replica of the app shell at 1920×1080.

- Lanes: **Act now** (complicit, critical ring), **Review** (other flagged), **Clear** (not in a ring).
- Right rail: selected account's figures, top-3 scorer drivers, suggested step; the 13-feature
  ranking lights the selected account's drivers 1–3.
- Reference drawer: standards (7), pipeline (5), channels.
- `spec.js`: reference tables from the team's dashboard spec, as written. Counts in braces are
  filled from the loaded file.

To integrate: add a `/ledger` route in `frontend/src`, fetch `/api/v1/csv-upload/ledger`, reuse the
app tokens (`App.css`). The endpoint and its fields are in `backend/services/cbs_ledger.py`.
