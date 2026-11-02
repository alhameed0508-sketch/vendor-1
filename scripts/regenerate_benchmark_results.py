"""
Rebuild data/benchmark_results.json from the current detector, replacing whatever was there.

The file is appended to every time someone runs a benchmark from the UI, so it collects
duplicates and rows from older detector versions. Run this to start it again from a known state.

Usage (from the repository root):
    python scripts/regenerate_benchmark_results.py [--out data/benchmark_results.json]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from benchmark.service import BenchmarkService  # noqa: E402

DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark_results.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    # Build in a scratch file so a failed run never leaves a half-written results file.
    with tempfile.TemporaryDirectory() as scratch:
        built = os.path.join(scratch, "benchmark_results.json")
        service = BenchmarkService(results_path=built)
        service.run_synthetic(num_clusters=3, num_legit_accounts=30)
        service.run_adversarial(num_clusters=3, num_legit=30, num_adversarial=20)
        service.run_full_evaluation()
        os.replace(built, args.out) if os.path.dirname(built) == os.path.dirname(args.out) else _copy(built, args.out)
    print(f"wrote {args.out}")


def _copy(src: str, dst: str) -> None:
    with open(src, "rb") as fh, open(dst, "wb") as out:
        out.write(fh.read())


if __name__ == "__main__":
    main()
