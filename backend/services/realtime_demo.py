"""Helpers for seeding the real-time scorer with synthetic data (demo mode only)."""

from typing import Dict, List, Mapping, Sequence

# Ground-truth fields the generator emits. Detectors must never see them.
LABEL_FIELDS = frozenset({"role", "high_risk", "cluster_id", "is_suspicious", "pattern"})


def strip_labels(rows: Sequence[Mapping]) -> List[Dict]:
    """Return copies of ``rows`` without ground-truth label fields."""
    return [{k: v for k, v in row.items() if k not in LABEL_FIELDS} for row in rows]
