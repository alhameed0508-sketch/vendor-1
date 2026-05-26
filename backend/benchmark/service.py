"""
Benchmark Service — orchestrates benchmark runs on synthetic and PaySim data.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

from benchmark.runner import BenchmarkResult, BenchmarkRunner, CrossValResult
from detection.pipeline import DetectionPipeline

logger = logging.getLogger(__name__)

RESULTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "benchmark_results.json"
)


class BenchmarkService:
    """Orchestrates synthetic + PaySim benchmark runs."""

    def __init__(self, pipeline: Optional[DetectionPipeline] = None):
        self._runner = BenchmarkRunner(pipeline)

    def run_synthetic(
        self, num_clusters: int = 3, num_legit_accounts: int = 30
    ) -> BenchmarkResult:
        """Run benchmark on MuleCatch synthetic data."""
        from data.synthetic.generator import build_full_dataset

        dataset = build_full_dataset(
            num_clusters=num_clusters,
            num_legit_accounts=num_legit_accounts,
        )
        result = self._runner.run(
            transactions=dataset["transactions"],
            accounts=dataset["accounts"],
            dataset_name=f"synthetic_{num_clusters}clusters",
        )
        self._save_result(result)
        return result

    def run_paysim(self, csv_path: str, max_rows: int = 50000) -> BenchmarkResult:
        """Run benchmark on PaySim dataset."""
        from data.adapters.paysim_adapter import PaySimAdapter

        adapter = PaySimAdapter()
        transactions, accounts = adapter.load(csv_path, max_rows=max_rows)

        result = self._runner.run(
            transactions=transactions,
            accounts=accounts,
            dataset_name="paysim",
        )
        self._save_result(result)
        return result

    def run_adversarial(
        self,
        num_clusters: int = 3,
        num_legit: int = 30,
        num_adversarial: int = 20,
    ) -> BenchmarkResult:
        """Run holdout benchmark on adversarial dataset."""
        from data.synthetic.generator import build_adversarial_dataset

        dataset = build_adversarial_dataset(
            num_clusters=num_clusters,
            num_legit_accounts=num_legit,
            num_adversarial=num_adversarial,
        )
        result = self._runner.run_holdout(
            transactions=dataset["transactions"],
            accounts=dataset["accounts"],
            dataset_name=f"adversarial_{num_clusters}c_{num_adversarial}adv",
        )
        self._save_result(result)
        return result

    def run_cross_validation(
        self,
        num_clusters: int = 3,
        num_legit: int = 30,
        num_folds: int = 5,
    ) -> CrossValResult:
        """Run k-fold cross-validation on synthetic data."""
        from data.synthetic.generator import build_full_dataset

        dataset = build_full_dataset(
            num_clusters=num_clusters,
            num_legit_accounts=num_legit,
        )
        return self._runner.run_cross_validation(
            transactions=dataset["transactions"],
            accounts=dataset["accounts"],
            dataset_name=f"crossval_{num_clusters}clusters_{num_folds}folds",
            num_folds=num_folds,
        )

    def run_full_evaluation(self) -> Dict:
        """
        Run comprehensive evaluation: standard synthetic, adversarial,
        and cross-validation. Returns combined report.
        """
        standard = self.run_synthetic(num_clusters=3, num_legit_accounts=30)
        adversarial = self.run_adversarial(
            num_clusters=3, num_legit=30, num_adversarial=20,
        )
        crossval = self.run_cross_validation(
            num_clusters=3, num_legit=30, num_folds=5,
        )
        return {
            "standard": standard.to_dict(),
            "adversarial": adversarial.to_dict(),
            "cross_validation": crossval.to_dict(),
        }

    def run_comparison(self) -> List[Dict]:
        """Run multi-config comparison on synthetic data."""
        results = []
        for n_clusters in [3, 5, 8]:
            result = self.run_synthetic(
                num_clusters=n_clusters,
                num_legit_accounts=n_clusters * 10,
            )
            results.append(result.to_dict())
        return results

    def get_saved_results(self) -> List[Dict]:
        """Load previously saved benchmark results."""
        if not os.path.exists(RESULTS_PATH):
            return []
        try:
            with open(RESULTS_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _save_result(self, result: BenchmarkResult) -> None:
        """Append result to persistent storage."""
        results = self.get_saved_results()
        results.append(result.to_dict())
        # Keep last 50 results
        results = results[-50:]
        try:
            os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
            with open(RESULTS_PATH, "w") as f:
                json.dump(results, f, indent=2)
        except OSError as exc:
            logger.warning("Failed to save benchmark results: %s", exc)
