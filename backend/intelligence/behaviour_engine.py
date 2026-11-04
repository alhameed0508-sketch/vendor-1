"""Feature 3: Adaptive Customer Behaviour (the false-positive control's eyes).

Each customer is compared with their own history, not with a generic rule: amounts on a log scale
(median and robust spread, personal 99th percentile), the hours they pay, how many payments they make
in a busy hour, the places they pay from, and who they pay. The engine reports two things:
  - anomaly reasons (BH01-BH04): "unusual for you", which never prove fraud on their own;
  - familiarity (FC01-FC03): how ordinary this payment is for this person, which the false-positive
    control uses to quiet weak signals.
Codes match docs/SYSTEM_DESIGN.md section 6.3.4.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Mapping, Optional

from intelligence.contracts import BEHAVIOUR, FAMILIARITY, STRONG, WEAK, EngineResult, Reason
from intelligence.profiles import HOUR_S, CustomerProfile, local_hour

Z_ALERT = 3.0
MIN_HISTORY_FOR_AMOUNT = 5
MIN_HISTORY_FOR_HOURS = 20
RARE_HOUR_SHARE = 0.02
USUAL_HOUR_SHARE = 0.05
FAMILIAR_PAYEE_MIN = 3
FAMILIAR_AMOUNT_MULTIPLE = 3.0


@dataclass(frozen=True)
class BehaviourView:
    result: EngineResult
    familiarity: float
    familiarity_reasons: tuple
    confidence: float
    personal_limit: float  # amount above which this customer's payment counts as unusual
    amount_log_ratio: float


def _rupees(x: float) -> str:
    return f"₹{x:,.0f}"


class AdaptiveBehaviourEngine:
    def assess(
        self, payee: str, amount: float, at: float, session: Optional[Mapping], profile: Optional[CustomerProfile]
    ) -> BehaviourView:
        if profile is None or profile.n_payments == 0:
            note = "no history for this customer yet: nothing to compare with"
            return BehaviourView(EngineResult(BEHAVIOUR, (), True, {}, note), 0.0, (), 0.0, 0.0, 0.0)

        reasons: List[Reason] = []
        familiar: List[Reason] = []
        confidence = profile.confidence()
        hour = local_hour(at)
        device = (session or {}).get("device_id")
        city = (session or {}).get("city")

        hist = profile.payees.get(payee)
        trusted_payee = payee in profile.trusted_payees
        familiar_payee = trusted_payee or (
            hist is not None
            and hist.count >= FAMILIAR_PAYEE_MIN
            and amount <= FAMILIAR_AMOUNT_MULTIPLE * max(hist.usual_amount, 1.0)
        )
        if familiar_payee:
            why = (
                "confirmed genuine earlier"
                if trusted_payee and (hist is None or hist.count < FAMILIAR_PAYEE_MIN)
                else f"{hist.count} earlier payments, usually about {_rupees(hist.usual_amount)}"
            )
            familiar.append(Reason("FC01", f"Familiar payee: {why}.", 0.60, FAMILIARITY))

        known_device = bool(device) and (device in profile.devices or device in profile.trusted_devices)
        usual_place = not city or not profile.places or city in profile.places or city in profile.trusted_places
        if known_device and usual_place:
            familiar.append(Reason("FC02", "Known device and usual place.", 0.25, FAMILIARITY))
        if profile.n_payments >= MIN_HISTORY_FOR_HOURS and profile.hour_share(hour) >= USUAL_HOUR_SHARE:
            familiar.append(Reason("FC03", "A usual time of day for this customer.", 0.15, FAMILIARITY))

        med, spread, p99 = profile.amount_stats()
        personal_limit = max(p99, math.exp(med + Z_ALERT * spread)) if spread else 0.0
        log_ratio = math.log(max(amount, 1.0)) - med if spread else 0.0
        if profile.n_payments >= MIN_HISTORY_FOR_AMOUNT and spread and not familiar_payee:
            z = log_ratio / spread
            if z >= Z_ALERT and amount > p99:
                reasons.append(
                    Reason(
                        "BH01",
                        f"{_rupees(amount)} is far above this customer's usual payments "
                        f"(usual up to about {_rupees(personal_limit)}).",
                        min(0.6, 0.30 + 0.08 * (z - Z_ALERT)),
                        STRONG,
                    )
                )

        recent = profile.payments_in_window(at, HOUR_S) + 1
        usual_peak = profile.usual_busiest_hour(at)
        if profile.n_payments >= MIN_HISTORY_FOR_AMOUNT and recent >= max(3, 3 * max(usual_peak, 1)):
            reasons.append(
                Reason(
                    "BH02",
                    f"{recent} payments in the last hour; this customer's busiest hour so far had {usual_peak}.",
                    0.45,
                    STRONG,
                )
            )

        if profile.n_payments >= MIN_HISTORY_FOR_HOURS and profile.hour_share(hour) < RARE_HOUR_SHARE:
            reasons.append(Reason("BH03", f"{hour:02d}:00 is an hour this customer almost never uses.", 0.20, WEAK))
        if city and profile.places and city not in profile.places and city not in profile.trusted_places:
            reasons.append(Reason("BH04", f"First payment from {city} for this customer.", 0.20, WEAK))

        keep = 1.0
        for r in familiar:
            keep *= 1.0 - r.strength
        familiarity = round(1.0 - keep, 3)
        features = {"amount_log_ratio": round(log_ratio, 3), "payments_last_hour": float(recent)}
        note = f"{profile.n_payments} payments over {profile.history_days:.0f} days of history"
        return BehaviourView(
            EngineResult(BEHAVIOUR, tuple(reasons), True, features, note),
            familiarity,
            tuple(familiar),
            confidence,
            round(personal_limit, 2),
            round(log_ratio, 3),
        )
