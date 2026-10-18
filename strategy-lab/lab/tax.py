"""After-tax estimate for a taxable account (PROTOCOL.md, "Taxes").

Tracks first-in-first-out lots of a recorded run's SPY / SSO / BIL holdings
(``engine.run(..., record=True)``), with each distribution reinvested as a new
lot on its ex-date. Taxes per calendar year:

- short-term gains, and SSO's and BIL's distributions: ``ORDINARY_RATE``;
- long-term gains (lots held more than a year) and SPY's dividends:
  ``LONG_RATE``.

Gains and losses net within each tax year. A net loss carries forward,
keeping its character. Each year's tax is paid at its last session by
trimming every lot pro rata, which realizes nothing.

Trimming keeps the weights, so the run's trades are unchanged. Every lot is
then the pre-tax run's lot times one running factor, and the after-tax account
is the pre-tax run scaled down after each year end. This needs real prices,
so it runs only where all three funds trade (BIL listed 2007-05-30).
Ignored: wash sales, state tax, the $3,000 loss offset against income.
"""
import pandas as pd

from . import data

ORDINARY_RATE, LONG_RATE = 0.35, 0.20
QUALIFIED = {"spy"}
SYMBOLS = {"spy": "SPY", "sso": "SSO", "bil": "BIL"}


def _sell(lots, shares, price, day, out):
    while shares > 1e-12 and lots:
        lot = lots[0]
        take = min(shares, lot[0])
        basis = lot[1] * take / lot[0]
        gain = take * price - basis
        out["lt" if (day - lot[2]).days > 365 else "st"] += gain
        lot[0] -= take
        lot[1] -= basis
        shares -= take
        if lot[0] <= 1e-12:
            lots.pop(0)


def realized(sim, start, end):
    """Per calendar year, the pre-tax run's realized short- and long-term gains,
    qualified dividends and ordinary distributions, from buying the opening
    position at the close before ``start``. Also the gains unrealized at
    ``end`` and the run's equity at each year's last session."""
    part = sim.loc[: end]
    i0 = part.index.searchsorted(pd.Timestamp(start)) - 1
    part = part.iloc[i0:]
    px = {k: data.load(s)[["close", "dividends"]].reindex(part.index) for k, s in SYMBOLS.items()}
    lots = {k: [] for k in SYMBOLS}
    years = {}
    d0 = part.index[0]
    for k in SYMBOLS:
        v = part[f"{k}_post"].iloc[0]
        if v > 0:
            lots[k].append([v / px[k]["close"].iloc[0], v, d0])
    for i in range(1, len(part)):
        day = part.index[i]
        y = years.setdefault(day.year, {"st": 0.0, "lt": 0.0, "qualified": 0.0, "ordinary": 0.0})
        for k in SYMBOLS:
            p, d = px[k]["close"].iloc[i], px[k]["dividends"].iloc[i]
            shares = sum(l[0] for l in lots[k])
            if d > 0 and shares > 0:
                cash = shares * d
                y["qualified" if k in QUALIFIED else "ordinary"] += cash
                lots[k].append([cash / p, cash, day])
                shares += cash / p
            have, want = shares * p, part[f"{k}_post"].iloc[i]
            if want < have - 1e-12:
                _sell(lots[k], (have - want) / p, p, day, y)
            elif want > have + 1e-12:
                lots[k].append([(want - have) / p, want - have, day])
    last = part.index[-1]
    unreal = {"st": 0.0, "lt": 0.0}
    for k in SYMBOLS:
        p = px[k]["close"].iloc[-1]
        for sh, basis, bought in lots[k]:
            unreal["lt" if (last - bought).days > 365 else "st"] += sh * p - basis
    year_end = part["equity"].groupby(part.index.year).last()
    return years, unreal, year_end, part["equity"]


def _net(st, lt, cf):
    st, lt = st + cf["st"], lt + cf["lt"]
    if st < 0 < lt or lt < 0 < st:
        x = st + lt
        st, lt = (x, 0.0) if (x >= 0) == (st > 0) else (0.0, x)
    return max(st, 0.0), max(lt, 0.0), {"st": min(st, 0.0), "lt": min(lt, 0.0)}


def after_tax(sim, start, end):
    """End value per dollar invested at the close before ``start``: before tax,
    after tax as held, and after tax liquidated at ``end``; plus each year's
    tax as a share of the account."""
    years, unreal, year_end, eq = realized(sim, start, end)
    v0 = eq.iloc[0]
    scale, cf, paid = 1.0, {"st": 0.0, "lt": 0.0}, {}
    final_year = eq.index[-1].year
    held = liquidated = None
    for yr in sorted(years):
        a = years[yr]
        income = ORDINARY_RATE * a["ordinary"] + LONG_RATE * a["qualified"]
        st, lt, new_cf = _net(a["st"], a["lt"], cf)
        tax = scale * (ORDINARY_RATE * st + LONG_RATE * lt + income)
        wealth = scale * year_end[yr]
        if yr == final_year:
            held = (wealth - tax) / v0
            st2, lt2, _ = _net(a["st"] + unreal["st"], a["lt"] + unreal["lt"], cf)
            tax2 = scale * (ORDINARY_RATE * st2 + LONG_RATE * lt2 + income)
            liquidated = (wealth - tax2) / v0
        paid[yr] = tax / wealth
        cf = new_cf
        if yr != final_year:
            # amounts are in the pre-tax run's units: the account shrinks by the tax paid,
            # a loss carried forward keeps its dollars, so in those units it grows
            scale *= 1 - tax / wealth
            cf = {k: v / (1 - tax / wealth) for k, v in cf.items()}
    days = (eq.index[-1] - eq.index[0]).days
    ann = lambda x: x ** (365.25 / days) - 1
    pre = eq.iloc[-1] / v0
    return {"pre_tax": pre, "after_tax_held": held, "after_tax_liquidated": liquidated,
            "cagr_pre_tax": ann(pre), "cagr_after_tax_held": ann(held), "cagr_after_tax_liquidated": ann(liquidated),
            "tax_paid_share_by_year": paid}
