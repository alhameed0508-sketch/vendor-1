"""
UNSC consolidated sanctions list fetcher and parser.
Downloads XML from UN sanctions website, parses individuals and entities.
"""
import logging
from typing import List, Dict
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

DEFAULT_UNSC_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"


def fetch_and_parse_unsc(url: str = DEFAULT_UNSC_URL) -> List[Dict]:
    """Download and parse UNSC consolidated sanctions XML."""
    try:
        response = httpx.get(url, timeout=60, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        logger.error("Failed to fetch UNSC list from %s: %s", url, exc)
        return []

    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        logger.error("Failed to parse UNSC XML: %s", exc)
        return []

    entries = []

    # Parse individuals
    for individual in root.iter("INDIVIDUAL"):
        entry = _parse_individual(individual)
        if entry:
            entries.append(entry)

    # Parse entities
    for entity in root.iter("ENTITY"):
        entry = _parse_entity(entity)
        if entry:
            entries.append(entry)

    logger.info("Parsed %d entries from UNSC consolidated list", len(entries))
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
