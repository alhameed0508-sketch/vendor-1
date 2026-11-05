"""
Assessment ledger: one CBS batch from raw rows to a suggested next step per account.

Feeds the Assessment ledger dashboard. Every figure comes from the file currently loaded:

- raw-row figures (row counts, credit and debit legs, liens, negative balances, channels)
  are read straight from the uploaded rows, before the adapter pairs debit and credit legs;
- risk score, mule classification and ring come from the detection pipeline's alerts, via
  ``upload_analysis.analyze_dataset``, the same numbers ``POST /csv-upload/analyze`` returns;
- each account's three leading drivers are the largest terms of the lightweight scorer's
  own weighted sum (``HEURISTIC_WEIGHTS`` x normalised feature value), so a driver is named
  only when the scorer would actually weigh it.

With no CBS upload loaded, the ledger shows the synthetic sample extract
(``data_adapters.sample_cbs``) scored in isolation, so the public demo carries no bank data
and nobody's upload is overwritten. Only the sample knows which accounts are the planted
ring, so only the sample can report how many genuine customers were flagged.
"""

from __future__ import annotations

import csv
import hashlib
import statistics
from collections import defaultdict
from io import StringIO
from types import SimpleNamespace
from typing import Dict, Iterable, List, Mapping, Optional

from models.gnn.lightweight_scorer import FEATURE_NAMES, HEURISTIC_WEIGHTS, extract_features

FEATURE_KEYS = {
    "account_age": "account_age_days",
    "kyc_numeric": "kyc_numeric",
    "smurf_score": "smurf_score",
    "velocity": "velocity",
    "fan_out": "fan_out",
    "fan_in": "fan_in",
    "rhythm": "rhythm",
    "consolidation": "consolidation",
    "in_degree": "in_degree",
    "out_degree": "out_degree",
    "betweenness": "betweenness",
    "pagerank": "pagerank",
    "baseline_deviation": "baseline_deviation",
}
DRIVERS_PER_ACCOUNT = 3
MAX_ROWS = 50000  # MuleCSVAdapter.parse default
SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


def _amount(value) -> float:
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def summarize_cbs(content: str, max_rows: int = MAX_ROWS) -> Dict:
    """Raw-row figures for a pipe-delimited CBS extract: batch totals, channels, per account.

    Reads the same rows the adapter parses (BOM stripped, first ``max_rows``).
    """
    reader = csv.DictReader(StringIO(content.lstrip("﻿")), delimiter="|")
    amounts: List[float] = []
    legs = {"C": [0, 0.0], "D": [0, 0.0]}
    channels: Dict[str, List[float]] = defaultdict(lambda: [0, 0.0])
    accounts: Dict[str, Dict] = {}
    dates = set()
    for index, row in enumerate(reader):
        if max_rows and index >= max_rows:
            break
        acid = (row.get("ACID") or "").strip()
        if not acid:
            continue
        amount = _amount(row.get("TRAN_AMT"))
        balance = _amount(row.get("balance"))
        lien = _amount(row.get("LIEN_AMT"))
        part = (row.get("PART_TRAN_TYPE") or "").strip().upper()
        channel = (row.get("channel") or "UNKNOWN").strip() or "UNKNOWN"
        amounts.append(amount)
        dates.add((row.get("TRAN_DATE") or "").strip())
        if part in legs:
            legs[part][0] += 1
            legs[part][1] += amount
        channels[channel][0] += 1
        channels[channel][1] += amount
        acc = accounts.setdefault(
            acid,
            {
                "rows": 0,
                "credit_count": 0,
                "credit_amount": 0.0,
                "debit_count": 0,
                "debit_amount": 0.0,
                "min_balance": balance,
                "negative_rows": 0,
                "lien": 0.0,
                "customer_age": int(_amount(row.get("customer_age"))),
                "opened": (row.get("ACCT_OPN_DATE") or "").strip()[:10],
                "channels": set(),
            },
        )
        acc["rows"] += 1
        if part == "C":
            acc["credit_count"] += 1
            acc["credit_amount"] += amount
        elif part == "D":
            acc["debit_count"] += 1
            acc["debit_amount"] += amount
        acc["min_balance"] = min(acc["min_balance"], balance)
        acc["negative_rows"] += balance < 0
        acc["lien"] = max(acc["lien"], lien)
        acc["channels"].add(channel)

    total = sum(amounts)
    for acc in accounts.values():
        acc["channels"] = sorted(acc["channels"])
        acc["turnover"] = round(acc["credit_amount"] + acc["debit_amount"], 2)
        acc["credit_amount"] = round(acc["credit_amount"], 2)
        acc["debit_amount"] = round(acc["debit_amount"], 2)
        acc["pass_through"] = round(acc["debit_amount"] / acc["credit_amount"], 4) if acc["credit_amount"] > 0 else None
        acc["share_of_batch"] = round(acc["turnover"] / total, 4) if total else 0.0

    liens = [a["lien"] for a in accounts.values() if a["lien"] > 0]
    negative = [a for a in accounts.values() if a["negative_rows"]]
    batch = {
        "rows": len(amounts),
        "accounts": len(accounts),
        "total_amount": round(total, 2),
        "credit": {"count": legs["C"][0], "amount": round(legs["C"][1], 2)},
        "debit": {"count": legs["D"][0], "amount": round(legs["D"][1], 2)},
        "amount_stats": {
            "min": min(amounts) if amounts else 0.0,
            "median": round(statistics.median(amounts), 2) if amounts else 0.0,
            "mean": round(total / len(amounts), 2) if amounts else 0.0,
            "max": max(amounts) if amounts else 0.0,
        },
        "lien": {"accounts": len(liens), "amount": round(sum(liens), 2)},
        "negative_balance": {
            "rows": sum(a["negative_rows"] for a in accounts.values()),
            "accounts": len(negative),
            "min_balance": round(min((a["min_balance"] for a in accounts.values()), default=0.0), 2),
        },
        "distinct_timestamps": len(dates - {""}),
    }
    channel_rows = sorted(
        (
            {"channel": name, "count": int(c), "amount": round(a, 2), "mean": round(a / c, 2) if c else 0.0}
            for name, (c, a) in channels.items()
        ),
        key=lambda r: -r["amount"],
    )
    return {"batch": batch, "channels": channel_rows, "accounts": accounts}


def account_drivers(dataset: Mapping, per_account: Iterable[Mapping]) -> Dict[str, List[Dict]]:
    """Each account's largest terms in the lightweight scorer's weighted sum, largest first."""
    per = {a["account_id_full"]: a for a in per_account}
    smurf = {k: SimpleNamespace(smurf_score=v.get("smurf_score", 0.0)) for k, v in per.items()}
    centrality = {
        k: {"betweenness": v.get("betweenness", 0.0), "pagerank": v.get("pagerank", 0.0)} for k, v in per.items()
    }
    baselines = {k: SimpleNamespace(composite_score=v.get("baseline_deviation", 0.0)) for k, v in per.items()}
    ids, matrix = extract_features(
        list(dataset.get("accounts", [])),
        list(dataset.get("transactions", [])),
        smurf_scores=smurf,
        centrality=centrality,
        baselines=baselines,
    )
    out: Dict[str, List[Dict]] = {}
    for acc_id, features in zip(ids, matrix):
        terms = []
        for name, weight, value in zip(FEATURE_NAMES, HEURISTIC_WEIGHTS, features):
            adjusted = 1.0 - value if name == "account_age" else value  # the scorer inverts age
            terms.append(
                {
                    "feature": FEATURE_KEYS.get(name, name),
                    "value": round(adjusted, 4),
                    "weight": weight,
                    "contribution": round(weight * adjusted, 4),
                }
            )
        terms.sort(key=lambda t: -t["contribution"])
        out[acc_id] = [t for t in terms[:DRIVERS_PER_ACCOUNT] if t["contribution"] > 0]
    return out


def suggested_step(classification: str, severity: Optional[str], lien: float) -> str:
    """A next step for the investigator to confirm or change; the ledger never acts on it."""
    if classification == "CLEAN":
        return "No action"
    if lien > 0:
        return "Keep lien; investigate"
    if classification == "COMPLICIT":
        return "Escalate; prepare STR for review" if severity == "CRITICAL" else "Escalate to supervisor"
    return "Customer outreach; step-up verification"


def build_ledger(
    summary: Mapping,
    dataset: Mapping,
    analysis: Mapping,
    source: Mapping,
    planted_ring: Optional[Iterable[str]] = None,
) -> Dict:
    """Join raw-row figures, engine output and drivers into the dashboard's payload."""
    per_account = list(analysis.get("per_account", []))
    drivers = account_drivers(dataset, per_account)
    clusters = sorted(analysis.get("clusters", []), key=lambda c: -c.get("risk_score", 0))
    ring_of: Dict[str, int] = {}
    severity_of: Dict[str, str] = {}
    for index, cluster in enumerate(clusters, start=1):
        for member in cluster.get("members", []):
            ring_of.setdefault(member, index)
            current = severity_of.get(member)
            if SEVERITY_ORDER.get(cluster.get("severity"), 0) > SEVERITY_ORDER.get(current, 0):
                severity_of[member] = cluster.get("severity")

    raw = summary.get("accounts", {})
    rows = []
    for acc in per_account:
        acc_id = acc["account_id_full"]
        stats = raw.get(acc_id, {})
        classification = acc.get("mule_classification", "CLEAN")
        rows.append(
            {
                "account_id": acc_id,
                "customer_age": stats.get("customer_age"),
                "opened": stats.get("opened"),
                "account_age_days": acc.get("account_age_days"),
                "rows": stats.get("rows", 0),
                "credit_count": stats.get("credit_count", 0),
                "credit_amount": stats.get("credit_amount", 0.0),
                "debit_count": stats.get("debit_count", 0),
                "debit_amount": stats.get("debit_amount", 0.0),
                "turnover": stats.get("turnover", 0.0),
                "share_of_batch": stats.get("share_of_batch", 0.0),
                "pass_through": stats.get("pass_through"),
                "min_balance": stats.get("min_balance"),
                "negative_rows": stats.get("negative_rows", 0),
                "lien": stats.get("lien", 0.0),
                "channels": stats.get("channels", []),
                "risk_score": acc.get("risk_score", 0.0),
                "classification": classification,
                "severity": severity_of.get(acc_id),
                "ring": ring_of.get(acc_id),
                "drivers": drivers.get(acc_id, []) if classification != "CLEAN" else [],
                "rule_hits": [hit.split(":")[0] for hit in acc.get("rule_hits", [])][:6],
                "suggested_step": suggested_step(classification, severity_of.get(acc_id), stats.get("lien", 0.0)),
            }
        )
    rows.sort(key=lambda r: (-r["risk_score"], -r["turnover"]))

    flagged = [r for r in rows if r["classification"] != "CLEAN"]
    counts = analysis.get("aggregate", {}).get("classification_counts", {})
    quality = analysis.get("aggregate", {}).get("data_quality", {}) or dataset.get("data_quality", {})
    genuine = None
    if planted_ring is not None:
        ring = set(planted_ring)
        genuine_rows = [r for r in rows if r["account_id"] not in ring]
        genuine = {
            "planted_ring": len(ring),
            "ring_flagged": sum(1 for r in rows if r["account_id"] in ring and r["classification"] != "CLEAN"),
            "genuine_accounts": len(genuine_rows),
            "genuine_flagged": sum(1 for r in genuine_rows if r["classification"] != "CLEAN"),
        }
    scores = [c.get("risk_score", 0.0) for c in clusters]
    return {
        "source": dict(source),
        "batch": dict(summary.get("batch", {})),
        "channels": list(summary.get("channels", [])),
        "engine": {
            "normalized_transactions": analysis.get("aggregate", {}).get("total_transactions", 0),
            "internal_links": analysis.get("aggregate", {}).get("internal_links", 0),
            "alerts": analysis.get("aggregate", {}).get("total_alerts", 0),
            "rings": [
                {
                    "ring": i,
                    "members": c.get("member_count", 0),
                    "risk_score": c.get("risk_score", 0.0),
                    "severity": c.get("severity"),
                    "amount": c.get("total_amount", 0.0),
                }
                for i, c in enumerate(clusters, start=1)
            ],
            "score_range": [min(scores), max(scores)] if scores else None,
            "flagged_accounts": len(flagged),
            "classification_counts": {
                "COMPLICIT": counts.get("COMPLICIT", 0),
                "EXPLOITED": counts.get("EXPLOITED", 0),
                "CLEAN": counts.get("CLEAN", 0),
            },
            "linkage_confidence": quality.get("linkage_confidence"),
            "warnings": list(quality.get("warnings", [])),
        },
        "genuine_check": genuine,
        "accounts": rows,
    }


def upload_source(filename: str, content: str) -> Dict:
    return {
        "kind": "upload",
        "filename": filename,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def sample_ledger(pipeline) -> Dict:
    """The synthetic sample extract, parsed and scored without touching the loaded dataset."""
    from data_adapters.mule_csv_adapter import MuleCSVAdapter
    from data_adapters.sample_cbs import FILENAME, build_sample_cbs
    from services.detection_service import alert_to_dict
    from services.upload_analysis import analyze_dataset

    content, ring = build_sample_cbs()
    parsed = MuleCSVAdapter().parse(content)
    dataset = {
        "transactions": parsed["transactions"],
        "accounts": parsed["accounts"],
        "data_quality": parsed.get("data_quality", {}),
    }
    alerts = [alert_to_dict(a) for a in pipeline.run(dataset["transactions"], dataset["accounts"])]
    source = {**upload_source(FILENAME, content), "kind": "sample", "synthetic": True}
    return build_ledger(summarize_cbs(content), dataset, analyze_dataset(dataset, alerts), source, planted_ring=ring)
