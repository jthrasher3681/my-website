"""Calibration of the random-timing test on random walks (PROTOCOL.md,
"Calibration"), run before any real-data run.

    python3 -m crossover.calibration.walks [--reps 200] [--draws 200]

On data with no timing information the share of replications with p < 0.05
should be at most 8% for every rule in the gated cases (ii)-(iv). The
asymmetric (GJR) case is reported, not gated: there volatility rises after
drops, so exiting after drops really does avoid risk.

Writes calibration/results.json and results.txt.
"""
import argparse, json, os, time
import multiprocessing as mp
import numpy as np
import pandas as pd

from .. import portfolio as P, signals as S

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = S.CONFIRMATORY + list(S.REFERENCE)
MU, VOL = 0.08, 0.16                 # S&P-like drift and volatility, a year
HOURS = ["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"]

# name: (kind, assets, bars after warm-up, bars a day, gated)
CASES = {
    "i_iid_sp500": ("iid", 1, 7000, 1, False),
    "ii_garch_sp500": ("garch", 1, 7000, 1, True),
    "iii_panel_stocks": ("garch_panel", 200, 1250, 1, True),
    "iv_hourly_garch": ("garch", 1, 3300, 7, True),
    "iv_hourly_panel": ("garch_panel", 100, 3300, 7, True),
    "gjr_sp500": ("gjr", 1, 7000, 1, False),
}


def garch(n, rng, bars_a_day=1, alpha=0.08, beta=0.90, gamma=0.0):
    """GARCH(1,1) (GJR when gamma > 0) innovations with S&P-like unconditional
    volatility, no drift."""
    var = VOL ** 2 / (252 * bars_a_day)
    omega = var * (1 - alpha - beta - gamma / 2)
    z = rng.standard_normal(n)
    out = np.empty(n)
    v = var
    for t in range(n):
        out[t] = np.sqrt(v) * z[t]
        v = omega + (alpha + gamma * (out[t] < 0)) * out[t] ** 2 + beta * v
    return out


def times(n, bars_a_day):
    days = pd.bdate_range("1990-01-02", periods=-(-n // bars_a_day))
    if bars_a_day == 1:
        return days[:n].to_numpy("datetime64[ns]")
    t = pd.DatetimeIndex([pd.Timestamp(f"{d.date()} {h}") for d in days for h in HOURS])
    return t[:n].to_numpy("datetime64[ns]")


def market(case, seed):
    kind, A, n, k, _ = CASES[case]
    n += S.WARMUP + 2
    rng = np.random.default_rng(seed)
    mu = MU / (252 * k)
    t = times(n, k)
    if kind == "iid":
        rets = [mu + rng.normal(0, VOL / np.sqrt(252 * k), n)]
    elif kind == "garch":
        rets = [mu + garch(n, rng, k)]
    elif kind == "gjr":
        rets = [mu + garch(n, rng, k, alpha=0.02, beta=0.90, gamma=0.12)]
    else:
        f = garch(n, rng, k)
        betas = rng.uniform(0.5, 1.5, A)
        idio = 0.25 / np.sqrt(252 * k)
        rets = [mu + b * f + rng.normal(0, idio, n) for b in betas]
    assets = {}
    for i, r in enumerate(rets):
        close = 100 * np.exp(np.cumsum(r))
        assets[f"A{i:03d}"] = {"t": t, "close": close, "tr": close, "liquid": np.ones(n, bool)}
    days = pd.DatetimeIndex(t).normalize().unique()
    return assets, pd.Series(0.0, index=days)


def one(job):
    case, rep, draws = job
    assets, cash = market(case, seed=1000 * rep + 7)
    p = P.Panel(assets, cash)
    block = 63 if CASES[case][3] == 1 else 70
    out = {}
    for rule in RULES:
        H, W = p.rule(rule)
        j0, j1 = p.window(H, p.cal[0])
        real, d = p.null_sharpes(H, j0, j1, block, draws, seed=P.seed_of(case, rep, rule))
        out[rule] = (P.null_test(real, d)["p"], real - d.mean())
    return case, rep, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--draws", type=int, default=200)
    ap.add_argument("--cases", nargs="*", default=list(CASES))
    a = ap.parse_args()
    t0 = time.time()
    jobs = [(c, rep, a.draws) for c in a.cases for rep in range(a.reps)]
    with mp.get_context("fork").Pool(4) as pool:
        rows = pool.map(one, jobs, chunksize=4)
    res = {"reps": a.reps, "draws": a.draws, "cases": {}}
    lines = []
    for c in a.cases:
        ps = {rule: np.array([o[rule][0] for cc, _, o in rows if cc == c]) for rule in RULES}
        ed = {rule: np.array([o[rule][1] for cc, _, o in rows if cc == c]) for rule in RULES}
        gated = CASES[c][4]
        res["cases"][c] = {"gated": gated, "rules": {rule: {
            "reject_05": float((ps[rule] < 0.05).mean()), "reject_10": float((ps[rule] < 0.10).mean()),
            "mean_p": float(ps[rule].mean()), "mean_edge": float(ed[rule].mean())} for rule in RULES}}
        res["cases"][c]["ok"] = bool(not gated or all(v["reject_05"] <= 0.08 for k, v in res["cases"][c]["rules"].items()
                                                       if k in S.CONFIRMATORY))
        lines.append(f"{c} ({'gated' if gated else 'reported'})" + ("" if res["cases"][c]["ok"] else "  ABOVE 8%"))
        for rule, v in res["cases"][c]["rules"].items():
            lines.append(f"  {rule}: p<0.05 in {v['reject_05']:.1%}, p<0.10 in {v['reject_10']:.1%}, "
                         f"mean p {v['mean_p']:.3f}, mean Sharpe edge {v['mean_edge']:+.4f}")
    res["all_gated_ok"] = all(v["ok"] for v in res["cases"].values())
    lines.append(f"all gated cases at most 8%: {res['all_gated_ok']}  ({time.time() - t0:.0f}s)")
    json.dump(res, open(f"{HERE}/results.json", "w"), indent=1)
    open(f"{HERE}/results.txt", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
