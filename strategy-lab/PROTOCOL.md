# Strategy lab: research protocol

Written and committed before any candidate strategy has been run. The commit
that adds this file is the pre-registration. Anything run later that this file
does not describe is exploratory and is labelled as such.

## Question

Is there a rule-based, fully automatable way to hold the S&P 500 that would
have beaten buying and holding SPY (dividends reinvested) after costs, at no
more than 2x leverage, on data it was not chosen on?

The rectangle-screener backtest is the starting point. Its 3% breakouts did no
better than random entries on the same days, and nearly all the portfolio's
profit came from being in the market at all. So this lab doesn't try to pick
stocks. It only varies how much S&P 500 exposure to hold, from 0x to 2x, using
published rules with their published parameters.

## Data

Yahoo Finance daily history in `data/yahoo/`, downloaded by `fetch_history.py`
(see the workflow) on 2026-10-18. Checks made before writing this file:

- SPY total return rebuilt from split-adjusted closes plus cash dividends
  matches Yahoo's adjusted close (cumulative ratio 1.0007 over 1993-2026). Its
  CAGR is 0.12 pp a year below `^SP500TR`, about SPY's expense ratio.
- Robinhood's split-adjusted closes match Yahoo's on the median day. Where they
  differ by more than 1% (2000, 2005-06, 2008-09), Yahoo agrees with the index
  and Robinhood is off by a session. Robinhood's dividend-adjusted daily bars
  subtract dividends in dollars, run negative for SSO, UPRO, QLD and XLU, and
  have missing and backwards adjustments before about 2013. They are not used.
- VFINX before 1988 is missing its capital-gain distributions (TR CAGR 11.9%
  for 1980-87 against about 16% for the index), so it is not used.
- BIL's total return runs 0.09 pp a year below the 13-week T-bill rate
  (`^IRX`) accrued daily, about its expense ratio.

Series used:

| series | source |
| --- | --- |
| S&P 500 signal | `^GSPC` close (price index) |
| S&P 1x return | SPY total return from 1993-01-29; before that `^SP500TR` less 0.0945% a year |
| S&P 2x return | SSO total return from 2006-06-21; before that simulated (below) |
| cash return | BIL total return from 2007-05-31; before that `^IRX` (previous close) accrued over calendar days / 365, less 0.10% a year |

Simulated 2x before SSO existed, for each session:
`2 * r_1x - r_cash - c / 252`. `c` is one constant, covering the expense
ratio and swap financing above the cash rate. It is set so the simulation's
cumulative return equals SSO's over 2006-06-22 to 2015-12-31, in-sample only.
Tracking error and CAGR gap against real SSO are reported for 2006-2015 and,
as a check, for 2016-2026. Real SSO is what the strategies hold from
2006-06-21 on.

## Periods

- **In-sample: 1988-01-04 to 2015-12-31.** This is the only period used to
  choose. It is the whole span of `^SP500TR`.
- **Held out: 2016-01-04 to 2026-10-16.** The finalist is scored on it once.
  It is a pass/fail test, not a choice between candidates.
- **Stress test: 1962-01-02 to 1987-12-31.** Reported, not part of the pass
  bar. S&P 1x is `^GSPC` price return plus 3.6% a year accrued daily (the
  index's 1988 dividend yield, the first year the total-return index gives).
  2x is simulated with the calibrated `c`, and cash is `^IRX`. It covers
  1973-74 and the 1987 crash, which the in-sample period misses.

A caveat that pre-registration can't remove: the researcher knows in broad
strokes how markets went in 2016-2026. Keeping to rules and parameters
published by others, mostly before 2016, limits how far that knowledge could
have shaped the candidate list. It doesn't eliminate it. The only fully blind
test is forward trading from the date of this commit.

## Execution and costs (all candidates)

- **Timing.** A signal computed from session t's close is traded at session
  t+1's close. The new position earns its first return on session t+2. This is
  a one-session delay, and it matches the live plan: the order is placed late
  in the session after the signal.
- **Instruments.** For a target exposure e, the portfolio is:
  - e = 0: 100% cash (BIL);
  - 0 < e <= 1: e in SPY and 1 - e in cash;
  - 1 < e <= 2: e - 1 in SSO and 2 - e in SPY.

  Fractional shares are allowed.
- **Costs.** 0.05% of the value traded, on each side of every trade, covering
  spread and slippage. Commissions are $0. Buying the initial position is
  charged to every series, SPY buy-and-hold included.
- **Rebalancing.** Rules with continuous exposure trade only when the target
  is more than 0.10 away from the current exposure. A move to or from 0 is
  always traded.

## Candidates (fixed before testing)

| id | rule | source |
| --- | --- | --- |
| C1 | `^GSPC` close above its 200-session simple moving average: 1x; else cash. Checked daily. | Siegel, *Stocks for the Long Run* (1994); Faber (2007) |
| C2 | Same signal as C1; 2x when above, cash when below. | Gayed & Bilello, "Leverage for the Long Run" (2016) |
| C3 | Month-end `^GSPC` close above the average of the last 10 month-end closes: 2x for the next month; else cash. | Faber, "A Quantitative Approach to Tactical Asset Allocation" (2007), with C2's 2x |
| C4 | Exposure = min(2, 15% / sigma). Sigma is the annualized EWMA volatility of `^GSPC` daily returns, lambda 0.94. | S&P 500 Daily Risk Control 15% index method (RiskMetrics lambda); Moreira & Muir (2017) |
| C5 | C1's signal times C4's exposure: min(2, 15% / sigma) when above the 200-session average, cash when below. | the two combined |

Reference rows (not candidates): SPY buy-and-hold, SSO buy-and-hold (2x
constant), 1.5x constant.

Sigma is seeded from the first 21 sessions of `^GSPC` returns in 1961 and run
forward. Each EWMA step is
`var_t = 0.94 * var_{t-1} + 0.06 * r_t^2`, and `sigma = sqrt(252 * var)`.

## Metrics

Computed on daily equity after costs, from the close before the period's first
session to its last close.

- CAGR: (end / start) ^ (365.25 / calendar days) - 1.
- Sharpe: mean / std of daily returns in excess of the cash series, times
  sqrt(252).
- Max drawdown: on daily closes.
- Also reported: volatility, worst calendar year, longest time under water,
  average exposure, time in market, trades per year.

## Pass bar

A strategy passes a period if it beats SPY buy-and-hold over that period on
all three of these:

1. higher CAGR;
2. Sharpe at least as high;
3. max drawdown no deeper.

## Choosing the finalist

1. Score C1-C5 on the in-sample period.
2. The finalist is the candidate with the highest in-sample CAGR among those
   that pass in-sample. If none passes, the lab stops and reports that.
3. In-sample robustness checks on the finalist are reported as warnings. They
   don't change the pick:
   - its parameters moved about 25% either way (moving average 150 / 250
     sessions; 8 / 12 months; volatility target 12% / 18%; lambda 0.97);
   - execution at the signal close (no delay);
   - execution at the next open, 2006-07 to 2015, where SPY, SSO and BIL
     opens exist;
   - costs doubled to 0.10% a side;
   - each decade on its own.
4. Random-timing null: the finalist's daily exposure series is shuffled in
   blocks of 63 sessions, 1,000 times, and run with the same costs. Its
   percentile for CAGR and Sharpe is reported in-sample and held out. This
   asks whether the timing matters or only the average exposure.

## The held-out test

- Score the finalist on 2016-01-04 to 2026-10-16, starting from the position
  its rules hold at the 2015-12-31 close.
- Pass/fail is the three-part bar above against SPY buy-and-hold over the
  same dates.
- Also reported:
  - a 90% interval for the yearly log-return difference against SPY
    (circular block bootstrap, 63-session blocks, 10,000 draws);
  - the random-timing null.
- All candidates' held-out scores are shown for transparency. They don't
  change the decision, and a candidate other than the finalist is never
  promoted on its held-out score.
- An independent re-implementation, written from this file and the code's
  docstrings by an agent that hasn't seen the results, must reproduce the
  finalist's held-out CAGR within 0.1 pp and its max drawdown within 0.5 pp.

**Outcomes:**

- **Pass:** the finalist is proposed for live trading, described in full.
  Nothing is traded until the account owner confirms:
  - the account;
  - the capital;
  - the instruments;
  - the limits and the kill switch.
- **Fail:** the lab reports that it did not find a system that clears the bar,
  and buy-and-hold SPY stays the recommendation. A new idea would need a new
  protocol and a forward test from its own commit date, because the held-out
  period would have been used.

## Taxes (reported, not part of the pass bar)

The pass bar is before tax, which is what an IRA would see. For a taxable
account, an after-tax estimate is reported for the finalist and SPY
buy-and-hold:

- **Rates:** 35% on short-term gains, ordinary distributions and interest
  (BIL, and SSO's distributions); 20% on long-term gains (held more than a
  year) and on SPY dividends. No state tax.
- **Lots:** first in, first out.
- **Netting:** gains and losses are netted within each tax year. A net loss
  carries forward. The $3,000 offset against ordinary income is ignored.
- **Paying the tax:** tax is paid out of the account at each year end, by
  trimming every lot pro rata without realizing anything.
- **The final value** is reported two ways: as held, and liquidated on the
  last day.
- **Not modelled:** wash sales, which defer losses rather than remove them.
