"""Feature 2: Payment Intent & Beneficiary Intelligence.

Where is the money going, and why? Catches authorised push-payment scams: the customer authenticates
correctly, but the payee is a known-fraud account, sits one hop from a mule ring, is suddenly receiving
from many new payers, was added minutes ago, or the customer is on a call / being coached.

Ring membership itself is counted once, in the mule-network engine (MN02); this engine reads the ring
map only for one-hop links (BI02), so "two engines agree" stays two independent facts.
Codes BI01-BI10 match docs/SYSTEM_DESIGN.md section 6.3.3.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Mapping, Optional

from intelligence.contracts import BENEFICIARY, DECISIVE, STRONG, WEAK, EngineResult, Reason
from intelligence.mule_network import MuleNetworkIntel
from intelligence.profiles import CustomerProfile, PayeeIntel

from models.scam.victim_detector import ScamVictimDetector

NEW_PAYERS_24H = 5
YOUNG_PAYEE_DAYS = 7
JUST_ADDED_S = 30 * 60
SANCTIONS_MIN_CONFIDENCE = 0.85
COMPLAINT_REFRESH_SECONDS = 60.0
# Common Indian UPI scam phrases, in addition to the scam detector's own list (SV06).
INDIA_SCAM_PHRASES = (
    "digital arrest",
    "kyc update",
    "kyc pending",
    "account blocked",
    "electricity bill",
    "refund process",
    "part time job",
    "task reward",
    "courier seized",
    "customs duty",
    "cbi",
    "investment double",
    "crypto profit",
)


class KnownFraudRegistry:
    """Payees confirmed as fraud (feedback, decided complaints) and payees named in open complaints."""

    def __init__(
        self,
        complaint_source: Optional[Callable[[], Dict[str, str]]] = None,
        refresh_seconds: float = COMPLAINT_REFRESH_SECONDS,
        background: bool = True,
    ):
        self._confirmed: Dict[str, str] = {}
        self._from_complaints: Dict[str, str] = {}
        self._source = complaint_source
        self._lock = threading.Lock()
        self._refresh_seconds = refresh_seconds
        self._background = background
        self._last_refresh = float("-inf")
        self._worker: Optional[threading.Thread] = None
        self.refreshed_at: Optional[float] = None

    def maybe_refresh(self) -> None:
        """Reload complaint payees when due, off the payment path (cheap when not due)."""
        if self._source is None or time.monotonic() - self._last_refresh < self._refresh_seconds:
            return
        with self._lock:
            if time.monotonic() - self._last_refresh < self._refresh_seconds:
                return
            self._last_refresh = time.monotonic()
            if not self._background:
                worker = None
            elif self._worker is not None and self._worker.is_alive():
                return
            else:
                worker = self._worker = threading.Thread(target=self.refresh, daemon=True, name="known-fraud")
        if worker is None:
            self.refresh()
        else:
            worker.start()

    def confirm(self, account: str, why: str) -> None:
        with self._lock:
            self._confirmed[account] = why

    def clear(self, account: str) -> None:
        with self._lock:
            self._confirmed.pop(account, None)

    def refresh(self) -> None:
        if self._source is None:
            return
        try:
            found = self._source()
        except Exception:  # noqa: BLE001 - complaints are an extra signal; keep the last good copy
            return
        with self._lock:
            self._from_complaints = dict(found)
        self.refreshed_at = time.time()

    def lookup(self, account: str) -> Optional[Dict]:
        with self._lock:
            if account in self._confirmed:
                return {"status": "confirmed", "why": self._confirmed[account]}
            status = self._from_complaints.get(account)
        if status:
            return {"status": status, "why": "fraud complaint"}
        return None

    def size(self) -> Dict[str, int]:
        with self._lock:
            return {"confirmed": len(self._confirmed), "from_complaints": len(self._from_complaints)}


class BeneficiaryIntelligenceEngine:
    def __init__(
        self,
        mule: MuleNetworkIntel,
        known_fraud: Optional[KnownFraudRegistry] = None,
        sanctions_search: Optional[Callable[[str], List[Dict]]] = None,
        scam_detector: Optional[ScamVictimDetector] = None,
    ):
        self.mule = mule
        self.known_fraud = known_fraud or KnownFraudRegistry()
        self.sanctions_search = sanctions_search
        self.scam = scam_detector or ScamVictimDetector()

    def assess(
        self,
        payer: str,
        payee: str,
        amount: float,
        at: float,
        context: Mapping,
        profile: Optional[CustomerProfile],
        intel: Optional[PayeeIntel],
        payee_added_at: Optional[float],
    ) -> EngineResult:
        reasons: List[Reason] = []
        known = self.known_fraud.lookup(payee)
        if known:
            if known["status"] in ("confirmed", "decided"):
                reasons.append(
                    Reason(
                        "BI01",
                        f"The payee {payee} is a known-fraud account ({known['why']}, confirmed).",
                        0.95,
                        DECISIVE,
                    )
                )
            else:
                reasons.append(
                    Reason(
                        "BI01",
                        f"The payee {payee} is named in an open fraud complaint (not yet confirmed).",
                        0.55,
                        STRONG,
                    )
                )

        hop = self.mule.one_hop_ring(payee)
        if hop:
            reasons.append(
                Reason(
                    "BI02", f"The payee {payee} has sent to or received from mule ring {hop['ring_id']}.", 0.50, STRONG
                )
            )

        if intel is not None:
            fresh = intel.new_payers(at)
            if fresh >= NEW_PAYERS_24H:
                reasons.append(
                    Reason(
                        "BI03",
                        f"The payee received from {fresh} new payers in the last 24 h.",
                        min(0.75, 0.45 + 0.03 * (fresh - NEW_PAYERS_24H)),
                        STRONG,
                    )
                )
            if intel.first_seen and intel.age_days(at) < YOUNG_PAYEE_DAYS:
                reasons.append(
                    Reason("BI04", f"The payee was first seen {intel.age_days(at):.1f} days ago.", 0.25, WEAK)
                )

        trusted = profile is not None and payee in profile.trusted_payees
        new_payee = profile is not None and profile.n_payments > 0 and payee not in profile.payees and not trusted
        if new_payee:
            reasons.append(Reason("BI05", "First payment from this customer to this payee.", 0.15, WEAK))
        if payee_added_at is not None and 0 <= at - payee_added_at <= JUST_ADDED_S and not trusted:
            minutes = (at - payee_added_at) / 60
            reasons.append(Reason("BI06", f"The payee was added {minutes:.0f} min before the payment.", 0.35, STRONG))

        scam = self.scam.detect(
            payer,
            {
                "amount": amount,
                "narration": str(context.get("note") or ""),
                "is_new_beneficiary": new_payee,
                "account": {},
            },
            session_context={
                "on_phone_call": bool(context.get("on_call")),
                "backspace_count": int(context.get("backspace_count") or 0),
                "amount_pasted": bool(context.get("amount_pasted")),
                "app_switch_count": int(context.get("app_switch_count") or 0),
            },
        )
        call, coached = scam.score_breakdown.get("active_call", 0.0), scam.score_breakdown.get("coached_behavior", 0.0)
        if call > 0 or coached > 0:
            what = " and ".join(w for w, v in (("on a phone call", call), ("showing coached input", coached)) if v > 0)
            reasons.append(
                Reason(
                    "BI07",
                    f"The customer was {what} during the payment.",
                    min(0.65, 0.35 + 0.3 * max(call, coached)),
                    STRONG,
                )
            )
        note = str(context.get("note") or "").lower()
        phrases = [p for p in INDIA_SCAM_PHRASES if p in note]
        if scam.score_breakdown.get("scam_keywords", 0.0) > 0 or phrases:
            reasons.append(
                Reason(
                    "BI08",
                    f"The payment note contains scam phrases{': ' + ', '.join(phrases[:3]) if phrases else ''}.",
                    0.40,
                    STRONG,
                )
            )

        channel = str(context.get("channel") or "").upper()
        if channel in ("UPI_COLLECT", "QR") and (new_payee or (intel is None)):
            reasons.append(
                Reason(
                    "BI09",
                    f"{'Collect request' if channel == 'UPI_COLLECT' else 'QR payment'} to an unknown payee.",
                    0.30,
                    WEAK,
                )
            )

        name = context.get("payee_name")
        if name and self.sanctions_search is not None:
            try:
                hits = [
                    m for m in self.sanctions_search(str(name)) if m.get("confidence", 0) >= SANCTIONS_MIN_CONFIDENCE
                ]
            except Exception:  # noqa: BLE001 - screening is an extra check; never fail the payment on it
                hits = []
            if hits:
                top = max(hits, key=lambda m: m.get("confidence", 0))
                reasons.append(
                    Reason(
                        "BI10",
                        f"The payee name matches '{top.get('name')}' on the UN sanctions list "
                        f"({top.get('confidence', 0):.2f}).",
                        0.95,
                        DECISIVE,
                    )
                )

        features = {"new_payee": float(new_payee), "payee_new_payers_24h": float(intel.new_payers(at) if intel else 0)}
        return EngineResult(BENEFICIARY, tuple(reasons), True, features)


def complaint_beneficiaries(service) -> Dict[str, str]:
    """Payees named in fraud complaints: 'decided' when a fraud outcome was recorded, else 'open'."""
    fraud_categories = {"BANK_NEGLIGENCE", "THIRD_PARTY_BREACH", "CUSTOMER_NEGLIGENCE"}
    found: Dict[str, str] = {}
    for row in service.list_cases().get("cases", []):
        case = service.get_case(row["complaint_id"])
        account = case.get("beneficiary_account")
        if not account:
            continue
        category = (case.get("finding") or {}).get("category")
        if case.get("decision") and category in fraud_categories:
            found[account] = "decided"
        elif category != "NOT_FRAUD" and case.get("status") == "OPEN":
            found.setdefault(account, "open")
    return found
