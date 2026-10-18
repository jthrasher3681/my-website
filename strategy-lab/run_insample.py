"""In-sample evaluation and the choice of finalist (PROTOCOL.md, "Choosing the
finalist"), plus the 1962-87 stress test. Nothing after 2015-12-31 is read.

    python3 run_insample.py

Writes results/insample.json and results/insample_curves.csv.gz.
"""
import json, os, sys
import numpy as np
import pandas as pd

from lab import data, engine, metrics, strategies

HERE = os.path.dirname(os.path.abspath(__file__))
START, END = "1988-01-05", "2015-12-31"       # first session with a total-return index return
DECADES = (("1988-01-05", "1997-12-31"), ("1998-01-02", "2007-12-31"), ("2008-01-02", "2015-12-31"))
OPEN_WINDOW = ("2006-07-03", "2015-12-31")
STRESS = ("1962-01-02", "1987-12-31")
NULL_DRAWS, NULL_BLOCK = 1000, 63


def rounded(x):
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rounded(v) for v in x]
    if isinstance(x, float):
        return round(x, 5)
    return x


def line(name, s, bench=None):
    flag = ""
    if bench is not None:
        ok, chk = metrics.passes(s, bench)
        flag = "PASS" if ok else "fail " + ",".join(k for k, v in chk.items() if not v)
    return (f"{name:44} CAGR {s['cagr'] * 100:6.2f}%  Sharpe {s['sharpe']:5.2f}  maxDD {s['max_dd'] * 100:6.1f}%  "
            f"vol {s['vol'] * 100:5.1f}%  worst yr {s['worst_year'] * 100:6.1f}% ({s['worst_year_is']})  "
            f"expo {s['avg_exposure']:.2f}  trades/yr {s['trades_per_year']:5.1f}  {flag}")


def random_timing(sim, r, cash, draws=NULL_DRAWS, block=NULL_BLOCK, seed=0):
    """CAGR and Sharpe of the run's own held exposures, shuffled in blocks."""
    held = sim["exposure"].iloc[1:].to_numpy()
    days = sim.index
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(draws):
        t = pd.Series(metrics.block_shuffle(held, block, rng), index=days[:-1])
        s = metrics.stats(engine.run(t, r, days[1], days[-1], lag=0, band=0.0), cash)
        out.append((s["cagr"], s["sharpe"]))
    return np.array(out)


def main():
    r, c, gspc = data.returns(end=END)
    cash = r["bil"]
    sso_real = data.on_calendar(data.growth(data.load("SSO", END)), r.index)
    a, b = data.CALIBRATION
    sim2x = data.simulated_2x(r["spy"], r["bil"], c).loc[a:b]
    te = float((sim2x - sso_real.loc[a:b]).std() * np.sqrt(252))
    monthly = lambda x: (1 + x).groupby(x.index.to_period("M")).prod() - 1
    te_m = float((monthly(sim2x) - monthly(sso_real.loc[a:b])).std() * np.sqrt(12))
    print(f"2x simulation: c = {c * 100:.3f}% a year; tracking error vs SSO {a}..{b} {te * 100:.2f}% a year daily, "
          f"{te_m * 100:.2f}% on monthly returns (SPY's closing prints were 4:15pm until 2008)")

    out = {"period": [START, END], "c_2x": c, "tracking_error_2006_2015": {"daily": te, "monthly": te_m},
           "candidates": {}, "references": {}}
    curves = {}
    spy = engine.buy_and_hold(r, START, END, 1.0)
    bench = metrics.stats(spy, cash)
    out["references"]["SPY buy-and-hold"] = bench
    curves["SPY"] = spy["equity"]
    print(line("SPY buy-and-hold", bench))
    for lev, name in ((2.0, "SSO buy-and-hold (2x)"), (1.5, "1.5x constant")):
        s = metrics.stats(engine.buy_and_hold(r, START, END, lev), cash)
        out["references"][name] = s
        print(line(name, s, bench))

    sims = {}
    for cid, (name, rule) in strategies.CANDIDATES.items():
        sim = engine.run(rule(gspc), r, START, END)
        s = metrics.stats(sim, cash)
        ok, chk = metrics.passes(s, bench)
        out["candidates"][cid] = {"name": name, **s, "passes": ok, "checks": chk}
        sims[cid] = sim
        curves[cid] = sim["equity"]
        print(line(f"{cid} {name}", s, bench))

    passers = [k for k, v in out["candidates"].items() if v["passes"]]
    if not passers:
        out["finalist"] = None
        print("No candidate passes in-sample: the lab stops here (PROTOCOL.md).")
    else:
        fin = max(passers, key=lambda k: out["candidates"][k]["cagr"])
        out["finalist"] = fin
        name, rule = strategies.CANDIDATES[fin]
        print(f"\nFinalist: {fin} {name}\n\nRobustness (in-sample, warnings only):")
        rob = {}
        for vname, vrule in strategies.VARIANTS[fin].items():
            s = metrics.stats(engine.run(vrule(gspc), r, START, END), cash)
            rob[f"parameter: {vname}"] = s
            print(line(f"  {vname}", s, bench))
        s = metrics.stats(engine.run(rule(gspc), r, START, END, lag=0), cash)
        rob["traded at the signal close"] = s
        print(line("  traded at the signal close", s, bench))
        s = metrics.stats(engine.run(rule(gspc), r, START, END, cost=0.001), cash)
        rob["costs 0.10% a side"] = s
        print(line("  costs 0.10% a side", s, bench))
        on, intra = data.open_returns(*OPEN_WINDOW)
        o0, o1 = on.index[1], OPEN_WINDOW[1]
        s_open = metrics.stats(engine.run(rule(gspc), r, o0, o1, at_open=(on, intra)), cash)
        s_close = metrics.stats(metrics.window(sims[fin], o0, o1), cash)
        s_spy = metrics.stats(metrics.window(spy, o0, o1), cash)
        # BIL's opens start 2007-05-30, so the window starts there rather than in 2006-07
        rob[f"next open, {o0:%Y-%m} to 2015"] = {"next_open": s_open, "next_close": s_close, "spy": s_spy}
        print(line(f"  {o0.date()}.. next open", s_open, s_spy))
        print(line(f"  {o0.date()}.. next close (base)", s_close, s_spy))
        print(line(f"  {o0.date()}.. SPY", s_spy))
        dec = {}
        for d0, d1 in DECADES:
            s, sb = metrics.stats(metrics.window(sims[fin], d0, d1), cash), metrics.stats(metrics.window(spy, d0, d1), cash)
            dec[f"{d0[:4]}-{d1[:4]}"] = {"finalist": s, "spy": sb}
            print(line(f"  {d0[:4]}-{d1[:4]} finalist", s, sb))
            print(line(f"  {d0[:4]}-{d1[:4]} SPY", sb))
        rob["decades"] = dec
        out["robustness"] = rob
        null = random_timing(sims[fin], r, cash)
        fs = out["candidates"][fin]
        out["random_timing"] = {"draws": NULL_DRAWS, "block": NULL_BLOCK,
                                "cagr_percentile": float((null[:, 0] < fs["cagr"]).mean() * 100),
                                "sharpe_percentile": float((null[:, 1] < fs["sharpe"]).mean() * 100),
                                "cagr_null_median": float(np.median(null[:, 0])), "sharpe_null_median": float(np.median(null[:, 1]))}
        print("\nRandom timing (same exposures, 63-session blocks shuffled):", rounded(out["random_timing"]))

    # stress test, 1962-87 (reported only)
    rs, gs = data.stress_returns(c, *STRESS)
    st = {}
    sb = metrics.stats(engine.buy_and_hold(rs, *STRESS), rs["bil"])
    st["S&P 1x"] = sb
    print("\nStress test 1962-1987 (S&P price + 3.6% yield; simulated 2x):")
    print(line("  S&P 1x buy-and-hold", sb))
    s = metrics.stats(engine.buy_and_hold(rs, *STRESS, leverage=2.0), rs["bil"])
    st["2x constant"] = s
    print(line("  2x constant", s, sb))
    for cid, (name, rule) in strategies.CANDIDATES.items():
        sim = engine.run(rule(gs), rs, *STRESS)
        s = metrics.stats(sim, rs["bil"])
        worst_day = float(sim["equity"].pct_change().min())
        st[cid] = {**s, "worst_day": worst_day, "worst_day_is": str(sim["equity"].pct_change().idxmin().date())}
        print(line(f"  {cid} {name}", s, sb) + f"  worst day {worst_day * 100:.1f}% ({st[cid]['worst_day_is']})")
    out["stress_1962_1987"] = st

    os.makedirs(f"{HERE}/results", exist_ok=True)
    json.dump(rounded(out), open(f"{HERE}/results/insample.json", "w"), indent=1)
    pd.DataFrame(curves).to_csv(f"{HERE}/results/insample_curves.csv.gz", float_format="%.6f")


if __name__ == "__main__":
    main()
