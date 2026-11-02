"""
Live Bitcoin payments from mempool.space (public API, no key) as MuleCatch payments.

A Bitcoin transaction pays from its input addresses to its output addresses. Outputs that return
to an input address are change and are not payments. With several inputs, each sender is assumed to
pay an equal share, because the chain does not say who funded which output. Satoshis are converted
to rupees at the current BTC/USD (mempool.space) and USD/INR (frankfurter.dev) rates so the scorer's
rupee thresholds keep their meaning.

The data is real and unlabelled: nothing here says which addresses are mules, so a flag is a lead
and no accuracy can be claimed from it. Addresses are not bank accounts, and the detector was not
built for Bitcoin.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Mapping

MEMPOOL_API = "https://mempool.space/api"
INR_RATE_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=INR"
SATS_PER_BTC = 100_000_000
MAX_PAYMENTS_PER_TX = 8  # a 500-output payout must not flood the scorer
MIN_PAYMENT_INR = 1.0
HTTP_TIMEOUT_S = 8.0
USER_AGENT = "mulecatch-live-feed/1.0"


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def tx_to_payments(tx: Mapping, inr_per_btc: float, observed_at: str) -> List[Dict]:
    """Payments implied by one mempool.space transaction (empty for coinbase or script-only outputs)."""
    senders = list(
        dict.fromkeys(
            addr
            for vin in tx.get("vin", [])
            if not vin.get("is_coinbase") and (addr := (vin.get("prevout") or {}).get("scriptpubkey_address"))
        )
    )
    if not senders:
        return []
    receivers = sorted(
        (
            (o["scriptpubkey_address"], o["value"])
            for o in tx.get("vout", [])
            if o.get("scriptpubkey_address") and o["scriptpubkey_address"] not in senders and o.get("value", 0) > 0
        ),
        key=lambda r: -r[1],
    )
    status = tx.get("status") or {}
    when = _iso(status["block_time"]) if status.get("confirmed") and status.get("block_time") else observed_at
    payments = []
    for to_addr, sats in receivers:
        amount = sats / SATS_PER_BTC * inr_per_btc / len(senders)
        if amount < MIN_PAYMENT_INR:
            continue
        for sender in senders:
            payments.append(
                {
                    "txn_id": f"{tx['txid'][:16]}:{len(payments)}",
                    "from_account": sender,
                    "to_account": to_addr,
                    "amount": amount,
                    "timestamp": when,
                    "device_id": "",
                    "ip_address": "",
                    "upi_id": "",
                }
            )
    return payments[:MAX_PAYMENTS_PER_TX]


def _get_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:  # noqa: S310 - fixed https hosts
        try:
            return json.load(response)
        except ValueError as exc:  # a proxy error page is an upstream failure, not a crash
            raise OSError(f"invalid JSON from {url}") from exc


class MempoolClient:
    """Thin read-only client for the two public endpoints the live feed needs."""

    def recent_txids(self) -> List[str]:
        return [t["txid"] for t in _get_json(f"{MEMPOOL_API}/mempool/recent")]

    def tx(self, txid: str) -> Dict:
        return _get_json(f"{MEMPOOL_API}/tx/{txid}")

    def inr_per_btc(self) -> float:
        usd = _get_json(f"{MEMPOOL_API}/v1/prices")["USD"]
        inr = _get_json(INR_RATE_URL)["rates"]["INR"]
        return float(usd) * float(inr)
