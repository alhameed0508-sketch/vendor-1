"""
Live US stock trades from Finnhub's trade stream (free API key, ``FINNHUB_API_KEY``).

Finnhub sends every individual trade (``{"s": symbol, "p": price, "v": shares, "t": ms}``). The
free plan streams US stocks; Tokyo symbols sent nothing while Tokyo was trading (checked
2026-11-05). So only the US names come from here and every other exchange stays on Yahoo's keyless
streamer (``market_adapter.py``).

A busy US stock prints dozens of trades a second, more than a person can follow on screen. Each
stock's trades are summed into one print per second: shares, rupee value, last price and the number
of trades. One Yahoo update covers about the same span, so the market checks compare like with
like across both sources.

The key travels in the connection URL. It is never logged and is removed from error messages.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Callable, Dict, Iterator, List, Mapping, Optional, Tuple

from data.adapters.market_adapter import BY_SYMBOL, HTTP_TIMEOUT_S, USER_AGENT, Trade

try:
    from websockets.exceptions import WebSocketException
except ImportError:  # pragma: no cover - depends on the image
    WebSocketException = OSError  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

FINNHUB_URL = "wss://ws.finnhub.io"
PROVIDER = "finnhub"
BAR_SECONDS = 1.0


def _redact(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def parse_message(text: str) -> Tuple[List[Dict], Optional[str]]:
    """One stream message -> (trades on the watchlist, Finnhub's error message or None). Pings give ([], None)."""
    try:
        message = json.loads(text)
    except ValueError:
        return [], None
    if not isinstance(message, dict):
        return [], None
    if message.get("type") == "error":
        return [], str(message.get("msg") or "unknown error")
    if message.get("type") != "trade" or not isinstance(message.get("data"), list):
        return [], None
    trades = []
    for item in message["data"]:
        try:
            symbol, price, shares, time_ms = str(item["s"]), float(item["p"]), float(item["v"]), int(item["t"])
        except (KeyError, TypeError, ValueError):
            continue
        if symbol in BY_SYMBOL and price > 0 and shares > 0:
            trades.append({"symbol": symbol, "price": price, "shares": shares, "time_ms": time_ms})
    return trades, None


class TradeBars:
    """Sums each stock's individual trades into one print per ``seconds`` of arrival time."""

    def __init__(self, inr_per_unit: Mapping[str, float], seconds: float = BAR_SECONDS):
        self._fx = dict(inr_per_unit)
        self._seconds = seconds
        self._open: Dict[str, Dict] = {}

    def add(self, trade: Mapping, now: float) -> None:
        listing = BY_SYMBOL.get(trade["symbol"])
        rate = self._fx.get(listing.currency) if listing else None
        if rate is None:
            return
        bar = self._open.setdefault(
            listing.symbol, {"opened": now, "shares": 0.0, "value": 0.0, "trades": 0, "price": 0.0, "time_ms": 0}
        )
        bar["shares"] += trade["shares"]
        bar["value"] += trade["shares"] * trade["price"] * rate
        bar["trades"] += 1
        if trade["time_ms"] >= bar["time_ms"]:  # trades can arrive out of order within a message
            bar["price"], bar["time_ms"] = trade["price"], trade["time_ms"]

    def due(self, now: float) -> List[Trade]:
        """Prints whose second has passed, oldest first."""
        ready = sorted((b["opened"], s) for s, b in self._open.items() if now - b["opened"] >= self._seconds)
        out = []
        for _, symbol in ready:
            bar = self._open.pop(symbol)
            when = (
                datetime.fromtimestamp(bar["time_ms"] / 1000, tz=timezone.utc)
                if bar["time_ms"]
                else datetime.now(timezone.utc)
            )
            out.append(
                Trade(
                    BY_SYMBOL[symbol],
                    int(round(bar["shares"])),
                    bar["price"],
                    bar["value"],
                    when.isoformat(),
                    bar["time_ms"],
                    trades=bar["trades"],
                    provider=PROVIDER,
                )
            )
        return out


def finnhub_trades(
    token: str,
    symbols: List[str],
    inr_per_unit: Mapping[str, float],
    idle_timeout: float,
    connect: Optional[Callable] = None,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[Optional[Trade]]:
    """One-second prints for ``symbols``; yields None when a poll passes with nothing ready, so callers can stop."""
    if connect is None:
        try:
            from websockets.sync.client import connect  # ships with uvicorn[standard]
        except ImportError as exc:  # pragma: no cover - depends on the image
            raise OSError("the websockets package is not installed") from exc
    bars = TradeBars(inr_per_unit)
    poll = min(idle_timeout, BAR_SECONDS)
    try:
        with connect(
            f"{FINNHUB_URL}?token={token}", additional_headers={"User-Agent": USER_AGENT}, open_timeout=HTTP_TIMEOUT_S
        ) as ws:
            for symbol in symbols:
                ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))
            while True:
                try:
                    frame = ws.recv(timeout=poll)
                except TimeoutError:
                    frame = None
                now = clock()
                if frame is not None:
                    if isinstance(frame, bytes):
                        frame = frame.decode("utf-8", "replace")
                    trades, error = parse_message(frame)
                    if error:
                        logger.warning("Finnhub stream: %s", _redact(error, token))
                    for trade in trades:
                        bars.add(trade, now)
                ready = bars.due(now)
                if ready:
                    yield from ready
                elif frame is None:
                    yield None
    except (WebSocketException, OSError) as exc:  # refused key, dropped connection, DNS
        raise OSError(f"Finnhub stream: {_redact(str(exc), token)}") from None
