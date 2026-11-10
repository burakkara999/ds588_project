"""Point-in-time universe: the 100 largest US ETFs by AUM at the start of 2026.

The current AUM ranking (fetch_us_etfs.py, October 2026) contains ETFs that grew into the
top 100 *during* the test period, which is a look-ahead bias. Instead we use the etfdb.com
"largest ETFs by AUM" table as archived by the Internet Archive on 4 January 2026.

Outputs:
    data/us_top100_2026-01.csv              symbol, name, AUM (USD) on 2026-01-04, asset class
    data/us_top100_2026-01_prices_usd.csv   adjusted daily closes (USD) of these 100 ETFs
"""

import html
import re
import time
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

SNAPSHOT = "https://web.archive.org/web/20260104074504id_/https://etfdb.com/compare/market-cap/"
DATA = Path(__file__).parent / "data"
UNIVERSE = DATA / "us_top100_2026-01.csv"
PRICES = DATA / "us_top100_2026-01_prices_usd.csv"
HEADERS = {"User-Agent": "ds588-project/1.0 (course research script)"}  # default python UA gets HTTP 429
START, END = "2021-10-01", "2026-10-03"  # fixed window (END exclusive): same period as the Phase 1 data


def get(url, tries=6):
    """GET with retries: the Internet Archive answers 429 when called too often."""
    for i in range(tries):
        r = requests.get(url, timeout=60, headers=HEADERS)
        if r.status_code != 429 or i == tries - 1:
            r.raise_for_status()
            return r
        time.sleep(30 * (i + 1))


def fetch_snapshot(url=SNAPSHOT):
    r = get(url)
    rows = []
    for tr in re.findall(r"<tr.*?</tr>", r.text, flags=re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", td)).strip() for td in re.findall(r"<td.*?</td>", tr, flags=re.S)]
        if len(cells) >= 3:
            rows.append(cells[:3])
    df = pd.DataFrame(rows, columns=["symbol", "name", "aum"])
    # etfdb reports AUM in thousands of USD
    df["aum_usd"] = df.pop("aum").str.replace(r"[$,]", "", regex=True).astype(float) * 1_000
    df.insert(0, "rank", range(1, len(df) + 1))
    if len(df) != 100:
        raise RuntimeError(f"expected 100 ETFs in the snapshot, got {len(df)}")
    return df


def add_asset_class(df):
    """Asset class labels from the stockanalysis.com list (data/us_etfs.csv, Phase 1)."""
    classes = pd.read_csv(DATA / "us_etfs.csv").set_index("symbol")["assetClass"]
    df["assetClass"] = df["symbol"].map(classes)
    if df["assetClass"].isna().any():
        raise RuntimeError(f"no asset class for {df.loc[df['assetClass'].isna(), 'symbol'].tolist()}")
    return df


def fetch_prices(symbols):
    px = yf.download(list(symbols), start=START, end=END, auto_adjust=True, progress=False)["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px.index.name = "date"
    missing = set(symbols) - set(px.columns[px.notna().any()])
    if missing:
        raise RuntimeError(f"no prices for {sorted(missing)}")
    return px[list(symbols)]


def main():
    uni = add_asset_class(fetch_snapshot())
    uni.to_csv(UNIVERSE, index=False)
    print(f"universe: {len(uni)} ETFs, AUM {uni['aum_usd'].sum() / 1e12:.2f}T USD -> {UNIVERSE}")
    px = fetch_prices(uni["symbol"])
    px.to_csv(PRICES)
    print(f"prices: {px.shape[1]} ETFs x {len(px)} days ({px.index[0].date()} -> {px.index[-1].date()}) -> {PRICES}")


if __name__ == "__main__":
    main()
