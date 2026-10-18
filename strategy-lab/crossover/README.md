# Moving-average crossover study

Do crossover rules beat buying and holding the same assets on years held
back from the choice? Is their timing better than random timing? And does
any of them beat buy-and-hold SPY? A crossover rule holds the asset while a
fast average is above a slow one, and cash otherwise. `PROTOCOL.md` fixed
the rules, data, periods, costs, tests and pass bars before anything ran
(commit 3e22908). The random-data calibration was committed before the
first real run (2c615bb).

## Result

**No system to build on.**
- **In-sample.** Of the 20 confirmatory tests (5 rules x 4 datasets), only
  the golden cross on the S&P 500 passed the three-part bar:

  | 1988-2015 | CAGR | Sharpe | max drawdown |
  | --- | --- | --- | --- |
  | golden cross (SMA 50/200) | 10.08% | 0.58 | -19.4% |
  | SPY buy-and-hold | 10.00% | 0.44 | -55.2% |

  It still was not a finalist. Its timing edge over random timing
  (p 0.019) did not survive the correction for 20 tests (q 0.38). At
  double costs it also fell 0.02 points short of SPY (9.985% a year).
- **So under the protocol the answer is no.** Nothing was eligible for the
  held-out test.
- **Held out (scored for transparency).** No rule passed on any dataset.
  The golden cross on the S&P 500 made 9.74% a year from 2016 to 2026,
  against SPY's 14.84%. Its drawdown was the same -33.7%, because the
  2020 crash was over before the averages crossed.
- **The one near-pass looks like volatility timing.**
  - **The setup.** The S&P 500 is more volatile after it falls. The review
    fitted that pattern to SPY's 1988-2015 returns (an asymmetric GARCH-t)
    on random data with no predictability at all.
  - **The result.** On that data the same test gave the golden cross
    p <= 0.019 in 8.5% of runs, and p < 0.05 in 15.5%.
  - **So** stepping aside after falls lowers risk, but it is no evidence
    that crossovers predict returns.

**The faster the rule, the worse.**
- **20/50, 12/26 MACD, 9/21 EMA.** These switch 6-12 times a year and lost
  to buy-and-hold by 4.6-6.4 points a year on the S&P 500 in-sample.
- **The MACD signal-line cross.** It switches about 21 times a year. It made
  1.2% a year on the S&P 500 in-sample, and 3.5-5.4% a year held out across
  the datasets.
- **Hourly bars.** The same rules switch 11-132 times a year. On hourly
  stocks they trailed buy-and-hold by 16-29 points a year in-sample.

**The rules cut drawdowns, and paid for it in return.** Across the 40
rule, dataset and period cases:
- **Time in the market.** The rules held the asset 50-82% of the time.
- **Drawdowns.** The worst drop was smaller than buy-and-hold's in 39 cases
  (the median was 57% of it). The exception is the golden cross on the
  S&P 500 held out: equal.
- **CAGR.** It was lower in 39 cases, by up to 29 points a year. The
  exception is the golden cross on the S&P 500 in-sample, by 0.08 points.
- **Sharpe ratio.** It was higher in only 4 cases, all in-sample, by 0.01
  to 0.13.

| dataset | period | buy-and-hold CAGR / Sharpe / max DD | best crossover by CAGR |
| --- | --- | --- | --- |
| S&P 500 | 1988-2015 | 10.00% / 0.44 / -55.2% | golden cross 10.08% / 0.58 / -19.4% |
| S&P 500 | 2016-2026 | 14.84% / 0.75 / -33.7% | 20/50 9.90% / 0.70 / -26.5% |
| stocks, equal weight | 2017-2021 | 16.43% / 0.76 / -41.0% | golden cross 8.91% / 0.64 / -29.0% |
| stocks, equal weight | 2022-2026 | 10.64% / 0.42 / -23.3% | golden cross 6.69% / 0.32 / -13.1% |
| 26 ETFs, equal weight | 1994-2015 | 9.50% / 0.49 / -40.0% | golden cross 7.65% / 0.53 / -22.7% |
| 26 ETFs, equal weight | 2016-2026 | 10.38% / 0.69 / -26.9% | golden cross 6.25% / 0.50 / -22.7% |
| hourly, equal weight | Jan 2024 - Sep 2025 | 35.91% / 1.49 / -20.8% | golden cross 19.91% / 1.51 / -8.7% |
| hourly, equal weight | Oct 2025 - Oct 2026 | 25.47% / 1.27 / -7.4% | golden cross 14.36% / 1.08 / -4.1% |

- **Stocks.** 1,357 different stocks were members in 2017-2021 (959 on an
  average day), and 1,816 in 2022-2026 (1,361 on an average day).
- **Hourly.** 316 symbols in-sample and 318 held out.

**Their timing is no better than random.**
- **The test.** Each rule's held exposures were shuffled in blocks (63 bars
  daily, 70 hourly), keeping its time in the market.
- **In-sample.** No rule's Sharpe ratio beat the shuffles after correction
  for 20 tests.
- **Held out.** No p-value was below 0.15.
- **A flaw in this test.** The review found that the pre-registered shuffle
  leaks a little of the future, which tilts it against the rules (see
  "Verification"). Rerun with a leak-free version, the conclusion stands.

## Exploratory (not tests)

- **Picking the best backtest (X3).**
  - **The grid.** 70 fast/slow pairs (SMA and EMA, fast 5-100, slow
    20-300) on the S&P 500.
  - **In-sample, 16 pairs beat SPY** on all three parts of the bar. CAGR
    was the hard part: all 70 had a smaller drawdown, and 44 a higher
    Sharpe. The best, EMA 50/250, made 10.67% with a -19.0% drawdown.
  - **Held out, none beat SPY** on CAGR or on Sharpe. EMA 50/250 made
    8.78% with a -33.9% drawdown.
  - **The order did not hold.**
    - In-sample and held-out Sharpe ratios had a rank correlation of
      -0.37. That is mainly because slow pairs did best in-sample and
      faster ones held out. CAGR ranks correlated at +0.11.
    - The pairs overlap heavily, so this is one change of regime, not 70
      separate results.
- **2x leverage (X1).**
  - **In-sample, two rules at 2x beat SPY on all three:** the golden cross
    (14.46%, Sharpe 0.54, -40.0%) and price above its 200-day average
    (11.53%, 0.45, -45.4%).
  - **Held out,** the golden cross at 2x made 13.78% with a -59.3%
    drawdown.
  - **Three 2x rules beat SPY's held-out CAGR,** but none beat its Sharpe
    (0.75):
    - **20/50** made 15.81%, after 4.1% a year in-sample.
    - **EMA 9/21** made 16.09%, and it alone also had a smaller drawdown
      (-32.8%). In-sample it had made 3.1% a year.
    - **Price above its 200-day average** made 17.01% with a deeper
      drawdown (-41.5%). This is the SPY lab's C2.
- **Long/short (X2).** Shorting when bearish was run on the S&P 500 and the
  ETFs: 20 cases.
  - It lost to buy-and-hold on CAGR (by 1.7 to 20 points a year) and on
    Sharpe in all 20.
  - It had a smaller or equal drawdown in 8.
  - It was modelled generously, with no borrowing fee.
- **1962-1987 (X4).** These years were not part of this study's choice.
  - **The slow rules did well.** The golden cross made 10.1% and price
    above its 200-day average 11.0%, against buy-and-hold's 8.7%, with
    smaller drawdowns. That was the best of the rules at 1x.
  - **But they are not independent of these years.** The 50/200 and 200-day
    defaults were made popular by studies of pre-1990 data, such as Brock,
    Lakonishok & LeBaron on the Dow, 1897-1986.
  - **The 1987 crash.** The golden cross was still long on 1987-10-19 and
    lost 20.5% that day (41% at 2x).
- **4-hour bars (X5)** behaved like hourly bars: every rule trailed
  buy-and-hold of the same symbols in both periods.
  - **Three beat SPY held out** on all three parts: the golden cross,
    20/50 and price above its 200-bar average.
  - **That comes from how the symbols were chosen** (below), not from the
    rules. Each still lost to holding its own symbols.
- **Price above its 200-day average (X6)** reproduces the SPY lab's C1
  exactly (8.24% in-sample, 10.48% held out).

## Caveats

- **The stock universes were chosen on 2026 values.**
  - **Daily stocks** are the rectangle screener's universe as of today:
    market cap at least $2B, price at least $5, and at least $20M a day
    traded.
  - **Hourly symbols** are 30 ETFs and the most traded US stocks as of
    2026.
  - **That favours buy-and-hold far more than survivorship alone.** In the
    review's simulation, keeping the top 40% of random-walk stocks by
    final value widened the buy-and-hold-minus-rule gap by 3.5-4.5 points
    a year. It left the random-timing test unchanged.
  - **So the stock and hourly return gaps are not reliable evidence either
    way.** The in-sample gaps (7.5-8.4 points daily, 16-29 hourly) are
    larger than that. The S&P 500 and ETF results are not affected.
- **Daily stocks and hourly bars are price only.** Both portfolios miss
  dividends, but buy-and-hold misses more. That favours the rules by about
  0.4-0.8% a year. It also biases the SPY comparisons (which include SPY's
  dividends) against them on those datasets.
- **Rebalancing costs are ignored.** The equal-weight benchmark turns over
  about 1.7-1.9 times as much as the rule portfolios, so leaving the cost
  out favours it by about 0.1-0.3% a year.
- **The SPY benchmark.** Its held-out CAGR here, 14.84%, pays for an opening
  purchase at the end of 2015. The SPY lab reported 14.85% from a
  continuous run.
- **The daily stock cache's spike filter** compares each close with the next
  one. It removed 158 of 2.33 million in-sample bars, mostly bad prints.

## Verification

- **Two independent reimplementations**, written from `PROTOCOL.md`
  without seeing this code or its results, found no finalist either.
  - **They agree on every rule, dataset and period.** CAGR, Sharpe,
    drawdown and the bar match to 0.01 points on the S&P 500, stocks and
    ETFs. On hourly bars they match to 0.05 points, since the window
    starts a few bars apart.
  - **Their random-timing p-values** agree within Monte Carlo noise.
  - **Time in the market.** Both average the portfolio's exposure over
    bars. This code had averaged over asset-bars, which weighs late ETF
    years more. It now does as they do: R1 on ETFs in-sample is 69%, not
    65%.
- **Adversarial review of the code.**
  - **No look-ahead.** Every row after the in-sample end was corrupted in
    copies of the data. The in-sample results came out identical for the
    S&P 500, ETFs and stocks. Panels cut at random dates kept every earlier
    exposure.
  - **Sleeves, costs, lags, dividends and the hourly marks** were checked
    by hand from raw closes.
  - **The S&P 500 was re-simulated without the lab's code**, and matched.
- **Adversarial review of the statistics.** It re-ran the nulls, fitted
  volatility models to SPY, and rechecked every claim here.
- **What the reviews found, and what changed.** No conclusion changed.
  1. **The random-timing shuffle leaks a little of the future.**
     - **How.** A block moved earlier can put an exposure in front of
        returns its moving averages already contain. The short final block
        also shifts every later block by a few bars, so even blocks that
        land in their own slot carry some of this.
     - **The effect.** The shuffles gain about 1-1.5% a year of return,
        which tilts the test against the rules. It is worst on short
        windows and panels, where it gave random walks an edge of about
        -0.15. The calibration only limited false positives, so it missed
        a bias in this direction.
     - **The leak-free version.** Every timing test was rerun with each
        exposure series shifted in a circle by at least 260 bars, one shift
        for all assets (`Panel.shift_sharpes`, reported as `null_shift`).
        On random walks its bias is about zero. But it is a little generous
        to slow rules on short panels: the golden cross is flagged in 12%
        of random panel runs at the 5% level
        (`calibration/results_shift.txt`).
     - **The result is the same.** The golden cross on the S&P 500 has
        p 0.010 and q 0.20 across the 20 tests, and there is no finalist.
        No other in-sample p is below 0.11, and no held-out p is below
        0.17.
     - **The SPY lab used the same shuffle.** For its finalist C3, the
        leak-free check is stronger: 96% of shifts beat C3's held-out CAGR,
        against the 91% reported (`calibration/spylab_c3_shift.py`).
  2. **The in-sample hourly universe read later bars.** The Elliott
     study's data rules (gaps over 3x, under 1,000 bars) were applied to
     whole files. They now use only the bars a run may read: 316 symbols
     in-sample instead of 317. R1's CAGR is 19.91% instead of 19.98%.
  3. **Double costs doubled the opening purchase too** on the S&P 500. Only
     switches are doubled now: 9.985% instead of 9.983%, still short of
     SPY's 10.002%.
  4. **Wording.** Fixed where the review found claims too broad: the grid,
     the 2x and long/short summaries, the 1962-87 test, and the caveats
     above.
- **Unit tests.** 17 tests cover the averages, the lag, costs, membership,
  hourly marks and both nulls.

## Files

- `PROTOCOL.md`: the pre-registration.
- `signals.py`: the averages and rules.
- `data.py`: datasets, periods, costs.
- `portfolio.py`: sleeves, portfolios, both random-timing nulls.
- `run.py`: one dataset and period.
- `select_finalists.py`: the decisions, plus the shift-null robustness.
- `explore.py`: X1-X4.
- `calibration/`:
  - `walks.py` and `results.txt`: random-walk checks of the pre-registered
    null;
  - `results_shift.*`: the same checks of the shift null;
  - `spylab_c3_shift.py`: the SPY lab check.
- `tests/`: unit tests.
- `results/`: every output, JSON and text, and the daily equity curves.

```sh
cd strategy-lab
python3 -m unittest crossover.tests.test_crossover
python3 -m crossover.calibration.walks                # --null shift for the leak-free null
python3 -m crossover.run sp500 insample                # reads nothing after 2015-12-31
python3 -m crossover.select_finalists insample
python3 -m crossover.run sp500 heldout
python3 -m crossover.select_finalists heldout
python3 -m crossover.explore
```

The daily stock bars are the Elliott study's cache of the rectangle
screener's Robinhood history (`../elliott/data.py`), so they are not in the
repository. The hourly bars are in `../data/yahoo_1h`.
