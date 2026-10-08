"""Step 4: one market on both venues. Give Predictefy a market and it finds the
same question on the other venues and lines the prices up.

Cost: 10 credits for the comparison, 5 for the anchor's own book, 1 for the lookup.
The gap it prints is indicative: a price difference, not a trade.
"""
from common import MARKETS, client, done, yes_outcome
from step3_order_book import order_book


def compare(venue, market_id):
    """Every other venue's price for the market `venue:market_id`, from live books."""
    return client.router.compare_market_prices(
        {"marketId": f"{venue}:{market_id}", "live": True}
    )


def show_comparison(anchor, book, rows):
    bid, ask = book["bids"][0]["price"], book["asks"][0]["price"]
    print(anchor["title"])
    print(f"  {'venue':<12} {'bid':>5} {'ask':>5} {'mid':>6}")
    print(f"  {anchor['venue']:<12} {bid:>5.2f} {ask:>5.2f} {(bid + ask) / 2:>6.3f}  (the anchor)")
    for row in rows:
        if row["bestBid"] is None or row["bestAsk"] is None:
            print(f"  {row['venue']:<12} no live book right now")
            continue
        mid = (row["bestBid"] + row["bestAsk"]) / 2
        cents = (mid - (bid + ask) / 2) * 100
        quality = row.get("matchQuality") or {}
        print(f"  {row['venue']:<12} {row['bestBid']:>5.2f} {row['bestAsk']:>5.2f} {mid:>6.3f}"
              f"  similarity {row['similarity']:.2f}")
        print()
        print(f"  {row['venue']} is {abs(cents):.1f} cents {'below' if cents < 0 else 'above'}"
              f" {anchor['venue']}")
        print(f"  label:   {row['label']}")
        print(f"  verdict: {quality.get('verdict')}"
              f" ({', '.join(quality.get('differenceKinds') or [])})")


if __name__ == "__main__":
    anchor = yes_outcome("polymarket", MARKETS["polymarket"])
    book = order_book("polymarket", anchor["outcomeId"])
    show_comparison(anchor, book, compare("polymarket", anchor["marketId"]))
    done()
