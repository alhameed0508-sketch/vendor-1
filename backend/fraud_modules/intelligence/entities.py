"""Entity references and links between accounts.

A link says two accounts may be the same party or share an actor, and how sure we are.
Only verified identifiers (CIF_ID, device id) give VERIFIED. A name match is POSSIBLE at most
and never merges two entities.
"""

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from typing import Dict, Iterable, List, Set, Tuple

VERIFIED, PROBABLE, POSSIBLE = "VERIFIED", "PROBABLE", "POSSIBLE"
NAME_MATCH_RATIO = 0.9


@dataclass(frozen=True)
class EntityRef:
    kind: str
    entity_id: str


@dataclass(frozen=True)
class Link:
    a: EntityRef
    b: EntityRef
    basis: str
    confidence: str


def _pairs(ids: Iterable[str]):
    return combinations(sorted(set(ids)), 2)


def _shared(groups: Dict[str, Set[str]], basis: str) -> List[Tuple[Tuple[str, str], str]]:
    return [(pair, f"{basis} {key}") for key, ids in groups.items() for pair in _pairs(ids)]


def link_accounts(accounts: List[Dict], transactions: List[Dict]) -> Tuple[Link, ...]:
    """Links between accounts, one per pair, keeping the strongest basis found."""
    by_cif: Dict[str, Set[str]] = defaultdict(set)
    for a in accounts:
        if a.get("cif_id"):
            by_cif[a["cif_id"]].add(a["account_id"])
    by_device: Dict[str, Set[str]] = defaultdict(set)
    for t in transactions:
        if t.get("device_id"):
            by_device[t["device_id"]].add(t["from_account"])

    found: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for pair, basis in _shared(by_cif, "same CIF_ID") + _shared(by_device, "same device id"):
        found.setdefault(pair, (basis, VERIFIED))

    # shortcut: all-pairs name comparison, fine for demo-sized data; index by name prefix beyond ~5k named accounts.
    named = [(a["account_id"], a["holder_name"].strip().lower()) for a in accounts if a.get("holder_name")]
    for (id_a, name_a), (id_b, name_b) in combinations(named, 2):
        pair = tuple(sorted((id_a, id_b)))
        if pair not in found and SequenceMatcher(None, name_a, name_b).ratio() >= NAME_MATCH_RATIO:
            found[pair] = ("similar holder name, no shared verified identifier", POSSIBLE)

    return tuple(
        Link(EntityRef("account", a), EntityRef("account", b), basis, confidence)
        for (a, b), (basis, confidence) in sorted(found.items())
    )
