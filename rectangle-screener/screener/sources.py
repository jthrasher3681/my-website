"""Daily OHLCV loaders for the rectangle screener.

Every loader returns ``{symbol: DataFrame}`` where each frame has a
DatetimeIndex of trading days (ascending, tz-naive) and float columns
``open, high, low, close, volume``. The last row is the most recent
completed session.

Two sources are supported:

* ``load_hood_dumps`` - JSON files saved from Robinhood's
  ``get_equity_historicals`` tool (daily bars, optionally plus 30-minute
  bars used to fill in a session whose daily bar is not published yet).
* ``load_yfinance`` - Yahoo Finance via the ``yfinance`` package, for
  unattended refreshes (GitHub Actions).
"""

from __future__ import annotations

import glob
import json
import os
from collections import defaultdict

import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]

# A regular session runs 13:30-20:00 UTC (EDT) / 14:30-21:00 UTC (EST): 13
# half-hour bars. Accept a slightly short day (half-day sessions excluded).
MIN_INTRADAY_BARS = 12


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
        if not b.get("interpolated")
    ]
    df = pd.DataFrame(rows, columns=["ts"] + COLUMNS)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def _daily_from_intraday(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate half-hour bars into one bar per complete session."""
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    df = df.sort_values("ts")
    day = df["ts"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
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
    return out[g.size() >= MIN_INTRADAY_BARS]


def load_hood_dumps(raw_dir: str) -> dict[str, pd.DataFrame]:
    """Load ``daily_*.json`` (+ optional ``intra_*.json``) dumps from a directory."""
    daily: dict[str, list[dict]] = defaultdict(list)
    intra: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        name = os.path.basename(path)
        target = daily if name.startswith("daily_") else intra if name.startswith("intra_") else None
        if target is None:
            continue
        with open(path) as fh:
            payload = json.load(fh)
        for res in payload["data"]["results"]:
            target[res["symbol"]].extend(res.get("bars") or [])

    out: dict[str, pd.DataFrame] = {}
    for sym, bars in daily.items():
        df = _bars_to_frame(bars)
        if df.empty:
            continue
        df.index = df.pop("ts").dt.tz_localize(None).dt.normalize()
        df = df[~df.index.duplicated(keep="last")].sort_index()
        if sym in intra:
            agg = _daily_from_intraday(_bars_to_frame(intra[sym]))
            # Half-hour bars carry only part of the consolidated volume, so scale
            # by the ratio seen on sessions that have both kinds of bar.
            both = agg.index.intersection(df.index)
            ratio = (df.loc[both, "volume"] / agg.loc[both, "volume"].clip(lower=1)).median() if len(both) else float("nan")
            # Only fill sessions newer than the last published daily bar.
            extra = agg[agg.index > df.index[-1]].copy()
            if not extra.empty:
                extra["volume"] = extra["volume"] * ratio
                df = pd.concat([df, extra]).sort_index()
        out[sym] = df[COLUMNS].astype(float)
    return out


def load_yfinance(symbols: list[str], period: str = "14mo", chunk: int = 200) -> dict[str, pd.DataFrame]:
    """Download split-adjusted daily bars from Yahoo Finance."""
    import yfinance as yf  # imported lazily: only the scheduled refresh needs it

    out: dict[str, pd.DataFrame] = {}
    for i in range(0, len(symbols), chunk):
        part = symbols[i : i + chunk]
        yahoo = {s.replace(".", "-"): s for s in part}  # BRK.B -> BRK-B
        data = yf.download(
            list(yahoo),
            period=period,
            interval="1d",
            auto_adjust=False,
            actions=False,
            group_by="ticker",
            threads=True,
            progress=False,
        )
        if data is None or data.empty:
            continue
        for ysym, sym in yahoo.items():
            if isinstance(data.columns, pd.MultiIndex):
                if ysym not in data.columns.get_level_values(0):
                    continue
                df = data[ysym]
            else:
                df = data
            df = df.rename(columns=str.lower)
            if not set(COLUMNS) <= set(df.columns):
                continue
            # Split-adjust OHLC the same way Robinhood does (no dividend adjustment):
            # yfinance's unadjusted prices are already split-adjusted.
            df = df[COLUMNS].dropna(subset=["open", "high", "low", "close"])
            if df.empty:
                continue
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            out[sym] = df.astype(float)
    return out
