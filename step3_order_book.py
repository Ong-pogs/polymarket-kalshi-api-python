"""Step 3: an order book. The same function reads the book on either venue.

Cost: 5 credits per book, plus 1 credit to look the market up.
"""
from common import MARKETS, client, done, yes_outcome


def order_book(venue, outcome_id, depth=3):
    reply = client.exchange(venue).fetch_order_book({"outcomeId": outcome_id, "limit": depth})
    return reply["data"]


def show_book(venue, book):
    best_bid, best_ask = book["bids"][0]["price"], book["asks"][0]["price"]
    print(f'{venue}  as of {book["datetime"][11:19]} UTC')
    for level in reversed(book["asks"]):
        print(f'    ask {level["price"]:.2f}  {level["size"]:>12,.0f}')
    print(f"    ---- spread {best_ask - best_bid:.2f} ----")
    for level in book["bids"]:
        print(f'    bid {level["price"]:.2f}  {level["size"]:>12,.0f}')


if __name__ == "__main__":
    for venue, market_id in MARKETS.items():
        market = yes_outcome(venue, market_id)
        show_book(venue, order_book(venue, market["outcomeId"]))
    done()
