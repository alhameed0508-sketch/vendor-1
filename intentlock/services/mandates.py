"""Mandate lifecycle: draft, confirm (lock), amend (new version), revoke. Confirmed versions never change."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from intentlock.db.models import Buyer, MandateVersion, PurchaseMandate, utcnow
from intentlock.domain import MandateSpec, MandateState
from intentlock.services import audit


class MandateError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@event.listens_for(MandateVersion, "before_update")
def _confirmed_versions_are_immutable(_mapper, _conn, target: MandateVersion) -> None:
    state = inspect(target)
    hist = state.attrs.confirmed_at.history
    previously = hist.deleted[0] if hist.deleted else (target.confirmed_at if not hist.has_changes() else None)
    locked = ("structured_mandate", "canonical_hash", "version", "confirmed_at", "confirmed_by")
    if previously is not None and any(state.attrs[name].history.has_changes() for name in locked):
        raise MandateError(409, "MANDATE_VERSION_IMMUTABLE", "A confirmed mandate version cannot be changed")


def get_or_create_buyer(s: Session, buyer_id: uuid.UUID | None) -> Buyer:
    buyer = s.get(Buyer, buyer_id) if buyer_id else None
    if buyer is None:
        buyer = Buyer(id=uuid.uuid4())
        s.add(buyer)
        s.commit()
    return buyer


def current_version(s: Session, mandate: PurchaseMandate) -> MandateVersion:
    return s.scalars(select(MandateVersion).where(MandateVersion.mandate_id == mandate.id, MandateVersion.version == mandate.current_version)).one()


def spec_of(version: MandateVersion) -> MandateSpec:
    return MandateSpec.model_validate(version.structured_mandate)


def effective_status(mandate: PurchaseMandate, spec: MandateSpec, now: datetime) -> str:
    return "EXPIRED" if mandate.status == "CONFIRMED" and now >= spec.expires_at else mandate.status


def state_of(mandate: PurchaseMandate, version: MandateVersion) -> MandateState:
    return MandateState(mandate_id=str(mandate.id), version=version.version, status=mandate.status,
                        is_current_version=version.version == mandate.current_version and version.confirmed_at is not None)  # fmt: skip


def _check_new_spec(spec: MandateSpec, enabled_currency: str, now: datetime) -> None:
    if spec.currency != enabled_currency.upper():
        raise MandateError(422, "UNSUPPORTED_CURRENCY", f"This merchant takes payment in {enabled_currency.upper()} only")
    if spec.expires_at <= now:
        raise MandateError(422, "EXPIRY_IN_PAST", "The mandate expiry must be in the future")


def create_draft(s: Session, buyer: Buyer, original_request: str, spec: MandateSpec, source: str, enabled_currency: str) -> PurchaseMandate:
    _check_new_spec(spec, enabled_currency, utcnow())
    mandate = PurchaseMandate(id=uuid.uuid4(), buyer_id=buyer.id, original_request=original_request[:4000], source=source, current_version=1, status="DRAFT")
    s.add(mandate)
    s.flush()
    s.add(MandateVersion(mandate_id=mandate.id, version=1, structured_mandate=spec.model_dump(mode="json"), canonical_hash=spec.canonical_hash()))
    audit.record(s, correlation_id=mandate.id, aggregate_type="mandate", aggregate_id=mandate.id, action="MANDATE_DRAFTED",
                 actor_type="buyer", actor_id=buyer.id, data={"version": 1, "source": source, "hash": spec.canonical_hash()})  # fmt: skip
    s.commit()
    return mandate


def update_draft(s: Session, mandate: PurchaseMandate, spec: MandateSpec, buyer: Buyer, enabled_currency: str) -> PurchaseMandate:
    """Edit an unconfirmed draft, or start a new version of a confirmed mandate. Either way the buyer must confirm again."""
    _check_new_spec(spec, enabled_currency, utcnow())
    if mandate.status == "REVOKED":
        raise MandateError(409, "MANDATE_REVOKED", "A revoked mandate cannot be changed")
    version = current_version(s, mandate)
    if version.confirmed_at is None:
        version.structured_mandate = spec.model_dump(mode="json")
        version.canonical_hash = spec.canonical_hash()
        action = "MANDATE_DRAFT_EDITED"
    else:
        mandate.current_version += 1
        mandate.status = "DRAFT"
        s.add(MandateVersion(mandate_id=mandate.id, version=mandate.current_version, structured_mandate=spec.model_dump(mode="json"),
                             canonical_hash=spec.canonical_hash()))  # fmt: skip
        action = "MANDATE_VERSION_PROPOSED"
    audit.record(s, correlation_id=mandate.id, aggregate_type="mandate", aggregate_id=mandate.id, action=action, actor_type="buyer",
                 actor_id=buyer.id, data={"version": mandate.current_version, "hash": spec.canonical_hash()})  # fmt: skip
    s.commit()
    return mandate


def confirm(s: Session, mandate: PurchaseMandate, buyer: Buyer, expected_hash: str | None = None) -> PurchaseMandate:
    """Buyer confirmation locks the current version. `expected_hash` proves the buyer saw this exact mandate."""
    version = current_version(s, mandate)
    if mandate.status == "CONFIRMED" and version.confirmed_at is not None:
        return mandate
    if mandate.status != "DRAFT":
        raise MandateError(409, "MANDATE_NOT_DRAFT", f"A mandate in status {mandate.status} cannot be confirmed")
    spec = spec_of(version)
    if spec.canonical_hash() != version.canonical_hash:
        raise MandateError(409, "MANDATE_HASH_MISMATCH", "The stored mandate does not match its hash")
    if expected_hash and expected_hash != version.canonical_hash:
        raise MandateError(409, "MANDATE_CHANGED", "The mandate changed after it was shown; review it again before confirming")
    if spec.expires_at <= utcnow():
        raise MandateError(422, "EXPIRY_IN_PAST", "The mandate expiry must be in the future")
    version.confirmed_by = str(buyer.id)
    version.confirmed_at = utcnow()
    mandate.status = "CONFIRMED"
    audit.record(s, correlation_id=mandate.id, aggregate_type="mandate", aggregate_id=mandate.id, action="MANDATE_CONFIRMED", actor_type="buyer",
                 actor_id=buyer.id, data={"version": version.version, "hash": version.canonical_hash})  # fmt: skip
    s.commit()
    return mandate


def revoke(s: Session, mandate: PurchaseMandate, buyer: Buyer) -> PurchaseMandate:
    if mandate.status != "REVOKED":
        mandate.status = "REVOKED"
        audit.record(s, correlation_id=mandate.id, aggregate_type="mandate", aggregate_id=mandate.id, action="MANDATE_REVOKED",
                     actor_type="buyer", actor_id=buyer.id, data={"version": mandate.current_version})  # fmt: skip
        s.commit()
    return mandate


def view(s: Session, mandate: PurchaseMandate) -> dict:
    version = current_version(s, mandate)
    spec = spec_of(version)
    return {
        "mandate_id": str(mandate.id),
        "version": version.version,
        "status": effective_status(mandate, spec, utcnow()),
        "source": mandate.source,
        "original_request": mandate.original_request,
        "mandate": spec.model_dump(mode="json"),
        "canonical_hash": version.canonical_hash,
        "confirmed_at": version.confirmed_at.isoformat() if version.confirmed_at else None,
        "created_at": mandate.created_at.isoformat(),
    }
