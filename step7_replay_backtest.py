"""Step 7 (Builder plan and above): the same rule on real quotes.

The replay route returns every top-of-book update for one outcome. Predictefy's Python
package ships a backtest engine that runs on it with the same fill rules as paper
trading: orders fill on the next quote, at the quoted size, and pay the venue's fees.

    python step7_replay_backtest.py --download   pull the quotes once (5 credits a page)
    python step7_replay_backtest.py              replay them from disk (0 credits)

A free key gets 403 PLAN_REQUIRED from the replay route.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone

from predictefy import PredictefyError
from predictefy.backtest import Backtest, NdjsonFileFeed, Strategy

from common import MARKETS, ROOT, client, done, explain, money, now, yes_outcome

DATA = ROOT / "data"
FOUR_HOURS = 4 * 60 * 60 * 1000


class BuyTheDip(Strategy):
    """Step 6's rule on live quotes: buy at the ask when it is `dip` under the average
    of the last `lookback` four-hour closes, sell at the bid when it is back there."""

    def __init__(self, lookback=6, dip=0.02, shares=100):
        self.lookback, self.dip, self.shares = lookback, dip, shares
        self.closes, self.bar, self.mid = [], None, None

    def on_event(self, ev, ctx):
        if ev.k != "tob" or ev.bid is None or ev.ask is None:
            return
        if ev.ts // FOUR_HOURS != self.bar:  # a new four-hour bar starts
            if self.mid is not None:
                self.closes.append(self.mid)
            self.bar = ev.ts // FOUR_HOURS
        self.mid = (ev.bid + ev.ask) / 2
        if len(self.closes) < self.lookback or ctx.open_orders:
            return
        average = sum(self.closes[-self.lookback:]) / self.lookback
        if ctx.position == 0 and ev.ask <= average - self.dip:
            ctx.buy(size=self.shares, price=ev.ask)    # fills no earlier than the next quote
        elif ctx.position > 0 and ev.bid >= average:
            ctx.sell(size=ctx.position, price=ev.bid)


def quotes_file(venue):
    return DATA / f"{venue}-{MARKETS[venue]}-tob.ndjson"


def download(venue, days):
    """Save every top-of-book row in the window. One page is up to 20,000 rows."""
    market = yes_outcome(venue, MARKETS[venue])
    until = now().replace(minute=0, second=0, microsecond=0)
    DATA.mkdir(exist_ok=True)
    rows = 0
    with quotes_file(venue).open("w", encoding="utf8") as out:
        for row in client.replay_history(venue, market["outcomeId"], kind="tob", limit=20000,
                                         since=until - timedelta(days=days), until=until):
            out.write(json.dumps(row) + "\n")
            rows += 1
    print(f"saved {rows:,} quotes to {quotes_file(venue).relative_to(ROOT)}")


def replay(venue, cash=1000.0):
    feed = NdjsonFileFeed(quotes_file(venue))
    return Backtest(feed, BuyTheDip(), venue=venue, initial_cash=cash).run()


def orders_filled(result):
    """One line per order: how much filled, at what average price, in how many pieces."""
    orders = {}
    for fill in result.fills:
        order = orders.setdefault(fill.order_id, {"side": fill.side, "ts": fill.ts, "size": 0.0,
                                                  "cost": 0.0, "fees": 0.0, "fills": 0})
        order["size"] += fill.size
        order["cost"] += fill.size * fill.price
        order["fees"] += fill.fee
        order["fills"] += 1
    return list(orders.values())


def show_report(venue, result):
    report = result.report()
    print(f'{venue}: replayed {report["counts_by_kind"].get("tob", 0):,} quotes'
          f' over {report["duration_days"]:.0f} days')
    for order in orders_filled(result):
        when = datetime.fromtimestamp(order["ts"] / 1000, timezone.utc)
        print(f'    {order["side"]:<4} {order["size"]:>6.0f} @ {order["cost"] / order["size"]:.3f}'
              f'  in {order["fills"]:>2} fills  fees ${order["fees"]:.2f}   {when:%b %d %H:%M} UTC')
    if report["position"]:
        print(f'    still holding {report["position"]:.0f}')
    print(f'    result: {money(report["final_equity"] - report["initial_cash"])}'
          f' after ${report["fees_paid"]:.2f} in fees')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--venue", default="kalshi", choices=sorted(MARKETS))
    parser.add_argument("--days", type=int, default=28, help="window to download (31 at most)")
    parser.add_argument("--download", action="store_true", help="pull the quotes first")
    args = parser.parse_args()
    try:
        if args.download:
            download(args.venue, args.days)
        saved = quotes_file(args.venue)
        if not saved.exists():
            raise SystemExit("No saved quotes yet. Run this once with --download.")
        if saved.stat().st_size == 0:
            raise SystemExit(f"Predictefy has no top-of-book rows for this {args.venue} outcome"
                             " in that window. Try the other venue.")
        show_report(args.venue, replay(args.venue))
    except PredictefyError as error:
        print(explain(error))
    done()
