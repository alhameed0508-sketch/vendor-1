# Fraud Complaint Desk — design

Date: 2026-11-02. Status: approved by the user ("implement the ideas ... to the mulecatch").

## Why
From 1 January 2027 every fraud complaint a customer raises with their bank runs on an RBI clock
(RBI/2026-27/167, issued 24 June 2026). The bank must prove customer liability, decide within
45 days (60 cross-border), credit card frauds back provisionally within 5 days, and pay small-value
compensation within 5 days of a completed claim. Banks hold their own logs but not the merchant's
or courier's proof, and nothing assembles a defensible case in time. MuleCatch already finds the
mule accounts the stolen money lands in; under the new scheme the bank that received the money pays
part of the compensation, so mule detection and complaint handling now share a balance sheet.

The user sells to banks. The desk is a new MuleCatch module, not a separate product.

## Goals
1. One case per complaint with an acknowledgement number and live deadlines.
2. A liability recommendation that applies the RBI categories and says, item by item, whether the
   bank holds the evidence to hold the customer liable (the burden of proof is the bank's).
3. Compensation amount, eligibility and the RBI / customer bank / beneficiary bank split.
4. Evidence from bank logs, merchants, couriers and MuleCatch on one timeline, each item hashed into
   a chain so tampering shows.
5. A plain-English narrative where every sentence cites an evidence id (Gemini when configured,
   template otherwise; uncited sentences are dropped).
6. An evidence pack as JSON and PDF.
7. A live workflow view: sources (customer, bank core, SMS gateway, telecom, merchant, courier,
   MuleCatch) → evidence chain → RBI rules → recommendation → decision → evidence pack. "Play"
   streams the case event by event (clock, recommendation and checklist update at each step);
   evidence posted through the API appears on an open case within seconds.

Research behind this: `docs/research/2026-11-02-fraud-complaint-evidence-research.md`.

## Non-goals (this version)
- Filing to RBI, NCRP or card networks. No live bank, merchant or courier integrations.
- Signed mobile capture app, X-ray scanning, behavioural biometrics, cross-institution hash
  registry (DPIP already occupies that layer).
- Persisting complaints to Postgres; the in-memory repository matches the rest of the demo.

## Anti-goals
- Never present the recommendation as the decision. A supervisor records the decision.
- Never cite a rule the research did not confirm. Where the circular's wording is unknown, the
  engine says "bank policy" instead of guessing.

## Rules encoded (sources: MediaNama 25 Jun 2026, CorpLawUpdates, ELP Law, The Bar Bulletin)
| Rule | Value |
|---|---|
| Applies to | EBTs on or after 2027-01-01 (commercial banks) |
| Resolution limit | 45 calendar days domestic, 60 cross-border, from the complaint |
| Zero liability, third-party breach | reported within 5 calendar days of the fraud |
| Zero liability, bank negligence | regardless of reporting time |
| Customer negligence | customer bears loss until reported; bank bears loss after |
| Late third-party report | per the bank's board-approved policy |
| Shadow reversal, credit card | within 5 calendar days of notification |
| Burden of proof | on the bank |
| Compensation | customer-negligence loss up to ₹50,000; individual or sole proprietor; reported to bank and NCRP/1930 within 5 days; fraud within one year of 2027-01-01; once in a lifetime |
| Compensation amount | min(85% of net loss, ₹25,000); paid within 5 days of the completed form |
| Split, domestic | RBI 65 : customer bank 10 : beneficiary bank 10 (of net loss, scaled when capped) |
| Split, cross-border | RBI 65 : customer bank 20 |
| Reimbursement claim | within 30 days of quarter end |

Check: loss ₹40,000, recovered ₹15,000 → net ₹25,000 → ₹21,250 (RBI ₹16,250, banks ₹2,500 each);
capped case → RBI ₹19,118, banks ₹2,941 each (matches the Direction's worked example).

## Shape
Backend (FastAPI, existing layering):
- `backend/complaints/rules.py` — pure functions: deadlines, liability, compensation.
- `backend/complaints/evidence.py` — evidence items, hash chain, burden-of-proof checklist.
- `backend/complaints/narrative.py` — cited narrative, LLM with validation, template fallback.
- `backend/complaints/seed.py` — demo cases, one per path, beneficiaries drawn from live alerts.
- `backend/complaints/pdf.py` — evidence pack PDF (fpdf2, like `api/str_pdf.py`).
- `repositories/complaint_repository.py`, `services/complaint_service.py`,
  `api/v1/routes/complaints.py`, `api/v1/schemas/complaints.py`.
- Permissions: `complaints:read`, `complaints:write`, `complaints:decide`, `complaints:export`.
  GUEST reads only; packs and decisions need staff roles.

Demo clock: in demo mode the desk runs at 15 Feb 2027 10:00 IST so the rules are in force and the
seeded deadlines stay stable; production uses the real time. The page shows the clock it runs on.

Frontend (CRA): `/complaints` page in the Operations nav — deadline KPIs, case list with a clock
bar, case view with timeline + replay slider, "show your work" checklist, compensation card,
mule link, narrative, decision form and pack downloads. Same tokens, fonts and components.

API (`/api/v1/complaints`): `GET ""`, `POST ""`, `GET /{id}`, `POST /{id}/evidence`,
`POST /{id}/decision`, `GET /{id}/narrative`, `GET /{id}/pack`, `GET /{id}/pack.pdf`.

## Left to the builder
Field names, layout details, seed wording, test structure.
