# Triangle and support/resistance breakouts: research protocol

This file is written and committed before any detector has been run on real
prices. Its commit is the pre-registration, and anything run later that it
does not describe is labelled exploratory.

## Question

Do breakouts from ascending triangles, descending triangles, and horizontal
support or resistance levels predict returns on daily, weekly and monthly
bars? Specifically:

- **Against random trades.** Do they beat random trades with the same stop,
  target and holding limit?
- **Against plain breakouts.** Do they beat ordinary breakouts to a new high
  or low over the same number of bars? Every flat-top breakout is also a
  new N-bar high, so the pattern only adds something if it beats that.
- **As a system.** Does any of them make a system that beats buy-and-hold
  SPY on years held back from the choice?

**Prior evidence.** `research/` has the sources.
- **Bulkowski's figures are not tradable as they stand.** He reports, for
  example, that ascending triangles break upward 63% of the time, rise 43%
  on average after an upward breakout, and reach the measured-move target
  70% of the time. Those figures come from:
  - daily, bull-market-only tables;
  - visually selected patterns;
  - no costs;
  - a hindsight exit at the "ultimate high".
- **His own trading test fell apart out of sample.** He found about 2% a
  trade with a 3-day hold, and the best in-sample rule ranked near the
  bottom out of sample. He also reports that breakout failure rates roughly
  doubled from the 1990s to 2003-07.
- **No published test of these triangles on weekly or monthly bars was
  found.**
- **Academic tests of trading-range breaks (Brock, Lakonishok & LeBaron).**
  These found predictive power on the Dow, 1897-1986. It did not survive
  corrections for the number of rules tried, or out-of-sample years
  (Sullivan, Timmermann & White; Bajgrowicz & Scaillet).
- **The 52-week-high effect (George & Hwang).** It was strong before 2000
  and weak or reversed afterwards.
- **Horizontal levels as support** sometimes predict bounces (Osler,
  intraday FX; Zapranis & Tsinaslanidis), but trading them has not beaten
  buy-and-hold.
- **This lab's rectangle study.** Daily rectangle breakouts confirmed 3%
  outside the range did no better than random entries with the same stops
  and targets (`../../rectangle-screener`).

## Data and periods

| dataset | bars | in-sample (choice) | held out (scored once) |
| --- | --- | --- | --- |
| `daily` | the Elliott study's cache: Robinhood daily bars, 1,897 stocks of the rectangle screener's universe, 2016-01-04 to 2026-10-16 | signals 2016-01-04 to 2021-12-31 | signals 2022-01-03 to 2026-10-16 |
| `weekly` | Yahoo weekly bars (`../data/yahoo_long/weekly.npz`), 1,943 of the same universe's symbols, bars from 1985 | signals 1990-01-01 to 2011-12-31 | signals 2012-01-01 to 2026-10-16 |
| `monthly` | Yahoo monthly bars (`monthly.npz`), 1,875 symbols, bars from 1985 | signals 1990-01-01 to 2011-12-31 | signals 2012-01-01 to 2026-09-30 |

- **In-sample runs read nothing after the in-sample end.** Held-out runs read
  everything.
- **A signal counts in a period** when its bar is in the period and the last
  bar its trade can reach is in the data the run reads (as in the Elliott
  study).
- **Yahoo bars.**
  - Prices are split-adjusted, not dividend-adjusted.
  - Bars before 1985 are dropped.
  - A bar is dropped when any price is missing or not positive.
  - A bar is dropped when its close is more than 2.5x away from the
    previous close and the next close is back within 1.25x of the previous
    one (a one-bar spike; 9 weekly and 8 monthly cases).
  - High and low are widened to contain the open and close.
- **Liquidity.** A signal is taken only when the stock passes a liquidity
  rule on its signal bar:
  - daily: the screener's rule, a median dollar volume of at least $20M over
    the last 50 sessions;
  - weekly: a median of close x volume over the last 26 weeks of at least
    $25M a week;
  - monthly: a median over the last 12 months of at least $100M a month.
  Twins must pass the same rule on the bar before their entry.
- **Survivors.** Every symbol is a US stock of at least $2B as of October
  2026. Its history is a survivor's history: stocks that failed are absent.
  - This favours long trades and hurts short trades.
  - It inflates every account's return.
  - The random twins and the plain breakouts below come from the same
    survivors, so the comparisons with them are fair. Absolute returns, and
    the comparison with SPY, are not.

## Swing points

- **Pivots (fractal).** A pivot high at bar j has a high at least as high as
  each of the k bars before it, and higher than each of the k bars after
  it. It becomes known at the close of bar j + k. Pivot lows mirror this.
- **k** is 5 daily, 3 weekly, 2 monthly.
- **A pattern may use a pivot only from its confirmation bar on.** That is
  the study's look-ahead rule.
- **ATR** is Wilder's 14-bar average of the log true range, as in the
  Elliott study.

## Patterns

Prices are logs. Each pattern is checked at every bar t as a possible
breakout bar. Short patterns are the long ones with prices mirrored
(highs become negated lows), so one piece of code does both. A pattern
starts at a confirmed pivot high that touches its flat line (the "first
touch", at bar f), and is defined by the pivots confirmed by bar t.

**Shared rules**
- **Duration.** t - f is 15-250 bars daily, 8-156 weekly, 8-120 monthly.
- **The level and its tolerance.**
  - The level U is the highest confirmed pivot high from f to t.
  - The tolerance tau is the median bar range, log(high/low), over bars f
    to t.
  - A touch is a confirmed pivot high from f to t at or above U - tau.
- **Containment and breakout.** Every close from f to t - 1 is at or below
  U, and the close at t is above U. So t is the first close above the
  level.
- **The earliest start wins.** Of the bars f that qualify, the earliest is
  used.

**AT, ascending triangle, long breakouts**
- **Lines.** At least 2 touches on the flat top. At least 2 pivot lows after
  f, each higher than the one before.
- **Touches.** At least 5 in all.
- **Not a rectangle.** The lows span more than tau.
- **Alternation.** In time order, the touches and the lows alternate: no two
  touches without a low between, no two lows without a touch between.
  Pivot highs below U - tau are ignored.
- **Apex.** The least-squares line through the lows rises, and at bar t it
  is still below U.

**DT, descending triangle, short breakdowns.** The mirror of AT: a flat
bottom, falling highs, and the first close below the level.

**HR, horizontal resistance, long breakouts**
- **Touches.** At least 3.
- **Alternation.** Between each two touches there is a confirmed pivot low
  at least 2 x tau below U.
- **The lows are otherwise free.** So HR includes AT whenever the AT has 3
  top touches.

**HS, horizontal support, short breakdowns.** The mirror of HR.

## Trades

- **Entry** at the open of the bar after the signal.
- **Stop.**
  - Longs: the pattern low (the lowest low from f to t) less 0.01%.
  - Shorts: the pattern high plus 0.01%.
- **Target.** The measured move.
  - Longs: U plus the pattern's height in price, U - pattern low.
  - Shorts: the mirror. A short target at or below zero means no target.
- **Time exit** at the close of entry + 63 bars daily, 26 weekly, 12
  monthly.
- **Exits.** These are the Elliott study's (`../elliott/waves.py`
  `run_exit`):
  - a stop or target touched within a bar fills at its level;
  - a bar that opens beyond the stop or the target fills at that open;
  - when one bar touches both, the stop counts first.
- **No trade** when the entry opens beyond the stop or the target, or when
  the stop is within half an ATR of the entry (the Elliott study's rule).
- **One position per stock, setup and direction.** A signal while one is
  open is dropped.
- **Costs** are 0.05% a side.
- **Shorts** pay no borrowing fee. The result is measured in R: profit
  divided by the distance from entry to stop, net of costs.

## Controls

1. **Random twins** (the Elliott study's entry-bar twins).
   - Each trade gets 20 other stocks that pass the liquidity rule on the bar
     before its entry. Each is entered at the open of the same bar.
   - Each twin uses the same direction, the same stop and target distances
     in units of its own ATR, and the same time exit.
   - Twins are drawn without replacement. A trade needs at least 10 twins.
   - **The edge** is the trade's R minus its twins' mean R.
2. **Matched plain breakouts.**
   - **Which stocks.** For a pattern signal at bar time T with duration
     N = t - f, up to 5 other stocks are drawn at random, seeded per
     signal. Each must pass the liquidity rule at T. Each must make a plain
     breakout at T: its close at T is above the highest high of its
     previous N bars, and its close the bar before was not above the
     highest high of the N bars before that (below the lowest low, for
     shorts). None may have a signal of the same setup at T.
   - **When none qualifies at T,** the nearest bar times within 5 bars are
     searched.
   - **How each is traded.** The same rules, with:
     - stop: the lowest low of the N bars, less 0.01%;
     - target: the breakout level plus the N-bar range (highest high less
       lowest low);
     - the same time exit.
   - **The pattern's premium** is the trade's R minus the mean R of its
     matched breakouts.

## Scoring and choosing finalists (in-sample)

**The confirmatory family** is 4 setups x 3 datasets = 12 tests:
- the setups are AT long, DT short, HR long and HS short;
- the datasets are daily, weekly and monthly.

**Inference** uses a bootstrap over calendar clusters, resampling whole
clusters with 10,000 draws:
- clusters are quarters for daily trades, and years for weekly and monthly
  trades (by signal bar);
- p is one-sided, the share of resampled means at or below zero.

**A test is a finalist if all of these hold in-sample:**
1. its edge over the twins is positive, with a Benjamini-Hochberg q below
   0.05 across the 12 tests;
2. its mean R is positive with p below 0.05;
3. its premium over matched plain breakouts is positive with p below 0.05;
4. its mean R is still positive at double costs;
5. its edge is positive in both halves of the in-sample period. The halves
   split at 2019-01-01 daily, and at 2001-01-01 weekly and monthly.

## Held-out test (scored once)

**A finalist passes** if, in its held-out period:
- its edge is positive with a Holm-adjusted p below 0.05 across the
  finalists;
- its mean R is positive with p below 0.05;
- its premium over plain breakouts is positive.

**A system to build on** is a finalist that passes and also passes this
account test on the held-out period:
- **Rules.** The Elliott study's (`../elliott/portfolio.py`): $100,000, 0.5%
  of equity risked per trade, at most 10% of equity in one position, gross
  exposure at most 100%. Simultaneous entries are taken in random order;
  the median of 10 orders is used.
- **The bar.** It beats SPY with dividends over the same dates on the
  three-part bar: a higher CAGR, a Sharpe ratio at least as high, and a
  worst drawdown no deeper.

**No finalist means the answer is no.** The held-out years are still scored
for every setup, for transparency.

## Calibration (before any real-data run)

**The data.**
- Path-consistent random walks (the Elliott study's `walks.py`), with no
  drift:
  - daily: 300 symbols x 2,700 bars, at 2% a bar;
  - weekly: 300 x 1,800 bars, at 4.5% a bar;
  - monthly: 300 x 480 bars, at 9% a bar.
- Every walk is liquid.

**What is reported.**
- The number of patterns.
- The mean edge over twins and the premium over plain breakouts, with
  their intervals.
- The share of 20 seeds in which a setup's edge has p < 0.05.

**The bars to clear.**
- No edge or premium should differ from zero by more than 0.05 R.
- No setup should show p < 0.05 in more than 3 of 20 seeds.
- If one does, the scoring is fixed and calibration is rerun before any
  real data is read.
- The results are committed before the first real run.

## Exploratory (labelled as such)

- **X1 Against the pattern.**
  - AT down-breaks: a close below the lows' line less tau, short.
  - DT up-breaks: a close above the highs' line plus tau, long.
- **X2 The ladder.** Two-touch levels (H2), plain N-bar breakouts on their
  own, and 52-week and all-time-high breakouts, each against twins.
- **X3 Other exits.**
  - Bulkowski's: exit at the close 3 bars after entry.
  - No target (stop and time exit only).
  - Event-study returns against twins at 5, 21 and 63 bars daily; 4, 13 and
    26 weekly; 3, 6 and 12 monthly.
- **X4 Volume.**
  - Breakout-bar volume at least 1.5x its 50-bar average.
  - Volume falling through the pattern.
- **X5 A 3% breakout filter**, as in the rectangle study.
- **X6 Pivot length** k = 3 and 10 on daily bars.
- **X7 Weekly and monthly bars on the 26 ETFs and the S&P 500 index.**
- **X8 Results by decade.**
- **X9 Breakout direction against simulated prices.**
  - Does an ascending triangle break up more often than the same detector
    finds on stationary-bootstrap shuffles of each stock's returns?
  - Bulkowski's 63% must be compared with the shuffles, not with 50%.
- **X10 The account test** for every confirmatory setup held out, against
  SPY.

## Verification

- Unit tests on synthetic series with known patterns, and a look-ahead test:
  cutting the data at random bars must not change any earlier signal.
- Two independent reimplementations, written from this file without seeing
  the code or its results, must reproduce the detections and the
  in-sample scores.
- An adversarial review of the code, the statistics and the claims.

## Files

- `PROTOCOL.md`: this file.
- `research/`: the source notes.
- `data.py`: loaders, cleaning, liquidity, periods.
- `pivots.py`: fractal pivots.
- `detect.py`: the patterns.
- `controls.py`: matched breakouts.
- `run.py`: one dataset and period.
- `select_finalists.py`: the decisions.
- `calibration/`: random-walk checks.
- `tests/`: unit tests.
- `results/`: every output.
