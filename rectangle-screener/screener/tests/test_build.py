import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import numpy as np
import pandas as pd

from screener import build
from screener.sources import load_hood_dumps, load_yfinance


def _bar(ts, o, h, l, c, v, interpolated=False):
    b = {"begins_at": ts, "open_price": str(o), "high_price": str(h), "low_price": str(l), "close_price": str(c), "volume": v}
    if interpolated:
        b["interpolated"] = True
    return b


def _dump(path, symbol, interval, bars):
    with open(path, "w") as fh:
        json.dump({"data": {"results": [{"symbol": symbol, "interval": interval, "bars": bars}]}, "guide": ""}, fh)


def _session(day, volume):
    """The 13 regular-session half-hour bars of a (daylight-time) day."""
    stamps = pd.date_range(f"{day} 13:30", periods=13, freq="30min", tz="UTC")
    return [_bar(ts.strftime("%Y-%m-%dT%H:%M:%SZ"), 10, 11, 9, 10, volume) for ts in stamps]


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

    def test_session_fetched_before_the_close_is_not_filled(self):
        with tempfile.TemporaryDirectory() as d:
            _dump(os.path.join(d, "daily_b000.json"), "ABC", "day", [_bar("2026-10-15T00:00:00Z", 10, 11, 9, 10, 1000)])
            path = os.path.join(d, "intra_b000.json")
            _dump(path, "ABC", "30minute", _session("2026-10-16", 10))
            fetched = datetime(2026, 10, 16, 19, 45, tzinfo=timezone.utc).timestamp()  # 3:45pm ET
            os.utime(path, (fetched, fetched))
            bars = load_hood_dumps(d)["ABC"]
        self.assertEqual(str(bars.index[-1].date()), "2026-10-15")

    def test_duplicate_intraday_bars_counted_once(self):
        with tempfile.TemporaryDirectory() as d:
            _dump(os.path.join(d, "daily_b000.json"), "ABC", "day", [_bar("2026-10-15T00:00:00Z", 10, 11, 9, 10, 2600)])
            _dump(os.path.join(d, "intra_b000.json"), "ABC", "30minute", _session("2026-10-15", 100) + _session("2026-10-16", 100))
            _dump(os.path.join(d, "intra_b001.json"), "ABC", "30minute", _session("2026-10-16", 100))
            bars = load_hood_dumps(d)["ABC"]
        self.assertAlmostEqual(bars.iloc[-1]["volume"], 2600)  # 13 x 100, scaled x2

    def test_empty_intraday_result_does_not_break_the_load(self):
        with tempfile.TemporaryDirectory() as d:
            _dump(os.path.join(d, "daily_b000.json"), "ABC", "day", [_bar("2026-10-15T00:00:00Z", 10, 11, 9, 10, 1000)])
            _dump(os.path.join(d, "intra_b000.json"), "ABC", "30minute", [])
            bars = load_hood_dumps(d)
        self.assertEqual(len(bars["ABC"]), 1)

    def test_market_wide_volume_ratio_without_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            _dump(os.path.join(d, "daily_b000.json"), "AAA", "day", [_bar("2026-10-15T00:00:00Z", 10, 11, 9, 10, 3900)])
            _dump(os.path.join(d, "daily_b001.json"), "BBB", "day", [_bar("2026-10-15T00:00:00Z", 10, 11, 9, 10, 500)])
            _dump(os.path.join(d, "intra_b000.json"), "AAA", "30minute", _session("2026-10-15", 100) + _session("2026-10-16", 100))
            _dump(os.path.join(d, "intra_b001.json"), "BBB", "30minute", _session("2026-10-16", 10))
            bars = load_hood_dumps(d)
        self.assertAlmostEqual(bars["BBB"].iloc[-1]["volume"], 130 * 3)  # AAA's 3x ratio
        self.assertEqual(bars["BBB"].attrs["filled_sessions"], ["2026-10-16"])


def _yahoo_frame(tickers, days, failed=()):
    """A frame shaped like yf.download(group_by="ticker", auto_adjust=False) output."""
    parts = {}
    for t in tickers:
        nan = t in failed  # yfinance reports a failed ticker as all-NaN columns
        parts[t] = pd.DataFrame(
            {
                "Open": float("nan") if nan else 10.0,
                "High": float("nan") if nan else 11.0,
                "Low": float("nan") if nan else 9.0,
                "Close": float("nan") if nan else 10.5,
                "Adj Close": float("nan") if nan else 10.4,
                "Volume": float("nan") if nan else 1000.0,
            },
            index=pd.DatetimeIndex(days, name="Date"),
        )
    return pd.concat(parts.values(), axis=1, keys=parts.keys(), names=["Ticker", "Price"])


class YahooLoaderTests(unittest.TestCase):
    def test_parses_frames_and_retries_failed_tickers(self):
        days = pd.bdate_range("2026-10-12", "2026-10-16")
        calls = []

        def fake_download(tickers, **kw):
            calls.append((list(tickers), kw))
            # BRK-B fails on the first pass only (e.g. a rate-limited request).
            return _yahoo_frame(tickers, days, failed={"BRK-B"} if len(calls) == 1 else set())

        fake = mock.MagicMock(download=fake_download)
        with mock.patch.dict(sys.modules, {"yfinance": fake}), mock.patch("time.sleep"):
            bars = load_yfinance(["AAPL", "BRK.B"], retries=2)

        self.assertEqual(sorted(bars), ["AAPL", "BRK.B"])
        self.assertEqual(list(bars["AAPL"].columns), ["open", "high", "low", "close", "volume"])
        self.assertEqual(bars["AAPL"]["close"].iloc[-1], 10.5)  # Close, not Adj Close
        self.assertIsNone(bars["AAPL"].index.tz)
        self.assertEqual(calls[0][0], ["AAPL", "BRK-B"])
        self.assertEqual(calls[1][0], ["BRK-B"])
        self.assertFalse(calls[0][1]["auto_adjust"])
        self.assertEqual(calls[0][1]["group_by"], "ticker")


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

    def test_pick_as_of_ignores_a_lagging_minority(self):
        days = pd.bdate_range("2026-10-12", "2026-10-16")
        frame = lambda n: pd.DataFrame({"close": 1.0}, index=days[:n])
        bars = {f"S{i}": frame(5) for i in range(9)} | {"LAG": frame(4)}
        self.assertEqual(build.pick_as_of(bars), days[-1])
        bars = {f"S{i}": frame(4) for i in range(5)} | {f"T{i}": frame(5) for i in range(5)}
        self.assertEqual(build.pick_as_of(bars), days[-2])

    def test_is_liquid_uses_the_median_dollar_volume(self):
        idx = pd.bdate_range("2026-08-03", periods=60)
        df = pd.DataFrame({"close": 50.0, "volume": 500_000.0}, index=idx)  # $25M a day
        self.assertTrue(build.is_liquid(df))
        df.loc[idx[-1], "volume"] = 10_000.0  # one quiet day doesn't matter
        self.assertTrue(build.is_liquid(df))
        df["volume"] = 300_000.0  # $15M a day
        self.assertFalse(build.is_liquid(df))

    def test_not_common_filter(self):
        self.assertTrue(build.NOT_COMMON.search("Strategy Inc Variable Rate Series A Perpetual Stretch Preferred Stock"))
        self.assertTrue(build.NOT_COMMON.search("Alphabet Inc. Depositary Shares representing a 1/20th Interest in a Share of Series A Mandatory Convertible Preferred Stock"))
        for name in ("Itau Unibanco Banco Holding SA American Depositary Shares (Each repstg 500 Preferred shares)",
                     "MPLX LP Common Units Representing Limited Partner Interests",
                     "America Movil S.A.B. de C.V. American Depositary Shares (each representing the right to receive twenty (20) Series B Shares"):
            self.assertIsNone(build.NOT_COMMON.search(name), name)

    def test_write_json_is_strict(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.json")
            build._write_json(path, {"ok": 1})
            with self.assertRaises(ValueError):
                build._write_json(path, {"bad": float("nan")})
            with open(path) as fh:
                self.assertEqual(json.load(fh), {"ok": 1})  # previous file left intact

    def test_volume_profile_declining_and_steady(self):
        steps = [100.0] * 10 + [80.0] * 10 + [50.0] * 10
        p = build.volume_profile(steps)
        self.assertEqual([round(x) for x in p["thirds"]], [100, 80, 50])
        self.assertLess(p["trend_pct"], -15)
        self.assertTrue(p["declining"])
        self.assertTrue(p["steady"])
        # a steady fade with noise is declining throughout
        rng = np.random.default_rng(1)
        fade = list(1e6 * np.linspace(1.0, 0.5, 60) * rng.uniform(0.8, 1.2, 60))
        self.assertTrue(build.volume_profile(fade)["steady"])

    def test_volume_profile_declining_but_not_steadily(self):
        # AMT, Jun-Oct 2026: busy start, quiet middle, a partial pick-up late in the box
        # (thirds ~100 -> 57 -> 79): the trend line falls, but not every third is lower
        rng = np.random.default_rng(3)
        amt = list(np.array([100.0] * 26 + [57.0] * 26 + [79.0] * 26) * rng.uniform(0.85, 1.15, 78))
        p = build.volume_profile(amt)
        self.assertTrue(p["declining"])
        self.assertFalse(p["steady"])
        # falls, then goes flat (or flat, then falls): not steady
        for v in ([100.0] * 10 + [80.0] * 10 + [79.0] * 10, [100.0] * 10 + [99.0] * 10 + [60.0] * 10):
            self.assertFalse(build.volume_profile(v)["steady"])
        # a long fade whose last week trades back above the middle of the box (GEV, EPD)
        p = build.volume_profile([100.0] * 30 + [85.0] * 30 + [70.0] * 25 + [140.0] * 5)
        self.assertLessEqual(p["thirds"][2], p["thirds"][1] * 0.95)
        self.assertFalse(p["steady"])
        self.assertTrue(build.volume_profile([100.0] * 30 + [85.0] * 30 + [70.0] * 30)["steady"])

    def test_volume_profile_not_declining(self):
        # steps down only slightly, rises, or the middle traded the most
        self.assertFalse(build.volume_profile([100.0] * 10 + [98.0] * 10 + [96.0] * 10)["declining"])
        self.assertFalse(build.volume_profile([50.0] * 15 + [100.0] * 15)["declining"])
        self.assertFalse(build.volume_profile([100.0] * 10 + [160.0] * 10 + [60.0] * 10)["steady"])
        # a trend line that falls while the last third trades like the first
        self.assertFalse(build.volume_profile([100.0] * 10 + [40.0] * 10 + [95.0] * 10)["declining"])

    def test_volume_profile_rarely_flags_noise(self):
        rng = np.random.default_rng(7)
        for n in (15, 30, 60):
            runs = [build.volume_profile(list(np.exp(rng.normal(0, 0.35, n)))) for _ in range(400)]
            self.assertLess(sum(p["declining"] for p in runs) / 400, 0.12, n)
            self.assertLess(sum(p["steady"] for p in runs) / 400, 0.05, n)

    def test_volume_profile_keep_and_line(self):
        decay = [1e6 * 0.99 ** t for t in range(30)]
        p = build.volume_profile(decay)
        self.assertAlmostEqual(p["trend_pct"], (0.99 ** 29 - 1) * 100, places=6)
        self.assertAlmostEqual(p["line"][0], 1e6, delta=1)
        self.assertAlmostEqual(p["line"][1], 1e6 * 0.99 ** 29, delta=1)
        # sessions left out (a breakout attempt's heavy volume) neither count nor shift the others in time
        spiked = list(decay)
        spiked[20] = spiked[21] = 9e6
        keep = [i not in (20, 21) for i in range(30)]
        q = build.volume_profile(spiked, keep=keep)
        self.assertAlmostEqual(q["trend_pct"], p["trend_pct"], places=6)
        self.assertAlmostEqual(q["line"][1], p["line"][1], delta=1)
        self.assertGreater(build.volume_profile(spiked)["trend_pct"], p["trend_pct"])

    def test_confirmation(self):
        days = pd.bdate_range("2026-10-01", periods=6)
        close = pd.Series([99.0, 99.5, 101.0, 103.2, 102.5, 102.0], index=days)
        up = {"status": "breakout_up", "top": 100.0, "bottom": 90.0, "breakout_date": "2026-10-05"}
        c = build.confirmation(close, up)
        self.assertEqual(c["confirmed_date"], "2026-10-06")
        self.assertAlmostEqual(c["max_close_beyond_pct"], 3.2)
        self.assertAlmostEqual(c["close_beyond_pct"], 2.0)
        # the breakout day itself can confirm; a close exactly 3% beyond counts
        down = {"status": "breakout_down", "top": 60.0, "bottom": 50.0, "breakout_date": "2026-10-02"}
        close = pd.Series([51.0, 49.0, 48.6, 48.5, 49.5, 49.0], index=days)
        c = build.confirmation(close, down)
        self.assertEqual(c["confirmed_date"], "2026-10-06")
        self.assertAlmostEqual(c["max_close_beyond_pct"], 3.0)
        self.assertAlmostEqual(c["close_beyond_pct"], 2.0)
        c = build.confirmation(close.iloc[:3], down)
        self.assertIsNone(c["confirmed_date"])
        self.assertAlmostEqual(c["max_close_beyond_pct"], 2.8)
        self.assertEqual(build.confirmation(close, {"status": "inside", "top": 60.0, "bottom": 50.0, "breakout_date": None}),
                         {"close_beyond_pct": None, "max_close_beyond_pct": None, "confirmed_date": None})

    def test_volume_profile_robust_inputs(self):
        # one spike does not move a third's median; missing prints are skipped
        p = build.volume_profile([100.0] * 9 + [1e9] + [70.0] * 10 + [60.0] * 10)
        self.assertEqual([round(x) for x in p["thirds"]], [100, 70, 60])
        p = build.volume_profile([100.0, float("nan"), 0.0] * 5 + [70.0] * 6 + [50.0] * 9)
        self.assertEqual([round(x) for x in p["thirds"]], [100, 70, 50])
        self.assertIsNone(build.volume_profile([100.0] * 8))
        self.assertIsNone(build.volume_profile([float("nan")] * 30))

    def test_clean_name(self):
        self.assertEqual(build.clean_name("Apple Inc. Common Stock"), "Apple Inc.")
        self.assertEqual(build.clean_name("Alphabet Inc. Class A Common Stock"), "Alphabet Inc.")
        self.assertEqual(build.clean_name("Taiwan Semiconductor Manufacturing Company Ltd."), "Taiwan Semiconductor Manufacturing Company Ltd.")

    def test_round_hit(self):
        hit = {"top": 12.3456, "bottom": 0.123456, "target": 0.98765, "height_pct": 3.14159, "quality": 77.77,
               "touches": [{"date": "2026-10-01", "side": "top", "price": 12.3456}]}
        r = build._round_hit(hit)
        self.assertEqual(r["top"], 12.3456)          # levels are re-checked next scan: kept exact
        self.assertEqual(r["bottom"], 0.123456)
        self.assertEqual(r["target"], 0.9877)
        self.assertEqual(r["height_pct"], 3.14)
        self.assertEqual(r["quality"], 77.8)
        self.assertEqual(r["touches"][0]["price"], 12.35)


if __name__ == "__main__":
    unittest.main()
