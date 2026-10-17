"""Tests for the rectangle detector on small deterministic synthetic series.

Each series is a piecewise-linear close path (waypoints) with a little seeded noise and
short wicks, so the expected answer is unambiguous.

    cd rectangle-screener && python3 -m unittest discover -s screener/tests -t .
"""

import json
import math
import re
import unittest

import numpy as np
import pandas as pd

from screener import rectangle

SPEC_KEYS = {
    "status", "top", "bottom", "start", "end", "bars", "height_pct", "top_touches",
    "bottom_touches", "switches", "touches", "breakout_date", "days_since_breakout",
    "breakout_volume_ratio", "position_pct", "extension_pct", "target",
    "failed_breakout", "atr_pct", "quality",
}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def series(waypoints, seed=0, noise=0.12, wick=0.3, volume=None):
    """Daily bars following waypoints [(0, start_price), (n_bars, price), ...]."""
    rng = np.random.default_rng(seed)
    path = [float(waypoints[0][1])]
    for n, price in waypoints[1:]:
        path.extend(np.linspace(path[-1], price, n + 1)[1:])
    close = np.asarray(path) + rng.normal(0.0, noise, len(path))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.0, wick, len(close))
    low = np.minimum(open_, close) - rng.uniform(0.0, wick, len(close))
    vol = rng.uniform(0.8e6, 1.2e6, len(close)) if volume is None else volume
    index = pd.bdate_range("2025-01-02", periods=len(close))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=index)


# A 100-110 box reached by a rally: first touch of the top at bar 40, then six
# swings of eight bars between the lines (bars 40..88).
LEAD = [(0, 80.0), (40, 110.0)]
BOX = [(8, 100.0), (8, 110.0), (8, 100.0), (8, 110.0), (8, 100.0), (8, 110.0)]
FIRST_TOUCH = 40


class RectangleStatusTests(unittest.TestCase):
    def assertBox(self, r, top=110.0, bottom=100.0, tol=1.0):
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r["top"], top, delta=tol)
        self.assertAlmostEqual(r["bottom"], bottom, delta=tol)
        self.assertGreaterEqual(r["switches"], 3)
        self.assertGreaterEqual(r["top_touches"], 2)
        self.assertGreaterEqual(r["bottom_touches"], 2)

    def test_inside(self):
        df = series(LEAD + BOX + [(6, 104.0)])
        r = rectangle.detect(df)
        self.assertBox(r)
        self.assertEqual(r["status"], "inside")
        self.assertEqual(r["end"], df.index[-1].strftime("%Y-%m-%d"))
        start = df.index.get_loc(pd.Timestamp(r["start"]))
        self.assertLessEqual(abs(start - FIRST_TOUCH), 3)       # the rally leg is excluded
        self.assertIsNone(r["failed_breakout"])
        self.assertIsNone(r["breakout_date"])
        self.assertIsNone(r["target"])
        self.assertTrue(0.0 < r["position_pct"] < 100.0)

    def test_breakout_up(self):
        df = series(LEAD + BOX + [(8, 100.0), (8, 109.0), (1, 114.0), (3, 116.0)])
        r = rectangle.detect(df)
        self.assertBox(r)
        self.assertEqual(r["status"], "breakout_up")
        self.assertEqual(r["days_since_breakout"], 3)
        self.assertEqual(r["breakout_date"], df.index[-4].strftime("%Y-%m-%d"))
        self.assertEqual(r["end"], df.index[-5].strftime("%Y-%m-%d"))
        self.assertAlmostEqual(r["target"], r["top"] + (r["top"] - r["bottom"]), places=3)
        self.assertGreater(r["extension_pct"], 0.0)
        self.assertIsNone(r["failed_breakout"])

    def test_breakout_down(self):
        df = series(LEAD + BOX + [(8, 101.0), (1, 96.0), (2, 95.0)])
        r = rectangle.detect(df)
        self.assertBox(r)
        self.assertEqual(r["status"], "breakout_down")
        self.assertEqual(r["days_since_breakout"], 2)
        self.assertAlmostEqual(r["target"], r["bottom"] - (r["top"] - r["bottom"]), places=3)
        self.assertLess(r["position_pct"], 0.0)

    def test_breakout_volume_ratio(self):
        df = series(LEAD + BOX + [(8, 101.0), (1, 96.0), (2, 95.0)])
        df.loc[df.index[-3], "volume"] = 3.0e6               # the breakout bar
        r = rectangle.detect(df)
        self.assertEqual(r["status"], "breakout_down")
        self.assertGreater(r["breakout_volume_ratio"], 2.5)

    def test_failed_breakout_up(self):
        # breaks above the top for two closes, then falls back into the box
        df = series(LEAD + BOX + [(1, 113.0), (1, 113.5), (4, 106.0), (3, 104.0)])
        r = rectangle.detect(df)
        self.assertBox(r)
        self.assertEqual(r["status"], "inside")
        self.assertEqual(r["failed_breakout"], "up")
        self.assertIsNone(r["breakout_date"])

    def test_failed_breakout_down(self):
        df = series(LEAD + BOX + [(8, 100.0), (1, 97.0), (1, 96.5), (4, 104.0), (3, 106.0)])
        r = rectangle.detect(df)
        self.assertBox(r)
        self.assertEqual(r["status"], "inside")
        self.assertEqual(r["failed_breakout"], "down")

    def test_stale_breakout_is_out_of_scope(self):
        # broke out 20 bars ago (> max_breakout_age) and kept trending
        df = series(LEAD + BOX + [(1, 114.0), (19, 128.0)])
        self.assertIsNone(rectangle.detect(df))

    def test_breakout_then_reversal_is_out_of_scope(self):
        # broke out up, held above for weeks, then fell back through the whole box
        df = series(LEAD + BOX + [(1, 114.0), (14, 116.0), (6, 96.0), (1, 95.0)])
        self.assertIsNone(rectangle.detect(df))

    def test_breakout_age_parameter(self):
        df = series(LEAD + BOX + [(8, 100.0), (8, 109.0), (1, 114.0), (3, 116.0)])
        self.assertEqual(rectangle.detect(df)["status"], "breakout_up")
        self.assertIsNone(rectangle.detect(df, {"max_breakout_age": 2}))


class RectangleRejectionTests(unittest.TestCase):
    def test_trend(self):
        rng = np.random.default_rng(3)
        steps = rng.normal(0.25, 1.0, 160)
        self.assertIsNone(rectangle.detect(series([(0, 50.0)] + [(1, 50.0 + x) for x in np.cumsum(steps)])))

    def test_rising_channel(self):
        # swings between two parallel lines rising 4 points per swing
        legs = [(0, 80.0)] + [(8, 92.0 + 4 * i) if i % 2 == 0 else (8, 82.0 + 4 * i) for i in range(10)]
        self.assertIsNone(rectangle.detect(series(legs)))

    def test_symmetric_triangle(self):
        legs = [(0, 80.0), (30, 120.0)]
        for i in range(1, 7):
            amp = 20.0 * (1 - i / 7)
            legs.append((7, 100.0 - amp if i % 2 else 100.0 + amp))
        self.assertIsNone(rectangle.detect(series(legs, noise=0.05, wick=0.15)))

    def test_too_narrow(self):
        # a 1.5% box: below min_height_pct and only a few ATRs tall
        box = [(8, 100.0), (8, 101.5)] * 3
        self.assertIsNone(rectangle.detect(series([(0, 85.0), (30, 101.5)] + box + [(4, 100.7)])))

    def test_too_short(self):
        # a clean 100-110 range of only ~10 bars after the rally (min_bars is 15)
        df = series(LEAD + [(3, 100.0), (3, 110.0), (3, 100.0), (2, 104.0)])
        self.assertIsNone(rectangle.detect(df))

    def test_degenerate_input(self):
        self.assertIsNone(rectangle.detect(series([(0, 100.0), (10, 101.0)])))
        flat = series([(0, 100.0), (80, 100.0)], noise=0.0, wick=0.0)
        self.assertIsNone(rectangle.detect(flat))
        self.assertIsNone(rectangle.detect(flat.iloc[:0]))


class RectangleContractTests(unittest.TestCase):
    def setUp(self):
        self.df = series(LEAD + BOX + [(8, 101.0), (1, 96.0), (2, 95.0)])
        self.r = rectangle.detect(self.df)

    def test_default_params(self):
        P = rectangle.DEFAULT_PARAMS
        self.assertEqual(P["max_breakout_age"], 10)
        for key in ("min_bars", "min_touches_per_side", "min_switches", "min_height_atr",
                    "min_height_pct", "max_height_pct", "breakout_buffer_atr"):
            self.assertIn(key, P)
        json.dumps(P)                         # published in the page's JSON

    def test_keys_and_types(self):
        r = self.r
        self.assertEqual(set(r), SPEC_KEYS)
        json.dumps(r)
        for key in ("status", "start", "end"):
            self.assertIsInstance(r[key], str)
        for key in ("top", "bottom", "height_pct", "position_pct", "atr_pct", "quality",
                    "extension_pct", "target", "breakout_volume_ratio"):
            self.assertIs(type(r[key]), float, key)
            self.assertTrue(math.isfinite(r[key]), key)
        for key in ("bars", "top_touches", "bottom_touches", "switches", "days_since_breakout"):
            self.assertIs(type(r[key]), int, key)
        self.assertRegex(r["start"], DATE)
        self.assertRegex(r["end"], DATE)
        self.assertRegex(r["breakout_date"], DATE)
        self.assertIn(r["failed_breakout"], (None, "up", "down"))
        self.assertTrue(0.0 <= r["quality"] <= 100.0)

    def test_touches(self):
        touches = self.r["touches"]
        self.assertEqual(len(touches), self.r["top_touches"] + self.r["bottom_touches"])
        self.assertEqual([t["date"] for t in touches], sorted(t["date"] for t in touches))
        for t in touches:
            self.assertEqual(set(t), {"date", "side", "price"})
            self.assertRegex(t["date"], DATE)
            self.assertIn(t["side"], ("top", "bottom"))
            self.assertIs(type(t["price"]), float)
            self.assertTrue(self.r["start"] <= t["date"] <= self.r["end"])

    def test_internal_consistency(self):
        r = self.r
        self.assertGreater(r["top"], r["bottom"])
        start = self.df.index.get_loc(pd.Timestamp(r["start"]))
        end = self.df.index.get_loc(pd.Timestamp(r["end"]))
        self.assertEqual(r["bars"], end - start + 1)
        self.assertAlmostEqual(r["height_pct"], (r["top"] - r["bottom"]) / r["bottom"] * 100, places=2)
        last = float(self.df["close"].iloc[-1])
        self.assertAlmostEqual(r["position_pct"], (last - r["bottom"]) / (r["top"] - r["bottom"]) * 100, places=1)

    def test_pure_and_deterministic(self):
        before = self.df.copy()
        again = rectangle.detect(self.df)
        self.assertEqual(again, self.r)
        pd.testing.assert_frame_equal(self.df, before)

    def test_missing_values_and_volume(self):
        df = self.df.copy()
        df.loc[df.index[5], "close"] = np.nan          # a bad print far from the box
        r = rectangle.detect(df.drop(columns="volume"))
        self.assertEqual(r["status"], "breakout_down")
        self.assertIsNone(r["breakout_volume_ratio"])


if __name__ == "__main__":
    unittest.main()
