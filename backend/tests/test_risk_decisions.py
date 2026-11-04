"""The unified decision: false-positive controls, explainability, idempotency and feedback."""

import math
from datetime import datetime, timedelta, timezone

import pytest
from intelligence.contracts import APPROVE, EVIDENCE_CODES, REVIEW, STEP_UP
from intelligence.engine import EngineConfig, TxnConflict, UnifiedRiskEngine
from intelligence.model import FEATURES, PRIOR, RiskModel

IST = timezone(timedelta(hours=5, minutes=30))
T0 = datetime(2026, 9, 1, 10, 0, tzinfo=IST)


def _session(device="PHONE-1", city="Pune", sid="S", **extra):
    return {
        "session_id": sid,
        "device_id": device,
        "ip": "10.1.1.1",
        "city": city,
        "lat": 18.52,
        "lon": 73.86,
        "auth_events": [],
        "typing_ms_per_char": 200.0,
        **extra,
    }


def _pay(txn, payer, payee, amount, when, session=None, context=None):
    return {
        "txn_id": txn,
        "from_account": payer,
        "to_account": payee,
        "amount": amount,
        "timestamp": when.isoformat(),
        "session": session if session is not None else _session(sid=txn),
        "context": context or {"channel": "UPI_PUSH"},
    }


def _engine_with_history(customer="C1", days=30, **kw):
    engine = UnifiedRiskEngine(**kw)
    events = []
    for d in range(days):
        for k in range(2):
            when = T0 + timedelta(days=d, hours=3 * k)
            events.append(_pay(f"H{customer}{d}-{k}", customer, f"SHOP{k}", 400 + 50 * k, when))
    engine.warm_up(events)
    return engine


def _control(engine, raw, decisive=False, corroboration=3, confidence=1.0, has_strong=True, has_evidence=True):
    return engine._false_positive_control(raw, decisive, corroboration, confidence, has_strong, has_evidence)


# ------------------------------------------------------------- false-positive controls (rule level)
def test_weak_context_alone_never_reaches_step_up():
    score, controls = _control(UnifiedRiskEngine(), 90, has_strong=False, has_evidence=False)
    assert score == 39 and "weak context" in controls[0]


def test_no_fraud_evidence_caps_below_review():
    score, controls = _control(UnifiedRiskEngine(), 92, has_evidence=False)
    assert score == 69 and "no evidence of fraud" in controls[0]


def test_one_engine_alone_cannot_hold_a_payment():
    score, controls = _control(UnifiedRiskEngine(), 95, corroboration=1)
    assert score == 69 and "Only 1 engine" in controls[0]


def test_thin_baseline_steps_up_instead_of_holding():
    score, controls = _control(UnifiedRiskEngine(), 95, confidence=0.2)
    assert score == 69 and "baseline is thin" in controls[0]


def test_decisive_fact_sets_a_floor_and_skips_caps():
    score, controls = _control(UnifiedRiskEngine(), 20, decisive=True, corroboration=1, confidence=0.0)
    assert score == 85 and "Confirmed fact" in controls[0]


def test_bands_follow_config_and_never_auto_decline_by_default():
    engine = UnifiedRiskEngine(config=EngineConfig(step_up_at=30, review_at=60))
    assert engine._band(29, 4) == APPROVE
    assert engine._band(30, 4) == STEP_UP
    assert engine._band(100, 4) == REVIEW


def test_context_codes_are_not_evidence():
    for code in ("BI05", "BI06", "BH01", "BH02", "BH03", "BH04", "SD01", "SD10"):
        assert code not in EVIDENCE_CODES


# ------------------------------------------------------------- end-to-end decisions
def test_new_payee_large_amount_without_evidence_is_never_held():
    engine = _engine_with_history()
    when = T0 + timedelta(days=31)
    added = (when - timedelta(minutes=10)).isoformat()
    d = engine.assess(
        _pay("X1", "C1", "NEW-SELLER", 80_000, when, context={"channel": "UPI_PUSH", "beneficiary_added_at": added})
    )
    assert d.band in (APPROVE, STEP_UP)
    assert d.explanation["action"]
    assert any(r["code"] == "BH01" for r in d.reasons)


def test_new_city_on_known_phone_is_approved():
    engine = _engine_with_history()
    d = engine.assess(_pay("X2", "C1", "SHOP0", 450, T0 + timedelta(days=31), _session(city="Kolkata", sid="X2")))
    assert d.band == APPROVE


def test_known_fraud_payee_is_held_with_decisive_reason():
    engine = _engine_with_history()
    engine.known_fraud.confirm("FRAUDSTER", "confirmed in test")
    d = engine.assess(_pay("X3", "C1", "FRAUDSTER", 5_000, T0 + timedelta(days=31)))
    assert d.band == REVIEW and d.score >= 85
    assert d.reasons[0]["code"] == "BI01" and d.reasons[0]["kind"] == "decisive"


def test_explanation_lists_engines_contributions_and_controls():
    engine = _engine_with_history()
    d = engine.assess(_pay("X4", "C1", "SHOP0", 450, T0 + timedelta(days=31)))
    exp = d.explanation
    assert set(exp["engines"]) == {"mule_network", "session_device", "beneficiary_intent", "behaviour"}
    assert set(d.contributions) == set(exp["model"]["log_odds"])
    assert {"summary", "action", "familiarity", "confidence", "false_positive_controls"} <= set(exp)
    assert d.latency_ms >= 0 and d.model_version


# ------------------------------------------------------------- idempotency and trust boundaries
def test_resent_payment_returns_the_original_decision():
    engine = _engine_with_history()
    p = _pay("DUP", "C1", "SHOP0", 450, T0 + timedelta(days=31))
    first = engine.assess(p, commit=True)
    again = engine.assess(p, commit=True)
    assert again.decision_id == first.decision_id
    assert engine.profiles.customer("C1").n_payments == 61


def test_reused_txn_id_with_different_content_conflicts():
    engine = _engine_with_history()
    engine.assess(_pay("DUP", "C1", "SHOP0", 450, T0 + timedelta(days=31)), commit=True)
    with pytest.raises(TxnConflict):
        engine.assess(_pay("DUP", "C1", "SHOP0", 9_999, T0 + timedelta(days=31)), commit=True)


def test_what_if_never_blocks_or_replaces_the_real_payment():
    engine = _engine_with_history()
    real = _pay("T-REAL", "C1", "SHOP0", 450, T0 + timedelta(days=31))
    engine.assess({**real, "amount": 99_999}, commit=False, source="api")  # staff what-if with other content
    d = engine.assess(real, commit=True, source="ingest")
    assert d.committed and d.amount == 450
    assert engine.profiles.customer("C1").n_payments == 61
    assert engine.store.by_txn("T-REAL").decision_id == d.decision_id


def test_what_if_does_not_change_profiles():
    engine = _engine_with_history()
    before = engine.profiles.customer("C1").n_payments
    engine.assess(_pay("W1", "C1", "SHOP0", 450, T0 + timedelta(days=31)), commit=False)
    assert engine.profiles.customer("C1").n_payments == before


def test_invalid_payment_is_rejected():
    engine = UnifiedRiskEngine()
    with pytest.raises(ValueError):
        engine.assess(_pay("BAD1", "C1", "C1", 10, T0))
    with pytest.raises(ValueError):
        engine.assess(_pay("BAD2", "C1", "C2", -5, T0))


def test_labels_are_kept_only_for_synthetic_sources():
    engine = UnifiedRiskEngine()
    assert engine.assess(_pay("L1", "A", "B", 10, T0), source="ingest", label="fraud").label is None
    assert engine.assess(_pay("L2", "A", "B", 10, T0), source="synthetic", label="fraud").label == "fraud"


# ------------------------------------------------------------- feedback
def test_false_alert_teaches_the_baseline():
    engine = _engine_with_history()
    when = T0 + timedelta(days=31)
    d = engine.assess(_pay("F1", "C1", "NEW-TUTOR", 30_000, when, _session(device="NEW-PHONE", sid="F1")), commit=True)
    engine.feedback(d.decision_id, "FALSE_ALERT", "customer confirmed", "analyst1")
    profile = engine.profiles.customer("C1")
    assert "NEW-TUTOR" in profile.trusted_payees and "NEW-PHONE" in profile.trusted_devices
    assert engine.store.get(d.decision_id).outcome == "FALSE_ALERT"


def test_confirmed_fraud_marks_the_payee_for_every_customer():
    engine = _engine_with_history()
    d = engine.assess(_pay("F2", "C1", "MULE-X", 20_000, T0 + timedelta(days=31)), commit=True)
    engine.feedback(d.decision_id, "CONFIRMED_FRAUD", "", "analyst1")
    assert engine.known_fraud.lookup("MULE-X")["status"] == "confirmed"
    later = engine.assess(_pay("F3", "C9", "MULE-X", 1_000, T0 + timedelta(days=32)))
    assert later.band == REVIEW


def test_feedback_rejects_unknown_outcome():
    engine = _engine_with_history()
    d = engine.assess(_pay("F4", "C1", "SHOP0", 450, T0 + timedelta(days=31)))
    with pytest.raises(ValueError):
        engine.feedback(d.decision_id, "MAYBE", "", "x")


# ------------------------------------------------------------- model
def test_prior_model_contributions_are_exact_log_odds():
    model = RiskModel(dict(PRIOR))
    features = {f: 0.5 for f in FEATURES}
    z = model.intercept + sum(model.contributions(features).values())
    assert model.probability(features) == pytest.approx(1 / (1 + math.exp(-z)), abs=1e-3)
