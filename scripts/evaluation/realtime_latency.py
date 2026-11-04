"""
Per-payment latency of RealtimeScorer.score_payment() as the rolling window grows.

Each point scores N fresh payments against a window of the given size with
commit=False (the public API path) and reports median / p95 / max in ms.

Usage (from the repository root):
    python scripts/evaluation/realtime_latency.py --out docs/buildx/realtime_latency_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import uuid
from datetime import datetime
from typing import Dict, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from services.realtime_scorer import RealtimeScorer  # noqa: E402

from data.synthetic.generator import build_adversarial_dataset  # noqa: E402

WINDOW_SIZES = (500, 1000, 2000, 5000)
PROBES_PER_POINT = 25
SEED = 11


def _probe_payments(accounts: List[Dict], count: int, rng: random.Random) -> List[Dict]:
    ids = [a["account_id"] for a in accounts]
    now = datetime.now().isoformat()  # naive, like the generator's history
    return [
        {
            "txn_id": f"PROBE_{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}",
            "from_account": rng.choice(ids),
            "to_account": rng.choice(ids),
            "amount": round(rng.uniform(500, 40000), 2),
            "timestamp": now,
        }
        for _ in range(count)
    ]


def measure(window_size: int) -> Dict:
    random.seed(SEED)
    rng = random.Random(SEED)
    # Enough clusters/legit accounts that the dataset holds at least window_size transactions.
    scale = max(1, window_size // 400)
    ds = build_adversarial_dataset(num_clusters=5 * scale, num_legit_accounts=150 * scale, num_adversarial=50 * scale)
    history = ds["transactions"][:window_size]
    scorer = RealtimeScorer(ds["accounts"], history, max_window=window_size)
    latencies = sorted(
        scorer.score_payment(p, commit=False).latency_ms for p in _probe_payments(ds["accounts"], PROBES_PER_POINT, rng)
    )
    return {
        "window_transactions": scorer.history_size,
        "probes": len(latencies),
        "median_ms": round(statistics.median(latencies), 1),
        "p95_ms": round(latencies[int(0.95 * (len(latencies) - 1))], 1),
        "max_ms": round(latencies[-1], 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", default=None, help="Write JSON results to this path")
    args = parser.parse_args()
    results = {"points": [measure(size) for size in WINDOW_SIZES]}
    text = json.dumps(results, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")


if __name__ == "__main__":
    main()
