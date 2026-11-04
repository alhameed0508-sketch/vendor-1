"""LiveFeed turns mempool transactions into scored events without touching the network in tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.live_feed import LiveFeed  # noqa: E402


def _tx(txid, sender, receiver, sats=50_000_000):
    return {
        "txid": txid * 64,
        "vin": [{"is_coinbase": False, "prevout": {"scriptpubkey_address": sender, "value": sats + 1000}}],
        "vout": [{"scriptpubkey_address": receiver, "value": sats}],
        "status": {"confirmed": False},
    }


class FakeClient:
    def __init__(self, polls):
        self._polls = list(polls)  # list of lists of tx dicts, one list per poll
        self._by_id = {}
        self.fetched = []
        self.recent_calls = 0

    def inr_per_btc(self):
        return 1_000_000.0

    def recent_txids(self):
        self.recent_calls += 1
        batch = self._polls.pop(0) if self._polls else []
        for tx in batch:
            self._by_id[tx["txid"]] = tx
        return [tx["txid"] for tx in batch]

    def tx(self, txid):
        self.fetched.append(txid)
        return self._by_id[txid]


def _feed(client, **kw):
    return LiveFeed(client, poll_interval=0, sleep=lambda s: None, **kw)


def test_events_have_the_replay_shape_and_a_live_source():
    client = FakeClient([[_tx("a", "S1", "R1"), _tx("b", "S2", "R2")]])
    events = list(_feed(client).events(limit=2))
    assert len(events) == 2
    first = events[0]
    assert {"payment", "decision", "case_id", "ring_members", "risk_score", "latency_ms", "reasons", "counters"} <= set(first)
    assert first["source"] == "live"
    assert events[1]["counters"]["payments"] == 2
    assert events[1]["counters"]["accounts"] == 4


def test_partition_rebuilds_off_the_hot_path():
    assert LiveFeed(client=object())._scorer._background is True


def test_a_transaction_seen_twice_is_scored_once():
    client = FakeClient([[_tx("a", "S1", "R1")], [_tx("a", "S1", "R1"), _tx("b", "S2", "R2")]])
    events = list(_feed(client).events(limit=2))
    assert [e["payment"]["to_account"] for e in events] == ["R1", "R2"]
    assert len(client.fetched) == 2


def test_stops_at_the_time_budget():
    ticks = iter(range(0, 1000, 100))
    feed = LiveFeed(FakeClient([[]] * 50), poll_interval=0, sleep=lambda s: None, clock=lambda: next(ticks), max_seconds=250)
    assert list(feed.events()) == []


def test_gives_up_after_repeated_upstream_failures():
    class Down(FakeClient):
        def recent_txids(self):
            raise OSError("upstream down")

    with pytest.raises(RuntimeError, match="mempool.space"):
        list(_feed(Down([])).events(limit=1))


def test_fetches_a_bounded_number_of_new_transactions_per_poll():
    txs = [_tx(c, f"S{c}", f"R{c}") for c in "abcdef"]
    client = FakeClient([txs])
    list(_feed(client, max_fetch_per_poll=2).events(limit=2))
    assert len(client.fetched) == 2
