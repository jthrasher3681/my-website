"""Causal swing pivots and trade simulation for the Elliott Wave study.

Pivots come from an ATR zigzag. In up mode it tracks the highest high since
the last confirmed low, and confirms that high as a pivot on the first later
bar whose low is at least ``k`` x ATR below it. ATR is as of the confirming
bar. Down mode mirrors this. A bar that sets a new extreme can't also confirm
it, because the order of prices inside a bar is unknown. So every pivot has
two bars:

- ``i``, where the extreme printed;
- ``confirm``, the first bar at whose close the pivot is known.

A setup may use a pivot only from ``confirm`` on, and trades enter at the
next bar's open. That is the look-ahead rule the whole study rests on.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

ATR_N = 14


@dataclass(frozen=True)
class Pivot:
    i: int          # bar of the extreme
    price: float
    kind: int       # +1 high, -1 low
    confirm: int    # bar at whose close it is known


def atr(h, l, c, n=ATR_N):
    """Mean true range over the last n bars (NaN until n bars exist)."""
    prev = np.concatenate(([np.nan], c[:-1]))
    tr = np.nanmax(np.vstack([h - l, np.abs(h - prev), np.abs(l - prev)]), axis=0)
    return pd.Series(tr).rolling(n, min_periods=n).mean().to_numpy()


def zigzag(h, l, a, k):
    """Confirmed pivots, alternating high/low, from highs ``h``, lows ``l`` and
    ATR ``a`` with reversal threshold ``k`` x ATR."""
    n = len(h)
    out = []
    start = int(np.argmax(~np.isnan(a))) if np.any(~np.isnan(a)) else n
    if start >= n:
        return out
    mode = 0                       # 0 until the first move of k ATR decides a direction
    hi_i = lo_i = start
    for t in range(start + 1, n):
        if np.isnan(a[t]):
            continue
        if mode == 0:
            if h[t] > h[hi_i]:
                hi_i = t
            if l[t] < l[lo_i]:
                lo_i = t
            up = lo_i < t and h[t] >= l[lo_i] + k * a[t]
            down = hi_i < t and l[t] <= h[hi_i] - k * a[t]
            if up and (not down or lo_i < hi_i):
                out.append(Pivot(lo_i, float(l[lo_i]), -1, t))
                mode, hi_i = 1, int(lo_i + 1 + np.argmax(h[lo_i + 1:t + 1]))
            elif down:
                out.append(Pivot(hi_i, float(h[hi_i]), 1, t))
                mode, lo_i = -1, int(hi_i + 1 + np.argmin(l[hi_i + 1:t + 1]))
        elif mode == 1:
            if h[t] > h[hi_i]:
                hi_i = t                       # a new high can't also confirm it
            elif l[t] <= h[hi_i] - k * a[t]:
                out.append(Pivot(hi_i, float(h[hi_i]), 1, t))
                mode, lo_i = -1, int(hi_i + 1 + np.argmin(l[hi_i + 1:t + 1]))
        else:
            if l[t] < l[lo_i]:
                lo_i = t
            elif h[t] >= l[lo_i] + k * a[t]:
                out.append(Pivot(lo_i, float(l[lo_i]), -1, t))
                mode, hi_i = 1, int(lo_i + 1 + np.argmax(h[lo_i + 1:t + 1]))
    return out


def simulate(o, h, l, c, entry, direction, stop, target, max_hold):
    """One trade entered at ``o[entry]``: exit at the stop, at the target, or at
    the close of the last bar of ``max_hold``. A gap through a level exits at
    the open. When stop and target are both inside one bar, the stop is
    assumed to come first. Returns (exit_bar, exit_price, outcome) with outcome
    "stop", "target" or "time", or None when the data ends first."""
    n = len(o)
    last = entry + max_hold - 1
    if last >= n:
        return None
    d = direction
    for j in range(entry, last + 1):
        if d * (o[j] - stop) <= 0:                     # opened through the stop
            return j, o[j], "stop"
        if target is not None and d * (o[j] - target) >= 0:
            return j, o[j], "target"
        lo, hi = (l[j], h[j]) if d > 0 else (-h[j], -l[j])
        s, t = d * stop, (d * target if target is not None else np.inf)
        if lo <= s:
            return j, stop, "stop"
        if hi >= t:
            return j, target, "target"
    return last, c[last], "time"
