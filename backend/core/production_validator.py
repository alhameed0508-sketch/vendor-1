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


def validate_or_die(settings) -> None:
    """Validate production configuration. Exits the process if violations found."""
    violations: List[str] = []

    # JWT secret must not be a default
    if settings.jwt_secret in _DEFAULT_SECRETS:
        violations.append(
            "JWT_SECRET is set to a default placeholder. "
            "Set a strong, unique secret for production."
        )

    # Neo4j password must not be a default
    if settings.neo4j_password in _DEFAULT_SECRETS:
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
