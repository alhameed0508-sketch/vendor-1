"""
What a complaint shows at a given moment: its clocks, the current finding, and how that finding
moved as each piece of evidence arrived (the replay the live workflow view plays back).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from complaints.evidence import classify, verify_chain
from complaints.rules import assess_liability, calendar_days, compensation, deadlines

DUE_SOON_DAYS = 7
COMPENSATION_CUSTOMER_TYPES = ("INDIVIDUAL", "SOLE_PROPRIETOR")


def _at(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _iso(values: Dict) -> Dict:
    return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in values.items()}


def _clocks(case: Dict, now: datetime) -> Dict:
    return deadlines(
        occurred_at=_at(case["occurred_at"]),
        reported_at=_at(case["reported_at"]),
        cross_border=case["cross_border"],
        channel=case["channel"],
        now=now,
    )


def _assess(case: Dict, chain: List[Dict], within_window: bool) -> Dict:
    found = classify(chain)
    liability = assess_liability(
        category=found["category"],
        amount=case["amount"],
        amount_after_report=case["amount_after_report"],
        within_zero_liability_window=within_window,
        proof_complete=found["proof_complete"],
    )
    return {"finding": found, "liability": liability}


def _compensation(case: Dict, category: str, reported_after_days: int) -> Dict:
    occurred, ncrp = _at(case["occurred_at"]), _at(case.get("ncrp_reported_at"))
    result = compensation(
        category=category,
        loss=case["amount"],
        recovered=case["recovered"],
        cross_border=case["cross_border"],
        occurred_at=occurred,
        reported_after_days=reported_after_days,
        ncrp_reported_after_days=calendar_days(occurred, ncrp) if ncrp else None,
        is_individual=case["customer_type"] in COMPENSATION_CUSTOMER_TYPES,
        previously_compensated=case["previously_compensated"],
        form_received_at=_at(case.get("compensation_form_at")),
    )
    return _iso(result)


def _step(case: Dict, chain: List[Dict], within_window: bool) -> Dict:
    latest = chain[-1]
    state = _assess(case, chain, within_window)
    checklist = state["finding"]["checklist"]
    return {
        "evidence_id": latest["id"],
        "at": latest["at"],
        "received_at": latest["received_at"],
        "source": latest["source"],
        "kind": latest["kind"],
        "summary": latest["summary"],
        "category": state["finding"]["category"],
        "outcome": state["liability"]["outcome"],
        "customer_liability": state["liability"]["customer_liability"],
        "flags": state["finding"]["flags"],
        "proof_met": sum(c["met"] for c in checklist),
        "proof_needed": len(checklist),
    }


def _mule_link(chain: List[Dict]) -> Optional[Dict]:
    match = next((i for i in chain if i["kind"] == "mule_match"), None)
    return {"evidence_id": match["id"], **match["data"]} if match else None


def build_view(case: Dict, now: datetime) -> Dict:
    """The full case as of `now`: stored fields plus every derived clock, finding and check."""
    chain = case["evidence"]
    clocks = _clocks(case, now)
    window = clocks["within_zero_liability_window"]
    state = _assess(case, chain, window)
    return {
        **case,
        **state,
        "as_of": now.isoformat(),
        "deadlines": _iso(clocks),
        "compensation": _compensation(case, state["finding"]["category"], clocks["reported_after_days"]),
        "replay": [_step(case, chain[:n], window) for n in range(1, len(chain) + 1)],
        "chain": verify_chain(chain),
        "mule_link": _mule_link(chain),
    }


def summarize(view: Dict) -> Dict:
    """One row of the case list."""
    clocks = view["deadlines"]
    return {
        **{
            k: view[k]
            for k in ("complaint_id", "customer_name", "channel", "amount", "reported_at", "status", "cross_border")
        },
        "resolve_by": clocks["resolve_by"],
        "days_left": clocks["days_left"],
        "overdue": clocks["overdue"],
        "resolution_limit_days": clocks["resolution_limit_days"],
        "shadow_credit_by": clocks["shadow_credit_by"],
        "category": view["finding"]["category"],
        "outcome": view["liability"]["outcome"],
        "flags": view["finding"]["flags"],
        "evidence_count": len(view["evidence"]),
    }


def desk_summary(views: List[Dict]) -> Dict:
    """Counts for the top of the desk. Only open cases are on the clock."""
    open_cases = [v for v in views if v["status"] == "OPEN"]
    return {
        "open": len(open_cases),
        "due_soon": sum(
            not v["deadlines"]["overdue"] and v["deadlines"]["days_left"] <= DUE_SOON_DAYS for v in open_cases
        ),
        "overdue": sum(v["deadlines"]["overdue"] for v in open_cases),
        "shadow_credits_pending": sum(v["deadlines"]["shadow_credit_by"] is not None for v in open_cases),
        "compensation_due": sum(v["compensation"]["amount"] for v in open_cases),
        "mule_linked": sum("MULE_BENEFICIARY" in v["finding"]["flags"] for v in views),
        "amount_disputed": sum(v["amount"] for v in open_cases),
    }
