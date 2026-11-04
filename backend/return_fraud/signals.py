"""The signal record every detector returns, and the names fusion knows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

SIGNAL_NAMES = ("exif", "vlm", "receipt", "device", "behavioral", "graph")
# Where each finding comes from, for the evidence ledger. The image check is a simulation unless a model judged it.
SIGNAL_SOURCES = {
    "exif": "Photo metadata and perceptual hash (Pillow, ImageHash)",
    "vlm": "Photo labels compared with the claim text (simulated)",
    "receipt": "Receipt file metadata and SHA-256 (pypdf)",
    "device": "Device fingerprints on file",
    "behavioral": "Order and return history",
    "graph": "Shared device, address and card; claim text (RapidFuzz)",
}


@dataclass(frozen=True)
class Signal:
    """One detector's finding. ``score`` is 0-100; ``confidence`` scales its weight in fusion."""

    name: str
    score: float
    confidence: float = 1.0
    available: bool = True
    reasons: Tuple[str, ...] = ()
    detail: Tuple[Tuple[str, object], ...] = ()

    @property
    def detail_dict(self) -> Dict:
        return dict(self.detail)

    def as_dict(self) -> Dict:
        return {
            "name": self.name,
            "score": round(self.score, 1),
            "confidence": round(self.confidence, 2),
            "available": self.available,
            "reasons": list(self.reasons),
            "source": SIGNAL_SOURCES[self.name],
            "detail": dict(self.detail),
        }


def unavailable(name: str, why: str) -> Signal:
    return Signal(name=name, score=0.0, confidence=0.0, available=False, reasons=(why,))
