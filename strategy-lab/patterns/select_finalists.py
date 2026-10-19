"""The finalist rule in-sample and the held-out verdict (PROTOCOL.md, "Scoring
and choosing finalists", "Held-out test").

    python3 -m patterns.select_finalists insample
    python3 -m patterns.select_finalists heldout
"""
import json, os, sys

from elliott.execute import bh, holm
from .detect import CONFIRMATORY

HERE = os.path.dirname(os.path.abspath(__file__))
DATASETS = ["daily", "weekly", "monthly"]


def load(dataset, period):
    return json.load(open(f"{HERE}/results/{dataset}_{period}.json"))["setups"]


def _p(x):
    return 1.0 if x is None or x.get("p") is None else x["p"]


def insample():
    rows = [{"dataset": ds, "setup": s, "s": load(ds, "insample").get(s)} for ds in DATASETS for s in CONFIRMATORY]
    q = bh([_p(r["s"]["edge"]) if r["s"] else 1.0 for r in rows])
    table, finalists = [], []
    for r, qq in zip(rows, q):
        s = r["s"]
        if s is None:
            table.append({"dataset": r["dataset"], "setup": r["setup"], "trades": 0, "finalist": False})
            continue
        checks = {
            "edge_bh": bool(qq < 0.05 and (s["edge"]["mean"] or 0) > 0),
            "mean_R_positive": bool(_p(s["R_stats"]) < 0.05 and s["mean_R"] > 0),
            "beats_plain_breakouts": bool(_p(s["premium"]) < 0.05 and (s["premium"]["mean"] or 0) > 0),
            "positive_at_2x_cost": bool(s["mean_R_2x_cost"] > 0),
            "both_halves": bool(all(h is not None and h > 0 for h in s["edge_halves"])),
        }
        fin = all(checks.values())
        table.append({"dataset": r["dataset"], "setup": r["setup"], "direction": s["direction"], "trades": s["trades"],
                      "mean_R": s["mean_R"], "mean_twin_R": s["mean_twin_R"], "mean_match_R": s["mean_match_R"],
                      "edge": s["edge"], "edge_q_bh": float(qq), "premium": s["premium"], "R_stats": s["R_stats"],
                      "mean_R_2x_cost": s["mean_R_2x_cost"], "edge_halves": s["edge_halves"], "target_rate": s["target_rate"],
                      "checks": checks, "finalist": fin})
        if fin:
            finalists.append({"dataset": r["dataset"], "setup": r["setup"]})
    json.dump({"confirmatory": table, "finalists": finalists}, open(f"{HERE}/results/finalists.json", "w"), indent=1)
    for t in table:
        if not t["trades"]:
            print(f"{t['dataset']:8} {t['setup']:3} no trades")
            continue
        e, p = t["edge"], t["premium"]
        print(f"{t['dataset']:8} {t['setup']:3} {t['direction']:5} n {t['trades']:5d}  R {t['mean_R']:+.3f} (p {t['R_stats']['p']:.3f})  "
              f"edge {e['mean']:+.3f} [{e['lo']:+.3f},{e['hi']:+.3f}] q {t['edge_q_bh']:.3f}  "
              f"premium {p['mean'] if p['mean'] is None else round(p['mean'], 3)} p {p['p']}  "
              + " ".join(k for k, v in t["checks"].items() if v) + ("  FINALIST" if t["finalist"] else ""))
    print("finalists:", finalists)


def heldout():
    fin = json.load(open(f"{HERE}/results/finalists.json"))["finalists"]
    rows = [{**f, "s": load(f["dataset"], "heldout").get(f["setup"])} for f in fin]
    adj = holm([_p(r["s"]["edge"]) if r["s"] else 1.0 for r in rows]) if rows else []
    verdict = []
    for r, q in zip(rows, adj):
        s = r["s"]
        checks = {"edge_holm": bool(s and q < 0.05 and (s["edge"]["mean"] or 0) > 0),
                  "mean_R_positive": bool(s and _p(s["R_stats"]) < 0.05 and s["mean_R"] > 0),
                  "beats_plain_breakouts": bool(s and (s["premium"]["mean"] or 0) > 0)}
        verdict.append({"dataset": r["dataset"], "setup": r["setup"], "edge_q_holm": float(q), "checks": checks,
                        "passes": all(checks.values()), "summary": s})
    every = []
    for ds in DATASETS:
        for setup, s in load(ds, "heldout").items():
            every.append({"dataset": ds, "setup": setup, "confirmatory": setup in CONFIRMATORY, "trades": s["trades"],
                          "mean_R": s["mean_R"], "R_p": s["R_stats"]["p"], "edge": s["edge"]["mean"], "edge_p": s["edge"]["p"],
                          "premium": s["premium"]["mean"], "premium_p": s["premium"]["p"], "target_rate": s["target_rate"]})
    json.dump({"finalists": verdict, "all_setups_transparency": every}, open(f"{HERE}/results/heldout_verdict.json", "w"), indent=1)
    for v in verdict:
        print(v["dataset"], v["setup"], v["checks"], "PASSES" if v["passes"] else "fails")
    if not verdict:
        print("no finalists: nothing is tested held out")
    for e in every:
        print(f"  {e['dataset']:8} {e['setup']:4} n {e['trades']:5d}  R {e['mean_R']:+.3f} (p {e['R_p']:.3f})  edge {e['edge'] if e['edge'] is None else round(e['edge'], 3)} "
              f"p {e['edge_p']}  premium {e['premium'] if e['premium'] is None else round(e['premium'], 3)} p {e['premium_p']}")


if __name__ == "__main__":
    {"insample": insample, "heldout": heldout}[sys.argv[1]]()
