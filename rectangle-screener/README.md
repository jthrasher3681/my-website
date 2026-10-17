# Rectangle Screener

`/rectangle-screener/` is a daily-chart screener for the classic **rectangle**
pattern (a flat, horizontal trading range). It lists stocks that are

- **inside** an active rectangle as of the latest close, or
- broke out of one **recently** — a decisive close above resistance (bullish)
  or below support (bearish) within the last 10 sessions, with no close back
  inside since.

The page (`index.html`) is static. It reads two files that the scan writes:

| file | contents |
| --- | --- |
| `data/screen.json` | run metadata, detector parameters, and one row per match (levels, touches, breakout stats, a small close-price thumbnail) |
| `data/charts.json` | daily OHLCV around each match, loaded when a row is expanded |

## How a refresh works

`screener/build.py` loads daily bars for the universe, runs
`screener/rectangle.py`'s `detect()` on each stock, and writes the data files.

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
price ≥ $5 (preferreds, convertibles, notes and warrants excluded), rebuilt
from the daily NASDAQ/NYSE/AMEX listings when `--refresh-universe` is passed.
Each run then keeps only stocks with a median of at least $20M traded per day
over the last 50 sessions, measured on the downloaded bars rather than on one
day's listing snapshot.

## Tests

```sh
cd rectangle-screener
python3 -m unittest discover -s screener/tests -t .
```
