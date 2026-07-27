"""
CSV Upload routes — /api/v1/csv-upload/*

Handles upload and processing of pipe-delimited CBS mule account data.
"""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, Request, UploadFile, File
from slowapi import Limiter

from core.response import success_response, error_response
from middleware.auth import require_permission
from api.deps import get_detection_service, get_dataset_repo, get_alert_repo
from data_adapters.mule_csv_adapter import MuleCSVAdapter
from services.detection_service import DetectionService
from repositories.dataset_repository import DatasetRepository
from repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def register_csv_upload_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register CSV upload routes on the given router."""

    @r.post("/upload")
    @limiter.limit("5/minute")
    def upload_csv(
        request: Request,
        file: UploadFile = File(...),
        user: dict = Depends(require_permission("alerts:write")),
        detection_svc: DetectionService = Depends(get_detection_service),
        dataset_repo: DatasetRepository = Depends(get_dataset_repo),
    ):
        """Upload and process a pipe-delimited CBS CSV file.

        Parses the CSV, loads into the dataset repository, clears existing
        alerts, and triggers the detection pipeline.
        """
        if not file.filename or not file.filename.lower().endswith(".csv"):
            return error_response(
                code="INVALID_FILE",
                message="Only .csv files are accepted",
                status_code=400,
            )

        content_bytes = file.file.read(MAX_FILE_SIZE + 1)
        if len(content_bytes) > MAX_FILE_SIZE:
            return error_response(
                code="FILE_TOO_LARGE",
                message=f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit",
                status_code=400,
            )

        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return error_response(
                code="ENCODING_ERROR",
                message="File must be UTF-8 encoded",
                status_code=400,
            )

        # Parse CSV through adapter
        adapter = MuleCSVAdapter()
        try:
            parsed = adapter.parse(content)
        except Exception as exc:
            logger.exception("CSV parse failed: %s", exc)
            return error_response(
                code="PARSE_ERROR",
                message=f"Failed to parse CSV: {str(exc)}",
                status_code=400,
            )

        transactions = parsed["transactions"]
        accounts = parsed["accounts"]
        anomaly_flags = parsed.get("anomaly_flags", [])
        data_quality = parsed.get("data_quality", {})

        if not transactions:
            return error_response(
                code="EMPTY_DATA",
                message="No transactions found in the uploaded file",
                status_code=400,
            )

        # Clear existing data + alerts, then store parsed dataset
        dataset = {
            "transactions": transactions,
            "accounts": accounts,
            "data_quality": data_quality,
        }
        dataset_repo.clear()
        dataset_repo.set(dataset)

        # Run detection pipeline — skip demo statuses for real uploaded data
        alerts = detection_svc.ensure_alerts(skip_demo_statuses=True)

        # Build channel breakdown
        channels: dict = {}
        for txn in transactions:
            ch = txn.get("channel", "UNKNOWN")
            channels[ch] = channels.get(ch, 0) + 1

        # Build preview rows (first 50 transactions)
        preview_rows = transactions[:50]

        # Compute date range
        timestamps = [t["timestamp"] for t in transactions if t.get("timestamp")]
        date_range = {
            "earliest": min(timestamps) if timestamps else None,
            "latest": max(timestamps) if timestamps else None,
        }

        # Count internal vs external links
        account_ids = {a["account_id"] for a in accounts}
        internal_txns = sum(
            1
            for t in transactions
            if t["from_account"] in account_ids and t["to_account"] in account_ids
        )

        logger.info(
            "CSV upload processed: %d transactions (%d internal links), "
            "%d accounts, %d alerts",
            len(transactions),
            internal_txns,
            len(accounts),
            len(alerts),
        )

        return success_response(
            {
                "accounts": len(accounts),
                "transactions": len(transactions),
                "internal_links": internal_txns,
                "alerts_generated": len(alerts),
                "anomaly_flags": anomaly_flags,
                "data_quality": data_quality,
                "channels": channels,
                "date_range": date_range,
                "preview_rows": preview_rows,
                "account_summaries": accounts[:50],
            }
        )

    @r.get("/preview")
    @limiter.limit("30/minute")
    def preview_data(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        dataset_repo: DatasetRepository = Depends(get_dataset_repo),
        alert_repo: AlertRepository = Depends(get_alert_repo),
    ):
        """Get current uploaded data summary and detection results."""
        dataset = dataset_repo.get()
        if dataset is None:
            return success_response(
                {
                    "loaded": False,
                    "message": "No data has been uploaded yet",
                }
            )

        transactions = dataset.get("transactions", [])
        accounts = dataset.get("accounts", [])
        alerts = alert_repo.find_all(limit=200)

        # Severity breakdown
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for alert in alerts:
            sev = alert.get("severity", "MEDIUM")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        channels: dict = {}
        for txn in transactions:
            ch = txn.get("channel", "UNKNOWN")
            channels[ch] = channels.get(ch, 0) + 1

        return success_response(
            {
                "loaded": True,
                "accounts": len(accounts),
                "transactions": len(transactions),
                "alerts": len(alerts),
                "severity_counts": severity_counts,
                "channels": channels,
                "account_summaries": accounts[:50],
                "data_quality": dataset.get("data_quality", {}),
            }
        )

    @r.post("/analyze")
    @limiter.limit("10/minute")
    def analyze_data(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        dataset_repo: DatasetRepository = Depends(get_dataset_repo),
        alert_repo: AlertRepository = Depends(get_alert_repo),
    ):
        """Run analysis on uploaded data and return per-account mule risk breakdown.

        Returns:
            - per_account: risk score, mule classification, rule hits, CBS features
            - aggregate: total mule candidates, severity breakdown, feature importance
            - clusters: account groupings from community detection
        """
        dataset = dataset_repo.get()
        if dataset is None:
            return error_response(
                code="NO_DATA",
                message="No data uploaded. Upload a CSV first.",
                status_code=400,
            )

        transactions = dataset.get("transactions", [])
        accounts = dataset.get("accounts", [])
        alerts = alert_repo.find_all(limit=200)

        if not alerts:
            return error_response(
                code="NO_ALERTS",
                message="No detection results available. Upload and process a CSV first.",
                status_code=400,
            )

        # Build account lookup
        acc_map = {a["account_id"]: a for a in accounts}
        account_ids = set(acc_map.keys())

        # Map accounts to their alert memberships and classifications
        account_alerts: dict = defaultdict(list)
        for alert in alerts:
            for node in alert.get("nodes", []):
                acc_id = node.get("account_id", "")
                if acc_id in account_ids:
                    account_alerts[acc_id].append(alert)

        # Build per-account analysis
        per_account = []
        for acc in accounts:
            acc_id = acc["account_id"]
            related_alerts = account_alerts.get(acc_id, [])

            # Aggregate risk from all alerts this account appears in
            max_risk = 0.0
            all_reason_codes: list = []
            mule_classification = "CLEAN"
            smurf_score = 0.0
            node_data = {}

            for alert in related_alerts:
                max_risk = max(max_risk, alert.get("risk_score", 0))
                all_reason_codes.extend(alert.get("reason_codes", []))

                # Get node-level data for this account
                for node in alert.get("nodes", []):
                    if node.get("account_id") == acc_id:
                        smurf_score = max(smurf_score, node.get("smurf_score", 0))
                        node_data = node
                        break

                # Get mule classification from alert
                mc = alert.get("mule_classification", {})
                if mc:
                    for member in mc.get("account_classifications", []):
                        if member.get("account_id") == acc_id:
                            role = member.get("classification", "UNKNOWN")
                            if role in ("COMPLICIT_MULE", "COMPLICIT"):
                                mule_classification = "COMPLICIT"
                            elif (
                                role in ("EXPLOITED_MULE", "EXPLOITED")
                                and mule_classification != "COMPLICIT"
                            ):
                                mule_classification = "EXPLOITED"
                            elif role == "UNKNOWN" and mule_classification == "CLEAN":
                                mule_classification = "EXPLOITED"
                            break

            # Deduplicate reason codes
            unique_reasons = list(dict.fromkeys(all_reason_codes))

            per_account.append(
                {
                    "account_id": acc_id[:12] + "..." if len(acc_id) > 12 else acc_id,
                    "account_id_full": acc_id,
                    "risk_score": round(max_risk, 3),
                    "mule_classification": mule_classification,
                    "smurf_score": round(smurf_score, 3),
                    "rule_hits": unique_reasons[:10],
                    "alert_count": len(related_alerts),
                    # CBS features
                    "account_age_days": acc.get("account_age_days", 0),
                    "debit_count": acc.get("debit_count", 0),
                    "credit_count": acc.get("credit_count", 0),
                    "debit_volume": acc.get("debit_volume", 0),
                    "credit_volume": acc.get("credit_volume", 0),
                    "pass_through_ratio": acc.get("pass_through_ratio", 0),
                    "balance_volatility": acc.get("balance_volatility", 0),
                    "negative_balance_count": acc.get("negative_balance_count", 0),
                    "debit_credit_ratio": acc.get("debit_credit_ratio", 0),
                    "max_single_txn_ratio": acc.get("max_single_txn_ratio", 0),
                    # Node-level scores if available
                    "betweenness": node_data.get("betweenness", 0),
                    "pagerank": node_data.get("pagerank", 0),
                    "baseline_deviation": node_data.get("baseline_deviation", 0),
                }
            )

        # Sort by risk score descending
        per_account.sort(key=lambda x: -x["risk_score"])

        # Aggregate statistics
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for alert in alerts:
            sev = alert.get("severity", "MEDIUM")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        classification_counts = {"COMPLICIT": 0, "EXPLOITED": 0, "CLEAN": 0}
        for pa in per_account:
            mc = pa["mule_classification"]
            classification_counts[mc] = classification_counts.get(mc, 0) + 1

        # Feature importance: count how often each reason code appears
        reason_counts: dict = defaultdict(int)
        for alert in alerts:
            for code in alert.get("reason_codes", []):
                reason_counts[code] += 1
        feature_importance = sorted(
            [{"signal": k, "count": v} for k, v in reason_counts.items()],
            key=lambda x: -x["count"],
        )

        # Cluster membership
        clusters = []
        for alert in alerts:
            cluster_members = [
                n.get("account_id", "")
                for n in alert.get("nodes", [])
                if n.get("account_id", "") in account_ids
            ]
            if cluster_members:
                clusters.append(
                    {
                        "alert_id": alert.get("alert_id", ""),
                        "severity": alert.get("severity", ""),
                        "risk_score": alert.get("risk_score", 0),
                        "members": cluster_members,
                        "member_count": len(cluster_members),
                        "total_amount": alert.get("total_amount", 0),
                    }
                )

        # Internal link stats
        internal_txns = sum(
            1
            for t in transactions
            if t["from_account"] in account_ids and t["to_account"] in account_ids
        )

        return success_response(
            {
                "per_account": per_account,
                "aggregate": {
                    "total_accounts": len(accounts),
                    "total_transactions": len(transactions),
                    "internal_links": internal_txns,
                    "total_alerts": len(alerts),
                    "mule_candidates": classification_counts["COMPLICIT"]
                    + classification_counts["EXPLOITED"],
                    "severity_counts": severity_counts,
                    "classification_counts": classification_counts,
                    "feature_importance": feature_importance[:15],
                    "data_quality": dataset.get("data_quality", {}),
                },
                "clusters": clusters,
            }
        )
