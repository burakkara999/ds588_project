import pandas as pd
import numpy as np


df_tefas = pd.read_csv("data/tefas_top100_prices_usd.csv", parse_dates=["date"], index_col="date")
df_us = pd.read_csv("data/us_top100_prices_usd.csv", parse_dates=["date"], index_col="date")

print(df_tefas.head())

print(df_us.head())

pd.set_option("display.max_rows", None)

for name, df in [("TEFAS", df_tefas), ("US", df_us)]:
    print(f"\n===== {name} =====")

    # NaN count per row (only dates that have NaNs)
    print(f"\n--- NaN count per row ---")
    nan_per_row = df.isna().sum(axis=1)
    print(nan_per_row[nan_per_row > 0])

    # Last date with a NaN value for each ticker (only tickers that have NaNs)
    print(f"\n--- Last NaN date per ticker ---")
    last_nan_date = df.isna().apply(lambda col: col[col].index.max())
    print(last_nan_date.dropna().sort_values())


