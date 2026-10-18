"""Download the daily history the strategy lab tests on (Yahoo Finance, via yfinance).

    python3 fetch_history.py [out_dir]

Writes one gzipped CSV per symbol (``^`` becomes ``_`` in the file name) with
date, open, high, low, close, adj_close, volume, dividends, splits. ``close``
is split-adjusted only and ``dividends`` is the cash paid per (split-adjusted)
share on its ex-date, so a total-return series can be rebuilt from the two and
checked against Yahoo's own ``adj_close``.

Run by .github/workflows/strategy-lab-data.yml: the research container cannot
reach Yahoo, and Robinhood's dividend-adjusted daily bars are unusable before
~2013 (missing and backwards adjustments).
"""
import os, sys, time
import pandas as pd
import yfinance as yf

ETFS = ["SPY", "QQQ", "IWM", "MDY", "DIA", "VTI", "EFA", "EEM", "VNQ", "GLD", "DBC",
        "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
        "BIL", "SGOV", "SHY", "IEF", "TLT", "AGG", "LQD", "TIP",
        "SSO", "UPRO", "QLD"]
FUNDS = ["VFINX", "VGTSX", "VBMFX", "VFISX", "VFITX", "VUSTX"]   # longer histories for the same asset classes
INDEXES = ["^GSPC", "^SP500TR", "^IRX", "^TNX", "^VIX"]
REQUIRED = {"SPY", "SSO", "VFINX", "^SP500TR", "^IRX"}


def fetch(sym, retries=4):
    for k in range(retries):
        try:
            df = yf.Ticker(sym).history(period="max", interval="1d", auto_adjust=False, actions=True)
            if len(df):
                return df
        except Exception as exc:  # rate limits and transient errors: back off and retry
            print(f"{sym}: {exc!r}", file=sys.stderr)
        time.sleep(5 * 2 ** k)
    return None


def main(out):
    os.makedirs(out, exist_ok=True)
    missing = []
    for sym in ETFS + FUNDS + INDEXES:
        df = fetch(sym)
        if df is None:
            missing.append(sym)
            print(f"{sym}: no data", file=sys.stderr)
            continue
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Adj Close": "adj_close",
                                "Volume": "volume", "Dividends": "dividends", "Stock Splits": "splits"})
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df.index.name = "date"
        df = df[[c for c in ("open", "high", "low", "close", "adj_close", "volume", "dividends", "splits") if c in df]]
        df = df[~df.index.duplicated(keep="last")].sort_index()
        df.to_csv(f"{out}/{sym.replace('^', '_')}.csv.gz", float_format="%.6f")
        print(f"{sym:9} {df.index[0].date()} .. {df.index[-1].date()} rows {len(df):6d} "
              f"dividends {int((df.get('dividends', 0) > 0).sum()):4d} last close {df['close'].iloc[-1]:.2f}")
        time.sleep(1)
    if REQUIRED & set(missing):
        sys.exit(f"missing required symbols: {sorted(REQUIRED & set(missing))}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "yahoo"))
