"""
Pipeline hardening tests: indexed rule engine, row-level rejection of malformed
transactions, and sampled betweenness (docs/buildx/05-evaluation.md 7.5 and 7.6).
"""

import copy
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from backend.detection.pipeline import DetectionPipeline, RuleEngine
from backend.detection.validation import validate_transactions
from data.synthetic.generator import build_adversarial_dataset


@pytest.fixture(scope="module")
def dataset():
    random.seed(11)
    return build_adversarial_dataset(num_clusters=3, num_legit_accounts=60, num_adversarial=20)


# ── Indexed rule engine must match the naive full-scan result ─────────────────


def _naive_rule_hits(accounts, transactions):
    results = {}
    thresholds = RuleEngine().thresholds
    for acc in accounts:
        hits = [f"{code}: {desc}" for code, desc, fn in RuleEngine.RULES if fn(acc, transactions, thresholds)]
        if hits:
            results[acc["account_id"]] = hits
    return results


def test_indexed_rules_match_full_scan(dataset):
    expected = _naive_rule_hits(dataset["accounts"], dataset["transactions"])
    assert RuleEngine().evaluate(dataset["accounts"], dataset["transactions"]) == expected


def test_indexed_rules_flag_shared_device():
    accounts = [{"account_id": "A"}, {"account_id": "B"}, {"account_id": "C"}]
    txns = [
        {
            "txn_id": "1",
            "from_account": "A",
            "to_account": "C",
            "amount": 10,
            "timestamp": "2026-01-01T10:00:00",
            "device_id": "D1",
        },
        {
            "txn_id": "2",
            "from_account": "B",
            "to_account": "C",
            "amount": 10,
            "timestamp": "2026-01-01T11:00:00",
            "device_id": "D1",
        },
    ]
    hits = RuleEngine().evaluate(accounts, txns)
    assert any(h.startswith("R18") for h in hits["A"])
    assert any(h.startswith("R18") for h in hits["B"])
    assert "C" not in hits or not any(h.startswith("R18") for h in hits["C"])


# ── Row-level rejection of malformed input ────────────────────────────────────


def _row(**over):
    base = {
        "txn_id": "T1",
        "from_account": "A",
        "to_account": "B",
        "amount": 100.0,
        "timestamp": "2026-01-01T10:00:00",
    }
    return {**base, **over}


def _without(key):
    row = _row()
    del row[key]
    return row


@pytest.mark.parametrize(
    "bad_row, reason_fragment",
    [
        (_row(amount="abc"), "amount"),
        (_row(amount=-500.0), "amount"),
        (_row(amount=float("nan")), "amount"),
        (_without("amount"), "amount"),
        (_without("timestamp"), "timestamp"),
        (_row(timestamp="yesterday"), "timestamp"),
        (_without("to_account"), "to_account"),
        (_row(from_account=""), "from_account"),
    ],
)
def test_bad_rows_rejected_with_reason(bad_row, reason_fragment):
    good = _row(txn_id="T2")
    valid, rejected = validate_transactions([bad_row, good])
    assert valid == [good]
    assert len(rejected) == 1
    assert rejected[0].index == 0
    assert reason_fragment in rejected[0].reason


def test_duplicate_txn_ids_keep_first_only():
    first, dup = _row(), _row(amount=999.0)
    valid, rejected = validate_transactions([first, dup])
    assert valid == [first]
    assert "duplicate" in rejected[0].reason


def test_validation_does_not_mutate_input():
    rows = [_row(), _row(txn_id="T2", amount="abc")]
    snapshot = copy.deepcopy(rows)
    validate_transactions(rows)
    assert rows == snapshot


def test_accepts_datetime_timestamps():
    from datetime import datetime

    valid, rejected = validate_transactions([_row(timestamp=datetime(2026, 1, 1, 10))])
    assert len(valid) == 1 and not rejected


def test_pipeline_survives_malformed_batch_and_reports_rejections(dataset):
    txns = copy.deepcopy(dataset["transactions"])
    txns[0]["amount"] = "abc"
    txns[1].pop("timestamp")
    txns[2]["timestamp"] = "yesterday"
    txns[3].pop("to_account")
    txns[4]["amount"] = -5.0
    txns.extend(copy.deepcopy(txns[10:15]))  # duplicate ids

    pipeline = DetectionPipeline()
    alerts = pipeline.run(txns, dataset["accounts"])

    assert isinstance(alerts, list)
    assert len(pipeline.last_rejections) == 10
    assert {r.index for r in pipeline.last_rejections} >= {0, 1, 2, 3, 4}


def test_pipeline_clean_batch_has_no_rejections(dataset):
    pipeline = DetectionPipeline()
    pipeline.run(dataset["transactions"], dataset["accounts"])
    assert pipeline.last_rejections == ()


# ── Sampled betweenness on large graphs ───────────────────────────────────────


def test_large_graph_centrality_is_sampled_and_deterministic():
    import networkx as nx

    from models.community_detection.louvain_detector import BETWEENNESS_EXACT_MAX_NODES, LouvainClusterDetector

    graph = nx.gnm_random_graph(BETWEENNESS_EXACT_MAX_NODES + 50, 1500, seed=3)
    nx.set_edge_attributes(graph, 1.0, "weight")

    def centrality():
        detector = LouvainClusterDetector()
        detector._graph = graph
        return detector.compute_centrality()

    first, second = centrality(), centrality()
    assert first == second
    assert set(first) == set(graph.nodes)
