# Return fraud: gap analysis and readiness report

Audit of the return-fraud screens and API (`feat/return-fraud`) against the spec's gap table (G1 to G10), its
self-explanation section (9.1 to 9.6) and its validation gates. Statuses are what the code and tests show today.
Anything not run is marked **not run**, not passed.

## Where this differs from the spec

| Spec | Built | Why |
|---|---|---|
| FastAPI, SQLite, TypeScript, Vite, Zustand | FastAPI, in-memory repository, React JavaScript (CRA/craco), React state | Fits the MuleCatch stack, auth and design tokens instead of adding a second one. |
| No login | One click on "View as guest" | MuleCatch's existing guest flow. Guests see synthetic data and cannot change anything. |
| React Flow or Cytoscape graph | A small static SVG | A ring has at most 8 customers on screen (`MAX_RING_COLUMNS`), so a graph engine adds weight for nothing. See G1. |
| Gemini 2.5 Flash reads the photo | Optional text-only judgment of photo labels | The `genai` SDK is not installed. The image check is a **simulation** and says so on every screen and in the bank package. |
| PyMuPDF, exifread, ReportLab | pypdf, Pillow, fpdf2 | PyMuPDF is AGPL. The others were already installed or are permissively licensed. |
| `/receipts/verify`, `/admin/queue`, `/evidence/{id}/pdf` | `/api/v1/returns/...` (list, overview, detail, review, package, package.pdf, two webhooks) | Same functions under one prefix. A standalone receipt-check endpoint is not built. |

## Open-source parts used

| Library | Licence | Used for |
|---|---|---|
| pypdf 6.21.4 | BSD-3 | Receipt producer, dates and later saves. Parsed once when a claim is filed, on a capped pool of two. A file it cannot read falls back to a byte scan and is flagged. The seeded receipts are real PDFs. |
| ImageHash 4.3.2 (with PyWavelets 1.6.0) | BSD-2 | Perceptual hash: the same photo sent by another customer, even resized or stripped of metadata. |
| RapidFuzz 3.14.5 | MIT | Claim text that reads almost the same across a ring. |
| Pillow | HPND | EXIF and image size. |
| fpdf2 | LGPL | The PDF bank package. |

PyWavelets is held at 1.6.0 because newer releases need numpy 1.26.4 and the repo pins 1.26.3.
A GitHub search for return-fraud projects found only small student repositories with no licence, so none was reused.

## Gap table

| ID | Gap | Status | Evidence |
|---|---|---|---|
| G1 | Graph engine | **Closed** (documented) | Static SVG in `frontend/src/returns/ClaimLayers.js`, at most 8 customers, no physics, no animation above the ring's own few edges. A force engine would be needed only past about 150 nodes. |
| G2 | Evidence ledger and bank package | **Closed** | `ClaimView.js` ledger with source, evidence time and agreeing checks; `backend/return_fraud/evidence.py` PDF and JSON with every check, fired or not, and a SHA-256 integrity block. |
| G3 | Score provenance | **Closed** | `ClaimScore.js`: each check's share of the score, adjustments, the combined score; a corroboration badge; the three-line narrative. `fusion.py` `_contributions` makes the shares add up to the score, tested. |
| G4 | Failure states | **Partly closed** | Overview, case page and the linked-claims panel show the last result with its time and a Retry (`lastGood.js`, `Notices.js`). The saved result lives in memory only and is keyed by user, so a reload or another person starts clean. A refusal (403, 404, 422) is shown as is, never hidden behind an old result. Verified in the browser by stopping the backend. Not covered: the field capture page and downloads show a plain error, because they write or fetch files. |
| G5 | Tablet and phone | **Partly closed** | Phone: the graph is replaced by a note and the ledger scrolls sideways; checked at 390 px with no page overflow. Tablet: the graph sits in a scrolling box that allows touch pan and pinch. Not tried on a real touch device. |
| G6 | Guided entry | **Closed, with changes** | Three cards: See it work, Review what needs a person, Check a return in the field. The spec's "Verify a receipt" card and the "What you'll see" thumbnail strip are not built. |
| G7 | Case narrative strip | **Closed, with changes** | Three parts with a coloured recommendation and two actions beside it. No per-line icons. The narrative leads with the three strongest checks and points to the ledger for the rest. |
| G8 | Microcopy | **Partly closed** | Empty, loading and error texts follow the spec's pattern; check names carry one-sentence tooltips. The primary button reads "Check this return", not "File this return claim". |
| G9 | Ring animation | **Closed, with changes** | CSS animation of about 4 s with a caption and a Replay button. The score does not tick up in sync, and the "What you're seeing" card is not built. Motion was not watched in a browser. |
| G10 | Demo resilience | **Closed, with one step** | Seeded synthetic claims, a guided tour and the guest login. One click is needed to enter. |

## Self-explanation (section 9)

| Item | Status | Where |
|---|---|---|
| 9.1 Guided entry | Implemented, with changes | `ReturnsPage.js` `GuidedEntry`, `DemoTour.js` |
| 9.2 Narrative strip | Implemented | `ClaimView.js` `Strip`, `evidence.py` `narrative` |
| 9.3 Microcopy | Partly implemented | `Notices.js`, `ClaimLayers.js`, `labels.js` |
| 9.4 Aha moment | Partly implemented | `ClaimLayers.js` `RingGraph`, `returns.css` |
| 9.5 Progressive disclosure | Partly implemented | Raw data is folded away and labelled "for debugging, not for review". The three layers and the ledger are always open. |
| 9.6 Help without modals | Partly implemented | Tooltips on check names (`SIGNAL_HELP`), an inline help panel. The panel is short, not eight sections, and the dispute category has a note rather than expandable definitions. |

## Validation gates

| Gate | Result |
|---|---|
| Failure states: stop the backend | **Pass.** `/returns` shows the last result, its time and Retry. |
| Empty states | **Pass.** Unit tests cover an empty heatmap, graph and timeline. |
| Score reconciliation | **Pass.** Tests: the contributions plus adjustments equal the combined score within 0.3 rounding. |
| Bank package has every check | **Pass.** `test_return_fraud_evidence.py` lists fired and quiet checks. |
| Shown score agrees with the tier | **Pass.** Tested; the page says when it differs from the combined score. |
| Timeline scrubber drives the layers | **Pass** in unit tests. |
| Colour never carries meaning alone | **Pass by design.** Every result has a word and a glyph. No colour-blind simulator was run. |
| Timestamps | **Partly.** The package keeps full ISO times. The screens show day, month and minute in IST, not seconds. |
| Graph at 150 nodes | **Not applicable.** The graph never has more than 8 customers. |
| Contrast (WCAG AA), keyboard walk, projector readability, scenarios under 2 s | **Not run.** |
| The Stranger Test (three people) | **Not run.** It needs real people. |

## Readiness report

**Fixed in this pass**
- Photo reuse across customers (ImageHash), receipt edit detection through pypdf, near-identical claim text (RapidFuzz).
- Each check's share of the score, where it comes from, and which other checks agree.
- Last-result fallback, linked-claims retry, phone and tablet graph handling, empty states.
- Security review findings: oversized images and untrusted PDFs are bounded; the PDF is parsed once at filing; an oversized photo is reported as unchecked rather than skipped; the last-result cache is in memory and per user.
- The seeded demo receipts were hand-built bytes that pypdf could not open, so the demo never used it. They are now valid PDFs.

**Deferred, with reason**
- Real image model: needs the `genai` SDK and an API key.
- Standalone receipt-check page and endpoint, "What you'll see" thumbnails, score tick-up, eight-section help: not needed to show the core flow.
- Delivery-scan engine beyond webhook events, and an installable phone app: only the capture page exists.
- The Stranger Test and accessibility measurements: need people and tools.

**Three riskiest elements for a demo**
1. The photo-against-claim check is a simulation. A viewer who assumes it reads pixels will be misled unless the label is noticed.
2. The ring animation: its timing was never watched in a browser.
3. The guest login and seeded data: if the backend is down at the start, there is no session to show a last result from.

**30-second path per scenario** (open Return fraud, choose "See it work", step through the tour)
- Ordinary return: refund, nothing fired.
- Edited receipt: one loud check, so it stays at "Ask for proof".
- Old photo: two checks agree, so "Hold the refund".
- Ring: five customers, six checks agree, open the case and watch the graph.
- Worn once, says it never arrived, carrier damage: each shows one reason a person must weigh.

**Stranger Test, from the microcopy only:** likely to pass parts (a), (b) and (d), uncertain on (c) because the score
is a heuristic with no stated scale. This is an estimate, not a result.

**Where the screens could still imply false certainty**
- Scores such as 100 or 23.0 points look precise. The weights are chosen by hand and were never calibrated on labelled data.
- The shares in "How the score adds up" are a presentation of combined evidence, not separate causes.
- Photo reuse uses a 6-bit hash distance. Two honest customers who send a similar stock product photo could match.
- The dispute category is indicative. The package says to confirm it against the bank's own reason codes.
- All seeded claims are synthetic, and every "ring" in the demo was built to be found.

**Known limit:** a crafted PDF that hangs pypdf holds one of two parser slots until it ends. While both are held, new receipts are read by the byte scan and flagged. A subprocess with a hard kill would remove this.

**Receipt reading when parsers are busy:** if both parser slots are taken, the receipt is marked `deferred`, scored without the byte-scan penalty, and parsed again on the next read. Only a file pypdf cannot read, or that hangs, gets the +15.
**Oversized photos:** JPEG, TIFF and WebP metadata is still read (it sits in the header). PNG metadata is not, because it can follow the pixels.
