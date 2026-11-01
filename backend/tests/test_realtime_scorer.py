"""Per-payment real-time scoring: ring detection, bystander safety, latency."""

import random
from datetime import datetime, timedelta

import pytest
from services.realtime_scorer import RealtimeScorer

from data.synthetic.generator import build_adversarial_dataset

LABEL_FIELDS = ("role", "high_risk", "cluster_id", "is_suspicious", "pattern")


def _strip_labels(rows):
    return [{k: v for k, v in r.items() if k not in LABEL_FIELDS} for r in rows]


@pytest.fixture(scope="module")
def dataset():
    random.seed(7)
    return build_adversarial_dataset(num_clusters=3, num_legit_accounts=60, num_adversarial=10)


@pytest.fixture(scope="module")
def split(dataset):
    txns = sorted(dataset["transactions"], key=lambda t: t["timestamp"])
    live = txns[::5]
    history = [t for i, t in enumerate(txns) if i % 5]
    return dataset["accounts"], history, live


def _scorer(split):
    accounts, history, _ = split
    return RealtimeScorer(_strip_labels(accounts), _strip_labels(history))


def test_result_shape_and_latency(split):
    scorer = _scorer(split)
    txn = _strip_labels(split[2])[0]
    result = scorer.score_payment(txn)
    assert result.txn_id == txn["txn_id"]
    assert 0.0 <= result.risk_score <= 1.0
    assert result.decision in {"FLAG", "PASS"}
    assert result.latency_ms < 500


def test_does_not_mutate_input(split):
    scorer = _scorer(split)
    txn = _strip_labels(split[2])[0]
    before = dict(txn)
    scorer.score_payment(txn)
    assert txn == before


def test_history_grows_with_each_payment(split):
    scorer = _scorer(split)
    start = scorer.history_size
    scorer.score_payment(_strip_labels(split[2])[0])
    assert scorer.history_size == start + 1


def test_flags_mule_payments_and_spares_most_genuine(split):
    accounts, _, live = split
    role = {a["account_id"]: a.get("role") for a in accounts}
    mule_roles = {"SOURCE", "MULE", "AGGREGATOR"}
    scorer = _scorer(split)

    flagged_mule = total_mule = flagged_genuine = total_genuine = 0
    for raw in live:
        is_mule = role.get(raw["from_account"]) in mule_roles and role.get(raw["to_account"]) in mule_roles
        result = scorer.score_payment(_strip_labels([raw])[0])
        if is_mule:
            total_mule += 1
            flagged_mule += result.decision == "FLAG"
        elif role.get(raw["from_account"]) not in mule_roles and role.get(raw["to_account"]) not in mule_roles:
            total_genuine += 1
            flagged_genuine += result.decision == "FLAG"

    assert total_mule > 0 and total_genuine > 0
    assert flagged_mule / total_mule >= 0.5
    assert flagged_genuine / total_genuine <= 0.1


def test_flagged_payment_reports_ring_case(split):
    scorer = _scorer(split)
    flagged = [r for r in (scorer.score_payment(t) for t in _strip_labels(split[2])) if r.decision == "FLAG"]
    assert flagged, "expected at least one flagged payment"
    for r in flagged:
        assert r.case_id is not None
        assert len(r.ring_members) >= 3
        assert r.reasons


def test_unknown_accounts_pass_without_error():
    scorer = RealtimeScorer([], [])
    result = scorer.score_payment(
        {
            "txn_id": "T1",
            "from_account": "A",
            "to_account": "B",
            "amount": 100,
            "timestamp": datetime(2026, 1, 1).isoformat(),
        }
    )
    assert result.decision == "PASS"
    assert result.case_id is None


def test_window_bounds_history():
    scorer = RealtimeScorer([], [], max_window=5)
    base = datetime(2026, 1, 1)
    for i in range(12):
        scorer.score_payment(
            {
                "txn_id": f"T{i}",
                "from_account": f"A{i}",
                "to_account": f"B{i}",
                "amount": 100,
                "timestamp": (base + timedelta(minutes=i)).isoformat(),
            }
        )
    assert scorer.history_size == 5


def test_rejects_invalid_payment():
    scorer = RealtimeScorer([], [])
    with pytest.raises(ValueError):
        scorer.score_payment({"txn_id": "T1", "from_account": "A"})


# ── Label-leak regression: alert roles must come from flow, not labels ─────────


def test_infer_role_from_money_flow():
    from detection.pipeline import _infer_role

    flows = [
        {"from_account": "S", "to_account": "M", "amount": 100},
        {"from_account": "M", "to_account": "A", "amount": 90},
        {"from_account": "X", "to_account": "A", "amount": 90},
        {"from_account": "Y", "to_account": "A", "amount": 90},
    ]
    assert _infer_role("S", flows) == "SOURCE"
    assert _infer_role("M", flows) == "MULE"
    assert _infer_role("A", flows) == "AGGREGATOR"
    assert _infer_role("Z", flows) == "UNKNOWN"


def test_alert_nodes_ignore_ground_truth_role(split):
    from detection.pipeline import DetectionPipeline

    accounts, history, _ = split
    mislabeled = [{**a, "role": "LEGITIMATE"} for a in _strip_labels(accounts)]
    alerts = DetectionPipeline().run(_strip_labels(history), mislabeled)
    assert alerts
    assert any(n.role in {"SOURCE", "MULE", "AGGREGATOR"} for a in alerts for n in a.nodes)
    assert all(e.pattern == "OBSERVED" for a in alerts for e in a.edges)
