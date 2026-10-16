import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

import pandas as pd

from screener import build
from screener.sources import load_hood_dumps


def _bar(ts, o, h, l, c, v, interpolated=False):
    b = {"begins_at": ts, "open_price": str(o), "high_price": str(h), "low_price": str(l), "close_price": str(c), "volume": v}
    if interpolated:
        b["interpolated"] = True
    return b


def _dump(path, symbol, interval, bars):
    with open(path, "w") as fh:
        json.dump({"data": {"results": [{"symbol": symbol, "interval": interval, "bars": bars}]}, "guide": ""}, fh)


class HoodDumpTests(unittest.TestCase):
    def test_daily_plus_intraday_fill(self):
        with tempfile.TemporaryDirectory() as d:
            _dump(
                os.path.join(d, "daily_b000.json"),
                "ABC",
                "day",
                [
                    _bar("2026-10-14T00:00:00Z", 10, 11, 9, 10.5, 3000),
                    _bar("2026-10-15T00:00:00Z", 10.5, 12, 10, 11, 3000),
                    _bar("2026-10-16T00:00:00Z", 11, 11, 11, 11, 0, interpolated=True),
                ],
            )
            half_hours = pd.date_range("2026-10-15 13:30", periods=13, freq="30min", tz="UTC").append(
                pd.date_range("2026-10-16 13:30", periods=13, freq="30min", tz="UTC")
            )
            intra = [
                _bar(ts.strftime("%Y-%m-%dT%H:%M:%SZ"), 11 + i * 0.01, 11.5 + i * 0.01, 10.8, 11 + i * 0.02, 100)
                for i, ts in enumerate(half_hours)
            ]
            _dump(os.path.join(d, "intra_b000.json"), "ABC", "30minute", intra)

            bars = load_hood_dumps(d)["ABC"]

        self.assertEqual([str(x.date()) for x in bars.index], ["2026-10-14", "2026-10-15", "2026-10-16"])
        last = bars.iloc[-1]
        self.assertAlmostEqual(last["open"], 11 + 13 * 0.01)
        self.assertAlmostEqual(last["close"], 11 + 25 * 0.02)
        self.assertAlmostEqual(last["low"], 10.8)
        # 13 half-hour bars of 100 vs a 3000 daily bar on 10-15 -> scale x(3000/1300)
        self.assertAlmostEqual(last["volume"], 1300 * 3000 / 1300)
        # The published 10-15 daily bar wins over the intraday aggregate.
        self.assertEqual(bars.loc["2026-10-15", "close"], 11)

    def test_incomplete_intraday_session_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            _dump(os.path.join(d, "daily_b000.json"), "ABC", "day", [_bar("2026-10-15T00:00:00Z", 10, 11, 9, 10, 1000)])
            stamps = pd.date_range("2026-10-16 13:30", periods=5, freq="30min", tz="UTC")
            _dump(os.path.join(d, "intra_b000.json"), "ABC", "30minute",
                  [_bar(ts.strftime("%Y-%m-%dT%H:%M:%SZ"), 10, 11, 9, 10, 10) for ts in stamps])
            bars = load_hood_dumps(d)["ABC"]
        self.assertEqual(str(bars.index[-1].date()), "2026-10-15")


class BuildHelperTests(unittest.TestCase):
    def test_thumb_keeps_endpoints_and_caps_points(self):
        closes = list(range(300))
        t = build.thumb(closes)
        self.assertEqual(t[0], 0)
        self.assertEqual(t[-1], 299)
        self.assertLessEqual(len(t), build.THUMB_POINTS)
        self.assertEqual(build.thumb([5.0, 6.0]), [5.0, 6.0])

    def test_drop_incomplete_session(self):
        idx = pd.to_datetime(["2026-10-15", "2026-10-16"])
        df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
        bars = {"A": df.copy()}
        build.drop_incomplete_session(bars, datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc))  # 2pm ET
        self.assertEqual(len(bars["A"]), 1)
        bars = {"A": df.copy()}
        build.drop_incomplete_session(bars, datetime(2026, 10, 16, 22, 30, tzinfo=timezone.utc))  # 6:30pm ET
        self.assertEqual(len(bars["A"]), 2)

    def test_clean_name(self):
        self.assertEqual(build.clean_name("Apple Inc. Common Stock"), "Apple Inc.")
        self.assertEqual(build.clean_name("Alphabet Inc. Class A Common Stock"), "Alphabet Inc.")
        self.assertEqual(build.clean_name("Taiwan Semiconductor Manufacturing Company Ltd."), "Taiwan Semiconductor Manufacturing Company Ltd.")

    def test_round_hit(self):
        hit = {"top": 12.3456, "bottom": 0.123456, "target": None, "height_pct": 3.14159, "quality": 77.77,
               "touches": [{"date": "2026-10-01", "side": "top", "price": 12.3456}]}
        r = build._round_hit(hit)
        self.assertEqual(r["top"], 12.35)
        self.assertEqual(r["bottom"], 0.1235)
        self.assertIsNone(r["target"])
        self.assertEqual(r["height_pct"], 3.14)
        self.assertEqual(r["quality"], 77.8)
        self.assertEqual(r["touches"][0]["price"], 12.35)


if __name__ == "__main__":
    unittest.main()
