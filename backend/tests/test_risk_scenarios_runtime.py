"""Scenarios from the brief, the journey simulator, the live feed and demo traffic (no network)."""

from collections import Counter

import pytest
from intelligence.contracts import APPROVE, REVIEW, STEP_UP
from intelligence.decision_store import DecisionStore
from intelligence.engine import UnifiedRiskEngine
from intelligence.mule_network import MuleNetworkIntel
from intelligence.runtime import DemoTraffic, RiskLiveFeed
from intelligence.scenarios import SCENARIOS, list_scenarios, run_scenario
from intelligence.simulator import JourneySimulator, split_by_day


# ------------------------------------------------------------- scenarios
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_every_scenario_matches_its_written_expectation(name):
    result = run_scenario(name)
    assert result["matched_expectation"], [(d["band"], d["score"]) for d in result["decisions"]]
    assert all(d["source"] == "scenario" for d in result["decisions"])
    assert result["data"].startswith("synthetic")


def test_customer_a_vs_b_same_amount_different_outcome():
    a, b = run_scenario("customer_a_vs_b")["decisions"]
    assert a["band"] == APPROVE and b["band"] == STEP_UP
    assert any("no evidence of fraud" in c for c in b["explanation"]["false_positive_controls"])


def test_app_scam_cites_the_mule_core():
    (d,) = run_scenario("app_scam_mule_payee")["decisions"]
    assert d["band"] == REVIEW
    assert {"MN02", "BI07"} <= {r["code"] for r in d["reasons"]}


def test_scenarios_write_to_a_given_store_and_are_listed():
    store = DecisionStore()
    run_scenario("genuine_traveller", store=store)
    assert store.recent(source="scenario")
    assert {s["name"] for s in list_scenarios()} == set(SCENARIOS)


# ------------------------------------------------------------- simulator
def test_simulator_is_deterministic_and_time_ordered():
    a = JourneySimulator(seed=5, customers=20, rings=1).run(days=6, fraud_from_day=3)
    b = JourneySimulator(seed=5, customers=20, rings=1).run(days=6, fraud_from_day=3)
    assert [e.event for e in a] == [e.event for e in b]
    stamps = [e.event["timestamp"] for e in a]
    assert stamps == sorted(stamps)
    assert len({e.event["txn_id"] for e in a}) == len(a)


def test_fraud_and_traps_start_only_after_the_warm_up():
    sim = JourneySimulator(seed=5, customers=30, rings=1)
    events = sim.run(days=8, fraud_from_day=5, fraud_per_day=6, traps_per_day=6)
    history, live = split_by_day(events, sim.start, 5)
    kinds_before = Counter(e.kind for e in history)
    assert set(kinds_before) <= {"everyday", "instalment_big_payee", "mule_inbound", "mule_forward"}
    assert any(e.kind.startswith("trap_") for e in live)
    assert {e.label for e in events} == {"fraud", "genuine"}


def test_accounts_carry_no_labels():
    sim = JourneySimulator(seed=1, customers=5, rings=1)
    for account in sim.accounts():
        assert set(account) == {"account_id", "account_age_days"}


# ------------------------------------------------------------- live feed (fake mempool client)
def _tx(txid, sender, receiver, sats=50_000_000):
    return {
        "txid": txid * 64,
        "vin": [{"is_coinbase": False, "prevout": {"scriptpubkey_address": sender, "value": sats + 1000}}],
        "vout": [{"scriptpubkey_address": receiver, "value": sats}],
        "status": {"confirmed": False},
    }


class FakeClient:
    def __init__(self, polls, fail=False):
        self._polls = list(polls)
        self._by_id = {}
        self.fail = fail

    def inr_per_btc(self):
        if self.fail:
            raise OSError("offline")
        return 1_000_000.0

    def recent_txids(self):
        batch = self._polls.pop(0) if self._polls else []
        for tx in batch:
            self._by_id[tx["txid"]] = tx
        return [tx["txid"] for tx in batch]

    def tx(self, txid):
        return self._by_id[txid]


def test_live_feed_scores_real_shaped_payments_with_provenance():
    feed = RiskLiveFeed(
        FakeClient([[_tx("a", "S1", "R1"), _tx("b", "S2", "R2")]]), poll_interval=0, sleep=lambda s: None
    )
    events = list(feed.events(limit=2))
    assert len(events) == 2
    for event in events:
        assert event["source"] == "live"
        assert event["decision"]["source"] == "live" and event["decision"]["label"] is None
        assert event["provenance"]["url"].startswith("https://mempool.space/tx/")
        assert event["decision"]["explanation"]["engines"]["session_device"]["data_available"] is False


def test_live_feed_uses_a_private_engine():
    shared = UnifiedRiskEngine()
    feed = RiskLiveFeed(FakeClient([[_tx("c", "S1", "R1")]]), poll_interval=0, sleep=lambda s: None)
    list(feed.events(limit=1))
    assert feed.engine is not shared and shared.store.sequence == 0


def test_live_feed_reports_an_unreachable_provider():
    with pytest.raises(RuntimeError, match="unreachable"):
        list(RiskLiveFeed(FakeClient([], fail=True), poll_interval=0, sleep=lambda s: None).events(limit=1))


# ------------------------------------------------------------- demo traffic
def test_demo_traffic_feeds_labelled_synthetic_decisions():
    engine = UnifiedRiskEngine(mule=MuleNetworkIntel(), store=DecisionStore())
    traffic = DemoTraffic(engine, rate=50, customers=20, rings=1, sleep=lambda s: None)
    traffic.touch()
    traffic._thread.join(timeout=0.01)
    deadline = 0
    while engine.store.sequence < 20 and deadline < 2000:
        traffic._thread.join(timeout=0.01)
        deadline += 1
    traffic.stop()
    traffic._thread.join(timeout=5)
    decisions = engine.store.recent(limit=20)
    assert decisions and all(d.source == "synthetic" and d.label in ("fraud", "genuine") for d in decisions)
    assert traffic.status()["warm_up_payments"] > 0


def test_store_tailing_returns_decisions_after_a_sequence():
    engine = UnifiedRiskEngine()
    first = engine.store.sequence
    sim = JourneySimulator(seed=2, customers=5, rings=1)
    for e in sim.run(days=2, fraud_from_day=99)[:5]:
        engine.assess(e.event, commit=True, source="synthetic", label=e.label)
    tail = engine.store.since(first)
    assert [s for s, _ in tail] == list(range(first + 1, first + 6))
    assert engine.store.since(tail[-1][0]) == []
