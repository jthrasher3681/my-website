"""Calibration on random walks (PROTOCOL.md, "Calibration"), run before any real
data is read.

    python3 -m patterns.calibration.walks [--seeds 20]

Each seed is a fresh market of 300 path-consistent random walks (no drift,
every bar liquid) for each timeframe: daily 2,700 bars at 2% a bar, weekly
1,800 at 4.5%, monthly 480 at 9%. The whole pipeline runs on it: patterns,
the slot rule, twins and matched plain breakouts. With no information in the
prices, every edge and premium should be about zero.

Writes calibration/results.json and results.txt.
"""
import argparse, json, os, time
import numpy as np
import pandas as pd

from elliott.calibration.walks import path_walk
from .. import detect, run as RUN

HERE = os.path.dirname(os.path.abspath(__file__))
SHAPES = {"daily": (2700, 0.02, "B", "2000-01-03"), "weekly": (1800, 0.045, "W-MON", "1985-01-07"),
          "monthly": (480, 0.09, "MS", "1985-01-01")}
N_SYM = 300


def market(dataset, seed):
    n, vol, freq, start = SHAPES[dataset]
    t = pd.date_range(start, periods=n, freq=freq).to_numpy("datetime64[ns]")
    bars = {}
    for s in range(N_SYM):
        o, h, l, c = path_walk(n, 100_000 * seed + s, vol=vol)
        bars[f"W{s:03d}"] = {"t": t, "open": o, "high": h, "low": l, "close": c, "volume": np.ones(n),
                             "liquid": np.ones(n, bool)}
    return bars


def one(dataset, seed):
    bars = market(dataset, seed)
    trades, signals_at = RUN.build(bars, dataset)
    keep = RUN.controls(RUN.members(trades, bars, None, None), bars, signals_at)
    return RUN.summarize(keep, dataset)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--datasets", nargs="*", default=list(SHAPES))
    a = ap.parse_args()
    t0 = time.time()
    res, lines = {}, []
    for ds in a.datasets:
        per = []
        for seed in range(a.seeds):
            per.append(one(ds, seed))
            print(f"{ds} seed {seed} done, {time.time() - t0:.0f}s", flush=True)
        res[ds] = {}
        for setup in detect.SETUPS:
            rows = [p[setup] for p in per if setup in p]
            if not rows:
                continue
            ed = np.array([r["edge"]["mean"] for r in rows if r["edge"]["mean"] is not None])
            pr = np.array([r["premium"]["mean"] for r in rows if r["premium"]["mean"] is not None])
            pe = np.array([r["edge"]["p"] for r in rows if r["edge"]["p"] is not None])
            pp = np.array([r["premium"]["p"] for r in rows if r["premium"]["p"] is not None])
            n = np.array([r["trades"] for r in rows])
            mr = np.array([r["mean_R"] for r in rows])
            w = n[: len(ed)].astype(float)
            out = {"seeds": len(rows), "trades_per_seed": float(n.mean()),
                   "mean_R": float(np.average(mr, weights=n)),
                   "edge": float(np.average(ed, weights=w)) if len(ed) else None,
                   "edge_se": float(ed.std(ddof=1) / np.sqrt(len(ed))) if len(ed) > 1 else None,
                   "premium": float(np.average(pr, weights=n[: len(pr)])) if len(pr) else None,
                   "premium_se": float(pr.std(ddof=1) / np.sqrt(len(pr))) if len(pr) > 1 else None,
                   "seeds_edge_p05": int((pe < 0.05).sum()), "seeds_premium_p05": int((pp < 0.05).sum()),
                   "target_rate": float(np.mean([r["target_rate"] for r in rows]))}
            out["ok"] = bool((out["edge"] is None or abs(out["edge"]) <= 0.05) and (out["premium"] is None or abs(out["premium"]) <= 0.05)
                             and out["seeds_edge_p05"] <= 3)
            res[ds][setup] = out
            lines.append(f"{ds:8} {setup:4} trades/seed {out['trades_per_seed']:8.1f}  R {out['mean_R']:+.3f}  "
                         f"edge {out['edge']:+.3f} (se {out['edge_se'] or 0:.3f}, p<.05 in {out['seeds_edge_p05']}/{len(rows)})  "
                         f"premium {out['premium'] if out['premium'] is None else round(out['premium'], 3)} "
                         f"(se {out['premium_se'] or 0:.3f}, p<.05 in {out['seeds_premium_p05']})  target {out['target_rate']:.0%}"
                         + ("" if out["ok"] else "  CHECK"))
            print(lines[-1], flush=True)
    res["all_ok"] = all(v["ok"] for ds in res.values() if isinstance(ds, dict) for v in ds.values())
    lines.append(f"all within the bars: {res['all_ok']} ({time.time() - t0:.0f}s)")
    json.dump(res, open(f"{HERE}/results.json", "w"), indent=1)
    open(f"{HERE}/results.txt", "w").write("\n".join(lines) + "\n")
    print(lines[-1])


if __name__ == "__main__":
    main()
