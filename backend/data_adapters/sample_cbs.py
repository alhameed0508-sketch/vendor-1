"""
A small, clearly synthetic CBS extract (pipe-delimited) with one planted mule ring.

The assessment dashboard shows this file until someone uploads their own, so the public
demo never needs real bank data. Same generator and seed as the demo video's
``MuleCatch_sample_CBS_extract.csv``: 908 rows, 40 accounts.

Ordinary customers: salary credits, merchant UPI payments, a few payments to regular
contacts, ATM cash. Ring: victim credits -> collector -> 8 recently opened mule accounts
(amounts just under Rs 50,000, within hours) -> aggregator -> cash-out. Internal transfers
carry the same TRAN_ID on the D and C legs, which is how the adapter links them.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, FrozenSet, List, Tuple

COLUMNS = (
    "TRAN_DATE",
    "TRAN_ID",
    "TRAN_TYPE",
    "TRAN_SUB_TYPE",
    "PART_TRAN_TYPE",
    "ACID",
    "TRAN_AMT",
    "balance",
    "channel",
    "CIF_ID",
    "ACCT_OPN_DATE",
    "LIEN_AMT",
    "customer_age",
)
SEED = 2027
START = datetime(2026, 10, 20, 9, 0)
FILENAME = "MuleCatch_sample_CBS_extract.csv"


@lru_cache(maxsize=1)
def build_sample_cbs() -> Tuple[str, FrozenSet[str]]:
    """Return (pipe-delimited CSV text, ACIDs of the planted ring). Deterministic."""
    rng = random.Random(SEED)
    rows: List[Dict[str, str]] = []
    balances: Dict[str, int] = {}
    meta: Dict[str, Dict] = {}
    seq = [0]

    def acct(acid: str, opened: datetime, age: int) -> None:
        meta[acid] = {"CIF_ID": "CIF" + acid[2:], "ACCT_OPN_DATE": opened.strftime("%d/%m/%Y"), "customer_age": age}
        balances[acid] = rng.randint(20_000, 120_000)

    def tran_id() -> str:
        seq[0] += 1
        return f"S{seq[0]:07d}"

    def leg(when: datetime, tid: str, part: str, acid: str, amount: int, channel: str) -> None:
        balances[acid] += amount if part == "C" else -amount
        m = meta[acid]
        rows.append(
            {
                "TRAN_DATE": when.strftime("%d/%m/%Y %H:%M"),
                "TRAN_ID": tid,
                "TRAN_TYPE": "T",
                "TRAN_SUB_TYPE": "CI",
                "PART_TRAN_TYPE": part,
                "ACID": acid,
                "TRAN_AMT": f"{amount:.2f}",
                "balance": f"{balances[acid]:.2f}",
                "channel": channel,
                "CIF_ID": m["CIF_ID"],
                "ACCT_OPN_DATE": m["ACCT_OPN_DATE"],
                "LIEN_AMT": "0",
                "customer_age": str(m["customer_age"]),
            }
        )

    def transfer(when: datetime, src: str, dst: str, amount: int, channel: str = "UPI") -> None:
        tid = tran_id()
        leg(when, tid, "D", src, amount, channel)
        leg(when + timedelta(seconds=5), tid, "C", dst, amount, channel)

    def external(when: datetime, acid: str, part: str, amount: int, channel: str) -> None:
        leg(when, tran_id(), part, acid, amount, channel)

    normal = [f"AC5{n:07d}" for n in range(1, 31)]
    for a in normal:
        acct(a, START - timedelta(days=rng.randint(400, 3000)), rng.randint(24, 66))
    # Real retail graphs are sparse: most spending goes to merchants outside the bank's
    # book, and each customer pays only a couple of regular contacts inside it.
    contacts = {a: rng.sample([x for x in normal if x != a], 2) for a in normal}
    for day in range(10):
        base = START + timedelta(days=day)
        for a in normal:
            if day == 0:
                external(base + timedelta(hours=1), a, "C", rng.randint(35_000, 90_000), "NEFT")  # salary
            for _ in range(rng.randint(1, 3)):  # merchant UPI payments
                external(
                    base + timedelta(hours=rng.randint(8, 21), minutes=rng.randint(0, 59)),
                    a,
                    "D",
                    rng.choice([120, 240, 380, 560, 899, 1450, 2600]) + rng.randint(0, 99),
                    "UPI",
                )
            if rng.random() < 0.15:  # occasional payment to a regular contact
                transfer(
                    base + timedelta(hours=rng.randint(9, 20), minutes=rng.randint(0, 59)),
                    a,
                    rng.choice(contacts[a]),
                    rng.choice([500, 1200, 2500, 4000]) + rng.randint(0, 99),
                )
            if rng.random() < 0.25:
                external(base + timedelta(hours=rng.randint(9, 20)), a, "D", rng.choice([2000, 3000, 5000]), "ATM")

    collector, aggregator = "AC90000001", "AC90000002"
    mules = [f"AC9100{n:04d}" for n in range(1, 9)]
    acct(collector, START - timedelta(days=5), 23)
    acct(aggregator, START - timedelta(days=4), 27)
    for m in mules:
        acct(m, START - timedelta(days=rng.randint(1, 6)), rng.randint(19, 26))
    for day in (3, 5, 7):
        t = START + timedelta(days=day, hours=22)
        for _ in range(6):  # victim money arrives from outside the bank
            external(t, collector, "C", rng.randint(60_000, 95_000), "IMPS")
            t += timedelta(minutes=rng.randint(3, 9))
        for m in mules:  # split just under Rs 50,000
            transfer(t, collector, m, rng.randint(45_000, 49_800), "IMPS")
            t += timedelta(minutes=rng.randint(2, 6))
        t += timedelta(hours=1)
        for m in mules:  # forwarded within hours
            transfer(t, m, aggregator, rng.randint(44_000, 48_000), "UPI")
            t += timedelta(minutes=rng.randint(1, 4))
        for k in range(4):  # cash-out
            external(t + timedelta(minutes=10 * k), aggregator, "D", rng.randint(80_000, 99_000), "IMPS")

    rows.sort(key=lambda r: datetime.strptime(r["TRAN_DATE"], "%d/%m/%Y %H:%M"))
    lines = ["|".join(COLUMNS)] + ["|".join(r[c] for c in COLUMNS) for r in rows]
    return "\n".join(lines) + "\n", frozenset([collector, aggregator, *mules])
