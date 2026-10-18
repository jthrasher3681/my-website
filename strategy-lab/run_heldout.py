"""The held-out test (PROTOCOL.md, "The held-out test"): the in-sample finalist,
run on from 1988 and scored once on 2016-01-04 .. 2026-10-16 against SPY.

    python3 run_heldout.py

Writes results/heldout.json, results/heldout.txt (via stdout) and
results/heldout_curves.csv.gz.
"""
import json, os
import numpy as np
import pandas as pd

from lab import data, engine, metrics, strategies, tax
from run_insample import START as START_IS, END as END_IS, line, random_timing, rounded

HERE = os.path.dirname(os.path.abspath(__file__))
START, END = "2016-01-04", "2026-10-16"


def main():
    ins = json.load(open(f"{HERE}/results/insample.json"))
    fin = ins["finalist"]
    if fin is None:
        raise SystemExit("no finalist: nothing to test (PROTOCOL.md)")
    r, c, gspc = data.returns()
    if abs(c - ins["c_2x"]) > 1e-5:
        raise SystemExit(f"2x cost changed: {c} vs in-sample {ins['c_2x']}")
    cash = r["bil"]
    const = lambda x: pd.Series(x, index=r.index.insert(0, r.index[0] - pd.Timedelta(days=1)))
    spy_full = engine.run(const(1.0), r, START_IS, END, record=True)
    bench = metrics.stats(metrics.window(spy_full, START, END), cash)
    out = {"period": [START, END], "finalist": fin, "c_2x": c, "candidates": {}, "references": {"SPY buy-and-hold": bench}}
    curves = {"SPY": metrics.window(spy_full, START, END)["equity"]}
    print(line("SPY buy-and-hold", bench))
    for lev, name in ((2.0, "SSO buy-and-hold (2x)"), (1.5, "1.5x constant")):
        s = metrics.stats(metrics.window(engine.run(const(lev), r, START_IS, END), START, END), cash)
        out["references"][name] = s
        print(line(name, s, bench))

    full = {}
    for cid, (name, rule) in strategies.CANDIDATES.items():
        full[cid] = engine.run(rule(gspc), r, START_IS, END, record=True)
        # the in-sample part must be the same run the finalist was chosen on
        again = metrics.stats(metrics.window(full[cid], START_IS, END_IS), cash)
        if abs(again["cagr"] - ins["candidates"][cid]["cagr"]) > 1e-5:
            raise SystemExit(f"{cid}: in-sample CAGR {again['cagr']} differs from the recorded {ins['candidates'][cid]['cagr']}")
        w = metrics.window(full[cid], START, END)
        s = metrics.stats(w, cash)
        ok, chk = metrics.passes(s, bench)
        out["candidates"][cid] = {"name": name, **s, "passes": ok, "checks": chk}
        curves[cid] = w["equity"]
        print(line(f"{cid} {name}{'  <- finalist' if cid == fin else ''}", s, bench))

    f = out["candidates"][fin]
    out["finalist_passes"] = f["passes"]
    print(f"\nFinalist {fin}: {'PASSES' if f['passes'] else 'FAILS'} the held-out bar {f['checks']}")

    w_fin, w_spy = metrics.window(full[fin], START, END), metrics.window(spy_full, START, END)
    diff = np.log1p(w_fin["equity"].pct_change().iloc[1:]) - np.log1p(w_spy["equity"].pct_change().iloc[1:])
    out["log_return_diff_per_year"] = float(diff.mean() * 252)
    out["log_return_diff_ci90"] = metrics.block_bootstrap_ci(diff.to_numpy())
    print(f"Yearly log-return difference vs SPY {out['log_return_diff_per_year'] * 100:.2f} pp, "
          f"90% interval {[round(x * 100, 2) for x in out['log_return_diff_ci90']]} pp")

    null = random_timing(w_fin, r, cash)
    out["random_timing"] = {"cagr_percentile": float((null[:, 0] < f["cagr"]).mean() * 100),
                            "sharpe_percentile": float((null[:, 1] < f["sharpe"]).mean() * 100),
                            "cagr_null_median": float(np.median(null[:, 0])), "sharpe_null_median": float(np.median(null[:, 1]))}
    print("Random timing:", rounded(out["random_timing"]))

    years = {}
    for name, w in (("finalist", w_fin), ("SPY", w_spy)):
        years[name] = metrics.calendar_years(w["equity"])
    ytd = {name: float(w["equity"].iloc[-1] / w["equity"].loc[:"2025-12-31"].iloc[-1] - 1) for name, w in (("finalist", w_fin), ("SPY", w_spy))}
    out["calendar_years"], out["2026_to_date"] = years, ytd
    print("Calendar years (finalist / SPY):", {y: (round(years["finalist"][y] * 100, 1), round(years["SPY"][y] * 100, 1)) for y in years["SPY"]},
          "2026 to date:", {k: round(v * 100, 1) for k, v in ytd.items()})

    sso_real = data.on_calendar(data.growth(data.load("SSO")), r.index).loc[START:END]
    sim2x = data.simulated_2x(r["spy"], r["bil"], c).loc[START:END]
    monthly = lambda x: (1 + x).groupby(x.index.to_period("M")).prod() - 1
    yrs = (sim2x.index[-1] - r.index[r.index.searchsorted(pd.Timestamp(START)) - 1]).days / 365.25
    out["sim_2x_check_2016_2026"] = {
        "tracking_error_daily": float((sim2x - sso_real).std() * np.sqrt(252)),
        "tracking_error_monthly": float((monthly(sim2x) - monthly(sso_real)).std() * np.sqrt(12)),
        "cagr_sim": float((1 + sim2x).prod() ** (1 / yrs) - 1), "cagr_sso": float((1 + sso_real).prod() ** (1 / yrs) - 1)}
    print("Simulated 2x vs real SSO, 2016-2026:", rounded(out["sim_2x_check_2016_2026"]))

    out["taxes"] = {"finalist": tax.after_tax(full[fin], START, END), "SPY": tax.after_tax(spy_full, START, END)}
    for k, v in out["taxes"].items():
        print(f"Taxable account, {k}: CAGR before tax {v['cagr_pre_tax'] * 100:.2f}%, after tax as held "
              f"{v['cagr_after_tax_held'] * 100:.2f}%, liquidated {v['cagr_after_tax_liquidated'] * 100:.2f}%")

    trades = w_fin[w_fin["traded"] == 1].index[1:] if w_fin["traded"].iloc[0] else w_fin[w_fin["traded"] == 1].index
    out["finalist_trades"] = [str(d.date()) for d in trades]
    out["finalist_exposure_at_end"] = float(w_fin["exposure"].iloc[-1])
    print("Finalist trade dates:", out["finalist_trades"])
    json.dump(rounded(out), open(f"{HERE}/results/heldout.json", "w"), indent=1)
    pd.DataFrame(curves).to_csv(f"{HERE}/results/heldout_curves.csv.gz", float_format="%.6f")


if __name__ == "__main__":
    main()
