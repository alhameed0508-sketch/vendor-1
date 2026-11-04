"""The IBM AMLworld evaluation pipeline: no look-ahead, clean splits, counted cleaning, honest thresholds."""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "evaluation"))

from ibm_temporal import features, metrics, preprocess  # noqa: E402

HEADER = "Timestamp,From Bank,Account,To Bank,Account,Amount Received,Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering\n"


def _write(tmp_path, rows):
    p = tmp_path / "T_Trans.csv"
    p.write_text(HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")
    return str(p)


ROWS = [
    "2022/09/01 00:00,001,A1,002,B1,100.00,US Dollar,100.00,US Dollar,ACH,0",
    "2022/09/01 00:00,001,A1,002,B1,50.00,US Dollar,50.00,US Dollar,ACH,0",  # same minute as row 1
    "2022/09/01 00:05,002,B1,003,C1,90.00,Euro,100.00,US Dollar,Wire,1",  # USD -> EUR at 0.9
    "2022/09/01 01:00,001,A1,003,C1,20.00,Euro,20.00,Euro,Cheque,0",
    "2022/09/02 03:00,001,A1,001,A1,5.00,US Dollar,5.00,US Dollar,Reinvestment,0",
    "2022/09/02 03:00,001,A1,001,A1,5.00,US Dollar,5.00,US Dollar,Reinvestment,0",  # exact duplicate
    "not a date,001,A1,002,B1,1.00,US Dollar,1.00,US Dollar,ACH,0",  # invalid
]


def test_load_validates_counts_and_normalises(tmp_path):
    df, q = preprocess.load(_write(tmp_path, ROWS))
    assert q["source_rows"] == 7 and q["invalid_rows"] == 1 and q["rows_used"] == 6
    assert q["exact_duplicate_rows"] == 1 and df.is_duplicate.sum() == 2
    assert q["self_transfers"] == 2
    assert q["currency_rates_to_usd"]["Euro"] == pytest.approx(1 / 0.9)
    assert df.amount_usd.iloc[3] == pytest.approx(20 / 0.9)
    assert list(df.minute) == sorted(df.minute)
    assert df.src.iloc[0] == "001:A1"


def test_wrong_header_is_rejected(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with pytest.raises(preprocess.SchemaError):
        preprocess.load(str(p))


def test_features_never_see_the_same_minute_or_the_future(tmp_path):
    df, _ = preprocess.load(_write(tmp_path, ROWS))
    f = features.build(df)
    # rows 0 and 1 share minute 0: neither sees the other
    assert f.s_out_count.iloc[0] == 0 and f.s_out_count.iloc[1] == 0
    assert f.pair_count.iloc[1] == 0 and f.new_pair.iloc[1] == 1
    # B1 received at minute 0 and pays at minute 5: it has seen both inflows, 5 minutes ago
    assert f.s_in_count.iloc[2] == 2 and f.s_mins_since_last_in.iloc[2] == 5
    # A1 at minute 60 has two earlier payments to one payee
    assert f.s_out_count.iloc[3] == 2 and f.s_distinct_payees.iloc[3] == 1
    # the payment at day 2 is outside the 24 h window of the minute-0 payments
    assert f.s_out_24h.iloc[4] == 0 and f.s_out_count.iloc[4] == 3


def test_event_index_window_and_since():
    idx = features.EventIndex(np.array([7, 7, 7]), np.array([0, 10, 2000]), np.array([1.0, 2.0, 4.0]))
    q = idx.query(np.array([7, 7, 8]), np.array([10, 2001, 5]))
    assert list(q["count"]) == [1, 3, 0]
    assert list(q["sum"]) == [1.0, 7.0, 0.0]
    assert list(q["count_window"]) == [1, 1, 0]
    assert q["since_last"][0] == 10 and q["since_last"][2] == features.NEVER


def test_chronological_split_has_no_overlap():
    n = 1000
    df = pd.DataFrame(
        {
            "minute": np.repeat(np.arange(100), 10),
            "label": np.zeros(n, dtype=np.int8),
            "ts": pd.date_range("2022-09-01", periods=n, freq="6s"),
        }
    )
    tr, va, te, tail, info = preprocess.chronological_split(df)
    assert not (tr & va).any() and not (va & te).any() and (tr | va | te).all() and not tail.any()
    assert df.minute[tr].max() < df.minute[va].min() and df.minute[va].max() < df.minute[te].min()


def test_false_alert_threshold_respects_the_budget():
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(10_000, dtype=int), np.ones(50, dtype=int)]
    s = np.r_[rng.random(10_000), rng.random(50) + 0.5]
    thr = metrics.threshold_for_fpr(y, s, 0.005)
    m = metrics.at_threshold(y, s, thr)
    assert m["false_positive_rate"] <= 0.005
    assert m["confusion"]["tp"] + m["confusion"]["fn"] == 50


def test_account_level_takes_the_highest_score():
    codes, label, score = metrics.account_level(
        np.array(["a", "b"]), np.array(["b", "c"]), np.array([0, 1]), np.array([0.2, 0.9])
    )
    got = dict(zip(codes, zip(label, score)))
    assert got["a"] == (0, 0.2) and got["b"] == (1, 0.9) and got["c"] == (1, 0.9)


def test_wind_down_tail_is_kept_out_of_the_splits():
    # ten busy days, then three days with a handful of payments
    minutes = np.r_[np.repeat(np.arange(10) * 1440, 1000), np.array([10, 11, 12]) * 1440 + 5]
    n = len(minutes)
    df = pd.DataFrame(
        {
            "minute": minutes,
            "label": np.zeros(n, dtype=np.int8),
            "ts": pd.Timestamp("2022-09-01") + pd.to_timedelta(minutes, unit="min"),
        }
    )
    tr, va, te, tail, info = preprocess.chronological_split(df)
    assert tail.sum() == 3 and not (tail & (tr | va | te)).any()
    assert info["tail_after_ordinary_traffic_ends"]["rows"] == 3


def test_plotted_curves_never_pass_below_a_real_operating_point():
    rng = np.random.default_rng(1)
    y = np.r_[np.zeros(200_000, dtype=int), np.ones(300, dtype=int)]
    s = np.r_[rng.random(200_000), rng.random(300) * 0.5 + 0.5]
    c = metrics.curve_points(y, s)
    for thr in (0.9, 0.97, 0.995):
        m = metrics.at_threshold(y, s, thr)
        i = int(np.searchsorted(c["recall"], m["recall"], side="right")) - 1  # grid recall just below the point
        assert c["precision"][i] >= m["precision"] - 1e-9
        j = int(np.searchsorted(c["fpr"], m["false_positive_rate"], side="right")) - 1
        assert c["tpr"][j] <= m["recall"] + 1e-9 or c["fpr"][j] >= m["false_positive_rate"] - 1e-12
