"""Cited complaint narratives: every sentence must point at evidence that exists."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from complaints.evidence import append
from complaints.narrative import write_narrative
from genai.base import LLMProvider, LLMResponse

CHAIN = append(
    append([], at="2027-02-01T10:00:00+05:30", source="TELECOM", kind="sim_swap", summary="SIM swapped 2 hours before",
           data={}, submitted_by="t", received_at="2027-02-01T10:05:00+05:30"),
    at="2027-02-01T12:00:00+05:30", source="AUTH_LOG", kind="login", summary="Login from a new device",
    data={"new_device": True}, submitted_by="t", received_at="2027-02-01T12:05:00+05:30",
)
ASSESSMENT = {"category": "THIRD_PARTY_BREACH", "outcome": "ZERO_LIABILITY", "basis": "Zero liability.",
              "reasons": [{"text": "SIM swapped", "evidence": ["E1"]}]}


class FakeProvider(LLMProvider):
    def __init__(self, text=None, error=None):
        self._text, self._error, self.prompts = text, error, []

    @property
    def provider_name(self):
        return "gemini"

    def generate(self, messages, **kwargs):
        self.prompts.append(messages)
        if self._error:
            raise self._error
        return LLMResponse(content=self._text, model="m", provider="gemini")


def test_template_cites_every_item_and_the_conclusion():
    result = write_narrative(CHAIN, ASSESSMENT, provider=None)
    assert result["source"] == "template"
    assert [s["evidence"] for s in result["sentences"][:2]] == [["E1"], ["E2"]]
    assert result["sentences"][-1]["evidence"] == ["E1"]


def test_template_tells_the_story_in_time_order_not_arrival_order():
    late_arrival = append(CHAIN, at="2027-01-31T23:00:00+05:30", source="TELECOM", kind="sim_swap",
                          summary="SIM swapped the night before", data={}, submitted_by="t",
                          received_at="2027-02-02T09:00:00+05:30")
    result = write_narrative(late_arrival, ASSESSMENT, provider=None)
    assert [s["evidence"] for s in result["sentences"][:3]] == [["E3"], ["E1"], ["E2"]]


def test_llm_sentences_without_valid_citations_are_dropped():
    text = ("The SIM was swapped before the payment [E1]. A new device logged in [E2]. "
            "The customer is clearly lying. The fraudster used a VPN [E9].")
    result = write_narrative(CHAIN, ASSESSMENT, provider=FakeProvider(text))
    assert result["source"] == "gemini"
    assert [s["text"] for s in result["sentences"]] == ["The SIM was swapped before the payment.", "A new device logged in."]
    assert result["dropped"] == 2


def test_prompt_asks_for_timestamped_citations_and_carries_the_evidence():
    provider = FakeProvider("The SIM was swapped [E1]. A new device logged in [E2].")
    write_narrative(CHAIN, ASSESSMENT, provider=provider)
    prompt = " ".join(m.content for m in provider.prompts[0])
    assert "traceable to timestamps" in prompt
    assert "E2" in prompt and "2027-02-01T12:00:00+05:30" in prompt


def test_falls_back_to_the_template_when_the_llm_fails_or_cites_too_little():
    assert write_narrative(CHAIN, ASSESSMENT, provider=FakeProvider(error=TimeoutError()))["source"] == "template"
    assert write_narrative(CHAIN, ASSESSMENT, provider=FakeProvider("No citations at all."))["source"] == "template"


def test_empty_evidence_gives_an_empty_narrative():
    assert write_narrative([], ASSESSMENT, provider=None)["sentences"] == []
