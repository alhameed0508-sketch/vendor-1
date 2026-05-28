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
_DEFAULT_SECRETS = frozenset({
    "change_me_before_deployment",
    "CHANGE_ME_NOT_FOR_PRODUCTION",
    "INSECURE_DEV_ONLY_REPLACE_IN_PRODUCTION",
    "local_dev_secret_not_for_prod",
    "localdev",
    "changeme",
    "secret",
    "password",
})

# Minimum entropy for JWT secrets (32 chars recommended for HS256)
_MIN_JWT_SECRET_LENGTH = 32

# CORS origins that should never be allowed in production
_UNSAFE_CORS_PATTERNS = ("*", "http://localhost", "http://127.0.0.1")


def validate_or_die(settings) -> None:
    """Validate production configuration. Exits the process if violations found."""
    violations: List[str] = []
    warnings: List[str] = []

    # ── Secret validation ──────────────────────────────────────

    # JWT secret must not be a default
    if settings.jwt_secret in _DEFAULT_SECRETS:
        violations.append(
            "JWT_SECRET is set to a default placeholder. "
            "Set a strong, unique secret for production."
        )

    # JWT secret entropy check
    if len(settings.jwt_secret) < _MIN_JWT_SECRET_LENGTH:
        violations.append(
            f"JWT_SECRET is too short ({len(settings.jwt_secret)} chars). "
            f"Use at least {_MIN_JWT_SECRET_LENGTH} characters for HS256."
        )

    # Neo4j password must not be a default
    if settings.neo4j_password in _DEFAULT_SECRETS:
        violations.append(
            "NEO4J_PASSWORD is set to a default placeholder. "
            "Set a strong password for production."
        )

    # ── Auth & access control ──────────────────────────────────

    # Auth must be enabled in production
    if not settings.auth_enabled:
        violations.append(
            "AUTH_ENABLED must be true in production. "
            "Running without authentication is not allowed."
        )

    # ── CORS validation ────────────────────────────────────────

    for origin in settings.cors_origins:
        for pattern in _UNSAFE_CORS_PATTERNS:
            if origin == pattern or origin.startswith(pattern):
                violations.append(
                    f"CORS_ORIGINS contains unsafe origin '{origin}'. "
                    "Remove localhost/wildcard origins in production."
                )
                break

    # ── Infrastructure ─────────────────────────────────────────

    # Kafka must be enabled in production
    if not settings.kafka_enabled:
        violations.append(
            "KAFKA_ENABLED must be true in production. "
            "Real-time transaction ingestion is required."
        )

    # Neo4j TLS should be enabled in production
    if not settings.neo4j_tls_enabled:
        warnings.append(
            "NEO4J_TLS_ENABLED is false. "
            "Enable TLS for encrypted Neo4j connections in production."
        )

    # Redis URL should use TLS (rediss://) in production
    if settings.redis_url and not settings.redis_url.startswith("rediss://"):
        warnings.append(
            "REDIS_URL does not use TLS (rediss://). "
            "Consider enabling TLS for encrypted Redis connections."
        )

    # ── GenAI validation ───────────────────────────────────────

    if settings.genai_enabled and not settings.genai_api_key:
        violations.append(
            "GENAI_ENABLED is true but GENAI_API_KEY is empty. "
            "Provide a valid API key or disable GenAI."
        )

    # ── Report results ─────────────────────────────────────────

    if warnings:
        logger.warning("=" * 60)
        logger.warning("PRODUCTION CONFIGURATION WARNINGS")
        logger.warning("=" * 60)
        for i, w in enumerate(warnings, 1):
            logger.warning("  [%d] %s", i, w)

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
