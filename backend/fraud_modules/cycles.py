"""Circular fund flow (CF01): money that leaves an account and comes back to it through other accounts.

A loop is reported when all three hold:
1. 3 to 6 distinct accounts form a directed cycle of payments (self-transfers are ignored);
2. there is a starting point from which every hop happens no earlier than the previous one, and the
   whole loop completes within the window (laundering moves forward in time; a refund loop does not
   have to);
3. it is the same money moving on: every hop is 0.85-1.15x the previous one. Taken from IBM AMLworld's
   labelled CYCLE attempts, where 90% of hops sit within 0.91-1.10x (in US dollars). Ordinary customers
   also pay each other in circles (shared bills, family), but those hops are unrelated amounts.

Every account on a reported loop gets one finding that names the loop, its duration and amounts.
Enumeration is capped so a dense graph cannot stall a request; the cap is reported, never hidden.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import datetime, timedelta
from typing import Dict, List, Mapping, Sequence, Tuple

import networkx as nx

CODE = "CF01"
MIN_LENGTH, MAX_LENGTH = 3, 6
WINDOW = timedelta(days=7)
HOP_RATIO_BAND = (0.85, 1.15)  # next hop / previous hop
MAX_CYCLES_EXAMINED = 20_000

Hop = Tuple[str, str, datetime, float]


def _ts(value) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _timed_path(cycle: Sequence[str], edges: Mapping[Tuple[str, str], List[Tuple[datetime, float]]]):
    """The tightest time-ordered walk around the cycle, trying every starting account. None if none exists."""
    best = None
    n = len(cycle)
    for start in range(n):
        order = [cycle[(start + k) % n] for k in range(n)]
        hops: List[Hop] = []
        prev = datetime.min
        for k in range(n):
            a, b = order[k], order[(k + 1) % n]
            options = edges[(a, b)]
            i = bisect_left(options, (prev, float("-inf")))
            if i == len(options):
                hops = []
                break
            ts, amount = options[i]
            hops.append((a, b, ts, amount))
            prev = ts
        if not hops:
            continue
        span = hops[-1][2] - hops[0][2]
        if best is None or span < best[0]:
            best = (span, hops)
    return best


def find_cycles(transactions: Sequence[Mapping]) -> Dict:
    """Return {"cycles": [...], "examined": n, "capped": bool}."""
    edges: Dict[Tuple[str, str], List[Tuple[datetime, float]]] = {}
    for t in transactions:
        a, b = str(t["from_account"]), str(t["to_account"])
        if a == b:
            continue
        try:
            when, amount = _ts(t["timestamp"]), float(t["amount"])
        except (KeyError, TypeError, ValueError):
            continue
        if amount <= 0:
            continue
        edges.setdefault((a, b), []).append((when, amount))
    for options in edges.values():
        options.sort()
    graph = nx.DiGraph(list(edges))
    cycles, examined, capped = [], 0, False
    for cycle in nx.simple_cycles(graph, length_bound=MAX_LENGTH):
        examined += 1
        if examined > MAX_CYCLES_EXAMINED:
            capped = True
            break
        if len(cycle) < MIN_LENGTH:
            continue
        found = _timed_path(cycle, edges)
        if found is None:
            continue
        span, hops = found
        amounts = [h[3] for h in hops]
        low, high = HOP_RATIO_BAND
        if span > WINDOW or not all(low <= b / a <= high for a, b in zip(amounts, amounts[1:])):
            continue
        cycles.append(
            {
                "accounts": [h[0] for h in hops],
                "hops": hops,
                "span": span,
                "amount_out": amounts[0],
                "amount_back": amounts[-1],
            }
        )
    return {"cycles": cycles, "examined": min(examined, MAX_CYCLES_EXAMINED), "capped": capped}


def describe(cycle: Dict) -> str:
    loop = " -> ".join(cycle["accounts"] + [cycle["accounts"][0]])
    hours = cycle["span"].total_seconds() / 3600
    when = f"{hours:.1f} h" if hours < 48 else f"{hours / 24:.1f} days"
    return (
        f"{CODE}: Circular fund flow: {loop} within {when} "
        f"({cycle['amount_out']:,.0f} out, {cycle['amount_back']:,.0f} back)"
    )


def cycle_hits(transactions: Sequence[Mapping]) -> List[Tuple[str, str]]:
    """(account_id, explanation) for every account on a reported loop; one per account per loop."""
    hits = []
    for cycle in find_cycles(transactions)["cycles"]:
        text = describe(cycle)
        hits.extend((account, text) for account in dict.fromkeys(cycle["accounts"]))
    return hits
