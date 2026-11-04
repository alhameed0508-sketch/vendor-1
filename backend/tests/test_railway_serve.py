"""Railway entrypoint: startup guard, API/SPA routing and static-file containment."""

import importlib
import os
import sys

import pytest
from core.config import Settings, get_settings
from starlette.testclient import TestClient

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SAFE_ENV = {
    "AUTH_ENABLED": "true",
    "DEMO_INVESTIGATOR_PASSWORD": "investigator-demo-pass",
    "DEMO_SUPERVISOR_PASSWORD": "supervisor-demo-pass",
    "DEMO_ADMIN_PASSWORD": "admin-demo-password",
}
STRONG_SECRET = "railway-test-secret-with-more-than-32-characters"


@pytest.fixture(scope="module")
def serve():
    """Import railway.serve under a safe environment, then restore the suite's settings."""
    with pytest.MonkeyPatch.context() as mp:
        for name, value in SAFE_ENV.items():
            mp.setenv(name, value)
        mp.syspath_prepend(REPO_ROOT)
        get_settings.cache_clear()
        sys.modules.pop("railway.serve", None)
        module = importlib.import_module("railway.serve")
        yield module
    get_settings.cache_clear()


@pytest.fixture
def build_dir(serve, tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>app shell</html>", encoding="utf-8")
    (tmp_path / "static" / "js").mkdir(parents=True)
    (tmp_path / "static" / "js" / "main.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("outside the build", encoding="utf-8")
    monkeypatch.setattr(serve, "BUILD_DIR", tmp_path.resolve())
    monkeypatch.setattr(serve, "INDEX_HTML", tmp_path.resolve() / "index.html")
    return tmp_path


def _settings(**overrides) -> Settings:
    values = {"auth_enabled": True, "jwt_secret": STRONG_SECRET, **overrides}
    return Settings(**values)


def test_guard_refuses_when_auth_is_off(serve):
    with pytest.raises(RuntimeError, match="AUTH_ENABLED"):
        serve.require_safe_settings(_settings(auth_enabled=False), env=SAFE_ENV)


def test_guard_refuses_a_weak_jwt_secret(serve):
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        serve.require_safe_settings(_settings(jwt_secret="short"), env=SAFE_ENV)


def test_guard_refuses_published_demo_passwords(serve):
    env = {**SAFE_ENV, "DEMO_ADMIN_PASSWORD": "admin@2024"}
    with pytest.raises(RuntimeError, match="DEMO_ADMIN_PASSWORD"):
        serve.require_safe_settings(_settings(), env=env)


def test_guard_accepts_a_safe_configuration(serve):
    serve.require_safe_settings(_settings(), env=SAFE_ENV)


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/api/v1/alerts", True),
        ("/health", True),
        ("/ready", True),
        ("/docs", True),
        ("/openapi.json", True),
        ("/", False),
        ("/queue", False),
        ("/alert/ALT_123", False),
        ("/metrics", False),
        ("/internal/metrics", False),
        ("/apix", False),
    ],
)
def test_api_routing(serve, path, expected):
    assert serve.is_api_path(path) is expected


def test_static_files_stay_inside_the_build(serve, build_dir):
    assert serve.static_file("/static/js/main.js") == (build_dir / "static" / "js" / "main.js").resolve()
    assert serve.static_file("/../secret.txt") is None
    assert serve.static_file("/static/../../secret.txt") is None
    assert serve.static_file("/") is None


def test_client_routes_get_the_app_shell(serve, build_dir):
    client = TestClient(serve.app)
    response = client.get("/alert/ALT_123")
    assert response.status_code == 200
    assert "app shell" in response.text
    assert response.headers["cache-control"] == "no-cache"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_hashed_assets_are_cached_for_a_year(serve, build_dir):
    response = TestClient(serve.app).get("/static/js/main.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["cache-control"]


def test_metrics_and_non_get_requests_are_not_served(serve, build_dir):
    client = TestClient(serve.app)
    assert client.get("/internal/metrics").status_code == 404
    assert client.get("/metrics").status_code == 404
    assert client.post("/queue").status_code == 404


def test_api_requests_reach_fastapi(serve, build_dir):
    response = TestClient(serve.app).get("/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"
