"""The steps, against a fake API. Run with: python -m pytest"""
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from predictefy import Predictefy, PredictefyError
from predictefy.backtest import Backtest, NdjsonFileFeed

import chart
import common
from conftest import candle, envelope, error, market
from step1_first_call import search_polymarket, show
from step2_same_code_kalshi import search
from step3_order_book import order_book, show_book
from step4_compare_venues import compare, show_comparison
from step5_price_history import candles
from step6_backtest import backtest
from step7_replay_backtest import BuyTheDip, orders_filled

BOOK = {"bids": [{"price": 0.26, "size": 500.0}, {"price": 0.25, "size": 900.0}],
        "asks": [{"price": 0.27, "size": 80.0}, {"price": 0.28, "size": 400.0}],
        "datetime": "2030-01-01T12:00:00.000Z"}


def closes(*values):
    return [candle(hour * 4, value) for hour, value in enumerate(values)]


def test_first_call_searches_polymarket(api, capsys):
    api.on("/api/polymarket/fetchMarkets", envelope([market("polymarket", "111", "Will it rain?", 0.4)]))
    markets = search_polymarket("rain")
    assert api.query() == {"query": "rain", "status": "active", "sort": "volume", "limit": "3"}
    show(markets)
    assert "yes 0.400" in capsys.readouterr().out


def test_same_code_reaches_either_venue(api):
    api.on("/api/polymarket/fetchMarkets", envelope([market("polymarket", "111", "A", 0.4)]))
    api.on("/api/kalshi/fetchMarkets", envelope([market("kalshi", "KX-A", "A", 0.38)]))
    polymarket, kalshi = search("polymarket", "rain")[0], search("kalshi", "rain")[0]
    # Only the venue in the path differs; the query and the field names do not.
    assert api.query(0) == api.query(1)
    assert sorted(polymarket) == sorted(kalshi)


def test_order_book_keys_on_the_outcome(api, capsys):
    api.on("/api/kalshi/fetchOrderBook", envelope(BOOK), credits=5)
    book = order_book("kalshi", "KX-A-YES")
    assert api.query() == {"outcomeId": "KX-A-YES", "limit": "3"}
    show_book("kalshi", book)
    out = capsys.readouterr().out
    assert "spread 0.01" in out and out.index("ask 0.28") < out.index("ask 0.27") < out.index("bid 0.26")
    assert common.credits()[0] == 5


def test_compare_uses_the_canonical_id_and_keeps_the_indicative_label(api, capsys):
    row = {"venue": "kalshi", "market": market("kalshi", "KX-A", "A", 0.24), "similarity": 0.99,
           "bestBid": 0.23, "bestAsk": 0.24, "label": "indicative price comparison",
           "matchQuality": {"verdict": "judged_not_equivalent", "differenceKinds": ["deadline_handling"]}}
    dark = {**row, "venue": "limitless", "bestBid": None, "bestAsk": None}
    api.on("/api/router/compareMarketPrices", envelope([row, dark]), credits=10)
    rows = compare("polymarket", "111")
    assert api.query() == {"marketId": "polymarket:111", "live": "true"}
    show_comparison({"venue": "polymarket", "title": "A"}, BOOK, rows)
    out = capsys.readouterr().out
    assert "kalshi is 3.0 cents below polymarket" in out
    assert "indicative price comparison" in out and "judged_not_equivalent" in out
    assert "limitless    no live book right now" in out
    assert "arbitrage" not in out.lower()


def test_candles_drop_empty_buckets_and_ask_for_the_window(api):
    rows = [candle(0, 0.0, 0, "official", "true-candle"), candle(4, 0.31), candle(8, 0.0, 0), candle(12, 0.30)]
    api.on("/api/kalshi/fetchOHLCV", envelope(rows, meta={"provenance": "merged"}), credits=5)
    kept = candles("kalshi", "KX-A-YES", days=7)
    assert [row["close"] for row in kept] == [0.31, 0.30]
    query = api.query()
    assert query["resolution"] == "4h" and query["outcomeId"] == "KX-A-YES"
    start = datetime.fromisoformat(query["start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(query["end"].replace("Z", "+00:00"))
    assert end - start == timedelta(days=7) - timedelta(hours=1)


def test_a_seven_day_window_starts_inside_the_free_plan(api):
    start, _ = common.window(7)
    asked = datetime.fromisoformat(start.replace("Z", "+00:00"))
    assert asked > datetime.now(timezone.utc) - timedelta(days=7)


def test_a_longer_window_on_a_free_key_explains_the_plan(api):
    api.on("/api/polymarket/fetchOHLCV", error("PLAN_REQUIRED", "History beyond 7 days requires Builder"), status=403)
    with pytest.raises(PredictefyError) as caught:
        candles("polymarket", "111-YES", days=30)
    assert caught.value.code == "PLAN_REQUIRED" and caught.value.status == 403
    message = common.explain(caught.value)
    assert "7 days" in message and "Builder" in message and common.UPGRADE_URL in message
    assert "utm_campaign=polymarket-kalshi-api-python" in common.UPGRADE_URL


def test_backtest_trades_at_the_next_close_never_the_one_it_saw():
    rows = closes(0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.27, 0.26, 0.31, 0.32)
    result = backtest(rows, lookback=6, dip=0.02, shares=100)
    # The dip shows at 0.27; the buy fills one candle later, at 0.26.
    assert [(mark["side"], mark["price"]) for mark in result["marks"]] == [("buy", 0.26), ("sell", 0.32)]
    assert result["marks"][0]["timestamp"] == rows[7]["timestamp"]
    assert result["trades"][0]["pnl"] == pytest.approx(6.0)
    assert result["pnl"] == pytest.approx(6.0) and result["holding"] is None


def test_backtest_does_nothing_on_a_flat_price_and_marks_an_open_position():
    assert backtest(closes(*[0.30] * 12))["marks"] == []
    falling = backtest(closes(0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.27, 0.26, 0.25, 0.24))
    assert falling["trades"] == [] and falling["holding"] == 0.26
    assert falling["pnl"] == pytest.approx((0.24 - 0.26) * 100)


def test_credits_come_from_the_response_header(api):
    api.on("/api/polymarket/fetchMarkets", envelope([]), credits=1)
    api.on("/api/polymarket/fetchOrderBook", envelope(BOOK), credits=5)
    search_polymarket("x"), order_book("polymarket", "a"), order_book("polymarket", "b")
    assert common.credits() == (11, "fetchMarkets 1, fetchOrderBook 5 x2")


def test_a_recording_replays_without_the_network(tmp_path):
    def served(request):
        return httpx.Response(200, json=envelope([market("kalshi", "KX-A", "A", 0.2)]),
                              headers={"x-credits-charged": "1"})

    recorder = common.Tape(httpx.MockTransport(served), record=tmp_path)
    first = Predictefy(api_key="pk_test_not_a_real_key", transport=recorder).kalshi.fetch_markets({"limit": 1})
    saved = list(tmp_path.glob("0*.json"))
    assert len(saved) == 1 and "pk_test" not in saved[0].read_text()

    player = common.Tape(None, replay=tmp_path)
    again = Predictefy(api_key="unused", transport=player).kalshi.fetch_markets({"limit": 1})
    assert list(again) == list(first) and player.calls[0]["credits"] == 1
    with pytest.raises(SystemExit):
        Predictefy(api_key="unused", transport=player).kalshi.fetch_markets({"limit": 2})


def test_a_missing_key_stops_with_instructions(monkeypatch, tmp_path, capsys):
    common._state.clear()
    monkeypatch.setattr(common, "load_env", lambda path=None: None)
    for name in ("PREDICTEFY_REPLAY", "PREDICTEFY_RECORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PREDICTEFY_API_KEY", common.PLACEHOLDER)
    with pytest.raises(SystemExit) as stopped:
        common.connect()
    assert common.KEYS_URL in str(stopped.value)
    common._state.clear()


def test_replay_strategy_fills_on_a_later_quote_and_pays_fees(tmp_path):
    hour = 3_600_000
    ticks = [{"k": "tob", "ts": 1_800_000_000_000 + i * 4 * hour, "bid": 0.30, "ask": 0.31,
              "bidSize": 400, "askSize": 400, "mid": 0.305, "last": None, "mechanism": "ws-lossless"}
             for i in range(8)]
    base = ticks[-1]["ts"]
    for i, (bid, ask) in enumerate([(0.26, 0.27), (0.26, 0.27), (0.26, 0.27), (0.33, 0.34), (0.33, 0.34)]):
        ticks.append({**ticks[0], "ts": base + (i + 1) * 60_000, "bid": bid, "ask": ask,
                      "mid": (bid + ask) / 2, "bidSize": 400 + i, "askSize": 400 + i})
    file = tmp_path / "tob.ndjson"
    file.write_text("\n".join(json.dumps(tick) for tick in ticks))
    result = Backtest(NdjsonFileFeed(file), BuyTheDip(), venue="kalshi", initial_cash=1000).run()
    filled = orders_filled(result)
    assert filled[0]["side"] == "buy" and filled[0]["size"] == pytest.approx(100)
    # The dip appears on the first 0.27 quote; nothing can fill until the quote after it.
    assert result.fills[0].ts > base + 60_000
    assert result.report()["fees_paid"] > 0


def test_charts_are_self_contained_and_escape_their_data(tmp_path, monkeypatch):
    monkeypatch.setattr(chart, "OUT", tmp_path)
    rows = closes(0.30, 0.29, 0.28)
    path = chart.write_history_chart({"polymarket": rows, "kalshi": rows}, "Will </script> break it?")
    page = path.read_text(encoding="utf8")
    assert "fetchOHLCV" in page and "indicative" in page and "http" not in page.replace("http://www.w3.org", "")
    assert "</script> break" not in page
    result = {**backtest(closes(*[0.30] * 8)), "venue": "kalshi", "days": 7, "resolution": "4h"}
    assert chart.write_backtest_chart(result, "A").name == "backtest-kalshi-7d.html"
