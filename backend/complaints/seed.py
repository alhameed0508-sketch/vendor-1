"""
Demo complaints and the demo clock.

The RBI rules apply to frauds from 1 January 2027, so the demo desk runs on a clock that starts at
1 March 2027 10:00 IST and moves with real time. Every seeded date is relative to that clock, so the
deadlines on screen (one overdue, one due soon, one awaiting a shadow credit) stay the same.
All people, accounts and amounts are synthetic.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from complaints.evidence import mule_summary
from complaints.rules import IST

DEMO_NOW = datetime(2027, 3, 1, 10, 0, tzinfo=IST)
FALLBACK_BENEFICIARY = "AC_DEMO_BENEFICIARY"
_STARTED = time.monotonic()


def demo_clock() -> datetime:
    return DEMO_NOW + timedelta(seconds=time.monotonic() - _STARTED)


def _base(**fields) -> Dict:
    defaults = {
        "customer_type": "INDIVIDUAL",
        "amount_after_report": 0,
        "recovered": 0,
        "cross_border": False,
        "beneficiary_bank": "",
        "ncrp_reported_at": None,
        "previously_compensated": False,
        "compensation_form_at": None,
    }
    return {**defaults, **fields}


def demo_cases(now: datetime, mule: Optional[Dict]) -> List[Dict]:
    """Seven cases, one per situation a fraud desk meets. `mule` is a live MuleCatch alert node, if any."""

    def ago(days: int, hour: int, minute: int = 0) -> str:
        return (now - timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()

    def item(at, source, kind, summary, received_at, data=None, by="core-banking"):
        return {
            "at": at,
            "source": source,
            "kind": kind,
            "summary": summary,
            "data": data or {},
            "submitted_by": by,
            "received_at": received_at,
        }

    beneficiary = mule["account_id"] if mule else FALLBACK_BENEFICIARY
    mule_items = (
        [
            item(
                ago(6, 9, 16),
                "MULECATCH",
                "mule_match",
                mule_summary(beneficiary, mule),
                ago(6, 9, 16),
                dict(mule),
                by="mulecatch",
            )
        ]
        if mule
        else []
    )

    return [
        {
            "fields": _base(
                customer_name="Kavitha Raman",
                account="XXXX4821",
                channel="NETBANKING",
                amount=185_000,
                occurred_at=ago(6, 1, 40),
                reported_at=ago(6, 9, 15),
                ncrp_reported_at=ago(6, 9, 50),
                beneficiary_account=beneficiary,
                beneficiary_bank=mule.get("bank", "") if mule else "",
                description="Woke up to a ₹1,85,000 transfer and no mobile signal.",
            ),
            "evidence": [
                item(
                    ago(6, 9, 15),
                    "CUSTOMER",
                    "complaint",
                    "Customer reported a ₹1,85,000 transfer they did not make",
                    ago(6, 9, 15),
                    by="branch-desk",
                ),
                *mule_items,
                item(
                    ago(6, 1, 40),
                    "BANK_CORE",
                    "transaction",
                    "₹1,85,000 sent by IMPS to a payee added 8 minutes earlier",
                    ago(6, 9, 25),
                    {"amount": 185_000, "beneficiary": beneficiary},
                ),
                item(
                    ago(6, 1, 30),
                    "AUTH_LOG",
                    "login",
                    "Net banking login from a device never seen on this account",
                    ago(6, 9, 27),
                    {"new_device": True, "otp_verified": True},
                ),
                item(
                    ago(6, 9, 50),
                    "CUSTOMER",
                    "ncrp_report",
                    "Customer also reported it on 1930 within the hour",
                    ago(6, 10, 5),
                    by="branch-desk",
                ),
                item(
                    ago(7, 23, 55),
                    "TELECOM",
                    "sim_swap",
                    "Operator re-issued the registered SIM 2 hours before the transfer",
                    ago(5, 11, 30),
                    by="telecom-api",
                ),
            ],
        },
        {
            "fields": _base(
                customer_name="Arun Prakash",
                account="XXXX1937",
                channel="NETBANKING",
                amount=28_000,
                recovered=3_000,
                occurred_at=ago(2, 18, 20),
                reported_at=ago(2, 19, 5),
                ncrp_reported_at=ago(2, 19, 30),
                compensation_form_at=ago(1, 11),
                beneficiary_account="AC_DEMO_PAYEE_77",
                beneficiary_bank="Demo Payments Bank",
                description="Caller said my account would be frozen and asked for the OTP.",
            ),
            "evidence": [
                item(
                    ago(2, 19, 5),
                    "CUSTOMER",
                    "complaint",
                    "Customer reported a ₹28,000 transfer after reading an OTP to a caller posing as the bank",
                    ago(2, 19, 5),
                    by="branch-desk",
                ),
                item(
                    ago(2, 18, 20),
                    "BANK_CORE",
                    "transaction",
                    "₹28,000 net banking transfer authorised with an OTP",
                    ago(2, 19, 12),
                    {"amount": 28_000},
                ),
                item(
                    ago(2, 18, 18),
                    "SMS_GATEWAY",
                    "sms_alert",
                    "OTP and debit alert both delivered to the registered mobile",
                    ago(2, 19, 14),
                    {"delivered": True},
                    by="sms-gateway",
                ),
                item(
                    ago(2, 18, 15),
                    "AUTH_LOG",
                    "login",
                    "Transfer approved on the customer's usual phone with the OTP",
                    ago(2, 19, 15),
                    {"new_device": False, "otp_verified": True},
                ),
                item(
                    ago(2, 18, 17),
                    "CUSTOMER",
                    "credential_disclosed",
                    "Customer's signed statement: they read the OTP out to the caller",
                    ago(2, 19, 40),
                    by="branch-desk",
                ),
                item(
                    ago(2, 19, 30),
                    "CUSTOMER",
                    "ncrp_report",
                    "Customer reported it on 1930 the same evening",
                    ago(2, 19, 45),
                    by="branch-desk",
                ),
            ],
        },
        {
            "fields": _base(
                customer_name="Vikram Sethi",
                account="XXXX6612",
                channel="DEBIT_CARD",
                amount=64_999,
                occurred_at=ago(30, 21, 4),
                reported_at=ago(26, 10),
                beneficiary_account="MERCHANT_DEMO_ELECTRONICS",
                beneficiary_bank="Demo Acquirer",
                description="I never ordered this phone.",
            ),
            "evidence": [
                item(
                    ago(26, 10),
                    "CUSTOMER",
                    "complaint",
                    "Customer says they never ordered the ₹64,999 phone on their card",
                    ago(26, 10),
                    by="branch-desk",
                ),
                item(
                    ago(30, 21, 4),
                    "BANK_CORE",
                    "transaction",
                    "₹64,999 card payment to an online electronics store",
                    ago(26, 10, 20),
                    {"amount": 64_999},
                ),
                item(
                    ago(30, 21, 3),
                    "AUTH_LOG",
                    "login",
                    "Payment passed 3-D Secure on the phone this customer always banks on",
                    ago(26, 10, 22),
                    {"new_device": False, "otp_verified": True},
                ),
                item(
                    ago(28, 14, 12),
                    "COURIER",
                    "delivery_confirmed",
                    "Delivered to the registered address; the delivery OTP sent to the customer was entered",
                    ago(25, 12),
                    {"address_matches": True, "otp_verified": True},
                    by="courier-webhook",
                ),
                item(
                    ago(30, 21, 2),
                    "MERCHANT",
                    "device_history",
                    "Ordered from the same phone as 14 earlier orders the customer never disputed",
                    ago(25, 12, 5),
                    {"same_device": True, "prior_orders": 14},
                    by="merchant-webhook",
                ),
                item(
                    ago(20, 16, 40),
                    "MERCHANT",
                    "return_inspection",
                    "The customer also returned the order; the box held an older handset with a different IMEI",
                    ago(20, 17),
                    {"item_matches": False},
                    by="merchant-webhook",
                ),
            ],
        },
        {
            "fields": _base(
                customer_name="Meena Krishnan",
                account="XXXX3058",
                channel="NETBANKING",
                amount=72_000,
                occurred_at=ago(24, 10, 10),
                reported_at=ago(17, 12),
                beneficiary_account="AC_DEMO_PAYEE_31",
                beneficiary_bank="Demo Co-operative Bank",
                description="Found the debit in my statement. I got no SMS.",
            ),
            "evidence": [
                item(
                    ago(17, 12),
                    "CUSTOMER",
                    "complaint",
                    "Customer reported a ₹72,000 transfer a week late; they never got a debit alert",
                    ago(17, 12),
                    by="branch-desk",
                ),
                item(
                    ago(24, 10, 10),
                    "BANK_CORE",
                    "transaction",
                    "₹72,000 net banking transfer to a new payee",
                    ago(17, 12, 30),
                    {"amount": 72_000},
                ),
                item(
                    ago(24, 10, 5),
                    "AUTH_LOG",
                    "login",
                    "Login from a device never seen on this account",
                    ago(17, 12, 32),
                    {"new_device": True},
                ),
                item(
                    ago(24, 10, 11),
                    "SMS_GATEWAY",
                    "sms_alert",
                    "Gateway log: the debit alert for this transfer was rejected and never delivered",
                    ago(16, 15),
                    {"delivered": False},
                    by="sms-gateway",
                ),
            ],
        },
        {
            "fields": _base(
                customer_name="Imran Hussain",
                customer_type="SOLE_PROPRIETOR",
                account="XXXX7740",
                channel="UPI",
                amount=240_000,
                occurred_at=ago(57, 8),
                reported_at=ago(48, 17, 30),
                beneficiary_account="AC_DEMO_PAYEE_09",
                beneficiary_bank="Demo Small Finance Bank",
                description="Noticed three UPI payments when reconciling the shop's books.",
            ),
            "evidence": [
                item(
                    ago(48, 17, 30),
                    "CUSTOMER",
                    "complaint",
                    "Shop owner reported ₹2,40,000 in UPI payments nine days after they went out",
                    ago(48, 17, 30),
                    by="branch-desk",
                ),
                item(
                    ago(57, 8),
                    "BANK_CORE",
                    "transaction",
                    "Three UPI payments totalling ₹2,40,000 to one new payee",
                    ago(48, 18),
                    {"amount": 240_000},
                ),
                item(
                    ago(58, 23, 10),
                    "AUTH_LOG",
                    "login",
                    "UPI was registered on a new phone the night before",
                    ago(48, 18, 5),
                    {"new_device": True},
                ),
                item(
                    ago(57, 8, 1),
                    "SMS_GATEWAY",
                    "sms_alert",
                    "All three debit alerts were delivered to the registered mobile",
                    ago(47, 11),
                    {"delivered": True},
                    by="sms-gateway",
                ),
            ],
        },
        {
            "fields": _base(
                customer_name="Sneha D'Souza",
                account="XXXX2290",
                channel="CREDIT_CARD",
                amount=46_250,
                cross_border=True,
                occurred_at=ago(2, 3, 12),
                reported_at=ago(2, 8, 40),
                beneficiary_account="MERCHANT_DEMO_OVERSEAS",
                beneficiary_bank="Overseas acquirer",
                description="A charge in US dollars from a site I have never used.",
            ),
            "evidence": [
                item(
                    ago(2, 8, 40),
                    "CUSTOMER",
                    "complaint",
                    "Customer reported a ₹46,250 overseas card charge",
                    ago(2, 8, 40),
                    by="phone-banking",
                ),
                item(
                    ago(2, 3, 12),
                    "BANK_CORE",
                    "transaction",
                    "₹46,250 (US$555) card-not-present charge at an overseas merchant",
                    ago(2, 8, 50),
                    {"amount": 46_250, "currency": "USD"},
                ),
                item(
                    ago(2, 3, 13),
                    "SMS_GATEWAY",
                    "sms_alert",
                    "Debit alert delivered to the registered mobile",
                    ago(2, 8, 52),
                    {"delivered": True},
                    by="sms-gateway",
                ),
                item(
                    ago(2, 3, 11),
                    "AUTH_LOG",
                    "login",
                    "Card used from a device and country never linked to this card",
                    ago(2, 9, 5),
                    {"new_device": True},
                ),
            ],
        },
        {
            "fields": _base(
                customer_name="Lakshmi Narayanan",
                account="XXXX5503",
                channel="UPI",
                amount=15_500,
                occurred_at=ago(41, 20),
                reported_at=ago(40, 9),
                beneficiary_account="AC_DEMO_PAYEE_52",
                beneficiary_bank="Demo Payments Bank",
                description="Paid a seller on a marketplace app who then blocked me.",
            ),
            "evidence": [
                item(
                    ago(40, 9),
                    "CUSTOMER",
                    "complaint",
                    "Customer reported a ₹15,500 UPI payment to a seller who vanished",
                    ago(40, 9),
                    by="branch-desk",
                ),
                item(
                    ago(41, 20),
                    "BANK_CORE",
                    "transaction",
                    "₹15,500 UPI payment approved with the customer's UPI PIN",
                    ago(40, 9, 30),
                    {"amount": 15_500},
                ),
            ],
        },
    ]
