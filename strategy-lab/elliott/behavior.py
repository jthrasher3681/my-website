"""Behavior tests of Frost & Prechter's expectations (PROTOCOL.md, "Behavior
tests"), against stationary-bootstrap surrogates.

    python3 -m elliott.behavior stocks_daily insample

- For each symbol, every confirmed-pivot pattern is measured, dated by its
  last confirmation bar and counted in the period that bar falls in.
- The same measurements run on 20 surrogates per symbol. Each surrogate
  resamples whole bars in random-length blocks (mean 20 daily or 35 hourly
  bars) as vectors of log open, high, low and close relative to the
  previous close.
- The statistic is the pooled share in real data minus the pooled share in
  the surrogates. Its interval and one-sided p come from a bootstrap over
  symbols, as pre-registered.
- A robustness version resamples calendar months (daily) or ISO weeks
  (hourly) instead: stocks swing together on the same dates, so symbols are
  not independent. That version was added after an independent review.
- B1a_arith and B1b_arith repeat B1a and B1b with arithmetic (chart)
  ratios. They are exploratory.
"""
import argparse, json, os, sys, zlib
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd

from . import data as D, waves

HERE = os.path.dirname(os.path.abspath(__file__))
N_SURR = 20
BLOCK = {"stocks_daily": 20, "etf_daily": 20, "stocks_1h": 35, "stocks_4h": 10}
TESTS = ["B1a", "B1b", "B2", "B3", "B4", "B5", "B6", "B7"]
EXTRA = ["B1a_arith", "B1b_arith"]
# (name, test, centre, half-width in log for ratio tests / relative for B3, B6, B7 / absolute for B5)
CONTROLS = {"B1a": [0.437, 0.556, 0.697], "B1b": [0.309, 0.437], "B3": [0.8, 1.25], "B5": [0.5, -0.5],
            "B6": [1.4, 1.8], "B7": [0.85, 1.15], "B1a_arith": [0.437, 0.556, 0.697], "B1b_arith": [0.309, 0.437]}


def _near_log(r, f, w=0.03):
    return abs(np.log(r / f)) <= w


def _near_rel(r, f, w=0.10):
    return abs(r / f - 1) <= w


def measure(b, piv, ok, cl):
    """Counts per test and calendar cluster for one series:
    {test: {cluster: [events, hits, control hits...]}}, for patterns whose last
    confirmation bar passes ``ok`` (a boolean array). ``cl`` holds each bar's
    calendar cluster."""
    h, l = b["high"], b["low"]
    e, cc, kind, p = piv["e"], piv["c"], piv["kind"], piv["p"]
    x = np.log(p)
    n = len(p)
    m = len(h)
    cnt = {t: {} for t in TESTS + EXTRA}
    cur = [0]

    def add(t, hit, ctl=()):
        row = cnt[t].get(cur[0])
        if row is None:
            row = cnt[t][cur[0]] = np.zeros(2 + len(CONTROLS.get(t, [])), np.int64)
        row[0] += 1
        row[1] += hit
        for i, cflag in enumerate(ctl):
            row[2 + i] += cflag

    for j in range(1, n):
        if not ok[cc[j]]:
            continue
        cur[0] = int(cl[cc[j]])
        if j >= 3:                                            # B1a: P0-P1-P2 = j-2..j
            W1, W2 = abs(x[j - 1] - x[j - 2]), abs(x[j] - x[j - 1])
            r2 = W2 / W1
            if r2 < 1:
                add("B1a", _near_log(r2, 0.618) or _near_log(r2, 0.5), [_near_log(r2, f) for f in CONTROLS["B1a"]])
            ra = abs(p[j] - p[j - 1]) / abs(p[j - 1] - p[j - 2])
            if ra < 1:
                add("B1a_arith", _near_log(ra, 0.618) or _near_log(ra, 0.5), [_near_log(ra, f) for f in CONTROLS["B1a"]])
        if j >= 4:                                            # B6 on P0..P3, B7 on A0, A1, B, C
            q = (j - 3, j - 2, j - 1, j)
            d = 1 if kind[q[3]] == 1 else -1                  # a high ends an up wave 3
            W1, W3 = abs(x[q[1]] - x[q[0]]), abs(x[q[3]] - x[q[2]])
            if d * (x[q[2]] - x[q[0]]) > 0 and d * (x[q[3]] - x[q[1]]) > 0:
                ratio = W3 / W1
                add("B6", _near_rel(ratio, 1.618), [_near_rel(ratio, f) for f in CONTROLS["B6"]])
            dc = 1 if kind[q[3]] == -1 else -1                # a low ends a down C (correction of an up move)
            A, Bl, C = abs(x[q[0]] - x[q[1]]), abs(x[q[2]] - x[q[1]]), abs(x[q[3]] - x[q[2]])
            if 0.382 <= Bl / A <= 0.786 and dc * (x[q[1]] - x[q[3]]) > 0:
                add("B7", _near_rel(C / A, 1.0), [_near_rel(C / A, f) for f in CONTROLS["B7"]])
        if j >= 5:                                            # B1b on P0..P4
            q = list(range(j - 4, j + 1))
            d = 1 if kind[j] == -1 else -1                    # a low ends an up wave 4
            if d * (x[q[2]] - x[q[0]]) > 0 and d * (x[q[3]] - x[q[1]]) > 0 and d * (x[q[4]] - x[q[1]]) > 0:
                r4 = abs(x[q[4]] - x[q[3]]) / abs(x[q[3]] - x[q[2]])
                add("B1b", _near_log(r4, 0.382), [_near_log(r4, f) for f in CONTROLS["B1b"]])
                ra = abs(p[q[4]] - p[q[3]]) / abs(p[q[3]] - p[q[2]])
                add("B1b_arith", _near_log(ra, 0.382), [_near_log(ra, f) for f in CONTROLS["B1b"]])
        if j >= 6:                                            # B2-B5 on P0..P5
            q = list(range(j - 5, j + 1))
            d = 1 if kind[j] == 1 else -1                     # a high ends an up impulse
            W = [abs(x[q[i + 1]] - x[q[i]]) for i in range(5)]
            W1, W3, W5 = W[0], W[2], W[4]
            if not (d * (x[q[2]] - x[q[0]]) > 0 and d * (x[q[3]] - x[q[1]]) > 0
                    and d * (x[q[4]] - x[q[1]]) > 0 and d * (x[q[5]] - x[q[3]]) > 0):
                continue
            add("B2", W3 >= max(W1, W5))
            if not W3 > min(W1, W5):
                continue
            if W3 >= 1.618 * max(W1, W5):
                rho = W5 / W1
                add("B3", _near_rel(rho, 1.0), [_near_rel(rho, f) for f in CONTROLS["B3"]])
            r2, r4 = W[1] / W[0], W[3] / W[2]
            D2, D4 = e[q[2]] - e[q[1]], e[q[4]] - e[q[3]]
            alt = (r2 >= 0.5 and r4 <= 0.382) or (r2 <= 0.382 and r4 >= 0.5) or max(D2, D4) / max(1, min(D2, D4)) >= 1.618
            add("B4", alt)
            e0, e5 = e[q[0]], e[q[5]]
            end = e5 + (e5 - e0)
            if end >= m:
                continue
            seg_h, seg_l = h[e5 + 1:end + 1], l[e5 + 1:end + 1]
            beyond = np.flatnonzero(seg_h > p[q[5]]) if d > 0 else np.flatnonzero(seg_l < p[q[5]])
            stop_at = beyond[0] if len(beyond) else len(seg_h)
            if stop_at == 0:
                continue
            mm = np.log(seg_l[:stop_at].min()) if d > 0 else np.log(seg_h[:stop_at].max())
            z = (mm - x[q[4]]) / (x[q[3]] - x[q[4]])
            add("B5", abs(z) <= 0.15, [abs(z - f) <= 0.15 for f in CONTROLS["B5"]])
    return cnt


def surrogate(b, block, seed):
    """One stationary-bootstrap surrogate of a bar series (same length and times)."""
    o, h, l, c = (np.log(b[k]) for k in ("open", "high", "low", "close"))
    v = np.stack([o[1:] - c[:-1], h[1:] - c[:-1], l[1:] - c[:-1], c[1:] - c[:-1]], axis=1)
    n = len(v)
    rng = np.random.default_rng(seed)
    idx = np.empty(n, np.int64)
    i = rng.integers(n)
    for t in range(n):
        idx[t] = i
        i = rng.integers(n) if rng.random() < 1 / block else (i + 1) % n
    vv = v[idx]
    cc = np.concatenate(([c[0]], c[0] + np.cumsum(vv[:, 3])))
    prev = cc[:-1]
    out = {"t": b["t"], "liquid": b["liquid"]}
    out["open"] = np.exp(np.concatenate(([o[0]], prev + vv[:, 0])))
    out["high"] = np.exp(np.concatenate(([h[0]], prev + vv[:, 1])))
    out["low"] = np.exp(np.concatenate(([l[0]], prev + vv[:, 2])))
    out["close"] = np.exp(cc)
    return out


def clusters(t, daily):
    """Calendar cluster of each bar: its month (daily) or its Monday-based week."""
    if daily:
        return t.astype("datetime64[M]").astype(np.int64)
    return (t.astype("datetime64[D]").astype(np.int64) + 3) // 7


def _symbol(args):
    sym, b, lo, hi, block, k = args[:6]
    daily = args[6] if len(args) > 6 else True
    t = b["t"]
    ok = b["liquid"] & (t >= lo) & (t <= hi)
    cl = clusters(t, daily)
    real = measure(b, waves.pivots(b["high"], b["low"], b["close"], k), ok, cl)
    surr = {tt: {} for tt in real}
    for r in range(N_SURR):
        sb = surrogate(b, block, zlib.crc32(f"{sym}|{r}".encode()))
        sm = measure(sb, waves.pivots(sb["high"], sb["low"], sb["close"], k), ok, cl)
        for tt, by in sm.items():
            for c_, v in by.items():
                surr[tt][c_] = surr[tt].get(c_, 0) + v / N_SURR
    return sym, real, surr


def _width(t):
    return 2 + len(CONTROLS.get(t, []))


def per_symbol(res, t):
    """(symbols x counts) arrays of real and surrogate totals for test t."""
    syms = sorted(res)
    R = np.array([sum(res[s][0][t].values(), np.zeros(_width(t))) for s in syms], float)
    S = np.array([sum(res[s][1][t].values(), np.zeros(_width(t))) for s in syms], float)
    return R, S


def per_cluster(res, t):
    """(calendar clusters x counts) arrays of real and surrogate totals for test t."""
    keys = sorted({c_ for s in res for c_ in list(res[s][0][t]) + list(res[s][1][t])})
    pos = {c_: i for i, c_ in enumerate(keys)}
    R = np.zeros((len(keys), _width(t))); S = np.zeros((len(keys), _width(t)))
    for s in res:
        for c_, v in res[s][0][t].items():
            R[pos[c_]] += v
        for c_, v in res[s][1][t].items():
            S[pos[c_]] += v
    return R, S


def symbol_bootstrap(real, surr, draws=10_000, seed=0):
    """Pooled real share - pooled surrogate share, with a bootstrap over symbols.
    real / surr: arrays (symbols x [events, hits, ...])."""
    def share(a, col):
        return a[:, col].sum() / max(a[:, 0].sum(), 1e-12)
    out = {"events": int(real[:, 0].sum()), "surrogate_events": float(surr[:, 0].sum()),
           "real_share": float(share(real, 1)), "null_share": float(share(surr, 1))}
    out["excess"] = out["real_share"] - out["null_share"]
    rng = np.random.default_rng(seed)
    nsym = len(real)
    pick = rng.integers(0, nsym, size=(draws, nsym))
    rs = real[pick].sum(1)
    ss = surr[pick].sum(1)
    diff = rs[:, 1] / np.maximum(rs[:, 0], 1e-12) - ss[:, 1] / np.maximum(ss[:, 0], 1e-12)
    out.update({"lo": float(np.percentile(diff, 2.5)), "hi": float(np.percentile(diff, 97.5)),
                "p": float((diff <= 0).mean())})
    ctl = []
    for i in range(2, real.shape[1]):
        ctl.append({"real_share": float(share(real, i)), "null_share": float(share(surr, i)),
                    "excess": float(share(real, i) - share(surr, i))})
    out["controls"] = ctl
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("period", choices=["insample", "heldout"])
    ap.add_argument("--k", type=float, default=2.0)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    full = D.DATASETS[a.dataset]()
    start, is_end, ho_start = D.PERIODS[a.dataset]
    if a.period == "insample":
        bars = D.truncate(full, is_end)
        lo, hi = np.datetime64(pd.Timestamp(start)), np.datetime64(pd.Timestamp(is_end))
    else:
        bars = full
        lo, hi = np.datetime64(pd.Timestamp(ho_start)), np.datetime64("2100-01-01")
    jobs = [(s, b, lo, hi, BLOCK[a.dataset], a.k, D.DAILY[a.dataset]) for s, b in sorted(bars.items())]
    res = {}
    with ProcessPoolExecutor(a.workers) as ex:
        for i, (sym, real, surr) in enumerate(ex.map(_symbol, jobs, chunksize=8)):
            res[sym] = (real, surr)
            if i % 200 == 0:
                print(f"{i}/{len(jobs)}", flush=True)
    out = {}
    for t in TESTS + EXTRA:
        out[t] = symbol_bootstrap(*per_symbol(res, t))
        cal = symbol_bootstrap(*per_cluster(res, t))
        out[t]["calendar"] = {"lo": cal["lo"], "hi": cal["hi"], "p": cal["p"], "clusters": len(per_cluster(res, t)[0])}
        o = out[t]
        print(f"{t}: events {o['events']:7d}  real {o['real_share']:.4f}  null {o['null_share']:.4f}  "
              f"excess {o['excess']:+.4f} [{o['lo']:+.4f}, {o['hi']:+.4f}] p {o['p']:.4f}  calendar p {o['calendar']['p']:.4f}  controls "
              + ", ".join(f"{c['excess']:+.4f}" for c in o["controls"]), flush=True)
    os.makedirs(f"{HERE}/results", exist_ok=True)
    json.dump(out, open(f"{HERE}/results/behavior_{a.dataset}_{a.period}_k{a.k:g}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
