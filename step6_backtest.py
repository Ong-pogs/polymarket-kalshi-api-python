"""Step 6: a short backtest on candles. One rule, replayed over each venue's history.

    python step6_backtest.py            the last 7 days (what the free plan can read)
    python step6_backtest.py --days 30  needs Builder: a free key gets 403 PLAN_REQUIRED

Cost: 5 credits per venue, plus 1 credit each to look the markets up.
A first look only: it trades at candle closes with no spread and no fees.
"""
import argparse
from datetime import datetime, timezone

from predictefy import PredictefyError

from chart import write_backtest_chart
from common import MARKETS, done, explain, money, yes_outcome
from step5_price_history import candles


def backtest(rows, lookback=6, dip=0.02, shares=100):
    """Buy when a close is `dip` under the average of the `lookback` closes before it,
    sell when a close is back at that average. One position at a time.

    The rule decides on one candle and trades at the NEXT candle's close, so it never
    uses a price it could not have seen.
    """
    trades, marks, held, order = [], [], None, None
    for i in range(lookback, len(rows)):
        close = rows[i]["close"]
        if order:  # the order placed on the previous candle fills at this close
            marks.append({"side": order, "price": close, "timestamp": rows[i]["timestamp"]})
            if order == "buy":
                held = close
            else:
                trades.append({"buy": held, "sell": close, "pnl": (close - held) * shares})
                held = None
            order = None
        average = sum(row["close"] for row in rows[i - lookback:i]) / lookback
        if held is None and close <= average - dip:
            order = "buy"
        elif held is not None and close >= average:
            order = "sell"
    open_pnl = (rows[-1]["close"] - held) * shares if held is not None else 0.0
    return {"trades": trades, "marks": marks, "candles": rows, "holding": held,
            "pnl": sum(trade["pnl"] for trade in trades) + open_pnl}


def show_backtest(result):
    print(f'{result["venue"]}: {len(result["candles"])} candles over {result["days"]} days')
    for mark in result["marks"]:
        when = datetime.fromtimestamp(mark["timestamp"] / 1000, timezone.utc)
        print(f'    {mark["side"]:<4} 100 @ {mark["price"]:.3f}   {when:%b %d %H:%M} UTC')
    if result["holding"] is not None:
        print(f'    still holding 100 bought at {result["holding"]:.3f}')
    trips = len(result["trades"])
    print(f'    {trips} round trip{"" if trips == 1 else "s"},'
          f' result on paper: {money(result["pnl"])}')


def run(venue, days, resolution="4h"):
    market = yes_outcome(venue, MARKETS[venue])
    rows = candles(venue, market["outcomeId"], days=days, resolution=resolution)
    result = backtest(rows) if len(rows) > 6 else {
        "trades": [], "marks": [], "candles": rows, "holding": None, "pnl": 0.0}
    result.update(venue=venue, days=days, resolution=resolution, title=market["title"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7, help="how far back to read")
    args = parser.parse_args()
    try:
        for venue in MARKETS:
            result = run(venue, args.days)
            show_backtest(result)
            print("    chart:", write_backtest_chart(result, result["title"]))
    except PredictefyError as error:
        print(explain(error))
    done()
