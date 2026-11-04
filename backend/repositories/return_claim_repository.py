"""
Return-claim repository — in-memory store with immutable updates.
"""

from typing import Dict, List, Optional


class ReturnClaimRepository:
    """In-memory claim store. Callers serialise writes (see ReturnClaimService)."""

    def __init__(self):
        self._claims: Dict[str, Dict] = {}

    def create(self, claim: Dict) -> Dict:
        self._claims[claim["claim_id"]] = dict(claim)
        return dict(claim)

    def find_by_id(self, claim_id: str) -> Optional[Dict]:
        claim = self._claims.get(claim_id)
        return dict(claim) if claim else None

    def find_all(self) -> List[Dict]:
        return [dict(c) for c in self._claims.values()]

    def count(self) -> int:
        return len(self._claims)

    def update(self, claim_id: str, **updates) -> Optional[Dict]:
        claim = self._claims.get(claim_id)
        if claim is None:
            return None
        updated = {**claim, **updates}
        self._claims[claim_id] = updated
        return dict(updated)
