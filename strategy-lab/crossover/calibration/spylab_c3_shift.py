"""Leak-free check of the SPY lab's random-timing percentile for C3 held out
(the crossover review's finding applies to ../run_heldout.py too).

    cd strategy-lab && python3 crossover/calibration/spylab_c3_shift.py
"""
import sys
sys.path.insert(0, "/home/user/my-website/strategy-lab")
import numpy as np, pandas as pd
from lab import data, engine, metrics, strategies
from run_insample import random_timing
r, c, gspc = data.returns()
cash = r["bil"]
rule = strategies.CANDIDATES["C3"][1]
full = engine.run(rule(gspc), r, "1988-01-05", "2026-10-16")
w = metrics.window(full, "2016-01-04", "2026-10-16")
s = metrics.stats(w, cash)
held = w["exposure"].iloc[1:].to_numpy()
days = w.index
T = len(held)
out = []
for k in range(260, T - 260 + 1, 2):
    t = pd.Series(np.roll(held, -k), index=days[:-1])
    st = metrics.stats(engine.run(t, r, days[1], days[-1], lag=0, band=0.0), cash)
    out.append((st["cagr"], st["sharpe"]))
out = np.array(out)
print("C3 held out CAGR", round(s["cagr"], 4), "Sharpe", round(s["sharpe"], 3), "shifts", len(out))
print("shift null: CAGR percentile", round((out[:, 0] < s["cagr"]).mean() * 100, 1), "median", round(np.median(out[:, 0]), 4),
      "| Sharpe percentile", round((out[:, 1] < s["sharpe"]).mean() * 100, 1), "median", round(np.median(out[:, 1]), 3))
