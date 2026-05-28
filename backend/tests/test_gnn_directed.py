"""
Tests for directed-edge GNN with edge features.

Covers:
  - Directed vs undirected edge construction in ``build_graph_data``
  - Edge feature computation (amount, timestamp, payment type)
  - Model training with edge features
  - Backward compatibility (edge_attr=None)
  - Prediction differences with/without edge features
  - Edge cases: no edges, single edge, self-loops
"""

import pytest
import torch
import numpy as np

from models.gnn.gnn_model import (
    MuleCatchGNN,
    build_graph_data,
    GNNScorer,
    GNNPrediction,
    _parse_timestamp,
    _PAYMENT_TYPE_ENCODING,
    HAS_TORCH_GEOMETRIC,
)

pytestmark = pytest.mark.skipif(
    not HAS_TORCH_GEOMETRIC,
    reason="torch_geometric not installed",
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_accounts(n: int = 4, roles=None):
    """Create ``n`` test account dicts.

    ``roles`` is an optional list of roles aligned with accounts.
    """
    roles = roles or (["MULE"] * (n // 2) + ["LEGIT"] * (n - n // 2))
    return [
        {
            "account_id": f"ACC_{i:03d}",
            "account_age_days": 30 + i * 60,
            "avg_monthly_txn": 10 + i * 5,
            "kyc_status": "VERIFIED" if i % 2 == 0 else "PENDING",
            "role": roles[i] if i < len(roles) else "LEGIT",
        }
        for i in range(n)
    ]


def _make_transactions(accounts, payment_type="UPI"):
    """Create a ring of transactions between consecutive accounts."""
    txns = []
    for i, acc in enumerate(accounts):
        target = accounts[(i + 1) % len(accounts)]
        txns.append(
            {
                "txn_id": f"TXN_{i}",
                "from_account": acc["account_id"],
                "to_account": target["account_id"],
                "amount": 50000 + i * 10000,
                "timestamp": f"2024-01-0{min(i + 1, 9)}T10:00:00",
                "payment_type": payment_type,
            }
        )
    return txns


# ---------------------------------------------------------------------------
# 1. Directed edges: no reverse edges
# ---------------------------------------------------------------------------

class TestDirectedEdges:
    """build_graph_data with directed=True should NOT add reverse edges."""

    def test_directed_edge_count(self):
        accounts = _make_accounts(4)
        txns = _make_transactions(accounts)
        data, ids = build_graph_data(accounts, txns, directed=True)

        # 4 transactions in the ring -> 4 directed edges (no reverse)
        assert data.edge_index.shape[1] == len(txns)

    def test_undirected_edge_count(self):
        accounts = _make_accounts(4)
        txns = _make_transactions(accounts)
        data, ids = build_graph_data(accounts, txns, directed=False)

        # 4 transactions * 2 (reverse) = 8 edges
        assert data.edge_index.shape[1] == len(txns) * 2

    def test_directed_edges_only_forward(self):
        """Each directed edge should go from src->dst, never dst->src."""
        accounts = _make_accounts(3)
        # Single transaction: ACC_000 -> ACC_001
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
            }
        ]
        data, ids = build_graph_data(accounts, txns, directed=True)

        src_nodes = data.edge_index[0].tolist()
        dst_nodes = data.edge_index[1].tolist()

        # Should have exactly one edge: 0 -> 1
        assert len(src_nodes) == 1
        assert src_nodes[0] == 0
        assert dst_nodes[0] == 1

    def test_undirected_adds_reverse(self):
        """Undirected mode should add both forward and reverse edges."""
        accounts = _make_accounts(3)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
            }
        ]
        data, ids = build_graph_data(accounts, txns, directed=False)

        edges = set()
        for i in range(data.edge_index.shape[1]):
            edges.add((data.edge_index[0, i].item(), data.edge_index[1, i].item()))

        assert (0, 1) in edges
        assert (1, 0) in edges
        assert len(edges) == 2

    def test_default_is_directed(self):
        """Default behaviour should be directed."""
        accounts = _make_accounts(3)
        txns = _make_transactions(accounts)
        data_default, _ = build_graph_data(accounts, txns)
        data_directed, _ = build_graph_data(accounts, txns, directed=True)

        assert data_default.edge_index.shape == data_directed.edge_index.shape


# ---------------------------------------------------------------------------
# 2. Edge feature computation
# ---------------------------------------------------------------------------

class TestEdgeFeatures:
    """Verify that edge_attr is correctly computed."""

    def test_edge_attr_shape(self):
        accounts = _make_accounts(4)
        txns = _make_transactions(accounts)
        data, _ = build_graph_data(accounts, txns, directed=True)

        assert hasattr(data, "edge_attr")
        assert data.edge_attr.shape == (len(txns), 3)

    def test_amount_normalisation(self):
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 50000,
                "timestamp": "2024-01-01T00:00:00",
            }
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        # 50000 / 100000 = 0.5
        assert abs(data.edge_attr[0, 0].item() - 0.5) < 1e-6

    def test_amount_capped_at_one(self):
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 200000,
                "timestamp": "2024-01-01T00:00:00",
            }
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        assert data.edge_attr[0, 0].item() == 1.0

    def test_timestamp_normalisation(self):
        """With two edges at different times, timestamps should span [0, 1]."""
        accounts = _make_accounts(3)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
            },
            {
                "txn_id": "T2",
                "from_account": "ACC_001",
                "to_account": "ACC_002",
                "amount": 10000,
                "timestamp": "2024-01-02T00:00:00",
            },
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        ts_col = data.edge_attr[:, 1].tolist()
        assert min(ts_col) == pytest.approx(0.0)
        assert max(ts_col) == pytest.approx(1.0)

    def test_single_timestamp_normalises_to_zero(self):
        """When all timestamps are identical, they should all be 0.0."""
        accounts = _make_accounts(3)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
            },
            {
                "txn_id": "T2",
                "from_account": "ACC_001",
                "to_account": "ACC_002",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
            },
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        assert data.edge_attr[0, 1].item() == pytest.approx(0.0)
        assert data.edge_attr[1, 1].item() == pytest.approx(0.0)

    def test_payment_type_upi(self):
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
                "payment_type": "UPI",
            }
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        assert data.edge_attr[0, 2].item() == pytest.approx(0.0)

    def test_payment_type_imps(self):
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
                "payment_type": "IMPS",
            }
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        assert data.edge_attr[0, 2].item() == pytest.approx(0.5)

    def test_payment_type_neft(self):
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
                "payment_type": "NEFT",
            }
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        assert data.edge_attr[0, 2].item() == pytest.approx(1.0)

    def test_payment_type_rtgs(self):
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
                "payment_type": "RTGS",
            }
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        assert data.edge_attr[0, 2].item() == pytest.approx(1.0)

    def test_payment_type_default(self):
        """Missing or unknown payment type defaults to 0.5."""
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
            }
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        assert data.edge_attr[0, 2].item() == pytest.approx(0.5)

    def test_undirected_edge_attr_duplicated(self):
        """In undirected mode, edge_attr should be duplicated for reverse edges."""
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 30000,
                "timestamp": "2024-01-01T00:00:00",
                "payment_type": "UPI",
            }
        ]
        data, _ = build_graph_data(accounts, txns, directed=False)
        assert data.edge_attr.shape[0] == 2
        # Both edges should have same features
        assert torch.allclose(data.edge_attr[0], data.edge_attr[1])


# ---------------------------------------------------------------------------
# 3. Model training with edge features
# ---------------------------------------------------------------------------

class TestModelTrainingWithEdgeFeatures:
    """Verify the model trains and converges with edge features."""

    def test_train_with_edge_features(self):
        accounts = _make_accounts(6, roles=["MULE", "MULE", "MULE", "LEGIT", "LEGIT", "LEGIT"])
        txns = _make_transactions(accounts, payment_type="UPI")
        data, ids = build_graph_data(accounts, txns, directed=True)

        model = MuleCatchGNN(in_channels=8, hidden=32, out_channels=2)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

        model.train()
        initial_loss = None
        for epoch in range(20):
            optimizer.zero_grad()
            logits, _ = model(data.x, data.edge_index, data.edge_attr)
            loss = torch.nn.functional.cross_entropy(logits, data.y)
            if epoch == 0:
                initial_loss = loss.item()
            loss.backward()
            optimizer.step()

        final_loss = loss.item()
        # Loss should decrease over training
        assert final_loss < initial_loss

    def test_train_produces_embeddings(self):
        accounts = _make_accounts(4)
        txns = _make_transactions(accounts)
        data, _ = build_graph_data(accounts, txns, directed=True)

        model = MuleCatchGNN(in_channels=8, hidden=32, out_channels=2)
        model.eval()
        with torch.no_grad():
            logits, embeddings = model(data.x, data.edge_index, data.edge_attr)

        assert logits.shape == (4, 2)
        assert embeddings.shape == (4, 16)  # hidden // 2 = 32 // 2 = 16


# ---------------------------------------------------------------------------
# 4. Backward compatibility (edge_attr=None)
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """The model MUST work identically when edge_attr is None."""

    def test_forward_without_edge_attr(self):
        """Model should produce valid output with edge_attr=None."""
        accounts = _make_accounts(4)
        txns = _make_transactions(accounts)
        data, _ = build_graph_data(accounts, txns, directed=True)

        model = MuleCatchGNN(in_channels=8, hidden=32, out_channels=2)
        model.eval()
        with torch.no_grad():
            logits, emb = model(data.x, data.edge_index, edge_attr=None)

        assert logits.shape == (4, 2)
        assert emb.shape[0] == 4
        # Probabilities should be valid
        probs = torch.softmax(logits, dim=1)
        assert torch.all(probs >= 0.0)
        assert torch.all(probs <= 1.0)

    def test_forward_default_no_edge_attr(self):
        """Forward with only (x, edge_index) should work (default param)."""
        model = MuleCatchGNN(in_channels=8, hidden=32, out_channels=2)
        x = torch.randn(3, 8)
        edge_index = torch.tensor([[0, 1], [1, 2]], dtype=torch.long).t()

        model.eval()
        with torch.no_grad():
            logits, emb = model(x, edge_index)

        assert logits.shape == (3, 2)

    def test_scorer_train_without_edge_features(self):
        """GNNScorer.train should work without edge features in transactions."""
        accounts = _make_accounts(4)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
            }
        ]
        scorer = GNNScorer(model_path="/tmp/test_gnn_bc.pt")
        losses = scorer.train(accounts, txns, {}, epochs=5)
        assert isinstance(losses, list)
        assert len(losses) == 5

    def test_scorer_predict_without_edge_features(self):
        """GNNScorer.predict should work without edge features."""
        accounts = _make_accounts(4)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 10000,
            }
        ]
        scorer = GNNScorer(model_path="/tmp/test_gnn_bc_pred.pt")
        preds = scorer.predict(accounts, txns, {})
        assert len(preds) == 4
        for p in preds:
            assert isinstance(p, GNNPrediction)
            assert 0.0 <= p.mule_probability <= 1.0


# ---------------------------------------------------------------------------
# 5. Predictions change with edge features
# ---------------------------------------------------------------------------

class TestEdgeFeaturesAffectPredictions:
    """Verify that edge features actually influence model output."""

    def test_predictions_differ_with_vs_without_edge_attr(self):
        """Output should differ when edge_attr is provided vs None."""
        accounts = _make_accounts(4)
        txns = _make_transactions(accounts)
        data, _ = build_graph_data(accounts, txns, directed=True)

        model = MuleCatchGNN(in_channels=8, hidden=32, out_channels=2)
        model.eval()

        with torch.no_grad():
            logits_with, _ = model(data.x, data.edge_index, data.edge_attr)
            logits_without, _ = model(data.x, data.edge_index, edge_attr=None)

        # The logits should differ (edge encoder adds signal)
        assert not torch.allclose(logits_with, logits_without, atol=1e-6)

    def test_different_amounts_produce_different_predictions(self):
        """Changing transaction amounts should change model output."""
        accounts = _make_accounts(3)

        txns_small = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 100,
                "timestamp": "2024-01-01T00:00:00",
                "payment_type": "UPI",
            }
        ]
        txns_large = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 99000,
                "timestamp": "2024-01-01T00:00:00",
                "payment_type": "UPI",
            }
        ]

        data_small, _ = build_graph_data(accounts, txns_small, directed=True)
        data_large, _ = build_graph_data(accounts, txns_large, directed=True)

        model = MuleCatchGNN(in_channels=8, hidden=32, out_channels=2)
        model.eval()

        with torch.no_grad():
            logits_small, _ = model(data_small.x, data_small.edge_index, data_small.edge_attr)
            logits_large, _ = model(data_large.x, data_large.edge_index, data_large.edge_attr)

        assert not torch.allclose(logits_small, logits_large, atol=1e-6)


# ---------------------------------------------------------------------------
# 6. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: no edges, single edge, self-loops."""

    def test_no_edges(self):
        """Graph with no transactions should still work."""
        accounts = _make_accounts(3)
        data, ids = build_graph_data(accounts, [], directed=True)

        assert data.edge_index.shape == (2, 0)
        assert data.edge_attr.shape == (0, 3)

        model = MuleCatchGNN(in_channels=8, hidden=32, out_channels=2)
        model.eval()
        with torch.no_grad():
            logits, emb = model(data.x, data.edge_index, data.edge_attr)

        assert logits.shape == (3, 2)

    def test_single_edge(self):
        """Graph with exactly one transaction."""
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_001",
                "amount": 25000,
                "timestamp": "2024-06-15T12:00:00",
                "payment_type": "IMPS",
            }
        ]
        data, ids = build_graph_data(accounts, txns, directed=True)

        assert data.edge_index.shape == (2, 1)
        assert data.edge_attr.shape == (1, 3)
        # Amount: 25000/100000 = 0.25
        assert data.edge_attr[0, 0].item() == pytest.approx(0.25)
        # Single timestamp -> normalised to 0.0
        assert data.edge_attr[0, 1].item() == pytest.approx(0.0)
        # IMPS -> 0.5
        assert data.edge_attr[0, 2].item() == pytest.approx(0.5)

        model = MuleCatchGNN(in_channels=8, hidden=32, out_channels=2)
        model.eval()
        with torch.no_grad():
            logits, _ = model(data.x, data.edge_index, data.edge_attr)
        assert logits.shape == (2, 2)

    def test_self_loop(self):
        """Transaction from an account to itself (self-loop)."""
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "ACC_000",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
            }
        ]
        data, ids = build_graph_data(accounts, txns, directed=True)

        # Self-loop: src == dst == 0
        assert data.edge_index[0, 0].item() == 0
        assert data.edge_index[1, 0].item() == 0
        assert data.edge_attr.shape == (1, 3)

        model = MuleCatchGNN(in_channels=8, hidden=32, out_channels=2)
        model.eval()
        with torch.no_grad():
            logits, _ = model(data.x, data.edge_index, data.edge_attr)
        assert logits.shape == (2, 2)

    def test_transaction_with_unknown_account_skipped(self):
        """Transactions referencing unknown accounts should be skipped."""
        accounts = _make_accounts(2)
        txns = [
            {
                "txn_id": "T1",
                "from_account": "ACC_000",
                "to_account": "UNKNOWN_ACC",
                "amount": 10000,
                "timestamp": "2024-01-01T00:00:00",
            }
        ]
        data, _ = build_graph_data(accounts, txns, directed=True)
        assert data.edge_index.shape[1] == 0
        assert data.edge_attr.shape[0] == 0

    def test_no_accounts(self):
        """Empty accounts list should produce empty graph."""
        data, ids = build_graph_data([], [], directed=True)
        assert data.x.shape[0] == 0
        assert data.edge_index.shape[1] == 0
        assert len(ids) == 0


# ---------------------------------------------------------------------------
# 7. Timestamp parsing
# ---------------------------------------------------------------------------

class TestTimestampParsing:
    """Verify _parse_timestamp handles various formats."""

    def test_iso_string(self):
        ts = _parse_timestamp("2024-01-01T00:00:00")
        assert ts > 0

    def test_iso_string_with_z(self):
        ts = _parse_timestamp("2024-01-01T00:00:00Z")
        assert ts > 0

    def test_numeric_epoch(self):
        ts = _parse_timestamp(1704067200)
        assert ts == 1704067200.0

    def test_float_epoch(self):
        ts = _parse_timestamp(1704067200.5)
        assert ts == 1704067200.5

    def test_invalid_string_returns_zero(self):
        ts = _parse_timestamp("not-a-timestamp")
        assert ts == 0.0

    def test_none_returns_zero(self):
        ts = _parse_timestamp(None)
        assert ts == 0.0


# ---------------------------------------------------------------------------
# 8. Payment type encoding map
# ---------------------------------------------------------------------------

class TestPaymentTypeEncoding:
    """Verify the payment type encoding constants."""

    def test_upi_encoding(self):
        assert _PAYMENT_TYPE_ENCODING["UPI"] == 0.0

    def test_imps_encoding(self):
        assert _PAYMENT_TYPE_ENCODING["IMPS"] == 0.5

    def test_neft_encoding(self):
        assert _PAYMENT_TYPE_ENCODING["NEFT"] == 1.0

    def test_rtgs_encoding(self):
        assert _PAYMENT_TYPE_ENCODING["RTGS"] == 1.0


# ---------------------------------------------------------------------------
# 9. GNNScorer integration
# ---------------------------------------------------------------------------

class TestGNNScorerIntegration:
    """End-to-end tests through the GNNScorer wrapper."""

    def test_scorer_train_with_edge_features(self):
        accounts = _make_accounts(6, roles=["MULE", "MULE", "MULE", "LEGIT", "LEGIT", "LEGIT"])
        txns = _make_transactions(accounts, payment_type="NEFT")
        scorer = GNNScorer(model_path="/tmp/test_gnn_directed.pt")
        losses = scorer.train(accounts, txns, {}, epochs=5)
        assert len(losses) == 5
        assert all(isinstance(l, float) for l in losses)

    def test_scorer_predict_with_edge_features(self):
        accounts = _make_accounts(4)
        txns = _make_transactions(accounts, payment_type="UPI")
        scorer = GNNScorer(model_path="/tmp/test_gnn_directed_pred.pt")
        preds = scorer.predict(accounts, txns, {})
        assert len(preds) == 4
        for p in preds:
            assert 0.0 <= p.mule_probability <= 1.0
            assert p.embedding is not None

    def test_scorer_train_and_predict(self):
        accounts = _make_accounts(6, roles=["MULE", "MULE", "MULE", "LEGIT", "LEGIT", "LEGIT"])
        txns = _make_transactions(accounts, payment_type="IMPS")
        scorer = GNNScorer(model_path="/tmp/test_gnn_directed_tap.pt")
        preds, metrics = scorer.train_and_predict(
            accounts, txns, {}, epochs=5, train_ratio=0.5,
        )
        assert len(preds) == 6
        assert metrics.epochs == 5
        assert len(metrics.loss_curve) == 5
