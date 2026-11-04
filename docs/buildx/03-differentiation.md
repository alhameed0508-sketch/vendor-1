# 4. Competitor and differentiation analysis (Phase C)

## 4.1 Landscape

| Player | What it does (public material) | Relevance | Source |
|---|---|---|---|
| **RBI / RBIH MuleHunter.AI** | Regulator-built AI/ML mule-account detection given to banks; 23 banks live by Dec 2025 | The default "free" alternative for Indian banks; detects accounts | [MediaNama](https://www.medianama.com/2025/12/223-rti-23-banks-mulehunter-mule-accounts/) |
| **Clari5 (acquired by Perfios, Feb 2025)** | Real-time FRM across UPI/IMPS/NEFT/CBS; mule detection with MuleHunter integration; link analysis and money-flow graph tool | Closest Indian incumbent; already offers network views | [Clari5 mule](https://www.clari5.com/?p=50856), [inbound monitoring](https://clari5.com/?p=48160), [CB Insights](https://www.cbinsights.com/company/customer-xps) |
| **BioCatch** | Behavioural biometrics + device/network telemetry for mule account detection; India-focused research | Strong on device/behaviour signals MuleCatch cannot access | [BioCatch](https://www.biocatch.com/mule-account-detection?hsLang=en) |
| **Feedzai** | Behavioural + cross-channel ML, federated learning; Chartis FCC50 2026 mule-detection winner (self-reported) | Global enterprise | [Feedzai](https://www.feedzai.com/resource/chartis-fcc50-2026-aml-mule-detection/) |
| **Quantexa** | Entity resolution + network-based "contextual" platform for scams and mule fraud | The archetype of graph-based investigation | [Quantexa brief](https://info.quantexa.com/hubfs/Fraud-%20Digital%20Radish/Solution%20brief%20%7C%20Quantexa%20Scams%20and%20Mule%20Fraud.pdf) |
| **NICE Actimize, SAS** | Enterprise AML/fraud suites; Actimize case study claims a 33 % false-positive reduction | Incumbents at large banks | [Actimize case](https://niceactimize.com/Lists/CustomerSuccesses/Attachments/53/aml_case_study_bank_reduces_false_positives_33_percent.pdf) |
| **Academic / open source** | IBM AMLworld synthetic AML datasets (NeurIPS 2023): GNNs and GBTs are both effective | Benchmark data, not a competitor | [Altman et al.](https://arxiv.org/pdf/2306.16424) |
| **Substitute** | Spreadsheets + rules + manual link analysis | What small teams actually do (hypothesis) | — |

All vendor performance claims above are self-reported. None were independently
verified.

## 4.2 Candidate differentiators, assessed

| Candidate | Already provided by others? | MuleCatch evidence today | Verdict |
|---|---|---|---|
| Network-level suspicious-activity detection | Yes (Quantexa, Clari5 link analysis, MuleHunter) | Louvain + smurf scoring works on synthetic rings | Not unique by itself |
| Temporal pattern analysis | Yes (all modern FRM) | Smurf weighting is the strongest single signal measured | Supporting |
| Evidence-backed reason codes | Common claim | Present, but some rules do not discriminate | Supporting, needs cleanup |
| **Case prioritisation for a limited team, with genuine customers kept out of the case** | Incumbents do case management; a ring-level queue that *measures* genuine-customer exposure is not a published claim we found | **Measured on synthetic data:** 5–7 cases reach 90 % mule recall, vs ≈ 225 account reviews for the rules queue (which never reached 90 % on hardened data) and 55–118 for a graph-scored account queue; purity-weighted ranking reduced genuine accounts exposed from a median of 150 to 0 on hardened data (see [05 §7.4](05-evaluation.md#74-investigator-workload-the-primary-differentiator-metric)) | **Primary** |
| Human-review workflow and audit | Standard in enterprise suites | Implemented and tested | Hygiene, not a differentiator |
| Measured reduction in investigation effort | Vendors claim it | Proxy measured; human timing not yet measured | Part of the primary claim's evidence |
| Detection quality at a controlled FPR | Everyone claims it | Graph+temporal beats rules on synthetic data | Supporting |

## 4.3 Primary differentiator

> **One ring, one case, no innocent bystanders.** MuleCatch converts
> account-level noise into a short queue of network cases. They are ranked by
> how much evidence *each member* carries, so an analyst covers most of a mule
> network in a handful of reviews without pulling genuine customers into the
> investigation.

| Question | Answer |
|---|---|
| Why it matters to the customer | Analyst hours are the binding constraint. Wrongly freezing genuine customers is a harm the challenge statement names directly |
| What alternatives do | Rule TM produces one alert per account, so analysts reconstruct the ring by hand. Enterprise graph tools offer link analysis *after* an alert fires, inside large, expensive suites |
| What MuleCatch changes | The *unit of work* becomes the ring. Ranking penalises cases whose members carry little individual evidence. Each case shows "who else is affected" explicitly |
| How to demonstrate it | Side by side on the same held-out data: (a) the account-level rules queue, (b) the MuleCatch case queue. Show reviews needed to reach 90 % of mules and genuine accounts touched along the way. Then open the top case live |
| What would disprove it | On independent data (AMLworld, or a bank's labelled history), the case queue needs as many reviews as the account queue, **or** exposes as many genuine accounts, **or** analysts in a timed test are no faster or less accurate with case view |

Not claimed: that GNNs, explainable AI, graph databases or the dashboard are
novel. The measured evaluation does **not** support the GNN, and it is removed
from the demo path.

**Decision:** Primary differentiator = *ring-level case prioritisation with
genuine-customer protection*. **Next action:** implement purity-weighted
ranking in the product (backlog #3) and re-run the evaluation on AMLworld
(backlog #8).
