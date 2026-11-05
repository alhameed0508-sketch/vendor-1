"""Finnhub's US trade stream: parsing, one-second prints, the connection, and merging with Yahoo."""

import json

import pytest
from api.deps import get_market_feed
from core.config import get_settings

from data.adapters.finnhub_adapter import TradeBars, finnhub_trades, parse_message
from data.adapters.market_adapter import WATCHLIST, MarketClient, Trade, merge_sources

FX = {"INR": 1.0, "USD": 90.0}
TOKEN = "sekret-token-123"


def _msg(*trades):
    return json.dumps(
        {"type": "trade", "data": [{"s": s, "p": p, "v": v, "t": t, "c": ["1"]} for s, p, v, t in trades]}
    )


def test_parses_trades_on_the_watchlist_and_reports_errors():
    trades, error = parse_message(_msg(("AAPL", 270.5, 100, 1_000), ("BINANCE:BTCUSDT", 80_000, 0.1, 1_001)))
    assert error is None
    assert trades == [{"symbol": "AAPL", "price": 270.5, "shares": 100.0, "time_ms": 1_000}]
    assert parse_message(json.dumps({"type": "ping"})) == ([], None)
    assert parse_message(json.dumps({"type": "error", "msg": "Invalid symbol X"})) == ([], "Invalid symbol X")
    assert parse_message("not json") == ([], None)
    assert parse_message(_msg(("AAPL", 0, 100, 1), ("AAPL", 270.0, 0, 2))) == ([], None)  # no price or no shares


def test_a_stocks_trades_in_one_second_become_one_print_in_rupees():
    bars = TradeBars(FX)
    bars.add({"symbol": "AAPL", "price": 270.0, "shares": 100, "time_ms": 2_000}, now=10.0)
    bars.add({"symbol": "AAPL", "price": 271.0, "shares": 50, "time_ms": 1_500}, now=10.2)  # arrived late
    bars.add({"symbol": "NVDA", "price": 190.0, "shares": 10, "time_ms": 2_100}, now=10.5)
    assert bars.due(10.9) == []
    (apple,) = bars.due(11.0)
    assert apple.listing.name == "Apple" and apple.provider == "finnhub"
    assert apple.shares == 150 and apple.trades == 2
    assert apple.value_inr == pytest.approx((100 * 270.0 + 50 * 271.0) * 90.0)
    assert apple.price == 270.0  # the latest trade's price, not the last to arrive
    (nvidia,) = bars.due(11.6)
    assert nvidia.listing.name == "Nvidia"
    assert bars.due(20.0) == []


class _Socket:
    def __init__(self, frames):
        self.frames, self.sent = list(frames), []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send(self, text):
        self.sent.append(json.loads(text))

    def recv(self, timeout):
        if not self.frames:
            raise OSError("connection closed")
        frame = self.frames.pop(0)
        if frame is None:
            raise TimeoutError
        return frame


def test_subscribes_to_the_us_stocks_and_yields_prints():
    socket, urls = _Socket([_msg(("AAPL", 270.0, 100, 1_000)), _msg(("AAPL", 270.0, 300, 2_000)), None]), []

    def connect(url, **kwargs):
        urls.append(url)
        return socket

    clock = iter([0.0, 0.5, 1.2, 1.3]).__next__
    items = []
    with pytest.raises(OSError):
        for item in finnhub_trades(TOKEN, ["AAPL", "MSFT"], FX, idle_timeout=5, connect=connect, clock=clock):
            items.append(item)
    assert urls == [f"wss://ws.finnhub.io?token={TOKEN}"]
    assert socket.sent == [{"type": "subscribe", "symbol": "AAPL"}, {"type": "subscribe", "symbol": "MSFT"}]
    (apple,) = [i for i in items if i is not None]
    assert apple.shares == 400 and apple.trades == 2


def test_the_key_never_appears_in_an_error():
    def connect(url, **kwargs):
        raise OSError(f"could not open {url}")

    with pytest.raises(OSError) as caught:
        list(finnhub_trades(TOKEN, ["AAPL"], FX, idle_timeout=5, connect=connect))
    assert TOKEN not in str(caught.value) and "***" in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def _trade(symbol, provider="yahoo"):
    listing = next(item for item in WATCHLIST if item.symbol == symbol)
    return Trade(listing, 1, 1.0, 1.0, "2026-11-05T00:00:00+00:00", 1, provider=provider)


def _failing():
    raise OSError("refused")
    yield  # pragma: no cover


def test_merging_reads_every_stream_and_a_failed_one_falls_back():
    def take(n, gen):
        out = []
        for item in gen:
            if item is not None:
                out.append(item)
            if len(out) == n:
                gen.close()
                return out
        return out

    got = take(
        2,
        merge_sources(
            {"yahoo": lambda: iter([_trade("SBIN.NS")]), "finnhub": _failing},
            fallbacks={"finnhub": lambda: iter([_trade("AAPL")])},
            idle_timeout=1,
        ),
    )
    assert sorted(t.listing.symbol for t in got) == ["AAPL", "SBIN.NS"]


def test_merging_fails_only_when_every_stream_has_failed():
    with pytest.raises(OSError, match="refused"):
        list(merge_sources({"yahoo": _failing, "finnhub": _failing}, fallbacks={}, idle_timeout=1))


def test_with_a_key_us_stocks_go_to_finnhub_and_the_rest_to_yahoo(monkeypatch):
    calls = {}

    def fake_finnhub(token, symbols, fx, idle_timeout):
        calls["finnhub"] = (token, symbols)
        yield _trade("AAPL", provider="finnhub")
        raise OSError("closed")

    def fake_yahoo(self, symbols, fx, idle_timeout):
        calls.setdefault("yahoo", []).append(symbols)
        return iter([])

    monkeypatch.setattr("data.adapters.finnhub_adapter.finnhub_trades", fake_finnhub)
    monkeypatch.setattr(MarketClient, "yahoo_trades", fake_yahoo)
    trades = [t for t in MarketClient(finnhub_token=f"  {TOKEN} ").trades(FX, idle_timeout=1) if t is not None]
    assert [t.provider for t in trades] == ["finnhub"]
    us = [item.symbol for item in WATCHLIST if item.finnhub]
    assert us == ["AAPL", "MSFT", "NVDA", "AMZN", "JPM"]
    assert calls["finnhub"] == (TOKEN, us)
    rest = [item.symbol for item in WATCHLIST if not item.finnhub]
    assert sorted(calls["yahoo"]) == sorted([rest, us])  # Finnhub closed, so the US stocks went back to Yahoo


def test_without_a_key_every_stock_comes_from_yahoo(monkeypatch):
    seen = []
    monkeypatch.setattr(
        MarketClient, "yahoo_trades", lambda self, symbols, fx, idle_timeout: seen.append(symbols) or iter([])
    )
    assert list(MarketClient().trades(FX, idle_timeout=1)) == []
    assert seen == [[item.symbol for item in WATCHLIST]]


def test_the_key_comes_from_FINNHUB_API_KEY(monkeypatch):
    monkeypatch.setenv("LIVE_FEED_ENABLED", "true")
    monkeypatch.setenv("FINNHUB_API_KEY", TOKEN)
    get_settings.cache_clear()
    try:
        feed = get_market_feed("market")
    finally:
        get_settings.cache_clear()
    assert feed._client._finnhub_token == TOKEN
