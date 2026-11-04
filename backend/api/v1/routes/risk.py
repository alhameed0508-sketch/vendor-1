"""Unified risk engine: /api/v1/risk (docs/API_RISK_ENGINE.md).

The mule-detection core stays the centre: its ring map is one of the four engines, and its alert queue
and complaint register feed the others. Nothing here blocks a payment; REVIEW holds it for a human.
"""

import json
import time
from pathlib import Path

from api.deps import get_audit_service, get_risk_demo_traffic, get_risk_engine, get_threat_feeds
from api.v1.schemas.risk import RiskEventRequest, RiskFeedbackRequest
from core.config import get_settings
from core.exceptions import ConflictError, NotFoundError, ValidationError
from core.response import success_response
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from intelligence.contracts import BANDS_ORDER
from intelligence.engine import TxnConflict, UnifiedRiskEngine
from intelligence.scenarios import SCENARIOS, list_scenarios, run_scenario
from middleware.auth import require_role
from services.audit_service import AuditService
from slowapi import Limiter

SCORE_ROLES = ("ADMIN", "SUPERVISOR", "INVESTIGATOR")
READ_ROLES = (*SCORE_ROLES, "AUDITOR", "GUEST")  # guests exist only in demo mode (middleware/auth.py)
INGEST_ROLES = ("ADMIN",)
STREAM_POLL_SECONDS = 0.5
STREAM_MAX_SECONDS = 300.0
EVALUATION_SUMMARY = Path(__file__).resolve().parents[3] / "intelligence" / "model" / "evaluation_summary.json"


def _decision_or_404(engine: UnifiedRiskEngine, decision_id: str):
    decision = engine.store.get(decision_id)
    if decision is None:
        raise NotFoundError("Decision", decision_id)
    return decision


def register_risk_routes(r: APIRouter, limiter: Limiter) -> None:
    @r.post("/assess")
    @limiter.limit("120/minute")
    def assess(
        request: Request,
        body: RiskEventRequest,
        user: dict = Depends(require_role(*SCORE_ROLES)),
        engine: UnifiedRiskEngine = Depends(get_risk_engine),
    ):
        """What-if scoring for staff: full explanation, nothing committed to profiles or the ring window."""
        try:
            decision = engine.assess(body.to_event(), commit=False, source="api")
        except ValueError as exc:
            raise ValidationError("Payment could not be scored", str(exc)) from exc
        return success_response(decision.to_dict(full=True))

    @r.post("/events")
    @limiter.limit("600/minute")
    def ingest_event(
        request: Request,
        body: RiskEventRequest,
        user: dict = Depends(require_role(*INGEST_ROLES)),
        engine: UnifiedRiskEngine = Depends(get_risk_engine),
    ):
        """Trusted ingest: score and commit (idempotent on txn_id; 409 if reused with different content)."""
        try:
            decision = engine.assess(body.to_event(), commit=True, source="ingest")
        except TxnConflict as exc:
            raise ConflictError("txn_id already used", str(exc)) from exc
        except ValueError as exc:
            raise ValidationError("Payment could not be scored", str(exc)) from exc
        return success_response(decision.to_dict(full=True))

    @r.get("/decisions")
    @limiter.limit("120/minute")
    def decisions(
        request: Request,
        limit: int = Query(50, ge=1, le=500),
        band: str = Query("", pattern="^(|APPROVE|STEP_UP|REVIEW|DECLINE)$"),
        min_score: int = Query(0, ge=0, le=100),
        source: str = Query("", pattern="^(|synthetic|scenario|api|ingest)$"),
        user: dict = Depends(require_role(*READ_ROLES)),
        engine: UnifiedRiskEngine = Depends(get_risk_engine),
        traffic=Depends(get_risk_demo_traffic),
    ):
        if traffic is not None:
            traffic.touch()
        items = engine.store.recent(limit=limit, band=band or None, min_score=min_score, source=source or None)
        return success_response(
            {"decisions": [d.to_dict(full=False) for d in items], "sequence": engine.store.sequence}
        )

    @r.get("/decisions/{decision_id}")
    @limiter.limit("240/minute")
    def decision_detail(
        request: Request,
        decision_id: str,
        user: dict = Depends(require_role(*READ_ROLES)),
        engine: UnifiedRiskEngine = Depends(get_risk_engine),
    ):
        return success_response(_decision_or_404(engine, decision_id).to_dict(full=True))

    @r.post("/decisions/{decision_id}/feedback")
    @limiter.limit("60/minute")
    def decision_feedback(
        request: Request,
        decision_id: str,
        body: RiskFeedbackRequest,
        user: dict = Depends(require_role(*SCORE_ROLES)),
        engine: UnifiedRiskEngine = Depends(get_risk_engine),
        audit: AuditService = Depends(get_audit_service),
    ):
        """Analyst outcome. FALSE_ALERT teaches the customer's baseline; CONFIRMED_FRAUD marks the payee."""
        _decision_or_404(engine, decision_id)
        by = user.get("sub", "unknown")
        decision = engine.feedback(decision_id, body.outcome, body.note, by)
        audit.log(
            "RISK_DECISION_FEEDBACK",
            by,
            details=f"decision={decision_id} txn={decision.txn_id} outcome={body.outcome} "
            f"band={decision.band} score={decision.score}",
        )
        return success_response(decision.to_dict(full=True))

    @r.get("/metrics")
    @limiter.limit("120/minute")
    def metrics(
        request: Request,
        user: dict = Depends(require_role(*READ_ROLES)),
        engine: UnifiedRiskEngine = Depends(get_risk_engine),
        traffic=Depends(get_risk_demo_traffic),
    ):
        if traffic is not None:
            traffic.touch()
        return success_response(
            {
                **engine.store.metrics(),
                "bands_order": list(BANDS_ORDER),
                "demo_traffic": traffic.status() if traffic is not None else None,
            }
        )

    @r.get("/stream")
    @limiter.limit("20/minute")
    def stream(
        request: Request,
        source: str = Query("demo", pattern="^(demo|live)$"),
        limit: int = Query(300, ge=1, le=2000),
        user: dict = Depends(require_role(*READ_ROLES)),
        engine: UnifiedRiskEngine = Depends(get_risk_engine),
        traffic=Depends(get_risk_demo_traffic),
    ):
        """Server-sent decisions: the shared engine's synthetic demo traffic, or real public payments (live)."""
        settings = get_settings()
        if source == "live":
            if not (settings.demo_mode or settings.live_feed_enabled):
                raise ConflictError(
                    "Live payment feed is disabled",
                    "Set LIVE_FEED_ENABLED=true to stream public mempool.space transactions.",
                )
            from intelligence.runtime import RiskLiveFeed

            feed = RiskLiveFeed()

            def _live():
                try:
                    for event in feed.events(limit=limit):
                        yield f"data: {json.dumps(event)}\n\n"
                except RuntimeError as exc:
                    yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

            return StreamingResponse(_live(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

        if traffic is None:
            raise ConflictError(
                "Synthetic demo traffic is disabled", "Production decisions arrive through POST /api/v1/risk/events."
            )
        traffic.touch()

        def _demo():
            after = max(0, engine.store.sequence - 20)
            sent, started = 0, time.monotonic()
            while sent < limit and time.monotonic() - started < STREAM_MAX_SECONDS:
                traffic.touch()
                for seq, decision in engine.store.since(after, limit=50, source="synthetic"):
                    after = seq
                    sent += 1
                    payload = {
                        "source": "synthetic",
                        "decision": decision.to_dict(full=True),
                        "provenance": {
                            "provider": "MuleCatch journey simulator",
                            "note": "Synthetic customers and fraud journeys; event times are simulated.",
                        },
                        "traffic": traffic.status(),
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    if sent >= limit:
                        return
                time.sleep(STREAM_POLL_SECONDS)

        return StreamingResponse(_demo(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @r.get("/scenarios")
    @limiter.limit("60/minute")
    def scenarios(request: Request, user: dict = Depends(require_role(*READ_ROLES))):
        return success_response({"scenarios": list_scenarios()})

    @r.post("/scenarios/{name}/run")
    @limiter.limit("20/minute")
    def run(
        request: Request,
        name: str,
        user: dict = Depends(require_role(*READ_ROLES)),
        engine: UnifiedRiskEngine = Depends(get_risk_engine),
    ):
        """Replay a worked scenario on an isolated engine (synthetic); decisions also appear in the feed."""
        if name not in SCENARIOS:
            raise NotFoundError("Scenario", name)
        return success_response(run_scenario(name, store=engine.store))

    @r.get("/feeds")
    @limiter.limit("60/minute")
    def feeds(request: Request, user: dict = Depends(require_role(*READ_ROLES)), threat=Depends(get_threat_feeds)):
        """Provenance of every external data source the engines use, with fetch times and staleness."""
        settings = get_settings()
        return success_response(
            {
                "threat_feeds": threat.status(),
                "live_payments": {
                    "provider": "mempool.space (public Bitcoin mempool)",
                    "enabled": settings.demo_mode or settings.live_feed_enabled,
                    "used_by": "GET /api/v1/risk/stream?source=live (private engine)",
                },
                "sanctions": {
                    "provider": "UN Security Council consolidated list (existing screening module)",
                    "enabled": settings.screening_enabled,
                    "used_by": "BI10 payee-name match",
                },
                "complaints": {
                    "provider": "MuleCatch fraud-complaint register (existing module)",
                    "used_by": "BI01 known-fraud payee",
                },
                "mule_alerts": {
                    "provider": "MuleCatch alert queue (existing mule detection)",
                    "used_by": "MN03 open-alert payee",
                },
            }
        )

    @r.get("/evaluation")
    @limiter.limit("60/minute")
    def evaluation(request: Request, user: dict = Depends(require_role(*READ_ROLES))):
        """Latest offline evaluation (synthetic, time-separated) with the design targets kept separate."""
        if not EVALUATION_SUMMARY.exists():
            raise NotFoundError("Evaluation", "run scripts/evaluation/evaluate_unified.py")
        return success_response(json.loads(EVALUATION_SUMMARY.read_text(encoding="utf-8")))

    @r.get("/config")
    @limiter.limit("60/minute")
    def config(
        request: Request,
        user: dict = Depends(require_role(*READ_ROLES)),
        engine: UnifiedRiskEngine = Depends(get_risk_engine),
        traffic=Depends(get_risk_demo_traffic),
    ):
        return success_response({**engine.status(), "demo_traffic": traffic.status() if traffic else None})
