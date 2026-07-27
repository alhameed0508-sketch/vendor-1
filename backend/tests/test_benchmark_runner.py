"""Metric and persistence tests for the benchmark engine."""

import json

import pytest

from benchmark.runner import BenchmarkRunner
from benchmark.service import BenchmarkService
from core.config import Settings


class EmptyPipeline:
    def run(self, transactions, accounts):
        return []


def test_runner_reports_accuracy_with_empty_predictions():
    runner = BenchmarkRunner(EmptyPipeline())
    accounts = [
        {"account_id": "mule", "role": "MULE"},
        {"account_id": "legit-1", "role": "LEGIT"},
        {"account_id": "legit-2", "role": "LEGIT"},
    ]

    result = runner.run([], accounts, "metric-test")

    assert result.true_negatives == 2
    assert result.false_negatives == 1
    assert result.accuracy == pytest.approx(2 / 3)
    assert result.to_dict()["accuracy"] == 0.6667


def test_cross_validation_rejects_more_folds_than_smallest_class():
    runner = BenchmarkRunner(EmptyPipeline())
    accounts = [
        {"account_id": "mule", "role": "MULE"},
        {"account_id": "legit-1", "role": "LEGIT"},
        {"account_id": "legit-2", "role": "LEGIT"},
    ]

    with pytest.raises(ValueError, match="smallest ground-truth class"):
        runner.run_cross_validation([], accounts, num_folds=2)


def test_service_saves_normalized_result_atomically(tmp_path):
    results_path = tmp_path / "benchmark_results.json"
    service = BenchmarkService(
        pipeline=EmptyPipeline(),
        results_path=str(results_path),
    )

    service._save_payload(
        "synthetic",
        {"accuracy": 0.9},
        {"num_clusters": 3},
    )

    records = json.loads(results_path.read_text(encoding="utf-8"))
    assert records[0]["benchmark_type"] == "synthetic"
    assert records[0]["result"]["accuracy"] == 0.9
    assert records[0]["run_id"].startswith("BENCH_")
    assert list(tmp_path.glob("*.tmp")) == []


def test_benchmark_results_path_is_configurable():
    settings = Settings(BENCHMARK_RESULTS_PATH="/app/logs/benchmark-results.json")

    assert settings.benchmark_results_path == "/app/logs/benchmark-results.json"
