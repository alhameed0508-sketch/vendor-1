# Accent, Typography and Professional Polish — Design

Follows `2026-11-02-professional-ui-redesign-design.md` (board, approval flow, graph panel — done).

## Intent
Give MuleCatch a distinct, bank-grade identity: an emerald accent, one clean type
system, and consistent spacing/elevation, applied to every screen. Inputs come from
the user's choices plus the ui-ux-pro-max design-system search (fintech dark mode:
deep near-black background, green positive accent, high contrast, visible focus).

## Decided by the user
- Accent: emerald green.
- Fonts: Inter (all UI text) + JetBrains Mono (IDs, numbers, eyebrow labels). Space Grotesk is dropped.
- Density: balanced (slightly tighter spacing, consistent radii and shadows, same layouts).
- Scope: global tokens, then every screen hand-polished: Dashboard, Alert Queue, Alert Detail, Network, ROI Analytics, Compliance, Customer Risk (Onboarding), Data Import, Benchmarks, Login, Sidebar.

## Goals
- One token layer in `frontend/src/App.css` drives accent, type, spacing, radius, shadow, in both themes.
- Accent used for primary actions, active nav, focus rings, selected filters, links.
- Meets ui-ux-pro-max rules: text contrast ≥ 4.5:1 in both themes, visible focus rings, `cursor: pointer` on clickable items, 150–300 ms transitions, `prefers-reduced-motion` respected, no emoji icons, no layout shift on hover, tables scroll horizontally on narrow screens.
- Responsive and free of horizontal page scroll at 375, 768, 1024, 1440 px.

## Non-goals
- No layout restructuring, new features, new dependencies or backend changes.
- No change to detection logic, data, routes or auth.
- No copying Guildly branding.

## Anti-goals
- Accent that reads as "low risk" or "success" by accident (see risk colours below).
- Light theme that is an afterthought, or text below contrast minimum.
- Visual churn that breaks existing tests or the board / approval / graph-panel work.

## Palette (my calls, adjustable)
| Token | Dark | Light |
|---|---|---|
| accent | `#10B981` | `#047857` (white text ≥ 5:1) |
| accent hover | `#34D399` | `#065F46` |
| accent-dim (tint) | accent at 14% | accent at 8% |
| text on accent | `#04261A` | `#FFFFFF` |
| background | keep deep near-black | keep light neutral |

The legacy `--emerald*` aliases currently point at blue; they are re-pointed to the real accent so code that uses them follows the new brand without edits.

**Risk colours stay separate from the accent.** Severity keeps red (critical), orange (high), amber (medium). "Low" and other neutral/positive states move to a neutral slate/teal so the brand green is never mistaken for "safe". `--accent-green` keeps its current meaning only where it already denotes success (e.g. STR Filed badge, "Live" dot); the builder checks each use.

## Typography (my calls)
- `--font-sans`: Inter; `--font-display` becomes Inter too (headings 600–700, tighter tracking); `--font-mono`: JetBrains Mono.
- Scale: 12 / 13 / 14 (body) / 16 / 20 / 24 / 30 px; body line-height 1.5; numerals in tables and stats use `font-variant-numeric: tabular-nums`.
- Fonts load once (replace the current three-family import in `src/index.css`), `display=swap`.

## Density and surfaces (my calls)
- Spacing scale 4/8/12/16/24/32; page padding 24–32 px; card radius 12 px, control radius 8 px; one soft shadow level plus a 1 px border; no glow on idle elements.

## Constraints
- Both themes verified visually per screen (dark and light) at 1440 and 375 px.
- Existing tests keep passing; add tests only for new logic (there should be little).
- Hard-coded hex colours in JS/CSS are replaced by tokens where they express brand or state; chart/graph data colours may stay if they encode data.
- Keep touch targets ≥ 44 px on small screens for primary controls.

## Staging
1. Token layer: palette, fonts, spacing, radius, shadow, focus ring, reduced-motion (global; both themes).
2. Shared components: buttons, inputs, badges, filter tabs, tables, cards, sidebar, command palette.
3. Dashboard, Alert Queue, Alert Detail.
4. Network, ROI Analytics, Compliance.
5. Customer Risk, Data Import, Benchmarks, Login.
6. Responsive and accessibility sweep, then full test + build.

## Left to the builder
Exact tint values, component-level spacing, how to replace hard-coded hex per file, icon sizing, skeleton states.

## Open questions
None.
