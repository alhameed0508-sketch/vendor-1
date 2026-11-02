"""
RBI fraudulent-EBT rules as pure functions.

Source: RBI amendment directions RBI/2026-27/167 (24 June 2026), in force for electronic banking
transactions from 1 January 2027, as summarised in docs/research/2026-11-02-fraud-complaint-evidence-research.md.
Where the circular leaves a case to the bank's board-approved policy, these functions say so
instead of guessing a number.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

IST = timezone(timedelta(hours=5, minutes=30))
RULES_IN_FORCE_FROM = datetime(2027, 1, 1, tzinfo=IST)
COMPENSATION_SCHEME_ENDS = datetime(2028, 1, 1, tzinfo=IST)

RESOLUTION_DAYS_DOMESTIC = 45
RESOLUTION_DAYS_CROSS_BORDER = 60
ZERO_LIABILITY_REPORT_DAYS = 5
SHADOW_CREDIT_DAYS = 5
COMPENSATION_LOSS_LIMIT = 50_000
COMPENSATION_CAP = 25_000
COMPENSATION_PAY_DAYS = 5
# Shares of the net loss; together they make the 85% compensation rate.
SPLIT_DOMESTIC = {"rbi": 65, "customer_bank": 10, "beneficiary_bank": 10}
SPLIT_CROSS_BORDER = {"rbi": 65, "customer_bank": 20}

CATEGORIES = ("BANK_NEGLIGENCE", "THIRD_PARTY_BREACH", "CUSTOMER_NEGLIGENCE", "NOT_FRAUD", "UNDETERMINED")


def calendar_days(start: datetime, end: datetime) -> int:
    """Whole calendar days between two instants, counted on IST dates."""
    return (end.astimezone(IST).date() - start.astimezone(IST).date()).days


def _rupees(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_inr(amount: int, symbol: str = "₹") -> str:
    """Whole rupees with Indian digit grouping: ₹1,85,000."""
    digits = str(abs(int(amount)))
    head, tail = digits[:-3], digits[-3:]
    groups = [head[max(i - 2, 0) : i] for i in range(len(head), 0, -2)][::-1]
    return f"{'-' if amount < 0 else ''}{symbol}{','.join([*groups, tail])}"


def deadlines(*, occurred_at: datetime, reported_at: datetime, cross_border: bool, channel: str, now: datetime) -> Dict:
    """Every clock a complaint runs on, measured from the customer's report."""
    limit = RESOLUTION_DAYS_CROSS_BORDER if cross_border else RESOLUTION_DAYS_DOMESTIC
    resolve_by = reported_at + timedelta(days=limit)
    reported_after_days = calendar_days(occurred_at, reported_at)
    return {
        "rules_in_force": occurred_at >= RULES_IN_FORCE_FROM,
        "resolution_limit_days": limit,
        "resolve_by": resolve_by,
        "days_left": calendar_days(now, resolve_by),
        "overdue": now > resolve_by,
        "shadow_credit_by": reported_at + timedelta(days=SHADOW_CREDIT_DAYS) if channel == "CREDIT_CARD" else None,
        "reported_after_days": reported_after_days,
        "within_zero_liability_window": reported_after_days <= ZERO_LIABILITY_REPORT_DAYS,
    }


def assess_liability(
    *, category: str, amount: int, amount_after_report: int, within_zero_liability_window: bool, proof_complete: bool
) -> Dict:
    """Who bears the loss under the RBI categories. The burden of proving customer liability is the bank's."""
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category: {category}")

    def result(outcome: str, customer: Optional[int], basis: str) -> Dict:
        bank = None if customer is None else amount - customer
        return {
            "category": category,
            "outcome": outcome,
            "customer_liability": customer,
            "bank_liability": bank,
            "basis": basis,
        }

    if category in ("CUSTOMER_NEGLIGENCE", "NOT_FRAUD") and not proof_complete:
        return result("UNPROVEN", 0, "The bank cannot yet prove customer liability, so the loss stays with the bank.")
    if category == "BANK_NEGLIGENCE":
        return result("ZERO_LIABILITY", 0, "Bank negligence: zero customer liability whenever it was reported.")
    if category == "THIRD_PARTY_BREACH" and within_zero_liability_window:
        return result(
            "ZERO_LIABILITY", 0, "Third-party breach reported within 5 calendar days: zero customer liability."
        )
    if category == "THIRD_PARTY_BREACH":
        return result(
            "BANK_POLICY",
            None,
            "Third-party breach reported after 5 days: liability follows the bank's board-approved policy.",
        )
    if category == "CUSTOMER_NEGLIGENCE":
        return result(
            "CUSTOMER_LIABLE",
            amount - amount_after_report,
            "Customer negligence: the customer bears the loss until reporting, the bank after.",
        )
    if category == "NOT_FRAUD":
        return result("NOT_FRAUD", amount, "The customer made this payment, so it is not a fraudulent EBT.")
    return result("UNPROVEN", 0, "The evidence does not yet point to a category, so the loss stays with the bank.")


def _split(amount: int, cross_border: bool) -> Dict[str, int]:
    shares = SPLIT_CROSS_BORDER if cross_border else SPLIT_DOMESTIC
    total = sum(shares.values())
    banks = {k: _rupees(Decimal(amount) * v / total) for k, v in shares.items() if k != "rbi"}
    return {"rbi": amount - sum(banks.values()), **banks}


def compensation(
    *,
    category: str,
    loss: int,
    recovered: int,
    cross_border: bool,
    occurred_at: datetime,
    reported_after_days: int,
    ncrp_reported_after_days: Optional[int],
    is_individual: bool,
    previously_compensated: bool,
    form_received_at: Optional[datetime],
) -> Dict:
    """Small-value fraud compensation: eligibility checks, amount and who funds it."""
    checks: List[Dict] = [
        {"label": "Loss came from customer negligence", "met": category == "CUSTOMER_NEGLIGENCE"},
        {"label": f"Loss of ₹{COMPENSATION_LOSS_LIMIT:,} or less", "met": loss <= COMPENSATION_LOSS_LIMIT},
        {"label": "Individual or sole proprietor", "met": is_individual},
        {"label": "Reported to the bank within 5 days", "met": reported_after_days <= ZERO_LIABILITY_REPORT_DAYS},
        {
            "label": "Reported to NCRP or 1930 within 5 days",
            "met": ncrp_reported_after_days is not None and ncrp_reported_after_days <= ZERO_LIABILITY_REPORT_DAYS,
        },
        {
            "label": "Fraud in the scheme's first year",
            "met": RULES_IN_FORCE_FROM <= occurred_at < COMPENSATION_SCHEME_ENDS,
        },
        {"label": "First claim in the customer's lifetime", "met": not previously_compensated},
    ]
    eligible = all(c["met"] for c in checks)
    net_loss = max(loss - recovered, 0)
    amount = min(_rupees(Decimal(net_loss) * Decimal("0.85")), COMPENSATION_CAP) if eligible else 0
    return {
        "eligible": eligible,
        "checks": checks,
        "net_loss": net_loss,
        "amount": amount,
        "split": _split(amount, cross_border) if eligible else {},
        "pay_by": form_received_at + timedelta(days=COMPENSATION_PAY_DAYS) if eligible and form_received_at else None,
    }
