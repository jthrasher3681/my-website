"""Download hourly bars for the Elliott Wave study (Yahoo Finance, via yfinance).

    python3 fetch_intraday.py [out_dir]

Yahoo keeps 730 days of hourly bars. For each symbol in
``elliott/hourly_symbols.txt`` (30 ETFs, then the most traded US stocks), this
writes one gzipped CSV of regular-session bars: ts (bar start, New York time),
open, high, low, close, volume. Prices are split-adjusted, not
dividend-adjusted. Run by .github/workflows/strategy-lab-intraday.yml.
"""
import os, sys, time
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
CHUNK = 40


def split(data, chunk):
    """Per-symbol frames from a ``yf.download(group_by="ticker")`` result."""
    out = {}
    if isinstance(data.columns, pd.MultiIndex):
        for s in chunk:
            if s in data.columns.get_level_values(0):
                out[s] = data[s]
    elif len(chunk) == 1:
        out[chunk[0]] = data
    return out


def main(out):
    os.makedirs(out, exist_ok=True)
    syms = [s.strip() for s in open(os.path.join(HERE, "elliott", "hourly_symbols.txt")) if s.strip()]
    todo, done = list(syms), set()
    for attempt in range(3):
        for i in range(0, len(todo), CHUNK):
            chunk = todo[i:i + CHUNK]
            try:
                data = yf.download(chunk, period="730d", interval="1h", auto_adjust=False, group_by="ticker",
                                   threads=True, progress=False, prepost=False)
            except Exception as exc:
                print(f"batch failed: {exc!r}", file=sys.stderr)
                time.sleep(30)
                continue
            for s, df in split(data, chunk).items():
                df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
                if len(df) < 500:
                    continue
                idx = pd.to_datetime(df.index)
                idx = idx.tz_convert("America/New_York") if idx.tz is not None else idx
                df.index = idx.tz_localize(None)
                df.index.name = "ts"
                df = df[~df.index.duplicated(keep="last")].sort_index()
                df.to_csv(os.path.join(out, f"{s}.csv.gz"), float_format="%.4f")
                done.add(s)
            time.sleep(3)
        todo = [s for s in syms if s not in done]
        print(f"pass {attempt + 1}: {len(done)} saved, {len(todo)} missing", flush=True)
        if not todo:
            break
        time.sleep(60)
    if todo:
        print("missing:", " ".join(todo))
    if len(done) < 0.9 * len(syms):
        sys.exit("fewer than 90% of symbols downloaded")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data", "yahoo_1h"))
