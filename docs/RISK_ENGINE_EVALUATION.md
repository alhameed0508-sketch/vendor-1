# Unified risk engine: evaluation

> **Synthetic data only.** Every number below comes from the MuleCatch journey simulator (`backend/intelligence/simulator.py`), not from bank data. Generated 2026-11-04T12:21:11+00:00 by `scripts/evaluation/evaluate_unified.py`; raw output in `docs/evaluation/risk_engine_evaluation.json`.

## Protocol

- Warm-up days 0-44: history only (profiles, ring map); nothing scored.
- Calibration days 45-51: scored with the prior model; these rows train the logistic model (seed 101 only).
- Test days 52-59: every metric below. Seeds [101, 202, 303] (400 customers, 4 mule rings each); seeds other than 101 are populations the model never saw.
- Customer payments = genuine payments plus customer-initiated fraud (APP scams and account takeovers, including quiet variants and brand-new mule payees). Mule movements (payments into and between mule accounts) are reported separately because the mule core already sees those rings.

## Targets (design targets, not results)

| Target | Value | Result on synthetic test days (hand-set prior model, mean of seeds) | Met? |
|---|---|---|---|
| Genuine payments interrupted (step-up + review) | <= 0.5% | 0.20% | yes (synthetic) |
| Precision of the REVIEW band | >= 90.0% | 100.00% | yes (synthetic) |
| Fraud payments interrupted (recall) | >= 95.0% | 97.35% | yes (synthetic) |
| Decision latency p95 (ms) | <= 200 ms | 0.24 ms (worst seed) | yes (synthetic) |

Meeting a target on simulated data says the logic works as designed; it is not evidence about real traffic. The simulator was written by the same team as the engine.

## Customer payments: unified engine vs baselines (hand-set prior model, mean over seeds, [min-max])

| System | Fraud interrupted | Fraud held (REVIEW) | Genuine interrupted | Genuine held | REVIEW precision | PR-AUC | Fraud ₹ interrupted |
|---|---|---|---|---|---|---|---|
| Static rules (amount + new payee/device/city + night) | 94.55% [91.07%-100.00%] | 33.72% [30.86%-36.36%] | 0.26% [0.21%-0.32%] | 0.09% [0.04%-0.15%] | 84.89% [73.08%-92.31%] | 0.798 [0.691-0.881] | 93.73% [89.82%-100.00%] |
| Mule core alone (existing ring map and endpoint evidence) | 74.28% [53.03%-87.65%] | 74.28% [53.03%-87.65%] | 0.34% [0.28%-0.41%] | 0.34% [0.28%-0.41%] | 74.92% [64.81%-84.52%] | 0.746 [0.537-0.879] | 76.39% [56.02%-88.66%] |
| Unified score, false-positive controls switched off | 97.35% [93.83%-100.00%] | 94.92% [91.36%-96.97%] | 0.20% [0.13%-0.32%] | 0.14% [0.09%-0.21%] | 90.67% [84.38%-94.87%] | 0.991 [0.986-0.996] | 98.13% [96.05%-100.00%] |
| Unified engine (this work) | 97.35% [93.83%-100.00%] | 85.98% [83.93%-87.65%] | 0.20% [0.13%-0.32%] | 0.00% [0.00%-0.00%] | 100.00% [100.00%-100.00%] | 0.984 [0.973-0.990] | 98.13% [96.05%-100.00%] |

## All payments, including mule movements (mean over seeds)

| System | Fraud interrupted | Genuine interrupted | REVIEW precision | PR-AUC |
|---|---|---|---|---|
| Static rules (amount + new payee/device/city + night) | 9.55% | 0.26% | 84.89% | 0.241 |
| Mule core alone (existing ring map and endpoint evidence) | 81.14% | 0.34% | 97.93% | 0.844 |
| Unified score, false-positive controls switched off | 82.83% | 0.20% | 98.88% | 0.985 |
| Unified engine (this work) | 82.83% | 0.20% | 100.00% | 0.988 |

## Where each fraud journey type ends up (unified, seed 101)

| Payment type | APPROVE | STEP_UP | REVIEW |
|---|---|---|---|
| app_scam | 0 | 0 | 18 |
| app_scam_fresh_mule | 3 | 3 | 0 |
| app_scam_quiet | 0 | 0 | 8 |
| ato | 0 | 0 | 30 |
| ato_own_device | 0 | 0 | 14 |
| ato_quiet | 2 | 2 | 1 |
| everyday | 4513 | 0 | 0 |
| mule_forward | 5 | 2 | 442 |
| mule_inbound | 5 | 0 | 501 |
| trap_big_known_payee | 15 | 0 | 0 |
| trap_festival | 64 | 0 | 0 |
| trap_new_payee_large | 4 | 6 | 0 |
| trap_new_phone | 16 | 0 | 0 |
| trap_night | 10 | 0 | 0 |
| trap_password_reset | 10 | 0 | 0 |
| trap_travel | 15 | 0 | 0 |

## Time to detection (customer-initiated fraud journeys, unified, seed 101)

- Journeys: 52; held on the first payment: 80.77%; interrupted on the first payment: 90.38%; never held: 19.23%; median payments before the hold: 0.0.

## Mule rings (the core)

| Seed | Rings at test start | Mule accounts in rings | Non-mule accounts in rings |
|---|---|---|---|
| 101 | 1 | 6 of 38 | 0 |
| 202 | 4 | 24 of 39 | 0 |
| 303 | 2 | 12 of 38 | 0 |

## Who carries the false positives (genuine interruption rate, unified, seed 101)

| Segment | Genuine payments | Interrupted |
|---|---|---|
| confidence: full (>=0.7) | 4653 | 0.13% |
| amount_inr: 10k-50k | 28 | 10.71% |
| amount_inr: 1k-10k | 2742 | 0.00% |
| amount_inr: <1k | 1877 | 0.00% |
| amount_inr: >=50k | 6 | 50.00% |

## Speed (measured on this machine, single process)

| Seed | Decision p50 | p95 | p99 | Assess incl. commit + synchronous ring refresh p95 | max | Ring-map refresh |
|---|---|---|---|---|---|---|
| 101 | 0.153 ms | 0.239 ms | 0.304 ms | 0.352 ms | 629.6 ms | 387.6 ms |
| 202 | 0.156 ms | 0.233 ms | 0.297 ms | 0.346 ms | 626.5 ms | 315.1 ms |
| 303 | 0.145 ms | 0.232 ms | 0.297 ms | 0.349 ms | 610.0 ms | 403.7 ms |

In the API the ring map is rebuilt on a background thread, so the refresh is off the payment path; the evaluation runs it synchronously every 25 payments to stay deterministic.

## Drift and calibration

| Seed | PSI genuine score (calibration vs test) | PSI all | Brier (customer payments) |
|---|---|---|---|
| 101 | 0.003 | 0.102 | 0.00152 |
| 202 | 0.003 | 0.001 | 0.00189 |
| 303 | 0.002 | 0.023 | 0.00104 |

PSI below 0.1 is usually read as stable, 0.1-0.25 as moderate shift, above 0.25 as a shift to investigate.

## Prior vs fitted model

Gate: fitted must not raise genuine interruptions by more than 0.05 pp, nor lower recall or REVIEW precision by more than 1 pp (means over the test windows of all seeds). Result: **prior model kept**.

| Model | Genuine interrupted | Fraud interrupted | REVIEW precision | PR-AUC |
|---|---|---|---|---|
| Prior (hand-set) | 0.20% | 97.35% | 100.00% | 0.984 |
| Fitted (lr-synthetic-s101-20261104) | 0.28% | 94.92% | 100.00% | 0.963 |

## What this does not show

- Real-world precision. At a 0.1 % fraud rate, even 0.5 % of genuine payments interrupted means most interruptions are genuine (docs/SYSTEM_DESIGN.md section 6). The simulator's fraud rate is far higher.
- Adversaries who adapt. The simulated fraudsters follow fixed scripts.
- Session and device signals on real devices: the simulator invents sessions; the live Bitcoin feed has none.
- The brand-new mule payee (`app_scam_fresh_mule`) and the quiet takeover paying a fresh account have no evidence to find at payment time; the engine asks for a step-up at most, by design.
