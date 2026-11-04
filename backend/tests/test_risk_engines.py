"""Unit tests for the four engines behind the unified risk score (backend/intelligence)."""

from datetime import datetime, timedelta, timezone

import pytest
from intelligence.behaviour_engine import AdaptiveBehaviourEngine
from intelligence.beneficiary_engine import BeneficiaryIntelligenceEngine, KnownFraudRegistry, complaint_beneficiaries
from intelligence.contracts import DECISIVE, FAMILIARITY, STRONG, WEAK, EngineResult, Reason
from intelligence.mule_network import MuleNetworkIntel, ring_core
from intelligence.profiles import ProfileStore, event_seconds
from intelligence.session_engine import SessionIntegrityEngine
from intelligence.threat_feeds import DROP_URL, TOR_URL, ThreatFeeds, parse_drop, parse_tor

from models.community_detection.louvain_detector import Community, LouvainClusterDetector

IST = timezone(timedelta(hours=5, minutes=30))
T0 = datetime(2026, 10, 1, 9, 0, tzinfo=IST)


def _at(minutes=0, days=0):
    return T0 + timedelta(days=days, minutes=minutes)


def _session(device="PHONE-1", ip="10.0.0.5", city="Pune", sid="S1", **extra):
    return {
        "session_id": sid,
        "device_id": device,
        "ip": ip,
        "city": city,
        "lat": 18.52,
        "lon": 73.86,
        "auth_events": [],
        **extra,
    }


def _history(store, customer="C1", payee="SHOP", days=20, amount=500.0, device="PHONE-1", hour_minutes=0):
    for d in range(days):
        for k in range(2):
            when = _at(minutes=hour_minutes + 60 * k, days=d)
            store.commit_payment(
                customer,
                f"{payee}{k}",
                amount * (1 + 0.1 * k),
                event_seconds(when.isoformat()),
                device=device,
                place="Pune",
                session=_session(device),
                typing_ms=200.0,
            )


# ---------------------------------------------------------------- contracts
def test_noisy_or_score_and_familiarity_dampens_only_weak_reasons():
    res = EngineResult("x", (Reason("A", "a", 0.5, WEAK), Reason("B", "b", 0.5, STRONG)))
    assert res.score(0.0) == pytest.approx(1 - 0.5 * 0.5)
    # Full familiarity silences weak context but never strong evidence.
    assert res.score(1.0) == pytest.approx(0.5)
    assert not res.decisive
    assert EngineResult("x", (Reason("C", "c", 0.9, DECISIVE),)).decisive


def test_reason_rejects_unknown_kind_and_out_of_range_strength():
    with pytest.raises(ValueError):
        Reason("A", "a", 0.5, "maybe")
    with pytest.raises(ValueError):
        Reason("A", "a", 1.5, WEAK)


# ---------------------------------------------------------------- session engine
def test_session_engine_without_session_data_says_so():
    res = SessionIntegrityEngine().assess("C1", event_seconds(_at().isoformat()), None, None, None)
    assert res.data_available is False
    assert res.reasons == ()


def test_ip_change_inside_session_is_weak_but_device_change_is_strong():
    engine = SessionIntegrityEngine()
    store = ProfileStore()
    at = event_seconds(_at().isoformat())
    store.commit_payment("C1", "SHOP", 500, at, device="PHONE-1", place="Pune", session=_session(ip="10.0.0.5"))
    profile = store.customer("C1")
    ip_only = engine.assess("C1", at + 60, _session(ip="10.0.9.9"), profile, None)
    sd07 = [r for r in ip_only.reasons if r.code == "SD07"]
    assert sd07 and sd07[0].kind == WEAK
    device = engine.assess("C1", at + 60, _session(device="OTHER", ip="10.0.0.5"), profile, None)
    sd07 = [r for r in device.reasons if r.code == "SD07"]
    assert sd07 and sd07[0].kind == STRONG


def test_takeover_sequence_needs_reset_then_new_device_then_new_payee():
    engine = SessionIntegrityEngine()
    store = ProfileStore()
    _history(store)
    at = event_seconds(_at(days=21).isoformat())
    auth = [{"type": "password_reset", "at": (_at(days=21) - timedelta(minutes=10)).isoformat()}]
    res = engine.assess("C1", at, _session(device="NEW-PHONE", auth_events=auth), store.customer("C1"), at - 120)
    codes = {r.code: r for r in res.reasons}
    assert "SD08" in codes and codes["SD08"].strength >= 0.8
    # A password reset on its own (same phone, no new payee) is not a takeover.
    calm = engine.assess("C1", at, _session(auth_events=auth), store.customer("C1"), None)
    assert "SD08" not in {r.code for r in calm.reasons}


def test_threat_feed_hit_is_cited_with_its_source():
    feeds = ThreatFeeds(fetch=lambda url: {TOR_URL: "185.220.101.1\n", DROP_URL: '{"cidr":"192.0.2.0/24"}'}[url])
    feeds.refresh()
    engine = SessionIntegrityEngine(feeds=feeds)
    res = engine.assess("C1", event_seconds(_at().isoformat()), _session(ip="185.220.101.1"), None, None)
    sd04 = [r for r in res.reasons if r.code == "SD04"]
    assert sd04 and "Tor" in sd04[0].text


# ---------------------------------------------------------------- threat feeds
def test_parsers_skip_comments_and_bad_lines():
    assert parse_tor("# header\n1.2.3.4\nnot-an-ip\n") == ["1.2.3.4"]
    drop = '{"cidr":"10.1.0.0/16","sblid":"SBL1"}\n{"type":"metadata","records":1}\ngarbage'
    assert parse_drop(drop) == ["10.1.0.0/16"]


def test_failed_refresh_keeps_last_good_copy_and_reports_error(tmp_path):
    cache = tmp_path / "feeds.json"
    good = ThreatFeeds(cache_path=cache, fetch=lambda url: {TOR_URL: "5.6.7.8", DROP_URL: '{"cidr":"9.9.0.0/16"}'}[url])
    good.refresh()
    assert good.lookup("9.9.1.1")[0]["feed"] == "spamhaus_drop"

    def broken(url):
        raise OSError("network down")

    restarted = ThreatFeeds(cache_path=cache, fetch=broken)  # loads the disk cache
    status = restarted.refresh()
    assert restarted.lookup("5.6.7.8")[0]["feed"] == "tor_exit"
    assert all(f["error"] for f in status["feeds"])
    assert all(f["origin"] == "disk cache" for f in status["feeds"])


def test_disabled_feeds_never_fetch():
    calls = []
    feeds = ThreatFeeds(fetch=lambda url: calls.append(url) or "", enabled=False)
    feeds.refresh()
    feeds.start()
    assert calls == []
    assert all(f["stale"] for f in feeds.status()["feeds"])


# ---------------------------------------------------------------- beneficiary engine
def test_known_fraud_payee_is_decisive_and_open_complaint_is_strong():
    registry = KnownFraudRegistry(
        complaint_source=lambda: {"PAYEE-OPEN": "open", "PAYEE-DONE": "decided"}, background=False
    )
    registry.maybe_refresh()
    engine = BeneficiaryIntelligenceEngine(MuleNetworkIntel(), registry)
    store = ProfileStore()
    at = event_seconds(_at().isoformat())
    done = engine.assess("C1", "PAYEE-DONE", 5000, at, {}, store.customer("C1"), store.payee("PAYEE-DONE"), None)
    open_ = engine.assess("C1", "PAYEE-OPEN", 5000, at, {}, store.customer("C1"), store.payee("PAYEE-OPEN"), None)
    assert {r.code: r.kind for r in done.reasons}["BI01"] == DECISIVE
    assert {r.code: r.kind for r in open_.reasons}["BI01"] == STRONG


def test_complaint_beneficiaries_maps_decided_and_open_cases():
    class Service:
        cases = {
            "C1": {"beneficiary_account": "A", "decision": "x", "finding": {"category": "THIRD_PARTY_BREACH"}},
            "C2": {"beneficiary_account": "B", "status": "OPEN", "finding": {}},
            "C3": {"beneficiary_account": "C", "status": "OPEN", "finding": {"category": "NOT_FRAUD"}},
        }

        def list_cases(self):
            return {"cases": [{"complaint_id": k} for k in self.cases]}

        def get_case(self, cid):
            return self.cases[cid]

    assert complaint_beneficiaries(Service()) == {"A": "decided", "B": "open"}


def test_coached_payment_to_payee_added_minutes_ago():
    engine = BeneficiaryIntelligenceEngine(MuleNetworkIntel())
    store = ProfileStore()
    at = event_seconds(_at().isoformat())
    ctx = {"on_call": True, "note": "digital arrest settlement", "app_switch_count": 7, "amount_pasted": True}
    res = engine.assess("C1", "NEWPAYEE", 85_000, at, ctx, store.customer("C1"), store.payee("NEWPAYEE"), at - 300)
    codes = {r.code for r in res.reasons}
    assert {"BI06", "BI07", "BI08"} <= codes


def test_sanctions_match_needs_high_confidence():
    hits = [{"name": "Some Listed Person", "confidence": 0.95, "list": "UN"}]
    engine = BeneficiaryIntelligenceEngine(MuleNetworkIntel(), sanctions_search=lambda name: hits)
    store = ProfileStore()
    at = event_seconds(_at().isoformat())
    res = engine.assess(
        "C1", "P", 100, at, {"payee_name": "Some Listed Person"}, store.customer("C1"), store.payee("P"), None
    )
    assert "BI10" in {r.code for r in res.reasons}
    low = BeneficiaryIntelligenceEngine(
        MuleNetworkIntel(), sanctions_search=lambda name: [{**hits[0], "confidence": 0.5}]
    )
    res = low.assess(
        "C1", "P", 100, at, {"payee_name": "Some Listed Person"}, store.customer("C1"), store.payee("P"), None
    )
    assert "BI10" not in {r.code for r in res.reasons}


# ---------------------------------------------------------------- behaviour engine
def test_familiar_payee_suppresses_amount_anomaly():
    store = ProfileStore()
    _history(store)
    for d in range(3):  # the customer pays this payee a large sum every week
        store.commit_payment(
            "C1", "LANDLORD", 30_000, event_seconds(_at(days=2 + 7 * d).isoformat()), device="PHONE-1", place="Pune"
        )
    view = AdaptiveBehaviourEngine().assess(
        "LANDLORD", 31_000, event_seconds(_at(days=21).isoformat()), _session(), store.customer("C1")
    )
    assert "BH01" not in {r.code for r in view.result.reasons}
    assert "FC01" in {r.code for r in view.familiarity_reasons}
    assert view.familiarity >= 0.6


def test_unusual_amount_to_new_payee_is_flagged_as_context():
    store = ProfileStore()
    _history(store)
    view = AdaptiveBehaviourEngine().assess(
        "STRANGER", 80_000, event_seconds(_at(days=21).isoformat()), _session(), store.customer("C1")
    )
    bh01 = [r for r in view.result.reasons if r.code == "BH01"]
    assert bh01 and bh01[0].kind != DECISIVE
    assert view.personal_limit is not None


def test_new_customer_has_low_confidence():
    view = AdaptiveBehaviourEngine().assess(
        "X", 500, event_seconds(_at().isoformat()), _session(), ProfileStore().customer("NEW")
    )
    assert view.confidence == 0.0
    assert all(r.kind != FAMILIARITY for r in view.result.reasons)


# ---------------------------------------------------------------- mule network (core)
def _ring_window():
    """One ring (M0..M3) collecting from 12 one-off victims and passing money round; plus quiet customers."""
    window, n = [], 0

    def pay(a, b, amt, minutes, device="", ip=""):
        nonlocal n
        n += 1
        window.append(
            {
                "txn_id": f"T{n}",
                "from_account": a,
                "to_account": b,
                "amount": amt,
                "timestamp": _at(minutes=minutes).isoformat(),
                "device_id": device,
                "ip_address": ip,
            }
        )

    mules = ["M0", "M1", "M2", "M3"]
    for v in range(12):
        pay(f"VICTIM{v}", mules[v % 3], 9_500 + v, v * 5)
    for k, m in enumerate(mules[:3]):
        pay(m, "M3", 28_000, 90 + k, device="HERDER-PHONE", ip="203.0.113.7")
    pay("M3", "M0", 5_000, 120, device="HERDER-PHONE", ip="203.0.113.7")
    for c in range(10):
        pay(f"CUST{c}", f"SHOP{c % 3}", 400 + c, 200 + c)
    return window, mules


def test_ring_core_excludes_payers_who_only_paid_in():
    window, mules = _ring_window()
    community = Community(
        community_id=1,
        accounts=set(mules) | {f"VICTIM{v}" for v in range(12)},
        internal_edges=0,
        shared_devices=[],
        shared_ips=[],
        density=0.0,
        size=16,
    )
    detector = LouvainClusterDetector()
    detector.detect_clusters(window, [{"account_id": a} for a in mules])
    core, leaves = ring_core(
        community, window, [{"account_id": m, "account_age_days": 10} for m in mules], detector, {}
    )
    assert core is not None and core.accounts == set(mules)
    assert leaves == frozenset(f"VICTIM{v}" for v in range(12))
    assert core.shared_devices == ["HERDER-PHONE"]
    assert core.suspicion_score > 0


def test_accounts_attached_only_through_victims_are_not_ring_members():
    window, mules = _ring_window()
    # Two victims also pay their usual shop; Louvain can pull that shop into the ring's community.
    window += [
        {
            "txn_id": f"S{k}",
            "from_account": f"VICTIM{k}",
            "to_account": "VICTIMS-SHOP",
            "amount": 300,
            "timestamp": _at(minutes=300 + k).isoformat(),
            "device_id": "",
            "ip_address": "",
        }
        for k in range(2)
    ]
    victims = {f"VICTIM{v}" for v in range(12)}
    community = Community(
        community_id=1,
        accounts=set(mules) | victims | {"VICTIMS-SHOP"},
        internal_edges=0,
        shared_devices=[],
        shared_ips=[],
        density=0.0,
        size=17,
    )
    detector = LouvainClusterDetector()
    detector.detect_clusters(window, [])
    core, excluded = ring_core(community, window, [], detector, {})
    assert core.accounts == set(mules)
    assert "VICTIMS-SHOP" in excluded and victims <= excluded


def test_payer_with_its_own_mule_evidence_is_kept_in_the_core():
    window, mules = _ring_window()
    victims = {f"VICTIM{v}" for v in range(12)}
    community = Community(
        community_id=1,
        accounts=set(mules) | victims,
        internal_edges=0,
        shared_devices=[],
        shared_ips=[],
        density=0.0,
        size=16,
    )

    class Ev:
        smurf_score = 0.9

    detector = LouvainClusterDetector()
    detector.detect_clusters(window, [])
    core, leaves = ring_core(community, window, [], detector, {"VICTIM0": Ev()})
    assert core.accounts == set(mules) | {"VICTIM0"}
    assert leaves == frozenset(victims - {"VICTIM0"})


def test_ring_map_is_read_in_constant_time_and_dedupes_txns():
    intel = MuleNetworkIntel(refresh_every=1000)
    window, _ = _ring_window()
    for t in window:
        intel.add(t, allow_refresh=False)
        intel.add(t, allow_refresh=False)  # re-sent payment
    intel.refresh()
    assert intel.status()["payments_in_window"] == len(window)
    res = intel.assess("CUST1", "SHOP1")
    assert res.data_available and not res.decisive


def test_open_alert_members_raise_mn03():
    intel = MuleNetworkIntel(alert_members=lambda: frozenset({"ALERTED"}))
    intel.refresh()
    res = intel.assess("C1", "ALERTED")
    assert "MN03" in {r.code for r in res.reasons}


def test_alert_source_failure_keeps_last_good_set():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("alert store down")
        return frozenset({"ALERTED"})

    intel = MuleNetworkIntel(alert_members=flaky)
    intel.refresh()
    intel.refresh()
    assert "MN03" in {r.code for r in intel.assess("C1", "ALERTED").reasons}
