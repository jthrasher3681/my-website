"""python3 -m unittest patterns.tests.test_patterns (from strategy-lab/)"""
import unittest
import numpy as np
import pandas as pd

from patterns import detect, pivots
from elliott.calibration.walks import path_walk


def bars_from_closes(path, wick=0.2):
    c = np.asarray(path, float)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + wick
    l = np.minimum(o, c) - wick
    t = pd.bdate_range("2010-01-04", periods=len(c)).to_numpy("datetime64[ns]")
    return {"t": t, "open": o, "high": h, "low": l, "close": c, "volume": np.ones(len(c)), "liquid": np.ones(len(c), bool)}


def legs(points):
    """Piecewise-linear closes through (bar, price) points."""
    out = []
    for (b0, p0), (b1, p1) in zip(points[:-1], points[1:]):
        out += list(np.linspace(p0, p1, b1 - b0 + 1)[:-1])
    out.append(points[-1][1])
    return np.array(out)


ASC = [(0, 90), (10, 100), (20, 92), (30, 100), (40, 95), (50, 100), (58, 97), (70, 106)]


class Pivots(unittest.TestCase):
    def test_fractal(self):
        h = np.array([1, 2, 3, 5, 3, 2, 1, 2, 5, 5, 4, 3, 2, 1.0])
        self.assertEqual(list(pivots.pivot_highs(h, 2)), [3, 9])     # left ties allowed, right strict: the last of equal highs

    def test_lows(self):
        l = -np.array([1, 2, 3, 5, 3, 2, 1, 2, 5, 5, 4, 3, 2, 1.0])
        self.assertEqual(list(pivots.pivot_lows(l, 2)), [3, 9])


class Shapes(unittest.TestCase):
    def test_ascending_triangle(self):
        b = bars_from_closes(legs(ASC))
        sig = detect.scan(b, "AT", 5, 15, 250)
        self.assertEqual(len(sig), 1)
        s = sig[0]
        t = s["sig"]
        self.assertGreater(b["close"][t], 100.2)
        self.assertLessEqual(b["close"][t - 1], 100.2)
        self.assertEqual(s["first"], 11)                  # bars 10 and 11 share the high; the pivot is the last
        self.assertAlmostEqual(s["level"], 100.2, places=6)
        self.assertAlmostEqual(s["extreme"], b["low"][10:t + 1].min(), places=6)
        self.assertEqual(s["touches"], 3)
        hr = detect.scan(b, "HR", 5, 15, 250)
        self.assertEqual([x["sig"] for x in hr], [t])

    def test_descending_triangle_is_the_mirror(self):
        c = 1e4 / legs(ASC)
        o = np.r_[c[0], c[:-1]]
        b = bars_from_closes(c, 0.0)
        # mirror wicks exactly: the low of the mirror is 1e4 / the high of the original
        orig = bars_from_closes(legs(ASC))
        b["high"], b["low"] = 1e4 / orig["low"], 1e4 / orig["high"]
        dt = detect.scan(b, "DT", 5, 15, 250)
        at = detect.scan(orig, "AT", 5, 15, 250)
        self.assertEqual([x["sig"] for x in dt], [x["sig"] for x in at])
        self.assertAlmostEqual(dt[0]["level"], 1e4 / at[0]["level"], places=6)
        self.assertAlmostEqual(dt[0]["extreme"], 1e4 / at[0]["extreme"], places=6)
        o = detect.orders(b, "DT", 5, 15, 250, 63)[0]
        self.assertEqual(o["d"], -1)
        self.assertGreater(o["stop"], o["level"])
        self.assertLess(o["target"], o["level"])

    def test_flat_lows_are_a_rectangle_not_a_triangle(self):
        rect = [(0, 90), (10, 100), (20, 95), (30, 100), (40, 95), (50, 100), (60, 95), (72, 106)]
        b = bars_from_closes(legs(rect))
        self.assertEqual(detect.scan(b, "AT", 5, 15, 250), [])
        self.assertEqual(len(detect.scan(b, "HR", 5, 15, 250)), 1)

    def test_two_touches_is_not_hr(self):
        two = [(0, 90), (10, 100), (20, 92), (30, 100), (40, 95), (55, 106)]
        b = bars_from_closes(legs(two))
        self.assertEqual(detect.scan(b, "HR", 5, 15, 250), [])
        self.assertEqual(len(detect.scan(b, "H2R", 5, 15, 250)), 1)

    def test_a_close_above_the_level_breaks_containment(self):
        bad = [(0, 90), (10, 100), (20, 92), (30, 103), (40, 95), (50, 100), (58, 97), (70, 106)]
        b = bars_from_closes(legs(bad))
        for setup in ("AT", "HR", "H2R"):
            for s in detect.scan(b, setup, 5, 15, 250):
                self.assertGreaterEqual(s["first"], 30)
                self.assertGreater(s["level"], 103)

    def test_orders(self):
        b = bars_from_closes(legs(ASC))
        o = detect.orders(b, "AT", 5, 15, 250, 63)[0]
        self.assertAlmostEqual(o["target"], o["level"] + (o["level"] - o["extreme"]))
        self.assertAlmostEqual(o["stop"], o["extreme"] * (1 - 1e-4))
        self.assertEqual(o["deadline"], o["sig"] + 64)


class NoLookahead(unittest.TestCase):
    def test_truncation(self):
        for seed in range(6):
            o, h, l, c = path_walk(1500, seed, vol=0.02)
            b = {"t": pd.bdate_range("2000-01-03", periods=1500).to_numpy("datetime64[ns]"), "open": o, "high": h,
                 "low": l, "close": c}
            for setup in ["AT", "DT", "HR", "HS", "H2R", "H2S"]:
                full = detect.scan(b, setup, 5, 15, 250)
                for cut in (400, 777, 1200):
                    part = detect.scan({k: v[:cut] for k, v in b.items()}, setup, 5, 15, 250)
                    self.assertEqual(part, [s for s in full if s["sig"] < cut], (seed, setup, cut))

    def test_patterns_found_on_walks(self):
        n = {s: 0 for s in detect.SETUPS}
        for seed in range(10):
            o, h, l, c = path_walk(2700, seed, vol=0.02)
            b = {"open": o, "high": h, "low": l, "close": c}
            for s in n:
                n[s] += len(detect.scan(b, s, 5, 15, 250))
        self.assertTrue(all(v > 0 for v in n.values()), n)
        print("\nsignals on 10 random walks of 2,700 bars:", n)


if __name__ == "__main__":
    unittest.main()


class Controls(unittest.TestCase):
    def test_plain_breakout(self):
        from elliott import execute as X
        from patterns import controls as C
        path = legs([(0, 100), (30, 110), (60, 95), (80, 112), (100, 130), (200, 130)])
        b = bars_from_closes(path)
        X.prepare(b)
        N = 40
        # the first close above the prior 40-bar high
        j = next(j for j in range(N + 1, len(path)) if b["close"][j] > b["high"][j - N:j].max()
                 and b["close"][j - 1] <= b["high"][j - N - 1:j - 1].max())
        r = C.plain(b, j, N, 1, 63, 0.0)
        lvl, ext = b["high"][j - N:j].max(), b["low"][j - N:j].min()
        E, stop, tgt = b["open"][j + 1], ext * (1 - 1e-4), lvl + (lvl - ext)
        # by hand: the target is reached before the stop on this path
        k = next(k for k in range(j + 1, len(path)) if b["high"][k] >= tgt)
        self.assertTrue(all(b["low"][j + 1:k + 1] > stop))
        px = max(tgt, b["open"][k]) if k > j + 1 else tgt
        self.assertAlmostEqual(r, (px - E) / (E - stop), places=10)
        self.assertIsNone(C.plain(b, j + 1, N, 1, 63, 0.0))          # not the first close above
        self.assertIsNone(C.plain(b, j, N, -1, 63, 0.0))             # not a breakdown


class Membership(unittest.TestCase):
    def test_members(self):
        from patterns import run as RUN
        b = bars_from_closes(np.linspace(100, 110, 300))
        trades = [{"symbol": "A", "sig": 100, "deadline": 164}, {"symbol": "A", "sig": 250, "deadline": 314},
                  {"symbol": "A", "sig": 10, "deadline": 74}]
        lo, hi = str(pd.Timestamp(b["t"][50]).date()), str(pd.Timestamp(b["t"][260]).date())
        got = RUN.members(trades, {"A": b}, lo, hi)
        self.assertEqual([t["sig"] for t in got], [100])                 # 250's deadline is past the data; 10 is early
        got = RUN.members(trades, {"A": b}, None, None, last=str(pd.Timestamp(b["t"][150]).date()))
        self.assertEqual([t["sig"] for t in got], [10])
