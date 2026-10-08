"""Test setup. Every test talks to a fake transport: no network, no key, no credits.

The response bodies below are synthetic. They follow the documented envelope
({"success": true, "data": ...}) but none of the numbers are real market data.
"""
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common  # noqa: E402


def market(venue, market_id, title, price):
    side = {"outcomeId": f"{market_id}-YES", "label": "Yes", "price": price, "side": "yes"}
    other = {"outcomeId": f"{market_id}-NO", "label": "No", "price": round(1 - price, 3), "side": "no"}
    return {"marketId": market_id, "title": title, "outcomes": [side, other], "yes": side,
            "no": other, "sourceExchange": venue, "status": "open", "volume24h": 1000.0,
            "volume24hUnit": "usd" if venue == "polymarket" else "contracts",
            "resolutionDate": "2030-01-01T00:00:00.000Z", "url": f"https://example.test/{venue}"}


class FakeApi:
    """Routes requests by path and remembers what was asked."""

    def __init__(self):
        self.requests = []
        self.routes = {}

    def on(self, path, body, status=200, credits=1):
        self.routes[path] = (body, status, credits)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body, status, credits = self.routes[request.url.path]
        if callable(body):
            body = body(request)
        return httpx.Response(status, json=body, headers={"x-credits-charged": str(credits)})

    def query(self, index=-1):
        return dict(self.requests[index].url.params)


@pytest.fixture
def api(monkeypatch):
    for name in ("PREDICTEFY_REPLAY", "PREDICTEFY_RECORD"):
        monkeypatch.delenv(name, raising=False)
    fake = FakeApi()
    common._state.clear()
    common.connect(transport=httpx.MockTransport(fake), api_key="pk_test_not_a_real_key")
    yield fake
    common._state.clear()


def envelope(data, **extra):
    return {"success": True, "data": data, **extra}


def error(code, message):
    return {"success": False, "error": {"code": code, "message": message, "retryable": False,
                                        "requestId": "req_test"}}


def candle(hour, close, volume=None, source="derived", kind="rollup"):
    return {"timestamp": 1_800_000_000_000 + hour * 3_600_000, "open": close, "high": close,
            "low": close, "close": close, "volume": volume, "source": source,
            "sourceType": kind, "quality": "ok", "isTrueCandle": kind == "true-candle"}


__all__ = ["market", "envelope", "error", "candle", "json"]
