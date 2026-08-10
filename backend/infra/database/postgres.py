"""
PostgreSQL connection manager using SQLAlchemy Core.
Provides engine creation, table metadata, and schema bootstrap.
"""

import hashlib
import json
import logging
from functools import lru_cache

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

metadata = MetaData()

# ── Table definitions ────────────────────────────────────────────────────────

str_reports = Table(
    "str_reports",
    metadata,
    Column("str_id", Text, primary_key=True),
    Column("alert_ids", JSONB, nullable=False, server_default="[]"),
    Column("account_ids", JSONB, nullable=False, server_default="[]"),
    Column("status", Text, nullable=False, server_default="DRAFT"),
    Column("narrative", Text, nullable=False, server_default=""),
    Column("total_amount", Float, nullable=False, server_default="0"),
    Column("risk_score", Float, nullable=False, server_default="0"),
    Column("gnn_score", Float),
    Column("reason_codes", JSONB, nullable=False, server_default="[]"),
    Column("reporting_entity", Text, nullable=False, server_default=""),
    Column("reporting_ifsc", Text, nullable=False, server_default=""),
    Column("prepared_by", Text, nullable=False, server_default=""),
    Column("approved_by", Text),
    Column("fiu_reference", Text),
    Column("fiu_format_version", Text),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
    Column("submitted_at", DateTime(timezone=True)),
    Column("acknowledged_at", DateTime(timezone=True)),
)

audit_logs = Table(
    "audit_logs",
    metadata,
    Column("log_id", Text, primary_key=True),
    Column("action", Text, nullable=False),
    Column("username", Text, nullable=False, server_default=""),
    Column("alert_id", Text),
    Column("details", Text),
    Column("previous_hash", Text, nullable=False, server_default=""),
    Column("entry_hash", Text, nullable=False, server_default=""),
    Column("timestamp", DateTime(timezone=True)),
)

escalations = Table(
    "escalations",
    metadata,
    Column("escalation_id", Text, primary_key=True),
    Column("alert_id", Text, nullable=False),
    Column("reason", Text, nullable=False, server_default=""),
    Column("priority", Text, nullable=False, server_default="MEDIUM"),
    Column("status", Text, nullable=False, server_default="PENDING"),
    Column("user_id", Text),
    Column("resolved_by", Text),
    Column("resolved_action", Text),
    Column("resolution_notes", Text),
    Column("escalated_at", DateTime(timezone=True)),
    Column("resolved_at", DateTime(timezone=True)),
)

screening_results = Table(
    "screening_results",
    metadata,
    Column("result_id", Text, primary_key=True),
    Column("account_id", Text, nullable=False),
    Column("screened_name", Text, nullable=False, server_default=""),
    Column("matches", JSONB, nullable=False, server_default="[]"),
    Column("match_count", Integer, nullable=False, server_default="0"),
    Column("highest_confidence", Float, nullable=False, server_default="0"),
    Column("status", Text, nullable=False, server_default="CLEAR"),
    Column("screened_at", DateTime(timezone=True)),
)

screening_watchlist = Table(
    "screening_watchlist",
    metadata,
    Column("entry_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("aliases", JSONB, nullable=False, server_default="[]"),
    Column("identifiers", JSONB, nullable=False, server_default="[]"),
    Column("entity_type", Text, nullable=False, server_default="INDIVIDUAL"),
    Column("countries", JSONB, nullable=False, server_default="[]"),
    Column("risk_category", Text, nullable=False, server_default="SANCTIONS"),
    Column("source", Text, nullable=False, server_default=""),
    Column("date_of_birth", Text),
    Column("added_date", DateTime(timezone=True)),
)

onboarding_assessments = Table(
    "onboarding_assessments",
    metadata,
    Column("assessment_id", Text, primary_key=True),
    Column("account_id", Text, nullable=False),
    Column("risk_score", Float, nullable=False, server_default="0"),
    Column("risk_level", Text, nullable=False, server_default="LOW"),
    Column("signals", JSONB, nullable=False, server_default="[]"),
    Column("reason_codes", JSONB, nullable=False, server_default="[]"),
    Column("recommendation", Text, nullable=False, server_default=""),
    Column("entity_resolution", JSONB, nullable=False, server_default="{}"),
    Column("assessed_at", DateTime(timezone=True)),
)

identity_profiles = Table(
    "identity_profiles",
    metadata,
    Column("entity_id", Text, primary_key=True),
    Column("full_name", Text, nullable=False, server_default=""),
    Column("phone_hash", Text, nullable=False, server_default=""),
    Column("email_hash", Text, nullable=False, server_default=""),
    Column("postal_address", Text, nullable=False, server_default=""),
    Column("government_id_hash", Text, nullable=False, server_default=""),
    Column("device_fingerprint", Text, nullable=False, server_default=""),
    Column("updated_at", DateTime(timezone=True)),
)
Index("idx_identity_phone", identity_profiles.c.phone_hash)
Index("idx_identity_email", identity_profiles.c.email_hash)
Index("idx_identity_gov", identity_profiles.c.government_id_hash)
Index("idx_identity_device", identity_profiles.c.device_fingerprint)

kpi_snapshots = Table(
    "kpi_snapshots",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("total_alerts", Integer, nullable=False, server_default="0"),
    Column("false_positives_avoided", Integer, nullable=False, server_default="0"),
    Column("hours_saved", Float, nullable=False, server_default="0"),
    Column("fraud_prevented_inr", Float, nullable=False, server_default="0"),
    Column("investigation_time_reduction_pct", Integer, nullable=False, server_default="75"),
    Column("strs_filed", Integer, nullable=False, server_default="0"),
    Column("snapshot_at", DateTime(timezone=True)),
)

monthly_trends = Table(
    "monthly_trends",
    metadata,
    Column("month", Text, primary_key=True),
    Column("alerts", Integer, nullable=False, server_default="0"),
    Column("prevented", Float, nullable=False, server_default="0"),
    Column("hours", Float, nullable=False, server_default="0"),
)

detection_breakdown = Table(
    "detection_breakdown",
    metadata,
    Column("pattern", Text, primary_key=True),
    Column("count", Integer, nullable=False, server_default="0"),
)

users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("role", Text, nullable=False, server_default="READONLY"),
    Column("display_name", Text, nullable=False, server_default=""),
    Column("branch", Text, nullable=False, server_default=""),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
    Column("last_login", DateTime(timezone=True)),
)

failed_logins_table = Table(
    "failed_logins",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", Text, nullable=False),
    Column("attempt_time", DateTime(timezone=True)),
    Column("ip_address", Text, nullable=False, server_default="unknown"),
)


# ── Engine management ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_engine(postgres_url: str) -> Engine:
    """Create and cache a SQLAlchemy engine."""
    engine = create_engine(
        postgres_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    logger.info("PostgreSQL engine created: %s", postgres_url.split("@")[-1])
    return engine


def ensure_tables(engine: Engine) -> None:
    """Apply idempotent additive schema changes under a cluster-wide lock."""
    # Every statement runs in one committed transaction. The advisory lock
    # serializes startup across replicas so create/alter/backfill operations
    # cannot race each other.
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(129743750)"))
        metadata.create_all(conn)
        # create_all does not add columns to an existing installation.
        conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS previous_hash TEXT NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entry_hash TEXT NOT NULL DEFAULT ''"))
        conn.execute(
            text(
                "ALTER TABLE onboarding_assessments ADD COLUMN IF NOT EXISTS "
                "entity_resolution JSONB NOT NULL DEFAULT '{}'"
            )
        )
        _backfill_legacy_audit_chain(conn)
        row = conn.execute(text("SELECT COUNT(*) FROM kpi_snapshots")).scalar()
        if row == 0:
            conn.execute(
                kpi_snapshots.insert().values(
                    total_alerts=0,
                    false_positives_avoided=0,
                    hours_saved=0,
                    fraud_prevented_inr=0,
                    strs_filed=0,
                )
            )
    logger.info("PostgreSQL tables ensured.")


def _backfill_legacy_audit_chain(conn) -> None:
    """Hash legacy audit rows once; reject mixed chains as unsafe.

    Rows created before hash-chain support have both hash columns empty.
    A mixture of hashed and unhashed rows can indicate an interrupted migration
    or tampering and therefore requires operator intervention.
    """
    conn.execute(text("SELECT pg_advisory_xact_lock(129743751)"))
    rows = conn.execute(
        audit_logs.select().order_by(audit_logs.c.timestamp.asc(), audit_logs.c.log_id.asc())
    ).fetchall()
    if not rows:
        return

    hashed = [bool(row._mapping.get("entry_hash")) for row in rows]
    if all(hashed):
        return
    if any(hashed):
        raise RuntimeError("Audit chain contains mixed hashed and legacy rows; manual integrity review is required.")

    previous_hash = ""
    for row in rows:
        values = dict(row._mapping)
        timestamp = values.get("timestamp")
        timestamp_iso = timestamp.isoformat() if timestamp else ""
        payload = {
            "log_id": values["log_id"],
            "action": values.get("action", ""),
            "user": values.get("username", ""),
            "alert_id": values.get("alert_id"),
            "details": values.get("details"),
            "timestamp": timestamp_iso,
            "previous_hash": previous_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        entry_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        conn.execute(
            audit_logs.update()
            .where(audit_logs.c.log_id == values["log_id"])
            .values(previous_hash=previous_hash, entry_hash=entry_hash)
        )
        previous_hash = entry_hash

    logger.warning(
        "Backfilled tamper-evident hashes for %d legacy audit rows. "
        "Pre-migration history remains outside hash-chain assurance.",
        len(rows),
    )
