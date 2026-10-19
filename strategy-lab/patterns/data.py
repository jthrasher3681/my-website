"""Bars for the triangle and support/resistance study (PROTOCOL.md, "Data and
periods"), one dict per symbol: {"t", "open", "high", "low", "close",
"volume", "liquid"}.

- ``daily``: the Elliott study's cache of the rectangle screener's Robinhood
  daily bars, with the screener's liquidity flag.
- ``weekly`` / ``monthly``: Yahoo bars from ``../data/yahoo_long`` (bar start
  dates), cleaned here, with this study's liquidity rule.
"""
import os
import numpy as np
import pandas as pd

from elliott import data as E

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG = os.path.join(LAB, "data", "yahoo_long")
FIRST_BAR = "1985-01-01"

# (in-sample start, in-sample end, held-out start, data end)
PERIODS = {
    "daily": ("2016-01-04", "2021-12-31", "2022-01-03", "2026-10-16"),
    "weekly": ("1990-01-01", "2011-12-31", "2012-01-01", "2026-10-16"),
    "monthly": ("1990-01-01", "2011-12-31", "2012-01-01", "2026-09-30"),
}
HALF = {"daily": "2019-01-01", "weekly": "2001-01-01", "monthly": "2001-01-01"}
K = {"daily": 5, "weekly": 3, "monthly": 2}                  # pivot length
DUR = {"daily": (15, 250), "weekly": (8, 156), "monthly": (8, 120)}
N_TIME = {"daily": 63, "weekly": 26, "monthly": 12}
CLUSTER = {"daily": "Q", "weekly": "Y", "monthly": "Y"}
LIQ = {"weekly": (26, 25e6), "monthly": (12, 100e6)}           # bars, median dollar volume
COST = 0.0005


def daily(end=None):
    d = E.stocks_daily()
    return truncate(d, end) if end is not None else d


def clean(df):
    """PROTOCOL.md, "Yahoo bars": drop early, missing and one-bar-spike bars; widen
    high and low to contain the open and close."""
    df = df[df.index >= pd.Timestamp(FIRST_BAR)]
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & df[["open", "high", "low", "close"]].notna().all(axis=1)]
    c = np.log(df["close"].to_numpy(float))
    if len(c) >= 3:
        spike = np.zeros(len(c), bool)
        spike[1:-1] = (np.abs(c[1:-1] - c[:-2]) > np.log(2.5)) & (np.abs(c[2:] - c[:-2]) < np.log(1.25))
        df = df[~spike]
    df = df.copy()
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return df


def liquid(close, volume, n, floor):
    """Median close x volume over the last n bars (this one included) >= floor."""
    dv = pd.Series(close * volume)
    return (dv.rolling(n, min_periods=n).median() >= floor).to_numpy()


def _long(name, end=None):
    """``end``: cut every series there before cleaning, so an in-sample run reads
    nothing after it (the spike rule looks one bar ahead)."""
    z = np.load(os.path.join(LONG, f"{name}.npz"))
    syms, st = z["symbols"], z["start"]
    n, floor = LIQ[name]
    out = {}
    for i, s in enumerate(syms):
        a, b = st[i], st[i + 1]
        df = pd.DataFrame({k: z[k][a:b].astype(float) for k in ("open", "high", "low", "close", "volume")},
                          index=pd.to_datetime(z["t"][a:b].astype("int64"), unit="D"))
        if end is not None:
            df = df[df.index <= pd.Timestamp(end)]
        df = clean(df)
        if len(df) < 30:
            continue
        out[str(s)] = {"t": df.index.to_numpy(dtype="datetime64[ns]"),
                       **{k: df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume")},
                       "liquid": liquid(df["close"].to_numpy(), df["volume"].to_numpy(), n, floor)}
    return out


def weekly(end=None):
    return _long("weekly", end)


def monthly(end=None):
    return _long("monthly", end)


DATASETS = {"daily": daily, "weekly": weekly, "monthly": monthly}


def truncate(data, end):
    """Every series cut after ``end``: what an in-sample run may read."""
    end = np.datetime64(pd.Timestamp(end))
    out = {}
    for s, d in data.items():
        k = int(np.searchsorted(d["t"], end, side="right"))
        if k >= 30:
            out[s] = {key: (v[:k] if isinstance(v, np.ndarray) else v) for key, v in d.items()}
    return out
