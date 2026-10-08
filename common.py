"""Shared by every step: the API key, the client, a credit counter and record/replay.

Nothing here is specific to one venue. The steps import a few names from it:

    from common import client, done, MARKETS
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl

import httpx
from predictefy import Predictefy, PredictefyError

ROOT = Path(__file__).parent
KEYS_URL = "https://portal.predictefy.com/keys"
UPGRADE_URL = (
    "https://predictefy.com/en/pricing?utm_source=youtube&utm_medium=video"
    "&utm_campaign=polymarket-kalshi-api-python&utm_content=upgrade"
)
PLACEHOLDER = "pk_live_your_key_here"

# The same question on two venues. The ids come from step 2's output; set
# PM_MARKET and KALSHI_MARKET (or edit these) to follow a different market.
MARKETS = {
    "polymarket": os.environ.get("PM_MARKET", "634974"),
    "kalshi": os.environ.get("KALSHI_MARKET", "KXAKSENATE-26NOV03-DSUL"),
}


def load_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=VALUE lines from .env into the environment (existing values win)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


class Tape(httpx.BaseTransport):
    """Counts the credits each response reports, and can record or replay responses.

    PREDICTEFY_RECORD=folder  saves every response under folder/<script>/
    PREDICTEFY_REPLAY=folder  answers from those files: no network, no key, no credits
    """

    def __init__(self, inner: httpx.BaseTransport | None, record: Path | None = None,
                 replay: Path | None = None) -> None:
        self.inner, self.record, self.replay = inner, record, replay
        self.calls: list[dict] = []
        self.used: set[Path] = set()

    @staticmethod
    def _key(request: httpx.Request) -> dict:
        pairs = parse_qsl(request.url.query.decode("ascii"), keep_blank_values=True)
        return {"method": request.method, "path": request.url.path,
                "query": sorted([name, value] for name, value in pairs)}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        key = self._key(request)
        if self.replay is not None:
            return self._replayed(request, key)
        response = self.inner.handle_request(request)
        charged = response.headers.get("x-credits-charged")
        self.calls.append({**key, "status": response.status_code, "credits": int(charged or 0)})
        # Replay pages are streamed NDJSON; step 7 saves those itself.
        if self.record is None or key["path"].startswith("/v1/history/replay"):
            return response
        body = response.read()
        self.record.mkdir(parents=True, exist_ok=True)
        name = f"{len(self.calls):03d}{key['path'].replace('/', '-')}.json"
        (self.record / name).write_text(json.dumps({
            **key, "status": response.status_code, "credits": charged,
            "contentType": response.headers.get("content-type", "application/json"),
            "body": body.decode("utf8"),
        }, indent=1), encoding="utf8")
        return self._response(request, response.status_code, charged,
                              response.headers.get("content-type"), body)

    def _replayed(self, request: httpx.Request, key: dict) -> httpx.Response:
        for file in sorted(self.replay.glob("[0-9]*.json")):
            saved = json.loads(file.read_text(encoding="utf8"))
            if file not in self.used and all(saved[field] == key[field] for field in key):
                self.used.add(file)
                self.calls.append({**key, "status": saved["status"],
                                   "credits": int(saved["credits"] or 0)})
                return self._response(request, saved["status"], saved["credits"],
                                      saved["contentType"], saved["body"].encode("utf8"))
        raise SystemExit(f"Not in the recording at {self.replay}: {key['path']} {key['query']}")

    @staticmethod
    def _response(request, status, charged, content_type, body: bytes) -> httpx.Response:
        headers = {"content-type": content_type or "application/json"}
        if charged is not None:
            headers["x-credits-charged"] = str(charged)
        return httpx.Response(status, headers=headers, content=body, request=request)


_state: dict = {}


def _folder(name: str) -> Path | None:
    """The record or replay folder for this run: one per script and set of arguments."""
    base = os.environ.get(name)
    if not base:
        return None
    run = Path(sys.argv[0]).stem + "".join("-" + arg.strip("-") for arg in sys.argv[1:])
    return Path(base) / run


def connect(transport: httpx.BaseTransport | None = None, api_key: str | None = None):
    """Build the client once. Tests pass their own transport; you never need to."""
    load_env()
    replay = None if transport else _folder("PREDICTEFY_REPLAY")
    record = None if transport or replay else _folder("PREDICTEFY_RECORD")
    key = api_key or os.environ.get("PREDICTEFY_API_KEY", "")
    if replay is not None:
        if not (replay / "meta.json").exists():
            raise SystemExit(f"No recording at {replay}. Make one with PREDICTEFY_RECORD first.")
        key = key or "replay-needs-no-key"
    elif transport is None and (not key or key == PLACEHOLDER):
        raise SystemExit(
            "PREDICTEFY_API_KEY is not set.\n"
            f"Create a key at {KEYS_URL}, then copy .env.example to .env and paste it in."
        )
    tape = Tape(transport or (None if replay else httpx.HTTPTransport()), record, replay)
    _state.update(client=Predictefy(api_key=key, transport=tape), tape=tape, now=None)
    if replay is not None:
        saved = json.loads((replay / "meta.json").read_text(encoding="utf8"))
        _state["now"] = datetime.fromisoformat(saved["now"])
        print(f"[replay] responses recorded {_state['now']:%Y-%m-%d %H:%M} UTC, no API call made")
    elif record is not None:
        record.mkdir(parents=True, exist_ok=True)
        _state["now"] = datetime.now(timezone.utc).replace(microsecond=0)
        (record / "meta.json").write_text(json.dumps({"now": _state["now"].isoformat()}))
    return _state["client"]


class _Lazy:
    """`client` connects on first use, so importing a step never needs a key."""

    def __getattr__(self, name: str):
        return getattr(_state.get("client") or connect(), name)


client = _Lazy()


def now() -> datetime:
    """The current time in UTC, or the recording's time when replaying."""
    if not _state:
        connect()
    return _state.get("now") or datetime.now(timezone.utc)


def window(days: float) -> tuple[str, str]:
    """ISO start and end for the last `days` days, on the hour.

    The start is rounded forward, so a 7-day window stays inside the free plan's 7 days.
    """
    end = now().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days) + timedelta(hours=1)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")


def yes_outcome(venue: str, market_id: str) -> dict:
    """The market's title and the outcomeId of its Yes side (books and candles key on it)."""
    market = client.exchange(venue).fetch_market(market_id)
    side = market.get("yes") or market["outcomes"][0]
    return {"venue": venue, "marketId": market["marketId"], "title": market["title"],
            "outcomeId": side["outcomeId"], "price": side["price"]}


def credits() -> tuple[int, str]:
    """Credits charged so far and where they went, from the X-Credits-Charged header."""
    by_verb: dict[str, list[int]] = {}
    for call in _state["tape"].calls if _state else []:
        by_verb.setdefault(call["path"].rsplit("/", 1)[-1], []).append(call["credits"])
    parts = [f"{verb} {costs[0]}" + (f" x{len(costs)}" if len(costs) > 1 else "")
             for verb, costs in by_verb.items()]
    return sum(sum(costs) for costs in by_verb.values()), ", ".join(parts)


def done() -> None:
    """Print what the run cost. Every step ends with this."""
    total, detail = credits()
    recorded = " (as recorded)" if _state and _state["tape"].replay else ""
    print()
    print(f"credits used: {total}{recorded}   [{detail or 'no API call'}]")


def money(amount: float) -> str:
    """A signed dollar amount: +$1.00, -$4.00."""
    return f"{'-' if amount < 0 else '+'}${abs(amount):.2f}"


def explain(error: PredictefyError) -> str:
    """A plain sentence for the errors a reader of this tutorial is most likely to meet."""
    if error.code == "PLAN_REQUIRED":
        return (f"403 PLAN_REQUIRED: {error.message}\n"
                "The free plan reads 7 days of history. Builder reads 12 months and adds\n"
                f"the replay route. Plans: {UPGRADE_URL}")
    if error.status == 402:
        return (f"402 {error.code}: this month's credits are used up.\n"
                f"Plans: {UPGRADE_URL}")
    if error.status == 401:
        return f"401 {error.code}: the API key was not accepted. Check it at {KEYS_URL}"
    return f"{error.status} {error.code}: {error.message}"
