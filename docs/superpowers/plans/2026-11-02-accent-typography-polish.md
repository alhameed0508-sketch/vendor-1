# Accent, Typography and Professional Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every MuleCatch screen an emerald accent, an Inter + JetBrains Mono type system, and consistent spacing and elevation in dark and light themes.

**Architecture:** One token layer in `frontend/src/App.css` drives accent, type, spacing, radius, shadow and focus. Legacy `--emerald*` aliases are re-pointed so existing CSS follows the new brand. Screens are then polished stage by stage, replacing hard-coded brand and state hex with tokens. Two small Jest guard tests (token contract and "no brand-blue hex left") make the visual work checkable.

**Tech Stack:** React 18 (craco/CRA), plain CSS custom properties, Jest + Testing Library, Playwright MCP for visual checks. No new dependencies, no backend changes.

**Spec:** `docs/superpowers/specs/2026-11-02-accent-typography-polish-design.md`

## Global Constraints

- Accent dark `#10B981`, hover `#34D399`, text-on-accent `#04261A`; tint = accent at 14%.
- Accent light `#047857`, hover `#065F46`, text-on-accent `#FFFFFF`; tint = accent at 8%.
- Severity keeps red / orange / amber. Brand green is never used for "low risk". `--accent-green` stays only where it already means success (STR Filed badge, Live dot).
- Fonts: Inter (sans + display, headings 600–700), JetBrains Mono (IDs, numerals, eyebrows). Space Grotesk removed. One font load with `display=swap`.
- Type scale 12 / 13 / 14 / 16 / 20 / 24 / 30 px; body line-height 1.5; `font-variant-numeric: tabular-nums` on table and stat numerals.
- Spacing 4/8/12/16/24/32; card radius 12, control radius 8; one soft shadow + 1px border; no idle glow.
- Text contrast ≥ 4.5:1 in both themes; visible focus ring; `cursor: pointer` on clickables; transitions 150–300ms; `prefers-reduced-motion` respected; no emoji icons; no hover layout shift.
- No horizontal page scroll at 375 / 768 / 1024 / 1440; tables scroll inside their own wrapper; primary controls ≥ 44px tall at ≤ 640px.
- No new dependencies, no backend changes, no layout restructuring. Existing tests (16 suites, 126 tests) keep passing. Chart/graph colours that encode data may stay hard-coded.
- Both themes verified visually per screen at 1440 and 375px.

## Review Focus

- Light theme text/muted text under 4.5:1 on `--bg-card` and `--bg-surface` — pinned by the contrast test in Task 1.
- Brand green mistaken for risk state: any `.badge-LOW` / low-risk bar using the accent — pinned by the guard test in Task 2.
- Focus ring invisible on accent-filled buttons — pinned by the focus-token assertion in Task 2.
- Wide tables or the board causing page-level horizontal scroll at 375px — checked per screen in Tasks 3–6 and by the overflow script in Task 6.
- Fonts failing to load (offline / blocked): fallbacks must still render legibly — `--font-sans` and `--font-mono` carry system fallbacks, asserted in Task 1.

## File Structure

| File | Responsibility |
|---|---|
| `frontend/src/index.css` | Single Google Fonts load (Inter + JetBrains Mono) and base reset. |
| `frontend/src/App.css` | Tokens (both themes), shared component styles, sidebar, screen styles. |
| `frontend/src/styles/tokens.test.js` (create) | Reads CSS text; asserts token contract and WCAG contrast of text/accent pairs. |
| `frontend/src/styles/noBrandHex.test.js` (create) | Asserts screen JS files contain no brand-blue / legacy-accent hex. |
| `frontend/src/styles/contrast.js` (create) | `hexToRgb`, `contrastRatio(fg, bg)` helpers used by the tests. |
| Screen files (Dashboard, AlertQueue, AlertDetail, NetworkOverview, NetworkGraph, ROIDashboard, CompliancePortal, RiskOperationsPage, DataImportPage, BenchmarkPage, LoginPage, Sidebar, CommandPalette) | Replace hard-coded brand/state hex with `var(--token)`; adjust spacing to scale. |

---

### Task 1: Token layer and fonts

**Files:**
- Create: `frontend/src/styles/contrast.js`, `frontend/src/styles/tokens.test.js`
- Modify: `frontend/src/index.css` (font import), `frontend/src/App.css` (`:root,[data-theme="dark"]` block ~10–115, `html[data-theme="light"]` block ~117–190, `:focus-visible` ~1328)

**Interfaces:**
- Produces: `contrastRatio(fg: string, bg: string): number` and `hexToRgb(hex: string): [number, number, number]` in `styles/contrast.js`; CSS tokens `--accent`, `--accent-hover`, `--accent-tint`, `--on-accent`, `--font-sans`, `--font-mono`, `--font-display`, `--space-1..8`, `--radius-card`, `--radius-control`, `--shadow-card`, `--focus-ring` in both themes. Legacy `--emerald`, `--emerald-light`, `--emerald-dim`, `--emerald-glow`, `--accent-primary`, `--color-primary` alias the new accent.

- [ ] **Step 1: Write failing tests** in `tokens.test.js`, reading `App.css` and `index.css` with `fs`:
  - `test('contrastRatio black on white is 21')` (`contrastRatio('#000000','#FFFFFF')` ≈ 21).
  - `test('dark accent tokens match spec')`: dark block defines `--accent: #10B981`, `--accent-hover: #34D399`, `--on-accent: #04261A`.
  - `test('light accent tokens match spec')`: light block defines `--accent: #047857`, `--accent-hover: #065F46`, `--on-accent: #FFFFFF`.
  - `test('on-accent text meets 4.5:1 in both themes')` and `test('light text-secondary and text-muted meet 4.5:1 on bg-card')` using `contrastRatio` on parsed hex values.
  - `test('emerald aliases follow the accent')`: no `--emerald*` value contains `#2563EB`.
  - `test('fonts: Inter + JetBrains Mono, no Space Grotesk')`: `index.css` contains `Inter` and `JetBrains+Mono`, not `Space+Grotesk`, and includes `display=swap`; `--font-sans` ends with a generic family (`sans-serif`), `--font-mono` with `monospace`.
  - `test('focus ring uses accent token')`: `:focus-visible` rule references `var(--focus-ring)` or `var(--accent)`.
- [ ] **Step 2: Run** `cd frontend && CI=true npx craco test --watchAll=false src/styles` — Expected: FAIL (helpers/tokens missing).
- [ ] **Step 3: Implement** `contrast.js` (WCAG relative luminance; accepts `#RRGGBB`). Edit both token blocks to the Global Constraints values; re-point legacy aliases and `--gradient-brand` to the accent; add spacing/radius/shadow/type tokens; set `body { font-family: var(--font-sans); line-height: 1.5; font-size: 14px }`; headings use `--font-display`, weight 600–700, `letter-spacing: -0.01em`; `.eyebrow`, ids and `.mono` use `--font-mono`. Light `--text-muted` must be ≥ `#475569`. Replace the three-family `@import` in `index.css` with one Inter + JetBrains Mono import using `display=swap`.
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Run full frontend suite** `CI=true npx craco test --watchAll=false` — Expected: 126+ tests pass.
- [ ] **Step 6: Visual check** (dark + light, 1440): app loads, sidebar and buttons show emerald, fonts are Inter. Commit: `feat: emerald accent tokens and Inter/JetBrains Mono type system`.

---

### Task 2: Shared components

**Files:**
- Modify: `frontend/src/App.css` (`.btn*` ~893, `.glass-card` ~981, `.badge*` ~1066, `.filter-tab` ~1095, inputs ~1162, `.sidebar-*` ~784/~1441, table, command palette, reduced-motion ~1613), `frontend/src/components/Sidebar.js`, `frontend/src/components/CommandPalette.js` (hex only)
- Test: `frontend/src/styles/tokens.test.js` (extend)

**Interfaces:**
- Consumes: Task 1 tokens.
- Produces: component classes unchanged in name (`.btn`, `.btn-primary`, `.btn-ghost`, `.glass-card`, `.badge-*`, `.filter-tab`, `.sidebar-link`) so screens need no markup change.

- [ ] **Step 1: Extend tests**:
  - `test('btn-primary uses accent and on-accent tokens')`: `.btn-primary` rule contains `var(--accent)` and `var(--on-accent)`.
  - `test('low-risk badge does not use the brand accent')`: `.badge-LOW` / `.badge-low` rule contains neither `--accent` nor `--emerald`.
  - `test('no idle glow on cards')`: `.glass-card` rule has no `box-shadow` containing `rgba(37`.
  - `test('interactive classes set cursor pointer')`: `.btn`, `.filter-tab`, `.sidebar-link` each contain `cursor: pointer`.
  - `test('reduced motion block exists')`.
- [ ] **Step 2: Run** `CI=true npx craco test --watchAll=false src/styles` — Expected: FAIL on the new assertions.
- [ ] **Step 3: Implement** the CSS: solid accent buttons (hover = `--accent-hover`, no glow, no ripple layout shift), ghost buttons with border, 38→40px min-height (44px at ≤640px); inputs with `--radius-control` and accent focus ring; badges on tint backgrounds with severity colours, low/neutral on slate; filter tabs active = accent tint + accent text; sidebar active link = accent tint with 3px accent left bar; table header 12px uppercase mono-free, rows 44px, `tabular-nums`, wrapper `overflow-x: auto`; cards `--radius-card`, `--shadow-card`, 1px border; transitions 150–200ms on color/background/border/opacity only.
- [ ] **Step 4: Run** the style tests then the full suite — Expected: all PASS.
- [ ] **Step 5: Visual check** Dashboard shell in dark + light at 1440 and 375. Commit: `feat: polish shared components for emerald design system`.

---

### Task 3: Dashboard, Alert Queue, Alert Detail

**Files:**
- Modify: `frontend/src/investigator_dashboard/Dashboard.js`, `frontend/src/alert_queue/AlertQueue.js`, `frontend/src/alert_queue/BoardView.js`, `frontend/src/alert_detail/AlertDetail.js`, and the matching blocks in `frontend/src/App.css` (board, view-toggle, approval dialog, stat cards)
- Test: `frontend/src/styles/noBrandHex.test.js` (create)

**Interfaces:**
- Produces: `noBrandHex.test.js` exporting nothing; it holds a `SCREEN_FILES` array that Tasks 4 and 5 append to. Forbidden pattern: `/#(2563EB|3B82F6|1D4ED8|60A5FA)/i` and `rgba\(37,\s*99,\s*235`.

- [ ] **Step 1: Write failing test** `test('screen files contain no brand-blue hex')` for the Task 3 files (`it.each(SCREEN_FILES)`); also assert the board columns keep `STR Filed` visible (existing board tests already cover; run them).
- [ ] **Step 2: Run** `CI=true npx craco test --watchAll=false src/styles/noBrandHex` — Expected: FAIL only for files that still contain forbidden values (Dashboard has 1 hex; if none fail, the test is vacuous — list the offending file in the failure message and add a deliberate fixture check that the regex matches `#2563EB`).
- [ ] **Step 3: Implement**: stat cards with mono numerals and eyebrow labels; queue toolbar spacing on the 4/8 scale; board columns use column header + count chip, cards 12px radius, selected/drag-over state = accent border; Alert Detail sections as cards with consistent 24px padding, risk score uses severity colour, action buttons use `.btn-primary` / `.btn-ghost`; approval dialog buttons on the new tokens. Replace hex with tokens.
- [ ] **Step 4: Run** `CI=true npx craco test --watchAll=false src/alert_queue src/alert_detail src/investigator_dashboard src/styles` — Expected: PASS.
- [ ] **Step 5: Visual check** each of the three screens, dark + light, 1440 + 375 (board scrolls inside its container, no page scroll). Commit: `feat: polish dashboard, alert queue and alert detail`.

---

### Task 4: Network, ROI Analytics, Compliance

**Files:**
- Modify: `frontend/src/network/NetworkOverview.js`, `frontend/src/network/RegionalStatsPanel.js`, `frontend/src/components/IndiaMap.js`, `frontend/src/graph_viz/NetworkGraph.js`, `frontend/src/graph_viz/NodeDetailPanel.js`, `frontend/src/roi_dashboard/ROIDashboard.js` (37 hex), `frontend/src/compliance_portal/CompliancePortal.js`, matching `App.css` blocks
- Test: append these files to `SCREEN_FILES` in `noBrandHex.test.js`

- [ ] **Step 1: Append files** to `SCREEN_FILES`; run `CI=true npx craco test --watchAll=false src/styles/noBrandHex` — Expected: FAIL naming each file with brand-blue.
- [ ] **Step 2: Implement**: replace brand/state hex with `var(--…)` (SVG attributes use `style={{ fill: 'var(--accent)' }}` or `currentColor`); keep severity and data-encoding colours (graph node risk colours, map choropleth, chart series) but source them from severity tokens where they mean risk; graph selected-node ring and edges to the accent; ROI cards on the shared card/stat styles with mono numerals; Compliance tables in the shared table wrapper.
- [ ] **Step 3: Run** `CI=true npx craco test --watchAll=false src/network src/graph_viz src/roi_dashboard src/compliance_portal src/styles` — Expected: PASS (existing NodeDetailPanel tests unchanged).
- [ ] **Step 4: Visual check** Network (click a node, panel opens, no console error), ROI, Compliance; dark + light; 1440 + 375. Commit: `feat: polish network, ROI and compliance screens`.

---

### Task 5: Customer Risk, Data Import, Benchmarks, Login

**Files:**
- Modify: `frontend/src/risk_operations/RiskOperationsPage.js`, `frontend/src/data_import/DataImportPage.js` (34 hex), `frontend/src/benchmark/BenchmarkPage.js`, `frontend/src/login/LoginPage.js`, matching `App.css` blocks
- Test: append the first three to `SCREEN_FILES`; add `test('login page has labelled inputs')` only if `LoginPage` has no existing test for it (check first)

- [ ] **Step 1: Append files**; run `CI=true npx craco test --watchAll=false src/styles/noBrandHex` — Expected: FAIL for DataImport and Benchmark.
- [ ] **Step 2: Implement**: Data Import dropzone with dashed `--border-strong`, accent tint on drag-over, status chips on severity/neutral tokens; Benchmarks tables and metric tiles on shared styles; Login centred card, Inter heading, accent primary button, visible focus; Customer Risk forms use shared inputs, labels tied to inputs.
- [ ] **Step 3: Run** `CI=true npx craco test --watchAll=false` — Expected: all suites PASS.
- [ ] **Step 4: Visual check** each screen, dark + light, 1440 + 375. Commit: `feat: polish customer risk, data import, benchmarks and login`.

---

### Task 6: Responsive and accessibility sweep, final verification

**Files:**
- Modify: `frontend/src/App.css` (media queries, any overflow fixes found)
- Test: none new unless the sweep finds a logic bug

- [ ] **Step 1: Overflow sweep.** For each route at 375 / 768 / 1024 / 1440 in both themes, run `document.documentElement.scrollWidth <= window.innerWidth` via `browser_evaluate`; Expected: `true` everywhere. Fix any offender inside its container, not by hiding page overflow.
- [ ] **Step 2: Keyboard and contrast sweep.** Tab through Sidebar, Dashboard filters, a board card, the approval dialog: focus ring visible each stop. Spot-check muted text and badges in light theme against 4.5:1.
- [ ] **Step 3: Full verification.** `CI=true npx craco test --watchAll=false` (Expected: all pass) and `npx craco build` (Expected: compiled, no new warnings); backend suite not touched.
- [ ] **Step 4: Cleanup.** `rm -rf .playwright-mcp`; confirm `git status` shows only intended files, `build/` ignored. Commit: `chore: responsive and accessibility sweep` (and the spec + plan docs in the same series if not yet committed).

---

## Self-review

- **Spec coverage:** palette, aliases, risk separation (Tasks 1–2); fonts and scale (1); density/surfaces (1–2); screens (3–5); responsive/a11y/tests/build (6). Touch-target and reduced-motion rules are in Tasks 2 and 6.
- **Type consistency:** `contrastRatio`, `hexToRgb`, `SCREEN_FILES`, token names are identical across tasks.
- **Proportion:** visual tasks verify through two guard tests plus browser checks, since CSS has little unit-testable logic; that gap is stated, not hidden.
