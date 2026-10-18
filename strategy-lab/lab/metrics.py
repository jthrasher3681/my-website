"""Performance statistics and the pass bar (PROTOCOL.md, "Metrics", "Pass bar")."""
import math
import numpy as np
import pandas as pd


def cagr(eq):
    days = (eq.index[-1] - eq.index[0]).days
    return (eq.iloc[-1] / eq.iloc[0]) ** (365.25 / days) - 1


def max_drawdown(eq):
    return float((eq / eq.cummax() - 1).min())


def sharpe(eq, cash):
    r = eq.pct_change().iloc[1:]
    ex = r - cash.reindex(r.index)
    return float(ex.mean() / ex.std() * math.sqrt(252))


def calendar_years(eq):
    """Returns of each full calendar year in the window (a year counts when the
    window holds its whole span: it starts at or before the previous year's last
    session and reaches the year's last session)."""
    ye = eq.groupby(eq.index.year).last()
    out = {}
    for y in ye.index:
        prev = eq.loc[: f"{y - 1}-12-31"]
        if len(prev) == 0 or prev.index[-1].year != y - 1:
            continue
        if eq.index[-1] < pd.Timestamp(f"{y}-12-24"):
            continue
        out[int(y)] = float(ye[y] / prev.iloc[-1] - 1)
    return out


def longest_underwater_years(eq):
    """Longest span from a high to the next one (or to the end), in years."""
    highs = eq.index[(eq >= eq.cummax()).to_numpy()]
    edges = pd.Series(highs.append(pd.DatetimeIndex([eq.index[-1]])))
    gaps = edges.diff().dt.days.dropna() / 365.25
    return float(gaps.max()) if len(gaps) else 0.0


def stats(sim, cash):
    """sim: engine.run output; cash: daily cash returns."""
    eq = sim["equity"]
    r = eq.pct_change().iloc[1:]
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cy = calendar_years(eq)
    worst = min(cy.items(), key=lambda kv: kv[1]) if cy else (None, None)
    expo = sim["exposure"].iloc[1:]
    return {
        "start": str(eq.index[0].date()), "end": str(eq.index[-1].date()),
        "cagr": cagr(eq), "vol": float(r.std() * math.sqrt(252)), "sharpe": sharpe(eq, cash),
        "max_dd": max_drawdown(eq), "worst_year": worst[1], "worst_year_is": worst[0],
        "longest_underwater_years": longest_underwater_years(eq),
        "avg_exposure": float(expo.mean()), "time_in_market": float((expo > 1e-9).mean()),
        "trades_per_year": float(sim["traded"].iloc[1:].sum() / years), "end_value": float(eq.iloc[-1] / eq.iloc[0]),
    }


def passes(s, bench):
    """The three-part bar: higher CAGR, Sharpe at least as high, drawdown no deeper."""
    checks = {"cagr": bool(s["cagr"] > bench["cagr"]), "sharpe": bool(s["sharpe"] >= bench["sharpe"]),
              "max_dd": bool(s["max_dd"] >= bench["max_dd"])}
    return all(checks.values()), checks


def window(sim, start, end):
    """The part of a longer run from the close before ``start`` to ``end``, with
    equity rebased to 1 there (exposure and trades as in the run)."""
    idx = sim.index
    i0 = idx.searchsorted(pd.Timestamp(start)) - 1
    i1 = idx.searchsorted(pd.Timestamp(end), side="right")
    part = sim.iloc[max(i0, 0):i1].copy()
    part["equity"] = part["equity"] / part["equity"].iloc[0]
    part.iloc[0, part.columns.get_loc("traded")] = 0
    return part


def block_shuffle(x, block, rng):
    """x cut into consecutive blocks of ``block`` (the last may be short), in a
    random order."""
    blocks = [x[i:i + block] for i in range(0, len(x), block)]
    order = rng.permutation(len(blocks))
    return np.concatenate([blocks[k] for k in order])


def block_bootstrap_ci(diff, block=63, draws=10_000, seed=0, q=(5, 95)):
    """Circular block bootstrap of the mean of daily log-return differences,
    annualized (x 252)."""
    x = np.asarray(diff, float)
    n = len(x)
    rng = np.random.default_rng(seed)
    k = math.ceil(n / block)
    xx = np.concatenate([x, x[:block]])
    means = np.empty(draws)
    for d in range(draws):
        starts = rng.integers(0, n, k)
        means[d] = np.concatenate([xx[s:s + block] for s in starts])[:n].mean()
    return [float(np.percentile(means, p) * 252) for p in q]
