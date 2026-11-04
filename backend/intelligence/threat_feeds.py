"""Real public IP-reputation lists for the session engine (SD04 Tor exit nodes, SD05 Spamhaus DROP).

Rules: fetch with a timeout, keep the last good copy on failure, mark a list stale after 24 h, cache
to disk so a restart does not start empty, and never invent entries. Lookups are in memory.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

TOR_URL = "https://check.torproject.org/torbulkexitlist"
DROP_URL = "https://www.spamhaus.org/drop/drop_v4.json"
REFRESH_SECONDS = 6 * 3600
STALE_SECONDS = 24 * 3600
TIMEOUT_SECONDS = 10.0
MAX_BYTES = 5_000_000


def _http_get(url: str) -> str:
    import httpx

    with httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": "MuleCatch-risk-engine/1.0 (threat list refresh)"},
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        if len(resp.content) > MAX_BYTES:
            raise ValueError(f"{url} returned more than {MAX_BYTES} bytes")
        return resp.text


def parse_tor(text: str) -> List[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(str(ipaddress.ip_address(line)))
        except ValueError:
            continue
    return out


def parse_drop(text: str) -> List[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            cidr = json.loads(line).get("cidr")
            if cidr:
                out.append(str(ipaddress.ip_network(cidr, strict=False)))
        except (ValueError, json.JSONDecodeError):
            continue
    return out


FEEDS = {
    "tor_exit": {"url": TOR_URL, "parse": parse_tor, "label": "Tor exit-node list (torproject.org)"},
    "spamhaus_drop": {"url": DROP_URL, "parse": parse_drop, "label": "Spamhaus DROP (hijacked networks)"},
}


class ThreatFeeds:
    def __init__(
        self, cache_path: Optional[Path] = None, fetch: Callable[[str], str] = _http_get, enabled: bool = True
    ):
        self._cache_path = cache_path
        self._fetch = fetch
        self._enabled = enabled
        self._lock = threading.Lock()
        self._tor: frozenset = frozenset()
        self._drop: Dict[int, List] = {}
        self._status: Dict[str, Dict] = {
            name: {
                "name": name,
                "label": f["label"],
                "url": f["url"],
                "fetched_at": None,
                "entries": 0,
                "error": None,
                "origin": None,
            }
            for name, f in FEEDS.items()
        }
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._load_cache()

    # ---------------------------------------------------------------- loading
    def _apply(self, name: str, entries: List[str], fetched_at: float, origin: str) -> None:
        with self._lock:
            if name == "tor_exit":
                self._tor = frozenset(entries)
            else:
                buckets: Dict[int, List] = {}
                for cidr in entries:
                    net = ipaddress.ip_network(cidr, strict=False)
                    first = int(net.network_address) >> 24
                    last = int(net.broadcast_address) >> 24
                    for octet in range(first, last + 1):
                        buckets.setdefault(octet, []).append(net)
                self._drop = buckets
            self._status[name].update(fetched_at=fetched_at, entries=len(entries), error=None, origin=origin)

    def _load_cache(self) -> None:
        if not self._cache_path or not self._cache_path.exists():
            return
        try:
            cached = json.loads(self._cache_path.read_text(encoding="utf-8"))
            for name in FEEDS:
                if name in cached:
                    self._apply(name, cached[name]["entries"], cached[name]["fetched_at"], "disk cache")
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("threat feed cache unreadable: %s", exc)

    def _save_cache(self, payload: Dict) -> None:
        if not self._cache_path:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self._cache_path)
        except OSError as exc:
            logger.warning("threat feed cache not written: %s", exc)

    def refresh(self) -> Dict:
        """Fetch every list now. A failed list keeps its last good copy and records the error."""
        if not self._enabled:
            return self.status()
        payload = {}
        for name, feed in FEEDS.items():
            try:
                entries = feed["parse"](self._fetch(feed["url"]))
                if not entries:
                    raise ValueError("list came back empty")
                now = time.time()
                self._apply(name, entries, now, "download")
                payload[name] = {"entries": entries, "fetched_at": now}
            except Exception as exc:  # noqa: BLE001 - network, HTTP or parse failure: keep the last good copy
                with self._lock:
                    self._status[name]["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
                logger.warning("threat feed %s refresh failed: %s", name, exc)
        if payload:
            existing = {}
            if self._cache_path and self._cache_path.exists():
                try:
                    existing = json.loads(self._cache_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    existing = {}
            self._save_cache({**existing, **payload})
        return self.status()

    def start(self) -> None:
        """Refresh now and then every 6 hours on a daemon thread."""
        if not self._enabled or (self._thread and self._thread.is_alive()):
            return

        def loop():
            while not self._stop.is_set():
                self.refresh()
                self._stop.wait(REFRESH_SECONDS)

        self._thread = threading.Thread(target=loop, daemon=True, name="threat-feeds")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # ----------------------------------------------------------------- lookup
    def lookup(self, ip: str) -> List[Dict]:
        """Which lists contain this IP. Empty when the IP is unknown, invalid or no list is loaded."""
        try:
            addr = ipaddress.ip_address(str(ip).strip())
        except ValueError:
            return []
        hits = []
        with self._lock:
            tor, drop = self._tor, self._drop
            status = {k: dict(v) for k, v in self._status.items()}
        if str(addr) in tor:
            hits.append({"feed": "tor_exit", "match": str(addr), "fetched_at": status["tor_exit"]["fetched_at"]})
        if addr.version == 4:
            for net in drop.get(int(addr) >> 24, []):
                if addr in net:
                    hits.append(
                        {
                            "feed": "spamhaus_drop",
                            "match": str(net),
                            "fetched_at": status["spamhaus_drop"]["fetched_at"],
                        }
                    )
                    break
        return hits

    def status(self) -> Dict:
        now = time.time()
        with self._lock:
            feeds = []
            for s in self._status.values():
                row = dict(s)
                row["stale"] = row["fetched_at"] is None or now - row["fetched_at"] > STALE_SECONDS
                row["age_hours"] = round((now - row["fetched_at"]) / 3600, 1) if row["fetched_at"] else None
                feeds.append(row)
        return {"enabled": self._enabled, "feeds": feeds}
