"""Bar series for the Elliott Wave study, one dict per symbol:
{"t": bar start times, "open", "high", "low", "close", "volume", "liquid"}.

The datasets:

- ``stocks_daily``: the rectangle screener's universe, 2016-2026 Robinhood
  daily bars, cleaned as in its backtest, cached by
  ``cache_daily.py`` (a pickle outside the repository, see ``DAILY_CACHE``).
  ``liquid`` is the screener's rule: median dollar volume over the last 50
  sessions of at least $20M.
- ``etf_daily``: the 30 ETFs in ``../data/yahoo`` with open/high/low/close,
  their whole Yahoo history. Split-adjusted, not dividend-adjusted.
- ``stocks_1h``: ``../data/yahoo_1h``, Yahoo's last 730 days of hourly
  regular-session bars (9:30, 10:30 .. 15:30; the last one is 30 minutes).
- ``stocks_4h``: the same hours in two bars a day, 9:30-13:30 and 13:30-16:00.
"""
import glob, os, pickle
import numpy as np
import pandas as pd

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_CACHE = os.environ.get("ELLIOTT_DAILY_CACHE",
                             "/tmp/claude-0/-home-user-my-website/7e6193d5-03fd-55b8-ab0d-60cef84cba96/scratchpad/elliott/daily_stocks.pkl")
ETFS = ["SPY", "QQQ", "IWM", "MDY", "DIA", "VTI", "EFA", "EEM", "VNQ", "GLD", "DBC", "XLB", "XLE", "XLF", "XLI",
        "XLK", "XLP", "XLU", "XLV", "XLY", "SHY", "IEF", "TLT", "AGG", "LQD", "TIP"]


def _frame(df):
    d = {"t": df.index.to_numpy(dtype="datetime64[ns]")}
    for k in ("open", "high", "low", "close", "volume"):
        d[k] = df[k].to_numpy(float)
    return d


def stocks_daily():
    raw = pickle.load(open(DAILY_CACHE, "rb"))
    return {s: {"t": v["dates"].astype("datetime64[ns]"), **{k: v[k] for k in ("open", "high", "low", "close", "volume")},
                "liquid": v["liquid"]} for s, v in raw.items()}


def etf_daily():
    out = {}
    for s in ETFS:
        df = pd.read_csv(os.path.join(LAB, "data", "yahoo", f"{s}.csv.gz"), index_col=0, parse_dates=True)
        df = df[(df["open"] > 0) & (df["high"] >= df["low"])]
        d = _frame(df)
        d["liquid"] = np.ones(len(df), bool)
        out[s] = d
    return out


def _hourly_frames():
    for f in sorted(glob.glob(os.path.join(LAB, "data", "yahoo_1h", "*.csv.gz"))):
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        df = df[(df["open"] > 0) & (df["high"] >= df["low"]) & (df["volume"] >= 0)]
        df = df[(df.index.time >= pd.Timestamp("09:30").time()) & (df.index.time < pd.Timestamp("16:00").time())]
        yield os.path.basename(f)[:-7], df


def stocks_1h():
    out = {}
    for s, df in _hourly_frames():
        d = _frame(df)
        d["liquid"] = np.ones(len(df), bool)
        out[s] = d
    return out


def to_4h(df):
    """Two bars a day: the hours starting 9:30-12:30 and 13:30-15:30."""
    half = np.where(df.index.time < pd.Timestamp("13:30").time(), "09:30", "13:30")
    key = pd.to_datetime(df.index.strftime("%Y-%m-%d ") + half)
    g = df.groupby(key)
    return pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                         "close": g["close"].last(), "volume": g["volume"].sum()})


def stocks_4h():
    out = {}
    for s, df in _hourly_frames():
        d = _frame(to_4h(df))
        d["liquid"] = np.ones(len(d["t"]), bool)
        out[s] = d
    return out


DATASETS = {"stocks_daily": stocks_daily, "etf_daily": etf_daily, "stocks_4h": stocks_4h, "stocks_1h": stocks_1h}
