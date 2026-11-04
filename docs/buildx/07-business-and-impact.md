# 9–10. Business model, transparent ROI and social-impact assessment (Phase G)

Everything in this file is a **hypothesis or an explicit assumption** unless
it is marked as measured. No customer has been interviewed and no bank has
committed to anything.

## 9.1 Business model

| Element | Proposal | Status |
|---|---|---|
| First target customer | Small finance banks, cooperative banks and payments banks with UPI exposure and small fraud teams | Hypothesis: they may lack budget for enterprise suites. Must be validated |
| Daily user | Fraud investigator / AML analyst | Hypothesis |
| Buyer / budget owner | Head of Fraud Risk Management or CRO; IT/CISO sign-off | Hypothesis |
| Current alternative | Vendor FRM rules + manual link analysis; RBIH MuleHunter.AI (free to adopting banks) | Researched |
| Positioning vs MuleHunter.AI | **Complement, not replacement**: MuleHunter-style scores flag *accounts*; MuleCatch turns flagged accounts and payments into *ring-level cases* with audit trail | Hypothesis; needs to be checked against how MuleHunter outputs are consumed |
| Deployment requirement | On-premise or bank-private cloud; no customer data leaves the bank; no third-party LLM calls | Design constraint |
| Procurement obstacles | Vendor empanelment, security audit, data-localisation, RBI outsourcing/IT guidelines, long sales cycles, incumbent contracts | Known risk |
| Proposed pilot | 8–12 weeks, read-only, on 3–6 months of historical transactions with confirmed outcomes, run in parallel with existing alerts (no customer impact) | Proposal |
| Pricing (plausible) | Annual licence by monitored-account tier, plus a fixed pilot fee | Unvalidated; do not quote numbers in the pitch |
| Acquisition route | T-Hub / AIC network intros, bank innovation labs and hackathon partners, RBIH sandbox / innovation programmes | Proposal |
| Recurring value | Ongoing queue reduction, typology updates, audit-ready case records | Proposal |

## 9.2 Transparent ROI framework

```
Net annual benefit = investigation-cost savings
                   + validated loss reduction
                   − total solution cost
```

| Term | Formula | Inputs that must come from the bank / pilot |
|---|---|---|
| Investigation-cost savings | (reviews avoided per year) × (minutes per review ÷ 60) × (loaded analyst cost per hour) | reviews/year today; **measured** reviews avoided in the pilot; measured minutes per review |
| Validated loss reduction | Σ funds actually held or recovered **because** a MuleCatch case was actioned earlier than the existing process would have | Confirmed by the bank's case outcomes; counterfactual agreed in advance |
| Total solution cost | licence + integration + infrastructure + bank staff time for the pilot and operation | Quotes and internal estimates |

Rules:

- Do **not** count alerts as prevented fraud.
- Do **not** multiply synthetic-data recall by national fraud losses.
- Report the savings only after the pilot measures reviews avoided and minutes per review.

### Worked example (illustrative only, every number is an assumption)

| Input | Assumed value | Source |
|---|---|---|
| Alerts reviewed per year | *A* | Bank |
| Fraction of reviews avoided by case grouping | *r*, measured in pilot | Pilot |
| Minutes per review | *m* (vendor blogs cite 20–60; unverified) | Pilot timing study |
| Loaded analyst cost per hour | *c* | Bank HR |
| Savings | *A × r × m/60 × c* | — |

The pitch should show **this formula with blanks**, not a filled-in rupee figure.

## 10. Social impact and risk assessment

### 10.1 Potential positive impact (all potential, none measured in the field)

| Impact | Mechanism | Evidence needed before claiming |
|---|---|---|
| Faster disruption of mule networks | Whole ring reviewed as one case | Pilot: time from first scam credit to case review, vs baseline |
| Fewer genuine customers frozen | Purity-weighted ranking keeps bystanders out of cases | Pilot: genuine accounts touched per confirmed mule, vs baseline |
| Better use of analyst time | Fewer reviews for the same coverage | Pilot: reviews and minutes per confirmed mule |
| Accountability | Reason codes + human disposition + hash-chained audit | Audit by bank's internal audit |

### 10.2 Risks and mitigations

| Risk | Who is harmed | Mitigation in MVP | Residual |
|---|---|---|---|
| False suspicion of a genuine customer | Customer | Output is "suspicion for review", never an automatic block; the UI separates **suspicion score**, **model confidence** and **verified outcome**; natural-justice steps (RBI July 2024 directions) left to the bank's process | Bank processes may still over-act on scores |
| Bias against groups (new accounts, rural, Jan Dhan, students) | Vulnerable customers | Static attributes (account age, KYC status) removed from the core score in the hardened evaluation; report per-segment false-positive rates in the pilot | Real-data bias unknown |
| Recruited or coerced mules are also victims | Students, low-income people | Language: "account used for mule activity", not "criminal"; case view can record "possible victim-mule" | Policy is the bank's |
| Privacy | All customers | On-prem processing; no LLM/third-party calls; data minimisation (only fields in 5.4); pseudonymised IDs in demo | Pilot data-sharing agreement needed |
| Over-claiming from synthetic data | Judges, buyers | Every slide labels data as synthetic; limitations section | — |
| Adversarial adaptation | Bank | Rings that avoid shared devices and spread timing reduce signal; documented in 05 | Ongoing |
| Model drift | Bank | Drift detector exists (`models/active_learning/drift_detector.py`), outside the MVP | Deferred |

**Decision:** Sell investigation efficiency and genuine-customer protection,
measured in a pilot, not rupee savings. **Next action:** use the
blank-formula ROI slide; prepare the pilot one-pager.
