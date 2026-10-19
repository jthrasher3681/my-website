"""Run the setups on one dataset and period (PROTOCOL.md, "Trades", "Controls",
"Scoring").

    python3 -m patterns.run daily insample
    python3 -m patterns.run weekly heldout

- **insample** reads nothing after the in-sample end.
- **heldout** reads everything and scores signals from the held-out start.
  It also checks that its in-sample part reproduces the in-sample run's
  trades.

Writes results/<dataset>_<period>.json; trade rows go to the folder named by
PATTERNS_OUT.
"""
import argparse, json, os, pickle, time
import multiprocessing as mp
import numpy as np
import pandas as pd

from elliott import execute as X
from . import controls as C, data as D, detect

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("PATTERNS_OUT", "/tmp/claude-0/-home-user-my-website/7e6193d5-03fd-55b8-ab0d-60cef84cba96/scratchpad/patterns/out")
SETUPS = list(detect.SETUPS)                      # AT DT HR HS, and the exploratory H2R H2S
_G = {}


def symbol_trades(sym, b, dataset, cost):
    """(trades after the slot rule, {bar time: setups signalled}) of one symbol."""
    k, (dmin, dmax), nt = D.K[dataset], D.DUR[dataset], D.N_TIME[dataset]
    trades, sig = [], {}
    for setup in SETUPS:
        orders = detect.orders(b, setup, k, dmin, dmax, nt)
        for o in orders:
            sig.setdefault(int(b["tk"][o["sig"]]), set()).add(setup)
        trades += X.run_symbol(sym, b, orders, cost, True)
    return trades, sig


def _work(sym):
    return sym, *symbol_trades(sym, _G["bars"][sym], _G["dataset"], D.COST)


def _twins(chunk):
    return X.twins(chunk, _G["bars"], _G["pool"], D.COST)


def _matched(chunk):
    return C.matched(chunk, _G["bars"], _G["sig_pool"], _G["signals_at"], D.COST)


def build(bars, dataset, workers=4):
    """Every setup's trades on every symbol (before period membership), and
    (symbol, bar time) -> setups signalled there."""
    for b in bars.values():
        X.prepare(b)
    _G.update({"bars": bars, "dataset": dataset})
    with mp.get_context("fork").Pool(workers) as pool:
        per = pool.map(_work, sorted(bars), chunksize=8)
    trades, signals_at = [], {}
    for sym, tr, sig in per:
        trades += tr
        for T, s in sig.items():
            signals_at[(sym, T)] = s
    return trades, signals_at


def members(trades, bars, lo, hi, last=None):
    """Signals in [lo, hi] whose deadline is inside the data (and, with ``last``,
    whose deadline bar is at or before that date)."""
    keep = []
    for t in trades:
        b = bars[t["symbol"]]
        ts = pd.Timestamp(b["t"][t["sig"]])
        if (lo is not None and ts < pd.Timestamp(lo)) or (hi is not None and ts > pd.Timestamp(hi)) or t["deadline"] >= len(b["t"]):
            continue
        if last is not None and pd.Timestamp(b["t"][t["deadline"]]) > pd.Timestamp(last):
            continue
        keep.append({**t, "t_sig": str(ts)})
    return keep


def controls(keep, bars, signals_at, workers=4):
    """Twins, matched plain breakouts and the double-cost R, in place."""
    _G["pool"] = X.twin_pool(bars, True)
    _G["sig_pool"] = X.twin_pool(bars, True, lag=0)
    _G["signals_at"] = signals_at
    chunks = [keep[i::workers * 8] for i in range(workers * 8)]
    with mp.get_context("fork").Pool(workers) as pool:
        tw = pool.map(_twins, chunks)
        mt = pool.map(_matched, chunks)
    for c in range(len(chunks)):
        for i, t in enumerate(chunks[c]):
            t["twin_R"] = float(tw[c][i])
            t["match_R"] = float(mt[c][0][i])
            t["n_match"] = int(mt[c][1][i])
    for t in keep:
        t["R2"] = X.r_multiple(t["d"], t["entry_px"], t["stop"], t["exit_px"], 2 * D.COST)[0]
    return keep


def clusters(ts, dataset):
    ts = pd.DatetimeIndex(ts)
    return (ts.to_period("Q").astype(str) if D.CLUSTER[dataset] == "Q" else ts.year.astype(str)).to_numpy()


def summarize(trades, dataset):
    df = pd.DataFrame(trades)
    out = {}
    if df.empty:
        return out
    df["cluster"] = clusters(pd.to_datetime(df["t_sig"]), dataset)
    half = pd.Timestamp(D.HALF[dataset])
    for (setup, d), g in df.groupby(["setup", "d"]):
        gt = g[g["twin_R"].notna()]
        gm = g[g["match_R"].notna()]
        edge = gt["R"] - gt["twin_R"]
        prem = gm["R"] - gm["match_R"]
        ts = pd.to_datetime(gt["t_sig"])
        out[setup] = {
            "setup": setup, "direction": "long" if d > 0 else "short", "confirmatory": setup in detect.CONFIRMATORY,
            "trades": int(len(g)), "with_twins": int(len(gt)), "with_match": int(len(gm)),
            "mean_R": float(g["R"].mean()), "mean_R_2x_cost": float(g["R2"].mean()), "mean_ret": float(g["ret"].mean()),
            "win_rate": float((g["R"] > 0).mean()), "target_rate": float((g["exit_kind"] == 1).mean()),
            "stop_rate": float((g["exit_kind"] == 0).mean()), "median_n": float(g["n"].median()),
            "mean_twin_R": float(gt["twin_R"].mean()) if len(gt) else None,
            "mean_match_R": float(gm["match_R"].mean()) if len(gm) else None,
            "R_stats": X.cluster_bootstrap(g["R"], g["cluster"]),
            "edge": X.cluster_bootstrap(edge, gt["cluster"]),
            "premium": X.cluster_bootstrap(prem, gm["cluster"]),
            "edge_halves": [float(edge[ts < half].mean()) if (ts < half).any() else None,
                            float(edge[ts >= half].mean()) if (ts >= half).any() else None],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=list(D.DATASETS))
    ap.add_argument("period", choices=["insample", "heldout"])
    a = ap.parse_args()
    t0 = time.time()
    start, is_end, ho, end = D.PERIODS[a.dataset]
    bars = D.DATASETS[a.dataset](end=is_end if a.period == "insample" else None)
    print(f"{a.dataset} {a.period}: {len(bars)} symbols, {time.time() - t0:.0f}s", flush=True)
    all_trades, signals_at = build(bars, a.dataset)
    os.makedirs(OUT, exist_ok=True)
    tag = f"{a.dataset}_{a.period}"
    if a.period == "heldout":
        # the in-sample part of this full-data run must reproduce the in-sample run's trades
        path = f"{OUT}/{a.dataset}_insample_trades.pkl"
        if os.path.exists(path):
            ref = {(t["symbol"], t["setup"], t["sig"]): (t["entry"], t["exit"], round(t["R"], 9)) for t in pickle.load(open(path, "rb"))}
            mine = {(t["symbol"], t["setup"], t["sig"]): (t["entry"], t["exit"], round(t["R"], 9))
                    for t in members(all_trades, bars, start, is_end, last=is_end)}
            same = sum(1 for k2, v in ref.items() if mine.get(k2) == v)
            print(f"in-sample reproduction: {same} of {len(ref)} in-sample trades identical; {len(mine)} found here", flush=True)
    lo, hi = (start, is_end) if a.period == "insample" else (ho, None)
    trades = controls(members(all_trades, bars, lo, hi), bars, signals_at)
    print(f"{len(trades)} trades, {time.time() - t0:.0f}s", flush=True)
    pickle.dump(trades, open(f"{OUT}/{tag}_trades.pkl", "wb"))
    res = {"dataset": a.dataset, "period": a.period, "periods": D.PERIODS[a.dataset], "setups": summarize(trades, a.dataset)}
    os.makedirs(f"{HERE}/results", exist_ok=True)
    json.dump(res, open(f"{HERE}/results/{tag}.json", "w"), indent=1, default=float)
    for s, v in res["setups"].items():
        e, p = v["edge"], v["premium"]
        print(f"{s:4} {v['direction']:5} n {v['trades']:6d}  R {v['mean_R']:+.3f}  twin {v['mean_twin_R'] if v['mean_twin_R'] is None else round(v['mean_twin_R'], 3)}"
              f"  edge {e['mean'] if e['mean'] is None else round(e['mean'], 3)} p {e['p']}  premium {p['mean'] if p['mean'] is None else round(p['mean'], 3)} p {p['p']}"
              f"  target {v['target_rate']:.0%}")
    print(f"done, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
