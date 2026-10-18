"""The finalist rule in-sample and the held-out verdict (PROTOCOL.md,
"Choosing finalists", "Held-out test").

    python3 -m crossover.select_finalists insample
    python3 -m crossover.select_finalists heldout
"""
import json, os, sys

from elliott.execute import bh, holm
from .signals import CONFIRMATORY

HERE = os.path.dirname(os.path.abspath(__file__))
DATASETS = ["sp500", "stocks_daily", "etf_daily", "stocks_1h"]


def load(dataset, period):
    return json.load(open(f"{HERE}/results/{dataset}_{period}.json"))


def insample():
    rows = [{"dataset": ds, "rule": rule, "r": load(ds, "insample")["rules"][rule]} for ds in DATASETS for rule in CONFIRMATORY]
    q = bh([r["r"]["full"]["null"]["p"] for r in rows])
    table, finalists = [], []
    for r, qq in zip(rows, q):
        f = r["r"]["full"]
        checks = {"bar": f["passes_bar"],
                  "timing_edge_bh": bool(qq < 0.05 and f["null"]["edge"] > 0),
                  "bar_at_2x_cost": f["passes_bar_2x_cost"],
                  "edge_both_halves": bool(r["r"]["half1"]["null"]["edge"] > 0 and r["r"]["half2"]["null"]["edge"] > 0)}
        fin = all(checks.values())
        table.append({"dataset": r["dataset"], "rule": r["rule"], "name": r["r"]["name"], "cagr": f["net"]["cagr"],
                      "bench_cagr": f["benchmark"]["cagr"], "sharpe": f["net"]["sharpe"], "bench_sharpe": f["benchmark"]["sharpe"],
                      "max_dd": f["net"]["max_dd"], "bench_max_dd": f["benchmark"]["max_dd"], "edge": f["null"]["edge"],
                      "p": f["null"]["p"], "q_bh": float(qq), "edge_halves": [r["r"]["half1"]["null"]["edge"], r["r"]["half2"]["null"]["edge"]],
                      "checks": checks, "finalist": fin})
        if fin:
            finalists.append({"dataset": r["dataset"], "rule": r["rule"]})
    # robustness, added after the independent review: the same rule with the leak-free shift null
    qs = bh([r["r"]["full"]["null_shift"]["p"] for r in rows])
    robust, robust_fin = [], []
    for r, qq in zip(rows, qs):
        f = r["r"]
        checks = {"bar": f["full"]["passes_bar"],
                  "timing_edge_bh": bool(qq < 0.05 and f["full"]["null_shift"]["edge"] > 0),
                  "bar_at_2x_cost": f["full"]["passes_bar_2x_cost"],
                  "edge_both_halves": bool(f["half1"]["null_shift"]["edge"] > 0 and f["half2"]["null_shift"]["edge"] > 0)}
        robust.append({"dataset": r["dataset"], "rule": r["rule"], "edge": f["full"]["null_shift"]["edge"],
                       "p": f["full"]["null_shift"]["p"], "q_bh": float(qq), "checks": checks, "finalist": all(checks.values())})
        if all(checks.values()):
            robust_fin.append({"dataset": r["dataset"], "rule": r["rule"]})
    json.dump({"confirmatory": table, "finalists": finalists,
               "robustness_shift_null": {"tests": robust, "finalists": robust_fin}},
              open(f"{HERE}/results/finalists.json", "w"), indent=1)
    for t in table:
        print(f"{t['dataset']:13} {t['rule']} CAGR {t['cagr']:+.2%} vs {t['bench_cagr']:+.2%}  Sharpe {t['sharpe']:.2f} vs {t['bench_sharpe']:.2f}  "
              f"DD {t['max_dd']:.1%} vs {t['bench_max_dd']:.1%}  edge {t['edge']:+.3f} p {t['p']:.3f} q {t['q_bh']:.3f}  "
              + " ".join(k for k, v in t["checks"].items() if v) + ("  FINALIST" if t["finalist"] else ""))
    print("finalists:", finalists)
    print("robustness, shift null: min q", round(min(x["q_bh"] for x in robust), 3), "finalists:", robust_fin)
    for x in sorted(robust, key=lambda x: x["p"])[:5]:
        print(f"  {x['dataset']:13} {x['rule']} shift edge {x['edge']:+.3f} p {x['p']:.3f} q {x['q_bh']:.3f}")


def heldout():
    fin = json.load(open(f"{HERE}/results/finalists.json"))["finalists"]
    rows = [{**f, "r": load(f["dataset"], "heldout")["rules"][f["rule"]]["full"]} for f in fin]
    adj = holm([r["r"]["null"]["p"] for r in rows]) if rows else []
    verdict = []
    for r, q in zip(rows, adj):
        f = r["r"]
        checks = {"bar": f["passes_bar"], "timing_edge_holm": bool(q < 0.05 and f["null"]["edge"] > 0)}
        passes = all(checks.values())
        verdict.append({"dataset": r["dataset"], "rule": r["rule"], "q_holm": float(q), "checks": checks, "passes": passes,
                        "beats_spy": f["passes_vs_spy"], "system_to_build_on": bool(passes and f["passes_vs_spy"])})
    # every rule, for transparency (not a test)
    every = []
    for ds in DATASETS:
        res = load(ds, "heldout")
        for rule, v in res["rules"].items():
            f = v["full"]
            every.append({"dataset": ds, "rule": rule, "cagr": f["net"]["cagr"], "bench_cagr": f["benchmark"]["cagr"],
                          "spy_cagr": f["spy"]["cagr"], "sharpe": f["net"]["sharpe"], "bench_sharpe": f["benchmark"]["sharpe"],
                          "max_dd": f["net"]["max_dd"], "bench_max_dd": f["benchmark"]["max_dd"], "passes_bar": f["passes_bar"],
                          "passes_vs_spy": f["passes_vs_spy"], "edge": f["null"]["edge"], "p": f["null"]["p"],
                          "shift_edge": f["null_shift"]["edge"], "shift_p": f["null_shift"]["p"]})
    json.dump({"finalists": verdict, "all_rules_transparency": every}, open(f"{HERE}/results/heldout_verdict.json", "w"), indent=1)
    for v in verdict:
        print(v["dataset"], v["rule"], v["checks"], "PASSES" if v["passes"] else "fails",
              "| a system to build on" if v["system_to_build_on"] else "")
    if not verdict:
        print("no finalists: nothing is tested held out")
    for e in every:
        print(f"  {e['dataset']:13} {e['rule']} CAGR {e['cagr']:+.2%} vs {e['bench_cagr']:+.2%} (SPY {e['spy_cagr']:+.2%})  "
              f"Sharpe {e['sharpe']:.2f} vs {e['bench_sharpe']:.2f}  DD {e['max_dd']:.1%} vs {e['bench_max_dd']:.1%}  "
              f"bar {'pass' if e['passes_bar'] else 'fail'}  edge {e['edge']:+.3f} p {e['p']:.3f}  shift p {e['shift_p']:.3f}")


if __name__ == "__main__":
    {"insample": insample, "heldout": heldout}[sys.argv[1]]()
