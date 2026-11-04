# Professional UI Redesign — Design

## Intent
Make MuleCatch look and flow like a professional investigator workspace, taking
its visual and workflow cues from tryguildly.com (dark terminal-pro look,
board-based "ask, approve, ship" flow). Reference site has no graph; "graph"
here means MuleCatch's own network graph, restyled.

## Goals
- Core flow redone: Dashboard, Alert Queue, Alert Detail, Network graph.
- Dark and light themes with a toggle (builds on `frontend/src/ThemeContext.js`,
  which already sets `data-theme` and persists to localStorage).
- Alert Queue offers a board view and the existing table view, switchable; the
  choice is remembered per viewer.
- Moving an alert toward STR filing needs an explicit approval step.
- Network graph keeps its data; gains risk-coloured nodes, a legend and a
  node-detail side panel.
- Colours, type and spacing are defined once as CSS variables so untouched pages
  inherit the new look.

## Non-goals
- No restyle or layout change of Analytics, Compliance, Data Import, Risk
  Operations, Benchmarks beyond inheriting the tokens.
- No new services or dependencies. Backend change limited to the `STR_FILED` status.
- No copying Guildly's branding, copy or assets.

## Anti-goals
- A redesign that breaks existing routes, auth, or tests.
- Light theme that is an afterthought (unreadable contrast).
- Drag-and-drop that changes status without the approval step where required.

## Look
- Dark: deep background, card panels, mono uppercase eyebrow labels, one accent.
- Light: same layout, clean neutrals, same accent family.
- Risk colours (low/medium/high/critical) are shared by cards, badges and graph nodes.

## Workflow (board)
Backend alert statuses today: `OPEN`, `UNDER_REVIEW`, `RESOLVED`,
`FALSE_POSITIVE` (`backend/api/v1/schemas/alerts.py`). There is no STR status.

**Decided by user:** a dedicated "STR Filed" column is required. Add an `STR_FILED`
status to the alert status pattern (`backend/api/v1/schemas/alerts.py`) and wherever
the alert service validates or stores status. Board columns: Open, Under Review,
Resolved, False Positive, STR Filed. Moving a card to STR Filed opens the approval
panel (reason + confirm); confirming sets `STR_FILED` and calls the existing STR
export/escalation endpoint.

## Graph
`frontend/src/graph_viz/NetworkGraph.js` keeps its data source. Add: node colour
by risk level, legend, click-to-open side panel (account, risk, links to alert).

## Constraints
- Stack stays React (CRA/craco) + existing CSS. Reuse `components/ui` (GlassCard, BackgroundGrid).
- Existing tests keep passing; new UI logic gets tests (board status mapping,
  view toggle persistence, approval gate).
- Must work at laptop width; keyboard accessible; contrast OK in both themes.
- Local dev note: frontend installs only via `npm install --no-package-lock --legacy-peer-deps`
  plus `ajv@8` (lockfile is out of sync) — fixing that is out of scope.

## Staging
1. Theme tokens (dark + light) and shared card/badge styles.
2. Dashboard.
3. Alert Queue: table restyle, board view, toggle, approval gate.
4. Alert Detail.
5. Network graph restyle.

## Left to the builder
Exact palette, fonts, spacing scale, drag-and-drop library choice (prefer native
HTML5 DnD or an already-installed package), component split.

## Open questions
None.
