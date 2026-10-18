"""Run the setups on one dataset and period (PROTOCOL.md, "Scoring a setup").

    python3 -m elliott.run stocks_daily insample [--k 2.0]
    python3 -m elliott.run stocks_daily heldout

- **insample**: reads nothing after the in-sample end (the data are cut there
  first).
- **heldout**: reads everything and scores signals from the held-out start.

A signal counts in a period only if its deadline (the last bar its life
can reach, fixed when it appears) falls inside the data the run reads. The
held-out run checks that its in-sample part reproduces the in-sample run's
trades.

Writes results/<dataset>_<period>_k<k>.json (per-setup summaries). The
trade rows are written to the scratch folder named by ELLIOTT_OUT.
"""
import argparse, json, os, pickle, sys, time
import numpy as np
import pandas as pd

from . import data as D, execute as X, setups, waves

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("ELLIOTT_OUT", "/tmp/claude-0/-home-user-my-website/7e6193d5-03fd-55b8-ab0d-60cef84cba96/scratchpad/elliott/out")
CONFIRMATORY = ["S1", "S2", "S3", "S5", "F2-618", "F2-500", "F4-382"]
BASELINE = {"S1": ["S1-base"], "S2": ["S2-base"], "S3": ["S3-base"], "S5": ["S5-c085", "S5-c115"],
            "F2-618": ["F2-c437", "F2-c556", "F2-c697"], "F2-500": ["F2-c437", "F2-c556", "F2-c697"],
            "F4-382": ["F4-c309", "F4-c437"]}
FIB_CONTRASTS = {"F2": (["F2-618", "F2-500"], ["F2-c437", "F2-c556", "F2-c697"]),
                 "F4": (["F4-382"], ["F4-c309", "F4-c437"]), "S5": (["S5"], ["S5-c085", "S5-c115"])}


def build(dataset, period, k):
    full = D.DATASETS[dataset]()
    start, is_end, ho_start = D.PERIODS[dataset]
    bars = D.truncate(full, is_end) if period == "insample" else full
    for b in bars.values():
        X.prepare(b)
    trades = []
    t0 = time.time()
    for i, (s, b) in enumerate(sorted(bars.items())):
        piv = waves.pivots(b["high"], b["low"], b["close"], k, b["atr"])
        orders = setups.orders(b, piv)
        trades += X.run_symbol(s, b, orders, D.COST[dataset], D.NEED_LIQUID[dataset])
        if i % 200 == 0:
            print(f"{i}/{len(bars)} symbols, {len(trades)} trades, {time.time() - t0:.0f}s", flush=True)
    # period membership: signal date and the deadline inside the data read
    lo, hi = (start, is_end) if period == "insample" else (ho_start, None)
    keep = []
    for t in trades:
        b = bars[t["symbol"]]
        ts = pd.Timestamp(b["t"][t["sig"]])
        if ts < pd.Timestamp(lo) or (hi is not None and ts > pd.Timestamp(hi)) or t["deadline"] >= len(b["t"]):
            continue
        t["t_sig"] = str(ts)
        keep.append(t)
    print(f"{len(keep)} trades in the period; twins...", flush=True)
    pool = X.twin_pool(bars, D.NEED_LIQUID[dataset])
    sig_pool = X.twin_pool(bars, D.NEED_LIQUID[dataset], lag=0)
    tw = X.twins(keep, bars, pool, D.COST[dataset], sig_pool=sig_pool)
    for t, v in zip(keep, tw):
        t["twin_R"] = float(v)
    # 2x costs
    for t in keep:
        E, d = t["entry_px"], t["d"]
        t["R2"] = X.r_multiple(d, E, t["stop"], t["exit_px"], 2 * D.COST[dataset])[0]
    return keep


def summarize(trades, dataset):
    df = pd.DataFrame(trades)
    out = {}
    if df.empty:
        return out
    df["cluster"] = X.clusters_of(pd.to_datetime(df["t_sig"]), D.DAILY[dataset])
    half = pd.Timestamp(D.HALF[dataset])
    for (setup, d), g in df.groupby(["setup", "d"]):
        key = f"{setup}|{'long' if d > 0 else 'short'}"
        gt = g[g["twin_R"].notna()]
        edge = gt["R"] - gt["twin_R"]
        s = {"setup": setup, "direction": "long" if d > 0 else "short", "trades": int(len(g)),
             "with_twins": int(len(gt)), "mean_R": float(g["R"].mean()), "mean_R_2x_cost": float(g["R2"].mean()),
             "win_rate": float((g["R"] > 0).mean()), "mean_ret": float(g["ret"].mean()),
             "mean_twin_R": float(gt["twin_R"].mean()) if len(gt) else None,
             "exit_kinds": {str(k): int(v) for k, v in g["exit_kind"].value_counts().items()},
             "limit_fill_at_open": int(((g["kind"] == "limit") & (g["entry_px"] != g.get("limit", np.nan))).sum()) if "limit" in g else 0,
             "R_stats": X.cluster_bootstrap(g["R"], g["cluster"]),
             "edge": X.cluster_bootstrap(edge, gt["cluster"])}
        ts = pd.to_datetime(gt["t_sig"])
        s["edge_halves"] = [float(edge[ts < half].mean()) if (ts < half).any() else None,
                            float(edge[ts >= half].mean()) if (ts >= half).any() else None]
        out[key] = s
    # baseline / control contrasts
    for setup, bases in BASELINE.items():
        for dname, d in (("long", 1), ("short", -1)):
            a = df[(df["setup"] == setup) & (df["d"] == d)]
            b = df[(df["setup"].isin(bases)) & (df["d"] == d)]
            if f"{setup}|{dname}" in out:
                out[f"{setup}|{dname}"]["baseline"] = {"vs": bases, "baseline_trades": int(len(b)),
                                                       **X.contrast_bootstrap(a["R"], a["cluster"], b["R"], b["cluster"])}
    fib = {}
    for name, (fs, cs) in FIB_CONTRASTS.items():
        for dname, d in (("long", 1), ("short", -1)):
            a = df[(df["setup"].isin(fs)) & (df["d"] == d)]
            b = df[(df["setup"].isin(cs)) & (df["d"] == d)]
            fib[f"{name}|{dname}"] = {"fib": fs, "controls": cs, "fib_trades": int(len(a)), "control_trades": int(len(b)),
                                      **X.contrast_bootstrap(a["R"], a["cluster"], b["R"], b["cluster"])}
    return {"setups": out, "fib_contrasts": fib}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("period", choices=["insample", "heldout"])
    ap.add_argument("--k", type=float, default=2.0)
    a = ap.parse_args()
    trades = build(a.dataset, a.period, a.k)
    os.makedirs(OUT, exist_ok=True)
    tag = f"{a.dataset}_{a.period}_k{a.k:g}"
    pickle.dump(trades, open(f"{OUT}/{tag}_trades.pkl", "wb"))
    res = summarize(trades, a.dataset)
    os.makedirs(f"{HERE}/results", exist_ok=True)
    json.dump(res, open(f"{HERE}/results/{tag}.json", "w"), indent=1, default=float)
    for key in sorted(res.get("setups", {})):
        s = res["setups"][key]
        e = s["edge"]
        print(f"{key:18} n {s['trades']:6d}  mean R {s['mean_R']:+.3f}  twin R {s['mean_twin_R'] if s['mean_twin_R'] is None else round(s['mean_twin_R'], 3)}"
              f"  edge {e['mean'] if e['mean'] is None else round(e['mean'], 3)} p {e['p']}")


if __name__ == "__main__":
    main()
