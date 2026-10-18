"""Exploratory runs (PROTOCOL.md, "Exploratory"): not tests, and labelled so.

    python3 -m crossover.explore

- X1 each rule at 2x on the S&P 500 (SSO when bullish);
- X2 long/short (-1 when bearish) on the S&P 500 and the ETFs;
- X3 the fast/slow grid on the S&P 500, and the best in-sample pairs held out;
- X4 the 1962-1987 stress test.

X5 (4-hour bars) is ``python3 -m crossover.run stocks_4h ...``; X6 (price
above its 200-bar average) is reported by ``run``.

Writes results/exploratory.json and results/exploratory.txt.
"""
import json, os
import numpy as np
import pandas as pd

from lab import data as L, engine, metrics
from . import data as D, portfolio as P, signals as S
from .run import build

HERE = os.path.dirname(os.path.abspath(__file__))
FAST = [5, 10, 20, 30, 50, 100]
SLOW = [20, 50, 100, 150, 200, 250, 300]
lines = []


def say(s):
    lines.append(s)
    print(s, flush=True)


def brief(s):
    return {k: s[k] for k in ("start", "end", "cagr", "sharpe", "max_dd", "vol", "worst_year", "worst_year_is")}


def fmt(s):
    return f"CAGR {s['cagr']:+.2%}  Sharpe {s['sharpe']:.2f}  max DD {s['max_dd']:.1%}"


def windows():
    start, is_end, ho = D.PERIODS["sp500"]
    return {"insample": (start, is_end), "heldout": (ho, D.END)}


def x1(r, gspc):
    say("X1: each rule at 2x on the S&P 500 (SSO when bullish), against SPY buy-and-hold")
    out = {}
    for wname, (a, b) in windows().items():
        spy = P.stats(engine.buy_and_hold(r, a, b, 1.0)["equity"], r["bil"])
        out[wname] = {"SPY": brief(spy)}
        say(f"  {wname}: SPY {fmt(spy)}")
        for rule in S.CONFIRMATORY + list(S.REFERENCE):
            t = 2 * pd.Series(S.signal(rule, gspc.to_numpy(float)), index=gspc.index)
            s = P.stats(engine.run(t, r, a, b)["equity"], r["bil"])
            ok = metrics.passes(s, spy)[0]
            out[wname][rule] = {**brief(s), "passes_vs_spy": ok}
            say(f"    {rule} 2x {fmt(s)}  {'beats SPY on all three' if ok else ''}")
    return out


def x2():
    say("X2: long/short (-1 when bearish, no borrowing fee), against buy-and-hold of the same assets")
    out = {}
    for ds in ("sp500", "etf_daily"):
        for period in ("insample", "heldout"):
            panel, r, gspc = build(ds, period)
            start, is_end, ho = D.PERIODS[ds]
            lo, hi = (start, is_end) if period == "insample" else (ho, None)
            key = f"{ds}_{period}"
            out[key] = {}
            for rule in S.CONFIRMATORY:
                H, W = panel.rule(rule, expo=lambda s: 2 * s - 1)
                j0, j1 = panel.window(H, lo, hi)
                s = P.stats(panel.equity(panel.bar_returns(H, W, j0, j1, "net", D.COST), j0, j1), panel.cash_day)
                b = P.stats(panel.equity(panel.bar_returns(H, W, j0, j1, "hold"), j0, j1), panel.cash_day)
                out[key][rule] = {**brief(s), "benchmark": brief(b), "passes_bar": metrics.passes(s, b)[0]}
                say(f"  {key} {rule} {fmt(s)}  (hold {fmt(b)})")
    return out


def x3(r_full, gspc_full):
    say("X3: fast/slow grid on the S&P 500 (1x), net of costs")
    start, is_end, ho = D.PERIODS["sp500"]
    r_in, _, g_in = L.returns(end=is_end)
    grid = []
    for kind in ("SMA", "EMA"):
        for f in FAST:
            for s in SLOW:
                if f >= s:
                    continue
                fn = S.pair(kind, f, s)
                row = {"kind": kind, "fast": f, "slow": s}
                for wname, (rr, gg, a, b) in {"insample": (r_in, g_in, start, is_end),
                                              "heldout": (r_full, gspc_full, ho, D.END)}.items():
                    t = pd.Series(S.signal(fn, gg.to_numpy(float)), index=gg.index)
                    st = P.stats(engine.run(t, rr, a, b)["equity"], rr["bil"])
                    row[wname] = {k: st[k] for k in ("cagr", "sharpe", "max_dd")}
                grid.append(row)
    spy = {w: P.stats(engine.buy_and_hold(rr, a, b, 1.0)["equity"], rr["bil"])
           for w, (rr, a, b) in {"insample": (r_in, start, is_end), "heldout": (r_full, ho, D.END)}.items()}
    best = {}
    for crit in ("cagr", "sharpe"):
        g = max(grid, key=lambda x: x["insample"][crit])
        best[crit] = g
        say(f"  best in-sample by {crit}: {g['kind']} {g['fast']}/{g['slow']}  in-sample CAGR {g['insample']['cagr']:+.2%} "
            f"Sharpe {g['insample']['sharpe']:.2f} DD {g['insample']['max_dd']:.1%} | held out CAGR {g['heldout']['cagr']:+.2%} "
            f"Sharpe {g['heldout']['sharpe']:.2f} DD {g['heldout']['max_dd']:.1%}")
    for w in ("insample", "heldout"):
        n = len(grid)
        beat = sum(1 for g in grid if metrics.passes(g[w], spy[w])[0])
        say(f"  {w}: SPY {fmt(spy[w])}; {beat} of {n} pairs beat it on all three; "
            f"{sum(1 for g in grid if g[w]['cagr'] > spy[w]['cagr'])} on CAGR")
    rank_in = np.argsort(np.argsort([-g["insample"]["sharpe"] for g in grid]))
    rank_ho = np.argsort(np.argsort([-g["heldout"]["sharpe"] for g in grid]))
    rho = float(np.corrcoef(rank_in, rank_ho)[0, 1])
    say(f"  rank correlation of in-sample and held-out Sharpe across the {len(grid)} pairs: {rho:+.2f}")
    return {"grid": grid, "spy": {w: brief(v) for w, v in spy.items()}, "best_insample": best, "rank_corr_sharpe": rho}


def x4(c):
    say("X4: stress test 1962-1987 (^GSPC plus a 3.6% yield; the 2x cost as in the SPY lab)")
    r, gspc = L.stress_returns(c)
    a, b = "1962-01-02", "1987-12-31"
    spy = P.stats(engine.buy_and_hold(r, a, b, 1.0)["equity"], r["bil"])
    out = {"hold": brief(spy)}
    say(f"  hold {fmt(spy)}")
    for rule in S.CONFIRMATORY + list(S.REFERENCE):
        for lev in (1, 2):
            t = lev * pd.Series(S.signal(rule, gspc.to_numpy(float)), index=gspc.index)
            sim = engine.run(t, r, a, b)
            s = P.stats(sim["equity"], r["bil"])
            crash = float(sim["equity"].pct_change().loc["1987-10-19"])
            out[f"{rule}_{lev}x"] = {**brief(s), "1987-10-19": crash, "passes_vs_hold": metrics.passes(s, spy)[0]}
            say(f"  {rule} {lev}x {fmt(s)}  1987-10-19 {crash:+.1%}")
    return out


def main():
    r, c, gspc = L.returns()
    res = {"X1_2x": x1(r, gspc), "X2_long_short": x2(), "X3_grid": x3(r, gspc), "X4_stress": x4(c)}
    json.dump(res, open(f"{HERE}/results/exploratory.json", "w"), indent=1, default=float)
    open(f"{HERE}/results/exploratory.txt", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
