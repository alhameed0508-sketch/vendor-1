"""
Benchmark Service — orchestrates benchmark runs on synthetic and PaySim data.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from benchmark.runner import BenchmarkResult, BenchmarkRunner, CrossValResult
from detection.pipeline import DetectionPipeline

logger = logging.getLogger(__name__)

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "benchmark_results.json")


class BenchmarkService:
    """Orchestrates serialized, reproducible detection benchmark runs."""

    def __init__(
        self,
        pipeline: Optional[DetectionPipeline] = None,
        results_path: Optional[str] = None,
    ):
        self._runner = BenchmarkRunner(pipeline)
        self._results_path = results_path or RESULTS_PATH
        self._run_lock = threading.Lock()

    def execute(self, benchmark_type: str, parameters: Optional[Dict] = None) -> Dict:
        """Run one supported benchmark while preventing overlapping evaluations."""
        parameters = parameters or {}
        if not self._run_lock.acquire(blocking=False):
            raise BenchmarkBusyError("Another benchmark is already running in this API worker")
        try:
            if benchmark_type == "synthetic":
                result = self.run_synthetic(**parameters)
                return result.to_dict()
            if benchmark_type == "adversarial":
                result = self.run_adversarial(**parameters)
                return result.to_dict()
            if benchmark_type == "cross_validation":
                result = self.run_cross_validation(**parameters)
                return result.to_dict()
            if benchmark_type == "comparison":
                return self.run_comparison(**parameters)
            if benchmark_type == "full_evaluation":
                return self.run_full_evaluation()
            raise ValueError(f"Unsupported benchmark type: {benchmark_type}")
        finally:
            self._run_lock.release()

    def run_synthetic(
        self,
        num_clusters: int = 3,
        num_legit_accounts: int = 30,
        *,
        persist: bool = True,
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
        if persist:
            self._save_payload(
                "synthetic",
                result.to_dict(),
                {
                    "num_clusters": num_clusters,
                    "num_legit_accounts": num_legit_accounts,
                },
            )
        return result

    def run_paysim(
        self,
        csv_path: str,
        max_rows: int = 50000,
        *,
        persist: bool = True,
    ) -> BenchmarkResult:
        """Run benchmark on PaySim dataset."""
        from data.adapters.paysim_adapter import PaySimAdapter

        adapter = PaySimAdapter()
        transactions, accounts = adapter.load(csv_path, max_rows=max_rows)

        result = self._runner.run(
            transactions=transactions,
            accounts=accounts,
            dataset_name="paysim",
        )
        if persist:
            self._save_payload(
                "paysim",
                result.to_dict(),
                {"max_rows": max_rows},
            )
        return result

    def run_adversarial(
        self,
        num_clusters: int = 3,
        num_legit: int = 30,
        num_adversarial: int = 20,
        *,
        persist: bool = True,
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
        if persist:
            self._save_payload(
                "adversarial",
                result.to_dict(),
                {
                    "num_clusters": num_clusters,
                    "num_legit": num_legit,
                    "num_adversarial": num_adversarial,
                },
            )
        return result

    def run_cross_validation(
        self,
        num_clusters: int = 3,
        num_legit: int = 30,
        num_folds: int = 5,
        *,
        persist: bool = True,
    ) -> CrossValResult:
        """Run k-fold cross-validation on synthetic data."""
        from data.synthetic.generator import build_full_dataset

        dataset = build_full_dataset(
            num_clusters=num_clusters,
            num_legit_accounts=num_legit,
        )
        result = self._runner.run_cross_validation(
            transactions=dataset["transactions"],
            accounts=dataset["accounts"],
            dataset_name=f"crossval_{num_clusters}clusters_{num_folds}folds",
            num_folds=num_folds,
        )
        if persist:
            self._save_payload(
                "cross_validation",
                result.to_dict(),
                {
                    "num_clusters": num_clusters,
                    "num_legit": num_legit,
                    "num_folds": num_folds,
                },
            )
        return result

    def run_full_evaluation(self) -> Dict:
        """
        Run comprehensive evaluation: standard synthetic, adversarial,
        and cross-validation. Returns combined report.
        """
        standard = self.run_synthetic(
            num_clusters=3,
            num_legit_accounts=30,
            persist=False,
        )
        adversarial = self.run_adversarial(
            num_clusters=3,
            num_legit=30,
            num_adversarial=20,
            persist=False,
        )
        crossval = self.run_cross_validation(
            num_clusters=3,
            num_legit=30,
            num_folds=5,
            persist=False,
        )
        result = {
            "benchmark_type": "full_evaluation",
            "summary": standard.to_dict(),
            "standard": standard.to_dict(),
            "adversarial": adversarial.to_dict(),
            "cross_validation": crossval.to_dict(),
        }
        self._save_payload("full_evaluation", result, {})
        return result

    def run_comparison(
        self,
        cluster_counts: Optional[List[int]] = None,
    ) -> Dict:
        """Run multi-config comparison on synthetic data."""
        cluster_counts = cluster_counts or [3, 5, 8]
        results = []
        for n_clusters in cluster_counts:
            result = self.run_synthetic(
                num_clusters=n_clusters,
                num_legit_accounts=n_clusters * 10,
                persist=False,
            )
            item = result.to_dict()
            item["config"] = f"{n_clusters} clusters"
            results.append(item)
        payload = {
            "benchmark_type": "comparison",
            "benchmarks": results,
        }
        self._save_payload(
            "comparison",
            payload,
            {"cluster_counts": cluster_counts},
        )
        return payload

    def get_saved_results(self) -> List[Dict]:
        """Load previously saved benchmark results."""
        if not os.path.exists(self._results_path):
            return []
        try:
            with open(self._results_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, TypeError):
            return []

    def _save_payload(
        self,
        benchmark_type: str,
        result: Dict,
        parameters: Dict,
    ) -> None:
        """Atomically append a normalized benchmark record."""
        results = self.get_saved_results()
        results.append(
            {
                "run_id": f"BENCH_{uuid.uuid4().hex[:12].upper()}",
                "benchmark_type": benchmark_type,
                "parameters": parameters,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
            }
        )
        results = results[-50:]
        directory = os.path.dirname(self._results_path) or "."
        temporary_path = None
        try:
            os.makedirs(directory, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".tmp",
                prefix="benchmark_",
                dir=directory,
                delete=False,
            ) as temporary:
                temporary_path = temporary.name
                json.dump(results, temporary, indent=2)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self._results_path)
        except OSError as exc:
            logger.warning("Failed to save benchmark results: %s", exc)
            if temporary_path and os.path.exists(temporary_path):
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass


class BenchmarkBusyError(RuntimeError):
    """Raised when an API worker is already executing a benchmark."""
