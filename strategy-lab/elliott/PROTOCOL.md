# Elliott Wave study: research protocol

This file is written and committed before any setup or behavior test has been
run on prices. Its commit is the pre-registration, and anything run later
that it does not describe is labelled exploratory.

## Question

Can the trade setups and price behavior that Elliott Wave practitioners
publish be turned into rules a computer applies without hindsight? If they
can, do those rules beat random entries made the same way, and do any of them
add up to a trading system that beats buy-and-hold SPY on data held back from
the choice? Frost & Prechter's Fibonacci expectations are tested directly:

- wave 2 retraces 61.8% or 50% of wave 1;
- wave 4 retraces 38.2% of wave 3;
- wave 3 is 1.618 x wave 1;
- wave 5 equals wave 1 when wave 3 extends;
- C equals A in a zigzag;
- a correction ends near the previous fourth wave.

**Sources.** The setups and parameters come from a literature sweep: Frost &
Prechter's *Elliott Wave Principle* (EWP), Jeffrey Kennedy and other Elliott
Wave International material, the Advanced GET / eSignal manuals (Tom Joseph),
Glenn Neely, Gorman & Kennedy (2013), and open-source wave tools. The
researchers could read search excerpts but not full texts, so some numbers
are from memory of the sources. Where no source gives a number, the choice
here is marked [chosen].

**Prior evidence.**
- No peer-reviewed study shows rule-based Elliott trading beating a proper
  null out of sample.
- Tests of Fibonacci levels found no special clustering or bounce compared
  with other levels: Batchelor & Ramyar 2006 (Dow, block bootstrap);
  Bulkowski 2020 (489 stocks); Tsinaslanidis et al. 2022.
- Prechter's published forecasts scored lowest among tracked forecasters
  (Bailey et al.).
- Five random swings filtered by Elliott's three hard rules already show
  "wave 3 is the longest" about 80% of the time.

This study therefore compares every claim with matched random data, not
with zero.

## Data and periods

| dataset | bars | role | in-sample (choice) | held out (scored once) |
| --- | --- | --- | --- | --- |
| `stocks_daily` | Robinhood daily, 1,897 stocks of the screener universe, 2016-01-04 to 2026-10-16 | confirmatory | signals 2016-01-04 to 2021-12-31 | signals 2022-01-03 to 2026-10-16 |
| `stocks_1h` | Yahoo hourly, regular session, 323 symbols (30 ETFs and the most traded stocks), 2023-11-17 to 2026-10-16 | confirmatory | signals before 2025-10-01 | signals from 2025-10-01 |
| `stocks_4h` | the same hours in two bars a day (09:30-13:30, 13:30-16:00) | exploratory | same split | same split |
| `etf_daily` | Yahoo daily, the 26 ETFs in `../data/yahoo`, from listing | exploratory | signals to 2015-12-31 | signals from 2016-01-04 |

Data rules:

- **Daily stocks.** Bars are cleaned as in the screener backtest. A signal is
  taken only when the stock passes the screener's liquidity rule (median
  dollar volume over 50 sessions of at least $20M) on the signal bar.
- **Hourly symbols.** A symbol is dropped if any overnight gap exceeds a
  factor of 3 (an unadjusted split or a data error; this drops BNY and
  BMNR), or if it has fewer than 1,000 bars.
- **Survivorship.** Every symbol is one that trades today. That flatters
  longs and hurts shorts, and the random twins (below) are drawn from the
  same survivors.
- **Period boundaries.** A signal belongs to a period only if its whole
  possible life ends inside that period. Its deadline is fixed when the
  signal appears, and is the order's expiry (for a limit order) plus the
  time exit. Signals whose deadline crosses a boundary are dropped from both
  periods. That rule doesn't depend on how the trade turns out.

## Swing pivots (all setups and tests)

All of this is computed in log prices.

- **True range.** TR_t = max(lnH_t - lnL_t, |lnH_t - lnC_{t-1}|,
  |lnL_t - lnC_{t-1}|), with TR_0 = lnH_0 - lnL_0.
- **ATR (Wilder, 14).** ATR_13 = mean(TR_0..TR_13), then
  ATR_t = (13 ATR_{t-1} + TR_t)/14.
- **Threshold.** k = 2.0 for the confirmatory tests. k = 1.5 and 3.0 are
  exploratory.
- **Start.** From bar 50, track a running high H* and a running low L*,
  each with its bar e and threshold theta = k x ATR_e. The low is confirmed
  at the first bar t > e_L whose close >= ln L* + theta_L. The high is
  confirmed at the first t > e_H whose close <= ln H* - theta_H. If both
  happen on one bar, the extreme with the earlier bar wins. This first pivot
  sets the direction. It is never used in a pattern.
- **Up mode** (after a low confirmed at bar c):
  - H* = the highest high over bars (e_L, c], at its earliest bar e_H, with
    theta_H = k x ATR_{e_H}.
  - On each later bar t: if high_t > H*, set H* = high_t, e_H = t,
    theta_H = k x ATR_t.
  - Otherwise, if close_t <= ln H* - theta_H, the pivot high (H*, e_H) is
    confirmed at c = t, and down mode starts from the lowest low over
    (e_H, t].
  - Down mode mirrors this.
- **What gets stored.** The threshold is frozen at the extreme's bar. A bar
  that makes a new extreme cannot also confirm it. Each pivot stores its
  price p (bar high or low), extreme bar e and confirmation bar c. A pattern
  may use a pivot only from bar c on. Confirmed pivots never move.

**Notation.**
- P_i: consecutive confirmed pivots.
- W_i = |ln p_i - ln p_{i-1}|; D_i = e_i - e_{i-1}; r2 = W2/W1, r4 = W4/W3.
- **K1** (Neely's similarity): for two adjacent legs, min/max of their W >=
  1/3, or min/max of their D >= 1/3.
- A "tick" is 1 bp: stop = level x (1 - 0.0001) for longs, x (1 + 0.0001)
  for shorts.
- Arithmetic levels (the limit orders) use prices, as charting tools draw
  them.

## Execution (all setups)

- **Market entries** fill at the open of the bar after the signal.
- **Limit entries:**
  - fill at the limit when a bar's range reaches it;
  - fill at the open when a bar opens beyond the limit (but not beyond the
    stop or the cancel level);
  - no fill on a bar that also breaches the setup's cancel level.
- **Stops and targets** rest from the entry bar on:
  - a gap through a level fills at the open;
  - when the stop and the target are both inside one bar, the stop counts
    first;
  - on a limit-fill bar the stop is checked but the target is not.
- **Time exits** are at the close of entry bar + N.
- **One slot per symbol, setup and direction.** A pending order or an open
  trade holds it, and a new signal while it is busy is dropped.
- **Skips.** A market entry is skipped when the entry open is already at or
  beyond the stop or the target.
- **Costs** per side, as a share of price: 0.05% on daily bars, 0.10% on
  hourly and 4-hour bars. A 2x-cost run is reported.

## Setups

Long versions are described here. Each short version is the mirror image
(highs and lows swapped, signs reversed). The confirmatory set is S1, S2, S3,
S5, F2-618, F2-500 and F4-382, each long and short, on `stocks_daily` and
`stocks_1h`: 28 tests. P_{-1} is the pivot before P0.

**S1, the wave-3 entry at the end of wave 2** (Kennedy)
- Evaluated at c2, on pivots P_{-1} (high), P0 (low), P1 (high), P2 (low):
  - high(P1) > high(P_{-1});
  - p2 > p0;
  - 0.50 <= r2 <= 0.786;
  - K1(W1, W2).
- Market entry at c2+1.
- Stop: a tick below p0.
- Target: ln T = ln p2 + 1.618 W1.
- Time exit: entry + 3 D1 [chosen].
- Baseline: identical, but with r2 < 0.50 or r2 > 0.786.
- Reported: the share of fills at or above p1.

**S2, the wave-5 entry at the end of wave 4** (Kennedy; Advanced GET
projection)
- Evaluated at c4, on pivots P0 (low) .. P4 (low):
  - p2 > p0;
  - high(P3) > high(P1);
  - W3 > W1;
  - low(P4) > high(P1);
  - 0.236 <= r4 <= 0.50;
  - K1 on (W1, W2), (W2, W3) and (W3, W4).
- Market entry at c4+1.
- Stop: a tick below high(P1).
- Target:
  - if W3 >= 1.618 W1: ln T = ln p4 + W1;
  - otherwise: ln T = ln p4 + 0.618 (ln p3 - ln p0).
- Time exit: entry + 3 D1.
- Baseline: identical, but with r4 < 0.236 or r4 > 0.50, while still
  keeping low(P4) > high(P1).

**S3, the Elliott Wave Oscillator wave-4 pullback** (inspired by Advanced
GET's Type 1; the oscillator alone, with no wave count)
- **Definitions.**
  - EWO_t = SMA5(hl2) - SMA35(hl2), where hl2 = (high + low)/2.
  - DMA_t = mean(close_{t-9}..close_{t-4}), a 6-bar average displaced 4
    bars.
  - Warm-up: 334 bars.
- **Wave-3 peak.** At bar t, it is a candidate peak (s3 = t, M = EWO_t) if:
  - EWO_t is the maximum of EWO over [t-149, t];
  - EWO_t > 0;
  - EWO_t >= 2.0 x the population standard deviation of EWO over
    [t-149, t] [chosen, standing in for GET's proprietary breakout band].

  A newer candidate replaces an unarmed one.
- **Arming.**
  - It arms at the first t4 > s3 with EWO_t4 <= 0.10 M, provided EWO
    stayed >= -0.40 M on every bar in (s3, t4].
  - M and s3 are then frozen.
  - P3 = the highest high over [s3, t4], at bar e3.
  - Each s3 arms once.
- **Cancel** if any of these happens, checked before the trigger on each bar:
  - EWO < -0.40 M;
  - a high > P3;
  - more than 35 bars after t4.
- **Trigger.** The first armed bar t on which close_t > DMA_t and
  close_{t-1} <= DMA_{t-1}. Market entry at t+1.
- **Stop:** a tick below the lowest low over [e3, t].
- **Exit.** After the first bar whose high exceeds P3, exit at the next
  open after the first close below the DMA. The trade also has the stop and
  a time exit at entry + 35.
- **Baseline.** Any 150-bar EWO maximum above 0, with no band test. It arms
  at the first later close below the DMA, with no oscillator depth
  condition. P3, the trigger, stop, exits, the expiry and the "high > P3"
  cancel are the same.

**S5, the ABC zigzag C = A buy zone** (elliottwave-forecast's "blue box";
simplified exits)
- Evaluated at cB, on pivots P_{-1} (high), Q (low), A0 (high), A1 (low),
  B (high):
  - high(A0) > high(P_{-1});
  - A = ln a0 - ln a1;
  - 0.382 <= (ln B - ln a1)/A <= 0.786;
  - K1(A, B).
- **Box.** U = exp(ln B - 1.0 A) (C = A) and V = exp(ln B - 1.618 A).
- **Order.** A buy limit at U, live from cB+1. Cancel if a high > high(B)
  or a bar opens at or below V. It expires at cB + 3 D_A, where
  D_A = e_A1 - e_A0.
- **Stop:** a tick below V.
- **Target:** high(A0).
- **Time exit:** fill + 3 D_A.
- **Controls** (the baseline, pooled): the same trade with the limit at
  ln B - 0.85 A and at ln B - 1.15 A.

**F2-618 and F2-500, the Fibonacci wave-2 buy limits** (EWP: "sharp
corrections tend more often to retrace 61.8% or 50% of the previous wave,
particularly when they occur as wave 2")
- Evaluated at c1, on pivots P_{-1} (high), P0 (low), P1 (high), with
  high(P1) > high(P_{-1}) (wave 1 makes a higher high).
- **Level.** L = p1 - f (p1 - p0) with f = 0.618 or 0.500. Skip if the
  close at c1 is already at or below L.
- **Order.** A buy limit at L from c1+1. Cancel if a high > p1 or a bar
  opens at or below the stop. It expires at c1 + 3 D1.
- **Stop:** a tick below p0 (wave 2 may not pass the start of wave 1).
- **Target:** L + 1.618 (p1 - p0), i.e. wave 3 = 1.618 x wave 1 from the
  fill.
- **Time exit:** fill + 3 D1.
- **Controls** (pooled, shared by both): f = 0.437, 0.556 and 0.697, the
  geometric midpoints between the practitioner levels 0.382, 0.5, 0.618 and
  0.786.

**F4-382, the Fibonacci wave-4 buy limit** (EWP: "sideways corrections tend
more often to retrace 38.2% of the previous impulse wave, particularly when
they occur as wave 4")
- Evaluated at c3, on pivots P0 (low), P1 (high), P2 (low), P3 (high):
  - p2 > p0;
  - high(P3) > high(P1);
  - W3 > W1;
  - K1 on (W1, W2) and (W2, W3).
- **Level.** L = p3 - 0.382 (p3 - p2). Skip if L <= high(P1) (no overlap
  allowed), or if the close at c3 is already at or below L.
- **Order.** A buy limit at L from c3+1. Cancel if a high > p3 or a bar
  opens at or below the stop. It expires at c3 + 3 D1.
- **Stop:** a tick below high(P1).
- **Target:** L + (p1 - p0), i.e. wave 5 = wave 1 from the fill.
- **Time exit:** fill + 3 D1.
- **Controls** (pooled): f = 0.309 and 0.437.

**Exploratory setups.** These are reported but carry no decision.
- **S4: fading a completed five-wave impulse when the oscillator diverges**
  (Advanced GET Type 2, Gorman & Kennedy).
  - Pattern, evaluated at c5, on pivots P0..P5 with P5 a high:
    - the hard rules: p2 > p0, high(P3) > high(P1), low(P4) > high(P1),
      W3 > min(W1, W5), high(P5) > high(P3);
    - K1 on every adjacent pair;
    - E3 = max EWO over [e2, e3] > 0;
    - min EWO over [e3, e4] <= 0.10 E3;
    - max EWO over [e4, e5] < E3.
  - Entry: short at the next open after the first close below the DMA at or
    after c5. Cancel if a high > high(P5), or a low <= low(P4).
  - Stop: a tick above high(P5).
  - Target: low(P4).
  - Time exit: e5 + (e5 - e4). Skip if that is at or before the entry bar.
- **S6: the ending-diagonal fade.**
  - Pattern, evaluated at c5, on pivots P0..P5:
    - p2 > p0;
    - high(P3) > high(P1);
    - low(P4) > low(P2);
    - high(P5) > high(P3);
    - low(P4) < high(P1);
    - W3 < W1, W4 < W2, W5 < W3;
    - the P2-P4 slope (log per bar) > the P1-P3 slope > 0;
    - K1 on every adjacent pair.
  - Entry: short at the next open after the first close below low(P4).
    Cancel if a high > high(P5).
  - Stop: a tick above high(P5).
  - Target: low(P0).
  - Time exit: e5 + ceil(0.5 (e5 - e0)).
- **Other variations:**
  - F4 at 0.236;
  - S1 with Kennedy's conservative trigger (the first close above p1) and
    with the stop at p2;
  - every setup at k = 1.5 and 3.0, on `stocks_4h` and on `etf_daily`.

## Scoring a setup

- **R.** For a long, R = (exit - E)/(E - stop) - 2 x cost x E/(E - stop),
  where E is the fill price. Shorts mirror this.
- **Random twins** (20 per trade). Each twin is another symbol that has a
  bar at the trade's entry bar time and is liquid on the bar before it. It
  enters at that bar's open, in the same direction.
  - Its stop and target are the same distances from entry in its own ATR as
    of the bar before entry (log ATR, as above).
  - It has the same time exit in bars.
  - For S3, the "new high" level is set the same way, and the DMA exit runs
    on the twin's own prices.
  - A trade with fewer than 10 usable twins is dropped.
- **Edge.** The trade's R minus its twins' mean R.
- **Inference** uses a cluster bootstrap over the calendar month of the
  signal bar (daily) or its ISO week (hourly), with 10,000 draws.
  One-sided p is the share of resampled means <= 0.
- **Baseline contrast.** The setup's mean R minus its baseline's or
  controls' mean R. Both are resampled by the same clusters.

**Choosing finalists (in-sample).** A setup / direction / dataset is a
finalist only if all of these hold:
1. its mean edge is > 0 and significant after Benjamini-Hochberg at q = 0.05
   across the 28 confirmatory tests;
2. mean R > 0 (p < 0.05);
3. the baseline contrast is > 0 (p < 0.05);
4. mean R > 0 at 2x costs;
5. mean edge > 0 in each half of the in-sample period (split at 2019-01-01
   daily, 2024-11-01 hourly).

**The held-out test (each finalist once).** All of these must hold:
- mean edge > 0, with p < 0.05 after Holm across the finalists;
- mean R > 0 (p < 0.05);
- baseline contrast > 0.

**Is it a system?** A finalist that passes the held-out test is then traded
as a portfolio over the held-out period:
- **Account.** $100,000 to start.
- **Sizing.** Each trade risks 0.5% of equity between entry and stop, and
  is capped at 10% of equity. Gross exposure is capped at 100%.
- **Shorts** are funded in cash, with no borrow fee.
- **Costs** as above.
- **Order of simultaneous signals.** Ten random orders are run, and the
  median result is used.

The benchmark is SPY with dividends (`../data/yahoo`) over the same dates.
To pass, the median run needs a higher CAGR, a Sharpe ratio (daily excess
over BIL x sqrt(252)) at least as high, and a max drawdown no deeper.

**The answer to "can we build on it".** Yes only for a setup that passes
the held-out test and the portfolio test. If none does, the answer is no.

## Behavior tests (Frost & Prechter's expectations)

All of these are on `stocks_daily` and `stocks_1h` at k = 2. Patterns are
dated by their last confirmation bar, and in-sample and held-out are
reported separately.

| id | claim (EWP) | measurement | Elliott predicts |
| --- | --- | --- | --- |
| B1a | wave 2 retraces 61.8% or 50% of wave 1 | among triples P0-P1-P2 with r2 < 1: share with \|ln(r2/0.618)\| <= 0.03 or \|ln(r2/0.5)\| <= 0.03 | above null |
| B1b | wave 4 retraces 38.2% of wave 3 | among P0..P4 with p2 > p0, high(P3) > high(P1), low(P4) > high(P1): share with \|ln(r4/0.382)\| <= 0.03 | above null |
| B2 | wave 3 is never the shortest, and often the longest | among P0..P5 with p2 > p0, P3 beyond P1, no overlap, P5 beyond P3, and without the wave-3 rule: share with W3 the longest of W1, W3, W5 | above null |
| B3 | when wave 3 extends, wave 5 tends to equal wave 1 | among those impulses also passing W3 > min(W1, W5) and with W3 >= 1.618 max(W1, W5): share with \|W5/W1 - 1\| <= 0.10 | above null |
| B4 | alternation of waves 2 and 4 | among B3's base impulses: share with (r2 >= 0.5 and r4 <= 0.382) or (r2 <= 0.382 and r4 >= 0.5) or max(D2, D4)/min(D2, D4) >= 1.618 | above null |
| B5 | a correction ends in the span of the previous fourth wave, most often near its end | for each B3-base impulse, the correction low m (lowest low from e5 until a high beyond p5 or e5 + (e5 - e0)), with z = (ln m - ln p4)/(ln p3 - ln p4): share with \|z\| <= 0.15 | above null |
| B6 | wave 3 is 1.618 x wave 1 | among P0..P3 with p2 > p0 and high(P3) > high(P1): share with \|(W3/W1)/1.618 - 1\| <= 0.10 | above null |
| B7 | in a zigzag, C equals A | among A-B-C (pivots A0, A1, B, C) with 0.382 <= B/A <= 0.786 and C beyond A1: share with \|C/A - 1\| <= 0.10 | above null |

- **Directions.** Up and down patterns are pooled. Reported but not
  decided on: the same shares at non-Fibonacci controls (0.437 / 0.556 /
  0.697 for B1a; 0.309 / 0.437 for B1b; W5/W1 = 0.8 and 1.25 for B3; z = 0.5
  and -0.5 for B5; 1.4 and 1.8 for B6; C/A = 0.85 and 1.15 for B7), the full
  ratio histograms, and arithmetic ratios.
- **Null.** For each symbol, 20 stationary-bootstrap surrogates (Politis &
  Romano). Whole bars are resampled as vectors of log open, high, low and
  close relative to the previous close. The mean block is 20 daily or 35
  hourly bars. The same detector and measurements run on them.
- **Test.** The statistic is the pooled share in real data minus the pooled
  share in the surrogates. Its interval and one-sided p come from a
  bootstrap over symbols (10,000 draws). Benjamini-Hochberg at q = 0.05 runs
  across the 16 in-sample tests.
- **Supported** means significant in-sample, then p < 0.05 held out.

**Fibonacci levels against neighbouring levels, in trades.** Each Fibonacci
limit setup is compared with its non-Fibonacci controls: F2 (0.618 and 0.5
pooled) against the F2 controls, F4-382 against its controls, and S5's
C = A against its 0.85 / 1.15 controls. Mean R difference, for each
direction and dataset, gives 12 tests: BH in-sample, then a held-out
replication at p < 0.05. This is the test of whether the Fibonacci numbers
themselves matter.

## Amendments before the first real-data run

**Why.** Before any setup or test touched real prices, the scoring was
calibrated on simulated random walks, where no setup can have an edge. That
code is in `calibration/`, with results in `calibration/*_result.txt`. The
walks used 300 symbols x 2,700 bars, and each bar was 16 sub-steps of one
price path. The calibration showed two flaws in the scoring as first
written.

1. **Minimum stop distance.** Some F4 stops sat 0.1-0.2 ATR from entry, at
   the 5th percentile. That gave R values up to ±165, which decided the
   means. So a trade whose entry-to-stop distance is under 0.5 x log ATR (as
   of the bar before entry) is skipped and does not hold the slot. Twins
   follow the same rule.
2. **Twins of limit-order setups** (F2, F4, S5 and their controls).
   - **Problem.** Entry-bar twins penalized limit trades on random walks:
     edges of -0.03 to -0.5 R, several with intervals excluding zero.
   - **Change.** Each twin now places the same order on its own symbol, at
     the signal bar's time, liquid on that bar. The limit, cancel level,
     cancel-open level, stop and target sit at the same log-ATR distances
     from the twin's signal-bar close (ATR of the signal bar). Expiry and
     time exit are the same. Only twins whose orders fill count: up to 200
     draws per trade for 20 fills, with 10 the minimum.
   - **Market setups** keep entry-bar twins.
3. **Non-positive targets.** A target at or below zero, possible for short
   arithmetic targets, counts as no target.

**Results after the amendments.**
- **The 14 confirmatory setup x direction combinations:** random-walk edges
  run from -0.056 to +0.055 R, and every 95% interval includes zero.
- **Exploratory S6:** ±0.10 to 0.18 R, with intervals excluding zero. Its
  real-data results are read with that in mind.
- **Behavior tests on random walks:** excesses run from -0.022 to +0.007,
  and every interval includes zero.
