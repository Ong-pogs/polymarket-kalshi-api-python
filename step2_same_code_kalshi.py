"""Step 2: the same code for Kalshi. The venue becomes a parameter; nothing else changes.

Cost: 1 credit per venue.
"""
from common import client, done
from step1_first_call import show

FIELDS = ("title", "status", "resolutionDate", "volume24h", "volume24hUnit", "url")


def search(venue, query, limit=3):
    return client.exchange(venue).fetch_markets(
        {"query": query, "status": "active", "sort": "volume", "limit": limit}
    )


if __name__ == "__main__":
    found = {}
    for venue in ("polymarket", "kalshi"):
        print(f'{venue}: "Dan Sullivan"')
        found[venue] = search(venue, "Dan Sullivan")
        show(found[venue])

    # Every venue answers with the same set of fields.
    polymarket, kalshi = found["polymarket"][0], found["kalshi"][0]
    shared = set(polymarket) & set(kalshi)
    print()
    print(f"fields: polymarket {len(polymarket)}, kalshi {len(kalshi)}, shared {len(shared)}")
    print("only on one venue:", sorted(set(polymarket) ^ set(kalshi)))
    for field in FIELDS:
        print(f"  {field:<14} {str(polymarket[field])[:30]:<31} {str(kalshi[field])[:30]}")
    done()
