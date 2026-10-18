"""Return and signal series for the strategy lab (PROTOCOL.md, "Data").

Every loader takes ``end``: nothing after that date is read, so an in-sample
run cannot see held-out prices even by accident.

Series, all on one trading calendar, as daily simple returns:

- ``spy``: S&P 1x. SPY total return from its listing (1993-01-29); before that
  ``^SP500TR`` less SPY's expense ratio.
- ``sso``: S&P 2x. SSO total return from its listing (2006-06-21); before that
  ``2 * spy - bil - c / 252``, with ``c`` calibrated by ``calibrate_2x``.
- ``bil``: cash. BIL total return from its listing (2007-05-30); before that
  the previous close's 13-week T-bill rate (``^IRX``) accrued over calendar
  days / 365, less ``CASH_DRAG``.

The stress-test variant (``stress_returns``) runs on ``^GSPC`` alone: price
return plus ``STRESS_YIELD`` a year.
"""
import os
import numpy as np
import pandas as pd

YAHOO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "yahoo")
SPY_ER = 0.000945            # SPY expense ratio, a year
CASH_DRAG = 0.0010           # BIL's shortfall to the accrued T-bill rate, a year
STRESS_YIELD = 0.036         # S&P dividend yield in 1988, the first year of ^SP500TR
CALIBRATION = ("2006-06-22", "2015-12-31")
INSTRUMENTS = ("spy", "sso", "bil")


def load(sym, end=None):
    df = pd.read_csv(os.path.join(YAHOO, sym.replace("^", "_") + ".csv.gz"), index_col=0, parse_dates=True)
    df.index = df.index.astype("datetime64[ns]")
    return df if end is None else df.loc[:end]


def growth(df):
    """Cumulative total-return index from split-adjusted closes plus cash dividends."""
    c = df["close"]
    r = ((c + df["dividends"]) / c.shift(1)).fillna(1.0)
    return r.cumprod()


def on_calendar(g, cal):
    """Daily returns on ``cal`` from a cumulative index on its own dates (a day the
    series lacks earns 0 and the next day earns both)."""
    g = g.reindex(g.index.union(cal)).ffill().reindex(cal)
    return g / g.shift(1) - 1


def calendar(end=None):
    """^SP500TR's sessions before SPY listed, SPY's after."""
    spy = load("SPY", end).index
    tr = load("^SP500TR", end).index
    return tr[tr < spy[0]].append(spy)


def cash_returns(cal, end=None):
    irx = load("^IRX", end)["close"]
    lvl = irx.reindex(irx.index.union(cal)).ffill().reindex(cal)
    days = cal.to_series().diff().dt.days
    r = (lvl.shift(1) / 100 - CASH_DRAG) * days / 365
    bil = load("BIL", end)
    real = on_calendar(growth(bil), cal)
    return r.where(cal <= bil.index[0], real)


def spy_returns(cal, end=None):
    spy = load("SPY", end)
    idx = on_calendar(load("^SP500TR", end)["close"], cal)
    days = cal.to_series().diff().dt.days
    sim = idx - SPY_ER * days / 365
    return sim.where(cal <= spy.index[0], on_calendar(growth(spy), cal))


def simulated_2x(spy, bil, c):
    return 2 * spy - bil - c / 252


def calibrate_2x(spy, bil, sso, window=CALIBRATION):
    """The yearly cost ``c`` that makes simulated 2x end where real SSO does over
    ``window`` (bisection; the end value falls as c rises)."""
    a, b = window
    s, cash, real = spy.loc[a:b], bil.loc[a:b], sso.loc[a:b]
    target = np.log1p(real).sum()
    lo, hi = -0.05, 0.10
    for _ in range(100):
        mid = (lo + hi) / 2
        if np.log1p(simulated_2x(s, cash, mid)).sum() > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def returns(end=None):
    """The three instruments' daily returns on the lab calendar, the yearly 2x cost
    ``c``, and the ^GSPC close (the signal series, on its own dates)."""
    cal = calendar(end)
    spy, bil = spy_returns(cal, end), cash_returns(cal, end)
    sso_df = load("SSO", end)
    real = on_calendar(growth(sso_df), cal)
    c = calibrate_2x(spy, bil, real)
    sso = simulated_2x(spy, bil, c).where(cal <= sso_df.index[0], real)
    r = pd.DataFrame({"spy": spy, "sso": sso, "bil": bil})
    r.iloc[0] = 0.0     # the first session has no return: the runs start at its close
    return r, c, load("^GSPC", end)["close"]


def stress_returns(c, start="1962-01-02", end="1987-12-31"):
    """1x / 2x / cash for the 1962-87 stress test, on ^GSPC's sessions."""
    gspc = load("^GSPC", end)["close"]
    cal = gspc.loc[pd.Timestamp(start) - pd.Timedelta(days=10):].index
    spy = gspc.reindex(cal).pct_change() + STRESS_YIELD / 252
    irx = load("^IRX", end)["close"]
    lvl = irx.reindex(irx.index.union(cal)).ffill().reindex(cal)
    days = cal.to_series().diff().dt.days
    bil = (lvl.shift(1) / 100 - CASH_DRAG) * days / 365
    r = pd.DataFrame({"spy": spy, "sso": simulated_2x(spy, bil, c), "bil": bil})
    r.iloc[0] = 0.0
    return r, gspc


def open_returns(start, end):
    """Overnight (previous close to open, dividend included) and intraday (open to
    close) returns of SPY, SSO and BIL, for the next-open execution check."""
    on, intra = {}, {}
    for name, sym in (("spy", "SPY"), ("sso", "SSO"), ("bil", "BIL")):
        df = load(sym, end)
        on[name] = (df["open"] + df["dividends"]) / df["close"].shift(1) - 1
        intra[name] = df["close"] / df["open"] - 1
    on, intra = pd.DataFrame(on).loc[start:end], pd.DataFrame(intra).loc[start:end]
    keep = on.dropna().index.intersection(intra.dropna().index)
    return on.loc[keep], intra.loc[keep]
