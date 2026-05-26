"""
MuleCatch Graph Neural Network
================================
A GraphSAGE-based GNN that learns node embeddings from
account transaction graphs to classify accounts as mule/legitimate.

Architecture:
  Input features  -> GraphSAGE layers -> MLP classifier
  Node features: account_age, avg_txn, in_degree, out_degree,
                 velocity_score, amount_ceiling_score
"""

from __future__ import annotations
import importlib.util
import os
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# Fast check: skip torch import entirely if the package isn't installed
# (avoids hangs from broken/partial installs on some systems)
if importlib.util.find_spec("torch") is None:
    raise ImportError("torch is not installed")

import torch
import torch.nn as nn
import torch.nn.functional as F

# Optional torch_geometric import (graceful fallback for environments without it)
try:
    from torch_geometric.nn import SAGEConv, global_mean_pool
    from torch_geometric.data import Data, DataLoader as GeoDataLoader
    HAS_TORCH_GEOMETRIC = True
except ImportError:
    HAS_TORCH_GEOMETRIC = False


DEFAULT_MODEL_PATH = "models/gnn/trained_model.pt"


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
    """

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

    def forward(self, x, edge_index):
        x = F.relu(self.bn1(self.conv1(x, edge_index)))
        x = F.dropout(x, p=0.3, training=self.training)
        x = F.relu(self.bn2(self.conv2(x, edge_index)))
        x = self.conv3(x, edge_index)
        out = self.classifier(x)
        return out, x   # logits + embeddings


def build_graph_data(
    accounts: List[Dict],
    transactions: List[Dict],
    smurf_scores: Optional[Dict] = None,
) -> Tuple:
    """
    Convert account/transaction data into torch_geometric Data object.
    Returns (Data, account_id_list) or (None, None) if torch_geometric missing.
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
            1.0 if acc.get("high_risk", False) else 0.0,
            ss.velocity_score if ss else 0.0,
            ss.amount_ceiling_score if ss else 0.0,
            ss.fan_out_score if ss else 0.0,
            ss.smurf_score if ss else 0.0,
        ]
        features.append(feat)

    x = torch.tensor(features, dtype=torch.float)

    # ── Edge index ────────────────────────────────────────────────────────────
    edges = []
    for t in transactions:
        src = t["from_account"]
        dst = t["to_account"]
        if src in acc_idx and dst in acc_idx:
            edges.append([acc_idx[src], acc_idx[dst]])
            edges.append([acc_idx[dst], acc_idx[src]])   # undirected

    if not edges:
        edge_index = torch.zeros((2, 0), dtype=torch.long)
    else:
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()

    # ── Labels (for supervised training) ─────────────────────────────────────
    labels = []
    for acc in accounts:
        is_mule = acc.get("role") in ("MULE", "SOURCE", "AGGREGATOR")
        labels.append(1 if is_mule else 0)
    y = torch.tensor(labels, dtype=torch.long)

    data = Data(x=x, edge_index=edge_index, y=y)
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

    def train(
        self,
        accounts: List[Dict],
        transactions: List[Dict],
        smurf_scores: Dict,
        epochs: int = 50,
        lr: float = 0.01,
    ) -> List[float]:
        if not HAS_TORCH_GEOMETRIC or self.model is None:
            print("torch_geometric not available — skipping GNN training")
            return []

        data, _ = build_graph_data(accounts, transactions, smurf_scores)
        data = data.to(self.device)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=5e-4)
        criterion = nn.CrossEntropyLoss()

        losses = []
        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            logits, _ = self.model(data.x, data.edge_index)
            loss = criterion(logits, data.y)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
            if (epoch + 1) % 10 == 0:
                print(f"  GNN Epoch {epoch+1}/{epochs}  loss={loss.item():.4f}")

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
                epochs=0, loss_curve=[], final_loss=0.0, train_accuracy=0.0,
            )

        data, account_ids = build_graph_data(accounts, transactions, smurf_scores)
        data = data.to(self.device)

        num_nodes = data.y.size(0)
        labels_np = data.y.cpu().numpy()

        # Stratified split: separate indices by label, sample train_ratio from each
        pos_indices = np.where(labels_np == 1)[0]
        neg_indices = np.where(labels_np == 0)[0]
        np.random.shuffle(pos_indices)
        np.random.shuffle(neg_indices)

        pos_train_n = max(1, int(len(pos_indices) * train_ratio))
        neg_train_n = max(1, int(len(neg_indices) * train_ratio))

        train_indices = np.concatenate([
            pos_indices[:pos_train_n],
            neg_indices[:neg_train_n],
        ])

        train_mask = torch.zeros(num_nodes, dtype=torch.bool)
        train_mask[torch.from_numpy(train_indices)] = True
        train_mask = train_mask.to(self.device)

        optimizer = torch.optim.Adam(
            self.model.parameters(), lr=lr, weight_decay=5e-4,
        )
        criterion = nn.CrossEntropyLoss()

        losses = []
        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            logits, _ = self.model(data.x, data.edge_index)
            loss = criterion(logits[train_mask], data.y[train_mask])
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
            if (epoch + 1) % 10 == 0:
                print(f"  GNN Epoch {epoch+1}/{epochs}  loss={loss.item():.4f}")

        # Compute train accuracy
        self.model.eval()
        with torch.no_grad():
            logits, _ = self.model(data.x, data.edge_index)
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
            logits, embeddings = self.model(data.x, data.edge_index)
            probs = F.softmax(logits, dim=1).cpu().numpy()
            embs = embeddings.cpu().numpy()

        results = []
        for i, acc_id in enumerate(account_ids):
            mule_prob = float(probs[i][1])
            results.append(GNNPrediction(
                account_id=acc_id,
                mule_probability=mule_prob,
                embedding=embs[i].tolist(),
                is_flagged=mule_prob >= 0.5,
            ))

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
        if not HAS_TORCH_GEOMETRIC or self.model is None:
            return self._heuristic_predict(accounts, smurf_scores)

        data, account_ids = build_graph_data(accounts, transactions, smurf_scores)
        data = data.to(self.device)

        self.model.eval()
        with torch.no_grad():
            logits, embeddings = self.model(data.x, data.edge_index)
            probs = F.softmax(logits, dim=1).cpu().numpy()
            embs  = embeddings.cpu().numpy()

        results = []
        for i, acc_id in enumerate(account_ids):
            mule_prob = float(probs[i][1])
            results.append(GNNPrediction(
                account_id=acc_id,
                mule_probability=mule_prob,
                embedding=embs[i].tolist(),
                is_flagged=mule_prob >= 0.5,
            ))
        return results

    def _heuristic_predict(
        self, accounts: List[Dict], smurf_scores: Dict
    ) -> List[GNNPrediction]:
        """Simple heuristic fallback when GNN is unavailable"""
        results = []
        for acc in accounts:
            acc_id = acc["account_id"]
            ss = smurf_scores.get(acc_id)
            prob = ss.smurf_score if ss else 0.0
            results.append(GNNPrediction(
                account_id=acc_id,
                mule_probability=prob,
                is_flagged=prob >= 0.5,
            ))
        return results

    def save(self, path: str):
        if self.model:
            torch.save(self.model.state_dict(), path)

    def load(self, path: str):
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
    losses = scorer.train(
        dataset["accounts"], dataset["transactions"], smurf_scores, epochs=30
    )
    preds = scorer.predict(dataset["accounts"], dataset["transactions"], smurf_scores)
    flagged = [p for p in preds if p.is_flagged]
    print(f"GNN flagged {len(flagged)}/{len(preds)} accounts")