"""Weekly backtest of the mean-variance strategy against two equal-weight benchmarks.

Timing (no look-ahead):
    decision date d   = last trading day of each calendar week. The strategy receives
                        returns.loc[:d] only, i.e. information available at the close of d.
    execution date    = `exec_lag` trading days after d (default 1). Trades are filled at
                        that day's adjusted close. Until then the old portfolio is held.
    between trades    = weights drift with prices (buy-and-hold inside the week).
    start             = `capital` USD in cash at the close of the last trading day before
                        `start`; the first decision is taken on that day.
    trading cost      = cost_bps * |traded USD|, the same for every strategy.

Benchmarks (same universe, capital, costs, timing):
    EW weekly         = 1/N of the eligible ETFs, rebalanced at every decision date
    EW buy-and-hold   = 1/N at the first execution, never rebalanced afterwards

Usage:
    python backtest.py                                  # default parameters, Jan-2026 universe
    python backtest.py --universe 2026-10 --out output/mean_variance_universe_2026-10   # biased list
    python backtest.py --lookback 63 --lam 5            # other parameters
    python backtest.py --sensitivity                    # + lookback x lambda grid
    python backtest.py --solver fista                   # our own solver instead of Gurobi
"""

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from build_returns import DEFAULT_UNIVERSE, UNIVERSES, load_returns, paths
from mean_variance import MeanVariance

ROOT = Path(__file__).parent
OUT = ROOT / "output" / "mean_variance"
CLASS = {"Currency": "Crypto"}  # stockanalysis labels IBIT (bitcoin) as "Currency"


# ------------------------------------------------------------------ benchmarks
class EqualWeight:
    """1/N over the same eligible universe as the strategy (full history in the window)."""

    def __init__(self, lookback, name):
        self.lookback, self.name = lookback, name

    def __call__(self, history):
        window = history.tail(self.lookback)
        eligible = window.notna().all()
        return eligible.astype(float) / eligible.sum()


# ------------------------------------------------------------------ engine
@dataclass
class Result:
    name: str
    values: pd.Series        # portfolio value (USD) per day, starting with the initial capital
    weights: pd.DataFrame    # end-of-day (drifted) weights per day
    targets: pd.DataFrame    # target weights per rebalance (index = execution date)
    trades: pd.DataFrame     # one row per rebalance: decision/execution date, turnover, cost


def decision_dates(index, start, end):
    """Last trading day before `start`, then the last trading day of every week in [start, end]."""
    days = index[(index >= start) & (index <= end)]
    week_ends = pd.Series(days, index=days).groupby(days.to_period("W-FRI")).last()
    return [index[index < start][-1], *week_ends]


def backtest(returns, strategy, start, end, capital=100_000.0, cost_bps=5.0, exec_lag=1, rebalance=True):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    idx = returns.index
    dates = decision_dates(idx, start, end)
    if not rebalance:
        dates = dates[:1]

    schedule = {}  # execution date -> (decision date, target weights)
    for d in dates:
        pos = idx.get_loc(d) + exec_lag
        if pos < len(idx) and idx[pos] <= end:
            history = returns.loc[:d]  # <- the only data the strategy ever sees
            assert history.index[-1] == d
            schedule[idx[pos]] = (d, strategy(history))

    t0 = idx[idx < start][-1]
    days = [t0, *idx[(idx >= start) & (idx <= end)]]
    hold = pd.Series(0.0, index=returns.columns)  # USD per ETF
    cash = capital
    values, weights, targets, trades = {}, {}, {}, []
    for t in days:
        if t != t0:
            hold *= 1 + returns.loc[t].fillna(0.0)
        if t in schedule:
            d, w = schedule[t]
            value = hold.sum() + cash
            traded = (w * value - hold).abs().sum() + 0.0
            cost = cost_bps / 1e4 * traded
            value -= cost
            hold, cash = w * value, value * (1 - w.sum())
            targets[t] = w
            trades.append({"decision_date": d, "execution_date": t, "turnover": traded / (value + cost),
                           "cost_usd": cost, "n_holdings": int((w > 0).sum())})
        values[t] = hold.sum() + cash
        weights[t] = hold / values[t]

    return Result(strategy.name, pd.Series(values, name=strategy.name),
                  pd.DataFrame(weights).T, pd.DataFrame(targets).T, pd.DataFrame(trades))


# ------------------------------------------------------------------ metrics
def metrics(res: Result):
    """Performance = realized return only; the other fields describe the trading activity."""
    v = res.values
    return {
        "strategy": res.name,
        "final_value_usd": v.iloc[-1],
        "realized_return": v.iloc[-1] / v.iloc[0] - 1,
        "n_rebalances": len(res.trades),
        "avg_turnover": res.trades["turnover"].iloc[1:].mean() if len(res.trades) > 1 else 0.0,
        "total_cost_usd": res.trades["cost_usd"].sum(),
        "avg_n_holdings": res.trades["n_holdings"].mean(),
    }


def run_all(returns, start, end, lookback, lam, w_max, cost_bps, exec_lag, capital, solver="gurobi"):
    kw = dict(start=start, end=end, capital=capital, cost_bps=cost_bps, exec_lag=exec_lag)
    return [
        backtest(returns, MeanVariance(lookback, lam, w_max, solver), **kw),
        backtest(returns, EqualWeight(lookback, "EW weekly rebalanced"), **kw),
        backtest(returns, EqualWeight(lookback, "EW buy-and-hold"), rebalance=False, **kw),
    ]


# ------------------------------------------------------------------ outputs
def holdings_table(returns, strategy, res, universe):
    """Long table of every non-zero target weight, with the model's estimates at that date."""
    rows = []
    for _, tr in res.trades.iterrows():
        w = res.targets.loc[tr["execution_date"]]
        w = w[w > 0].sort_values(ascending=False)
        diag = strategy.diagnostics(returns.loc[: tr["decision_date"]]).loc[w.index]
        for rank, (sym, wt) in enumerate(w.items(), 1):
            rows.append({"decision_date": tr["decision_date"].date(), "execution_date": tr["execution_date"].date(),
                         "rank": rank, "symbol": sym, "name": universe.loc[sym, "name"],
                         "asset_class": universe.loc[sym, "asset_class"], "weight": wt,
                         "exp_return_ann": diag.loc[sym, "exp_return_ann"], "vol_ann": diag.loc[sym, "vol_ann"]})
    return pd.DataFrame(rows)


def class_weights(weights, universe):
    return weights.T.groupby(universe["asset_class"]).sum().T


def sensitivity(returns, periods, lookbacks, lams, w_max, cost_bps, exec_lag, capital, solver="gurobi"):
    rows = []
    for label, (s, e) in periods.items():
        kw = dict(start=s, end=e, capital=capital, cost_bps=cost_bps, exec_lag=exec_lag)
        for lb in lookbacks:
            ew = metrics(backtest(returns, EqualWeight(lb, "EW"), **kw))
            for lam in lams:
                m = metrics(backtest(returns, MeanVariance(lb, lam, w_max, solver), **kw))
                rows.append({"period": label, "lookback": lb, "lam": lam,
                             "realized_return": m["realized_return"],
                             "ew_weekly_return": ew["realized_return"],
                             "excess_vs_ew_weekly": m["realized_return"] - ew["realized_return"],
                             "avg_turnover": m["avg_turnover"], "avg_n_holdings": m["avg_n_holdings"]})
            print(f"  sensitivity {label}: lookback={lb} done")
    return pd.DataFrame(rows)


def rel(path):
    """Path relative to the project folder, so no local directory names end up in the outputs."""
    path = Path(path).resolve()
    return str(path.relative_to(ROOT.resolve())) if path.is_relative_to(ROOT.resolve()) else path.name


def pct(x):
    return f"{x:.2%}"


def md_table(df, index=True):
    """Small markdown table writer (avoids the optional `tabulate` dependency)."""
    d = df.reset_index() if index else df
    rows = [[str(c) for c in d.columns], ["---"] * d.shape[1]] + [[str(v) for v in r] for r in d.to_numpy()]
    return "\n".join("| " + " | ".join(r) + " |" for r in rows)


def write_readme(path, cfg, summary, alloc, last_holdings, runtime, sens=None):
    s = summary.set_index("strategy")
    fmt = s[["final_value_usd", "realized_return", "avg_turnover", "total_cost_usd", "avg_n_holdings"]].copy()
    for c in ["realized_return", "avg_turnover"]:
        fmt[c] = fmt[c].map(pct)
    for c in ["final_value_usd", "total_cost_usd"]:
        fmt[c] = fmt[c].map(lambda x: f"{x:,.0f}")
    fmt["avg_n_holdings"] = fmt["avg_n_holdings"].map(lambda x: f"{x:.1f}")

    lines = [
        "# Mean-variance strategy vs. equal-weight benchmarks",
        "",
        f"Test period: **{cfg['start']} -> {cfg['end']}**, weekly rebalancing, "
        f"initial capital {cfg['capital']:,.0f} USD, trading cost {cfg['cost_bps']:g} bps of traded value, "
        f"execution {cfg['exec_lag']} trading day(s) after the decision.",
        "",
        f"Universe: top {cfg['n_assets']} US-listed ETFs by AUM, list of {cfg['universe']} "
        f"(data/{UNIVERSES[cfg['universe']][0]}), adjusted closes in USD.",
        "",
        f"Model: maximize `mu'w - (lambda/2) w'Sigma w`, `sum w = 1`, `0 <= w <= {cfg['w_max']:.0%}`, "
        f"with sample mean / covariance of the last **{cfg['lookback']}** daily returns, "
        f"lambda = **{cfg['lam']:g}**, solver = {cfg['solver']}.",
        "",
        "## Results",
        "",
        md_table(fmt),
        "",
        "Performance is measured by the realized return over the test period only. "
        "`avg_turnover` = average sum of |weight change| per weekly rebalance (first purchase excluded).",
        "",
        "## Allocation by asset class",
        "",
        "Average = mean of the daily (drifted) weights over the test period; final = weights at the last day.",
        "",
        md_table(alloc.map(pct).set_axis([f'{a} - {b}' for a, b in alloc.columns], axis=1)),
        "",
        f"## Last mean-variance portfolio (decided {last_holdings['decision_date'].iloc[0]}, "
        f"executed {last_holdings['execution_date'].iloc[0]})",
        "",
        md_table(last_holdings[["symbol", "name", "asset_class", "weight", "exp_return_ann", "vol_ann"]]
                 .assign(weight=lambda d: d["weight"].map(pct),
                         exp_return_ann=lambda d: d["exp_return_ann"].map(pct),
                         vol_ann=lambda d: d["vol_ann"].map(pct)), index=False),
        "",
        *([] if sens is None else [
            "## Parameter sensitivity (realized return, mean-variance)",
            "",
            "Rows = lookback (days), columns = lambda. `dev` periods are earlier years used for development; "
            "the test period is the one above. The last block is the return minus the EW weekly benchmark.",
            "",
            *[block for label, g in sens.groupby("period", sort=False) for block in (
                f"**{label}**", "",
                md_table(g.pivot(index="lookback", columns="lam", values="realized_return").map(pct)), "")],
            f"**test {cfg['start'][:4]}: excess return vs. EW weekly**", "",
            md_table(sens[sens["period"].str.startswith("test")]
                     .pivot(index="lookback", columns="lam", values="excess_vs_ew_weekly").map(pct)),
            "",
        ]),
        "## Files",
        "",
        "| file | content |",
        "|---|---|",
        "| `summary.csv` | performance metrics of the three strategies |",
        "| `daily_values.csv` | portfolio value (USD) of each strategy for every trading day |",
        "| `weekly_holdings.csv` | every mean-variance position per rebalance: weight and the model inputs (estimated return, volatility) |",
        "| `weekly_target_weights.csv` | mean-variance target weights, one row per rebalance, one column per ETF |",
        "| `rebalance_log.csv` | turnover, cost and number of holdings per rebalance, all strategies |",
        "| `final_allocation.csv` | weight of every ETF on the last day, all strategies |",
        "| `asset_class_allocation.csv` | average and final weight per asset class, all strategies |",
        "| `equity_curve.png` | portfolio values over the test period |",
        "| `mv_asset_class_weights.png` | mean-variance weights per asset class over time |",
        "| `sensitivity.csv` | lookback x lambda grid (only with `--sensitivity`) |",
        "| `config.json` | parameters of this run |",
        "",
        f"Runtime: {runtime:.1f} s.",
        "",
    ]
    path.write_text("\n".join(lines))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--universe", choices=list(UNIVERSES), default=DEFAULT_UNIVERSE,
                   help="ETF list: 2026-01 = point-in-time top 100 (default), 2026-10 = Phase 1 list (biased)")
    p.add_argument("--start", default="2026-01-01")
    p.add_argument("--end", default="2026-09-30")
    p.add_argument("--lookback", type=int, default=126, help="days of past returns for mean/covariance")
    p.add_argument("--lam", type=float, default=10.0, help="risk aversion (variance penalty)")
    p.add_argument("--w-max", type=float, default=0.20, help="max weight per ETF")
    p.add_argument("--cost-bps", type=float, default=5.0, help="trading cost in bps of traded value")
    p.add_argument("--exec-lag", type=int, default=1, help="trading days between decision and execution")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--solver", choices=["gurobi", "fista"], default="gurobi",
                   help="QP solver: Gurobi (default) or our own projected-gradient implementation")
    p.add_argument("--sensitivity", action="store_true", help="also run the lookback x lambda grid")
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()

    t_start = time.perf_counter()
    returns = load_returns(a.universe)
    universe = pd.read_csv(paths(a.universe)[0]).set_index("symbol")
    universe["asset_class"] = universe["assetClass"].replace(CLASS)
    universe = universe.reindex(returns.columns)

    cfg = {k: (rel(v) if isinstance(v, Path) else v) for k, v in vars(a).items()}
    cfg["n_assets"] = returns.shape[1]
    out = a.out
    out.mkdir(parents=True, exist_ok=True)

    results = run_all(returns, a.start, a.end, a.lookback, a.lam, a.w_max, a.cost_bps, a.exec_lag, a.capital,
                      a.solver)
    mv = results[0]
    strategy = MeanVariance(a.lookback, a.lam, a.w_max, a.solver)

    summary = pd.DataFrame([metrics(r) for r in results])
    summary.to_csv(out / "summary.csv", index=False)

    values = pd.concat([r.values for r in results], axis=1)
    values.index.name = "date"
    values.to_csv(out / "daily_values.csv")

    holdings = holdings_table(returns, strategy, mv, universe)
    holdings.to_csv(out / "weekly_holdings.csv", index=False)

    tw = mv.targets.copy()
    tw.insert(0, "decision_date", mv.trades["decision_date"].to_numpy())
    tw.index.name = "execution_date"
    tw.to_csv(out / "weekly_target_weights.csv")

    pd.concat([r.trades.assign(strategy=r.name) for r in results]).to_csv(out / "rebalance_log.csv", index=False)

    final = pd.DataFrame({r.name: r.weights.iloc[-1] for r in results})
    final = universe[["name", "asset_class"]].join(final)
    final.index.name = "symbol"
    final.sort_values(mv.name, ascending=False).to_csv(out / "final_allocation.csv")

    alloc = pd.concat({
        "average": pd.DataFrame({r.name: class_weights(r.weights.iloc[1:], universe).mean() for r in results}),
        "final": pd.DataFrame({r.name: class_weights(r.weights.iloc[[-1]], universe).iloc[0] for r in results}),
    }, axis=1)
    alloc.index.name = "asset_class"
    alloc.to_csv(out / "asset_class_allocation.csv")

    plots(results, universe, out)

    sens = None
    if a.sensitivity:
        periods = {"dev 2024": ("2024-01-01", "2024-12-31"), "dev 2025": ("2025-01-01", "2025-12-31"),
                   f"test {a.start[:4]}": (a.start, a.end)}
        sens = sensitivity(returns, periods, [21, 63, 126, 252], [0, 1, 5, 10, 25, 50],
                           a.w_max, a.cost_bps, a.exec_lag, a.capital, a.solver)
        sens.to_csv(out / "sensitivity.csv", index=False)

    with open(out / "config.json", "w") as f:
        json.dump(cfg, f, indent=2)

    last = holdings[holdings["decision_date"] == holdings["decision_date"].max()]
    runtime = time.perf_counter() - t_start
    write_readme(out / "README.md", cfg, summary, alloc, last, runtime, sens)

    show = summary.set_index("strategy")[["final_value_usd", "realized_return", "avg_turnover",
                                          "total_cost_usd", "avg_n_holdings"]]
    print(show.to_string(float_format=lambda x: f"{x:,.4f}"))
    print(f"-> {out}  ({runtime:.1f} s)")


# light-mode surface / ink and categorical slots of the dataviz reference palette
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
CLASS_ORDER = ["Equity", "Fixed Income", "Commodity", "Crypto"]


def _style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)


def plots(results, universe, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    # 1) portfolio value
    fig, ax = plt.subplots(figsize=(10, 5.2), facecolor=SURFACE)
    _style(ax)
    ends = []
    for r, color in zip(results, SERIES):
        ax.plot(r.values.index, r.values / 1000, color=color, linewidth=2, label=r.name)
        ends.append((r.values.iloc[-1] / 1000, r.values.iloc[-1] / r.values.iloc[0] - 1, color))
    ends.sort(key=lambda e: e[0])
    span = ax.get_ylim()[1] - ax.get_ylim()[0]
    last_y = -np.inf
    for y, ret, color in ends:  # direct labels at the line ends, nudged apart if they collide
        y_lab = max(y, last_y + 0.045 * span)
        ax.annotate(f"{ret:+.1%}", (results[0].values.index[-1], y), xytext=(8, (y_lab - y) / span * 260),
                    textcoords="offset points", va="center", fontsize=9, color=INK)
        ax.plot([], [], color=color)
        last_y = y_lab
    ax.set_ylabel("Portfolio value (thousand USD)", color=INK_2, fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_title("Portfolio value, weekly rebalancing", loc="left", color=INK, fontsize=12, pad=24)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=8.5,
              labelcolor=INK_2, borderaxespad=0.2)
    ax.margins(x=0.01)
    fig.tight_layout()
    fig.savefig(out / "equity_curve.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)

    # 2) mean-variance weights per asset class (daily, drifted)
    cw = class_weights(results[0].weights.iloc[1:], universe)
    cw = cw.reindex(columns=[c for c in CLASS_ORDER if c in cw.columns and cw[c].max() > 0])
    fig, ax = plt.subplots(figsize=(10, 4.6), facecolor=SURFACE)
    _style(ax)
    colors = [SERIES[CLASS_ORDER.index(c)] for c in cw.columns]
    ax.stackplot(cw.index, (cw * 100).T.to_numpy(), labels=cw.columns, colors=colors,
                 edgecolor=SURFACE, linewidth=1)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Weight (%)", color=INK_2, fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_title("Mean-variance portfolio by asset class", loc="left", color=INK, fontsize=12, pad=24)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, frameon=False, fontsize=8.5,
              labelcolor=INK_2, borderaxespad=0.2)
    ax.margins(x=0)
    fig.tight_layout()
    fig.savefig(out / "mv_asset_class_weights.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    main()
