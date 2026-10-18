"""Order handling, trade results and random twins (PROTOCOL.md,
"Execution" and "Scoring a setup").

``run_symbol`` turns one symbol's orders into trades under the one-slot rule.
A slot (symbol, setup variant, direction) is held by a pending order or an
open trade, and a signal arriving while it is busy is dropped. An order whose
life runs past the end of the data keeps the slot to the end and gives no
trade.

``twins`` gives each trade 20 random twins: other symbols with a bar at the
trade's entry time, liquid on the bar before it, entered at that bar's
open. Each twin uses the trade's direction, its stop / target (and S3
"new extreme") distances in log ATR as of the bar before entry, its time
exit and its fill-bar rule.
"""
import zlib
import numpy as np
import pandas as pd
from numba import njit

from . import waves

N_TWINS, MIN_TWINS = 20, 10
MIN_RISK_ATR = 0.5


def prepare(bars):
    """Adds log ATR, the displaced MA, int bar times and a time -> index map."""
    if "atr" not in bars:
        bars["atr"] = waves.log_atr(bars["high"], bars["low"], bars["close"])
        bars["dma"] = waves.dma(bars["close"])
        bars["tk"] = bars["t"].astype("datetime64[ns]").astype("int64")
        bars["pos"] = {t: i for i, t in enumerate(bars["tk"].tolist())}
    return bars


@njit(cache=True)
def _fill_limit(op, hi, lo, sig, d, limit, cancel_level, cancel_open, expiry):
    n = len(op)
    for j in range(sig + 1, expiry + 1):
        if j >= n:
            return -1, np.nan, -1
        if d * (op[j] - cancel_open) <= 0:
            return -1, np.nan, j
        if d * (op[j] - limit) <= 0:
            return j, op[j], j
        far = hi[j] if d > 0 else lo[j]
        near = lo[j] if d > 0 else hi[j]
        if d * (far - cancel_level) > 0:
            return -1, np.nan, j
        if d * (limit - near) >= 0:
            return j, limit, j
    return -1, np.nan, expiry


def fill_limit(b, o):
    """(fill_bar, fill_price), or (None, end_bar) when cancelled or expired
    (end_bar -1 when the data ends first)."""
    j, px, end = _fill_limit(b["open"], b["high"], b["low"], int(o["sig"]), int(o["d"]), float(o["limit"]),
                             float(o["cancel_level"]), float(o["cancel_open"]), int(o["expiry"]))
    return (int(j), float(px)) if j >= 0 else (None, int(end))


def r_multiple(d, E, stop, exit_px, cost):
    risk = abs(E - stop)
    return (d * (exit_px - E) - 2 * cost * E) / risk, d * (exit_px / E - 1) - 2 * cost


def run_symbol(sym, b, orders, cost, need_liquid):
    """Trades of one symbol's orders under the slot rule."""
    n = len(b["open"])
    trades = []
    slots = {}
    for o in sorted(orders, key=lambda o: o["sig"]):
        key = (o["setup"], o["d"])
        if o["sig"] <= slots.get(key, -1):
            continue
        if need_liquid and not b["liquid"][o["sig"]]:
            continue
        d = o["d"]
        if o["kind"] == "market":
            e = o["sig"] + 1
            if e >= n:
                slots[key] = np.inf
                continue
            E = b["open"][e]
            if d * (E - o["stop"]) <= 0 or (not np.isnan(o["target"]) and d * (o["target"] - E) <= 0):
                continue
            limit_fill = False
        else:
            e, E = fill_limit(b, o)
            if e is None:
                slots[key] = np.inf if E == -1 else E
                continue
            limit_fill = True
        a = b["atr"][e - 1]
        if not (a > 0) or abs(np.log(E) - np.log(o["stop"])) < MIN_RISK_ATR * a:
            # a stop inside half a bar's typical range: noise decides it (amendment 1); the slot is not held
            continue
        target = o["target"] if o["target"] > 0 else np.nan
        j, px, kind = waves.run_exit(b["open"], b["high"], b["low"], b["close"], e, E, d, o["stop"], target,
                                     o["n_time"], limit_fill, o["s3_level"], b["dma"])
        if j < 0:
            slots[key] = np.inf
            continue
        slots[key] = j
        R, ret = r_multiple(d, E, o["stop"], px, cost)
        trades.append({**o, "symbol": sym, "entry": int(e), "entry_px": float(E), "exit": int(j), "exit_px": float(px),
                       "exit_kind": int(kind), "limit_fill": limit_fill, "R": float(R), "ret": float(ret)})
    return trades


def _geometry(b, t):
    """The trade's stop / target / S3-level distances in log ATR of the bar before entry."""
    a = b["atr"][t["entry"] - 1] if t["entry"] >= 1 else np.nan
    if not (a > 0):
        return None
    lE, d = np.log(t["entry_px"]), t["d"]
    g = {"a": a, "stop": d * (lE - np.log(t["stop"])) / a,
         "target": np.nan if not (t["target"] > 0) else d * (np.log(t["target"]) - lE) / a,
         "s3": np.nan if np.isnan(t["s3_level"]) else d * (np.log(t["s3_level"]) - lE) / a}
    return g


def twin_pool(data, need_liquid, lag=1):
    """bar time -> symbols with a bar then that pass the liquidity rule ``lag`` bars
    earlier (1: entry-bar twins, liquid the bar before; 0: order twins, liquid on
    the signal bar)."""
    pool = {}
    for s in sorted(data):
        b = data[s]
        if not need_liquid:
            ok = np.ones(len(b["tk"]), bool)
        else:
            ok = b["liquid"].copy() if lag == 0 else np.concatenate(([False], b["liquid"][:-1]))
        for t in b["tk"][ok].tolist():
            pool.setdefault(t, []).append(s)
    return pool


def _order_geometry(b, t):
    """A limit order's levels as log-ATR distances from its signal bar's close (ATR of that bar)."""
    c = t["sig"]
    a, lc, d = b["atr"][c], np.log(b["close"][c]), t["d"]
    if not (a > 0):
        return None
    dist = lambda lvl: np.nan if not (lvl > 0) else d * (lc - np.log(lvl)) / a      # > 0: behind the close
    return {"limit": dist(t["limit"]), "cancel_level": dist(t["cancel_level"]), "cancel_open": dist(t["cancel_open"]),
            "stop": dist(t["stop"]), "target": dist(t["target"]), "expiry": t["expiry"] - c}


def _order_twin(bb, j, g, t, cost):
    """The same limit order placed on another symbol at bar j: its R, or None if it never fills."""
    a = bb["atr"][j]
    if not (a > 0) or j + 1 >= len(bb["open"]):
        return None
    lc, d = np.log(bb["close"][j]), t["d"]
    lvl = lambda x: np.nan if np.isnan(x) else np.exp(lc - d * x * a)
    o = {"sig": j, "d": d, "limit": lvl(g["limit"]), "cancel_level": lvl(g["cancel_level"]),
         "cancel_open": lvl(g["cancel_open"]), "expiry": j + g["expiry"]}
    e, E = fill_limit(bb, o)
    if e is None:
        return None
    stop, tgt = lvl(g["stop"]), lvl(g["target"])
    if abs(np.log(E) - np.log(stop)) < MIN_RISK_ATR * bb["atr"][e - 1]:
        return None
    jj, px, kind = waves.run_exit(bb["open"], bb["high"], bb["low"], bb["close"], e, E, d, stop, tgt,
                                  t["n_time"], True, np.nan, bb["dma"])
    if jj < 0:
        return None
    return r_multiple(d, E, stop, px, cost)[0]


def twins(trades, data, pool, cost, k=N_TWINS, sig_pool=None):
    """Mean twin R (NaN when fewer than MIN_TWINS) for each trade. Market trades get
    entry-bar twins; limit trades get order twins: the same order placed on the twin
    at the signal bar (amendment 2)."""
    out = np.full(len(trades), np.nan)
    for i, t in enumerate(trades):
        b = data[t["symbol"]]
        if t["kind"] == "limit":
            g = _order_geometry(b, t)
            if g is None:
                continue
            T = int(b["tk"][t["sig"]])
            cands = [s for s in (sig_pool or pool).get(T, []) if s != t["symbol"]]
            if not cands:
                continue
            rng = np.random.default_rng(zlib.crc32(f"{t['symbol']}|{t['setup']}|{t['d']}|{t['sig']}".encode()))
            got = []
            for _ in range(10 * k):
                if len(got) >= k:
                    break
                s = cands[rng.integers(len(cands))]
                r = _order_twin(data[s], data[s]["pos"][T], g, t, cost)
                if r is not None:
                    got.append(r)
            if len(got) >= MIN_TWINS:
                out[i] = float(np.mean(got))
            continue
        g = _geometry(b, t)
        if g is None:
            continue
        T = int(b["tk"][t["entry"]])
        cands = [s for s in pool.get(T, []) if s != t["symbol"]]
        if not cands:
            continue
        rng = np.random.default_rng(zlib.crc32(f"{t['symbol']}|{t['setup']}|{t['d']}|{t['sig']}".encode()))
        got = []
        for _ in range(3 * k):
            if len(got) >= k:
                break
            s = cands[rng.integers(len(cands))]
            bb = data[s]
            j = bb["pos"][T]
            a = bb["atr"][j - 1] if j >= 1 else np.nan
            if not (a > 0):
                continue
            E = bb["open"][j]
            lE, d = np.log(E), t["d"]
            stop = np.exp(lE - d * g["stop"] * a)
            tgt = np.nan if np.isnan(g["target"]) else np.exp(lE + d * g["target"] * a)
            if abs(lE - np.log(stop)) < MIN_RISK_ATR * a:
                continue
            s3 = np.nan if np.isnan(g["s3"]) else np.exp(lE + d * g["s3"] * a)
            jj, px, kind = waves.run_exit(bb["open"], bb["high"], bb["low"], bb["close"], j, E, d, stop, tgt,
                                          t["n_time"], t["limit_fill"], s3, bb["dma"])
            if jj < 0:
                continue
            got.append(r_multiple(d, E, stop, px, cost)[0])
        if len(got) >= MIN_TWINS:
            out[i] = float(np.mean(got))
    return out


def cluster_bootstrap(values, clusters, draws=10_000, seed=0):
    """Mean, 95% interval and one-sided p (share of resampled means <= 0),
    resampling whole clusters with replacement."""
    v = np.asarray(values, float)
    if len(v) == 0:
        return {"mean": None, "lo": None, "hi": None, "p": None, "n": 0, "clusters": 0}
    keys, inv = np.unique(np.asarray(clusters), return_inverse=True)
    sums = np.bincount(inv, weights=v, minlength=len(keys))
    cnts = np.bincount(inv, minlength=len(keys)).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(keys), size=(draws, len(keys)))
    means = sums[pick].sum(1) / np.maximum(cnts[pick].sum(1), 1)
    return {"mean": float(v.mean()), "lo": float(np.percentile(means, 2.5)), "hi": float(np.percentile(means, 97.5)),
            "p": float((means <= 0).mean()), "n": int(len(v)), "clusters": int(len(keys))}


def contrast_bootstrap(va, ca, vb, cb, draws=10_000, seed=0):
    """Mean(a) - mean(b), both resampled by the same clusters."""
    va, vb = np.asarray(va, float), np.asarray(vb, float)
    if len(va) == 0 or len(vb) == 0:
        return {"diff": None, "lo": None, "hi": None, "p": None}
    keys = np.unique(np.concatenate([np.asarray(ca), np.asarray(cb)]))
    ia, ib = np.searchsorted(keys, ca), np.searchsorted(keys, cb)
    sa = np.bincount(ia, weights=va, minlength=len(keys)); na = np.bincount(ia, minlength=len(keys)).astype(float)
    sb = np.bincount(ib, weights=vb, minlength=len(keys)); nb = np.bincount(ib, minlength=len(keys)).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(keys), size=(draws, len(keys)))
    diff = sa[pick].sum(1) / np.maximum(na[pick].sum(1), 1) - sb[pick].sum(1) / np.maximum(nb[pick].sum(1), 1)
    return {"diff": float(va.mean() - vb.mean()), "lo": float(np.percentile(diff, 2.5)),
            "hi": float(np.percentile(diff, 97.5)), "p": float((diff <= 0).mean())}


def bh(pvals):
    """Benjamini-Hochberg adjusted p-values, in the input order."""
    p = np.asarray(pvals, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        running = min(running, p[i] * m / (rank + 1))
        adj[i] = running
    return adj


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    m = len(p)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj


def clusters_of(times, daily):
    ts = pd.DatetimeIndex(times)
    if daily:
        return ts.strftime("%Y-%m").to_numpy()
    iso = ts.isocalendar()
    return (iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)).to_numpy()
