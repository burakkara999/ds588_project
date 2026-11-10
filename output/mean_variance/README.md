# Mean-variance strategy vs. equal-weight benchmarks

Test period: **2026-01-01 -> 2026-09-30**, weekly rebalancing, initial capital 100,000 USD, trading cost 5 bps of traded value, execution 1 trading day(s) after the decision.

Universe: top 100 US-listed ETFs by AUM, list of 2026-01 (data/us_top100_2026-01.csv), adjusted closes in USD.

Model: maximize `mu'w - (lambda/2) w'Sigma w`, `sum w = 1`, `0 <= w <= 20%`, with sample mean / covariance of the last **126** daily returns, lambda = **10**, solver = gurobi.

## Results

| strategy | final_value_usd | realized_return | avg_turnover | total_cost_usd | avg_n_holdings |
| --- | --- | --- | --- | --- | --- |
| Mean-variance (lookback=126d, lambda=10, w_max=20%) | 117,785 | 17.79% | 39.01% | 922 | 6.2 |
| EW weekly rebalanced | 109,023 | 9.02% | 1.25% | 76 | 100.0 |
| EW buy-and-hold | 108,680 | 8.68% | 0.00% | 50 | 100.0 |

Performance is measured by the realized return over the test period only. `avg_turnover` = average sum of |weight change| per weekly rebalance (first purchase excluded).

## Allocation by asset class

Average = mean of the daily (drifted) weights over the test period; final = weights at the last day.

| asset_class | average - Mean-variance (lookback=126d, lambda=10, w_max=20%) | average - EW weekly rebalanced | average - EW buy-and-hold | final - Mean-variance (lookback=126d, lambda=10, w_max=20%) | final - EW weekly rebalanced | final - EW buy-and-hold |
| --- | --- | --- | --- | --- | --- | --- |
| Commodity | 13.49% | 4.00% | 3.93% | 0.00% | 4.03% | 3.40% |
| Crypto | 0.00% | 0.99% | 0.77% | 0.00% | 1.01% | 0.85% |
| Equity | 85.76% | 74.02% | 75.36% | 100.00% | 73.90% | 76.81% |
| Fixed Income | 0.75% | 20.99% | 19.94% | 0.00% | 21.07% | 18.93% |

## Last mean-variance portfolio (decided 2026-09-25, executed 2026-09-28)

| symbol | name | asset_class | weight | exp_return_ann | vol_ann |
| --- | --- | --- | --- | --- | --- |
| XLV | State Street Health Care Select Sector SPDR ETF | Equity | 20.00% | 34.80% | 17.51% |
| XLK | State Street Technology Select Sector SPDR ETF | Equity | 20.00% | 83.64% | 30.01% |
| VGT | Vanguard Information Technology ETF | Equity | 20.00% | 78.64% | 27.41% |
| IWD | iShares Russell 1000 Value ETF | Equity | 15.10% | 36.05% | 11.30% |
| TQQQ | ProShares UltraPro QQQ | Equity | 14.89% | 154.21% | 65.77% |
| XLE | State Street Energy Select Sector SPDR ETF | Equity | 10.01% | 7.14% | 23.86% |

## Parameter sensitivity (realized return, mean-variance)

Rows = lookback (days), columns = lambda. `dev` periods are earlier years used for development; the test period is the one above. The last block is the return minus the EW weekly benchmark.

**dev 2024**

| lookback | 0 | 1 | 5 | 10 | 25 | 50 |
| --- | --- | --- | --- | --- | --- | --- |
| 21 | 16.96% | 14.52% | 18.18% | 19.53% | 19.87% | 18.09% |
| 63 | 10.58% | 7.41% | 10.65% | 8.97% | 4.24% | 4.22% |
| 126 | 18.55% | 10.08% | 10.71% | 6.13% | 6.28% | 5.22% |
| 252 | 26.71% | 30.51% | 23.92% | 22.92% | 18.71% | 12.46% |

**dev 2025**

| lookback | 0 | 1 | 5 | 10 | 25 | 50 |
| --- | --- | --- | --- | --- | --- | --- |
| 21 | 34.32% | 28.56% | 24.71% | 26.22% | 24.44% | 15.15% |
| 63 | 61.82% | 58.67% | 53.42% | 52.68% | 35.56% | 23.18% |
| 126 | 37.72% | 42.35% | 43.43% | 44.29% | 27.88% | 17.13% |
| 252 | 53.08% | 50.80% | 47.67% | 34.42% | 21.15% | 12.09% |

**test 2026**

| lookback | 0 | 1 | 5 | 10 | 25 | 50 |
| --- | --- | --- | --- | --- | --- | --- |
| 21 | 33.31% | 30.45% | 35.25% | 35.01% | 28.84% | 21.32% |
| 63 | 17.60% | 20.09% | 13.08% | 9.97% | 12.21% | 8.21% |
| 126 | 8.26% | 13.66% | 18.75% | 17.79% | 14.24% | 10.87% |
| 252 | 26.57% | 21.99% | 18.21% | 21.97% | 14.29% | 8.99% |

**test 2026: excess return vs. EW weekly**

| lookback | 0 | 1 | 5 | 10 | 25 | 50 |
| --- | --- | --- | --- | --- | --- | --- |
| 21 | 24.29% | 21.43% | 26.22% | 25.99% | 19.82% | 12.29% |
| 63 | 8.58% | 11.06% | 4.05% | 0.94% | 3.18% | -0.81% |
| 126 | -0.77% | 4.63% | 9.73% | 8.76% | 5.21% | 1.84% |
| 252 | 17.55% | 12.97% | 9.19% | 12.94% | 5.27% | -0.03% |

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

Runtime: 32.7 s.
