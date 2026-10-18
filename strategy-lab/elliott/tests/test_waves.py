import unittest
import numpy as np

from elliott import waves


def bars(closes, spread=0.0):
    c = np.asarray(closes, float)
    return c + spread, c - spread, c


class ZigzagTests(unittest.TestCase):
    def test_pivots_and_confirmation_bars(self):
        # up to 10, down to 4, up to 9; ATR fixed at 1, k = 3
        c = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 8, 7, 6, 5, 4, 5, 6, 7, 8, 9]
        h, l, _ = bars(c)
        a = np.ones(len(c))
        p = waves.zigzag(h, l, a, 3)
        # first move up from the start: the low at bar 0 is confirmed at bar 3 (4 >= 1 + 3)
        self.assertEqual((p[0].i, p[0].kind, p[0].confirm), (0, -1, 3))
        # high 10 at bar 9, confirmed when a low reaches 7, at bar 12
        self.assertEqual((p[1].i, p[1].price, p[1].kind, p[1].confirm), (9, 10.0, 1, 12))
        # low 4 at bar 15, confirmed when a high reaches 7, at bar 18
        self.assertEqual((p[2].i, p[2].price, p[2].kind, p[2].confirm), (15, 4.0, -1, 18))
        self.assertEqual(len(p), 3)

    def test_no_pivot_uses_a_later_bar(self):
        rng = np.random.default_rng(3)
        c = 100 + np.cumsum(rng.normal(0, 1, 2000))
        h, l = c + rng.uniform(0, 1, 2000), c - rng.uniform(0, 1, 2000)
        a = waves.atr(h, l, c)
        full = waves.zigzag(h, l, a, 2.5)
        # the pivots known at bar t are exactly those found on data cut at t
        for t in (300, 777, 1500):
            cut = waves.zigzag(h[:t + 1], l[:t + 1], a[:t + 1], 2.5)
            known = [p for p in full if p.confirm <= t]
            self.assertEqual(cut, known)

    def test_alternates(self):
        rng = np.random.default_rng(4)
        c = 50 + np.cumsum(rng.normal(0, 1, 3000))
        h, l = c + 0.5, c - 0.5
        p = waves.zigzag(h, l, waves.atr(h, l, c), 3)
        self.assertTrue(all(a.kind != b.kind for a, b in zip(p, p[1:])))
        self.assertTrue(all(a.i < b.i and a.confirm <= b.confirm and a.i < a.confirm for a, b in zip(p, p[1:])))


class SimulateTests(unittest.TestCase):
    def test_long_target_stop_time(self):
        o = np.array([10, 10, 10, 10, 10.0]); h = o + 1; l = o - 1; c = o
        self.assertEqual(waves.simulate(o, h, l, c, 1, 1, 8.5, 10.8, 3), (1, 10.8, "target"))
        self.assertEqual(waves.simulate(o, h, l, c, 1, 1, 9.5, 12, 3), (1, 9.5, "stop"))
        self.assertEqual(waves.simulate(o, h, l, c, 1, 1, 8, 12, 3), (3, 10.0, "time"))
        self.assertIsNone(waves.simulate(o, h, l, c, 3, 1, 8, 12, 3))

    def test_both_in_one_bar_is_a_stop(self):
        o = np.array([10, 10.0]); h = np.array([11, 11.0]); l = np.array([9, 9.0]); c = o
        self.assertEqual(waves.simulate(o, h, l, c, 1, 1, 9.5, 10.5, 1)[2], "stop")
        self.assertEqual(waves.simulate(o, h, l, c, 1, -1, 10.5, 9.5, 1)[2], "stop")

    def test_short_and_gaps(self):
        o = np.array([10, 10, 12, 7.0]); h = o + 0.2; l = o - 0.2; c = o
        # short with stop 11: bar 2 opens at 12, through the stop
        self.assertEqual(waves.simulate(o, h, l, c, 1, -1, 11, 8, 3), (2, 12.0, "stop"))
        # long with target 11: bar 2 opens at 12, through the target
        self.assertEqual(waves.simulate(o, h, l, c, 1, 1, 9, 11, 3), (2, 12.0, "target"))


if __name__ == "__main__":
    unittest.main()
