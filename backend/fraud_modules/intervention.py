"""Simulated intervention gateway.

No bank system is connected. A hold or verification request is recorded in the audit chain so the
workflow can be shown end to end, and the response says plainly that nothing was done to the account.
"""

from typing import Dict

from core.exceptions import ValidationError
from services.audit_service import AuditService

SIMULATED_LABEL = "SIMULATED: no bank system connected"
KINDS = ("HOLD", "VERIFY")


def request_intervention(audit: AuditService, kind: str, account_id: str, investigation: Dict, user: str) -> Dict:
    if kind not in KINDS:
        raise ValidationError(f"Unknown intervention '{kind}'. Use one of: {', '.join(KINDS)}")
    audit.log(
        "INTERVENTION_REQUESTED",
        user,
        investigation["source_id"],
        f"{SIMULATED_LABEL}; kind={kind} account={account_id}",
    )
    return {
        "simulated": True,
        "label": SIMULATED_LABEL,
        "status": "RECORDED_ONLY",
        "kind": kind,
        "account_id": account_id,
    }
