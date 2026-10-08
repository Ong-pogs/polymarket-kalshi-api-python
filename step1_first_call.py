"""Step 1: the first call. Search Polymarket and print what comes back.

Cost: 1 credit (a catalog search).
"""
from common import client, done


def search_polymarket(query, limit=3):
    return client.polymarket.fetch_markets(
        {"query": query, "status": "active", "sort": "volume", "limit": limit}
    )


def show(markets):
    for market in markets:
        yes = market.get("yes") or market["outcomes"][0]
        print(f'  yes {yes["price"]:.3f}  {market["marketId"]:<32}  {market["title"][:36]}')


if __name__ == "__main__":
    print('polymarket: "Dan Sullivan"')
    show(search_polymarket("Dan Sullivan"))
    done()
