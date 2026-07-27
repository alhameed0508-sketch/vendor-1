"""Validated request contracts for model benchmark execution."""

from typing import Annotated, List

from pydantic import BaseModel, Field


ClusterCount = Annotated[int, Field(ge=1, le=8)]


class SyntheticBenchmarkRequest(BaseModel):
    num_clusters: ClusterCount = 3
    num_legit_accounts: int = Field(30, ge=10, le=500)


class AdversarialBenchmarkRequest(BaseModel):
    num_clusters: ClusterCount = 3
    num_legit: int = Field(30, ge=10, le=500)
    num_adversarial: int = Field(20, ge=1, le=200)


class CrossValidationRequest(BaseModel):
    num_clusters: ClusterCount = 3
    num_legit: int = Field(30, ge=10, le=500)
    num_folds: int = Field(5, ge=2, le=10)


class ComparisonRequest(BaseModel):
    cluster_counts: List[ClusterCount] = Field(
        default_factory=lambda: [3, 5, 8],
        min_length=2,
        max_length=5,
    )
