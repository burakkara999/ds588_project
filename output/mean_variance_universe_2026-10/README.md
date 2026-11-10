# Mean-variance strategy vs. equal-weight benchmarks

Test period: **2026-01-01 -> 2026-09-30**, weekly rebalancing, initial capital 100,000 USD, trading cost 5 bps of traded value, execution 1 trading day(s) after the decision.

Universe: top 100 US-listed ETFs by AUM, list of 2026-10 (data/us_top100.csv), adjusted closes in USD.

Model: maximize `mu'w - (lambda/2) w'Sigma w`, `sum w = 1`, `0 <= w <= 20%`, with sample mean / covariance of the last **126** daily returns, lambda = **10**, solver = gurobi.

## Results

| strategy | final_value_usd | realized_return | avg_turnover | total_cost_usd | avg_n_holdings |
| --- | --- | --- | --- | --- | --- |
| Mean-variance (lookback=126d, lambda=10, w_max=20%) | 125,706 | 25.71% | 36.03% | 887 | 6.3 |
| EW weekly rebalanced | 110,380 | 10.38% | 1.25% | 76 | 100.0 |
| EW buy-and-hold | 110,211 | 10.21% | 0.00% | 50 | 100.0 |

Performance is measured by the realized return over the test period only. `avg_turnover` = average sum of |weight change| per weekly rebalance (first purchase excluded).

## Allocation by asset class

Average = mean of the daily (drifted) weights over the test period; final = weights at the last day.

| asset_class | average - Mean-variance (lookback=126d, lambda=10, w_max=20%) | average - EW weekly rebalanced | average - EW buy-and-hold | final - Mean-variance (lookback=126d, lambda=10, w_max=20%) | final - EW weekly rebalanced | final - EW buy-and-hold |
| --- | --- | --- | --- | --- | --- | --- |
| Commodity | 17.26% | 4.00% | 3.91% | 0.00% | 4.03% | 3.36% |
| Crypto | 0.00% | 0.99% | 0.76% | 0.00% | 1.01% | 0.84% |
| Equity | 82.32% | 74.02% | 75.54% | 100.00% | 73.89% | 77.09% |
| Fixed Income | 0.42% | 20.98% | 19.79% | 0.00% | 21.07% | 18.71% |

## Last mean-variance portfolio (decided 2026-09-25, executed 2026-09-28)

| symbol | name | asset_class | weight | exp_return_ann | vol_ann |
| --- | --- | --- | --- | --- | --- |
| XLV | State Street Health Care Select Sector SPDR ETF | Equity | 20.00% | 34.80% | 17.51% |
| VGT | Vanguard Information Technology ETF | Equity | 20.00% | 78.64% | 27.41% |
| XLK | State Street Technology Select Sector SPDR ETF | Equity | 20.00% | 83.64% | 30.01% |
| IWD | iShares Russell 1000 Value ETF | Equity | 15.97% | 36.05% | 11.30% |
| SOXX | iShares Semiconductor ETF | Equity | 10.01% | 126.44% | 54.94% |
| XLE | State Street Energy Select Sector SPDR ETF | Equity | 7.13% | 7.14% | 23.86% |
| TQQQ | ProShares UltraPro QQQ | Equity | 6.89% | 154.21% | 65.77% |

## Parameter sensitivity (realized return, mean-variance)

Rows = lookback (days), columns = lambda. `dev` periods are earlier years used for development; the test period is the one above. The last block is the return minus the EW weekly benchmark.

**dev 2024**

| lookback | 0 | 1 | 5 | 10 | 25 | 50 |
| --- | --- | --- | --- | --- | --- | --- |
| 21 | 18.99% | 16.14% | 13.90% | 11.28% | 15.36% | 14.41% |
| 63 | 13.96% | 10.00% | 11.07% | 11.12% | 2.80% | 3.17% |
| 126 | 14.99% | 6.37% | 12.25% | 4.87% | 5.53% | 5.77% |
| 252 | 29.03% | 25.30% | 25.30% | 24.53% | 18.51% | 13.09% |

**dev 2025**

| lookback | 0 | 1 | 5 | 10 | 25 | 50 |
| --- | --- | --- | --- | --- | --- | --- |
| 21 | 24.51% | 23.20% | 19.38% | 19.81% | 17.80% | 9.59% |
| 63 | 50.21% | 43.11% | 37.41% | 37.49% | 28.34% | 21.39% |
| 126 | 33.49% | 33.55% | 41.94% | 46.30% | 29.90% | 17.92% |
| 252 | 49.03% | 49.35% | 39.15% | 34.61% | 22.33% | 12.57% |

**test 2026**

| lookback | 0 | 1 | 5 | 10 | 25 | 50 |
| --- | --- | --- | --- | --- | --- | --- |
| 21 | 38.14% | 37.35% | 44.69% | 39.24% | 32.69% | 24.70% |
| 63 | 35.16% | 26.62% | 18.74% | 16.80% | 17.65% | 10.29% |
| 126 | 20.23% | 22.89% | 26.80% | 25.71% | 19.04% | 12.47% |
| 252 | 44.87% | 37.12% | 37.60% | 28.45% | 19.72% | 9.75% |

**test 2026: excess return vs. EW weekly**

| lookback | 0 | 1 | 5 | 10 | 25 | 50 |
| --- | --- | --- | --- | --- | --- | --- |
| 21 | 27.76% | 26.97% | 34.31% | 28.86% | 22.31% | 14.32% |
| 63 | 24.78% | 16.24% | 8.36% | 6.42% | 7.27% | -0.09% |
| 126 | 9.85% | 12.51% | 16.42% | 15.33% | 8.66% | 2.09% |
| 252 | 34.49% | 26.74% | 27.22% | 18.07% | 9.34% | -0.63% |

## Files

| file | content |
|---|---|
| `summary.csv` | performance metrics of the three strategies |
| `daily_values.csv` | portfolio value (USD) of each strategy for every trading day |
| `weekly_holdings.csv` | every mean-variance position per rebalance: weight and the model inputs (estimated return, volatility) |
| `weekly_target_weights.csv` | mean-variance target weights, one row per rebalance, one column per ETF |
| `rebalance_log.csv` | turnover, cost and number of holdings per rebalance, all strategies |
| `final_allocation.csv` | weight of every ETF on the last day, all strategies |
| `asset_class_allocation.csv` | average and final weight per asset class, all strategies |
| `equity_curve.png` | portfolio values over the test period |
| `mv_asset_class_weights.png` | mean-variance weights per asset class over time |
| `sensitivity.csv` | lookback x lambda grid (only with `--sensitivity`) |
| `config.json` | parameters of this run |

Runtime: 33.3 s.
