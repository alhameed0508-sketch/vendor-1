"""
Centralized configuration via Pydantic BaseSettings.
Replaces scattered os.getenv() calls throughout the codebase.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Neo4j
    neo4j_uri: str = Field("bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field("CHANGE_ME_NOT_FOR_PRODUCTION", alias="NEO4J_PASSWORD")
    neo4j_tls_enabled: bool = Field(False, alias="NEO4J_TLS_ENABLED")

    # Kafka
    kafka_bootstrap: str = Field("kafka:9092", alias="KAFKA_BOOTSTRAP")
    kafka_enabled: bool = Field(False, alias="KAFKA_ENABLED")
    kafka_security_protocol: str = Field("PLAINTEXT", alias="KAFKA_SECURITY_PROTOCOL")
    kafka_ssl_cafile: str = Field("", alias="KAFKA_SSL_CAFILE")
    kafka_ssl_certfile: str = Field("", alias="KAFKA_SSL_CERTFILE")
    kafka_ssl_keyfile: str = Field("", alias="KAFKA_SSL_KEYFILE")

    # Auth
    jwt_secret: str = Field("change_me_before_deployment", alias="JWT_SECRET")
    auth_enabled: bool = Field(False, alias="AUTH_ENABLED")

    # Token expiry
    access_token_expire_minutes: int = Field(15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # Account lockout
    lockout_max_attempts: int = Field(5, alias="LOCKOUT_MAX_ATTEMPTS")
    lockout_duration_minutes: int = Field(30, alias="LOCKOUT_DURATION_MINUTES")

    # LDAP
    ldap_enabled: bool = Field(False, alias="LDAP_ENABLED")
    ldap_url: str = Field("ldap://localhost:389", alias="LDAP_URL")
    ldap_bind_dn: str = Field("", alias="LDAP_BIND_DN")
    ldap_bind_password: str = Field("", alias="LDAP_BIND_PASSWORD")
    ldap_search_base: str = Field("", alias="LDAP_SEARCH_BASE")

    # Screening
    screening_enabled: bool = Field(False, alias="SCREENING_ENABLED")
    unsc_url: str = Field(
        "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
        alias="UNSC_URL",
    )
    fri_api_url: str = Field("", alias="FRI_API_URL")

    # PostgreSQL (set to enable persistent storage for STRs, audit, etc.)
    postgres_url: str = Field("", alias="POSTGRES_URL")

    # Redis / Cache
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    cache_l1_max_size: int = Field(1000, alias="CACHE_L1_MAX_SIZE")
    cache_l1_ttl_seconds: int = Field(60, alias="CACHE_L1_TTL_SECONDS")
    cache_l2_ttl_seconds: int = Field(600, alias="CACHE_L2_TTL_SECONDS")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://frontend:80"],
        alias="CORS_ORIGINS",
    )

    # App
    env: str = Field("development", alias="ENV")
    reporting_entity: str = Field("Indian Overseas Bank", alias="REPORTING_ENTITY")
    reporting_ifsc: str = Field("IOBA0000001", alias="REPORTING_IFSC")
    fiu_format_version: str = Field("2.1", alias="FIU_FORMAT_VERSION")
    analyst_hourly_cost_inr: float = Field(0.0, alias="ANALYST_HOURLY_COST_INR", ge=0)
    benchmark_results_path: str = Field(
        "data/benchmark_results.json",
        alias="BENCHMARK_RESULTS_PATH",
    )

    # Detection thresholds
    smurf_flag_threshold: float = Field(0.55, alias="SMURF_FLAG_THRESHOLD")
    onboarding_risk_threshold: float = Field(0.50, alias="ONBOARDING_RISK_THRESHOLD")

    # Behavioral signal thresholds (v2.0 - externalized from detection logic)
    passthrough_threshold_high: float = Field(0.90, alias="PASSTHROUGH_THRESHOLD_HIGH")
    passthrough_threshold_medium: float = Field(0.70, alias="PASSTHROUGH_THRESHOLD_MEDIUM")
    round_amount_threshold: float = Field(0.70, alias="ROUND_AMOUNT_THRESHOLD")
    velocity_spike_threshold: float = Field(0.05, alias="VELOCITY_SPIKE_THRESHOLD")
    negative_balance_threshold: float = Field(0.50, alias="NEGATIVE_BALANCE_THRESHOLD")
    high_volume_txn_threshold: int = Field(500, alias="HIGH_VOLUME_TXN_THRESHOLD")

    # Risk classification thresholds (v2.0 - tuned for better precision)
    # HIGH RISK requires stronger evidence than before
    risk_high_anomaly_min: int = Field(2, alias="RISK_HIGH_ANOMALY_MIN")
    risk_high_behavioral_min: int = Field(2, alias="RISK_HIGH_BEHAVIORAL_MIN")
    risk_high_anomaly_alt: int = Field(1, alias="RISK_HIGH_ANOMALY_ALT")
    risk_high_behavioral_alt: int = Field(3, alias="RISK_HIGH_BEHAVIORAL_ALT")
    # MEDIUM RISK thresholds
    risk_medium_behavioral_min: int = Field(3, alias="RISK_MEDIUM_BEHAVIORAL_MIN")
    risk_medium_anomaly_min: int = Field(1, alias="RISK_MEDIUM_ANOMALY_MIN")

    # Active learning / feedback
    feedback_store_path: str = Field("", alias="FEEDBACK_STORE_PATH")
    feedback_fp_raise_bound: float = Field(0.30, alias="FEEDBACK_FP_RAISE_BOUND")
    feedback_fp_lower_bound: float = Field(0.10, alias="FEEDBACK_FP_LOWER_BOUND")
    feedback_raise_delta: float = Field(0.05, alias="FEEDBACK_RAISE_DELTA")
    feedback_lower_delta: float = Field(-0.03, alias="FEEDBACK_LOWER_DELTA")
    feedback_recent_window: int = Field(20, alias="FEEDBACK_RECENT_WINDOW")
    feedback_min_for_adjustment: int = Field(5, alias="FEEDBACK_MIN_FOR_ADJUSTMENT")
    feedback_retrain_batch_size: int = Field(20, alias="FEEDBACK_RETRAIN_BATCH_SIZE")

    # GNN model persistence
    gnn_model_path: str = Field("models/gnn/trained_model.pt", alias="GNN_MODEL_PATH")
    model_version: str = Field("unvalidated-dev", alias="MODEL_VERSION")
    rule_version: str = Field("rules-2026.2", alias="RULE_VERSION")

    # Live payment feed (public Bitcoin mempool). Always on in demo mode; opt-in elsewhere.
    live_feed_enabled: bool = Field(False, alias="LIVE_FEED_ENABLED")

    # GenAI / LLM
    genai_enabled: bool = Field(False, alias="GENAI_ENABLED")
    genai_provider: str = Field("gemini", alias="GENAI_PROVIDER")
    genai_api_key: str = Field("", alias="GENAI_API_KEY")
    genai_model: str = Field("", alias="GENAI_MODEL")
    genai_temperature: float = Field(0.3, alias="GENAI_TEMPERATURE")
    genai_max_tokens: int = Field(2048, alias="GENAI_MAX_TOKENS")
    genai_timeout_seconds: float = Field(30.0, alias="GENAI_TIMEOUT_SECONDS")

    @computed_field
    @property
    def demo_mode(self) -> bool:
        """True when NOT running in production — enables demo features."""
        return self.env != "production"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "protected_namespaces": ("settings_",),
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton settings instance."""
    return Settings()
