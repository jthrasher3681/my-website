"""Matched plain breakouts (PROTOCOL.md, "Controls" 2).

For a pattern trade signalled at bar time T with duration N, up to 5 other
stocks that pass the liquidity rule at T and make a plain N-bar breakout at
T (and have no signal of the same setup there) are traded with the same
rules: stop at the N-bar extreme, target the breakout level plus the N-bar
range, the same time exit. When none qualifies at T, the nearest bar times
within 5 bars are searched (-1, +1, -2, ...) until one does.
"""
import zlib
import numpy as np

from elliott import execute as X, waves

N_MATCH, SEARCH = 5, 5


def plain(bb, j, N, d, n_time, cost):
    """R of a plain N-bar breakout signalled at bar j of ``bb``, or None."""
    n = len(bb["close"])
    if j - N - 1 < 0 or j + 1 >= n:
        return None
    h, l, c = bb["high"], bb["low"], bb["close"]
    if d > 0:
        lvl, prev = h[j - N:j].max(), h[j - N - 1:j - 1].max()
        if not (c[j] > lvl and c[j - 1] <= prev):
            return None
        ext = l[j - N:j].min()
    else:
        lvl, prev = l[j - N:j].min(), l[j - N - 1:j - 1].min()
        if not (c[j] < lvl and c[j - 1] >= prev):
            return None
        ext = h[j - N:j].max()
    stop = ext * (1 - d * 1e-4)
    target = lvl + d * abs(lvl - ext)
    if not (target > 0):
        target = np.nan
    e = j + 1
    E = bb["open"][e]
    if d * (E - stop) <= 0 or (not np.isnan(target) and d * (target - E) <= 0):
        return None
    a = bb["atr"][e - 1]
    if not (a > 0) or abs(np.log(E) - np.log(stop)) < X.MIN_RISK_ATR * a:
        return None
    jj, px, kind = waves.run_exit(bb["open"], bb["high"], bb["low"], bb["close"], e, E, d, stop, target,
                                  n_time, False, np.nan, bb["dma"])
    if jj < 0:
        return None
    return X.r_multiple(d, E, stop, px, cost)[0]


def matched(trades, data, sig_pool, signals_at, cost):
    """(mean R of the matched plain breakouts, how many) per trade; NaN, 0 when none.

    sig_pool     bar time -> symbols liquid at that bar (``X.twin_pool(lag=0)``)
    signals_at   (symbol, bar time) -> setups signalled there (before the slot rule)
    """
    out = np.full(len(trades), np.nan)
    cnt = np.zeros(len(trades), int)
    offsets = [0] + [s * o for o in range(1, SEARCH + 1) for s in (-1, 1)]
    for i, t in enumerate(trades):
        b = data[t["symbol"]]
        rng = np.random.default_rng(zlib.crc32(f"match|{t['symbol']}|{t['setup']}|{t['d']}|{t['sig']}".encode()))
        got = []
        for off in offsets:
            j0 = t["sig"] + off
            if j0 < 0 or j0 >= len(b["tk"]):
                continue
            T = int(b["tk"][j0])
            cands = [s for s in sig_pool.get(T, []) if s != t["symbol"] and t["setup"] not in signals_at.get((s, T), ())]
            for k in rng.permutation(len(cands)):
                if len(got) >= N_MATCH:
                    break
                bb = data[cands[k]]
                r = plain(bb, bb["pos"][T], t["n"], t["d"], t["n_time"], cost)
                if r is not None:
                    got.append(r)
            if got:
                break
        if got:
            out[i] = float(np.mean(got))
            cnt[i] = len(got)
    return out, cnt
