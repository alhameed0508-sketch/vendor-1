"""
Benchmark routes — /api/v1/benchmark/*
Run detection pipeline on labeled datasets and compute precision/recall/F1.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from slowapi import Limiter

from core.response import success_response, error_response
from middleware.auth import require_permission
from api.deps import get_benchmark_service
from benchmark.service import BenchmarkService


class SyntheticBenchmarkRequest(BaseModel):
    num_clusters: int = 3
    num_legit_accounts: int = 30


class AdversarialBenchmarkRequest(BaseModel):
    num_clusters: int = 3
    num_legit: int = 30
    num_adversarial: int = 20


class CrossValRequest(BaseModel):
    num_clusters: int = 3
    num_legit: int = 30
    num_folds: int = 5


class PaySimBenchmarkRequest(BaseModel):
    csv_path: str
    max_rows: int = 50000


def register_benchmark_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register benchmark routes on the given router."""

    @r.post("/benchmark/synthetic")
    @limiter.limit("10/minute")
    def run_synthetic_benchmark(
        request: Request,
        body: SyntheticBenchmarkRequest = SyntheticBenchmarkRequest(),
        user: dict = Depends(require_permission("alerts:read")),
        svc: BenchmarkService = Depends(get_benchmark_service),
    ):
        """Run detection benchmark on synthetic data."""
        result = svc.run_synthetic(
            num_clusters=body.num_clusters,
            num_legit_accounts=body.num_legit_accounts,
        )
        return success_response(result.to_dict())

    @r.post("/benchmark/paysim")
    @limiter.limit("5/minute")
    def run_paysim_benchmark(
        request: Request,
        body: PaySimBenchmarkRequest,
        user: dict = Depends(require_permission("alerts:read")),
        svc: BenchmarkService = Depends(get_benchmark_service),
    ):
        """Run detection benchmark on PaySim CSV data."""
        import os
        if not os.path.exists(body.csv_path):
            return error_response(
                code="NOT_FOUND",
                message=f"PaySim CSV not found at {body.csv_path}",
                status_code=404,
            )
        result = svc.run_paysim(
            csv_path=body.csv_path,
            max_rows=body.max_rows,
        )
        return success_response(result.to_dict())

    @r.get("/benchmark/comparison")
    @limiter.limit("5/minute")
    def run_comparison(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        svc: BenchmarkService = Depends(get_benchmark_service),
    ):
        """Run multi-config comparison on synthetic data (3, 5, 8 clusters)."""
        results = svc.run_comparison()
        return success_response({"benchmarks": results})

    @r.post("/benchmark/adversarial")
    @limiter.limit("5/minute")
    def run_adversarial_benchmark(
        request: Request,
        body: AdversarialBenchmarkRequest = AdversarialBenchmarkRequest(),
        user: dict = Depends(require_permission("alerts:read")),
        svc: BenchmarkService = Depends(get_benchmark_service),
    ):
        """Run benchmark on adversarial dataset with holdout evaluation."""
        result = svc.run_adversarial(
            num_clusters=body.num_clusters,
            num_legit=body.num_legit,
            num_adversarial=body.num_adversarial,
        )
        return success_response(result.to_dict())

    @r.post("/benchmark/cross-validation")
    @limiter.limit("5/minute")
    def run_cross_validation(
        request: Request,
        body: CrossValRequest = CrossValRequest(),
        user: dict = Depends(require_permission("alerts:read")),
        svc: BenchmarkService = Depends(get_benchmark_service),
    ):
        """Run k-fold stratified cross-validation on synthetic data."""
        result = svc.run_cross_validation(
            num_clusters=body.num_clusters,
            num_legit=body.num_legit,
            num_folds=body.num_folds,
        )
        return success_response(result.to_dict())

    @r.get("/benchmark/full-evaluation")
    @limiter.limit("3/minute")
    def run_full_evaluation(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        svc: BenchmarkService = Depends(get_benchmark_service),
    ):
        """Run comprehensive evaluation: standard + adversarial + cross-validation."""
        result = svc.run_full_evaluation()
        return success_response(result)

    @r.get("/benchmark/results")
    @limiter.limit("30/minute")
    def get_results(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        svc: BenchmarkService = Depends(get_benchmark_service),
    ):
        """Retrieve previously saved benchmark results."""
        return success_response({"results": svc.get_saved_results()})
