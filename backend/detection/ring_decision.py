"""One rule for "is this ring worth a human's time", shared by both engines.

The batch pipeline (alert list) and the per-payment scorer (live flags) used to decide
on their own. Both now ask ``ring_is_flaggable``: the ring has at least ``MIN_RING_SIZE``
accounts, at least ``MIN_RING_PURITY`` of its members carry evidence of their own, and
either the ring's suspicion or a member's own evidence reaches the flag threshold.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence

from models.community_detection.louvain_detector import Community
from models.temporal_weighting.smurf_weighting import SmurfWeightingEngine, score_transaction_batch

DEFAULT_FLAG_THRESHOLD = 0.50
MIN_RING_SIZE = 3
# Calibrated on seeded synthetic data: 78% of mule accounts vs 1.9% of genuine accounts reach it.
ENDPOINT_EVIDENCE_MIN = 0.30
# Share of ring members that must carry their own evidence ("no innocent bystanders").
MIN_RING_PURITY = 0.30
MERCHANT_TYPE = "MERCHANT"  # account_type whose own activity is not evidence (legitimate hubs)

# Evidence is scored at the default windows and at a slow scale (6x), keeping the stronger
# score per account, so stretching the timeline does not hide a ring.
SLOW_SCALE = SmurfWeightingEngine(velocity_minutes=360, consolidation_hours=36)
# A ring is also judged on payments between its own members, with a third scale that waits up to
# 6 days for the forward (consolidation), so decoys sent to outsiders or a very slow timeline cannot
# dilute the evidence. The velocity window stays at 6 h: a window of 12 h or more made genuine
# communities look like bursts (48 of 97 genuine payments flagged in the small test set).
LONG_FORWARD_SCALE = SmurfWeightingEngine(velocity_minutes=360, consolidation_hours=144)
RING_SCALES = (None, SLOW_SCALE, LONG_FORWARD_SCALE)


def multi_scale_evidence(window: Sequence[Mapping]) -> Dict:
    fast, slow = score_transaction_batch(list(window)), score_transaction_batch(list(window), SLOW_SCALE)
    return {acc: max(fast[acc], slow[acc], key=lambda s: s.smurf_score) for acc in fast}


def with_ring_evidence(smurf: Dict, ring: Optional[Community], window: Sequence[Mapping]) -> Dict:
    """Keep the stronger of an account's overall evidence and its evidence from ring-internal payments."""
    if ring is None or ring.size < MIN_RING_SIZE:
        return smurf
    internal = [t for t in window if t["from_account"] in ring.accounts and t["to_account"] in ring.accounts]
    if not internal:
        return smurf
    merged = dict(smurf)
    for engine in RING_SCALES:
        for acc, score in score_transaction_batch(internal, engine).items():
            if acc not in merged or score.smurf_score > merged[acc].smurf_score:
                merged[acc] = score
    return merged


def ring_is_pure(ring: Optional[Community], smurf: Mapping, merchants: frozenset = frozenset()) -> bool:
    if ring is None or not ring.accounts:
        return False
    with_evidence = sum(
        1
        for a in ring.accounts
        if a not in merchants and a in smurf and smurf[a].smurf_score >= ENDPOINT_EVIDENCE_MIN
    )
    return with_evidence / len(ring.accounts) >= MIN_RING_PURITY


def ring_is_flaggable(
    ring: Optional[Community],
    smurf: Mapping,
    merchants: frozenset = frozenset(),
    threshold: float = DEFAULT_FLAG_THRESHOLD,
) -> bool:
    """The ring-level decision: big enough, backed by its members' own evidence, and strong enough."""
    if ring is None or ring.size < MIN_RING_SIZE or not ring_is_pure(ring, smurf, merchants):
        return False
    best_member = max((smurf[a].smurf_score for a in ring.accounts if a not in merchants and a in smurf), default=0.0)
    return max(ring.suspicion_score, best_member) >= threshold
