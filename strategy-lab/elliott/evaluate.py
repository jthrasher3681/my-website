"""Scoring setups' trades against matched random entries.

A trade is a dict with symbol, sig (the bar at whose close the setup is
known), direction (+1 / -1), stop, target, max_hold and setup. It enters at
the open of bar sig + 1.

- ``R``: the result in multiples of the entry-to-stop distance, after costs
  (``COST`` on each side, as a fraction of price).
- ``ret``: the result as a fraction of the entry price, after costs.

A random twin keeps the trade's direction, holding limit and stop and target
distances, measured in the twin's own ATR at its signal bar, and enters at a
random place:

- ``cross``: another symbol, at the same bar time, that has a bar then and
  next and passes the liquidity rule;
- ``time``: the same symbol, at a random bar in the same calendar year.

``edge`` is a trade's R minus the mean R of its twins. ``cluster_bootstrap``
resamples calendar periods, since trades near in time aren't independent.
"""
import numpy as np
import pandas as pd

from . import waves

COST = 0.0005


def prepare(data):
    """Adds ATR and a time -> bar index map to each symbol's series."""
    for d in data.values():
        if "atr" not in d:
            d["atr"] = waves.atr(d["high"], d["low"], d["close"])
            d["tk"] = d["t"].astype("datetime64[ns]").astype("int64")      # bar times as int ns, for lookups
            d["pos"] = {t: i for i, t in enumerate(d["tk"].tolist())}
    return data


def outcome(d, sig, direction, stop, target, max_hold, cost=COST):
    """(R, ret, kind, exit_bar) for an entry at the open after ``sig``, or None
    when the entry opens beyond the stop or target, or the data ends first."""
    e = sig + 1
    if e >= len(d["open"]):
        return None
    E = d["open"][e]
    if not (E > 0) or direction * (E - stop) <= 0 or (target is not None and direction * (target - E) <= 0):
        return None
    r = waves.simulate(d["open"], d["high"], d["low"], d["close"], e, direction, stop, target, max_hold)
    if r is None:
        return None
    j, px, kind = r
    ret = direction * (px / E - 1) - 2 * cost
    risk = abs(E - stop) / E
    return ret / risk, ret, kind, j


def score(trades, data, cost=COST):
    """Each trade's own result, with its geometry in ATR for the twins."""
    out = []
    for t in trades:
        d = data[t["symbol"]]
        r = outcome(d, t["sig"], t["direction"], t["stop"], t["target"], t["max_hold"], cost)
        if r is None:
            continue
        a = d["atr"][t["sig"]]
        if not (a > 0):
            continue
        E = d["open"][t["sig"] + 1]
        out.append({**t, "R": r[0], "ret": r[1], "kind": r[2], "exit": r[3], "entry_px": E, "t_sig": int(d["tk"][t["sig"]]),
                    "stop_atr": t["direction"] * (E - t["stop"]) / a,
                    "target_atr": None if t["target"] is None else t["direction"] * (t["target"] - E) / a})
    return out


def _twin(d, i, tr, cost):
    a = d["atr"][i]
    if not (a > 0) or i + 1 >= len(d["open"]):
        return None
    E = d["open"][i + 1]
    stop = E - tr["direction"] * tr["stop_atr"] * a
    target = None if tr["target_atr"] is None else E + tr["direction"] * tr["target_atr"] * a
    if tr["direction"] > 0 and stop <= 0:
        return None
    return outcome(d, i, tr["direction"], stop, target, tr["max_hold"], cost)


def twins(scored, data, mode, k=20, seed=0, cost=COST):
    """Mean twin R and ret for each scored trade (fewer than k/2 twins: None)."""
    rng = np.random.default_rng(seed)
    syms = sorted(data)
    by_time = {}
    if mode == "cross":
        for s in syms:
            d = data[s]
            for i, (t, ok) in enumerate(zip(d["tk"].tolist(), d["liquid"])):
                if ok and i + 1 < len(d["t"]):
                    by_time.setdefault(t, []).append(s)
    years = {}
    if mode == "time":
        for s in syms:
            y = pd.DatetimeIndex(data[s]["t"]).year.to_numpy()
            years[s] = {yr: np.flatnonzero(y == yr) for yr in np.unique(y)}
    out = []
    for tr in scored:
        got = []
        if mode == "cross":
            pool = [s for s in by_time.get(tr["t_sig"], []) if s != tr["symbol"]]
            for _ in range(3 * k):
                if len(got) >= k or not pool:
                    break
                s = pool[rng.integers(len(pool))]
                d = data[s]
                i = d["pos"][tr["t_sig"]]
                r = _twin(d, i, tr, cost)
                if r is not None:
                    got.append(r)
        else:
            d = data[tr["symbol"]]
            yr = pd.Timestamp(tr["t_sig"]).year
            cand = years[tr["symbol"]][yr]
            cand = cand[np.abs(cand - tr["sig"]) > tr["max_hold"]]
            for _ in range(3 * k):
                if len(got) >= k or len(cand) == 0:
                    break
                r = _twin(d, int(cand[rng.integers(len(cand))]), tr, cost)
                if r is not None:
                    got.append(r)
        if len(got) < k // 2:
            out.append(None)
        else:
            out.append({"R": float(np.mean([g[0] for g in got])), "ret": float(np.mean([g[1] for g in got])), "n": len(got)})
    return out


def cluster_bootstrap(values, clusters, draws=5000, seed=0):
    """Mean, 95% interval and one-sided p (share of resampled means <= 0) of
    ``values``, resampling whole clusters with replacement."""
    v = np.asarray(values, float)
    c = pd.Series(clusters).to_numpy()
    keys, inv = np.unique(c, return_inverse=True)
    sums = np.bincount(inv, weights=v, minlength=len(keys))
    cnts = np.bincount(inv, minlength=len(keys)).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(keys), size=(draws, len(keys)))
    means = sums[pick].sum(1) / cnts[pick].sum(1)
    return {"mean": float(v.mean()), "lo": float(np.percentile(means, 2.5)), "hi": float(np.percentile(means, 97.5)),
            "p": float((means <= 0).mean()), "n": int(len(v)), "clusters": int(len(keys))}


def holm(pvals):
    """Holm step-down adjusted p-values, in the input order."""
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    m = len(p)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj
