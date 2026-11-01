"""
Evasion playbooks: ways a mule operator might adapt to the detector.

Each playbook is a pure function (txns, is_mule, rng) -> new txns. Inputs are
never mutated. Only mule-to-mule payments are reshaped; genuine traffic is left
alone, except for decoys that mules send to or receive from genuine accounts.

  split      each mule payment becomes SPLIT_PARTS smaller payments a few minutes apart
  noise      mules exchange small decoy payments with random genuine accounts
  slow_drip  mule payments are spread out in time (gaps stretched SLOW_FACTOR times)
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Mapping, Sequence

SPLIT_PARTS = 3
SPLIT_GAP_MINUTES = 7
NOISE_PER_MULE = 4
NOISE_AMOUNT = 150.0
SLOW_FACTOR = 6

Txn = Dict
Playbook = Callable[[Sequence[Txn], Mapping[str, bool], random.Random], List[Txn]]


def _is_mule_payment(txn: Mapping, is_mule: Mapping[str, bool]) -> bool:
    return is_mule.get(txn["from_account"], False) and is_mule.get(txn["to_account"], False)


def _when(txn: Mapping) -> datetime:
    value = txn["timestamp"]
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def split(txns: Sequence[Txn], is_mule: Mapping[str, bool], rng: random.Random) -> List[Txn]:
    out: List[Txn] = []
    for t in txns:
        if not _is_mule_payment(t, is_mule):
            out.append(dict(t))
            continue
        start, part = _when(t), round(float(t["amount"]) / SPLIT_PARTS, 2)
        out.extend(
            {
                **t,
                "txn_id": f"{t['txn_id']}-s{i}",
                "amount": part,
                "timestamp": (start + timedelta(minutes=SPLIT_GAP_MINUTES * i)).isoformat(),
            }
            for i in range(SPLIT_PARTS)
        )
    return out


def noise(txns: Sequence[Txn], is_mule: Mapping[str, bool], rng: random.Random) -> List[Txn]:
    mules = sorted(a for a, m in is_mule.items() if m)
    genuine = sorted(a for a, m in is_mule.items() if not m)
    if not txns or not mules or not genuine:
        return [dict(t) for t in txns]
    times = sorted(_when(t) for t in txns)
    decoys = []
    for mule in mules:
        for n in range(NOISE_PER_MULE):
            other = rng.choice(genuine)
            sender, receiver = (mule, other) if n % 2 == 0 else (other, mule)
            decoys.append(
                {
                    "txn_id": f"NOISE-{mule}-{n}",
                    "from_account": sender,
                    "to_account": receiver,
                    "amount": NOISE_AMOUNT,
                    "timestamp": rng.choice(times).isoformat(),
                }
            )
    return [*(dict(t) for t in txns), *decoys]


def slow_drip(txns: Sequence[Txn], is_mule: Mapping[str, bool], rng: random.Random) -> List[Txn]:
    mule_times = [_when(t) for t in txns if _is_mule_payment(t, is_mule)]
    if not mule_times:
        return [dict(t) for t in txns]
    origin = min(mule_times)
    return [
        {**t, "timestamp": (origin + (_when(t) - origin) * SLOW_FACTOR).isoformat()}
        if _is_mule_payment(t, is_mule)
        else dict(t)
        for t in txns
    ]


PLAYBOOKS: Dict[str, Playbook] = {"split": split, "noise": noise, "slow_drip": slow_drip}
