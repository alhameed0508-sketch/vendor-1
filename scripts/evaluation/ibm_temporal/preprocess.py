"""Load and clean an IBM AMLworld transactions file (Altman et al., NeurIPS 2023) without losing anything.

Every step is counted in a data-quality report. Rows are never dropped silently: a row that fails
validation is counted, kept out of modelling, and reported. The raw file is never modified.

Steps: schema check, type validation, missing values, timestamp normalisation, account-id
normalisation (bank + account), currency normalisation to US dollars with rates derived from the
file itself, duplicate and self-transfer flags, typology mapping from the patterns file, and a
stable chronological sort.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

import numpy as np
import pandas as pd

EXPECTED_HEADER = [
    "Timestamp",
    "From Bank",
    "Account",
    "To Bank",
    "Account",
    "Amount Received",
    "Receiving Currency",
    "Amount Paid",
    "Payment Currency",
    "Payment Format",
    "Is Laundering",
]
COLUMNS = [
    "ts",
    "from_bank",
    "from_acct",
    "to_bank",
    "to_acct",
    "amt_received",
    "recv_ccy",
    "amt_paid",
    "pay_ccy",
    "fmt",
    "label",
]
TS_FORMAT = "%Y/%m/%d %H:%M"
USD = "US Dollar"


class SchemaError(ValueError):
    pass


def read_header(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [h.strip() for h in f.readline().rstrip("\n").split(",")]


def load(path: str) -> Tuple[pd.DataFrame, Dict]:
    """Return (clean frame sorted by time, data-quality report)."""
    header = read_header(path)
    if header != EXPECTED_HEADER:
        raise SchemaError(f"unexpected header: {header}")
    raw = pd.read_csv(path, header=0, names=COLUMNS, dtype=str, keep_default_na=False)
    report: Dict = {"source_rows": int(len(raw)), "columns": len(COLUMNS)}
    report["blank_values"] = {c: int((raw[c].str.strip() == "").sum()) for c in COLUMNS}

    df = pd.DataFrame({"row": np.arange(len(raw), dtype=np.int64)})
    df["ts"] = pd.to_datetime(raw.ts.str.strip(), format=TS_FORMAT, errors="coerce")
    for col in ("amt_received", "amt_paid"):
        df[col] = pd.to_numeric(raw[col].str.strip(), errors="coerce")
    df["label"] = pd.to_numeric(raw.label.str.strip(), errors="coerce")
    for col in ("from_bank", "to_bank"):
        df[col] = raw[col].str.strip()  # leading zeros are part of the bank id
    for col in ("from_acct", "to_acct"):
        df[col] = raw[col].str.strip().str.upper()
    for col in ("recv_ccy", "pay_ccy", "fmt"):
        df[col] = raw[col].str.strip()

    invalid = (
        df.ts.isna()
        | df.amt_received.isna()
        | df.amt_paid.isna()
        | (df.amt_received < 0)
        | (df.amt_paid < 0)
        | ~df.label.isin([0, 1])
        | (df.from_acct == "")
        | (df.to_acct == "")
        | (df.from_bank == "")
        | (df.to_bank == "")
    )
    report["invalid_rows"] = int(invalid.sum())
    report["invalid_rows_laundering"] = int((invalid & (df.label == 1)).sum())
    df = df.loc[~invalid].copy()
    df["label"] = df.label.astype(np.int8)

    report["exact_duplicate_rows"] = int(raw.loc[df.row].duplicated().sum())
    dup = raw.loc[df.row].duplicated(keep=False).to_numpy()
    report["exact_duplicate_rows_laundering"] = int((dup & (df.label.to_numpy() == 1)).sum())
    df["is_duplicate"] = dup  # kept: repeated identical payments in one minute can be genuine

    df["src"] = df.from_bank + ":" + df.from_acct
    df["dst"] = df.to_bank + ":" + df.to_acct
    df["self_transfer"] = df.src == df.dst
    report["self_transfers"] = int(df.self_transfer.sum())
    report["self_transfers_laundering"] = int((df.self_transfer & (df.label == 1)).sum())

    rates, rate_report = usd_rates(df)
    report["currency_rates_to_usd"] = rate_report
    df["amount_usd"] = df.amt_paid * df.pay_ccy.map(rates)
    report["zero_amount_rows"] = int((df.amt_paid == 0).sum())

    df = df.sort_values(["ts", "row"], kind="stable").reset_index(drop=True)
    start = df.ts.iloc[0]
    df["minute"] = ((df.ts - start).dt.total_seconds() // 60).astype(np.int64)
    report["time_coverage"] = {
        "first": str(df.ts.iloc[0]),
        "last": str(df.ts.iloc[-1]),
        "days": int(df.minute.iloc[-1] // 1440) + 1,
    }
    report["rows_used"] = int(len(df))
    report["laundering_rows"] = int(df.label.sum())
    report["laundering_rate"] = float(df.label.mean())
    report["accounts"] = int(pd.unique(np.concatenate([df.src.to_numpy(), df.dst.to_numpy()])).size)
    report["payment_formats"] = {k: int(v) for k, v in df.fmt.value_counts().items()}
    return df, report


def usd_rates(df: pd.DataFrame) -> Tuple[Dict[str, float], Dict]:
    """US-dollar value of one unit of each currency, from the file's own cross-currency payments.

    For a payment from currency A to currency B, amount_received / amount_paid is the A->B rate. The
    median over all A<->USD payments gives A in dollars; currencies never paired with dollars go through
    the currency they are most often paired with.
    """
    cross = df[(df.pay_ccy != df.recv_ccy) & (df.amt_paid > 0) & (df.amt_received > 0)]
    pair_rate: Dict[Tuple[str, str], float] = {}
    for (a, b), g in cross.groupby(["pay_ccy", "recv_ccy"]):
        pair_rate[(a, b)] = float(np.median(g.amt_received / g.amt_paid))  # units of b per unit of a
    rates = {USD: 1.0}
    currencies = sorted(set(df.pay_ccy) | set(df.recv_ccy))
    for c in currencies:
        if c == USD:
            continue
        if (c, USD) in pair_rate:
            rates[c] = pair_rate[(c, USD)]
        elif (USD, c) in pair_rate:
            rates[c] = 1.0 / pair_rate[(USD, c)]
    for c in currencies:  # one hop through a currency that already has a dollar rate
        if c in rates:
            continue
        for (a, b), r in pair_rate.items():
            if a == c and b in rates:
                rates[c] = r * rates[b]
                break
            if b == c and a in rates:
                rates[c] = rates[a] / r
                break
    missing = [c for c in currencies if c not in rates]
    if missing:
        raise SchemaError(f"no exchange-rate path to US dollars for: {missing}")
    return rates, {c: round(v, 6) for c, v in sorted(rates.items())}


def typologies(df: pd.DataFrame, patterns_path: str) -> Tuple[pd.Series, Dict]:
    """Typology (FAN-OUT, CYCLE, ...) for each laundering row, from the patterns file. '' if unmatched."""
    keys: Dict[Tuple, str] = {}
    current = ""
    with open(patterns_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("BEGIN LAUNDERING ATTEMPT"):
                m = re.match(r"BEGIN LAUNDERING ATTEMPT - ([A-Z\-]+)", line)
                current = m.group(1) if m else "UNKNOWN"
            elif line and not line.startswith("END"):
                p = line.split(",")
                if len(p) >= 8:
                    keys[
                        (
                            p[0].strip(),
                            p[1].strip(),
                            p[2].strip().upper(),
                            p[3].strip(),
                            p[4].strip().upper(),
                            p[7].strip(),
                        )
                    ] = current
    ts = df.ts.dt.strftime(TS_FORMAT)
    paid = df.amt_paid.map(lambda v: f"{v:.2f}")
    joined = pd.Series(
        [keys.get(k, "") for k in zip(ts, df.from_bank, df.from_acct, df.to_bank, df.to_acct, paid)], index=df.index
    )
    joined[df.label == 0] = ""
    matched = int((joined != "").sum())
    return joined, {
        "laundering_rows": int(df.label.sum()),
        "matched_to_a_typology": matched,
        "typology_counts": {k: int(v) for k, v in joined[joined != ""].value_counts().items()},
    }


TAIL_SHARE = 0.01  # a trailing day with fewer payments than 1% of the median day is the generator winding down


def trailing_tail(df: pd.DataFrame) -> np.ndarray:
    """Trailing days where ordinary traffic has stopped (AMLworld keeps only laundering chains running)."""
    day = df.minute.to_numpy() // 1440
    counts = np.bincount(day)
    present = counts[counts > 0]
    floor = TAIL_SHARE * float(np.median(present))
    last_main = len(counts) - 1
    while last_main > 0 and counts[last_main] < floor:
        last_main -= 1
    return day > last_main


def chronological_split(df: pd.DataFrame, train: float = 0.6, val: float = 0.2):
    """Train / validation / test by time over the main period; the wind-down tail is kept apart.

    Cuts fall on minute boundaries, so no minute is in two splits. Returns (train, val, test, tail, info).
    """
    tail = trailing_tail(df)
    minutes = df.minute.to_numpy()
    main_minutes = minutes[~tail]
    n = len(main_minutes)
    cut1 = main_minutes[int(n * train)]
    cut2 = main_minutes[int(n * (train + val))]
    tr = ~tail & (minutes < cut1)
    va = ~tail & (minutes >= cut1) & (minutes < cut2)
    te = ~tail & (minutes >= cut2)
    info = {}
    for name, m in (("train", tr), ("validation", va), ("test", te), ("tail_after_ordinary_traffic_ends", tail)):
        part = df.loc[m]
        info[name] = {
            "rows": int(m.sum()),
            "laundering": int(part.label.sum()),
            "laundering_rate": float(part.label.mean()) if len(part) else 0.0,
            "from": str(part.ts.iloc[0]) if len(part) else "",
            "to": str(part.ts.iloc[-1]) if len(part) else "",
        }
    return tr, va, te, tail, info
