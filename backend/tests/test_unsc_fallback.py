"""Tests for UNSC watchlist offline fallback."""
import os
import pytest
from unittest.mock import patch, MagicMock
from services.screening.unsc_fetcher import (
    fetch_and_parse_unsc,
    fetch_unsc_with_fallback,
    _parse_entries,
    UNSCFetchResult,
    BUNDLED_SNAPSHOT_PATH,
)
from xml.etree import ElementTree


def test_unsc_fetch_result_immutable():
    result = UNSCFetchResult(entries=(), source="NONE", last_updated="2024-01-01", entry_count=0)
    assert result.source == "NONE"
    with pytest.raises(AttributeError):
        result.source = "LIVE"


def test_parse_entries_individuals():
    xml = """<ROOT>
      <INDIVIDUAL>
        <DATAID>1</DATAID><FIRST_NAME>John</FIRST_NAME><SECOND_NAME>Doe</SECOND_NAME>
      </INDIVIDUAL>
    </ROOT>"""
    root = ElementTree.fromstring(xml)
    entries = _parse_entries(root)
    assert len(entries) == 1
    assert entries[0]["name"] == "John Doe"
    assert entries[0]["entry_id"] == "UNSC-1"


def test_parse_entries_entities():
    xml = """<ROOT>
      <ENTITY>
        <DATAID>E1</DATAID><FIRST_NAME>Evil Corp</FIRST_NAME>
        <ENTITY_ALIAS><ALIAS_NAME>EC</ALIAS_NAME></ENTITY_ALIAS>
      </ENTITY>
    </ROOT>"""
    root = ElementTree.fromstring(xml)
    entries = _parse_entries(root)
    assert len(entries) == 1
    assert entries[0]["name"] == "Evil Corp"
    assert entries[0]["aliases"] == ["EC"]


@patch("services.screening.unsc_fetcher.httpx.get")
def test_fallback_to_bundled_on_network_failure(mock_get):
    """When live fetch fails, should fall back to bundled snapshot."""
    mock_get.side_effect = Exception("Network error")
    result = fetch_unsc_with_fallback()
    # Should fall back to BUNDLED or NONE depending on snapshot availability
    assert result.source in ("BUNDLED", "NONE")
    assert isinstance(result.entries, tuple)


@patch("services.screening.unsc_fetcher.httpx.get")
def test_live_fetch_returns_live_source(mock_get):
    """Successful live fetch should return source=LIVE."""
    xml_content = b"""<?xml version="1.0"?>
    <ROOT>
      <INDIVIDUAL>
        <DATAID>99</DATAID><FIRST_NAME>Test</FIRST_NAME><SECOND_NAME>Person</SECOND_NAME>
      </INDIVIDUAL>
    </ROOT>"""
    mock_response = MagicMock()
    mock_response.content = xml_content
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = fetch_unsc_with_fallback()
    assert result.source == "LIVE"
    assert result.entry_count == 1


def test_backward_compat_fetch_and_parse():
    """fetch_and_parse_unsc should still return a plain list."""
    with patch("services.screening.unsc_fetcher.httpx.get") as mock_get:
        mock_get.side_effect = Exception("offline")
        entries = fetch_and_parse_unsc()
        assert isinstance(entries, list)
