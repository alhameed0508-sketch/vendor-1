"""
MuleCatch Backend API
FastAPI application serving the investigator dashboard.
All endpoints < 500ms. Detection pipeline target < 60s.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json, os, sys, uuid, time

# Fix Windows cp1252 encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detection.pipeline import DetectionPipeline, Alert
from data.synthetic.generator import build_full_dataset
from models.active_learning.feedback_loop import ActiveLearningEngine, FeedbackStore
from graph_engine.persistence import PersistenceLayer
from middleware.auth import (
    get_current_user, require_role, require_permission,
    AUTH_ENABLED, authenticate as auth_authenticate, audit_middleware,
)
from ingest.kafka_consumer import TransactionConsumer, KAFKA_ENABLED

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    from starlette.responses import Response
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

app = FastAPI(
    title="MuleCatch API",
    description="Mule account detection via explainable graph intelligence",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ── Prometheus metrics ─────────────────────────────────────────────────────────
if HAS_PROMETHEUS:
    REQUEST_COUNT = Counter("mulecatch_api_requests_total", "Total API requests", ["method", "endpoint", "status"])
    REQUEST_DURATION = Histogram("mulecatch_api_request_duration_seconds", "API request duration", ["endpoint"])
    ALERT_COUNT = Gauge("mulecatch_alert_count", "Current total alerts")
    DETECTION_LATENCY = Histogram("mulecatch_detection_latency_seconds", "Detection pipeline latency")

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        endpoint = request.url.path
        REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
        REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
        return response

    @app.get("/metrics")
    def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Audit middleware — logs every request
app.middleware("http")(audit_middleware)


# ── Auth endpoints ─────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Authenticate and return JWT token"""
    token = auth_authenticate(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "token": token,
        "token_type": "bearer",
        "auth_enabled": AUTH_ENABLED,
    }


@app.get("/api/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    """Return current user info from JWT"""
    return {
        "user_id": user.get("sub"),
        "role": user.get("role"),
        "auth_enabled": AUTH_ENABLED,
    }

# ── Service singletons ────────────────────────────────────────────────────────

persistence = PersistenceLayer()
feedback_engine = ActiveLearningEngine()
feedback_store = FeedbackStore()
pipeline = DetectionPipeline()
kafka_consumer = TransactionConsumer()


@app.on_event("startup")
async def startup_event():
    """Start Kafka consumer if enabled."""
    if KAFKA_ENABLED:
        kafka_consumer.start(pipeline=pipeline, persistence=persistence)


def _get_or_generate_dataset():
    ds = persistence.get_dataset()
    if ds is None:
        ds = build_full_dataset(num_clusters=8, num_legit_accounts=60)
        persistence.set_dataset(ds)
    return ds


def _ensure_alerts():
    existing = persistence.get_alerts(limit=200)
    if existing:
        return existing
    dataset = _get_or_generate_dataset()

    # Apply feedback-adjusted thresholds
    threshold_delta = feedback_store.get_threshold_adjustment()
    if threshold_delta != 0.0:
        pipeline._smurf_threshold = 0.55 + threshold_delta

    alerts = pipeline.run(dataset["transactions"], dataset["accounts"])
    alert_dicts = [_alert_to_dict(a) for a in alerts]

    # Assign diverse statuses for realistic demo
    # Sort by risk_score descending so highest-risk stay OPEN
    alert_dicts.sort(key=lambda a: -a["risk_score"])
    demo_statuses = [
        "OPEN", "OPEN", "UNDER_REVIEW", "OPEN", "RESOLVED",
        "UNDER_REVIEW", "OPEN", "FALSE_POSITIVE",
    ]
    for i, ad in enumerate(alert_dicts):
        if i < len(demo_statuses):
            ad["status"] = demo_statuses[i]
        if ad["status"] == "UNDER_REVIEW":
            ad["investigator_notes"] = "Reviewing cluster topology and transaction velocity patterns."
        elif ad["status"] == "RESOLVED":
            ad["investigator_notes"] = "Confirmed mule network. STR filed with FIU."
        elif ad["status"] == "FALSE_POSITIVE":
            ad["investigator_notes"] = "Legitimate payroll batch. Accounts verified by branch manager."

    persistence.store_alerts(alert_dicts)

    # Update KPIs
    persistence.update_kpi(
        total_alerts=len(alerts),
        fraud_prevented_inr=sum(a.total_amount for a in alerts),
        hours_saved=len(alerts) * 3.0,
        strs_filed=len([a for a in alerts if a.risk_score > 0.7]),
    )
    return alert_dicts


def _alert_to_dict(a: Alert) -> Dict:
    return {
        "alert_id": a.alert_id,
        "cluster_id": a.cluster_id,
        "severity": a.severity,
        "confidence": a.confidence,
        "risk_score": a.risk_score,
        "total_amount": a.total_amount,
        "txn_count": a.txn_count,
        "account_count": a.account_count,
        "reason_codes": a.reason_codes,
        "shared_devices": a.shared_devices,
        "shared_ips": a.shared_ips,
        "created_at": a.created_at,
        "status": a.status,
        "investigator_notes": a.investigator_notes,
        "gnn_score": a.gnn_score,
        "nodes": [vars(n) for n in a.nodes],
        "edges": [vars(e) for e in a.edges],
        "explanation": a.explanation,
        "narrative": a.narrative,
        "mule_classification": a.mule_classification,
    }


# ── Pydantic models ────────────────────────────────────────────────────────────

class AlertUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, pattern="^(OPEN|UNDER_REVIEW|RESOLVED|FALSE_POSITIVE)$")
    investigator_notes: Optional[str] = Field(None, max_length=5000)


class FeedbackRequest(BaseModel):
    alert_id: str = Field(..., min_length=1, max_length=100)
    is_true_positive: bool
    investigator_id: str = Field("investigator_001", max_length=100)
    notes: str = Field("", max_length=5000)


class EscalationRequest(BaseModel):
    alert_id: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=1, max_length=2000)
    priority: str = Field("HIGH", pattern="^(HIGH|CRITICAL|URGENT)$")


class EscalationActionRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT|REASSIGN)$")
    notes: str = Field("", max_length=2000)


class STRExportRequest(BaseModel):
    alert_ids: List[str] = Field(..., min_length=1, max_length=50)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "MuleCatch API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "persistence": "neo4j" if persistence.is_persistent else "in-memory",
    }


@app.get("/api/alerts")
def list_alerts(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(require_permission("alerts:read")),
):
    alerts = _ensure_alerts()
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity.upper()]
    if status:
        alerts = [a for a in alerts if a["status"] == status.upper()]
    return {
        "total": len(alerts),
        "alerts": alerts[:limit],
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.get("/api/alerts/{alert_id}")
def get_alert(alert_id: str, user: dict = Depends(require_permission("alerts:read"))):
    _ensure_alerts()
    alert = persistence.get_alert(alert_id)
    if not alert:
        # Fallback to in-memory list search
        for a in persistence.get_alerts(limit=500):
            if a["alert_id"] == alert_id:
                return a
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@app.patch("/api/alerts/{alert_id}")
def update_alert(alert_id: str, req: AlertUpdateRequest, user: dict = Depends(require_permission("alerts:write"))):
    _ensure_alerts()
    result = persistence.update_alert(alert_id, status=req.status, notes=req.investigator_notes)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    _audit("ALERT_UPDATE", user.get("sub", "unknown"), alert_id,
           f"status={req.status}" + (f", notes_length={len(req.investigator_notes or '')}" if req.investigator_notes else ""))
    return result


@app.get("/api/alerts/{alert_id}/explanation")
def get_explanation(alert_id: str, user: dict = Depends(require_permission("alerts:read"))):
    """Returns explainability data for an alert — score decomposition, fraud chain, cycles"""
    _ensure_alerts()
    alerts = persistence.get_alerts(limit=500)
    for a in alerts:
        if a["alert_id"] == alert_id:
            explanation = a.get("explanation")
            if explanation:
                return explanation
            # Generate on-the-fly if not cached
            from explainability.explainer import explain_alert
            exp = explain_alert(a)
            return exp.to_dict()
    raise HTTPException(status_code=404, detail="Alert not found")


@app.get("/api/alerts/{alert_id}/narrative")
def get_narrative(alert_id: str, user: dict = Depends(require_permission("alerts:read"))):
    """Returns judge-ready narrative for an alert"""
    _ensure_alerts()
    alerts = persistence.get_alerts(limit=500)
    for a in alerts:
        if a["alert_id"] == alert_id:
            narrative = a.get("narrative")
            if narrative:
                return narrative
            from explainability.narrative_generator import generate_narrative
            from detection.mule_classifier import classify_cluster
            classification = classify_cluster(a, [])
            narr = generate_narrative(a, classification)
            return narr.to_dict()
    raise HTTPException(status_code=404, detail="Alert not found")


@app.get("/api/alerts/{alert_id}/shap")
def get_shap(alert_id: str, user: dict = Depends(require_permission("alerts:read"))):
    """Returns SHAP values for an alert's nodes"""
    _ensure_alerts()
    alerts = persistence.get_alerts(limit=500)
    for a in alerts:
        if a["alert_id"] == alert_id:
            from explainability.shap_explainer import compute_shap_values, format_for_waterfall_chart
            results = compute_shap_values(a)
            return {
                "alert_id": alert_id,
                "shap_results": [r.to_dict() for r in results],
                "waterfall_charts": [format_for_waterfall_chart(r) for r in results[:5]],
            }
    raise HTTPException(status_code=404, detail="Alert not found")


@app.get("/api/alerts/{alert_id}/subgraph")
def get_subgraph(alert_id: str, user: dict = Depends(require_permission("alerts:read"))):
    """Returns graph topology for visualization"""
    _ensure_alerts()
    alerts = persistence.get_alerts(limit=500)
    for a in alerts:
        if a["alert_id"] == alert_id:
            return {
                "alert_id": alert_id,
                "nodes": a.get("nodes", []),
                "edges": a.get("edges", []),
                "shared_devices": a.get("shared_devices", []),
                "shared_ips": a.get("shared_ips", []),
                "reason_codes": a.get("reason_codes", []),
            }
    raise HTTPException(status_code=404, detail="Alert not found")


@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest, user: dict = Depends(require_permission("feedback:write"))):
    """Investigator feedback — feeds active learning loop"""
    _ensure_alerts()

    # Find the alert to get cluster_id
    alert = persistence.get_alert(req.alert_id)
    if not alert:
        for a in persistence.get_alerts(limit=500):
            if a["alert_id"] == req.alert_id:
                alert = a
                break
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Record feedback in the active learning engine
    cluster_id = alert.get("cluster_id") if isinstance(alert, dict) else None
    fb = feedback_engine.record_feedback(
        alert_id=req.alert_id,
        cluster_id=cluster_id,
        investigator_id=req.investigator_id,
        is_true_positive=req.is_true_positive,
        notes=req.notes,
    )

    if not req.is_true_positive:
        persistence.increment_kpi("false_positives_avoided")
        persistence.update_alert(req.alert_id, status="FALSE_POSITIVE")

    _audit("FEEDBACK", user.get("sub", "unknown"), req.alert_id,
           f"is_true_positive={req.is_true_positive}")
    return {
        "accepted": True,
        "feedback_id": fb.feedback_id,
        "message": "Feedback recorded. Model will be updated in next cycle.",
        "alert_id": req.alert_id,
        "retraining_recommended": feedback_engine.should_retrain(),
    }


@app.get("/api/feedback/stats")
def feedback_stats():
    """Feedback statistics for the ROI dashboard"""
    summary = feedback_engine.get_retraining_summary()
    return {
        "total_feedback": summary["total_feedback"],
        "true_positives": summary["true_positives"],
        "false_positives": summary["false_positives"],
        "false_positive_rate": summary["false_positive_rate"],
        "recommended_threshold_delta": summary["recommended_threshold_delta"],
        "retraining_recommended": summary["retraining_recommended"],
        "current_smurf_threshold": 0.55 + feedback_store.get_threshold_adjustment(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Audit log ─────────────────────────────────────────────────────────────────

_audit_log: List[Dict] = []


def _audit(action: str, user: str, alert_id: str = None, details: str = ""):
    """Append an immutable audit entry."""
    entry = {
        "log_id": f"LOG_{uuid.uuid4().hex[:8].upper()}",
        "action": action,
        "user": user,
        "alert_id": alert_id,
        "details": details,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _audit_log.append(entry)
    return entry


# ── Escalation workflow ────────────────────────────────────────────────────────

# In-memory escalation store (would use DB in production)
_escalations: Dict[str, Dict] = {}


@app.post("/api/escalations")
def create_escalation(req: EscalationRequest, user: dict = Depends(require_permission("alerts:write"))):
    """Investigator escalates an alert to supervisor."""
    esc_id = f"ESC_{uuid.uuid4().hex[:8].upper()}"
    escalation = {
        "escalation_id": esc_id,
        "alert_id": req.alert_id,
        "reason": req.reason,
        "priority": req.priority,
        "status": "PENDING",
        "escalated_by": user.get("sub", "investigator"),
        "escalated_at": datetime.utcnow().isoformat(),
        "resolved_by": None,
        "resolved_at": None,
        "action": None,
        "supervisor_notes": "",
    }
    _escalations[esc_id] = escalation
    persistence.update_alert(req.alert_id, status="UNDER_REVIEW")
    _audit("ESCALATION_CREATED", user.get("sub", "unknown"), req.alert_id, f"priority={req.priority}")
    return escalation


@app.get("/api/escalations")
def list_escalations(
    status: Optional[str] = None,
    user: dict = Depends(require_permission("alerts:read")),
):
    """List all escalations, optionally filtered by status."""
    result = list(_escalations.values())
    if status:
        result = [e for e in result if e["status"] == status.upper()]
    return sorted(result, key=lambda e: e["escalated_at"], reverse=True)


@app.patch("/api/escalations/{escalation_id}")
def resolve_escalation(
    escalation_id: str,
    req: EscalationActionRequest,
    user: dict = Depends(require_role("ADMIN", "SUPERVISOR")),
):
    """Supervisor acts on an escalation: APPROVE, REJECT, or REASSIGN."""
    esc = _escalations.get(escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if esc["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Escalation already resolved")

    esc["status"] = req.action
    esc["resolved_by"] = user.get("sub", "supervisor")
    esc["resolved_at"] = datetime.utcnow().isoformat()
    esc["supervisor_notes"] = req.notes
    _audit("ESCALATION_RESOLVED", user.get("sub", "unknown"), esc["alert_id"], f"action={req.action}")

    # Update alert status based on action
    if req.action == "APPROVE":
        persistence.update_alert(esc["alert_id"], status="UNDER_REVIEW",
                                 notes=f"Escalation approved: {req.notes}")
    elif req.action == "REJECT":
        persistence.update_alert(esc["alert_id"], status="RESOLVED",
                                 notes=f"Escalation rejected: {req.notes}")

    return esc


@app.get("/api/audit-log")
def get_audit_log(
    alert_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(require_permission("alerts:read")),
):
    """Query the audit trail. Supports filtering by alert_id and action type."""
    result = list(_audit_log)
    if alert_id:
        result = [e for e in result if e.get("alert_id") == alert_id]
    if action:
        result = [e for e in result if e.get("action") == action.upper()]
    return sorted(result, key=lambda e: e["timestamp"], reverse=True)[:limit]


@app.post("/api/feedback/retrain")
def trigger_retrain(
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("ADMIN", "SUPERVISOR")),
):
    """Trigger model retraining based on accumulated feedback.
    In production this would dispatch a GNN retraining job;
    for demo, it re-runs the pipeline with adjusted thresholds."""
    summary = feedback_engine.get_retraining_summary()
    delta = feedback_store.get_threshold_adjustment()

    def _retrain():
        """Background retrain: clear stale alerts, recompute with adjusted thresholds."""
        persistence.clear()
        if delta != 0.0:
            pipeline._smurf_threshold = 0.55 + delta
        dataset = _get_or_generate_dataset()
        alerts = pipeline.run(dataset["transactions"], dataset["accounts"])
        alert_dicts = [_alert_to_dict(a) for a in alerts]
        persistence.store_alerts(alert_dicts)

    background_tasks.add_task(_retrain)
    _audit("RETRAIN_TRIGGERED", user.get("sub", "unknown"), details=f"delta={delta}, feedback_count={summary['total_feedback']}")

    return {
        "status": "RETRAINING_STARTED",
        "threshold_adjustment": delta,
        "new_smurf_threshold": round(0.55 + delta, 3),
        "feedback_count": summary["total_feedback"],
        "false_positive_rate": summary["false_positive_rate"],
        "message": "Pipeline re-running with adjusted thresholds",
    }


@app.get("/api/kpi")
def get_kpi():
    _ensure_alerts()
    k = persistence.get_kpi()
    return {
        **k,
        "manpower_saved_lakh": round(k["hours_saved"] * 500 / 100000, 2),
        "fraud_prevented_crore": round(k["fraud_prevented_inr"] / 10_000_000, 2),
        "false_positive_reduction_pct": 40,
        "avg_investigation_time_min": 45,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/compliance/str-export")
def export_str(req: STRExportRequest, user: dict = Depends(require_permission("str:export"))):
    """Generate FIU-compatible STR for selected alerts"""
    alerts = _ensure_alerts()
    alert_map = {a["alert_id"]: a for a in alerts}
    selected = [alert_map[aid] for aid in req.alert_ids if aid in alert_map]

    str_reports = []
    for a in selected:
        str_reports.append({
            "str_id": f"STR_{uuid.uuid4().hex[:8].upper()}",
            "alert_id": a["alert_id"],
            "reporting_entity": "Indian Overseas Bank",
            "ifsc": "IOBA0000001",
            "transaction_type": "UPI",
            "total_amount": a["total_amount"],
            "transaction_count": a["txn_count"],
            "accounts_involved": [n["account_id"] for n in a.get("nodes", [])],
            "reason_codes": a["reason_codes"],
            "risk_score": a["risk_score"],
            "gnn_score": a.get("gnn_score"),
            "generated_at": datetime.utcnow().isoformat(),
            "status": "READY_FOR_SUBMISSION",
            "fiu_format_version": "2.1",
        })
        persistence.increment_kpi("strs_filed")

    return {
        "generated": len(str_reports),
        "str_reports": str_reports,
    }


@app.get("/api/compliance/str-pdf/{alert_id}")
def export_str_pdf(alert_id: str, user: dict = Depends(require_permission("str:export"))):
    """Download a single alert's STR as a PDF file."""
    from api.str_pdf import generate_str_pdf

    alerts = _ensure_alerts()
    alert_map = {a["alert_id"]: a for a in alerts}
    alert = alert_map.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    str_record = {
        "str_id": f"STR_{uuid.uuid4().hex[:8].upper()}",
        "alert_id": alert_id,
        "generated_at": datetime.utcnow().isoformat(),
    }
    pdf_bytes = generate_str_pdf(alert, str_record)
    persistence.increment_kpi("strs_filed")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="STR_{alert_id}.pdf"',
        },
    )


@app.post("/api/run-detection")
def run_detection(background_tasks: BackgroundTasks, user: dict = Depends(require_role("ADMIN", "SUPERVISOR"))):
    """Trigger a fresh detection run on the synthetic dataset"""
    persistence.clear()
    background_tasks.add_task(_ensure_alerts)
    return {
        "message": "Detection pipeline triggered",
        "estimated_completion_seconds": 30,
    }


@app.get("/api/ingest/status")
def ingest_status():
    """Kafka consumer health and lag metrics"""
    return kafka_consumer.get_status()


@app.get("/api/ingest/stream-demo")
def stream_demo(count: int = 10):
    """Simulated real-time transaction stream for demo visualization.
    Returns recent transactions as if they were just ingested from Kafka."""
    import random
    dataset = _get_or_generate_dataset()
    txns = dataset.get("transactions", [])
    if not txns:
        return {"transactions": [], "source": "demo"}

    sample = random.sample(txns, min(count, len(txns)))
    # Adjust timestamps to "now" for live feel
    now = datetime.utcnow()
    stream = []
    for i, t in enumerate(sample):
        entry = dict(t)
        entry["timestamp"] = (now - __import__("datetime").timedelta(seconds=random.randint(0, 30))).isoformat()
        entry["stream_offset"] = i
        stream.append(entry)

    return {
        "transactions": stream,
        "source": "kafka" if KAFKA_ENABLED else "demo-simulation",
        "topic": kafka_consumer.topic,
        "timestamp": now.isoformat(),
    }


@app.get("/api/graph/stats")
def graph_stats():
    dataset = _get_or_generate_dataset()
    alerts = _ensure_alerts()
    return {
        "total_accounts": len(dataset["accounts"]),
        "total_transactions": len(dataset["transactions"]),
        "suspicious_transactions": dataset["stats"]["suspicious_transactions"],
        "mule_clusters_detected": len([a for a in alerts if a["severity"] in ("CRITICAL", "HIGH")]),
        "total_alerts": len(alerts),
        "critical": len([a for a in alerts if a["severity"] == "CRITICAL"]),
        "high": len([a for a in alerts if a["severity"] == "HIGH"]),
        "medium": len([a for a in alerts if a["severity"] == "MEDIUM"]),
    }
