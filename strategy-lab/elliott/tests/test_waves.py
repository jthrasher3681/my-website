import unittest
import numpy as np

from elliott import waves


def walk(n, seed, vol=0.01):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, vol, n)))
    o = np.concatenate(([c[0]], c[:-1])) * np.exp(rng.normal(0, vol / 4, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, vol / 2, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, vol / 2, n)))
    return o, h, l, c


class AtrTests(unittest.TestCase):
    def test_wilder_log_atr(self):
        o, h, l, c = walk(40, 1)
        a = waves.log_atr(h, l, c)
        tr = [np.log(h[0] / l[0])] + [max(np.log(h[t] / l[t]), abs(np.log(h[t] / c[t - 1])), abs(np.log(l[t] / c[t - 1]))) for t in range(1, 40)]
        self.assertTrue(np.isnan(a[12]))
        self.assertAlmostEqual(a[13], np.mean(tr[:14]))
        self.assertAlmostEqual(a[14], (13 * a[13] + tr[14]) / 14)


class ZigzagTests(unittest.TestCase):
    def test_hand_example(self):
        # flat warm-up, then up to 130, down to 100, up again; ATR about 1% (log), k = 2
        base = [100.0] * 55
        up = list(np.linspace(100, 130, 16)[1:])
        down = list(np.linspace(130, 100, 16)[1:])
        up2 = list(np.linspace(100, 115, 8)[1:])
        c = np.array(base + up + down + up2)
        h, l = c * 1.005, c * 0.995
        a = np.full(len(c), 0.01)
        p = waves.pivots(h, l, c, 2.0, a)
        # the high at the top of the first leg (bar 69) is confirmed once a close is
        # 2% (log) below it; the low at bar 84 is confirmed by a close 2% above it
        hi = int(np.flatnonzero(p["kind"] == 1)[0])
        self.assertEqual(p["e"][hi], 69)
        self.assertAlmostEqual(p["p"][hi], 130 * 1.005)
        cc = p["c"][hi]
        self.assertTrue(np.log(c[cc]) <= np.log(130 * 1.005) - 0.02)
        self.assertTrue(np.log(c[cc - 1]) > np.log(130 * 1.005) - 0.02)
        lo = int(np.flatnonzero((p["kind"] == -1) & (p["e"] > 69))[0])
        self.assertEqual(p["e"][lo], 84)

    def test_causal(self):
        o, h, l, c = walk(3000, 3)
        a = waves.log_atr(h, l, c)
        full = waves.pivots(h, l, c, 2.0, a)
        for t in (400, 1234, 2500):
            cut = waves.pivots(h[:t + 1], l[:t + 1], c[:t + 1], 2.0, a[:t + 1])
            known = full["c"] <= t
            for key in ("e", "c", "kind", "p"):
                np.testing.assert_array_equal(cut[key], full[key][known])

    def test_alternation_and_thresholds(self):
        o, h, l, c = walk(5000, 4)
        a = waves.log_atr(h, l, c)
        p = waves.pivots(h, l, c, 2.0, a)
        self.assertTrue(np.all(p["kind"][1:] != p["kind"][:-1]))
        self.assertTrue(np.all(p["e"] < p["c"]))
        self.assertTrue(np.all(np.diff(p["e"]) > 0))
        # each confirmation close is at least k x ATR(extreme bar) beyond the extreme
        for e, cc, kd, pr in zip(p["e"], p["c"], p["kind"], p["p"]):
            self.assertGreaterEqual(-kd * (np.log(c[cc]) - np.log(pr)), 2.0 * a[e] - 1e-12)
        # a pivot high is the highest high from after the previous pivot's extreme to its own
        # confirmation (and a low the lowest low)
        for i in range(1, len(p["e"])):
            seg = slice(p["e"][i - 1] + 1, p["c"][i] + 1)
            if p["kind"][i] == 1:
                self.assertEqual(p["p"][i], h[seg].max())
            else:
                self.assertEqual(p["p"][i], l[seg].min())


class ExitTests(unittest.TestCase):
    def setUp(self):
        self.o = np.array([10, 10, 10, 10, 10.0])
        self.h, self.l, self.c = self.o + 1, self.o - 1, self.o.copy()
        self.dm = np.full(5, np.nan)

    def ex(self, entry, d, stop, target, n, limit=False, o=None, h=None, l=None):
        o = self.o if o is None else o
        h = self.h if h is None else h
        l = self.l if l is None else l
        return waves.run_exit(o, h, l, self.c, entry, o[entry], d, stop, target, n, limit, np.nan, self.dm)

    def test_market_long(self):
        self.assertEqual(self.ex(1, 1, 8.5, 10.8, 2)[1:], (10.8, 1))
        self.assertEqual(self.ex(1, 1, 9.5, 12.0, 2)[1:], (9.5, 0))
        self.assertEqual(self.ex(1, 1, 8.0, 12.0, 2), (3, 10.0, 2))
        self.assertEqual(self.ex(3, 1, 8.0, 12.0, 2)[0], -1)

    def test_both_in_bar_is_stop(self):
        self.assertEqual(self.ex(1, 1, 9.5, 10.5, 1)[2], 0)
        self.assertEqual(self.ex(1, -1, 10.5, 9.5, 1)[2], 0)

    def test_limit_fill_bar_checks_stop_not_target(self):
        r = self.ex(1, 1, 8.0, 10.5, 2, limit=True)
        self.assertEqual((r[0], r[2]), (2, 1))          # target only from the next bar
        r = self.ex(1, 1, 9.5, 20.0, 2, limit=True)
        self.assertEqual((r[0], r[2]), (1, 0))          # stop on the fill bar

    def test_gaps(self):
        o = np.array([10, 10, 12, 7.0]); h, l = o + 0.2, o - 0.2
        self.assertEqual(self.ex(1, -1, 11, 8, 2, o=o, h=h, l=l)[1:], (12.0, 0))
        self.assertEqual(self.ex(1, 1, 9, 11, 2, o=o, h=h, l=l)[1:], (12.0, 1))

    def test_s3_dma_exit(self):
        o = np.array([10, 10, 11, 12, 11, 10.5]); h, l, c = o + 0.3, o - 0.3, o.copy()
        dm = np.array([np.nan, 9, 10, 11, 11.5, 11])
        r = waves.run_exit(o, h, l, c, 1, 10.0, 1, 5.0, np.nan, 4, False, 12.1, dm)
        # bar 3 trades above 12.1; bar 4 closes below its DMA; exit at bar 5's open
        self.assertEqual(r, (5, 10.5, 3))


if __name__ == "__main__":
    unittest.main()
