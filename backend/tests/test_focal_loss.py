"""
Tests for FocalLoss implementation in the GNN model.

Validates:
  - Gradient flow through FocalLoss
  - Equivalence with CrossEntropyLoss when gamma=0
  - Down-weighting of easy (high-confidence) examples
  - GNNScorer.train integration with FocalLoss
  - Edge cases: all-same-class labels, single-sample batches

Run: python -m pytest backend/tests/test_focal_loss.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
import torch
import torch.nn as nn

from models.gnn.gnn_model import FocalLoss

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def focal_default():
    """FocalLoss with default production parameters (gamma=2, alpha=0.25)."""
    return FocalLoss(gamma=2.0, alpha=0.25)


@pytest.fixture
def binary_logits_and_targets():
    """Simple binary classification logits and targets for reuse."""
    logits = torch.tensor([[2.0, -1.0], [-1.0, 2.0], [0.5, 0.5]], dtype=torch.float)
    targets = torch.tensor([0, 1, 0], dtype=torch.long)
    return logits, targets


# ---------------------------------------------------------------------------
# 1. Gradient flow
# ---------------------------------------------------------------------------


class TestFocalLossGradients:
    def test_produces_valid_gradients(self, focal_default, binary_logits_and_targets):
        """Loss must be differentiable and produce finite, non-zero gradients."""
        logits, targets = binary_logits_and_targets
        logits = logits.clone().requires_grad_(True)

        loss = focal_default(logits, targets)
        loss.backward()

        assert logits.grad is not None, "No gradient computed"
        assert torch.isfinite(logits.grad).all(), "Gradient contains inf/nan"
        assert logits.grad.abs().sum() > 0, "All gradients are zero"

    def test_gradient_shape_matches_input(self, focal_default):
        """Gradient tensor must have the same shape as the input logits."""
        logits = torch.randn(16, 2, requires_grad=True)
        targets = torch.randint(0, 2, (16,))

        loss = focal_default(logits, targets)
        loss.backward()

        assert logits.grad.shape == logits.shape

    def test_gradients_through_linear_layer(self, focal_default):
        """FocalLoss must propagate gradients through upstream parameters."""
        linear = nn.Linear(4, 2)
        x = torch.randn(8, 4)
        targets = torch.randint(0, 2, (8,))

        logits = linear(x)
        loss = focal_default(logits, targets)
        loss.backward()

        for param in linear.parameters():
            assert param.grad is not None, "Gradient missing on upstream parameter"
            assert torch.isfinite(param.grad).all()


# ---------------------------------------------------------------------------
# 2. Equivalence with CrossEntropyLoss when gamma=0
# ---------------------------------------------------------------------------


class TestFocalLossGammaZeroEquivalence:
    def test_gamma_zero_matches_cross_entropy_balanced(self):
        """With gamma=0 and alpha=0.5, FocalLoss should equal CrossEntropyLoss."""
        focal = FocalLoss(gamma=0.0, alpha=0.5, reduction="mean")
        ce = nn.CrossEntropyLoss(reduction="mean")

        torch.manual_seed(42)
        logits = torch.randn(32, 2)
        targets = torch.randint(0, 2, (32,))

        focal_loss = focal(logits, targets)
        ce_loss = ce(logits, targets)

        # alpha=0.5 means both classes weighted equally (0.5 each), so
        # focal_loss = 0.5 * CE.  Scale accordingly for comparison.
        torch.testing.assert_close(
            focal_loss,
            ce_loss * 0.5,
            atol=1e-5,
            rtol=1e-5,
        )

    def test_gamma_zero_per_sample(self):
        """Per-sample losses (reduction='none') should match element-wise."""
        focal = FocalLoss(gamma=0.0, alpha=0.5, reduction="none")
        ce = nn.CrossEntropyLoss(reduction="none")

        torch.manual_seed(99)
        logits = torch.randn(16, 2)
        targets = torch.randint(0, 2, (16,))

        focal_losses = focal(logits, targets)
        ce_losses = ce(logits, targets)

        torch.testing.assert_close(
            focal_losses,
            ce_losses * 0.5,
            atol=1e-5,
            rtol=1e-5,
        )

    def test_gamma_zero_sum_reduction(self):
        """Sum reduction should also match (scaled by alpha)."""
        focal = FocalLoss(gamma=0.0, alpha=0.5, reduction="sum")
        ce = nn.CrossEntropyLoss(reduction="sum")

        torch.manual_seed(7)
        logits = torch.randn(20, 2)
        targets = torch.randint(0, 2, (20,))

        torch.testing.assert_close(
            focal(logits, targets),
            ce(logits, targets) * 0.5,
            atol=1e-5,
            rtol=1e-5,
        )


# ---------------------------------------------------------------------------
# 3. Down-weighting of easy examples
# ---------------------------------------------------------------------------


class TestFocalLossDownWeighting:
    def test_high_confidence_correct_gets_lower_loss(self):
        """
        For a correctly classified sample, higher confidence should produce
        lower focal loss (gamma > 0 down-weights easy examples).
        """
        focal = FocalLoss(gamma=2.0, alpha=0.5, reduction="none")

        # High confidence correct: logit strongly favours class 0
        high_conf = torch.tensor([[5.0, -5.0]], dtype=torch.float)
        # Low confidence correct: logit weakly favours class 0
        low_conf = torch.tensor([[0.5, -0.5]], dtype=torch.float)
        target = torch.tensor([0], dtype=torch.long)

        loss_high = focal(high_conf, target)
        loss_low = focal(low_conf, target)

        assert loss_high.item() < loss_low.item(), (
            f"High-confidence loss ({loss_high.item():.6f}) should be less "
            f"than low-confidence loss ({loss_low.item():.6f})"
        )

    def test_gamma_increases_down_weighting(self):
        """Higher gamma should produce a larger ratio between easy and hard losses."""
        # An easy example (high confidence correct prediction)
        easy_logits = torch.tensor([[4.0, -4.0]], dtype=torch.float)
        target = torch.tensor([0], dtype=torch.long)

        focal_low_gamma = FocalLoss(gamma=1.0, alpha=0.5, reduction="none")
        focal_high_gamma = FocalLoss(gamma=3.0, alpha=0.5, reduction="none")

        loss_low_gamma = focal_low_gamma(easy_logits, target).item()
        loss_high_gamma = focal_high_gamma(easy_logits, target).item()

        assert loss_high_gamma < loss_low_gamma, "Higher gamma should down-weight easy examples more aggressively"

    def test_misclassified_gets_higher_loss(self):
        """A misclassified sample should receive substantially higher loss."""
        focal = FocalLoss(gamma=2.0, alpha=0.5, reduction="none")

        # Correctly classified (logit favours true class 0)
        correct_logits = torch.tensor([[3.0, -3.0]], dtype=torch.float)
        # Misclassified (logit favours wrong class 1, but true label is 0)
        wrong_logits = torch.tensor([[-3.0, 3.0]], dtype=torch.float)
        target = torch.tensor([0], dtype=torch.long)

        loss_correct = focal(correct_logits, target)
        loss_wrong = focal(wrong_logits, target)

        assert loss_wrong.item() > loss_correct.item()

    def test_focal_loss_less_than_ce_for_easy_example(self):
        """Focal loss should be strictly less than CE for easy examples (gamma>0)."""
        focal = FocalLoss(gamma=2.0, alpha=0.5, reduction="none")
        ce = nn.CrossEntropyLoss(reduction="none")

        easy_logits = torch.tensor([[6.0, -6.0]], dtype=torch.float)
        target = torch.tensor([0], dtype=torch.long)

        fl = focal(easy_logits, target).item()
        ce_val = ce(easy_logits, target).item() * 0.5  # scale by alpha for comparison

        assert fl < ce_val, f"Focal loss ({fl:.8f}) should be less than scaled CE ({ce_val:.8f}) for easy examples"


# ---------------------------------------------------------------------------
# 4. GNNScorer.train integration
# ---------------------------------------------------------------------------


class TestGNNScorerWithFocalLoss:
    @pytest.fixture
    def _skip_without_torch_geometric(self):
        """Skip tests if torch_geometric is not installed."""
        try:
            import torch_geometric  # noqa: F401
        except ImportError:
            pytest.skip("torch_geometric not installed")

    def test_train_returns_decreasing_losses(self, _skip_without_torch_geometric):
        """GNNScorer.train with FocalLoss should produce a converging loss curve."""
        from data.synthetic.generator import build_full_dataset
        from models.gnn.gnn_model import GNNScorer
        from models.temporal_weighting.smurf_weighting import score_transaction_batch

        dataset = build_full_dataset(num_clusters=2, num_legit_accounts=15)
        smurf_scores = score_transaction_batch(dataset["transactions"])

        scorer = GNNScorer(model_path="/tmp/test_focal_model.pt")
        losses = scorer.train(
            dataset["accounts"],
            dataset["transactions"],
            smurf_scores,
            epochs=30,
            lr=0.01,
        )

        assert len(losses) == 30, f"Expected 30 loss values, got {len(losses)}"
        assert all(isinstance(loss, float) for loss in losses)
        assert all(loss >= 0.0 for loss in losses), "Loss values must be non-negative"
        # The loss curve should generally decrease (compare first 5 avg vs last 5 avg)
        avg_first = sum(losses[:5]) / 5
        avg_last = sum(losses[-5:]) / 5
        assert avg_last <= avg_first, f"Loss should decrease: first-5 avg={avg_first:.4f}, last-5 avg={avg_last:.4f}"

    def test_train_marks_model_as_trained(self, _skip_without_torch_geometric):
        """After training, GNNScorer.is_trained should be True."""
        from data.synthetic.generator import build_full_dataset
        from models.gnn.gnn_model import GNNScorer
        from models.temporal_weighting.smurf_weighting import score_transaction_batch

        dataset = build_full_dataset(num_clusters=2, num_legit_accounts=10)
        smurf_scores = score_transaction_batch(dataset["transactions"])

        scorer = GNNScorer(model_path="/tmp/test_focal_trained.pt")
        scorer.train(
            dataset["accounts"],
            dataset["transactions"],
            smurf_scores,
            epochs=5,
        )

        assert scorer.is_trained is True


# ---------------------------------------------------------------------------
# 5. Edge cases
# ---------------------------------------------------------------------------


class TestFocalLossEdgeCases:
    def test_all_same_class_zero(self):
        """All targets are class 0 (legitimate). Loss should be finite."""
        focal = FocalLoss(gamma=2.0, alpha=0.25)
        logits = torch.randn(10, 2)
        targets = torch.zeros(10, dtype=torch.long)

        loss = focal(logits, targets)
        assert torch.isfinite(loss), f"Loss is not finite: {loss.item()}"
        assert loss.item() >= 0.0

    def test_all_same_class_one(self):
        """All targets are class 1 (mule). Loss should be finite."""
        focal = FocalLoss(gamma=2.0, alpha=0.25)
        logits = torch.randn(10, 2)
        targets = torch.ones(10, dtype=torch.long)

        loss = focal(logits, targets)
        assert torch.isfinite(loss), f"Loss is not finite: {loss.item()}"
        assert loss.item() >= 0.0

    def test_single_sample(self):
        """Loss must work with a single sample (N=1)."""
        focal = FocalLoss(gamma=2.0, alpha=0.25)
        logits = torch.tensor([[1.0, -1.0]], dtype=torch.float)
        targets = torch.tensor([0], dtype=torch.long)

        loss = focal(logits, targets)
        assert torch.isfinite(loss)
        assert loss.item() >= 0.0

    def test_single_sample_class_one(self):
        """Single mule sample."""
        focal = FocalLoss(gamma=2.0, alpha=0.25)
        logits = torch.tensor([[-1.0, 1.0]], dtype=torch.float)
        targets = torch.tensor([1], dtype=torch.long)

        loss = focal(logits, targets)
        assert torch.isfinite(loss)
        assert loss.item() >= 0.0

    def test_large_logits_numerical_stability(self):
        """Very large logits should not cause inf or nan."""
        focal = FocalLoss(gamma=2.0, alpha=0.25)
        logits = torch.tensor([[100.0, -100.0], [-100.0, 100.0]], dtype=torch.float)
        targets = torch.tensor([0, 1], dtype=torch.long)

        loss = focal(logits, targets)
        assert torch.isfinite(loss), f"Loss is not finite for large logits: {loss.item()}"

    def test_equal_logits(self):
        """Equal logits (maximum uncertainty) should produce valid loss."""
        focal = FocalLoss(gamma=2.0, alpha=0.25)
        logits = torch.tensor([[0.0, 0.0], [0.0, 0.0]], dtype=torch.float)
        targets = torch.tensor([0, 1], dtype=torch.long)

        loss = focal(logits, targets)
        assert torch.isfinite(loss)
        assert loss.item() > 0.0


# ---------------------------------------------------------------------------
# 6. Constructor validation
# ---------------------------------------------------------------------------


class TestFocalLossValidation:
    def test_negative_gamma_raises(self):
        with pytest.raises(ValueError, match="gamma must be non-negative"):
            FocalLoss(gamma=-1.0)

    def test_alpha_zero_raises(self):
        with pytest.raises(ValueError, match="alpha must be in"):
            FocalLoss(alpha=0.0)

    def test_alpha_one_raises(self):
        with pytest.raises(ValueError, match="alpha must be in"):
            FocalLoss(alpha=1.0)

    def test_invalid_reduction_raises(self):
        with pytest.raises(ValueError, match="reduction must be"):
            FocalLoss(reduction="avg")

    def test_valid_construction(self):
        fl = FocalLoss(gamma=0.0, alpha=0.5, reduction="sum")
        assert fl.gamma == 0.0
        assert fl.alpha == 0.5
        assert fl.reduction == "sum"


# ---------------------------------------------------------------------------
# 7. Reduction modes
# ---------------------------------------------------------------------------


class TestFocalLossReductions:
    def test_none_returns_per_sample(self):
        focal = FocalLoss(gamma=2.0, alpha=0.25, reduction="none")
        logits = torch.randn(8, 2)
        targets = torch.randint(0, 2, (8,))

        loss = focal(logits, targets)
        assert loss.shape == (8,), f"Expected shape (8,), got {loss.shape}"

    def test_mean_returns_scalar(self):
        focal = FocalLoss(gamma=2.0, alpha=0.25, reduction="mean")
        logits = torch.randn(8, 2)
        targets = torch.randint(0, 2, (8,))

        loss = focal(logits, targets)
        assert loss.dim() == 0, "Mean reduction should return a scalar"

    def test_sum_returns_scalar(self):
        focal = FocalLoss(gamma=2.0, alpha=0.25, reduction="sum")
        logits = torch.randn(8, 2)
        targets = torch.randint(0, 2, (8,))

        loss = focal(logits, targets)
        assert loss.dim() == 0, "Sum reduction should return a scalar"

    def test_sum_equals_none_summed(self):
        """Sum reduction should equal the sum of per-sample losses."""
        torch.manual_seed(123)
        logits = torch.randn(12, 2)
        targets = torch.randint(0, 2, (12,))

        focal_sum = FocalLoss(gamma=2.0, alpha=0.25, reduction="sum")
        focal_none = FocalLoss(gamma=2.0, alpha=0.25, reduction="none")

        loss_sum = focal_sum(logits, targets)
        loss_none = focal_none(logits, targets).sum()

        torch.testing.assert_close(loss_sum, loss_none, atol=1e-6, rtol=1e-6)

    def test_mean_equals_none_meaned(self):
        """Mean reduction should equal the mean of per-sample losses."""
        torch.manual_seed(456)
        logits = torch.randn(12, 2)
        targets = torch.randint(0, 2, (12,))

        focal_mean = FocalLoss(gamma=2.0, alpha=0.25, reduction="mean")
        focal_none = FocalLoss(gamma=2.0, alpha=0.25, reduction="none")

        loss_mean = focal_mean(logits, targets)
        loss_none = focal_none(logits, targets).mean()

        torch.testing.assert_close(loss_mean, loss_none, atol=1e-6, rtol=1e-6)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
