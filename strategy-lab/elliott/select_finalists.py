"""The finalist rule and the Fibonacci contrasts, in-sample (PROTOCOL.md,
"Choosing finalists (in-sample)" and "Fibonacci levels against neighbouring
levels, in trades"), and the held-out verdict for the finalists.

    python3 -m elliott.select_finalists insample
    python3 -m elliott.select_finalists heldout
"""
import json, os, sys
import numpy as np

from . import execute as X
from .run import CONFIRMATORY

HERE = os.path.dirname(os.path.abspath(__file__))
DATASETS = ["stocks_daily", "stocks_1h"]


def load(period, dataset, k=2.0):
    return json.load(open(f"{HERE}/results/{dataset}_{period}_k{k:g}.json"))


def insample():
    rows = []
    for ds in DATASETS:
        res = load("insample", ds)
        for setup in CONFIRMATORY:
            for dname in ("long", "short"):
                s = res["setups"].get(f"{setup}|{dname}")
                rows.append({"dataset": ds, "setup": setup, "direction": dname, "s": s})
    p = [r["s"]["edge"]["p"] if r["s"] and r["s"]["edge"]["p"] is not None else 1.0 for r in rows]
    adj = X.bh(p)
    finalists = []
    table = []
    for r, q in zip(rows, adj):
        s = r["s"]
        if s is None:
            table.append({**{k: r[k] for k in ("dataset", "setup", "direction")}, "trades": 0, "finalist": False})
            continue
        checks = {
            "edge_bh": bool(q < 0.05 and (s["edge"]["mean"] or 0) > 0),
            "mean_R_positive": bool((s["R_stats"]["p"] if s["R_stats"]["p"] is not None else 1) < 0.05 and s["mean_R"] > 0),
            "beats_baseline": bool(s.get("baseline", {}).get("p") is not None and s["baseline"]["p"] < 0.05 and s["baseline"]["diff"] > 0),
            "positive_at_2x_cost": bool(s["mean_R_2x_cost"] > 0),
            "both_halves": bool(all(h is not None and h > 0 for h in s["edge_halves"])),
        }
        fin = all(checks.values())
        row = {"dataset": r["dataset"], "setup": r["setup"], "direction": r["direction"], "trades": s["trades"],
               "mean_R": s["mean_R"], "mean_twin_R": s["mean_twin_R"], "edge": s["edge"]["mean"], "edge_lo": s["edge"]["lo"],
               "edge_hi": s["edge"]["hi"], "edge_p": s["edge"]["p"], "edge_q_bh": float(q),
               "baseline_diff": s.get("baseline", {}).get("diff"), "baseline_p": s.get("baseline", {}).get("p"),
               "mean_R_2x_cost": s["mean_R_2x_cost"], "edge_halves": s["edge_halves"], "checks": checks, "finalist": fin}
        table.append(row)
        if fin:
            finalists.append({k: r[k] for k in ("dataset", "setup", "direction")})
    fib_rows = []
    for ds in DATASETS:
        res = load("insample", ds)
        for key, v in res["fib_contrasts"].items():
            fib_rows.append({"dataset": ds, "contrast": key, **v})
    fq = X.bh([r["p"] if r["p"] is not None else 1.0 for r in fib_rows])
    for r, q in zip(fib_rows, fq):
        r["q_bh"] = float(q)
        r["significant"] = bool(q < 0.05 and (r["diff"] or 0) > 0)
    out = {"confirmatory": table, "finalists": finalists, "fib_contrasts": fib_rows}
    json.dump(out, open(f"{HERE}/results/finalists.json", "w"), indent=1)
    for r in table:
        if r.get("trades"):
            print(f"{r['dataset']:13} {r['setup']:7} {r['direction']:5} n {r['trades']:6d} R {r['mean_R']:+.3f} edge {r['edge']:+.3f} "
                  f"[{r['edge_lo']:+.3f},{r['edge_hi']:+.3f}] q {r['edge_q_bh']:.3f} base {r['baseline_diff'] if r['baseline_diff'] is None else round(r['baseline_diff'], 3)} "
                  f"{'FINALIST' if r['finalist'] else ''}")
    print("finalists:", finalists)
    for r in fib_rows:
        print(f"fib {r['dataset']:13} {r['contrast']:9} n {r['fib_trades']}/{r['control_trades']} diff {r['diff']} q {r['q_bh']:.3f}")


def heldout():
    fin = json.load(open(f"{HERE}/results/finalists.json"))
    rows = []
    for f in fin["finalists"]:
        s = load("heldout", f["dataset"])["setups"].get(f"{f['setup']}|{f['direction']}")
        rows.append({**f, "s": s})
    p = [r["s"]["edge"]["p"] if r["s"] else 1.0 for r in rows]
    adj = X.holm(p) if p else []
    verdict = []
    for r, q in zip(rows, adj):
        s = r["s"]
        checks = {"edge_holm": bool(s and q < 0.05 and s["edge"]["mean"] > 0),
                  "mean_R_positive": bool(s and s["R_stats"]["p"] < 0.05 and s["mean_R"] > 0),
                  "beats_baseline": bool(s and s.get("baseline", {}).get("diff") is not None and s["baseline"]["diff"] > 0)}
        verdict.append({**{k: r[k] for k in ("dataset", "setup", "direction")}, "edge_q_holm": float(q), "checks": checks,
                        "passes": all(checks.values()), "summary": s})
    held = {"finalists": verdict}
    fib_rows = []
    for ds in DATASETS:
        res = load("heldout", ds)
        for key, v in res["fib_contrasts"].items():
            fib_rows.append({"dataset": ds, "contrast": key, **v})
    held["fib_contrasts"] = fib_rows
    json.dump(held, open(f"{HERE}/results/heldout_verdict.json", "w"), indent=1)
    for v in verdict:
        print(v["dataset"], v["setup"], v["direction"], v["checks"], "PASSES" if v["passes"] else "fails")


def behavior():
    """BH across the 16 in-sample behavior tests; held-out replication (p < 0.05) of the significant ones."""
    rows = []
    for ds in DATASETS:
        ins = json.load(open(f"{HERE}/results/behavior_{ds}_insample_k2.json"))
        path = f"{HERE}/results/behavior_{ds}_heldout_k2.json"
        out = json.load(open(path)) if os.path.exists(path) else {}
        for t, v in ins.items():
            if t in ("B1a_arith", "B1b_arith"):
                continue
            rows.append({"dataset": ds, "test": t, "insample": v, "heldout": out.get(t)})
    q = X.bh([r["insample"]["p"] for r in rows])
    qc = X.bh([r["insample"].get("calendar", {}).get("p", 1.0) for r in rows])
    for r, qq, qqc in zip(rows, q, qc):
        r["q_bh"] = float(qq)
        r["significant_insample"] = bool(qq < 0.05 and r["insample"]["excess"] > 0)
        h = r["heldout"]
        r["replicates"] = bool(r["significant_insample"] and h is not None and h["p"] < 0.05 and h["excess"] > 0)
        r["supported"] = r["replicates"]
        # robustness (after review): calendar-clustered p-values, BH across the same 16 tests
        r["q_bh_calendar"] = float(qqc)
        r["supported_calendar"] = bool(qqc < 0.05 and r["insample"]["excess"] > 0 and h is not None
                                       and h.get("calendar", {}).get("p", 1.0) < 0.05 and h["excess"] > 0)
    json.dump(rows, open(f"{HERE}/results/behavior_verdict.json", "w"), indent=1)
    for r in rows:
        i, h = r["insample"], r["heldout"]
        print(f"{r['dataset']:13} {r['test']:4} in: real {i['real_share']:.4f} null {i['null_share']:.4f} excess {i['excess']:+.4f} q {r['q_bh']:.3f}"
              + (f" | held out: excess {h['excess']:+.4f} [{h['lo']:+.4f},{h['hi']:+.4f}] p {h['p']:.4f}" if h else "")
              + ("  SUPPORTED" if r["supported"] else ("  (significant in-sample only)" if r["significant_insample"] else ""))
              + f"  | calendar q {r['q_bh_calendar']:.3f}" + ("  supported by calendar too" if r["supported_calendar"] else ""))


if __name__ == "__main__":
    {"insample": insample, "heldout": heldout, "behavior": behavior}[sys.argv[1]]()
