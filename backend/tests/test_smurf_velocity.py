"""The velocity score must match the brute-force definition while running in O(k log k)."""

import random
from datetime import datetime, timedelta

import pytest
from models.temporal_weighting.smurf_weighting import SmurfWeightingEngine, Transaction

START = datetime(2026, 1, 1, 9, 0, 0)


def _txn(i: int, when: datetime) -> Transaction:
    return Transaction(
        txn_id=f"T{i}",
        from_account="A",
        to_account="B",
        amount=1000.0,
        timestamp=when,
        device_id="",
        ip_address="",
    )


def _reference(engine: SmurfWeightingEngine, txns) -> float:
    """The original quadratic definition, kept here as the oracle."""
    if len(txns) < 2:
        return 0.0
    stamps = sorted(t.timestamp for t in txns)
    best = 0
    for i, ts in enumerate(stamps):
        end = ts + timedelta(minutes=engine.velocity_minutes)
        best = max(best, sum(1 for later in stamps[i:] if later <= end))
    return min(best / 12.0, 1.0)


@pytest.mark.parametrize("minutes", [60, 360])
@pytest.mark.parametrize("seed", range(5))
def test_velocity_matches_reference(seed, minutes):
    rng = random.Random(seed)
    engine = SmurfWeightingEngine(velocity_minutes=minutes)
    txns = [_txn(i, START + timedelta(minutes=rng.randint(0, 5000))) for i in range(rng.randint(2, 80))]
    assert engine._velocity_score(txns) == pytest.approx(_reference(engine, txns))


def test_velocity_counts_ties_and_window_edge():
    engine = SmurfWeightingEngine(velocity_minutes=60)
    txns = [
        _txn(0, START),
        _txn(1, START),
        _txn(2, START + timedelta(minutes=60)),
        _txn(3, START + timedelta(minutes=61)),
    ]
    assert engine._velocity_score(txns) == pytest.approx(_reference(engine, txns))


def test_velocity_handles_empty_and_single():
    engine = SmurfWeightingEngine()
    assert engine._velocity_score([]) == 0.0
    assert engine._velocity_score([_txn(0, START)]) == 0.0


def test_velocity_scales_to_large_account():
    engine = SmurfWeightingEngine()
    txns = [_txn(i, START + timedelta(seconds=i)) for i in range(20000)]
    assert engine._velocity_score(txns) == 1.0
