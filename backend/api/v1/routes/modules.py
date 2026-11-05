"""
Module registry and Command Center routes — /api/v1/modules, /api/v1/command-center
"""

import re
from collections import Counter
from typing import Dict, List

from api.deps import get_alert_service, get_detection_service, get_escalation_service, get_live_buffer
from core.exceptions import NotFoundError
from core.response import success_response
from fastapi import APIRouter, Depends, Query, Request
from fraud_modules.registry import MODULES, get_module, module_dict
from fraud_modules.rule_modules import RULE_MODULES
from middleware.auth import require_permission
from services.alert_service import AlertService
from services.detection_service import DetectionService
from services.escalation_service import EscalationService
from slowapi import Limiter

router = APIRouter(tags=["modules"])

ALERT_LIMIT = 100_000
# The mule pipeline produces alerts; rule modules run their share of the rules on the loaded dataset.
# Any other module (Loan) has no findings source and reports None.


def _alert_summary(alerts: list) -> Dict:
    return {
        "total": len(alerts),
        "by_severity": dict(Counter(a["severity"] for a in alerts)),
        "by_status": dict(Counter(a["status"] for a in alerts)),
    }


def _module_summary(spec, alert_total: int, dataset: Dict) -> Dict:
    base = {k: module_dict(spec)[k] for k in ("module_id", "name", "status", "workspace_path")}
    if spec.module_id == "mule":
        return {**base, "findings": alert_total}
    rule_module = RULE_MODULES.get(spec.module_id)
    if rule_module is None:
        return {**base, "findings": None}
    run = rule_module.run(dataset.get("accounts", []), dataset.get("transactions", []))
    skipped = [{"rule_code": s.rule_code, "reason": s.reason} for s in run.signals_skipped]
    return {**base, "findings": len(run.findings), "skipped_signals": skipped}


TOP_ROWS = 50


def _rule_label(explanation: str) -> str:
    """'R14: Rapid round-trip (12 payments)' -> 'Rapid round-trip'; 'CF01: Circular fund flow: A -> B' -> 'Circular fund flow'."""
    text = explanation.split(":", 1)[1] if ":" in explanation else explanation
    return re.split(r"[:(]| - ", text)[0].strip(" .") or explanation


def _module_findings(spec, alerts: list, dataset: Dict) -> Dict:
    """What one module has found in the loaded dataset, shaped for its workspace and its card."""
    if spec.module_id == "mule":
        ranked = sorted(alerts, key=lambda a: -float(a.get("risk_score") or 0))
        return {
            "kind": "alerts",
            "findings_total": len(alerts),
            "accounts_in_alerts": sum(int(a.get("account_count") or 0) for a in alerts),
            "alerts": _alert_summary(alerts),
            "top_alerts": [
                {k: a.get(k) for k in ("alert_id", "severity", "status", "risk_score", "account_count", "total_amount")}
                | {"reasons": [str(r).split(":")[0] for r in (a.get("reason_codes") or [])][:4]}
                for a in ranked[:TOP_ROWS]
            ],
        }
    rule_module = RULE_MODULES.get(spec.module_id)
    if rule_module is None:
        return {"kind": "none", "findings_total": None}
    return _rule_findings(rule_module.run(dataset.get("accounts", []), dataset.get("transactions", [])))


def _rule_findings(run) -> Dict:
    by_rule: Dict[str, Dict] = {}
    for f in run.findings:
        row = by_rule.setdefault(
            f.rule_code,
            {"rule_code": f.rule_code, "label": _rule_label(f.explanation), "findings": 0, "accounts": set()},
        )
        row["findings"] += 1
        row["accounts"].add(f.account_id)
    return {
        "kind": "rules",
        "findings_total": len(run.findings),
        "accounts_flagged": len({f.account_id for f in run.findings}),
        "rows_considered": run.rows_considered,
        "signals_run": list(run.signals_run),
        "signals_skipped": [{"rule_code": s.rule_code, "reason": s.reason} for s in run.signals_skipped],
        "by_rule": sorted(
            ({**row, "accounts": len(row["accounts"])} for row in by_rule.values()), key=lambda r: -r["findings"]
        ),
        "findings": [
            {"account_id": f.account_id, "rule_code": f.rule_code, "explanation": f.explanation, "score": f.score}
            for f in run.findings[:TOP_ROWS]
        ],
    }


def _live_findings(spec, events: List[Dict]) -> Dict:
    """What one module finds in the recent real public payments (no synthetic data, no labels).

    The mule module reports the payments the live network scorer held, by reason; rule modules run
    their rules on the same payments. Payments carry no device, UPI or account-age data, so the rules
    that need those report themselves as skipped.
    """
    payments = [e["payment"] for e in events]
    base = {"live_payments": len(payments)}
    if spec.module_id == "mule":
        held = [e for e in events if e.get("decision") == "FLAG"]
        by_rule: Dict[str, Dict] = {}
        rows = []
        for e in held:
            members = e.get("ring_members") or [e["payment"]["from_account"]]
            for reason in e.get("reasons") or ["Held by the network scorer"]:
                code = str(reason).split(":", 1)[0].strip()
                row = by_rule.setdefault(
                    code, {"rule_code": code, "label": _rule_label(str(reason)), "findings": 0, "accounts": set()}
                )
                row["findings"] += 1
                row["accounts"].update(members)
            first = (e.get("reasons") or ["Held by the network scorer"])[0]
            rows.append(
                {
                    "account_id": e["payment"]["from_account"],
                    "rule_code": str(first).split(":", 1)[0],
                    "explanation": str(first),
                    "score": None,
                }
            )
        return {
            **base,
            "kind": "rules",
            "findings_total": len(held),
            "accounts_flagged": len(
                {m for e in held for m in (e.get("ring_members") or [e["payment"]["from_account"]])}
            ),
            "rows_considered": len(payments),
            "cases": len({e.get("case_id") for e in held if e.get("case_id")}),
            "signals_run": [],
            "signals_skipped": [],
            "by_rule": sorted(
                ({**r, "accounts": len(r["accounts"])} for r in by_rule.values()), key=lambda r: -r["findings"]
            ),
            "findings": rows[-TOP_ROWS:][::-1],
        }
    rule_module = RULE_MODULES.get(spec.module_id)
    if rule_module is None:
        return {**base, "kind": "none", "findings_total": None}
    accounts = [
        {"account_id": a} for a in dict.fromkeys(x for p in payments for x in (p["from_account"], p["to_account"]))
    ]
    return {**base, **_rule_findings(rule_module.run(accounts, payments))}


def register_module_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register module registry and Command Center routes on the given router."""

    @r.get("/modules")
    @limiter.limit("100/minute")
    def list_modules(request: Request, user: dict = Depends(require_permission("alerts:read"))):
        return success_response({"modules": [module_dict(m) for m in MODULES]})

    @r.get("/modules/{module_id}")
    @limiter.limit("100/minute")
    def get_module_detail(
        request: Request,
        module_id: str,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        try:
            return success_response(module_dict(get_module(module_id)))
        except KeyError:
            raise NotFoundError("Module", module_id) from None

    @r.get("/modules/{module_id}/findings")
    @limiter.limit("100/minute")
    def get_module_findings(
        request: Request,
        module_id: str,
        source: str = Query("dataset", pattern="^(dataset|live)$"),
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        """What this module has found: in the loaded dataset (default), or in the recent real public
        payments the live views have streamed (source=live). Counts, a breakdown by rule and the top rows."""
        try:
            spec = get_module(module_id)
        except KeyError:
            raise NotFoundError("Module", module_id) from None
        if source == "live":
            data = _live_findings(spec, get_live_buffer().snapshot())
            return success_response(
                {"module_id": module_id, "status": spec.status.value, "data_source": "live", **data}
            )
        detection_svc.ensure_alerts()
        alerts = alert_svc.list_alerts(limit=ALERT_LIMIT)["alerts"] if module_id == "mule" else []
        data = _module_findings(spec, alerts, detection_svc.get_or_generate_dataset())
        return success_response(
            {"module_id": module_id, "status": spec.status.value, "data_source": detection_svc.data_source(), **data}
        )

    @r.get("/command-center")
    @limiter.limit("100/minute")
    def command_center(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
        escalation_svc: EscalationService = Depends(get_escalation_service),
    ):
        detection_svc.ensure_alerts()
        alerts = alert_svc.list_alerts(limit=ALERT_LIMIT)["alerts"]
        summary = _alert_summary(alerts)
        dataset = detection_svc.get_or_generate_dataset()
        modules = [_module_summary(m, summary["total"], dataset) for m in MODULES]
        return success_response(
            {
                "data_source": detection_svc.data_source(),
                "alerts": summary,
                "escalations": {"pending": len(escalation_svc.list_all(status="PENDING"))},
                "modules": modules,
            }
        )
