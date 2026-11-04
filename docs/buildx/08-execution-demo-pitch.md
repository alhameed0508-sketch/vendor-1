# 12–15. Hackathon schedule, demo script, pitch outline and go/no-go (Phase I)

## 12.0 Facts to confirm with the organisers first

| Item | What the official page says | Action |
|---|---|---|
| Dates and duration | **Conflicting:** "4th and 5th Nov 2026, 36 Hours" and "13th and 14th Oct 2026, 48 Hours" | Email the T-Hub contact listed on the BuildX page |
| Pre-existing code / prior work | **Allowed** (organisers confirmed, 2026-11-02) | Keep a git log of what was built during the event (`git log --since`), in case judges ask what is new |
| Datasets / external APIs | Not stated | Ask: are public datasets (IBM AMLworld) and synthetic data allowed? |
| Judging criteria | Not published | Do not guess; build to the challenge text ("identify suspicious transactions while minimising false alerts for genuine customers") |
| Team size | 2–4 in one place, 2–5 in another | Confirm |

If pre-existing code is not allowed, the plan changes: rebuild only the MVP
slice (ingest → Louvain + smurf → ranked cases → disposition) during the
event, reusing ideas but not code. Keep the evaluation harness design.

## 12. Execution schedule

### Before the event (now → T-0)

| Order | Task | Backlog # |
|---|---|---|
| 1 | Confirm rules and dates (12.0) | — |
| 2 | Label stripping + structural roles + tests | 1 |
| 3 | Remove silent demo fallback; explicit offline state | 2 |
| 4 | Purity-weighted case ranking + tests; re-run evaluation | 3, 4 |
| 5 | Python 3.12 environment that installs cleanly (`uv` or Docker image) | 9 |
| 6 | Run AMLworld HI-Small through the harness (if allowed) | 8 |
| 7 | 3–5 analyst conversations (02 §2.6) | — |

### During a 36-hour event (adapt proportionally for 48 h)

| Hours | Work | Exit criterion |
|---|---|---|
| 0–2 | Rules check with mentors; freeze scope; branch `buildx` | Scope list signed off by team |
| 2–8 | Disposition vocabulary + mandatory reason; audit list in case view | T6 passes |
| 8–14 | Evaluation page (reads `evaluation_results.json`); hide non-core pages | Sidebar = Queue, Case, Evaluation |
| 14–18 | Case report export; money-path highlight | T10 draft passes |
| 18–22 | **Sleep in shifts.** One person runs the full flow 10 times and logs defects | Defect list |
| 22–28 | Fix defects only; no new features | T1–T10 green |
| 28–31 | Mentor feedback round; record backup video | Video saved locally and on a USB stick |
| 31–34 | Pitch rehearsals × 5 with a timer; Q&A drill on limitations | ≤ 5 min, every claim sourced |
| 34–36 | Buffer; final run on the presentation laptop | — |

Rule for the event: **after hour 22, only fixes.**

## 13. Demonstration script (≈ 3 minutes)

| Time | Say | Do |
|---|---|---|
| 0:00 | "Scam money leaves through rings of mule accounts. Banks see one alert per account, mostly false. Here is a day of synthetic UPI traffic: about 250 accounts, about 2,000 payments, 5 hidden mule rings plus 50 legitimate accounts designed to look suspicious." | Upload the demo CSV |
| 0:25 | "The rules baseline flags accounts one at a time. To reach 90 % of the mule accounts an analyst would review about 225 accounts, and on the harder dataset never gets there." | Evaluation page, rules column |
| 0:50 | "MuleCatch groups accounts into ring-level cases and ranks them by how much evidence each member carries. Five to seven cases cover 90 % of mules, with no genuine customer swept in on this data." | Evaluation page, case-queue column; point at "legitimate accounts exposed". **Only say this once backlog #3 (purity ranking) is merged and the harness re-run confirms it**; today's shipped ranking exposes a median of 150 legitimate accounts on the hardened data |
| 1:20 | "Open the top case." | Click case #1 |
| 1:30 | "One source, *[N]* payments under ₹50k in *[H]* hours, fanned to *[M]* accounts, consolidated into *[K]* collector(s). These are the reasons, and this is each member's evidence." Fill N/H/M/K from the actual top case of the seeded demo dataset; never quote numbers that are not on screen | Network, money path, timeline, reasons |
| 2:10 | "MuleCatch never blocks anyone. The investigator decides, gives a reason, and the decision is hash-chained." | Record `SUSPICION_CONFIRMED_ESCALATED` with a reason; show audit entry |
| 2:35 | "Export the case report for the bank's process, including the RBI natural-justice steps the bank must follow." | Export |
| 2:50 | "All data here is synthetic. What we would measure in a pilot is on the next slide." | Back to slides |

Fallback: if anything fails, switch to the recorded video at the same
timestamp. Never show fabricated data.

## 14. Pitch outline (≈ 5 minutes, 8 slides)

| # | Slide | Content | Evidence label |
|---|---|---|---|
| 1 | Problem | 4.5 lakh mule accounts frozen in a year; regulator built MuleHunter.AI because rules give high false positives | Sourced public data |
| 2 | Today's workflow | One alert per account; analyst rebuilds the ring by hand; genuine customers caught in freezes | Hypothesis from public sources; interviews pending |
| 3 | Mechanism | Payments → graph → temporal smurf signal + communities → **ring-level cases ranked by member evidence** → human decision → audit | Implemented |
| 4 | Live demo | Section 13 | Synthetic |
| 5 | Measured comparison | Table: rules vs graph/temporal vs MuleCatch; AP, FPR, reviews to 90 % recall, genuine accounts exposed; both scenarios | **Measured, synthetic, held-out seeds** |
| 6 | Customer and model | Users: fraud analysts. Buyers: Head of FRM at small finance / cooperative banks. Complements MuleHunter.AI. 8–12 week read-only pilot | Hypothesis |
| 7 | Responsible deployment | No auto-blocking; suspicion ≠ verdict; on-prem; no LLM; bias check plan; natural justice | Design |
| 8 | Limits and next steps | Synthetic and circular data; no human timing study yet; AMLworld run; pilot ask | Honest |

Q&A preparation (one-line answers): "Why not a GNN?" (we measured: no gain,
leakage found and removed) · "Is this better than MuleHunter?" (different unit:
cases, not account scores; complementary) · "Real data?" (CSV path tested on a
2,000-row sample, but it has no labels, so no accuracy claim) · "Real time?"
(`POST /api/v1/score` scores one payment in about 35 ms on the demo graph, about 200 ms at a 2,000-payment window; measured on synthetic data, see
`docs/buildx/payment_eval_results.json` once the held-out run is merged. Louvain reruns per payment today; incremental updates are the known next step).

## 15. Go / no-go recommendation

| Criterion (from the brief) | Evidence | Met? |
|---|---|---|
| Existing project can become a reliable demo of the core workflow | Workflow API exists and is tested (417 tests pass); UI unverified; fixes are small and known | **Yes, conditional** on backlog 1–4 |
| Credible improvement over a simple baseline | On held-out synthetic data with labels stripped, graph/temporal methods clearly beat the rules baseline; case queue cuts reviews to 90 % recall from ~225 to 5–7 | **Yes on synthetic data**; independent data pending |
| Does the graph approach improve results? | Yes vs rules. The *full* 7-layer pipeline scores **below** the simple graph+temporal combination (hardened AP 0.867 vs 0.929) and is about 15× slower | Simplify: keep graph + temporal, drop the rest from the decision path |
| Customer problem validated? | Public and regulator evidence of the problem; **no user interviews** | **Not validated**; say so |
| Data supports performance claims? | Only synthetic, generated by the same team that wrote the detectors | Claims must be labelled synthetic; no real-world accuracy or savings claims |

### Recommendation: **GO, with a simplified scope and honest framing**

Continue with MuleCatch. Cut it down to the ring-level case workflow, fix the
leakage and the fake-data fallback, and present measured synthetic results
next to their limitations. Escalate to "NO-GO" only if (a) the organisers
forbid pre-existing code *and* the team cannot rebuild the MVP slice in the
event window, or (b) the AMLworld run shows no advantage for the case queue
over the account queue.

**Next action:** send the rules/dates email today; then backlog items 1–4.


## 13b. Opening: the first 30 seconds

Judges form a view in about 30 seconds. Start with the demo, not slides, and introduce the team afterwards.

| Time | Say | Do |
|---|---|---|
| 0:00 | (silence for a moment, stream already running on `/live`) | Press **Start stream** at 5 payments/s. Payments appear as dots |
| 0:08 | "Every dot is a payment being scored as it arrives." | Point at the p95 latency tile |
| 0:15 | "That cluster just turned red: a ring of mule accounts. One case, not forty alerts." | Case card opens on the right |
| 0:22 | "And this counter is genuine customers flagged: zero. Synthetic data." | Point at **Genuine accounts flagged** |
| 0:30 | "I'm *[name]*, this is *[team]*. We built MuleCatch." | Team intro, then slides |

Wording rules (from `00-CONTEXT.md`): say "flags" and "routes to a human reviewer", never "blocks", "stops" or "recovers". Say "synthetic data" next to every result. Never claim a bank partnership, "83 % accuracy" or "production-ready".

## 13c. Backup plan

| Risk | Mitigation |
|---|---|
| Live stream fails | Switch to the recorded video at the same timestamp. Never show fabricated data |
| Backend will not start on the venue laptop | Run the pre-built stack from a second laptop; keep the recording on a USB stick |
| Venue network blocks the API | Everything runs on localhost; no internet needed except slides |
| Stream finishes mid-pitch | Press **Replay**; the seeded replay is deterministic |
| Wrong numbers on screen | Quote only what the screen shows; the held-out results table is on slide 5 |

### Recording checklist

- [ ] Record the 30-second opener and the full 3-minute demo at 1080p, with audible narration
- [ ] Save on the laptop, on a USB stick, and on a phone
- [ ] Re-record after any change that alters the screen
- [ ] Run the stream 10 times in a row and note every defect before the recording
