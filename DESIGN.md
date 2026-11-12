---
name: Netrava IntentLock
description: Merchant console for AI-agent purchases, kept as a reconciliation book.
colors:
  paper: "#f1f4ef"
  panel: "#fbfcfa"
  sunken: "#e8ede6"
  rule: "#d3dcd0"
  rule-strong: "#b3c1b0"
  ink: "#14202a"
  ink-2: "#3c4a52"
  muted: "#5d6b72"
  cloth: "#15392d"
  cloth-2: "#1d4a3b"
  cloth-ink: "#e4eee8"
  cloth-muted: "#9bb6a8"
  cloth-line: "#2a5646"
  accent: "#1d6a4d"
  accent-ink: "#ffffff"
  accent-soft: "#dcebe2"
  focus: "#2563a8"
  allow: "#1c6a45"
  allow-bg: "#e1f0e6"
  block: "#b42318"
  block-bg: "#fbe8e5"
  reauth: "#935600"
  reauth-bg: "#fbefd8"
  review: "#1f5a99"
  review-bg: "#e3edf8"
typography:
  display:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "clamp(1.5rem, 1.25rem + 1vw, 1.95rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "clamp(1.15rem, 1rem + .6vw, 1.45rem)"
    fontWeight: 600
    lineHeight: 1.3
  title-serif:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "clamp(1.2rem, 1.05rem + .6vw, 1.5rem)"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.005em"
  title:
    fontFamily: "Source Sans 3, system-ui, Segoe UI, sans-serif"
    fontSize: "1.02rem"
    fontWeight: 650
    lineHeight: 1.2
  body:
    fontFamily: "Source Sans 3, system-ui, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum, lnum"
  label:
    fontFamily: "Source Sans 3, system-ui, Segoe UI, sans-serif"
    fontSize: "0.76rem"
    fontWeight: 650
    letterSpacing: "0.06em"
  mono:
    fontFamily: "Source Code Pro, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.82rem"
    fontWeight: 400
rounded:
  bar: "2px"
  badge: "3px"
  chip: "4px"
  control: "5px"
  panel: "6px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  gutter: "28px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.control}"
    padding: "7px 14px"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "7px 14px"
  button-quiet:
    textColor: "{colors.accent}"
    rounded: "{rounded.control}"
    padding: "7px 6px"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
  panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.panel}"
    padding: "18px 20px"
  rail:
    backgroundColor: "{colors.cloth}"
    textColor: "{colors.cloth-ink}"
    width: "236px"
  rail-nav-active:
    backgroundColor: "{colors.cloth-2}"
    textColor: "{colors.cloth-ink}"
    rounded: "{rounded.control}"
    padding: "7px 10px"
  segmented-on:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.panel}"
    padding: "6px 12px"
  chip:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.chip}"
    padding: "4px 10px"
  badge-allow:
    backgroundColor: "{colors.allow-bg}"
    textColor: "{colors.allow}"
    rounded: "{rounded.badge}"
    padding: "2px 8px"
  badge-block:
    backgroundColor: "{colors.block-bg}"
    textColor: "{colors.block}"
    rounded: "{rounded.badge}"
    padding: "2px 8px"
  badge-reauth:
    backgroundColor: "{colors.reauth-bg}"
    textColor: "{colors.reauth}"
    rounded: "{rounded.badge}"
    padding: "2px 8px"
  badge-review:
    backgroundColor: "{colors.review-bg}"
    textColor: "{colors.review}"
    rounded: "{rounded.badge}"
    padding: "2px 8px"
---

# Design System: Netrava IntentLock

## Overview

**Creative North Star: "The Reconciliation Book"**

The console is kept like a merchant's account book. A bookcloth-green rail binds the left edge; the page is pale ruled ledger paper; text is blue-black ink; refusals post in red ink with parenthesised amounts and the rule code as the memo; totals close on a double rule. Every surface reads as an entry, a statement or a column of figures, never as a grid of KPI tiles.

Density is working-office density: 15px body, tight table rows, hairline seams between panels, and figures set tabular everywhere so columns add up by eye. Serif carries the statement voice (page titles, the dashboard headline sentence, flow-page questions); a workhorse sans carries every control and label; mono carries references, rule codes and version strings.

Light and dark share one token set: a `prefers-color-scheme: dark` block swaps every value, so components only ever reference tokens.

**Key Characteristics:**
- Bookcloth rail, ruled paper ground, hairline seams, no drop shadows.
- Four state inks (green allow, red block, amber reauthorise, blue review), each with a tinted ground.
- Ledger tables with uppercase tracked column heads, faint vertical column rules and a double-ruled total.
- Serif for statements, sans for operation, mono for references.
- Tabular lining figures on the body element, not opt-in.

## Colors

A restrained cool-green paper palette with one bookcloth accent and four state inks that carry all the meaning.

### Primary
- **Bookcloth Green** (`cloth`, deep shade `cloth-2`): the rail and the public receipt header; the binding of the book. Rail text uses Pale Cloth Ink (`cloth-ink`) and Faded Cloth (`cloth-muted`); internal rail seams use `cloth-line`.
- **Ledger Green** (`accent`, with `accent-soft` tint): primary buttons, links, the active flow step, timeline dots, guide strip ground, text caret, checkbox tint.

### Secondary
- **State inks** (`allow`, `block`, `reauth`, `review`, each with a matching `-bg` ground): badges, notices, chart series, rule bars and amount colouring. Green is captured or allowed, red is refused, amber needs re-approval, blue is unverified or under review. These are the only saturated colours on a screen besides the accent.

### Neutral
- **Ledger Paper** (`paper`): page ground.
- **Clean Sheet** (`panel`): panels, inputs, secondary buttons, flow bar.
- **Sunken Leaf** (`sunken`): flat cards, out-of-stock products, bar tracks, plain badges.
- **Hairline** (`rule`) and **Strong Rule** (`rule-strong`): row dividers and seams; column-head underlines, control borders, statement sub-total rules.
- **Blue-black Ink** (`ink`), **Second Ink** (`ink-2`), **Pencil** (`muted`): primary text, secondary text, captions and column heads.
- **Focus Blue** (`focus`): the 2px focus outline only.

### Named Rules
**The Red Ink Rule.** Red (`block`) means refused and nothing else: refused amounts in parentheses, rule-code memos, the "stopped" count in the headline, failed fields. Never use it for decoration or emphasis.

**The State Pair Rule.** Every state colour ships as an ink plus its tinted ground; a badge or notice uses both, never the ink on paper alone.

## Typography

**Display Font:** Source Serif 4 (Georgia fallback), weights 600/700
**Body Font:** Source Sans 3 (system-ui fallback), weights 400/500/600/650/700
**Label/Mono Font:** Source Code Pro (Consolas fallback), weights 400/500

**Character:** An accountant's book typeset in one superfamily: serif for the sentences that state a position, sans for the machinery, mono for anything a person might copy or cite.

### Hierarchy
- **Display** (serif 600, clamp 1.5 to 1.95rem, 1.15, -0.01em): page h1; held at 1.25rem in the sticky top bar.
- **Headline** (serif 600, clamp 1.15 to 1.45rem, 1.3, max 46ch): the dashboard's one-sentence verdict; the refused count inside it is set roman in red.
- **Title, serif** (serif 600, clamp 1.2 to 1.5rem, 1.25): the question or outcome heading on flow pages (mandate, review, receipt).
- **Title** (sans 650, 1.02rem; panel heads .98rem; h3 .95rem): panel and section headings.
- **Body** (sans 400, 15px, 1.5, tabular lining figures): everything else; ledes cap at 68ch.
- **Label** (sans 650, .76rem, .06em, uppercase): ledger column heads; rail group names use .72rem at .09em. Form labels are sentence case, .8rem 600.
- **Mono** (.78 to .86rem): entry refs like IL-0001, rule codes, policy version, IDs.

### Named Rules
**The Three Voices Rule.** Serif states, sans operates, mono cites. A rule code or reference in sans, or a button in serif, is off-system.

**The Tabular Rule.** Figures are tabular and lining everywhere; amounts right-align and never wrap.

## Layout

A two-column shell: a 236px sticky rail and a fluid main column holding a 58px sticky translucent top bar (paper at 92% with a 6px blur), an optional flow bar of numbered steps, and content padded 24px 28px 56px up to 1320px wide. Pages stack at 20px; panel internals at 8 to 12px. Two-panel splits are proportioned, not even by default (5:6, 7:5, 320px:fluid with a sticky aside, or 2:1:1), and collapse to one column at 880px. Below 960px the rail becomes a 264px off-canvas drawer behind a scrim and gutters drop to 16px. Product grids use auto-fill columns of at least 290px. The public receipt page drops the rail for a cloth header and a 1160px centred column.

## Elevation & Depth

Flat. Depth is conveyed by tone and line: paper, panel and sunken grounds, separated by 1px hairlines and strong rules. There are no drop shadows anywhere; the only `box-shadow` in the build is a 1px inset cloth-line ring on the active rail item, which acts as a border. The top bar's backdrop blur is the only layering effect.

### Named Rules
**The Seam Rule.** Separate surfaces with a hairline seam or a change of ground, never with a shadow.

## Shapes

Small, near-square corners that step by role: 2px on bar tracks and legend swatches, 3px on badges, 4px on chips and product art, 5px on buttons, inputs, segmented controls and rail items, 6px on panels and notices. Full pills appear only on the sandbox status indicator; circles only on status dots, timeline nodes and progress counters. Lines carry the form: hairline row rules, faint vertical column rules, dotted leaders in the statement, a 1px ink rule over and 3px double rule under every total. A dashed border marks quoted seller text as untrusted.

## Components

### Buttons
- **Shape:** gently squared (5px).
- **Primary:** Ledger Green ground, white text, 600 weight, 7px 14px; hover darkens by mixing 12% black.
- **Secondary:** Clean Sheet ground, ink text, strong-rule border; hover darkens the border to second ink.
- **Quiet:** borderless accent text for in-panel actions. **Small:** 4px 10px at .84rem. Disabled at 50% opacity.
- **Focus:** 2px Focus Blue outline, 2px offset, on every interactive element.

### Chips
- **Style:** Clean Sheet ground, second-ink text, strong-rule border, 4px corners, .82rem; used for suggested prompts and quick picks. Hover inks the text and border.

### Segmented control
- One strong-rule bordered strip; the pressed option inverts to ink ground with paper text. Used for period selection.

### Cards / Containers
- **Corner Style:** 6px.
- **Background:** Clean Sheet; flat variant on Sunken Leaf.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** 1px hairline.
- **Internal Padding:** 18px 20px; the panel head aligns its title and a muted note on a shared baseline.

### Inputs / Fields
- **Style:** Clean Sheet ground, strong-rule border, 5px corners, 8px 10px. Labels sit above in sentence case.
- **Focus:** the global Focus Blue outline.
- **Error:** border and ground switch to the block ink and its tint; the message appears below in red.

### Navigation
- **Rail:** cloth ground; brand mark is a 30px rounded tile in inverted cloth with the serif product name. Uppercase tracked group names; items carry an authored 18px line icon (1.6 stroke, round joins) at 80% opacity. Hover and active take the deeper cloth; active adds an inset cloth-line ring and 600 weight.
- **Flow bar:** numbered steps in mono; the current step carries a 2px accent underline; completed steps colour their number in accent.
- **Mobile:** off-canvas rail with a 0.22s slide, disabled under reduced motion.

### Badges and notices
- **Badge:** 3px tag, .76rem 650, a 6px dot in the current colour, ink on tinted ground per state; a plain neutral variant for non-terminal states.
- **Notice:** tinted ground per state with a 35% ink border, 6px corners, 10px 14px.

### Ledger table (signature)
Each proposal is one row: mono reference, time, item with seller below, proposer, memo, amount, outcome badge. Column heads are uppercase tracked labels over a strong rule; rows divide on hairlines with faint vertical column rules; row hover tints with the accent. Refused rows post the amount in red parentheses and the failed rule codes as a red mono memo; captured amounts set in allow green. Footers close with an ink rule over a 3px double rule.

### Reconciliation statement (signature)
An accounting statement, not tiles: labelled lines with dotted leaders running to right-aligned count and value columns; "Less:" lines and their parenthesised figures in red; indented sub-lines in second ink; strong rules above sub-totals; the captured total in 700 weight on a double rule. Leaders drop below 600px.

### Rule bars and charts
Hand-drawn SVG charts on hairline gridlines with 11px muted sans labels; series use the four state inks. Rule bars list each rule's plain name with its mono code, a right-aligned count, and a 7px red bar on a sunken track.

## Do's and Don'ts

### Do:
- **Do** reference tokens only; the dark scheme works by swapping them.
- **Do** post refusals in red ink with parenthesised amounts and the rule code as a mono memo.
- **Do** close totals with a 1px ink rule above and a 3px double rule below.
- **Do** give every entry its sequential mono reference (IL-0001) and name the range in view in table heads.
- **Do** draw icons from the authored set (18px, 1.6 stroke, round joins) and charts in SVG with the state inks.

### Don't:
- **Don't** build dashboards from KPI tile grids; state figures as a reconciliation statement or ledger.
- **Don't** add drop shadows; separate with hairline seams and tonal grounds.
- **Don't** use red for anything but a refusal.
- **Don't** set references, rule codes or IDs in anything but mono, or amounts in anything but right-aligned tabular figures.
