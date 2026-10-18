"""Assets for the crossover study (PROTOCOL.md, "Data and periods"), one dict
per asset: {"t": bar times, "close": the price signals use, "tr": the index
returns use, "liquid": whether the asset passes the liquidity rule}.

- ``stocks_daily``: the Elliott study's cache of the screener universe's
  Robinhood daily bars. Price only, so ``tr`` is the close.
- ``etf_daily``: the 26 ETFs in ``../data/yahoo``. ``close`` is the
  split-adjusted close and ``tr`` adds the cash dividends (``lab.data.growth``).
- ``stocks_1h`` / ``stocks_4h``: the Elliott study's hourly symbols.

``sp500`` is not here: it runs on the SPY lab's own series (``lab.data.returns``).
"""
import numpy as np
import pandas as pd

from lab import data as L
from elliott import data as E

END = "2026-10-16"
COST = 0.0010                     # a switch, all datasets
DAILY = {"sp500": True, "stocks_daily": True, "etf_daily": True, "stocks_1h": False, "stocks_4h": False}
BLOCK = {True: 63, False: 70}     # null blocks, daily / hourly bars
NEED_LIQUID = {"stocks_daily": True}

# (in-sample start, in-sample end, held-out start); every held-out period ends at END
PERIODS = {
    "sp500": ("1988-01-05", "2015-12-31", "2016-01-04"),
    "stocks_daily": ("2016-01-04", "2021-12-31", "2022-01-03"),
    "etf_daily": ("1993-01-29", "2015-12-31", "2016-01-04"),
    "stocks_1h": ("2023-11-17", "2025-09-30 23:59", "2025-10-01"),
    "stocks_4h": ("2023-11-17", "2025-09-30 23:59", "2025-10-01"),
}
HALF = {"sp500": "2002-01-01", "stocks_daily": "2019-07-01", "etf_daily": "2005-01-01",
        "stocks_1h": "2024-11-01", "stocks_4h": "2024-11-01"}


def _from_elliott(raw):
    return {s: {"t": d["t"], "close": d["close"], "tr": d["close"], "liquid": d["liquid"]} for s, d in raw.items()}


def stocks_daily():
    return _from_elliott(E.stocks_daily())


def stocks_1h():
    return _from_elliott(E.stocks_1h())


def stocks_4h():
    return _from_elliott(E.stocks_4h())


def etf_daily():
    out = {}
    for s in E.ETFS:
        df = L.load(s)
        df = df[df["close"] > 0]
        out[s] = {"t": df.index.to_numpy(dtype="datetime64[ns]"), "close": df["close"].to_numpy(float),
                  "tr": L.growth(df).to_numpy(float), "liquid": np.ones(len(df), bool)}
    return out


DATASETS = {"stocks_daily": stocks_daily, "etf_daily": etf_daily, "stocks_1h": stocks_1h, "stocks_4h": stocks_4h}


def truncate(assets, end):
    """Every series cut after ``end``: what an in-sample run may read."""
    end = np.datetime64(pd.Timestamp(end))
    out = {}
    for s, d in assets.items():
        k = int(np.searchsorted(d["t"], end, side="right"))
        if k > 0:
            out[s] = {key: v[:k] for key, v in d.items()}
    return out
