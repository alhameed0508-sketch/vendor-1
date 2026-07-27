"""API contract tests for executable model benchmark programs."""

from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import get_benchmark_service
from core.config import get_settings
from core.exceptions import ConflictError


@dataclass
class FakeBenchmarkService:
    calls: list

    def execute(self, benchmark_type, parameters=None):
        self.calls.append((benchmark_type, parameters or {}))
        if benchmark_type == "cross_validation":
            return {
                "dataset_name": "crossval",
                "num_folds": 5,
                "fold_results": [],
                "mean_precision": 0.8,
                "mean_recall": 0.7,
                "mean_f1": 0.7467,
                "mean_accuracy": 0.9,
            }
        if benchmark_type == "comparison":
            return {"benchmark_type": "comparison", "benchmarks": []}
        if benchmark_type == "full_evaluation":
            return {"benchmark_type": "full_evaluation", "summary": {}}
        return {
            "dataset_name": benchmark_type,
            "precision": 0.8,
            "recall": 0.7,
            "f1_score": 0.7467,
            "accuracy": 0.9,
        }

    def get_saved_results(self):
        return [{"run_id": "BENCH_TEST", "result": {"f1_score": 0.75}}]


@pytest.fixture
def benchmark_service():
    return FakeBenchmarkService(calls=[])


@pytest.fixture
def benchmark_app(monkeypatch, benchmark_service):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()

    from api.app import app

    app.dependency_overrides[get_benchmark_service] = lambda: benchmark_service
    yield app
    app.dependency_overrides.pop(get_benchmark_service, None)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_benchmark_capabilities_and_saved_results(benchmark_app):
    transport = ASGITransport(app=benchmark_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        capabilities = await client.get("/api/v1/benchmark/capabilities")
        history = await client.get("/api/v1/benchmark/results")

    assert capabilities.status_code == 200
    assert capabilities.json()["data"]["execution_enabled"] is True
    assert len(capabilities.json()["data"]["available_benchmarks"]) == 5
    assert history.status_code == 200
    assert history.json()["data"]["results"][0]["run_id"] == "BENCH_TEST"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload", "expected_type"),
    [
        (
            "/api/v1/benchmark/synthetic",
            {"num_clusters": 3, "num_legit_accounts": 30},
            "synthetic",
        ),
        (
            "/api/v1/benchmark/adversarial",
            {"num_clusters": 3, "num_legit": 30, "num_adversarial": 20},
            "adversarial",
        ),
        (
            "/api/v1/benchmark/cross-validation",
            {"num_clusters": 3, "num_legit": 30, "num_folds": 5},
            "cross_validation",
        ),
        (
            "/api/v1/benchmark/comparison",
            {"cluster_counts": [3, 5, 8]},
            "comparison",
        ),
        (
            "/api/v1/benchmark/full-evaluation",
            None,
            "full_evaluation",
        ),
    ],
)
async def test_benchmark_programs_call_real_service_contract(
    benchmark_app,
    benchmark_service,
    path,
    payload,
    expected_type,
):
    transport = ASGITransport(app=benchmark_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json=payload)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert benchmark_service.calls[-1][0] == expected_type


@pytest.mark.asyncio
async def test_benchmark_request_limits_are_validated(benchmark_app):
    transport = ASGITransport(app=benchmark_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/benchmark/cross-validation",
            json={"num_clusters": 99, "num_legit": 2, "num_folds": 1},
        )

    assert response.status_code == 422


def test_benchmark_execution_is_rejected_in_production(monkeypatch):
    from api.v1.routes.benchmark import _ensure_execution_enabled

    monkeypatch.setenv("ENV", "production")
    get_settings.cache_clear()
    with pytest.raises(ConflictError, match="disabled in production"):
        _ensure_execution_enabled()
    get_settings.cache_clear()
