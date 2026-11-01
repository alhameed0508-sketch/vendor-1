"""Evasion playbooks reshape mule traffic without mutating inputs or touching genuine payments."""

import copy
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "evaluation"))

from evasion_playbooks import NOISE_PER_MULE, PLAYBOOKS, SPLIT_PARTS  # noqa: E402

IS_MULE = {"M1": True, "M2": True, "G1": False, "G2": False}
TXNS = [
    {"txn_id": "T1", "from_account": "M1", "to_account": "M2", "amount": 900.0, "timestamp": "2026-01-01T10:00:00"},
    {"txn_id": "T2", "from_account": "M2", "to_account": "M1", "amount": 600.0, "timestamp": "2026-01-01T12:00:00"},
    {"txn_id": "T3", "from_account": "G1", "to_account": "G2", "amount": 50.0, "timestamp": "2026-01-01T11:00:00"},
]


def run(name):
    return PLAYBOOKS[name](TXNS, IS_MULE, random.Random(1))


def test_inputs_are_not_mutated():
    before = copy.deepcopy(TXNS)
    for name in PLAYBOOKS:
        run(name)
    assert TXNS == before


def test_genuine_payment_unchanged_in_every_playbook():
    for name in PLAYBOOKS:
        assert TXNS[2] in run(name)


def test_split_keeps_total_and_makes_parts():
    out = run("split")
    parts = [t for t in out if t["txn_id"].startswith("T1-")]
    assert len(parts) == SPLIT_PARTS
    assert abs(sum(t["amount"] for t in parts) - 900.0) < 0.05
    assert len({t["txn_id"] for t in out}) == len(out)


def test_noise_adds_small_decoys_between_mules_and_genuine():
    out = run("noise")
    decoys = [t for t in out if t["txn_id"].startswith("NOISE-")]
    assert len(decoys) == NOISE_PER_MULE * 2
    assert all(IS_MULE[t["from_account"]] != IS_MULE[t["to_account"]] for t in decoys)


def test_slow_drip_stretches_gaps_between_mule_payments():
    out = {t["txn_id"]: t for t in run("slow_drip")}
    assert out["T1"]["timestamp"] == TXNS[0]["timestamp"]
    assert out["T2"]["timestamp"] == "2026-01-01T22:00:00"  # 2 h gap x SLOW_FACTOR 6
