"""Daily OHLCV loaders for the rectangle screener.

Every loader returns ``{symbol: DataFrame}`` where each frame has a
DatetimeIndex of trading days (ascending, tz-naive) and float columns
``open, high, low, close, volume``. The last row is the most recent
completed session.

Two sources are supported:

* ``load_hood_dumps`` - JSON files saved from Robinhood's
  ``get_equity_historicals`` tool (daily bars, optionally plus 30-minute
  bars used to fill in a session whose daily bar is not published yet).
  A filled session is an estimate: its close is the last half-hour's close
  and its volume is scaled up from the half-hour bars, which carry only part
  of the consolidated volume. Filled dates are listed in
  ``df.attrs["filled_sessions"]``.
* ``load_yfinance`` - Yahoo Finance via the ``yfinance`` package, for
  unattended refreshes (GitHub Actions).
"""

from __future__ import annotations

import glob
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]
NY = ZoneInfo("America/New_York")

# A regular session's last half-hour bar starts at 15:30 New York time; a
# session is only filled from intraday bars if that bar is present and the
# dump was saved after the close (half-day sessions are left to the daily bar).
LAST_HALF_HOUR = (15, 30)
CLOSE_GRACE = timedelta(minutes=5)


def _bars_to_frame(bars: list[dict]) -> pd.DataFrame:
    rows = [
        (
            b["begins_at"],
            float(b["open_price"]),
            float(b["high_price"]),
            float(b["low_price"]),
            float(b["close_price"]),
            float(b.get("volume") or 0),
        )
        for b in bars
        if not b.get("interpolated") and b.get("session", "reg") == "reg"
    ]
    df = pd.DataFrame(rows, columns=["ts"] + COLUMNS)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    # The same bar can appear in more than one dump (re-fetches).
    return df.drop_duplicates("ts", keep="last")


def _daily_from_intraday(df: pd.DataFrame, fetched_at: datetime | None = None) -> pd.DataFrame:
    """Aggregate half-hour bars into one bar per session that was complete when fetched."""
    if df.empty:
        return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([]), dtype=float)
    df = df.sort_values("ts")
    local = df["ts"].dt.tz_convert(NY)
    day = local.dt.normalize().dt.tz_localize(None)
    g = df.groupby(day)
    out = pd.DataFrame(
        {
            "open": g["open"].first(),
            "high": g["high"].max(),
            "low": g["low"].min(),
            "close": g["close"].last(),
            "volume": g["volume"].sum(),
        }
    )
    has_last_bar = (local.dt.hour == LAST_HALF_HOUR[0]) & (local.dt.minute == LAST_HALF_HOUR[1])
    complete = has_last_bar.groupby(day).any()
    if fetched_at is not None:
        closes = pd.Series(
            [datetime(d.year, d.month, d.day, 16, tzinfo=NY) + CLOSE_GRACE for d in out.index], index=out.index
        )
        complete &= closes <= fetched_at
    return out[complete.reindex(out.index, fill_value=False)]


def load_hood_dumps(raw_dir: str) -> dict[str, pd.DataFrame]:
    """Load ``daily_*.json`` (+ optional ``intra_*.json``) dumps from a directory.

    A dump file's modification time is taken as the time it was fetched.
    """
    daily: dict[str, list[dict]] = defaultdict(list)
    intra: dict[str, list[dict]] = defaultdict(list)
    intra_fetched: dict[str, datetime] = {}
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        name = os.path.basename(path)
        kind = "daily" if name.startswith("daily_") else "intra" if name.startswith("intra_") else None
        if kind is None:
            continue
        with open(path) as fh:
            payload = json.load(fh)
        fetched = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
        for res in payload["data"]["results"]:
            bars = res.get("bars") or []
            if not bars:
                continue
            if kind == "daily":
                daily[res["symbol"]].extend(bars)
            else:
                intra[res["symbol"]].extend(bars)
                # Several dumps for one symbol: trust the earliest fetch.
                intra_fetched[res["symbol"]] = min(fetched, intra_fetched.get(res["symbol"], fetched))

    frames: dict[str, pd.DataFrame] = {}
    fills: dict[str, pd.DataFrame] = {}
    ratios = []
    for sym, bars in daily.items():
        try:
            df = _bars_to_frame(bars)
            if df.empty:
                continue
            df.index = df.pop("ts").dt.tz_localize(None).dt.normalize()
            df = df[~df.index.duplicated(keep="last")].sort_index()[COLUMNS].astype(float)
            frames[sym] = df
            if sym in intra:
                agg = _daily_from_intraday(_bars_to_frame(intra[sym]), intra_fetched[sym])
                # Half-hour bars carry only part of the consolidated volume:
                # measure the ratio on sessions that have both kinds of bar.
                both = agg.index.intersection(df.index)
                if len(both):
                    r = (df.loc[both, "volume"] / agg.loc[both, "volume"].clip(lower=1)).median()
                    if pd.notna(r) and r > 0:
                        ratios.append(r)
                else:
                    r = float("nan")
                extra = agg[agg.index > df.index[-1]]  # only sessions newer than the last daily bar
                if not extra.empty:
                    fills[sym] = extra.assign(ratio=r)
        except (KeyError, TypeError, ValueError) as exc:
            print(f"{sym}: skipped unreadable bars: {exc!r}", file=sys.stderr)

    market_ratio = float(pd.Series(ratios).median()) if ratios else float("nan")
    for sym, extra in fills.items():
        ratio = extra.pop("ratio").fillna(market_ratio)
        extra["volume"] = extra["volume"] * ratio
        df = pd.concat([frames[sym], extra]).sort_index()
        df.attrs["filled_sessions"] = [d.strftime("%Y-%m-%d") for d in extra.index]
        frames[sym] = df
    return frames


def _yf_frames(data: pd.DataFrame, yahoo: dict[str, str]) -> dict[str, pd.DataFrame]:
    """Split a ``yf.download(group_by="ticker")`` result into per-symbol frames."""
    out = {}
    if data is None or data.empty:
        return out
    for ysym, sym in yahoo.items():
        if isinstance(data.columns, pd.MultiIndex):
            if ysym not in data.columns.get_level_values(0):
                continue
            df = data[ysym]
        elif len(yahoo) == 1:
            df = data
        else:
            continue
        df = df.rename(columns=str.lower)
        if not set(COLUMNS) <= set(df.columns):
            continue
        # auto_adjust=False: OHLC are split-adjusted but not dividend-adjusted,
        # matching Robinhood's default bars.
        df = df[COLUMNS].dropna(subset=["open", "high", "low", "close"])
        if df.empty:
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        out[sym] = df.astype(float).fillna({"volume": 0.0})
    return out


def load_yfinance(symbols: list[str], days: int = 430, chunk: int = 200, retries: int = 3) -> dict[str, pd.DataFrame]:
    """Download daily bars from Yahoo Finance, retrying symbols that come back empty.

    yfinance reports per-ticker failures (including rate limiting) by returning
    empty columns, so missing symbols are retried in smaller, slower batches.
    """
    import yfinance as yf  # imported lazily: only the scheduled refresh needs it

    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    out: dict[str, pd.DataFrame] = {}
    todo = list(symbols)
    for attempt in range(retries + 1):
        size = chunk if attempt == 0 else max(20, chunk // (4 * attempt))
        for i in range(0, len(todo), size):
            part = todo[i : i + size]
            yahoo = {s.replace(".", "-"): s for s in part}  # BRK.B -> BRK-B
            try:
                data = yf.download(
                    list(yahoo),
                    start=start,
                    interval="1d",
                    auto_adjust=False,
                    actions=False,
                    group_by="ticker",
                    threads=attempt == 0,
                    progress=False,
                    multi_level_index=True,
                )
            except Exception as exc:  # network errors: retry this batch later
                print(f"yfinance batch failed: {exc!r}", file=sys.stderr)
                data = None
            out.update(_yf_frames(data, yahoo))
            if attempt:
                time.sleep(2 * attempt)
        todo = [s for s in symbols if s not in out]
        if not todo:
            break
        print(f"yfinance: {len(todo)} symbols missing after pass {attempt + 1}", file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    return out
