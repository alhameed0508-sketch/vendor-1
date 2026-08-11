# Model benchmark programs

The **Model Benchmarks** page at `/benchmarks` is backed by executable API
programs. It is not a static dashboard.

## Programs

| UI action | API | What runs |
|---|---|---|
| Synthetic | `POST /api/v1/benchmark/synthetic` | Generates labelled mule clusters and legitimate peer accounts, runs the complete detection pipeline, and calculates account-level metrics. |
| Adversarial | `POST /api/v1/benchmark/adversarial` | Adds difficult legitimate edge cases and evasive mule patterns, uses a deterministic stratified holdout, and reports holdout metrics. |
| Cross-Validation | `POST /api/v1/benchmark/cross-validation` | Runs deterministic stratified account folds using an isolated pipeline for every fold and reports per-fold mean and standard deviation. |
| Comparison | `POST /api/v1/benchmark/comparison` | Evaluates multiple cluster/network sizes and returns a side-by-side result set. |
| Full Evaluation | `POST /api/v1/benchmark/full-evaluation` | Runs standard, adversarial, and five-fold evaluation and returns one combined report. |

`GET /api/v1/benchmark/capabilities` reports whether execution is enabled.
`GET /api/v1/benchmark/results` returns the last 50 normalized run records.

## Metrics

Each applicable program reports:

- precision;
- recall;
- F1 score;
- accuracy;
- AUC-ROC when both ground-truth classes are present;
- TP, FP, TN, and FN;
- evaluated account and transaction counts;
- elapsed execution time.

The holdout and fold implementations only retain transactions whose sender and
recipient both belong to the evaluated account partition. This prevents
counterparties outside the partition from leaking into a fold.

## Operational controls

- Only `ADMIN` and `SUPERVISOR` roles can execute benchmarks.
- Investigators and auditors may read capabilities and saved results.
- Parameters have bounded Pydantic validation.
- Expensive actions have stricter rate limits.
- A worker rejects overlapping benchmark execution.
- Every evaluation uses an isolated detection pipeline.
- Result history is written with atomic file replacement.
- Synthetic execution is rejected when `ENV=production`.

Production validation must run offline against a governed, representative,
time-split bank dataset and an approved immutable model artifact. Synthetic
scores demonstrate pipeline behaviour and regression safety; they do not
establish production sensitivity, specificity, fairness, or regulatory fitness.

