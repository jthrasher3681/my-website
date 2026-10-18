import unittest
import numpy as np
import pandas as pd

from lab import data, engine, metrics, strategies


def frame(n=10, spy=0.01, sso=None, bil=0.0001, start="2020-01-01"):
    idx = pd.bdate_range(start, periods=n)
    sso = 2 * spy if sso is None else sso
    return pd.DataFrame({"spy": spy, "sso": sso, "bil": bil}, index=idx, dtype=float)


class WeightsTests(unittest.TestCase):
    def test_mapping(self):
        np.testing.assert_allclose(engine.weights(0), [0, 0, 1])
        np.testing.assert_allclose(engine.weights(0.4), [0.4, 0, 0.6])
        np.testing.assert_allclose(engine.weights(1), [1, 0, 0])
        np.testing.assert_allclose(engine.weights(1.5), [0.5, 0.5, 0])
        np.testing.assert_allclose(engine.weights(2), [0, 1, 0])
        for e in (0.3, 1.0, 1.7, 2.0):
            self.assertAlmostEqual(engine.LEVER @ engine.weights(e), e)


class RunTests(unittest.TestCase):
    def test_constant_one_is_spy(self):
        r = frame(20, spy=0.01)
        sim = engine.run(pd.Series(1.0, index=r.index), r, r.index[2], r.index[-1], cost=0.001)
        self.assertEqual(sim["equity"].iloc[0], 1.0)
        self.assertAlmostEqual(sim["equity"].iloc[-1], 0.999 * 1.01 ** 18)
        self.assertEqual(sim["traded"].iloc[1:].sum(), 0)

    def test_one_session_delay(self):
        r = frame(8, spy=0.01, bil=0.0)
        t = pd.Series(0.0, index=r.index)
        t.iloc[3:] = 2.0                        # decided at the close of session 3
        sim = engine.run(t, r, r.index[2], r.index[-1], cost=0.0)
        # traded at session 4's close; session 5 is the first earned at 2x
        self.assertEqual(list(sim["exposure"].loc[r.index[1]:]), [0, 0, 0, 0, 2, 2, 2])
        self.assertEqual(sim["traded"].loc[r.index[4]], 1)
        self.assertAlmostEqual(sim["equity"].iloc[-1], 1.02 ** 3)

    def test_no_delay(self):
        r = frame(8, spy=0.01, bil=0.0)
        t = pd.Series(0.0, index=r.index)
        t.iloc[3:] = 2.0
        sim = engine.run(t, r, r.index[2], r.index[-1], cost=0.0, lag=0)
        self.assertEqual(list(sim["exposure"].loc[r.index[1]:]), [0, 0, 0, 2, 2, 2, 2])

    def test_opening_position_uses_decision_before_start(self):
        r = frame(6, spy=0.01, bil=0.0)
        t = pd.Series([2.0, 0, 0, 0, 0, 0], index=r.index)
        sim = engine.run(t, r, r.index[2], r.index[-1], cost=0.0)
        # bought at session 1's close with session 0's decision (2x); session 1 decided 0
        self.assertEqual(sim["exposure"].iloc[0], 2.0)
        self.assertEqual(sim["exposure"].iloc[1], 2.0)
        self.assertEqual(sim["exposure"].iloc[2], 0.0)

    def test_switch_cost(self):
        r = frame(6, spy=0.0, bil=0.0)
        t = pd.Series(0.0, index=r.index)
        t.iloc[2:] = 2.0
        sim = engine.run(t, r, r.index[2], r.index[-1], cost=0.001)
        # opening buy of BIL, then sell BIL and buy SSO
        self.assertAlmostEqual(sim["equity"].iloc[-1], 0.999 * (1 - 0.002))

    def test_band(self):
        r = frame(6, spy=0.0, bil=0.0)
        small = pd.Series([1.0, 1.0, 1.08, 1.08, 1.08, 1.08], index=r.index)
        big = pd.Series([1.0, 1.0, 1.2, 1.2, 1.2, 1.2], index=r.index)
        self.assertEqual(engine.run(small, r, r.index[2], r.index[-1])["traded"].iloc[1:].sum(), 0)
        self.assertEqual(engine.run(big, r, r.index[2], r.index[-1])["traded"].iloc[1:].sum(), 1)

    def test_move_to_zero_always_trades(self):
        r = frame(6, spy=0.0, bil=0.0)
        t = pd.Series([0.05, 0.05, 0.0, 0.0, 0.0, 0.0], index=r.index)
        sim = engine.run(t, r, r.index[2], r.index[-1])
        self.assertEqual(sim["traded"].iloc[1:].sum(), 1)
        self.assertEqual(sim["exposure"].iloc[-1], 0.0)

    def test_drift_of_mixed_position(self):
        r = frame(4, spy=0.0, sso=0.10, bil=0.0)
        sim = engine.run(pd.Series(1.5, index=r.index), r, r.index[2], r.index[-1], cost=0.0, band=1.0)
        # half SPY, half SSO; SSO +10% on session 2 drifts exposure up for session 3
        self.assertAlmostEqual(sim["exposure"].iloc[2], (0.5 + 2 * 0.55) / 1.05)

    def test_next_open(self):
        r = frame(6, spy=0.0, bil=0.0)
        on = frame(6, spy=0.01, sso=0.02, bil=0.0)
        intra = frame(6, spy=0.03, sso=0.06, bil=0.0)
        r = on * 0 + (1 + on) * (1 + intra) - 1
        t = pd.Series(0.0, index=r.index)
        t.iloc[2:] = 2.0                        # decided at session 2's close
        sim = engine.run(t, r, r.index[2], r.index[-1], cost=0.0, at_open=(on, intra))
        # session 3: overnight in cash, intraday in SSO; sessions 4-5 fully in SSO
        self.assertAlmostEqual(sim["equity"].iloc[-1], 1.06 * (1.02 * 1.06) ** 2)


class SignalTests(unittest.TestCase):
    def test_above_sma(self):
        px = pd.Series([1, 2, 3, 2, 1, 5], index=pd.bdate_range("2020-01-01", periods=6), dtype=float)
        sig = strategies.above_sma(px, 3)
        self.assertTrue(np.isnan(sig.iloc[1]))
        self.assertEqual(list(sig.iloc[2:]), [1.0, 0.0, 0.0, 1.0])

    def test_month_ends(self):
        idx = pd.DatetimeIndex(["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-28", "2020-03-02", "2020-03-03"])
        self.assertEqual(list(strategies.month_ends(idx)), list(pd.DatetimeIndex(["2020-01-31", "2020-02-28"])))

    def test_month_end_at_data_end(self):
        idx = pd.DatetimeIndex(["2015-12-29", "2015-12-30", "2015-12-31"])
        self.assertEqual(list(strategies.month_ends(idx)), [pd.Timestamp("2015-12-31")])
        self.assertEqual(len(strategies.month_ends(pd.DatetimeIndex(["2026-10-15", "2026-10-16"]))), 0)

    def test_monthly_sma_carried(self):
        idx = pd.bdate_range("2019-01-01", "2020-12-31")
        px = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
        sig = strategies.above_monthly_sma(px, 10)
        me = strategies.month_ends(idx)
        self.assertTrue(np.isnan(sig.loc[me[8]]))
        self.assertEqual(sig.loc[me[9]], 1.0)
        # the decision holds until the next month end
        self.assertTrue((sig.loc[me[9]:me[10]].iloc[:-1] == sig.loc[me[9]]).all())

    def test_ewma_vol(self):
        idx = pd.bdate_range("1961-01-02", periods=40)
        rng = np.random.default_rng(1)
        px = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 40)), index=idx)
        vol = strategies.ewma_vol(px, 0.94)
        r = px.pct_change().dropna()
        var = np.mean(r.iloc[:21] ** 2)
        for i in range(21, 25):
            var = 0.94 * var + 0.06 * r.iloc[i] ** 2
        self.assertAlmostEqual(vol.loc[r.index[24]], np.sqrt(252 * var))
        self.assertAlmostEqual(vol.loc[r.index[20]], np.sqrt(252 * np.mean(r.iloc[:21] ** 2)))
        self.assertTrue(np.isnan(vol.loc[r.index[19]]))

    def test_vol_target_cap(self):
        idx = pd.bdate_range("1961-01-02", periods=60)
        px = pd.Series(100 * 1.0001 ** np.arange(60), index=idx)
        self.assertTrue((strategies.vol_target(px).dropna() == 2.0).all())


class DataTests(unittest.TestCase):
    def test_calibration_recovers_cost(self):
        idx = pd.bdate_range("2006-06-01", "2016-01-31")
        rng = np.random.default_rng(2)
        spy = pd.Series(rng.normal(0.0004, 0.01, len(idx)), index=idx)
        bil = pd.Series(0.0001, index=idx)
        sso = data.simulated_2x(spy, bil, 0.012)
        self.assertAlmostEqual(data.calibrate_2x(spy, bil, sso), 0.012, places=6)

    def test_in_sample_load_stops_at_end(self):
        r, c, gspc = data.returns(end="2015-12-31")
        self.assertLessEqual(r.index[-1], pd.Timestamp("2015-12-31"))
        self.assertLessEqual(gspc.index[-1], pd.Timestamp("2015-12-31"))
        self.assertFalse(r.isna().any().any())
        self.assertTrue(r.index.is_monotonic_increasing)
        self.assertEqual(r.index[0], pd.Timestamp("1988-01-04"))
        self.assertTrue(0.0 < c < 0.05)


class MetricTests(unittest.TestCase):
    def test_cagr_and_drawdown(self):
        idx = pd.DatetimeIndex(["2020-01-01", "2020-07-01", "2020-12-31"])
        eq = pd.Series([1.0, 0.5, 2.0], index=idx)
        self.assertAlmostEqual(metrics.cagr(eq), 2.0 ** (365.25 / 365) - 1)
        self.assertAlmostEqual(metrics.max_drawdown(eq), -0.5)

    def test_calendar_years_full_only(self):
        idx = pd.DatetimeIndex(["2019-12-31", "2020-06-30", "2020-12-31", "2021-06-30"])
        eq = pd.Series([1.0, 1.1, 1.2, 1.3], index=idx)
        self.assertEqual(list(metrics.calendar_years(eq)), [2020])
        self.assertAlmostEqual(metrics.calendar_years(eq)[2020], 0.2)

    def test_window_rebases(self):
        idx = pd.bdate_range("2020-01-01", periods=5)
        sim = pd.DataFrame({"equity": [1, 2, 4, 8, 16.0], "exposure": 1.0, "traded": [1, 0, 1, 0, 0]}, index=idx)
        w = metrics.window(sim, idx[2], idx[4])
        self.assertEqual(list(w["equity"]), [1, 2, 4, 8])
        self.assertEqual(w["traded"].iloc[0], 0)

    def test_passes(self):
        b = {"cagr": 0.10, "sharpe": 0.5, "max_dd": -0.5}
        self.assertTrue(metrics.passes({"cagr": 0.11, "sharpe": 0.5, "max_dd": -0.5}, b)[0])
        self.assertFalse(metrics.passes({"cagr": 0.11, "sharpe": 0.6, "max_dd": -0.51}, b)[0])
        self.assertFalse(metrics.passes({"cagr": 0.10, "sharpe": 0.6, "max_dd": -0.2}, b)[0])

    def test_block_shuffle_keeps_values(self):
        x = np.arange(10)
        y = metrics.block_shuffle(x, 3, np.random.default_rng(0))
        self.assertEqual(sorted(y), list(x))

    def test_underwater(self):
        idx = pd.DatetimeIndex(["2020-01-01", "2021-01-01", "2022-01-01", "2022-07-01"])
        eq = pd.Series([1.0, 0.8, 1.1, 1.0], index=idx)
        self.assertAlmostEqual(metrics.longest_underwater_years(eq), 731 / 365.25)


class TaxTests(unittest.TestCase):
    def test_netting(self):
        from lab.tax import _net
        z = {"st": 0.0, "lt": 0.0}
        self.assertEqual(_net(10, -4, z)[:2], (6, 0))
        self.assertEqual(_net(-10, 4, z)[:2], (0, 0))
        self.assertEqual(_net(-10, 4, z)[2], {"st": -6, "lt": 0})
        self.assertEqual(_net(3, 5, {"st": -4, "lt": 0})[:2], (0, 4))

    def test_fifo_holding_period(self):
        from lab.tax import _sell
        lots = [[1.0, 10.0, pd.Timestamp("2020-01-02")], [1.0, 20.0, pd.Timestamp("2021-06-01")]]
        out = {"st": 0.0, "lt": 0.0}
        _sell(lots, 1.5, 30.0, pd.Timestamp("2021-07-01"), out)
        self.assertAlmostEqual(out["lt"], 20.0)       # first lot, held 18 months
        self.assertAlmostEqual(out["st"], 5.0)        # half the second, held a month
        self.assertAlmostEqual(lots[0][0], 0.5)
        self.assertAlmostEqual(lots[0][1], 10.0)

    def test_one_year_exactly_is_short_term(self):
        from lab.tax import _sell
        out = {"st": 0.0, "lt": 0.0}
        _sell([[1.0, 10.0, pd.Timestamp("2020-01-02")]], 1.0, 30.0, pd.Timestamp("2021-01-02"), out)
        self.assertEqual(out, {"st": 20.0, "lt": 0.0})

    def test_buy_and_hold_spy_taxes(self):
        from lab import tax
        r, c, gspc = data.returns(end="2010-12-31")
        sim = engine.run(pd.Series(1.0, index=r.index), r, "2008-01-02", "2010-12-31", cost=0.0, record=True)
        out = tax.after_tax(sim, "2008-01-02", "2010-12-31")
        self.assertAlmostEqual(out["pre_tax"], sim["equity"].iloc[-1] / sim["equity"].iloc[0])
        # only dividends are taxed while held: 20% of a ~2% yield
        self.assertLess(out["pre_tax"] - out["after_tax_held"], 0.02)
        self.assertGreater(out["pre_tax"] - out["after_tax_held"], 0.005)


if __name__ == "__main__":
    unittest.main()
