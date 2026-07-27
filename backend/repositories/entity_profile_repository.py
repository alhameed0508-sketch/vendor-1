"""In-memory identity profile repository for demo and tests."""

from __future__ import annotations

from typing import Dict, List


class EntityProfileRepository:
    def __init__(self):
        self._profiles: Dict[str, Dict] = {}

    def find_candidates(self, profile: Dict, limit: int = 200) -> List[Dict]:
        """Return blocked candidates; exact identifiers first, then names."""
        exact_fields = (
            "phone_hash",
            "email_hash",
            "government_id_hash",
            "device_fingerprint",
        )
        exact = [
            candidate
            for candidate in self._profiles.values()
            if candidate["entity_id"] != profile["entity_id"]
            and any(
                profile.get(field) and profile.get(field) == candidate.get(field)
                for field in exact_fields
            )
        ]
        remaining = [
            candidate
            for candidate in self._profiles.values()
            if candidate["entity_id"] != profile["entity_id"] and candidate not in exact
        ]
        return (exact + remaining)[:limit]

    def upsert_profile(self, profile: Dict) -> None:
        self._profiles[profile["entity_id"]] = dict(profile)
