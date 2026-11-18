"""Alertas de flujos (src/report/alertas.py) con datos SINTÉTICOS (sin red): clasificación del volumen, días especiales,
filtros de Form 4, 13D/13G, 13F, recompras / buyback yield y deduplicación de las notificaciones."""
import json

import numpy as np
import pandas as pd

from src.ingest import sec_flujos as SF
from src.report import alertas as AL

HOY = pd.Timestamp("2026-11-16")


def _base(n=400, fin=HOY, seed=1):
    """Volumen ~1 M con ruido log-normal y precio con paseo aleatorio suave (σ diaria ≈ 1 %)."""
    rng = np.random.default_rng(seed)
    ix = pd.bdate_range(end=fin, periods=n)
    v = pd.Series(1e6 * np.exp(rng.normal(0, 0.2, n)), index=ix)
    c = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=ix)
    return v, c


def _dia(v, c, k, mult, ret, clv=None):
    v, c = v.copy(), c.copy()
    f = v.index[k]
    v.iloc[k] = mult * 1e6
    c.iloc[k:] = c.iloc[k:] * (1 + ret) / (c.iloc[k] / c.iloc[k - 1]) if k else c.iloc[k:]
    h, lo = c * 1.01, c * 0.99
    if clv is not None:
        rango = c.iloc[k] * 0.04
        lo.iloc[k] = c.iloc[k] - clv * rango
        h.iloc[k] = lo.iloc[k] + rango
    return v, c, h, lo, f


# ------------------------------------------------------------------------------------------ volumen
def test_volumen_clasificacion_sube_baja_plano_y_cierre_en_rango():
    v, c = _base()
    for ret, clase, clv, txt in ((0.05, "sube", 0.9, "máximo"), (-0.05, "baja", 0.1, "mínimo"), (0.001, "plano", 0.5, "mitad")):
        vv, cc, h, lo, f = _dia(v, c, -1, 4.0, ret, clv)
        d = AL.senal_volumen(vv, cc, h, lo)
        r = d.loc[f]
        assert r["nivel"] == 2 and r["ratio"] > 3 and r["z"] > 3
        assert r["clase"] == clase
        fr = AL.frase_volumen(r.to_dict())
        assert txt in fr and AL.LECTURA[clase] in fr


def test_volumen_moderada_y_sin_alerta():
    v, c = _base()
    vv, cc, h, lo, f = _dia(v, c, -1, 2.3, 0.0)
    assert AL.senal_volumen(vv, cc, h, lo).loc[f, "nivel"] == 1
    vv, cc, h, lo, f = _dia(v, c, -1, 1.3, 0.0)
    assert AL.senal_volumen(vv, cc, h, lo).loc[f, "nivel"] == 0


def test_volumen_5_sesiones_una_alerta_por_racha():
    v, c = _base()
    v.iloc[-5:] = 2.2e6     # 5 sesiones altas (× ≈ 2,1): moderada; la alerta sale una vez, no cada día
    d = AL.senal_volumen(v, c)
    ev = [e for e in AL.eventos_volumen("AAA", d, {}, None, HOY - pd.Timedelta(days=30)) if e["tipo"] == "volumen_5s"]
    assert len(ev) == 1 and ev[0]["fuerza"] == 1


# ------------------------------------------------------------------------------------------ días especiales
def test_dias_especiales_vencimientos_russell_msci_resultados_y_split():
    ix = pd.bdate_range("2026-01-01", "2026-12-31").drop(pd.Timestamp("2026-06-19"))   # Juneteenth (festivo)
    esp = AL.dias_especiales(ix, [{"fecha": "2026-11-04"}], [{"fecha": "2026-10-01", "factor": 6.665}])
    assert "triple witching" in esp[pd.Timestamp("2026-03-20")]            # 3.er viernes de marzo
    assert "triple witching" in esp[pd.Timestamp("2026-06-18")]            # viernes festivo → jueves
    assert pd.Timestamp("2026-06-19") not in esp
    assert "Russell" in esp[pd.Timestamp("2026-06-26")]                    # último viernes de junio
    assert "MSCI" in esp[pd.Timestamp("2026-11-30")]                       # último día hábil de noviembre
    assert "resultados" in esp[pd.Timestamp("2026-11-04")] and "resultados" in esp[pd.Timestamp("2026-11-05")]
    assert "split" in esp[pd.Timestamp("2026-10-01")] and "split" in esp[pd.Timestamp("2026-10-07")]
    assert pd.Timestamp("2026-11-06") not in esp and pd.Timestamp("2026-03-19") not in esp


def test_dia_especial_y_sesion_incompleta_no_alertan():
    v, c = _base(fin=pd.Timestamp("2026-03-20"))
    vv, cc, h, lo, f = _dia(v, c, -1, 5.0, 0.05)
    d = AL.senal_volumen(vv, cc, h, lo)
    esp = AL.dias_especiales(d.index)
    ev = AL.eventos_volumen("AAA", d, esp, None, f - pd.Timedelta(days=5))
    e = [x for x in ev if x["tipo"] == "volumen"][0]
    assert e["fuerza"] == 0 and "triple witching" in e["especial"] and e["nivel"] == 2
    v, c = _base()
    vv, cc, h, lo, f = _dia(v, c, -1, 5.0, 0.05)
    d = AL.senal_volumen(vv, cc, h, lo)
    e = [x for x in AL.eventos_volumen("AAA", d, {}, f, f - pd.Timedelta(days=5)) if x["tipo"] == "volumen"][0]
    assert e["fuerza"] == 0 and "incompleto" in e["especial"]
    e = [x for x in AL.eventos_volumen("AAA", d, {}, None, f - pd.Timedelta(days=5)) if x["tipo"] == "volumen"][0]
    assert e["fuerza"] == 2 and e["especial"] is None


# ------------------------------------------------------------------------------------------ Form 4
def _f4(**kw):
    base = dict(accession="a", filing_date=pd.Timestamp("2026-11-12"), trans_date="2026-11-10", issuer_cik="1",
                ticker="AAA", owner_cik="9", owner_name="Pérez Ana", title="CFO", director=False, officer=True,
                ten_pct=False, code="S", acq_disp="D", shares=1000, price=100.0, plan_10b5_1=False, fuente="t",
                owned_after=np.nan)
    return {**base, **kw}


def test_form4_filtros():
    ops = pd.DataFrame([
        _f4(owner_cik="1", code="P", shares=20_000, price=100.0, officer=False, ten_pct=True, title=None, acq_disp="A"),  # 2 M$ 10 %
        _f4(owner_cik="2", code="P", shares=500, price=100.0, acq_disp="A"),                                       # 50 mil $: no
        _f4(owner_cik="3", code="S", shares=200_000, price=100.0, plan_10b5_1=True),                                # 20 M$ con plan: no
        _f4(owner_cik="4", code="A", shares=900_000, price=0.0, acq_disp="A"),                                      # concesión: no
        _f4(owner_cik="5", code="F", shares=100_000, price=100.0),                                                  # retención: no
        _f4(owner_cik="6", code="S", shares=120_000, price=100.0, owned_after=5_000_000),                          # 12 M$ sin plan
        _f4(owner_cik="7", code="S", shares=20_000, price=100.0, owned_after=20_000),                              # 2 M$, 50 % de lo suyo
        _f4(owner_cik="8", code="S", shares=600_000, price=100.0, owned_after=1e7),                                # 60 M$ sin plan
        _f4(owner_cik="9", code="S", shares=1_000, price=100.0, owned_after=0),                                    # 100 mil $: no
        _f4(owner_cik="10", code="S", shares=100_000, price=100.0, director=False, officer=False, ten_pct=False),   # ni directivo ni 10 %
    ])
    ev = {e["clave"].split("|")[2]: e for e in AL.eventos_form4("AAA", ops, None, None)}
    assert set(ev) == {"1", "6", "7", "8"}
    assert ev["1"]["fuerza"] == 2 and "COMPRA" in ev["1"]["frase"] and "10 %" in ev["1"]["frase"]
    assert ev["6"]["fuerza"] == 1 and "SIN plan" in ev["6"]["frase"]
    assert ev["7"]["fuerza"] == 1 and "50 % de esa forma de tenencia" in ev["7"]["frase"]
    assert ev["8"]["fuerza"] == 2
    assert all(e["fecha"] == pd.Timestamp("2026-11-12") for e in ev.values())   # fecha = cuando se hizo público


def test_form4_owned_after_en_xml():
    xml = """<ownershipDocument><documentType>4</documentType><issuer><issuerCik>0001</issuerCik></issuer>
<reportingOwner><reportingOwnerId><rptOwnerCik>0009</rptOwnerCik><rptOwnerName>X</rptOwnerName></reportingOwnerId>
<reportingOwnerRelationship><isOfficer>1</isOfficer></reportingOwnerRelationship></reportingOwner>
<nonDerivativeTable><nonDerivativeTransaction><transactionDate><value>2026-11-10</value></transactionDate>
<transactionCoding><transactionCode>S</transactionCode></transactionCoding><transactionAmounts>
<transactionShares><value>10</value></transactionShares><transactionPricePerShare><value>5</value></transactionPricePerShare>
<transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts>
<postTransactionAmounts><sharesOwnedFollowingTransaction><value>90</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
</nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""
    from src.ingest import sec_form4_detalle as F4
    r = F4.parse_xml(xml, "acc", "2026-11-12", "AAA")
    assert r[0]["owned_after"] == 90
    assert "owned_after" in F4.COLS


# ------------------------------------------------------------------------------------------ 13D / 13G
def _dg(**kw):
    base = dict(ticker="AAA", issuer_cik="1", accession="x", form="SCHEDULE 13G", filing_date=pd.Timestamp("2026-11-01"),
                event_date=pd.Timestamp("2026-10-30"), filer_cik="7", filer="Gestora", pct=6.0, acciones=1e6,
                reorganizacion=False, xml=True)
    return {**base, **kw}


def test_13dg_reglas():
    dg = pd.DataFrame([
        _dg(accession="a1", form="SCHEDULE 13D", filer_cik="1", filer="Activista", pct=8.0),
        _dg(accession="a2", form="SCHEDULE 13G", filer_cik="2", pct=6.0, filing_date=pd.Timestamp("2026-05-01")),
        _dg(accession="a3", form="SCHEDULE 13G/A", filer_cik="2", pct=4.0),                      # baja del 5 %
        _dg(accession="a4", form="SCHEDULE 13G/A", filer_cik="3", pct=0.0, reorganizacion=True), # reorganización
        _dg(accession="a5", form="SCHEDULE 13G", filer_cik="4", pct=7.0, filing_date=pd.Timestamp("2026-05-01")),
        _dg(accession="a6", form="SCHEDULE 13G/A", filer_cik="4", pct=7.4),                       # +0,4 pp: nada
        _dg(accession="a7", form="SCHEDULE 13D/A", filer_cik="1", pct=11.0, filing_date=pd.Timestamp("2026-11-10")),
        _dg(accession="b1", ticker="BBB", form="SCHEDULE 13D", filer_cik="9", pct=30.0),          # otra empresa
    ])
    ev = {e["clave"].split("|")[2]: e for e in AL.eventos_13dg("AAA", dg)}
    assert "b1" not in ev
    assert ev["a1"]["fuerza"] == 2 and "13D" in ev["a1"]["frase"]
    assert ev["a2"]["fuerza"] == 1 and ev["a3"]["fuerza"] == 1 and "por debajo del 5 %" in ev["a3"]["frase"]
    assert ev["a4"]["fuerza"] == 0 and "reorganización" in ev["a4"]["frase"]
    assert ev["a6"]["fuerza"] == 0
    assert ev["a7"]["fuerza"] == 2 and "sube al 11,0 %" in ev["a7"]["frase"]


def test_parse_13dg_xml_y_reorganizacion():
    xml = """<?xml version="1.0"?><edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13g"><headerData><submissionType>SCHEDULE 13G/A</submissionType>
<filerInfo><filer><filerCredentials><cik>0000102909</cik></filerCredentials></filer></filerInfo></headerData><formData>
<coverPageHeader><eventDateRequiresFilingThisStatement>03/13/2026</eventDateRequiresFilingThisStatement><issuerInfo><issuerCik>0001543151</issuerCik></issuerInfo></coverPageHeader>
<coverPageHeaderReportingPersonDetails><reportingPersonName>The Vanguard Group</reportingPersonName>
<reportingPersonBeneficiallyOwnedAggregateNumberOfShares>0</reportingPersonBeneficiallyOwnedAggregateNumberOfShares>
<classPercent>0</classPercent><comments>Vanguard went through an internal realignment.</comments></coverPageHeaderReportingPersonDetails></formData></edgarSubmission>"""
    p = SF.parse_13dg(xml)
    assert p["issuer_cik"] == "1543151" and p["filer_cik"] == "102909" and p["pct"] == 0 and p["reorganizacion"]
    assert p["event_date"] == "2026-03-13" and p["filer"] == "The Vanguard Group"


# ------------------------------------------------------------------------------------------ 13F
def test_13f_cambios_reorganizacion_e_informe_ausente():
    filas = []
    for p, f in (("2026-03-31", "2026-05-10"), ("2026-06-30", "2026-08-10")):
        def pos(cik, nom, sh):
            filas.append({"ticker": "AAA", "period": pd.Timestamp(p), "cik": cik, "accession": cik + p,
                          "filing_date": pd.Timestamp(f), "gestor": nom, "shares": sh, "value": sh * 100.0})
        pos("1", "Gestora Uno", 1_000_000 if p < "2026-06" else 2_000_000)   # +100 %, 1 % de la empresa: fuerte
        pos("2", "Gestora Dos", 1_000_000 if p < "2026-06" else 1_100_000)   # +10 %: nada
        if p < "2026-06":
            pos("3", "VANGUARD GROUP INC", 3_000_000)                        # cambia de CIK: reorganización
            pos("4", "Ausente SA", 800_000)                                  # no presenta en jun: informe ausente
            pos("5", "Vende Todo LLC", 500_000)                              # presenta en jun sin esta acción: sale
        else:
            pos("6", "Vanguard Capital Management", 3_000_000)
    pos13 = pd.DataFrame(filas)
    presentes = {pd.Timestamp("2026-03-31"): {"1", "2", "3", "4", "5"}, pd.Timestamp("2026-06-30"): {"1", "2", "5", "6"}}
    cie = pd.Series(100.0, index=pd.bdate_range("2026-01-01", "2026-09-30"))
    ev = AL.eventos_13f("AAA", pos13, cie, None, 1e8, presentes=presentes)
    por = {e["clave"].split("|")[3]: e for e in ev if e["tipo"] == "13f"}
    assert set(por) == {"1", "5"}
    assert por["1"]["fuerza"] == 2 and "+100 %" in por["1"]["frase"]
    assert por["5"]["fuerza"] == 1 and "ya no declara" in por["5"]["frase"]
    assert all("45 días" in e["frase"] for e in ev)
    assert por["1"]["fecha"] == pd.Timestamp("2026-08-10")
    assert any(e["tipo"] == "13f_agregado" for e in ev)


# ------------------------------------------------------------------------------------------ recompras
def _h(start, end, val, filed, form="10-Q"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


def test_recompras_trimestres_ttm_yield_y_acciones():
    pago = [_h("2025-01-01", "2025-03-31", 100, "2025-05-01"), _h("2025-01-01", "2025-06-30", 250, "2025-08-01"),
            _h("2025-01-01", "2025-09-30", 450, "2025-11-01"), _h("2025-01-01", "2025-12-31", 600, "2026-02-01", "10-K"),
            _h("2026-01-01", "2026-03-31", 2000, "2026-05-01"), _h("2026-01-01", "2026-06-30", 2000, "2026-08-01"),
            _h("2026-01-01", "2026-09-30", 2100, "2026-11-01"),
            _h("2026-01-01", "2026-03-31", 2000, "2026-08-01")]   # repetido en un 10-Q posterior: cuenta la 1.ª fecha
    q = AL.trimestres(pago)
    assert list(q["importe"]) == [100, 150, 200, 150, 2000, 0, 100]
    assert q.iloc[4]["publicado"] == pd.Timestamp("2026-05-01")
    acc = [{"end": "2025-10-25", "val": 1000, "filed": "2025-11-01"}, {"end": "2026-10-25", "val": 980, "filed": "2026-11-01"}]
    emp = {"hechos": {"us-gaap:PaymentsForRepurchaseOfCommonStock": pago, "dei:EntityCommonStockSharesOutstanding": acc}}
    cie = pd.Series(100.0, index=pd.bdate_range("2024-06-01", HOY))   # capitalización = 980 × 100 = 98 000
    rc = AL.recompras("AAA", emp, cie, None, HOY)
    assert rc["ttm"] == 150 + 2000 + 0 + 100
    assert abs(rc["yield"] - 2250 / 98_000) < 1e-12
    assert abs(rc["var_acciones_12m"] - (980 / 1000 - 1)) < 1e-12
    tipos = {e["clave"]: e for e in rc["eventos"]}
    fuerte = tipos["recompra|AAA|2026-03-31"]
    assert fuerte["fuerza"] == 2 and fuerte["fecha"] == pd.Timestamp("2026-05-01")   # 2000 / 100 000 = 2 %
    assert tipos["recompra|AAA|2026-06-30"]["frase"].startswith("Parón")


def test_recompras_split_en_acciones():
    acc = [{"end": "2025-11-01", "val": 100, "filed": "2025-11-05"}, {"end": "2026-11-01", "val": 1000, "filed": "2026-11-05"}]
    emp = {"hechos": {"dei:EntityCommonStockSharesOutstanding": acc}}
    cie = pd.Series(10.0, index=pd.bdate_range("2025-01-01", HOY))
    rc = AL.recompras("AAA", emp, cie, [{"fecha": "2026-06-01", "factor": 10.0}], HOY)
    assert abs(rc["var_acciones_12m"]) < 1e-12   # 100 antes del split 10:1 = 1000 después: sin cambio real


# ------------------------------------------------------------------------------------------ notificaciones
def _ev(clave, fuerza=2, fecha=HOY):
    return {"clave": clave, "fuerza": fuerza, "fecha": fecha, "ticker": "AAA", "frase": 'Algo "raro" <b>pasó</b>. Detalle.',
            "tipo": "volumen"}


def test_notificacion_deduplica_y_se_desactiva(tmp_path, monkeypatch):
    evs = [_ev("a"), _ev("b", fuerza=1), _ev("c", fecha=HOY - pd.Timedelta(days=30))]
    monkeypatch.setattr(AL, "cargar", lambda base=None: {})
    monkeypatch.setattr(AL, "calcular", lambda X=None, hoy=None: {"hoy": str(HOY.date()), "eventos": evs})
    monkeypatch.setenv("FIN_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("FIN_ALERTAS_NOTIFICAR", raising=False)
    est = tmp_path / "alertas" / "notificadas.json"
    m = AL.notificar()
    assert m.startswith("1 alerta fuerte: AAA") and '"' not in m and "<b>" not in m
    assert json.loads(est.read_text()) == {"a": str(HOY.date())}
    assert AL.notificar() == ""                       # la misma alerta no se repite
    evs.append(_ev("d"))
    assert AL.notificar().startswith("1 alerta")      # solo la nueva
    evs.append(_ev("e"))
    monkeypatch.setenv("FIN_ALERTAS_NOTIFICAR", "0")
    assert AL.notificar() == ""
    monkeypatch.delenv("FIN_ALERTAS_NOTIFICAR")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "alertas.json").write_text('{"notificar": false}')
    assert AL.notificar() == ""
    assert "e" not in json.loads(est.read_text())     # desactivada: no se apunta como notificada


# ------------------------------------------------------------------------------------------ HTML tolerante
def test_html_sin_datos_no_falla():
    assert "s/d" in AL.bloque_alertas(None)
    assert "s/d" in AL.ficha_flujos("AAA", None)
    R = {"hoy": str(HOY.date()), "eventos": [], "activos": {"AAA": {"eventos": [], "errores": {"volumen": "x"}}}}
    assert "sin alertas" in AL.bloque_alertas(R)
    assert "Flujos fuertes" in AL.ficha_flujos("AAA", R)


def test_calcular_con_fuentes_rotas_no_lanza(monkeypatch):
    R = AL.calcular({"error_volumen": "roto", "error_form4": "roto"}, HOY.date())
    assert R["eventos"] == [] and "volumen" in R["activos"]["UBER"]["errores"]
