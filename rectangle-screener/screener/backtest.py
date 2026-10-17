"""Backtest: how did the screener's breakouts do once a daily close reached CONFIRM_PCT past the line?

    python3 -m screener.backtest --hood-dir DIR [--hood-dir DIR ...] --out OUT_DIR

Run from the ``rectangle-screener`` directory with Robinhood daily dumps (``daily_*.json``).

1. Replay.  The screener is re-run for every stock on every session, point in time: each
   evening sees only the bars up to that day, through the same window (REPLAY_BARS bars),
   liquidity rule and previous-evening hint as the nightly build.  Every breakout or
   breakdown it would have listed is kept (``replay.pkl`` in OUT_DIR, reused on later runs).

2. Signals.  A breakout is confirmed by the first close at least ``pct``% past the broken
   line (above resistance / below support, as % of the line) while the screener still lists
   it: within ``max_breakout_age`` sessions and with no close back inside the box.  pct = 0
   is "every listed breakout".  One position per stock and direction at a time.

3. Trades.  Entry at the next session's open (the screener runs after the close), two ways:
   "target" trade
     target   the measured move, the box height projected from the broken line: exit there
              (or at the open, if it gaps through; a box shorter than the confirmation
              distance can have its target behind the entry already: exit at once, flagged)
     failure  a close back inside the box: exit at the next open
     timeout  the close MAX_HOLD sessions after entry
     A session that reaches the target intraday and closes back inside counts as the target.
   "run" trade: the same without a target (exit only on a failure or the timeout).
   Plus plain holds of HORIZONS sessions.  Bearish breakdowns are traded short.  Returns
   are per trade, before costs.

4. Benchmark.  Each trade is compared with the equal-weighted average of every stock that
   passed the liquidity rule on the signal day, over the same entry and exit, so the
   market's own drift is taken out ("excess").

Caveat: the universe is today's list (market cap >= $2B now), so stocks that were delisted
or shrank since 2016 are missing.  That flatters raw long returns; the excess figures are
measured against the same survivor universe, which cancels most of it.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pickle
import sys
from collections import defaultdict
from multiprocessing import Pool

import numpy as np
import pandas as pd

from . import rectangle
from .build import LIQUIDITY_BARS, MIN_BARS, MIN_DOLLAR_VOLUME, MIN_PRICE, is_liquid, volume_profile
from .sources import load_hood_dumps

REPLAY_BARS = 300          # bars the nightly build sees (Yahoo's 430 calendar days)
MAX_HOLD = 60              # sessions
HORIZONS = (5, 10, 20, 60)
THRESHOLDS = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
CONFIRM_PCT = 3.0
KEEP = ("status", "top", "bottom", "start", "end", "bars", "height_pct", "top_touches", "bottom_touches",
        "switches", "breakout_date", "days_since_breakout", "breakout_volume_ratio", "failed_breakout", "quality")


# ---------------------------------------------------------------------------------- replay
def replay_symbol(item):
    """Every breakout row the nightly build would have listed for one stock: {date: row}."""
    sym, df = item
    out = {}
    prev = None
    for i in range(MIN_BARS - 1, len(df)):
        w = df.iloc[max(0, i + 1 - REPLAY_BARS): i + 1]
        if len(w) < MIN_BARS or not is_liquid(w):
            prev = None               # not in that evening's results: no hint the next day
            continue
        try:
            r = rectangle.detect(w, None, hint=prev)
        except Exception:             # the build skips a series that fails, so do we
            r = None
        prev = {k: r[k] for k in ("start", "top", "bottom")} if r else None
        if r and r["status"] != "inside":
            out[df.index[i]] = {k: r[k] for k in KEEP}
    return sym, out


def replay(bars, path, procs=4):
    """Replay every stock (cached in ``path``)."""
    if os.path.exists(path):
        with open(path, "rb") as fh:
            done = pickle.load(fh)
    else:
        done = {}
    todo = [(s, df) for s, df in sorted(bars.items()) if s not in done]
    if todo:
        with Pool(procs) as pool:
            for k, (sym, rows) in enumerate(pool.imap_unordered(replay_symbol, todo, chunksize=4), 1):
                done[sym] = rows
                if k % 100 == 0 or k == len(todo):
                    print(f"replayed {k}/{len(todo)}", file=sys.stderr, flush=True)
                    with open(path + ".tmp", "wb") as fh:
                        pickle.dump(done, fh)
                    os.replace(path + ".tmp", path)
    return done


# ---------------------------------------------------------------------------------- trades
def simulate(o, h, l, c, e, d, line, target, max_hold=MAX_HOLD):
    """Trade entered at the open after bar e.  d = 1 (long) or -1 (short); target None for
    no target.

    Returns (exit_index, exit_price, outcome, exit_at) with exit_at "open" / "close" /
    "target", or None when the data ends before the trade is decided."""
    n = len(c)
    if e + 1 >= n:
        return None
    entry = o[e + 1]
    for j in range(e + 1, min(e + max_hold, n - 1) + 1):
        ref = entry if j == e + 1 else o[j]
        if target is not None and ((d > 0 and h[j] >= target) or (d < 0 and l[j] <= target)):
            return j, (max(ref, target) if d > 0 else min(ref, target)), "target", "target"
        if (d > 0 and c[j] < line) or (d < 0 and c[j] > line):
            if j + 1 >= n:
                return None
            return j + 1, o[j + 1], "failed", "open"
        if j == e + max_hold:
            return j, c[j], "timeout", "close"
    return None


def signals(rows, bars, pct):
    """Confirmed breakouts: (sym, signal_date, row) for the first listed close >= pct past the
    line, one position per stock and direction at a time (exits filled in by trades())."""
    out = []
    for sym, by_date in rows.items():
        df = bars[sym]
        close = df["close"]
        for when in sorted(by_date):
            r = by_date[when]
            up = r["status"] == "breakout_up"
            past = (close[when] / r["top"] - 1) * 100 if up else (1 - close[when] / r["bottom"]) * 100
            if round(past, 2) >= pct:
                out.append((sym, when, r, past))
    return out


def trades(rows, bars, pct, bench, max_hold=MAX_HOLD):
    """Simulated trades for one confirmation threshold."""
    taken = []
    busy = defaultdict(lambda: pd.Timestamp.min)    # (sym, direction) -> last exit date
    seen = set()
    for sym, when, r, past in sorted(signals(rows, bars, pct), key=lambda x: (x[1], x[0])):
        key = (sym, r["status"], r["breakout_date"])
        if key in seen:
            continue                  # this breakout already gave its signal
        df = bars[sym]
        d = 1 if r["status"] == "breakout_up" else -1
        if when <= busy[(sym, d)]:
            continue
        seen.add(key)
        o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        e = df.index.get_loc(when)
        height = r["top"] - r["bottom"]
        line = r["top"] if d > 0 else r["bottom"]
        target = line + d * height
        res = simulate(o, h, l, c, e, d, line, target, max_hold)
        run = simulate(o, h, l, c, e, d, line, None, max_hold)
        if res is None or run is None:
            continue                  # not decided before the data ends
        j, px, outcome, exit_at = res
        entry = o[e + 1]
        if not (entry > 0 and math.isfinite(entry) and math.isfinite(px) and math.isfinite(run[1])):
            continue
        busy[(sym, d)] = df.index[max(j, run[0])]
        ret = d * (px / entry - 1) * 100
        b = bench.span(when, df.index[e + 1], df.index[j], exit_at)
        rb = bench.span(when, df.index[e + 1], df.index[run[0]], run[3])
        t = {
            "symbol": sym, "direction": "up" if d > 0 else "down", "signal_date": when.strftime("%Y-%m-%d"),
            "breakout_date": r["breakout_date"], "days_to_signal": int(r["days_since_breakout"]),
            "past_pct": round(past, 2), "entry_date": df.index[e + 1].strftime("%Y-%m-%d"), "entry": entry,
            "line": line, "target": target, "height_pct": r["height_pct"], "quality": r["quality"],
            "bars": r["bars"], "breakout_volume_ratio": r["breakout_volume_ratio"],
            "failed_before": bool(r["failed_breakout"]), "exit_date": df.index[j].strftime("%Y-%m-%d"),
            "exit": px, "outcome": outcome, "held": int(j - e), "ret": ret,
            "bench": None if b is None else d * b, "excess": None if b is None else ret - d * b,
            "target_at_entry": bool(d * (entry - target) >= 0),
            "run_outcome": run[2], "run_held": int(run[0] - e), "run_ret": d * (run[1] / entry - 1) * 100,
        }
        t["run_excess"] = None if rb is None else t["run_ret"] - d * rb
        box = df.loc[r["start"]:r["end"]]
        vp = volume_profile(box["volume"].to_numpy(), keep=((box["close"] <= r["top"]) & (box["close"] >= r["bottom"])).to_numpy())
        t["volume_declining"] = bool(vp and vp["declining"])
        for hz in HORIZONS:
            k = e + hz
            if k < len(c) and math.isfinite(c[k]):
                t[f"r{hz}"] = d * (c[k] / entry - 1) * 100
                bh = bench.span(when, df.index[e + 1], df.index[k], "close")
                t[f"x{hz}"] = None if bh is None else t[f"r{hz}"] - d * bh
        t["path"] = [d * (c[k] / entry - 1) * 100 if k < len(c) and math.isfinite(c[k]) else None
                     for k in range(e + 1, e + 1 + max_hold)]
        bp = bench.path(when, df.index[e + 1], df.index[e + 1: e + 1 + max_hold])
        t["xpath"] = [None if p is None or q is None else p - d * q for p, q in zip(t["path"], bp)]
        taken.append(t)
    return taken


class Benchmark:
    """Equal-weighted average return of the stocks that were liquid on the signal day."""

    def __init__(self, bars):
        self.O = pd.DataFrame({s: df["open"] for s, df in bars.items()}).sort_index()
        self.C = pd.DataFrame({s: df["close"] for s, df in bars.items()}).sort_index()
        V = pd.DataFrame({s: df["volume"] for s, df in bars.items()}).reindex(self.C.index)
        dv = (self.C * V).rolling(LIQUIDITY_BARS, min_periods=LIQUIDITY_BARS).median()
        self.liquid = (dv >= MIN_DOLLAR_VOLUME) & (self.C >= MIN_PRICE)

    def span(self, signal, entry, exit_, exit_at):
        """Mean return (in %) from the entry open to the exit (open / close; an intraday
        target exit is measured at that session's close)."""
        try:
            m = self.liquid.loc[signal].to_numpy()
            a = self.O.loc[entry].to_numpy()
            z = (self.O if exit_at == "open" else self.C).loc[exit_].to_numpy()
        except KeyError:
            return None
        ok = m & np.isfinite(a) & np.isfinite(z) & (a > 0)
        return float(np.mean(z[ok] / a[ok] - 1) * 100) if ok.sum() >= 50 else None

    def path(self, signal, entry, dates):
        """span() from the entry open to each of the given closes."""
        try:
            m = self.liquid.loc[signal].to_numpy() & np.isfinite(self.O.loc[entry].to_numpy())
            a = self.O.loc[entry].to_numpy()
            z = self.C.loc[dates].to_numpy()
        except KeyError:
            return [None] * len(dates)
        out = []
        for row in z:
            ok = m & np.isfinite(row) & (a > 0)
            out.append(float(np.mean(row[ok] / a[ok] - 1) * 100) if ok.sum() >= 50 else None)
        return out


# ---------------------------------------------------------------------------------- stats
def _boot_ci(values, months, n=2000, seed=0):
    """95% interval of the mean, resampling whole months (signals cluster in time)."""
    v = np.asarray(values, float)
    if len(v) < 10:
        return None
    by = defaultdict(list)
    for x, m in zip(v, months):
        by[m].append(x)
    groups = [np.asarray(g) for g in by.values()]
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        allv = np.concatenate([groups[i] for i in pick])
        means.append(allv.mean())
    return [round(float(np.percentile(means, 2.5)), 2), round(float(np.percentile(means, 97.5)), 2)]


def summarize(ts):
    """Headline numbers for a list of trades."""
    if not ts:
        return {"n": 0}
    ret = np.array([t["ret"] for t in ts])
    exc = [t["excess"] for t in ts if t["excess"] is not None]
    months = [t["signal_date"][:7] for t in ts]
    out = {
        "n": len(ts),
        "target": round(sum(t["outcome"] == "target" for t in ts) / len(ts) * 100, 1),
        "failed": round(sum(t["outcome"] == "failed" for t in ts) / len(ts) * 100, 1),
        "timeout": round(sum(t["outcome"] == "timeout" for t in ts) / len(ts) * 100, 1),
        "win": round(float((ret > 0).mean() * 100), 1),
        "avg": round(float(ret.mean()), 2),
        "avg_ci": _boot_ci(ret, months),
        "median": round(float(np.median(ret)), 2),
        "avg_win": round(float(ret[ret > 0].mean()), 2) if (ret > 0).any() else None,
        "avg_loss": round(float(ret[ret <= 0].mean()), 2) if (ret <= 0).any() else None,
        "profit_factor": round(float(ret[ret > 0].sum() / -ret[ret < 0].sum()), 2) if (ret < 0).any() else None,
        "held": round(float(np.mean([t["held"] for t in ts])), 1),
        "excess": round(float(np.mean(exc)), 2) if exc else None,
        "excess_ci": _boot_ci(exc, [t["signal_date"][:7] for t in ts if t["excess"] is not None]) if exc else None,
        "beat_bench": round(float(np.mean(np.array(exc) > 0) * 100), 1) if exc else None,
        "target_at_entry": round(sum(t["target_at_entry"] for t in ts) / len(ts) * 100, 1),
    }
    rr = np.array([t["run_ret"] for t in ts])
    rx = [t["run_excess"] for t in ts if t["run_excess"] is not None]
    out["run"] = {
        "failed": round(sum(t["run_outcome"] == "failed" for t in ts) / len(ts) * 100, 1),
        "win": round(float((rr > 0).mean() * 100), 1),
        "avg": round(float(rr.mean()), 2), "avg_ci": _boot_ci(rr, months), "median": round(float(np.median(rr)), 2),
        "avg_win": round(float(rr[rr > 0].mean()), 2) if (rr > 0).any() else None,
        "avg_loss": round(float(rr[rr <= 0].mean()), 2) if (rr <= 0).any() else None,
        "profit_factor": round(float(rr[rr > 0].sum() / -rr[rr < 0].sum()), 2) if (rr < 0).any() else None,
        "held": round(float(np.mean([t["run_held"] for t in ts])), 1),
        "excess": round(float(np.mean(rx)), 2) if rx else None,
        "excess_ci": _boot_ci(rx, [t["signal_date"][:7] for t in ts if t["run_excess"] is not None]) if rx else None,
    }
    for hz in HORIZONS:
        r = [t[f"r{hz}"] for t in ts if t.get(f"r{hz}") is not None]
        x = [t[f"x{hz}"] for t in ts if t.get(f"x{hz}") is not None]
        out[f"h{hz}"] = {"n": len(r), "avg": round(float(np.mean(r)), 2) if r else None,
                         "win": round(float(np.mean(np.array(r) > 0) * 100), 1) if r else None,
                         "excess": round(float(np.mean(x)), 2) if x else None}
    return out


def mean_path(ts, key="path"):
    """Average return path (in %) from the entry open to each of the next MAX_HOLD closes."""
    cols = list(zip(*[t[key] for t in ts])) if ts else []
    return [round(float(np.mean([v for v in col if v is not None])), 3) if any(v is not None for v in col) else None
            for col in cols]


SPLITS = {
    "year": lambda t: t["signal_date"][:4],
    "quality": lambda t: "60+" if t["quality"] >= 60 else "55-60" if t["quality"] >= 55 else "under 55",
    "volume_declining": lambda t: "declining" if t["volume_declining"] else "not declining",
    "days_to_signal": lambda t: "breakout day" if t["days_to_signal"] == 0 else "1-3 days later"
                                if t["days_to_signal"] <= 3 else "4-10 days later",
    "breakout_volume": lambda t: "n/a" if t["breakout_volume_ratio"] is None else "under 1x"
                                 if t["breakout_volume_ratio"] < 1 else "1-2x" if t["breakout_volume_ratio"] < 2 else "2x+",
    "height": lambda t: "under 8%" if t["height_pct"] < 8 else "8-15%" if t["height_pct"] < 15 else "15%+",
    "second_try": lambda t: "after a failed attempt" if t["failed_before"] else "first attempt",
}


def splits(ts):
    """summarize() by trade attributes, separately for breakouts and breakdowns."""
    out = {}
    for name, f in SPLITS.items():
        out[name] = {}
        for dr in ("up", "down"):
            groups = defaultdict(list)
            for t in ts:
                if t["direction"] == dr:
                    groups[f(t)].append(t)
            out[name][dr] = {g: summarize(v) for g, v in sorted(groups.items())}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hood-dir", action="append", required=True, help="directory of daily_*.json dumps (repeatable)")
    ap.add_argument("--out", required=True, help="output directory (replay cache, trades, summary)")
    ap.add_argument("--procs", type=int, default=4)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    parts = defaultdict(list)
    for d in args.hood_dir:
        for sym, df in load_hood_dumps(d).items():
            parts[sym].append(df)
    bars = {}
    for sym, dfs in parts.items():
        df = pd.concat(dfs)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        bars[sym] = df.replace([math.inf, -math.inf], math.nan).dropna(subset=["open", "high", "low", "close"])
    print(f"{len(bars)} stocks, {min(df.index[0] for df in bars.values()).date()} .. "
          f"{max(df.index[-1] for df in bars.values()).date()}", file=sys.stderr)

    rows = replay(bars, os.path.join(args.out, "replay.pkl"), args.procs)
    bench = Benchmark(bars)
    result = {"params": {"replay_bars": REPLAY_BARS, "max_hold": MAX_HOLD, "confirm_pct": CONFIRM_PCT,
                         "detector": rectangle.DEFAULT_PARAMS},
              "period": [str(min(df.index[0] for df in bars.values()).date()),
                         str(max(df.index[-1] for df in bars.values()).date())],
              "stocks": len(bars), "thresholds": {}}
    for pct in THRESHOLDS:
        ts = trades(rows, bars, pct, bench)
        res = {"all": summarize(ts),
               "up": summarize([t for t in ts if t["direction"] == "up"]),
               "down": summarize([t for t in ts if t["direction"] == "down"]),
               "path": {dr: {k: mean_path([t for t in ts if t["direction"] == dr], k) for k in ("path", "xpath")}
                        for dr in ("up", "down")}}
        if pct == CONFIRM_PCT:
            res["splits"] = splits(ts)
        result["thresholds"][str(pct)] = res
        pd.DataFrame([{k: v for k, v in t.items() if k not in ("path", "xpath")} for t in ts]).to_csv(
            os.path.join(args.out, f"trades_{pct:g}.csv"), index=False)
        with open(os.path.join(args.out, f"trades_{pct:g}.pkl"), "wb") as fh:
            pickle.dump(ts, fh)
        a = res["all"]
        if a["n"]:
            print(f"pct {pct:g}: {a['n']} trades | target trade: target {a['target']}% failed {a['failed']}% "
                  f"win {a['win']}% avg {a['avg']}% excess {a['excess']}% | run: failed {a['run']['failed']}% "
                  f"avg {a['run']['avg']}% excess {a['run']['excess']}% | 20d avg {a['h20']['avg']}% "
                  f"excess {a['h20']['excess']}%", file=sys.stderr)
    with open(os.path.join(args.out, "summary.json"), "w") as fh:
        json.dump(result, fh, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
