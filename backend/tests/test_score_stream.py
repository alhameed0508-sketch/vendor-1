"""Live replay stream: event shape, label safety, counters, demo-only."""

import json

import pytest
from api.deps import get_demo_replay
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from services.realtime_demo import LABEL_FIELDS, DemoReplay

FORBIDDEN = LABEL_FIELDS | {"high_risk", "genuine", "is_mule"}


@pytest.fixture(scope="module")
def replay_events():
    return list(DemoReplay(seed=7).events(limit=60))


def test_event_shape(replay_events):
    assert len(replay_events) == 60
    e = replay_events[0]
    assert {"payment", "decision", "case_id", "ring_members", "risk_score", "latency_ms", "counters"} <= set(e)
    assert {"payments", "flagged", "genuine_accounts_flagged", "mule_payments_flagged"} <= set(e["counters"])


def test_no_label_fields_in_any_event(replay_events):
    blob = json.dumps(replay_events)
    for field in FORBIDDEN:
        assert f'"{field}"' not in blob


def test_counters_are_monotonic(replay_events):
    payments = [e["counters"]["payments"] for e in replay_events]
    assert payments == list(range(1, 61))
    flagged = [e["counters"]["flagged"] for e in replay_events]
    assert flagged == sorted(flagged)


def test_replay_is_deterministic_for_a_seed():
    a = [(e["payment"]["txn_id"], e["decision"]) for e in DemoReplay(seed=3).events(limit=15)]
    b = [(e["payment"]["txn_id"], e["decision"]) for e in DemoReplay(seed=3).events(limit=15)]
    assert [d for _, d in a] == [d for _, d in b]


def test_replay_flags_some_rings_and_few_genuine():
    events = list(DemoReplay(seed=7).events(limit=150))
    last = events[-1]["counters"]
    assert last["mule_payments_flagged"] > 0
    assert last["genuine_accounts_flagged"] == 0


@pytest.fixture()
def stream_app(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    from api.app import app

    app.dependency_overrides[get_demo_replay] = lambda: DemoReplay(seed=7)
    yield app
    app.dependency_overrides.pop(get_demo_replay, None)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_stream_emits_sse_events(stream_app):
    async with AsyncClient(transport=ASGITransport(app=stream_app), base_url="http://test") as client:
        resp = await client.get("/api/v1/score/stream", params={"limit": 5, "rate": 0})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]
    assert len(events) == 5


@pytest.mark.asyncio
async def test_stream_rejects_bad_params(stream_app):
    async with AsyncClient(transport=ASGITransport(app=stream_app), base_url="http://test") as client:
        resp = await client.get("/api/v1/score/stream", params={"limit": 0})
    assert resp.status_code in {400, 422}


@pytest.mark.asyncio
async def test_stream_disabled_in_production(stream_app, monkeypatch):
    class _Prod:
        demo_mode = False

    app = stream_app
    app.dependency_overrides.pop(get_demo_replay, None)  # exercise the real gate
    monkeypatch.setattr("api.deps.get_settings", lambda: _Prod())
    async with AsyncClient(transport=ASGITransport(app=stream_app), base_url="http://test") as client:
        resp = await client.get("/api/v1/score/stream", params={"limit": 1, "rate": 0})
    assert resp.status_code == 409


def test_replay_does_not_change_global_random_state():
    import random

    random.seed(123)
    before = random.getstate()
    DemoReplay(seed=7)
    assert random.getstate() == before


def test_replay_delay_is_clamped(monkeypatch):
    delays = []
    monkeypatch.setattr("services.realtime_demo.time.sleep", delays.append)
    list(DemoReplay(seed=7).events(limit=2, rate=0.001))
    assert delays and max(delays) <= 2.0
