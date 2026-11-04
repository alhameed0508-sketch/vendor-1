"""How much traffic will MuleCatch's unified risk engine get? A bottom-up workload model.

Two traffic classes:
  1. Payment events from the bank's payment switch (machine-to-machine, 24 x 7). This is the load
     that sizes the system. It starts from public NPCI UPI volumes, not from a round guess.
  2. People: investigators, supervisors and admins using the dashboards (working hours only).

Blocks:
  MEASURED  - public facts and figures measured in this repository, each with its source.
  A         - every judgement call in one dict. Change one and re-run.
Outputs next to this script:
  workload_model_result.json   every number the design page quotes
  expected_strings.json        {"label": "text"} pairs for check_page.py numbers
Usage: python -I -X utf8 workload_model.py
"""
import datetime as dt
import json
from pathlib import Path

# ---------------------------------------------------------------- MEASURED --
MEASURED = {
    # NPCI data as reported by third-party outlets (see SOURCES). National UPI, Sep 2026.
    "upi_national_per_month_sep2026": 24.07e9,
    # Indian Overseas Bank as UPI remitter, May 2025 (third-party reproduction of NPCI's table).
    "iob_remitter_per_month_may2025": 298.90e6,
    # Reported year-on-year UPI growth (Jan 2026), used to age the May 2025 bank figure.
    "upi_yoy_growth": 0.28,
    # docs/buildx/05-evaluation.md 7.6b: today's per-payment scorer on the audit laptop (Louvain inside).
    "existing_scorer_p50_ms": 165.0,
    "existing_scorer_p95_ms": 264.0,
    # Rescored every N committed payments by the existing scorer (backend/services/realtime_scorer.py).
    "existing_partition_every_n_payments": 10,
    # Demo replay rate options in the live-stream page (frontend/src/live_stream/LiveStream.js RATES).
    "demo_max_payments_per_s": 20,
    # evidence/capacity_benchmark_result.json: this machine, 1 desktop core, synthetic history of 1,667 payments.
    "existing_scorer_cached_p50_ms_here": 46.41,
    "existing_scorer_rebuild_p50_ms_here": 108.45,
    "existing_scorer_blended_mean_ms_here": 52.89,
    # Decision log on disk incl. 3 indexes and full explanations for the ~3 % non-approved rows.
    "decision_log_bytes_per_row_measured": 890,
    "durable_appends_per_s_sqlite": 88889,
}
SOURCES = {
    "upi_national_per_month_sep2026": "https://startuptalky.com/india-upi-transactions-september-2026/",
    "iob_remitter_per_month_may2025": "https://hellobanker.in/top-banks-in-upi-payments-for-may-2025-check-sbi-pnb-bob-hdfc-icici-rank/",
    "upi_yoy_growth": "https://entrackr.com/news/upi-sets-new-monthly-record-with-217-bn-transactions-in-january-11063663",
    "existing_scorer_p50_ms": "docs/buildx/05-evaluation.md section 7.6b",
}

# ---------------------------------------------------------------- ASSUMED --
A = {
    "days_per_month": 30.4,
    "pilot_share": 0.05,                 # pilot: shadow-score 5 % of the bank's UPI outward payments
    "growth_years_since_may2025": 1.4,   # May 2025 -> Oct 2026
    "busiest_day_factor": 1.4,           # salary days, festivals vs an average day
    "peak_hour_share_of_day": 0.075,     # UPI's evening peak hour carries ~7.5 % of the day
    "burst_factor_within_hour": 1.5,     # busiest minute vs the busiest-hour average (machine traffic is smooth)
    "cpu_ms_per_decision_target": 20,    # unified engine hot path, Louvain moved off the hot path
    "target_cpu_utilisation": 0.6,       # plan cores so the busiest minute runs at 60 %
    "non_approve_share": 0.03,           # step-up + review share (design target, not measured)
    "event_bytes": 900,                  # one payment event with session context on the wire (Kafka / HTTP)
    "response_time_s": 0.05,             # for Little's law
    "staff_hours_per_day": 9,
    "fraud_prevalence": 0.001,           # 1 in 1,000 payments is fraud (order of magnitude; banks' real rate needed)
    "target_recall": 0.95, "target_precision": 0.90, "target_fpr": 0.005,   # the brief's engineering targets
}
STAFF = {  # people per scenario (A): investigators, supervisors, admins
    "Pilot": {"Investigator": 6, "Supervisor": 2, "Admin": 2},
    "Whole bank": {"Investigator": 40, "Supervisor": 8, "Admin": 4},
    "Larger bank (3x)": {"Investigator": 120, "Supervisor": 20, "Admin": 8},
}
STAFF_MIX = {  # requests per person per working day, by endpoint (A)
    "Investigator": {"GET /alerts": 40, "GET /alerts/:id": 60, "GET /alerts/:id/subgraph": 40, "GET /risk/decisions": 60,
                     "GET /risk/decisions/:id": 40, "POST /risk/decisions/:id/feedback": 15, "POST /genai/chat": 5},
    "Supervisor": {"GET /alerts": 30, "GET /alerts/:id": 40, "GET /alerts/:id/subgraph": 20, "GET /risk/decisions": 40,
                   "GET /risk/decisions/:id": 30, "POST /risk/decisions/:id/feedback": 15, "POST /genai/chat": 5},
    "Admin": {"GET /risk/metrics": 20, "GET /risk/decisions": 20, "GET /risk/feeds": 10, "GET /alerts": 10},
}
STAFF_READS = {role: sum(mix.values()) for role, mix in STAFF_MIX.items()}


def scenario(name, bank_multiple, share):
    growth = (1 + MEASURED["upi_yoy_growth"]) ** A["growth_years_since_may2025"]
    bank_month = MEASURED["iob_remitter_per_month_may2025"] * growth * bank_multiple
    per_day = bank_month / A["days_per_month"] * share
    avg_s = per_day / 86400
    busy_hour = per_day * A["busiest_day_factor"] * A["peak_hour_share_of_day"] / 3600
    peak = busy_hour * A["burst_factor_within_hour"]
    cores_target = peak * A["cpu_ms_per_decision_target"] / 1000 / A["target_cpu_utilisation"]
    cores_existing = peak * MEASURED["existing_scorer_p50_ms"] / 1000 / A["target_cpu_utilisation"]
    rows_year = per_day * 365
    db_gb_year = rows_year * MEASURED["decision_log_bytes_per_row_measured"] / 1e9
    db_gb_year_non_approve = rows_year * A["non_approve_share"] * MEASURED["decision_log_bytes_per_row_measured"] / 1e9
    cores_blended = peak * MEASURED["existing_scorer_blended_mean_ms_here"] / 1000 / A["target_cpu_utilisation"]
    staff = STAFF[name]
    staff_req = sum(n * STAFF_READS[r] for r, n in staff.items())
    per_endpoint = {"POST /risk/assess": round(per_day)}
    for role, n in staff.items():
        for ep, k in STAFF_MIX[role].items():
            per_endpoint[ep] = per_endpoint.get(ep, 0) + n * k
    return {
        "scenario": name,
        "bank_payments_per_month_m": round(bank_month / 1e6, 1),
        "payments_per_day": round(per_day),
        "avg_payments_per_s": round(avg_s, 1),
        "ms_between_payments": round(1000 / avg_s, 1),
        "busy_hour_per_s": round(busy_hour, 1),
        "busiest_minute_per_s": round(peak, 1),
        "in_flight_at_peak": round(peak * A["response_time_s"], 1),
        "cpu_cores_at_target": round(cores_target, 2),
        "cpu_cores_with_existing_scorer": round(cores_existing, 1),
        "cpu_cores_existing_measured_here": round(cores_blended, 1),
        "non_approve_per_day": round(per_day * A["non_approve_share"]),
        "decision_log_gb_per_year": round(db_gb_year, 1),
        "decision_log_tb_10y": round(db_gb_year * 10 / 1000, 2),
        "non_approved_log_gb_per_year": round(db_gb_year_non_approve, 1),
        "ingress_mb_per_s_at_peak": round(peak * A["event_bytes"] / 1e6, 2),
        "staff": sum(staff.values()),
        "staff_requests_per_day": staff_req,
        "staff_busiest_minute_per_s": round(staff_req * 3 * 0.25 / 3600, 2),
        "per_endpoint_per_day": per_endpoint,
    }


SCENARIOS = [scenario("Pilot", 1, A["pilot_share"]), scenario("Whole bank", 1, 1.0),
             scenario("Larger bank (3x)", 3, 1.0)]
national_per_day = MEASURED["upi_national_per_month_sep2026"] / A["days_per_month"]
# Base-rate effect: what the targets imply for the same alert set.
prev, rec, fpr, prec_t = A["fraud_prevalence"], A["target_recall"], A["target_fpr"], A["target_precision"]
precision_at_target_fpr = prev * rec / (prev * rec + (1 - prev) * fpr)
fpr_needed_for_target_precision = prev * rec * (1 - prec_t) / (prec_t * (1 - prev))
pilot_day = SCENARIOS[0]["payments_per_day"]
BASE_RATE = {
    "precision_if_fpr_is_0_5pct": round(precision_at_target_fpr, 3),
    "fpr_needed_for_90pct_precision": round(fpr_needed_for_target_precision, 6),
    "pilot_fraud_per_day": round(pilot_day * prev),
    "pilot_genuine_flagged_per_day_at_0_5pct": round(pilot_day * (1 - prev) * fpr),
    "pilot_genuine_flagged_per_day_at_needed_fpr": round(pilot_day * (1 - prev) * fpr_needed_for_target_precision),
}
here = Path(__file__).resolve().parent
(here / "workload_model_result.json").write_text(json.dumps(
    {"generated": dt.date.today().isoformat(), "measured": MEASURED, "sources": SOURCES, "assumptions": A,
     "staff": STAFF, "staff_mix": STAFF_MIX, "staff_reads": STAFF_READS, "scenarios": SCENARIOS,
     "base_rate": BASE_RATE,
     "national_upi_per_day": round(national_per_day), "national_upi_avg_per_s": round(national_per_day / 86400)},
    indent=2), encoding="utf8")
p, w, g = SCENARIOS
expected = {
    "pilot payments/day": f'{p["payments_per_day"]:,}',
    "pilot busiest minute": f'{p["busiest_minute_per_s"]}',
    "pilot cores": f'{p["cpu_cores_at_target"]}',
    "bank payments/day": f'{w["payments_per_day"]:,}',
    "bank busiest minute": f'{w["busiest_minute_per_s"]}',
    "bank cores target": f'{w["cpu_cores_at_target"]}',
    "bank cores existing": f'{w["cpu_cores_with_existing_scorer"]}',
    "bank log GB/yr": f'{w["decision_log_gb_per_year"]:,}',
    "pilot log GB/yr": f'{p["decision_log_gb_per_year"]}',
    "bank cores measured here": f'{w["cpu_cores_existing_measured_here"]}',
    "larger busiest minute": f'{g["busiest_minute_per_s"]:,}',
    "precision at 0.5% fpr": f'{BASE_RATE["precision_if_fpr_is_0_5pct"] * 100:.0f}%',
    "genuine flagged at 0.5%": f'{BASE_RATE["pilot_genuine_flagged_per_day_at_0_5pct"]:,}',
}
(here / "expected_strings.json").write_text(json.dumps(expected, indent=2), encoding="utf8")
for s in SCENARIOS:
    print(f"\n== {s['scenario']}")
    for k, v in s.items():
        if k != "scenario":
            print(f"  {k}: {v}")
print(f"\nnational UPI per day: {national_per_day:,.0f} ({national_per_day / 86400:,.0f}/s average)")
