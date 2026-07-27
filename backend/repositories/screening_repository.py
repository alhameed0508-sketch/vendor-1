"""
Screening repository — data access for watchlist and screening results.
Uses Neo4j for persistence with in-memory fallback.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Confidence score assigned to exact alias matches
ALIAS_EXACT_CONFIDENCE = 0.95


class ScreeningRepository:
    """Watchlist and screening result data access."""

    def __init__(self):
        self._watchlist: List[Dict] = []
        self._results: List[Dict] = []

    def bulk_import_entries(self, entries: List[Dict], source: str) -> int:
        """Delete old entries for source, insert new ones."""
        self._watchlist = [e for e in self._watchlist if e.get("source") != source]
        for entry in entries:
            entry["source"] = source
            entry["added_date"] = datetime.now(timezone.utc).isoformat()
        self._watchlist.extend(entries)
        return len(entries)

    def search_by_name(self, name: str, fuzzy: bool = True) -> List[Dict]:
        """Search watchlist by name — exact (case-insensitive) + Levenshtein if fuzzy."""
        matches = []
        name_lower = name.lower()
        name_tokens = set(name_lower.split())

        for entry in self._watchlist:
            entry_name = entry.get("name", "").lower()
            # Exact match (case-insensitive)
            if entry_name == name_lower:
                matches.append({**entry, "match_type": "EXACT", "confidence": 1.0})
                continue

            # Token overlap
            entry_tokens = set(entry_name.split())
            overlap = name_tokens & entry_tokens
            if len(overlap) >= 2 or (len(overlap) == 1 and len(name_tokens) == 1):
                confidence = len(overlap) / max(len(name_tokens), len(entry_tokens))
                if confidence >= 0.5:
                    matches.append(
                        {
                            **entry,
                            "match_type": "TOKEN_OVERLAP",
                            "confidence": round(confidence, 2),
                        }
                    )
                    continue

            # Check aliases
            aliases = entry.get("aliases", [])
            for alias in aliases:
                if alias.lower() == name_lower:
                    matches.append(
                        {
                            **entry,
                            "match_type": "ALIAS_EXACT",
                            "confidence": ALIAS_EXACT_CONFIDENCE,
                        }
                    )
                    break

            # Fuzzy (Levenshtein) if enabled
            if fuzzy and not any(
                m.get("entry_id") == entry.get("entry_id") for m in matches
            ):
                distance = _levenshtein(name_lower, entry_name)
                if distance <= 2 and len(name_lower) > 4:
                    confidence = max(0.5, 1.0 - (distance / len(name_lower)))
                    matches.append(
                        {
                            **entry,
                            "match_type": "FUZZY",
                            "confidence": round(confidence, 2),
                        }
                    )

        return sorted(matches, key=lambda m: -m["confidence"])

    def search_by_identifier(self, identifier: str) -> List[Dict]:
        """Exact match on identifiers (passport, national ID, etc.)."""
        matches = []
        for entry in self._watchlist:
            identifiers = entry.get("identifiers", [])
            if identifier in identifiers:
                matches.append({**entry, "match_type": "IDENTIFIER", "confidence": 1.0})
        return matches

    def store_result(self, result: Dict) -> None:
        self._results.append(result)

    def get_results_for_account(self, account_id: str) -> List[Dict]:
        return [r for r in self._results if r.get("account_id") == account_id]

    def get_entries(self, source: Optional[str] = None, limit: int = 100) -> List[Dict]:
        entries = self._watchlist
        if source:
            entries = [e for e in entries if e.get("source") == source]
        return entries[:limit]

    def get_stats(self) -> Dict:
        sources = {}
        for entry in self._watchlist:
            s = entry.get("source", "unknown")
            sources[s] = sources.get(s, 0) + 1
        return {
            "total_entries": len(self._watchlist),
            "total_results": len(self._results),
            "sources": sources,
        }


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]
