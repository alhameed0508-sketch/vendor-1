"""STR_FILED may only be set by ADMIN/SUPERVISOR and only when an STR exists for the alert."""

import pytest
from api.deps import get_alert_service, get_detection_service, get_str_service
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from middleware.auth import get_current_user
from repositories.str_repository import STRRepository
from services.str_service import STRService


class FakeDetection:
    def ensure_alerts(self):
        return []


class FakeAlerts:
    def __init__(self):
        self.updates = []

    def update_alert(self, alert_id, status, notes, user_id):
        self.updates.append((alert_id, status, notes))
        return {"alert_id": alert_id, "status": status}


def make_str_service(alert_ids=None):
    svc = STRService(STRRepository())
    if alert_ids:
        svc.create_str(alert_ids=alert_ids, account_ids=["ACC1"], narrative="n")
    return svc


def test_has_str_for_alert():
    svc = make_str_service(["ALT-1"])
    assert svc.has_str_for_alert("ALT-1") is True
    assert svc.has_str_for_alert("ALT-2") is False


@pytest.fixture()
def guard_app(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    from api.app import app

    state = {"role": "ADMIN", "alerts": FakeAlerts(), "str": make_str_service(["ALT-1"])}
    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1", "role": state["role"]}
    app.dependency_overrides[get_detection_service] = lambda: FakeDetection()
    app.dependency_overrides[get_alert_service] = lambda: state["alerts"]
    app.dependency_overrides[get_str_service] = lambda: state["str"]
    yield app, state
    for dep in (get_current_user, get_detection_service, get_alert_service, get_str_service):
        app.dependency_overrides.pop(dep, None)
    get_settings.cache_clear()


async def patch(app, alert_id, status="STR_FILED"):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        return await c.patch(f"/api/v1/alerts/{alert_id}", json={"status": status})


@pytest.mark.asyncio
async def test_str_filed_allowed_for_admin_with_existing_str(guard_app):
    app, state = guard_app
    assert (await patch(app, "ALT-1")).status_code == 200
    assert state["alerts"].updates == [("ALT-1", "STR_FILED", None)]


@pytest.mark.asyncio
async def test_str_filed_rejected_without_str(guard_app):
    app, state = guard_app
    assert (await patch(app, "ALT-2")).status_code == 409
    assert state["alerts"].updates == []


@pytest.mark.asyncio
async def test_str_filed_rejected_for_non_approver_role(guard_app):
    app, state = guard_app
    state["role"] = "ANALYST"
    assert (await patch(app, "ALT-1")).status_code == 403
    assert state["alerts"].updates == []


@pytest.mark.asyncio
async def test_other_statuses_unaffected(guard_app):
    app, state = guard_app
    state["role"] = "ANALYST"
    assert (await patch(app, "ALT-2", "RESOLVED")).status_code == 200
