"""python3 -m unittest crossover.tests.test_crossover (from strategy-lab/)"""
import unittest
import numpy as np
import pandas as pd

from lab import engine
from crossover import data as D, portfolio as P, signals as S


def walk(n, seed=0, vol=0.01, start="2000-01-03", freq="B"):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, vol, n)))
    t = pd.date_range(start, periods=n, freq=freq).to_numpy("datetime64[ns]")
    return {"t": t, "close": close, "tr": close.copy(), "liquid": np.ones(n, bool)}


def hourly_times(days, start="2024-01-02"):
    d = pd.bdate_range(start, periods=days)
    hours = ["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"]
    return pd.DatetimeIndex([pd.Timestamp(f"{x.date()} {h}") for x in d for h in hours]).to_numpy("datetime64[ns]")


class Averages(unittest.TestCase):
    def test_sma(self):
        x = np.arange(1.0, 11.0)
        s = S.sma(x, 3)
        self.assertTrue(np.isnan(s[:2]).all())
        np.testing.assert_allclose(s[2:], [(x[i - 2] + x[i - 1] + x[i]) / 3 for i in range(2, 10)])

    def test_ema(self):
        x = np.array([1.0, 2.0, 4.0, 3.0])
        a = 2 / 4
        y = [1.0]
        for v in x[1:]:
            y.append(a * v + (1 - a) * y[-1])
        np.testing.assert_allclose(S.ema(x, 3), y)

    def test_tie_is_not_bullish(self):
        self.assertEqual(S.above(np.array([1.0]), np.array([1.0]))[0], 0.0)

    def test_warmup(self):
        c = walk(600)["close"]
        for rule in S.RULES:
            s = S.signal(rule, c)
            self.assertTrue(np.isnan(s[:259]).all(), rule)
            self.assertTrue(np.isfinite(s[259:]).all(), rule)
            self.assertTrue(set(np.unique(s[259:])) <= {0.0, 1.0})

    def test_golden_cross_by_hand(self):
        c = walk(600, seed=3)["close"]
        s = S.signal("R1", c)
        for i in (259, 300, 599):
            self.assertEqual(s[i], float(c[i - 49:i + 1].mean() > c[i - 199:i + 1].mean()))

    def test_macd_signal_by_hand(self):
        c = walk(400, seed=4)["close"]
        m = S.ema(c, 12) - S.ema(c, 26)
        sig = S.ema(m, 9)
        np.testing.assert_array_equal(S.signal("R4", c)[259:], (m > sig).astype(float)[259:])

    def test_no_lookahead(self):
        c = walk(800, seed=5)["close"]
        for rule in list(S.RULES) + list(S.REFERENCE):
            full = S.signal(rule, c)
            for cut in (300, 451, 799):
                np.testing.assert_array_equal(S.signal(rule, c[:cut]), full[:cut])


class Sleeves(unittest.TestCase):
    def setUp(self):
        self.a = walk(700, seed=1)
        self.cash = pd.Series(0.0001, index=pd.DatetimeIndex(self.a["t"]))

    def test_lag_and_cost(self):
        p = P.Panel({"A": self.a}, self.cash)
        H, W = p.rule("R2")
        s = S.signal("R2", self.a["close"])
        np.testing.assert_array_equal(H[2:, 0], s[:-2])
        np.testing.assert_array_equal(W[2:, 0], np.abs(s[1:-1] - s[:-2]))
        j0, j1 = p.window(H, "2000-01-01")
        self.assertEqual(j0, 261)
        r = self.a["tr"][1:] / self.a["tr"][:-1] - 1
        net = p.bar_returns(H, W, j0, j1, "net", 0.001)
        i = j0 + 5
        expect = s[i - 2] * r[i - 1] + (1 - s[i - 2]) * 0.0001 - 0.001 * abs(s[i - 1] - s[i - 2])
        self.assertAlmostEqual(net[5], expect, places=14)

    def test_matches_lab_engine(self):
        """One asset, 0/1 exposure: the sleeve equals the SPY lab's engine (cost 0 exactly;
        with cost the engine's two 0.05% legs make 0.10% a switch)."""
        cal = pd.DatetimeIndex(self.a["t"])
        rs = pd.Series(self.a["tr"], index=cal).pct_change().fillna(0.0)
        r = pd.DataFrame({"spy": rs, "sso": 2 * rs, "bil": self.cash})
        r.iloc[0] = 0.0
        sig = pd.Series(S.signal("R5", self.a["close"]), index=cal)
        p = P.Panel({"A": {**self.a, "tr": np.cumprod(1 + rs.to_numpy())}}, r["bil"])
        H, W = p.rule("R5")
        j0, j1 = p.window(H, cal[300])
        sim = engine.run(sig, r, cal[j0], cal[j1], cost=0.0)
        mine = p.equity(p.bar_returns(H, W, j0, j1, "gross"), j0, j1)
        np.testing.assert_allclose(sim["equity"].to_numpy(), mine.to_numpy(), rtol=1e-12)
        np.testing.assert_allclose(sim["exposure"].to_numpy()[1:], H[j0:j1 + 1, 0])
        # with costs the engine also pays for the opening purchase, and charges a switch
        # on the value at the close rather than at the start of the bar: second order
        sim = engine.run(sig, r, cal[j0], cal[j1], cost=engine.COST)
        mine = p.equity(p.bar_returns(H, W, j0, j1, "net", 2 * engine.COST), j0, j1)
        ratio = sim["equity"].to_numpy()[1:] / mine.to_numpy()[1:]
        switches = int(np.nansum(W[j0:j1 + 1, 0]))
        self.assertGreater(switches, 5)
        np.testing.assert_allclose(ratio, 1 - engine.COST, atol=switches * 0.001 * 0.03)

    def test_membership_and_liquidity_lag(self):
        b = walk(700, seed=2)
        b["liquid"] = np.ones(700, bool)
        b["liquid"][400] = False
        late = walk(400, seed=3, start="2001-01-01")
        p = P.Panel({"A": self.a, "B": b, "C": late}, self.cash.reindex(pd.DatetimeIndex(np.union1d(self.a["t"], late["t"]))).fillna(0), need_liquid=True)
        H, W = p.rule("R1")
        M = p.member(H)
        ib = p.names.index("B")
        self.assertFalse(M[p.pos["B"][402], ib])
        self.assertTrue(M[p.pos["B"][401], ib] and M[p.pos["B"][403], ib])
        ic = p.names.index("C")
        self.assertFalse(M[p.pos["C"][260], ic])
        self.assertTrue(M[p.pos["C"][261], ic])

    def test_portfolio_is_mean_of_members(self):
        b = walk(700, seed=7)
        p = P.Panel({"A": self.a, "B": b}, self.cash)
        H, W = p.rule("R3")
        j0, j1 = p.window(H, "2000-01-01")
        both = p.bar_returns(H, W, j0, j1, "net", 0.001)
        one = [P.Panel({k: v}, self.cash) for k, v in (("A", self.a), ("B", b))]
        parts = []
        for q in one:
            h, w = q.rule("R3")
            parts.append(q.bar_returns(h, w, j0, j1, "net", 0.001))
        np.testing.assert_allclose(both, (parts[0] + parts[1]) / 2, rtol=1e-12)
        hold = p.bar_returns(H, W, j0, j1, "hold")
        np.testing.assert_allclose(hold, np.nanmean(p.R[j0:j1 + 1], axis=1))


class Hourly(unittest.TestCase):
    def test_daily_marks(self):
        t = hourly_times(80)
        rng = np.random.default_rng(0)
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, len(t))))
        a = {"t": t, "close": close, "tr": close, "liquid": np.ones(len(t), bool)}
        days = pd.DatetimeIndex(t).normalize().unique()
        p = P.Panel({"A": a}, pd.Series(0.0007, index=days))
        self.assertEqual(len(p.days), 80)
        np.testing.assert_allclose(p.c[:7], 0.0001)
        H, W = p.rule("R5")
        j0, j1 = p.window(H, days[0])
        self.assertEqual(j0 % 7, 0)
        x = p.bar_returns(H, W, j0, j1, "hold")
        eq = p.equity(x, j0, j1)
        np.testing.assert_allclose(eq.iloc[-1], close[j1] / close[j0 - 1])
        np.testing.assert_allclose(eq.iloc[1], close[j0 + 6] / close[j0 - 1])


class Null(unittest.TestCase):
    def setUp(self):
        self.assets = {f"A{i}": walk(900, seed=10 + i) for i in range(4)}
        self.cash = pd.Series(0.0, index=pd.DatetimeIndex(self.assets["A0"]["t"]))

    def test_one_block_is_identity(self):
        p = P.Panel(self.assets, self.cash)
        H, W = p.rule("R2")
        j0, j1 = p.window(H, "2000-01-01")
        real, draws = p.null_sharpes(H, j0, j1, block=j1 - j0 + 1, draws=5)
        np.testing.assert_allclose(draws, real)
        gross = P.stats(p.equity(p.bar_returns(H, W, j0, j1, "gross"), j0, j1), self.cash)
        self.assertAlmostEqual(real, gross["sharpe"], places=10)

    def test_clairvoyant_rule_is_found(self):
        """A rule that knows tomorrow's return must get a small p."""
        a = walk(900, seed=99)
        c = a["close"]
        fut = np.r_[c[2:] / c[1:-1] - 1, 0.0, 0.0]          # the return over bar i + 2
        p = P.Panel({"A": a}, self.cash, source=lambda name, rule: np.where(np.arange(900) >= 259, (fut > 0).astype(float), np.nan))
        H, W = p.rule("any")
        j0, j1 = p.window(H, "2000-01-01")
        real, draws = p.null_sharpes(H, j0, j1, block=63, draws=200)
        self.assertLess(P.null_test(real, draws)["p"], 0.01)

    def test_shift_null(self):
        """The shift null moves every exposure by at least 260 bars, one shift for all assets."""
        p = P.Panel(self.assets, self.cash)
        H, W = p.rule("R1")
        j0, j1 = p.window(H, "2000-01-01")
        T = j1 - j0 + 1
        real, draws = p.shift_sharpes(H, j0, j1, draws=10_000)
        self.assertEqual(len(draws), T - 2 * 260 + 1)          # every shift used
        k = 300
        h = np.nan_to_num(H[j0:j1 + 1])
        M = p.member(H)[j0:j1 + 1]
        x = np.where(M, p.R[j0:j1 + 1] * h[(np.arange(T) + k) % T], 0).sum(1) / M.sum(1)
        cash = p.cash_day.reindex(p.daily_index(j0, j1)).to_numpy()
        self.assertAlmostEqual(draws[k - 260], P._sharpe(p.to_daily(x, j0, j1), cash), places=10)
        a = walk(1200, seed=99)
        c = a["close"]
        fut = np.r_[c[2:] / c[1:-1] - 1, 0.0, 0.0]
        q = P.Panel({"A": a}, self.cash.reindex(pd.DatetimeIndex(a["t"])).fillna(0),
                    source=lambda name, rule: np.where(np.arange(1200) >= 259, (fut > 0).astype(float), np.nan))
        H, W = q.rule("any")
        j0, j1 = q.window(H, "2000-01-01")
        real, draws = q.shift_sharpes(H, j0, j1)
        self.assertLess(P.null_test(real, draws)["p"], 0.01)

    def test_time_in_market_is_kept(self):
        p = P.Panel(self.assets, self.cash)
        H, W = p.rule("R1")
        j0, j1 = p.window(H, "2000-01-01")
        rng = np.random.default_rng(1)
        from lab import metrics
        perm = metrics.block_shuffle(np.arange(j1 - j0 + 1), 63, rng)
        h = H[j0:j1 + 1]
        np.testing.assert_allclose(np.nanmean(h[perm], 0), np.nanmean(h, 0))


class Periods(unittest.TestCase):
    def test_truncate(self):
        a = walk(700)
        cut = D.truncate({"A": a}, "2001-06-29")
        self.assertLessEqual(cut["A"]["t"][-1], np.datetime64("2001-06-29"))
        self.assertEqual(len(cut["A"]["close"]), len(cut["A"]["t"]))


if __name__ == "__main__":
    unittest.main()
