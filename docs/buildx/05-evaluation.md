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

## 7.6c Evasion playbooks (mules adapt)

Script: `scripts/evaluation/evaluate_evasion.py` (playbooks in `evasion_playbooks.py`). Raw output: `evasion_results.json`. Gate fixed at 0.30, nothing re-tuned. Test seeds 100-104, scorer before the community-refresh change.

| Playbook | What the mules do | Mule payments flagged | Genuine payments flagged | Mule accounts in flagged rings |
|---|---|---|---|---|
| Baseline | Nothing | 98.9% | 0.0% | 89.5% |
| Split | Each payment becomes 3 smaller ones, 7 min apart | 100% | 0.0% | 100% |
| Noise | Each mule exchanges 4 small decoy payments with random genuine accounts | **5.8%** | 0.5% | 13.8% |
| Slow drip | Gaps between mule payments stretched 6x | **35.4%** | 0.0% | 45.6% |

Standard and hardened scenarios give identical numbers. That is expected: the hardened scenario only equalises static account attributes, which the real-time scorer does not use.

**Finding.** The scorer is robust to splitting but **fails against decoy noise** and is badly weakened by slowing down. Decoys connect mules to genuine accounts, so Louvain merges rings into larger mixed communities that fail the ring-purity gate. Slowing down pushes payments outside the 60-minute velocity and 6-hour consolidation windows. Both are cheap for a real mule operator. Fixing them (for example decoy-robust ring extraction such as dense-subgraph peeling, and multi-scale time windows) is the top detection priority, ahead of new features.

## 7.6d After the robustness fixes

Same scripts, gate still 0.30, nothing re-tuned. Scorer at commit `2d7a923`, which adds:

- **Materiality filter.** A payment enters the graph and the evidence only if its sender-receiver pair totals at least ₹400 in the window. One-off small decoys drop out, but structuring (many payments just under ₹400 between the same pair) still counts.
- **Multi-scale evidence.** Smurf evidence is also computed with 6-hour velocity and 36-hour consolidation windows, keeping the higher score per account.
- **Merchant exemption and a refreshed community cache** (section 7.6b method otherwise unchanged).

Raw output: `evasion_results_v2.json`, `payment_eval_results_v2.json`.

**Evasion (test seeds 100-104).** Standard and hardened give the same recall; latency differs slightly.

| Playbook | Mule payments flagged, before → after | Genuine payments flagged, after | Mule accounts in flagged rings, after |
|---|---|---|---|
| Baseline | 98.9% → 100% | 0.0% | 92.1% |
| Split | 100% → 100% | 0.0% | 100% |
| Noise | **5.8% → 100%** | 0.0% | 100% |
| Slow drip | **35.4% → 92.9%** | 0.0% | 94.1% |

**Per-payment test (seeds 100-119).**

| Scenario | Mule payments flagged | Genuine payments flagged | Mule accounts in flagged rings | Latency p50 / p95 |
|---|---|---|---|---|
| Standard | 98.8% (was 96.7%) | 0.0% | 90.0% | 154 ms / 265 ms |
| Hardened | 97.5% (was 95.9%) | 0.0% | 88.7% | 148 ms / 219 ms |

**Caveats.**
- All of section 7.6b's caveats still apply: synthetic data from the same code family, high prevalence, and "0.0%" means none in this sample.
- The playbooks were written by the same team that wrote the fixes. A fix that passes its own attack is weak evidence; an independent red team or dataset is needed.
- **Known limit: bystander dilution.** A probe on one dataset (seed 7, not part of the harness) sent material decoys (≥ ₹400 per pair) from every mule to genuine accounts. With 2 bystanders per mule, recall stayed at 100%. With 4 per mule, it fell to 76-79%, whether the money went as one payment or several small ones. Bystanders join the ring and push it under the 30% purity gate. The operator pays real money for each bystander, but this is the current weak point.
- p95 latency is still above a typical 100 ms payment budget.

## 7.6e Gap fixes: ring-internal evidence, faster scoring, ranked queue

Gate still 0.30, nothing re-tuned. Raw output: `evasion_results_v3.json`, `payment_eval_results_v3.json`.

**What changed.**
- **Ring-internal evidence.** Once a ring is found, its members are also scored on payments between ring members only, at three scales (default, 6 h / 36 h, and 6 h velocity with a 6-day consolidation wait). Decoys sent to outsiders no longer dilute a member's evidence. A velocity window of 12 h or more was tried and rejected: it made genuine communities look like bursts (48 of 97 genuine payments flagged in the small test set).
- **Faster scoring.** The per-account velocity score was quadratic (about 80% of smurf time); it is now O(k log k) with identical results. One first-time account paying into a known ring no longer forces a full Louvain run.
- **Ranked queue.** Batch alerts carry `rank_score` (risk x mean member smurf score) and `evidence_share` (share of members with their own evidence). The pipeline, the demo status assignment and the Triage page rank by it (backlog #3). Severity is unchanged. On the demo data every top alert still has raw risk 0.99; the rank spreads them from 0.39 down to 0.11, and the 60-account ring with 2% evidence share is last.

**Evasion (test seeds 100-104, standard).** Two new playbooks were added: `dilute` (each mule pays 4 distinct genuine bystanders a material amount) and `slower` (gaps stretched 24x), plus `combo` (split, noise and slow drip together).

| Playbook | Mule payments flagged, before → after | Genuine payments flagged, after | Mule accounts in flagged rings, after |
|---|---|---|---|
| Baseline | 100% → 100% | 0.0% | 92.1% |
| Split | 100% → 100% | 0.0% | 100% |
| Noise | 100% → 100% | 0.0% | 100% |
| Slow drip (6x) | 92.9% → 94.9% | 0.0% | 97.4% |
| **Dilute** | **0.0% → 68.4%** | **2.0%** | 69.5% |
| **Slower (24x)** | **19% → 62.1%** | 0.0% | 63.9% |
| Combo | 99% → 99.3% | 0.0% | 100% |

**Per-payment test (seeds 100-119, stride 25).**

| Scenario | Mule payments flagged | Genuine payments flagged | Mule accounts in flagged rings | Latency p50 / p95 |
|---|---|---|---|---|
| Standard | 99.2% (was 98.8%) | 0.0% | 90.7% | 68 ms / 197 ms (was 154 / 265) |
| Hardened | 98.0% (was 97.5%) | 0.0% | 89.3% | 75 ms / 204 ms (was 148 / 219) |

**Caveats.**
- `dilute` is only partly fixed and has a cost: the rings are found, but bystanders sit inside them. Genuine payments flagged rose to 2.0% (over the 1% budget) and a median 45 genuine accounts were inside flagged rings on that playbook. A case view should show which members carry their own evidence (`evidence_share`).
- `slower` at 24x is still missed in about 38% of payments. A longer velocity window fixes it but flags genuine communities. Treat slowing a whole ring operation by a day-scale factor as an open limit.
- Latency was measured with two evaluations and a dev server sharing the machine; p95 is still the 1-in-10 Louvain refresh payment. A background refresh would bring it near 70 ms (not built).
- The playbooks are still written by the team that wrote the fixes (see 7.6d caveats).

## 7.6f Rule discrimination and the rules removed

`scripts/evaluation/evaluate_rules.py` measures the share of mule and of genuine accounts each rule fires on (20 test seeds, pooled; output in `rule_discrimination.json` and `rule_discrimination_hardened.json`, measured on the full 20-rule set before removal). A rule is kept only if it fires on at least 10 % of mules and at least 3 times as often as on genuine accounts.

| Rule | Mule | Genuine | Outcome |
|---|---|---|---|
| R01 account age | 0.84 | 0.05 | keep (0.00 / 0.00 once ages are equalised: this is the data shortcut from 7.3) |
| R18 shared device | 0.55 | 0.02 | keep |
| R11 cross-bank layering | 0.08 | 0.90 | **removed** |
| R07 fan-in then consolidation | 0.00 | 0.66 | **removed** |
| R10 beneficiary spike | 0.08 | 0.65 | **removed** |
| R16 intermediary only | 0.00 | 0.59 | **removed** |
| R19 rapid fund sweep | 0.01 | 0.42 | **removed** |
| R08 night-time high value | 0.03 | 0.15 | **removed** |
| R09 round trip | 0.00 | 0.13 | **removed** |
| R02, R03, R04, R06, R14, R17, R20 | 0.00-0.06 | 0.00-0.06 | kept for now: rare, near-equal rates, little noise |
| R05, R12, R13, R15 | 0.00 | 0.00 | kept, **untested**: the synthetic data never triggers them |

Rules only add reason codes to a case; they do not change the risk score, so benchmark numbers are unchanged. The removed rules were the ones adding misleading reason codes to most genuine accounts. The rule version is now `rules-2026.2`.

Caveats:

- Synthetic data. The genuine class includes deliberate hard cases (payroll fan-in), so fan-in rules fire there by design. A bank should re-run this script on its own labelled history before trusting any rule, including the two kept.
- Rare rules are not proven useful, only not harmful here. Externalising thresholds (the hardcoded-values audit) should now cover only the surviving rules.

## 7.7 Still to measure (not yet run)

| Measurement | Plan | Why |
|---|---|---|
| Independent dataset, time split | Run done without a time split: see 7.8. Still to do: calibrate on earlier days, test on later | Breaks the generator/detector circularity |
| Investigation time | 4–6 volunteers, 10 cases each, account view vs case view, randomised order; time to decision and agreement with ground truth | Converts "review units" into minutes |
| Evidence traceability | For each top case, check every reason code links to specific transactions in the evidence table | Audit requirement |
| Per-segment false positives | On real or AMLworld data: FPR by account age band and KYC type | Fairness |
| Real-time path | Per-payment latency measured in 7.6b (p95 264-370 ms). Still to measure: micro-batch latency at 100 / 1,000 txn and load under concurrent callers | Challenge says real time |

## 7.8 Independent dataset: IBM AMLworld (HI-Small)

Script: `scripts/evaluation/evaluate_ibm_aml.py`; adapter: `data/adapters/ibm_aml_adapter.py`; raw output: `ibm_aml_results.json`. Data: a public third-party mirror of the IBM HI-Small files (5.08M payments, 5,177 laundering payments in 370 attempts of 8 typologies), downloaded to `data/external/ibm-aml/` and never committed. Amounts converted to rupees with fixed approximate rates. The gate is the same 0.30, nothing tuned on this data.

Each of 20 cases holds 4 random laundering attempts, each mule's other payments (up to 30) and 60 ordinary accounts (up to 30 payments each), about 2,000 payments, replayed one at a time.

| Measure | Result |
|---|---|
| Laundering payments flagged | **0.0%** (0 of 136 replayed; every one of the 8 typologies is 0) |
| Genuine payments flagged | 0.04% |
| Laundering accounts in flagged rings | 0.1% |
| Account evidence AUC (multi-scale smurf score, mule vs not) | 0.68 |
| Latency p50 / p95 | 49 ms / 110 ms |

**Finding.** The detector does not transfer. Evidence scores of laundering accounts are barely above ordinary ones (AUC 0.68, with no laundering account reaching 0.30 in the probe case), and the graph communities score low (suspicion about 0.3). The features were built for fast, structured, below-ceiling smurfing; AMLworld laundering is cycles, stacks and scatter-gather over days, hidden in normal activity. The system is quiet on this data (almost no false flags) but finds nothing.

**Caveats.** The case construction (neighbourhood samples, rupee conversion, no time split, one 475 MB file) is mine and not a published benchmark protocol; it is not a leaderboard number. The result says our current evidence does not carry over, not that no signal exists (AUC 0.68). **Next:** pass-through, cycle and amount-scale-free features, calibrated on earlier days and tested on later ones.

**Decision:** Graph + temporal signals give a measurable improvement over the
rules baseline on synthetic data. Ring-level, purity-weighted cases are the
strongest measured result. The full 7-layer stack is not justified by the
measurements. **Next action:** backlog #3 is done (7.6e). AMLworld (7.8) shows the evidence features do not transfer: build features for cycles and pass-through next, then run the time split.
