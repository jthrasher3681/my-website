# Rectangle Screener

`/rectangle-screener/` is a daily-chart screener for the classic **rectangle**
pattern (a flat, horizontal trading range). It lists stocks that are

- **inside** an active rectangle as of the latest close, or
- broke out of one **recently** — a decisive close above resistance (bullish)
  or below support (bearish) within the last 10 sessions, with no close back
  inside since. A breakout counts as **confirmed** once a daily close has
  reached 3% past the broken line.

The page (`index.html`) is static. It reads two files that the scan writes:

| file | contents |
| --- | --- |
| `data/screen.json` | run metadata, detector parameters, and one row per match (levels, touches, breakout stats, a small close-price thumbnail) |
| `data/charts.json` | daily OHLCV around each match, loaded when a row is expanded |

## Detection

`screener/rectangle.py` finds the best rectangle that is still current for one
stock (its docstring explains the algorithm and the quality score; every
threshold lives in `DEFAULT_PARAMS`). It was picked from three independently
written detectors (window scan, zigzag pivots, horizontal-level clustering)
and then tuned, using three checks:

- a labeled synthetic benchmark of 725 daily charts, including trends,
  channels, triangles, wedges, broadening patterns, flags, stale breakouts and
  whipsaws that must be rejected: precision 1.00, recall 0.86, status correct
  on every detection;
- blind grading of its real-stock picks by two independent chart readers: on
  the Oct 16, 2026 scan, 0.87 of the 185 picks were judged genuine rectangles
  (borderline counted as half) and picks scoring 60+ quality were judged 0.95;
- a replay of the last 25 sessions over the whole universe: a box shown inside
  one day is shown as a breakout the day it breaks out (whipsaws excepted),
  and boxes that still qualify do not drop out from one day to the next.

A box's first touch must be approached from at least 45% of the box height
away, so a pause in the trend leg into the range doesn't count as a test of
the line. Once a box is established from later touches, its start is
extended back to the first bounce after price entered the range. That bounce
only needs to come from 30% of the height away. On the Oct 16, 2026 scan this
moved 9 of 167 box starts earlier (AMT's to Jun 24) and changed nothing
else.

## Volume in box

`build.py` adds these volume fields to each row (`volume_profile`). Sessions
in the box that closed beyond a line are left out: that volume belongs to a
breakout attempt, not to the range.

- `volume_trend_pct`: a Theil-Sen trend line through the log volume of the
  box's sessions, as the % change from its first to its last session;
  `volume_line` is that line's volume at both ends (the dashed line on the
  chart).
- `volume_thirds`: the median volume of each third of the box, as % of the
  first.
- `volume_declining`: the trend line falls at least 15%, the last third
  trades at least 15% below the first, and a Mann-Kendall test says the
  decline is unlikely to be noise (p < 0.10). On trendless random volume this
  fires 4-9% of the time.
- `volume_steady`: declining *throughout*. Each third also trades at least 5%
  less than the one before, p < 0.05, and the last week and last sixth of the
  box trade no more than its middle third (no late surge). This fires about 2%
  of the time on random volume.

AMT's Jun-Oct 2026 box is the reference case for "declining". Volume is busy
when price enters the range, quiet through August, and picks up a little in
September (thirds 100 → 57 → 79, trend −24%). It is declining, but not
steadily.

## Breakout confirmation

For a breakout row, `confirmation()` measures how far each close since the
breakout day got past the broken line, as % of the line's price:
`close_beyond_pct` (latest close), `max_close_beyond_pct` (furthest close)
and `confirmed_date` (the first close at least `CONFIRM_PCT` = 3% past the
line, or null). The page filters on it and draws the 3% level on the chart.

## How a refresh works

`screener/build.py` loads daily bars for the universe, runs
`screener/rectangle.py`'s `detect()` on each stock, and writes the data files.
Each stock's box from the previous scan (the committed `data/screen.json`) is
passed back to `detect()` as a hint and re-checked on the new bars, so a
rectangle that still qualifies doesn't drop out of the list for a day just
because one new bar shifted the swing points the lines are fitted to.

```sh
cd rectangle-screener
pip install -r screener/requirements.txt

# Yahoo Finance (what the scheduled GitHub Action runs after each close)
python3 -m screener.build --yfinance --refresh-universe

# or: Robinhood get_equity_historicals dumps (daily_*.json, plus optional
# intra_*.json 30-minute bars to fill a session whose daily bar isn't out yet)
python3 -m screener.build --hood-dir path/to/dumps
```

`.github/workflows/rectangle-screener.yml` runs the unit tests and then the
Yahoo refresh at 22:30 UTC on weekdays, and commits the new data files when
there is a newer session (market holidays are no-ops). The scan date is the
latest session at least 80% of the universe has reached; if fewer than 80% of
stocks have data through it, the run exits without overwriting the previous
scan. The page flags a scan that has missed two or more sessions.

A session filled in from Robinhood's 30-minute bars (because its daily bar
wasn't published yet) is marked provisional on the page: its close is the
last half-hour's close and its volume is scaled up from the half-hour bars.

## Universe

`screener/universe.csv`: US-listed common stocks with market cap ≥ $2B and
price ≥ $5 (preferreds, convertibles, notes, warrants and equity units
excluded), rebuilt from the daily NASDAQ/NYSE/AMEX listings when
`--refresh-universe` is passed. The listing step only drops names that traded
less than $5M on the listing day.
Each run then keeps only stocks with a median of at least $20M traded per day
over the last 50 sessions, measured on the downloaded bars rather than on one
day's listing snapshot.

## Tests

```sh
cd rectangle-screener
python3 -m unittest discover -s screener/tests -t .
```
