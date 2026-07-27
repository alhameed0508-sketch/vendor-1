"""Tests for production reliability and tamper-evidence controls."""

from unittest.mock import Mock

from ingest.kafka_consumer import TransactionConsumer
from repositories.audit_repository import AuditRepository
from services.audit_service import AuditService
from core.config import Settings
from core.production_validator import validate_or_die
import pytest


def test_audit_hash_chain_verifies_and_detects_tampering():
    repository = AuditRepository()
    service = AuditService(repository)
    first = service.log("ALERT_VIEWED", "investigator", "ALT-1", "opened")
    second = service.log("ALERT_UPDATED", "supervisor", "ALT-1", "reviewed")

    assert first["previous_hash"] == ""
    assert second["previous_hash"] == first["entry_hash"]
    assert service.verify_integrity()["valid"] is True

    repository._entries[0]["details"] = "tampered"
    verification = service.verify_integrity()
    assert verification["valid"] is False
    assert verification["reason"] == "entry_hash"


def test_kafka_batch_reports_failure_without_dependencies():
    consumer = TransactionConsumer()
    assert consumer._process_batch([{"txn_id": "T1"}], None, None, None) is False


def test_kafka_batch_success_is_commit_safe():
    consumer = TransactionConsumer()
    pipeline = Mock()
    pipeline.run.return_value = []
    alert_repo = Mock()
    dataset_repo = Mock()
    dataset_repo.get.return_value = {"accounts": [{"account_id": "A1"}]}

    result = consumer._process_batch(
        [{"txn_id": "T1", "from_account": "A1", "to_account": "A2"}],
        pipeline,
        alert_repo,
        dataset_repo,
    )
    assert result is True
    assert consumer.get_status()["batches_processed"] == 1


def test_kafka_dedupe_cache_is_bounded():
    consumer = TransactionConsumer()
    consumer._dedupe_capacity = 2
    consumer._remember_txn_id("T1")
    consumer._remember_txn_id("T2")
    consumer._remember_txn_id("T3")

    assert "T1" not in consumer._seen_txn_ids
    assert consumer._seen_txn_ids == {"T2", "T3"}


def test_production_validator_rejects_plaintext_transports():
    settings = Settings(
        ENV="production",
        AUTH_ENABLED=True,
        JWT_SECRET="a" * 48,
        NEO4J_PASSWORD="b" * 24,
        NEO4J_TLS_ENABLED=False,
        KAFKA_ENABLED=True,
        KAFKA_SECURITY_PROTOCOL="PLAINTEXT",
        POSTGRES_URL="postgresql://user:pass@postgres/mulecatch",
        REDIS_URL="redis://redis:6379/0",
        MODEL_VERSION="approved-2026-07",
        RULE_VERSION="rules-2026.1",
    )
    with pytest.raises(SystemExit):
        validate_or_die(settings)


def test_production_validator_accepts_governed_tls_configuration():
    settings = Settings(
        ENV="production",
        AUTH_ENABLED=True,
        JWT_SECRET="a" * 48,
        NEO4J_PASSWORD="b" * 24,
        NEO4J_TLS_ENABLED=True,
        KAFKA_ENABLED=True,
        KAFKA_SECURITY_PROTOCOL="SSL",
        KAFKA_SSL_CAFILE="/secrets/ca.crt",
        POSTGRES_URL=("postgresql://user:pass@postgres/mulecatch?sslmode=verify-full"),
        REDIS_URL="rediss://redis:6379/0",
        MODEL_VERSION="approved-2026-07",
        RULE_VERSION="rules-2026.1",
        CORS_ORIGINS=["https://mulecatch.bank.example"],
    )
    validate_or_die(settings)
