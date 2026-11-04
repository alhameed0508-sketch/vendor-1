"""
PostgreSQL-backed screening repository.
Same interface as the in-memory ScreeningRepository.
Watchlist stored in screening_watchlist table; results in screening_results.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import delete
from sqlalchemy.engine import Engine

from backend.infra.database.postgres import screening_results, screening_watchlist

logger = logging.getLogger(__name__)

# Confidence score assigned to exact alias matches
ALIAS_EXACT_CONFIDENCE = 0.95


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def _wl_row_to_dict(row) -> Dict:
    d = dict(row._mapping)
    if d.get("added_date") is not None:
        d["added_date"] = d["added_date"].isoformat()
    return d


def _result_row_to_dict(row) -> Dict:
    d = dict(row._mapping)
    if d.get("screened_at") is not None:
        d["screened_at"] = d["screened_at"].isoformat()
    return d


class PgScreeningRepository:
    """PostgreSQL watchlist and screening result data access."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def bulk_import_entries(self, entries: List[Dict], source: str) -> int:
        """Delete old entries for source, insert new ones."""
        now = datetime.now(timezone.utc)
        with self._engine.connect() as conn:
            conn.execute(delete(screening_watchlist).where(screening_watchlist.c.source == source))
            for entry in entries:
                values = {
                    "entry_id": entry.get("entry_id", ""),
                    "name": entry.get("name", ""),
                    "aliases": entry.get("aliases", []),
                    "identifiers": entry.get("identifiers", []),
                    "entity_type": entry.get("entity_type", "INDIVIDUAL"),
                    "countries": entry.get("countries", []),
                    "risk_category": entry.get("risk_category", "SANCTIONS"),
                    "source": source,
                    "date_of_birth": entry.get("date_of_birth"),
                    "added_date": now,
                }
                conn.execute(screening_watchlist.insert().values(**values))
            conn.commit()
        return len(entries)

    def search_by_name(self, name: str, fuzzy: bool = True) -> List[Dict]:
        """Search watchlist by name — exact + token overlap + alias + fuzzy."""
        with self._engine.connect() as conn:
            rows = conn.execute(screening_watchlist.select()).fetchall()

        entries = [_wl_row_to_dict(r) for r in rows]
        matches = []
        name_lower = name.lower()
        name_tokens = set(name_lower.split())

        for entry in entries:
            entry_name = entry.get("name", "").lower()
            if entry_name == name_lower:
                matches.append({**entry, "match_type": "EXACT", "confidence": 1.0})
                continue

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

            if fuzzy and not any(m.get("entry_id") == entry.get("entry_id") for m in matches):
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
        with self._engine.connect() as conn:
            rows = conn.execute(screening_watchlist.select()).fetchall()

        matches = []
        for row in rows:
            entry = _wl_row_to_dict(row)
            identifiers = entry.get("identifiers", [])
            if identifier in identifiers:
                matches.append({**entry, "match_type": "IDENTIFIER", "confidence": 1.0})
        return matches

    def store_result(self, result: Dict) -> None:
        now = datetime.now(timezone.utc)
        values = {
            "result_id": result.get("result_id", ""),
            "account_id": result.get("account_id", ""),
            "screened_name": result.get("screened_name", ""),
            "matches": result.get("matches", []),
            "match_count": result.get("match_count", 0),
            "highest_confidence": result.get("highest_confidence", 0),
            "status": result.get("status", "CLEAR"),
            "screened_at": now,
        }
        with self._engine.connect() as conn:
            conn.execute(screening_results.insert().values(**values))
            conn.commit()

    def get_results_for_account(self, account_id: str) -> List[Dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                screening_results.select().where(screening_results.c.account_id == account_id)
            ).fetchall()
        return [_result_row_to_dict(r) for r in rows]

    def get_entries(self, source: Optional[str] = None, limit: int = 100) -> List[Dict]:
        query = screening_watchlist.select()
        if source:
            query = query.where(screening_watchlist.c.source == source)
        query = query.limit(limit)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_wl_row_to_dict(r) for r in rows]

    def get_stats(self) -> Dict:
        from sqlalchemy import func, select

        with self._engine.connect() as conn:
            total_entries = conn.execute(select(func.count()).select_from(screening_watchlist)).scalar() or 0
            total_results = conn.execute(select(func.count()).select_from(screening_results)).scalar() or 0

            source_rows = conn.execute(
                select(screening_watchlist.c.source, func.count().label("cnt")).group_by(screening_watchlist.c.source)
            ).fetchall()
        sources = {r._mapping["source"]: r._mapping["cnt"] for r in source_rows}
        return {
            "total_entries": total_entries,
            "total_results": total_results,
            "sources": sources,
        }
