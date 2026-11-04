# MuleCatch detection model card

## Intended use

Decision support for trained bank AML/fraud investigators identifying possible
mule accounts and coordinated transaction networks.

## Prohibited use

- Fully automated account closure, customer accusation, or law-enforcement
  referral
- Use outside approved bank products, jurisdictions, or customer populations
- Treating the score as a calibrated probability without validation
- Training or threshold adjustment from unreviewed investigator feedback

## System composition

The risk decision can combine rules, smurf weighting, behavioral baselines,
transaction semantics, device signals, Markov lifecycle transitions, Louvain
communities, and an optional GNN/lightweight scorer. Alerts retain reason codes,
subgraphs, explanations, and model/rule versions.

## Current evidence

Unit and integration tests establish software behavior. Synthetic and PaySim
benchmarks are development evidence only. No repository artifact demonstrates
effectiveness on a representative bank population.

## Required validation

- Time-based and institution-specific holdout sets
- Precision/recall/PR-AUC and probability calibration
- Performance at investigator-capacity thresholds
- Segment, channel, geography, and account-tenure analysis
- Stability and drift analysis
- False-positive harm analysis
- Adversarial typology and data-quality testing
- Independent validation and approval

## Human oversight

Investigators must review the underlying transactions, graph, identity/device
evidence, explanations, and conflicting evidence. Feedback must be attributable
and quality controlled. Threshold or model changes require maker-checker
approval and a recorded release identifier.

## Known limitations

- Cross-bank visibility depends on supplied counterparty-bank metadata.
- Sparse or single-use mules may lack sufficient graph evidence.
- Shared devices/IPs can reflect legitimate households, branches, NAT, or
  assisted banking.
- Synthetic datasets can exaggerate separability.
- Optional learned models may fall back when artifacts/dependencies are absent.
- Concept drift and policy changes require periodic revalidation.
