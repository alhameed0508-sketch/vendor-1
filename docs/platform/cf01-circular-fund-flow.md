# CF01: circular fund flow

`backend/fraud_modules/cycles.py`, run by the Transaction and AML module on the loaded dataset.

A loop is reported when 3 to 6 distinct accounts form a directed cycle whose hops happen in time order (from some starting account) within 7 days, and every hop is 0.85-1.15x the previous one. That is the same money moving on. Self-transfers are ignored. Two-hop loops (A to B and back) are left out because they look like refunds. Cycle enumeration is capped at 20,000 cycles per run, and the cap is reported.

The hop band comes from IBM AMLworld's labelled CYCLE attempts, where 90% of hops sit within 0.91-1.10x of the previous hop (in US dollars). Ordinary customers also pay each other in circles, but those hops are unrelated amounts. A first version that only required the smallest hop to be at least half the largest flagged 12 loops of legitimate accounts in the synthetic dataset.

## Checks

| Check | Result |
|---|---|
| IBM HI-Small labelled CYCLE attempts with 3-6 hops (CF01's scope) | 19 of 20 detected (95%) |
| All IBM CYCLE attempts, including 2-hop and longer than 6 | 19 of 54 (35%): the rest are out of scope |
| Other IBM laundering typologies flagged as loops | 0 of 316 |
| IBM genuine payments on 2022-09-09 (653,953 payments; 44 loops in the graph) | 0 loops flagged, 5 s |
| Legitimate accounts in the synthetic adversarial dataset | 0 flagged (12 before the hop band) |

IBM AMLworld is published synthetic data, not bank data. Loops longer than 6 hops and multi-currency loops in raw (unconverted) amounts are not covered.
