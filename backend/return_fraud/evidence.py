"""The package a retailer hands the bank: decision, plain-language narrative, every signal, and a hash.

The dispute category is an indicative mapping from what the evidence shows, not a network reason code; the
package says so. The hash covers everything except itself, so a changed tier or reason no longer verifies.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Mapping

from fpdf import FPDF

FIRED_ABOVE = 30
MAX_FINDINGS_SHOWN = 3  # the narrative leads with the strongest checks; the ledger and package list every one
NOT_RECEIVED_PHRASES = ("never received", "not received", "did not arrive", "didn't arrive")
ALGORITHM = "sha256 over canonical JSON (sorted keys, UTF-8), excluding this block"
CATEGORY_NOTE = (
    "Indicative mapping from the evidence. Confirm against the bank's current dispute reason codes before filing."
)
RECOMMENDATION = {
    "APPROVE": "Refund. Nothing in the evidence needs a second look.",
    "VERIFY": "Ask the customer for one more proof before refunding. A reviewer decides; nothing is blocked.",
    "CHALLENGE": "Hold the refund and ask for the original proof. A reviewer decides; nothing is blocked automatically.",
    "BLOCK": "Send to the fraud desk and do not refund yet. A person confirms before any action is taken.",
}
LIMITS = (
    "The image check compares labels attached to the photo with the customer's words. No image model ran, so it is a simulation.",
    "Device and ring checks only see claims filed with this retailer.",
    "A high score is a reason to look closer, not proof of fraud.",
)


def _inr(amount: int) -> str:
    return f"INR {amount:,}"


def category(assessment: Mapping) -> Dict:
    claim, fusion = assessment["claim"], assessment["fusion"]
    fired = {s["name"] for s in assessment["signals"] if s["score"] > FIRED_ABOVE}
    delivered = any(e.get("type") == "delivered" for e in claim.get("carrier_events", []))
    if fusion["tier"] == "APPROVE":
        code, label = "NONE", "No dispute category: the evidence supports the claim"
    elif "graph" in fired and "device" in fired:
        code, label = "RING", "Possible organised return-fraud ring: several customers acting together"
    elif {"receipt", "exif"} & fired:
        code, label = "DOC", "Supporting documents that appear altered or reused"
    elif delivered and any(p in claim.get("reason_text", "").lower() for p in NOT_RECEIVED_PHRASES):
        code, label = "RECEIVED", "Claim contradicted by delivery confirmation: item was received"
    elif "vlm" in fired:
        code, label = "NOT_AS_CLAIMED", "Item not as claimed: the photo contradicts the description"
    else:
        code, label = "REVIEW", "Repeated returns that need review"
    return {"code": code, "label": label, "note": CATEGORY_NOTE}


def narrative(assessment: Mapping) -> Dict[str, str]:
    claim, fusion = assessment["claim"], assessment["fusion"]
    fired = sorted((s for s in assessment["signals"] if s["score"] > FIRED_ABOVE), key=lambda s: -s["score"])
    found: List[str] = [s["reasons"][0] for s in fired[:MAX_FINDINGS_SHOWN] if s["reasons"]]
    if len(fired) > MAX_FINDINGS_SHOWN:
        found.append(f"{len(fired) - MAX_FINDINGS_SHOWN} more checks fired; the evidence ledger lists them all")
    adjustments = [a["label"] for a in fusion["adjustments"]]
    return {
        "what_happened": (
            f"{claim['customer_name']} returned {claim['item']} worth {_inr(claim['amount'])}, "
            f'saying: "{claim["reason_text"]}".'
        ),
        "what_we_found": " ".join(f"{r}." for r in [*found, *adjustments])
        or "Every check came back clean. The photo, receipt, device and history all fit the claim.",
        "what_we_recommend": RECOMMENDATION[fusion["tier"]],
    }


def _digest(body: Mapping) -> str:
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_package(assessment: Mapping, generated_at: str) -> Dict:
    fusion = assessment["fusion"]
    body = {
        "claim_id": assessment["claim"]["claim_id"],
        "generated_at": generated_at,
        "claim": assessment["claim"],
        "decision": {
            "tier": fusion["tier"],
            "score": fusion["score"],
            "capped_from": fusion["capped_from"],
            "corroborating_signals": fusion["corroborating"],
            "firewall": fusion["firewall"],
            "adjustments": fusion["adjustments"],
        },
        "dispute_category": category(assessment),
        "narrative": narrative(assessment),
        "signals": [{**s, "fired": s["available"] and s["score"] > FIRED_ABOVE} for s in assessment["signals"]],
        "limits": list(LIMITS),
    }
    return {**body, "integrity": {"sha256": _digest(body), "algorithm": ALGORITHM}}


def verify_package(package: Mapping) -> Dict:
    body = {k: v for k, v in package.items() if k != "integrity"}
    return {"intact": _digest(body) == package.get("integrity", {}).get("sha256")}


def _latin(text) -> str:
    return str(text).replace("₹", "INR ").encode("latin-1", "replace").decode("latin-1")


class _Pack(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, "RETURN CLAIM EVIDENCE PACKAGE", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, "Prepared for the issuing bank  |  Confidential", align="C", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}  |  Generated by MuleCatch", align="C")

    def heading(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 7, _latin(title), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)

    def para(self, text: str):
        self.multi_cell(0, 5, _latin(text), new_x="LMARGIN", new_y="NEXT")


def build_pdf(package: Mapping) -> bytes:
    pdf = _Pack()
    pdf.alias_nb_pages()
    pdf.add_page()
    decision, narrative = package["decision"], package["narrative"]
    pdf.heading(f"Claim {package['claim_id']}")
    pdf.para(
        f"Recommendation: {decision['tier']} (score {decision['score']:.0f} of 100). {narrative['what_we_recommend']}"
    )
    pdf.heading("What happened")
    pdf.para(narrative["what_happened"])
    pdf.heading("What we found")
    pdf.para(narrative["what_we_found"])
    pdf.heading("Dispute category")
    pdf.para(f"{package['dispute_category']['label']}. {package['dispute_category']['note']}")
    pdf.heading("Signals")
    for s in package["signals"]:
        state = "fired" if s["fired"] else ("quiet" if s["available"] else "not run")
        pdf.para(f"{s['name']} - {state} ({s['score']:.0f}): {'; '.join(s['reasons'])}")
    pdf.heading("How to read this")
    pdf.para(decision["firewall"])
    for limit in package["limits"]:
        pdf.para(f"- {limit}")
    pdf.heading("Integrity")
    pdf.para(f"SHA-256: {package['integrity']['sha256']}")
    pdf.para(f"Generated {package['generated_at']}. {package['integrity']['algorithm']}.")
    return bytes(pdf.output())
