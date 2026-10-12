# 2–3. Refined problem statement and customer map (Phase B)

## 2.1 Official challenge (verified)

From the BuildX 2026 *Industry Problem Statements* PDF, Banking/FinTech track:

> **Detect Payment Fraud in Real Time.** As digital payments grow, fraud
> patterns are becoming increasingly dynamic. At the same time, excessive fraud
> alerts can disrupt genuine customers. *Challenge:* develop a real-time fraud
> detection solution that can identify suspicious transactions while
> **minimising false alerts for genuine customers**. Explore: Machine Learning ·
> Fraud Analytics · APIs · Real-Time Systems.

The challenge statement scores two things: catching suspicious activity, and
**not** burdening genuine customers. MuleCatch must show both.

## 2.2 Refined problem statement

> Money stolen through UPI and online-banking scams is moved out within hours
> through **networks** of mule accounts. Bank fraud teams see these accounts as
> separate transaction-monitoring alerts, most of which are false positives.
> As a result they review the same ring many times, see the network late, and
> sometimes freeze legitimate customers along the way.
>
> **MuleCatch turns a stream of payments into a short, ranked queue of
> evidence-backed *network cases*.** An investigator reviews one ring at a
> time, sees why it was prioritised, and records an auditable human decision.
> Legitimate customers who merely transact with the ring are not swept into
> the case.

## 2.3 Evidence base (public sources, not interviews)

| Claim | Source | Strength |
|---|---|---|
| I4C froze about 4.5 lakh mule accounts in roughly one year (reported Nov 2024) | [Business Standard](https://www.business-standard.com/india-news/centre-freezes-450-000-mule-bank-accounts-used-in-cyber-fraud-schemes-124111200320_1.html), [The Wire](https://thewire.in/tech/india-lost-rs-11333-crore-to-cyber-fraud-in-2024) | Press report of government data |
| ₹11,333 crore lost to cyber fraud in the first nine months of 2024 | [The Wire](https://thewire.in/tech/india-lost-rs-11333-crore-to-cyber-fraud-in-2024) | Press report; other sources give different totals, so cite the scope with the figure |
| RBI built MuleHunter.AI because static rules produce high false positives and long turnaround; 23 banks had implemented it by Dec 2025 (RTI); Finance Ministry has urged adoption | [MediaNama RTI](https://www.medianama.com/2025/12/223-rti-23-banks-mulehunter-mule-accounts/), [Business Standard](https://www.business-standard.com/industry/banking/15-more-banks-to-adopt-rbi-s-mulehunter-fraud-detection-tool-by-october-125080101845_1.html), [Moneylife](https://www.moneylife.in/article/rbi-finmin-ask-banks-to-use-mulehunterai-to-control-mule-bank-accounts-used-in-fraud/75829.html) | Regulator-level signal that the problem is a priority |
| Banks are advised to use real-time monitoring, AI tools and **network analytics** to find mule networks | [TaxGuru summary of RBI communication](https://taxguru.in/rbi/ai-tool-launched-to-detect-mule-accounts-used-in-cyber-fraud.html) | Secondary summary |
| Over 90 % of transaction-monitoring alerts are false positives at most banks | Widely cited (McKinsey via [NameScan](https://namescan.io/insights/?p=14416); [Facctum](https://www.facctum.com/blog/aml-false-positive-report)) | **Vendor/consultancy figure**, not peer-reviewed; use as context only |
| 20–60 minutes per alert review | Vendor blog estimates found during research (e.g. [Tookitaki](https://www.tookitaki.com/compliance-hub/reducing-false-positives-transaction-monitoring), [Facctum](https://www.facctum.com/blog/aml-false-positive-report)), labelled by them as operational estimates | **Soft**; no time-and-motion study found. Treat as an assumption to validate |
| RBI fraud directions (15 July 2024) require natural justice (notice, ≥21 days to respond, reasoned order) before classifying a person as fraudulent | [Business Today](https://www.businesstoday.in/amp/industry/banks/story/rbi-issues-revised-circular-to-declare-accounts-as-fraud-incorporates-supreme-court-ruling-on-borrower-rights-437244-2024-07-15), [SCC Online](https://www.scconline.com/blog/post/2024/07/17/rbi-revises-master-directions-on-fraud-risk-management-in-regulated-entities-legal-news) | Regulatory; supports mandatory human review |
| RBI FREE-AI framework (Aug 2025): board-approved AI policy, audit, consumer protection, attention to opacity/bias | [KPMG summary](https://kpmg.com/in/en/insights/2025/08/rbi-free-ai-committee-report-on-framework-for-responsible-and-ethical-enablement-of-artificial-intelligence.html) | Regulatory guidance; supports explainability and audit trail |

**Not available:** interviews with investigators, bank alert volumes, per-bank
false-positive rates, or a buyer's budget. Every user need below is therefore a
**hypothesis**.

## 2.4 Perspectives

| Stakeholder | Has the problem when… | Cost | Current handling | Gap (hypothesis) |
|---|---|---|---|---|
| **A. Ordinary people** (scam victims; also genuine customers wrongly frozen) | Victim: money leaves their account and is layered within hours. Genuine customer: account debit-frozen because it touched a flagged account | Victim: lost funds, slow recovery via 1930 / cybercrime.gov.in. Genuine customer: blocked salary/rent, branch visits, distrust | Victims report to the helpline/portal; banks place liens on traceable recipient accounts | Funds already moved several hops; blunt freezes hit innocents |
| **B. Fraud investigators / AML analysts** | Daily, in the alert queue | Minutes per alert × many alerts; repeated work on accounts from the same ring | Rule-based TM alerts reviewed one account at a time; manual link analysis in spreadsheets or a graph tool | No consolidated ring view; little explanation of *why*; false positives dominate |
| **C. Fraud & compliance leadership** (Head of FRM, Principal Officer for FIU-IND reporting) | Quarterly, during audits, and when regulators push (MuleHunter adoption, I4C freeze requests) | Analyst headcount, regulatory exposure, reputational risk | Vendor FRM/AML suites + in-house rules; MuleHunter.AI where adopted | Hard to prove effectiveness; explainability and audit needed for regulators |
| **D. Institutions that buy** | When renewing FRM/AML tooling or responding to regulator advisories | Licence plus integration cost; procurement cycles | Large vendors (Clari5/Perfios, Feedzai, BioCatch, Quantexa, SAS, NICE Actimize) or RBIH's MuleHunter.AI | Smaller banks (cooperative, small finance, payments banks) may lack budget for large suites (hypothesis) |

## 2.5 Answers

| Question | Answer | Confidence |
|---|---|---|
| Who has the problem? | Bank fraud/AML investigation teams (direct); scam victims and wrongly flagged genuine customers (indirect) | High for existence, unknown for size per bank |
| When does it occur? | Continuously; the critical window is the hours after a scam credit, before funds are layered out | Medium |
| What does it cost? | Lost victim funds, analyst time per alert, and customer disruption from false freezes. **We do not have bank-specific numbers** | Low (quantity) |
| How is it handled today? | Rules plus vendor ML, account-by-account alert review, MuleHunter.AI at about 23+ banks | Medium |
| What is insufficient? | Account-level alerts hide the network. False positives dominate. Explanations and audit trails are weak in rule outputs | Medium (public sources, vendor bias) |
| Who uses MuleCatch? | Fraud investigator / AML analyst (daily), team lead (queue, QA) | Hypothesis |
| Who buys? | Head of Fraud Risk Management / CRO, with the CISO and IT for deployment; procurement committee | Hypothesis |
| What evidence would justify a pilot? | (1) On the bank's historical, *time-split* data with confirmed outcomes, MuleCatch's case queue reaches the same confirmed mules with fewer reviews **and** fewer genuine accounts touched than their current alerts. (2) In a timed test, analysts reach the same decisions faster. (3) Security review passes for on-premise deployment | Defines the bar |

## 2.6 Validation plan (because no interviews exist yet)

| Step | Who | What to ask or measure | Disproves the hypothesis if… |
|---|---|---|---|
| 1 | 5–8 fraud/AML analysts (LinkedIn, T-Hub mentors, alumni at banks) | Walk through last week's alert review; time per alert; how they spot linked accounts; what makes them escalate | They already get ring-level cases from their current tool |
| 2 | 2 fraud/compliance heads | Which metric they report to the board; what a pilot must show; data-sharing constraints | Network analytics is already solved by MuleHunter.AI or their vendor |
| 3 | At the hackathon: mentors and judges with banking backgrounds | 3-minute demo, then "would you pilot this, and on what data?" | No one can name a data path to a pilot |
| 4 | Controlled task (see 05-evaluation) | Same 10 cases, account view vs case view, time and decision agreement | No time saving or worse decisions |

**Decision:** The problem is real and regulator-endorsed. The specific user
pain (ring-level triage, fewer false alerts) is an **unvalidated hypothesis**,
and the pitch must say so. **Next action:** run steps 1 and 3 before and
during the event.
