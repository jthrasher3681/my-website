# Design memo: a pre-registered backtest of ascending-triangle, descending-triangle and horizontal support/resistance breakouts in US stocks, on daily, weekly and monthly bars

**How numbers are tagged.** Every number in this memo carries one tag.
- **[E]**: comes from a search-tool excerpt of the cited page. The page was never opened in full, because fetches were blocked. Treat it as provisional.
- **[S]**: comes from a secondary source or from recollection. It is unverified.
- **[code]**: read in full from an open-source file. These are GitHub mirrors and may differ from the live scripts.
- **[C]**: chosen here. No published number exists. It is fixed in advance and must not be tuned.
- **[D]**: my own arithmetic.

No number was checked against a full primary text. The key tables (Bulkowski, Lo-Mamaysky-Wang (LMW), Brock-Lakonishok-LeBaron (BLL), George-Hwang, Huddart-Lang-Yetman) need checking before registration.

---

## 1. Identification rules

### 1.0 Rules shared by all patterns

- **Prices.** Pattern shapes are measured on split-adjusted OHLCV that is not adjusted for dividends. Performance is measured on total returns, including delisting returns. [C]
- **Bars.** Weekly and monthly bars are built only from completed periods. Signals are read only at the close of a completed bar. The stock-pattern loader rounds end dates forward to week-end or month-end, which leaks future bars. Do not copy it. [code]
- **Pivots (turning points).** A pivot high at bar j requires:
  - H[j] ≥ every high in the k bars before it, and
  - H[j] > every high in the k bars after it.

  The pivot only becomes known at the close of bar j+k. Store both the pivot's own bar and the bar on which it was confirmed [code: neurotrader888, TradingView `ta.pivothigh`].
  - k = 5 daily, 3 weekly, 2 monthly [C]. Defaults in open code range from 3 to 15 [code].
  - Daily sensitivity runs use k = 3 and k = 10.
  - The tie rule (≥ on the left, > on the right) [C] matters because flat tops often contain exactly equal highs.
- **Alternation.** Between two touches of the same line there must be a pivot on the opposite line [C]. This puts Bulkowski's requirement that price "crosses the pattern from side to side" [E] into a rule.
- **Flatness tolerance τ.** The highest touch minus the lowest touch on the flat line must be ≤ 1.0 × the median bar range (high minus low) over the pattern, on that timeframe [C].
  - The precedent is the stock-pattern code, which uses the median bar range [code].
  - Bulkowski, Edwards & Magee, Murphy and StockCharts give no number. They use words like "practically horizontal".
  - The only codified tolerance is LMW's rectangle band: each extreme within 0.75% of its group mean [E]. Use it as a daily sensitivity run only. It was set for 38-day daily windows and is too tight for weekly or monthly ranges.
- **Containment.** No close beyond either boundary (flat line ± τ) between the first touch and the bar before the breakout [code: stock-pattern]. Wicks may cross.
- **Duration, from first touch to breakout bar.** Daily 15–250 bars, weekly 8–156, monthly 8–120 [C]. Duration is recorded as a covariate.
  - Published anchors: Bierovic ≥15 bars [S]; LMW window of 38 days [E], split as 35 + 3 [S]; Brandt prefers 8–16 weeks, or 10–26 weeks for horizontal patterns [E]; O'Neil flat base ≥5 weeks, cup ≥7 weeks [S].
  - **No duration for triangles on weekly or monthly bars has been published anywhere.**
  - Brandt's 8–16 weeks is a pre-registered weekly subgroup.
- **Breakout.** The first completed-bar close beyond the flat line. Bulkowski defines the breakout as a close outside the line [E].
  - Sensitivity run: the Edwards & Magee filter, a close ≥3% beyond the line [S].
  - Volume is a subgroup, not part of the primary definition. Thresholds: above the 30-day average (Bulkowski) [E]; 40–50% above the 50-day average (O'Neil) [S]; an increase of at least 150% (O'Neil Global Advisors) [E].
- **One signal per level.** A level is retired after its first breakout in either direction, with no re-entry.
  - Duplicates are removed on (ticker, level, breakout bar) within each timeframe.
  - If several sets of touches qualify, keep the one with the earliest first touch [C].

### 1.1 Ascending triangle

- **Flat top.** At least 2 pivot highs within τ. The level U is the highest of them [C].
- **Rising lows.** At least 2 pivot lows, each higher than the last (StockCharts, Bulkowski) [E]. The lows must fail the flatness test; otherwise the pattern is a rectangle [C]. No minimum slope has been published anywhere.
- **Touches.** At least 5 in total and at least 2 per line, i.e. 3+2 either way (Bulkowski) [E].
  - Sensitivity run: 2+2 (Murphy's 4 reversal points) [S].
  - Bulkowski's own pages disagree (3+2 versus 2+2) [E].
- **Apex.** The least-squares line through the lows must meet U after the breakout bar [C].
  - Record how far the breakout came from base to apex, but do not filter on it.
  - Bulkowski's median is 64% [E]. Edwards & Magee via StockCharts give 1/2–3/4 [S]. Murphy gives 2/3–3/4 [S].
- **Breakouts.** Up: close > U. Down: close below the lower line minus τ [C].
- **Height.** H = U minus the lowest low in the pattern [E].

### 1.2 Descending triangle

This is the mirror image of 1.1.
- Flat bottom L = the lowest of at least 2 pivot lows within τ.
- At least 2 strictly falling pivot highs that fail the flatness test, with 3+2 touches.
- **Down breakout:** close < L. This is an N-bar low.
- **Up breakout:** close above the falling top line (least-squares fit through the pivot highs) plus τ [C]. This is a trendline break, not an N-bar high, so it needs different controls (section 4, B7).
- **Height:** H = highest peak minus L [E].

### 1.3 Horizontal resistance and support, and rectangles

- **H2 resistance.** At least 2 pivot highs within τ, separated by a pivot low at least 2τ below U [C]. The lows are otherwise unconstrained.
  - Open-code precedent: trendln `min_touches=2` and LonesomeTheBlue's tooltip value of 2 [code].
- **H3 resistance.** The same, with at least 3 touches.
- **Rectangle.** H2 or H3 where at least 2 pivot lows also lie within τ, and the lowest top is above the highest bottom. At least 5 alternating extremes are required (LMW's rectangle top/bottom and Bulkowski's 3+2) [E].
- **Support.** The mirror image of resistance.
- **Nesting.** N-bar high ⊃ H2 ⊃ H3 ⊃ {rectangle, ascending triangle}. Section 4 uses this ladder.

## 2. Trade rules as published

**Entry**
- **E1 (primary):** signal at the bar's close, fill at the next daily open [C].
- **E2 (Bulkowski):** a buy-stop at U + $0.01, or the open if price gaps above it [E].
  - Simulate on daily bars: when the high ≥ U + tick, the fill is the greater of the open and U + tick.
  - Take the tick from raw, unadjusted prices.

**Exits.** Each is a separate pre-registered rule.

| Rule | Stop | Target | Time stop | Source |
|---|---|---|---|---|
| R1 Bulkowski | Pattern low − $0.01 (mirrored for downward breaks) | Breakout ± H × 0.70 (ascending up), 0.44 (ascending down), 0.64 (descending up), 0.50 (descending down). Variant: the full H, as in Murphy, StockCharts, Edwards & Magee | None published. Use 63 / 26 / 12 bars (daily / weekly / monthly) [C] | [E]; full H [S] |
| R2 Bulkowski's tested setup | None | None | Close 3 trading days after entry, on every timeframe | [E] |
| R3 Brandt | "Last Day Rule": low of the last bar inside the pattern. Later version: low of the breakout bar if at least half of it is inside the boundary | At least H | 63 / 26 / 12 bars [C] | [E] |
| R4 Bierovic (as tested by Bulkowski) | Initial: pattern low [C]. Once price reaches U + H, trail 10¢ below the prior bar's low | – | – | [E]; ≥15-bar filter [S] |
| R5 Wilcox-Crittenden | Trailing stop at 10 × ATR(42) | None | None | [E]; the ATR length comes from later work |
| R6 O'Neil (flat bases) | 7–8% below entry. Entry at pivot + $0.10, skipped if more than 5% above the pivot | – | – | [S] |
| Event study | – | – | Daily 1, 5, 10, 21, 63, 126, 252 bars; weekly 1, 4, 13, 26, 52; monthly 1, 3, 6, 12. Primary horizon: 63 trading days / 13 weeks / 6 months | [C] |

**Context numbers**
- A stop less than 4% below the breakout is hit within a month about 50% of the time; a stop 8% or more away survives 75% of the time [E].
- Throwbacks: 58% of 10,305 upward breakouts. Price peaks about 8% above the breakout after about 6 days, and the round trip takes about 10 days. On high volume the throwback rate is 70–74% [E].
- On weekly and monthly patterns the pattern-low stop can be very wide. Report R-multiples (return divided by initial risk) as well as percent returns.
- Bulkowski's measures can be computed for comparison only: break-even failure (a move under 5%), bust (a move under 10% followed by a close beyond the opposite side), throwback (within 30 calendar days) [E]. His "ultimate high" uses hindsight and is not a tradable exit.

## 3. Prior evidence

**Bulkowski.** These are daily, bull-market-only tables of visually selected patterns, without costs, measured to a hindsight "ultimate high".
- **Ascending triangle:** breaks up 63% of the time.
  - Up: +43% average, 17% break-even failure, target met 70%, throwback 64%, rank 16/39.
  - Down: −13% average, 38% failure, target met 44%, rank 30/36.
  - Sample: more than 1,400 [E].
  - 46% of downward breakouts bust, then rise 36% [E].
  - The average rise conflicts across sources: 43% on his site, 35% at chartguys, 44% in older data [S].
- **Descending triangle:**
  - Up: +38%, 22% failure, target met 64%, rank 33/39.
  - Down: −15%, 23% failure, target met 50%, rank 15/36 [E].
  - **Conflict on direction:** his site says 53% break up [E]; older secondary sources say about 54% break down [S].
  - 276 of 650 downward breakouts busted [E].
- **Rectangle top**, the closest horizontal pattern: breaks up 63%; up +51%, 15% failure, target met 78%, rank 4/39; down −13%, 34% failure [E].
- **His own tradable test:** about 2% per trade with a 3-day exit, 65% winners, 16% maximum drawdown, more than 1,000 patterns since 1991. The best in-sample rule ranked near the bottom out of sample [E].
  - Bierovic's rule made 0.8% per trade, or 1.7% after filtering, with a 15-day hold [E].
- **Decay:** upward breakouts failing to rise 10% went from 14% in the 1990s to 28% in 2003–07. Downward breakouts went from 26% to 49% (about 14,000 patterns) [E].
- **Overhead resistance:** breakouts to all-time highs rose 65%, against 29% when resistance lay overhead (16,530 patterns) [E]. The hindsight endpoint partly builds in this gap.
- **Higher timeframes:** he publishes **no triangle statistics for weekly or monthly bars**.
  - His chart-pattern setup page reports break-even failure of 3% weekly versus 6% daily, average rise of 60% versus 48%, on 213 weekly and 518 daily patterns [E].
  - Monthly symmetrical triangles: 147 patterns, +121% in bull markets [E].
- **Yearly range:** breakouts in the lowest third of the yearly range did best [E]. This conflicts with the 52-week-high literature. Test it directly, with price ÷ 52-week high as a covariate.

**Academic tests of chart patterns**
- **LMW (2000), US stocks 1962–96.** Their triangles are symmetrical, not right-angle. The test is distributional, not a profit test.
  - NYSE/AMEX goodness-of-fit test: 7 of 10 patterns significant. The triangle bottom was significant, the triangle top was not.
  - NYSE/AMEX Kolmogorov-Smirnov test: 5 of 10 significant, including both rectangles and neither triangle.
  - Nasdaq: 10 of 10 significant [S].
- **Dawson & Steeley, UK 1986–2001:** the patterns were informative, but average market-adjusted returns after them were negative [E].
- **Zapranis & Tsinaslanidis (2012), horizontal support/resistance on NYSE/Nasdaq daily data:** support predicted interruptions better than resistance, but trading the levels did not beat buy-and-hold [E]. In their second paper, profits on 7 stocks appeared only in the 1990s [S].
- **Osler (2000), intraday FX:** price bounced off published levels 60.8% of the time, against 56.2% for random levels [E]. This is a bounce effect, not a breakout effect.
- **Park & Irwin survey:** of 95 studies, 56 positive, 20 negative and 19 mixed, with profits mostly before the early 1990s [E].
- **No peer-reviewed test of right-angle triangles on US stocks with weekly or monthly bars was found.**

**Trading-range-break (TRB) literature**
- **BLL, DJIA 1897–1986:** buy signals beat sell signals, and returns after sell signals were negative. The bootstrap rejected random walk, AR(1), GARCH-M and EGARCH [E].
  - The TRB table itself was not retrieved.
  - Parameters, from memory: n = 50/150/200 days, a 0% or 1% band, 10-day hold [S].
  - For the moving-average rules: 10-day buy return +0.53% versus sell −0.40% versus unconditional +0.17% [S].
- **Bessembinder & Chan:** the break-even one-way cost was 0.39% over the full sample and 0.22% after 1975 [E].
- **Sullivan, Timmermann & White:** 7,846 rules; the best rule was not significant out of sample in 1987–96 [E]. In sample it made about 16% a year versus 4.5% for the DJIA [S].
- **Bajgrowicz & Scaillet:** after false-discovery control, even low costs eliminate the profits in sample, and there is no persistence [E].
- **Individual stocks:** in 1,065 stocks over 1990–2004, only about 3% showed significant profits [S]. TRB on the Nasdaq index over 1971–2007 showed no reliable power [E].

**52-week highs and all-time highs**
- **George & Hwang, 1963–2001:**
  - Monthly returns: 52-week-high strategy 0.45%, Jegadeesh-Titman momentum 0.48%, industry momentum 0.45%.
  - The 52-week-high strategy returned 1.23% excluding January [S].
  - The returns did not reverse [E].
- **Decay:** 0.43% a month in 1980–2000 (significant), −0.34% in 2001–14 [E]. The paper is inconsistent about whether the later figure is significant.
  - Ben-David et al. show US momentum near 0.90% a month before June 2002 and negligible after [E].
- **What explains it:** the effect is concentrated in small stocks [S], and the q-factor model captures it [S]. Internationally it is profitable in 18 of 20 markets and significant in 10, but mostly not after costs [E].
- **Huddart, Lang & Yetman (2009), about 2,000 stocks 1982–2006:** volume spikes when price crosses the 52-week high or low, and later returns are positive [E]. The reported magnitudes are inconsistent [S].
- **Li & Yu (2012):** at index level, nearness to the 52-week high predicts higher returns, while nearness to the all-time high predicts lower returns [E].
- **All-time-high entries with a 10 × ATR trailing stop:** more than 18,000 trades, 0.5% round-trip costs, positive expectancy; 17% of trades gained 50% or more [E].
  - Zarattini et al. found it held out of sample in 2005–24, on more than 66,000 trades, with fewer than 7% of trades driving the profit [E].
- **O'Neil Global Advisors, base breakouts 1995–2021:** 3-month alpha of 1.1% for all breakouts, and 2.8% when volume rose 150% or more [E].

## 4. Controls

**The core point.** With the containment rule in place, a close above U is the highest close since the first touch. Every flat-top breakout is therefore an N-bar-high breakout, with N = bars since the first touch, and usually also a 52-week high. Flat-bottom breakdowns mirror this. The pattern's only claim is that its internal shape (touches, rising lows, contraction, volume dry-up) adds information.

**Primary estimand.** For each pattern × timeframe × direction: the mean net excess return at the primary horizon, pattern breakouts minus matched non-pattern N-bar breakouts.

**Baselines**
- **B1. Matched N-bar breakouts (the main control).**
  - For each event (stock i, bar t, N_i), take first closes above the prior N_i-bar maximum high in other stocks, in the same week (or the same month for monthly signals), that meet no pattern definition. The breakout test is identical; only the shape differs.
  - Primary matching: N, size, price, ATR%, 1-month and 12-2 momentum, distance to the 52-week and all-time highs, sector, with earnings windows as a stratum. Use nearest-neighbour 1:5 matching [C], or a regression with date fixed effects.
  - Secondary matching adds the breakout bar's return and volume ratio.
- **B2. Fixed-parameter TRB/Donchian breakouts as published**, with the same exits:
  - Daily: N = 20 and 55 (Turtle) [E]; N = 50, 150 and 200 with a 0% or 1% band (BLL) [S].
  - Weekly: 13, 26, 52. Monthly: 6, 12, 24 [C].
- **B3. 52-week-high and all-time-high crossings.**
  - First close above the prior 252-day high (Huddart-Lang-Yetman), all-time-high closes (Wilcox-Crittenden), and George-Hwang price ÷ 52-week-high deciles.
  - Tag every pattern event, then compare within strata, e.g. pattern and 52-week high versus non-pattern and 52-week high.
- **B4. The nested ladder.**
  - Estimate each step as an increment: N-bar high → H2 → H3 → rectangle or ascending triangle.
  - Add a contraction control: N-bar breakouts after the same range contraction (pattern range ÷ ATR, and ATR10 ÷ ATR50) but without triangle geometry. This separates shape from a plain volatility squeeze.
  - Add a volume-trend-matched control for volume dry-up, which Bulkowski reports in 78% of patterns [E].
- **B5. Random entries.**
  - Same stock, random eligible bars, matched to the calendar distribution of the signals, with the same percent stop and target as the paired signal. Use at least 1,000 draws [C].
  - Compute Bulkowski's own measures on these entries too. The base rates are not zero.
  - Under a driftless random walk, the chance of reaching +H before −H is about 50% [D]. Compare that with the 70% "target met" figure [E]. Throwbacks after any new high are also common.
- **B6. Placebo on simulated price paths.**
  - Run the identical detector on surrogate series: a stationary block bootstrap of each stock's returns; BLL's model nulls (random walk, AR(1), GARCH-M, EGARCH) [E]; and Ley-Varian cyclic permutations [E].
  - This gives the number of chance patterns, and their direction frequencies and returns.
  - Geometry alone favours upward exits from ascending triangles, because price ends near the flat top (gambler's ruin) [D]. So the 63% upward rate [E] must be compared with the surrogate rate, not with 50%.
- **B7. Sloped-line counterparts.**
  - Descending-triangle up-breaks versus generic falling-trendline breaks (same detector, no flat bottom).
  - Ascending-triangle down-breaks versus generic rising-trendline breaks.
  - Flat-bottom breakdowns versus N-bar lows and 52-week lows.
- **B8. Passive benchmarks.** The CRSP value-weighted index, characteristic-matched (DGTW) returns, and alphas from FF5 + UMD and from the q-factor model.

**Inference**
- Use calendar-time portfolios, plus event regressions clustered by date and stock. Overlapping returns violate the i.i.d. assumption behind the Kolmogorov-Smirnov and chi-square tests [E].
- **Multiple testing.** There are 18 primary tests (3 patterns × 3 timeframes × 2 directions), Holm-adjusted [C]. Report every variant, exit, horizon and subgroup in full, under Romano-Wolf, White's Reality Check, or false-discovery-rate control.
- **Splits [C].**
  - Develop on 1963–2004 using a random half of stock IDs (PERMNOs).
  - Confirm on the other half.
  - Hold out all stocks for 2005–25, and open the holdout once.
  - Require at least 100 events per cell for inference; smaller cells are reported descriptively only.
- **Costs.**
  - Half-spread (quoted, or estimated with Corwin-Schultz in early years) plus commission.
  - Sensitivity run at 0.5% round trip [E].
  - Compare results with the 0.22–0.39% one-way break-even costs [E].
  - Stops that gap fill at the open.
- **Universe.**
  - CRSP share codes 10 and 11 on NYSE, AMEX and Nasdaq, including delisted stocks.
  - Raw price of at least $5 at the signal [C].
  - Report the full sample and stocks above the NYSE 20th size percentile separately [C], because the 52-week-high effect sits in small stocks.

## 5. Pitfalls

1. **Look-ahead in pivots.** `scipy.argrelextrema` uses a centred window. Several common libraries look ahead:
   - chart_patterns uses 3 future bars.
   - trendln uses centred extrema and scales by the whole series.
   - smart-money-concepts shifts by 50 bars and forces a swing at the last bar [code].

   Detect only on confirmed pivots. Touches in the last k bars before a breakout cannot be seen. Test for look-ahead by truncating the data at t and re-running: the signals must be identical.
2. **Repainting zigzags.** Trendoscope runs with offset 0 and needs 1 to stop repainting. MT4's ZigZag recounts its last 3 extremes and measures deviation in points, not percent [code]. Use neither.
3. **Partial higher-timeframe bars**, and the stock-pattern loader's forward rounding of end dates [code].
4. **Hindsight and conditioning.**
   - The ultimate-high endpoint, and Bulkowski's bull-market-only tables.
   - Counting only confirmed patterns: on Bulkowski's double bottoms, only 52% confirm, and the median rise is 10% for all versus 22% for confirmed only [E].
   - Track every detected pattern from the moment it is detected, including those with no breakout or a breakout in the other direction.
5. **Thresholds that depend on price level.** Raw price-per-bar slope limits (1e-5; 0.1/0.2) [code], and $0.01 or $0.10 offsets on split-adjusted series. Normalise by price or ATR, and take ticks from raw prices.
6. **Survivorship and data quality.**
   - Include dead stocks and their delisting returns.
   - CRSP open prices start only around 1992, and pre-1992 Nasdaq highs and lows are bid/ask values or missing [S, unverified]. In those years, enter at the next close or restrict the sample.
7. **Earnings gaps.** Earnings-day breakouts confound the pattern with post-earnings drift. Flag them and report results with and without them.
8. **Duplicates and clustering.** The same level can be found on several timeframes, touch sets can nest, and several lines can qualify. Never pool timeframes. Breakouts cluster in rising markets, so cluster standard errors by date.
9. **Regime filters** must be causal, e.g. the index above its 200-day average at the signal [C]. Do not use a bull-market label applied after the fact.
10. **Data snooping.** Freeze the code and τ, k and the duration windows before opening the confirmation and holdout samples. Bulkowski's own rankings flipped out of sample [E].
11. **Thin monthly samples** with overlapping long horizons. Bulkowski's top-third monthly bucket had n = 18 [E].
12. **Distributional significance is not profit** (LMW, Jegadeesh, Dawson-Steeley).
13. **Decay** after about 1990–2002. Report results by decade.
14. **The short side.** Borrow costs and short-sale constraints make gross downward-breakout results optimistic.
15. **Broken libraries.** The `tradingpattern` package's "triangle" fires on any up or down close [code]. Write the detector yourself and unit-test it on synthetic series with known patterns.

**Conflicts left open**
- Descending-triangle direction: 53% up versus about 54% down.
- Ascending-triangle average rise: 43% versus 35% versus 44%.
- Touch counts: 3+2 versus 2+2.
- Breakout location: 64% versus 1/2–3/4 versus 2/3–3/4.
- LMW kernel bandwidth: 0.3× versus 3.0× the cross-validated value. This does not matter here, because no kernel smoothing is used.
- The sign and significance of the 52-week-high effect in 2001–14.
- Huddart-Lang-Yetman return magnitudes.
- Bulkowski's yearly-range finding versus the 52-week-high literature.

Downloaded source-code copies are in /tmp/claude-0/-home-user-my-website/7e6193d5-03fd-55b8-ab0d-60cef84cba96/scratchpad/src and /tmp/claude-0/-home-user-my-website/7e6193d5-03fd-55b8-ab0d-60cef84cba96/scratchpad/pypi_tp.