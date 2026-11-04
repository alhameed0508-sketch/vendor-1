"""Run every detector on a claim and fuse the result. No detector here makes a network call."""

from __future__ import annotations

import hashlib
from typing import Dict, Iterable, Mapping

from return_fraud.detectors import (
    behavioral_signal,
    device_signal,
    exif_signal,
    graph_signal,
    receipt_signal,
    vlm_signal,
)
from return_fraud.fusion import CORROBORATION_MIN, fuse

HIGH_VALUE_INR = 25000
NEW_CUSTOMER_DAYS = 30
REPEAT_RETURNS = 3
PUBLIC_FIELDS = (
    "claim_id", "scenario", "customer_id", "customer_name", "amount", "currency", "category", "item",
    "delivered_at", "returned_at", "reason_text", "device_id", "address", "payment_fp",
    "carrier_fault", "carrier_events", "chargebacks",
)  # fmt: skip


def context_for(claim: Mapping) -> Dict[str, bool]:
    history = claim.get("history") or {}
    return {
        "high_value": claim.get("amount", 0) >= HIGH_VALUE_INR,
        "new_customer": history.get("account_age_days", 10**6) < NEW_CUSTOMER_DAYS,
        "repeat_returner": history.get("returns_90d", 0) >= REPEAT_RETURNS,
        "carrier_fault": bool(claim.get("carrier_fault")),
    }


def receipt_registry(claims: Iterable[Mapping]) -> Dict[str, str]:
    """sha256 of every receipt on file -> the first claim that used it."""
    seen: Dict[str, str] = {}
    for c in claims:
        if c.get("receipt_pdf"):
            seen.setdefault(hashlib.sha256(c["receipt_pdf"]).hexdigest(), c["claim_id"])
    return seen


def public_claim(claim: Mapping) -> Dict:
    return {k: claim[k] for k in PUBLIC_FIELDS if k in claim}


def assess_claim(claim: Mapping, pool: Iterable[Mapping]) -> Dict:
    pool = list(pool)
    others = [c for c in pool if c["claim_id"] != claim["claim_id"]]
    signals = [
        exif_signal(claim, others),
        vlm_signal(claim),
        receipt_signal(claim, receipt_registry(others)),
        device_signal(claim, others),
        behavioral_signal(claim),
        graph_signal(claim, others),
    ]
    context = context_for(claim)
    return {
        "claim": public_claim(claim),
        "context": context,
        "signals": _with_corroboration([s.as_dict() for s in signals]),
        "fusion": fuse(signals, context),
    }


def _with_corroboration(signals: list) -> list:
    """Name, for every signal that fired, the other fired signals that agree with it."""
    loud = {s["name"] for s in signals if s["available"] and s["score"] > CORROBORATION_MIN and s["confidence"] >= 0.5}
    return [{**s, "corroborated_by": sorted(loud - {s["name"]}) if s["name"] in loud else []} for s in signals]
