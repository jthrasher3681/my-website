"""Run the rectangle detector over the universe and write the page's data files.

    python3 -m screener.build --hood-dir RAW_DIR      # Robinhood dumps
    python3 -m screener.build --yfinance              # Yahoo Finance download

Run from the ``rectangle-screener`` directory. Writes ``data/screen.json``
(one row per match, plus a small close-price thumbnail) and
``data/charts.json`` (daily OHLCV around each match for the detail chart).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from . import rectangle
from .sources import load_hood_dumps, load_yfinance

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UNIVERSE_CSV = os.path.join(HERE, "universe.csv")
NY = ZoneInfo("America/New_York")

MIN_MARKET_CAP = 2e9
MIN_PRICE = 5.0
MIN_VOLUME = 5e5
MIN_DOLLAR_VOLUME = 2e7
UNIVERSE_RULE = "US-listed stocks with market cap ≥ $2B, price ≥ $5 and ≥ $20M traded per day"
LISTS_URL = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/{ex}/{ex}_full_tickers.json"

MIN_BARS = 60
THUMB_POINTS = 90
CHART_PAD = 30  # bars shown before the rectangle starts
CHART_MIN = 120
CHART_MAX = 260


def _num(x) -> float:
    try:
        return float(str(x).replace("$", "").replace(",", ""))
    except ValueError:
        return 0.0


def fetch_universe() -> list[dict]:
    """Rebuild the universe from the daily NASDAQ/NYSE/AMEX listings."""
    rows = []
    for ex in ("nasdaq", "nyse", "amex"):
        with urllib.request.urlopen(LISTS_URL.format(ex=ex), timeout=60) as fh:
            for r in json.load(fh):
                sym = r["symbol"].replace("/", ".")
                price, vol, cap = _num(r["lastsale"]), _num(r["volume"]), _num(r["marketCap"])
                if not re.fullmatch(r"[A-Z]{1,5}(\.[A-Z])?", sym):
                    continue
                if cap >= MIN_MARKET_CAP and price >= MIN_PRICE and vol >= MIN_VOLUME and price * vol >= MIN_DOLLAR_VOLUME:
                    rows.append(
                        {
                            "symbol": sym,
                            "name": r["name"],
                            "exchange": ex.upper(),
                            "sector": r["sector"],
                            "industry": r["industry"],
                            "market_cap": int(cap),
                        }
                    )
    rows.sort(key=lambda r: -r["market_cap"])
    return rows


def read_universe(path: str = UNIVERSE_CSV) -> list[dict]:
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["market_cap"] = int(float(r["market_cap"] or 0))
    return rows


def write_universe(rows: list[dict], path: str = UNIVERSE_CSV) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "name", "exchange", "sector", "industry", "market_cap"])
        w.writeheader()
        w.writerows(rows)


def clean_name(name: str) -> str:
    """'Apple Inc. Common Stock' -> 'Apple Inc.'"""
    name = re.sub(
        r"\s+(Class [A-C] )?(Common Stock|Ordinary Shares|Common Shares|American Depositary Shares|"
        r"Depositary Shares|Subordinate Voting Shares|Common Units|Shares of Beneficial Interest).*$",
        "",
        name,
        flags=re.I,
    )
    return name.strip() or name


def drop_incomplete_session(bars: dict[str, pd.DataFrame], now: datetime) -> None:
    """Drop today's bar if the regular session has not closed yet."""
    local = now.astimezone(NY)
    if local.hour * 60 + local.minute >= 16 * 60 + 15:
        return
    today = pd.Timestamp(local.date())
    for sym, df in bars.items():
        if len(df) and df.index[-1] >= today:
            bars[sym] = df[df.index < today]


def _r(x: float, nd: int = 2):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), nd)


def _round_hit(hit: dict) -> dict:
    """Trim the detector's floats to what the page displays."""
    out = dict(hit)
    for k in ("top", "bottom", "target"):
        if out.get(k) is not None:
            out[k] = _r(out[k], 2 if abs(out[k]) >= 1 else 4)
    for k in ("height_pct", "position_pct", "extension_pct", "atr_pct", "breakout_volume_ratio"):
        if out.get(k) is not None:
            out[k] = _r(out[k], 2)
    if out.get("quality") is not None:
        out["quality"] = _r(out["quality"], 1)
    out["touches"] = [{**t, "price": _r(t["price"], 2 if abs(t["price"]) >= 1 else 4)} for t in out.get("touches") or []]
    return out


def thumb(closes) -> list:
    """Evenly spaced samples of a close series (first and last bar included)."""
    n = len(closes)
    p = min(n, THUMB_POINTS)
    idx = sorted({round(k * (n - 1) / (p - 1)) for k in range(p)}) if p > 1 else [0]
    return [_r(closes[i]) for i in idx]


def scan(bars: dict[str, pd.DataFrame], universe: list[dict], as_of: pd.Timestamp, params: dict | None):
    meta = {r["symbol"]: r for r in universe}
    results, charts = [], {}
    skipped = Counter()
    for sym in sorted(bars):
        df = bars[sym]
        if sym not in meta:
            skipped["not in universe"] += 1
            continue
        if len(df) < MIN_BARS:
            skipped["short history"] += 1
            continue
        if df.index[-1] != as_of:
            skipped["stale last bar"] += 1
            continue
        try:
            hit = rectangle.detect(df, params)
        except Exception as exc:  # one bad series must not sink the run
            print(f"{sym}: detect failed: {exc!r}", file=sys.stderr)
            skipped["error"] += 1
            continue
        if not hit:
            continue

        start_i = int(df.index.get_indexer([pd.Timestamp(hit["start"])])[0])
        c0 = max(0, min(start_i - CHART_PAD, len(df) - CHART_MIN))
        c0 = max(c0, len(df) - CHART_MAX)
        win = df.iloc[c0:]
        charts[sym] = {
            "d": [d.strftime("%Y-%m-%d") for d in win.index],
            "o": [_r(x) for x in win["open"]],
            "h": [_r(x) for x in win["high"]],
            "l": [_r(x) for x in win["low"]],
            "c": [_r(x) for x in win["close"]],
            "v": [int(x) if math.isfinite(x) else 0 for x in win["volume"]],
        }

        last, prev = df["close"].iloc[-1], df["close"].iloc[-2]
        dollar_vol = (df["close"] * df["volume"]).iloc[-50:].mean()
        m = meta[sym]
        row = {
            "symbol": sym,
            "name": clean_name(m["name"]),
            "exchange": m.get("exchange") or "",
            "sector": m.get("sector") or "",
            "industry": m.get("industry") or "",
            "market_cap": m["market_cap"],
            "close": _r(last),
            "change_pct": _r((last / prev - 1) * 100),
            "dollar_volume": _r(dollar_vol, 0),
        }
        row.update(_round_hit(hit))
        # Thumbnail: closes from a little before the rectangle to today, with the
        # rectangle's first/last bar given as fractions of the thumbnail width.
        t0 = max(0, start_i - 15)
        end_i = int(df.index.get_indexer([pd.Timestamp(hit["end"])])[0])
        span = max(1, len(df) - 1 - t0)
        row["thumb"] = thumb(df["close"].to_numpy()[t0:])
        row["thumb_box"] = [_r((start_i - t0) / span, 4), _r((end_i - t0) / span, 4)]
        results.append(row)
    return results, charts, skipped


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--hood-dir", help="directory of Robinhood daily_*/intra_* JSON dumps")
    src.add_argument("--yfinance", action="store_true", help="download bars from Yahoo Finance")
    ap.add_argument("--refresh-universe", action="store_true", help="rebuild universe.csv from the daily exchange listings")
    ap.add_argument("--out", default=os.path.join(ROOT, "data"))
    args = ap.parse_args(argv)

    universe = read_universe()
    if args.refresh_universe:
        try:
            fresh = fetch_universe()
            if len(fresh) > 0.6 * len(universe):  # guard against a truncated listing
                universe = fresh
                write_universe(universe)
        except Exception as exc:
            print(f"universe refresh failed, keeping {UNIVERSE_CSV}: {exc!r}", file=sys.stderr)

    now = datetime.now(timezone.utc)
    symbols = [r["symbol"] for r in universe]
    if args.hood_dir:
        bars = load_hood_dumps(args.hood_dir)
        source = "Robinhood daily bars"
    else:
        bars = load_yfinance(symbols)
        source = "Yahoo Finance daily bars"
    drop_incomplete_session(bars, now)
    bars = {s: df for s, df in bars.items() if len(df)}
    if len(bars) < 0.5 * len(universe):
        # A mostly failed download would publish a misleadingly short list.
        print(f"only {len(bars)}/{len(universe)} symbols loaded; keeping the previous scan", file=sys.stderr)
        return 1

    as_of = Counter(df.index[-1] for df in bars.values()).most_common(1)[0][0]
    t0 = time.time()
    results, charts, skipped = scan(bars, universe, as_of, None)
    elapsed = time.time() - t0

    order = {"breakout_up": 0, "breakout_down": 1, "inside": 2}
    results.sort(key=lambda r: (order[r["status"]], -(r.get("quality") or 0)))
    counts = Counter(r["status"] for r in results)
    scanned = len(bars) - sum(skipped.values())

    os.makedirs(args.out, exist_ok=True)
    screen = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": as_of.strftime("%Y-%m-%d"),
        "source": source,
        "universe": {"rule": UNIVERSE_RULE, "size": len(universe), "scanned": scanned},
        "params": rectangle.DEFAULT_PARAMS,
        "counts": {k: counts.get(k, 0) for k in ("inside", "breakout_up", "breakout_down")},
        "results": results,
    }
    with open(os.path.join(args.out, "screen.json"), "w") as fh:
        json.dump(screen, fh, separators=(",", ":"))
    with open(os.path.join(args.out, "charts.json"), "w") as fh:
        json.dump(charts, fh, separators=(",", ":"))

    print(
        f"as of {screen['as_of']}: scanned {scanned}/{len(universe)} in {elapsed:.1f}s -> "
        f"{len(results)} matches {dict(counts)}; skipped {dict(skipped)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
