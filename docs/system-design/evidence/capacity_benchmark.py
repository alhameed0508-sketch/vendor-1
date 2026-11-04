"""Synthetic capacity check for MuleCatch's hot paths. No customer data: every row comes from a fixed seed.

Part 1 times today's per-payment mule scorer (backend/services/realtime_scorer.py) on this machine, on the
project's own synthetic history, in two modes:
  - "rebuild": the payment forces a Louvain partition rebuild (happens every 10 committed payments today);
  - "cached":  the partition is reused (the other 9 of every 10 payments).
Part 2 times the proposed decision log (SQLite standing in for PostgreSQL): durable batched appends,
recent-decisions page, one decision by id, and the daily false-alert count the metrics page needs.

How to read it: CPU time on a desktop core, single thread. A cloud vCPU is slower: multiply by about 2.
PostgreSQL adds network and WAL overhead: multiply database times by about 3.

Usage: python -I capacity_benchmark.py <repo_root> [work_dir]
Writes capacity_benchmark_result.json next to this script.
"""
import json
import os
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

SEED = 20261104
ROWS = 1_000_000  # decision log rows (~1.4 days of the pilot)


def pct(values, q):
    values = sorted(values)
    return round(values[min(len(values) - 1, int(q * (len(values) - 1)))], 3)


def timed(fn, runs):
    out = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t) * 1000)
    return {"runs": runs, "p50_ms": round(statistics.median(out), 3), "p95_ms": pct(out, 0.95), "max_ms": round(max(out), 3)}


def scorer_benchmark(repo: Path):
    sys.path[:0] = [str(repo / "backend"), str(repo)]
    from services.realtime_demo import strip_labels
    from services.realtime_scorer import RealtimeScorer

    from data.synthetic.generator import build_adversarial_dataset

    data = build_adversarial_dataset(num_clusters=5, num_legit_accounts=150, num_adversarial=50)
    txns = sorted(strip_labels(data["transactions"]), key=lambda t: t["timestamp"])
    accounts = strip_labels(data["accounts"])
    history, live = txns[: int(len(txns) * 0.8)], txns[int(len(txns) * 0.8):]
    scorer = RealtimeScorer(accounts, history)
    rebuild, cached = [], []
    for i, t in enumerate(live[:200]):
        r = scorer.score_payment(t, commit=True)
        (rebuild if i % 10 == 0 else cached).append(r.latency_ms)
    return {"history_payments": len(history), "accounts": len(accounts), "scored": min(200, len(live)),
            "rebuild": {"p50_ms": round(statistics.median(rebuild), 2), "p95_ms": pct(rebuild, 0.95)},
            "cached": {"p50_ms": round(statistics.median(cached), 2), "p95_ms": pct(cached, 0.95)},
            "blended_mean_ms": round(statistics.mean(rebuild + cached), 2)}


def db_benchmark(work: Path):
    db = work / "mc_capacity_benchmark.db"
    for s in ("", "-wal", "-shm"):
        if Path(str(db) + s).exists():
            os.remove(str(db) + s)
    rng = random.Random(SEED)
    con = sqlite3.connect(str(db), isolation_level=None)
    con.executescript("""
        PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
        CREATE TABLE risk_decision(decision_id TEXT PRIMARY KEY, txn_id TEXT UNIQUE NOT NULL, customer_id TEXT NOT NULL,
          beneficiary_id TEXT NOT NULL, amount REAL NOT NULL, score INT NOT NULL, band TEXT NOT NULL, confidence REAL,
          families TEXT NOT NULL, source TEXT NOT NULL, decided_at TEXT NOT NULL, outcome TEXT, explanation TEXT);
        CREATE INDEX rd_time ON risk_decision(decided_at DESC);
        CREATE INDEX rd_customer ON risk_decision(customer_id, decided_at DESC);
        CREATE INDEX rd_open ON risk_decision(band, decided_at DESC) WHERE band <> 'APPROVE';
    """)
    bands = [("APPROVE", 0.97), ("STEP_UP", 0.025), ("REVIEW", 0.005)]

    def band():
        x, acc = rng.random(), 0.0
        for b, w in bands:
            acc += w
            if x <= acc:
                return b
        return "APPROVE"

    t0 = time.perf_counter()
    con.execute("BEGIN")
    batch = []
    for i in range(ROWS):
        b = band()
        day = 1 + i * 30 // ROWS
        batch.append((f"D{i:09d}", f"T{i:09d}", f"C{rng.randint(1, 200_000):06d}", f"B{rng.randint(1, 400_000):06d}",
                      round(rng.lognormvariate(7.5, 1.2), 2), rng.randint(0, 100), b, round(rng.random(), 2),
                      '{"mule":0.1,"session":0.0,"beneficiary":0.2,"behaviour":0.1}', "bench",
                      f"2026-10-{day:02d}T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:00",
                      None, "x" * 3500 if b != "APPROVE" else None))
        if len(batch) == 10_000:
            con.executemany("INSERT INTO risk_decision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
            batch = []
    con.execute("COMMIT")
    build_s = time.perf_counter() - t0
    con.execute("ANALYZE")
    nxt = [ROWS]

    def append_batch_100():  # the scoring worker commits decisions in small batches
        rows = []
        for _ in range(100):
            nxt[0] += 1
            rows.append((f"D{nxt[0]:09d}", f"T{nxt[0]:09d}", "C000001", "B000001", 1500.0, 12, "APPROVE", 0.9,
                         "{}", "bench", "2026-10-31T23:59:00", None, None))
        con.execute("BEGIN IMMEDIATE")
        con.executemany("INSERT INTO risk_decision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.execute("COMMIT")

    def recent_page():
        con.execute("SELECT decision_id, customer_id, beneficiary_id, amount, score, band FROM risk_decision "
                    "WHERE band <> 'APPROVE' ORDER BY decided_at DESC LIMIT 50").fetchall()

    def one_decision():
        con.execute("SELECT * FROM risk_decision WHERE decision_id=?", (f"D{rng.randint(0, ROWS - 1):09d}",)).fetchone()

    def customer_history():
        con.execute("SELECT amount, score, band, decided_at FROM risk_decision WHERE customer_id=? "
                    "ORDER BY decided_at DESC LIMIT 100", (f"C{rng.randint(1, 200_000):06d}",)).fetchall()

    def daily_false_alerts():
        con.execute("SELECT substr(decided_at,1,10) d, band, COUNT(*) FROM risk_decision WHERE decided_at >= ? "
                    "GROUP BY d, band", ("2026-10-24",)).fetchall()

    res = {"append_batch_of_100_durable": timed(append_batch_100, 100), "recent_non_approved_page_50": timed(recent_page, 300),
           "decision_by_id": timed(one_decision, 500), "customer_last_100": timed(customer_history, 500),
           "metrics_last_7_days": timed(daily_false_alerts, 10)}
    size_mb = sum(os.path.getsize(str(db) + s) for s in ("", "-wal") if os.path.exists(str(db) + s)) / 1e6
    con.close()
    for s in ("", "-wal", "-shm"):
        if Path(str(db) + s).exists():
            os.remove(str(db) + s)
    return {"rows": ROWS, "db_size_mb": round(size_mb, 1), "bulk_load_s": round(build_s, 1),
            "bytes_per_row_on_disk": round(size_mb * 1e6 / ROWS), "queries": res,
            "durable_appends_per_s": round(100 / (res["append_batch_of_100_durable"]["p50_ms"] / 1000))}


def main():
    repo = Path(sys.argv[1]).resolve()
    work = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.gettempdir())
    summary = {"what": "synthetic data; single thread; desktop core; SQLite stands in for PostgreSQL",
               "machine": {"cpu_count": os.cpu_count(), "sqlite": sqlite3.sqlite_version},
               "existing_scorer": scorer_benchmark(repo), "decision_log": db_benchmark(work)}
    (Path(__file__).resolve().parent / "capacity_benchmark_result.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
