"""
Centralized configuration via Pydantic BaseSettings.
Replaces scattered os.getenv() calls throughout the codebase.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field, computed_field


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

    # Detection thresholds
    smurf_flag_threshold: float = Field(0.55, alias="SMURF_FLAG_THRESHOLD")

    @computed_field
    @property
    def demo_mode(self) -> bool:
        """True when NOT running in production — enables demo features."""
        return self.env != "production"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton settings instance."""
    return Settings()
