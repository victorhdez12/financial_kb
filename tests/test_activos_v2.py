"""Ficha v2 de «Mis activos» (src/report/activos_v2.py): volumen, Form 4, 13F y analistas con datos sintéticos (sin red)."""
from datetime import date

import numpy as np
import pandas as pd

from src.ingest import sec_form4_detalle as F4
from src.ingest import yahoo_analistas as YA
from src.report import activos_v2 as AV

HOY = pd.Timestamp("2026-11-16")


def _serie(v, n=300, fin=HOY):
    return pd.Series(v if np.ndim(v) else [v] * n, index=pd.bdate_range(end=fin, periods=n), dtype=float)


# ------------------------------------------------------------------------------------------ volumen
def test_volumen_medias_excluyen_ultima_sesion_e_importe():
    vol = _serie(100.0)
    vol.iloc[-1] = 300.0
    r = AV.volumen_resumen(vol, _serie(10.0))
    assert r["ultimo"] == 300 and r["media_20"] == 100 and r["media_3m"] == 100
    assert r["ratio_20"] == 3 and r["importe"] == 3000 and r["importe_20"] == 1000


def test_volumen_futuro_sin_importe_y_pocos_datos():
    r = AV.volumen_resumen(_serie(50.0), _serie(70.0), es_futuro=True)
    assert r["importe"] is None and r["es_futuro"]
    assert AV.volumen_resumen(_serie(1.0, n=10), None) is None


# ------------------------------------------------------------------------------------------ Form 4
def _ops():
    base = dict(accession="a", filing_date=pd.Timestamp("2026-06-03"), issuer_cik="1", ticker="AAA", owner_cik="9",
                owner_name="Pérez Ana", title="CFO", director=False, officer=True, ten_pct=False, acq_disp="D",
                fuente="t")
    f = [
        {**base, "trans_date": "2026-06-01", "code": "P", "shares": 100, "price": 10.0, "plan_10b5_1": False, "acq_disp": "A"},
        {**base, "trans_date": "2026-06-02", "code": "P", "shares": 300, "price": 12.0, "plan_10b5_1": False, "acq_disp": "A"},
        {**base, "trans_date": "2026-06-02", "code": "S", "shares": 200, "price": 11.0, "plan_10b5_1": False},
        {**base, "trans_date": "2026-06-03", "code": "S", "shares": 200, "price": 13.0, "plan_10b5_1": True},
        {**base, "trans_date": "2026-06-03", "code": "M", "shares": 999, "price": 1.0, "plan_10b5_1": False},
        {**base, "trans_date": "2026-06-03", "code": "G", "shares": 50, "price": 0.0, "plan_10b5_1": False},
        {**base, "trans_date": "2026-06-03", "code": "F", "shares": 40, "price": 11.0, "plan_10b5_1": False},
        {**base, "trans_date": "2026-06-04", "code": "S", "shares": 10, "price": 1100.0, "plan_10b5_1": False},  # error
        {**base, "trans_date": "2026-06-04", "code": "P", "shares": 1000, "price": 11.0, "plan_10b5_1": False,
         "officer": False, "ten_pct": True, "owner_cik": "7", "title": None},                     # solo accionista 10 %
        {**base, "trans_date": "2024-01-02", "code": "P", "shares": 500, "price": 11.0, "plan_10b5_1": False},   # > 12 m
    ]
    return pd.DataFrame(f)


def test_clasificar_tipos():
    assert AV.clasificar("P", False) == "compra" and AV.clasificar("S", False) == "venta"
    assert AV.clasificar("S", True) == "venta_plan" and AV.clasificar("M", False) == "opciones"
    assert AV.clasificar("G", True) == "regalo" and AV.clasificar("A", False) == "concesion"
    assert AV.clasificar("F", False) == "fiscal" and AV.clasificar("J", False) == "otro" and AV.clasificar(None, False) == "otro"


def test_medias_ponderadas_filtros_y_descartes():
    cierre = _serie(11.0, n=800)
    d = AV.preparar_ops(_ops(), [], cierre)
    assert d["descartada"].sum() == 1                       # la venta a 1100 (> 50 % del cierre)
    m = AV.medias_12m(d, HOY, 11.0)
    assert m["compras"]["lineas"] == 2                      # sin la del accionista 10 % ni la de 2024
    assert abs(m["compras"]["precio_medio"] - (100 * 10 + 300 * 12) / 400) < 1e-9
    assert m["ventas_sin_plan"]["precio_medio"] == 11.0
    assert abs(m["ventas"]["precio_medio"] - 12.0) < 1e-9   # (200·11 + 200·13) / 400
    assert abs(m["compras"]["vs_actual"] - 100 * (11 / 11.5 - 1)) < 1e-9
    assert set(m["otras"]) == {AV.CAT["opciones"], AV.CAT["regalo"], AV.CAT["fiscal"]}


def test_split_posterior_reescala_precio_y_acciones():
    d = AV.preparar_ops(_ops().iloc[:1], [{"fecha": "2026-07-01", "factor": 2.0}, {"fecha": "2020-01-01", "factor": 3.0}])
    assert d["precio_aj"].iloc[0] == 5.0 and d["acciones_aj"].iloc[0] == 200
    assert AV.media_ponderada(pd.Series([1.0, 3.0]), pd.Series([0.0, 0.0])) is None


def test_agrupar_por_persona_dia_tipo():
    d = AV.preparar_ops(_ops(), [], _serie(11.0, n=800))
    g = AV.agrupar(d)
    assert set(g["cat"]) == {"compra", "venta", "venta_plan"}
    dia = g[(g["trans_date"] == "2026-06-02") & (g["cat"] == "compra")].iloc[0]
    assert dia["acciones"] == 300 and dia["precio"] == 12
    assert "accionista > 10 %" in set(g["cargo"]) and not g[g["owner_cik"] == "7"]["directivo"].iloc[0]


def test_parse_xml_form4_plan_por_nota():
    xml = """<ownershipDocument><documentType>4</documentType><issuer><issuerCik>0000000001</issuerCik></issuer>
    <reportingOwner><reportingOwnerId><rptOwnerCik>0009</rptOwnerCik><rptOwnerName>Ana</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>CEO</officerTitle></reportingOwnerRelationship></reportingOwner>
    <nonDerivativeTable>
     <nonDerivativeTransaction><transactionDate><value>2026-10-01</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode><footnoteId id="F1"/></transactionCoding>
      <transactionAmounts><transactionShares><value>10</value></transactionShares>
      <transactionPricePerShare><value>5.5</value></transactionPricePerShare>
      <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction>
     <nonDerivativeTransaction><transactionDate><value>2026-10-01</value></transactionDate>
      <transactionCoding><transactionCode>G</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>3</value></transactionShares>
      <transactionPricePerShare><value>0</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
    </nonDerivativeTable>
    <footnotes><footnote id="F1">Sold pursuant to a Rule 10b5-1 trading plan adopted on May 1.</footnote></footnotes>
    </ownershipDocument>"""
    r = F4.parse_xml(xml, "acc", "2026-10-03", "AAA")
    assert len(r) == 2 and r[0]["plan_10b5_1"] and not r[1]["plan_10b5_1"]
    assert r[0]["title"] == "CEO" and r[0]["owner_name"] == "Ana" and r[1]["code"] == "G"


# ------------------------------------------------------------------------------------------ 13F
def test_resumen_13f_cambios_aprox_y_errores_de_unidades():
    per = pd.to_datetime(["2026-03-31", "2026-06-30"])
    filas = []
    for p, k in zip(per, (100.0, 150.0)):
        filas.append({"ticker": "AAA", "period": p, "cik": "1", "gestor": "Fondo A", "shares": k, "value": k * 10,
                      "filing_date": p + pd.Timedelta(days=40)})
    filas.append({"ticker": "AAA", "period": per[1], "cik": "2", "gestor": "Fondo B", "shares": 50.0, "value": 500.0,
                  "filing_date": per[1] + pd.Timedelta(days=40)})
    filas.append({"ticker": "AAA", "period": per[1], "cik": "3", "gestor": "Erróneo", "shares": 1e9, "value": 10.0,
                  "filing_date": per[1] + pd.Timedelta(days=40)})
    cierre = pd.Series(10.0, index=pd.bdate_range("2026-01-01", "2026-09-30"))
    r = AV.resumen_13f(pd.DataFrame(filas), cierre)
    assert [f["gestor"] for f in r["top"]] == ["Fondo A", "Fondo B"]         # el erróneo, fuera
    ch = r["top"][0]["cambios"][-1]
    assert ch["delta"] == 50 and ch["pct"] == 50 and ch["importe_aprox"] == 500
    assert r["top"][1]["cambios"][-1]["nueva"]
    assert r["agregado"][-1]["gestores_comunes"] == 1 and r["agregado"][-1]["suben"] == 1
    # split posterior: el precio del trimestre vuelve a la escala de entonces
    assert AV.precio_trimestre(cierre, per[1], [{"fecha": "2026-08-01", "factor": 2.0}]) == 20
    assert AV.resumen_13f(pd.DataFrame(), cierre) is None


# ------------------------------------------------------------------------------------------ analistas
def test_analistas_resumen_y_consenso():
    raw = {"financialData": {"targetMeanPrice": {"raw": 120.0}, "targetHighPrice": {"raw": 150.0},
                             "targetLowPrice": {"raw": 80.0}, "numberOfAnalystOpinions": {"raw": 20},
                             "recommendationMean": {"raw": 2.1}},
           "recommendationTrend": {"trend": [{"period": "0m", "strongBuy": 5, "buy": 7, "hold": 6, "sell": 1, "strongSell": 1}]},
           "upgradeDowngradeHistory": {"history": [
               {"epochGradeDate": int(pd.Timestamp("2026-11-01").timestamp()), "firm": "X", "fromGrade": "Hold",
                "toGrade": "Buy", "action": "up", "currentPriceTarget": 130},
               {"epochGradeDate": int(pd.Timestamp("2026-01-01").timestamp()), "firm": "Y", "action": "down"}]}}
    a = YA.resumir(raw)
    r = AV.resumen_analistas(a, 100.0, HOY)
    assert r["consenso"] == {"comprar": 12, "mantener": 6, "vender": 2, "total": 20}
    assert abs(r["objetivo"]["medio"]["vs_actual"] - 20) < 1e-9 and abs(r["objetivo"]["bajo"]["vs_actual"] + 20) < 1e-9
    assert r["n_suben"] == 1 and r["n_bajan"] == 0 and len(r["cambios"]) == 1      # el de enero queda fuera de 90 días
    assert AV.resumen_analistas(None, 100.0, HOY) is None


# ------------------------------------------------------------------------------------------ guardas
def test_ficha_no_cae_sin_datos_ni_con_datos_rotos(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_DATA_ROOT", str(tmp_path))
    X = AV.cargar()
    assert {"error_volumen", "error_form4", "error_13f", "error_analistas"} <= set(X)
    r = {"nombre": "Aaa", "grupo": "Acciones", "precio": 10.0, "moneda": "USD"}
    h = AV.ficha_v2("AAA", r, X, date(2026, 11, 16))
    assert "s/d" in h and "Opinión de terceros" in h
    assert "s/d" in AV.ficha_v2("AAA", r, None)
    roto = {"volumen": "no es un DataFrame", "form4": 42, "f13": object(), "analistas": {"acciones": {"AAA": {"x": 1}}}}
    h2 = AV.ficha_v2("AAA", r, roto, date(2026, 11, 16))
    assert "s/d" in h2


def test_ficha_completa_sintetica_svg_y_etf():
    idx = pd.bdate_range(end=HOY, periods=400)
    px = pd.Series(np.linspace(8, 12, 400), index=idx)
    X = {"volumen": pd.DataFrame({"AAA": 1000.0, "XLK": 500.0}, index=idx), "cierre": pd.DataFrame({"AAA": px, "XLK": px}),
         "splits": {}, "form4": _ops().assign(trans_date=lambda d: pd.to_datetime(d["trans_date"])),
         "meta_form4": {"desde": "2025-01-01"}, "f13": pd.DataFrame(), "analistas": {"acciones": {}}}
    r = {"nombre": "Aaa", "grupo": "Acciones", "precio": 12.0, "moneda": "USD"}
    h = AV.ficha_v2("AAA", r, X, date(2026, 11, 16))
    assert h.count("<svg") == 1 and 'class="av-c"' in h and 'class="av-vp"' in h and "compra (P)" in h
    e = AV.ficha_v2("XLK", {"nombre": "ETF tecnología (XLK)", "grupo": "ETF sectoriales", "precio": 12.0, "moneda": "USD"}, X)
    assert "<svg" in e and "Form 4" not in e and "analistas" not in e.lower().replace("volumen, directivos, gestoras y analistas", "")
