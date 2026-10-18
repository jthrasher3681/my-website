"""The portfolio test for a finalist that passes the held-out test (PROTOCOL.md,
"Is it a system?").

- **Account.** $100,000; each trade risks 0.5% of equity between entry and
  stop, capped at 10% of equity, with gross exposure capped at 100%.
- **Shorts** are funded in cash, with no borrow fee.
- **Costs** are the dataset's, per side.
- **Simultaneous signals.** Entries at the same bar time are taken in a
  random order, ten orders in all, and the median run is used.
- **Equity** is marked at every bar close and scored on daily closes
  against SPY with dividends; Sharpe is daily excess over BIL x sqrt(252).

    python3 -m elliott.portfolio <dataset> <setup> <long|short>
"""
import json, os, pickle, sys
import numpy as np
import pandas as pd

from . import data as D
from .run import OUT

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
START_CASH, RISK, CAP, GROSS = 100_000.0, 0.005, 0.10, 1.0


def _tr(sym):
    df = pd.read_csv(os.path.join(LAB, "data", "yahoo", f"{sym}.csv.gz"), index_col=0, parse_dates=True)
    return ((df["close"] + df["dividends"]) / df["close"].shift(1)).fillna(1).cumprod()


def stats(eq, cash_r):
    r = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    ex = r - cash_r.reindex(r.index).fillna(0)
    return {"cagr": float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1), "sharpe": float(ex.mean() / ex.std() * np.sqrt(252)),
            "max_dd": float((eq / eq.cummax() - 1).min()), "end": float(eq.iloc[-1] / eq.iloc[0])}


def run(trades, bars, cost, seed, start):
    rng = np.random.default_rng(seed)
    times = np.unique(np.concatenate([bars[s]["tk"] for s in {t["symbol"] for t in trades}]))
    times = times[times >= int(np.datetime64(start, "ns").astype("int64"))]
    ix = {int(t): i for i, t in enumerate(times)}
    entries, exits = {}, {}
    for k, t in enumerate(trades):
        b = bars[t["symbol"]]
        entries.setdefault(ix[int(b["tk"][t["entry"]])], []).append(k)
        exits.setdefault(ix[int(b["tk"][t["exit"]])], []).append(k)
    cash, open_, eq = START_CASH, {}, np.empty(len(times))
    last_px = {}
    for i, T in enumerate(times):
        for k in rng.permutation(entries.get(i, [])):
            t = trades[k]
            equity = cash + sum(p["sh"] * t2["d"] * (last_px.get(t2["symbol"], t2["entry_px"]) - t2["entry_px"])
                                for k2, p in open_.items() for t2 in [trades[k2]])
            gross = sum(abs(p["sh"]) * last_px.get(trades[k2]["symbol"], trades[k2]["entry_px"]) for k2, p in open_.items())
            risk_frac = abs(t["entry_px"] - t["stop"]) / t["entry_px"]
            value = min(equity * RISK / risk_frac, equity * CAP)
            if gross + value > GROSS * equity or value <= 0:
                continue
            open_[k] = {"sh": value / t["entry_px"]}
            cash -= value * cost
        for k in exits.get(i, []):
            if k in open_:
                t = trades[k]
                sh = open_.pop(k)["sh"]
                cash += sh * t["d"] * (t["exit_px"] - t["entry_px"]) - sh * t["exit_px"] * cost
        for k, p in open_.items():
            t = trades[k]
            b = bars[t["symbol"]]
            j = b["pos"].get(int(T))
            if j is not None:
                last_px[t["symbol"]] = b["close"][j]
        eq[i] = cash + sum(p["sh"] * trades[k]["d"] * (last_px.get(trades[k]["symbol"], trades[k]["entry_px"]) - trades[k]["entry_px"])
                           for k, p in open_.items())
    s = pd.Series(eq, index=pd.to_datetime(times))
    return s.groupby(s.index.normalize()).last()


def main(dataset, setup, direction):
    trades = pickle.load(open(f"{OUT}/{dataset}_heldout_k2_trades.pkl", "rb"))
    d = 1 if direction == "long" else -1
    tr = [t for t in trades if t["setup"] == setup and t["d"] == d]
    bars = D.DATASETS[dataset]()
    from . import execute as X
    for b in bars.values():
        X.prepare(b)
    spy, bil = _tr("SPY"), _tr("BIL")
    start = pd.Timestamp(D.PERIODS[dataset][2])
    runs = [run(tr, bars, D.COST[dataset], seed, start) for seed in range(10)]
    start = min(r.index[0] for r in runs)
    end = max(r.index[-1] for r in runs)
    cash_r = bil.pct_change()
    res = [stats(r, cash_r) for r in runs]
    spy_w = spy.loc[start:end]
    bench = stats(spy_w / spy_w.iloc[0], cash_r)
    med = {k: float(np.median([r[k] for r in res])) for k in res[0]}
    ok = med["cagr"] > bench["cagr"] and med["sharpe"] >= bench["sharpe"] and med["max_dd"] >= bench["max_dd"]
    out = {"dataset": dataset, "setup": setup, "direction": direction, "median": med, "runs": res, "spy": bench, "passes": ok}
    json.dump(out, open(f"{HERE}/results/portfolio_{dataset}_{setup}_{direction}.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
