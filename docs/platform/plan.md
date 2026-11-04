# MuleCatch Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans, in the main session. The owner's standing rule forbids subagents. Each phase below gets its own task-level plan (written with superpowers:writing-plans) at the start of that phase, because later phases depend on the interfaces the earlier ones settle. Steps use checkbox syntax.

**Goal:** Turn MuleCatch from a mule-detection app into a unified fraud-intelligence platform with a module registry, institution-scoped access, cross-module entity links and one investigation workflow.

**Architecture:** One shell and a module registry in which every module declares an honest status (Implemented, Partial or Planned). A pure permission policy sits in front of every alert, case and chat query. Shared entity and risk records link module findings without merging their scores. One investigation facade fronts the existing alert and complaint case flows.

**Tech Stack:** FastAPI, Python 3, pytest, ruff, React 18 (CRA and craco), Playwright for e2e. No new dependencies.

**Spec:** the three architecture diagrams supplied by the owner (ten-layer architecture, institution hierarchy and permission evaluation, event-to-explanation sequence), the transformation brief, and `docs/platform/gap-analysis.md`. No separate design document was written; this plan states the decisions.

## Global Constraints

- Push only to `https://github.com/alhameed0508-sketch/buildx`. Run `git remote get-url <remote>` and confirm that exact URL before every push. Never push to or open a PR on `muhammedsayeedurrahman/mulecatch`.
- One phase is one branch from buildx master. A phase is never mixed with another and never merged to master without the owner's word.
- No subagents or workflows.
- Baseline that must stay green: `pytest backend/tests` (excluding `test_focal_loss.py` and `test_gnn_directed.py`) at 787 passed and 5 skipped or more; `ruff check backend models` and `ruff format --check backend models` clean.
- Stop and ask before: deleting files, adding a dependency, changing the database schema, pushing, deploying.
- Module status comes from one registry. UI and docs read it and never hard-code a claim.
- Demo data is the real IBM AMLworld sample (`~/Documents/mulecatch/data/ibm-amlworld-hi-small-sample.csv`). Anything generated is labelled "Synthetic" in the UI. The detector's AMLworld result is shown as it is: zero alerts.
- Scores from different modules are never averaged. A consolidated view lists each module's score, evidence and uncertainty side by side.
- Fuzzy matches carry a confidence label and are never merged silently. Verified identifiers are account id, CIF_ID, TRAN_ID and device id.
- Nothing is called "fraudulent" from a model output alone. Use "suspected" and keep the human decision separate.
- No customer-facing app. Payee-risk is not reintroduced.
- Fonts are IBM Plex Sans (UI and body) and IBM Plex Serif (editorial only). Keep the existing light and dark theme tokens and the colour-blind-safe risk colours. Show a design preview before building screens.
- Files stay under 400 lines. Create new objects instead of mutating existing ones.
- New code never goes in a package named `platform`. Use `backend/fraud_modules/`, `backend/access/` and `frontend/src/shell/`.

## Review Focus

1. A user with no assignment asks for the alert list: they get an empty list, never a 403 that reveals other cases exist.
2. A user in bank A asks for a case id that belongs to bank B: the response is identical to "not found".
3. A Planned module is called through its API: it returns its status and no data, never sample or invented findings.
4. Two accounts with similar names but no shared verified identifier: they are linked as POSSIBLE at most and never merged into one entity.
5. The AMLworld demo yields zero alerts: Command Center shows zeros and a "no data from this module" note and does not crash or hide the tile.

## Progress and rulings

- Phase 1 done (`platform/audit`).
- Phase 2 done (`platform/shell`): registry, `/api/v1/modules`, `/api/v1/command-center`, Command center and Detection modules pages, a Platform nav section.
- **Phase 3 deferred by the owner** ("ignore the banks for now"). Institution isolation and the office hierarchy are not built. Existing global roles stay in force. Later phases do not depend on it, except scoped Mule Chat in Phase 7, which will use the existing role checks until Phase 3 exists.
- Ruling: a module's status is derived from its capabilities, so it cannot claim more than its capabilities list.
- Ruling: Loan is Planned. Its only existing building block (the screening service) is not wired to loan applications, so that row is Planned too.
- Ruling: `/` stays the alert dashboard until Phase 4 moves it into the mule workspace. The new pages live at `/command-center` and `/modules`.
- Ruling: the Command center reports `data_source` ("synthetic", "loaded" or "none") so synthetic demo data is labelled. `DetectionService` now marks the datasets it generates.
- Correction: alert severity already includes CRITICAL; the earlier gap analysis said otherwise.

## Phase map

| Phase | Branch | Delivers | Model |
|---|---|---|---|
| 1 | `platform/audit` | This plan and the gap analysis. No code. | Opus |
| 2 | `platform/shell` | Module registry, navigation, Command Center | Sonnet |
| 3 | `platform/access` | Institution hierarchy and the permission policy (Diagram 2) | Sonnet |
| 4 | `platform/mule-module` | Mule detection moved into the shell as Module 1 | Sonnet |
| 5 | `platform/modules` | UPI, Transaction and AML, Identity (Partial); Loan (Planned shell) | Sonnet |
| 6 | `platform/intelligence` | Entity links, cross-module correlation, separate scores | Sonnet |
| 7 | `platform/investigation` | One case workflow, simulated intervention gateway, scoped Mule Chat, e2e | Sonnet |

Phase 3 is new relative to the first draft. Diagram 2 makes access control a prerequisite for every later screen, so it comes before the modules move.

## Phase 2: shell, registry, Command Center

**Files**
- Create `backend/fraud_modules/registry.py`: frozen `ModuleSpec(module_id, name, status, purpose, data_requirements, capabilities)`, `STATUS = ("IMPLEMENTED", "PARTIAL", "PLANNED")`, `MODULES: tuple[ModuleSpec, ...]`, `get_module(module_id) -> ModuleSpec`.
- Create `backend/api/v1/routes/modules.py`: `GET /api/v1/modules` and `GET /api/v1/modules/{module_id}`, registered in `api/v1/router.py`.
- Create `backend/api/v1/routes/command_center.py`: `GET /api/v1/command-center` returning counts from existing services (alerts by risk level, open escalations, graph stats) and `module_statuses`.
- Create `frontend/src/shell/` with `ModuleCard.js`, `CommandCenter.js`, `shellApi.js`, tests beside them.
- Modify `frontend/src/components/navItems.js`, `frontend/src/App.js`.

**Tests first**
- `test_registry_every_module_has_valid_status`, `test_planned_module_lists_no_capabilities_as_implemented`.
- `test_command_center_counts_match_alert_service` against a seeded in-memory repository.
- `test_command_center_with_zero_alerts_returns_zeros_not_error`.
- Frontend: tiles link to real routes; a Planned module card shows a "Planned" badge and no metrics.

**Done when:** all tests pass, navigation works at 375 px and 1440 px, every Command Center tile links to a page that exists.

**Risks:** the sidebar and phone tabs share `navItems.js`, so one change reaches both. Keep the old routes reachable until Phase 4.

## Phase 3: access control (Diagram 2)

**Needs your approval before starting:** adding institution, office, branch, employee and assignment tables is a schema change.

**Files**
- Create `backend/access/models.py`: frozen dataclasses `Institution(institution_id, kind)`, `Office(office_id, institution_id, parent_id, level)`, `Employee(user_id, institution_id, office_id, role)`, `CaseAssignment(case_id, user_id)`.
- Create `backend/access/policy.py`: `can(user: UserContext, action: str, case: CaseContext) -> Decision` where `Decision(allowed: bool, reason: str)`. Pure function, no I/O.
- Create `backend/access/repository.py`: in-memory first, Postgres variant behind the existing repository pattern after approval.
- Create `backend/access/seed.py`: two demo banks (one public-sector, one private-sector) labelled Synthetic.
- Modify alert, escalation and genai routes to filter by `can`.

**Tests first**
- A matrix test over role (INVESTIGATOR, SUPERVISOR, READONLY, ADMIN) × office scope (same office, child office, other office, other institution) × assignment (assigned, not assigned) for `read`, `write` and `escalate`.
- The two review-focus access cases above.

**Done when:** the matrix passes, existing 787 tests still pass with the default demo user mapped to a seeded employee, and no route returns data outside the caller's scope.

**Risks:** auth currently returns a demo ADMIN when `AUTH_ENABLED=false`. That path must map to a seeded bank-admin context and not bypass the policy.

## Phase 4: mule detection as Module 1

**Files:** create `frontend/src/shell/ModuleWorkspace.js` (shared template: purpose, metrics, alerts, analysis, link to investigation); modify `App.js` so `/modules/mule` hosts the existing dashboard, queue, network and live pages; keep old paths as redirects.

**Tests first:** a redirect test per old path; the existing frontend tests unchanged.

**Done when:** no mule capability is lost, old links still work, and all 787 backend tests pass.

## Phase 5: other modules

**Files**
- `backend/fraud_modules/upi.py`: runs R14, R15, R17, R18 and the real-time scorer on rows where `channel == "UPI"`. Status Partial. Signals that need `upi_id`, device or IP are listed as "needs data".
- `backend/fraud_modules/transaction_aml.py`: wraps R06, R12, R14 and the pass-through and circular-flow signals plus the STR service. Status Partial.
- `backend/fraud_modules/identity.py`: wraps `EntityResolutionService` and `OnboardingService`. Status Partial; evidence of verification is stored apart from inferred risk.
- `backend/fraud_modules/loan.py`: registry entry and a `ScreeningService` call for borrower sanction checks only. Status Planned, with required data fields listed.

**Tests first:** each module returns its status; Loan returns no findings for any input except a sanction-screening call; UPI on the AMLworld sample reports which signals could not run.

**Done when:** every alert from these modules has an explanation, and no Planned module shows data.

## Phase 6: unified intelligence

**Files**
- `backend/fraud_modules/intelligence/entities.py`: frozen `EntityRef(kind, entity_id)`; `Link(a, b, basis, confidence)` with `confidence` in `("VERIFIED", "PROBABLE", "POSSIBLE")`.
- `backend/fraud_modules/intelligence/correlate.py`: `correlate(findings) -> tuple[CorrelatedFinding, ...]`, each holding the original per-module findings unchanged.
- `GET /api/v1/intelligence/entities/{entity_id}` and a `frontend/src/shell/EntityView.js`.
- Add a CRITICAL level to the platform risk vocabulary only in the consolidated view, with documented criteria, since the module classifier has three levels.

**Tests first:** an account flagged by Mule and by UPI resolves to one entity with both findings; shared verified id gives VERIFIED; similar name only gives POSSIBLE; module scores are returned side by side and never combined.

## Phase 7: investigation, gateway, Mule Chat, e2e

**Files**
- `backend/services/investigation/investigation_service.py`: facade over alert cases and complaint cases. Statuses New, Under Review, Investigating, Escalated, Resolved, Closed; outcomes Confirmed, False positive, Unresolved; assignment; every transition writes an audit entry.
- `backend/fraud_modules/intervention.py`: simulated gateway. It records a hold or verification request in the audit chain and returns "SIMULATED: no bank system connected". The UI shows that label.
- Extend `AuditService` so the investigation workflow is chained.
- Mule Chat retrieval filtered through `access.policy.can`.
- `e2e/` Playwright test of: alert, case, evidence, outcome, report.

**Tests first:** invalid transitions are rejected; a hold request appears in the audit chain and `verify_integrity` still passes; chat never returns a case the caller cannot read.

**Done when:** the e2e journey passes and the full baseline is green.

## Not built, on purpose

Feature store, analytical warehouse, durable event store, bank-specific connectors for loan, UPI switch, KYC and I4C, SSO and MFA, and live STR submission. They stay Planned in the registry. The event bus remains the optional Kafka adapter that exists today.

## Open decision

**Tenancy depth.** Default: put an institution id on every new record and seed one public-sector and one private-sector demo bank, labelled Synthetic, with full office and branch hierarchy. The alternative is a single demo bank, which is faster but cannot show Diagram 2's institution isolation.
