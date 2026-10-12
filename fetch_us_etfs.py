"""Fetch all US-listed ETFs with AUM (assets under management).

Primary source:  stockanalysis.com screener (symbol, name, asset class, AUM, ...)
Cross-check:     Nasdaq ETF screener (symbol list only, no AUM)

Output: data/us_etfs.csv
"""

from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).parent / "data" / "us_etfs.csv"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}
COLUMNS = "s,n,assetClass,aum,price,volume,expenseRatio,inceptionDate,issuer"


def stockanalysis_etfs():
    url = "https://stockanalysis.com/_api/endpoints/screener/table"
    params = {"type": "e", "m": "aum", "s": "desc", "c": COLUMNS, "cn": 10000, "p": 1, "i": "etf"}
    r = requests.get(url, params=params, headers={**HEADERS, "Referer": "https://stockanalysis.com/etf/"}, timeout=60)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["data"]["data"])
    return df.rename(columns={"s": "symbol", "n": "name", "aum": "aum_usd"})


def nasdaq_symbols():
    r = requests.get("https://api.nasdaq.com/api/screener/etf?download=true", headers=HEADERS, timeout=60)
    r.raise_for_status()
    return {row["symbol"] for row in r.json()["data"]["data"]["rows"]}


def main():
    df = stockanalysis_etfs().sort_values("aum_usd", ascending=False)
    nasdaq = nasdaq_symbols()
    df["in_nasdaq_list"] = df["symbol"].isin(nasdaq)
    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"stockanalysis: {len(df)} ETFs | nasdaq list: {len(nasdaq)} | overlap: {df['in_nasdaq_list'].sum()}")
    print(f"total AUM: ${df['aum_usd'].sum() / 1e12:.2f}T -> {OUT}")


if __name__ == "__main__":
    main()
