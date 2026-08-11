# MuleCatch — Compliance and Controls

---

## Document control

| Field | Value |
|---|---|
| Purpose | Map regulatory obligations to controls that exist in code, and state precisely what evidence remains outstanding |
| Audience | Compliance, legal, internal audit, model risk management, regulatory liaison |
| Built from | Forensic code inventories: `compliance-str`, `security-controls`, `tests-evidence`, `api-surface` |
| Codebase | `master` @ `a7b05bf` |
| Method | Instruments are cited **by name only**. No clause number, date or schema version is asserted that could not be verified from the repository. Quantitative regulatory timelines are referenced to [REGULATORY_CONTROL_MATRIX.md](../REGULATORY_CONTROL_MATRIX.md) rather than restated here |
| Related | [Investigator workflow](07-INVESTIGATOR-WORKFLOW.md) · [Security architecture](09-SECURITY-ARCHITECTURE.md) · [AI and explainability](06-AI-AND-EXPLAINABILITY.md) · [Delta register](11-DELTA-REGISTER.md) |

> **This document is not a compliance opinion and not a declaration of conformance.** It is an
> engineering statement of which controls exist in source code and which do not. Determining whether
> the resulting control environment satisfies a regulatory obligation is a judgement for the bank's
> compliance and legal functions, informed by evidence this repository cannot produce on its own.

---

## 1. Why this document is conservative

The pre-existing project documentation contains statements — "production-ready", "FIU-IND v2.1
compatible", specific false-positive and investigation-time reductions — that this document does not
repeat. Each is either a readiness judgement belonging to the bank, an assertion requiring acceptance
testing that has not occurred, or an unmeasured figure. The relevant one to name explicitly: the "75%
investigation time reduction" originates as a **database column default** at
[init.sql:127](../../infra/database/init.sql#L127), surfaced through the ROI dashboard as though it
were an outcome.

Being conservative here is not modesty. A control matrix that overstates is worse than no matrix,
because a reviewer who finds one overstatement must then re-verify everything.

---

## 2. Control mapping

Column meanings: **Status** uses the document-set labels. **Evidence still required** is never blank
for a control that has not been externally validated.

### 2.1 Customer due diligence and onboarding

| Requirement | Source instrument | Control in code | Status | Evidence still required |
|---|---|---|---|---|
| Risk-based customer risk assessment at onboarding | RBI Master Direction on Know Your Customer | `assess_onboarding_risk` ([risk_scorer.py:291](../../models/onboarding/risk_scorer.py#L291)) via `/api/v1/onboarding/assess` | `[INTEGRATED]` | Threshold approval; validation against the bank's own onboarding population |
| Identity duplicate and synthetic-identity detection | RBI KYC Master Direction | `EntityResolutionService` with `rapidfuzz` matching ([entity_resolution_service.py:57](../../backend/services/entity_resolution_service.py#L57)) | `[VALIDATED]` | Match-rate and false-match measurement on real applications |
| Sanctions and watchlist screening | PMLA obligations; UNSC list adoption | `ScreeningService` plus UNSC fetcher ([unsc_fetcher.py:52](../../backend/services/screening/unsc_fetcher.py#L52)) | `[VALIDATED]` | Coverage of all lists the bank is obliged to screen; refresh SLA; match-threshold approval |
| Graph cross-check against known-flagged parties | RBI mule-account monitoring expectations | `find_flagged_neighbors` ([neo4j_client.py:452](../../backend/graph_engine/neo4j_client.py#L452)) | **Broken** | **This returns all zeros in practice** — the device edge label differs between the application and the seeder. See [05](05-GRAPH-LAYER.md) §2.2 |

The last row is a material finding for this section: onboarding risk is currently computed **with its
graph signal permanently absent**, and the score is emitted as though the check had run.

### 2.2 Ongoing transaction monitoring

| Requirement | Source instrument | Control in code | Status | Evidence still required |
|---|---|---|---|---|
| Ongoing monitoring for mule-account behaviour | RBI Master Directions on Fraud Risk Management; RBI mule-monitoring expectations | `DetectionPipeline.run` ([pipeline.py:611](../../backend/detection/pipeline.py#L611)) | `[VALIDATED]` | Real-data precision and recall; approved alert capacity |
| Monitoring beyond static thresholds | Same | Behavioural, temporal, graph, device and ML layers | `[VALIDATED]` | Comparison against the bank's incumbent rule baseline |
| Detection of structuring | PMLA reporting thresholds | R04 plus smurf-weighting engine | `[INTEGRATED]` | Threshold approval against the applicable reporting ceiling |
| Alignment with published behavioural indicator sets | RBI / RBIH MuleHunter.AI initiative | 20 rules, R01–R20 | `[INTEGRATED]` | A documented mapping from each rule to the indicator it implements. **Note the docstring claims 19 indicators while 20 are defined** |
| Risk scoring and prioritisation | RBI fraud risk governance | Ensemble fusion, severity banding | `[INTEGRATED]` | **Calibration, probability calibration, segment thresholds, and formal threshold approval — none exist** |

### 2.3 Reporting

| Requirement | Source instrument | Control in code | Status | Evidence still required |
|---|---|---|---|---|
| STR preparation | PMLA and PML (Maintenance of Records) Rules | `STRService` state machine ([str_service.py:16](../../backend/services/str_service.py#L16)) | `[VALIDATED]` | — |
| Separation of duties on filing | PMLA; internal control expectations | Role-gated ladder: draft → SUPERVISOR approve → ADMIN submit | `[INTEGRATED]` | **The approver identity is the literal `'demo_user'`** — see §3 |
| STR transmission to FIU-IND | FIU-IND reporting framework, FINGate | **None** | **`[SIMULATED]`** | Reporting-entity credentials; schema conformance; packaging; submission, rejection and acknowledgement acceptance testing |
| Report schema conformance | FIU-IND published reporting formats | Field set generated by the STR generator | **Unverified** | Validation against the current published schema and code lists. **No conformance evidence exists in this repository** |
| Retention of reports and supporting records | PMLA record-retention obligations | `str_reports` table | `[INTEGRATED]` | **No retention, archival, deletion or legal-hold policy exists in code or configuration** |

**On transmission, stated plainly.** No outbound call of any kind is made. The FIU reference is minted
locally from a UUID at [str_service.py:83](../../backend/services/str_service.py#L83) in the form
`FIU-YYYYMMDD-XXXXXX`. Among 56 configuration fields there is no FINGate URL, credential or
certificate setting — only the cosmetic `reporting_entity`, `reporting_ifsc` and `fiu_format_version`.
The repository is internally honest about this: the service docstring says `(simulated)` and the README
already states that portal submission requires reporting-entity credentials and acceptance testing.
That internal honesty is worth crediting and should be preserved, not softened.

### 2.4 Auditability

| Requirement | Source instrument | Control in code | Status | Evidence still required |
|---|---|---|---|---|
| Tamper-evident record of decisions | PMLA record-keeping; RBI audit expectations | SHA-256 hash chain ([init.sql:35-36](../../infra/database/init.sql#L35-L36)), verification endpoint | `[VALIDATED]` | External anchoring; append-only enforcement at the database level |
| Audit coverage of the filing workflow | Same | **None** | **Absent** | **Create, approve, submit and acknowledge are unchained** — verified by searching `str_service.py` for `audit` |
| Audit coverage of authentication | Same | **None** | **Absent** | Login, logout and token refresh are unchained |
| Access control over records | RBI IT governance expectations | 4-role RBAC, 13 permissions | `[INTEGRATED]` | `AUDITOR` role is unusable; 4 permissions declared and never enforced. See [09](09-SECURITY-ARCHITECTURE.md) §2 |
| Referential integrity of evidentiary records | Record-keeping obligations | **None** | **Absent** | **No foreign key exists anywhere in the schema** — an audit row can reference a non-existent alert |

### 2.5 Human oversight and customer fairness

| Requirement | Source instrument | Control in code | Status | Evidence still required |
|---|---|---|---|---|
| Human decision on adverse action | RBI fraud risk governance; natural justice | No automated action path exists, by design | `[VALIDATED]` | Documented investigator SOP |
| Explainability of an adverse decision | RBI expectations on responsible AI use | Reason codes, graph evidence, SHAP, narrative | Partial | **Three of seven explanation artifacts do not reach the investigator** — see [06](06-AI-AND-EXPLAINABILITY.md) §4 |
| Customer grievance and remediation | RBI expectations on wrongly restricted accounts | **None** | **`[PLANNED]`** | An unfreeze and grievance workflow. No customer-facing path exists at all |
| Fairness / bias assessment | Responsible AI expectations | **None** | **Absent** | **`bias_assessment` does not exist anywhere in the repository**, although the UI reads a field of that name |
| Senior management oversight reporting | RBI requirement for unified fraud oversight reporting | KPI and ROI dashboards | `[INTEGRATED]` | Whether the dashboard content satisfies the required oversight scope. Note one displayed figure is a column default |

---

## 3. Three findings that bear directly on filing integrity

These matter more than detection quality for this document's audience, because they concern whether the
output would withstand examination.

**The approver of record is a placeholder.** The compliance portal sends `approved_by` with the literal
string `'demo_user'` ([CompliancePortal.js:30](../../frontend/src/compliance_portal/CompliancePortal.js#L30),
[:130](../../frontend/src/compliance_portal/CompliancePortal.js#L130)); the authenticated principal is
never used. The role gate correctly ensures *a* supervisor performed the approval. The record does not
capture *which* supervisor. Separation of duties is enforced in the request path and lost in the record.

**The filing workflow is outside the tamper-evident chain.** Combined with the above, there is no
trustworthy record of who approved or submitted any report. The only trace of a submission is a Python
log line at [str_service.py:92](../../backend/services/str_service.py#L92).

**An approved report cannot be withdrawn.** `READY_FOR_SUBMISSION → DRAFT` is legal in the transition
table but no service method or route implements it. A supervisor who approves in error has no path back.

Together these three mean the STR lifecycle is procedurally correct and evidentially weak. All three
are small, local fixes, and closing them would materially change this section's assessment.

---

## 4. Model governance

What exists:

- **Version provenance on alerts.** Alerts retain model and rule version identifiers, which is the
  correct foundation for retrospective reconstruction.
- **A production gate on model version.** The production validator rejects the default
  `unvalidated-dev` value, so a production deployment cannot silently run an unapproved model.
- **A model card.** [MODEL_CARD.md](../MODEL_CARD.md) exists and — importantly — lists PR-AUC,
  calibration, segment analysis and investigator-capacity thresholds as *required*.

What does not exist, verified:

| Governance control | Status |
|---|---|
| Independent model validation | Absent |
| Probability calibration | Absent |
| PR-AUC and operating-point analysis | Absent — the harness reports a single arbitrary point |
| Segment-specific thresholds | Absent |
| Formal threshold approval and change history | Absent — thresholds are code literals, so a change requires a deployment |
| Champion / challenger operation | Absent |
| Shadow mode for parallel running | Absent — see [08](08-PLATFORM-AND-DEPLOYMENT.md) §6 |
| Fairness / bias assessment | Absent |
| Drift monitoring in production | `DriftDetector` exists with no caller |
| Closed feedback loop | Thresholds are computed and never read by the pipeline |

The evidence position is set out fully in [04-DETECTION-ENGINE.md](04-DETECTION-ENGINE.md) §6. In
summary, and stated as ranges rather than headline figures: five of ten cross-validation folds detected
nothing at all; two runs with identical parameters produced mean F1 of 0.4158 and 0.2291; σ(F1) across
folds is 0.28–0.36 and is computed but never surfaced; precision of 1.0 in the adversarial runs reflects
0–1 alerts emitted rather than a low false-positive rate; and **no metric on labelled real data exists**,
because the one supplied bank file has no labels and the adapter correctly emits
`GROUND_TRUTH_LABELS_ABSENT`.

A model risk function will reach one conclusion from this: the detector is not yet validated, and the
absence of a shadow mode blocks the parallel-run study that would be the natural first step toward
validating it.

---

## 5. Why explainability is a regulatory requirement

Set out in [06-AI-AND-EXPLAINABILITY.md](06-AI-AND-EXPLAINABILITY.md) §6. In short, three obligations
each demand something different: **contestability** — a customer subject to an adverse action must
receive an explanation in terms of observable facts, not a score; **supervisory review** — a supervisor
accepting responsibility for a filing cannot do so on an opaque output; and **retrospective
reconstruction** — an examiner months later must be able to reproduce the reasoning, which requires the
explanation to be persisted alongside the model version that produced it.

Reason codes and graph evidence satisfy the first two reasonably well today. Retrospective
reconstruction is weakened by the two competing SHAP implementations, which mean the bank could not say
with certainty which attribution was shown at the time. And five rule names describe time-window
analyses the code never performs, so a reason code reaching a regulator can characterise an analysis
that did not occur — the single most compliance-relevant defect in the detection layer.

---

## 6. Evidence posture

**Engineering readiness is not regulatory approval.** The distinction is the organising idea of this
document. Substantial engineering controls exist. None of the following can be produced by writing more
code, and each is a prerequisite the bank alone can supply:

| Gate | Evidence required | Who supplies it |
|---|---|---|
| Detector validation | De-identified labelled historical data with a defined mule-label taxonomy; time-based train/validation/test splits | Bank |
| Operating point | Approved thresholds tied to an alert-capacity and false-positive budget | Bank risk committee |
| Independent validation | Model validation report from a function independent of the build | Bank model risk |
| Regulatory filing | Reporting-entity credentials; schema conformance; submission, rejection and acknowledgement acceptance testing | Bank + FIU-IND |
| FRI integration | Live endpoint access and credentials | Bank + RBI |
| Identity and secrets | Bank IAM integration, certificates, production secret provisioning | Bank |
| Security assurance | Penetration test and remediation evidence | Bank + external tester |
| Resilience | Backup and restore exercise with agreed RPO and RTO | Bank |
| Approval to operate | Legal, compliance, security and model-risk sign-off | Bank |

Against this list, four items in the codebase must be closed before real customer data enters **any**
environment, because they are not gated on external evidence at all: authentication fails open outside
`ENV=production`; the STR lifecycle is unchained and its approver identity is a placeholder;
`/internal/metrics` is unauthenticated and publicly proxied; and PostgreSQL, holding the audit chain and
every report, has no backup path. These are engineering fixes, and they are the honest precondition for
the rest.

---

## 7. What this section establishes

MuleCatch implements a credible AML control *workflow* with real access control, a real STR lifecycle, a
real tamper-evident audit mechanism, and a genuine commitment to explainability and human oversight. For
a platform at this stage that is a strong position, and the project's own documentation is notably honest
about the FINGate boundary.

Three things must be true before this can be described as an AML control rather than an AML control
prototype:

1. **The filing record must be trustworthy.** Chain the STR lifecycle, capture the real approver
   identity, restore the withdrawal path.
2. **The detector must be validated on real labelled data**, at an approved operating point, with a
   shadow-mode parallel run to establish it.
3. **Regulatory transmission must be real**, with conformance and acknowledgement testing against the
   current published schema.

Item 1 is engineering and can be done now. Items 2 and 3 require the bank and FIU-IND. All are recorded
with severity and ownership in [11-DELTA-REGISTER.md](11-DELTA-REGISTER.md).
