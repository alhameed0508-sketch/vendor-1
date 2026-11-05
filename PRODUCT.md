# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Bank fraud investigators and AML analysts** working a case queue on a desktop monitor (1920×1080 is the confirmed main screen). Job: see which accounts in a batch of core-banking (CBS) transactions look like mule accounts, why, and what to do next.
- **Supervisors and auditors** who need to see which regulation each check serves and that every alert carries a reason a human can read.
- **Hackathon judges and technical evaluators** (BuildX 2026, Banking/FinTech track: "Detect payment fraud in real time ... while minimising false alerts for genuine customers") who inspect how raw rows become a decision.

## Product Purpose

MuleCatch scores payments in the context of the account network, groups mule accounts into one explainable case per ring, and keeps genuine customers out of those cases. Success: fewer, better cases; genuine customers not flagged; every flag explained and decided by a human.

## Positioning

The whole ring is the unit of investigation, not the single account or payment, and the product measures how many genuine customers get pulled in. It complements RBI's MuleHunter.AI rather than replacing it.

## Operating Context

- Analysts upload a pipe-delimited Finacle-style CBS extract (13 columns: TRAN_DATE, TRAN_ID, TRAN_TYPE, TRAN_SUB_TYPE, PART_TRAN_TYPE, ACID, TRAN_AMT, balance, channel, CIF_ID, ACCT_OPN_DATE, LIEN_AMT, customer_age) through Data Import; the detection pipeline runs on upload.
- Roles: investigator, supervisor, admin, guest. Human decides every case; hash-chained audit log.
- Public demo: https://buildx-production-6bb1.up.railway.app (Railway, `railway` branch of the buildx repo).

## Capabilities and Constraints

- The main dashboard is **upload-driven**: every per-file figure is computed from the CBS file currently loaded. With no upload, it shows the synthetic 908-row sample extract (40 accounts, one planted ring).
- Reference content (regulatory standards ledger, 13-feature ranking with formulas, 5-stage pipeline ledger) comes from the team's dashboard spec (`new dashboard/dashboard.md`) and is shown as written, by the user's decision (2026-11-05).
- The dashboard is graph-free: values are shown as ranked rows, tables and numbers, not node-link diagrams.
- Real bank datasets are never committed or baked into the public site.

## Brand Commitments

- Name: MuleCatch. Tagline: "One payment reveals the whole scam ring: real-time AI that flags fraud, not genuine customers."
- Honesty rules (docs/buildx/00-CONTEXT.md): say "synthetic data" next to synthetic results; say "flags" / "helps banks act faster", never "stops", "blocks" or "recovers"; no bank partnership claims and no bank names on uploaded data; no "83% accuracy" or "production-ready"; no unvalidated prices.

## Evidence on Hand

- Synthetic CBS extract: `demo_video/MuleCatch_sample_CBS_extract.csv` (908 rows, 40 accounts; engine finds 1 ring of 10, 30 clean).
- Sample mule account file (`dataset/iob/`, not committed): 2,000 rows, 19 accounts, no mule/genuine labels, one timestamp; engine finds 4 clusters scored 0.767–0.796, 10 complicit / 9 exploited. No false-positive rate can be computed from it.
- IBM AMLworld evaluation: `docs/IBM_AML_EVALUATION.md`.

## Product Principles

1. Every number on screen traces to the loaded file or a named source.
2. Explain before you flag: each flagged account shows its leading drivers in words.
3. The ring is the case; genuine customers stay out of it.
4. A human decides; the product recommends.

## Accessibility & Inclusion

WCAG AA contrast in both themes; keyboard-reachable tables and controls; visible focus.
