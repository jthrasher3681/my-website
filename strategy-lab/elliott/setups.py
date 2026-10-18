"""Signals of the pre-registered setups (PROTOCOL.md, "Setups").

``orders(bars, piv)`` returns every order the setups place on one symbol,
before the one-slot rule (``execute.py``). Each order is a dict:

- setup: the variant, e.g. "S1", "S1-base", "F2-618", "F2-c437", "S5-c085";
- family; d (+1 long, -1 short); sig (the bar at whose close it is known);
- kind: "market" (fills at the open of sig + 1) or "limit";
- for limits: limit, cancel_level (cancel when price trades beyond it
  against the order's direction of travel: above it for a buy), cancel_open
  (cancel when a bar opens at or beyond it), expiry (last bar it may fill);
- stop, target (NaN for none), n_time (time exit at fill bar + n_time),
  s3_level (NaN except S3), deadline (the last bar its life can reach).

Long patterns are written with P0 a low. Every condition is applied as
``d * (...)`` so the short mirror is the same code with d = -1. Patterns
never use pivot 0 (the zigzag's start pivot).
"""
import numpy as np

from . import waves

TICK = 1e-4
F2_SETUP = {"F2-618": 0.618, "F2-500": 0.500}
F2_CONTROL = {"F2-c437": 0.437, "F2-c556": 0.556, "F2-c697": 0.697}
F4_SETUP = {"F4-382": 0.382}
F4_CONTROL = {"F4-c309": 0.309, "F4-c437": 0.437}
F4_EXPLORE = {"F4-236": 0.236}
S5_LEVELS = {"S5": 1.0, "S5-c085": 0.85, "S5-c115": 1.15}


def _k1(wa, wb, da, db):
    """Neely's similarity: price or time ratio of two adjacent legs >= 1/3."""
    return min(wa, wb) / max(wa, wb) >= 1 / 3 or (max(da, db) > 0 and min(da, db) / max(da, db) >= 1 / 3)


def _stop(level, d):
    return level * (1 - d * TICK)


def _market(setup, family, d, sig, stop, target, n_time, s3_level=np.nan):
    return {"setup": setup, "family": family, "d": d, "sig": int(sig), "kind": "market", "stop": float(stop),
            "target": float(target), "n_time": int(n_time), "s3_level": float(s3_level),
            "deadline": int(sig + 1 + n_time)}


def _limit(setup, family, d, sig, limit, cancel_level, cancel_open, expiry, stop, target, n_time):
    return {"setup": setup, "family": family, "d": d, "sig": int(sig), "kind": "limit", "limit": float(limit),
            "cancel_level": float(cancel_level), "cancel_open": float(cancel_open), "expiry": int(expiry),
            "stop": float(stop), "target": float(target), "n_time": int(n_time), "s3_level": np.nan,
            "deadline": int(expiry + n_time)}


def pivot_setups(bars, piv):
    """S1, S2, S5, F2, F4 and their baselines / controls, plus exploratory S4 and S6."""
    c = bars["close"]
    e, cc, kind, p = piv["e"], piv["c"], piv["kind"], piv["p"]
    x = np.log(p)
    n = len(p)
    ew = waves.ewo(bars["high"], bars["low"])
    out = []
    for j in range(1, n):
        # direction of the pattern whose last pivot is j: a low ends a long wave-2 / wave-4 / C,
        # a high ends a long wave-1 / wave-3 / B
        last_low = kind[j] == -1
        # --- patterns ending at a correction low (long) / high (short): S1 and S2
        d = 1 if last_low else -1
        if j >= 4:                                   # S1 on P_-1, P0, P1, P2 = j-3 .. j
            m1, p0, p1, p2 = j - 3, j - 2, j - 1, j
            W1, W2 = abs(x[p1] - x[p0]), abs(x[p2] - x[p1])
            D1, D2 = e[p1] - e[p0], e[p2] - e[p1]
            if d * (x[p1] - x[m1]) > 0 and d * (x[p2] - x[p0]) > 0 and _k1(W1, W2, D1, D2):
                r2 = W2 / W1
                setup = "S1" if 0.50 <= r2 <= 0.786 else "S1-base"
                tgt = np.exp(x[p2] + d * 1.618 * W1)
                out.append(_market(setup, "S1", d, cc[j], _stop(p[p0], d), tgt, 3 * D1))
        if j >= 5:                                   # S2 on P0 .. P4 = j-4 .. j
            q0, q1, q2, q3, q4 = j - 4, j - 3, j - 2, j - 1, j
            W1, W2, W3, W4 = (abs(x[b] - x[a]) for a, b in ((q0, q1), (q1, q2), (q2, q3), (q3, q4)))
            D1, D2, D3, D4 = (e[b] - e[a] for a, b in ((q0, q1), (q1, q2), (q2, q3), (q3, q4)))
            if (d * (x[q2] - x[q0]) > 0 and d * (x[q3] - x[q1]) > 0 and W3 > W1 and d * (x[q4] - x[q1]) > 0
                    and _k1(W1, W2, D1, D2) and _k1(W2, W3, D2, D3) and _k1(W3, W4, D3, D4)):
                r4 = W4 / W3
                setup = "S2" if 0.236 <= r4 <= 0.50 else "S2-base"
                if W3 >= 1.618 * W1:
                    tgt = np.exp(x[q4] + d * W1)
                else:
                    tgt = np.exp(x[q4] + d * 0.618 * abs(x[q3] - x[q0]))
                out.append(_market(setup, "S2", d, cc[j], _stop(p[q1], d), tgt, 3 * D1))
        # --- patterns ending at an impulse extreme: F2 (wave 1 done), F4 (wave 3 done), S5 (B done)
        d = -1 if last_low else 1                    # a high ends a long wave 1 / wave 3 / B
        if j >= 3:                                   # F2 on P_-1, P0, P1 = j-2 .. j
            m1, p0, p1 = j - 2, j - 1, j
            if d * (x[p1] - x[m1]) > 0:
                D1 = e[p1] - e[p0]
                for setup, f in {**F2_SETUP, **F2_CONTROL}.items():
                    L = p[p1] - f * (p[p1] - p[p0])
                    if d * (c[cc[j]] - L) <= 0:
                        continue
                    stop = _stop(p[p0], d)
                    out.append(_limit(setup, "F2", d, cc[j], L, p[p1], stop, cc[j] + 3 * D1, stop,
                                      L + 1.618 * (p[p1] - p[p0]), 3 * D1))
        if j >= 4:                                   # F4 on P0 .. P3 = j-3 .. j
            q0, q1, q2, q3 = j - 3, j - 2, j - 1, j
            W1, W2, W3 = (abs(x[b] - x[a]) for a, b in ((q0, q1), (q1, q2), (q2, q3)))
            D1, D2, D3 = (e[b] - e[a] for a, b in ((q0, q1), (q1, q2), (q2, q3)))
            if (d * (x[q2] - x[q0]) > 0 and d * (x[q3] - x[q1]) > 0 and W3 > W1
                    and _k1(W1, W2, D1, D2) and _k1(W2, W3, D2, D3)):
                for setup, f in {**F4_SETUP, **F4_CONTROL, **F4_EXPLORE}.items():
                    L = p[q3] - f * (p[q3] - p[q2])
                    if d * (L - p[q1]) <= 0 or d * (c[cc[j]] - L) <= 0:
                        continue
                    stop = _stop(p[q1], d)
                    out.append(_limit(setup, "F4", d, cc[j], L, p[q3], stop, cc[j] + 3 * D1, stop,
                                      L + (p[q1] - p[q0]), 3 * D1))
        if j >= 5:                                   # S5 on P_-1, Q, A0, A1, B = j-4 .. j
            m1, qq, a0, a1, bb = j - 4, j - 3, j - 2, j - 1, j
            A = abs(x[a0] - x[a1])
            Bl = abs(x[bb] - x[a1])
            DA, DB = e[a1] - e[a0], e[bb] - e[a1]
            if d * (x[a0] - x[m1]) > 0 and 0.382 <= Bl / A <= 0.786 and _k1(A, Bl, DA, DB):
                V = np.exp(x[bb] - d * 1.618 * A)
                for setup, mult in S5_LEVELS.items():
                    U = np.exp(x[bb] - d * mult * A)
                    out.append(_limit(setup, "S5", d, cc[j], U, p[bb], V, cc[j] + 3 * DA, _stop(V, d), p[a0], 3 * DA))
        # --- exploratory fades of a completed five-wave move, at the confirmation of P5
        if j >= 6:
            q = list(range(j - 5, j + 1))            # P0 .. P5; P5 is the end of the impulse
            dd = 1 if kind[j] == 1 else -1           # impulse direction; the fade trades -dd
            W = [abs(x[q[i + 1]] - x[q[i]]) for i in range(5)]
            D = [e[q[i + 1]] - e[q[i]] for i in range(5)]
            k1_all = all(_k1(W[i], W[i + 1], D[i], D[i + 1]) for i in range(4))
            base = dd * (x[q[2]] - x[q[0]]) > 0 and dd * (x[q[3]] - x[q[1]]) > 0 and dd * (x[q[5]] - x[q[3]]) > 0
            if base and k1_all and dd * (x[q[4]] - x[q[1]]) > 0 and W[2] > min(W[0], W[4]):
                o4 = _s4(bars, ew, e, cc, p, q, dd)
                if o4 is not None:
                    out.append(o4)
            if (base and k1_all and dd * (x[q[4]] - x[q[2]]) > 0 and dd * (x[q[4]] - x[q[1]]) < 0
                    and W[2] < W[0] and W[3] < W[1] and W[4] < W[2]):
                s24 = (x[q[4]] - x[q[2]]) / max(1, e[q[4]] - e[q[2]])
                s13 = (x[q[3]] - x[q[1]]) / max(1, e[q[3]] - e[q[1]])
                if dd * s24 > dd * s13 > 0:
                    o6 = _s6(bars, e, cc, p, q, dd)
                    if o6 is not None:
                        out.append(o6)
    return out


def _s4(bars, ew, e, cc, p, q, dd):
    """S4: fade the impulse once a close crosses back through the DMA (exploratory)."""
    e2, e3, e4, e5 = e[q[2]], e[q[3]], e[q[4]], e[q[5]]
    E3 = dd * np.nanmax(dd * ew[e2:e3 + 1])
    # in the impulse's direction: E3 > 0, the oscillator back to within 10% of zero in wave 4,
    # and a lower peak in wave 5 (all written for dd * EWO)
    if not (dd * E3 > 0) or not (np.nanmin(dd * ew[e3:e4 + 1]) <= 0.10 * dd * E3):
        return None
    if not (np.nanmax(dd * ew[e4:e5 + 1]) < dd * E3):
        return None
    c5 = cc[q[5]]
    t_exit = e5 + (e5 - e4)
    dm = waves.dma(bars["close"]) if "dma" not in bars else bars["dma"]
    hi, lo, cl = bars["high"], bars["low"], bars["close"]
    for t in range(c5, min(t_exit, len(cl) - 1)):
        if dd * ((hi if dd > 0 else lo)[t] - p[q[5]]) > 0 or dd * ((lo if dd > 0 else hi)[t] - p[q[4]]) <= 0:
            return None
        if dd * (cl[t] - dm[t]) < 0:
            n_time = t_exit - (t + 1)
            if n_time <= 0:
                return None
            return _market("S4", "S4", -dd, t, _stop(p[q[5]], -dd), p[q[4]], n_time)
    return None


def _s6(bars, e, cc, p, q, dd):
    """S6: fade an ending diagonal on a close back through P4 (exploratory)."""
    e0, e5 = e[q[0]], e[q[5]]
    t_exit = e5 + int(np.ceil(0.5 * (e5 - e0)))
    hi, lo, cl = bars["high"], bars["low"], bars["close"]
    for t in range(cc[q[5]], min(t_exit, len(cl) - 1)):
        if dd * ((hi if dd > 0 else lo)[t] - p[q[5]]) > 0:
            return None
        if dd * (cl[t] - p[q[4]]) < 0:
            n_time = t_exit - (t + 1)
            if n_time <= 0:
                return None
            return _market("S6", "S6", -dd, t, _stop(p[q[5]], -dd), p[q[0]], n_time)
    return None


def s3_orders(bars, baseline=False):
    """S3 (EWO wave-4 pullback) or its baseline, both directions."""
    h, l, c = bars["high"], bars["low"], bars["close"]
    ew = waves.ewo(h, l)
    dm = waves.dma(c)
    n = len(c)
    out = []
    win = 150
    # trailing 150-bar max / min and population std of EWO
    s = np.lib.stride_tricks.sliding_window_view
    roll_max = np.full(n, np.nan); roll_min = np.full(n, np.nan); roll_sd = np.full(n, np.nan)
    if n >= win:
        w = s(ew, win)
        roll_max[win - 1:] = np.max(w, axis=1)
        roll_min[win - 1:] = np.min(w, axis=1)
        roll_sd[win - 1:] = np.std(w, axis=1)
    for d in (1, -1):
        name = "S3-base" if baseline else "S3"
        cand = None          # (s3, M)
        armed = None         # dict
        for t in range(334, n):
            E = ew[t]
            if np.isnan(E) or np.isnan(dm[t]) or np.isnan(dm[t - 1]):
                continue
            if armed is not None:
                M = armed["M"]
                cancel = (d * (h if d > 0 else l)[t] > d * armed["P3"]) or t > armed["t4"] + 35
                if not baseline and d * E < -0.40 * d * M:
                    cancel = True
                if cancel:
                    armed = None
                elif d * (c[t] - dm[t]) > 0 and d * (c[t - 1] - dm[t - 1]) <= 0:
                    if t + 1 < n:
                        seg = slice(armed["e3"], t + 1)
                        ext = np.min(l[seg]) if d > 0 else np.max(h[seg])
                        out.append(_market(name, "S3", d, t, _stop(ext, d), np.nan, 35, s3_level=armed["P3"]))
                    armed = None
                continue
            extreme = (E == roll_max[t]) if d > 0 else (E == roll_min[t])
            if extreme and d * E > 0 and (baseline or abs(E) >= 2.0 * roll_sd[t]):
                cand = (t, E)
                continue
            if cand is None:
                continue
            s3, M = cand
            arm = False
            if baseline:
                arm = d * (c[t] - dm[t]) < 0
            else:
                if d * E < -0.40 * d * M:
                    cand = None
                    continue
                arm = d * E <= 0.10 * d * M
            if arm:
                seg = slice(s3, t + 1)
                if d > 0:
                    e3 = s3 + int(np.argmax(h[seg])); P3 = h[e3]
                else:
                    e3 = s3 + int(np.argmin(l[seg])); P3 = l[e3]
                armed = {"M": M, "t4": t, "P3": P3, "e3": e3}
                cand = None
                # the trigger may come on the arming bar itself
                if d * (c[t] - dm[t]) > 0 and d * (c[t - 1] - dm[t - 1]) <= 0 and t + 1 < n:
                    ext = np.min(l[e3:t + 1]) if d > 0 else np.max(h[e3:t + 1])
                    out.append(_market(name, "S3", d, t, _stop(ext, d), np.nan, 35, s3_level=P3))
                    armed = None
    return out


def orders(bars, piv):
    return pivot_setups(bars, piv) + s3_orders(bars) + s3_orders(bars, baseline=True)
