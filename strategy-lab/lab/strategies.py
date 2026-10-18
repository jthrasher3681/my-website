"""Target exposure rules (PROTOCOL.md, "Candidates").

Each rule maps the ^GSPC close (its own sessions) to the S&P exposure, 0 to 2,
decided at each close. ``CANDIDATES`` holds the five pre-registered rules with
their published parameters.
"""
import numpy as np
import pandas as pd

LAMBDA = 0.94
VOL_TARGET = 0.15
CAP = 2.0
VOL_SEED_YEAR = "1961"


def above_sma(px, n=200):
    """1.0 where the close is above its n-session simple average, 0.0 below, NaN
    until n sessions exist."""
    sma = px.rolling(n, min_periods=n).mean()
    return (px > sma).astype(float).where(sma.notna())


def month_ends(index):
    """Sessions whose next session falls in a later month (the last session of the
    data is never one: its month may not be over)."""
    nxt = index[1:].to_period("M")
    return index[:-1][nxt != index[:-1].to_period("M")]


def above_monthly_sma(px, months=10):
    """Decided at each month-end close: 1.0 if it is above the average of the last
    ``months`` month-end closes (itself included), else 0.0; carried until the
    next month end."""
    me = px.loc[month_ends(px.index)]
    sma = me.rolling(months, min_periods=months).mean()
    sig = (me > sma).astype(float).where(sma.notna())
    return sig.reindex(px.index).ffill()


def ewma_vol(px, lam=LAMBDA, seed_year=VOL_SEED_YEAR):
    """Annualized EWMA volatility of daily returns: var_t = lam * var_{t-1} +
    (1 - lam) * r_t^2, seeded with the mean square of the first 21 returns of
    ``seed_year`` and run forward from the session after them."""
    r = px.pct_change().loc[seed_year:].dropna()
    out = np.full(len(r), np.nan)
    x = r.to_numpy()
    var = np.mean(x[:21] ** 2)
    out[20] = var
    for i in range(21, len(x)):
        var = lam * var + (1 - lam) * x[i] ** 2
        out[i] = var
    return pd.Series(np.sqrt(252 * out), index=r.index).reindex(px.index)


def vol_target(px, target=VOL_TARGET, cap=CAP, lam=LAMBDA):
    return np.minimum(cap, target / ewma_vol(px, lam))


CANDIDATES = {
    "C1": ("200-day average, 1x", lambda px: above_sma(px, 200)),
    "C2": ("200-day average, 2x", lambda px: 2 * above_sma(px, 200)),
    "C3": ("10-month average, 2x", lambda px: 2 * above_monthly_sma(px, 10)),
    "C4": ("15% volatility target, cap 2x", lambda px: vol_target(px)),
    "C5": ("200-day average x 15% volatility target", lambda px: above_sma(px, 200) * vol_target(px)),
}

# the finalist's in-sample robustness variants (PROTOCOL.md, "Choosing the finalist" 3)
VARIANTS = {
    "C1": {"150-day": lambda px: above_sma(px, 150), "250-day": lambda px: above_sma(px, 250)},
    "C2": {"150-day": lambda px: 2 * above_sma(px, 150), "250-day": lambda px: 2 * above_sma(px, 250)},
    "C3": {"8-month": lambda px: 2 * above_monthly_sma(px, 8), "12-month": lambda px: 2 * above_monthly_sma(px, 12)},
    "C4": {"12% target": lambda px: vol_target(px, 0.12), "18% target": lambda px: vol_target(px, 0.18),
           "lambda 0.97": lambda px: vol_target(px, lam=0.97)},
    "C5": {"150-day": lambda px: above_sma(px, 150) * vol_target(px), "250-day": lambda px: above_sma(px, 250) * vol_target(px),
           "12% target": lambda px: above_sma(px, 200) * vol_target(px, 0.12),
           "18% target": lambda px: above_sma(px, 200) * vol_target(px, 0.18),
           "lambda 0.97": lambda px: above_sma(px, 200) * vol_target(px, lam=0.97)},
}
