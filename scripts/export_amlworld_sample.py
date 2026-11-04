"""
Export a sample of the IBM AMLworld (HI-Small) dataset as a CBS file for the Data Import page.

AMLworld is IBM's published dataset (Altman et al., NeurIPS 2023) with labelled laundering
attempts (fan-out, fan-in, cycle, stack, ...). It is not real bank data (none is public) but
it comes from an independent generator, not ours. MuleCatch finds almost nothing on it
(docs/buildx/05-evaluation.md 7.8), so the sample is an honest independent check, not a
showcase.

The import file is pipe-delimited CBS; a ground-truth labels file is written beside it and
stays out of the import so alerts can be compared with the truth.

Usage (from the repository root, after downloading AMLworld to data/external/ibm-aml/):
    python scripts/export_amlworld_sample.py --out-dir ~/Documents/mulecatch/data
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from typing import NamedTuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from data.adapters.cbs_export import labels_csv, to_cbs_csv  # noqa: E402
from data.adapters.ibm_aml_adapter import IbmAml  # noqa: E402

IBM_DIR = os.path.join(ROOT, "data", "external", "ibm-aml")
DEFAULT_OUT = os.path.join("~", "Documents", "mulecatch", "data")
SEED = 2026
MAX_IMPORT_ROWS = 50_000  # the importer stops reading here


class Sample(NamedTuple):
    attempts: int  # labelled laundering attempts to include
    controls: int  # ordinary accounts added as genuine traffic
    neighbor_cap: int  # ordinary payments kept per account


SAMPLES = {"sample": Sample(attempts=8, controls=40, neighbor_cap=12)}


def write_sample(ibm: IbmAml, name: str, sample: Sample, out_dir: str) -> None:
    accounts, payments, is_mule = ibm.build_case(
        random.Random(f"{SEED}-{name}"), sample.attempts, sample.controls, sample.neighbor_cap
    )
    if 2 * len(payments) > MAX_IMPORT_ROWS:
        raise SystemExit(f"{name}: {2 * len(payments)} CBS rows exceed the importer limit of {MAX_IMPORT_ROWS}")
    stem = os.path.join(out_dir, f"ibm-amlworld-hi-small-{name}")
    with open(f"{stem}.csv", "w", encoding="utf-8", newline="") as fh:
        fh.write(to_cbs_csv(payments))
    with open(f"{stem}-labels.csv", "w", encoding="utf-8", newline="") as fh:
        fh.write(labels_csv([a["account_id"] for a in accounts], is_mule))
    print(
        f"{os.path.basename(stem)}: {len(payments)} payments, {len(accounts)} accounts ({sum(is_mule.values())} mule)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out-dir", default=DEFAULT_OUT)
    parser.add_argument("--trans", default=os.path.join(IBM_DIR, "HI-Small_Trans.csv"))
    parser.add_argument("--patterns", default=os.path.join(IBM_DIR, "HI-Small_Patterns.txt"))
    args = parser.parse_args()

    if not os.path.exists(args.trans):
        raise SystemExit(f"{args.trans} not found; download IBM AMLworld HI-Small first")
    out_dir = os.path.expanduser(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    ibm = IbmAml.load(args.trans, args.patterns)
    for name, sample in SAMPLES.items():
        write_sample(ibm, name, sample, out_dir)


if __name__ == "__main__":
    main()
