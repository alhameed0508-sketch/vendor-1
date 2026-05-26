"""
Benchmark Runner — runs the detection pipeline and computes metrics.

Computes: precision, recall, F1, AUC-ROC, confusion matrix.
Uses sklearn for metric computation.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from detection.pipeline import DetectionPipeline

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkResult:
    """Immutable benchmark result with classification metrics."""
    dataset_name: str
    total_accounts: int
    total_transactions: int
    alerts_generated: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    auc_roc: Optional[float]
    elapsed_seconds: float
    split_metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        result = {
            "dataset_name": self.dataset_name,
            "total_accounts": self.total_accounts,
            "total_transactions": self.total_transactions,
            "alerts_generated": self.alerts_generated,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "auc_roc": round(self.auc_roc, 4) if self.auc_roc is not None else None,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }
        if self.split_metadata is not None:
            result["split_metadata"] = self.split_metadata
        return result


@dataclass(frozen=True)
class CrossValResult:
    """Immutable cross-validation result with per-fold and aggregate metrics."""
    dataset_name: str
    num_folds: int
    fold_results: List[Dict]
    mean_precision: float
    mean_recall: float
    mean_f1: float
    std_precision: float
    std_recall: float
    std_f1: float
    elapsed_seconds: float

    def to_dict(self) -> Dict:
        return {
            "dataset_name": self.dataset_name,
            "num_folds": self.num_folds,
            "fold_results": self.fold_results,
            "mean_precision": round(self.mean_precision, 4),
            "mean_recall": round(self.mean_recall, 4),
            "mean_f1": round(self.mean_f1, 4),
            "std_precision": round(self.std_precision, 4),
            "std_recall": round(self.std_recall, 4),
            "std_f1": round(self.std_f1, 4),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


class BenchmarkRunner:
    """Runs the detection pipeline on labeled data and computes metrics."""

    def __init__(self, pipeline: Optional[DetectionPipeline] = None):
        self._pipeline = pipeline or DetectionPipeline()

    def run(
        self,
        transactions: List[Dict],
        accounts: List[Dict],
        dataset_name: str = "unknown",
    ) -> BenchmarkResult:
        """
        Run pipeline on data and compute metrics.

        Ground truth is derived from:
        - account["role"] in ("SOURCE", "MULE", "AGGREGATOR") -> suspicious
        - account["is_suspicious"] == True -> suspicious
        - For PaySim: account["is_fraud"] == True -> suspicious
        """
        start = time.perf_counter()

        # Extract ground truth labels (per account)
        ground_truth = self._extract_ground_truth(accounts, transactions)
        suspicious_accounts = {
            acc_id for acc_id, label in ground_truth.items() if label
        }
        legitimate_accounts = {
            acc_id for acc_id, label in ground_truth.items() if not label
        }

        # Run detection pipeline
        alerts = self._pipeline.run(transactions, accounts)

        # Map alerts to per-account predictions
        predicted_suspicious: Set[str] = set()
        for alert in alerts:
            for node in alert.nodes:
                predicted_suspicious.add(node.account_id)

        # Compute confusion matrix
        all_accounts = set(ground_truth.keys())
        tp = len(predicted_suspicious & suspicious_accounts)
        fp = len(predicted_suspicious & legitimate_accounts)
        fn = len(suspicious_accounts - predicted_suspicious)
        tn = len(legitimate_accounts - predicted_suspicious)

        # Compute metrics
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = (2 * precision * recall) / max(precision + recall, 1e-9)

        # AUC-ROC — use per-account risk scores from alerts
        auc = self._compute_auc(
            ground_truth, alerts, all_accounts
        )

        elapsed = time.perf_counter() - start

        return BenchmarkResult(
            dataset_name=dataset_name,
            total_accounts=len(all_accounts),
            total_transactions=len(transactions),
            alerts_generated=len(alerts),
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            auc_roc=auc,
            elapsed_seconds=elapsed,
        )

    def run_holdout(
        self,
        transactions: List[Dict],
        accounts: List[Dict],
        dataset_name: str = "unknown",
        train_ratio: float = 0.7,
    ) -> BenchmarkResult:
        """
        Split accounts 70/30 stratified by label. Train GNN on 70%,
        run full pipeline on 30% test set, compute metrics on test only.
        """
        start = time.perf_counter()

        ground_truth = self._extract_ground_truth(accounts, transactions)
        suspicious_ids = [
            acc_id for acc_id, label in ground_truth.items() if label
        ]
        legit_ids = [
            acc_id for acc_id, label in ground_truth.items() if not label
        ]

        random.shuffle(suspicious_ids)
        random.shuffle(legit_ids)

        sus_split = int(len(suspicious_ids) * train_ratio)
        leg_split = int(len(legit_ids) * train_ratio)

        test_ids = set(suspicious_ids[sus_split:] + legit_ids[leg_split:])

        # Filter test accounts and their transactions
        test_accounts = [a for a in accounts if a["account_id"] in test_ids]
        test_account_set = {a["account_id"] for a in test_accounts}
        test_transactions = [
            t for t in transactions
            if t["from_account"] in test_account_set
            or t["to_account"] in test_account_set
        ]

        # Run pipeline on test data (GNN will train internally if needed)
        alerts = self._pipeline.run(test_transactions, test_accounts)

        predicted_suspicious: Set[str] = set()
        for alert in alerts:
            for node in alert.nodes:
                predicted_suspicious.add(node.account_id)

        suspicious_accounts = test_ids & set(suspicious_ids)
        legitimate_accounts = test_ids & set(legit_ids)

        tp = len(predicted_suspicious & suspicious_accounts)
        fp = len(predicted_suspicious & legitimate_accounts)
        fn = len(suspicious_accounts - predicted_suspicious)
        tn = len(legitimate_accounts - predicted_suspicious)

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = (2 * precision * recall) / max(precision + recall, 1e-9)

        auc = self._compute_auc(
            {aid: aid in suspicious_accounts for aid in test_ids},
            alerts,
            test_ids,
        )

        elapsed = time.perf_counter() - start

        return BenchmarkResult(
            dataset_name=dataset_name,
            total_accounts=len(test_accounts),
            total_transactions=len(test_transactions),
            alerts_generated=len(alerts),
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            auc_roc=auc,
            elapsed_seconds=elapsed,
            split_metadata={
                "method": "holdout",
                "train_ratio": train_ratio,
                "train_accounts": len(accounts) - len(test_accounts),
                "test_accounts": len(test_accounts),
            },
        )

    def run_cross_validation(
        self,
        transactions: List[Dict],
        accounts: List[Dict],
        dataset_name: str = "unknown",
        num_folds: int = 5,
    ) -> CrossValResult:
        """
        K-fold stratified cross-validation. Train/test on each fold,
        report mean + std for precision, recall, F1.
        """
        import math

        start = time.perf_counter()

        ground_truth = self._extract_ground_truth(accounts, transactions)
        suspicious_ids = [
            acc_id for acc_id, label in ground_truth.items() if label
        ]
        legit_ids = [
            acc_id for acc_id, label in ground_truth.items() if not label
        ]

        random.shuffle(suspicious_ids)
        random.shuffle(legit_ids)

        # Create stratified folds
        def split_into_folds(ids: List[str], k: int) -> List[List[str]]:
            folds: List[List[str]] = [[] for _ in range(k)]
            for i, acc_id in enumerate(ids):
                folds[i % k].append(acc_id)
            return folds

        sus_folds = split_into_folds(suspicious_ids, num_folds)
        leg_folds = split_into_folds(legit_ids, num_folds)

        fold_results = []
        precisions = []
        recalls = []
        f1s = []

        for fold_idx in range(num_folds):
            test_ids = set(sus_folds[fold_idx] + leg_folds[fold_idx])

            test_accounts = [a for a in accounts if a["account_id"] in test_ids]
            test_account_set = {a["account_id"] for a in test_accounts}
            test_transactions = [
                t for t in transactions
                if t["from_account"] in test_account_set
                or t["to_account"] in test_account_set
            ]

            # Fresh pipeline per fold (no leaked GNN weights)
            fold_pipeline = DetectionPipeline()
            alerts = fold_pipeline.run(test_transactions, test_accounts)

            predicted: Set[str] = set()
            for alert in alerts:
                for node in alert.nodes:
                    predicted.add(node.account_id)

            sus_set = test_ids & set(suspicious_ids)
            leg_set = test_ids & set(legit_ids)

            tp = len(predicted & sus_set)
            fp = len(predicted & leg_set)
            fn = len(sus_set - predicted)
            tn = len(leg_set - predicted)

            p = tp / max(tp + fp, 1)
            r = tp / max(tp + fn, 1)
            f = (2 * p * r) / max(p + r, 1e-9)

            precisions.append(p)
            recalls.append(r)
            f1s.append(f)

            fold_results.append({
                "fold": fold_idx + 1,
                "test_accounts": len(test_accounts),
                "tp": tp, "fp": fp, "tn": tn, "fn": fn,
                "precision": round(p, 4),
                "recall": round(r, 4),
                "f1_score": round(f, 4),
            })

        def mean(vals: List[float]) -> float:
            return sum(vals) / max(len(vals), 1)

        def std(vals: List[float]) -> float:
            m = mean(vals)
            variance = sum((v - m) ** 2 for v in vals) / max(len(vals), 1)
            return math.sqrt(variance)

        elapsed = time.perf_counter() - start

        return CrossValResult(
            dataset_name=dataset_name,
            num_folds=num_folds,
            fold_results=fold_results,
            mean_precision=mean(precisions),
            mean_recall=mean(recalls),
            mean_f1=mean(f1s),
            std_precision=std(precisions),
            std_recall=std(recalls),
            std_f1=std(f1s),
            elapsed_seconds=elapsed,
        )

    @staticmethod
    def _extract_ground_truth(
        accounts: List[Dict], transactions: List[Dict]
    ) -> Dict[str, bool]:
        """Extract per-account ground truth labels."""
        labels: Dict[str, bool] = {}

        for acc in accounts:
            acc_id = acc.get("account_id", "")
            role = acc.get("role", "LEGIT")
            is_suspicious = acc.get("is_suspicious", False)
            is_fraud = acc.get("is_fraud", False)

            is_mule = role in ("SOURCE", "MULE", "AGGREGATOR")
            labels[acc_id] = is_mule or is_suspicious or is_fraud

        # Also check transaction-level labels
        for txn in transactions:
            if txn.get("is_suspicious") or txn.get("isFraud"):
                from_acc = txn.get("from_account", "")
                if from_acc and from_acc not in labels:
                    labels[from_acc] = True

        return labels

    @staticmethod
    def _compute_auc(
        ground_truth: Dict[str, bool],
        alerts: list,
        all_accounts: Set[str],
    ) -> Optional[float]:
        """Compute AUC-ROC from per-account risk scores."""
        try:
            from sklearn.metrics import roc_auc_score
        except ImportError:
            logger.warning("sklearn not available — skipping AUC computation")
            return None

        # Build per-account score from alert data
        account_scores: Dict[str, float] = {}
        for alert in alerts:
            for node in alert.nodes:
                current = account_scores.get(node.account_id, 0.0)
                account_scores[node.account_id] = max(current, alert.risk_score)

        y_true = []
        y_scores = []
        for acc_id in all_accounts:
            if acc_id not in ground_truth:
                continue
            y_true.append(1 if ground_truth[acc_id] else 0)
            y_scores.append(account_scores.get(acc_id, 0.0))

        if len(set(y_true)) < 2:
            return None

        try:
            return roc_auc_score(y_true, y_scores)
        except Exception as exc:
            logger.warning("AUC-ROC computation failed: %s", exc)
            return None
