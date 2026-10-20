"""The account test (PROTOCOL.md, "Held-out test"; X10 for every setup).

The Elliott study's account (``elliott.portfolio.run``): $100,000, 0.5% of
equity risked per trade, at most 10% of equity in one position, gross
exposure at most 100%, simultaneous entries in random order, the median of 10
orders. Equity is marked at every bar close. Weekly and monthly bars are dated
by their start, so a mark is placed at the last day before the next bar
starts.

SPY with dividends (``../data/yahoo/SPY.csv.gz``) is read at the same marks.
Sharpe is the mark-to-mark excess over BIL (13-week bills before BIL),
annualized by the square root of the marks per year.

    python3 -m patterns.portfolio <dataset> <setup> [heldout|insample]
"""
import json, os, pickle, sys
import numpy as np
import pandas as pd

from elliott import execute as X
from elliott.portfolio import run as account
from lab import data as L
from . import data as D, detect
from .run import OUT

HERE = os.path.dirname(os.path.abspath(__file__))
PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12}


def marks(eq, dataset, next_start):
    """Equity indexed by bar start -> indexed by the last day of each bar."""
    if dataset == "daily":
        return eq
    idx = eq.index
    ends = [next_start.get(t, t + pd.Timedelta(days=6 if dataset == "weekly" else 27)) - pd.Timedelta(days=1) for t in idx]
    return pd.Series(eq.to_numpy(), index=pd.DatetimeIndex(ends))


def stats(eq, cash_tr, per_year):
    r = eq.pct_change().dropna()
    c = cash_tr.reindex(cash_tr.index.union(eq.index)).ffill().reindex(eq.index).pct_change().dropna()
    ex = r - c.reindex(r.index).fillna(0)
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return {"cagr": float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1), "sharpe": float(ex.mean() / ex.std() * np.sqrt(per_year)),
            "max_dd": float((eq / eq.cummax() - 1).min()), "end": float(eq.iloc[-1] / eq.iloc[0])}


def test(dataset, setup, period="heldout", seeds=10):
    trades = pickle.load(open(f"{OUT}/{dataset}_{period}_trades.pkl", "rb"))
    tr = [t for t in trades if t["setup"] == setup]
    if not tr:
        return None
    start, is_end, ho, end = D.PERIODS[dataset]
    bars = D.DATASETS[dataset](end=is_end if period == "insample" else None)
    for b in bars.values():
        X.prepare(b)
    first = pd.Timestamp(ho if period == "heldout" else start)
    runs = [account(tr, bars, D.COST, seed, first) for seed in range(seeds)]
    alltimes = pd.DatetimeIndex(np.unique(np.concatenate([b["t"] for b in bars.values()])))
    nxt = {alltimes[i]: alltimes[i + 1] for i in range(len(alltimes) - 1)}
    runs = [marks(r, dataset, nxt) for r in runs]
    cal = L.calendar()
    spy = L.growth(L.load("SPY")).reindex(cal).ffill()
    cash = (1 + L.cash_returns(cal).fillna(0)).cumprod()
    pyr = PER_YEAR[dataset]
    res = [stats(r, cash, pyr) for r in runs]
    s0, s1 = runs[0].index[0], runs[0].index[-1]
    spy_m = spy.reindex(spy.index.union(runs[0].index)).ffill().reindex(runs[0].index)
    bench = stats(spy_m / spy_m.iloc[0], cash, pyr)
    med = {k: float(np.median([r[k] for r in res])) for k in res[0]}
    ok = med["cagr"] > bench["cagr"] and med["sharpe"] >= bench["sharpe"] and med["max_dd"] >= bench["max_dd"]
    return {"dataset": dataset, "setup": setup, "period": period, "start": str(s0.date()), "end": str(s1.date()),
            "trades": len(tr), "median": med, "runs": res, "spy": bench, "passes": bool(ok)}


def main(dataset, setup, period="heldout"):
    out = test(dataset, setup, period)
    os.makedirs(f"{HERE}/results", exist_ok=True)
    json.dump(out, open(f"{HERE}/results/account_{dataset}_{setup}_{period}.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "runs"}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
