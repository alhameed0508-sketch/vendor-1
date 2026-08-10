"""Tests for the lightweight GNN alternative scorer."""

import pytest

from models.gnn.lightweight_scorer import (
    FEATURE_NAMES,
    LightweightPrediction,
    LightweightScorer,
    _kyc_to_numeric,
    extract_features,
)


def _make_accounts(n=5):
    return [
        {
            "account_id": f"ACC_{i:03d}",
            "account_age_days": 10 + i * 30,
            "kyc_status": "VERIFIED" if i % 2 == 0 else "PENDING",
            "avg_monthly_txn": 8,
        }
        for i in range(n)
    ]


def _make_transactions(accounts):
    txns = []
    for i, acc in enumerate(accounts):
        for j in range(3):
            target = accounts[(i + 1) % len(accounts)]
            txns.append(
                {
                    "txn_id": f"TXN_{i}_{j}",
                    "from_account": acc["account_id"],
                    "to_account": target["account_id"],
                    "amount": 10000 + j * 5000,
                    "timestamp": f"2024-01-0{j + 1}T10:00:00",
                }
            )
    return txns


class TestFeatureExtraction:
    def test_feature_count(self):
        accounts = _make_accounts()
        txns = _make_transactions(accounts)
        ids, matrix = extract_features(accounts, txns)
        assert len(ids) == 5
        assert all(len(row) == len(FEATURE_NAMES) for row in matrix)

    def test_empty_transactions(self):
        accounts = _make_accounts(2)
        ids, matrix = extract_features(accounts, [])
        assert len(ids) == 2
        assert all(len(row) == len(FEATURE_NAMES) for row in matrix)

    def test_kyc_numeric(self):
        assert _kyc_to_numeric("VERIFIED") == 0.0
        assert _kyc_to_numeric("PENDING") == 0.8
        assert _kyc_to_numeric("UNKNOWN") == 0.6


class TestHeuristicPredict:
    def test_heuristic_returns_valid_range(self):
        scorer = LightweightScorer(model_path="/tmp/nonexistent_model.pkl")
        accounts = _make_accounts()
        txns = _make_transactions(accounts)
        preds = scorer.predict(accounts, txns)
        assert len(preds) == 5
        for p in preds:
            assert 0.0 <= p.mule_probability <= 1.0
            assert isinstance(p, LightweightPrediction)

    def test_heuristic_higher_risk_for_new_accounts(self):
        young_acc = [{"account_id": "YOUNG", "account_age_days": 2, "kyc_status": "PENDING"}]
        old_acc = [{"account_id": "OLD", "account_age_days": 300, "kyc_status": "VERIFIED"}]
        txns_y = [
            {
                "txn_id": "T1",
                "from_account": "YOUNG",
                "to_account": "X",
                "amount": 50000,
                "timestamp": "2024-01-01T00:00:00",
            }
        ]
        txns_o = [
            {
                "txn_id": "T2",
                "from_account": "OLD",
                "to_account": "X",
                "amount": 50000,
                "timestamp": "2024-01-01T00:00:00",
            }
        ]

        scorer = LightweightScorer(model_path="/tmp/nonexistent_model.pkl")
        pred_young = scorer.predict(young_acc, txns_y)[0]
        pred_old = scorer.predict(old_acc, txns_o)[0]
        assert pred_young.mule_probability > pred_old.mule_probability


class TestLightweightPrediction:
    def test_frozen(self):
        pred = LightweightPrediction(account_id="A", mule_probability=0.5, feature_importances=())
        with pytest.raises(AttributeError):
            pred.mule_probability = 0.9
