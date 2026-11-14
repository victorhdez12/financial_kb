"""Pestaña «Manos fuertes»: cálculo COT/insiders con datos sintéticos y HTML sin errores (sin red)."""
from datetime import date

import numpy as np
import pandas as pd

from src.ingest import sec_insiders as SI
from src.report import manos_fuertes as MF
from src.report import panel_manos_fuertes as PMF


def test_percentil_y_senal():
    x = pd.Series(np.arange(100.0))
    assert MF.percentil(x, 99) == 100 and MF.percentil(x, 0) == 1
    assert MF.senal(95, 50) == "extremo alto"
    assert MF.senal(5, 3).startswith("extremo bajo (también")
    assert MF.senal(50, 99) is None and MF.senal(None, None) is None


def test_resumen_serie_cambios_y_fechas():
    idx = pd.date_range("2020-01-07", periods=300, freq="7D")  # martes
    s = pd.Series(np.linspace(-10, 20, 300), index=idx)
    r = MF.resumen_serie(s)
    assert r["p3a"] == 100 and r["senal"].startswith("extremo alto")
    assert abs(r["d1"] - (s.iloc[-1] - s.iloc[-2])) < 1e-9 and abs(r["d4"] - (s.iloc[-1] - s.iloc[-5])) < 1e-9
    assert len(r["spark"]) == MF.VENTANA_3A
    assert pd.Timestamp(r["publicado"]).dayofweek == 4  # viernes


def _trans():
    base = dict(issuer="X", director=True, officer=False, ten_pct=False, plan_10b5_1=False, fuente="t",
                trans_date=pd.Timestamp("2026-01-01"))
    filas = []
    for k, f in enumerate(pd.date_range("2024-01-01", "2026-09-30", freq="3D")):
        filas.append({**base, "accession": f"a{k}", "filing_date": f, "issuer_cik": str(k % 7), "ticker": "AAA",
                      "owner_cik": str(k % 11), "code": "P" if k % 3 == 0 else "S", "shares": 100.0, "price": 10.0})
    filas.append({**base, "accession": "bad", "filing_date": pd.Timestamp("2026-09-01"), "issuer_cik": "9",
                  "ticker": "NONE", "owner_cik": "1", "code": "P", "shares": 1e6, "price": 1e5})
    filas.append({**base, "accession": "10pct", "filing_date": pd.Timestamp("2026-09-01"), "issuer_cik": "8",
                  "ticker": "BBB", "owner_cik": "2", "code": "P", "shares": 1.0, "price": 5.0, "director": False})
    d = pd.DataFrame(filas)
    d["value"] = d["shares"] * d["price"]
    return d


def test_limpiar_excluye_sin_ticker_y_solo_10pct():
    d = MF.limpiar(_trans())
    assert "bad" not in set(d["accession"]) and "10pct" not in set(d["accession"])
    assert d["value"].max() <= 50e6


def test_insiders_agregado_y_tickers():
    d = MF.limpiar(_trans())
    a = MF.insiders_agregado(d)
    v = a["ventanas"]["13s"]
    assert a["hasta"] <= "2026-09-30"
    assert 0 <= v["amplitud"] <= 100 and v["empresas_compra"] > 0 and v["n_hist"] > 50
    t = MF.insiders_tickers(d, {"AAA": ("Aaa", "3")}, pd.Timestamp("2026-10-15"))[0]
    assert t["12m"]["n_compra"] + t["12m"]["n_venta"] > 0


def test_parse_form4_xml():
    xml = """<ownershipDocument><documentType>4</documentType><aff10b5One>1</aff10b5One>
    <issuer><issuerCik>0000001</issuerCik><issuerName>Acme</issuerName><issuerTradingSymbol>acm</issuerTradingSymbol></issuer>
    <reportingOwner><reportingOwnerId><rptOwnerCik>0000099</rptOwnerCik></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>1</isDirector></reportingOwnerRelationship></reportingOwner>
    <nonDerivativeTable>
    <nonDerivativeTransaction><transactionDate><value>2026-11-02</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>10</value></transactionShares>
      <transactionPricePerShare><value>5.5</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
    <nonDerivativeTransaction><transactionDate><value>2026-11-02</value></transactionDate>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding></nonDerivativeTransaction>
    </nonDerivativeTable></ownershipDocument>"""
    r = SI.parse_form4_xml(xml, "acc", "2026-11-03")
    assert len(r) == 1 and r[0]["code"] == "S" and r[0]["value"] == 55 and r[0]["director"]
    assert r[0]["plan_10b5_1"] and r[0]["ticker"] == "ACM" and r[0]["owner_cik"] == "99"


def test_html_sin_datos_y_con_datos():
    vacio = PMF.sec_manos_fuertes(date(2026, 11, 14), {"cot": [], "cot_error": "x", "insiders": {"error": "sin datos"}})
    assert "13F" in vacio and "sin datos" in vacio
    idx = pd.date_range("2020-01-07", periods=300, freq="7D")
    g = MF.resumen_serie(pd.Series(np.linspace(-10, 20, 300), index=idx))
    cot = [{"slug": "sp500_emini", "nombre": "S&P 500", "familia": "fin", "nota": "",
            "grupos": {"am": {**g, "etiqueta": "Gestoras"}}}]
    ins = {"agregado": MF.insiders_agregado(MF.limpiar(_trans())), "tickers": [], "recientes_hasta": None}
    h = PMF.sec_manos_fuertes(date(2026, 11, 14), {"cot": cot, "insiders": ins})
    assert "<svg" in h and "extremo alto" in h and "Contexto, no señal" in h


def test_tickers_mis_activos_sin_etf():
    t = SI.tickers_mis_activos()
    assert "MSFT" in t and "SPY" not in t and "GLD" not in t and "BAYN.DE" not in t
