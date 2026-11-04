# Spec: eval-heldout (branch `eval-heldout`)

Goal: honest numbers for the per-payment scorer.

- Extend `scripts/evaluation/` with a per-payment run: calibration seeds 0-4, test seeds 100-119, labels stripped before scoring (hardened scenario too).
- Report payment-level recall of mule payments, genuine-payment flag rate, p50/p95 latency, and ring cases opened vs account reviews.
- Check `ENDPOINT_EVIDENCE_MIN = 0.30` on calibration seeds only, then apply unchanged to test seeds.
- Add results table to `docs/buildx/05-evaluation.md`. Always say "synthetic data" and note circularity.
