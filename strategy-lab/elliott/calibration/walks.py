"""Path-consistent random walks for calibrating the scoring: each bar is 16
sub-steps of a driftless log random walk (2% a bar) after a small opening gap,
so its open, high, low and close come from one price path."""
import numpy as np


def path_walk(n, seed, vol=0.02, sub=16, gap=0.004, drift=0.0):
    rng = np.random.default_rng(seed)
    o = np.empty(n); h = np.empty(n); l = np.empty(n); c = np.empty(n)
    prev = 100.0
    for t in range(n):
        start = prev * np.exp(rng.normal(0, gap))
        steps = np.exp(np.cumsum(rng.normal(drift / sub, vol / np.sqrt(sub), sub)))
        path = np.concatenate(([start], start * steps))
        o[t], h[t], l[t], c[t] = path[0], path.max(), path.min(), path[-1]
        prev = c[t]
    return o, h, l, c
