"""Score the rules on one dataset and period (PROTOCOL.md, "Measures", "The
random-timing test", "Choosing finalists").

    python3 -m crossover.run sp500 insample
    python3 -m crossover.run stocks_daily heldout

- **insample** reads nothing after the in-sample end.
- **heldout** reads everything and scores the held-out window.

Writes results/<dataset>_<period>.json and the daily curves
results/<dataset>_<period>_curves.csv.gz.
"""
import argparse, json, os, time
import multiprocessing as mp
import numpy as np
import pandas as pd

from lab import data as L, engine, metrics
from . import data as D, portfolio as P, signals as S

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = S.CONFIRMATORY + list(S.REFERENCE)       # X6 is exploratory, reported alongside
DRAWS = 1000
_G = {}


def build(dataset, period):
    """The panel, the SPY lab's returns (for SPY and sp500's engine) and the
    signal series of sp500."""
    start, is_end, ho = D.PERIODS[dataset]
    read_end = is_end if period == "insample" else None
    r, _, gspc = L.returns(end=read_end)
    if dataset == "sp500":
        g = gspc.to_numpy(float)
        # the lab calendar starts 1988-01-04; two earlier ^GSPC sessions give the
        # first bars their held exposure (h_i = s_{i-2}), as the engine does
        cal = gspc.index[gspc.index < r.index[0]][-2:].append(r.index)

        def source(name, rule):
            sig = pd.Series(S.signal(rule, g), index=gspc.index)
            return sig.reindex(sig.index.union(cal)).ffill().reindex(cal).to_numpy(float)
        rs = r["spy"].reindex(cal).fillna(0.0).to_numpy(float)
        assets = {"S&P 500": {"t": cal.to_numpy("datetime64[ns]"), "close": None,
                              "tr": np.cumprod(1 + rs), "liquid": np.ones(len(cal), bool)}}
        panel = P.Panel(assets, r["bil"].reindex(cal).fillna(0.0), source=source)
    else:
        hourly = dataset in ("stocks_1h", "stocks_4h")
        assets = D.DATASETS[dataset](end=read_end) if hourly else D.DATASETS[dataset]()
        if period == "insample":
            assets = D.truncate(assets, is_end)
        days = pd.DatetimeIndex(np.unique(np.concatenate([pd.DatetimeIndex(a["t"]).normalize().to_numpy() for a in assets.values()])))
        cash = L.cash_returns(days, end=read_end).fillna(0.0)
        panel = P.Panel(assets, cash, need_liquid=D.NEED_LIQUID.get(dataset, False))
    return panel, r, gspc


def windows(dataset, period):
    start, is_end, ho = D.PERIODS[dataset]
    if period == "insample":
        half = pd.Timestamp(D.HALF[dataset])
        return {"full": (start, is_end), "half1": (start, half - pd.Timedelta(minutes=1)), "half2": (half, is_end)}
    return {"full": (ho, None)}


def score(rule):
    panel, r, gspc, dataset, period = (_G[k] for k in ("panel", "r", "gspc", "dataset", "period"))
    daily = D.DAILY[dataset]
    H, W = panel.rule(rule)
    out = {"rule": rule, "name": {**S.RULES, **S.REFERENCE}[rule][0], "exploratory": rule not in S.CONFIRMATORY}
    curves = {}
    for wname, (lo, hi) in windows(dataset, period).items():
        j0, j1 = panel.window(H, lo, hi)
        idx = panel.daily_index(j0, j1)
        cash = panel.cash_day
        res = {}
        if dataset == "sp500":
            target = pd.Series(S.signal(rule, gspc.to_numpy(float)), index=gspc.index)
            first, last = idx[0], idx[-1]
            sim = engine.run(target, r, first, last)
            res["net"] = P.stats(sim["equity"], r["bil"])
            # double the switch costs only: the engine at 2x also doubles the opening
            # purchase, which scales every later value by the same factor
            eq2 = engine.run(target, r, first, last, cost=2 * engine.COST)["equity"]
            eq2.iloc[1:] *= (1 - engine.COST) / (1 - 2 * engine.COST)
            res["net_2x_cost"] = P.stats(eq2, r["bil"])
            res["benchmark"] = P.stats(engine.buy_and_hold(r, first, last, 1.0)["equity"], r["bil"])
            eq = sim["equity"]
            bench_eq = engine.buy_and_hold(r, first, last, 1.0)["equity"]
        else:
            eq = panel.equity(panel.bar_returns(H, W, j0, j1, "net", D.COST), j0, j1)
            res["net"] = P.stats(eq, cash)
            res["net_2x_cost"] = P.stats(panel.equity(panel.bar_returns(H, W, j0, j1, "net", 2 * D.COST), j0, j1), cash)
            bench_eq = panel.equity(panel.bar_returns(H, W, j0, j1, "hold"), j0, j1)
            res["benchmark"] = P.stats(bench_eq, cash)
        spy_eq = engine.buy_and_hold(r, idx[0], idx[-1], 1.0)["equity"]
        res["spy"] = P.stats(spy_eq, r["bil"])
        res["gross"] = P.stats(panel.equity(panel.bar_returns(H, W, j0, j1, "gross"), j0, j1), cash)
        res["bar"] = metrics.passes(res["net"], res["benchmark"])[1]
        res["passes_bar"] = all(res["bar"].values())
        res["bar_2x_cost"] = metrics.passes(res["net_2x_cost"], res["benchmark"])[1]
        res["passes_bar_2x_cost"] = all(res["bar_2x_cost"].values())
        res["vs_spy"] = metrics.passes(res["net"], res["spy"])[1]
        res["passes_vs_spy"] = all(res["vs_spy"].values())
        res.update(panel.exposure_stats(H, W, j0, j1))
        real, draws = panel.null_sharpes(H, j0, j1, D.BLOCK[daily], DRAWS, seed=P.seed_of(dataset, period, rule, wname))
        res["null"] = P.null_test(real, draws)
        # robustness, added after the independent review: the leak-free shift null
        if j1 - j0 + 1 >= 2 * P.SHIFT_MIN + 1:
            real_s, shifts = panel.shift_sharpes(H, j0, j1, seed=P.seed_of(dataset, period, rule, wname, "shift"))
            res["null_shift"] = P.null_test(real_s, shifts)
        else:
            res["null_shift"] = None          # window too short to shift past the averages' memory
        out[wname] = res
        if wname == "full":
            curves = {rule: eq, "benchmark": bench_eq, "SPY": spy_eq}
    return out, curves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=list(D.PERIODS))
    ap.add_argument("period", choices=["insample", "heldout"])
    a = ap.parse_args()
    t0 = time.time()
    panel, r, gspc = build(a.dataset, a.period)
    _G.update({"panel": panel, "r": r, "gspc": gspc, "dataset": a.dataset, "period": a.period})
    print(f"{a.dataset} {a.period}: {panel.A} assets, {panel.T} bars, {time.time() - t0:.0f}s", flush=True)
    with mp.get_context("fork").Pool(min(4, len(RULES))) as pool:
        parts = pool.map(score, RULES)
    res = {"dataset": a.dataset, "period": a.period, "periods": D.PERIODS[a.dataset], "cost_per_switch": D.COST,
           "null_block": D.BLOCK[D.DAILY[a.dataset]], "draws": DRAWS, "rules": {}}
    curves = {}
    for out, cv in parts:
        res["rules"][out["rule"]] = out
        curves.update(cv)
    os.makedirs(f"{HERE}/results", exist_ok=True)
    tag = f"{a.dataset}_{a.period}"
    json.dump(res, open(f"{HERE}/results/{tag}.json", "w"), indent=1, default=float)
    pd.DataFrame({k: v for k, v in curves.items()}).to_csv(f"{HERE}/results/{tag}_curves.csv.gz", float_format="%.6f")
    for rule, out in res["rules"].items():
        f = out["full"]
        n, b, s = f["net"], f["benchmark"], f["spy"]
        print(f"{rule} {out['name'][:28]:28} CAGR {n['cagr']:+.2%} (bench {b['cagr']:+.2%}, SPY {s['cagr']:+.2%})  "
              f"Sharpe {n['sharpe']:.2f} ({b['sharpe']:.2f})  DD {n['max_dd']:.1%} ({b['max_dd']:.1%})  "
              f"in mkt {f['time_in_market']:.0%}  sw/yr {f['switches_per_asset_year']:.1f}  "
              f"bar {'PASS' if f['passes_bar'] else 'fail'}  null edge {f['null']['edge']:+.3f} p {f['null']['p']:.3f}  "
              + (f"shift edge {f['null_shift']['edge']:+.3f} p {f['null_shift']['p']:.3f}" if f["null_shift"] else ""))
    print(f"done, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
