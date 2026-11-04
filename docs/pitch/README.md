# BuildX 2026 pitch deck

`BuildX_MuleCatch_pitch.pptx`: 9 live slides (about 4.5 minutes, with a 30-second live opener) and 3 appendix slides.
Free-form, dark, projector-safe deck. Speaker notes with timings are on every slide.

## Rebuild

```
pip install python-pptx matplotlib
python docs/pitch/make_figures.py   # charts, read from docs/buildx/*.json
python docs/pitch/build_deck.py     # writes BuildX_MuleCatch_pitch.pptx
```

`deck_lib.py` holds the palette and shape helpers. Every number on a slide is read from a result file in `docs/buildx/`.

## Before the event

| Item | Where |
|---|---|
| Team name, member names, contact, repository link | Slides 1 and 9 (placeholders in square brackets) |
| Dates are unconfirmed on the organiser page (4-5 Nov or 13-14 Oct 2026) | Ask the organisers |
| Judging criteria are not published | The chips on each slide use the common convention (problem 20, innovation 25, feasibility 20, impact 20, presentation 15) |
| Record a 90-second backup video of the `/live` flow | Slide 4 notes |

## Claims that are targets or open

- The per-payment p95 (169 ms on the latest re-run) is above a 100 ms payment budget. Incremental ring updates are not built on this branch.
- The case-queue figure (5 vs 225 reviews) is from the evaluation harness. The ranking rule (`rank_score`) is in the product.
- Independent data (IBM AMLworld) shows the detector does not transfer. This is on slide 8 and in the appendix.
- The analyst persona is a hypothesis. No analyst interviews exist yet.
