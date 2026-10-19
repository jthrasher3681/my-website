"""Download long weekly and monthly histories for the triangle / support-resistance
study (Yahoo Finance, via yfinance).

    python3 fetch_long.py [out_dir]

For every symbol in ``../rectangle-screener/screener/universe.csv`` (the
rectangle screener's universe: US-listed common stocks of at least $2B as of
October 2026), this downloads Yahoo's whole history at two intervals, weekly
(``1wk``, bars start on Mondays) and monthly (``1mo``). Prices are
split-adjusted; ``adjclose`` also folds in dividends. Bars after the last
complete week (to 2026-10-16) or month (to 2026-09-30) are dropped.

Writes ``weekly.npz`` and ``monthly.npz``: ``symbols``, ``start`` (each
symbol's first row; the rows of symbol i are start[i]:start[i + 1]), ``t`` (bar
start dates, days since 1970-01-01), and float32 ``open``, ``high``, ``low``,
``close``, ``adjclose``, ``volume``. Run by
.github/workflows/strategy-lab-long.yml.
"""
import csv, os, sys, time
import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
UNIVERSE = os.path.join(HERE, "..", "rectangle-screener", "screener", "universe.csv")
CHUNK = 50
LAST = {"1wk": "2026-10-12", "1mo": "2026-09-01"}     # last bar start kept


def yahoo(sym):
    return sym.replace(".", "-").replace("/", "-")


def split(data, chunk):
    out = {}
    if isinstance(data.columns, pd.MultiIndex):
        for s in chunk:
            if s in data.columns.get_level_values(0):
                out[s] = data[s]
    elif len(chunk) == 1:
        out[chunk[0]] = data
    return out


def fetch(syms, interval):
    frames, todo = {}, list(syms)
    for attempt in range(3):
        for i in range(0, len(todo), CHUNK):
            chunk = todo[i:i + CHUNK]
            try:
                data = yf.download([yahoo(s) for s in chunk], period="max", interval=interval, auto_adjust=False,
                                   group_by="ticker", threads=True, progress=False, actions=False)
            except Exception as exc:
                print(f"batch failed: {exc!r}", file=sys.stderr)
                time.sleep(30)
                continue
            got = split(data, [yahoo(s) for s in chunk])
            for s in chunk:
                df = got.get(yahoo(s))
                if df is None:
                    continue
                df = df.rename(columns=lambda c: str(c).lower().replace(" ", ""))
                if "close" not in df or "adjclose" not in df:
                    continue
                df = df[["open", "high", "low", "close", "adjclose", "volume"]].dropna(subset=["close"])
                idx = pd.to_datetime(df.index)
                df.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
                df = df[~df.index.duplicated(keep="last")].sort_index()
                df = df[df.index <= pd.Timestamp(LAST[interval])]
                if len(df) >= 24:
                    frames[s] = df
            time.sleep(2)
        todo = [s for s in syms if s not in frames]
        print(f"{interval} pass {attempt + 1}: {len(frames)} saved, {len(todo)} missing", flush=True)
        if not todo:
            break
        time.sleep(60)
    if todo:
        print(f"{interval} missing:", " ".join(todo))
    return frames


def save(frames, path):
    syms = sorted(frames)
    start = np.cumsum([0] + [len(frames[s]) for s in syms])
    cat = pd.concat([frames[s] for s in syms])
    out = {"symbols": np.array(syms), "start": start.astype(np.int64),
           "t": ((cat.index - pd.Timestamp("1970-01-01")).days).to_numpy(np.int32)}
    for k in ("open", "high", "low", "close", "adjclose", "volume"):
        out[k] = cat[k].to_numpy(np.float32)
    np.savez_compressed(path, **out)
    print(path, len(syms), "symbols", len(cat), "rows", os.path.getsize(path) // 1024, "KB")


def main(out):
    os.makedirs(out, exist_ok=True)
    syms = [r["symbol"] for r in csv.DictReader(open(UNIVERSE))]
    ok = True
    for interval, name in (("1wk", "weekly"), ("1mo", "monthly")):
        frames = fetch(syms, interval)
        save(frames, os.path.join(out, f"{name}.npz"))
        ok &= len(frames) >= 0.9 * len(syms)
    if not ok:
        sys.exit("fewer than 90% of symbols downloaded")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data", "yahoo_long"))
