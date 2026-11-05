"""Tests SINTÉTICOS de INT-11 v3.1: imputación condicionada (PMM) de los activos sin dato
(docs/int/INT11_v3_1_imputacion.md). Ningún dato real."""
from __future__ import annotations

import numpy as np
import pytest

from src.intl import escenarios as E
from tests.sint_int11 import panel

RHO = -0.6


@pytest.fixture(scope="module")
def filas():
    return E.preparar_filas(panel(), covariables=("termo",))


@pytest.fixture(scope="module")
def filas_dep():
    """Panel sintético con oro DEPENDIENTE de los bonos (ρ log = −0,6) y sin dato antes de 1972 (78 % de huecos)."""
    df = panel(n_paises=8, semilla=1)
    rng = np.random.default_rng(5)
    b = np.log1p(df["bonos"])
    z = (b - b.mean()) / b.std()
    lg = 0.01 + 0.15 * (RHO * z + np.sqrt(1 - RHO ** 2) * rng.standard_normal(len(df)))
    df["oro"] = np.where(df["año"] >= 1972, np.expm1(lg), np.nan)
    return E.preparar_filas(df)


def _corr_sorteos(g, s0, a=1, b=4):
    e = g.simular("P01", s0, horizonte=1, n_lotes=50, por_lote=200, semilla=11)
    R = np.log1p(e.rent[:, 0, :])
    return float(np.corrcoef(R[:, a], R[:, b])[0, 1]), float(R[:, b].std())


# ------------------------------------------------------------------ v3 intacto (opción antigua, bit a bit)
def test_v3_sigue_reproducible_bit_a_bit(filas):
    """Valores calculados con src/intl/escenarios.py ANTES de añadir v3.1 (rama de 87f0c09), misma semilla."""
    for cfg in (E.Config.v3(), E.Config.v3(imputacion="independiente")):
        g = E.Generador(cfg).ajustar(filas)
        e = g.simular("P01", "sobrecalentamiento", horizonte=4, n_lotes=10, por_lote=50, semilla=3)
        assert float(np.nansum(e.rent)) == 46.3367364691508
        assert float(np.nansum(e.inflacion)) == 110.92944597829447
        assert int(e.regimen.sum()) == 1750
        assert float(np.nansum(g.simular_suave("P02", 0.031, 0.0, horizonte=2, n_lotes=10, por_lote=50,
                                                semilla=7).rent)) == 36.4998215266956
    g1 = E.Generador(E.Config()).ajustar(filas)
    assert float(np.nansum(g1.simular("P01", 1, horizonte=3, n_lotes=10, por_lote=50, semilla=2).rent)) == \
        49.56869777344693


def test_config_v3_1_solo_cambia_la_imputacion():
    a, b = E.Config.v3(), E.Config.v3_1()
    assert a.imputacion == "independiente" and E.Config().imputacion == "independiente"
    assert E.Config.v2().imputacion == "independiente"
    assert b.imputacion == "pmm" and b.k_pmm == E.K_PMM == 5
    da, db = a.__dict__.copy(), b.__dict__.copy()
    da.pop("imputacion"), db.pop("imputacion")
    assert da == db                                                          # semivida y el resto, iguales a v3
    assert E.Config.v3_1(semivida_epoca=10.0).semivida_epoca == 10.0


def test_imputacion_desconocida(filas):
    with pytest.raises(ValueError):
        E.Generador(E.Config.v3(imputacion="otra")).ajustar(filas)


# ------------------------------------------------------------------ PMM conserva la dependencia de las filas completas
def test_pmm_conserva_la_correlacion_de_las_filas_completas(filas_dep):
    comp = filas_dep[["bonos", "oro"]].dropna()
    rho_c = float(np.corrcoef(np.log1p(comp["bonos"]), np.log1p(comp["oro"]))[0, 1])
    assert rho_c == pytest.approx(RHO, abs=0.05)
    g3 = E.Generador(E.Config.v3()).ajustar(filas_dep)
    g31 = E.Generador(E.Config.v3_1()).ajustar(filas_dep)
    for s0 in (0, 1):
        r3, sd3 = _corr_sorteos(g3, s0)
        r31, sd31 = _corr_sorteos(g31, s0)
        assert abs(r31 - rho_c) < 0.12                                       # conservada (≈ −0,51/−0,54)
        assert abs(r3) < abs(rho_c) - 0.25                                   # v3 la diluye (≈ −0,26)
        assert sd31 == pytest.approx(sd3, rel=0.10)                          # la marginal del oro no cambia


def test_pmm_sin_suavizado_ni_escala_casi_exacta(filas_dep):
    """Sin las piezas que atenúan aparte (suavizado independiente, factor de país), la PMM queda a < 0,08."""
    comp = filas_dep[["bonos", "oro"]].dropna()
    rho_c = float(np.corrcoef(np.log1p(comp["bonos"]), np.log1p(comp["oro"]))[0, 1])
    g = E.Generador(E.Config.v3_1(c_suavizado=0.0, escala_pais=False)).ajustar(filas_dep)
    assert abs(_corr_sorteos(g, 1)[0] - rho_c) < 0.08


def test_pmm_candidatos_validos(filas_dep):
    g = E.Generador(E.Config.v3_1()).ajustar(filas_dep)
    v = g.vars.index("oro")
    falta = ~np.isfinite(g.V[:, v])
    for c in g.celdas:
        cand, n = g.pmm[(c, v)]
        assert (n[falta] == E.K_PMM).all() and (n[~falta] == 0).all()        # todas las filas sin oro emparejadas
        usados = cand[falta].ravel()
        assert np.isfinite(g.V[usados, v]).all()                             # los donantes tienen el dato
        assert g.pmm_nivel[(c, v)][3] == 0                                   # nadie cae a donante independiente
    # el donante está en la celda (nivel 0) cuando la celda tiene ≥ n_min_pmm filas con oro
    c0 = (0, 0)
    if g.pmm_nivel[(c0, v)][0]:
        assert set(g.pmm[(c0, v)][0][falta].ravel()) <= set(g.donantes[(c0, v)])


def test_pmm_tambien_en_v1(filas_dep):
    """La ruta sin piezas v2 (`_imputar`) usa el mismo emparejamiento."""
    comp = filas_dep[["bonos", "oro"]].dropna()
    rho_c = float(np.corrcoef(np.log1p(comp["bonos"]), np.log1p(comp["oro"]))[0, 1])
    r0 = _corr_sorteos(E.Generador(E.Config()).ajustar(filas_dep), 1)[0]
    r1 = _corr_sorteos(E.Generador(E.Config(imputacion="pmm")).ajustar(filas_dep), 1)[0]
    assert abs(r1 - rho_c) < 0.1 and abs(r0) < abs(rho_c) - 0.25


# ------------------------------------------------------------------ registro en vivo: serie nueva
def test_registro_serie_nueva_no_se_mezcla(tmp_path):
    from src.report import registro_vivo as RV
    base = {"procedencia": {"commit": "abc"}, "ventana_objetivo": {"desde": "2026-12-01", "hasta": "2027-11-30"}}
    v31 = tmp_path / "v3_1"
    RV.registrar({**base, "emision": "2026-11-20", "serie_registro": "int11_v3_1"}, v31)
    assert (v31 / "SERIE").read_text().strip() == "int11_v3_1"
    RV.registrar({**base, "emision": "2026-12-20", "serie_registro": "int11_v3_1"}, v31)       # misma serie: sigue
    with pytest.raises(SystemExit):
        RV.registrar({**base, "emision": "2027-01-20", "serie_registro": "int11_v3"}, v31)    # otra serie: no
    v2 = tmp_path / "v2"
    RV.registrar({**base, "emision": "2026-11-20"}, v2)                                       # serie v2 sin marca
    with pytest.raises(SystemExit):
        RV.registrar({**base, "emision": "2026-12-20", "serie_registro": "int11_v3_1"}, v2)
    from scripts import int11_v3_hoy as H
    assert H.SERIE_VIVO == "int11_v3_1" and H.VIVO_V3_1.name == "int11_v3_1_vivo"


def test_hoy_markdown_publica_la_dependencia_por_regimen():
    from scripts import int11_v3_hoy as H
    q = list(np.linspace(-0.3, 0.4, 99))
    dep = {"bolsa-bonos": 0.2, "bonos-oro": -0.05}
    r = {"estado": {"mes_ipc": "2026-09-01", "inflacion": 0.02, "brecha": 0.02, "codigo": 0},
         "pesos_regimen": {"expansion": 1.0, "sobrecalentamiento": 0.0, "estanflacion": 0.0, "crecimiento_bajo": 0.0},
         "regimen_dominante": "expansion", "cuantiles_1_99": {a: q for a in E.ACTIVOS},
         "p_caida_bolsa_20": {"p": 0.1, "ic90": (0.05, 0.15)}, "p_inflacion_5": {"p": 0.1, "ic90": (0.05, 0.15)},
         "p_inflacion_5_regimen_duro": 0.1, "distancia_umbral_pp": -1.0, "cerca_umbral": False,
         "dependencia_hoy": dep,
         "dependencia_por_regimen": {"expansion": dep, "sobrecalentamiento": {"bolsa-bonos": 0.45, "bonos-oro": -0.27}}}
    o = {"procedencia": {}, "emision": "2026-11-05", "corte_datos": "2026-10-31", "kappa": 1e6, "kappa_en_borde": True,
         "motor": "v3.1", "ventana_objetivo": {"desde": "2026-12-01", "hasta": "2027-11-30"}, "aviso": "x",
         "dependencia_descriptiva_2004": H.descriptiva_regimen(),
         "acierto_medido_fase_D": {"activo": {a: 0.9 for a in E.ACTIVOS}, "global": 0.898, "puerta_D": True,
                                   "cerca_umbral": 0.94, "regimen": {"expansion": {"bolsa": 0.93}},
                                   "pais": {"ESP": {"bolsa": 0.95}},
                                   "informativa_v3_1": {"global": 0.8993, "activo": {}, "cerca_umbral": 0.94}},
         "paises": {"ESP": r}}
    md = H.markdown(o)
    assert "≤ 2004, no confirmado" in md and "| ESP | +0,20 / -0,05 | +0,20 / -0,05 | +0,45 / -0,27 |" in md
    assert "motor v3.1" in md and "Recalculada con v3.1 (informativo, no es una puerta nueva): 89.9 %" in md
    assert "Descriptiva ≤ 2004" in md and "1972-2004" in md
