"""
UNSC consolidated sanctions list fetcher and parser.
Downloads XML from UN sanctions website, parses individuals and entities.
Falls back to bundled snapshot when live fetch fails.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Tuple
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

DEFAULT_UNSC_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
BUNDLED_SNAPSHOT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "data",
    "watchlists",
    "unsc_consolidated_snapshot.xml",
)


@dataclass(frozen=True)
class UNSCFetchResult:
    entries: Tuple[Dict, ...]
    source: str  # "LIVE" | "BUNDLED" | "NONE"
    last_updated: str
    entry_count: int


def fetch_and_parse_unsc(url: str = DEFAULT_UNSC_URL) -> List[Dict]:
    """Download and parse UNSC consolidated sanctions XML.

    Falls back to bundled snapshot if live fetch fails.
    Returns list of entry dicts for backward compatibility.
    """
    result = fetch_unsc_with_fallback(url)
    return list(result.entries)


def fetch_unsc_with_fallback(url: str = DEFAULT_UNSC_URL) -> UNSCFetchResult:
    """Fetch UNSC list with offline fallback. Returns typed result with source info."""
    # Try live fetch first
    try:
        response = httpx.get(url, timeout=60, follow_redirects=True)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        entries = _parse_entries(root)
        logger.info(
            "UNSC live fetch: %d entries from %s [source=LIVE]",
            len(entries),
            url,
        )
        return UNSCFetchResult(
            entries=tuple(entries),
            source="LIVE",
            last_updated=datetime.now(timezone.utc).isoformat(),
            entry_count=len(entries),
        )
    except Exception as exc:
        logger.warning("Live UNSC fetch failed (%s), trying bundled snapshot", exc)

    # Fallback to bundled snapshot
    snapshot_path = os.path.normpath(BUNDLED_SNAPSHOT_PATH)
    if os.path.exists(snapshot_path):
        try:
            tree = ElementTree.parse(snapshot_path)
            root = tree.getroot()
            entries = _parse_entries(root)
            logger.info(
                "UNSC bundled snapshot loaded: %d entries [source=BUNDLED]",
                len(entries),
            )
            return UNSCFetchResult(
                entries=tuple(entries),
                source="BUNDLED",
                last_updated=datetime.now(timezone.utc).isoformat(),
                entry_count=len(entries),
            )
        except Exception as exc:
            logger.error("Failed to parse bundled UNSC snapshot: %s", exc)

    logger.error("No UNSC data available (live fetch and bundled snapshot both failed)")
    return UNSCFetchResult(
        entries=(),
        source="NONE",
        last_updated=datetime.now(timezone.utc).isoformat(),
        entry_count=0,
    )


def _parse_entries(root) -> List[Dict]:
    """Parse individuals and entities from an UNSC XML root element."""
    entries = []
    for individual in root.iter("INDIVIDUAL"):
        entry = _parse_individual(individual)
        if entry:
            entries.append(entry)
    for entity in root.iter("ENTITY"):
        entry = _parse_entity(entity)
        if entry:
            entries.append(entry)
    return entries


def _parse_individual(elem) -> Dict:
    """Parse an INDIVIDUAL element from UNSC XML."""
    dataid = _text(elem, "DATAID") or ""
    first_name = _text(elem, "FIRST_NAME") or ""
    second_name = _text(elem, "SECOND_NAME") or ""
    third_name = _text(elem, "THIRD_NAME") or ""

    full_name = " ".join(filter(None, [first_name, second_name, third_name])).strip()
    if not full_name:
        return None

    aliases = []
    for alias_elem in elem.iter("INDIVIDUAL_ALIAS"):
        alias_name = _text(alias_elem, "ALIAS_NAME")
        if alias_name:
            aliases.append(alias_name)

    identifiers = []
    for doc_elem in elem.iter("INDIVIDUAL_DOCUMENT"):
        doc_number = _text(doc_elem, "NUMBER")
        if doc_number:
            identifiers.append(doc_number)

    nationalities = []
    for nat_elem in elem.iter("NATIONALITY"):
        value = _text(nat_elem, "VALUE")
        if value:
            nationalities.append(value)

    dob = _text(elem, "DATE_OF_BIRTH")

    return {
        "entry_id": f"UNSC-{dataid}",
        "name": full_name,
        "aliases": aliases,
        "identifiers": identifiers,
        "entity_type": "INDIVIDUAL",
        "countries": nationalities,
        "date_of_birth": dob,
        "risk_category": "SANCTIONS",
    }


def _parse_entity(elem) -> Dict:
    """Parse an ENTITY element from UNSC XML."""
    dataid = _text(elem, "DATAID") or ""
    first_name = _text(elem, "FIRST_NAME") or ""

    if not first_name:
        return None

    aliases = []
    for alias_elem in elem.iter("ENTITY_ALIAS"):
        alias_name = _text(alias_elem, "ALIAS_NAME")
        if alias_name:
            aliases.append(alias_name)

    return {
        "entry_id": f"UNSC-{dataid}",
        "name": first_name,
        "aliases": aliases,
        "identifiers": [],
        "entity_type": "ENTITY",
        "countries": [],
        "risk_category": "SANCTIONS",
    }


def _text(elem, tag: str) -> str:
    """Safely extract text from an XML child element."""
    child = elem.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""
