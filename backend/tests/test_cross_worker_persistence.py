"""Cross-worker detection-state persistence tests."""

import json

from cache.redis_client import RedisClient
from graph_engine.neo4j_client import Neo4jClient
from graph_engine.persistence import PersistenceLayer
from repositories.alert_repository import AlertRepository
from repositories.cache_keys import ALERTS_CACHE_KEY, DATASET_CACHE_KEY
from repositories.dataset_repository import DatasetRepository
from services.alert_service import AlertService


class SharedRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ttl=600):
        self.values[key] = value
        return True

    def delete(self, key):
        self.values.pop(key, None)
        return True


class ProcessPersistence:
    def __init__(self):
        self.dataset = None
        self.alerts = []

    def get_dataset(self):
        return self.dataset

    def set_dataset(self, dataset):
        self.dataset = dataset

    def get_alerts(self, severity=None, status=None, limit=50):
        return self.alerts[:limit]

    def get_alert(self, alert_id):
        return next(
            (alert for alert in self.alerts if alert["alert_id"] == alert_id),
            None,
        )

    def store_alerts(self, alerts):
        self.alerts = alerts

    def update_alert(self, alert_id, status=None, notes=None):
        return None

    def clear(self):
        self.dataset = None
        self.alerts = []


def test_dataset_is_visible_to_a_second_worker():
    shared = SharedRedis()
    first = DatasetRepository(ProcessPersistence(), shared)
    second = DatasetRepository(ProcessPersistence(), shared)
    dataset = {"accounts": [{"account_id": "A1"}], "transactions": []}

    first.set(dataset)

    assert second.get() == dataset
    assert shared.values[DATASET_CACHE_KEY] == dataset


def test_full_alert_payload_and_updates_are_shared_between_workers():
    shared = SharedRedis()
    first = AlertRepository(ProcessPersistence(), shared)
    second = AlertRepository(ProcessPersistence(), shared)
    alerts = [
        {
            "alert_id": "ALT-1",
            "severity": "CRITICAL",
            "status": "OPEN",
            "nodes": [{"account_id": "A1"}],
            "edges": [{"from_account": "A1", "to_account": "A2"}],
        }
    ]

    first.store_batch(alerts)
    loaded = second.find_by_id("ALT-1")
    updated = second.update("ALT-1", status="UNDER_REVIEW", notes="assigned")

    assert loaded["nodes"][0]["account_id"] == "A1"
    assert updated["status"] == "UNDER_REVIEW"
    assert first.find_by_id("ALT-1")["investigator_notes"] == "assigned"


def test_dataset_clear_removes_shared_dataset_and_alerts():
    shared = SharedRedis()
    shared.values[DATASET_CACHE_KEY] = {"accounts": []}
    shared.values[ALERTS_CACHE_KEY] = [{"alert_id": "ALT-1"}]
    repository = DatasetRepository(ProcessPersistence(), shared)

    repository.clear()

    assert DATASET_CACHE_KEY not in shared.values
    assert ALERTS_CACHE_KEY not in shared.values


def test_redis_client_supports_non_expiring_shared_state():
    calls = []

    class RawClient:
        def set(self, key, value, **kwargs):
            calls.append(("set", key, value, kwargs))

    client = RedisClient.__new__(RedisClient)
    client._available = True
    client._client = RawClient()

    assert client.set("persistent", {"value": 1}, ttl=None) is True
    assert client.set("expiring", {"value": 2}, ttl=60) is True
    assert calls[0][0] == "set"
    assert calls[0][3] == {}
    assert calls[1][0] == "set"
    assert calls[1][3] == {"ex": 60}


def test_redis_ping_reflects_live_client_state():
    class RawClient:
        def ping(self):
            return True

    client = RedisClient.__new__(RedisClient)
    client._available = True
    client._client = RawClient()

    assert client.ping() is True
    client._available = False
    assert client.ping() is False


def test_redis_close_releases_client_and_marks_it_unavailable():
    class RawClient:
        closed = False

        def close(self):
            self.closed = True

    raw = RawClient()
    client = RedisClient.__new__(RedisClient)
    client._available = True
    client._client = raw

    client.close()

    assert raw.closed is True
    assert client.available is False
    assert client._client is None


def test_neo4j_alert_round_trip_preserves_full_investigation_payload():
    calls = []
    client = Neo4jClient.__new__(Neo4jClient)
    alert = {
        "alert_id": "ALT-9",
        "severity": "HIGH",
        "confidence": 0.91,
        "risk_score": 84,
        "total_amount": 125000,
        "txn_count": 7,
        "account_count": 2,
        "status": "OPEN",
        "nodes": [{"account_id": "A1", "classification": "COMPLICIT"}],
        "edges": [{"from_account": "A1", "to_account": "A2", "amount": 50000}],
        "evidence": {"reason_codes": ["RAPID_MOVEMENT"]},
    }

    def capture(query, **params):
        calls.append((query, params))
        return [{"props": params}]

    client.run = capture
    client.upsert_alert(alert)

    query, params = calls[0]
    assert "payload_json" in query
    assert json.loads(params["payload_json"])["nodes"] == alert["nodes"]
    restored = PersistenceLayer._restore_alert(
        {
            "payload_json": params["payload_json"],
            "status": "UNDER_REVIEW",
            "investigator_notes": "assigned",
        }
    )
    assert restored["edges"] == alert["edges"]
    assert restored["status"] == "UNDER_REVIEW"
    assert restored["investigator_notes"] == "assigned"


def test_persistence_clear_deletes_durable_alerts():
    class Neo4j:
        def __init__(self):
            self.deleted = False

        def delete_all_alerts(self):
            self.deleted = True

    persistence = PersistenceLayer.__new__(PersistenceLayer)
    persistence._neo4j = Neo4j()
    persistence._use_neo4j = True
    persistence._memory = {"alerts": [{"alert_id": "ALT-1"}], "dataset": {"rows": 1}}

    persistence.clear()

    assert persistence._neo4j.deleted is True
    assert persistence._memory["alerts"] == []
    assert persistence._memory["dataset"] is None


def test_alert_list_does_not_return_a_stale_service_cache():
    class Repo:
        alerts = [{"alert_id": "NEW"}]

        def find_all(self, severity=None, status=None, limit=50):
            return self.alerts[:limit]

    class StaleCache:
        def get(self, key):
            return {"total": 1, "alerts": [{"alert_id": "OLD"}]}

    service = AlertService(alert_repo=Repo(), cache=StaleCache())

    assert service.list_alerts()["alerts"] == [{"alert_id": "NEW"}]
