"""Rectangle (horizontal trading range) detector for daily bars.

A rectangle is a sideways range bounded by two flat, parallel lines that price has
tested repeatedly, crossing from one line to the other.  ``detect`` returns the best
rectangle that is still current as of the last bar -- price is inside it, or broke out
of it within ``max_breakout_age`` bars -- or ``None``.  Every threshold lives in
``DEFAULT_PARAMS``; the defaults follow the screener spec (at least 2 touches per line,
3 side switches, 15 bars, height >= 2.5 ATR and 3-30 % of price, breakouts confirmed by
a close 0.3 ATR beyond the line and reported for 10 bars).

How it works
------------
1. Anchors.  A rectangle ends either at the last bar (status ``inside``) or on the bar
   before a breakout close (``breakout_up`` / ``breakout_down``).  Breakout candidates
   are the last ``max_breakout_age + 1`` bars whose close beats both the previous close
   and the third-most-extreme close of the ``min_bars`` closes before it.

2. Window scan.  For an anchor ``e`` every confirmed swing pivot ``s`` (``pivot_strength``
   bars on each side) up to ``max_bars`` back is a candidate first touch.  The swing
   highs and lows of ``[s, e]`` are kept in sorted lists while ``s`` moves back.  The top
   line is the median of the highest cluster of swing highs lying within one touch band
   of each other; up to ``max_skip_peaks`` isolated higher spikes may be skipped so a
   wick never defines the line (when skipping gives a competing cluster both are tried).
   The bottom line mirrors this.  Touch band = max(band_atr * ATR, band_frac * height),
   ATR = mean true range over the window.

3. Validation (``_evaluate_box``), in order:
   * size: ``min_height_pct`` <= height / bottom <= ``max_height_pct`` and
     height >= ``min_height_atr`` * ATR;
   * start: bar ``s`` touches its line and price came from at least ``retreat_frac`` of
     the height away within ``approach_lookback`` bars, so a pause inside the trend leg
     into the range is not a first touch;
   * breakout anchors: the close after the window is beyond the line by
     ``breakout_buffer_atr`` * ATR, clears every close inside the box, and no later close
     is back inside;
   * containment: an excursion starts with a close beyond line +/- buffer and lasts until
     a close is back inside the box.  The most recent excursion may be a failed breakout
     (began within ``failed_lookback`` bars, at most ``failed_max_closes`` closes beyond);
     it is reported as ``failed_breakout``.  Older excursions are false breakouts: at
     most ``max_false_closes`` closes in total, ``max_false_run`` per excursion;
   * touches: a bar touches the top when its high enters the band below the line;
     consecutive touches form one episode unless price retreated ``retreat_frac`` of
     the height in between.  Episodes whose extreme lies beyond the band are pokes (at
     most ``max_pokes_per_side``, not counting the failed breakout).  Each side needs
     ``min_touches_per_side`` confirmed in-band touches: an episode holding a false
     breakout close tests the line but does not define it, and on the breakout side the
     run straight into the breakout is not a test unless price turned (a swing pivot)
     inside it;
   * alternation: at least ``min_switches`` side switches (and one per
     ``switch_density_bars`` bars); the box is still being tested (``max_idle_*``) and
     its late part still spans ``min_late_range_frac`` of the height;
   * flatness: a least-squares line through each side's touches (pokes clipped to the
     line +/- ``poke_clip`` bands, the failed breakout left out) moves at most
     ``max_drift_frac`` of the height over the span of that side's touches (at least
     ``drift_min_span_frac`` of the box, so two close touches cannot fake a slope); the
     two lines may converge / diverge by at most ``max_converge_frac`` and tilt together
     by at most ``max_parallel_drift_frac`` of the height (triangles, broadening
     formations, channel segments);
   * no coiling: failed swings (a swing that turned ``retreat_frac`` away from a line
     without reaching the other one) stay a minority on each side, and the latest two
     on a side may not move progressively away from their line;
   * both lines are tested across the box (``min_side_span_frac``) from early on
     (``max_first_touch_frac``), and the closes fill the box (``min_upper_frac`` ..
     ``max_upper_frac`` of them in the upper half, regression drift of the closes at
     most ``max_close_drift`` of the height);
   * weak boxes -- only ``weak_switches`` side switches, or taller than
     ``tall_height_pct`` with fewer than ``tall_min_switches`` switches, or shorter than
     ``short_bars`` bars with fewer than ``short_min_switches`` -- must be clean in every
     other respect (the ``weak_*`` limits).  On real charts most such boxes are W / M
     shaped swings rather than ranges, so they need tight, flat lines, brisk swings and
     a decent quality score.

4. Selection.  Each anchor keeps the window with the best selection score (switches,
   touches, quality, fewer violations, slightly longer preferred).  The winner's start
   is then extended back over bars that already ranged inside the same box, when the
   longer box still validates.  The best anchor wins.

Quality (0-100) scores how textbook the box is; it is the sum of
    20 * touches   (top + bottom touches - 4) / 6           (10+ touches = full)
    15 * switches  (switches - 3) / 5                        (8+ switches = full)
    10 * tightness 1 - mean |in-band touch - line| / band
    10 * flatness  1 - line drift / max_drift_frac
    10 * contain   1 - (false-breakout closes + pokes / 2) / 3
    10 * fill      1 - |share of closes in the upper half - 0.5| / 0.25
     5 * level     1 - close regression drift / 0.6 (no trend inside the box)
     5 * height    (height / ATR - 2.5) / 4.5                (7+ ATR tall = full)
    10 * duration  1 for 20..130 bars, linear ramps to 0.5 at 15 and at 200 bars
     5 * balance   min(top, bottom touches) / max(top, bottom touches)
with every component clipped to [0, 1].
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right, insort

import numpy as np
import pandas as pd

DEFAULT_PARAMS: dict = {
    # --- duration ------------------------------------------------------------
    "min_bars": 15,                  # minimum rectangle length (start..end inclusive)
    "max_bars": 200,                 # maximum rectangle length
    # --- size ----------------------------------------------------------------
    "atr_period": 14,                # ATR period for the reported atr_pct
    "min_height_atr": 2.5,           # height >= this * mean true range over the box
    "min_height_pct": 3.0,           # 3% <= height / bottom * 100 ...
    "max_height_pct": 30.0,          # ... <= 30%
    # --- touches and alternation -----------------------------------------------
    "min_touches_per_side": 2,       # confirmed in-band touches each line needs
    "min_switches": 3,               # side switches in the time-ordered touch sequence
    "switch_density_bars": 40,       # long boxes need one switch per this many bars
    "band_atr": 0.5,                 # touch band half-width = max(band_atr * ATR,
    "band_frac": 0.10,               #   band_frac * height)
    "retreat_frac": 0.45,            # same-side touches are distinct only if price pulled
                                     #   this fraction of the height away in between
    "max_pokes_per_side": 1,         # touches whose extreme lies beyond the band
    "poke_clip": 2.0,                # pokes enter the flatness fit clipped at line +/- this * band
    "pivot_strength": 2,             # bars on each side of a swing pivot
    "max_skip_peaks": 2,             # isolated spikes that may be skipped when placing a line
    "approach_lookback": 15,         # the first touch must be approached from retreat_frac * height
                                     #   away within this many bars (not a pause in the trend leg)
    # --- flatness ----------------------------------------------------------------
    "max_drift_frac": 0.25,          # a side's touch line moves <= this * height over the span
    "drift_min_span_frac": 0.5,      #   of its touches, but at least this fraction of the box
    "max_converge_frac": 0.35,       # lines converge / diverge <= this * height (triangles)
    "max_parallel_drift_frac": 0.15, # lines tilt together <= this * height (channel segments)
    "min_side_span_frac": 0.30,      # each line's in-band touches span >= this fraction of the box
    "max_first_touch_frac": 0.45,    # ... and its first one comes within this fraction of the box
    "max_first_touch_bars": 10,      #   (or within this many bars)
    # --- containment, breakouts, failed breakouts -------------------------------------
    "breakout_buffer_atr": 0.3,      # breakout = close beyond line +/- this * ATR
    "max_breakout_age": 10,          # older breakouts are out of scope (None)
    "max_false_closes": 2,           # closes beyond the buffer tolerated in the box history ...
    "max_false_run": 2,              # ... at most this many per excursion
    "failed_lookback": 20,           # the latest excursion, if it began within this many bars,
    "failed_max_closes": 10,         #   may be a failed breakout of up to this many closes
    # --- still active --------------------------------------------------------------
    "max_idle_frac": 0.4,            # bars since the last touch <= max(max_idle_bars,
    "max_idle_bars": 15,             #   max_idle_frac * bars)
    "min_late_range_frac": 0.45,     # the late part of the box (its last late_window_frac, at
    "late_window_frac": 1 / 3,       #   least late_window_min_bars bars) still spans this * height
    "late_window_min_bars": 10,
    # --- how the closes fill the box -------------------------------------------------
    "min_upper_frac": 0.25,          # share of closes in the upper half of the box must lie
    "max_upper_frac": 0.75,          #   in [min, max] (not one side plus a spike)
    "max_close_drift": 0.6,          # regression drift of the closes <= this * height
    # --- weak boxes ----------------------------------------------------------------
    "weak_switches": 3,              # boxes with only this many switches are weak, as are
    "tall_height_pct": 20.0,         #   boxes taller than this (%) with fewer than
    "tall_min_switches": 5,          #   tall_min_switches switches, and boxes shorter than
    "short_bars": 20,                #   short_bars bars with fewer than short_min_switches
    "short_min_switches": 5,
    "weak_min_bars": 18,             # a weak box needs >= this many bars,
    "weak_min_height_atr": 3.0,      #   height >= this * ATR,
    "weak_max_height_pct": 30.0,     #   height <= this %,
    "weak_max_bars_per_switch": 19,  #   a switch at least every this many bars,
    "weak_max_drift_frac": 0.125,    #   touch lines drifting <= this * height,
    "weak_max_close_drift": 0.5,     #   close drift <= this * height,
    "weak_max_dev": 0.5,             #   mean |touch - line| <= this * band,
    "weak_min_quality": 48.0,        #   and quality >= this
    # --- output / selection ------------------------------------------------------------
    "volume_lookback": 50,           # breakout volume ratio: mean volume of this many bars before
    "length_pref": 0.04,             # selection bonus per bar (longer box when comparable)
    "scan_stop_mult": 1.5,           # stop scanning back once the robust close range exceeds
                                     #   this * max_height_pct
}


# ----------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------
def _true_range(h, l, c):
    tr = h - l
    if len(c) > 1:
        pc = c[:-1]
        tr[1:] = np.maximum(tr[1:], np.maximum(np.abs(h[1:] - pc), np.abs(l[1:] - pc)))
    return tr


def _wilder_atr_last(tr, n):
    """Wilder ATR(n) at the last bar."""
    if len(tr) == 0:
        return float("nan")
    if len(tr) <= n:
        return float(tr.mean())
    alpha = 1.0 / n
    rest = tr[n:]
    m = len(rest)
    weights = (1 - alpha) ** np.arange(m - 1, -1, -1)
    return float(tr[:n].mean() * (1 - alpha) ** m + alpha * np.dot(weights, rest))


def _swing_pivots(x, k, high):
    """x[i] is the extreme of x[i-k .. i+k] (window truncated at the series ends)."""
    pad = np.full(k, -np.inf if high else np.inf)
    win = np.lib.stride_tricks.sliding_window_view(np.concatenate([pad, x, pad]), 2 * k + 1)
    return x >= win.max(axis=1) if high else x <= win.min(axis=1)


def _rolling_prev(x, w, fn, fill):
    """out[i] = fn(x[i-w:i]) over the bars available before i (fill for i == 0)."""
    padded = np.concatenate([np.full(w, fill), x])
    return fn(np.lib.stride_tricks.sliding_window_view(padded, w)[:len(x)], axis=1)


def _median(a, i0, i1):
    """Median of the sorted slice a[i0:i1]."""
    return 0.5 * (a[(i0 + i1 - 1) // 2] + a[(i0 + i1) // 2])


def _line_levels(a, band, top_side, max_skip):
    """Candidate levels of one line from the ascending list ``a`` of swing extremes.

    For the top line the highest swing high is the reference; up to ``max_skip`` higher
    isolated spikes may be skipped.  The level is the median of the swing highs within
    two bands below the reference, re-centred on the members within one band of it.
    Returns up to two levels, the best supported first."""
    m = len(a)
    if m < 2:
        return []
    out = []
    for j in range(min(max_skip + 1, m - 1)):
        if top_side:
            hi = m - j                       # a[hi:] are skipped spikes
            ref = a[hi - 1]
            if j > 0 and a[hi] - ref <= band:
                continue                     # the skipped peak belongs to this cluster
            i0 = bisect_left(a, ref - 2.0 * band, 0, hi)
            if hi - i0 < 2:
                continue
            lvl = _median(a, i0, hi)
            k0 = bisect_left(a, lvl - band, 0, hi)
            k1 = bisect_right(a, lvl + band, 0, hi)
        else:
            lo = j                           # a[:lo] are skipped spikes
            ref = a[lo]
            if j > 0 and ref - a[lo - 1] <= band:
                continue
            i1 = bisect_right(a, ref + 2.0 * band, lo, m)
            if i1 - lo < 2:
                continue
            lvl = _median(a, lo, i1)
            k0 = bisect_left(a, lvl - band, lo, m)
            k1 = bisect_right(a, lvl + band, lo, m)
        count = k1 - k0
        if count >= 2:
            lvl = _median(a, k0, k1)
        else:
            count = 1
        out.append((lvl, count, j))
    out.sort(key=lambda t: (-t[1], t[2]))
    return [lvl for lvl, _, _ in out[:2]]


def _touch_episodes(ext, in_zone, away, top_side):
    """Touch episodes of one line (indices relative to the window).

    ``in_zone`` marks bars touching the line, ``away`` bars far enough from it that the
    next touch is a new episode.  Returns (extreme idx, extreme price, first idx,
    last idx) arrays, one entry per episode."""
    it = np.flatnonzero(in_zone)
    if len(it) <= 1:
        return it, ext[it], it, it
    away_cum = np.cumsum(away)
    prev = it[:-1]
    before = np.where(prev > 0, away_cum[np.maximum(prev - 1, 0)], 0)
    new = np.empty(len(it), dtype=bool)
    new[0] = True
    new[1:] = (away_cum[it[1:] - 1] - before) > 0
    starts = np.flatnonzero(new)
    vals = ext[it]
    if len(starts) == len(it):
        return it, vals, it, it
    episode = np.cumsum(new) - 1
    order = np.lexsort((-vals if top_side else vals, episode))
    first = order[starts]
    ends = np.append(starts[1:], len(it)) - 1
    return it[first], vals[first], it[starts], it[ends]


def _excursions(c, T, B, buf):
    """Close excursions beyond the box as [direction (+1 up / -1 down), first, last,
    closes beyond the buffer].  An excursion starts with a close beyond line +/- buf
    and lasts until a close is back inside the box (below the top / above the bottom)."""
    out = []
    state = 0
    up, dn = T + buf, B - buf
    for i, x in enumerate(c):
        if state == 1 and x < T or state == -1 and x > B:
            state = 0
        if state == 0:
            if x > up:
                state = 1
                out.append([1, i, i, 0])
            elif x < dn:
                state = -1
                out.append([-1, i, i, 0])
        if state:
            out[-1][2] = i
            if x > up or x < dn:
                out[-1][3] += 1
    return out


def _slope(x, y):
    """Least-squares slope of y on x (0 for fewer than two points)."""
    n = len(x)
    if n < 2:
        return 0.0
    xm = sum(x) / n
    ym = sum(y) / n
    den = sum((xi - xm) ** 2 for xi in x)
    num = sum((xi - xm) * (yi - ym) for xi, yi in zip(x, y))
    return num / den if den > 0 else 0.0


def _quality(m):
    """0-100 textbook score (see the module docstring)."""
    def clip(x):
        return min(1.0, max(0.0, x))
    nt, nb = m["top_touches"], m["bottom_touches"]
    bars = m["bars"]
    if bars < 20:
        duration = 0.5 + 0.5 * (bars - 15) / 5.0
    elif bars <= 130:
        duration = 1.0
    else:
        duration = 1.0 - 0.5 * (bars - 130) / 70.0
    q = (20.0 * clip((nt + nb - 4) / 6.0)
         + 15.0 * clip((m["switches"] - 3) / 5.0)
         + 10.0 * clip(1.0 - m["dev"])
         + 10.0 * clip(1.0 - m["drift"])
         + 10.0 * clip(1.0 - (m["viol"] + 0.5 * m["pokes"]) / 3.0)
         + 10.0 * clip(1.0 - abs(m["upfrac"] - 0.5) / 0.25)
         + 5.0 * clip(1.0 - m["cdrift"] / 0.6)
         + 5.0 * clip((m["h_atr"] - 2.5) / 4.5)
         + 10.0 * clip(duration)
         + 5.0 * min(nt, nb) / max(nt, nb))
    return round(min(100.0, max(0.0, q)), 1)


# ----------------------------------------------------------------------------------
# box evaluation
# ----------------------------------------------------------------------------------
class _Series:
    """Arrays shared by every window evaluated for one series."""

    def __init__(self, H, L, C, P):
        n = len(C)
        k = P["pivot_strength"]
        self.P = P
        self.H, self.L, self.C = H, L, C
        self.tr_cum = np.concatenate(([0.0], np.cumsum(_true_range(H, L, C))))
        self.ph = _swing_pivots(H, k, True)
        self.pl = _swing_pivots(L, k, False)
        # lowest low / highest high of the approach_lookback bars before each bar (the
        # first bar has no history and may always start a box)
        self.pre_lo = _rolling_prev(L, P["approach_lookback"], np.min, np.inf)
        self.pre_hi = _rolling_prev(H, P["approach_lookback"], np.max, -np.inf)
        self.pre_lo[0], self.pre_hi[0] = -np.inf, np.inf
        # a failed breakout may begin no earlier than this bar
        self.recent_start = n - 1 - P["failed_lookback"]
        # extreme closes from each bar to the end (breakout follow-through)
        self.suffix_min = np.concatenate((np.minimum.accumulate(C[::-1])[::-1], [np.inf]))
        self.suffix_max = np.concatenate((np.maximum.accumulate(C[::-1])[::-1], [-np.inf]))

    def atr(self, s, e):
        """Mean true range over bars s..e."""
        return (self.tr_cum[e + 1] - self.tr_cum[s]) / (e - s + 1)


def _evaluate_box(ser, s, e, mode, T, B):
    """Validate the box [B, T] over bars s..e (anchor mode "inside" / "up" / "down").

    Returns a dict describing the rectangle, or None when a rule fails."""
    P = ser.P
    H, L = ser.H, ser.L
    height = T - B
    if height <= 0 or B <= 0:
        return None
    hpct = height / B * 100.0
    if hpct < P["min_height_pct"] or hpct > P["max_height_pct"]:
        return None
    atr = ser.atr(s, e)
    if not (atr > 0 and height >= P["min_height_atr"] * atr):
        return None
    band = max(P["band_atr"] * atr, P["band_frac"] * height)
    retreat = P["retreat_frac"] * height
    buf = P["breakout_buffer_atr"] * atr

    # --- the window starts with a genuine test of one of the lines -------------------
    if not ((ser.ph[s] and H[s] >= T - band and ser.pre_lo[s] <= T - retreat)
            or (ser.pl[s] and L[s] <= B + band and ser.pre_hi[s] >= B + retreat)):
        return None
    bars = e - s + 1
    c = ser.C[s:e + 1]

    # --- breakout anchors: the next close breaks out decisively and holds ------------
    if mode == "up":
        nxt = ser.C[e + 1]
        if not (nxt > T + buf and nxt > c.max() and ser.suffix_min[e + 2] >= T):
            return None
    elif mode == "down":
        nxt = ser.C[e + 1]
        if not (nxt < B - buf and nxt < c.min() and ser.suffix_max[e + 2] <= B):
            return None

    # --- containment of the closes --------------------------------------------------
    viol = 0
    failed = None
    fail0 = fail1 = bars          # window-relative span of a tolerated failed breakout
    if c.max() > T + buf or c.min() < B - buf:
        exc = _excursions(c, T, B, buf)
        last = exc[-1]
        # the window starts inside the box and no excursion is still open at its end
        # (that would be a breakout in progress, handled by a breakout anchor)
        if exc[0][1] == 0 or last[2] == bars - 1:
            return None
        if (s + last[1] >= ser.recent_start and last[3] <= P["failed_max_closes"]
                and (mode == "inside" or (last[0] == 1) == (mode == "up"))):
            failed = "up" if last[0] == 1 else "down"
            fail0, fail1 = last[1], last[2]
            exc = exc[:-1]
        for x in exc:
            if x[3] > P["max_false_run"]:
                return None
            viol += x[3]
        if viol > P["max_false_closes"]:
            return None

    # --- touch episodes ---------------------------------------------------------------
    h = H[s:e + 1]
    l = L[s:e + 1]
    ti, tp, t0, t1 = _touch_episodes(h, h >= T - band, l <= T - retreat, True)
    bi, bp, b0, b1 = _touch_episodes(l, l <= B + band, h >= B + retreat, False)
    nt, nb = len(ti), len(bi)
    need = P["min_touches_per_side"]
    if nt < need or nb < need:
        return None
    t_in = tp <= T + band             # extreme within the band (else a poke)
    b_in = bp >= B - band
    # confirmed touches define the lines: no close beyond the buffer inside the
    # episode, and on the breakout side not the run straight into the breakout
    t_ok = t_in.copy()
    b_ok = b_in.copy()
    if viol or failed:
        up_cum = np.concatenate(([0], np.cumsum(c > T + buf)))
        dn_cum = np.concatenate(([0], np.cumsum(c < B - buf)))
        t_ok &= (up_cum[t1 + 1] - up_cum[t0]) == 0
        b_ok &= (dn_cum[b1 + 1] - dn_cum[b0]) == 0
    k = P["pivot_strength"]
    if mode == "up" and t1[-1] == bars - 1:
        a0, a1 = s + t0[-1], e - k + 1
        if not (ser.ph[a0:a1] & (H[a0:a1] >= T - band)).any():
            t_ok[-1] = False
    elif mode == "down" and b1[-1] == bars - 1:
        a0, a1 = s + b0[-1], e - k + 1
        if not (ser.pl[a0:a1] & (L[a0:a1] <= B + band)).any():
            b_ok[-1] = False
    if t_ok.sum() < need or b_ok.sum() < need:
        return None
    # pokes; touches overlapping the failed breakout are beyond the line by definition
    t_failed = (t1 >= fail0) & (t0 <= fail1)
    b_failed = (b1 >= fail0) & (b0 <= fail1)
    if (np.count_nonzero(~t_in & ~t_failed) > P["max_pokes_per_side"]
            or np.count_nonzero(~b_in & ~b_failed) > P["max_pokes_per_side"]):
        return None
    pokes = (nt - int(t_in.sum())) + (nb - int(b_in.sum()))

    # --- alternation and activity -------------------------------------------------
    idx = np.concatenate((ti, bi))
    side = np.concatenate((np.ones(nt, dtype=np.int8), np.zeros(nb, dtype=np.int8)))
    order = np.argsort(idx, kind="stable")
    idx, side = idx[order], side[order]
    switches = int(np.count_nonzero(side[1:] != side[:-1]))
    if switches < max(P["min_switches"], math.ceil(bars / P["switch_density_bars"])):
        return None
    if (bars - 1) - int(idx[-1]) > max(P["max_idle_bars"], P["max_idle_frac"] * bars):
        return None
    tail = max(P["late_window_min_bars"], int(bars * P["late_window_frac"]))
    if h[-tail:].max() - l[-tail:].min() < P["min_late_range_frac"] * height:
        return None

    # --- flatness: fit through each side's touches (pokes clipped, failed breakout
    # left out), measured over the span of the touches (at least drift_min_span_frac
    # of the box) ------------------------------------------------------------------------
    clip = P["poke_clip"] * band
    tx, bx = ti[~t_failed], bi[~b_failed]
    if len(tx) == 0 or len(bx) == 0:
        return None               # a line resting only on the failed breakout
    slope_t = _slope(tx.tolist(), np.minimum(tp[~t_failed], T + clip).tolist())
    slope_b = _slope(bx.tolist(), np.maximum(bp[~b_failed], B - clip).tolist())
    life = float(bars - 1)
    min_span = P["drift_min_span_frac"] * life
    span_t = max(float(tx[-1] - tx[0]), min_span)
    span_b = max(float(bx[-1] - bx[0]), min_span)
    drift = max(abs(slope_t) * span_t, abs(slope_b) * span_b) / height
    if drift > P["max_drift_frac"]:
        return None
    if abs(slope_b - slope_t) * life / height > P["max_converge_frac"]:
        return None
    if abs(slope_b + slope_t) * 0.5 * life / height > P["max_parallel_drift_frac"]:
        return None

    # --- failed swings: between two touches of the same line, the swing toward the
    # other line fell short; they must stay a minority and must not coil ----------------
    swings_hi, swings_lo = [], []     # per side, in time order: None = touch, value = failed swing
    sides = side.tolist()
    at = idx.tolist()
    for i, top in enumerate(sides):
        (swings_hi if top else swings_lo).append(None)
        if i + 1 < len(sides) and sides[i + 1] == top:
            seg = slice(at[i], at[i + 1] + 1)
            if top:
                swings_lo.append(float(l[seg].min()))
            else:
                swings_hi.append(float(h[seg].max()))
    nti, nbi = int(t_in.sum()), int(b_in.sum())
    if len(swings_hi) - nt > max(1, nti - 1) or len(swings_lo) - nb > max(1, nbi - 1):
        return None
    fh = [v for v in swings_hi[-3:] if v is not None]
    fl = [v for v in swings_lo[-3:] if v is not None]
    if (len(fh) >= 2 and fh[-1] < fh[-2]) or (len(fl) >= 2 and fl[-1] > fl[-2]):
        return None               # lower highs / higher lows: a triangle or wedge forming

    # --- both lines tested across the box, from early on --------------------------------
    tin_i, bin_i = ti[t_in], bi[b_in]
    if min(tin_i[-1] - tin_i[0], bin_i[-1] - bin_i[0]) < P["min_side_span_frac"] * life:
        return None
    first_limit = max(P["max_first_touch_bars"], P["max_first_touch_frac"] * life)
    if tin_i[0] > first_limit or bin_i[0] > first_limit:
        return None

    # --- the closes fill the box ------------------------------------------------------------
    xs = np.arange(bars, dtype=float) - 0.5 * life
    cdrift = abs(float(np.dot(xs, c - c.mean())) / float(np.dot(xs, xs))) * life / height
    upfrac = float(np.count_nonzero(c > B + 0.5 * height)) / bars
    if cdrift > P["max_close_drift"] or not (P["min_upper_frac"] <= upfrac <= P["max_upper_frac"]):
        return None

    dev = (np.abs(tp[t_in] - T).sum() + np.abs(bp[b_in] - B).sum()) / ((nti + nbi) * band)
    m = {
        "s": s, "e": e, "T": T, "B": B, "buf": buf,
        "top_touches": nt, "bottom_touches": nb, "switches": switches,
        "touch_idx": idx + s, "touch_side": side, "touch_price": np.concatenate((tp, bp))[order],
        "viol": viol, "pokes": pokes, "failed": failed, "bars": bars,
        "dev": float(dev), "drift": drift / P["max_drift_frac"], "cdrift": cdrift,
        "upfrac": upfrac, "h_atr": height / atr,
    }
    m["quality"] = _quality(m)

    # --- weak boxes must be clean in every other respect -----------------------------
    weak = (switches <= P["weak_switches"]
            or (hpct > P["tall_height_pct"] and switches < P["tall_min_switches"])
            or (bars < P["short_bars"] and switches < P["short_min_switches"]))
    if weak and not (bars >= P["weak_min_bars"]
                     and height >= P["weak_min_height_atr"] * atr
                     and hpct <= P["weak_max_height_pct"]
                     and bars <= P["weak_max_bars_per_switch"] * switches
                     and drift <= P["weak_max_drift_frac"]
                     and cdrift <= P["weak_max_close_drift"]
                     and dev <= P["weak_max_dev"]
                     and m["quality"] >= P["weak_min_quality"]):
        return None

    m["sel"] = (2.0 * min(switches, 12) + min(nt + nb, 16) - 3.0 * viol - pokes
                + 0.25 * m["quality"] + P["length_pref"] * bars)
    return m


def _scan_anchor(ser, e, mode):
    """Best rectangle ending at bar e (see the module docstring, steps 2-4)."""
    P = ser.P
    k = P["pivot_strength"]
    lo = max(0, e - P["max_bars"] + 1)
    hi = e - P["min_bars"] + 1
    if hi < lo:
        return None
    H, L = ser.H, ser.L
    # swing pivots of the region; the last k bars use a window truncated at the anchor
    ph = ser.ph[lo:e + 1].copy()
    pl = ser.pl[lo:e + 1].copy()
    for i in range(max(lo, e - k + 1), e + 1):
        j0 = max(0, i - k)
        ph[i - lo] = H[i] >= H[j0:e + 1].max()
        pl[i - lo] = L[i] <= L[j0:e + 1].min()
    peak_idx = (np.flatnonzero(ph) + lo).tolist()
    trough_idx = (np.flatnonzero(pl) + lo).tolist()
    Hl, Ll, Cl = H.tolist(), L.tolist(), ser.C.tolist()
    # candidate starts: confirmed pivots, newest first
    starts = (np.flatnonzero(ser.ph[lo:hi + 1] | ser.pl[lo:hi + 1]) + lo)[::-1].tolist()
    peaks, troughs = [], []           # sorted swing highs / lows of [s, e]
    pi, ti = len(peak_idx) - 1, len(trough_idx) - 1
    max_skip = P["max_skip_peaks"]
    # the (max_false_closes + 1)-th highest / lowest close of [s, e] -- outside the zone
    # where a failed breakout may sit -- bounds every box that could still validate
    nk = P["max_false_closes"] + 1
    top_c, bot_c = [], []
    cpos = min(e, ser.recent_start - 1) + 1
    max_range = P["max_height_pct"] / 100.0 * P["scan_stop_mult"]
    best = None
    for s in starts:
        while pi >= 0 and peak_idx[pi] >= s:
            insort(peaks, Hl[peak_idx[pi]])
            pi -= 1
        while ti >= 0 and trough_idx[ti] >= s:
            insort(troughs, Ll[trough_idx[ti]])
            ti -= 1
        while cpos > s:
            cpos -= 1
            v = Cl[cpos]
            if len(top_c) < nk:
                insort(top_c, v)
                insort(bot_c, v)
            else:
                if v > top_c[0]:
                    top_c.pop(0)
                    insort(top_c, v)
                if v < bot_c[-1]:
                    bot_c.pop()
                    insort(bot_c, v)
        if len(top_c) == nk and bot_c[-1] > 0 and top_c[0] - bot_c[-1] > max_range * bot_c[-1]:
            break                     # the closes already span more than any box allows
        if len(peaks) < 2 or len(troughs) < 2:
            continue
        band0 = P["band_atr"] * ser.atr(s, e)
        if not band0 > 0:
            continue
        # the start pivot must be able to touch a line: near the few highest swing
        # highs or lowest swing lows of the window
        bmax = max(band0, P["band_frac"] * (peaks[-1] - troughs[0]))
        if not ((ser.ph[s] and Hl[s] >= peaks[max(0, len(peaks) - 1 - max_skip)] - 3.0 * bmax)
                or (ser.pl[s] and Ll[s] <= troughs[min(len(troughs) - 1, max_skip)] + 3.0 * bmax)):
            continue
        tops = _line_levels(peaks, band0, True, max_skip)
        bots = _line_levels(troughs, band0, False, max_skip)
        if not tops or not bots or tops[0] <= bots[0]:
            continue
        band = P["band_frac"] * (tops[0] - bots[0])
        if band > band0:              # the height sets the band: re-cluster with it
            tops = _line_levels(peaks, band, True, max_skip)
            bots = _line_levels(troughs, band, False, max_skip)
        for T in tops:
            for B in bots:
                r = _evaluate_box(ser, s, e, mode, T, B)
                if r is not None and (best is None or r["sel"] > best["sel"]):
                    best = r
    if best is not None:
        best = _extend_start(ser, best, e, mode)
    return best


def _extend_start(ser, best, e, mode):
    """The same box may have begun earlier than the window the scan settled on (that
    window's own swing extremes gave slightly different lines).  Walk back over bars
    whose closes stay inside the box and re-validate it, lines fixed, from earlier swing
    pivots; the earliest start that validates and scores no worse wins."""
    T, B, s = best["T"], best["B"], best["s"]
    lo = max(0, e - ser.P["max_bars"] + 1)
    i = s - 1
    while i >= lo and B - best["buf"] <= ser.C[i] <= T + best["buf"]:
        i -= 1
    for s2 in (np.flatnonzero(ser.ph[i + 1:s] | ser.pl[i + 1:s]) + i + 1).tolist():
        r = _evaluate_box(ser, s2, e, mode, T, B)
        if r is not None and r["sel"] >= best["sel"]:
            return r
    return best


# ----------------------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------------------
def detect(df: pd.DataFrame, params: dict | None = None) -> dict | None:
    """Best current rectangle on daily bars, or None (see the module docstring / SPEC).

    df: DatetimeIndex ascending, float columns open, high, low, close, volume; the
    last row is the latest completed session.  The input is not modified."""
    P = dict(DEFAULT_PARAMS)
    if params:
        P.update(params)
    if df is None or len(df) == 0:
        return None
    d = df
    if d[["high", "low", "close"]].isna().to_numpy().any():
        d = d.dropna(subset=["high", "low", "close"])
    n = len(d)
    if n < P["min_bars"] + 1:
        return None
    C = d["close"].to_numpy(dtype=float)
    H = np.maximum(d["high"].to_numpy(dtype=float), C)     # guard against bad prints
    L = np.minimum(d["low"].to_numpy(dtype=float), C)
    V = np.nan_to_num(d["volume"].to_numpy(dtype=float)) if "volume" in d.columns else np.zeros(n)
    ser = _Series(H, L, C, P)

    candidates = []
    r = _scan_anchor(ser, n - 1, "inside")
    if r is not None:
        r["status"], r["k"] = "inside", None
        candidates.append(r)
    # breakout bars: closes beyond the third-most-extreme close of the min_bars before
    mb = P["min_bars"]
    for kb in range(max(mb, n - 1 - P["max_breakout_age"]), n):
        prior = np.sort(C[kb - mb:kb])
        for mode, status in (("up", "breakout_up"), ("down", "breakout_down")):
            if mode == "up" and not (C[kb] > prior[-3] and C[kb] > C[kb - 1]):
                continue
            if mode == "down" and not (C[kb] < prior[2] and C[kb] < C[kb - 1]):
                continue
            r = _scan_anchor(ser, kb - 1, mode)
            if r is not None:
                r["status"], r["k"] = status, kb
                candidates.append(r)
    if not candidates:
        return None
    best = max(candidates, key=lambda m: m["sel"])
    return _format(best, d, P, C, V, _true_range(H, L, C))


def _fmt_date(ts):
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _format(m, d, P, C, V, tr):
    idx = d.index
    n = len(C)
    T, B = float(m["T"]), float(m["B"])
    height = T - B
    last = float(C[-1])
    status = m["status"]
    kb = m["k"]
    atr_last = _wilder_atr_last(tr, P["atr_period"])
    out = {
        "status": status,
        "top": round(T, 4),
        "bottom": round(B, 4),
        "start": _fmt_date(idx[m["s"]]),
        "end": _fmt_date(idx[m["e"]]),
        "bars": int(m["bars"]),
        "height_pct": round(height / B * 100.0, 3),
        "top_touches": int(m["top_touches"]),
        "bottom_touches": int(m["bottom_touches"]),
        "switches": int(m["switches"]),
        "touches": [
            {"date": _fmt_date(idx[int(i)]), "side": "top" if sd else "bottom", "price": round(float(p), 4)}
            for i, sd, p in zip(m["touch_idx"], m["touch_side"], m["touch_price"])
        ],
        "breakout_date": None,
        "days_since_breakout": None,
        "breakout_volume_ratio": None,
        "position_pct": round((last - B) / height * 100.0, 2),
        "extension_pct": None,
        "target": None,
        "failed_breakout": m["failed"] if status == "inside" else None,
        "atr_pct": round(atr_last / last * 100.0, 3) if last > 0 else 0.0,
        "quality": float(m["quality"]),
    }
    if kb is not None:
        out["breakout_date"] = _fmt_date(idx[kb])
        out["days_since_breakout"] = int(n - 1 - kb)
        base = V[max(0, kb - P["volume_lookback"]):kb]
        mean_vol = float(base.mean()) if len(base) else 0.0
        out["breakout_volume_ratio"] = round(float(V[kb]) / mean_vol, 3) if mean_vol > 0 else None
        if status == "breakout_up":
            out["extension_pct"] = round((last - T) / height * 100.0, 2)
            out["target"] = round(T + height, 4)
        else:
            out["extension_pct"] = round((B - last) / height * 100.0, 2)
            out["target"] = round(B - height, 4)
    for key, val in out.items():
        if isinstance(val, float) and not math.isfinite(val):
            out[key] = 0.0 if key in ("atr_pct", "position_pct") else None
    return out
