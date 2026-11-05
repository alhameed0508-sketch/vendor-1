# Live sources on Detection modules

The Detection modules page and the module workspaces use real live data only. There is no synthetic
option there any more. The Command center, Alerts, complaints and the other pages still run on the
demonstration dataset.

## The two sources

| Option in the panel | What it is | Where it comes from | Checks |
|---|---|---|---|
| Live public payments | Real payments between public addresses, converted to rupees | mempool.space (no key), `services/live_feed.py` | The mule-network scorer (`RealtimeScorer`), as before |
| Live stock trades | Real exchange prints for 23 large stocks on NSE, Tokyo, Seoul, Hong Kong, Sydney, Frankfurt and New York | Yahoo Finance's public price streamer (no key), `data/adapters/market_adapter.py` | MK01 unusually large print, MK02 sharp price move (`services/market_feed.py`) |

Both sources are unlabelled, so the panel counts money as prevented (or, for trades, confirmed)
only when a reviewer confirms a case. Nothing is claimed as a measured catch.

**Stock trades.** A streamer message carries the session's running volume. The shares traded
since the previous message for that stock, at that message's price, count as one trade.
- **MK01** flags a print worth at least 10 times the stock's median over its last 60 prints. It
  needs 15 prints of history and a value of at least ₹5L.
- **MK02** flags a move of at least 0.5% within 60 seconds.

On 494 live prints (2026-11-05), 2.4% were flagged. Exchanges are closed at weekends and between
the US close and the Tokyo open (about 02:30 to 05:30 IST). In those hours the panel says that no
exchange is trading.

## Module findings on live payments

Every event from the live public payment feed is copied into a bounded in-memory buffer
(`services/live_buffer.py`, last 3,000 payments, one copy per payment however many people are
watching). `GET /api/v1/modules/{id}/findings?source=live` reports on that buffer:
- **mule:** the payments the live network scorer held, grouped by reason code, with the number of
  cases opened.
- **Rule modules:** their rules run on the buffered payments. Public payments carry no UPI channel,
  device or account age, so UPI shows nothing in scope and R20 reports itself as skipped.
- **loan:** no source.

Without `source`, the endpoint still reports on the loaded dataset, as before.

The buffer starts empty on each deploy and fills while someone has the Detection modules page (or
the mule workspace) open. The cards refresh every 10 seconds.

## API docs

`/docs` (Swagger UI) and `/redoc` load their bundles from cdn.jsdelivr.net. The security headers
now allow that host, plus ReDoc's fonts and web worker, on those two pages only. Every other
response keeps the strict policy.
