"""Append-only, hash-chained audit trail. PostgreSQL is authoritative; nothing here is ever updated."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from intentlock.db.models import AuditEvent, utcnow
from intentlock.domain import canonical_json, sha256_hex

GENESIS_HASH = "0" * 64
_CHAIN_LOCK_KEY = 482913077


def _hash(prev_hash: str, ev: AuditEvent) -> str:
    return sha256_hex(
        canonical_json(
            {
                "prev": prev_hash,
                "id": str(ev.id),
                "correlation_id": ev.correlation_id,
                "aggregate": [ev.aggregate_type, ev.aggregate_id],
                "actor": [ev.actor_type, ev.actor_id],
                "action": ev.action,
                "source_reference": ev.source_reference,
                "data": ev.event_data,
                "at": ev.created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            }
        )
    )


def record(s: Session, *, correlation_id, aggregate_type: str, aggregate_id, action: str, actor_type: str = "system",
           actor_id=None, data: dict | None = None, source_reference: str = "") -> AuditEvent:  # fmt: skip
    """Append one event inside the caller's transaction."""
    if s.get_bind().dialect.name == "postgresql":
        s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK_KEY})  # one writer at a time
    prev = s.scalar(select(AuditEvent.payload_hash).order_by(AuditEvent.seq.desc()).limit(1)) or GENESIS_HASH
    ev = AuditEvent(
        id=uuid.uuid4(),
        correlation_id=str(correlation_id),
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        actor_type=actor_type,
        actor_id=str(actor_id) if actor_id is not None else None,
        action=action,
        source_reference=source_reference,
        event_data=data or {},
        prev_hash=prev,
        created_at=utcnow(),
    )
    ev.payload_hash = _hash(prev, ev)
    s.add(ev)
    s.flush()
    return ev


def timeline(s: Session, correlation_id) -> list[dict]:
    rows = s.scalars(select(AuditEvent).where(AuditEvent.correlation_id == str(correlation_id)).order_by(AuditEvent.seq)).all()
    return [
        {
            "seq": r.seq,
            "id": str(r.id),
            "at": r.created_at.isoformat(),
            "action": r.action,
            "actor_type": r.actor_type,
            "aggregate_type": r.aggregate_type,
            "aggregate_id": r.aggregate_id,
            "source_reference": r.source_reference,
            "data": r.event_data,
            "hash": r.payload_hash,
        }
        for r in rows
    ]


def verify_chain(s: Session) -> tuple[bool, int]:
    """Recompute every hash. Returns (intact, number of events)."""
    prev, count = GENESIS_HASH, 0
    for ev in s.scalars(select(AuditEvent).order_by(AuditEvent.seq)):
        if ev.prev_hash != prev or ev.payload_hash != _hash(prev, ev):
            return False, count
        prev, count = ev.payload_hash, count + 1
    return True, count


def head_hash(s: Session) -> str:
    return s.scalar(select(AuditEvent.payload_hash).order_by(AuditEvent.seq.desc()).limit(1)) or GENESIS_HASH
