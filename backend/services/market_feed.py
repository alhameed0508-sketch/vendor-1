"""Live stock-exchange trades, checked as they arrive (see data/adapters/market_adapter.py).

A second real-time source next to the public payment feed, so the live views need no synthetic
data. Trades have no accounts behind them, so the mule-network scorer does not apply; two plain
market-surveillance checks do, each measured against the same stock's own recent trading:

- MK01 unusually large print: at least ``SIZE_MULTIPLE`` times the stock's median print value
  over its last ``HISTORY`` prints (after ``MIN_HISTORY`` prints, so a cold start never flags).
- MK02 sharp price move: the price moved at least ``MOVE_PCT`` percent within ``MOVE_WINDOW_S``.

Calibrated on two minutes of live Tokyo, Seoul and Sydney trading on 2026-11-05 (494 prints): 12 prints
(2.4%) were flagged, all by MK01, two of them also by MK02. There are no labels, so a flag is a lead
for a person, never a catch.
Events have the same shape as the payment feeds, with the stock as ``from_account`` and the
exchange as ``to_account``, plus a ``trade`` block.
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Iterator, List, Optional, Tuple

from data.adapters.market_adapter import WATCHLIST, MarketClient, TickTape, Trade

SOURCE = "market"
SIZE_MULTIPLE = 10.0
HISTORY = 60
MIN_HISTORY = 15
MIN_FLAG_INR = 5_00_000.0
MOVE_PCT = 0.5
MOVE_WINDOW_S = 60.0
MAX_STREAM_SECONDS = 300.0
QUIET_SECONDS = 45.0
IDLE_POLL_S = 5.0
CLOSED_NOTICE = (
    "No exchange on the watchlist is trading right now (Tokyo, Seoul, Hong Kong, Sydney, NSE, "
    "Frankfurt, New York). Try again during market hours."
)


def _rupees(value: float) -> str:
    if value >= 1e7:
        return f"₹{value / 1e7:.1f}Cr"
    if value >= 1e5:
        return f"₹{value / 1e5:.1f}L"
    return f"₹{value:,.0f}"


class MarketScorer:
    """Per-stock baselines; each trade is compared with its own stock's recent prints."""

    def __init__(self):
        self._values: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=HISTORY))
        self._prices: Dict[str, Deque[Tuple[float, float]]] = defaultdict(deque)

    def score(self, trade: Trade) -> Tuple[str, float, List[str]]:
        name = trade.listing.name
        reasons: List[str] = []
        risk = 0.0
        history = self._values[name]
        if len(history) >= MIN_HISTORY:
            median = statistics.median(history)
            if median > 0 and trade.value_inr >= max(MIN_FLAG_INR, SIZE_MULTIPLE * median):
                ratio = trade.value_inr / median
                reasons.append(
                    f"MK01: Unusually large print: {_rupees(trade.value_inr)} at once, {ratio:.0f}x this stock's recent median"
                )
                risk = max(risk, min(0.95, 0.55 + 0.01 * ratio))
        history.append(trade.value_inr)

        seconds = trade.time_ms / 1000 if trade.time_ms else time.time()
        window = self._prices[name]
        window.append((seconds, trade.price))
        while window and seconds - window[0][0] > MOVE_WINDOW_S:
            window.popleft()
        start_price = window[0][1]
        move = (trade.price / start_price - 1) * 100 if start_price else 0.0
        if abs(move) >= MOVE_PCT:
            span = max(1.0, seconds - window[0][0])
            reasons.append(f"MK02: Sharp price move: {move:+.2f}% in {span:.0f} s")
            risk = max(risk, min(0.9, 0.5 + 0.2 * abs(move)))
        if len(reasons) > 1:
            risk = min(0.99, risk + 0.1)
        return ("FLAG" if reasons else "PASS"), round(risk, 3), reasons


class MarketFeed:
    def __init__(
        self,
        client: Optional[MarketClient] = None,
        max_seconds: float = MAX_STREAM_SECONDS,
        quiet_seconds: float = QUIET_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = client or MarketClient()
        self._max_seconds = max_seconds
        self._quiet = quiet_seconds
        self._clock = clock

    def events(self, limit: Optional[int] = None, rate: float = 0.0) -> Iterator[dict]:
        """One event per trade until ``limit`` trades, the time budget, or a quiet market. ``rate`` is ignored."""
        try:
            fx = self._client.inr_per_unit()
        except OSError as exc:
            raise RuntimeError(f"exchange rates unavailable: {exc}") from exc
        tape, scorer = TickTape(fx), MarketScorer()
        started = last_trade = self._clock()
        trades = flagged = 0
        stocks: set = set()
        try:
            for tick in self._client.ticks([item.symbol for item in WATCHLIST], idle_timeout=IDLE_POLL_S):
                now = self._clock()
                if now - started >= self._max_seconds or (limit is not None and trades >= limit):
                    return
                trade = tape.observe(tick) if tick is not None else None
                if trade is None:
                    if now - last_trade >= self._quiet:
                        yield {"source": SOURCE, "notice": CLOSED_NOTICE if trades == 0 else "Trading has gone quiet."}
                        return
                    continue
                last_trade = now
                t0 = time.perf_counter()
                decision, risk, reasons = scorer.score(trade)
                latency_ms = round((time.perf_counter() - t0) * 1000, 3)
                trades += 1
                flagged += decision == "FLAG"
                name = trade.listing.name
                stocks.add(name)
                yield {
                    "source": SOURCE,
                    "payment": {
                        "txn_id": f"{trade.listing.symbol}:{trade.time_ms}:{trades}",
                        "from_account": name,
                        "to_account": trade.listing.exchange,
                        "amount": round(trade.value_inr, 2),
                        "timestamp": trade.timestamp,
                    },
                    "trade": {
                        "symbol": trade.listing.symbol,
                        "exchange": trade.listing.exchange,
                        "shares": trade.shares,
                        "price": trade.price,
                        "currency": trade.listing.currency,
                    },
                    "decision": decision,
                    "case_id": f"MKT-{trade.listing.symbol}" if decision == "FLAG" else None,
                    "ring_members": [name] if decision == "FLAG" else [],
                    "risk_score": risk,
                    "latency_ms": latency_ms,
                    "reasons": reasons,
                    "counters": {"payments": trades, "flagged": flagged, "accounts": len(stocks)},
                }
        except OSError as exc:
            raise RuntimeError(f"stock exchange stream unreachable: {exc}") from exc
