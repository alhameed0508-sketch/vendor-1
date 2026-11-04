"""The Louvain partition can rebuild off the hot path so a stale partition never stalls a payment."""

import random
import threading

import pytest
import services.realtime_scorer as scorer_module
from services.realtime_scorer import RealtimeScorer

from data.synthetic.generator import build_adversarial_dataset

LABEL_FIELDS = ("role", "high_risk", "cluster_id", "is_suspicious", "pattern")


def _strip(rows):
    return [{k: v for k, v in r.items() if k not in LABEL_FIELDS} for r in rows]


@pytest.fixture(scope="module")
def data():
    random.seed(11)
    ds = build_adversarial_dataset(num_clusters=2, num_legit_accounts=40, num_adversarial=5)
    txns = sorted(_strip(ds["transactions"]), key=lambda t: t["timestamp"])
    return _strip(ds["accounts"]), txns[:60], txns[60:]


class _GatedDetector:
    """Stands in for Louvain: counts calls and blocks the refresh until released."""

    calls = 0
    release = threading.Event()
    real = scorer_module.LouvainClusterDetector

    def detect_clusters(self, window, accounts):
        type(self).calls += 1
        if threading.current_thread() is not threading.main_thread():
            type(self).release.wait(timeout=5)
        return self.real().detect_clusters(window, accounts)


@pytest.fixture
def gated(monkeypatch):
    _GatedDetector.calls = 0
    _GatedDetector.release = threading.Event()
    monkeypatch.setattr(scorer_module, "LouvainClusterDetector", _GatedDetector)
    yield _GatedDetector
    _GatedDetector.release.set()


def test_stale_partition_does_not_block_the_payment(data, gated):
    accounts, history, live = data
    scorer = RealtimeScorer(accounts, history, community_refresh_every=3, background_refresh=True)
    scorer.score_payment(live[0])  # first call has nothing cached, so it builds the partition inline
    for txn in live[1:5]:  # 4 commits in total: the partition is now stale
        scorer.score_payment(txn)
    assert scorer.refresh_pending()  # a rebuild is running, held at the gate
    calls_before = gated.calls
    scorer.score_payment(live[5])  # returns without waiting for the held rebuild
    assert gated.calls == calls_before  # and did not start a second one
    gated.release.set()
    scorer.wait_for_refresh()
    assert not scorer.refresh_pending()


def test_finished_refresh_replaces_the_partition(data):
    accounts, history, live = data
    scorer = RealtimeScorer(accounts, history, community_refresh_every=2, background_refresh=True)
    for txn in live[:5]:
        scorer.score_payment(txn)
    scorer.wait_for_refresh()
    assert scorer._cached[0] >= 3  # a rebuild landed after the first inline one


def test_default_scorer_still_rebuilds_inline(data, gated):
    accounts, history, live = data
    scorer = RealtimeScorer(accounts, history, community_refresh_every=2)
    gated.release.set()
    for txn in live[:5]:
        scorer.score_payment(txn)
    assert not scorer.refresh_pending()
    assert gated.calls >= 2  # rebuilt on the calling thread
