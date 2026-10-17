"""Run the rectangle detector over the universe and write the page's data files.

    python3 -m screener.build --hood-dir RAW_DIR      # Robinhood dumps
    python3 -m screener.build --yfinance              # Yahoo Finance download

Run from the ``rectangle-screener`` directory. Writes ``data/screen.json``
(one row per match, plus a small close-price thumbnail) and
``data/charts.json`` (daily OHLCV around each match for the detail chart).
A run that cannot see most of the universe exits non-zero and leaves the
previous files in place.
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

import numpy as np
import pandas as pd

from . import rectangle
from .sources import load_hood_dumps, load_yfinance

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UNIVERSE_CSV = os.path.join(HERE, "universe.csv")
NY = ZoneInfo("America/New_York")

# Listing filters (one day's snapshot, so deliberately loose on turnover) ...
MIN_MARKET_CAP = 2e9
MIN_PRICE = 5.0
MIN_LISTING_DOLLAR_VOLUME = 5e6
# ... and the liquidity test applied to the downloaded bars.
MIN_DOLLAR_VOLUME = 2e7
LIQUIDITY_BARS = 50
UNIVERSE_RULE = "US-listed common stocks with market cap ≥ $2B, price ≥ $5 and a median of ≥ $20M traded per day over 50 sessions"
LISTS_URL = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/{ex}/{ex}_full_tickers.json"
# Preferreds, depositary/convertible lines, notes, warrants, rights and units
# carry the parent's market cap but are not the common stock.
NOT_COMMON = re.compile(
    r"preferred stock|mandatory convertible|perpetual|\bnotes? due\b|\bwarrants?\b|\bsubscription rights\b|\bunits?,? each\b"
    r"|corporate units|equity units",
    re.I,
)

VOLUME_DECLINE_PCT = -15.0  # "declining": trend line and last third vs first third down at least this much,
VOLUME_TREND_P = 0.10       #   and a Mann-Kendall decline this significant (see volume_profile);
VOLUME_STEP_PCT = 5.0       # "steadily": each third of the box at least this much below the one before,
VOLUME_STEADY_P = 0.05      #   and a Mann-Kendall decline this significant
CONFIRM_PCT = 3.0  # a breakout is confirmed by a daily close this far beyond the broken line (% of the line)
MIN_COVERAGE = 0.8  # share of the universe that must have data through the scan date
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
                if not re.fullmatch(r"[A-Z]{1,5}(\.[A-Z])?", sym) or NOT_COMMON.search(r["name"]):
                    continue
                if cap >= MIN_MARKET_CAP and price >= MIN_PRICE and price * vol >= MIN_LISTING_DOLLAR_VOLUME:
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
    return [r for r in rows if not NOT_COMMON.search(r["name"])]


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


def pick_as_of(bars: dict[str, pd.DataFrame], coverage: float = MIN_COVERAGE) -> pd.Timestamp:
    """The latest session that at least ``coverage`` of the symbols have reached."""
    last = pd.Series([df.index[-1] for df in bars.values()]).sort_values(ascending=False)
    return last.iloc[max(0, math.ceil(coverage * len(last)) - 1)]


def is_liquid(df: pd.DataFrame) -> bool:
    recent = df.iloc[-LIQUIDITY_BARS:]
    dollar_volume = (recent["close"] * recent["volume"]).median()
    return bool(recent["close"].iloc[-1] >= MIN_PRICE and dollar_volume >= MIN_DOLLAR_VOLUME)


def _r(x: float, nd: int = 2):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), nd)


def _round_hit(hit: dict) -> dict:
    """Trim the detector's floats to what the page displays."""
    out = dict(hit)
    # top / bottom keep the detector's precision: the next scan re-checks this box
    # from these numbers (see previous_boxes), and rounding can tip a marginal rule
    if out.get("target") is not None:
        out["target"] = _r(out["target"], 2 if abs(out["target"]) >= 1 else 4)
    for k in ("height_pct", "position_pct", "extension_pct", "atr_pct", "breakout_volume_ratio"):
        if out.get(k) is not None:
            out[k] = _r(out[k], 2)
    if out.get("quality") is not None:
        out["quality"] = _r(out["quality"], 1)
    out["touches"] = [{**t, "price": _r(t["price"], 2 if abs(t["price"]) >= 1 else 4)} for t in out.get("touches") or []]
    return out


def volume_profile(volume, keep=None) -> dict | None:
    """How volume behaved across a box.

    volume     the box's sessions in order; keep optionally masks the ones to use (the
               build leaves out sessions that closed beyond a line: that volume belongs
               to a breakout attempt, not to the range).  Sessions without a volume print
               are skipped; the rest keep their place in time.
    trend_pct  change of a robust trend line through the log volume (Theil-Sen: the
               median of all pairwise slopes), first to last session of the box, in %
    line       that trend line's volume at the box's first and last session
    thirds     median volume of the first, middle and last third of the sessions used,
               as % of the first
    declining  the trend line is down at least VOLUME_DECLINE_PCT, the last third trades
               at least that much below the first, and the decline is unlikely to be noise
               (one-sided Mann-Kendall test, p < VOLUME_TREND_P)
    steady     declining throughout: also each third at least VOLUME_STEP_PCT below the
               one before, p < VOLUME_STEADY_P, and no pick-up at the end (the last week
               and the last sixth trade no more than the middle third)
    None when a third would have fewer than three sessions."""
    raw = np.asarray(volume, dtype=float)
    ok = np.isfinite(raw) & (raw > 0)
    if keep is not None:
        ok &= np.asarray(keep, dtype=bool)
    t = np.flatnonzero(ok)
    v = raw[t]
    n = len(v)
    k = n // 3
    if k < 3:
        return None
    i, j = np.triu_indices(n, 1)
    lv = np.log(v)
    slope = float(np.median((lv[j] - lv[i]) / (t[j] - t[i])))
    level = float(np.median(lv - slope * t))
    span = len(raw) - 1
    trend = (math.exp(slope * span) - 1) * 100
    m1, m2, m3 = (float(np.median(part)) for part in (v[:k], v[k:-k], v[-k:]))
    p_down = _mann_kendall_p_down(v)
    declining = trend <= VOLUME_DECLINE_PCT and m3 <= m1 * (1 + VOLUME_DECLINE_PCT / 100) and p_down < VOLUME_TREND_P
    step = 1 - VOLUME_STEP_PCT / 100
    late = max(float(np.median(v[-5:])), float(np.median(v[-max(3, n // 6):])))
    steady = declining and m2 <= m1 * step and m3 <= m2 * step and p_down < VOLUME_STEADY_P and late <= m2
    return {
        "trend_pct": trend,
        "line": [math.exp(level), math.exp(level + slope * span)],
        "thirds": [100.0, m2 / m1 * 100, m3 / m1 * 100],
        "declining": bool(declining),
        "steady": bool(steady),
    }


def confirmation(close: pd.Series, hit: dict) -> dict:
    """How far the closes since a breakout got beyond the broken line, as % of the line.

    close_beyond_pct      the latest close
    max_close_beyond_pct  the furthest close since the breakout (breakout day included)
    confirmed_date        the first close at least CONFIRM_PCT beyond the line, or None
    All None for a stock still inside its box."""
    out = {"close_beyond_pct": None, "max_close_beyond_pct": None, "confirmed_date": None}
    if hit["status"] == "inside" or not hit.get("breakout_date"):
        return out
    after = close[close.index >= pd.Timestamp(hit["breakout_date"])].dropna()
    if after.empty:
        return out
    if hit["status"] == "breakout_up":
        beyond = (after / hit["top"] - 1) * 100
    else:
        beyond = (1 - after / hit["bottom"]) * 100
    beyond = beyond.round(2)  # decide on the value the page shows (2.996% is not "3.00%" unconfirmed)
    hits = beyond[beyond >= CONFIRM_PCT]
    out["close_beyond_pct"] = _r(beyond.iloc[-1], 2)
    out["max_close_beyond_pct"] = _r(beyond.max(), 2)
    out["confirmed_date"] = hits.index[0].strftime("%Y-%m-%d") if len(hits) else None
    return out


def _mann_kendall_p_down(v) -> float:
    """One-sided p-value that the series trends down (Mann-Kendall, normal approximation)."""
    n = len(v)
    i, j = np.triu_indices(n, 1)
    s = float(np.sign(v[j] - v[i]).sum())
    sd = math.sqrt(n * (n - 1) * (2 * n + 5) / 18)
    z = (s + 1) / sd if s < 0 else (s - 1) / sd if s > 0 else 0.0
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def thumb(closes) -> list:
    """Evenly spaced samples of a close series (first and last bar included)."""
    n = len(closes)
    p = min(n, THUMB_POINTS)
    idx = sorted({round(k * (n - 1) / (p - 1)) for k in range(p)}) if p > 1 else [0]
    return [_r(closes[i]) for i in idx]


def previous_boxes(path: str) -> dict[str, dict]:
    """Rectangles of the last published scan, re-checked as hints so a box doesn't drop
    out of the list just because one new bar shifted the detector's swing clusters."""
    try:
        with open(path) as fh:
            rows = json.load(fh)["results"]
        return {r["symbol"]: {k: r[k] for k in ("start", "top", "bottom")} for r in rows}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def scan(bars: dict[str, pd.DataFrame], universe: list[dict], as_of: pd.Timestamp, params: dict | None,
         hints: dict[str, dict] | None = None):
    meta = {r["symbol"]: r for r in universe}
    hints = hints or {}
    results, charts = [], {}
    stats = Counter()
    for sym in sorted(bars):
        df = bars[sym]
        filled = as_of.strftime("%Y-%m-%d") in df.attrs.get("filled_sessions", [])
        df = df[df.index <= as_of]  # a symbol that is a session ahead is scanned as of the same date
        df = df.replace([math.inf, -math.inf], math.nan)  # bad ticks: treat as missing
        if sym not in meta:
            stats["not in universe"] += 1
            continue
        if len(df) < MIN_BARS:
            stats["short history"] += 1
            continue
        if df.index[-1] != as_of:
            stats["stale last bar"] += 1
            continue
        stats["fresh"] += 1
        if not is_liquid(df):
            stats["illiquid"] += 1
            continue
        stats["scanned"] += 1
        stats["estimated last bar"] += filled
        try:
            hit = rectangle.detect(df, params, hint=hints.get(sym))
        except Exception as exc:  # one bad series must not sink the run
            print(f"{sym}: detect failed: {exc!r}", file=sys.stderr)
            stats["error"] += 1
            continue
        if not hit:
            continue

        start_i = int(df.index.get_indexer([pd.Timestamp(hit["start"])])[0])
        end_i = int(df.index.get_indexer([pd.Timestamp(hit["end"])])[0])
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
        m = meta[sym]
        row = {
            "symbol": sym,
            "name": clean_name(m["name"]),
            "exchange": m.get("exchange") or "",
            "sector": " ".join((m.get("sector") or "").split()),
            "industry": m.get("industry") or "",
            "market_cap": m["market_cap"],
            "close": _r(last),
            "change_pct": _r((last / prev - 1) * 100),
            "dollar_volume": _r((df["close"] * df["volume"]).iloc[-LIQUIDITY_BARS:].median(), 0),
        }
        row.update(_round_hit(hit))
        box = df.iloc[start_i : end_i + 1]
        inside = ((box["close"] <= hit["top"]) & (box["close"] >= hit["bottom"])).to_numpy()
        vp = volume_profile(box["volume"].to_numpy(), keep=inside)
        row["volume_trend_pct"] = _r(vp["trend_pct"], 1) if vp else None
        row["volume_line"] = [_r(x, 0) for x in vp["line"]] if vp else None
        row["volume_thirds"] = [_r(x, 0) for x in vp["thirds"]] if vp else None
        row["volume_declining"] = vp["declining"] if vp else False
        row["volume_steady"] = vp["steady"] if vp else False
        row.update(confirmation(df["close"], hit))
        # Thumbnail: closes from a little before the rectangle to today, with the
        # rectangle's first/last bar given as fractions of the thumbnail width.
        t0 = max(0, start_i - 15)
        span = max(1, len(df) - 1 - t0)
        row["thumb"] = thumb(df["close"].to_numpy()[t0:])
        row["thumb_box"] = [_r((start_i - t0) / span, 4), _r((end_i - t0) / span, 4)]
        results.append(row)
    return results, charts, stats


def _write_json(path: str, payload) -> None:
    """Strict (no NaN/Infinity) JSON, swapped into place atomically."""
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, separators=(",", ":"), allow_nan=False)
    os.replace(tmp, path)


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
            if len(fresh) > 0.8 * len(universe):  # guard against a truncated listing
                universe = fresh
                write_universe(universe)
            else:
                print(f"listing returned only {len(fresh)} names; keeping {UNIVERSE_CSV}", file=sys.stderr)
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
    listed = set(symbols)
    bars = {s: df for s, df in bars.items() if len(df) and s in listed}
    if not bars:
        print("no price data loaded", file=sys.stderr)
        return 1

    as_of = pick_as_of(bars)
    hints = previous_boxes(os.path.join(args.out, "screen.json"))
    t0 = time.time()
    results, charts, stats = scan(bars, universe, as_of, None, hints)
    elapsed = time.time() - t0
    if stats["fresh"] < MIN_COVERAGE * len(universe):
        # A mostly failed download would publish a misleadingly short list.
        print(
            f"only {stats['fresh']}/{len(universe)} symbols have data through {as_of.date()}; keeping the previous scan",
            file=sys.stderr,
        )
        return 1

    order = {"breakout_up": 0, "breakout_down": 1, "inside": 2}
    results.sort(key=lambda r: (order[r["status"]], -(r.get("quality") or 0)))
    counts = Counter(r["status"] for r in results)
    estimated = stats["estimated last bar"]
    provisional = estimated > 0
    note = ""
    if provisional:
        who = "" if estimated == stats["scanned"] else f" for {estimated:,} of the {stats['scanned']:,} stocks"
        note = (
            f"The {as_of:%b} {as_of.day} session{who} is built from 30-minute bars until the official daily bar is "
            "published, so those closes and volumes are estimates."
        )

    os.makedirs(args.out, exist_ok=True)
    screen = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": as_of.strftime("%Y-%m-%d"),
        "source": source,
        "source_note": note,
        "provisional_last_bar": provisional,
        "universe": {"rule": UNIVERSE_RULE, "listed": len(universe), "scanned": stats["scanned"]},
        "params": {**rectangle.DEFAULT_PARAMS, "volume_decline_pct": VOLUME_DECLINE_PCT, "volume_step_pct": VOLUME_STEP_PCT,
                   "confirm_pct": CONFIRM_PCT},
        "counts": {k: counts.get(k, 0) for k in ("inside", "breakout_up", "breakout_down")},
        "results": results,
    }
    _write_json(os.path.join(args.out, "charts.json"), charts)
    _write_json(os.path.join(args.out, "screen.json"), screen)

    print(
        f"as of {screen['as_of']}: scanned {stats['scanned']} liquid of {len(universe)} listed in {elapsed:.1f}s -> "
        f"{len(results)} matches {dict(counts)}; {dict(stats)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
