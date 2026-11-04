"""Guest mode: a password-free, view-only login for the public demo."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from api.deps import get_demo_replay
from api.v1.routes.auth import GUEST_ROLE, GUEST_USER
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from services.realtime_demo import DemoReplay

from infra.security.auth import create_access_token, create_refresh_token, decode_token

# Built directly: the guest endpoint allows 10 calls a minute, fewer than these tests make.
GUEST_HEADERS = {"Authorization": f"Bearer {create_access_token(GUEST_USER, GUEST_ROLE)}"}


def _use_env(monkeypatch, env: str) -> None:
    monkeypatch.setenv("ENV", env)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test_secret_key_for_testing_only_32chars")
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(monkeypatch):
    _use_env(monkeypatch, "development")
    from api.app import app

    app.dependency_overrides[get_demo_replay] = lambda: DemoReplay(seed=7)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_demo_replay, None)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_guest_login_issues_view_only_tokens(client):
    response = await client.post("/api/v1/auth/guest")

    assert response.status_code == 200
    data = response.json()["data"]
    access, refresh = decode_token(data["access_token"]), decode_token(data["refresh_token"])
    assert (access["sub"], access["role"], access["type"]) == ("guest", "GUEST", "access")
    assert (refresh["role"], refresh["type"]) == ("GUEST", "refresh")


@pytest.mark.asyncio
async def test_guest_login_is_off_outside_the_demo(monkeypatch):
    _use_env(monkeypatch, "production")
    from api.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/v1/auth/guest")
    get_settings.cache_clear()

    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/alerts",
        "/api/v1/kpi",
        "/api/v1/compliance/strs",
        "/api/v1/screening/stats",
        "/api/v1/benchmark/results",
        "/api/v1/score/stream?limit=1&rate=0",
    ],
)
async def test_guest_can_open_every_page(client, path):
    response = await client.get(path, headers=GUEST_HEADERS)

    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PATCH", "/api/v1/alerts/ALT_1", {"status": "CLOSED"}),
        ("POST", "/api/v1/compliance/str", {"alert_ids": ["ALT_1"], "account_ids": ["A"], "narrative": "x"}),
        ("POST", "/api/v1/compliance/str-export", {"alert_ids": ["ALT_1"]}),
        ("POST", "/api/v1/screening/screen", {"account_id": "A", "name": "x"}),
        ("POST", "/api/v1/feedback", {"alert_id": "ALT_1", "verdict": "CONFIRMED_MULE"}),
        ("GET", "/api/v1/compliance/str-pdf/ALT_1", None),
    ],
)
async def test_guest_cannot_change_anything(client, method, path, body):
    response = await client.request(method, path, json=body, headers=GUEST_HEADERS)

    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/compliance/strs", "/api/v1/screening/stats", "/api/v1/benchmark/results"])
async def test_staff_read_only_role_keeps_its_narrow_access(client, path):
    readonly = {"Authorization": f"Bearer {create_access_token('auditor', 'READONLY')}"}

    response = await client.get(path, headers=readonly)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_guest_tokens_stop_working_outside_the_demo(monkeypatch):
    _use_env(monkeypatch, "production")
    from api.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        page = await c.get("/api/v1/alerts", headers=GUEST_HEADERS)
        refresh = await c.post("/api/v1/auth/refresh", json={"token": create_refresh_token(GUEST_USER, GUEST_ROLE)})
    get_settings.cache_clear()

    assert page.status_code == 401
    assert refresh.status_code == 401
