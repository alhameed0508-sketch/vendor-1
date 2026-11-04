"""
Return-claim service — fraud signals on returns, and the package a bank can use.

Every read re-derives the assessment from the claim as stored, so a score can never drift from its evidence.
The assessment is a recommendation: only a person records a review, and nothing here refunds or blocks.
"""

import hashlib
import hmac
import logging
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional

from core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from genai.base import LLMProvider
from return_fraud.assess import assess_claim
from return_fraud.detectors import judge_with_provider, photo_hash, photo_too_large, read_exif, read_pdf_meta
from return_fraud.evidence import build_package, build_pdf, category, narrative, verify_package
from return_fraud.seed import SCENARIOS, seed_claims
from return_fraud.signals import SIGNAL_NAMES
from services.audit_service import AuditService

logger = logging.getLogger(__name__)

TIERS = ("BLOCK", "CHALLENGE", "VERIFY", "APPROVE")
FIRST_SEQUENCE = 2001
CARRIER_FAULT_EVENTS = ("lost_in_transit", "damaged_in_transit")
SCENARIO_BLURBS = {
    "legit": "An ordinary return. Every check agrees with the customer.",
    "receipt_manipulation": "One loud signal, an edited receipt. It cannot block on its own, so a person looks.",
    "exif_mismatch": "The photo predates delivery and was edited, and the image contradicts the claim.",
    "ring": "Five customers share a device, an address and a card, and one stolen receipt.",
    "wardrobing": "A dress worn to an event, then returned the next day.",
    "friendly_fraud": "Says the parcel never came. The carrier has a signed delivery.",
    "inr_carrier_fault": "A large claim where the carrier damaged the parcel, so the score is eased down.",
}


def _signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class ReturnClaimService:
    def __init__(
        self,
        repo,
        audit: AuditService,
        provider: Optional[LLMProvider],
        now_fn: Callable[[], datetime],
        webhook_secret: str = "",
    ):
        self._repo = repo
        self._audit = audit
        self._provider = provider
        self._now = now_fn
        self._secret = webhook_secret
        self._write_lock = threading.Lock()

    # ── Reads ────────────────────────────────────────────────────────────

    def _all(self) -> List[Dict]:
        return self._repo.find_all()

    def _find(self, claim_id: str) -> Dict:
        claim = self._repo.find_by_id(claim_id)
        if claim is None:
            raise NotFoundError("Return claim", claim_id)
        return claim

    def _view(self, claim: Dict, pool: List[Dict]) -> Dict:
        assessment = assess_claim(claim, pool)
        return {**assessment, "review": claim.get("review")}

    @staticmethod
    def _explained(view: Dict) -> Dict:
        return {**view, "narrative": narrative(view), "dispute_category": category(view)}

    def list_claims(self) -> Dict:
        pool = self._all()
        rows = []
        for c in pool:
            v = self._view(c, pool)
            rows.append(
                {
                    **v["claim"],
                    "tier": v["fusion"]["tier"],
                    "score": v["fusion"]["score"],
                    "reviewed": c.get("review") is not None,
                    "headline": c.get("headline", True),
                }
            )
        rows.sort(key=lambda r: -r["score"])
        return {"as_of": self._now().isoformat(), "claims": rows, "summary": self._summary(rows)}

    @staticmethod
    def _summary(rows: List[Dict]) -> Dict:
        return {
            "total": len(rows),
            "by_tier": {t: sum(1 for r in rows if r["tier"] == t) for t in TIERS},
            "needs_review": sum(1 for r in rows if r["tier"] != "APPROVE" and not r["reviewed"]),
            "amount_in_question": sum(r["amount"] for r in rows if r["tier"] != "APPROVE"),
        }

    def get_claim(self, claim_id: str) -> Dict:
        claim = self._find(claim_id)
        view = self._explained(self._view(claim, self._all()))
        return {
            **view,
            "claim": {**view["claim"], "has_photo": "exif" in claim, "has_receipt": bool(claim.get("receipt_pdf"))},
        }

    def overview(self) -> Dict:
        """The one-screen picture: where claims stand, which scenarios exist, and how far each check reaches."""
        pool = self._all()
        views = [self._view(c, pool) for c in pool]
        rows = [
            {
                **v["claim"],
                "tier": v["fusion"]["tier"],
                "score": v["fusion"]["score"],
                "reviewed": v["review"] is not None,
                "headline": c.get("headline", True),
            }
            for c, v in zip(pool, views)
        ]
        coverage = {
            n: {
                "ran": sum(1 for v in views for s in v["signals"] if s["name"] == n and s["available"]),
                "fired": sum(
                    1 for v in views for s in v["signals"] if s["name"] == n and s["available"] and s["score"] > 30
                ),
            }
            for n in SIGNAL_NAMES
        }
        rings: Dict[str, Dict] = {}
        for v in views:
            graph = next(s for s in v["signals"] if s["name"] == "graph")
            members = graph["detail"].get("ring_claims")
            if members and graph["score"] > 0:
                rings[members[0]] = {"claims": members, "customers": graph["detail"]["ring_size"]}
        by_id = {r["claim_id"]: r for r in rows}
        return {
            "as_of": self._now().isoformat(),
            "summary": self._summary(rows),
            "signal_coverage": coverage,
            "rings": [{**r, "amount": sum(by_id[c]["amount"] for c in r["claims"])} for r in rings.values()],
            "scenarios": [
                {
                    "scenario": s,
                    "blurb": SCENARIO_BLURBS[s],
                    "claim_id": next(
                        (r["claim_id"] for r in rows if r["scenario"] == s and r.get("headline", True)), None
                    ),
                    **next(
                        (
                            {"tier": r["tier"], "score": r["score"]}
                            for r in rows
                            if r["scenario"] == s and r.get("headline", True)
                        ),
                        {},
                    ),
                }
                for s in SCENARIOS
            ],
        }

    # ── Writes ───────────────────────────────────────────────────────────

    def create(self, req, user_id: str) -> Dict:
        photo, receipt = req.photo_bytes(), req.receipt_bytes()
        if req.returned_at < req.delivered_at:
            raise ValidationError("A return cannot happen before delivery")
        data = req.model_dump(mode="json", exclude={"photo_b64", "receipt_pdf_b64", "history"})
        history = req.history.model_dump() if req.history else None
        # Untrusted files are parsed here, once and outside the write lock, never on a read.
        parsed = {}
        if photo is not None:
            parsed.update(exif=read_exif(photo), photo_phash=photo_hash(photo), photo_unchecked=photo_too_large(photo))
        if receipt is not None:
            parsed.update(receipt_pdf=receipt, receipt_meta=read_pdf_meta(receipt))
        with self._write_lock:
            claim_id = f"RC-{FIRST_SEQUENCE + self._repo.count()}"
            claim = {
                **data,
                "claim_id": claim_id,
                "scenario": "submitted",
                "currency": "INR",
                "carrier_fault": False,
                "carrier_events": [],
                "chargebacks": [],
                "history": history,
                "delivered_at": req.delivered_at.isoformat(),
                "returned_at": req.returned_at.isoformat(),
            }
            claim.update(parsed)
            # The only provider call a claim ever causes: scored once here, stored, and reused by every read.
            judgment = judge_with_provider(claim, self._provider)
            if judgment:
                claim["vlm_judgment"] = judgment
            self._repo.create(claim)
        self._audit.log("RETURN_CLAIM_CREATED", user_id, claim_id, f"amount={req.amount}")
        return self.get_claim(claim_id)

    def review(self, claim_id: str, outcome: str, notes: str, user_id: str) -> Dict:
        with self._write_lock:
            claim = self._find(claim_id)
            if claim.get("review"):
                raise ConflictError("Claim already reviewed", "A review is recorded once.")
            recommended = self._view(claim, self._all())["fusion"]["tier"]
            review = {
                "outcome": outcome,
                "notes": notes,
                "reviewed_by": user_id,
                "reviewed_at": self._now().isoformat(),
                "recommended_tier": recommended,
            }
            self._repo.update(claim_id, review=review)
        self._audit.log("RETURN_CLAIM_REVIEWED", user_id, claim_id, f"outcome={outcome} tier={recommended}")
        return self.get_claim(claim_id)

    # ── Evidence ─────────────────────────────────────────────────────────

    def package(self, claim_id: str, user_id: str) -> Dict:
        pkg = build_package(self._view(self._find(claim_id), self._all()), self._now().isoformat())
        self._audit.log("RETURN_PACKAGE_EXPORTED", user_id, claim_id, pkg["integrity"]["sha256"][:12])
        return {**pkg, "verification": verify_package(pkg)}

    def package_pdf(self, claim_id: str, user_id: str) -> bytes:
        pkg = self.package(claim_id, user_id)
        return build_pdf({k: v for k, v in pkg.items() if k != "verification"})

    # ── Webhooks ─────────────────────────────────────────────────────────

    def check_signature(self, body: bytes, signature: Optional[str], strict: bool) -> None:
        """Webhooks carry an HMAC of the raw body. Without a configured secret only non-production accepts them."""
        if not self._secret:
            if strict:
                raise AuthenticationError("Webhook secret is not configured")
            return
        if not signature or not hmac.compare_digest(signature, _signature(self._secret, body)):
            raise AuthenticationError("Webhook signature does not match")

    def carrier_event(self, event) -> Dict:
        with self._write_lock:
            claim = self._find(event.claim_id)
            entry = {
                "type": event.event,
                "at": event.occurred_at.isoformat(),
                "carrier": event.carrier,
                "tracking_id": event.tracking_id,
            }
            if any(e["type"] == entry["type"] and e["at"] == entry["at"] for e in claim["carrier_events"]):
                return {"accepted": True, "duplicate": True}
            self._repo.update(
                event.claim_id,
                carrier_events=[*claim["carrier_events"], entry],
                carrier_fault=claim["carrier_fault"] or event.event in CARRIER_FAULT_EVENTS,
            )
        self._audit.log("RETURN_CARRIER_EVENT", "carrier", event.claim_id, event.event)
        return {"accepted": True, "duplicate": False}

    def chargeback_event(self, event) -> Dict:
        with self._write_lock:
            claim = self._find(event.claim_id)
            entry = {
                "chargeback_id": event.chargeback_id,
                "status": event.status,
                "reason_code": event.reason_code,
                "amount": event.amount,
                "at": event.occurred_at.isoformat(),
            }
            if any(
                c["chargeback_id"] == entry["chargeback_id"] and c["status"] == entry["status"]
                for c in claim["chargebacks"]
            ):
                return {"accepted": True, "duplicate": True}
            self._repo.update(event.claim_id, chargebacks=[*claim["chargebacks"], entry])
        self._audit.log("RETURN_CHARGEBACK_EVENT", "bank", event.claim_id, f"{event.chargeback_id} {event.status}")
        return {"accepted": True, "duplicate": False}

    def seed_demo(self) -> None:
        for claim in seed_claims():
            self._repo.create(claim)
