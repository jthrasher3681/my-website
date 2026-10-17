"""Tests for the backtest's trade rules on small hand-made bars.

    cd rectangle-screener && python3 -m unittest discover -s screener/tests -t .
"""

import unittest

import numpy as np
import pandas as pd

from screener import backtest


def arrays(rows):
    """[(open, high, low, close), ...] -> four float arrays."""
    return [np.array(col, float) for col in zip(*rows)]


class SimulateTests(unittest.TestCase):
    # a long from a 90-100 box: line 100, target 110; bar 0 is the confirming close
    def test_target(self):
        o, h, l, c = arrays([(103, 104, 102, 103), (103.5, 106, 103, 105), (105, 111, 104, 109)])
        self.assertEqual(backtest.simulate(o, h, l, c, 0, 1, 100.0, 110.0), (2, 110.0, "target", "target"))

    def test_gap_through_target_fills_at_the_open(self):
        o, h, l, c = arrays([(103, 104, 102, 103), (104, 105, 103, 104), (112, 113, 111, 112)])
        self.assertEqual(backtest.simulate(o, h, l, c, 0, 1, 100.0, 110.0)[:3], (2, 112.0, "target"))

    def test_close_back_inside_exits_next_open(self):
        o, h, l, c = arrays([(103, 104, 102, 103), (103, 104, 98, 99), (98.5, 99, 97, 98)])
        self.assertEqual(backtest.simulate(o, h, l, c, 0, 1, 100.0, 110.0), (2, 98.5, "failed", "open"))

    def test_target_and_close_inside_on_one_session_counts_as_target(self):
        o, h, l, c = arrays([(103, 104, 102, 103), (104, 111, 98, 99), (98, 99, 97, 98)])
        self.assertEqual(backtest.simulate(o, h, l, c, 0, 1, 100.0, 110.0)[2], "target")

    def test_timeout(self):
        o, h, l, c = arrays([(103, 104, 102, 103)] + [(104, 105, 103, 104)] * 5)
        self.assertEqual(backtest.simulate(o, h, l, c, 0, 1, 100.0, 110.0, max_hold=3), (3, 104.0, "timeout", "close"))

    def test_undecided_when_data_ends(self):
        o, h, l, c = arrays([(103, 104, 102, 103)] + [(104, 105, 103, 104)] * 2)
        self.assertIsNone(backtest.simulate(o, h, l, c, 0, 1, 100.0, 110.0, max_hold=5))
        # failed on the last bar: the exit open isn't known yet
        o, h, l, c = arrays([(103, 104, 102, 103), (103, 104, 98, 99)])
        self.assertIsNone(backtest.simulate(o, h, l, c, 0, 1, 100.0, 110.0))

    def test_no_target(self):
        o, h, l, c = arrays([(103, 104, 102, 103), (103.5, 106, 103, 105), (105, 111, 104, 109), (109, 112, 108, 99),
                             (98, 99, 97, 98)])
        self.assertEqual(backtest.simulate(o, h, l, c, 0, 1, 100.0, None), (4, 98.0, "failed", "open"))

    def test_short(self):
        # breakdown from a 100-110 box: line 100, target 90
        o, h, l, c = arrays([(97, 98, 96, 97), (96.5, 97, 89, 91)])
        self.assertEqual(backtest.simulate(o, h, l, c, 0, -1, 100.0, 90.0), (1, 90.0, "target", "target"))
        o, h, l, c = arrays([(97, 98, 96, 97), (98, 101.5, 97, 101), (101.2, 102, 100, 101)])
        self.assertEqual(backtest.simulate(o, h, l, c, 0, -1, 100.0, 90.0), (2, 101.2, "failed", "open"))


class FlatBench:
    def span(self, signal, entry, exit_, exit_at):
        return 0.0

    def path(self, signal, entry, dates):
        return [0.0] * len(dates)


class TradesTests(unittest.TestCase):
    def setUp(self):
        idx = pd.bdate_range("2024-01-01", periods=80)
        close = np.full(80, 95.0)
        close[40:] = [101.0, 102.0, 103.5, 104.0] + [104.5] * 36    # breakout at bar 40, 3%+ at bar 42
        self.df = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close,
                                "volume": np.full(80, 1e6)}, index=idx)
        box = {"status": "breakout_up", "top": 100.0, "bottom": 90.0, "start": idx[10].strftime("%Y-%m-%d"),
               "end": idx[39].strftime("%Y-%m-%d"), "bars": 30, "height_pct": 11.1, "top_touches": 3,
               "bottom_touches": 3, "switches": 4, "breakout_date": idx[40].strftime("%Y-%m-%d"),
               "breakout_volume_ratio": 1.0, "failed_breakout": None, "quality": 60.0}
        self.rows = {"X": {idx[k]: {**box, "days_since_breakout": k - 40} for k in range(40, 51)}}

    def test_confirmation_threshold_picks_the_first_close_far_enough_past(self):
        bars = {"X": self.df}
        any_ = backtest.trades(self.rows, bars, 0.0, FlatBench(), max_hold=20)
        three = backtest.trades(self.rows, bars, 3.0, FlatBench(), max_hold=20)
        self.assertEqual([t["signal_date"] for t in any_], ["2024-02-26"])      # breakout day, bar 40
        self.assertEqual([t["signal_date"] for t in three], ["2024-02-28"])     # bar 42: 103.5 is 3.5% past
        self.assertEqual(three[0]["days_to_signal"], 2)
        self.assertEqual(three[0]["entry"], 104.0)                               # next open
        self.assertEqual(three[0]["outcome"], "timeout")                         # target 110 never reached
        self.assertAlmostEqual(three[0]["ret"], 0.5 / 104 * 100)
        self.assertEqual((three[0]["run_outcome"], three[0]["run_held"]), ("timeout", 20))
        self.assertFalse(three[0]["target_at_entry"])

    def test_one_signal_per_breakout(self):
        ts = backtest.trades(self.rows, {"X": self.df}, 1.0, FlatBench(), max_hold=5)
        self.assertEqual(len(ts), 1)


if __name__ == "__main__":
    unittest.main()
