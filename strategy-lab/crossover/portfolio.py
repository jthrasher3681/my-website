"""Sleeves, equal-weight portfolios and the random-timing null (PROTOCOL.md,
"Execution and costs", "Measures", "The random-timing test").

A ``Panel`` puts every asset on one calendar of bars (the union of their
bars) as T x A arrays. On asset a's own bars i (0, 1, ..):

- r_i = tr_i / tr_{i-1} - 1, its return over bar i;
- h_i = s_{i-2}, the exposure held over bar i (a signal at close i - 2 is
  traded at close i - 1);
- w_i = |h_{i+1} - h_i| = |s_{i-1} - s_{i-2}|, the switch made at close i,
  whose cost falls in bar i;
- liquid at close i - 2 (daily stocks only).

Asset a is a member over bar i when r_i and h_i exist and it is liquid. A
portfolio's return over a bar is the mean of its members' sleeve returns.
"""
import math
import zlib
import numpy as np
import pandas as pd

from lab import metrics

SHIFT_MIN = 260       # bars: past the longest average (200) plus its lag, and EMA memory


class Panel:
    def __init__(self, assets, cash_day, need_liquid=False, source=None):
        """assets   {name: {"t", "close", "tr", "liquid"}}
        cash_day    daily cash returns, indexed by date (normalized); every bar's
                    day must be in it
        source      optional function (asset name, rule) -> the rule's signal on
                    the asset's bars, in place of computing it from ``close``"""
        self.names = sorted(assets)
        self.assets = assets
        cal = np.unique(np.concatenate([assets[s]["t"] for s in self.names]))
        self.cal = pd.DatetimeIndex(cal)
        T, A = len(cal), len(self.names)
        self.T, self.A = T, A
        self.pos = {}
        self.R = np.full((T, A), np.nan)
        self.L = np.zeros((T, A), bool)
        for a, s in enumerate(self.names):
            d = assets[s]
            p = np.searchsorted(cal, d["t"])
            self.pos[s] = p
            tr = np.asarray(d["tr"], float)
            self.R[p[1:], a] = tr[1:] / tr[:-1] - 1
            liq = np.asarray(d["liquid"], bool) if need_liquid else np.ones(len(p), bool)
            self.L[p[2:], a] = liq[:-2]
        self.source = source
        # days: one mark per day at its last bar
        day = self.cal.normalize()
        self.day_of = day
        first = np.r_[True, day[1:] != day[:-1]]
        self.day_start = np.flatnonzero(first)
        self.days = day[first]
        self.daily = bool(len(self.days) == T)
        cd = pd.Series(cash_day).reindex(self.days)
        if cd.isna().any():
            cd = cd.fillna(0.0)
        self.cash_day = cd
        nbars = np.diff(np.r_[self.day_start, T])
        self.c = np.repeat(cd.to_numpy(float) / nbars, nbars)

    # ---- one rule ------------------------------------------------------------
    def rule(self, rule, expo=None):
        """H (exposure held over each bar) and W (the switch at its close), T x A."""
        from .signals import signal
        H = np.full((self.T, self.A), np.nan)
        W = np.full((self.T, self.A), np.nan)
        for a, s in enumerate(self.names):
            if self.source is not None:
                sig = np.asarray(self.source(s, rule), float)
            else:
                sig = signal(rule, self.assets[s]["close"])
            if expo is not None:
                sig = expo(sig)
            p = self.pos[s]
            if len(p) < 3:
                continue
            H[p[2:], a] = sig[:-2]
            W[p[2:], a] = np.abs(sig[1:-1] - sig[:-2])
        return H, W

    def member(self, H):
        return np.isfinite(self.R) & np.isfinite(H) & self.L

    # ---- windows ---------------------------------------------------------------
    def window(self, H, lo, hi=None):
        """First and last bar of [lo, hi] (dates or times), starting at the first
        bar with a member."""
        t0 = self.cal.searchsorted(pd.Timestamp(lo))
        t1 = len(self.cal) - 1 if hi is None else self.cal.searchsorted(pd.Timestamp(hi), side="right") - 1
        n = self.member(H)[t0:t1 + 1].sum(1)
        if not n.any():
            raise ValueError("no member in the window")
        j0 = t0 + int(np.argmax(n > 0))
        # a portfolio starts at the first bar of a day
        d0 = int(np.searchsorted(self.day_start, j0, side="right") - 1)
        if self.day_start[d0] != j0:
            j0 = int(self.day_start[d0 + 1])
        return j0, t1

    def bar_returns(self, H, W, j0, j1, kind="net", cost=0.0):
        """The portfolio's return over bars j0..j1: kind ``net`` (cost a switch),
        ``gross`` or ``hold`` (buy-and-hold of the same members)."""
        sl = slice(j0, j1 + 1)
        M = self.member(H)[sl]
        R, c = self.R[sl], self.c[sl, None]
        if kind == "hold":
            S = R
        else:
            h = H[sl]
            S = h * R + (1 - h) * c
            if kind == "net":
                S = S - cost * np.nan_to_num(W[sl])
        n = M.sum(1)
        out = np.where(M, S, 0.0).sum(1) / np.maximum(n, 1)
        return np.where(n > 0, out, self.c[sl])

    def to_daily(self, x, j0, j1):
        """Bar returns over j0..j1 (j0 the first bar of a day) as daily returns."""
        starts = self.day_start[(self.day_start >= j0) & (self.day_start <= j1)] - j0
        lr = np.log1p(np.asarray(x))
        d = np.expm1(np.add.reduceat(lr, starts, axis=-1))
        return d

    def daily_index(self, j0, j1):
        k = (self.day_start >= j0) & (self.day_start <= j1)
        return self.days[k]

    def equity(self, x, j0, j1):
        """Daily equity, 1 at the mark before the window."""
        d = self.to_daily(x, j0, j1)
        idx = self.daily_index(j0, j1)
        before = self.day_of[j0 - 1] if j0 > 0 else idx[0] - pd.Timedelta(days=1)
        return pd.Series(np.r_[1.0, np.cumprod(1 + d)], index=idx.insert(0, before))

    def exposure_stats(self, H, W, j0, j1):
        sl = slice(j0, j1 + 1)
        M = self.member(H)[sl]
        years = (self.cal[j1] - self.cal[j0]).days / 365.25
        avg_members = M.sum() / (j1 - j0 + 1)
        h = np.where(M, H[sl], 0.0)
        per_bar = h.sum(1) / np.maximum(M.sum(1), 1)
        return {"time_in_market": float(per_bar[M.any(1)].mean()),
                "switches_per_asset_year": float(np.nan_to_num(W[sl])[M].sum() / avg_members / years) if years > 0 else None,
                "mean_members": float(avg_members), "assets": int(M.any(0).sum())}

    # ---- the null --------------------------------------------------------------
    def null_sharpes(self, H, j0, j1, block, draws=1000, seed=0):
        """Gross Sharpe ratios of the portfolio with its held exposures moved in
        blocks of ``block`` bars, in one random order for every asset."""
        c, X, n, hf, cash, real = self._null_parts(H, j0, j1)
        rng = np.random.default_rng(seed)
        idx = np.arange(j1 - j0 + 1)
        out = np.empty(draws)
        for k in range(draws):
            perm = metrics.block_shuffle(idx, block, rng)
            x = c + (X * hf[perm]).sum(1) / n
            out[k] = _sharpe(self.to_daily(x, j0, j1), cash)
        return real, out

    def shift_sharpes(self, H, j0, j1, min_shift=SHIFT_MIN, draws=1000, seed=0):
        """Gross Sharpe ratios with the held exposures shifted in a circle by k
        bars, one k for every asset, min_shift <= k <= T - min_shift (added after
        the independent review; not pre-registered).

        The block shuffle above can set an exposure computed after bar j against
        the return of bar j, which the averages behind that exposure already
        contain, and that look-ahead lifts the draws. A shift of at least the
        averages' memory moves every exposure either well past the returns it
        was computed from, or (after the wrap) to a later bar, so no draw sees
        its own return. Every k is used when there are fewer than ``draws``."""
        c, X, n, hf, cash, real = self._null_parts(H, j0, j1)
        T = j1 - j0 + 1
        ks = np.arange(min_shift, T - min_shift + 1)
        if len(ks) == 0:
            raise ValueError("window too short for the shift null")
        if len(ks) > draws:
            ks = np.sort(np.random.default_rng(seed).choice(ks, draws, replace=False))
        idx = np.arange(T)
        out = np.empty(len(ks))
        for i, k in enumerate(ks):
            x = c + (X * hf[(idx + k) % T]).sum(1) / n
            out[i] = _sharpe(self.to_daily(x, j0, j1), cash)
        return real, out

    def _null_parts(self, H, j0, j1):
        sl = slice(j0, j1 + 1)
        M = self.member(H)[sl]
        h = H[sl]
        c = self.c[sl]
        X = np.where(M, self.R[sl] - c[:, None], 0.0)
        n = np.maximum(M.sum(1), 1)
        mean_a = np.array([h[M[:, a], a].mean() if M[:, a].any() else 0.0 for a in range(self.A)])
        hf = np.where(np.isfinite(h), h, mean_a[None, :])
        cash = self.cash_day.reindex(self.daily_index(j0, j1)).to_numpy(float)
        real = _sharpe(self.to_daily(c + (X * np.nan_to_num(h)).sum(1) / n, j0, j1), cash)
        return c, X, n, hf, cash, real


def _sharpe(daily, cash):
    ex = daily - cash
    return float(ex.mean() / ex.std(ddof=1) * math.sqrt(252))


def seed_of(*parts):
    return zlib.crc32("|".join(map(str, parts)).encode())


def null_test(real, draws):
    return {"real_gross_sharpe": real, "null_mean": float(draws.mean()), "null_sd": float(draws.std()),
            "edge": float(real - draws.mean()), "p": float((1 + (draws >= real).sum()) / (1 + len(draws))),
            "draws": int(len(draws))}


def stats(eq, cash_day):
    """The SPY lab's measures on a daily equity curve."""
    r = eq.pct_change().iloc[1:]
    cy = metrics.calendar_years(eq)
    worst = min(cy.items(), key=lambda kv: kv[1]) if cy else (None, None)
    return {"start": str(eq.index[1].date()), "end": str(eq.index[-1].date()),
            "cagr": float(metrics.cagr(eq)), "vol": float(r.std() * math.sqrt(252)),
            "sharpe": float(metrics.sharpe(eq, cash_day)), "max_dd": metrics.max_drawdown(eq),
            "worst_year": worst[1], "worst_year_is": worst[0], "calendar_years": cy}
