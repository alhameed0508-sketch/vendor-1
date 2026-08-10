"""Executable benchmark API for development and controlled evaluation."""

from api.deps import get_benchmark_service
from api.v1.schemas.benchmark import (
    AdversarialBenchmarkRequest,
    ComparisonRequest,
    CrossValidationRequest,
    SyntheticBenchmarkRequest,
)
from benchmark.service import BenchmarkBusyError, BenchmarkService
from core.config import get_settings
from core.exceptions import ConflictError, ValidationError
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from middleware.auth import require_role
from slowapi import Limiter

BENCHMARK_ROLES = ("ADMIN", "SUPERVISOR")
READ_ROLES = ("ADMIN", "SUPERVISOR", "INVESTIGATOR", "AUDITOR")


def _ensure_execution_enabled() -> None:
    if not get_settings().demo_mode:
        raise ConflictError(
            "Synthetic benchmark execution is disabled in production",
            "Run approved offline validation against a governed dataset and model artifact.",
        )


def _execute(
    service: BenchmarkService,
    benchmark_type: str,
    parameters: dict | None = None,
) -> dict:
    _ensure_execution_enabled()
    try:
        return service.execute(benchmark_type, parameters)
    except BenchmarkBusyError as exc:
        raise ConflictError(
            "A benchmark is already running",
            str(exc),
        ) from exc
    except ValueError as exc:
        raise ValidationError(
            "Benchmark parameters are not valid for the generated dataset",
            str(exc),
        ) from exc


def register_benchmark_routes(router: APIRouter, limiter: Limiter) -> None:
    """Register model evaluation routes under ``/api/v1/benchmark``."""

    @router.get("/capabilities")
    def capabilities(
        user: dict = Depends(require_role(*READ_ROLES)),
    ):
        enabled = get_settings().demo_mode
        return success_response(
            {
                "execution_enabled": enabled,
                "production_safe": not enabled,
                "available_benchmarks": [
                    "synthetic",
                    "adversarial",
                    "cross_validation",
                    "comparison",
                    "full_evaluation",
                ],
                "restriction": (None if enabled else "Synthetic execution is disabled in production."),
            }
        )

    @router.get("/results")
    def saved_results(
        user: dict = Depends(require_role(*READ_ROLES)),
        service: BenchmarkService = Depends(get_benchmark_service),
    ):
        return success_response({"results": service.get_saved_results()})

    @router.post("/synthetic")
    @limiter.limit("3/minute")
    def synthetic(
        request: Request,
        body: SyntheticBenchmarkRequest,
        user: dict = Depends(require_role(*BENCHMARK_ROLES)),
        service: BenchmarkService = Depends(get_benchmark_service),
    ):
        return success_response(_execute(service, "synthetic", body.model_dump()))

    @router.post("/adversarial")
    @limiter.limit("3/minute")
    def adversarial(
        request: Request,
        body: AdversarialBenchmarkRequest,
        user: dict = Depends(require_role(*BENCHMARK_ROLES)),
        service: BenchmarkService = Depends(get_benchmark_service),
    ):
        return success_response(_execute(service, "adversarial", body.model_dump()))

    @router.post("/cross-validation")
    @limiter.limit("2/minute")
    def cross_validation(
        request: Request,
        body: CrossValidationRequest,
        user: dict = Depends(require_role(*BENCHMARK_ROLES)),
        service: BenchmarkService = Depends(get_benchmark_service),
    ):
        return success_response(_execute(service, "cross_validation", body.model_dump()))

    @router.post("/comparison")
    @limiter.limit("1/minute")
    def comparison(
        request: Request,
        body: ComparisonRequest,
        user: dict = Depends(require_role(*BENCHMARK_ROLES)),
        service: BenchmarkService = Depends(get_benchmark_service),
    ):
        return success_response(_execute(service, "comparison", body.model_dump()))

    @router.post("/full-evaluation")
    @limiter.limit("1/minute")
    def full_evaluation(
        request: Request,
        user: dict = Depends(require_role(*BENCHMARK_ROLES)),
        service: BenchmarkService = Depends(get_benchmark_service),
    ):
        return success_response(_execute(service, "full_evaluation"))
