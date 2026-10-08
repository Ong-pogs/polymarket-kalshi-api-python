"""Writes the two charts as self-contained HTML files in out/ (no libraries, no network).

    write_history_chart(series, title)   both venues' closes on one axis
    write_backtest_chart(result, title)  one venue's closes with the buys and sells marked
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).parent / "out"

# Blue and orange are a pair that stays apart for colour-blind readers on this dark surface.
COLORS = {"polymarket": "#3987e5", "kalshi": "#d95926"}

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { color-scheme: dark; --surface: #1a1a19; --page: #111110; --grid: #2e2e2c;
    --text: #ffffff; --text-2: #c3c2b7; --text-3: #8f8e85; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--page); color: var(--text);
    font: 18px/1.45 "Segoe UI", system-ui, sans-serif; }
  main { max-width: 1680px; margin: 0 auto; padding: 28px 32px 40px; }
  h1 { font-size: 34px; line-height: 1.2; margin: 0 0 6px; font-weight: 650; }
  .sub { color: var(--text-2); font-size: 20px; margin: 0 0 18px; }
  .sub code, .note code { font: 600 18px Consolas, monospace; color: var(--text); }
  .card { background: var(--surface); border-radius: 14px; padding: 20px 22px 14px; }
  .legend { display: flex; gap: 28px; font-size: 20px; color: var(--text-2); margin: 0 0 6px 6px; }
  .legend i { display: inline-block; width: 26px; height: 0; border-top: 3px solid; border-radius: 2px;
    vertical-align: middle; margin-right: 9px; }
  .legend b { color: var(--text); font-weight: 600; }
  svg { display: block; width: 100%; height: auto; }
  .tick { fill: var(--text-3); font-size: 18px; font-variant-numeric: tabular-nums; }
  .end { fill: var(--text); font-size: 20px; font-weight: 600; }
  .mark { fill: var(--text-2); font-size: 17px; }
  .stats { display: flex; gap: 14px; margin: 0 0 16px; flex-wrap: wrap; }
  .stat { background: var(--surface); border-radius: 12px; padding: 12px 18px; min-width: 190px; }
  .stat span { display: block; color: var(--text-2); font-size: 16px; }
  .stat b { font-size: 30px; font-weight: 650; }
  .note { color: var(--text-3); font-size: 17px; margin: 12px 4px 0; }
  #tip { position: fixed; pointer-events: none; background: #262624; border: 1px solid #3a3a37;
    border-radius: 8px; padding: 8px 12px; font-size: 16px; display: none; z-index: 5; }
  #tip div.when { color: var(--text-3); margin-bottom: 3px; }
  #tip div.row i { display: inline-block; width: 16px; border-top: 3px solid; vertical-align: middle;
    margin-right: 7px; }
  #tip div.row b { font-weight: 650; margin-right: 6px; }
  #tip div.row span { color: var(--text-2); }
  details { margin-top: 14px; color: var(--text-2); }
  summary { cursor: pointer; font-size: 17px; }
  table { border-collapse: collapse; margin-top: 8px; font-size: 16px; font-variant-numeric: tabular-nums; }
  td, th { padding: 3px 14px 3px 0; text-align: left; font-weight: 400; }
  th { color: var(--text-3); }
</style></head>
<body><main>
<h1 id="title"></h1>
<p class="sub" id="sub"></p>
<div class="stats" id="stats"></div>
<div class="card">
  <div class="legend" id="legend"></div>
  <svg id="plot" viewBox="0 0 1600 640" role="img"></svg>
</div>
<p class="note" id="note"></p>
<details><summary>The same numbers as a table</summary><table id="table"></table></details>
</main>
<div id="tip"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const data = JSON.parse(document.getElementById('data').textContent);
const NS = 'http://www.w3.org/2000/svg';
const el = (name, attrs, text) => { const node = document.createElementNS(NS, name);
  for (const key in attrs) node.setAttribute(key, attrs[key]);
  if (text !== undefined) node.textContent = text; return node; };
const put = (parent, tag, cls, text) => { const node = document.createElement(tag);
  if (cls) node.className = cls; if (text !== undefined) node.textContent = text; parent.append(node); return node; };
const cents = value => (value * 100).toFixed(1).replace(/\\.0$/, '') + '\\u00a2';
const when = ms => new Date(ms).toISOString().slice(5, 16).replace('T', ' ') + ' UTC';

document.getElementById('title').textContent = data.title;
const sub = document.getElementById('sub');
data.subtitle.forEach(part => put(sub, part.code ? 'code' : 'span', '', part.text));
data.stats.forEach(stat => { const box = put(document.getElementById('stats'), 'div', 'stat');
  put(box, 'span', '', stat.label); put(box, 'b', '', stat.value); });
document.getElementById('note').textContent = data.note;
const legend = document.getElementById('legend');
if (data.series.length > 1) data.series.forEach(s => { const item = put(legend, 'span');
  const key = put(item, 'i'); key.style.borderColor = s.color; put(item, 'b', '', s.name);
  item.append(' ' + s.detail); });

const W = 1600, H = 640, pad = {l: 78, r: 240, t: 22, b: 52};
const points = data.series.flatMap(s => s.points);
const t0 = Math.min(...points.map(p => p.t)), t1 = Math.max(...points.map(p => p.t));
const lowest = Math.min(...points.map(p => p.v)), highest = Math.max(...points.map(p => p.v));
const step = (highest - lowest) > 0.12 ? 0.05 : (highest - lowest) > 0.05 ? 0.02 : 0.01;
const y0 = Math.floor((lowest - step * 0.5) / step) * step, y1 = Math.ceil((highest + step * 0.5) / step) * step;
const x = t => pad.l + (t - t0) / Math.max(1, t1 - t0) * (W - pad.l - pad.r);
const y = v => H - pad.b - (v - y0) / (y1 - y0) * (H - pad.t - pad.b);
const svg = document.getElementById('plot');
svg.setAttribute('aria-label', data.title);
for (let v = y0; v <= y1 + 1e-9; v += step) {
  svg.append(el('line', {x1: pad.l, x2: W - pad.r, y1: y(v), y2: y(v), stroke: 'var(--grid)', 'stroke-width': 1}));
  svg.append(el('text', {x: pad.l - 12, y: y(v) + 6, 'text-anchor': 'end', class: 'tick'}, cents(v)));
}
const day = 86400000;
for (let t = Math.ceil(t0 / day) * day; t <= t1; t += day * Math.max(1, Math.round((t1 - t0) / day / 8))) {
  svg.append(el('text', {x: x(t), y: H - 16, 'text-anchor': 'middle', class: 'tick'},
    new Date(t).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'})));
}
// End labels sit beside their lines; when two would overlap they are pushed apart.
const ends = data.series.map(s => ({s, at: y(s.points.at(-1).v)})).sort((a, b) => a.at - b.at);
for (let i = 1; i < ends.length; i++) if (ends[i].at - ends[i - 1].at < 26) ends[i].at = ends[i - 1].at + 26;
data.series.forEach(s => {
  svg.append(el('polyline', {points: s.points.map(p => x(p.t) + ',' + y(p.v)).join(' '), fill: 'none',
    stroke: s.color, 'stroke-width': 2.5, 'stroke-linejoin': 'round', 'stroke-linecap': 'round'}));
  const last = s.points.at(-1);
  svg.append(el('circle', {cx: x(last.t), cy: y(last.v), r: 6, fill: s.color, stroke: 'var(--surface)', 'stroke-width': 2}));
  svg.append(el('text', {x: x(last.t) + 14, y: ends.find(e => e.s === s).at + 7, class: 'end'},
    (data.series.length > 1 ? s.name + ' ' : '') + cents(last.v)));
});
// Buys and sells: shape and a word carry the meaning, not colour.
(data.marks || []).forEach(m => {
  const cx = x(m.t), cy = y(m.v), up = m.side === 'buy';
  const tri = up ? [[cx, cy - 9], [cx - 8, cy + 6], [cx + 8, cy + 6]] : [[cx, cy + 9], [cx - 8, cy - 6], [cx + 8, cy - 6]];
  svg.append(el('polygon', {points: tri.map(p => p.join(',')).join(' '), fill: 'var(--text)', stroke: 'var(--surface)', 'stroke-width': 2}));
  const edge = cx > W - pad.r - 70;  // near the right edge the label moves left of the end label
  svg.append(el('text', {x: edge ? cx - 14 : cx, y: up ? cy + 28 : cy - 16, 'text-anchor': edge ? 'end' : 'middle', class: 'mark'},
    m.side + ' ' + cents(m.v)));
});
// Hover: a crosshair that snaps to the nearest time, one readout for every series.
const hair = el('line', {y1: pad.t, y2: H - pad.b, stroke: 'var(--text-3)', 'stroke-width': 1, visibility: 'hidden'});
svg.append(hair);
const tip = document.getElementById('tip');
const times = [...new Set(points.map(p => p.t))].sort((a, b) => a - b);
svg.addEventListener('pointermove', event => {
  const box = svg.getBoundingClientRect(), px = (event.clientX - box.left) / box.width * W;
  const t = times.reduce((best, c) => Math.abs(x(c) - px) < Math.abs(x(best) - px) ? c : best, times[0]);
  hair.setAttribute('x1', x(t)); hair.setAttribute('x2', x(t)); hair.setAttribute('visibility', 'visible');
  tip.replaceChildren(); put(tip, 'div', 'when', when(t));
  data.series.forEach(s => { const p = s.points.filter(q => q.t <= t).at(-1); if (!p) return;
    const row = put(tip, 'div', 'row'); const key = put(row, 'i'); key.style.borderColor = s.color;
    put(row, 'b', '', cents(p.v)); put(row, 'span', '', s.name); });
  tip.style.display = 'block';
  tip.style.left = Math.min(event.clientX + 16, innerWidth - tip.offsetWidth - 12) + 'px';
  tip.style.top = (event.clientY + 16) + 'px';
});
svg.addEventListener('pointerleave', () => { tip.style.display = 'none'; hair.setAttribute('visibility', 'hidden'); });
const table = document.getElementById('table');
const head = put(table, 'tr'); ['time', 'series', 'close'].forEach(h => put(head, 'th', '', h));
data.series.forEach(s => s.points.forEach(p => { const row = put(table, 'tr');
  put(row, 'td', '', when(p.t)); put(row, 'td', '', s.name); put(row, 'td', '', p.v.toFixed(3)); }));
</script></body></html>
"""


def _write(name: str, payload: dict) -> Path:
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    # "</" is escaped so no title or label can close the data block early.
    data = json.dumps(payload).replace("</", "<\\/")
    page = PAGE.replace("__TITLE__", html.escape(payload["title"])).replace("__DATA__", data)
    path.write_text(page, encoding="utf8")
    return path.relative_to(Path(__file__).parent) if path.is_relative_to(Path(__file__).parent) else path


def _points(rows: list[dict]) -> list[dict]:
    return [{"t": row["timestamp"], "v": row["close"]} for row in rows]


def _day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%b %d").replace(" 0", " ")


def write_history_chart(series: dict[str, list[dict]], title: str, resolution: str = "4h") -> Path:
    """Both venues' closing prices on one axis. `series` maps venue -> candles."""
    drawn = {venue: rows for venue, rows in series.items() if rows}
    stamps = [row["timestamp"] for rows in drawn.values() for row in rows]
    stats = [{"label": f"{venue} last close", "value": f"{rows[-1]['close'] * 100:.1f}¢"}
             for venue, rows in drawn.items()]
    if len(drawn) == 2:
        first, second = (rows[-1]["close"] for rows in drawn.values())
        stats.append({"label": "difference (indicative)", "value": f"{abs(first - second) * 100:.1f}¢"})
    return _write("history.html", {
        "title": title,
        "subtitle": [
            {"text": f"{resolution} candles, {_day(min(stamps))} to {_day(max(stamps))}, from "},
            {"text": "GET /api/{venue}/fetchOHLCV", "code": True},
            {"text": " through Predictefy. 5 credits per venue."},
        ],
        "stats": stats,
        "note": "Closing price of each candle that had a price in it. A difference between "
                "venues is a price difference, not a trade: check asks, depth, fees and "
                "the resolution rules first.",
        "series": [{"name": venue, "color": COLORS.get(venue, "#3987e5"),
                    "detail": f"{len(rows)} candles", "points": _points(rows)}
                   for venue, rows in drawn.items()],
    })


def write_backtest_chart(result: dict, title: str) -> Path:
    """One venue's closes with each buy and sell marked. `result` comes from step 6."""
    rows = result["candles"]
    stamps = [row["timestamp"] for row in rows]
    return _write(f"backtest-{result['venue']}-{result['days']}d.html", {
        "title": title,
        "subtitle": [
            {"text": f"{result['venue']}, {result['resolution']} candles, "
                     f"{_day(min(stamps))} to {_day(max(stamps))}, from "},
            {"text": "GET /api/{venue}/fetchOHLCV", "code": True},
            {"text": " through Predictefy."},
        ],
        "stats": [
            {"label": "candles", "value": str(len(rows))},
            {"label": "round trips", "value": str(len(result["trades"]))},
            {"label": "result on paper",
             "value": f"{'-' if result['pnl'] < 0 else '+'}${abs(result['pnl']):.2f}"},
        ],
        "note": "A first look, not a result to trust: it trades at candle closes with no "
                "spread, no fees and no limit on size. Step 7 replays real quotes.",
        "series": [{"name": result["venue"], "color": COLORS.get(result["venue"], "#3987e5"),
                    "detail": "", "points": _points(rows)}],
        "marks": [{"t": mark["timestamp"], "v": mark["price"], "side": mark["side"]}
                  for mark in result["marks"]],
    })
