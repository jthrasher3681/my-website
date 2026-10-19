"""Fractal pivots (PROTOCOL.md, "Swing points").

A pivot high at bar j has a high at least as high as each of the k bars before
it and higher than each of the k bars after it; it is known at the close of
bar j + k. Pivot lows mirror this. A bar can be both.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def _highs(x, k):
    n = len(x)
    e = np.empty(n, np.int64)
    m = 0
    for j in range(k, n - k):
        ok = True
        for i in range(1, k + 1):
            if x[j - i] > x[j] or x[j + i] >= x[j]:
                ok = False
                break
        if ok:
            e[m] = j
            m += 1
    return e[:m]


def pivot_highs(high, k):
    """Bars of pivot highs; each is confirmed at bar + k."""
    return _highs(np.asarray(high, float), k)


def pivot_lows(low, k):
    return _highs(-np.asarray(low, float), k)
