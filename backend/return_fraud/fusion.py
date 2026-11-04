"""Fuse the six signals into one score and a decision tier.

Independent evidence adds up (see ``fuse``), so several moderate findings can outweigh one strong one.

No single signal can push a claim past VERIFY. A claim is only CHALLENGED when at least
``CHALLENGE_MIN_SIGNALS`` signals each score above ``CORROBORATION_MIN`` and only BLOCKED when
``BLOCK_MIN_SIGNALS`` do. A signal that could not run is left out of the weighted average rather than
counted as clean, so missing evidence neither helps nor hurts the claim.
"""

from __future__ import annotations

import math
from typing import Dict, List, Mapping, Sequence

from return_fraud.signals import SIGNAL_NAMES, Signal

APPROVE_BELOW = 35
CHALLENGE_FROM = 65
BLOCK_FROM = 81
CORROBORATION_MIN = 60
CHALLENGE_MIN_SIGNALS = 2
BLOCK_MIN_SIGNALS = 3
CARRIER_FAULT_POINTS = 25
EVIDENCE_SCALE = 0.8
MAX_SIGNAL_CHANCE = 0.95

BASE_WEIGHTS: Mapping[str, float] = {
    "exif": 1.0,
    "vlm": 1.0,
    "receipt": 1.0,
    "device": 1.0,
    "behavioral": 1.0,
    "graph": 1.0,
}
# Context multipliers: what matters more for this kind of claim, and why.
CONTEXT_WEIGHTS: Mapping[str, Mapping[str, float]] = {
    "high_value": {"receipt": 1.6, "exif": 1.4, "vlm": 1.2},
    "new_customer": {"device": 1.5, "graph": 1.5, "behavioral": 0.6},
    "repeat_returner": {"behavioral": 1.6, "graph": 1.2},
}
FIREWALL_NOTE = (
    "No single signal can block or challenge a claim: it takes {need} independent signals above "
    f"{CORROBORATION_MIN} to go beyond verification."
)


def _tier(score: float) -> str:
    if score >= BLOCK_FROM:
        return "BLOCK"
    if score >= CHALLENGE_FROM:
        return "CHALLENGE"
    if score >= APPROVE_BELOW:
        return "VERIFY"
    return "APPROVE"


def _weights(context: Mapping) -> Dict[str, float]:
    weights = dict(BASE_WEIGHTS)
    for flag, multipliers in CONTEXT_WEIGHTS.items():
        if context.get(flag):
            for name, factor in multipliers.items():
                weights[name] *= factor
    return weights


def _contributions(chances: Mapping[str, float], score: float) -> Dict[str, float]:
    """Split the score before adjustments across the signals so the parts add up to it.

    Combined evidence is not a plain sum, so each signal takes a share of the total in proportion to its
    log-odds of being clean (-ln(1 - chance)). The shares add up to the score, give or take rounding.
    """
    shares = {name: -math.log(1.0 - chance) for name, chance in chances.items()}
    total = sum(shares.values())
    if total == 0:
        return {name: 0.0 for name in chances}
    return {name: round(score * share / total, 1) for name, share in shares.items()}


def _cap(tier: str, corroborating: int) -> str:
    if tier == "BLOCK" and corroborating < BLOCK_MIN_SIGNALS:
        tier = "CHALLENGE"
    if tier == "CHALLENGE" and corroborating < CHALLENGE_MIN_SIGNALS:
        tier = "VERIFY"
    return tier


def fuse(signals: Sequence[Signal], context: Mapping) -> Dict:
    """Return the fused score, tier, the firewall's verdict and every adjustment made."""
    live: List[Signal] = [s for s in signals if s.available]
    if not live:
        raise ValueError("fusion needs at least one signal that could run")
    weights = _weights(context)
    # Independent evidence combines: each signal is the chance, scaled by its weight and confidence, that the
    # claim is bad, and the claim is clean only if every signal is wrong. Squaring the score keeps a middling
    # signal from adding much while a strong one counts in full.
    clean = 1.0
    chances: Dict[str, float] = {}
    for s in live:
        chances[s.name] = min(MAX_SIGNAL_CHANCE, EVIDENCE_SCALE * weights[s.name] * s.confidence * (s.score / 100) ** 2)
        clean *= 1.0 - chances[s.name]
    score = 100.0 * (1.0 - clean)
    contributions = _contributions(chances, score)

    adjustments = []
    if context.get("carrier_fault"):
        taken = min(score, CARRIER_FAULT_POINTS)
        score -= taken
        adjustments.append(
            {"label": "Carrier route fault: the parcel was lost or damaged in transit", "points": -round(taken, 1)}
        )
    score = round(min(score, 100.0), 1)

    corroborating = sum(1 for s in live if s.score > CORROBORATION_MIN and s.confidence >= 0.5)
    raw_tier = _tier(score)
    tier = _cap(raw_tier, corroborating)
    # A loud signal alone cannot block, but it must not slip through as clean either: a person looks.
    loud = any(s.score > CORROBORATION_MIN and s.confidence >= 0.5 for s in live)
    if loud and tier == "APPROVE":
        tier = "VERIFY"
    # The score a person reads must agree with the tier: a capped claim shows the top of its own band.
    ceiling = {"CHALLENGE": BLOCK_FROM - 1, "VERIFY": CHALLENGE_FROM - 1}.get(tier) if tier != raw_tier else None
    shown = min(score, ceiling) if ceiling is not None else score
    if tier == "VERIFY":
        shown = max(shown, APPROVE_BELOW)
    return {
        "score": shown,
        "raw_score": score,
        "tier": tier,
        "capped_from": raw_tier if tier != raw_tier else None,
        "corroborating": corroborating,
        "firewall": FIREWALL_NOTE.format(
            need=CHALLENGE_MIN_SIGNALS if tier in {"CHALLENGE", "VERIFY"} else BLOCK_MIN_SIGNALS
        ),
        "contributions": {n: contributions.get(n, 0.0) for n in SIGNAL_NAMES},
        "weights": {n: round(weights[n], 2) for n in SIGNAL_NAMES},
        "missing": [n for n in SIGNAL_NAMES if n not in {s.name for s in live}],
        "adjustments": adjustments,
    }
