"""
Dependency injection — singleton service getters for FastAPI Depends.
"""

import logging
from functools import lru_cache

from cache.cache_manager import CacheManager
from cache.redis_client import RedisClient
from core.config import get_settings
from core.exceptions import ConflictError
from detection.pipeline import DetectionPipeline
from detection.rule_thresholds import RuleThresholds
from fastapi import Query
from graph_engine.persistence import PersistenceLayer
from ingest.kafka_consumer import KAFKA_ENABLED, TransactionConsumer
from repositories.alert_repository import AlertRepository
from repositories.audit_repository import AuditRepository
from repositories.dataset_repository import DatasetRepository
from repositories.escalation_repository import EscalationRepository
from repositories.kpi_repository import KPIRepository
from repositories.user_repository import UserRepository
from services.alert_service import AlertService
from services.audit_service import AuditService
from services.compliance_service import ComplianceService
from services.detection_service import DetectionService
from services.escalation_service import EscalationService
from services.feedback_service import FeedbackService
from services.graph_service import GraphService
from services.ingest_service import IngestService
from services.kpi_service import KPIService
from services.realtime_scorer import RealtimeScorer

from infra.database.user_db import UserDB
from models.active_learning.feedback_loop import (
    ActiveLearningEngine,
    FeedbackStore,
    ThresholdConfig,
)

_deps_logger = logging.getLogger(__name__)


# ── PostgreSQL engine (None if not configured) ───────────────────────────────


@lru_cache(maxsize=1)
def _get_pg_engine():
    """Return SQLAlchemy engine if POSTGRES_URL is set, else None."""
    settings = get_settings()
    if not settings.postgres_url:
        return None
    from backend.infra.database.postgres import ensure_tables, get_engine

    engine = get_engine(settings.postgres_url)
    ensure_tables(engine)
    _deps_logger.info("PostgreSQL persistence enabled")
    return engine


def close_runtime_resources() -> None:
    """Close initialized external clients without creating new dependencies."""
    if get_persistence.cache_info().currsize:
        try:
            get_persistence().close()
        except Exception as exc:
            _deps_logger.warning("Neo4j shutdown failed: %s", exc)
        finally:
            get_persistence.cache_clear()

    if get_redis_client.cache_info().currsize:
        try:
            get_redis_client().close()
        except Exception as exc:
            _deps_logger.warning("Redis shutdown failed: %s", exc)
        finally:
            get_redis_client.cache_clear()

    if _get_pg_engine.cache_info().currsize:
        engine = _get_pg_engine()
        if engine is not None:
            try:
                engine.dispose()
            except Exception as exc:
                _deps_logger.warning("PostgreSQL shutdown failed: %s", exc)
        _get_pg_engine.cache_clear()


# ── Singleton infrastructure ─────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_persistence() -> PersistenceLayer:
    return PersistenceLayer()


@lru_cache(maxsize=1)
def get_pipeline() -> DetectionPipeline:
    settings = get_settings()
    return DetectionPipeline(
        gnn_model_path=settings.gnn_model_path,
        genai_service=get_genai_service(),
        model_version=settings.model_version,
        rule_version=settings.rule_version,
        rule_thresholds=RuleThresholds.from_json(settings.rule_thresholds),
        device_profiler=get_device_profiler(),
    )


@lru_cache(maxsize=1)
def get_realtime_scorer() -> RealtimeScorer:
    """Per-payment scorer. Seeded with unlabelled synthetic history in demo mode only."""
    if not get_settings().demo_mode:
        return RealtimeScorer([], [])
    from services.realtime_demo import strip_labels

    from data.synthetic.generator import build_adversarial_dataset

    data = build_adversarial_dataset(num_clusters=3, num_legit_accounts=60, num_adversarial=10)
    return RealtimeScorer(strip_labels(data["accounts"]), strip_labels(data["transactions"]))


def get_demo_replay(source: str = Query("demo", pattern="^(demo|live|market)$")):
    """A fresh seeded replay per stream, so every viewer sees the same story from the start.

    Refuses outside demo mode before doing any work (the replay builds a dataset).
    Returns None for the real sources (``live``, ``market``), which have their own providers.
    """
    if source != "demo":
        return None
    if not get_settings().demo_mode:
        raise ConflictError(
            "Synthetic payment replay is disabled in production",
            "Production scoring is driven by validated ingest sources.",
        )
    from services.realtime_demo import DemoReplay

    return DemoReplay()


def _require_live_feeds() -> None:
    settings = get_settings()
    if not (settings.demo_mode or getattr(settings, "live_feed_enabled", False)):
        raise ConflictError(
            "Live feeds are disabled",
            "Set LIVE_FEED_ENABLED=true to stream public payments and stock-exchange trades.",
        )


@lru_cache(maxsize=1)
def get_live_buffer():
    """Recent real public payments seen by any live stream: what the Detection modules report on."""
    from services.live_buffer import LiveBuffer

    return LiveBuffer()


def get_live_feed(source: str = Query("demo", pattern="^(demo|live|market)$")):
    """A fresh feed of real public payments per stream (source=live). Demo mode, or LIVE_FEED_ENABLED."""
    if source != "live":
        return None
    _require_live_feeds()
    from services.live_feed import LiveFeed

    return LiveFeed(sink=get_live_buffer().add)


def get_market_feed(source: str = Query("demo", pattern="^(demo|live|market)$")):
    """A fresh feed of live stock-exchange trades per stream (source=market). Demo mode, or LIVE_FEED_ENABLED."""
    if source != "market":
        return None
    _require_live_feeds()
    from services.market_feed import MarketFeed

    return MarketFeed()


def _build_threshold_config() -> ThresholdConfig:
    """Build ThresholdConfig from centralised settings."""
    settings = get_settings()
    return ThresholdConfig(
        base_smurf_threshold=settings.smurf_flag_threshold,
        base_suspicion_threshold=settings.onboarding_risk_threshold,
        fp_raise_bound=settings.feedback_fp_raise_bound,
        fp_lower_bound=settings.feedback_fp_lower_bound,
        raise_delta=settings.feedback_raise_delta,
        lower_delta=settings.feedback_lower_delta,
        recent_window=settings.feedback_recent_window,
        min_feedback_for_adjustment=settings.feedback_min_for_adjustment,
        retrain_batch_size=settings.feedback_retrain_batch_size,
    )


@lru_cache(maxsize=1)
def get_feedback_store() -> FeedbackStore:
    settings = get_settings()
    path = settings.feedback_store_path or None
    return (
        FeedbackStore(
            path=path,
            config=_build_threshold_config(),
        )
        if path
        else FeedbackStore(config=_build_threshold_config())
    )


@lru_cache(maxsize=1)
def get_feedback_engine() -> ActiveLearningEngine:
    return ActiveLearningEngine(
        store=get_feedback_store(),
        config=_build_threshold_config(),
    )


@lru_cache(maxsize=1)
def get_kafka_consumer() -> TransactionConsumer:
    settings = get_settings()
    return TransactionConsumer(
        bootstrap_servers=settings.kafka_bootstrap,
        security_protocol=settings.kafka_security_protocol,
        ssl_cafile=settings.kafka_ssl_cafile or None,
        ssl_certfile=settings.kafka_ssl_certfile or None,
        ssl_keyfile=settings.kafka_ssl_keyfile or None,
    )


@lru_cache(maxsize=1)
def get_redis_client() -> RedisClient:
    settings = get_settings()
    return RedisClient(url=settings.redis_url)


@lru_cache(maxsize=1)
def get_cache_manager() -> CacheManager:
    settings = get_settings()
    return CacheManager(
        redis_client=get_redis_client(),
        l1_max_size=settings.cache_l1_max_size,
        l1_default_ttl=settings.cache_l1_ttl_seconds,
        l2_default_ttl=settings.cache_l2_ttl_seconds,
    )


# ── Singleton repositories ───────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_alert_repo():
    engine = _get_pg_engine()
    if engine is not None:
        from repositories.pg_alert_repository import PgAlertRepository

        return PgAlertRepository(engine)
    return AlertRepository(get_persistence(), get_redis_client())


@lru_cache(maxsize=1)
def get_escalation_repo():
    engine = _get_pg_engine()
    if engine is not None:
        from repositories.pg_escalation_repository import PgEscalationRepository

        return PgEscalationRepository(engine)
    return EscalationRepository()


@lru_cache(maxsize=1)
def get_audit_repo():
    engine = _get_pg_engine()
    if engine is not None:
        from repositories.pg_audit_repository import PgAuditRepository

        return PgAuditRepository(engine)
    return AuditRepository()


@lru_cache(maxsize=1)
def get_kpi_repo():
    engine = _get_pg_engine()
    if engine is not None:
        from repositories.pg_kpi_repository import PgKPIRepository

        return PgKPIRepository(engine)
    return KPIRepository(get_persistence())


@lru_cache(maxsize=1)
def get_dataset_repo():
    engine = _get_pg_engine()
    if engine is not None:
        from repositories.pg_dataset_repository import PgDatasetRepository

        return PgDatasetRepository(engine)
    return DatasetRepository(get_persistence(), get_redis_client())


# ── Singleton services ───────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_audit_service() -> AuditService:
    return AuditService(get_audit_repo())


@lru_cache(maxsize=1)
def get_alert_service() -> AlertService:
    return AlertService(
        alert_repo=get_alert_repo(),
        cache=get_cache_manager(),
        audit_service=get_audit_service(),
    )


@lru_cache(maxsize=1)
def get_detection_service() -> DetectionService:
    return DetectionService(
        pipeline=get_pipeline(),
        feedback_store=get_feedback_store(),
        alert_repo=get_alert_repo(),
        dataset_repo=get_dataset_repo(),
        kpi_repo=get_kpi_repo(),
    )


@lru_cache(maxsize=1)
def get_feedback_service() -> FeedbackService:
    return FeedbackService(
        feedback_engine=get_feedback_engine(),
        feedback_store=get_feedback_store(),
        alert_repo=get_alert_repo(),
        kpi_repo=get_kpi_repo(),
        audit_service=get_audit_service(),
        config=_build_threshold_config(),
    )


@lru_cache(maxsize=1)
def get_escalation_service() -> EscalationService:
    return EscalationService(
        escalation_repo=get_escalation_repo(),
        alert_repo=get_alert_repo(),
        audit_service=get_audit_service(),
    )


@lru_cache(maxsize=1)
def get_compliance_service() -> ComplianceService:
    return ComplianceService(
        alert_repo=get_alert_repo(),
        kpi_repo=get_kpi_repo(),
    )


@lru_cache(maxsize=1)
def get_kpi_service() -> KPIService:
    return KPIService(get_kpi_repo(), get_alert_repo())


@lru_cache(maxsize=1)
def get_ingest_service() -> IngestService:
    return IngestService(
        kafka_consumer=get_kafka_consumer(),
        kafka_enabled=KAFKA_ENABLED,
    )


@lru_cache(maxsize=1)
def get_graph_service() -> GraphService:
    return GraphService()


# ── User / Auth singletons ───────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_user_db():
    settings = get_settings()
    engine = _get_pg_engine()
    if engine is not None:
        from backend.infra.database.pg_user_db import PgUserDB

        db = PgUserDB(engine)
    else:
        db = UserDB()
    # Seed demo users when not in production
    if settings.demo_mode:
        db.seed_demo_users()
    return db


@lru_cache(maxsize=1)
def get_user_repository() -> UserRepository:
    settings = get_settings()
    return UserRepository(
        user_db=get_user_db(),
        lockout_max_attempts=settings.lockout_max_attempts,
        lockout_duration_minutes=settings.lockout_duration_minutes,
    )


# ── Screening singletons ────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_screening_repository():
    engine = _get_pg_engine()
    if engine is not None:
        from repositories.pg_screening_repository import PgScreeningRepository

        return PgScreeningRepository(engine)
    from repositories.screening_repository import ScreeningRepository

    return ScreeningRepository()


@lru_cache(maxsize=1)
def get_screening_service():
    from services.screening_service import ScreeningService

    return ScreeningService(get_screening_repository())


# ── Onboarding singletons ──────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_onboarding_repository():
    engine = _get_pg_engine()
    if engine is not None:
        from repositories.pg_onboarding_repository import PgOnboardingRepository

        return PgOnboardingRepository(engine)
    from repositories.onboarding_repository import OnboardingRepository

    return OnboardingRepository()


@lru_cache(maxsize=1)
def get_entity_profile_repository():
    engine = _get_pg_engine()
    if engine is not None:
        from repositories.pg_entity_profile_repository import (
            PgEntityProfileRepository,
        )

        return PgEntityProfileRepository(engine)
    from repositories.entity_profile_repository import EntityProfileRepository

    return EntityProfileRepository()


@lru_cache(maxsize=1)
def get_entity_resolution_service():
    from services.entity_resolution_service import EntityResolutionService

    return EntityResolutionService(get_entity_profile_repository())


@lru_cache(maxsize=1)
def get_onboarding_service():
    from services.onboarding_service import OnboardingService

    return OnboardingService(
        get_onboarding_repository(),
        persistence=get_persistence(),
        entity_resolver=get_entity_resolution_service(),
    )


# ── STR singletons ──────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_str_repository():
    engine = _get_pg_engine()
    if engine is not None:
        from repositories.pg_str_repository import PgSTRRepository

        return PgSTRRepository(engine)
    from repositories.str_repository import STRRepository

    return STRRepository()


@lru_cache(maxsize=1)
def get_str_service():
    from services.str_service import STRService

    return STRService(get_str_repository())


# ── Investigation singletons ────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_access_directory():
    from access.seed import demo_directory

    return demo_directory()


@lru_cache(maxsize=1)
def get_investigation_service():
    from core.exceptions import NotFoundError
    from repositories.investigation_repository import InvestigationRepository
    from services.investigation.investigation_service import InvestigationService

    def complaint_exists(complaint_id: str) -> bool:
        try:
            get_complaint_service().get_case(complaint_id)
        except NotFoundError:
            return False
        return True

    resolvers = {
        "alert": lambda alert_id: get_alert_repo().find_by_id(alert_id) is not None,
        "complaint": complaint_exists,
    }
    return InvestigationService(InvestigationRepository(), get_audit_service(), resolvers)


# ── GenAI singletons ──────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_llm_provider():
    from genai.factory import create_llm_provider

    return create_llm_provider(get_settings())


@lru_cache(maxsize=1)
def get_genai_service():
    from services.genai_service import GenAIService

    return GenAIService(provider=get_llm_provider())


# ── Fraud complaint singletons ──────────────────────────────────────────


@lru_cache(maxsize=1)
def get_complaint_service():
    from datetime import datetime

    from complaints.rules import IST
    from complaints.seed import demo_clock
    from repositories.complaint_repository import ComplaintRepository
    from services.complaint_service import ComplaintService

    settings = get_settings()
    # The RBI rules start on 1 Jan 2027, so the demo desk runs on a clock that is already past it.
    service = ComplaintService(
        repo=ComplaintRepository(),
        alert_repo=get_alert_repo(),
        audit=get_audit_service(),
        provider=get_llm_provider(),
        now_fn=demo_clock if settings.demo_mode else lambda: datetime.now(IST),
    )
    if settings.demo_mode:
        try:
            get_detection_service().ensure_alerts()  # so the SIM-swap demo case can point at a real mule
        except Exception as exc:
            _deps_logger.warning("Demo complaints seeded without mule alerts: %s", exc)
        service.seed_demo()
    return service


# ── Return-claim singletons ─────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_return_claim_service():
    from datetime import datetime

    from complaints.rules import IST
    from repositories.return_claim_repository import ReturnClaimRepository
    from services.return_claim_service import ReturnClaimService

    settings = get_settings()
    service = ReturnClaimService(
        repo=ReturnClaimRepository(),
        audit=get_audit_service(),
        provider=get_llm_provider(),
        now_fn=lambda: datetime.now(IST),
        webhook_secret=settings.returns_webhook_secret,
    )
    if settings.demo_mode:
        service.seed_demo()
    return service


# ── Benchmark singletons ─────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_benchmark_service():
    from benchmark.service import BenchmarkService

    # Benchmarks use isolated pipelines so stateful device/graph/model helpers
    # cannot leak data between evaluation runs or from live detection.
    return BenchmarkService(results_path=get_settings().benchmark_results_path)


# ── Propensity singletons ────────────────────────────────────────────────


# ── Device / Semantics singletons ──────────────────────────────────────


@lru_cache(maxsize=1)
def get_device_profiler():
    from models.device.device_profiler import DeviceProfiler

    return DeviceProfiler()


# ── Typology singletons ────────────────────────────────────────────────


# ── India-specific singletons ──────────────────────────────────────────


# ── Investigation singletons ──────────────────────────────────────────


# ── Scam detection singletons ─────────────────────────────────────────


# ── Unified risk engine (backend/intelligence) ─────────────────────────────


def open_alert_members(alert_service) -> frozenset:
    """Accounts in open or under-review mule alerts (the existing alert queue feeds the mule engine)."""
    members = set()
    for status in ("OPEN", "UNDER_REVIEW"):
        for alert in alert_service.list_alerts(status=status, limit=500).get("alerts", []):
            for node in alert.get("nodes") or ():
                account = node.get("account_id") if isinstance(node, dict) else getattr(node, "account_id", None)
                if account:
                    members.add(str(account))
    return frozenset(members)


@lru_cache(maxsize=1)
def get_threat_feeds():
    from pathlib import Path

    from intelligence.threat_feeds import ThreatFeeds

    settings = get_settings()
    feeds = ThreatFeeds(cache_path=Path(settings.threat_feeds_cache), enabled=settings.threat_feeds_enabled)
    feeds.start()
    return feeds


@lru_cache(maxsize=1)
def get_risk_engine():
    """The shared unified engine. Trusted commits come from POST /risk/events (and demo traffic in demo mode)."""
    from pathlib import Path

    from intelligence.beneficiary_engine import (
        BeneficiaryIntelligenceEngine,
        KnownFraudRegistry,
        complaint_beneficiaries,
    )
    from intelligence.decision_store import DecisionStore, PgDecisionSink
    from intelligence.engine import EngineConfig, UnifiedRiskEngine
    from intelligence.model import RiskModel
    from intelligence.mule_network import MuleNetworkIntel
    from intelligence.session_engine import SessionIntegrityEngine

    from models.device.device_profiler import DeviceProfiler

    settings = get_settings()

    def _alert_members():
        return open_alert_members(get_alert_service())

    def _complaints():
        return complaint_beneficiaries(get_complaint_service())

    def _sanctions(name: str):
        return get_screening_repository().search_by_name(name)

    mule = MuleNetworkIntel(background=True, alert_members=_alert_members)
    known_fraud = KnownFraudRegistry(complaint_source=_complaints)
    pg = _get_pg_engine()
    store = DecisionStore(sink=PgDecisionSink(pg) if pg is not None else None)
    config = EngineConfig(
        step_up_at=settings.risk_step_up_at, review_at=max(settings.risk_review_at, settings.risk_step_up_at + 1)
    )
    return UnifiedRiskEngine(
        mule=mule,
        session_engine=SessionIntegrityEngine(DeviceProfiler(), get_threat_feeds()),
        beneficiary_engine=BeneficiaryIntelligenceEngine(mule, known_fraud, sanctions_search=_sanctions),
        model=RiskModel.load(Path(settings.risk_model_path) if settings.risk_model_path else None),
        store=store,
        config=config,
        known_fraud=known_fraud,
    )


@lru_cache(maxsize=1)
def get_risk_demo_traffic():
    """Synthetic background traffic for the shared engine: demo mode only (None elsewhere)."""
    settings = get_settings()
    if not (settings.demo_mode and settings.risk_demo_traffic):
        return None
    from intelligence.runtime import DemoTraffic

    return DemoTraffic(get_risk_engine(), rate=settings.risk_demo_rate)
