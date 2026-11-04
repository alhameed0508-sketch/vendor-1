"""Shared types: what every engine returns and what a unified decision looks like."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

WEAK, STRONG, DECISIVE, FAMILIARITY = "weak", "strong", "decisive", "familiarity"
KINDS = (WEAK, STRONG, DECISIVE, FAMILIARITY)

MULE, SESSION, BENEFICIARY, BEHAVIOUR = "mule_network", "session_device", "beneficiary_intent", "behaviour"
ENGINES = (MULE, SESSION, BENEFICIARY, BEHAVIOUR)
ENGINE_LABELS = {
    MULE: "Mule network (core)",
    SESSION: "Session & device trust",
    BENEFICIARY: "Payment intent & beneficiary",
    BEHAVIOUR: "Behaviour baseline",
}

# Reasons that are evidence of fraud, not just of something new or unusual. A payment is held for review
# only when at least one of these is present (strong or decisive, strength >= EVIDENCE_MIN_STRENGTH).
# New payee (BI05/BI06), big amount (BH01), burst (BH02), odd hour or city (BH03/BH04), new device (SD01) and
# typing rhythm (SD10) are context: they can ask for a step-up, never a hold on their own.
EVIDENCE_CODES = frozenset(
    {
        "MN01",
        "MN02",
        "MN03",  # mule network (core)
        "SD02",
        "SD03",
        "SD04",
        "SD05",
        "SD06",
        "SD07",
        "SD08",
        "SD09",  # session & device
        "BI01",
        "BI02",
        "BI03",
        "BI07",
        "BI08",
        "BI10",  # payment intent & beneficiary
    }
)
EVIDENCE_MIN_STRENGTH = 0.35

APPROVE, STEP_UP, REVIEW, DECLINE = "APPROVE", "STEP_UP", "REVIEW", "DECLINE"
BANDS_ORDER = (APPROVE, STEP_UP, REVIEW, DECLINE)
BAND_ACTIONS = {
    APPROVE: "Let the payment through.",
    STEP_UP: "Ask for extra verification: show the payee's name, re-enter the PIN, warn about scams.",
    REVIEW: "Hold for a human reviewer before the money leaves, as the bank's policy allows.",
    DECLINE: "Decline under the bank's policy.",
}


@dataclass(frozen=True)
class Reason:
    code: str
    text: str
    strength: float  # 0..1 before familiarity dampening
    kind: str  # weak | strong | decisive | familiarity

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown reason kind {self.kind}")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("reason strength must be within 0..1")


@dataclass(frozen=True)
class EngineResult:
    engine: str
    reasons: Tuple[Reason, ...] = ()
    data_available: bool = True  # False when the event carries nothing this engine can read
    features: Dict[str, float] = field(default_factory=dict)
    note: str = ""

    def score(self, familiarity: float = 0.0) -> float:
        """Noisy-OR of the reasons. Weak reasons are dampened by familiarity; the rest are not."""
        keep = 1.0
        for r in self.reasons:
            if r.kind == FAMILIARITY:
                continue
            s = r.strength * (1.0 - familiarity) if r.kind == WEAK else r.strength
            keep *= 1.0 - s
        return round(1.0 - keep, 4)

    @property
    def decisive(self) -> bool:
        return any(r.kind == DECISIVE for r in self.reasons)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Decision:
    decision_id: str
    txn_id: str
    customer_id: str
    beneficiary_id: str
    amount: float
    score: int
    band: str
    confidence: float
    engines: Dict[str, float]
    contributions: Dict[str, float]  # points of the 0-100 score per engine / factor
    reasons: List[Dict]
    explanation: Dict
    source: str
    event_time: str
    decided_at: str
    latency_ms: float
    model_version: str
    committed: bool
    label: Optional[str] = None  # ground truth for synthetic events only (never used for scoring)
    outcome: Optional[str] = None
    outcome_note: str = ""
    outcome_by: str = ""
    outcome_at: Optional[str] = None

    def to_dict(self, full: bool = True) -> Dict:
        data = asdict(self)
        if not full:
            for key in ("explanation", "contributions"):
                data.pop(key, None)
            data["reasons"] = data["reasons"][:3]
        return data
