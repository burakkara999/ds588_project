"""Top N US ETFs and top N TEFAS YAT funds: daily close prices in USD since START.

US:     ranked by AUM (stockanalysis.com), prices from yfinance (already in USD)
TEFAS:  ranked by portfolio size (pytefas), only funds traded on TEFAS
        (private "ÖZEL" funds are excluded), TL prices / USDTRY (yfinance TRY=X)

Outputs (wide format: one row per date, one column per symbol):
    data/us_top{N}_prices_usd.csv
    data/tefas_top{N}_prices_usd.csv
    data/us_top{N}.csv, data/tefas_top{N}.csv   (selected funds + size)
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from pytefas import Crawler

from fetch_tefas import list_funds
from fetch_us_etfs import stockanalysis_etfs

TOP_N = 50
END = date.today()
START = date(2022, 1, 1)  # must stay within 5 years of today: TEFAS API rejects older dates
CHUNK_DAYS = 28  # TEFAS API returns at most ~1 month per request
ADJUSTED = True  # yfinance: True = close adjusted for dividends/splits, False = raw close
DATA = Path(__file__).parent / "data"

tefas = Crawler()


# --------------------------------------------------------------------------- US
def us_top(n=TOP_N):
    etfs = stockanalysis_etfs().sort_values("aum_usd", ascending=False)
    return etfs.head(n)[["symbol", "name", "assetClass", "aum_usd"]].reset_index(drop=True)


def us_prices(symbols):
    px = yf.download(list(symbols), start=START, end=END + timedelta(days=1),
                     auto_adjust=ADJUSTED, progress=False)["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px.index.name = "date"
    return px[[s for s in symbols if s in px.columns]]


# ------------------------------------------------------------------------ TEFAS
def tefas_top(n=TOP_N):
    traded = {r["fonKodu"] for r in list_funds("YAT")}
    recent = tefas.fetch(END - timedelta(days=10), END, kind="YAT")
    latest = recent.sort_values("date").groupby("fund_code").tail(1)
    latest = latest[latest["fund_code"].isin(traded)]
    top = latest.sort_values("portfolio_size", ascending=False).head(n)
    return top[["fund_code", "fund_name", "portfolio_size", "investor_count", "date"]].reset_index(drop=True)


def tefas_prices_try(codes):
    codes = set(codes)
    frames = []
    chunk_start = START
    while chunk_start <= END:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), END)
        df = tefas.fetch(chunk_start, chunk_end, kind="YAT")
        if not df.empty:
            frames.append(df.loc[df["fund_code"].isin(codes), ["date", "fund_code", "price"]])
        print(f"  TEFAS {chunk_start} -> {chunk_end}: {len(frames[-1]) if frames else 0} rows")
        chunk_start = chunk_end + timedelta(days=1)

    long = pd.concat(frames, ignore_index=True)
    long["date"] = pd.to_datetime(long["date"])
    long = long[long["price"] > 0]
    return long.pivot_table(index="date", columns="fund_code", values="price", aggfunc="last")


def usdtry(dates):
    fx = yf.download("TRY=X", start=START - timedelta(days=10), end=END + timedelta(days=1),
                     auto_adjust=True, progress=False)["Close"]["TRY=X"]
    fx.index = pd.to_datetime(fx.index).tz_localize(None)
    # TEFAS days without an FX quote (e.g. FX holiday) use the last available rate
    return fx.reindex(fx.index.union(dates)).ffill().reindex(dates)


# ------------------------------------------------------------------------- main
def main():
    DATA.mkdir(exist_ok=True)
    print(f"Period: {START} -> {END}")

    us = us_top()
    us.to_csv(DATA / f"us_top{TOP_N}.csv", index=False)
    us_px = us_prices(us["symbol"])
    us_px.to_csv(DATA / f"us_top{TOP_N}_prices_usd.csv")
    print(f"US: {us_px.shape[1]} ETFs x {len(us_px)} days -> us_top{TOP_N}_prices_usd.csv")

    tf = tefas_top()
    tf.to_csv(DATA / f"tefas_top{TOP_N}.csv", index=False, encoding="utf-8-sig")
    tf_try = tefas_prices_try(tf["fund_code"])
    tf_usd = tf_try.div(usdtry(tf_try.index), axis=0)
    tf_usd = tf_usd[[c for c in tf["fund_code"] if c in tf_usd.columns]]
    tf_usd.index.name = "date"
    tf_usd.to_csv(DATA / f"tefas_top{TOP_N}_prices_usd.csv")
    print(f"TEFAS: {tf_usd.shape[1]} funds x {len(tf_usd)} days -> tefas_top{TOP_N}_prices_usd.csv")


if __name__ == "__main__":
    main()
