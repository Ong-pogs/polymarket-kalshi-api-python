"""Step 5: price history. One function returns candles for either venue.

Cost: 5 credits per venue, plus 1 credit each to look the markets up.
The free plan reads the last 7 days. A longer window answers 403 PLAN_REQUIRED.
"""
from collections import Counter

from chart import write_history_chart
from common import MARKETS, client, done, window, yes_outcome


def candles(venue, outcome_id, days=7, resolution="4h"):
    start, end = window(days)
    reply = client.exchange(venue).fetch_ohlcv({
        "outcomeId": outcome_id, "resolution": resolution,
        "start": start, "end": end, "limit": 5000,
    })
    # A bucket with no price in it comes back as zeros: keep only the priced ones.
    return [candle for candle in reply["data"] if candle["close"] > 0]


def show_history(venue, rows):
    closes = [candle["close"] for candle in rows]
    kinds = Counter(f'{candle["source"]}/{candle["sourceType"]}' for candle in rows)
    print(f"{venue}: {len(rows)} candles, close {closes[0]:.3f} -> {closes[-1]:.3f},"
          f" low {min(closes):.3f}, high {max(closes):.3f}")
    print("    built from:", ", ".join(f"{count} {kind}" for kind, count in kinds.items()))


if __name__ == "__main__":
    series = {}
    for venue, market_id in MARKETS.items():
        market = yes_outcome(venue, market_id)
        series[venue] = candles(venue, market["outcomeId"])
        show_history(venue, series[venue])
    print("chart:", write_history_chart(series, market["title"]))
    done()
