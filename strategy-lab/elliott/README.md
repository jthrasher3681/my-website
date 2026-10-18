# Elliott Wave study

Can the trade setups and price behaviour that Elliott Wave practitioners
publish be turned into rules a computer applies without hindsight? And do
those rules, or Frost & Prechter's Fibonacci expectations, hold up against
matched random data? `PROTOCOL.md` fixed the setups, data, periods, costs,
tests and pass bars before anything ran (commit 0fcc41b). Its amendments
come from calibrating on random walks before any real data was used
(commit b382ece).

## Result

**No system to build on.**
- None of the 28 confirmatory tests passed the pre-set bar in the choice
  period. The tests were 7 setups x long/short x daily stocks (2016-2021) and
  hourly bars (Nov 2023 - Sep 2025). The lowest corrected q was 0.23.
- So nothing was eligible for the held-out test, and under the protocol the
  answer is no.
- The held-out years were still scored for transparency, and nothing passed
  there either.

**Frost & Prechter's Fibonacci retracements don't show in prices.**

| claim | daily stocks, real | shuffled |
| --- | --- | --- |
| wave 2 ends within 3% (log) of 61.8% or 50% of wave 1 (2016-2021) | 9.49% | 9.48% |
| wave 4 ends within 3% of 38.2% of wave 3 (2016-2021) | 6.63% | 6.71% |

- **Limit orders at the Fibonacci levels.** They did no better than orders
  at the levels between them (12 contrasts, lowest corrected q 0.06), and
  no contrast replicated on held-out data.
- **Wave-4 pullbacks on chart prices (exploratory).** Measured on
  arithmetic prices, slightly more wave-4 pullbacks ended near 38.2%:
  +0.7 points in both periods. But in 2016-2021 the non-Fibonacci 43.7%
  level had a larger excess (+1.0 point).

**Other wave-shape claims.** Each is the share of real swing patterns that
fit the claim, compared with stationary-bootstrap shuffles.
- **Two survive the pre-registered test** (a bootstrap over symbols), both
  small:
  - wave 5 about equal to wave 1 when wave 3 extends: daily, +2.9 points
    held out;
  - a correction ending near the previous wave-4 low: hourly, +1.3 points.
- **Neither survives a calendar-clustered bootstrap.** An independent review
  pointed out that stocks move together on the same dates, so symbols are
  not independent. Resampling calendar months or weeks instead, neither
  claim is significant (corrected q 0.063 and 0.059).
- **The first claim is also fragile on its own terms.** Its pre-registered q
  of 0.048 passes on only about two thirds of bootstrap seeds.

**The one lead.** The oscillator wave-4 pullback (S3), bought on daily
stocks, beat its random twins by +0.067 R in 2016-2021 (q 0.31, not a
finalist) and +0.071 R in 2022-2026.
- **As the protocol's portfolio (exploratory),** 2022-2026: +0.5% a year
  with a 36% worst drop, against SPY's +11.8% and 24.5%.
- **Why it fails as an account.** Signals arrive in clusters. An account
  with room for about 11 positions takes the first signals of each cluster,
  and those were the weak ones.

## Verification

- **Re-implementations.** Two independent ones, written from `PROTOCOL.md`
  without seeing this code or its results, reproduce:
  - the 162,810 in-sample daily pivots exactly;
  - the behaviour shares exactly;
  - the S1, F2-618 and S3 trades to within about 0.01 R of edge. The trade
    counts differ by under 1%, from slot-timing readings.
- **Adversarial review.**
  - It re-simulated all in-sample trades.
  - It found no look-ahead in 240 random data cuts.
  - It confirmed the random-walk calibration, including on GARCH
    volatility, mixed volatility levels and drift.
- **Fixes from the review**, all rerun with no change to any conclusion:
  - S3's DMA exit needs a high strictly above P3;
  - a limit order no longer fills at the open on a bar that also breaches its
    cancel level;
  - a fill skipped by the minimum-risk rule holds its slot up to the fill
    bar;
  - twins are drawn without replacement;
  - moving averages are summed directly;
  - the exploratory portfolio marks each position separately;
  - the calendar-clustered behaviour inference was added;
  - the protocol's promised extras are now reported: the share of S1 fills
    at or beyond p1 (about 10%), Kennedy's conservative trigger and the
    p2-stop variants of S1, and arithmetic ratios for B1a / B1b.
- **Full-data reproduction.** Every held-out run reproduces its in-sample
  run's trades exactly.

## Files

- `PROTOCOL.md`: the pre-registration and its amendments.
- `waves.py`: pivots, the oscillator and exits.
- `setups.py`: the setups, baselines and controls.
- `execute.py`: fills, the slot rule, twins and statistics.
- `run.py`: one dataset and period.
- `select_finalists.py`: the decisions.
- `behavior.py`: the behaviour tests.
- `portfolio.py`: the account test.
- `histograms.py`: the report's ratio histograms.
- `calibration/`: random-walk checks.
- `tests/`: unit tests.
- `results/`: every output, JSON and text.

```sh
cd strategy-lab
python3 -m unittest elliott.tests.test_waves elliott.tests.test_setups
python3 -m elliott.run stocks_daily insample      # reads nothing after 2021-12-31
python3 -m elliott.run stocks_1h insample
python3 -m elliott.select_finalists insample
python3 -m elliott.behavior stocks_daily insample
```

The hourly bars are in `../data/yahoo_1h`, downloaded by
`.github/workflows/strategy-lab-intraday.yml`. The daily stock bars are the
rectangle screener's Robinhood history, cached by a scratch script, so
they are not in the repository.
