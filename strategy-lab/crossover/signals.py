"""The averages and the crossover rules (PROTOCOL.md, "Rules").

Each rule maps an array of closes to a signal per bar: 1.0 bullish, 0.0 not,
NaN before the bar where the asset's signals count (its 260th).
"""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

WARMUP = 260


def sma(x, n):
    """Mean of the last n values, including the current one; NaN before n exist."""
    x = np.asarray(x, float)
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        out[n - 1:] = sliding_window_view(x, n).mean(axis=1)
    return out


def ema(x, n):
    """Recursive average with weight 2 / (n + 1), started at the first value."""
    return pd.Series(np.asarray(x, float)).ewm(alpha=2 / (n + 1), adjust=False).mean().to_numpy()


def above(a, b):
    """1.0 where a > b (an equal value counts as 0), NaN where either is NaN."""
    out = (a > b).astype(float)
    out[~(np.isfinite(a) & np.isfinite(b))] = np.nan
    return out


def macd(x, fast=12, slow=26):
    return ema(x, fast) - ema(x, slow)


RULES = {
    "R1": ("golden cross, SMA 50/200", lambda c: above(sma(c, 50), sma(c, 200))),
    "R2": ("SMA 20/50", lambda c: above(sma(c, 20), sma(c, 50))),
    "R3": ("MACD line above zero (EMA 12/26)", lambda c: above(ema(c, 12), ema(c, 26))),
    "R4": ("MACD above its signal line", lambda c: above(macd(c), ema(macd(c), 9))),
    "R5": ("EMA 9/21", lambda c: above(ema(c, 9), ema(c, 21))),
}
CONFIRMATORY = list(RULES)
# exploratory reference (X6): price above its 200-bar average, the SPY lab's C1
REFERENCE = {"X6": ("price above SMA 200", lambda c: above(np.asarray(c, float), sma(c, 200)))}


def pair(kind, fast, slow):
    """A fast/slow pair for the exploratory grid (X3)."""
    f = sma if kind == "SMA" else ema
    return lambda c: above(f(c, fast), f(c, slow))


def signal(rule, close):
    """The rule's signal on ``close``; ``rule`` is a name or a function of closes."""
    fn = rule if callable(rule) else {**RULES, **REFERENCE}[rule][1]
    s = fn(np.asarray(close, float))
    s[:WARMUP - 1] = np.nan
    return s
