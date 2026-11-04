"""The unified real-time risk engine: mule core + three engines -> learned weights -> false-positive control.

Pipeline (docs/SYSTEM_DESIGN.md 6.2): validate and enrich -> mule network (core) -> session & device trust
-> payment intent & beneficiary -> behaviour baseline -> learned weights (0-100) -> false-positive control
-> band + reasons -> optional commit (trusted ingest only) -> feedback.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

from intelligence.behaviour_engine import AdaptiveBehaviourEngine
from intelligence.beneficiary_engine import BeneficiaryIntelligenceEngine, KnownFraudRegistry
from intelligence.contracts import (
    APPROVE,
    BAND_ACTIONS,
    BEHAVIOUR,
    BENEFICIARY,
    DECISIVE,
    DECLINE,
    ENGINE_LABELS,
    ENGINES,
    EVIDENCE_CODES,
    EVIDENCE_MIN_STRENGTH,
    FAMILIARITY,
    MULE,
    REVIEW,
    SESSION,
    STEP_UP,
    WEAK,
    Decision,
    EngineResult,
    utc_now,
)
from intelligence.decision_store import CONFIRMED_FRAUD, FALSE_ALERT, DecisionStore
from intelligence.model import FEATURE_LABELS, RiskModel
from intelligence.mule_network import MuleNetworkIntel
from intelligence.profiles import ProfileStore, event_seconds
from intelligence.session_engine import SessionIntegrityEngine, session_snapshot

REQUIRED = ("txn_id", "from_account", "to_account", "amount", "timestamp")


class TxnConflict(ValueError):
    """A txn_id was reused for a different payment."""


@dataclass
class EngineConfig:
    step_up_at: int = 40
    review_at: int = 70
    engine_active: float = 0.4
    min_corroboration: int = 2
    min_confidence_for_review: float = 0.35
    decisive_floor: int = 85
    allow_decline: bool = False
    decline_at: int = 95
    extra: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "bands": {
                "APPROVE": f"0-{self.step_up_at - 1}",
                "STEP_UP": f"{self.step_up_at}-{self.review_at - 1}",
                "REVIEW": f"{self.review_at}-100",
            },
            "engine_active_at": self.engine_active,
            "min_corroboration_for_review": self.min_corroboration,
            "min_confidence_for_review": self.min_confidence_for_review,
            "decisive_floor": self.decisive_floor,
            "automatic_decline": self.allow_decline,
        }


def _validate(event: Mapping) -> None:
    missing = [f for f in REQUIRED if event.get(f) in (None, "")]
    if missing:
        raise ValueError(f"payment missing required fields: {', '.join(missing)}")
    amount = float(event["amount"])
    if not amount > 0 or amount != amount or amount > 1e10:
        raise ValueError("amount must be a positive number")
    if event["from_account"] == event["to_account"]:
        raise ValueError("payer and payee must differ")


def _content(event: Mapping) -> tuple:
    return (
        str(event["from_account"]),
        str(event["to_account"]),
        round(float(event["amount"]), 2),
        str(event["timestamp"]),
    )


class UnifiedRiskEngine:
    def __init__(
        self,
        profiles: Optional[ProfileStore] = None,
        mule: Optional[MuleNetworkIntel] = None,
        session_engine: Optional[SessionIntegrityEngine] = None,
        beneficiary_engine: Optional[BeneficiaryIntelligenceEngine] = None,
        behaviour_engine: Optional[AdaptiveBehaviourEngine] = None,
        model: Optional[RiskModel] = None,
        store: Optional[DecisionStore] = None,
        config: Optional[EngineConfig] = None,
        known_fraud: Optional[KnownFraudRegistry] = None,
    ):
        self.profiles = profiles or ProfileStore()
        self.mule = mule or MuleNetworkIntel()
        self.session = session_engine or SessionIntegrityEngine()
        self.known_fraud = known_fraud or (
            beneficiary_engine.known_fraud if beneficiary_engine else KnownFraudRegistry()
        )
        self.beneficiary = beneficiary_engine or BeneficiaryIntelligenceEngine(self.mule, self.known_fraud)
        self.behaviour = behaviour_engine or AdaptiveBehaviourEngine()
        self.model = model or RiskModel.load()
        self.store = store or DecisionStore()
        self.config = config or EngineConfig()
        self._lock = threading.RLock()
        self._contents: "OrderedDict[str, tuple]" = OrderedDict()
        self._max_contents = 200_000

    # ------------------------------------------------------------------ assess
    def assess(
        self, event: Mapping, commit: bool = False, source: str = "api", label: Optional[str] = None
    ) -> Decision:
        """Score one payment. ``commit`` updates profiles and the ring window (trusted ingest only).

        Idempotency covers committed payments only: a re-sent payment returns its original decision and is
        never counted twice; the same txn_id with different content raises ``TxnConflict``. A what-if
        (``commit=False``) is never remembered, so it cannot block or pre-empt the real payment later.
        """
        _validate(event)
        started = time.perf_counter()
        txn_id = str(event["txn_id"])
        with self._lock:
            if commit:
                seen = self._contents.get(txn_id)
                if seen is not None:
                    if seen != _content(event):
                        raise TxnConflict("txn_id already used by a different payment")
                    existing = self.store.by_txn(txn_id)
                    if existing is not None:
                        return existing
                    commit = False  # already committed earlier (decision aged out of memory): re-score only
            decision = self._decide(event, started, commit, source, label)
            if commit:
                self._remember(event)
                self._commit(event)
        self.store.put(decision)
        return decision

    def _remember(self, event: Mapping) -> None:
        self._contents[str(event["txn_id"])] = _content(event)
        while len(self._contents) > self._max_contents:
            self._contents.popitem(last=False)

    def _decide(self, event: Mapping, started: float, commit: bool, source: str, label: Optional[str]) -> Decision:
        payer, payee = str(event["from_account"]), str(event["to_account"])
        amount = float(event["amount"])
        at = event_seconds(event["timestamp"])
        session = event.get("session") or None
        context = event.get("context") or {}
        added = context.get("beneficiary_added_at")
        payee_added_at = event_seconds(added) if added else None
        profile = self.profiles.customer(payer)
        intel = self.profiles.payee(payee)

        self.known_fraud.maybe_refresh()
        mule_res = self.mule.assess(payer, payee)
        sess_res = self.session.assess(payer, at, session, profile, payee_added_at)
        ben_res = self.beneficiary.assess(payer, payee, amount, at, context, profile, intel, payee_added_at)
        beh = self.behaviour.assess(payee, amount, at, session, profile)
        results: Dict[str, EngineResult] = {
            MULE: mule_res,
            SESSION: sess_res,
            BENEFICIARY: ben_res,
            BEHAVIOUR: beh.result,
        }
        familiarity, confidence = beh.familiarity, beh.confidence
        engines = {name: res.score(familiarity) for name, res in results.items()}
        corroboration = sum(1 for s in engines.values() if s >= self.config.engine_active)
        decisive = any(res.decisive for res in results.values())
        strong_reasons = [r for res in results.values() for r in res.reasons if r.kind not in (WEAK, FAMILIARITY)]
        has_evidence = any(r.code in EVIDENCE_CODES and r.strength >= EVIDENCE_MIN_STRENGTH for r in strong_reasons)

        features = {
            **engines,
            "familiarity": familiarity,
            "corroboration": float(corroboration),
            "new_payee": ben_res.features.get("new_payee", 0.0),
            "new_device": sess_res.features.get("new_device", 0.0),
            "amount_log_ratio": beh.amount_log_ratio,
            "confidence": confidence,
        }
        probability = self.model.probability(features)
        raw = int(round(100 * probability))
        score, controls = self._false_positive_control(
            raw, decisive, corroboration, confidence, bool(strong_reasons), has_evidence
        )
        band = self._band(score, corroboration)

        reasons = []
        for name, res in results.items():
            for r in res.reasons:
                reasons.append(
                    {
                        "code": r.code,
                        "text": r.text,
                        "strength": round(r.strength, 3),
                        "kind": r.kind,
                        "engine": name,
                        "dampened": r.kind == WEAK and familiarity > 0,
                    }
                )
        reasons.sort(key=lambda r: (r["kind"] != DECISIVE, -r["strength"]))
        reasons += [
            {
                "code": r.code,
                "text": r.text,
                "strength": r.strength,
                "kind": FAMILIARITY,
                "engine": BEHAVIOUR,
                "dampened": False,
            }
            for r in beh.familiarity_reasons
        ]

        contributions = self.model.contributions(features)
        explanation = {
            "summary": self._summary(band, score, reasons, familiarity, controls),
            "action": BAND_ACTIONS[band],
            "model": {
                "version": self.model.version,
                "probability": round(probability, 4),
                "raw_score": raw,
                "features": {k: round(float(v), 4) for k, v in features.items()},
                "log_odds": {FEATURE_LABELS[k]: v for k, v in contributions.items()},
                "intercept": self.model.intercept,
            },
            "engines": {
                name: {
                    "label": ENGINE_LABELS[name],
                    "score": engines[name],
                    "data_available": res.data_available,
                    "note": res.note,
                    "codes": [r.code for r in res.reasons],
                }
                for name, res in results.items()
            },
            "familiarity": familiarity,
            "confidence": confidence,
            "corroborating_engines": corroboration,
            "false_positive_controls": controls,
            "personal_limit": beh.personal_limit,
            "context": {
                "device_id": (session or {}).get("device_id"),
                "city": (session or {}).get("city"),
                "channel": context.get("channel"),
            },
        }
        now = utc_now()
        return Decision(
            decision_id=str(uuid.uuid4()),
            txn_id=str(event["txn_id"]),
            customer_id=payer,
            beneficiary_id=payee,
            amount=round(amount, 2),
            score=score,
            band=band,
            confidence=confidence,
            engines={k: round(v, 4) for k, v in engines.items()},
            contributions={FEATURE_LABELS[k]: v for k, v in contributions.items()},
            reasons=reasons,
            explanation=explanation,
            source=source,
            event_time=str(event["timestamp"]),
            decided_at=now.isoformat(),
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            model_version=self.model.version,
            committed=commit,
            label=label if source in ("synthetic", "scenario") else None,
        )

    def _false_positive_control(
        self,
        raw: int,
        decisive: bool,
        corroboration: int,
        confidence: float,
        has_strong: bool,
        has_evidence: bool = True,
    ):
        c = self.config
        score, controls = raw, []
        if decisive:
            if score < c.decisive_floor:
                controls.append(
                    f"Confirmed fact (mule ring, known-fraud payee or sanctions match): score raised to "
                    f"{c.decisive_floor}."
                )
            return max(score, c.decisive_floor), controls
        if not has_strong and score >= c.step_up_at:
            controls.append(
                "Only weak context signals (new device, new payee, unusual hour or place): "
                "nothing to interrupt the customer for."
            )
            score = c.step_up_at - 1
        if score >= c.review_at and not has_evidence:
            controls.append(
                "Unusual and new, but no evidence of fraud (no mule link, compromised session, "
                "scam pattern or known-fraud payee): verify with the customer, don't hold."
            )
            score = c.review_at - 1
        if score >= c.review_at and corroboration < c.min_corroboration:
            controls.append(f"Only {corroboration} engine(s) found evidence: verify with the customer, don't hold.")
            score = c.review_at - 1
        if score >= c.review_at and confidence < c.min_confidence_for_review:
            controls.append(f"The customer's baseline is thin (confidence {confidence:.2f}): step-up instead of hold.")
            score = c.review_at - 1
        return score, controls

    def _band(self, score: int, corroboration: int) -> str:
        c = self.config
        if c.allow_decline and score >= c.decline_at and corroboration >= 3:
            return DECLINE
        if score >= c.review_at:
            return REVIEW
        if score >= c.step_up_at:
            return STEP_UP
        return APPROVE

    @staticmethod
    def _summary(band: str, score: int, reasons: List[Dict], familiarity: float, controls: List[str]) -> str:
        risky = [r for r in reasons if r["kind"] != FAMILIARITY]
        if band == APPROVE and not risky:
            base = "Nothing unusual for this customer."
        elif band == APPROVE:
            base = f"Approved: {len(risky)} minor signal(s) did not add up to a reason to interrupt."
        else:
            top = "; ".join(r["text"] for r in risky[:2])
            base = f"{band.replace('_', '-').title()} at {score}/100: {top}"
        if familiarity >= 0.5:
            base += f" Familiar payment (familiarity {familiarity:.2f})."
        if controls:
            base += " " + controls[0]
        return base

    # ------------------------------------------------------------------ commit
    def _commit(self, event: Mapping, allow_refresh: bool = True) -> None:
        payer, payee = str(event["from_account"]), str(event["to_account"])
        at = event_seconds(event["timestamp"])
        session = event.get("session") or None
        typing = (session or {}).get("typing_ms_per_char")
        self.profiles.commit_payment(
            payer,
            payee,
            float(event["amount"]),
            at,
            device=str((session or {}).get("device_id") or ""),
            place=str((session or {}).get("city") or ""),
            session=session_snapshot(session),
            typing_ms=typing,
        )
        self.session.commit(payer, at, session)
        self.mule.add(
            {k: event[k] for k in REQUIRED}
            | {"device_id": (session or {}).get("device_id", ""), "ip_address": (session or {}).get("ip", "")},
            allow_refresh=allow_refresh,
        )

    def warm_up(self, events, accounts=()) -> int:
        """Load trusted history without scoring it (fast start). Returns the number of payments loaded."""
        if accounts:
            self.mule.add_accounts(accounts)
        n = 0
        with self._lock:
            for e in events:
                self._commit(e, allow_refresh=False)
                self._remember(e)
                n += 1
        self.mule.refresh()
        return n

    # ---------------------------------------------------------------- feedback
    def feedback(self, decision_id: str, outcome: str, note: str, by: str) -> Optional[Decision]:
        decision = self.store.set_outcome(decision_id, outcome, note, by)
        if decision is None:
            return None
        ctx = decision.explanation.get("context", {})
        with self._lock:  # profiles are shared with the scoring path
            profile = self.profiles.customer(decision.customer_id, create=True)
            if outcome == FALSE_ALERT:
                profile.trusted_payees.add(decision.beneficiary_id)
                if ctx.get("device_id"):
                    profile.trusted_devices.add(ctx["device_id"])
                if ctx.get("city"):
                    profile.trusted_places.add(ctx["city"])
            elif outcome == CONFIRMED_FRAUD:
                profile.trusted_payees.discard(decision.beneficiary_id)
                self.known_fraud.confirm(decision.beneficiary_id, f"confirmed by {by} on decision {decision_id[:8]}")
        return decision

    def status(self) -> Dict:
        return {
            "model": self.model.describe(),
            "config": self.config.to_dict(),
            "ring_map": self.mule.status(),
            "profiles": self.profiles.sizes,
            "known_fraud": self.known_fraud.size(),
            "engines": [{"key": k, "label": ENGINE_LABELS[k]} for k in ENGINES],
        }
