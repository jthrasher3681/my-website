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

`.github/workflows/rectangle-screener.yml` runs the Yahoo refresh at
22:30 UTC on weekdays and commits the new data files. A run that loads fewer
than half the universe exits without overwriting the previous scan, and the
page flags a scan that is more than a few days old.

## Universe

`screener/universe.csv`: US-listed stocks with market cap ≥ $2B, price ≥ $5
and ≥ $20M traded per day (about 1,550 names), rebuilt from the daily
NASDAQ/NYSE/AMEX listings when `--refresh-universe` is passed.

## Tests

```sh
cd rectangle-screener
python3 -m unittest discover -s screener/tests -t .
```
