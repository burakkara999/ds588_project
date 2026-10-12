"""Fetch every TEFAS fund (YAT, EMK, BYF) with its portfolio size.

Fund list:  /api/funds/fonGetiriBazliBilgiGetir  (per fund type)
Fund info:  /api/funds/fonBilgiGetir             (portBuyukluk, yatirimciSayi, ...)

Output: data/tefas_funds.csv
"""

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
from tefas.crawler import Crawler

OUT = Path(__file__).parent / "data" / "tefas_funds.csv"
LIST_PAYLOAD = {
    "dil": "TR", "kurucuKodu": None, "sfonTurKod": None, "fonTurAciklama": None,
    "islem": 1, "fonTurKod": None, "fonGrubu": None,
    "donemGetiri1a": "1", "donemGetiri3a": "1", "donemGetiri6a": "1",
    "donemGetiri1y": "1", "donemGetiriyb": "1", "donemGetiri3y": "1",
    "donemGetiri5y": "1", "basTarih": None, "bitTarih": None,
    "calismaTipi": 2, "getiriOrani": "1",
}

crawler = Crawler()


def list_funds(kind):
    rows = crawler._do_post(crawler.list_endpoint, {**LIST_PAYLOAD, "fonTipi": kind})
    return [{**r, "fonTipi": kind} for r in rows if r.get("fonKodu")]


def fund_info(code, retries=3):
    for attempt in range(retries):
        try:
            res = crawler._do_post("/api/funds/fonBilgiGetir", {"fonKodu": code, "dil": "TR"})
            return res[0] if res else {"fonKodu": code}
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {"fonKodu": code}


def main():
    funds = pd.DataFrame([r for kind in ("YAT", "EMK", "BYF") for r in list_funds(kind)])
    print(funds["fonTipi"].value_counts().to_string())

    with ThreadPoolExecutor(max_workers=4) as pool:
        infos = list(pool.map(fund_info, funds["fonKodu"]))
    info = pd.DataFrame(infos).drop(columns=["fonUnvan"], errors="ignore")

    df = funds[["fonTipi", "fonKodu", "fonUnvan", "fonTurAciklama", "tefasDurum", "riskDegeri",
                "getiri1a", "getiri1y"]].merge(info, on="fonKodu", how="left")
    df = df.sort_values("portBuyukluk", ascending=False)
    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"{len(df)} funds -> {OUT}  (missing size: {df['portBuyukluk'].isna().sum()})")


if __name__ == "__main__":
    main()
