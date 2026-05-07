"""
Dependency injection — singleton service getters for FastAPI Depends.
"""

from functools import lru_cache

from core.config import get_settings
from graph_engine.persistence import PersistenceLayer
from detection.pipeline import DetectionPipeline
from models.active_learning.feedback_loop import ActiveLearningEngine, FeedbackStore
from ingest.kafka_consumer import TransactionConsumer, KAFKA_ENABLED

from cache.redis_client import RedisClient
from cache.cache_manager import CacheManager

from repositories.alert_repository import AlertRepository
from repositories.escalation_repository import EscalationRepository
from repositories.audit_repository import AuditRepository
from repositories.kpi_repository import KPIRepository
from repositories.dataset_repository import DatasetRepository
from repositories.user_repository import UserRepository

from infra.database.user_db import UserDB

from services.alert_service import AlertService
from services.audit_service import AuditService
from services.compliance_service import ComplianceService
from services.detection_service import DetectionService
from services.escalation_service import EscalationService
from services.feedback_service import FeedbackService
from services.graph_service import GraphService
from services.ingest_service import IngestService
from services.kpi_service import KPIService


# ── Singleton infrastructure ─────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_persistence() -> PersistenceLayer:
    return PersistenceLayer()


@lru_cache(maxsize=1)
def get_pipeline() -> DetectionPipeline:
    return DetectionPipeline()


@lru_cache(maxsize=1)
def get_feedback_engine() -> ActiveLearningEngine:
    return ActiveLearningEngine()


@lru_cache(maxsize=1)
def get_feedback_store() -> FeedbackStore:
    return FeedbackStore()


@lru_cache(maxsize=1)
def get_kafka_consumer() -> TransactionConsumer:
    return TransactionConsumer()


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
def get_alert_repo() -> AlertRepository:
    return AlertRepository(get_persistence())


@lru_cache(maxsize=1)
def get_escalation_repo() -> EscalationRepository:
    return EscalationRepository()


@lru_cache(maxsize=1)
def get_audit_repo() -> AuditRepository:
    return AuditRepository()


@lru_cache(maxsize=1)
def get_kpi_repo() -> KPIRepository:
    return KPIRepository(get_persistence())


@lru_cache(maxsize=1)
def get_dataset_repo() -> DatasetRepository:
    return DatasetRepository(get_persistence())


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
    return KPIService(get_kpi_repo())


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
def get_user_db() -> UserDB:
    settings = get_settings()
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
    from repositories.screening_repository import ScreeningRepository
    return ScreeningRepository()


@lru_cache(maxsize=1)
def get_screening_service():
    from services.screening_service import ScreeningService
    return ScreeningService(get_screening_repository())
