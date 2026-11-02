"""
Evidence for a fraud complaint: a hash-chained list of items and the classification it supports.

Each item's hash covers its content and the previous item's hash, so editing any item after the
fact breaks the chain from that item on. Classification maps the evidence to an RBI category and
lists, item by item, whether the bank can prove customer liability (the burden is the bank's).
"""

from __future__ import annotations

import hashlib
import json
from typing import Callable, Dict, List

GENESIS = "0" * 64
SOURCES = (
    "CUSTOMER", "BANK_CORE", "AUTH_LOG", "SMS_GATEWAY", "TELECOM", "BANK_SECURITY", "MERCHANT", "COURIER", "MULECATCH",
)
KINDS = (
    "complaint", "transaction", "sms_alert", "login", "sim_swap", "credential_disclosed", "bank_breach",
    "delivery_confirmed", "device_history", "return_inspection", "mule_match", "ncrp_report",
)
_HASHED_FIELDS = ("id", "at", "source", "kind", "summary", "data", "submitted_by", "received_at", "prev_hash")


def _digest(item: Dict) -> str:
    body = json.dumps({k: item[k] for k in _HASHED_FIELDS}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def append(
    chain: List[Dict], *, at: str, source: str, kind: str, summary: str, data: Dict, submitted_by: str, received_at: str
) -> List[Dict]:
    """Return a new chain with one more item, linked to the last item's hash."""
    if source not in SOURCES:
        raise ValueError(f"Unknown evidence source: {source}")
    if kind not in KINDS:
        raise ValueError(f"Unknown evidence kind: {kind}")
    item = {"id": f"E{len(chain) + 1}", "at": at, "source": source, "kind": kind, "summary": summary,
            "data": dict(data), "submitted_by": submitted_by, "received_at": received_at,
            "prev_hash": chain[-1]["hash"] if chain else GENESIS}
    return [*chain, {**item, "hash": _digest(item)}]


def verify_chain(chain: List[Dict]) -> Dict:
    """Recompute every hash; report the first item whose content or link no longer matches."""
    prev = GENESIS
    for item in chain:
        if item["prev_hash"] != prev or _digest(item) != item["hash"]:
            return {"intact": False, "broken_at": item["id"]}
        prev = item["hash"]
    return {"intact": True, "broken_at": None}


def _ids(chain: List[Dict], kind: str, test: Callable[[Dict], bool] = lambda d: True) -> List[str]:
    return [i["id"] for i in chain if i["kind"] == kind and test(i.get("data", {}))]


def _check(label: str, ids: List[str]) -> Dict:
    return {"label": label, "met": bool(ids), "evidence": ids}


def classify(chain: List[Dict]) -> Dict:
    """Map the evidence so far to an RBI category, with cited reasons and the burden-of-proof checklist."""
    bank_fault = _ids(chain, "bank_breach") + _ids(chain, "sms_alert", lambda d: d.get("delivered") is False)
    disclosed = _ids(chain, "credential_disclosed")
    mule = _ids(chain, "mule_match")
    third_party = _ids(chain, "sim_swap") + _ids(chain, "login", lambda d: d.get("new_device") is True) + mule
    delivered = _ids(chain, "delivery_confirmed", lambda d: d.get("address_matches") and d.get("otp_verified"))
    repeat_device = _ids(chain, "device_history", lambda d: d.get("same_device") and d.get("prior_orders", 0) >= 3)
    alert_sent = _ids(chain, "sms_alert", lambda d: d.get("delivered") is True)

    checklist: List[Dict] = []
    if bank_fault:
        category, decisive = "BANK_NEGLIGENCE", bank_fault
    elif disclosed:
        category, decisive = "CUSTOMER_NEGLIGENCE", disclosed
        checklist = [
            _check("Customer disclosed their credentials", disclosed),
            _check("Bank sent the mandatory SMS alert", alert_sent),
            _check("Payment passed OTP in the customer's session", _ids(chain, "login", lambda d: d.get("otp_verified") is True)),
        ]
    elif delivered and repeat_device and not third_party:
        category, decisive = "NOT_FRAUD", delivered + repeat_device
        checklist = [
            _check("Goods delivered to the registered address with OTP", delivered),
            _check("Same device as earlier undisputed orders", repeat_device),
            _check("Payment made from a device the bank knows", _ids(chain, "login", lambda d: d.get("new_device") is False)),
        ]
    elif third_party:
        category, decisive = "THIRD_PARTY_BREACH", third_party
    else:
        category, decisive = "UNDETERMINED", []

    by_id = {i["id"]: i for i in chain}
    flags = (["MULE_BENEFICIARY"] if mule else []) + (
        ["RETURN_ABUSE"] if _ids(chain, "return_inspection", lambda d: d.get("item_matches") is False) else [])
    return {
        "category": category,
        "reasons": [{"text": by_id[i]["summary"], "evidence": [i]} for i in decisive],
        "checklist": checklist,
        "proof_complete": bool(checklist) and all(c["met"] for c in checklist),
        "flags": flags,
    }
