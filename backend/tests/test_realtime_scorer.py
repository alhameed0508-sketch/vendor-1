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


# ── Shared-state safety ───────────────────────────────────────────────────────


def _payment(txn_id="T1"):
    return {
        "txn_id": txn_id,
        "from_account": "A",
        "to_account": "B",
        "amount": 100,
        "timestamp": datetime(2026, 1, 1).isoformat(),
    }


def test_commit_false_does_not_change_history():
    scorer = RealtimeScorer([], [])
    scorer.score_payment(_payment(), commit=False)
    assert scorer.history_size == 0


def test_duplicate_txn_id_not_added_twice():
    scorer = RealtimeScorer([], [])
    scorer.score_payment(_payment())
    scorer.score_payment(_payment())
    assert scorer.history_size == 1


def test_reused_txn_id_with_different_content_is_rejected():
    scorer = RealtimeScorer([], [])
    scorer.score_payment(_payment("T9"))
    other = {**_payment("T9"), "to_account": "C"}
    with pytest.raises(ValueError):
        scorer.score_payment(other)
    with pytest.raises(ValueError):
        scorer.score_payment(other, commit=False)


def test_identical_replay_is_scored_not_duplicated():
    scorer = RealtimeScorer([], [])
    first = scorer.score_payment(_payment("T8"))
    again = scorer.score_payment(_payment("T8"))
    assert again.decision == first.decision
    assert scorer.history_size == 1


# ── Merchant exemption ────────────────────────────────────────────────────────


def _first_flagged(split):
    scorer = _scorer(split)
    for raw in _strip_labels(split[2]):
        result = scorer.score_payment(raw, commit=False)
        if result.decision == "FLAG":
            return raw, result
    pytest.fail("expected a flagged payment")


def test_ring_made_only_of_merchants_is_not_flagged(split):
    accounts, history, _ = split
    txn, flagged = _first_flagged(split)
    merchants = set(flagged.ring_members)
    marked = [{**a, "account_type": "MERCHANT"} if a["account_id"] in merchants else a for a in _strip_labels(accounts)]
    scorer = RealtimeScorer(marked, _strip_labels(history))
    assert scorer.score_payment(txn, commit=False).decision == "PASS"


def test_one_merchant_in_a_ring_does_not_clear_it(split):
    accounts, history, _ = split
    txn, flagged = _first_flagged(split)
    one = flagged.ring_members[0]
    marked = [{**a, "account_type": "MERCHANT"} if a["account_id"] == one else a for a in _strip_labels(accounts)]
    scorer = RealtimeScorer(marked, _strip_labels(history))
    assert scorer.score_payment(txn, commit=False).decision == "FLAG"


# ── Community refresh (latency) ───────────────────────────────────────────────


@pytest.fixture
def louvain_calls(monkeypatch):
    from models.community_detection.louvain_detector import LouvainClusterDetector

    calls = []
    original = LouvainClusterDetector.detect_clusters

    def counting(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(LouvainClusterDetector, "detect_clusters", counting)
    return calls


def _chain(n):
    base = datetime(2026, 1, 1)
    return [
        {
            "txn_id": f"R{i}",
            "from_account": "A",
            "to_account": "B",
            "amount": 1000,
            "timestamp": (base + timedelta(minutes=i)).isoformat(),
        }
        for i in range(n)
    ]


def test_communities_are_reused_between_refreshes(louvain_calls):
    scorer = RealtimeScorer([], [], community_refresh_every=5)
    for txn in _chain(5):
        scorer.score_payment(txn)
    assert len(louvain_calls) == 1


def test_communities_refresh_after_n_commits(louvain_calls):
    scorer = RealtimeScorer([], [], community_refresh_every=5)
    for txn in _chain(11):
        scorer.score_payment(txn)
    assert len(louvain_calls) == 3  # payments 1, 6 and 11


def test_refresh_every_one_recomputes_each_time(louvain_calls):
    scorer = RealtimeScorer([], [], community_refresh_every=1)
    for txn in _chain(4):
        scorer.score_payment(txn)
    assert len(louvain_calls) == 4


def test_uncommitted_scoring_never_writes_the_shared_cache(louvain_calls):
    scorer = RealtimeScorer([], [], community_refresh_every=3)
    for txn in _chain(4):
        scorer.score_payment(txn, commit=False)
    assert len(louvain_calls) == 4  # each call computes its own partition
    assert scorer._cached is None


def test_uncommitted_payment_cannot_replace_a_trusted_partition():
    scorer = RealtimeScorer([], [], community_refresh_every=50)
    chain = _chain(3)
    for txn in chain:
        scorer.score_payment(txn)
    trusted = scorer._cached
    scorer.score_payment({**chain[0], "txn_id": "EVIL", "to_account": "B2"}, commit=False)
    assert scorer._cached is trusted


def test_payment_with_unseen_account_forces_a_fresh_partition(louvain_calls):
    scorer = RealtimeScorer([], [], community_refresh_every=50)
    for txn in _chain(3):
        scorer.score_payment(txn)
    assert len(louvain_calls) == 1
    scorer.score_payment(_chain(4)[3])  # both accounts already seen
    assert len(louvain_calls) == 1
    scorer.score_payment({**_chain(5)[4], "from_account": "NEW1", "to_account": "NEW2"})  # unseen
    assert len(louvain_calls) == 2


def test_rejects_non_positive_refresh_interval():
    with pytest.raises(ValueError):
        RealtimeScorer([], [], community_refresh_every=0)


# ── Evasion robustness ────────────────────────────────────────────────────────


def _mule_recall(accounts, history, live):
    role = {a["account_id"]: a.get("role") for a in accounts}
    mule_roles = {"SOURCE", "MULE", "AGGREGATOR"}
    scorer = RealtimeScorer(_strip_labels(accounts), _strip_labels(history))
    hits = total = 0
    for raw in live:
        if role.get(raw["from_account"]) in mule_roles and role.get(raw["to_account"]) in mule_roles:
            total += 1
            hits += scorer.score_payment(_strip_labels([raw])[0]).decision == "FLAG"
    return hits / total


def test_small_decoy_payments_do_not_hide_a_ring(dataset):
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "evaluation"))
    from evasion_playbooks import noise

    role = {a["account_id"]: a.get("role") for a in dataset["accounts"]}
    is_mule = {acc: r in {"SOURCE", "MULE", "AGGREGATOR"} for acc, r in role.items()}
    txns = sorted(noise(dataset["transactions"], is_mule, random.Random(7)), key=lambda t: t["timestamp"])
    live, history = txns[::5], [t for i, t in enumerate(txns) if i % 5]
    assert _mule_recall(dataset["accounts"], history, live) >= 0.5


def test_dust_payment_is_still_scored(split):
    scorer = _scorer(split)
    txn = {**_strip_labels(split[2])[0], "txn_id": "DUST1", "amount": 50}
    assert scorer.score_payment(txn, commit=False).decision in {"FLAG", "PASS"}


def test_slowed_down_ring_is_still_found(dataset):
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "evaluation"))
    from evasion_playbooks import slow_drip

    role = {a["account_id"]: a.get("role") for a in dataset["accounts"]}
    is_mule = {acc: r in {"SOURCE", "MULE", "AGGREGATOR"} for acc, r in role.items()}
    txns = sorted(slow_drip(dataset["transactions"], is_mule, random.Random(7)), key=lambda t: t["timestamp"])
    live, history = txns[::5], [t for i, t in enumerate(txns) if i % 5]
    assert _mule_recall(dataset["accounts"], history, live) >= 0.5


def test_long_window_engine_sees_slow_consolidation():
    from models.temporal_weighting.smurf_weighting import SmurfWeightingEngine, Transaction

    base = datetime(2026, 1, 1)
    incoming = [Transaction(f"I{i}", f"S{i}", "M", 20000, base + timedelta(hours=i), "", "") for i in range(3)]
    outgoing = [Transaction("O1", "M", "A", 59000, base + timedelta(hours=22), "", "")]
    short = SmurfWeightingEngine().score_account("M", outgoing, incoming)
    long = SmurfWeightingEngine(consolidation_hours=36).score_account("M", outgoing, incoming)
    assert short.consolidation_score == 0.0
    assert long.consolidation_score > 0.5
