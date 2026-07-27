"""
MuleCatch Integration Tests
Tests the full detection pipeline end-to-end using synthetic data.
Run: python -m pytest backend/tests/ -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from data.synthetic.generator import build_full_dataset, MuleClusterGenerator
from models.temporal_weighting.smurf_weighting import score_transaction_batch
from models.community_detection.louvain_detector import LouvainClusterDetector
from backend.detection.pipeline import DetectionPipeline, RuleEngine


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def small_dataset():
    return build_full_dataset(num_clusters=2, num_legit_accounts=20)


@pytest.fixture(scope="module")
def single_cluster():
    gen = MuleClusterGenerator()
    return gen.generate(num_mules=6)


# ── Synthetic data tests ───────────────────────────────────────────────────────


def test_dataset_generation(small_dataset):
    assert len(small_dataset["accounts"]) > 0
    assert len(small_dataset["transactions"]) > 0
    assert small_dataset["stats"]["mule_clusters"] == 2
    assert small_dataset["stats"]["suspicious_transactions"] > 0


def test_cluster_has_correct_roles(single_cluster):
    roles = {a["role"] for a in single_cluster["accounts"]}
    assert "SOURCE" in roles
    assert "MULE" in roles
    assert "AGGREGATOR" in roles


def test_cluster_transactions_below_ceiling(single_cluster):
    smurfing = [t for t in single_cluster["transactions"] if t["pattern"] == "SMURFING"]
    assert len(smurfing) > 0
    for t in smurfing:
        assert float(t["amount"]) < 50_000, (
            f"Smurfing txn {t['txn_id']} exceeds ₹50k ceiling"
        )


# ── Smurf-weighting tests ─────────────────────────────────────────────────────


def test_smurf_scores_generated(small_dataset):
    scores = score_transaction_batch(small_dataset["transactions"])
    assert len(scores) > 0


def test_mule_accounts_flagged(small_dataset):
    scores = score_transaction_batch(small_dataset["transactions"])
    # At least some suspicious accounts should be flagged
    flagged = [s for s in scores.values() if s.is_flagged]
    assert len(flagged) > 0, "No accounts flagged — detection broken"


def test_legitimate_accounts_not_all_flagged(small_dataset):
    scores = score_transaction_batch(small_dataset["transactions"])
    legit_accounts = [
        a["account_id"] for a in small_dataset["accounts"] if a["role"] == "LEGITIMATE"
    ]
    legit_flagged = [
        acc_id
        for acc_id in legit_accounts
        if scores.get(acc_id, None) and scores[acc_id].is_flagged
    ]
    # False positive rate should be < 50% even without tuning
    fp_rate = len(legit_flagged) / max(len(legit_accounts), 1)
    assert fp_rate < 0.5, f"False positive rate too high: {fp_rate:.2%}"


def test_reason_codes_generated(small_dataset):
    scores = score_transaction_batch(small_dataset["transactions"])
    flagged = [s for s in scores.values() if s.is_flagged]
    for s in flagged:
        assert len(s.reason_codes) > 0, (
            f"No reason codes for flagged account {s.account_id}"
        )


# ── Community detection tests ─────────────────────────────────────────────────


def test_louvain_detects_clusters(small_dataset):
    detector = LouvainClusterDetector()
    communities = detector.detect_clusters(
        small_dataset["transactions"], small_dataset["accounts"]
    )
    flagged = [c for c in communities if c.is_mule_cluster]
    assert len(flagged) > 0, "Louvain failed to detect any mule clusters"


def test_louvain_community_detection_is_deterministic(small_dataset):
    first = LouvainClusterDetector().detect_clusters(
        small_dataset["transactions"],
        small_dataset["accounts"],
    )
    second = LouvainClusterDetector().detect_clusters(
        small_dataset["transactions"],
        small_dataset["accounts"],
    )

    first_memberships = sorted(sorted(community.accounts) for community in first)
    second_memberships = sorted(sorted(community.accounts) for community in second)
    assert first_memberships == second_memberships


def test_cluster_size_minimum(small_dataset):
    detector = LouvainClusterDetector()
    communities = detector.detect_clusters(
        small_dataset["transactions"], small_dataset["accounts"]
    )
    for c in communities:
        assert c.size >= detector.MIN_CLUSTER_SIZE


# ── Rule engine tests ─────────────────────────────────────────────────────────


def test_rule_engine_young_accounts(small_dataset):
    engine = RuleEngine()
    young_accounts = [
        a for a in small_dataset["accounts"] if a.get("account_age_days", 999) < 7
    ]
    if young_accounts:
        hits = engine.evaluate(young_accounts, small_dataset["transactions"])
        young_with_txns = [
            a
            for a in young_accounts
            if any(
                t["from_account"] == a["account_id"]
                for t in small_dataset["transactions"]
            )
        ]
        if young_with_txns:
            assert any("R01" in " ".join(v) for v in hits.values()), (
                "R01 rule not firing"
            )


# ── End-to-end pipeline test ──────────────────────────────────────────────────


def test_pipeline_generates_alerts(small_dataset):
    pipeline = DetectionPipeline()
    alerts = pipeline.run(small_dataset["transactions"], small_dataset["accounts"])
    assert len(alerts) > 0, "Pipeline produced no alerts"


def test_alerts_have_required_fields(small_dataset):
    pipeline = DetectionPipeline()
    alerts = pipeline.run(small_dataset["transactions"], small_dataset["accounts"])
    for a in alerts:
        assert a.alert_id.startswith("ALT_")
        assert a.severity in ("CRITICAL", "HIGH", "MEDIUM")
        assert 0 <= a.risk_score <= 1
        assert a.account_count >= 3
        assert len(a.nodes) > 0
        assert len(a.reason_codes) > 0


def test_pipeline_latency(small_dataset):
    import time

    pipeline = DetectionPipeline()
    start = time.time()
    pipeline.run(small_dataset["transactions"], small_dataset["accounts"])
    elapsed = time.time() - start
    # Should complete well under 60s for small dataset
    assert elapsed < 30, f"Pipeline too slow: {elapsed:.1f}s"


# ── GNN training tests ──────────────────────────────────────────────────────


def test_gnn_score_populated(small_dataset):
    """GNN should produce non-None scores when torch_geometric is available."""
    pipeline = DetectionPipeline()
    alerts = pipeline.run(small_dataset["transactions"], small_dataset["accounts"])
    gnn_alerts = [a for a in alerts if a.gnn_score is not None]
    # If GNN is available, all alerts should have a score
    if pipeline._gnn_available:
        assert len(gnn_alerts) == len(alerts), (
            f"Only {len(gnn_alerts)}/{len(alerts)} alerts have GNN scores"
        )
        for a in gnn_alerts:
            assert 0.0 <= a.gnn_score <= 1.0


def test_gnn_model_persistence(small_dataset, tmp_path):
    """GNN should save and load model weights."""
    try:
        from models.gnn.gnn_model import GNNScorer
    except ImportError:
        pytest.skip("torch/torch_geometric not available")

    model_path = str(tmp_path / "test_model.pt")
    scorer = GNNScorer(model_path=model_path)
    if scorer.model is None:
        pytest.skip("GNN model not available")

    from models.temporal_weighting.smurf_weighting import score_transaction_batch

    smurf_scores = score_transaction_batch(small_dataset["transactions"])

    # Train and save
    preds, metrics = scorer.train_and_predict(
        small_dataset["accounts"],
        small_dataset["transactions"],
        smurf_scores,
        epochs=10,
    )
    assert scorer.is_trained
    assert metrics.epochs == 10
    assert len(metrics.loss_curve) == 10
    assert metrics.train_accuracy > 0.0
    assert os.path.exists(model_path)

    # Load in a new scorer
    scorer2 = GNNScorer(model_path=model_path)
    assert scorer2.is_trained
    preds2 = scorer2.predict(
        small_dataset["accounts"],
        small_dataset["transactions"],
        smurf_scores,
    )
    assert len(preds2) == len(preds)


# ── GenAI triage tests ──────────────────────────────────────────────────────


def test_pipeline_genai_triage_field(small_dataset):
    """Alerts should have genai_triage=None when no GenAI service is provided."""
    pipeline = DetectionPipeline()
    alerts = pipeline.run(small_dataset["transactions"], small_dataset["accounts"])
    for a in alerts:
        # Without genai_service, triage should be None
        assert a.genai_triage is None


def test_pipeline_with_genai_triage(small_dataset):
    """Pipeline with template GenAI service should set triage on uncertain alerts."""
    try:
        from services.genai_service import GenAIService
    except ImportError:
        pytest.skip("genai_service not importable")

    genai = GenAIService(provider=None)
    pipeline = DetectionPipeline(genai_service=genai)
    alerts = pipeline.run(small_dataset["transactions"], small_dataset["accounts"])
    # Template fallback on uncertain alerts: triage dict with MEDIUM assessment
    uncertain = [a for a in alerts if a.genai_triage is not None]
    for a in uncertain:
        assert a.genai_triage["llm_assessment"] == "MEDIUM"
        assert a.genai_triage["confidence_adjustment"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
