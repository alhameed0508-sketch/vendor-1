"""
Complaint narrative where every sentence cites evidence.

An LLM (Gemini when configured) drafts the narrative; any sentence that cites nothing, or cites an
evidence id that does not exist, is dropped. Too few cited sentences, or any provider failure, falls
back to a template built straight from the evidence.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from genai.base import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

MIN_LLM_SENTENCES = 2
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_CITATION = re.compile(r"\s*\[([^\]]*)\]")
_SYSTEM = (
    "You write dispute narratives for an Indian bank's fraud-complaint file under the RBI directions on "
    "fraudulent electronic banking transactions. Given these signals, write a plain-English dispute narrative "
    "traceable to timestamps. Rules: at most 8 sentences; every sentence ends with the ids of the evidence it "
    "relies on in square brackets, like [E2] or [E1, E3]; state only facts present in the evidence; mention the "
    "time of each event; no speculation about the customer's character."
)


def _when(at: str) -> str:
    return datetime.fromisoformat(at).strftime("%d %b %Y, %H:%M")


def _template(chain: List[Dict], assessment: Dict) -> List[Dict]:
    timeline = sorted(chain, key=lambda i: datetime.fromisoformat(i["at"]))
    sentences = [{"text": f"{_when(i['at'])}: {i['summary']}.", "evidence": [i["id"]]} for i in timeline]
    cited = [e for r in assessment.get("reasons", []) for e in r["evidence"]] or [chain[-1]["id"]]
    return [*sentences, {"text": assessment["basis"], "evidence": cited}]


def _cited_sentences(text: str, known: set) -> List[Dict]:
    kept = []
    for raw in _SENTENCE_END.split(text.strip()):
        ids = [e for group in _CITATION.findall(raw) for e in re.findall(r"E\d+", group)]
        if ids and all(e in known for e in ids):
            clean = re.sub(r"\s+([.!?])$", r"\1", _CITATION.sub("", raw).strip())
            kept.append({"text": clean, "evidence": ids})
    return kept


def write_narrative(chain: List[Dict], assessment: Dict, provider: Optional[LLMProvider]) -> Dict:
    """Return {"sentences": [{"text", "evidence"}], "source", "dropped"}."""
    if not chain:
        return {"sentences": [], "source": "template", "dropped": 0}
    if provider is not None and provider.provider_name != "template_fallback":
        evidence = [{k: i[k] for k in ("id", "at", "source", "summary")} for i in chain]
        facts = {"category": assessment["category"], "finding": assessment["basis"], "evidence": evidence}
        try:
            reply = provider.generate(
                [LLMMessage("system", _SYSTEM), LLMMessage("user", json.dumps(facts, ensure_ascii=False))],
                temperature=0.2,
                max_tokens=700,
            )
            total = len([s for s in _SENTENCE_END.split(reply.content.strip()) if s])
            kept = _cited_sentences(reply.content, {i["id"] for i in chain})
            if len(kept) >= MIN_LLM_SENTENCES:
                return {"sentences": kept, "source": provider.provider_name, "dropped": total - len(kept)}
        except Exception as exc:  # any provider failure falls back to the template
            logger.warning("Complaint narrative LLM call failed: %s", exc)
    return {"sentences": _template(chain, assessment), "source": "template", "dropped": 0}
