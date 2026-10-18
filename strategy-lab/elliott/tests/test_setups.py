import unittest
import numpy as np

from elliott import execute as X, setups, waves
from elliott.tests.test_waves import walk


def bars_from(o, h, l, c):
    t = np.datetime64("2010-01-01") + np.arange(len(c)).astype("timedelta64[D]")
    b = {"t": t, "open": o, "high": h, "low": l, "close": c, "volume": np.ones(len(c)), "liquid": np.ones(len(c), bool)}
    return X.prepare(b)


def mirror(o, h, l, c, k=10000.0):
    return k / o, k / l, k / h, k / c


class LimitFillTests(unittest.TestCase):
    def order(self, **kw):
        o = {"sig": 0, "d": 1, "limit": 9.0, "cancel_level": 11.0, "cancel_open": 8.0, "expiry": 3}
        o.update(kw)
        return o

    def test_fill_at_limit_and_at_open(self):
        o = np.array([10, 10, 10, 10.0]); h = o + 0.5; l = np.array([9.5, 9.5, 8.9, 9.5]); c = o
        b = {"open": o, "high": h, "low": l}
        self.assertEqual(X.fill_limit(b, self.order()), (2, 9.0))
        b2 = {"open": np.array([10, 8.5, 10, 10.0]), "high": h, "low": l}
        self.assertEqual(X.fill_limit(b2, self.order()), (1, 8.5))           # opened below the limit

    def test_cancels(self):
        o = np.array([10, 10, 10, 10.0]); l = np.array([9.5, 8.9, 9.5, 9.5])
        b = {"open": o, "high": np.array([10.5, 11.5, 10.5, 10.5]), "low": l}
        self.assertEqual(X.fill_limit(b, self.order()), (None, 1))           # touched the limit but broke 11 too
        b2 = {"open": np.array([10, 7.9, 10, 10.0]), "high": o + 0.5, "low": o - 0.5}
        self.assertEqual(X.fill_limit(b2, self.order()), (None, 1))          # opened through the stop
        b3 = {"open": o, "high": o + 0.5, "low": o - 0.5}
        self.assertEqual(X.fill_limit(b3, self.order()), (None, 3))          # expired
        b4 = {"open": np.array([10, 8.5, 10, 10.0]), "high": np.array([10.5, 11.5, 10.5, 10.5]), "low": o - 0.5}
        self.assertEqual(X.fill_limit(b4, self.order()), (None, 1))          # opened below the limit but broke 11

    def test_short_mirror(self):
        o = np.array([10, 10, 10, 10.0]); h = np.array([10.5, 10.5, 11.1, 10.5]); l = o - 0.5
        b = {"open": o, "high": h, "low": l}
        self.assertEqual(X.fill_limit(b, self.order(d=-1, limit=11.0, cancel_level=9.0, cancel_open=12.0)), (2, 11.0))


class SlotTests(unittest.TestCase):
    def test_busy_slot_drops_signals(self):
        o = np.full(50, 10.0); h, l, c = o + 0.1, o - 0.1, o.copy()
        b = bars_from(o, h, l, c)
        mk = lambda sig: setups._market("S1", "S1", 1, sig, 9.0, 11.0, 5)
        tr = X.run_symbol("A", b, [mk(20), mk(22), mk(26), mk(27)], 0.0, False)
        # the first trade runs from bar 21 to its time exit at bar 26: the signal at 22 is dropped,
        # the one at 26 too (26 <= 26), the one at 27 is taken
        self.assertEqual([t["sig"] for t in tr], [20, 27])
        self.assertEqual(tr[0]["exit"], 26)

    def test_tight_stop_is_skipped(self):
        o = np.full(50, 10.0); h, l, c = o + 0.1, o - 0.1, o.copy()
        b = bars_from(o, h, l, c)
        # log ATR is about 0.02, so a stop 0.5% away is inside half of it
        tr = X.run_symbol("A", b, [setups._market("S1", "S1", 1, 20, 9.95, 11.0, 5)], 0.0, False)
        self.assertEqual(tr, [])

    def test_r_multiple_with_costs(self):
        R, ret = X.r_multiple(1, 100.0, 95.0, 110.0, 0.001)
        self.assertAlmostEqual(R, (10 - 0.2) / 5)
        self.assertAlmostEqual(ret, 0.1 - 0.002)


class SetupTests(unittest.TestCase):
    def test_s1_hand_example(self):
        # pivots: P_-1 high 105, P0 low 95, P1 high 110, P2 low 102 (r2 = ln(110/102)/ln(110/95) = 0.517)
        e = np.array([60, 70, 80, 90, 100]); c_ = e + 3
        piv = {"e": e, "c": c_, "kind": np.array([-1, 1, -1, 1, -1]), "p": np.array([90, 105, 95, 110, 102.0])}
        n = 140
        cl = np.full(n, 105.0)
        b = bars_from(cl.copy(), cl + 1, cl - 1, cl)
        allo = [x for x in setups.pivot_setups(b, piv) if x["family"] == "S1"]
        self.assertEqual(sorted(x["setup"] for x in allo), ["S1", "S1-p2stop"])     # closes never pass p1: no trigger
        x = next(x for x in allo if x["setup"] == "S1")
        self.assertEqual((x["setup"], x["d"], x["sig"]), ("S1", 1, 103))
        self.assertAlmostEqual(x["stop"], 95 * (1 - 1e-4))
        self.assertAlmostEqual(x["target"], 102 * np.exp(1.618 * np.log(110 / 95)))
        self.assertEqual(x["n_time"], 30)
        self.assertAlmostEqual(next(x for x in allo if x["setup"] == "S1-p2stop")["stop"], 102 * (1 - 1e-4))

    def test_f2_levels(self):
        e = np.array([60, 70, 80, 90]); c_ = e + 3
        piv = {"e": e, "c": c_, "kind": np.array([1, -1, 1, -1]) * -1, "p": np.array([100, 105, 95, 110.0])}
        # kinds: low 100, high 105, low 95, high 110 -> F2 at the high 110 (P_-1 = 105, P0 = 95)
        cl = np.full(140, 109.0)
        b = bars_from(cl.copy(), cl + 0.5, cl - 0.5, cl)
        f2 = {x["setup"]: x for x in setups.pivot_setups(b, piv) if x["family"] == "F2"}
        self.assertAlmostEqual(f2["F2-618"]["limit"], 110 - 0.618 * 15)
        self.assertAlmostEqual(f2["F2-500"]["limit"], 102.5)
        self.assertAlmostEqual(f2["F2-618"]["target"], 110 - 0.618 * 15 + 1.618 * 15)
        self.assertEqual(f2["F2-618"]["expiry"], 93 + 3 * 10)
        self.assertEqual(set(f2), {"F2-618", "F2-500", "F2-c437", "F2-c556", "F2-c697"})

    def test_mirror_symmetry(self):
        o, h, l, c = walk(4000, 11, vol=0.015)
        b = bars_from(o, h, l, c)
        mo, mh, ml, mc = mirror(o, h, l, c)
        mb = bars_from(mo, mh, ml, mc)
        p1 = waves.pivots(h, l, c, 2.0, b["atr"])
        p2 = waves.pivots(mh, ml, mc, 2.0, mb["atr"])
        np.testing.assert_array_equal(p1["e"], p2["e"])
        np.testing.assert_array_equal(p1["kind"], -p2["kind"])
        fam = ("S1", "S2", "S5")
        a = sorted((x["setup"], x["d"], x["sig"]) for x in setups.pivot_setups(b, p1) if x["family"] in fam)
        m = sorted((x["setup"], -x["d"], x["sig"]) for x in setups.pivot_setups(mb, p2) if x["family"] in fam)
        self.assertEqual(a, m)
        self.assertTrue(len(a) > 20)

    def test_s3_signals_are_causal(self):
        o, h, l, c = walk(3000, 5, vol=0.02)
        b = bars_from(o, h, l, c)
        full = setups.s3_orders(b)
        for cut in (1500, 2400):
            bc = bars_from(o[:cut + 1], h[:cut + 1], l[:cut + 1], c[:cut + 1])
            part = setups.s3_orders(bc)
            known = [(x["d"], x["sig"], round(x["stop"], 9)) for x in full if x["sig"] < cut]
            self.assertEqual([(x["d"], x["sig"], round(x["stop"], 9)) for x in part if x["sig"] < cut], known)


if __name__ == "__main__":
    unittest.main()
