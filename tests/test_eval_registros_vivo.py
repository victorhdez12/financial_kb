"""Evaluación congelada de los registros en vivo (docs/int/EVAL_registros_vivo.md): SOLO datos sintéticos.
Cada script recupera una señal plantada, no la encuentra sin señal, y en modo real sin ventanas cerradas no lee el
warehouse ni escribe nada."""
import hashlib
import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from scripts import eval_e1_vivo as EE
from scripts import eval_int11_vivo as EI
from scripts import eval_k1_vivo as EK


def _sin_warehouse(monkeypatch):
    from src.warehouse import db

    def no(*a, **k):
        raise AssertionError("el modo real sin ventanas cerradas no debe conectar al warehouse")
    monkeypatch.setattr(db, "connect", no)


# ================================================================ E1 / E1b
@pytest.fixture(scope="module")
def e1_con():
    reg, pib, hoy = EE.sintetico(señal=1.0)
    return EE.evaluar_todo(reg, pib, hoy)


@pytest.fixture(scope="module")
def e1_sin():
    reg, pib, hoy = EE.sintetico(señal=0.0)
    return EE.evaluar_todo(reg, pib, hoy)


def test_e1_recupera_senal(e1_con):
    for k in ("E1_12", "E1_6"):
        v = e1_con[k]
        assert v["episodios_nuevos"] >= EE.MIN_EPISODIOS
        assert v["principal"]["dauc"] > 0.1 and v["p1"]["p"] < EE.ALFA and v["principal"]["dlogloss"] < 0
        assert v["veredicto"] == "CONFIRMADO"
        assert v["integridad"]["max_dif_p_A"] < EE.TOL_P
        assert {"m4", "p2_dauc", "p3_dauc", "por_episodio"} <= set(v)


def test_e1_sin_senal_no_confirma(e1_sin):
    for k in ("E1_12", "E1_6"):
        v = e1_sin[k]
        assert v["p1"]["p"] >= EE.ALFA and v["veredicto"] != "CONFIRMADO"
        assert abs(v["principal"]["dauc"]) < 0.1


def test_e1_menos_de_12_episodios_sin_veredicto():
    r = {"episodios_nuevos": 11, "principal": {"dauc": 0.3, "dlogloss": -0.1, "calib_A": {"pendiente": 1}},
         "p1": {"p": 0.001}, "por_episodio": {}}
    assert EE.veredicto(r)["veredicto"].startswith("DESCRIPTIVO")
    r["episodios_nuevos"] = 12
    r["por_episodio"] = {0: {"eventos": 9, "dauc": 0.2, "dauc_sin_el": 0.2}, 1: {"eventos": 5, "dauc": 0.1, "dauc_sin_el": 0.3}}
    assert EE.veredicto(r)["veredicto"] == "CONFIRMADO"
    r["principal"]["dlogloss"] = 0.001
    assert EE.veredicto(r)["veredicto"] == "REFUTADO"
    r["principal"]["dlogloss"], r["p1"]["p"] = -0.1, 0.2
    assert EE.veredicto(r)["veredicto"].startswith("NI REFUTADO")


def test_e1_calendario_y_episodios():
    assert EE.fin_ventana_pib(pd.Timestamp("2026-11-30"), 12) == pd.Timestamp("2028-03-15")
    assert EE.fin_ventana_pib(pd.Timestamp("2026-11-30"), 6) == pd.Timestamp("2027-09-13")
    e = pd.Series(pd.to_datetime(["2030-03-31", "2030-09-30", "2031-06-30", "2031-06-30", "2035-12-31"]))
    ep = EE.episodios(e)
    assert ep.nunique() == 3 and ep[pd.Timestamp("2030-03-31")] == ep[pd.Timestamp("2030-09-30")]


def test_e1_choque_declarado_tarde_no_excluye():
    d = pd.DataFrame({"fecha": pd.to_datetime(["2040-01-31", "2040-02-29"]),
                      "registrado": ["2040-02-02T09:00:00+00:00", "2040-03-02T09:00:00+00:00"]})
    x = [{"desde": "2040-01-01", "hasta": "2040-12-31", "declarado": "2040-02-15T00:00:00+00:00"}]
    assert EE.choques(d, x).tolist() == [False, True]


def test_e1_real_sin_ventanas_no_escribe(tmp_path, monkeypatch, capsys):
    log = tmp_path / "e1_vivo.jsonl"
    log.write_text(json.dumps({"origen": "2026-11-30", "pais": "DEU", "p_L": 0.1}) + "\n")
    monkeypatch.setattr(EE, "LOG", log)
    monkeypatch.setattr(EE, "SALIDA", tmp_path / "out.json")
    monkeypatch.setattr(EE, "VEREDICTO", {h: tmp_path / f"v{h}.json" for h in (12, 6)})
    _sin_warehouse(monkeypatch)
    assert EE.main(["--hoy", "2027-06-01"]) == 0
    assert "sin ventanas cerradas" in capsys.readouterr().out
    assert sorted(p.name for p in tmp_path.iterdir()) == ["e1_vivo.jsonl"]
    monkeypatch.setattr(EE, "LOG", tmp_path / "no_existe.jsonl")
    assert EE.main([]) == 0


# ================================================================ K1v
@pytest.fixture(scope="module")
def k1():
    out = {}
    for s in (1.0, 0.0):
        reg, ini, fe, hasta = EK.sintetico(señal=s)
        out[s] = EK.evaluar(reg, ini, hasta, fe)
    return out


def test_k1_recupera_senal_y_sin_senal_no(k1):
    a, b = k1[1.0], k1[0.0]
    assert a["principal"]["inicios"] >= EK.MIN_INICIOS and a["inicios_previos_excluidos"] > 0
    assert a["principal"]["dauc_estrat"] > 0.1 and a["principal"]["placebo"]["p"] < EK.ALFA
    assert a["veredicto"] == "CONFIRMADO"
    assert b["principal"]["placebo"]["p"] >= EK.ALFA and b["veredicto"] != "CONFIRMADO"
    assert {"sens_con_previos", "sens_usa_2023", "sens_sin_fin_nld"} <= set(a)
    assert a["sens_con_previos"]["inicios"] == a["principal"]["inicios"] + a["inicios_previos_excluidos"]


def test_k1_previo_y_cierre():
    assert EK.previo("DEU", 2027, "2027-07-15T09:00:00+00:00", {})                       # sin fecha → previo
    assert EK.previo("DEU", 2027, "2027-07-15T09:00:00+00:00", {("DEU", 2027): "2027-07"})  # mismo mes → previo
    assert not EK.previo("DEU", 2027, "2027-07-15T09:00:00+00:00", {("DEU", 2027): "2027-08"})
    reg = pd.DataFrame({"pais": ["DEU", "DEU"], "t": [2026, 2027]})
    assert EK.cerrados(reg, 2026).empty and len(EK.cerrados(reg, 2027)) == 1
    r = {"principal": {"inicios": 19}}
    assert EK.veredicto(r)["veredicto"].startswith("DESCRIPTIVO")


def test_k1_real_sin_ventanas_no_escribe(tmp_path, monkeypatch, capsys):
    log = tmp_path / "k1_vivo.jsonl"
    log.write_text(json.dumps({"pais": "DEU", "t": 2026, "p_L": 0.02, "p_K": 0.03}) + "\n")
    monkeypatch.setattr(EK, "LOG", log)
    monkeypatch.setattr(EK, "SALIDA", tmp_path / "out.json")
    monkeypatch.setattr(EK, "VEREDICTO", tmp_path / "v.json")
    _sin_warehouse(monkeypatch)
    assert EK.main([]) == 0
    assert "sin ventanas cerradas" in capsys.readouterr().out
    assert [p.name for p in tmp_path.iterdir()] == ["k1_vivo.jsonl"]


# ================================================================ INT-11 v3.1
def test_int11_recupera_descalibracion_y_k2():
    e, re = EI.sintetico(escala_real=1.7, k2_informativa=True, años=12)
    assert EI.detecta(EI.evaluar(e, re)) == {"descalibracion": True, "k2_habilidad": True}
    e, re = EI.sintetico(escala_real=1.0, k2_informativa=False, años=12)
    r = EI.evaluar(e, re)
    assert EI.detecta(r) == {"descalibracion": False, "k2_habilidad": False}
    assert set(r["activos_pendientes"]) == set()          # V8 (5-nov-2026): los 4 activos nuevos se miden
    assert r["principal_diciembre"]["K1_bolsa"]["n"] == 12 * 14
    assert r["principal_diciembre"]["K1_bolsa_sin_JPN"]["paises"] == 13


def test_int11_pit_crps():
    q = np.linspace(-0.49, 0.49, 99)
    assert EI.pit(-1, q) == 0.005 and EI.pit(1, q) == 0.995 and abs(EI.pit(0.0, q) - 0.5) < 1e-9
    assert EI.crps_cuantiles(0.0, q) < EI.crps_cuantiles(0.4, q)


def test_int11_cerrada_e_integridad(tmp_path):
    o = {"ventana_objetivo": {"desde": "2026-12-01", "hasta": "2027-11-30"}}
    assert not EI.cerrada(o, "2028-02-29") and EI.cerrada(o, "2028-03-01")
    c = tmp_path / "vivo"
    c.mkdir()
    (c / "SERIE").write_text("int11_v3_1\n")
    texto = json.dumps({"serie_registro": "int11_v3_1", "emision": "2026-11-20", "ventana_objetivo": o["ventana_objetivo"],
                        "paises": {}})
    (c / "2026-11.json").write_text(texto)
    (c / "indice.csv").write_text("mes,archivo,sha256\n2026-11,2026-11.json," +
                                  hashlib.sha256(texto.encode()).hexdigest() + "\n")
    assert len(EI.leer_emisiones(c)) == 1
    (c / "2026-11.json").write_text(texto + " ")
    with pytest.raises(SystemExit):
        EI.leer_emisiones(c)


def test_int11_real_sin_ventanas_no_escribe(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(EI, "CARPETA", tmp_path / "no_existe")
    monkeypatch.setattr(EI, "REALIZADO", tmp_path / "realizado")
    monkeypatch.setattr(EI, "SALIDA", tmp_path / "out.json")
    _sin_warehouse(monkeypatch)
    assert EI.main([]) == 0
    assert "sin ventanas cerradas" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_int11_lectura_realizado_con_warehouse_sintetico():
    """Fontanería de la lectura con un warehouse INVENTADO en memoria (USA y JPN, fechas inventadas)."""
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest (series_id varchar, date date, value double)")
    meses = pd.date_range("2016-01-01", "2029-12-01", freq="MS")   # AQR en %
    dias = pd.date_range("2016-01-01", "2029-12-31", freq="B")
    filas = [("aqr_rf_risk_free_rate_m", d, 0.2) for d in meses]
    for c in ("usa", "jpn"):
        filas += [(f"aqr_mkt_{c}_m", d, 0.5) for d in meses]
        filas += [(f"oecd_share_{c}", d, 100 * 1.004 ** i) for i, d in enumerate(meses)]
        filas += [(f"oecd_cpi_{c}_idx", d, 100 * 1.002 ** i) for i, d in enumerate(meses)]
    filas += [("DEXJPUS", d, 150.0) for d in dias]
    con.executemany("insert into obs_latest values (?, ?, ?)", filas)
    o = {"_mes": "2026-11", "ventana_objetivo": {"desde": "2026-12-01", "hasta": "2027-11-30"},
         "paises": {"USA": {}, "JPN": {}}}
    r = EI.leer_realizado_emision(con, o)
    nominal = (1.007 ** 12) - 1
    infl = 1.002 ** 12 - 1
    for c in ("USA", "JPN"):
        assert r["bolsa"][c]["usada"] == "principal"
        assert abs(r["bolsa"][c]["real"] - ((1 + nominal) / (1 + infl) - 1)) < 1e-9
        assert r["inflacion"][c]["y"] == 0
    assert r["bolsa"]["JPN"]["descriptiva_medias"] is not None and len(r["sha256_series"]) == 64


# ---------------------------------------------------------------- INT-11: activos nuevos y semáforo (borrador)
def test_int11_retraso_por_activo_y_activos_aprobados():
    o = {"ventana_objetivo": {"desde": "2027-01-01", "hasta": "2027-12-31"}}
    assert EI.cerrada(o, "2028-04-01", "oro") and not EI.cerrada(o, "2028-04-01", "vivienda")
    assert EI.cerrada(o, "2029-01-01", "vivienda")
    assert EI.MEDIDAS_NUEVAS_APROBADAS is True and EI.ACTIVOS_MEDIDOS == ("bolsa", "bonos", "letras", "vivienda", "oro")


def test_int11_bandas_congeladas_integridad(tmp_path):
    b = EI.bandas()
    assert set(b["10"]) >= {"bolsa", "bonos", "letras", "vivienda", "oro", "S5"}
    assert b["10"]["S5"]["p2_5"] < 0.9 < b["10"]["S5"]["p97_5"]
    f = tmp_path / "s.json"
    f.write_text(EI.SEMAFORO.read_text() + " ")
    with pytest.raises(SystemExit):
        EI.bandas(f)


def test_int11_semaforo_y_contraste_sintetico(monkeypatch):
    monkeypatch.setattr(EI, "ACTIVOS_MEDIDOS", EI.ACTIVOS)
    e, re = EI.sintetico(escala_real=1.0, k2_informativa=False, años=12)
    r = EI.evaluar(e, re)
    s = r["semaforo"]
    assert s["S5"]["años"] == 12 and s["S5"]["contraste_10_años"]["estado"] == "NO SE RECHAZA LA CALIBRACIÓN"
    assert all(s[a]["color"] in ("verde", "ámbar") for a in EI.ACTIVOS)
    assert r["principal_diciembre"]["K1_oro"]["n"] == 12 * 14
    e, re = EI.sintetico(escala_real=1.7, k2_informativa=False, años=12)
    s = EI.evaluar(e, re)["semaforo"]
    assert s["S5"]["color"] == "rojo" and s["S5"]["contraste_10_años"]["estado"] == "DESCALIBRADO EN VIVO"
    assert s["S5"]["contraste_10_años"]["lado"] == "abanico estrecho"
    e, re = EI.sintetico(escala_real=1.7, k2_informativa=False, años=4)
    assert EI.evaluar(e, re)["semaforo"]["S5"]["contraste_10_años"]["estado"].startswith("sin contraste")


def test_int11_semaforo_sin_los_5_activos_no_da_s5(monkeypatch):
    monkeypatch.setattr(EI, "ACTIVOS_MEDIDOS", ("bolsa",))        # como antes de V8: solo la bolsa medida
    e, re = EI.sintetico(escala_real=1.0, k2_informativa=False, años=3)
    s = EI.evaluar(e, re)["semaforo"]
    assert "nota" in s["S5"] and s["bolsa"]["años"] == 3
