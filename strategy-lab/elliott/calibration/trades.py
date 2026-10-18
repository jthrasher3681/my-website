"""Calibrate the setup scoring on random walks, where no setup can have an edge:
each setup's mean edge over its twins should be about 0.

    cd strategy-lab && python3 -m elliott.calibration.trades [symbols]
"""
import sys
import numpy as np, pandas as pd

from elliott import execute as X, setups, waves
from elliott.calibration.walks import path_walk
from elliott.tests.test_setups import bars_from


def main(n_sym=300):
    data = {f"R{s}": bars_from(*path_walk(2700, 1000 + s)) for s in range(n_sym)}
    trades = []
    for s, b in data.items():
        piv = waves.pivots(b["high"], b["low"], b["close"], 2.0, b["atr"])
        trades += X.run_symbol(s, b, setups.orders(b, piv), 0.0, False)
    tw = X.twins(trades, data, X.twin_pool(data, False), 0.0, sig_pool=X.twin_pool(data, False, lag=0))
    df = pd.DataFrame(trades)
    df["twin"] = tw
    df = df[df.twin.notna()]
    df["edge"] = df.R - df.twin
    rows = []
    for (s, d), x in df.groupby(["setup", "d"]):
        bs = X.cluster_bootstrap(x.edge, x.symbol, draws=2000)
        rows.append({"setup": s, "d": d, "n": len(x), "R": x.R.mean(), "twin": x.twin.mean(), "edge": bs["mean"],
                     "lo": bs["lo"], "hi": bs["hi"]})
    print(pd.DataFrame(rows).round(3).to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
