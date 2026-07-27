"""
Production startup validator — fail fast on insecure configuration.
Called at startup when ENV=production to reject default secrets
and missing mandatory settings.
"""

import sys
import logging
from typing import List

logger = logging.getLogger(__name__)

# Known default/placeholder values that must be changed in production
_DEFAULT_SECRETS = frozenset(
    {
        "change_me_before_deployment",
        "CHANGE_ME_NOT_FOR_PRODUCTION",
        "changeme",
        "secret",
        "password",
        "REPLACE_WITH_CRYPTOGRAPHIC_SECRET",
        "REPLACE_WITH_STRONG_PASSWORD",
        "dev_jwt_secret_change_in_production",
        "mulecatch2024",
        "mulecatch_dev_2024",
    }
)


def validate_or_die(settings) -> None:
    """Validate production configuration. Exits the process if violations found."""
    violations: List[str] = []

    # JWT secret must not be a default
    if settings.jwt_secret in _DEFAULT_SECRETS or len(settings.jwt_secret) < 32:
        violations.append(
            "JWT_SECRET is set to a default placeholder. "
            "Set a strong, unique secret for production."
        )

    # Neo4j password must not be a default
    if settings.neo4j_password in _DEFAULT_SECRETS or len(settings.neo4j_password) < 16:
        violations.append(
            "NEO4J_PASSWORD is set to a default placeholder. "
            "Set a strong password for production."
        )

    # Auth must be enabled in production
    if not settings.auth_enabled:
        violations.append(
            "AUTH_ENABLED must be true in production. "
            "Running without authentication is not allowed."
        )

    # Kafka must be enabled in production
    if not settings.kafka_enabled:
        violations.append(
            "KAFKA_ENABLED must be true in production. "
            "Real-time transaction ingestion is required."
        )

    if settings.kafka_enabled:
        if settings.kafka_security_protocol not in ("SSL", "SASL_SSL"):
            violations.append(
                "KAFKA_SECURITY_PROTOCOL must be SSL or SASL_SSL in production."
            )
        if not settings.kafka_ssl_cafile:
            violations.append("KAFKA_SSL_CAFILE is required for production Kafka TLS.")

    # PostgreSQL must be configured in production
    if not settings.postgres_url:
        violations.append(
            "POSTGRES_URL must be set in production. "
            "In-memory repositories lose data on restart."
        )

    if not settings.neo4j_tls_enabled:
        violations.append("NEO4J_TLS_ENABLED must be true in production.")

    if settings.redis_url and not settings.redis_url.startswith("rediss://"):
        violations.append("REDIS_URL must use rediss:// in production.")

    if settings.postgres_url and "sslmode=" not in settings.postgres_url:
        violations.append("POSTGRES_URL must configure sslmode in production.")

    if settings.ldap_enabled and not settings.ldap_url.startswith("ldaps://"):
        violations.append("LDAP_URL must use ldaps:// in production.")

    if settings.screening_enabled and not settings.unsc_url.startswith("https://"):
        violations.append(
            "UNSC_URL must use HTTPS when screening is enabled in production."
        )

    if "*" in settings.cors_origins:
        violations.append("CORS_ORIGINS must not contain a wildcard in production.")

    if (
        not settings.model_version
        or settings.model_version.startswith("unvalidated")
        or settings.model_version.startswith("REPLACE_")
    ):
        violations.append(
            "MODEL_VERSION must identify an approved, validated model release."
        )

    if not settings.rule_version or settings.rule_version == "unversioned":
        violations.append("RULE_VERSION must identify the governed AML rule release.")

    if violations:
        logger.critical("=" * 60)
        logger.critical("PRODUCTION CONFIGURATION VALIDATION FAILED")
        logger.critical("=" * 60)
        for i, v in enumerate(violations, 1):
            logger.critical("  [%d] %s", i, v)
        logger.critical("=" * 60)
        logger.critical(
            "Fix the above issues in your .env or environment variables, "
            "then restart the application."
        )
        sys.exit(1)

    logger.info("Production configuration validated successfully.")
