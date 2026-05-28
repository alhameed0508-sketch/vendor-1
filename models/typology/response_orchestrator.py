"""
Response Orchestrator — maps mule typology to operational response actions.

Each typology demands a different investigation urgency, notification set,
and remediation strategy. The orchestrator produces an ordered list of
ResponseAction objects that downstream systems (case management, alerting,
notification) can consume.

Mapping (from MuleCatch product spec):
  DECEIVER  -> Block + law enforcement + flag identity (IMMEDIATE, P1)
  PEDDLER   -> Freeze + supervisor + interview request  (IMMEDIATE, P2)
  ACCOMPLICE -> Enhanced monitoring + friction + escalate (HIGH, P3)
  CHUMP     -> Intervene + educate + freeze + contact    (HIGH, P2)
  VICTIM    -> Lock + customer notify + law enforcement   (IMMEDIATE, P1)
"""

from dataclasses import dataclass
from typing import List, Tuple

from models.typology.mule_classifier import MuleTypology, TypologyResult


@dataclass(frozen=True)
class ResponseAction:
    """Single immutable response action to execute."""

    action_type: str  # BLOCK, FREEZE, MONITOR, INTERVENE, LOCK
    urgency: str  # IMMEDIATE, HIGH, MEDIUM, LOW
    notification_targets: Tuple[str, ...]
    investigation_priority: int  # 1-5 (1 = highest)
    description: str


def _deceiver_actions(result: TypologyResult) -> List[ResponseAction]:
    """DECEIVER — block, report, flag synthetic identity elements."""
    return [
        ResponseAction(
            action_type="BLOCK",
            urgency="IMMEDIATE",
            notification_targets=("law_enforcement", "compliance_officer"),
            investigation_priority=1,
            description=(
                f"Block account {result.account_id} — professional mule with "
                f"synthetic identity indicators (confidence {result.confidence:.2f})"
            ),
        ),
        ResponseAction(
            action_type="REPORT",
            urgency="IMMEDIATE",
            notification_targets=("law_enforcement", "fiu_ind"),
            investigation_priority=1,
            description=(
                "File STR with FIU-IND and notify law enforcement — "
                "suspected synthetic identity fraud"
            ),
        ),
        ResponseAction(
            action_type="FLAG_IDENTITY",
            urgency="IMMEDIATE",
            notification_targets=("identity_verification_team",),
            investigation_priority=1,
            description=(
                "Flag identity elements (PAN, Aadhaar, phone, email) for "
                "cross-reference against known synthetic identity databases"
            ),
        ),
    ]


def _peddler_actions(result: TypologyResult) -> List[ResponseAction]:
    """PEDDLER — freeze, escalate to supervisor, request interview."""
    return [
        ResponseAction(
            action_type="FREEZE",
            urgency="IMMEDIATE",
            notification_targets=("supervisor", "compliance_officer"),
            investigation_priority=2,
            description=(
                f"Freeze account {result.account_id} — recruited mule showing "
                f"behavioral inflection (confidence {result.confidence:.2f})"
            ),
        ),
        ResponseAction(
            action_type="ESCALATE",
            urgency="IMMEDIATE",
            notification_targets=("supervisor",),
            investigation_priority=2,
            description="Escalate to supervisor for manual review of inflection point",
        ),
        ResponseAction(
            action_type="INTERVENE",
            urgency="HIGH",
            notification_targets=("customer", "branch_manager"),
            investigation_priority=2,
            description=(
                "Request in-person or video account holder interview to assess "
                "whether the customer has been recruited as a mule"
            ),
        ),
    ]


def _accomplice_actions(result: TypologyResult) -> List[ResponseAction]:
    """ACCOMPLICE — enhanced monitoring, progressive friction, conditional escalation."""
    return [
        ResponseAction(
            action_type="MONITOR",
            urgency="HIGH",
            notification_targets=("surveillance_team",),
            investigation_priority=3,
            description=(
                f"Enable enhanced transaction monitoring for {result.account_id} — "
                f"progressive structuring detected (confidence {result.confidence:.2f})"
            ),
        ),
        ResponseAction(
            action_type="FRICTION",
            urgency="HIGH",
            notification_targets=("digital_channels_team",),
            investigation_priority=3,
            description=(
                "Apply progressive friction: additional authentication steps, "
                "transfer delays, and beneficiary verification for outgoing payments"
            ),
        ),
        ResponseAction(
            action_type="ESCALATE",
            urgency="MEDIUM",
            notification_targets=("supervisor", "compliance_officer"),
            investigation_priority=3,
            description=(
                "Escalate to compliance after pattern confirmation — "
                "await 3 additional structuring events before STR filing"
            ),
        ),
    ]


def _chump_actions(result: TypologyResult) -> List[ResponseAction]:
    """CHUMP — intervene, educate, freeze, contact customer."""
    return [
        ResponseAction(
            action_type="INTERVENE",
            urgency="HIGH",
            notification_targets=("customer",),
            investigation_priority=2,
            description=(
                f"Send educational notification to {result.account_id} — "
                f"unwitting mule behavior detected (confidence {result.confidence:.2f})"
            ),
        ),
        ResponseAction(
            action_type="FREEZE",
            urgency="HIGH",
            notification_targets=("customer", "branch_manager"),
            investigation_priority=2,
            description=(
                "Freeze account pending customer contact — "
                "protect customer from further exploitation"
            ),
        ),
        ResponseAction(
            action_type="CONTACT",
            urgency="HIGH",
            notification_targets=("customer", "customer_support"),
            investigation_priority=2,
            description=(
                "Initiate direct customer contact via registered phone/email — "
                "verify awareness and intent of recent transactions"
            ),
        ),
    ]


def _victim_actions(result: TypologyResult) -> List[ResponseAction]:
    """VICTIM — lock, notify customer, alert law enforcement."""
    return [
        ResponseAction(
            action_type="LOCK",
            urgency="IMMEDIATE",
            notification_targets=("customer", "fraud_operations"),
            investigation_priority=1,
            description=(
                f"Lock account {result.account_id} — account takeover detected "
                f"(confidence {result.confidence:.2f})"
            ),
        ),
        ResponseAction(
            action_type="NOTIFY",
            urgency="IMMEDIATE",
            notification_targets=("customer",),
            investigation_priority=1,
            description=(
                "Send immediate multi-channel notification to account holder — "
                "possible unauthorized access and transfers"
            ),
        ),
        ResponseAction(
            action_type="REPORT",
            urgency="IMMEDIATE",
            notification_targets=("law_enforcement", "cyber_cell"),
            investigation_priority=1,
            description=(
                "Alert law enforcement cyber cell — "
                "suspected account takeover with fund diversion"
            ),
        ),
    ]


_ACTION_MAP = {
    MuleTypology.DECEIVER: _deceiver_actions,
    MuleTypology.PEDDLER: _peddler_actions,
    MuleTypology.ACCOMPLICE: _accomplice_actions,
    MuleTypology.CHUMP: _chump_actions,
    MuleTypology.VICTIM: _victim_actions,
}


class ResponseOrchestrator:
    """Maps typology classification results to ordered response actions."""

    def orchestrate_response(
        self, typology_result: TypologyResult
    ) -> List[ResponseAction]:
        """Produce a list of response actions for the given classification.

        Args:
            typology_result: Output of MuleTypologyClassifier.classify().

        Returns:
            Ordered list of ResponseAction objects (most urgent first).
        """
        handler = _ACTION_MAP.get(typology_result.predicted_type)
        if handler is None:
            return [
                ResponseAction(
                    action_type="MONITOR",
                    urgency="LOW",
                    notification_targets=("surveillance_team",),
                    investigation_priority=5,
                    description=(
                        f"Unknown typology for {typology_result.account_id} — "
                        "default to enhanced monitoring"
                    ),
                ),
            ]
        return handler(typology_result)
