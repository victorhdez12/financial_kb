"""INT-8b: nowcast descriptivo (src/intl/int8b.py, src/report/nowcast_vivo.py). Sintéticos sin red y, si existe el
warehouse real, reproducción de las referencias congeladas con corte 2004-12."""
import json

import numpy as np
import pandas as pd
import pytest

from src.intl import data as D
from src.intl import int8b as K
from src.report import nowcast_vivo as NV
from src.warehouse import db
from tests.test_termometro_vivo import _obs, _warehouse


# ---------------------------------------------------------------- piezas
def test_sahm():
    idx = pd.date_range("2000-01-01", periods=30, freq="MS")
    paro = pd.Series(5.0, index=idx)
    paro.iloc[20:] = 6.0
    s = K.sahm(paro)
    assert s.iloc[:14].isna().all()                      # 3 m + 12 m previos
    assert s.iloc[19] == 0
    assert s.iloc[22] == pytest.approx(1.0)              # media 3 m = 6, mínimo previo = 5


def test_paro_interpolado_fuera_antes_de_1998():
    idx = pd.date_range("1990-01-01", "2000-12-01", freq="MS")
    s = pd.Series(5.0, index=idx)
    assert K.paro_util("FRA", s).index.min() == pd.Timestamp("1998-01-01")
    assert K.paro_util("USA", s).index.min() == pd.Timestamp("1990-01-01")


def test_percentil_rango_medio_y_historia_corta():
    h = np.arange(100.0)
    assert K.percentil(h, 49.5)[0] == pytest.approx(50)
    assert K.percentil(h, -1)[0] == 0 and K.percentil(h, 1000)[0] == 100
    assert K.percentil(np.zeros(100), 0.0)[0] == pytest.approx(50)     # empates: centro del bloque
    assert np.isnan(K.percentil(np.arange(59.0), 10)[0])               # < 60 meses
    assert np.isnan(K.percentil(h, np.nan)[0])


def test_difusion_deja_fuera_al_propio_pais():
    nuc = ["A", "B", "C", "D", "E", "F"]
    base = pd.DataFrame([[-1, -1, 1, 1, 1, 1]], columns=nuc, dtype=float)
    d = K.difusion(base, nuc, nuc)
    assert d.loc[0, "A"] == pytest.approx(1 / 5) and d.loc[0, "C"] == pytest.approx(2 / 5)
    base.iloc[0, 1:] = np.nan                            # < 5 con dato
    assert K.difusion(base, nuc, nuc)["A"].isna().all()


def test_orientacion_indice_y_bandas():
    idx = pd.date_range("1960-01-31", periods=3, freq="ME")
    ref = {k: {"X": list(np.arange(100.0))} for k in K.CLAVES}
    comp = {k: pd.DataFrame({"X": [90.0, 90.0, 90.0]}, index=idx) for k in K.CLAVES}
    comp["K6"].iloc[2] = np.nan
    comp["K5"].iloc[2] = np.nan
    comp["K4"].iloc[1:] = np.nan
    comp["K3"].iloc[1:] = np.nan
    pct = K.orientados(comp, ref, ["X"])
    assert pct["K1"]["X"].iloc[0] == pytest.approx(9.5) and pct["K2"]["X"].iloc[0] == pytest.approx(90.5)
    N = K.indice(pct)["X"]
    # mes 0: K1 9,5 y K3 9,5 (bajo = riesgo), resto 90,5 → media simple con pesos iguales
    assert N.iloc[0] == pytest.approx((9.5 * 2 + 90.5 * 4) / 6)
    assert N.iloc[1] == pytest.approx((9.5 + 90.5 * 3) / 4)            # 4 de 6: vale
    assert np.isnan(N.iloc[2])                                          # 2 de 6: no
    assert [K.banda(p) for p in (10, 50, 80, 95, None)] == ["bajo", "medio", "alto", "muy alto", None]


def test_agregado_exige_10_paises():
    nuc = [f"P{i}" for i in range(14)]
    N = pd.DataFrame([[50.0] * 14, [50.0] * 9 + [np.nan] * 5], columns=nuc)
    A = K.agregado(N, nuc)
    assert A.iloc[0] == 50 and np.isnan(A.iloc[1])


# ---------------------------------------------------------------- en vivo, sintético
def _con(choque=0.0):
    con = _warehouse(choque=choque)
    fm = pd.date_range("1985-01-01", "2026-09-01", freq="MS")
    t = np.arange(len(fm))
    pos = fm > pd.Timestamp("2026-03-01")
    partes = []
    for i, c in enumerate(NV.TODOS):
        partes.append(_obs(f"oecd_ip_{c.lower()}", fm, 100 * np.exp(0.002 * t + 0.03 * np.sin(t / 20 + i)) * (1 + choque * pos)))
        partes.append(_obs(f"oecd_unemp_{c.lower()}", fm, 6 + np.sin(t / 25 + i) + choque * pos))
    df = pd.concat(partes, ignore_index=True)
    con.execute("insert into obs_latest select series_id, date, value from df")
    return con


def _refs(con):
    pm, bis, pib, paro, _ = NV.cargar(con, "2026-10-29")
    return K.referencias(K.componentes(pm, bis, pib, paro, NV.NUCLEO, NV.TODOS), NV.NUCLEO, NV.TODOS)


@pytest.fixture(scope="module")
def vivo():
    con = _con()
    res = NV.nowcast(con, "2026-10-29", refs=_refs(con))
    con.close()
    return res


def test_vivo_estructura(vivo):
    assert vivo["fecha_calculo"] == "2026-09-30"
    a = vivo["agregado"]
    assert a["paises_con_dato"] >= 10 and a["banda"] in {"bajo", "medio", "alto", "muy alto"}
    assert 0 <= a["percentil"] <= 100
    assert set(a["paises_en_recesion"]) == {"ESP", "DNK"}               # del fechado (EN_RECESION del núcleo)
    p = vivo["paises"]
    assert p["DNK"]["indicadores"]["K3"]["valor"] is None                # sin bolsa mensual
    for c in NV.TODOS:
        assert set(p[c]["indicadores"]) == set(K.CLAVES)
        if p[c]["indice"] is not None:
            assert p[c]["n_indicadores"] >= K.MIN_COMPONENTES
    assert "probabilidad" not in json.dumps({c: {k: v for k, v in d.items() if k != "indicadores"}
                                             for c, d in p.items()})


def test_markdown(vivo):
    md = NV.markdown(vivo)
    assert "Informativo, no es una señal de cartera" in md and NV.AVISO in md
    assert md.count("| USA |") == 1 and "| AUS (prueba) |" in md
    assert "5c. Nowcast" in md


def test_no_mira_el_futuro():
    a, b = _con(), _con(choque=1.0)
    refs = _refs(a)
    ra, rb = NV.nowcast(a, "2026-03-31", refs=refs), NV.nowcast(b, "2026-03-31", refs=refs)
    assert json.dumps(ra, sort_keys=True) == json.dumps(rb, sort_keys=True)


def test_referencias_incompletas(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"referencias": {"desde": "1960-01-31", "hasta": "2004-12-31", "indicadores": {},
                                             "indice": {}, "agregado": []}}))
    with pytest.raises(NV.ReferenciasIncompletas, match="distribución K1 BEL"):
        NV.referencias_congeladas(p)
    with pytest.raises(NV.ReferenciasIncompletas):
        NV.referencias_congeladas(tmp_path / "no_existe.json")


def test_vivo_fuera_de_src_intl():
    assert "intl" not in NV.__file__.split("/src/")[1]


# ---------------------------------------------------------------- warehouse real
@pytest.mark.skipif(not db.WAREHOUSE.exists() or not NV.REFERENCIAS.exists(), reason="sin warehouse o referencias")
def test_referencias_congeladas_igual_a_vivo_con_corte_2004():
    """Las referencias congeladas (datos load_dev) = las recalculadas con la carga en vivo cortada en 2004-12: la carga en
    vivo reproduce el desarrollo (también la IP interanual y el paro)."""
    from src.intl import panel as P
    con = db.connect(read_only=True)
    try:
        pm, bis, pib, paro, _ = NV.cargar(con, "2004-12-31")
        dev = P.mensual(con)
    finally:
        con.close()
    assert np.allclose(pm["ip_yoy"].to_numpy(), dev["ip_yoy"].reindex(pm.index).to_numpy(), equal_nan=True)
    rec = K.referencias(K.componentes(pm, bis, pib, paro, NV.NUCLEO, NV.TODOS), NV.NUCLEO, NV.TODOS)
    cong = NV.referencias_congeladas()
    for k in K.CLAVES:
        for c in NV.TODOS:
            a, b = rec["indicadores"][k][c], cong["indicadores"][k][c]
            assert len(a) == len(b) and np.allclose(a, b, rtol=0, atol=1e-12), (k, c)
    for c in NV.TODOS:
        assert np.allclose(rec["indice"][c], cong["indice"][c], rtol=0, atol=1e-9), c
    assert np.allclose(rec["agregado"], cong["agregado"], rtol=0, atol=1e-9)
    assert D.DEV_END == pd.Timestamp("2004-12-31") or D.DEV_END.year == 2004


def test_reporte_semanal_seccion_5c(vivo):
    from src.report import weekly as W
    assert "5c. Nowcast" in W.md_nowcast({"nowcast": vivo}) and NV.AVISO in W.md_nowcast({"nowcast": vivo})
    assert "No disponible" in W.md_nowcast({}) and "boom" in W.md_nowcast({"nowcast": {"error": "boom"}})
