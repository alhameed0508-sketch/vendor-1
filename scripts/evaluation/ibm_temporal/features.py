"""Point-in-time features for real-time scoring: each payment sees only payments from earlier minutes.

A payment at minute t uses events with minute < t. Payments in the same minute are treated as
simultaneous and never see each other, which is what a real-time system has when it must answer
before the payment completes. Labels are never used as features.

Implementation: events are sorted by a composite key (account * M + minute); counts, sums, last-seen
and window counts for any (account, minute) query are two binary searches and a prefix-sum lookup.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

M = 1_000_000  # > any minute index in these files (well under two years of minutes)
DAY = 1440
NEVER = 10**6  # "minutes since" when there is no earlier event


class EventIndex:
    """Prefix statistics over events (key, minute, value) for strictly-earlier lookups."""

    def __init__(self, key: np.ndarray, minute: np.ndarray, value: np.ndarray):
        comp = key.astype(np.int64) * M + minute.astype(np.int64)
        order = np.argsort(comp, kind="stable")
        self.comp = comp[order]
        self.minute = minute.astype(np.int64)[order]
        self.csum = np.concatenate([[0.0], np.cumsum(value.astype(np.float64)[order])])

    def query(self, key: np.ndarray, minute: np.ndarray, window: int = DAY) -> Dict[str, np.ndarray]:
        base = key.astype(np.int64) * M
        lo = np.searchsorted(self.comp, base, "left")
        hi = np.searchsorted(self.comp, base + minute.astype(np.int64), "left")  # minute' < minute
        win = np.maximum(np.searchsorted(self.comp, base + np.maximum(minute - window, 0), "left"), lo)
        count = hi - lo
        has = count > 0
        last = np.where(has, self.minute[np.maximum(hi - 1, 0)], -NEVER)
        first = np.where(has, self.minute[np.minimum(lo, len(self.minute) - 1)], -NEVER)
        return {
            "count": count,
            "sum": self.csum[hi] - self.csum[lo],
            "count_window": hi - win,
            "since_last": np.where(has, minute - last, NEVER),
            "since_first": np.where(has, minute - first, NEVER),
        }


def build(df: pd.DataFrame) -> pd.DataFrame:
    """Feature matrix aligned with df (sorted by time, with src, dst, minute, amount_usd, ...)."""
    codes, _ = pd.factorize(np.concatenate([df.src.to_numpy(), df.dst.to_numpy()]))
    n = len(df)
    src, dst = codes[:n].astype(np.int64), codes[n:].astype(np.int64)
    minute = df.minute.to_numpy().astype(np.int64)
    amount = df.amount_usd.to_numpy()

    out_ev = EventIndex(src, minute, amount)  # each account's outgoing payments
    in_ev = EventIndex(dst, minute, amount)  # each account's incoming payments
    pair = src * (codes.max() + 1) + dst
    pair_ev = EventIndex(pair, minute, np.ones(n))
    first_pair = ~pd.Series(pair).duplicated().to_numpy()  # first time this payer paid this payee
    new_benef_ev = EventIndex(src[first_pair], minute[first_pair], np.ones(first_pair.sum()))
    new_sender_ev = EventIndex(dst[first_pair], minute[first_pair], np.ones(first_pair.sum()))

    s_out, s_in = out_ev.query(src, minute), in_ev.query(src, minute)
    r_in, r_out = in_ev.query(dst, minute), out_ev.query(dst, minute)
    p = pair_ev.query(pair, minute)
    s_benef = new_benef_ev.query(src, minute)["count"]
    r_senders = new_sender_ev.query(dst, minute)["count"]

    f = pd.DataFrame(index=df.index)
    f["log_amount_usd"] = np.log1p(amount)
    f["fmt"] = df.fmt.astype("category").cat.codes.astype(np.int16)
    f["pay_ccy"] = df.pay_ccy.astype("category").cat.codes.astype(np.int16)
    f["recv_ccy"] = df.recv_ccy.astype("category").cat.codes.astype(np.int16)
    f["cross_currency"] = (df.pay_ccy != df.recv_ccy).astype(np.int8)
    f["cross_bank"] = (df.from_bank != df.to_bank).astype(np.int8)
    f["self_transfer"] = df.self_transfer.astype(np.int8)
    f["hour"] = df.ts.dt.hour.astype(np.int8)
    f["weekday"] = df.ts.dt.weekday.astype(np.int8)
    f["round_amount"] = ((df.amt_paid % 100) == 0).astype(np.int8)
    # payer history
    f["s_out_count"] = s_out["count"]
    f["s_out_log_sum"] = np.log1p(s_out["sum"])
    f["s_out_24h"] = s_out["count_window"]
    f["s_in_count"] = s_in["count"]
    f["s_in_24h"] = s_in["count_window"]
    f["s_mins_since_last_in"] = s_in["since_last"]  # pass-through: money in, then out
    f["s_mins_since_last_out"] = s_out["since_last"]
    f["s_age_mins"] = np.minimum(s_out["since_first"], s_in["since_first"])
    f["s_distinct_payees"] = s_benef
    mean_out = np.where(s_out["count"] > 0, s_out["sum"] / np.maximum(s_out["count"], 1), np.nan)
    f["s_amount_vs_usual"] = np.where(np.isnan(mean_out), 0.0, np.log1p(amount) - np.log1p(np.nan_to_num(mean_out)))
    f["s_in_out_ratio"] = np.log1p(s_in["sum"]) - np.log1p(s_out["sum"])
    # payee history
    f["r_in_count"] = r_in["count"]
    f["r_in_log_sum"] = np.log1p(r_in["sum"])
    f["r_in_24h"] = r_in["count_window"]
    f["r_out_count"] = r_out["count"]
    f["r_out_24h"] = r_out["count_window"]
    f["r_distinct_payers"] = r_senders  # fan-in
    f["r_age_mins"] = np.minimum(r_in["since_first"], r_out["since_first"])
    f["r_mins_since_last_out"] = r_out["since_last"]
    # the pair
    f["pair_count"] = p["count"]
    f["new_pair"] = (p["count"] == 0).astype(np.int8)
    f["pair_mins_since_last"] = p["since_last"]
    return f


CATEGORICAL = ("fmt", "pay_ccy", "recv_ccy")
