"""GET /score/stream?source=live: real-data feed, gated, and independent of the synthetic replay."""

import json

import pytest
from api.deps import get_demo_replay, get_live_feed
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from services.live_feed import LiveFeed
from services.realtime_demo import DemoReplay


def _tx(txid):
    return {
        "txid": txid * 64,
        "vin": [{"is_coinbase": False, "prevout": {"scriptpubkey_address": f"S{txid}", "value": 60_000_000}}],
        "vout": [{"scriptpubkey_address": f"R{txid}", "value": 50_000_000}],
        "status": {"confirmed": False},
    }


class _Client:
    def __init__(self):
        self._txs = {_tx(c)["txid"]: _tx(c) for c in "abc"}

    def inr_per_btc(self):
        return 1_000_000.0

    def recent_txids(self):
        return list(self._txs)

    def tx(self, txid):
        return self._txs[txid]


@pytest.fixture()
def live_app(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    from api.app import app

    app.dependency_overrides[get_live_feed] = lambda: LiveFeed(_Client(), poll_interval=0, sleep=lambda s: None)
    yield app
    app.dependency_overrides.pop(get_live_feed, None)
    app.dependency_overrides.pop(get_demo_replay, None)
    get_settings.cache_clear()


async def _get(app, **params):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/api/v1/score/stream", params=params)


@pytest.mark.asyncio
async def test_live_source_streams_real_shaped_events_without_building_the_synthetic_dataset(live_app, monkeypatch):
    def _boom():
        raise AssertionError("synthetic replay must not be built for source=live")

    monkeypatch.setattr("services.realtime_demo.DemoReplay.__init__", lambda self, *a, **k: _boom())
    resp = await _get(live_app, source="live", limit=3, rate=0)
    assert resp.status_code == 200
    events = [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]
    assert len(events) == 3
    assert all(e["source"] == "live" for e in events)


@pytest.mark.asyncio
async def test_unknown_source_is_rejected(live_app):
    assert (await _get(live_app, source="kafka", limit=1)).status_code in {400, 422}


@pytest.mark.asyncio
async def test_live_source_is_off_in_production_unless_enabled(live_app, monkeypatch):
    class _Prod:
        demo_mode = False
        live_feed_enabled = False

    live_app.dependency_overrides.pop(get_live_feed, None)  # exercise the real gate
    monkeypatch.setattr("api.deps.get_settings", lambda: _Prod())
    assert (await _get(live_app, source="live", limit=1)).status_code == 409


@pytest.mark.asyncio
async def test_default_source_is_still_the_synthetic_replay(live_app):
    live_app.dependency_overrides[get_demo_replay] = lambda: DemoReplay(seed=7)
    resp = await _get(live_app, limit=2, rate=0)
    events = [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]
    assert len(events) == 2 and "source" not in events[0]
