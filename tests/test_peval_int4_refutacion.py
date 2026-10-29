"""Tests SINTÉTICOS de scripts/peval_int4_refutacion.py (prerregistro docs/int/PEVAL_INT4_refutacion_v1.md).
Ninguno abre el warehouse ni lee datos reales: los lectores se sustituyen por trampas que fallan si se llaman.
Comprueban sobre todo la puerta doble (fichero de autorización del usuario + árbol limpio) y que, sin ella, se aborta
ANTES de leer ninguna fila; y la lógica del veredicto."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import peval_int4_refutacion as R
from src.intl import int4 as M

AUT_OK = "autoriza: usuario\nfecha: 2027-01-15\nmotivo: decision_B2_B1\ndecision: gastar el bloqueado para decidir B2\n"


class Trampa(AssertionError):
    pass


@pytest.fixture
def trampas(monkeypatch):
    """Cualquier lectura de datos (warehouse, parquet, lector del bloqueado, re-ajuste ≤ 2004) hace fallar el test."""
    llamadas = []

    def trampa(nombre):
        def f(*a, **k):
            llamadas.append(nombre)
            raise Trampa(f"se ha intentado leer datos: {nombre}")
        return f

    import src.intl.data as D
    import src.warehouse.db as db
    monkeypatch.setattr(D, "connect", trampa("D.connect"))
    monkeypatch.setattr(D, "load_dev", trampa("D.load_dev"))
    monkeypatch.setattr(db, "connect", trampa("db.connect"))
    monkeypatch.setattr(pd, "read_parquet", trampa("pd.read_parquet"))
    monkeypatch.setattr(R, "leer_bloqueado", trampa("leer_bloqueado"))
    monkeypatch.setattr(R, "modelo_congelado", trampa("modelo_congelado"))
    return llamadas


def _rutas(monkeypatch, tmp_path, autorizacion: str | None = None, salida: bool = False):
    a, s = tmp_path / "PEVAL_INT4_AUTORIZADO", tmp_path / "peval_int4_refutacion.json"
    if autorizacion is not None:
        a.write_text(autorizacion)
    if salida:
        s.write_text("{}")
    monkeypatch.setattr(R, "AUTORIZACION", a)
    monkeypatch.setattr(R, "SALIDA", s)
    return a, s


def test_ruta_real_de_la_autorizacion():
    assert R.AUTORIZACION == R.REPO / "research" / "int" / "PEVAL_INT4_AUTORIZADO"
    assert R.SALIDA == R.REPO / "research" / "int" / "peval_int4_refutacion.json"


def test_aborta_sin_fichero_de_autorizacion_sin_leer_nada(monkeypatch, tmp_path, trampas):
    _rutas(monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="NO AUTORIZADO"):
        R.main()
    assert trampas == []


def test_aborta_sin_fichero_aunque_el_arbol_este_limpio(monkeypatch, tmp_path, trampas):
    import src.intl.procedencia as Pr
    monkeypatch.setattr(Pr, "procedencia", lambda exigir_limpio=True: {"commit": "x", "arbol_limpio": True})
    monkeypatch.setattr(R, "_git_rastreado", lambda p: True)
    _rutas(monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="NO AUTORIZADO"):
        R.main()
    assert trampas == []


def test_aborta_con_fichero_y_arbol_sucio(monkeypatch, tmp_path, trampas):
    import src.intl.procedencia as Pr

    def sucio(exigir_limpio=True):
        raise SystemExit("árbol de git sucio")
    monkeypatch.setattr(Pr, "procedencia", sucio)
    monkeypatch.setattr(R, "_git_rastreado", lambda p: True)
    _rutas(monkeypatch, tmp_path, AUT_OK)
    with pytest.raises(SystemExit, match="sucio"):
        R.main()
    assert trampas == []


def test_aborta_si_la_autorizacion_no_esta_commiteada(monkeypatch, tmp_path, trampas):
    _rutas(monkeypatch, tmp_path, AUT_OK)          # tmp_path no está en el repo → no rastreado
    with pytest.raises(SystemExit, match="no está commiteado"):
        R.main()
    assert trampas == []


@pytest.mark.parametrize("texto,error", [
    ("", "faltan campos"),
    ("autoriza: agente\nfecha: 2027-01-15\nmotivo: decision_B2_B1\ndecision: x\n", "solo el usuario"),
    ("autoriza: usuario\nfecha: 2027-01-15\nmotivo: curiosidad\ndecision: x\n", "motivo"),
    ("autoriza: usuario\nfecha: 2027-01-15\nmotivo: decision_B2_B1\n", "faltan campos"),
])
def test_aborta_con_autorizacion_mal_formada(monkeypatch, tmp_path, trampas, texto, error):
    monkeypatch.setattr(R, "_git_rastreado", lambda p: True)
    _rutas(monkeypatch, tmp_path, texto)
    with pytest.raises(SystemExit, match=error):
        R.main()
    assert trampas == []


def test_un_solo_uso(monkeypatch, tmp_path, trampas):
    _rutas(monkeypatch, tmp_path, AUT_OK, salida=True)
    with pytest.raises(SystemExit, match="ya se gastó"):
        R.main()
    assert trampas == []


def test_aborta_si_cambia_el_prerregistro_o_el_modelo(monkeypatch, tmp_path, trampas):
    import src.intl.procedencia as Pr
    monkeypatch.setattr(Pr, "procedencia", lambda exigir_limpio=True: {"commit": "x", "arbol_limpio": True})
    monkeypatch.setattr(R, "_git_rastreado", lambda p: True)
    _rutas(monkeypatch, tmp_path, AUT_OK)
    monkeypatch.setattr(R, "DOC_SHA256", "0" * 64)
    with pytest.raises(SystemExit, match="enmienda"):
        R.main()
    monkeypatch.setattr(R, "DOC_SHA256", R._sha256(R.DOC))
    monkeypatch.setattr(R, "REF_MODELO_SHA256", "0" * 64)
    with pytest.raises(SystemExit, match="modelo congelado"):
        R.main()
    assert trampas == []


def test_doc_y_modelo_congelados_coinciden():
    assert R._sha256(R.DOC) == R.DOC_SHA256
    assert R._sha256(R.REF_MODELO) == R.REF_MODELO_SHA256


# ---------------------------------------------------------------- lectura escalonada (sintética)
def _pib_sintetico(recesion_extra: bool) -> dict[str, pd.Series]:
    años = np.arange(1990, 2021)
    out = {}
    for i, c in enumerate(R.NUCLEO):
        v = np.cumsum(np.full(len(años), 0.02)) + 1
        caidas = [2008] + ([2012] if recesion_extra and i % 2 else [])
        for a in caidas:
            v[años >= a] -= 0.05
        out[c] = pd.Series(np.exp(v), index=años)
    return out


def test_recuentos_distintos_abortan_antes_de_leer_indicadores(monkeypatch, tmp_path):
    """Puerta superada (simulada) y objetivo sintético que NO coincide con la potencia: se para tras leer solo el PIB."""
    import src.intl.data as D
    leidas = []

    class Con:
        def close(self):
            pass

    def lector(con, sid):
        leidas.append(sid)
        if not sid.endswith("_rgdpmad"):
            raise Trampa(f"indicador leído: {sid}")
        return _pib_sintetico(False)[sid.split("_")[1].upper()]

    monkeypatch.setattr(R, "puerta", lambda: {"procedencia": {}, "autorizacion": {}})
    monkeypatch.setattr(R, "modelo_congelado", lambda: {})
    monkeypatch.setattr(D, "connect", lambda: Con())
    monkeypatch.setattr(R, "leer_bloqueado", lector)
    with pytest.raises(SystemExit, match="no se leen indicadores"):
        R.main()
    assert leidas and all(s.endswith("_rgdpmad") for s in leidas)


def test_anual_desde_series_igual_que_panel_anual(monkeypatch):
    """Las derivadas del script son las de src/intl/panel.anual (con series sintéticas ≤ 2004)."""
    import src.intl.data as D
    from src.intl import panel as P
    rng = np.random.default_rng(0)
    fechas = pd.to_datetime([f"{a}-01-01" for a in range(1960, 2005)])
    sint = {}

    def load_dev(con, sid):
        if sid not in sint:
            sint[sid] = pd.Series(np.exp(rng.normal(0, 0.1, len(fechas)).cumsum()) + 1, index=fechas, name=sid)
        return sint[sid]
    monkeypatch.setattr(D, "load_dev", load_dev)
    a = P.anual(None)
    paises = ["DEU", "USA"]
    series = {c: {v: load_dev(None, f"jst_{c.lower()}_{v}").set_axis(fechas.year)
                  for v in ["rgdpmad"] + R.VARS_INDICADORES} for c in paises}
    b = R.anual_desde_series(series)
    cols = ["rgdpmad", "cpi", "ltrate", "stir", "eq_tr_real", "pib_real_g", "inflacion", "credito_pib"]
    pd.testing.assert_frame_equal(a.loc[paises, cols], b[cols], check_names=False)


def test_paneles_hasta_no_cambia_desarrollo():
    rng = np.random.default_rng(1)
    idx = pd.MultiIndex.from_product([["A", "B", "C", "D", "E", "F"], range(1870, 2021)], names=["pais", "año"])
    a = pd.DataFrame(rng.normal(size=(len(idx), 7)), index=idx,
                     columns=["ltrate", "stir", "credito_pib", "cpi", "inflacion", "eq_tr_real", "pib_real_g"])
    a["cpi"], a["rgdpmad"] = np.abs(a["cpi"]) + 1, np.exp(a["pib_real_g"].cumsum())
    paises = list("ABCDEF")
    dev = a[a.index.get_level_values("año") <= 2004]
    ex = pd.DataFrame(np.nan, index=a.index, columns=["hpnom", "money", "wage"])
    p0 = M.paneles(dev, ex.loc[dev.index], paises, paises, None)
    p1 = M.paneles(a, ex, paises, paises, None, hasta=2020)
    for k in ("C1", "C2", "C4", "C5", "C6", "S4"):
        pd.testing.assert_frame_equal(p0[k], p1[k].loc[:2004])
        assert p1[k].index.max() == 2020
    filas = pd.DataFrame({"pais": ["A", "B", "C"], "t": [2003, 2010, 2019], "pico": [2001, 2008, 2018]})
    x0, x1 = M.matriz(filas, p0, ["C1", "S5"]), M.matriz(filas, p1, ["C1", "S5"])
    assert x0[0, 0] == x1[0, 0] and np.isnan(x0[1:, 0]).all() and np.isfinite(x1[:, 0]).all()


# ---------------------------------------------------------------- estadísticos y veredicto
def _ev(d_auc=0.1, lo=0.55, eventos=25, no_eventos=21, años=5):
    return {"d_auc": d_auc, "auc_modelo_ic95": [lo, 0.9], "eventos": eventos, "no_eventos": no_eventos,
            "años_con_evento": años}


@pytest.mark.parametrize("ev,esperado", [
    (_ev(d_auc=-0.01), "refutado"),
    (_ev(d_auc=0.0), "refutado"),
    (_ev(d_auc=-0.2, lo=0.6), "refutado"),
    (_ev(d_auc=0.05, lo=0.51), "no_refutado"),
    (_ev(d_auc=0.05, lo=0.49), "no_concluyente"),
    (_ev(eventos=9), "no_concluyente_datos"),
    (_ev(no_eventos=9), "no_concluyente_datos"),
    (_ev(años=2, d_auc=-0.3), "no_concluyente_datos"),
])
def test_veredicto_giro(ev, esperado):
    assert R.veredicto_giro(ev) == esperado


def test_veredicto_global():
    v = lambda a, b: R.veredicto_global({"T1_sin_2020": a, "T2": b, "T1_con_2020": "refutado"})  # noqa: E731
    assert v("refutado", "no_refutado") == {"global": "refutado", "giros_refutados": ["T1_sin_2020"]}
    assert v("no_refutado", "refutado")["global"] == "refutado"
    assert v("no_refutado", "no_refutado")["global"] == "no_refutado"      # T1 con 2020 no cuenta (sensibilidad)
    assert v("no_refutado", "no_concluyente")["global"] == "no_concluyente"
    assert v("no_concluyente_datos", "no_refutado")["global"] == "no_concluyente"


def test_evaluar_sintetico():
    rng = np.random.default_rng(2)
    t = np.repeat(np.arange(2004, 2020), 14)
    y = (rng.random(len(t)) < np.where(np.isin(t, [2007, 2008, 2010, 2011, 2012]), 0.6, 0.0)).astype(float)
    p1 = 1 / (1 + np.exp(-(-2 + 2.5 * y + rng.normal(0, 1, len(t)))))
    p0 = 1 / (1 + np.exp(-(-2 + rng.normal(0, 1, len(t)))))
    ev = R.evaluar(y, p1, p0, t)
    assert ev["d_auc"] > 0.2 and ev["auc_modelo_ic95"][0] > 0.5 and ev["años_con_evento"] == 5
    assert ev["auc_modelo_ic95"][0] <= ev["auc_modelo"] <= ev["auc_modelo_ic95"][1]
    assert R.veredicto_giro(ev) == "no_refutado"
    ev_mal = R.evaluar(y, p0, p1, t)
    assert R.veredicto_giro(ev_mal) == "refutado"
