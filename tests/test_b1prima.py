"""Tests de B1′ (src/paper/b1prima.py, scripts/b1prima_congelar.py, scripts/paper_decision_b1prima.py).
Sintéticos salvo `test_coeficientes_reproducibles_warehouse` (se salta sin el warehouse)."""
from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from scripts import b1prima_congelar as C
from scripts import paper_decision_b1prima as P
from src.paper import b1prima as B
from src.paper import live as L

T = pd.Timestamp


# ---------------------------------------------------------------- reglas = las de B1
def test_mismas_reglas_que_b1():
    assert B.ESTRATEGICO == L.ESTRATEGICO and (B.RV_MIN, B.UMBRAL) == (L.RV_MIN, L.UMBRAL)
    assert B.MAX_DIAS_SIN_DATO == L.MAX_DIAS_SIN_DATO
    for sig, prev in ((0.10, 0.70), (0.40, 0.70), (0.1702 / 0.99, 0.70), (0.20, 0.60), (0.18, 0.55)):
        assert B.rv_regla(sig, prev, L.SIGMA_STAR) == L.rv_b1(sig, prev)


# ---------------------------------------------------------------- calendario de la NYSE
@pytest.mark.parametrize("mes,n", [("2026-11", 20), ("2026-12", 22), ("2027-01", 19), ("2022-06", 21),
                                   ("2021-12", 22), ("2025-01", 20), ("2005-01", 20), ("2026-04", 21)])
def test_sesiones_nyse(mes, n):
    assert B.sesiones_nyse(pd.Period(mes, "M")) == n


def test_calendario_solo_desde_2005():
    with pytest.raises(ValueError):
        B.festivos_nyse(2004)


# ---------------------------------------------------------------- medida y rasgos
def test_r_eur_diario():
    idx = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    r_usd = pd.Series([0.0, 0.01, 0.0], index=idx)
    x = pd.Series([1.0, 1.0, 1.1], index=pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-04"]))  # fixing en sábado
    r = B.r_eur_diario(r_usd, x)
    assert r.iloc[0] == pytest.approx(0.01) and r.iloc[1] == pytest.approx(0.10)   # el movimiento entra el lunes


def test_rasgos_como_int12():
    from src.intl import int12 as M
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2000-01-03", periods=600)
    r = pd.Series(rng.normal(0, 0.01, len(idx)), index=idx)
    a, b = B.rasgos_har(r)[B.HAR], M.rasgos_diarios(r)[M.HAR]
    pd.testing.assert_frame_equal(a, b, check_names=False)


def _camino(desde, hasta, seed=0):
    """GARCH(1,1) diario sintético: volatilidad persistente para que el HAR tenga algo que estimar."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(desde, hasta)
    h, r = 1e-4, np.empty(len(idx))
    for i in range(len(idx)):
        r[i] = np.sqrt(h) * rng.standard_normal()
        h = 2e-6 + 0.08 * r[i] ** 2 + 0.9 * h
    return pd.Series(r, index=idx)


def test_estimacion_determinista_y_sha():
    r = _camino("1960-01-01", "2004-12-31")
    o1, o2 = C.calcular(r), C.calcular(r.copy())
    assert o1["sha256_parametros"] == o2["sha256_parametros"]
    b = o1["parametros"]["beta"]
    assert 0.5 < sum(b[1:]) < 1.05 and o1["estimacion"]["n_meses"] == 497          # 1963-07 … 2004-11
    assert o1["estimacion"]["fin_objetivo"] <= "2004-12-31"
    p = dict(o1["parametros"], duan=o1["parametros"]["duan"] + 1e-9)
    assert B.sha256_parametros(p) != o1["sha256_parametros"]


# ---------------------------------------------------------------- la estimación no lee datos ≥ 2005
def _warehouse_sintetico(hasta="2026-10-30", veneno=False):
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest (series_id varchar, date date, value double)")
    r = _camino("1955-01-03", hasta, seed=3)
    if veneno:                                       # disparates a partir de 2005: no deben cambiar nada
        r[r.index >= "2005-01-01"] = 5.0
    filas = [("aqr_mkt_usa_d", d.date(), 100 * v) for d, v in r.items()]
    filas += [("bundesbank_usd_dem_d", d.date(), 2.0) for d in r.index if d < T("1999-01-01")]
    filas += [("ecb_eurusd_d", d.date(), 9.9 if veneno and d >= T("2005-01-01") else 1.1) for d in r.index if d >= T("1999-01-01")]
    con.executemany("insert into obs_latest values (?, ?, ?)", filas)
    return con


def test_estimacion_no_lee_2005():
    r1, _ = C.cargar_dev(_warehouse_sintetico())
    r2, _ = C.cargar_dev(_warehouse_sintetico(veneno=True))
    assert r1.index.max() <= T("2004-12-31")
    pd.testing.assert_series_equal(r1, r2)
    assert C.calcular(r1)["sha256_parametros"] == C.calcular(r2)["sha256_parametros"]


def test_script_congelar_solo_usa_la_puerta():
    import inspect
    src = inspect.getsource(C)
    assert "obs_latest" not in src and "db.connect" not in src and "F.load_dev" in src


# ---------------------------------------------------------------- fichero congelado
def test_congelado_integro_y_falla_si_se_toca(tmp_path):
    c = json.loads(B.CONGELADO.read_text())
    assert B.sha256_parametros(c["parametros"]) == c["sha256_parametros"]
    assert c["procedencia"]["arbol_limpio"] is True
    assert c["estimacion"]["desde"] == "1963-07" and c["estimacion"]["hasta"] == "2004-11"
    assert c["datos"]["r_eur_hasta"] <= "2004-12-31"
    c["parametros"]["sigma_star_prima"] += 0.01
    f = tmp_path / "x.json"
    f.write_text(json.dumps(c))
    with pytest.raises(RuntimeError):
        B.cargar_congelado(f)


def _hay_warehouse():
    try:
        from src.warehouse import db
        con = db.connect(read_only=True)
        n = con.execute("select count(*) from obs_latest where series_id = 'aqr_mkt_usa_d'").fetchone()[0]
        con.close()
        return n > 0
    except Exception:
        return False


@pytest.mark.skipif(not _hay_warehouse(), reason="necesita el warehouse con aqr_mkt_usa_d")
def test_coeficientes_reproducibles_warehouse():
    from src.factors import data as F
    c = json.loads(B.CONGELADO.read_text())
    con = F.connect()
    try:
        r, datos = C.cargar_dev(con)
    finally:
        con.close()
    assert datos["huellas_sha256"] == c["datos"]["huellas_sha256"], "la fuente ≤ 2004 ha cambiado"
    assert C.calcular(r)["sha256_parametros"] == c["sha256_parametros"]


# ---------------------------------------------------------------- decisión en vivo (sintética)
def _congelado_tmp(tmp_path, sigma_star=0.17):
    p = {"beta": [-2.0, 0.1, 0.3, 0.38], "duan": 1.3, "sigma_star_prima": sigma_star}
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"parametros": p, "sha256_parametros": B.sha256_parametros(p)}))
    return f


def _vivo(sd, hasta="2026-10-30", quitar=None):
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest (series_id varchar, date date, value double)")
    dias = [d for d in pd.bdate_range("2026-01-02", hasta) if d not in B.festivos_nyse(d.year)]
    rng = np.random.default_rng(0)
    sp = 5000 * np.exp(np.cumsum(rng.normal(0, sd, len(dias))))
    filas = [("SP500", d.date(), v) for d, v in zip(dias, sp) if d != (T(quitar) if quitar else None)]
    filas += [("ecb_eurusd_d", d.date(), 1.1) for d in pd.bdate_range("2026-01-02", hasta)]
    con.executemany("insert into obs_latest values (?, ?, ?)", filas)
    return con


def test_decidir_alta_y_baja_vol(tmp_path):
    cg, log = _congelado_tmp(tmp_path), tmp_path / "d.jsonl"
    alta = B.decidir(T("2026-10-31"), _vivo(0.03), cg, log)
    assert alta.b1prima["rv"] == pytest.approx(0.55) and alta.cambio_b1prima
    assert abs(sum(alta.b1prima.values()) - 1) < 1e-9 and alta.n_sesiones_mes_siguiente == 20
    x = np.array(list(alta.rasgos.values()))
    assert alta.f_varianza_mes == pytest.approx(20 * np.exp(-2.0 + x @ [0.1, 0.3, 0.38]) * 1.3, rel=1e-5)
    assert alta.sigma_hat_prima == pytest.approx(np.sqrt(12 * alta.f_varianza_mes), abs=1e-5)
    baja = B.decidir(T("2026-10-31"), _vivo(0.003), cg, log)
    assert baja.b1prima["rv"] == 0.70 and not baja.cambio_b1prima


def test_decidir_usa_el_peso_previo_de_su_propio_registro(tmp_path):
    cg, log = _congelado_tmp(tmp_path), tmp_path / "d.jsonl"
    d = B.decidir(T("2026-10-31"), _vivo(0.03), cg, log)
    B.registrar(d, {}, log)
    assert B.ultimo_b1p(log) == pytest.approx(0.55)
    baja = B.decidir(T("2026-10-31"), _vivo(0.003), cg, log)
    assert baja.b1prima["rv"] == 0.70 and baja.cambio_b1prima


def test_decidir_falla_cerrado(tmp_path):
    cg = _congelado_tmp(tmp_path)
    with pytest.raises(RuntimeError, match="sin dato reciente"):
        B.decidir(T("2026-12-31"), _vivo(0.01), cg, tmp_path / "d.jsonl")
    with pytest.raises(RuntimeError, match="faltan datos"):
        B.decidir(T("2026-10-31"), _vivo(0.01, quitar="2026-09-15"), cg, tmp_path / "d.jsonl")
    with pytest.raises(RuntimeError, match="faltan los coeficientes"):
        B.decidir(T("2026-10-31"), _vivo(0.01), tmp_path / "no.json", tmp_path / "d.jsonl")


# ---------------------------------------------------------------- reglas de registro
def test_registro_reglas():
    with pytest.raises(P.MesNoValido):
        P.validar_b1p(T("2026-10-31"), T("2026-11-05"), [])          # antes de la aprobación: sin retroactivo
    P.validar_b1p(T("2026-11-30"), T("2026-12-03"), [])
    with pytest.raises(P.MesNoValido):
        P.validar_b1p(T("2026-11-30"), T("2027-01-03"), [])          # atrasado
    with pytest.raises(P.YaRegistrado):
        P.validar_b1p(T("2026-11-30"), T("2026-12-20"), ["2026-11-30"])
    with pytest.raises(P.MesNoValido):
        P.validar_b1p(T("2027-01-31"), T("2027-02-03"), ["2026-11-30"])   # falta diciembre


def test_auto_antes_del_arranque_no_hace_nada(monkeypatch, tmp_path):
    monkeypatch.setattr(B, "LOG", tmp_path / "d.jsonl")
    monkeypatch.setattr(B, "decidir", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe decidir")))
    monkeypatch.setattr(P, "cierre_objetivo", lambda hoy: T("2026-10-31"))
    assert P.main(["--auto", "--registrar"]) == 0 and not (tmp_path / "d.jsonl").exists()


def test_sin_activo_no_registra(monkeypatch, tmp_path):
    monkeypatch.setattr(B, "ACTIVO", tmp_path / "ACTIVO")
    monkeypatch.setattr(B, "LOG", tmp_path / "d.jsonl")
    monkeypatch.setattr(P, "validar_b1p", lambda *a: None)
    monkeypatch.setattr(P, "cierre_objetivo", lambda hoy: T("2026-11-30"))
    llamado = []
    monkeypatch.setattr(B, "decidir", lambda *a, **k: llamado.append(1))
    assert P.main(["--auto", "--registrar"]) == 6
    assert not llamado and not (tmp_path / "d.jsonl").exists()


def test_no_toca_el_registro_de_b1():
    assert B.LOG != L.LOG and B.LOG.name == "decisiones_b1prima.jsonl"
