"""
Compliance service — STR generation and PDF export.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List

from core.config import get_settings
from repositories.alert_repository import AlertRepository
from repositories.kpi_repository import KPIRepository


class ComplianceService:
    """Business logic for STR generation and compliance exports."""

    def __init__(
        self,
        alert_repo: AlertRepository,
        kpi_repo: KPIRepository,
    ):
        self._alert_repo = alert_repo
        self._kpi_repo = kpi_repo

    def export_str(self, alert_ids: List[str], alerts: List[Dict]) -> Dict:
        """Generate FIU-compatible STR reports for selected alerts."""
        settings = get_settings()
        alert_map = {a["alert_id"]: a for a in alerts}
        selected = [alert_map[aid] for aid in alert_ids if aid in alert_map]

        str_reports = []
        for a in selected:
            str_reports.append(
                {
                    "str_id": f"STR_{uuid.uuid4().hex[:8].upper()}",
                    "alert_id": a["alert_id"],
                    "reporting_entity": settings.reporting_entity,
                    "ifsc": settings.reporting_ifsc,
                    "transaction_type": "UPI",
                    "total_amount": a["total_amount"],
                    "transaction_count": a["txn_count"],
                    "accounts_involved": [n["account_id"] for n in a.get("nodes", [])],
                    "reason_codes": a["reason_codes"],
                    "risk_score": a["risk_score"],
                    "gnn_score": a.get("gnn_score"),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "status": "READY_FOR_SUBMISSION",
                    "fiu_format_version": settings.fiu_format_version,
                }
            )
            self._kpi_repo.increment("strs_filed")

        return {
            "generated": len(str_reports),
            "str_reports": str_reports,
        }

    def generate_pdf(self, alert_id: str, alerts: List[Dict]) -> bytes:
        """Generate a PDF STR for a single alert. Returns PDF bytes."""
        from api.str_pdf import generate_str_pdf

        alert_map = {a["alert_id"]: a for a in alerts}
        alert = alert_map.get(alert_id)
        if not alert:
            from core.exceptions import NotFoundError

            raise NotFoundError("Alert", alert_id)

        str_record = {
            "str_id": f"STR_{uuid.uuid4().hex[:8].upper()}",
            "alert_id": alert_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        pdf_bytes = generate_str_pdf(alert, str_record)
        self._kpi_repo.increment("strs_filed")
        return pdf_bytes
