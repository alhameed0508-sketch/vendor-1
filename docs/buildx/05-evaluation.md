# 7. Dataset and evaluation plan, with measured results (Phase E)

All numbers in this file were **measured on 2026-10-12** by the scripts in
`scripts/evaluation/`. Raw output: [evaluation_results.json](evaluation_results.json),
[robustness_scale_results.json](robustness_scale_results.json). They are
**synthetic-data results** and say nothing yet about real bank traffic.

## 7.1 Dataset

| Property | Value |
|---|---|
| Generator | `data/synthetic/generator.py::build_adversarial_dataset` (project's own) |
| Per dataset | 5 mule rings (source → mules → aggregators), 150 legitimate accounts, 50 "adversarial" legitimate accounts built to look suspicious |
| Size (mean of 20 test datasets) | 254 accounts, 61 mule accounts (prevalence 24 %), ≈ 2,096 transactions |
| Calibration (threshold selection) | seeds 0–4 |
| Test (all reported metrics) | seeds 100–119, never used for tuning |
| Labels | account is positive if its generator role is SOURCE, MULE or AGGREGATOR |
| Leakage control | `role`, `high_risk`, `cluster_id`, `is_suspicious`, `pattern` removed before any detector runs |

### Scenarios

| Scenario | What changes | Why |
|---|---|---|
| **standard** | Generator output as is | Matches how the project has been benchmarked |
| **hardened** | Account age, KYC status and monthly activity resampled from **one shared distribution** for all accounts | In the generator, mules are 1–45 days old and legitimate accounts 180–3650 days old. Any age rule separates them perfectly. Hardening forces detectors to use behaviour and network structure |

### Known limitations (read before quoting any number)

1. **Circularity.** The same team wrote the generator and the detectors.
   Smurf scoring and Louvain grouping were designed for exactly the ring shape
   the generator produces. High scores here are an upper bound.
2. Prevalence (24 %) is far higher than in real banking (well under 1 %).
   Precision would be much lower at real prevalence.
3. Legitimate traffic is random pairs with uniform amounts; real legitimate
   behaviour (salaries, merchants, family transfers) is richer and harder.
4. No label noise; real labels are incomplete (undetected mules look "legitimate").
5. Small runs (20 test datasets) and minor non-determinism (generator uses
   `uuid4` and wall-clock time): repeated runs moved AP by ≤ 0.003.

## 7.2 Methods compared

| ID | Method | Account score |
|---|---|---|
| A0 | Account-age heuristic (diagnostic) | 1 − age/3650 |
| **A** | **Rules baseline** | number of R01–R20 rules hit |
| **B** | **Graph + temporal** | max(smurf score, Louvain community suspicion) |
| **C** | **MuleCatch full pipeline (as shipped)** | max risk score of any alert containing the account |

Thresholds were chosen on calibration seeds by maximum F1, then applied
unchanged to the test seeds.

## 7.3 Detection results (test seeds, pooled over 20 datasets)

**Standard scenario**

| Method | PR-AUC (AP) | Precision | Recall | FPR | False positives | Median latency / dataset |
|---|---|---|---|---|---|---|
| A0 age heuristic | 0.880 | 0.859 | 1.000 | 0.052 | 200 | < 1 ms |
| A rules | 0.233 | 0.240 | 1.000 | 1.000 | 3,860 | 0.63 s |
| B graph + temporal | **1.000** | 0.999 | 0.993 | 0.000 | 1 | **0.07 s** |
| C full pipeline | 0.963 | 0.809 | 0.941 | 0.070 | 271 | 1.02 s |

**Hardened scenario** (static attributes uninformative)

| Method | PR-AUC (AP) | Precision | Recall | FPR | False positives | Median latency / dataset |
|---|---|---|---|---|---|---|
| A0 age heuristic | 0.230 | 0.239 | 0.988 | 0.995 | 3,841 | < 1 ms |
| A rules | 0.182 | 0.240 | 1.000 | 1.000 | 3,860 | 0.62 s |
| B graph + temporal | **0.929** | 0.869 | 0.874 | **0.042** | 161 | **0.07 s** |
| C full pipeline | 0.867 | 0.754 | 0.811 | 0.084 | 323 | 1.02 s |

**As-shipped alerting** (every account in any alert counts as flagged):
precision 0.31, recall 1.00, **FPR 0.69** (standard) / 0.71 (hardened). In
the example dataset inspected (seed 100, hardened), one alert contained **89
legitimate accounts and no mules**. A large community of ordinary traffic was
flagged as a "mule cluster".

Prevalence is 0.24, so an AP of about 0.23 means *no better than random*.

### What this shows

| Finding | Evidence |
|---|---|
| The synthetic data has a shortcut | Account age alone gives AP 0.88 on standard data and collapses to 0.23 when ages are equalised |
| The 20 rules do not discriminate on this data | AP equals prevalence. Several rules fire more on legitimate accounts (seed 100: R11 91 % legit vs 8 % mule; R07 64 % vs 0 %; R16 58 % vs 0 %; R19 44 % vs 2 %). Only R01 (new account) and R18 (shared device) favour mules |
| Graph + temporal signals carry the value | B is the best method in both scenarios |
| The extra layers subtract value | C is below B on AP (0.867 vs 0.929 hardened), has twice the FPR, and is about 15× slower. Simplify |
| GNN | Not evaluated: torch is not installed, so the pipeline used the lightweight heuristic fallback. A label-leaking feature was found in the GNN (`high_risk`), so earlier GNN results should not be trusted |

## 7.4 Investigator workload (the primary-differentiator metric)

Question: *how many review units must an analyst open to reach 90 % of the
mule accounts, and how many genuine customers are pulled in along the way?*
An account queue opens one account per unit; a case queue opens one alert
(community) per unit. Median over the 20 test datasets.

| Queue | Standard: units opened | Standard: genuine accounts exposed | Hardened: units opened | Hardened: genuine accounts exposed | Hardened: datasets reaching 90 % |
|---|---|---|---|---|---|
| A rules, per account | 230.5 | 175.5 | 225 | 190 | **0 / 20** |
| B graph + temporal, per account | 55 | 0 | 117.5 | 62.5 | 20 / 20 |
| C case queue, as shipped (risk-ranked) | **5** | 0 | 7 | **150** | 19 / 20 |
| C case queue, **purity-weighted** | **5** | **0** | **5** | **0** | 19 / 20 |

Purity weighting = alert risk × mean smurf score of its members. It uses no
labels and no size threshold. It is implemented in the harness only; the
product change is backlog #3.

Interpretation: grouping into ring-level cases cuts review units by about
**45×** against the rules account queue on this data. Purity weighting removes
the genuine-customer exposure that the shipped ranking causes on hardened
data. *A review unit is not equal effort.* A case takes longer than a single
account, which is why the timed study in 7.7 is needed before claiming
time saved.

## 7.5 Latency and throughput (single process, audit laptop)

| Accounts | Transactions | Pipeline time | Throughput |
|---|---|---|---|
| 254 | 2,085 | 1.3 s | 1,605 txn/s |
| 605 | 4,661 | 7.6 s | 617 txn/s |
| 1,407 | 10,170 | 98.7 s | 103 txn/s |
| ≈ 3,000 | ≈ 20,000 | stopped after > 8 min | — |

Time grows much faster than linearly, because each rule scans the full
transaction list for every account. The pipeline's own docstring target
("< 60 s for 10k transactions") is **not met**. The B method alone is about
15× faster at the 2k size. Fix: index transactions by account once (backlog
#5) and evaluate in sliding windows for "real-time" micro-batches.

## 7.6 Reliability on malformed input (pipeline called directly)

| Input defect | Result |
|---|---|
| Empty batch / no account master | Handled |
| Self-transfer, unknown counterparty, duplicate txn IDs | Handled (duplicates **silently double-counted**) |
| Negative amount | Handled (**silently accepted**) |
| Non-numeric amount | **Crash** (`ValueError`) |
| Missing amount / timestamp / to_account | **Crash** (`KeyError`) |
| Unparseable timestamp | **Crash** (`ValueError`) |

The CSV upload adapter validates files before they reach this point, and its
tests pass. These crashes matter for any other ingestion path (API
micro-batch, Kafka). Acceptance criterion T3 requires row-level rejection
with reasons.

## 7.6b Per-payment real-time scorer

Script: `scripts/evaluation/evaluate_payments.py`. Raw output: `payment_eval_results.json`.

**Method.** Every 25th payment of a dataset is replayed live through `RealtimeScorer`; the rest is trusted history. Ground-truth labels are removed before scoring and used only to count outcomes. The endpoint-evidence gate was chosen on calibration seeds 0-2 (highest mule recall with genuine flag rate at most 1%, ties to the higher gate) and applied unchanged to test seeds 100-119.

| Scenario | Gate | Mule payments flagged | Genuine payments flagged | Mule accounts inside a flagged ring | Genuine accounts in flagged rings (median) | Latency p50 / p95 |
|---|---|---|---|---|---|---|
| Standard (20 datasets) | 0.30 | 96.7% | 0.0% | 88.7% | 0 | 165 ms / 264 ms |
| Hardened (20 datasets) | 0.30 | 95.9% | 0.0% | 88.0% | 0 | 194 ms / 370 ms |

**Caveats.**
- Synthetic data only, generated by the same code family the detector was developed against. This is the circularity described above, so treat the numbers as a regression check, not as expected real-world accuracy.
- Prevalence of mule accounts is about 24%, far above real rates, so precision-like figures flatter the scorer.
- Calibration is saturated: gates 0.25 and 0.30 both reach recall 1.0 with zero genuine flags (0.35 drops to 0.81). The gate choice is therefore weakly identified.
- A genuine flag rate of 0.0% means none in this sample, not a guarantee. With a small number of genuine payments per dataset the upper bound is wider than the point estimate suggests.
- Latency is per payment on a development machine with a window of about 5k payments, scoring the whole window each time. The hardened p95 of 370 ms exceeds a typical 100 ms payment budget. Incremental community updates are the planned fix.

## 7.7 Still to measure (not yet run)

| Measurement | Plan | Why |
|---|---|---|
| Independent dataset | IBM AMLworld HI-Small (Kaggle; Altman et al., NeurIPS 2023): map accounts and transfers, run the same harness with a **time split** (train/calibrate on earlier days, test on later) | Breaks the generator/detector circularity |
| Investigation time | 4–6 volunteers, 10 cases each, account view vs case view, randomised order; time to decision and agreement with ground truth | Converts "review units" into minutes |
| Evidence traceability | For each top case, check every reason code links to specific transactions in the evidence table | Audit requirement |
| Per-segment false positives | On real or AMLworld data: FPR by account age band and KYC type | Fairness |
| Real-time path | Per-payment latency measured in 7.6b (p95 264-370 ms). Still to measure: micro-batch latency at 100 / 1,000 txn and load under concurrent callers | Challenge says real time |

**Decision:** Graph + temporal signals give a measurable improvement over the
rules baseline on synthetic data. Ring-level, purity-weighted cases are the
strongest measured result. The full 7-layer stack is not justified by the
measurements. **Next action:** implement backlog #3 and #5, then run AMLworld.
