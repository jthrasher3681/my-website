"""Daily portfolio simulation (PROTOCOL.md, "Execution and costs").

A target exposure e decided at a close maps to weights in (SPY, SSO, BIL):
e <= 0 all cash; 0 < e <= 1 e in SPY, the rest cash; 1 < e <= 2 e - 1 in SSO,
2 - e in SPY. A decision is traded at the close ``lag`` sessions later (1 by
default; 0 trades at the signal's own close), or at the next open with
``at_open``. Each trade pays ``cost`` on the value bought and on the value
sold. Exposure that drifts within ``band`` of the target is left alone; a move
to or from zero always trades.
"""
import numpy as np
import pandas as pd

COST = 0.0005
BAND = 0.10
LEVER = np.array([1.0, 2.0, 0.0])      # S&P exposure per unit of SPY, SSO, BIL


def weights(e):
    if e <= 0:
        return np.array([0.0, 0.0, 1.0])
    if e <= 1:
        return np.array([e, 0.0, 1 - e])
    return np.array([2 - e, e - 1, 0.0])


def _needs_trade(target, current, band):
    if (target <= 0) != (current <= 1e-12):
        return True
    return abs(target - current) > max(band, 1e-9)


def run(target, r, start, end, cost=COST, band=BAND, lag=1, at_open=None, record=False):
    """Simulate from the close of the session before ``start`` (when the opening
    position is bought from cash) to ``end``.

    target  exposure decided at each close, on ``r``'s calendar (or reindexable)
    r       daily returns, columns spy / sso / bil
    at_open (overnight, intraday) return frames: trade decisions at the next open
            instead of a close; ``lag`` is then ignored

    Returns a DataFrame indexed from that first close: ``equity`` (starting at 1
    less the opening cost), ``exposure`` (S&P exposure held over the session),
    ``traded`` (1 on sessions with a trade). With ``record``, also each
    instrument's value at the close before and after that close's trade
    (``spy_pre`` .. ``bil_post``; close-execution runs only).
    """
    cal = r.index
    if at_open is not None:
        on, intra = at_open
        cal = cal.intersection(on.index)
        r = r.loc[cal]
        lag = 1
    target = pd.Series(target)
    tgt = target.reindex(target.index.union(cal)).ffill().reindex(cal).to_numpy(float)
    R = r[["spy", "sso", "bil"]].to_numpy(float)
    i0 = cal.searchsorted(pd.Timestamp(start)) - 1
    i1 = cal.searchsorted(pd.Timestamp(end), side="right") - 1
    if i0 < 0:
        raise ValueError("no session before start to buy the opening position")
    # the opening position: the decision at the close before it (lag 1) or at it (lag 0)
    before = target.loc[: cal[i0] - pd.Timedelta(lag, "ns")] if lag else target.loc[: cal[i0]]
    first = before.iloc[-1] if len(before) else np.nan
    if np.isnan(first):
        raise ValueError(f"no target before {cal[i0].date()}")
    v = weights(first) * (1 - cost)
    eq, expo, traded = [v.sum()], [float(LEVER @ weights(first))], [1]
    pre, post = [np.zeros(3)], [v.copy()]
    pending = _decide(tgt[i0], v, band, cal[i0]) if lag == 1 else None
    if at_open is not None:
        ON, ID = on.loc[cal].to_numpy(float), intra.loc[cal].to_numpy(float)
    for i in range(i0 + 1, i1 + 1):
        e_held = float(LEVER @ v) / v.sum()
        did = 0
        if at_open is not None:
            v = v * (1 + ON[i])
            if pending is not None:
                v, did = _trade(v, pending, cost), 1
                pending = None
            e_held = float(LEVER @ v) / v.sum()
            v = v * (1 + ID[i])
            pending = _decide(tgt[i], v, band, cal[i])
        else:
            v = v * (1 + R[i])
            pre.append(v.copy())
            if lag == 1:
                if pending is not None:
                    v, did = _trade(v, pending, cost), 1
                pending = _decide(tgt[i], v, band, cal[i])
            else:
                e = _decide(tgt[i], v, band, cal[i])
                if e is not None:
                    v, did = _trade(v, e, cost), 1
        eq.append(v.sum())
        expo.append(e_held)
        traded.append(did)
        post.append(v.copy())
    out = pd.DataFrame({"equity": eq, "exposure": expo, "traded": traded}, index=cal[i0:i1 + 1])
    if record:
        if at_open is not None:
            raise ValueError("record needs close execution")
        for j, name in enumerate(("spy", "sso", "bil")):
            out[f"{name}_pre"] = [x[j] for x in pre]
            out[f"{name}_post"] = [x[j] for x in post]
    return out


def _decide(e, v, band, day):
    if np.isnan(e):
        raise ValueError(f"no target at {day.date()}")
    current = float(LEVER @ v) / v.sum()
    return e if _needs_trade(e, current, band) else None


def _trade(v, e, cost):
    total = v.sum()
    new = weights(e) * total
    total -= cost * np.abs(new - v).sum()
    return weights(e) * total


def buy_and_hold(r, start, end, leverage=1.0, cost=COST):
    """A constant exposure: 1x is SPY and 2x SSO, never traded; 1.5x is half each,
    rebalanced when it drifts past the band."""
    t = pd.Series(leverage, index=r.index.insert(0, r.index[0] - pd.Timedelta(days=1)))
    return run(t, r, start, end, cost=cost)
