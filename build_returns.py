"""Daily simple returns of a top-100 US ETF universe.

Universes (--universe):
    2026-01  (default) 100 largest ETFs by AUM on 4 January 2026 (fetch_universe_2026.py),
             point-in-time: known at the start of the 2026 test period
    2026-10  100 largest ETFs by AUM in October 2026 (fetch_prices.py, Phase 1);
             kept only to measure the look-ahead bias of selecting by later AUM

Input:  data/<universe prices>   adjusted closes in USD, one column per ETF
Output: data/<universe returns>  same shape, r_t = P_t / P_{t-1} - 1

Prices are adjusted for dividends and splits, so the simple return already includes
distributions; nothing is added on top of it (no double counting).
The first row and the days before an ETF's launch are left empty (NaN).
"""

import argparse
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"
UNIVERSES = {  # name -> (ETF list, prices, returns)
    "2026-01": ("us_top100_2026-01.csv", "us_top100_2026-01_prices_usd.csv", "us_top100_2026-01_returns.csv"),
    "2026-10": ("us_top100.csv", "us_top100_prices_usd.csv", "us_top100_returns.csv"),
}
DEFAULT_UNIVERSE = "2026-01"


def paths(universe=DEFAULT_UNIVERSE):
    return tuple(DATA / f for f in UNIVERSES[universe])


def load_prices(path):
    return pd.read_csv(path, parse_dates=["date"], index_col="date").sort_index()


def daily_returns(prices):
    # fill_method=None: a missing price must not turn into a fake 0% return
    return prices.pct_change(fill_method=None).iloc[1:]


def load_returns(universe=DEFAULT_UNIVERSE):
    """Daily returns of a universe; built from the prices file if it does not exist yet."""
    _, prices, returns = paths(universe)
    if not returns.exists():
        daily_returns(load_prices(prices)).to_csv(returns)
    return pd.read_csv(returns, parse_dates=["date"], index_col="date")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--universe", choices=list(UNIVERSES), default=DEFAULT_UNIVERSE)
    a = p.parse_args()
    _, prices, returns = paths(a.universe)
    ret = daily_returns(load_prices(prices))
    ret.to_csv(returns)
    print(f"{ret.shape[1]} ETFs x {len(ret)} days ({ret.index[0].date()} -> {ret.index[-1].date()}) -> {returns}")


if __name__ == "__main__":
    main()
