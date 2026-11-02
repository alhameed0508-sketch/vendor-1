"""
Fraud complaint service — the bank's complaint desk under the RBI fraudulent-EBT directions.

Each complaint carries a hash-chained evidence list. Every read re-derives the clocks, the finding
and the compensation from that evidence, so the recommendation can never drift from what was filed.
The recommendation is never the decision: only a supervisor records one, once.
"""

import logging
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional

from complaints.case_view import build_view, desk_summary, summarize
from complaints.evidence import append
from complaints.narrative import write_narrative
from complaints.pdf import build_pack_pdf
from complaints.rules import format_inr
from complaints.seed import demo_cases
from core.exceptions import ConflictError, NotFoundError, ValidationError
from genai.base import LLMProvider
from services.audit_service import AuditService

logger = logging.getLogger(__name__)

FIRST_SEQUENCE = 101
MULE_ROLES = ("MULE", "AGGREGATOR")
ALERT_SCAN_LIMIT = 500
CHANNEL_LABELS = {"UPI": "UPI", "IMPS": "IMPS", "NEFT": "NEFT", "NETBANKING": "net banking",
                  "DEBIT_CARD": "debit card", "CREDIT_CARD": "credit card", "WALLET": "wallet"}
RULES_SOURCE = "RBI/2026-27/167 (24 June 2026): fraudulent electronic banking transactions, in force 1 January 2027"


class ComplaintService:
    """Business logic for fraud complaints: intake, evidence, recommendation, decision and evidence pack."""

    def __init__(self, repo, alert_repo, audit: AuditService, provider: Optional[LLMProvider],
                 now_fn: Callable[[], datetime]):
        self._repo = repo
        self._alert_repo = alert_repo
        self._audit = audit
        self._provider = provider
        self._now = now_fn
        self._write_lock = threading.Lock()  # one writer at a time, so ids and evidence chains never fork
        self._narratives: Dict[str, Dict] = {}  # keyed by the chain's last hash

    # ── Reads ────────────────────────────────────────────────────────────

    def list_cases(self) -> Dict:
        now = self._now()
        views = [build_view(c, now) for c in self._repo.find_all()]
        rows = sorted((summarize(v) for v in views), key=lambda r: (r["status"] != "OPEN", r["days_left"]))
        return {"as_of": now.isoformat(), "summary": desk_summary(views), "cases": rows}

    def get_case(self, complaint_id: str) -> Dict:
        return build_view(self._find(complaint_id), self._now())

    def narrative(self, complaint_id: str) -> Dict:
        view = self.get_case(complaint_id)
        chain = view["evidence"]
        key = chain[-1]["hash"]
        if key not in self._narratives:
            assessment = {**view["liability"], "reasons": view["finding"]["reasons"]}
            self._narratives[key] = write_narrative(chain, assessment, self._provider)
        return self._narratives[key]

    def pack(self, complaint_id: str, user_id: str) -> Dict:
        view = self.get_case(complaint_id)
        self._audit.log("COMPLAINT_PACK_EXPORTED", user_id, complaint_id, f"evidence={len(view['evidence'])}")
        return {**view, "narrative": self.narrative(complaint_id), "rules_source": RULES_SOURCE,
                "generated_at": self._now().isoformat(), "generated_by": user_id}

    def pack_pdf(self, complaint_id: str, user_id: str) -> bytes:
        return build_pack_pdf(self.pack(complaint_id, user_id))

    # ── Writes ───────────────────────────────────────────────────────────

    def create(self, fields: Dict, user_id: str) -> Dict:
        now = self._now()
        if datetime.fromisoformat(fields["reported_at"]) > now:
            raise ValidationError("The report time is in the future")
        with self._write_lock:
            complaint_id = f"FC-{now.year}-{FIRST_SEQUENCE + self._repo.count():06d}"
            chain = append([], at=fields["reported_at"], source="CUSTOMER", kind="complaint",
                           summary=f"Customer reported a {format_inr(fields['amount'])} "
                                   f"{CHANNEL_LABELS[fields['channel']]} payment as fraud",
                           data={"description": fields.get("description", "")}, submitted_by=user_id,
                           received_at=now.isoformat())
            chain = self._with_mule_check(chain, fields.get("beneficiary_account", ""), now)
            self._repo.create({**fields, "complaint_id": complaint_id, "status": "OPEN", "created_by": user_id,
                               "created_at": now.isoformat(), "evidence": chain, "decision": None})
        self._audit.log("COMPLAINT_CREATED", user_id, complaint_id, f"amount={fields['amount']}")
        return self.get_case(complaint_id)

    def add_evidence(self, complaint_id: str, item: Dict, user_id: str) -> Dict:
        now = self._now()
        if datetime.fromisoformat(item["at"]) > now:
            raise ValidationError("Evidence cannot describe an event in the future")
        with self._write_lock:
            case = self._find(complaint_id)
            if case["status"] != "OPEN":
                raise ConflictError("Complaint already decided", "Evidence closes when the decision is recorded.")
            chain = append(case["evidence"], **item, submitted_by=user_id, received_at=now.isoformat())
            self._repo.update(complaint_id, evidence=chain)
        self._audit.log("COMPLAINT_EVIDENCE_ADDED", user_id, complaint_id, f"{chain[-1]['id']} {item['kind']}")
        return self.get_case(complaint_id)

    def decide(self, complaint_id: str, outcome: str, customer_liability: int, notes: str, user_id: str) -> Dict:
        with self._write_lock:
            view = self.get_case(complaint_id)
            if view["status"] != "OPEN":
                raise ConflictError("Complaint already decided")
            if customer_liability > view["amount"]:
                raise ValidationError("Customer liability cannot exceed the disputed amount")
            if outcome == "ZERO_LIABILITY" and customer_liability:
                raise ValidationError("Zero liability means the customer pays nothing")
            recommended = view["liability"]
            decision = {
                "outcome": outcome, "customer_liability": customer_liability, "notes": notes,
                "decided_by": user_id, "decided_at": view["as_of"],
                "recommended_outcome": recommended["outcome"],
                "recommended_customer_liability": recommended["customer_liability"],
                # None when the rules leave the amount to bank policy, so there was no number to follow
                "followed_recommendation": None if recommended["customer_liability"] is None
                else customer_liability == recommended["customer_liability"],
                "within_time_limit": not view["deadlines"]["overdue"],
                "evidence_hash": view["evidence"][-1]["hash"],
            }
            self._repo.update(complaint_id, status="RESOLVED", decision=decision)
        self._audit.log("COMPLAINT_DECIDED", user_id, complaint_id, f"outcome={outcome} liability={customer_liability}")
        return self.get_case(complaint_id)

    def seed_demo(self) -> None:
        """Load the demo cases; the SIM-swap case points at a real mule from the current alerts, if any."""
        now = self._now()
        for spec in demo_cases(now, self._any_mule()):
            chain: List[Dict] = []
            for item in spec["evidence"]:
                chain = append(chain, **item)
            complaint_id = f"FC-{now.year}-{FIRST_SEQUENCE + self._repo.count():06d}"
            self._repo.create({**spec["fields"], "complaint_id": complaint_id, "status": "OPEN", "created_by": "demo",
                               "created_at": spec["fields"]["reported_at"], "evidence": chain, "decision": None})

    # ── Helpers ──────────────────────────────────────────────────────────

    def _find(self, complaint_id: str) -> Dict:
        case = self._repo.find_by_id(complaint_id)
        if not case:
            raise NotFoundError("Complaint", complaint_id)
        return case

    def _alerts(self) -> List[Dict]:
        try:
            return self._alert_repo.find_all(limit=ALERT_SCAN_LIMIT)
        except Exception as exc:  # a mule check must never block a complaint from being filed
            logger.warning("Mule check skipped, alerts unavailable: %s", exc)
            return []

    def _mule_nodes(self):
        for alert in sorted(self._alerts(), key=lambda a: a.get("risk_score", 0), reverse=True):
            for node in alert.get("nodes", []):
                if node.get("role") in MULE_ROLES:
                    yield {"alert_id": alert["alert_id"], "account_id": node["account_id"], "role": node["role"],
                           "risk_score": alert.get("risk_score"), "bank": node.get("bank", "")}

    def _any_mule(self) -> Optional[Dict]:
        return next(self._mule_nodes(), None)

    def _with_mule_check(self, chain: List[Dict], beneficiary: str, now: datetime) -> List[Dict]:
        match = next((m for m in self._mule_nodes() if beneficiary and m["account_id"] == beneficiary), None)
        if not match:
            return chain
        return append(chain, at=now.isoformat(), source="MULECATCH", kind="mule_match",
                      summary=f"Beneficiary {beneficiary} is a {match['role'].lower()} in MuleCatch alert {match['alert_id']}",
                      data=match, submitted_by="mulecatch", received_at=now.isoformat())
