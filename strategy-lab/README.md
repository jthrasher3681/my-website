# Strategy lab

This lab asks whether a rule that sets how much S&P 500 exposure to hold, from
0x to 2x, would have beaten buying and holding SPY after costs, on data the
rule wasn't chosen on. It follows on from the rectangle-screener backtest,
whose breakout signals added nothing beyond being in the market.

`PROTOCOL.md` fixed the candidates, periods, costs, metrics and pass bar. It
was committed before any candidate was run, in commit 2f699d7.

## Result

No candidate cleared the bar on the held-out years, 2016-01-04 to 2026-10-16.
Buy-and-hold SPY stays the recommendation. Nothing is traded.

| | 1988-2015 CAGR | Sharpe | max drawdown | 2016-2026 CAGR | Sharpe | max drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| SPY buy-and-hold | 10.00% | 0.44 | -55.2% | 14.85% | 0.75 | -33.7% |
| C3 10-month average, 2x (finalist) | 14.28% | 0.54 | -41.0% | 12.80% | 0.53 | -48.8% |

- **In-sample (1988-2015):** C2 (200-day average, 2x) and C3 passed. C3 had
  the higher CAGR, so it was the finalist.
- **Held out (2016-2026):** C3 failed all three parts of the bar, and no
  other candidate passed.
- **Random timing:** with its exposure shuffled at random, 91% of shuffles
  beat its held-out CAGR.
- **Stress test (1962-87):** C3 was 2x long through the 1987 crash and lost
  41% on 1987-10-19.

`results/` has every number: `insample.json` / `.txt`, `heldout.json` /
`.txt`, and the daily equity curves.

## Verification

- **Re-implementations:** two independent ones, written from `PROTOCOL.md`
  without seeing this code or its results, reproduce every candidate's CAGR,
  Sharpe and max drawdown in both periods, and C3's held-out trade dates.
- **Code review:** an adversarial review re-ran the in-sample script on
  copies of the data with every row after 2015-12-31 corrupted. The output
  was byte-identical, so the in-sample run can't see held-out data. The
  review also rebuilt the tax estimate independently.
- **Fixes from the review**, none of which changes the pass set, the
  finalist or a held-out result:
  - the opening trade's cost now reaches the metrics (-0.002 pp of in-sample
    CAGR);
  - the random-timing null replays exposures without the band;
  - "more than a year" for long-term gains follows the anniversary rule;
  - month-end detection knows 2015-12-31 closes December in the in-sample
    data;
  - the 2x tracking check counts years from the right close.

## Departures from the protocol

- **In-sample start:** the in-sample equity starts at the 1988-01-04 close,
  not the 1987-12-31 close. `^SP500TR`'s first value is 1988-01-04, so there
  is no 1x return for that session. Approximating it with `^GSPC` changes no
  pass or fail.
- **Next-open check:** it runs from 2007-06 rather than 2006-07, because
  BIL's opens start on 2007-05-30.

## Running it

```sh
cd strategy-lab
python3 -m unittest discover -s tests -t .
python3 run_insample.py     # reads nothing after 2015-12-31
python3 run_heldout.py
```

`data/yahoo/` holds the Yahoo Finance daily history. It was downloaded on
2026-10-18 by `.github/workflows/strategy-lab-data.yml`, which runs
`fetch_history.py`.
