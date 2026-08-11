# MuleCatch — Architecture Document Set

This is the architecture documentation for MuleCatch, an explainable graph-based platform for detecting
money mule account networks in digital payment systems. It was built by reading the code, not by
describing the intent: twelve forensic inventories were taken across `master` @ `a7b05bf` covering the
API surface, detection engine, graph layer, explainability stack, service and data layers, streaming,
frontend, infrastructure, security controls, compliance workflow, existing documentation and test
evidence. Those inventories are the source for every statement made here.

**The governing principle of this set is: true first, impressive second.** Every factual claim carries a
`file:line` citation so that any reader can verify it in seconds, and every gap found is recorded rather
than smoothed over. A reviewer who diffs these documents against the code should find no contradictions.
Where one exists, it is written down in [11-DELTA-REGISTER.md](11-DELTA-REGISTER.md) rather than
resolved silently.

---

## Status legend

Every component named in this set carries exactly one of these labels. Where a label was uncertain, the
weaker one was chosen.

| Label | Meaning |
|---|---|
| `[VALIDATED]` | Reachable from a registered route **and** covered by real, non-mock tests or repository benchmark evidence |
| `[INTEGRATED]` | Code exists **and** is reachable from a route registered in `backend/api/v1/router.py` or a route in `frontend/src/App.js` |
| `[IMPLEMENTED]` | Code exists, but no registered route reaches it. The import chain was traced and confirmed dead-ended |
| `[PLANNED]` | Target state. Not in the codebase today |
| `[SIMULATED]` | The step executes and changes state, but its external effect is synthesised locally rather than transmitted |

In diagrams, a **dashed border** marks the unreachable and the target state. You can see what is not
real without reading a single label.

---

## Reading paths

| If you are a… | Read, in this order | Why |
|---|---|---|
| **Bank executive** | [00-EXECUTIVE-SUMMARY](00-EXECUTIVE-SUMMARY.md), then Diagram 15 in [12](12-END-TO-END-ARCHITECTURE.md) | Under 10 minutes, no jargon, honest readiness posture |
| **Bank technical reviewer** | [00](00-EXECUTIVE-SUMMARY.md) → [01](01-CONTEXT-AND-SCOPE.md) → [02](02-SYSTEM-ARCHITECTURE.md) → [12](12-END-TO-END-ARCHITECTURE.md) → [11](11-DELTA-REGISTER.md) | Scope, structure, the whole chain, then the gap list |
| **Security architect** | [09](09-SECURITY-ARCHITECTURE.md) → [08](08-PLATFORM-AND-DEPLOYMENT.md) → [03](03-DATA-ARCHITECTURE.md) §6 → [11](11-DELTA-REGISTER.md) §D | Controls, deployment surface, personal data, then security gaps |
| **Compliance / audit** | [10](10-COMPLIANCE-AND-CONTROLS.md) → [07](07-INVESTIGATOR-WORKFLOW.md) → [11](11-DELTA-REGISTER.md) §E, §H | Control mapping, filing workflow, audit gaps, external evidence gates |
| **Model risk** | [04](04-DETECTION-ENGINE.md) → [05](05-GRAPH-LAYER.md) → [06](06-AI-AND-EXPLAINABILITY.md) → [10](10-COMPLIANCE-AND-CONTROLS.md) §4 | Detection design, evidence base, explainability, model governance |
| **Maintaining engineer** | [02](02-SYSTEM-ARCHITECTURE.md) → [03](03-DATA-ARCHITECTURE.md) → [04](04-DETECTION-ENGINE.md) → [05](05-GRAPH-LAYER.md) → [06](06-AI-AND-EXPLAINABILITY.md) → [08](08-PLATFORM-AND-DEPLOYMENT.md) | The full engineering picture |
| **Evaluation panel** | [00](00-EXECUTIVE-SUMMARY.md) → [12](12-END-TO-END-ARCHITECTURE.md) → [04](04-DETECTION-ENGINE.md) → [11](11-DELTA-REGISTER.md) | What it does, how the whole chain fits, the technical core, and an honest self-assessment |

Whatever your role, if you read only two documents, read `00` and `11`.

---

## File manifest

| File | Covers | Diagrams |
|---|---|---|
| [00-EXECUTIVE-SUMMARY.md](00-EXECUTIVE-SUMMARY.md) | Non-technical overview, readiness posture, path to pilot, verdict | — |
| [01-CONTEXT-AND-SCOPE.md](01-CONTEXT-AND-SCOPE.md) | The problem, actors, external systems and their real integration status, trust boundaries, scope | Context diagram |
| [02-SYSTEM-ARCHITECTURE.md](02-SYSTEM-ARCHITECTURE.md) | Layered architecture, middleware chain, API surface, service and repository layers | **1**, **2** |
| [03-DATA-ARCHITECTURE.md](03-DATA-ARCHITECTURE.md) | Four stores, full relational schema, Neo4j reality, cache design, personal data classification | **3**, **13** |
| [04-DETECTION-ENGINE.md](04-DETECTION-ENGINE.md) | All seven layers, complete R01–R20 rule enumeration, risk fusion, evidence base | **4**, **6** |
| [05-GRAPH-LAYER.md](05-GRAPH-LAYER.md) | Graph model, Neo4j schema, community detection, typology coverage | **5** |
| [06-AI-AND-EXPLAINABILITY.md](06-AI-AND-EXPLAINABILITY.md) | Why graph learning, SHAP, narratives, reason codes, and which explanations actually arrive | Explanation flow |
| [07-INVESTIGATOR-WORKFLOW.md](07-INVESTIGATOR-WORKFLOW.md) | Alert to closure, STR state machine, filing-path defects | **7**, **10** |
| [08-PLATFORM-AND-DEPLOYMENT.md](08-PLATFORM-AND-DEPLOYMENT.md) | Compose and Kubernetes topology, environments, availability, backup, CI/CD | **8**, **11**, **12**, **14** |
| [09-SECURITY-ARCHITECTURE.md](09-SECURITY-ARCHITECTURE.md) | Identity, full RBAC matrix, transport, secrets, audit integrity, threat surface | **9** |
| [10-COMPLIANCE-AND-CONTROLS.md](10-COMPLIANCE-AND-CONTROLS.md) | Regulatory control mapping, model governance, evidence posture | — (STR lifecycle is Diagram 7 in [07](07-INVESTIGATOR-WORKFLOW.md)) |
| [11-DELTA-REGISTER.md](11-DELTA-REGISTER.md) | **73 gaps, 14 critical, 26 blocking a pilot**, plus the eight one-line fixes | — |
| [12-END-TO-END-ARCHITECTURE.md](12-END-TO-END-ARCHITECTURE.md) | The complete chain, customer payment to closed case, with a 25-hop specification | **15** |

---

## Diagram index

All fifteen requested diagrams are present.

| # | Diagram | Document |
|---|---|---|
| 1 | High-Level System Architecture | [02](02-SYSTEM-ARCHITECTURE.md) |
| 2 | Enterprise Component Diagram | [02](02-SYSTEM-ARCHITECTURE.md) |
| 3 | Data Flow Diagram | [03](03-DATA-ARCHITECTURE.md) |
| 4 | Detection Pipeline | [04](04-DETECTION-ENGINE.md) |
| 5 | Graph Construction Pipeline | [05](05-GRAPH-LAYER.md) |
| 6 | Risk Scoring Flow | [04](04-DETECTION-ENGINE.md) |
| 7 | Investigator Workflow / STR State Machine | [07](07-INVESTIGATOR-WORKFLOW.md) |
| 8 | Deployment Architecture | [08](08-PLATFORM-AND-DEPLOYMENT.md) |
| 9 | Security Architecture | [09](09-SECURITY-ARCHITECTURE.md) |
| 10 | Sequence: payment to filed report | [07](07-INVESTIGATOR-WORKFLOW.md) |
| 11 | Infrastructure | [08](08-PLATFORM-AND-DEPLOYMENT.md) |
| 12 | Logical Component Interaction | [08](08-PLATFORM-AND-DEPLOYMENT.md) |
| 13 | Database Relationship Diagram | [03](03-DATA-ARCHITECTURE.md) |
| 14 | CI/CD Pipeline | [08](08-PLATFORM-AND-DEPLOYMENT.md) |
| 15 | Complete End-to-End Architecture | [12](12-END-TO-END-ARCHITECTURE.md) |

**Note on Diagram 12.** It is a *logical* component interaction diagram, not a microservice topology.
MuleCatch is a single-process modular monolith with one application factory and one backend container
image. No document in this set draws microservices, because none exist. Service decomposition appears
only as clearly labelled target state.

---

## How to verify this document set

This set is designed to be checked rather than believed.

1. **Pick any claim.** It carries a `file:line` citation as a clickable link. Open it.
2. **Check a status label.** A component marked `[INTEGRATED]` should be traceable to a registration in
   `backend/api/v1/router.py` or a route in `frontend/src/App.js`. One marked `[IMPLEMENTED]` should have
   no such path. Both directions are worth testing.
3. **Check a gap.** Every row in the delta register names where the defect lives. Absences are stated
   with the search that established them, for example "no dead-letter topic; searched
   `dead.?letter|DLQ|deadletter` repo-wide".
4. **Check a number.** Every figure either carries a source citation or is explicitly marked
   `TARGET — UNVALIDATED`. If you find a bare number without either, that is a defect in this
   documentation and should be reported.

You are invited to diff this set against the code. It was written on the assumption that someone will.

---

## Relationship to existing documentation

Thirteen documents already existed in [`docs/`](../) before this set. These architecture documents
**link to them rather than restating them**, and each retains ownership of its own subject.

| Existing document | Owns |
|---|---|
| [PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md) | The readiness gate list and what remains blocked |
| [DEPLOYMENT_RUNBOOK.md](../DEPLOYMENT_RUNBOOK.md) | Operational deployment procedure |
| [MODEL_CARD.md](../MODEL_CARD.md) | Model description and the validation requirements it defines |
| [MODEL_BENCHMARKS.md](../MODEL_BENCHMARKS.md) | Benchmark methodology and recorded results |
| [REGULATORY_CONTROL_MATRIX.md](../REGULATORY_CONTROL_MATRIX.md) | Regulatory control mapping and remaining institutional evidence |
| [SAMPLE_DATASET_VALIDATION.md](../SAMPLE_DATASET_VALIDATION.md) | Validation attempted against the supplied bank sample |
| [FINAL_PRODUCTION_VALIDATION.md](../FINAL_PRODUCTION_VALIDATION.md) | The production-hardening validation record |
| [IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md) | Change history of the hardening programme |
| [GITHUB_RESEARCH.md](../GITHUB_RESEARCH.md) | Prior art and comparable-platform research |
| [OPEN_SOURCE_INTEGRATIONS.md](../OPEN_SOURCE_INTEGRATIONS.md) | Third-party components and their roles |
| [RESEARCH_REPORT.md](../RESEARCH_REPORT.md) | Domain research underpinning the detection design |
| [research/mule_detection_deep_research.md](../research/mule_detection_deep_research.md) | Extended domain research |

**Where this set contradicts an existing document, the contradiction is recorded in
[11-DELTA-REGISTER.md](11-DELTA-REGISTER.md) §G rather than silently resolved.** Two are worth naming
here because they are live: `PRODUCTION_READINESS.md` records public internal-metrics exposure as
"Removed", but the ingress was hardened while the nginx proxy was not, so the exposure remains; and the
"75% investigation time reduction" figure quoted in several places originates as a database column
default rather than a measurement.

---

## Document control

| Field | Value |
|---|---|
| Describes | MuleCatch at `master` @ `a7b05bf` |
| Method | Twelve forensic code inventories, then documentation authored from those inventories with every claim cited to source |
| Scope of authority | A statement of what the code does. Not a compliance opinion, not a security certification, not a readiness declaration |
| Diagram format | Mermaid, rendering natively on GitHub |
| Palette | IOB design-system tokens, legible in both light and dark themes |

**Engineering readiness is not regulatory approval.** This set documents controls that exist in source
code. Whether the resulting control environment satisfies a regulatory obligation is a judgement for the
bank's compliance, legal, security and model-risk functions, informed by evidence that this repository
cannot produce on its own. That evidence is enumerated in
[11-DELTA-REGISTER.md](11-DELTA-REGISTER.md) §H.
