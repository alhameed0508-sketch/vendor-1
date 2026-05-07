"""
Screening service — orchestrates watchlist screening against accounts.
"""
import logging
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from repositories.screening_repository import ScreeningRepository

logger = logging.getLogger(__name__)


class ScreeningService:
    """Sanctions/PEP screening service."""

    def __init__(self, screening_repo: ScreeningRepository):
        self._repo = screening_repo

    def screen_account(self, account_id: str, name: str, identifiers: Optional[List[str]] = None) -> Dict:
        """Screen a single account against watchlist."""
        matches = self._repo.search_by_name(name, fuzzy=True)

        if identifiers:
            for identifier in identifiers:
                id_matches = self._repo.search_by_identifier(identifier)
                for m in id_matches:
                    if not any(existing.get("entry_id") == m.get("entry_id") for existing in matches):
                        matches.append(m)

        result = {
            "result_id": f"SCR-{uuid.uuid4().hex[:8].upper()}",
            "account_id": account_id,
            "screened_name": name,
            "screened_at": datetime.utcnow().isoformat(),
            "matches": matches[:10],
            "match_count": len(matches),
            "highest_confidence": max((m["confidence"] for m in matches), default=0.0),
            "status": "MATCH" if matches else "CLEAR",
        }
        self._repo.store_result(result)
        return result

    def screen_accounts_batch(self, accounts: List[Dict]) -> List[Dict]:
        """Screen multiple accounts. Each dict: {account_id, name, identifiers?}."""
        results = []
        for account in accounts:
            result = self.screen_account(
                account_id=account["account_id"],
                name=account["name"],
                identifiers=account.get("identifiers"),
            )
            results.append(result)
        return results

    def refresh_unsc_list(self, unsc_url: str) -> Dict:
        """Fetch and import UNSC consolidated sanctions list."""
        from services.screening.unsc_fetcher import fetch_and_parse_unsc
        entries = fetch_and_parse_unsc(unsc_url)
        count = self._repo.bulk_import_entries(entries, source="UNSC")
        logger.info("UNSC watchlist refreshed: %d entries imported", count)
        return {"source": "UNSC", "entries_imported": count}

    def import_csv(self, rows: List[Dict], source: str) -> Dict:
        """Import watchlist entries from parsed CSV rows."""
        entries = []
        for row in rows:
            entry = {
                "entry_id": row.get("entry_id", f"CSV-{uuid.uuid4().hex[:8].upper()}"),
                "name": row.get("name", ""),
                "aliases": [a.strip() for a in row.get("aliases", "").split(";") if a.strip()],
                "identifiers": [i.strip() for i in row.get("identifiers", "").split(";") if i.strip()],
                "entity_type": row.get("entity_type", "INDIVIDUAL"),
                "countries": [c.strip() for c in row.get("countries", "").split(";") if c.strip()],
                "risk_category": row.get("risk_category", "SANCTIONS"),
            }
            entries.append(entry)
        count = self._repo.bulk_import_entries(entries, source=source)
        return {"source": source, "entries_imported": count}

    def get_stats(self) -> Dict:
        return self._repo.get_stats()
