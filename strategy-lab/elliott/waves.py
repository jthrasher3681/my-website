"""Causal swing pivots, the Elliott Wave Oscillator, and trade exits
(PROTOCOL.md, "Swing pivots" and "Execution").

Pivots come from an ATR zigzag in log prices:

- ATR is Wilder's 14-bar average of the log true range.
- In up mode the zigzag tracks the highest high since the last confirmed
  low. The high is confirmed as a pivot on the first later bar whose close
  is at least theta = k x ATR below it, with ATR as of the extreme's bar
  (frozen there). Down mode mirrors this.
- A bar that makes a new extreme cannot also confirm it.
- Each pivot has two bars: ``e``, where the extreme printed, and ``c``, the
  first bar at whose close the pivot is known. A pattern may use a pivot
  only from ``c`` on, which is the study's look-ahead rule.
- The first confirmed pivot only sets the direction and is flagged so
  patterns skip it.
"""
import numpy as np
from numba import njit

ATR_N = 14
WARMUP = 50


@njit(cache=True)
def log_atr(h, l, c, n=ATR_N):
    """Wilder ATR of the log true range (NaN before bar n - 1)."""
    m = len(h)
    tr = np.empty(m)
    out = np.full(m, np.nan)
    for t in range(m):
        hl = np.log(h[t]) - np.log(l[t])
        if t == 0:
            tr[t] = hl
        else:
            pc = np.log(c[t - 1])
            tr[t] = max(hl, abs(np.log(h[t]) - pc), abs(np.log(l[t]) - pc))
    if m < n:
        return out
    out[n - 1] = tr[:n].mean()
    for t in range(n, m):
        out[t] = ((n - 1) * out[t - 1] + tr[t]) / n
    return out


@njit(cache=True)
def _zigzag(h, l, c, a, k, start):
    m = len(h)
    e_out = np.empty(m, np.int64)
    c_out = np.empty(m, np.int64)
    kind = np.empty(m, np.int64)
    price = np.empty(m)
    n = 0
    if start >= m:
        return e_out[:0], c_out[:0], kind[:0], price[:0]
    lh, ll, lc = np.log(h), np.log(l), np.log(c)
    mode = 0
    eh = el = start
    th = tl = k * a[start]
    for t in range(start + 1, m):
        if mode == 0:
            newh = h[t] > h[eh]
            newl = l[t] < l[el]
            if newh:
                eh = t
                th = k * a[t]
            if newl:
                el = t
                tl = k * a[t]
            up = (not newl) and el < t and lc[t] >= ll[el] + tl
            down = (not newh) and eh < t and lc[t] <= lh[eh] - th
            if up and (not down or el < eh):
                e_out[n], c_out[n], kind[n], price[n] = el, t, -1, l[el]
                n += 1
                mode = 1
                eh = el + 1
                for j in range(el + 1, t + 1):
                    if h[j] > h[eh]:
                        eh = j
                th = k * a[eh]
            elif down:
                e_out[n], c_out[n], kind[n], price[n] = eh, t, 1, h[eh]
                n += 1
                mode = -1
                el = eh + 1
                for j in range(eh + 1, t + 1):
                    if l[j] < l[el]:
                        el = j
                tl = k * a[el]
        elif mode == 1:
            if h[t] > h[eh]:
                eh = t
                th = k * a[t]
            elif lc[t] <= lh[eh] - th:
                e_out[n], c_out[n], kind[n], price[n] = eh, t, 1, h[eh]
                n += 1
                mode = -1
                el = eh + 1
                for j in range(eh + 1, t + 1):
                    if l[j] < l[el]:
                        el = j
                tl = k * a[el]
        else:
            if l[t] < l[el]:
                el = t
                tl = k * a[t]
            elif lc[t] >= ll[el] + tl:
                e_out[n], c_out[n], kind[n], price[n] = el, t, -1, l[el]
                n += 1
                mode = 1
                eh = el + 1
                for j in range(el + 1, t + 1):
                    if h[j] > h[eh]:
                        eh = j
                th = k * a[eh]
    return e_out[:n], c_out[:n], kind[:n], price[:n]


def pivots(h, l, c, k, a=None):
    """Confirmed pivots as a dict of arrays: e (extreme bar), c (confirmation
    bar), kind (+1 high, -1 low), p (price). Index 0 is the start pivot,
    which patterns skip."""
    if a is None:
        a = log_atr(h, l, c)
    e, cc, kd, p = _zigzag(np.asarray(h, float), np.asarray(l, float), np.asarray(c, float), a, float(k), WARMUP)
    return {"e": e, "c": cc, "kind": kd, "p": p}


def sma(x, n):
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        cs = np.cumsum(np.concatenate(([0.0], x)))
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def ewo(h, l):
    """SMA5 - SMA35 of the bar midpoint."""
    mid = (np.asarray(h, float) + np.asarray(l, float)) / 2
    return sma(mid, 5) - sma(mid, 35)


def dma(c):
    """6-bar simple average of closes displaced 4 bars: mean(close[t-9..t-4])."""
    s = sma(np.asarray(c, float), 6)
    out = np.full(len(s), np.nan)
    out[4:] = s[:-4]
    return out


@njit(cache=True)
def run_exit(o, h, l, c, entry, entry_px, d, stop, target, n_time, limit_fill, s3_level, dma_arr):
    """Exit of one trade (PROTOCOL.md, "Execution").

    entry       bar of the fill; entry_px its price
    d           +1 long, -1 short
    target      NaN for none
    n_time      time exit at the close of bar entry + n_time
    limit_fill  True when filled by a limit inside the entry bar: the stop is
                checked on that bar, the target is not
    s3_level    NaN, or S3's wave-3 extreme: after a bar trades beyond it,
                exit at the next open after the first close beyond the DMA
                the other way
    Returns (exit_bar, exit_price, kind) with kind 0 stop, 1 target, 2 time,
    3 DMA exit; exit_bar -1 when the data ends first."""
    last = entry + n_time
    m = len(o)
    if last >= m:
        return -1, np.nan, -1
    beyond = False
    for j in range(entry, last + 1):
        if j > entry or not limit_fill:
            if j > entry:
                if d * (o[j] - stop) <= 0:
                    return j, o[j], 0
                if not np.isnan(target) and d * (o[j] - target) >= 0:
                    return j, o[j], 1
        lo = l[j] if d > 0 else -h[j]
        hi = h[j] if d > 0 else -l[j]
        if lo <= d * stop:
            return j, stop, 0
        if (j > entry or not limit_fill) and not np.isnan(target) and hi >= d * target:
            return j, target, 1
        if not np.isnan(s3_level):
            if hi >= d * s3_level:
                beyond = True
            if beyond and d * (c[j] - dma_arr[j]) < 0 and j < last:
                return j + 1, o[j + 1], 3
    return last, c[last], 2
