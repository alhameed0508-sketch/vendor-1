"""Time-separated evaluation of the unified risk engine against three baselines. SYNTHETIC DATA ONLY.

    python scripts/evaluation/evaluate_unified.py            # full run (3 seeds, 400 customers)
    python scripts/evaluation/evaluate_unified.py --quick    # small smoke run

Protocol (docs/SYSTEM_DESIGN.md section 6):
* days 0-44  warm-up: history is committed to profiles and the ring map, nothing is scored;
* days 45-51 calibration: scored with the hand-set prior model; these rows train the logistic model;
* days 52-59 test: scored again from scratch with each model; every reported metric comes from here.
The fitted model is trained on ONE seed's calibration window and tested on that seed's later days and on
two other seeds (different customers, rings and fraud). Labels come from the simulator and are never
used for scoring. Nothing here is a measurement on real bank data; the targets are targets.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from intelligence.contracts import APPROVE, REVIEW, STEP_UP  # noqa: E402
from intelligence.engine import UnifiedRiskEngine  # noqa: E402
from intelligence.model import DEFAULT_PATH, PRIOR, RiskModel, fit, save  # noqa: E402
from intelligence.mule_network import MuleNetworkIntel  # noqa: E402
from intelligence.profiles import event_seconds, local_hour  # noqa: E402
from intelligence.simulator import JourneySimulator, day_of  # noqa: E402

WARM_UP_END, CALIBRATION_END, DAYS = 45, 52, 60
TRAIN_SEED = 101
SEEDS = (101, 202, 303)
CUSTOMER_FRAUD = ("app_scam", "app_scam_quiet", "app_scam_fresh_mule", "ato", "ato_own_device", "ato_quiet")
MULE_MOVEMENT = ("mule_inbound", "mule_forward")
SYSTEMS = ("static_rules", "mule_only", "unified_no_fp_control", "unified")
SYSTEM_LABELS = {
    "static_rules": "Static rules (amount + new payee/device/city + night)",
    "mule_only": "Mule core alone (existing ring map and endpoint evidence)",
    "unified_no_fp_control": "Unified score, false-positive controls switched off",
    "unified": "Unified engine (this work)",
}
# Design targets [P] from docs/SYSTEM_DESIGN.md (section 2 and D08). Targets, not results.
TARGETS = {
    "genuine_interrupt_rate": {"target": 0.005, "op": "<=", "label": "Genuine payments interrupted (step-up + review)"},
    "review_precision": {"target": 0.90, "op": ">=", "label": "Precision of the REVIEW band"},
    "recall_interrupt": {"target": 0.95, "op": ">=", "label": "Fraud payments interrupted (recall)"},
    "decision_p95_ms": {"target": 200.0, "op": "<=", "label": "Decision latency p95 (ms)"},
}
OUT_JSON = ROOT / "docs" / "evaluation" / "risk_engine_evaluation.json"
OUT_MD = ROOT / "docs" / "RISK_ENGINE_EVALUATION.md"
CANDIDATE = ROOT / "docs" / "evaluation" / "risk_model_candidate.json"
# Shipped with the backend (docs/ is not in the image): what GET /api/v1/risk/evaluation serves.
SUMMARY = ROOT / "backend" / "intelligence" / "model" / "evaluation_summary.json"


# ----------------------------------------------------------------------------- replay
def replay(seed: int, spec: Optional[Dict], customers: int, rings: int) -> Dict:
    """Run one population through the engine. Returns per-payment rows for days >= WARM_UP_END."""
    sim = JourneySimulator(seed=seed, customers=customers, rings=rings, run_tag=f"E{seed}")
    events = sim.run(days=DAYS, fraud_from_day=WARM_UP_END)
    warm = [e for e in events if day_of(e.event, sim.start) < WARM_UP_END]
    rest = [e for e in events if day_of(e.event, sim.start) >= WARM_UP_END]
    model = RiskModel(spec) if spec else RiskModel(dict(PRIOR))
    engine = UnifiedRiskEngine(mule=MuleNetworkIntel(sim.accounts()), model=model)
    engine.store._max = len(rest) + 10
    started = time.perf_counter()
    engine.warm_up([e.event for e in warm], sim.accounts())
    warm_seconds = time.perf_counter() - started
    mules = set(sim.mule_accounts) | set(sim.fresh_mules)  # fresh mules are created during the fraud days
    rings_at_test_start = _ring_check(engine, mules)
    rows = []
    for e in rest:
        t0 = time.perf_counter()
        d = engine.assess(e.event, commit=True, source="synthetic", label=e.label)
        wall = (time.perf_counter() - t0) * 1000
        codes = [r["code"] for r in d.reasons if r["kind"] != "familiarity"]
        rows.append(
            {
                "day": day_of(e.event, sim.start),
                "kind": e.kind,
                "label": e.label,
                "payer": d.customer_id,
                "amount": d.amount,
                "band": d.band,
                "score": d.score,
                "raw_score": d.explanation["model"]["raw_score"],
                "features": d.explanation["model"]["features"],
                "mule_score": d.engines["mule_network"],
                "codes": codes,
                "confidence": d.confidence,
                "hour": local_hour(event_seconds(e.event["timestamp"])),
                "latency_ms": d.latency_ms,
                "wall_ms": wall,
            }
        )
    refresh = []
    for _ in range(5):
        t0 = time.perf_counter()
        engine.mule.refresh()
        refresh.append((time.perf_counter() - t0) * 1000)
    return {
        "seed": seed,
        "model": model.version,
        "rows": rows,
        "warm_up_payments": len(warm),
        "warm_up_seconds": round(warm_seconds, 2),
        "ring_refresh_ms": round(statistics.median(refresh), 1),
        "rings_at_test_start": rings_at_test_start,
        "rings_at_end": _ring_check(engine, mules),
    }


def _ring_check(engine: UnifiedRiskEngine, mules: set) -> Dict:
    members = set(engine.mule.ring_map["member_of"])
    return {
        "rings": len(engine.mule.ring_map["rings"]),
        "mule_accounts": len(mules),
        "mules_in_rings": len(members & mules),
        "non_mules_in_rings": len(members - mules),
    }


# ----------------------------------------------------------------------------- baselines
def baseline(row: Dict, system: str):
    codes = set(row["codes"])
    if system == "unified":
        return row["band"], row["score"]
    if system == "unified_no_fp_control":
        raw = row["raw_score"]
        return (REVIEW if raw >= 70 else STEP_UP if raw >= 40 else APPROVE), raw
    if system == "mule_only":
        hit = bool(codes & {"MN01", "MN02", "MN03"})
        return (REVIEW if hit else APPROVE), round(100 * row["mule_score"])
    new_payee, new_device, new_city = "BI05" in codes, "SD01" in codes, "BH04" in codes
    night = row["hour"] < 5
    if row["amount"] >= 50_000 and (new_payee or new_device):
        return REVIEW, 100
    if (row["amount"] >= 10_000 and (new_payee or new_device or new_city)) or (night and row["amount"] >= 5_000):
        return STEP_UP, 50
    return APPROVE, 0


# ----------------------------------------------------------------------------- metrics
def average_precision(labels: Sequence[int], scores: Sequence[float]) -> Optional[float]:
    positives = sum(labels)
    if positives == 0:
        return None
    pairs = sorted(zip(scores, labels), key=lambda p: -p[0])
    tp = fp = 0
    ap, prev_recall, i = 0.0, 0.0, 0
    while i < len(pairs):  # ties are processed together (no credit for an arbitrary order)
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            tp += pairs[j][1]
            fp += 1 - pairs[j][1]
            j += 1
        recall = tp / positives
        ap += (recall - prev_recall) * (tp / (tp + fp))
        prev_recall, i = recall, j
    return ap


def _share(num: float, den: float) -> Optional[float]:
    return num / den if den else None


def metrics(rows: List[Dict], system: str) -> Dict:
    decided = [(r, *baseline(r, system)) for r in rows]
    fraud = [(r, b, s) for r, b, s in decided if r["label"] == "fraud"]
    genuine = [(r, b, s) for r, b, s in decided if r["label"] == "genuine"]
    reviewed = [(r, b, s) for r, b, s in decided if b == REVIEW]
    fraud_amount = sum(r["amount"] for r, _, _ in fraud)
    review_tp = sum(1 for r, _, _ in reviewed if r["label"] == "fraud")
    out = {
        "payments": len(decided),
        "fraud": len(fraud),
        "genuine": len(genuine),
        "recall_review": _share(sum(b == REVIEW for _, b, _ in fraud), len(fraud)),
        "recall_interrupt": _share(sum(b != APPROVE for _, b, _ in fraud), len(fraud)),
        "genuine_review_rate": _share(sum(b == REVIEW for _, b, _ in genuine), len(genuine)),
        "genuine_interrupt_rate": _share(sum(b != APPROVE for _, b, _ in genuine), len(genuine)),
        "review_precision": _share(review_tp, len(reviewed)),
        "review_false_discovery_rate": _share(len(reviewed) - review_tp, len(reviewed)),
        "step_up_rate": _share(sum(b == STEP_UP for _, b, _ in decided), len(decided)),
        "review_rate": _share(len(reviewed), len(decided)),
        "pr_auc": average_precision([int(r["label"] == "fraud") for r, _, _ in decided], [s for _, _, s in decided]),
        "fraud_amount_held_share": _share(sum(r["amount"] for r, b, _ in fraud if b == REVIEW), fraud_amount),
        "fraud_amount_interrupted_share": _share(sum(r["amount"] for r, b, _ in fraud if b != APPROVE), fraud_amount),
    }
    return out


def journeys(rows: List[Dict], system: str) -> Dict:
    """Customer-initiated fraud grouped into journeys (same payer, kind and day): how fast is it stopped?"""
    groups: Dict[tuple, List[str]] = defaultdict(list)
    for r in rows:
        if r["kind"] in CUSTOMER_FRAUD:
            groups[(r["payer"], r["kind"], r["day"])].append(baseline(r, system)[0])
    held_first = interrupted_first = never_held = 0
    before_hold = []
    for bands in groups.values():
        held_first += bands[0] == REVIEW
        interrupted_first += bands[0] != APPROVE
        if REVIEW in bands:
            before_hold.append(bands.index(REVIEW))
        else:
            never_held += 1
    n = len(groups)
    return {
        "journeys": n,
        "held_on_first_payment": _share(held_first, n),
        "interrupted_on_first_payment": _share(interrupted_first, n),
        "never_held": _share(never_held, n),
        "median_payments_before_hold": statistics.median(before_hold) if before_hold else None,
    }


def by_kind(rows: List[Dict], system: str) -> Dict:
    out: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        out[r["kind"]][baseline(r, system)[0]] += 1
    return {k: dict(v) for k, v in sorted(out.items())}


def segments(rows: List[Dict]) -> Dict:
    """Genuine interruption rate (unified) by customer-history confidence and amount: who pays for FPs?"""

    def bucket_conf(c):
        return "thin (<0.35)" if c < 0.35 else "partial (0.35-0.7)" if c < 0.7 else "full (>=0.7)"

    def bucket_amount(a):
        return "<1k" if a < 1_000 else "1k-10k" if a < 10_000 else "10k-50k" if a < 50_000 else ">=50k"

    out = {}
    for name, key in (
        ("confidence", lambda r: bucket_conf(r["confidence"])),
        ("amount_inr", lambda r: bucket_amount(r["amount"])),
    ):
        counts: Dict[str, Counter] = defaultdict(Counter)
        for r in rows:
            if r["label"] == "genuine":
                counts[key(r)]["n"] += 1
                counts[key(r)]["interrupted"] += r["band"] != APPROVE
        out[name] = {
            k: {"genuine": v["n"], "interrupt_rate": _share(v["interrupted"], v["n"])}
            for k, v in sorted(counts.items())
        }
    return out


def psi(expected: Sequence[float], actual: Sequence[float], bins: int = 10) -> Optional[float]:
    if not expected or not actual:
        return None
    edges = [100 * k / bins for k in range(bins + 1)]

    def dist(xs):
        counts = [0] * bins
        for x in xs:
            counts[min(bins - 1, int(x // (100 / bins)))] += 1
        return [max(c / len(xs), 1e-4) for c in counts]

    e, a = dist(expected), dist(actual)
    del edges
    return sum((ai - ei) * math.log(ai / ei) for ei, ai in zip(e, a))


def pct(xs: Sequence[float], q: float) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    return round(s[min(len(s) - 1, int(q * len(s)))], 3)


def summarise(run: Dict) -> Dict:
    test = [r for r in run["rows"] if r["day"] >= CALIBRATION_END]
    calibration = [r for r in run["rows"] if r["day"] < CALIBRATION_END]
    customer = [r for r in test if r["kind"] not in MULE_MOVEMENT]
    result = {
        "seed": run["seed"],
        "model": run["model"],
        "warm_up_payments": run["warm_up_payments"],
        "warm_up_seconds": run["warm_up_seconds"],
        "ring_refresh_ms": run["ring_refresh_ms"],
        "rings_at_test_start": run["rings_at_test_start"],
        "rings_at_end": run["rings_at_end"],
        "systems": {
            s: {
                "customer_payments": metrics(customer, s),
                "all_payments": metrics(test, s),
                "journeys": journeys(test, s),
                "by_kind": by_kind(test, s),
            }
            for s in SYSTEMS
        },
        "segments_unified": segments(customer),
        "latency": {
            "decision_ms": {
                "p50": pct([r["latency_ms"] for r in test], 0.5),
                "p95": pct([r["latency_ms"] for r in test], 0.95),
                "p99": pct([r["latency_ms"] for r in test], 0.99),
            },
            "assess_incl_commit_and_sync_refresh_ms": {
                "p50": pct([r["wall_ms"] for r in test], 0.5),
                "p95": pct([r["wall_ms"] for r in test], 0.95),
                "p99": pct([r["wall_ms"] for r in test], 0.99),
                "max": round(max(r["wall_ms"] for r in test), 1),
            },
        },
        "drift_psi_unified_score": {
            "genuine": psi(
                [r["score"] for r in calibration if r["label"] == "genuine"],
                [r["score"] for r in test if r["label"] == "genuine"],
            ),
            "all": psi([r["score"] for r in calibration], [r["score"] for r in test]),
        },
        "brier_customer_payments": _brier(customer),
    }
    return result


def _brier(rows: List[Dict]) -> Optional[float]:
    if not rows:
        return None
    return round(sum((r["raw_score"] / 100 - (r["label"] == "fraud")) ** 2 for r in rows) / len(rows), 5)


# ----------------------------------------------------------------------------- driver
def _job(args):
    seed, spec, customers, rings = args
    return summarise(replay(seed, spec, customers, rings)), seed


def train(customers: int, rings: int) -> Dict:
    run = replay(TRAIN_SEED, None, customers, rings)
    cal = [r for r in run["rows"] if WARM_UP_END <= r["day"] < CALIBRATION_END]
    spec = fit(
        [r["features"] for r in cal],
        [int(r["label"] == "fraud") for r in cal],
        version=f"lr-synthetic-s{TRAIN_SEED}-{datetime.now(timezone.utc):%Y%m%d}",
        trained_on=f"synthetic journey simulator, seed {TRAIN_SEED}, days {WARM_UP_END}-{CALIBRATION_END - 1} "
        f"({len(cal)} payments, {sum(r['label'] == 'fraud' for r in cal)} fraud)",
    )
    spec["trained_rows"] = len(cal)
    return spec


def gate(prior: Dict, fitted: Dict) -> Dict:
    """Ship the fitted model only if it is no worse on false positives and recall, averaged over seeds."""

    def mean(results, key):
        vals = [r["systems"]["unified"]["customer_payments"][key] for r in results]
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else 0.0

    p = {k: mean(prior, k) for k in ("genuine_interrupt_rate", "recall_interrupt", "review_precision", "pr_auc")}
    f = {k: mean(fitted, k) for k in p}
    ok = (
        f["genuine_interrupt_rate"] <= p["genuine_interrupt_rate"] + 0.0005
        and f["recall_interrupt"] >= p["recall_interrupt"] - 0.01
        and f["review_precision"] >= p["review_precision"] - 0.01
    )
    return {
        "prior": p,
        "fitted": f,
        "ship_fitted": ok,
        "rule": "fitted must not raise genuine interruptions by more than 0.05 pp, nor lower recall or REVIEW "
        "precision by more than 1 pp (means over the test windows of all seeds)",
    }


def main(argv=None) -> Dict:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="small population, one seed (smoke run)")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--no-write", action="store_true", help="print only; do not write docs or the model")
    parser.add_argument(
        "--from-json",
        action="store_true",
        help="re-render the report and summary from the saved JSON without re-running",
    )
    args = parser.parse_args(argv)
    if args.from_json:
        report = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        OUT_MD.write_text(render_markdown(report), encoding="utf-8")
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps(summary(report), indent=2), encoding="utf-8")
        return report
    customers, rings, seeds = (80, 2, (TRAIN_SEED,)) if args.quick else (400, 4, SEEDS)

    t0 = time.perf_counter()
    spec = train(customers, rings)
    jobs = [(s, None, customers, rings) for s in seeds] + [(s, spec, customers, rings) for s in seeds]
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            done = list(pool.map(_job, jobs))
    else:
        done = [_job(j) for j in jobs]
    prior = [r for r, _ in done[: len(seeds)]]
    fitted = [r for r, _ in done[len(seeds) :]]
    decision = gate(prior, fitted)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": "SYNTHETIC. MuleCatch journey simulator (backend/intelligence/simulator.py). Not bank data.",
        "protocol": {
            "warm_up_days": [0, WARM_UP_END - 1],
            "calibration_days": [WARM_UP_END, CALIBRATION_END - 1],
            "test_days": [CALIBRATION_END, DAYS - 1],
            "train_seed": TRAIN_SEED,
            "seeds": list(seeds),
            "customers": customers,
            "rings": rings,
            "note": "metrics come from the test days only; the fitted model never saw the test days or the other seeds",
        },
        "targets": TARGETS,
        "systems": SYSTEM_LABELS,
        "prior_model": prior,
        "fitted_model": fitted,
        "fitted_spec": spec,
        "model_gate": decision,
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    if not args.no_write:
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        save(spec, CANDIDATE)
        if decision["ship_fitted"] and not args.quick:
            save({**spec, "metrics": {"gate": decision}}, DEFAULT_PATH)
        OUT_MD.write_text(render_markdown(report), encoding="utf-8")
        if not args.quick:
            SUMMARY.parent.mkdir(parents=True, exist_ok=True)
            SUMMARY.write_text(json.dumps(summary(report), indent=2), encoding="utf-8")
    return report


def summary(report: Dict) -> Dict:
    """Compact, dashboard-ready summary: means over seeds on the test days, targets kept separate."""
    shipped = report["model_gate"]["ship_fitted"]
    best = report["fitted_model"] if shipped else report["prior_model"]
    keys = (
        "recall_interrupt",
        "recall_review",
        "genuine_interrupt_rate",
        "genuine_review_rate",
        "review_precision",
        "pr_auc",
        "fraud_amount_interrupted_share",
        "step_up_rate",
        "review_rate",
    )
    systems = {}
    for system in SYSTEMS:
        row = {}
        for key in keys:
            m, lo, hi = _mean(best, system, "customer_payments", key)
            row[key] = None if m is None else {"mean": round(m, 5), "min": round(lo, 5), "max": round(hi, 5)}
        systems[system] = {"label": report["systems"][system], "customer_payments": row}
    return {
        "data": report["data"],
        "generated_at": report["generated_at"],
        "protocol": report["protocol"],
        "model_used": report["fitted_spec"]["version"] if shipped else PRIOR["version"],
        "model_gate": report["model_gate"],
        "targets": report["targets"],
        "systems": systems,
        "latency_decision_p95_ms_worst_seed": max(r["latency"]["decision_ms"]["p95"] for r in best),
        "rings": [{"seed": r["seed"], **r["rings_at_test_start"]} for r in best],
        "journeys_unified": [{"seed": r["seed"], **r["systems"]["unified"]["journeys"]} for r in best],
        "by_kind_unified_first_seed": best[0]["systems"]["unified"]["by_kind"],
        "caveat": "Synthetic, time-separated test days. Targets are design targets, not results. The simulator was "
        "written by the same team as the engine; real-world precision depends on the real fraud rate.",
    }


# ----------------------------------------------------------------------------- report
def _fmt(v, kind="pct"):
    if v is None:
        return "n/a"
    if kind == "pct":
        return f"{100 * v:.2f}%"
    if kind == "ms":
        return f"{v:.2f} ms"
    return f"{v:.3f}"


def _mean(results: List[Dict], system: str, scope: str, key: str):
    vals = [r["systems"][system][scope][key] for r in results if r["systems"][system][scope][key] is not None]
    if not vals:
        return None, None, None
    return sum(vals) / len(vals), min(vals), max(vals)


def render_markdown(report: Dict) -> str:
    shipped = report["model_gate"]["ship_fitted"]
    best = report["fitted_model"] if shipped else report["prior_model"]
    model_name = "fitted logistic model" if shipped else "hand-set prior model"
    p = report["protocol"]
    lines = [
        "# Unified risk engine: evaluation",
        "",
        f"> **Synthetic data only.** Every number below comes from the MuleCatch journey simulator "
        f"(`backend/intelligence/simulator.py`), not from bank data. Generated {report['generated_at']} by "
        "`scripts/evaluation/evaluate_unified.py`; raw output in `docs/evaluation/risk_engine_evaluation.json`.",
        "",
        "## Protocol",
        "",
        f"- Warm-up days {p['warm_up_days'][0]}-{p['warm_up_days'][1]}: history only (profiles, ring map); nothing "
        "scored.",
        f"- Calibration days {p['calibration_days'][0]}-{p['calibration_days'][1]}: scored with the prior model; "
        f"these rows train the logistic model (seed {p['train_seed']} only).",
        f"- Test days {p['test_days'][0]}-{p['test_days'][1]}: every metric below. Seeds {p['seeds']} "
        f"({p['customers']} customers, {p['rings']} mule rings each); seeds other than {p['train_seed']} are "
        "populations the model never saw.",
        "- Customer payments = genuine payments plus customer-initiated fraud (APP scams and account takeovers, "
        "including quiet variants and brand-new mule payees). Mule movements (payments into and between mule "
        "accounts) are reported separately because the mule core already sees those rings.",
        "",
        "## Targets (design targets, not results)",
        "",
        "| Target | Value | Result on synthetic test days (" + model_name + ", mean of seeds) | Met? |",
        "|---|---|---|---|",
    ]
    for key, t in report["targets"].items():
        if key == "decision_p95_ms":
            vals = [r["latency"]["decision_ms"]["p95"] for r in best]
            value = max(vals)
            shown = f"{value:.2f} ms (worst seed)"
        else:
            value = _mean(best, "unified", "customer_payments", key)[0]
            shown = _fmt(value)
        met = value is not None and (value <= t["target"] if t["op"] == "<=" else value >= t["target"])
        target = (
            f"{t['op']} {t['target']:.0f} ms" if key == "decision_p95_ms" else f"{t['op']} {100 * t['target']:.1f}%"
        )
        lines.append(f"| {t['label']} | {target} | {shown} | {'yes (synthetic)' if met else '**no**'} |")
    lines += [
        "",
        "Meeting a target on simulated data says the logic works as designed; it is not evidence about real "
        "traffic. The simulator was written by the same team as the engine.",
        "",
        "## Customer payments: unified engine vs baselines (" + model_name + ", mean over seeds, [min-max])",
        "",
        "| System | Fraud interrupted | Fraud held (REVIEW) | Genuine interrupted | Genuine held | REVIEW precision "
        "| PR-AUC | Fraud ₹ interrupted |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for system in SYSTEMS:
        cells = []
        for key in (
            "recall_interrupt",
            "recall_review",
            "genuine_interrupt_rate",
            "genuine_review_rate",
            "review_precision",
            "pr_auc",
            "fraud_amount_interrupted_share",
        ):
            m, lo, hi = _mean(best, system, "customer_payments", key)
            kind = "num" if key == "pr_auc" else "pct"
            cells.append("n/a" if m is None else f"{_fmt(m, kind)} [{_fmt(lo, kind)}-{_fmt(hi, kind)}]")
        lines.append(f"| {report['systems'][system]} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## All payments, including mule movements (mean over seeds)",
        "",
        "| System | Fraud interrupted | Genuine interrupted | REVIEW precision | PR-AUC |",
        "|---|---|---|---|---|",
    ]
    for system in SYSTEMS:
        cells = []
        for key in ("recall_interrupt", "genuine_interrupt_rate", "review_precision", "pr_auc"):
            m = _mean(best, system, "all_payments", key)[0]
            cells.append(_fmt(m, "num" if key == "pr_auc" else "pct"))
        lines.append(f"| {report['systems'][system]} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## Where each fraud journey type ends up (unified, seed " + str(best[0]["seed"]) + ")",
        "",
        "| Payment type | APPROVE | STEP_UP | REVIEW |",
        "|---|---|---|---|",
    ]
    for kind, c in best[0]["systems"]["unified"]["by_kind"].items():
        lines.append(f"| {kind} | {c.get('APPROVE', 0)} | {c.get('STEP_UP', 0)} | {c.get('REVIEW', 0)} |")
    j = best[0]["systems"]["unified"]["journeys"]
    lines += [
        "",
        "## Time to detection (customer-initiated fraud journeys, unified, seed " + str(best[0]["seed"]) + ")",
        "",
        f"- Journeys: {j['journeys']}; held on the first payment: {_fmt(j['held_on_first_payment'])}; "
        f"interrupted on the first payment: {_fmt(j['interrupted_on_first_payment'])}; never held: "
        f"{_fmt(j['never_held'])}; median payments before the hold: {j['median_payments_before_hold']}.",
        "",
        "## Mule rings (the core)",
        "",
        "| Seed | Rings at test start | Mule accounts in rings | Non-mule accounts in rings |",
        "|---|---|---|---|",
    ]
    for r in best:
        rs = r["rings_at_test_start"]
        lines.append(
            f"| {r['seed']} | {rs['rings']} | {rs['mules_in_rings']} of {rs['mule_accounts']} | "
            f"{rs['non_mules_in_rings']} |"
        )
    seg = best[0]["segments_unified"]
    lines += [
        "",
        f"## Who carries the false positives (genuine interruption rate, unified, seed {best[0]['seed']})",
        "",
        "| Segment | Genuine payments | Interrupted |",
        "|---|---|---|",
    ]
    for name, rows in seg.items():
        for k, v in rows.items():
            lines.append(f"| {name}: {k} | {v['genuine']} | {_fmt(v['interrupt_rate'])} |")
    lines += [
        "",
        "## Speed (measured on this machine, single process)",
        "",
        "| Seed | Decision p50 | p95 | p99 | Assess incl. commit + synchronous ring refresh p95 | max | "
        "Ring-map refresh |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in best:
        d, w = r["latency"]["decision_ms"], r["latency"]["assess_incl_commit_and_sync_refresh_ms"]
        lines.append(
            f"| {r['seed']} | {d['p50']} ms | {d['p95']} ms | {d['p99']} ms | {w['p95']} ms | {w['max']} ms | "
            f"{r['ring_refresh_ms']} ms |"
        )
    lines += [
        "",
        "In the API the ring map is rebuilt on a background thread, so the refresh is off the payment path; "
        "the evaluation runs it synchronously every 25 payments to stay deterministic.",
        "",
        "## Drift and calibration",
        "",
        "| Seed | PSI genuine score (calibration vs test) | PSI all | Brier (customer payments) |",
        "|---|---|---|---|",
    ]
    for r in best:
        dpsi = r["drift_psi_unified_score"]
        lines.append(
            f"| {r['seed']} | {_fmt(dpsi['genuine'], 'num')} | {_fmt(dpsi['all'], 'num')} | "
            f"{r['brier_customer_payments']} |"
        )
    g = report["model_gate"]
    lines += [
        "",
        "PSI below 0.1 is usually read as stable, 0.1-0.25 as moderate shift, above 0.25 as a shift to investigate.",
        "",
        "## Prior vs fitted model",
        "",
        f"Gate: {g['rule']}. Result: **{'fitted model shipped' if shipped else 'prior model kept'}**.",
        "",
        "| Model | Genuine interrupted | Fraud interrupted | REVIEW precision | PR-AUC |",
        "|---|---|---|---|---|",
        f"| Prior (hand-set) | {_fmt(g['prior']['genuine_interrupt_rate'])} | {_fmt(g['prior']['recall_interrupt'])} "
        f"| {_fmt(g['prior']['review_precision'])} | {_fmt(g['prior']['pr_auc'], 'num')} |",
        f"| Fitted ({report['fitted_spec']['version']}) | {_fmt(g['fitted']['genuine_interrupt_rate'])} | "
        f"{_fmt(g['fitted']['recall_interrupt'])} | {_fmt(g['fitted']['review_precision'])} | "
        f"{_fmt(g['fitted']['pr_auc'], 'num')} |",
        "",
        "## What this does not show",
        "",
        "- Real-world precision. At a 0.1 % fraud rate, even 0.5 % of genuine payments interrupted means most "
        "interruptions are genuine (docs/SYSTEM_DESIGN.md section 6). The simulator's fraud rate is far higher.",
        "- Adversaries who adapt. The simulated fraudsters follow fixed scripts.",
        "- Session and device signals on real devices: the simulator invents sessions; the live Bitcoin feed has none.",
        "- The brand-new mule payee (`app_scam_fresh_mule`) and the quiet takeover paying a fresh account have "
        "no evidence to find at payment time; the engine asks for a step-up at most, by design.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    result = main()
    gate_result = result["model_gate"]
    print(
        json.dumps(
            {
                "runtime_seconds": result["runtime_seconds"],
                "ship_fitted": gate_result["ship_fitted"],
                "prior": gate_result["prior"],
                "fitted": gate_result["fitted"],
            },
            indent=2,
        )
    )
