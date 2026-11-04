"""Bitcoin transactions from mempool.space become rupee payments between addresses."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data.adapters.mempool_adapter import MAX_PAYMENTS_PER_TX, tx_to_payments  # noqa: E402

INR_PER_BTC = 1_000_000.0  # round number: 1 BTC = ₹10 lakh
NOW = "2026-11-03T10:00:00+00:00"


def _vin(addr, sats):
    return {"is_coinbase": False, "prevout": {"scriptpubkey_address": addr, "value": sats}}


def _vout(addr, sats):
    return {"scriptpubkey_address": addr, "value": sats}


TX = {
    "txid": "a" * 64,
    "vin": [_vin("S1", 60_000_000), _vin("S2", 40_000_000)],
    "vout": [_vout("R1", 50_000_000), _vout("S1", 49_000_000)],  # S1 is change
    "status": {"confirmed": False},
}


def test_change_output_is_not_a_payment():
    payments = tx_to_payments(TX, INR_PER_BTC, NOW)
    assert {p["to_account"] for p in payments} == {"R1"}


def test_each_sender_pays_an_equal_share_in_rupees():
    payments = tx_to_payments(TX, INR_PER_BTC, NOW)
    assert sorted(p["from_account"] for p in payments) == ["S1", "S2"]
    assert all(p["amount"] == 0.5 * 1_000_000 / 2 for p in payments)


def test_payment_has_the_scorer_fields_and_unique_ids():
    payments = tx_to_payments(TX, INR_PER_BTC, NOW)
    assert len({p["txn_id"] for p in payments}) == len(payments)
    assert all(p["timestamp"] == NOW and p["device_id"] == "" for p in payments)


def test_confirmed_tx_uses_its_block_time():
    tx = {**TX, "status": {"confirmed": True, "block_time": 1_793_600_000}}
    assert tx_to_payments(tx, INR_PER_BTC, NOW)[0]["timestamp"].startswith("2026-")
    assert tx_to_payments(tx, INR_PER_BTC, NOW)[0]["timestamp"] != NOW


def test_coinbase_and_addressless_outputs_yield_nothing():
    coinbase = {"txid": "b" * 64, "vin": [{"is_coinbase": True}], "vout": [_vout("R1", 5)], "status": {}}
    op_return = {**TX, "vout": [{"scriptpubkey_type": "op_return", "value": 0}]}
    assert tx_to_payments(coinbase, INR_PER_BTC, NOW) == []
    assert tx_to_payments(op_return, INR_PER_BTC, NOW) == []


def test_payment_count_is_capped():
    big = {
        **TX,
        "vin": [_vin(f"S{i}", 10_000_000) for i in range(20)],
        "vout": [_vout(f"R{i}", 10_000_000) for i in range(20)],
    }
    assert len(tx_to_payments(big, INR_PER_BTC, NOW)) == MAX_PAYMENTS_PER_TX
