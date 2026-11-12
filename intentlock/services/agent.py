"""An agent run: the assistant proposes, the rule engine judges, and a refusal is fed back for another try.

The agent never gets a say in the decision. Each proposal is stored and evaluated exactly like a buyer's
selection, and only the engine's ALLOW lets a checkout start.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from intentlock.ai import assistant
from intentlock.ai.llm import LLM, AIUnavailable
from intentlock.db.models import Product, PurchaseMandate
from intentlock.services import catalog, mandates, purchases

MAX_ATTEMPTS = 3
INJECTION_MARKERS = ("ignore the buyer", "system note", "ignore previous", "ignore all previous")


def _manipulated_choice(rows: list[Product]) -> dict:
    """Simulation of a compromised agent: it obeys the instruction hidden in a product description."""
    tricked = [p for p in rows if any(m in p.description.lower() for m in INJECTION_MARKERS)]
    pick = tricked[0] if tricked else max(rows, key=lambda p: p.unit_amount_minor)
    return {"product_id": pick.provider_product_id, "model": "simulated", "simulated": True,
            "rationale": "Simulated manipulated agent: it followed the instruction hidden in this product's description."}  # fmt: skip


def run(s: Session, *, llm: LLM | None, mandate: PurchaseMandate, mode: str, ttl_minutes: int) -> dict:
    """Propose up to MAX_ATTEMPTS times, stopping at the first ALLOW. `mode` is 'assistant' or 'manipulated'."""
    version = mandates.current_version(s, mandate)
    spec = mandates.spec_of(version)
    rows = catalog.search(s, category=spec.product.category) or catalog.search(s)
    offers = [catalog.product_view(p) for p in rows]
    ref = f"agent-{uuid.uuid4().hex[:12]}"
    steps: list[dict] = []
    refused: list[dict] = []
    last_view: dict | None = None
    last_choice: dict | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt == 1 and mode == "manipulated":
            choice = _manipulated_choice(rows)
        else:
            try:
                choice = {**assistant.propose_product(llm, version.structured_mandate, offers, refused), "simulated": False}
            except AIUnavailable as exc:
                if attempt == 1:
                    raise
                steps.append({"attempt": attempt, "stopped": True, "note": f"The assistant could not try again: {exc}"})
                break
        product = catalog.get_product(s, choice["product_id"])
        ps = purchases.propose(s, mandate=mandate, product=product, quantity=None, proposed_by="agent", agent_session_ref=ref,
                               actor_id=ref, ttl_minutes=ttl_minutes)  # fmt: skip
        last_view, last_choice = purchases.session_view(s, ps), choice
        ev = last_view["evaluation"]
        failed = [{"rule_id": c["rule_id"], "reason": c["reason"]} for c in ev["checks"] if c["status"] != "PASS"]
        steps.append({"attempt": attempt, "stopped": False, "product_id": product.provider_product_id, "title": product.title,
                      "rationale": choice["rationale"], "model": choice["model"], "simulated": choice["simulated"],
                      "decision": ev["decision"], "failed": failed, "purchase_session_id": last_view["purchase_session_id"]})  # fmt: skip
        if ev["decision"] == "ALLOW":
            break
        refused.append({"product_id": product.provider_product_id, "title": product.title, "refused_because": failed})

    return {**last_view, "agent": {**last_choice, "agent_session_ref": ref},
            "run": {"mode": mode, "agent_session_ref": ref, "steps": steps, "max_attempts": MAX_ATTEMPTS,
                    "outcome": last_view["evaluation"]["decision"]}}  # fmt: skip
