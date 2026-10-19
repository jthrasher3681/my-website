"""Pattern breakouts (PROTOCOL.md, "Patterns").

Everything is written for long breakouts on log prices. Shorts call the same
code on mirrored prices: high <- -log(low), low <- -log(high), close <-
-log(close), so a flat bottom becomes a flat top and a breakdown a breakout.

``scan`` checks every bar t as a possible breakout bar of one pattern and
returns, for each signal, the bar t, the first touch f, the level U, the
tolerance tau, the touch counts and the pattern low (all in the oriented log
prices). Pivots enter only from their confirmation bar (pivot bar + k).
"""
import numpy as np
from numba import njit

from . import pivots as P

AT, HR, H2 = 0, 1, 2
SETUPS = {"AT": (AT, 1), "DT": (AT, -1), "HR": (HR, 1), "HS": (HR, -1), "H2R": (H2, 1), "H2S": (H2, -1)}
CONFIRMATORY = ["AT", "DT", "HR", "HS"]


@njit(cache=True)
def _scan(xh, xl, xc, rng, ph, pl, k, dmin, dmax, mode):
    n = len(xc)
    out = np.empty((n, 7))
    m = 0
    nph, npl = len(ph), len(pl)
    tb = np.empty(nph + npl, np.int64)          # merged touches / lows, scratch
    tk = np.empty(nph + npl, np.int64)
    lb = np.empty(npl, np.int64)
    for t in range(dmin, n):
        # a breakout needs the highest close of at least dmin bars
        hi_prev = -1e300
        for i in range(t - dmin, t):
            if xc[i] > hi_prev:
                hi_prev = xc[i]
        if xc[t] <= hi_prev:
            continue
        # candidate first touches: pivot highs confirmed by t, t - dmax <= f <= t - dmin
        last = -1
        for j in range(nph):
            if ph[j] + k <= t and ph[j] <= t - dmin:
                last = j
        if last < 0:
            continue
        U = -1e300
        maxc = -1e300
        best = -1
        bU = 0.0
        btau = 0.0
        bnT = 0
        bnL = 0
        upto = t                                  # closes [f, t-1] folded into maxc so far: [upto, t-1]
        for j in range(last, -1, -1):
            f = ph[j]
            if f < t - dmax:
                break
            # U over confirmed pivot highs in [f, t]
            for jj in range(j, nph):
                if ph[jj] > t:
                    break
                if ph[jj] + k <= t and xh[ph[jj]] > U:
                    U = xh[ph[jj]]
            for i in range(f, upto):
                if xc[i] > maxc:
                    maxc = xc[i]
            upto = f
            if maxc > U or xc[t] <= U:
                continue
            tau = np.median(rng[f:t + 1])
            if xh[f] < U - tau:
                continue
            # touches and lows
            nT = 0
            for jj in range(j, nph):
                b = ph[jj]
                if b > t:
                    break
                if b + k <= t and xh[b] >= U - tau:
                    tb[nT] = b
                    nT += 1
            nL = 0
            for jj in range(npl):
                b = pl[jj]
                if b > f and b <= t and b + k <= t:
                    lb[nL] = b
                    nL += 1
            ok = False
            if mode == 0:
                if nT >= 2 and nL >= 2 and nT + nL >= 5:
                    inc = True
                    lo_min = 1e300
                    lo_max = -1e300
                    for i in range(nL):
                        v = xl[lb[i]]
                        if i > 0 and v <= xl[lb[i - 1]]:
                            inc = False
                        lo_min = min(lo_min, v)
                        lo_max = max(lo_max, v)
                    if inc and lo_max - lo_min > tau:
                        # alternation of touches (1) and lows (-1) in time order
                        a, b2, q = 0, 0, 0
                        while a < nT or b2 < nL:
                            if b2 >= nL or (a < nT and tb[a] < lb[b2]):
                                tk[q] = 1
                                a += 1
                            elif a >= nT or lb[b2] < tb[a]:
                                tk[q] = -1
                                b2 += 1
                            else:                 # a touch and a low on one bar: not alternating
                                tk[q] = 0
                                a += 1
                                b2 += 1
                            q += 1
                        alt = True
                        for i in range(q):
                            if tk[i] == 0 or (i > 0 and tk[i] == tk[i - 1]):
                                alt = False
                                break
                        if alt:
                            # least-squares line through the lows: rising, below U at t
                            sx = sy = sxx = sxy = 0.0
                            for i in range(nL):
                                xx = float(lb[i])
                                yy = xl[lb[i]]
                                sx += xx
                                sy += yy
                                sxx += xx * xx
                                sxy += xx * yy
                            den = nL * sxx - sx * sx
                            if den > 0:
                                slope = (nL * sxy - sx * sy) / den
                                icpt = (sy - slope * sx) / nL
                                if slope > 0 and icpt + slope * t < U:
                                    ok = True
            else:
                need = 3 if mode == 1 else 2
                if nT >= need:
                    ok = True
                    for i in range(1, nT):
                        found = False
                        for jj in range(npl):
                            b = pl[jj]
                            if b > tb[i - 1] and b < tb[i] and b + k <= t and xl[b] <= U - 2 * tau:
                                found = True
                                break
                        if not found:
                            ok = False
                            break
            if ok:
                best = f
                bU = U
                btau = tau
                bnT = nT
                bnL = nL
        if best >= 0:
            low = 1e300
            for i in range(best, t + 1):
                if xl[i] < low:
                    low = xl[i]
            out[m, 0] = t
            out[m, 1] = best
            out[m, 2] = bU
            out[m, 3] = btau
            out[m, 4] = bnT
            out[m, 5] = bnL
            out[m, 6] = low
            m += 1
    return out[:m]


def oriented(bars, d):
    h, l, c = np.log(bars["high"]), np.log(bars["low"]), np.log(bars["close"])
    if d > 0:
        return h, l, c
    return -l, -h, -c


def scan(bars, setup, k, dmin, dmax):
    """Signals of one setup on one symbol: a list of dicts in real prices.

    level        the flat line (U, or the support level for shorts)
    extreme      the pattern low (longs) or high (shorts): the stop's basis
    """
    mode, d = SETUPS[setup]
    xh, xl, xc = oriented(bars, d)
    rng = np.log(bars["high"]) - np.log(bars["low"])
    ph = P.pivot_highs(xh, k)
    pl = P.pivot_highs(-xl, k)
    ev = _scan(xh, xl, xc, rng, ph, pl, k, dmin, dmax, mode)
    out = []
    for t, f, U, tau, nT, nL, low in ev:
        out.append({"setup": setup, "d": d, "sig": int(t), "first": int(f), "level": float(np.exp(d * U)),
                    "extreme": float(np.exp(d * low)), "tau": float(tau), "touches": int(nT), "lows": int(nL),
                    "n": int(t - f)})
    return out


def orders(bars, setup, k, dmin, dmax, n_time):
    """Market orders for one setup's signals (PROTOCOL.md, "Trades"), in the Elliott
    study's order format (``elliott.execute.run_symbol``)."""
    out = []
    for s in scan(bars, setup, k, dmin, dmax):
        d, U, x = s["d"], s["level"], s["extreme"]
        stop = x * (1 - d * 1e-4)
        target = U + d * abs(U - x)
        if not (target > 0):
            target = np.nan
        out.append({**s, "family": setup, "kind": "market", "stop": float(stop), "target": float(target),
                    "n_time": int(n_time), "s3_level": np.nan, "deadline": int(s["sig"] + 1 + n_time)})
    return out
