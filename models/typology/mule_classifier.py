"""
Mule Typology Classifier — 5-class rule-based classification.

Classifies flagged accounts into one of five mule typologies based on
behavioral signals extracted from account metadata, transaction history,
and session data. Each typology maps to a distinct operational profile
used by money mule networks in Indian banking.

Typologies:
  MT01 DECEIVER   — Professional mule, synthetic identity
  MT02 PEDDLER    — Recruited mule, legitimate then inflects
  MT03 ACCOMPLICE — Willing participant, progressive structuring
  MT04 CHUMP      — Unwitting participant, coached behavior
  MT05 VICTIM     — Account takeover, complete behavioral shift
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class MuleTypology(Enum):
    """Five-class mule typology labels."""

    DECEIVER = "DECEIVER"
    PEDDLER = "PEDDLER"
    ACCOMPLICE = "ACCOMPLICE"
    CHUMP = "CHUMP"
    VICTIM = "VICTIM"


@dataclass(frozen=True)
class TypologyResult:
    """Immutable classification output for a single account."""

    account_id: str
    predicted_type: MuleTypology
    confidence: float
    probabilities: Dict[str, float]
    behavioral_signals: Dict[str, float]
    reason_codes: Tuple[str, ...]


# ---------------------------------------------------------------------------
# Thresholds — centralised for auditability
# ---------------------------------------------------------------------------
_ONBOARDING_FAST_SECONDS = 120
_ACCOUNT_YOUNG_DAYS = 30
_HIGH_OUTGOING_VOLUME = 500_000
_DORMANCY_DAYS = 60
_VELOCITY_SPIKE_FACTOR = 5.0
_PROGRESSIVE_TXN_MIN = 5
_FAN_OUT_THRESHOLD = 3
_SUPPORT_CONTACT_THRESHOLD = 2
_SMALL_TEST_AMOUNT = 1_000
_LARGE_TXN_AMOUNT = 100_000
_ATO_NEW_DEVICE_FLAG = True
_ATO_NEW_LOCATION_FLAG = True
_ATO_RAPID_TRANSFER_HOURS = 24


def _safe_get(d: Dict, key: str, default=0.0):
    """Safely retrieve a numeric value from a dict."""
    val = d.get(key, default)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_get_int(d: Dict, key: str, default: int = 0) -> int:
    val = d.get(key, default)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Individual typology scorers
# ---------------------------------------------------------------------------


def _score_deceiver(
    account: Dict,
    transactions: List[Dict],
    session_data: Optional[Dict],
) -> Tuple[float, Dict[str, float], List[str]]:
    """MT01 DECEIVER — synthetic identity, expert application fluency."""
    signals: Dict[str, float] = {}
    reasons: List[str] = []

    # Fast onboarding
    onboarding_time = _safe_get(account, "onboarding_time_seconds", 600)
    signals["fast_onboarding"] = _clamp(1.0 - (onboarding_time / 600)) if onboarding_time < 600 else 0.0
    if onboarding_time < _ONBOARDING_FAST_SECONDS:
        reasons.append("MT01: Onboarding completed in under 2 minutes")

    # High KYC completeness (paradoxically perfect for synthetic IDs)
    kyc = _safe_get(account, "kyc_completeness", 0.5)
    signals["kyc_completeness"] = _clamp(kyc)
    if kyc > 0.95:
        reasons.append("MT01: Near-perfect KYC completeness (synthetic marker)")

    # Young account
    age = _safe_get_int(account, "account_age_days", 365)
    signals["young_account"] = _clamp(1.0 - (age / _ACCOUNT_YOUNG_DAYS)) if age < _ACCOUNT_YOUNG_DAYS else 0.0
    if age < _ACCOUNT_YOUNG_DAYS:
        reasons.append(f"MT01: Account age {age} days (< {_ACCOUNT_YOUNG_DAYS})")

    # High outgoing volume
    total_out = sum(_safe_get(tx, "amount", 0) for tx in transactions if not tx.get("is_incoming", False))
    signals["high_outgoing"] = _clamp(total_out / _HIGH_OUTGOING_VOLUME)
    if total_out > _HIGH_OUTGOING_VOLUME:
        reasons.append("MT01: High outgoing transaction volume")

    # Synthetic identity markers from session
    if session_data:
        device_count = _safe_get_int(session_data, "unique_devices", 1)
        signals["multi_device"] = _clamp((device_count - 1) / 3)
        if device_count > 2:
            reasons.append("MT01: Multiple devices used during onboarding")

    score = _clamp(
        signals.get("fast_onboarding", 0) * 0.25
        + signals.get("kyc_completeness", 0) * 0.20
        + signals.get("young_account", 0) * 0.25
        + signals.get("high_outgoing", 0) * 0.20
        + signals.get("multi_device", 0) * 0.10
    )
    return score, signals, reasons


def _score_peddler(
    account: Dict,
    transactions: List[Dict],
    session_data: Optional[Dict],
) -> Tuple[float, Dict[str, float], List[str]]:
    """MT02 PEDDLER — legitimate onboarding then abrupt behavioral inflection."""
    signals: Dict[str, float] = {}
    reasons: List[str] = []

    # Normal account age (not brand-new)
    age = _safe_get_int(account, "account_age_days", 0)
    signals["normal_age"] = _clamp(age / 180) if age > _ACCOUNT_YOUNG_DAYS else 0.0
    if age > _ACCOUNT_YOUNG_DAYS:
        reasons.append("MT02: Account has legitimate history")

    # Good KYC
    kyc = _safe_get(account, "kyc_completeness", 0.5)
    signals["good_kyc"] = _clamp(kyc)

    # Dormancy then spike — look for gap in transactions
    if len(transactions) >= 2:
        sorted_txns = sorted(transactions, key=lambda t: _safe_get(t, "timestamp", 0))
        gaps = []
        for i in range(1, len(sorted_txns)):
            gap = _safe_get(sorted_txns[i], "timestamp", 0) - _safe_get(sorted_txns[i - 1], "timestamp", 0)
            gaps.append(gap)
        max_gap_days = max(gaps) / 86400 if gaps else 0
        signals["dormancy_gap"] = _clamp(max_gap_days / _DORMANCY_DAYS)
        if max_gap_days > _DORMANCY_DAYS:
            reasons.append(f"MT02: Dormancy gap of {int(max_gap_days)} days detected")

        # Velocity spike after dormancy
        if len(sorted_txns) >= 4:
            mid = len(sorted_txns) // 2
            early_avg = sum(_safe_get(t, "amount", 0) for t in sorted_txns[:mid]) / max(mid, 1)
            late_avg = sum(_safe_get(t, "amount", 0) for t in sorted_txns[mid:]) / max(len(sorted_txns) - mid, 1)
            spike = late_avg / max(early_avg, 1)
            signals["velocity_spike"] = _clamp(spike / _VELOCITY_SPIKE_FACTOR)
            if spike > _VELOCITY_SPIKE_FACTOR:
                reasons.append("MT02: Sudden velocity spike after dormant period")
        else:
            signals["velocity_spike"] = 0.0
    else:
        signals["dormancy_gap"] = 0.0
        signals["velocity_spike"] = 0.0

    score = _clamp(
        signals.get("normal_age", 0) * 0.15
        + signals.get("good_kyc", 0) * 0.10
        + signals.get("dormancy_gap", 0) * 0.35
        + signals.get("velocity_spike", 0) * 0.40
    )
    return score, signals, reasons


def _score_accomplice(
    account: Dict,
    transactions: List[Dict],
    session_data: Optional[Dict],
) -> Tuple[float, Dict[str, float], List[str]]:
    """MT03 ACCOMPLICE — progressive structuring, gradual escalation."""
    signals: Dict[str, float] = {}
    reasons: List[str] = []

    # Normal onboarding
    age = _safe_get_int(account, "account_age_days", 0)
    signals["normal_onboarding"] = _clamp(age / 90) if age > 14 else 0.0

    # Progressive amount increase
    if len(transactions) >= _PROGRESSIVE_TXN_MIN:
        sorted_txns = sorted(transactions, key=lambda t: _safe_get(t, "timestamp", 0))
        amounts = [_safe_get(t, "amount", 0) for t in sorted_txns]
        # Count consecutive increases
        increases = sum(1 for i in range(1, len(amounts)) if amounts[i] > amounts[i - 1])
        increase_ratio = increases / max(len(amounts) - 1, 1)
        signals["progressive_amounts"] = _clamp(increase_ratio)
        if increase_ratio > 0.6:
            reasons.append("MT03: Progressive transaction amount escalation")
    else:
        signals["progressive_amounts"] = 0.0

    # Fan-out ratio (many unique beneficiaries)
    beneficiaries = set()
    for tx in transactions:
        if not tx.get("is_incoming", False):
            bene = tx.get("beneficiary_id") or tx.get("counterparty_id")
            if bene:
                beneficiaries.add(bene)
    fan_out = len(beneficiaries)
    signals["fan_out"] = _clamp(fan_out / (_FAN_OUT_THRESHOLD * 3))
    if fan_out >= _FAN_OUT_THRESHOLD:
        reasons.append(f"MT03: Fan-out to {fan_out} unique beneficiaries")

    # Structuring — amounts just below threshold
    structured_count = sum(1 for tx in transactions if 45_000 <= _safe_get(tx, "amount", 0) <= 49_999)
    signals["structuring"] = _clamp(structured_count / 5)
    if structured_count >= 3:
        reasons.append("MT03: Amounts structured below 50k reporting threshold")

    score = _clamp(
        signals.get("normal_onboarding", 0) * 0.10
        + signals.get("progressive_amounts", 0) * 0.35
        + signals.get("fan_out", 0) * 0.25
        + signals.get("structuring", 0) * 0.30
    )
    return score, signals, reasons


def _score_chump(
    account: Dict,
    transactions: List[Dict],
    session_data: Optional[Dict],
) -> Tuple[float, Dict[str, float], List[str]]:
    """MT04 CHUMP — unwitting participant, coached behavior signals."""
    signals: Dict[str, float] = {}
    reasons: List[str] = []

    # Normal baseline behavior
    age = _safe_get_int(account, "account_age_days", 0)
    signals["established_account"] = _clamp(age / 180) if age > 30 else 0.0

    # Support contacts (hesitation signal)
    support_contacts = _safe_get_int(session_data or {}, "support_contacts", 0)
    signals["support_contacts"] = _clamp(support_contacts / (_SUPPORT_CONTACT_THRESHOLD * 2))
    if support_contacts >= _SUPPORT_CONTACT_THRESHOLD:
        reasons.append(f"MT04: {support_contacts} support contacts (hesitation signal)")

    # Small test transactions before large ones
    if len(transactions) >= 2:
        sorted_txns = sorted(transactions, key=lambda t: _safe_get(t, "timestamp", 0))
        small_then_large = False
        for i in range(len(sorted_txns) - 1):
            current_amt = _safe_get(sorted_txns[i], "amount", 0)
            next_amt = _safe_get(sorted_txns[i + 1], "amount", 0)
            if current_amt < _SMALL_TEST_AMOUNT and next_amt > _LARGE_TXN_AMOUNT:
                small_then_large = True
                break
        signals["test_before_large"] = 1.0 if small_then_large else 0.0
        if small_then_large:
            reasons.append("MT04: Small test transaction followed by large transfer")
    else:
        signals["test_before_large"] = 0.0

    # Irregular timing — transactions at unusual hours
    unusual_hour_count = 0
    for tx in transactions:
        hour = _safe_get_int(tx, "hour", 12)
        if hour < 6 or hour > 23:
            unusual_hour_count += 1
    signals["irregular_timing"] = _clamp(unusual_hour_count / max(len(transactions), 1))
    if unusual_hour_count >= 2:
        reasons.append("MT04: Transactions at unusual hours (coached behavior)")

    # Repeated same-beneficiary pattern (coached to send to specific account)
    if transactions:
        bene_counts: Dict[str, int] = {}
        for tx in transactions:
            if not tx.get("is_incoming", False):
                bene = tx.get("beneficiary_id") or tx.get("counterparty_id", "")
                if bene:
                    bene_counts[bene] = bene_counts.get(bene, 0) + 1
        max_to_single = max(bene_counts.values()) if bene_counts else 0
        signals["repeat_beneficiary"] = _clamp(max_to_single / 5)
        if max_to_single >= 3:
            reasons.append("MT04: Repeated transfers to same beneficiary")
    else:
        signals["repeat_beneficiary"] = 0.0

    score = _clamp(
        signals.get("established_account", 0) * 0.10
        + signals.get("support_contacts", 0) * 0.30
        + signals.get("test_before_large", 0) * 0.25
        + signals.get("irregular_timing", 0) * 0.15
        + signals.get("repeat_beneficiary", 0) * 0.20
    )
    return score, signals, reasons


def _score_victim(
    account: Dict,
    transactions: List[Dict],
    session_data: Optional[Dict],
) -> Tuple[float, Dict[str, float], List[str]]:
    """MT05 VICTIM — account takeover, complete behavioral shift."""
    signals: Dict[str, float] = {}
    reasons: List[str] = []
    sess = session_data or {}

    # New device
    new_device = bool(sess.get("new_device", False))
    signals["new_device"] = 1.0 if new_device else 0.0
    if new_device:
        reasons.append("MT05: Login from previously unseen device")

    # New location
    new_location = bool(sess.get("new_location", False))
    signals["new_location"] = 1.0 if new_location else 0.0
    if new_location:
        reasons.append("MT05: Login from new geographic location")

    # Rapid large transfers to unknown beneficiaries
    unknown_large = 0
    for tx in transactions:
        if not tx.get("is_incoming", False):
            amt = _safe_get(tx, "amount", 0)
            is_known = tx.get("known_beneficiary", True)
            if amt > _LARGE_TXN_AMOUNT and not is_known:
                unknown_large += 1
    signals["rapid_unknown_transfers"] = _clamp(unknown_large / 3)
    if unknown_large >= 1:
        reasons.append(f"MT05: {unknown_large} large transfer(s) to unknown beneficiaries")

    # Password/credential change before transfers
    cred_changed = bool(sess.get("credential_change", False))
    signals["credential_change"] = 1.0 if cred_changed else 0.0
    if cred_changed:
        reasons.append("MT05: Credential change preceding suspicious transfers")

    # Behavioral deviation score (externally provided)
    deviation = _safe_get(sess, "behavioral_deviation", 0)
    signals["behavioral_deviation"] = _clamp(deviation)
    if deviation > 0.7:
        reasons.append("MT05: High behavioral deviation from baseline")

    score = _clamp(
        signals.get("new_device", 0) * 0.25
        + signals.get("new_location", 0) * 0.20
        + signals.get("rapid_unknown_transfers", 0) * 0.25
        + signals.get("credential_change", 0) * 0.15
        + signals.get("behavioral_deviation", 0) * 0.15
    )
    return score, signals, reasons


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

_SCORERS = (
    (MuleTypology.DECEIVER, _score_deceiver),
    (MuleTypology.PEDDLER, _score_peddler),
    (MuleTypology.ACCOMPLICE, _score_accomplice),
    (MuleTypology.CHUMP, _score_chump),
    (MuleTypology.VICTIM, _score_victim),
)


class MuleTypologyClassifier:
    """Rule-based 5-class mule typology classifier.

    Runs all five typology scorers and selects the highest-scoring type.
    Confidence is defined as max_score - second_highest_score.
    """

    def classify(
        self,
        account: Dict,
        transactions: List[Dict],
        session_data: Optional[Dict] = None,
    ) -> TypologyResult:
        """Classify an account into one of five mule typologies.

        Args:
            account: Account metadata dict (kyc_completeness, account_age_days, etc.)
            transactions: List of transaction dicts (amount, timestamp, is_incoming, etc.)
            session_data: Optional session/device context dict.

        Returns:
            Immutable TypologyResult with predicted type, confidence, and signals.
        """
        account_id = str(account.get("account_id", "UNKNOWN"))

        all_scores: List[Tuple[MuleTypology, float, Dict[str, float], List[str]]] = []
        for typology, scorer in _SCORERS:
            score, signals, reasons = scorer(account, transactions, session_data)
            all_scores.append((typology, score, signals, reasons))

        # Sort descending by score
        all_scores.sort(key=lambda x: x[1], reverse=True)

        best_typology, best_score, best_signals, best_reasons = all_scores[0]
        second_score = all_scores[1][1] if len(all_scores) > 1 else 0.0

        confidence = _clamp(best_score - second_score)

        probabilities = {entry[0].value: round(entry[1], 4) for entry in all_scores}
        behavioral_signals = {k: round(v, 4) for k, v in best_signals.items()}

        # Merge reason codes from all scorers that contributed meaningfully
        merged_reasons: List[str] = list(best_reasons)
        for typology, score, _, reasons in all_scores[1:]:
            if score > 0.3:
                merged_reasons.extend(reasons)

        return TypologyResult(
            account_id=account_id,
            predicted_type=best_typology,
            confidence=round(confidence, 4),
            probabilities=probabilities,
            behavioral_signals=behavioral_signals,
            reason_codes=tuple(merged_reasons),
        )
