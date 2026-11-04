"""
MuleCatch Graph Neural Network
================================
A GraphSAGE-based GNN that learns node embeddings from
account transaction graphs to classify accounts as mule/legitimate.

Architecture:
  Input features  -> GraphSAGE layers -> MLP classifier
  Node features: account_age, avg_txn, in_degree, out_degree,
                 velocity_score, amount_ceiling_score

Directed edges & edge features (v2):
  - Directed message passing preserves money-flow direction
    (LAS-GNN: "almost perfect detection" of temporal motifs)
  - Edge features: normalised amount, timestamp offset, payment type
    (Amatriciana: 55 % FP reduction)
  - Backward compatible: ``directed=False`` or ``edge_attr=None``
    reproduce the original undirected/featureless behaviour.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

# Fast check: skip torch import entirely if the package isn't installed
# (avoids hangs from broken/partial installs on some systems)
if importlib.util.find_spec("torch") is None:
    raise ImportError("torch is not installed")

import torch
import torch.nn as nn
import torch.nn.functional as F

# Optional torch_geometric import (graceful fallback for environments without it)
try:
    from torch_geometric.data import Data
    from torch_geometric.nn import SAGEConv

    HAS_TORCH_GEOMETRIC = True
except ImportError:
    HAS_TORCH_GEOMETRIC = False


DEFAULT_MODEL_PATH = "models/gnn/trained_model.pt"


class FocalLoss(nn.Module):
    """
    Focal Loss for class-imbalanced classification.

    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)

    In fraud detection, mule accounts are typically <0.1% of all accounts.
    Standard CrossEntropyLoss is dominated by the easy negatives (legitimate
    accounts), causing the model to under-learn the minority class.  Focal
    Loss down-weights well-classified examples so training concentrates on
    hard, misclassified ones.

    Parameters
    ----------
    gamma : float
        Focusing parameter.  gamma=0 recovers standard CE.  Higher values
        increase the down-weighting of easy examples.  Default 2.0.
    alpha : float
        Balancing weight for the positive (mule) class.  The negative
        (legitimate) class receives weight (1 - alpha).  Default 0.25.
    reduction : str
        ``'mean'`` | ``'sum'`` | ``'none'``.

    References
    ----------
    - Lin et al., "Focal Loss for Dense Object Detection", ICCV 2017
    - Standard for fraud detection per arxiv 2508.02283
    """

    def __init__(
        self,
        gamma: float = 2.0,
        alpha: float = 0.25,
        reduction: str = "mean",
    ) -> None:
        super().__init__()
        if gamma < 0:
            raise ValueError(f"gamma must be non-negative, got {gamma}")
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        if reduction not in ("mean", "sum", "none"):
            raise ValueError(f"reduction must be 'mean', 'sum', or 'none', got '{reduction}'")
        self.gamma = gamma
        self.alpha = alpha
        self.reduction = reduction

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Compute focal loss.

        Parameters
        ----------
        inputs : Tensor of shape (N, C)
            Raw logits (unnormalized scores) for each class.
        targets : Tensor of shape (N,)
            Ground-truth class indices in [0, C).

        Returns
        -------
        Tensor
            Scalar loss (if reduction='mean' or 'sum') or per-sample loss
            tensor of shape (N,) if reduction='none'.
        """
        # Compute log-softmax for numerical stability (avoids log(softmax) underflow)
        log_probs = F.log_softmax(inputs, dim=1)
        probs = log_probs.exp()

        # Gather the probability and log-probability for the true class
        # targets_one_hot not needed — use gather for efficiency
        targets_unsqueezed = targets.unsqueeze(1)  # (N, 1)
        log_pt = log_probs.gather(1, targets_unsqueezed).squeeze(1)  # (N,)
        pt = probs.gather(1, targets_unsqueezed).squeeze(1)  # (N,)

        # Per-class alpha weighting: alpha for class 1 (mule), (1-alpha) for class 0
        alpha_t = torch.where(
            targets == 1,
            torch.tensor(self.alpha, dtype=inputs.dtype, device=inputs.device),
            torch.tensor(1.0 - self.alpha, dtype=inputs.dtype, device=inputs.device),
        )

        # Focal modulating factor
        focal_weight = (1.0 - pt) ** self.gamma

        # Focal loss: -alpha_t * (1 - p_t)^gamma * log(p_t)
        loss = -alpha_t * focal_weight * log_pt

        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        return loss


@dataclass
class TrainingMetrics:
    """Metrics from a GNN training run."""

    epochs: int
    loss_curve: List[float]
    final_loss: float
    train_accuracy: float


@dataclass
class GNNPrediction:
    account_id: str
    mule_probability: float
    embedding: Optional[List[float]] = None
    is_flagged: bool = False


class MuleCatchGNN(nn.Module):
    """
    GraphSAGE-based node classification model.
    Operates on the account transaction graph.

    When ``edge_attr`` is provided (3-dim per edge: amount, timestamp,
    payment-type), an edge encoder MLP projects these features to a
    scalar weight that is added to the node representations after each
    SAGEConv layer, giving the model edge-level signal without changing
    the conv type.  When ``edge_attr is None`` the model falls back to
    the original featureless behaviour (full backward compatibility).
    """

    EDGE_FEAT_DIM: int = 3  # amount, timestamp_offset, payment_type

    def __init__(self, in_channels: int = 8, hidden: int = 64, out_channels: int = 2):
        super().__init__()
        if not HAS_TORCH_GEOMETRIC:
            raise RuntimeError("torch_geometric required for GNN. Using fallback scorer.")

        self.conv1 = SAGEConv(in_channels, hidden)
        self.conv2 = SAGEConv(hidden, hidden)
        self.conv3 = SAGEConv(hidden, hidden // 2)
        self.classifier = nn.Sequential(
            nn.Linear(hidden // 2, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, out_channels),
        )
        self.bn1 = nn.BatchNorm1d(hidden)
        self.bn2 = nn.BatchNorm1d(hidden)

        # Edge encoder: projects 3-dim edge features to scalar weight per edge.
        # Used to bias node embeddings with edge-level information after each
        # SAGEConv layer (amount, temporal offset, payment channel).
        self.edge_encoder = nn.Sequential(
            nn.Linear(self.EDGE_FEAT_DIM, hidden),
            nn.ReLU(),
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with optional edge features.

        Parameters
        ----------
        x : Tensor [N, in_channels]
            Node feature matrix.
        edge_index : Tensor [2, E]
            COO edge index.
        edge_attr : Tensor [E, 3] or None
            Per-edge features (normalised amount, timestamp offset,
            payment-type encoding).  When ``None`` the model behaves
            identically to the original featureless GNN.

        Returns
        -------
        (logits, embeddings) : Tuple[Tensor, Tensor]
            logits  – [N, out_channels]
            embeddings – [N, hidden // 2]
        """
        # Pre-compute edge contribution once (reused after each conv layer)
        edge_signal: Optional[torch.Tensor] = None
        if edge_attr is not None and edge_index.size(1) > 0:
            # edge_enc: [E, hidden]
            edge_enc = self.edge_encoder(edge_attr)
            # Scalar weight per edge: [E]
            edge_weight = edge_enc.mean(dim=1)
            # Aggregate edge weights onto destination nodes via scatter-add
            num_nodes = x.size(0)
            dst = edge_index[1]  # destination nodes
            edge_signal = torch.zeros(num_nodes, device=x.device, dtype=x.dtype)
            edge_signal.scatter_add_(0, dst, edge_weight)

        # Layer 1
        x = F.relu(self.bn1(self.conv1(x, edge_index)))
        if edge_signal is not None:
            x = x + edge_signal.unsqueeze(1)
        x = F.dropout(x, p=0.3, training=self.training)

        # Layer 2
        x = F.relu(self.bn2(self.conv2(x, edge_index)))
        if edge_signal is not None:
            x = x + edge_signal.unsqueeze(1)

        # Layer 3
        x = self.conv3(x, edge_index)
        out = self.classifier(x)
        return out, x  # logits + embeddings


_PAYMENT_TYPE_ENCODING: Dict[str, float] = {
    "UPI": 0.0,
    "IMPS": 0.5,
    "NEFT": 1.0,
    "RTGS": 1.0,
}


def _parse_timestamp(ts_value) -> float:
    """Parse a timestamp to seconds since epoch.

    Accepts ISO-8601 strings, numeric epoch seconds, or ``datetime``
    objects.  Returns 0.0 on failure so that a single bad record never
    crashes the pipeline.
    """
    if isinstance(ts_value, (int, float)):
        return float(ts_value)
    if isinstance(ts_value, datetime):
        return ts_value.timestamp()
    if isinstance(ts_value, str):
        try:
            # Try ISO-8601 with timezone
            dt = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def build_graph_data(
    accounts: List[Dict],
    transactions: List[Dict],
    smurf_scores: Optional[Dict] = None,
    directed: bool = True,
) -> Tuple:
    """
    Convert account/transaction data into a ``torch_geometric.data.Data``
    object.

    Parameters
    ----------
    accounts : list of dict
        Account records.  Each must contain ``account_id``.
    transactions : list of dict
        Transaction records with ``from_account``, ``to_account``,
        ``amount``, and optionally ``timestamp`` and ``payment_type``.
    smurf_scores : dict or None
        Mapping ``account_id -> SmurfScore`` namedtuple (optional).
    directed : bool
        When ``True`` (default) edges follow the money-flow direction
        only.  When ``False`` a reverse edge is added for each
        transaction (legacy undirected behaviour).

    Returns
    -------
    (Data, account_id_list) or (None, None) if torch_geometric is
    missing.  The ``Data`` object carries ``edge_attr`` (shape ``[E, 3]``)
    when ``directed=True`` and transactions contain the required fields.
    """
    if not HAS_TORCH_GEOMETRIC:
        return None, None

    account_ids = [a["account_id"] for a in accounts]
    acc_idx = {acc_id: i for i, acc_id in enumerate(account_ids)}

    # ── Node features ────────────────────────────────────────────────────────
    features = []
    for acc in accounts:
        acc_id = acc["account_id"]
        ss = smurf_scores.get(acc_id) if smurf_scores else None
        feat = [
            min(acc.get("account_age_days", 365) / 365.0, 1.0),
            min(acc.get("avg_monthly_txn", 100) / 500.0, 1.0),
            1.0 if acc.get("kyc_status") == "VERIFIED" else 0.0,
            0.0,  # was the generator's high_risk label (a leak); slot kept so saved models keep their shape, retrain to drop it
            ss.velocity_score if ss else 0.0,
            ss.amount_ceiling_score if ss else 0.0,
            ss.fan_out_score if ss else 0.0,
            ss.smurf_score if ss else 0.0,
        ]
        features.append(feat)

    x = torch.tensor(features, dtype=torch.float)

    # ── Edge index + edge features ───────────────────────────────────────────
    edges: List[List[int]] = []
    raw_amounts: List[float] = []
    raw_timestamps: List[float] = []
    raw_payment_types: List[float] = []

    for t in transactions:
        src = t["from_account"]
        dst = t["to_account"]
        if src in acc_idx and dst in acc_idx:
            edges.append([acc_idx[src], acc_idx[dst]])
            raw_amounts.append(float(t.get("amount", 0)))
            raw_timestamps.append(_parse_timestamp(t.get("timestamp", 0)))
            ptype = str(t.get("payment_type", "")).upper()
            raw_payment_types.append(_PAYMENT_TYPE_ENCODING.get(ptype, 0.5))

            if not directed:
                # Legacy undirected mode: add reverse edge with same features
                edges.append([acc_idx[dst], acc_idx[src]])
                raw_amounts.append(raw_amounts[-1])
                raw_timestamps.append(raw_timestamps[-1])
                raw_payment_types.append(raw_payment_types[-1])

    if not edges:
        edge_index = torch.zeros((2, 0), dtype=torch.long)
        edge_attr = torch.zeros((0, MuleCatchGNN.EDGE_FEAT_DIM), dtype=torch.float)
    else:
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()

        # Normalise amounts: cap at 100k
        norm_amounts = [min(a / 100_000.0, 1.0) for a in raw_amounts]

        # Normalise timestamps to [0, 1] within the batch
        ts_arr = np.array(raw_timestamps, dtype=np.float64)
        ts_min = ts_arr.min()
        ts_max = ts_arr.max()
        ts_range = ts_max - ts_min
        if ts_range > 0:
            norm_timestamps = ((ts_arr - ts_min) / ts_range).tolist()
        else:
            norm_timestamps = [0.0] * len(raw_timestamps)

        edge_features = [[na, nt, pt] for na, nt, pt in zip(norm_amounts, norm_timestamps, raw_payment_types)]
        edge_attr = torch.tensor(edge_features, dtype=torch.float)

    # ── Labels (for supervised training) ─────────────────────────────────────
    labels = []
    for acc in accounts:
        is_mule = acc.get("role") in ("MULE", "SOURCE", "AGGREGATOR")
        labels.append(1 if is_mule else 0)
    y = torch.tensor(labels, dtype=torch.long)

    data = Data(x=x, edge_index=edge_index, y=y)
    data.edge_attr = edge_attr
    return data, account_ids


class GNNScorer:
    """
    Wraps training + inference for the MuleCatchGNN.
    Falls back to a heuristic scorer when torch_geometric is absent.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model: Optional[MuleCatchGNN] = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._is_trained = False
        self._model_path = model_path or DEFAULT_MODEL_PATH
        if HAS_TORCH_GEOMETRIC:
            self.model = MuleCatchGNN().to(self.device)
            # Auto-load saved weights if they exist
            if os.path.exists(self._model_path):
                try:
                    self.load(self._model_path)
                    self._is_trained = True
                except Exception:
                    self._is_trained = False

    @property
    def is_trained(self) -> bool:
        """Whether the model has been trained or loaded from disk."""
        return self._is_trained

    @staticmethod
    def _get_edge_attr(data: "Data") -> Optional[torch.Tensor]:
        """Safely extract edge_attr from a Data object, returning None
        if absent or empty."""
        edge_attr = getattr(data, "edge_attr", None)
        if edge_attr is not None and edge_attr.numel() == 0:
            return None
        return edge_attr

    def train(
        self,
        accounts: List[Dict],
        transactions: List[Dict],
        smurf_scores: Dict,
        epochs: int = 50,
        lr: float = 0.01,
    ) -> List[float]:
        """Train the GNN on the full graph (no train/test split).

        Edge features are automatically passed through when
        ``build_graph_data`` produces them.
        """
        if not HAS_TORCH_GEOMETRIC or self.model is None:
            print("torch_geometric not available — skipping GNN training")
            return []

        data, _ = build_graph_data(accounts, transactions, smurf_scores)
        data = data.to(self.device)
        edge_attr = self._get_edge_attr(data)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=5e-4)
        criterion = FocalLoss(gamma=2.0, alpha=0.25)

        losses: List[float] = []
        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            logits, _ = self.model(data.x, data.edge_index, edge_attr)
            loss = criterion(logits, data.y)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
            if (epoch + 1) % 10 == 0:
                print(f"  GNN Epoch {epoch + 1}/{epochs}  loss={loss.item():.4f}")

        self._is_trained = True
        return losses

    def train_and_predict(
        self,
        accounts: List[Dict],
        transactions: List[Dict],
        smurf_scores: Dict,
        epochs: int = 50,
        lr: float = 0.01,
        train_ratio: float = 0.7,
    ) -> Tuple[List[GNNPrediction], TrainingMetrics]:
        """
        Train on a stratified split of the data, save weights, then
        predict on ALL accounts. Returns (predictions, training_metrics).
        """
        if not HAS_TORCH_GEOMETRIC or self.model is None:
            print("torch_geometric not available — skipping GNN training")
            return self._heuristic_predict(accounts, smurf_scores), TrainingMetrics(
                epochs=0,
                loss_curve=[],
                final_loss=0.0,
                train_accuracy=0.0,
            )

        data, account_ids = build_graph_data(accounts, transactions, smurf_scores)
        data = data.to(self.device)
        edge_attr = self._get_edge_attr(data)

        num_nodes = data.y.size(0)
        labels_np = data.y.cpu().numpy()

        # Stratified split: separate indices by label, sample train_ratio from each
        pos_indices = np.where(labels_np == 1)[0]
        neg_indices = np.where(labels_np == 0)[0]
        np.random.shuffle(pos_indices)
        np.random.shuffle(neg_indices)

        pos_train_n = max(1, int(len(pos_indices) * train_ratio))
        neg_train_n = max(1, int(len(neg_indices) * train_ratio))

        train_indices = np.concatenate(
            [
                pos_indices[:pos_train_n],
                neg_indices[:neg_train_n],
            ]
        )

        train_mask = torch.zeros(num_nodes, dtype=torch.bool)
        train_mask[torch.from_numpy(train_indices)] = True
        train_mask = train_mask.to(self.device)

        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=lr,
            weight_decay=5e-4,
        )
        criterion = FocalLoss(gamma=2.0, alpha=0.25)

        losses: List[float] = []
        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            logits, _ = self.model(data.x, data.edge_index, edge_attr)
            loss = criterion(logits[train_mask], data.y[train_mask])
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
            if (epoch + 1) % 10 == 0:
                print(f"  GNN Epoch {epoch + 1}/{epochs}  loss={loss.item():.4f}")

        # Compute train accuracy
        self.model.eval()
        with torch.no_grad():
            logits, _ = self.model(data.x, data.edge_index, edge_attr)
            preds_train = logits[train_mask].argmax(dim=1)
            correct = (preds_train == data.y[train_mask]).sum().item()
            train_acc = correct / max(train_mask.sum().item(), 1)

        # Save model weights
        try:
            os.makedirs(os.path.dirname(self._model_path) or ".", exist_ok=True)
            self.save(self._model_path)
        except Exception as exc:
            print(f"Warning: Could not save GNN model: {exc}")

        self._is_trained = True

        # Predict on ALL accounts
        with torch.no_grad():
            logits, embeddings = self.model(data.x, data.edge_index, edge_attr)
            probs = F.softmax(logits, dim=1).cpu().numpy()
            embs = embeddings.cpu().numpy()

        results = []
        for i, acc_id in enumerate(account_ids):
            mule_prob = float(probs[i][1])
            results.append(
                GNNPrediction(
                    account_id=acc_id,
                    mule_probability=mule_prob,
                    embedding=embs[i].tolist(),
                    is_flagged=mule_prob >= 0.5,
                )
            )

        metrics = TrainingMetrics(
            epochs=epochs,
            loss_curve=losses,
            final_loss=losses[-1] if losses else 0.0,
            train_accuracy=train_acc,
        )
        return results, metrics

    def predict(
        self,
        accounts: List[Dict],
        transactions: List[Dict],
        smurf_scores: Dict,
    ) -> List[GNNPrediction]:
        """Predict mule probabilities for each account.

        Edge features are automatically forwarded to the model when
        present in the graph data.
        """
        if not HAS_TORCH_GEOMETRIC or self.model is None:
            return self._heuristic_predict(accounts, smurf_scores)

        data, account_ids = build_graph_data(accounts, transactions, smurf_scores)
        data = data.to(self.device)
        edge_attr = self._get_edge_attr(data)

        self.model.eval()
        with torch.no_grad():
            logits, embeddings = self.model(data.x, data.edge_index, edge_attr)
            probs = F.softmax(logits, dim=1).cpu().numpy()
            embs = embeddings.cpu().numpy()

        results = []
        for i, acc_id in enumerate(account_ids):
            mule_prob = float(probs[i][1])
            results.append(
                GNNPrediction(
                    account_id=acc_id,
                    mule_probability=mule_prob,
                    embedding=embs[i].tolist(),
                    is_flagged=mule_prob >= 0.5,
                )
            )
        return results

    def _heuristic_predict(self, accounts: List[Dict], smurf_scores: Dict) -> List[GNNPrediction]:
        """Simple heuristic fallback when GNN is unavailable"""
        results = []
        for acc in accounts:
            acc_id = acc["account_id"]
            ss = smurf_scores.get(acc_id)
            prob = ss.smurf_score if ss else 0.0
            results.append(
                GNNPrediction(
                    account_id=acc_id,
                    mule_probability=prob,
                    is_flagged=prob >= 0.5,
                )
            )
        return results

    def save(self, path: str):
        """Persist model weights to disk."""
        if self.model:
            torch.save(self.model.state_dict(), path)

    def load(self, path: str):
        """Load model weights from disk."""
        if self.model:
            self.model.load_state_dict(torch.load(path, map_location=self.device))


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    from data.synthetic.generator import build_full_dataset
    from models.temporal_weighting.smurf_weighting import score_transaction_batch

    print("Running GNN self-test...")
    dataset = build_full_dataset(num_clusters=3, num_legit_accounts=30)
    smurf_scores = score_transaction_batch(dataset["transactions"])

    scorer = GNNScorer()
    losses = scorer.train(dataset["accounts"], dataset["transactions"], smurf_scores, epochs=30)
    preds = scorer.predict(dataset["accounts"], dataset["transactions"], smurf_scores)
    flagged = [p for p in preds if p.is_flagged]
    print(f"GNN flagged {len(flagged)}/{len(preds)} accounts")
