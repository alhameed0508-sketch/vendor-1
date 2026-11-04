"""One ring rule for both engines: the batch pipeline and the per-payment scorer."""

from types import SimpleNamespace

import pytest

from backend.detection import pipeline as pipeline_module
from backend.detection.pipeline import DetectionPipeline
from backend.detection.ring_decision import (
    ENDPOINT_EVIDENCE_MIN,
    MIN_RING_PURITY,
    ring_is_flaggable,
)
from data.synthetic.generator import build_full_dataset


def _ring(accounts, suspicion=0.8):
    return SimpleNamespace(accounts=frozenset(accounts), size=len(accounts), suspicion_score=suspicion)


def _evidence(**scores):
    return {acc: SimpleNamespace(smurf_score=s) for acc, s in scores.items()}


def test_flags_a_pure_suspicious_ring():
    ring = _ring("ABCD")
    assert ring_is_flaggable(ring, _evidence(A=0.9, B=0.8, C=0.7, D=0.6))


def test_rejects_a_ring_where_few_members_carry_evidence():
    ring = _ring("ABCDEFGHIJ")
    # one evidenced member of ten is 10%, below MIN_RING_PURITY
    assert MIN_RING_PURITY > 0.1
    assert not ring_is_flaggable(ring, _evidence(A=0.95))


def test_rejects_a_ring_smaller_than_three_accounts():
    assert not ring_is_flaggable(_ring("AB"), _evidence(A=0.9, B=0.9))


def test_rejects_a_ring_below_the_flag_threshold():
    weak = _evidence(A=ENDPOINT_EVIDENCE_MIN, B=ENDPOINT_EVIDENCE_MIN, C=ENDPOINT_EVIDENCE_MIN)
    assert not ring_is_flaggable(_ring("ABC", suspicion=0.2), weak)


def test_merchants_are_not_evidence():
    ring = _ring("ABC")
    evidence = _evidence(A=0.9, B=0.9, C=0.9)
    assert ring_is_flaggable(ring, evidence)
    assert not ring_is_flaggable(ring, evidence, merchants=frozenset("ABC"))


@pytest.fixture(scope="module")
def dataset():
    return build_full_dataset(num_clusters=2, num_legit_accounts=20)


def test_pipeline_alerts_only_for_rings_the_shared_gate_accepts(dataset, monkeypatch):
    baseline = DetectionPipeline().run(dataset["transactions"], dataset["accounts"])
    assert baseline, "the synthetic data must contain rings"
    monkeypatch.setattr(pipeline_module, "ring_is_flaggable", lambda *a, **k: False)
    assert DetectionPipeline().run(dataset["transactions"], dataset["accounts"]) == []
