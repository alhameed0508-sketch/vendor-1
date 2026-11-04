# Professional UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the investigator core flow (Dashboard, Alert Queue, Alert Detail, Network graph) a professional dark/light look and a board workflow ending in an approved "STR Filed" state.

**Architecture:** Reuse the existing theme tokens in `frontend/src/App.css` (`:root`/`[data-theme="dark"]` and `html[data-theme="light"]`) and the existing `ThemeContext` + Sidebar toggle. Add a pure board model, a `BoardView`, and an `ApprovalDialog` beside `AlertQueue.js`; add one backend status `STR_FILED`. Graph gets a node side panel and risk legend.

**Tech Stack:** React 18 (CRA/craco), D3 (existing), FastAPI/pydantic, pytest, Jest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-02-professional-ui-redesign-design.md`

## Global Constraints

- No new services or dependencies; native HTML5 drag-and-drop only.
- Backend change limited to the `STR_FILED` status.
- Do not copy Guildly branding, copy or assets.
- Analytics, Compliance, Data Import, Risk Operations, Benchmarks: no layout change.
- Both themes must work: use `var(--…)` tokens only, never hard-coded colours in new CSS.
- Board columns, in order: `OPEN`, `UNDER_REVIEW`, `RESOLVED`, `FALSE_POSITIVE`, `STR_FILED`.
- Moving a card to `STR_FILED` always goes through the approval dialog (reason + confirm).
- View choice stored in `localStorage` key `mulecatch-queue-view` (`"board"` | `"table"`), reads/writes wrapped in try/catch.
- Existing tests keep passing.

## Review Focus

1. Dropping a card onto its own column → no request, no dialog.
2. Approval dialog cancelled or Escape pressed → card stays in its original column, no request sent.
3. STR export succeeds but status PATCH fails (or vice versa) → card reverts, error shown, no silent half-filed state.
4. `localStorage` unavailable or holds an unknown value → falls back to `"table"`, no crash.
5. Alert with unknown/legacy status (e.g. `ESCALATED`, which `AlertQueue.js` sends today but the backend rejects) → shown in a visible fallback, not dropped.

## Dev environment (once)

Backend tests: `.venv/bin/pip install -r backend/requirements-dev.txt`, run with `PYTHONPATH=$PWD/backend:$PWD .venv/bin/python -m pytest <path> -q` from repo root.
Frontend tests: `cd frontend && CI=true npx craco test --watchAll=false <path>`.

## File Structure

| File | Responsibility |
|---|---|
| `backend/api/v1/schemas/alerts.py` (modify) | allow `STR_FILED` |
| `backend/detection/pipeline.py:154` (modify) | status comment |
| `backend/tests/test_alert_status_schema.py` (create) | schema test |
| `frontend/src/alert_queue/boardModel.js` (create) | columns, grouping, approval rule |
| `frontend/src/alert_queue/boardModel.test.js` (create) | model tests |
| `frontend/src/alert_queue/ApprovalDialog.js` (create) | reason + confirm modal |
| `frontend/src/alert_queue/BoardView.js` (create) | columns, cards, drag/drop |
| `frontend/src/alert_queue/useQueueView.js` (create) | persisted board/table toggle |
| `frontend/src/alert_queue/AlertQueue.js` (modify) | toggle, board, wiring, status lists |
| `frontend/src/graph_viz/NodeDetailPanel.js` (create) | node side panel |
| `frontend/src/graph_viz/NetworkGraph.js` (modify) | click handler, risk legend |
| `frontend/src/App.css` (modify) | board, dialog, panel, `badge-STR_FILED`, eyebrow styles |
| `frontend/src/investigator_dashboard/Dashboard.js`, `frontend/src/alert_detail/AlertDetail.js` (modify) | status lists + restyle |

---

### Task 1: Backend `STR_FILED` status

**Files:**
- Modify: `backend/api/v1/schemas/alerts.py:11`, `backend/detection/pipeline.py:154`
- Test: `backend/tests/test_alert_status_schema.py`

**Interfaces:**
- Produces: `AlertUpdateRequest(status="STR_FILED")` validates; any other unknown status still raises `pydantic.ValidationError`.

- [ ] **Step 1: Write failing tests** `test_str_filed_accepted` (`AlertUpdateRequest(status="STR_FILED").status == "STR_FILED"`), `test_unknown_status_rejected` (`"ESCALATED"` raises `ValidationError`), `test_existing_statuses_still_accepted` (parametrized over the four current values).
- [ ] **Step 2: Run** `PYTHONPATH=$PWD/backend:$PWD .venv/bin/python -m pytest backend/tests/test_alert_status_schema.py -q` — Expected: `test_str_filed_accepted` FAILS.
- [ ] **Step 3: Add `STR_FILED` to the pattern** in `alerts.py` and to the comment in `pipeline.py`. Check `alert_repository`/persistence for any other status whitelist (`grep -rn "FALSE_POSITIVE" backend`) and extend it if found.
- [ ] **Step 4: Run** the test file — Expected: all PASS; then full `backend/tests` run for regressions.
- [ ] **Step 5: Commit** `feat: add STR_FILED alert status`.

### Task 2: Board model

**Files:**
- Create: `frontend/src/alert_queue/boardModel.js`, `frontend/src/alert_queue/boardModel.test.js`

**Interfaces:**
- Produces:
  - `BOARD_COLUMNS: Array<{ status: string, label: string }>` in the order given in Global Constraints.
  - `groupByStatus(alerts: Alert[]): Record<string, Alert[]>` — every column key present; alerts with a status not in `BOARD_COLUMNS` go under key `"OTHER"`.
  - `requiresApproval(toStatus: string): boolean` — true only for `"STR_FILED"`.
  - `canMove(fromStatus: string, toStatus: string): boolean` — false when equal.

- [ ] **Step 1: Write failing tests** for: five columns in order; `groupByStatus([])` has all keys with empty arrays; unknown `ESCALATED` lands in `OTHER` (Review Focus 5); `requiresApproval("STR_FILED") === true` and false for the rest; `canMove("OPEN","OPEN") === false` (Review Focus 1).
- [ ] **Step 2: Run** `cd frontend && CI=true npx craco test --watchAll=false src/alert_queue/boardModel.test.js` — Expected: FAIL (module missing).
- [ ] **Step 3: Implement** the four exports as pure functions (no mutation of inputs).
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat: add alert board model`.

### Task 3: Approval dialog

**Files:**
- Create: `frontend/src/alert_queue/ApprovalDialog.js`, `frontend/src/alert_queue/ApprovalDialog.test.js`

**Interfaces:**
- Produces: `default function ApprovalDialog({ alert, onConfirm, onCancel }: { alert: Alert, onConfirm: (reason: string) => Promise<void>, onCancel: () => void })`. Role `dialog`, labelled textarea "Reason for filing", "Confirm filing" button disabled while reason is blank or while `onConfirm` is pending; Escape and "Cancel" call `onCancel`; if `onConfirm` rejects, shows the error message and stays open.

- [ ] **Step 1: Write failing tests**: confirm disabled until reason typed; confirm calls `onConfirm("<reason>")` once; Escape calls `onCancel` and never `onConfirm` (Review Focus 2); rejected `onConfirm` shows `role="alert"` text and dialog remains (Review Focus 3).
- [ ] **Step 2: Run** the test file — Expected: FAIL.
- [ ] **Step 3: Implement** `ApprovalDialog` with focus on the textarea at mount; styles via classes added to `App.css` (`.approval-dialog`, `.approval-backdrop`) using tokens.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat: add STR approval dialog`.

### Task 4: Board view, toggle, wiring

**Files:**
- Create: `frontend/src/alert_queue/BoardView.js`, `frontend/src/alert_queue/useQueueView.js` (+ tests for both)
- Modify: `frontend/src/alert_queue/AlertQueue.js` (status lists at lines ~220 and ~373, status update near ~350, render switch), `frontend/src/App.css`

**Interfaces:**
- Consumes: `BOARD_COLUMNS`, `groupByStatus`, `canMove`, `requiresApproval` (Task 2); `ApprovalDialog` (Task 3).
- Produces:
  - `useQueueView(): ["board" | "table", (v: "board" | "table") => void]` — initial value from `localStorage["mulecatch-queue-view"]`; any other value or a throwing `localStorage` → `"table"`; writes wrapped in try/catch.
  - `default function BoardView({ alerts, onMove, onOpen }: { alerts: Alert[], onMove: (alert: Alert, toStatus: string) => void, onOpen: (alertId: string) => void })` — one column per `BOARD_COLUMNS` plus an "Other" column rendered only when `groupByStatus(...).OTHER` is non-empty; cards draggable (`draggable`, `onDragStart`/`onDrop`), also movable via a keyboard-accessible "Move to…" `<select>` on each card; dropping on the same column does nothing.

- [ ] **Step 1: Write failing tests**: `useQueueView` defaults to `"table"` with empty, garbage, and throwing storage (Review Focus 4) and persists a set value; `BoardView` renders five column headings with correct counts; same-column drop does not call `onMove`; "Move to…" select calls `onMove(alert, "RESOLVED")`; legacy status card appears under "Other".
- [ ] **Step 2: Run** the two test files — Expected: FAIL.
- [ ] **Step 3: Implement** `useQueueView` and `BoardView`.
- [ ] **Step 4: Wire into `AlertQueue.js`**: add a Board/Table segmented toggle in the header; replace the `ESCALATED` entries in both status lists with `STR_FILED` (keep legacy `ESCALATED` label mapping only in `STATUS_CONFIG` for display); `handleMove(alert, to)`: if `!canMove` return; if `requiresApproval(to)` open `ApprovalDialog`; else existing PATCH flow. Dialog `onConfirm(reason)`: `POST /api/v1/compliance/str-export` `{ alert_ids: [alert.alert_id] }`, then `PATCH /api/v1/alerts/{id}` `{ status: "STR_FILED", investigator_notes: reason }`; on any failure throw so the dialog shows the error and the card is left unchanged (optimistic updates only after both succeed).
- [ ] **Step 5: Add `STATUS_CONFIG.STR_FILED` and `.badge-STR_FILED`** (success-toned, near `App.css:1089`), plus board/column/card CSS using tokens only.
- [ ] **Step 6: Add a wiring test** (`AlertQueue.board.test.js`, `apiFetch` mocked): approving a move to `STR_FILED` calls str-export then PATCH in that order; a failing PATCH leaves the card in its column (Review Focus 3). Run all alert_queue tests — Expected: PASS.
- [ ] **Step 7: Commit** `feat: board view and STR approval flow for alert queue`.

### Task 5: Dashboard and Alert Detail polish

**Files:**
- Modify: `frontend/src/investigator_dashboard/Dashboard.js` (status filter ~line 218), `frontend/src/alert_detail/AlertDetail.js` (status list ~line 298), `frontend/src/App.css`

**Interfaces:**
- Consumes: `.badge-STR_FILED` (Task 4).

- [ ] **Step 1: Add `STR_FILED` to both status lists.** Alert Detail's status buttons for `STR_FILED` must not PATCH directly: they open `ApprovalDialog` using the same confirm handler as Task 4 (extract the handler into `alert_queue/fileStr.js` exporting `fileStr(alert, reason): Promise<void>` if sharing is needed, with a test).
- [ ] **Step 2: Restyle** with existing tokens: mono uppercase eyebrow class `.eyebrow` above section titles, `GlassCard` for stat tiles on Dashboard, consistent spacing; verify both themes visually (see Step 4).
- [ ] **Step 3: Run** `CI=true npx craco test --watchAll=false` — Expected: all PASS.
- [ ] **Step 4: Visual check**: start both servers (see README) and review `/`, `/queue`, `/alert/<id>` in dark and light with `chrome-devtools`/Playwright screenshots; fix contrast problems.
- [ ] **Step 5: Commit** `feat: restyle dashboard and alert detail`.

### Task 6: Network graph panel and legend

**Files:**
- Create: `frontend/src/graph_viz/NodeDetailPanel.js`, `frontend/src/graph_viz/NodeDetailPanel.test.js`
- Modify: `frontend/src/graph_viz/NetworkGraph.js` (node group near lines ~547–566, legend near ~837–940)

**Interfaces:**
- Produces: `default function NodeDetailPanel({ node, onClose }: { node: { id: string, smurf_score?: number, role?: string, alert_id?: string } | null, onClose: () => void })` — renders nothing when `node` is null; shows account id, risk label (Low <0.25, Medium <0.45, High <0.65, Critical otherwise, same thresholds as `riskColor`), and a link to `/alert/{alert_id}` when present; Escape and a close button call `onClose`.

- [ ] **Step 1: Write failing tests**: null node renders nothing; risk label boundaries at 0.24/0.25/0.64/0.65; link only when `alert_id`; close button and Escape call `onClose`.
- [ ] **Step 2: Run** the test file — Expected: FAIL.
- [ ] **Step 3: Implement** the panel; in `NetworkGraph.js` add click handler on nodes that stores the selected node in state and renders the panel; add a "Risk" block to the existing legend showing the four `riskColor` steps with labels.
- [ ] **Step 4: Run** the panel tests plus the full frontend suite — Expected: PASS. Visual check of `/network` in both themes.
- [ ] **Step 5: Commit** `feat: network graph node panel and risk legend`.

### Task 7: Final verification

- [ ] **Step 1:** Backend `pytest backend/tests -q` and frontend full suite and `npm run build` (use the install workaround from the dev notes) — Expected: green.
- [ ] **Step 2:** In the running app: drag a card to Resolved (PATCH only), drag to STR Filed (dialog → confirm → card in STR Filed, STR draft visible in Compliance), toggle theme, toggle view and reload (choice persists).
- [ ] **Step 3:** Update the table in `docs/` or README only if user-visible workflow docs mention statuses; commit.
