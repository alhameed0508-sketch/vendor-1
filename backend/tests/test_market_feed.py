"""Live stock-exchange trades: decoding the public price stream, ticks to trades, the two checks, the feed."""

import base64
import json
import struct

import pytest
from api.deps import get_market_feed
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from services.market_feed import CLOSED_NOTICE, MIN_HISTORY, SIZE_MULTIPLE, MarketFeed, MarketScorer

from data.adapters.market_adapter import BY_SYMBOL, MarketClient, TickTape, Trade, decode_pricing, parse_frame

# Two frames captured from the live streamer on 2026-11-05 (crypto with volume; Apple after hours, no volume).
BTC_FRAME = (
    "CgdCVEMtVVNEFQ99nUcYwIrikbVoIgNVU0QqA0NDQzApOAFFftmRQEiAwOeurQJV24qdR10nFp1HZQCvW0V9JxadR7ABgMDnrq0C"
    "2AEE4AGAwOeurQLoAYDA566tAvIBA0JUQ4ECAAAAQIksc0GJAgAA4/5jk3dC9QIAr1tF/QJ+2ZFA"
)
AAPL_FRAME = "CgRBQVBMFexxr0MYoOLkkbVoKgNOTVMwCDgCRXQoyj5lAKSwP9gBBPUCkOuXQf0CbBe3QA=="
FX = {"INR": 1.0, "JPY": 0.6, "USD": 90.0}


def _zigzag(n: int) -> int:
    return (n << 1) ^ (n >> 63)


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _frame(symbol: str, price: float, day_volume: int, time_ms: int) -> str:
    """A PricingData message as the streamer sends it (id, price, time, day_volume)."""
    sym = symbol.encode()
    body = (
        b"\x0a"
        + _varint(len(sym))
        + sym
        + b"\x15"
        + struct.pack("<f", price)
        + b"\x18"
        + _varint(_zigzag(time_ms))
        + b"\x48"
        + _varint(_zigzag(day_volume))
    )
    return json.dumps({"type": "pricing", "message": base64.b64encode(body).decode()})


def test_decodes_real_streamer_messages():
    btc = decode_pricing(BTC_FRAME)
    assert btc["id"] == "BTC-USD"
    assert btc["price"] == pytest.approx(80634.12, abs=0.01)
    assert btc["time_ms"] == 1793838564000  # 2026-11-05T00:29:24Z
    assert btc["day_volume"] > 0
    aapl = decode_pricing(AAPL_FRAME)
    assert aapl["id"] == "AAPL" and aapl["exchange"] == "NMS"
    assert "day_volume" not in aapl  # after-hours print: no volume, so never a trade


def test_ignores_frames_that_are_not_pricing_messages():
    assert parse_frame("not json") is None
    assert parse_frame(json.dumps({"type": "heartbeat"})) is None
    assert parse_frame(json.dumps({"type": "pricing", "message": "!!!"})) is None


def test_a_trade_is_the_volume_traded_since_the_previous_update_valued_in_rupees():
    tape = TickTape(FX)
    assert tape.observe(parse_frame(_frame("7203.T", 3000.0, 1_000, 1))) is None  # first sight: no baseline
    trade = tape.observe(parse_frame(_frame("7203.T", 3010.0, 1_400, 2)))
    assert trade.shares == 400
    assert trade.listing.name == "Toyota" and trade.listing.exchange == "Tokyo"
    assert trade.value_inr == pytest.approx(400 * 3010.0 * 0.6)
    assert tape.observe(parse_frame(_frame("7203.T", 3010.0, 1_400, 3))) is None  # quote move, nothing traded
    assert tape.observe(parse_frame(_frame("7203.T", 3010.0, 10, 4))) is None  # new session resets the count
    assert tape.observe(parse_frame(_frame("UNKNOWN", 1.0, 5, 5))) is None


def _trade(name_symbol: str, value: float, price: float = 100.0, t_ms: int = 0) -> Trade:
    return Trade(BY_SYMBOL[name_symbol], 1, price, value, "2026-11-05T00:00:00+00:00", t_ms)


def test_large_print_check_needs_history_and_compares_with_the_same_stock():
    scorer = MarketScorer()
    big = 50_00_000.0
    assert scorer.score(_trade("SBIN.NS", big * 10))[0] == "PASS"  # cold start never flags
    for i in range(MIN_HISTORY):
        scorer.score(_trade("SBIN.NS", 1_00_000.0, t_ms=(i + 1) * 1000))
    decision, risk, reasons = scorer.score(_trade("SBIN.NS", 1_00_000.0 * SIZE_MULTIPLE * 2, t_ms=30_000))
    assert decision == "FLAG" and reasons[0].startswith("MK01: Unusually large print")
    assert 0.5 < risk < 1
    assert scorer.score(_trade("TCS.NS", 2_00_000.0, t_ms=31_000))[0] == "PASS"  # other stock, own baseline


def test_sharp_price_move_within_a_minute_is_flagged_and_an_old_one_is_not():
    scorer = MarketScorer()
    scorer.score(_trade("INFY.NS", 10_000.0, price=100.0, t_ms=1_000))
    decision, _, reasons = scorer.score(_trade("INFY.NS", 10_000.0, price=100.8, t_ms=21_000))
    assert decision == "FLAG" and reasons[0].startswith("MK02: Sharp price move: +0.80%")
    calm = MarketScorer()
    calm.score(_trade("ITC.NS", 10_000.0, price=100.0, t_ms=1_000))
    assert calm.score(_trade("ITC.NS", 10_000.0, price=100.8, t_ms=121_000))[0] == "PASS"


class _Client(MarketClient):
    """The real client (no Finnhub key, so every stock goes through Yahoo's ticks) fed recorded frames."""

    def __init__(self, frames, fx=FX):
        super().__init__()
        self._frames, self._fx = frames, fx

    def inr_per_unit(self):
        if self._fx is None:
            raise OSError("down")
        return self._fx

    def ticks(self, symbols, idle_timeout):
        for frame in self._frames:
            yield None if frame is None else parse_frame(frame)


def _clock(step=1.0):
    t = [0.0]

    def now():
        t[0] += step
        return t[0]

    return now


def test_feed_emits_payment_shaped_events_with_a_trade_block():
    frames = [_frame("RELIANCE.NS", 1400.0, 100 + 10 * i, 1000 * (i + 1)) for i in range(4)]
    events = list(MarketFeed(_Client(frames), clock=_clock()).events())
    assert len(events) == 3  # the first frame only sets the baseline
    e = events[-1]
    assert e["source"] == "market"
    assert e["payment"]["from_account"] == "Reliance" and e["payment"]["to_account"] == "NSE"
    assert e["payment"]["amount"] == pytest.approx(10 * 1400.0)
    assert e["trade"]["shares"] == 10 and e["trade"]["currency"] == "INR"
    assert e["decision"] == "PASS" and e["case_id"] is None
    assert e["counters"] == {"payments": 3, "flagged": 0, "accounts": 1}


def test_feed_says_so_when_no_exchange_is_trading():
    events = list(MarketFeed(_Client([None] * 20), quiet_seconds=5, clock=_clock()).events())
    assert events == [{"source": "market", "notice": CLOSED_NOTICE}]


def test_feed_fails_clearly_without_exchange_rates():
    with pytest.raises(RuntimeError, match="exchange rates unavailable"):
        list(MarketFeed(_Client([], fx=None)).events())


@pytest.mark.asyncio
async def test_stream_route_serves_the_market_source(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    from api.app import app

    frames = [_frame("AAPL", 270.0, 1_000 + 5 * i, 1000 * (i + 1)) for i in range(3)]
    app.dependency_overrides[get_market_feed] = lambda: MarketFeed(_Client(frames), clock=_clock())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/score/stream", params={"source": "market", "limit": 5})
    finally:
        app.dependency_overrides.pop(get_market_feed, None)
        get_settings.cache_clear()
    assert resp.status_code == 200
    events = [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]
    assert [e["payment"]["from_account"] for e in events] == ["Apple", "Apple"]
    assert events[0]["payment"]["amount"] == pytest.approx(5 * 270.0 * 90.0)
