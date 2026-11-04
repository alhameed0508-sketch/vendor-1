"""Circular fund flow (CF01): real loops are found; refunds, merchants and slow or draining loops are not."""

import time
from datetime import datetime, timedelta

from fraud_modules.cycles import CODE, find_cycles
from fraud_modules.registry import Status, get_module
from fraud_modules.rule_modules import TRANSACTION_AML

T0 = datetime(2026, 9, 1, 10, 0)


def _t(a, b, amount, hours):
    return {
        "txn_id": f"{a}{b}{hours}",
        "from_account": a,
        "to_account": b,
        "amount": amount,
        "timestamp": (T0 + timedelta(hours=hours)).isoformat(),
    }


def _loop(hours=(0, 5, 9), amounts=(100_000, 97_000, 95_000)):
    (h1, h2, h3), (a1, a2, a3) = hours, amounts
    return [_t("A", "B", a1, h1), _t("B", "C", a2, h2), _t("C", "A", a3, h3)]


def test_a_forward_in_time_loop_with_the_money_preserved_is_found():
    result = find_cycles(_loop())
    assert len(result["cycles"]) == 1
    cycle = result["cycles"][0]
    assert set(cycle["accounts"]) == {"A", "B", "C"}
    assert cycle["span"] == timedelta(hours=9)


def test_a_loop_whose_hops_are_out_of_time_order_is_not_a_flow():
    # A->B at 0 h, B->C at 9 h, C->A at 5 h: no starting point gives forward-moving hops
    assert find_cycles(_loop(hours=(0, 9, 5)))["cycles"] == []


def test_any_starting_point_counts():
    # the loop starts at B: B->C at 1 h, C->A at 2 h, A->B at 3 h
    assert len(find_cycles(_loop(hours=(3, 1, 2)))["cycles"]) == 1


def test_slow_or_draining_loops_are_ignored():
    assert find_cycles(_loop(hours=(0, 100, 200)))["cycles"] == []  # more than 7 days
    assert find_cycles(_loop(amounts=(100_000, 90_000, 10_000)))["cycles"] == []  # most of the money left


def test_unrelated_payments_that_happen_to_form_a_loop_are_not_flagged():
    # friends settling up: a loop, in time order, but the amounts are unrelated (0.55x, then 1.98x)
    assert find_cycles(_loop(amounts=(39_333, 21_616, 42_822)))["cycles"] == []


def test_genuine_accounts_in_the_synthetic_dataset_form_no_flagged_loops():
    import random

    from data.synthetic.generator import build_adversarial_dataset

    random.seed(11)
    ds = build_adversarial_dataset(num_clusters=3, num_legit_accounts=60, num_adversarial=20)
    roles = {a["account_id"]: a.get("role") for a in ds["accounts"]}
    flagged = {a for c in find_cycles(ds["transactions"])["cycles"] for a in c["accounts"]}
    assert not any(roles.get(a) == "LEGITIMATE" for a in flagged)


def test_refunds_self_transfers_and_merchants_are_not_loops():
    refund = [_t("A", "B", 500, 0), _t("B", "A", 500, 2)]
    self_transfer = [_t("A", "A", 1_000, 0)]
    merchant = [_t(f"CUST{i}", "SHOP", 300, i) for i in range(30)] + [_t("SHOP", "SUPPLIER", 8_000, 40)]
    assert find_cycles(refund + self_transfer + merchant)["cycles"] == []


def test_a_dense_graph_is_capped_not_stalled():
    nodes = [f"N{i}" for i in range(14)]
    dense = [_t(a, b, 1_000, i % 24) for i, (a, b) in enumerate((a, b) for a in nodes for b in nodes if a != b)]
    started = time.perf_counter()
    result = find_cycles(dense)
    assert result["capped"] is True
    assert time.perf_counter() - started < 30


def test_the_transaction_module_reports_cf01_findings():
    rows = _loop() + [_t("X", "Y", 200, 1)]
    run = TRANSACTION_AML.run([], rows)
    cf = [f for f in run.findings if f.rule_code == CODE]
    assert {f.account_id for f in cf} == {"A", "B", "C"}
    assert all("Circular fund flow" in f.explanation and "within 9.0 h" in f.explanation for f in cf)
    assert CODE in run.signals_run


def test_registry_reflects_what_is_now_implemented():
    caps = {c.name: c.status for c in get_module("transaction_aml").capabilities}
    assert caps["Circular fund flow"] == Status.IMPLEMENTED
    upi = {c.name: c.status for c in get_module("upi").capabilities}
    assert upi["Session and IP anomalies"] == Status.IMPLEMENTED
    assert upi["High-risk UPI handle pattern"] == Status.PARTIAL  # still needs upi_id data
    assert get_module("loan").status == Status.PLANNED  # nothing built for loans yet


def test_the_registry_note_states_the_rule_the_code_applies():
    from fraud_modules.cycles import HOP_RATIO_BAND, MAX_LENGTH, MIN_LENGTH, WINDOW

    note = next(c.note for c in get_module("transaction_aml").capabilities if c.name == "Circular fund flow")
    low, high = HOP_RATIO_BAND
    assert f"{low}-{high}x" in note and f"{MIN_LENGTH}-{MAX_LENGTH} accounts" in note and f"{WINDOW.days} days" in note
