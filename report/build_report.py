"""Fill report/template.tex with tables generated from data/ -> report/phase1_report.tex"""

import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
DATA = HERE.parent / "data"
N = 50

MANAGERS = {
    "GARANTİ": "Garanti", "İŞ": "İş", "AK": "Ak", "QNB": "QNB", "YAPI KREDİ": "Yapı Kredi",
    "DENİZ": "Deniz", "KUVEYT TÜRK": "Kuveyt Türk", "ZİRAAT": "Ziraat", "TEB": "TEB",
    "ALBARAKA": "Albaraka", "HSBC": "HSBC", "PUSULA": "Pusula", "NUROL": "Nurol",
    "ATLAS": "Atlas", "FİBA": "Fiba",
}
CLASS = {"Currency": "Crypto"}  # stockanalysis labels IBIT as "Currency"


def esc(s):
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_")]:
        s = s.replace(a, b)
    return s


def tefas_type(name, category):
    if re.search(r"\bALTIN\b", name):  # not ALTINCI ("sixth")
        return "Gold"
    denom = "EUR" if "DÖVİZ-AVRO" in name else "USD" if "DÖVİZ" in name else "TRY"
    if "SERBEST" in name:
        kind = "Serbest MM" if "PARA PİYASASI" in name or "KISA VADELİ" in name else "Serbest"
    elif "PARA PİYASASI" in name:
        kind = "Money market"
    elif "HİSSE" in name:
        kind = "Foreign equity"
    elif "KİRA SERTİFİKA" in name:
        kind = "Sukuk"
    else:
        kind = category
    return f"{kind} ({denom})"


def manager(name):
    return next(v for k, v in MANAGERS.items() if name.startswith(k + " "))


def first_obs(prices):
    first = prices.apply(lambda s: s.first_valid_index())
    return {c: ("" if d == prices.index.min() else d.strftime("%b %Y")) for c, d in first.items()}


def main():
    tf = pd.read_csv(DATA / f"tefas_top{N}.csv")
    terms = pd.read_csv(DATA / f"tefas_top{N}_trading_terms.csv", dtype=str)
    tf = tf.merge(terms, on="fund_code")
    tf["type"] = [tefas_type(n, c) for n, c in zip(tf.fund_name, tf.category)]
    tf_first = first_obs(pd.read_csv(DATA / f"tefas_top{N}_prices_usd.csv", index_col=0, parse_dates=True))
    us = pd.read_csv(DATA / f"us_top{N}.csv")
    us_first = first_obs(pd.read_csv(DATA / f"us_top{N}_prices_usd.csv", index_col=0, parse_dates=True))

    tefas_rows = []
    for i, r in tf.iterrows():
        flag = r"$^\dagger$" if r.platform_status != "TEFAS'ta işlem görüyor" else ""
        tefas_rows.append(
            f"{i + 1} & {r.fund_code}{flag} & {manager(r.fund_name)} & {r.type} & "
            f"{r.portfolio_size / 1e9:.1f} & T+{r.buy_settlement_days} / T+{r.sell_settlement_days} & "
            f"{r.order_cutoff.replace('.', ':')} & {tf_first[r.fund_code]}\\\\"
        )
    tefas_rows.append(r"\midrule\multicolumn{8}{@{}l}{\footnotesize $^\dagger$ Currently closed to subscriptions and redemptions on TEFAS.}\\")

    us_rows = [
        f"{i + 1} & {r.symbol} & {CLASS.get(r.assetClass, r.assetClass)} & {esc(r['name'])}"
        f"{' (from ' + us_first[r.symbol] + ')' if us_first[r.symbol] else ''} & {r.aum_usd / 1e9:,.0f}\\\\"
        for i, r in us.iterrows()
    ]

    tf_kind = tf["type"].str.replace(r" \(.*\)", "", regex=True).replace({"Serbest MM": "Serbest money market"})
    tf_comp = tf_kind.value_counts()
    us_comp = us["assetClass"].replace(CLASS).value_counts()
    comp_rows = []
    for k in range(max(len(tf_comp), len(us_comp))):
        left = f"{tf_comp.index[k]} & {tf_comp.iloc[k]}" if k < len(tf_comp) else "&"
        right = f"{us_comp.index[k]} & {us_comp.iloc[k]}" if k < len(us_comp) else "&"
        comp_rows.append(f"{left} & {right}\\\\")
    denom = tf["type"].str.extract(r"\((\w+)\)")[0].fillna("gold").value_counts()
    comp_rows.append(r"\midrule")
    comp_rows.append(r"\multicolumn{4}{@{}l}{TEFAS denomination: " + ", ".join(f"{k} {v}" for k, v in denom.items()) + r"}\\")

    kind_of = lambda g: ", ".join(g["type"].str.replace(r" \(.*\)", "", regex=True).value_counts().index[:2])
    terms_rows = [
        f"{cut.replace('.', ':')} & T+{b} & T+{s} & {len(g)} & {kind_of(g)}\\\\"
        for (cut, b, s), g in tf.groupby(["order_cutoff", "buy_settlement_days", "sell_settlement_days"])
    ]

    tex = (HERE / "template.tex").read_text()
    for key, rows in [("TEFAS_TABLE", tefas_rows), ("US_TABLE", us_rows),
                      ("TEFAS_COMPOSITION", comp_rows), ("TERMS", terms_rows)]:
        tex = tex.replace(f"%%{key}%%", "\n".join(rows))
    (HERE / "phase1_report.tex").write_text(tex)
    print("written", HERE / "phase1_report.tex")


if __name__ == "__main__":
    main()
