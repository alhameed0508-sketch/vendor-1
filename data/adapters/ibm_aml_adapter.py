"""
IBM AMLworld (HI-Small) adapter: turns the public IBM synthetic AML dataset into MuleCatch cases.

The dataset has an independent generator (not ours): 5M payments in 15 currencies, with
laundering attempts of eight typologies (fan-out, fan-in, cycle, stack, ...) listed in a patterns
file. Download it to ``data/external/ibm-aml/`` (see docs/buildx/05-evaluation.md 7.8); it is never
committed.

Amounts are converted to rupees with fixed approximate rates (September 2022), so the scorer's
rupee thresholds keep their meaning. The rates are rough on purpose: nothing is tuned to them.

A case is a few laundering attempts, each mule's other payments (capped), and a few ordinary
accounts' payments (capped). Ground truth stays in the returned labels; payments carry only the
five fields the live scorer receives.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

# Approximate INR per unit, September 2022.
CURRENCY_TO_INR: Dict[str, float] = {
    "US Dollar": 80.0,
    "Euro": 80.0,
    "Swiss Franc": 83.0,
    "Yuan": 11.4,
    "Shekel": 23.0,
    "Yen": 0.56,
    "Ruble": 1.35,
    "Rupee": 1.0,
    "Canadian Dollar": 61.0,
    "Australian Dollar": 54.0,
    "Mexican Peso": 4.0,
    "Brazil Real": 15.5,
    "Saudi Riyal": 21.0,
    "UK Pound": 92.0,
    "Bitcoin": 1_600_000.0,
}
COLUMNS = ["ts", "from_bank", "from_acct", "to_bank", "to_acct", "amount", "currency", "laundering"]
USECOLS = [0, 1, 2, 3, 4, 7, 8, 10]
MIN_CONTROL_DEGREE, MAX_CONTROL_DEGREE = 5, 200
TXN_ID_PREFIX = "IBM-"


@dataclass(frozen=True)
class Attempt:
    typology: str
    rows: Tuple[int, ...]  # row indices into the frame


def _row_key(ts: str, src: str, dst: str, amount: float) -> Tuple[str, str, str, float]:
    return (ts, src, dst, round(amount, 2))


def _read_patterns(path: str) -> List[Tuple[str, List[Tuple]]]:
    attempts: List[Tuple[str, List[Tuple]]] = []
    typology: Optional[str] = None
    keys: List[Tuple] = []
    with open(path, newline="") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("BEGIN LAUNDERING ATTEMPT"):
                typology, keys = line.split(" - ", 1)[1].split(":")[0].strip(), []
            elif line.startswith("END LAUNDERING ATTEMPT"):
                attempts.append((typology or "UNKNOWN", keys))
                typology = None
            elif typology is not None and line:
                f = next(csv.reader([line]))
                keys.append(_row_key(f[0], f"{f[1]}-{f[2]}", f"{f[3]}-{f[4]}", float(f[7])))
    return attempts


class IbmAml:
    def __init__(self, frame: pd.DataFrame, attempts: List[Attempt]):
        self.frame = frame
        self.attempts = attempts
        self.laundering_ids: Set[str] = {f"{TXN_ID_PREFIX}{i}" for i in frame.index[frame.laundering == 1]}
        self._src = frame.src.to_numpy()
        self._dst = frame.dst.to_numpy()
        self._by_account = self._index_by_account()
        self._mule_accounts = set(frame.src[frame.laundering == 1]) | set(frame.dst[frame.laundering == 1])
        degree = {a: len(r) for a, r in self._by_account.items()}
        self._controls = sorted(
            a
            for a, d in degree.items()
            if MIN_CONTROL_DEGREE <= d <= MAX_CONTROL_DEGREE and a not in self._mule_accounts
        )

    @classmethod
    def load(cls, trans_csv: str, patterns_txt: Optional[str]) -> "IbmAml":
        raw = pd.read_csv(
            trans_csv, header=0, names=COLUMNS, usecols=USECOLS, dtype={"from_bank": str, "from_acct": str, "to_bank": str, "to_acct": str}
        )
        unknown = sorted(set(raw.currency) - set(CURRENCY_TO_INR))
        if unknown:
            raise ValueError(f"no rupee rate for currency: {', '.join(unknown)}")
        frame = pd.DataFrame(
            {
                "ts_raw": raw.ts,
                "timestamp": pd.to_datetime(raw.ts, format="%Y/%m/%d %H:%M"),
                "src": raw.from_bank + "-" + raw.from_acct,
                "dst": raw.to_bank + "-" + raw.to_acct,
                "amount_native": raw.amount,
                "amount_inr": raw.amount * raw.currency.map(CURRENCY_TO_INR),
                "laundering": raw.laundering,
            }
        )
        frame = frame[frame.src != frame.dst]  # reinvestments are not payments between accounts
        attempts = cls._match_attempts(frame, patterns_txt) if patterns_txt else []
        return cls(frame, attempts)

    @staticmethod
    def _match_attempts(frame: pd.DataFrame, patterns_txt: str) -> List[Attempt]:
        laundering = frame[frame.laundering == 1]
        index = {
            _row_key(ts, s, d, a): i
            for i, ts, s, d, a in zip(laundering.index, laundering.ts_raw, laundering.src, laundering.dst, laundering.amount_native)
        }
        attempts = []
        for typology, keys in _read_patterns(patterns_txt):
            rows = tuple(index[k] for k in keys if k in index)
            if rows:
                attempts.append(Attempt(typology, rows))
        return attempts

    def _index_by_account(self) -> Dict[str, np.ndarray]:
        n = len(self._src)
        codes, names = pd.factorize(np.concatenate([self._src, self._dst]))
        order = np.argsort(codes, kind="stable")
        bounds = np.searchsorted(codes[order], np.arange(len(names) + 1))
        rows = self.frame.index.to_numpy()
        return {names[c]: rows[order[bounds[c] : bounds[c + 1]] % n] for c in range(len(names))}

    def _plain_rows(self, account: str, rng: random.Random, cap: int) -> List[int]:
        rows = [int(i) for i in self._by_account.get(account, ()) if self.frame.laundering[i] == 0]
        return rows if len(rows) <= cap else rng.sample(rows, cap)

    def build_case(
        self, rng: random.Random, attempts: int, controls: int, neighbor_cap: int
    ) -> Tuple[List[Dict], List[Dict], Dict[str, bool]]:
        chosen = rng.sample(self.attempts, min(attempts, len(self.attempts)))
        rows: Set[int] = {i for a in chosen for i in a.rows}
        involved = {x for i in rows for x in (self._src[self._pos(i)], self._dst[self._pos(i)])}
        for account in sorted(involved):
            rows.update(self._plain_rows(account, rng, neighbor_cap))
        for account in rng.sample(self._controls, min(controls, len(self._controls))):
            rows.update(self._plain_rows(account, rng, neighbor_cap))

        picked = self.frame.loc[sorted(rows)].sort_values("timestamp")
        txns = [
            {
                "txn_id": f"{TXN_ID_PREFIX}{i}",
                "from_account": s,
                "to_account": d,
                "amount": float(a),
                "timestamp": t.isoformat(),
            }
            for i, s, d, a, t in zip(picked.index, picked.src, picked.dst, picked.amount_inr, picked.timestamp)
        ]
        ids = sorted(set(picked.src) | set(picked.dst))
        accounts = [{"account_id": a} for a in ids]
        is_mule = {a: a in self._mule_accounts for a in ids}
        return accounts, txns, is_mule

    def _pos(self, row_index: int) -> int:
        return self.frame.index.get_loc(row_index)
