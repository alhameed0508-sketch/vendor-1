"""
CSV Upload routes — /api/v1/csv-upload/*

Handles upload and processing of pipe-delimited CBS mule account data.
"""

import logging
import threading

from api.deps import get_alert_repo, get_dataset_repo, get_detection_service, get_pipeline
from core.response import error_response, success_response
from data_adapters.mule_csv_adapter import MuleCSVAdapter
from fastapi import APIRouter, Depends, File, Request, UploadFile
from middleware.auth import require_permission
from repositories.alert_repository import AlertRepository
from repositories.dataset_repository import DatasetRepository
from services.cbs_ledger import build_ledger, sample_ledger, summarize_cbs, upload_source
from services.detection_service import DetectionService
from services.upload_analysis import analyze_dataset
from slowapi import Limiter

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_sample_lock = threading.Lock()
_sample_cache: dict = {}


def _sample_ledger() -> dict:
    """Score the synthetic sample once per process, on its own pipeline instance."""
    with _sample_lock:
        if "ledger" not in _sample_cache:
            _sample_cache["ledger"] = sample_ledger(get_pipeline.__wrapped__())
        return _sample_cache["ledger"]


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
            # Raw-row figures for the Assessment ledger, read before debit/credit legs are paired
            "cbs_summary": summarize_cbs(content),
            "source": upload_source(file.filename, content),
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
            1 for t in transactions if t["from_account"] in account_ids and t["to_account"] in account_ids
        )

        logger.info(
            "CSV upload processed: %d transactions (%d internal links), %d accounts, %d alerts",
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

        alerts = alert_repo.find_all(limit=200)

        if not alerts:
            return error_response(
                code="NO_ALERTS",
                message="No detection results available. Upload and process a CSV first.",
                status_code=400,
            )

        return success_response(analyze_dataset(dataset, alerts))

    @r.get("/ledger")
    @limiter.limit("30/minute")
    def assessment_ledger(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        dataset_repo: DatasetRepository = Depends(get_dataset_repo),
        alert_repo: AlertRepository = Depends(get_alert_repo),
    ):
        """The Assessment ledger for the CBS file currently loaded.

        Raw-row figures, engine score / classification / ring and the three leading scorer
        drivers per account. With no CBS upload loaded, the synthetic sample extract.
        """
        dataset = dataset_repo.get()
        if not dataset or "cbs_summary" not in dataset:
            return success_response(_sample_ledger())
        analysis = analyze_dataset(dataset, alert_repo.find_all(limit=200))
        return success_response(build_ledger(dataset["cbs_summary"], dataset, analysis, dataset.get("source", {})))
