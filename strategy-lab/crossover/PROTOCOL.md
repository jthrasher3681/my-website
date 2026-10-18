# Moving-average crossover study: research protocol

This file is written and committed before any crossover rule has been run on
prices. Its commit is the pre-registration, and anything run later that it
does not describe is labelled exploratory.

## Question

Do moving-average crossover rules (be in the market while a fast average is
above a slow one, in cash otherwise) beat buying and holding the same assets
on data held back from the choice? Is their timing better than random timing
with the same time in the market? And does any of them make a system that
beats buy-and-hold SPY?

**Prior evidence.**
- Brock, Lakonishok & LeBaron (1992) found moving-average rules predictive
  on the Dow, 1897-1986.
- Sullivan, Timmermann & White (1999) corrected for the many rules tried
  (White's reality check). The best rule did not hold up out of sample after
  1986. Bajgrowicz & Scaillet (2012) found the same with false-discovery
  control and costs.
- Faber (2007) and Zakamulin (2014-2017) report that market timing with
  moving averages mostly reduces drawdowns. Its long-run edge comes from a
  few crashes and is uneven across decades.
- Trend following across many futures markets (Hurst, Ooi & Pedersen) has a
  longer record, but it uses leverage, shorts and dozens of markets, which
  is not what is tested here.
- This lab's SPY study (`../PROTOCOL.md`) tested price above its 200-day
  average (1x and 2x) and its 10-month average (2x). None passed the
  three-part bar on 2016-2026.

## Rules

Each rule gives a signal s_t at the close of bar t: 1 (bullish, hold the
asset) or 0 (cash). An equal value counts as 0.

| rule | name | bullish when |
| --- | --- | --- |
| R1 | golden cross | SMA(50) > SMA(200) |
| R2 | 20/50 | SMA(20) > SMA(50) |
| R3 | MACD line above zero | EMA(12) > EMA(26) |
| R4 | MACD signal cross | MACD line (EMA12 - EMA26) > its EMA(9) |
| R5 | 9/21 EMA | EMA(9) > EMA(21) |

- **Averages.** SMA(n) is the mean of the last n closes, including bar t.
  EMA(n) is the recursive average with weight 2 / (n + 1), started at the
  series' first close.
- **Prices.** Averages use closes as a trader sees them: split-adjusted
  closes for stocks and ETFs, `^GSPC` for the S&P 500. Returns use total
  return where the data have dividends (below).
- **Warm-up.** An asset's signals count from its 260th bar.
- **Lengths are the published defaults.** They are not tuned. Parameters
  near them are exploratory (below).

## Execution and costs

- **Timing.** A signal at the close of bar t is traded at the close of bar
  t + 1. So the exposure held over bar j (from close j - 1 to close j) is
  h_j = s_{j-2}.
- **One asset is one sleeve.** Its return over bar j is
  h_j * r_j + (1 - h_j) * c_j - k * |h_{j+1} - h_j|, where r is the asset's
  return, c the cash return and k the cost of a switch.
- **A switch costs k = 0.10% of the sleeve's value.** Daily, that is a sale
  and a purchase at 0.05% each (asset to T-bills or back), as in the SPY
  lab. Hourly, it is one trade at the intraday rate of 0.10%; cash is not
  traded.
- **Cash** earns the lab's cash series (`lab.data.cash_returns`): BIL total
  return from 2007-05-30; before that the 13-week T-bill rate less 0.10% a
  year. Hourly, each day's cash return is spread evenly over that day's
  bars.
- **Portfolios.** A dataset with many assets is an equal-weight portfolio of
  sleeves, rebalanced to equal weight at every close. Its return over bar j
  is the mean of the member sleeves' returns. The cost of that rebalancing
  is ignored, for the crossover portfolio and its buy-and-hold benchmark
  alike.
- **Membership.** An asset is a member over bar j if it has bars j - 1 and
  j, its signal at bar j - 2 counts (warm-up), and, for daily stocks, it
  passed the screener's liquidity rule at the close of bar j - 2 (median
  dollar volume over 50 sessions of at least $20M). An asset missing a bar
  is not a member over it, and its next return spans the gap.
- **The S&P 500** dataset is one asset run through the SPY lab's engine
  (`lab.engine.run`, SPY and BIL), which charges the same costs.

## Data and periods

| dataset | assets | benchmark | in-sample (choice) | held out (scored once) |
| --- | --- | --- | --- | --- |
| `sp500` | the S&P 500: signals on `^GSPC`, returns of SPY (`^SP500TR` before 1993) | SPY buy-and-hold | 1988-01-05 to 2015-12-31 | 2016-01-04 to 2026-10-16 |
| `stocks_daily` | 1,897 stocks of the screener universe, Robinhood daily bars | the same stocks, equal weight, held | 2016-01-04 to 2021-12-31 | 2022-01-03 to 2026-10-16 |
| `etf_daily` | 26 ETFs (US and world stocks, sectors, REITs, gold, commodities, Treasuries, corporate bonds, TIPS), Yahoo daily, total return | the same ETFs, equal weight, held | from the first member (SPY, early 1994) to 2015-12-31 | 2016-01-04 to 2026-10-16 |
| `stocks_1h` | 318 symbols, Yahoo hourly regular-session bars, as in the Elliott study | the same symbols, equal weight, held | from the first member (early 2024) to 2025-09-30 | 2025-10-01 to 2026-10-16 |

- **In-sample runs read nothing after the in-sample end.** Held-out runs read
  the earlier bars too, so averages and the opening exposure are warmed up.
- **Daily stocks are price only.** The Robinhood bars are split-adjusted but
  carry no dividends. Both portfolios miss dividends, but buy-and-hold
  misses more of them, so this favours the crossover by about the dividend
  yield times the share of time in cash (roughly 0.5% a year).
- **Daily stocks are survivors.** The universe is the stocks listed today.
  Survivors went up, and the crashes of stocks that delisted are missing.
  This favours buy-and-hold over timing. So this dataset's comparison with
  buy-and-hold is the least trustworthy of the four. Its random-timing test
  (below) is not affected, since both sides hold the same stocks.
- **Hourly symbols** follow the Elliott study's data rules (a symbol is
  dropped for an overnight gap over a factor of 3, or fewer than 1,000
  bars).

## Measures

All measures use daily marks: hourly portfolios are marked at each day's
last bar.

- **CAGR**, **Sharpe ratio** (daily return less cash, annualized by the
  square root of 252), **maximum drawdown**, volatility, the worst calendar
  year, time in the market (the mean exposure), and switches per asset per
  year.
- **The three-part bar** (as in the SPY lab): a higher CAGR, a Sharpe ratio
  at least as high, and a maximum drawdown no deeper than the benchmark's,
  over the same window and net of costs.
- **SPY buy-and-hold** over the same window is reported for every dataset.

## The random-timing test

Does the crossover's timing beat random timing with the same time in the
market and the same holding patterns?

- **The null.** Each draw cuts the period's bars into consecutive blocks of
  63 bars (daily) or 70 bars (hourly, about ten sessions) and puts the
  blocks in a random order. Each held exposure moves with its bar:
  h*_j = h_{pi(j)}.
  - One order is used for all assets of a portfolio, so the assets'
    exposures keep moving together, as the crossover's do (in a crash most
    rules exit at once).
  - If an asset is a member over bar j but has no counted exposure at
    pi(j), it gets its mean exposure over the period.
  - Returns stay where they are.
- **The statistic** is the portfolio's Sharpe ratio before switching costs,
  for the rule and every draw alike. Costs are left out because the block
  edges add switches the rule itself never makes. Costs are judged by the
  three-part bar instead.
- **p** = (1 + the number of draws with a Sharpe at least the rule's) /
  1,001, from 1,000 draws. The **timing edge** is the rule's Sharpe less the
  draws' mean.

## Calibration (before any real-data run)

The test is checked on random data where crossovers can have no timing
edge. The results are committed before the first real run.

- **Data.** Daily random walks with the S&P's drift and volatility, as:
  - (i) independent normal returns;
  - (ii) GARCH(1,1) volatility with persistence 0.98;
  - (iii) a 200-asset, one-factor panel with a GARCH common factor;
  - (iv) hourly bars (7 a day) of a GARCH walk.
- **Check.** In 200 replications of each, with 200 null draws each, the
  share of replications with p < 0.05 should be at most 8% for every rule.
- **Pre-set fix.** If any rule exceeds 8% in (ii)-(iv), the blocks become
  252 bars daily and 280 hourly for all rules, and calibration is rerun.
- **Asymmetric GARCH (GJR) is reported, not a gate.** There, volatility rises
  after drops, so a rule that exits after drops really does avoid risk.

## Choosing finalists (in-sample)

The confirmatory family is 5 rules x 4 datasets = 20 tests. A rule and
dataset is a finalist if all of these hold in-sample:

1. it passes the three-part bar against its benchmark;
2. its timing edge is positive with a Benjamini-Hochberg q below 0.05 across
   the 20 tests;
3. it still passes the three-part bar at double costs (0.20% a switch);
4. its timing edge is positive in each half of the in-sample period (each
   half with its own 1,000 draws). The halves split at 2002-01-01 (`sp500`),
   2019-07-01 (`stocks_daily`), 2005-01-01 (`etf_daily`) and 2024-11-01
   (`stocks_1h`).

## Held-out test (scored once)

- **A finalist passes** if, on its held-out period:
  - it passes the three-part bar against its benchmark, and
  - its timing edge is positive with a Holm-adjusted p below 0.05 across the
    finalists.
- **A system to build on** passes, and it also passes the three-part bar
  against SPY buy-and-hold over the same window (for `sp500` that is the
  same test).
- **No finalist means the answer is no.** The held-out years are still
  scored for every rule, for transparency, and labelled as such.

## Exploratory (labelled as such)

- **X1** each rule at 2x on `sp500` (SSO when bullish, as in the SPY lab).
- **X2** long/short: -1 when bearish (h r + (1 - h) c, no borrowing fee) on
  `sp500` and `etf_daily`.
- **X3** a parameter grid on `sp500` in-sample: SMA and EMA pairs with fast
  lengths 5-100 and slow lengths 20-300. The best in-sample pair is scored
  held out, to show what picking the best backtest does.
- **X4** the 1962-1987 stress test on `^GSPC` (`lab.data.stress_returns`).
- **X5** 4-hour bars (two a day, as in the Elliott study).
- **X6** price above its 200-bar SMA (the SPY lab's C1) on every dataset, as
  a reference.
- **X7** calendar-year returns and the equity curves for the report.

## Verification

- Unit tests of the averages, the lag, the costs, the membership rule and
  the null.
- Two independent reimplementations, written from this file without seeing
  the code or its results, must reproduce the in-sample statistics.
- An adversarial review looks for look-ahead (cutting the data at random
  dates must not change earlier exposures), cost and lag errors, and holes
  in the calibration.

## Files

- `PROTOCOL.md`: this pre-registration.
- `signals.py`: the averages and rules.
- `portfolio.py`: sleeves, portfolios, the null.
- `run.py`: one dataset and period.
- `select_finalists.py`: the decisions.
- `calibration/`: the random-data checks.
- `tests/`: unit tests.
- `results/`: every output.
