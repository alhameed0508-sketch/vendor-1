"""Tests for the PyOD cold-start anomaly tier."""

from models.anomaly.unsupervised_scorer import UnsupervisedAccountScorer


def test_unsupervised_scorer_skips_tiny_peer_group():
    scorer = UnsupervisedAccountScorer()
    accounts = [{"account_id": f"A{i}"} for i in range(5)]
    assert scorer.score(accounts, []) == {}


def test_unsupervised_scorer_returns_bounded_peer_scores():
    scorer = UnsupervisedAccountScorer(contamination=0.1)
    accounts = [
        {
            "account_id": f"A{i}",
            "account_age_days": 200 + i,
            "kyc_status": "VERIFIED",
        }
        for i in range(25)
    ]
    accounts[-1]["account_age_days"] = 0
    accounts[-1]["kyc_status"] = "PENDING"
    transactions = [
        {
            "from_account": "A24",
            "to_account": f"A{i}",
            "amount": 49000,
        }
        for i in range(20)
    ]

    predictions = scorer.score(accounts, transactions)

    assert len(predictions) == len(accounts)
    assert all(0 <= item.anomaly_score <= 1 for item in predictions.values())
    assert any(item.is_anomaly for item in predictions.values())
