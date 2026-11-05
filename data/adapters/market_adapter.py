"""
Live stock-exchange trades from Yahoo Finance's public price streamer (no key) as MuleCatch events.

The streamer pushes one protobuf ``PricingData`` message (base64 in a JSON envelope) per price
update for each subscribed symbol. A message carries the session's cumulative ``day_volume``, so
the shares traded since the previous message for that symbol are the difference between the two:
that difference, at the message's price, is one "trade" here. Updates without a volume change
(quote moves, pre/post-market prints without volume) are not trades.

Values are converted to rupees at the day's ECB reference rates (frankfurter.dev) so the rupee
thresholds used elsewhere keep their meaning. The data is real and unlabelled: nothing here says a
trade was abusive, so a flag is a lead for a person and no accuracy can be claimed from it.

The watchlist follows the sun (Tokyo, Seoul, Hong Kong, Sydney, NSE, Frankfurt, New York), so on a
weekday at least one exchange is usually open. Weekends and the gap after the US close are quiet.

With ``FINNHUB_API_KEY`` set, the US stocks come from Finnhub's trade stream instead
(``finnhub_adapter.py``), read on a second thread and merged with Yahoo's stream.
"""

from __future__ import annotations

import base64
import json
import logging
import queue
import struct
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Iterator, List, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

STREAMER_URL = "wss://streamer.finance.yahoo.com/?version=2"
FX_URL = "https://api.frankfurter.dev/v1/latest?base=INR&symbols=USD,EUR,JPY,KRW,HKD,AUD"
HTTP_TIMEOUT_S = 8.0
USER_AGENT = "mulecatch-market-feed/1.0"


@dataclass(frozen=True)
class Listing:
    symbol: str  # Yahoo symbol
    name: str  # short display name
    exchange: str  # display name of the exchange
    currency: str
    finnhub: bool = False  # on Finnhub's free trade stream (US stocks), used when FINNHUB_API_KEY is set


WATCHLIST: Tuple[Listing, ...] = (
    Listing("RELIANCE.NS", "Reliance", "NSE", "INR"),
    Listing("HDFCBANK.NS", "HDFC Bank", "NSE", "INR"),
    Listing("ICICIBANK.NS", "ICICI Bank", "NSE", "INR"),
    Listing("SBIN.NS", "SBI", "NSE", "INR"),
    Listing("TCS.NS", "TCS", "NSE", "INR"),
    Listing("INFY.NS", "Infosys", "NSE", "INR"),
    Listing("BHARTIARTL.NS", "Bharti Airtel", "NSE", "INR"),
    Listing("ITC.NS", "ITC", "NSE", "INR"),
    Listing("7203.T", "Toyota", "Tokyo", "JPY"),
    Listing("6758.T", "Sony", "Tokyo", "JPY"),
    Listing("8306.T", "MUFG", "Tokyo", "JPY"),
    Listing("005930.KS", "Samsung", "Seoul", "KRW"),
    Listing("0700.HK", "Tencent", "Hong Kong", "HKD"),
    Listing("0005.HK", "HSBC", "Hong Kong", "HKD"),
    Listing("BHP.AX", "BHP", "Sydney", "AUD"),
    Listing("CBA.AX", "CommBank", "Sydney", "AUD"),
    Listing("SAP.DE", "SAP", "Frankfurt", "EUR"),
    Listing("SIE.DE", "Siemens", "Frankfurt", "EUR"),
    Listing("AAPL", "Apple", "Nasdaq", "USD", finnhub=True),
    Listing("MSFT", "Microsoft", "Nasdaq", "USD", finnhub=True),
    Listing("NVDA", "Nvidia", "Nasdaq", "USD", finnhub=True),
    Listing("AMZN", "Amazon", "Nasdaq", "USD", finnhub=True),
    Listing("JPM", "JPMorgan", "NYSE", "USD", finnhub=True),
)
BY_SYMBOL: Dict[str, Listing] = {item.symbol: item for item in WATCHLIST}


# ── PricingData decoding (only the fields used here) ─────────────────────────
# id=1 string, price=2 float, time=3 sint64 (ms), currency=4, exchange=5, market_hours=7 enum,
# day_volume=9 sint64, last_size=22 sint64. Unknown fields are skipped.
_SINT64 = {3: "time_ms", 9: "day_volume", 22: "last_size"}
_STRINGS = {1: "id", 4: "currency", 5: "exchange"}


def _varint(buf: bytes, i: int) -> Tuple[int, int]:
    result = shift = 0
    while True:
        if i >= len(buf):
            raise ValueError("truncated varint")
        byte = buf[i]
        i += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return result, i


def decode_pricing(message: str) -> Dict:
    """Decode one base64 ``PricingData`` message into the fields this feed uses."""
    buf = base64.b64decode(message, validate=True)
    out: Dict = {}
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _varint(buf, i)
            if field in _SINT64:
                out[_SINT64[field]] = (value >> 1) ^ -(value & 1)
            elif field == 7:
                out["market_hours"] = value
        elif wire == 1:
            i += 8
        elif wire == 5:
            if field == 2:
                out["price"] = struct.unpack("<f", buf[i : i + 4])[0]
            i += 4
        elif wire == 2:
            length, i = _varint(buf, i)
            if field in _STRINGS:
                out[_STRINGS[field]] = buf[i : i + length].decode("utf-8", "replace")
            i += length
        else:
            raise ValueError(f"unsupported wire type {wire}")
    return out


def parse_frame(frame: str) -> Optional[Dict]:
    """One streamer frame (JSON envelope around a base64 message) -> decoded tick, or None."""
    try:
        envelope = json.loads(frame)
    except ValueError:
        return None
    if not isinstance(envelope, dict) or envelope.get("type") != "pricing" or not envelope.get("message"):
        return None
    try:
        tick = decode_pricing(envelope["message"])
    except (ValueError, struct.error):
        return None
    return tick if tick.get("id") else None


# ── Ticks to trades ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Trade:
    listing: Listing
    shares: int
    price: float
    value_inr: float
    timestamp: str
    time_ms: int
    trades: Optional[int] = None  # individual trades summed into this print, when the source says
    provider: str = "yahoo"


class TickTape:
    """Turns cumulative day volumes into trades: shares since the previous update for that symbol."""

    def __init__(self, inr_per_unit: Mapping[str, float]):
        self._fx = dict(inr_per_unit)
        self._last_volume: Dict[str, int] = {}

    def observe(self, tick: Mapping) -> Optional[Trade]:
        listing = BY_SYMBOL.get(tick.get("id", ""))
        volume, price = tick.get("day_volume"), tick.get("price")
        if listing is None or not volume or not price or price <= 0:
            return None
        previous = self._last_volume.get(listing.symbol)
        self._last_volume[listing.symbol] = volume
        if previous is None or volume <= previous:  # first sight, or a new session restarting the count
            return None
        rate = self._fx.get(listing.currency)
        if rate is None:
            return None
        shares = volume - previous
        time_ms = int(tick.get("time_ms") or 0)
        when = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc) if time_ms else datetime.now(timezone.utc)
        return Trade(listing, shares, float(price), shares * float(price) * rate, when.isoformat(), time_ms)


# ── Network ──────────────────────────────────────────────────────────────────
def inr_per_unit() -> Dict[str, float]:
    """Rupees per unit of each watchlist currency, from the ECB reference rates."""
    request = urllib.request.Request(FX_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:  # noqa: S310 - fixed https host
        try:
            rates = json.load(response)["rates"]
        except (ValueError, KeyError) as exc:
            raise OSError("invalid FX response") from exc
    out = {"INR": 1.0}
    out.update({code: 1.0 / float(units) for code, units in rates.items() if float(units) > 0})
    return out


_END = object()


def _pump(name: str, factory: Callable[[], Iterator], out: "queue.Queue", stop: threading.Event) -> None:
    source = None
    try:
        source = factory()
        for item in source:
            if stop.is_set():
                return
            if item is not None:
                out.put((name, item))
    except OSError as exc:
        out.put((name, exc))
    finally:
        if source is not None and hasattr(source, "close"):
            source.close()
        out.put((name, _END))


def merge_sources(
    sources: Mapping[str, Callable[[], Iterator]],
    fallbacks: Mapping[str, Callable[[], Iterator]],
    idle_timeout: float,
) -> Iterator[Optional["Trade"]]:
    """Trades from several streams at once, each read on its own thread; None after ``idle_timeout`` quiet.

    A stream that fails is replaced by its fallback, if it has one, and the others carry on. Fails
    only when every stream has failed. Closing the generator stops the threads within one poll.
    """
    out: "queue.Queue" = queue.Queue()
    stop = threading.Event()
    pending = dict(fallbacks)
    running = launched = 0
    errors: List[OSError] = []

    def launch(name: str, factory: Callable[[], Iterator]) -> None:
        nonlocal running, launched
        running += 1
        launched += 1
        threading.Thread(target=_pump, args=(name, factory, out, stop), name=f"market-{name}", daemon=True).start()

    for name, factory in sources.items():
        launch(name, factory)
    try:
        while running:
            try:
                name, item = out.get(timeout=idle_timeout)
            except queue.Empty:
                yield None
                continue
            if item is _END:
                running -= 1
            elif isinstance(item, OSError):
                errors.append(item)
                fallback = pending.pop(name, None)
                logger.warning("market stream %s failed (%s)%s", name, item, "; falling back" if fallback else "")
                if fallback:
                    launch(name, fallback)
            else:
                yield item
        if errors and len(errors) == launched:
            raise errors[0]
    finally:
        stop.set()


class MarketClient:
    """Read-only client: FX rates, and the trades for the watchlist.

    Without a Finnhub key every stock comes from Yahoo. With one, the US stocks come from Finnhub's
    trade stream (``finnhub_adapter.py``) and the rest from Yahoo; if Finnhub fails, the US stocks
    go back to Yahoo for the rest of that stream.
    """

    def __init__(self, finnhub_token: str = ""):
        self._finnhub_token = (finnhub_token or "").strip()

    def inr_per_unit(self) -> Dict[str, float]:
        return inr_per_unit()

    def trades(self, inr_per_unit: Mapping[str, float], idle_timeout: float) -> Iterator[Optional[Trade]]:
        """Trades for the whole watchlist, with None after ``idle_timeout`` seconds without one."""
        symbols = [item.symbol for item in WATCHLIST]
        if not self._finnhub_token:
            yield from self.yahoo_trades(symbols, inr_per_unit, idle_timeout)
            return
        from data.adapters.finnhub_adapter import finnhub_trades

        us = [item.symbol for item in WATCHLIST if item.finnhub]
        rest = [symbol for symbol in symbols if symbol not in us]
        yield from merge_sources(
            {
                "yahoo": lambda: self.yahoo_trades(rest, inr_per_unit, idle_timeout),
                "finnhub": lambda: finnhub_trades(self._finnhub_token, us, inr_per_unit, idle_timeout),
            },
            fallbacks={"finnhub": lambda: self.yahoo_trades(us, inr_per_unit, idle_timeout)},
            idle_timeout=idle_timeout,
        )

    def yahoo_trades(
        self, symbols: List[str], inr_per_unit: Mapping[str, float], idle_timeout: float
    ) -> Iterator[Optional[Trade]]:
        tape = TickTape(inr_per_unit)
        for tick in self.ticks(symbols, idle_timeout):
            yield None if tick is None else tape.observe(tick)

    def ticks(self, symbols: List[str], idle_timeout: float) -> Iterator[Optional[Dict]]:
        """Decoded ticks; yields None after ``idle_timeout`` seconds without a frame so the caller can stop."""
        try:
            from websockets.exceptions import WebSocketException
            from websockets.sync.client import connect  # ships with uvicorn[standard]
        except ImportError as exc:  # pragma: no cover - depends on the image
            raise OSError("the websockets package is not installed") from exc
        try:
            with connect(
                STREAMER_URL,
                additional_headers={"Origin": "https://finance.yahoo.com", "User-Agent": USER_AGENT},
                open_timeout=HTTP_TIMEOUT_S,
            ) as ws:
                ws.send(json.dumps({"subscribe": symbols}))
                while True:
                    try:
                        frame = ws.recv(timeout=idle_timeout)
                    except TimeoutError:
                        yield None
                        continue
                    if isinstance(frame, bytes):
                        frame = frame.decode("utf-8", "replace")
                    tick = parse_frame(frame)
                    if tick is not None:
                        yield tick
        except WebSocketException as exc:  # handshake refused, connection dropped
            raise OSError(f"price streamer: {exc}") from exc
