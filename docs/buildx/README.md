# MuleCatch × BuildX 2026: refinement pack

Audit, evaluation and plan for taking MuleCatch to the BuildX Hackathon 2026
challenge **"Detect Payment Fraud in Real Time"** (Banking/FinTech track). The
challenge asks for detection that minimises false alerts for genuine customers.

> New chat? Start with [00-CONTEXT.md](00-CONTEXT.md).

## Verdict

**GO, with a simplified scope.** Keep the ring-level case workflow. Fix label
leakage and the UI's fabricated-data fallback. Drop the GNN, the LLM score
adjustment and the heavy infrastructure from the demo path. Present only
measured, clearly labelled synthetic results. Details:
[08 §15](08-execution-demo-pitch.md#15-go--no-go-recommendation).

## Deliverables

| # | Deliverable | File |
|---|---|---|
| 1 | Repository audit | [01-repository-audit.md](01-repository-audit.md) |
| 2 | Refined problem statement | [02-problem-and-customer.md](02-problem-and-customer.md) |
| 3 | Customer and beneficiary map | [02-problem-and-customer.md](02-problem-and-customer.md) |
| 4 | Competitor and differentiation analysis | [03-differentiation.md](03-differentiation.md) |
| 5 | Current vs target architecture | [04-architecture.md](04-architecture.md) |
| 6 | Prioritised implementation backlog | [01 §1.4](01-repository-audit.md#14-prioritised-engineering-backlog) |
| 7 | Dataset and evaluation plan + results | [05-evaluation.md](05-evaluation.md) |
| 8 | MVP specification | [06-mvp-and-test-plan.md](06-mvp-and-test-plan.md) |
| 9 | Business model and ROI framework | [07-business-and-impact.md](07-business-and-impact.md) |
| 10 | Social impact and risk assessment | [07-business-and-impact.md](07-business-and-impact.md) |
| 11 | Test plan and acceptance criteria | [06-mvp-and-test-plan.md](06-mvp-and-test-plan.md) |
| 12 | Hackathon execution schedule | [08-execution-demo-pitch.md](08-execution-demo-pitch.md) |
| 13 | Demonstration script | [08-execution-demo-pitch.md](08-execution-demo-pitch.md) |
| 14 | Pitch-deck outline | [08-execution-demo-pitch.md](08-execution-demo-pitch.md) |
| 15 | Go / no-go recommendation | [08-execution-demo-pitch.md](08-execution-demo-pitch.md) |

## Reproduce the numbers

```bash
# Python 3.12+ with backend/requirements.txt installed (torch not required)
python scripts/evaluation/evaluate_detectors.py   --out docs/buildx/evaluation_results.json
python scripts/evaluation/robustness_and_scale.py --out docs/buildx/robustness_scale_results.json
```

Evidence labels used throughout: **Measured** (run in this audit) ·
**Sourced** (public document, linked) · **Hypothesis** (needs validation) ·
**Assumption** (a placeholder input).
