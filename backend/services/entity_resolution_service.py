"""Entity resolution for synthetic-identity and duplicate-account detection."""

from __future__ import annotations

import hashlib
import re
from typing import Dict

from rapidfuzz import fuzz


def _normalize(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def _hash_identifier(value: str | None) -> str:
    normalized = _normalize(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


class EntityResolutionService:
    """Resolve identities using exact identifiers plus fuzzy name/address."""

    MATCH_THRESHOLD = 0.55

    def __init__(self, repository):
        self._repository = repository

    @staticmethod
    def _profile(application: Dict) -> Dict:
        return {
            "entity_id": application.get("account_id", ""),
            "full_name": _normalize(application.get("full_name")),
            "phone_hash": _hash_identifier(application.get("phone_number")),
            "email_hash": _hash_identifier(application.get("email_address")),
            "postal_address": _normalize(application.get("postal_address")),
            "government_id_hash": application.get("government_id_hash") or "",
            "device_fingerprint": application.get("device_fingerprint") or "",
        }

    @staticmethod
    def _compare(profile: Dict, candidate: Dict) -> Dict:
        score = 0.0
        matched_fields = []
        weights = {
            "government_id_hash": 0.75,
            "phone_hash": 0.55,
            "email_hash": 0.45,
            "device_fingerprint": 0.45,
        }
        for field, weight in weights.items():
            if profile.get(field) and profile[field] == candidate.get(field):
                score += weight
                matched_fields.append(field)

        name_similarity = (
            fuzz.WRatio(profile["full_name"], candidate.get("full_name", "")) / 100
            if profile.get("full_name") and candidate.get("full_name")
            else 0.0
        )
        address_similarity = (
            fuzz.WRatio(
                profile["postal_address"],
                candidate.get("postal_address", ""),
            )
            / 100
            if profile.get("postal_address") and candidate.get("postal_address")
            else 0.0
        )
        if name_similarity >= 0.85:
            score += 0.25 * name_similarity
            matched_fields.append("full_name")
        if address_similarity >= 0.80:
            score += 0.15 * address_similarity
            matched_fields.append("postal_address")

        return {
            "entity_id": candidate["entity_id"],
            "match_score": round(min(score, 1.0), 4),
            "matched_fields": matched_fields,
            "name_similarity": round(name_similarity, 4),
            "address_similarity": round(address_similarity, 4),
        }

    def resolve_and_store(self, application: Dict) -> Dict:
        profile = self._profile(application)
        if not profile["entity_id"]:
            raise ValueError("account_id is required for entity resolution")

        matches = [
            result
            for candidate in self._repository.find_candidates(profile)
            if (result := self._compare(profile, candidate))["match_score"] >= self.MATCH_THRESHOLD
        ]
        matches.sort(key=lambda item: item["match_score"], reverse=True)
        self._repository.upsert_profile(profile)
        return {
            "entity_id": profile["entity_id"],
            "match_count": len(matches),
            "highest_match_score": matches[0]["match_score"] if matches else 0.0,
            "matches": matches[:20],
            "decision": "REVIEW_LINKED_IDENTITIES" if matches else "NO_MATCH",
            "engine": "rapidfuzz-hybrid-v1",
        }
