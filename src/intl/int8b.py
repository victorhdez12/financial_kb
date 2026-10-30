"""INT-8b: nowcast mensual DESCRIPTIVO de recesión (docs/int/INT8b_regla_v1.md, regla congelada en `88ae9be` antes de
escribir este código). No es una prueba ni una probabilidad: percentiles con pesos iguales frente a la propia historia
1960-2004 de cada país.

Solo funciones puras: los datos entran ya cargados (desarrollo: `load_dev`/`load_dev_curado` en scripts/int8b_corrida.py;
en vivo: src/report/nowcast_vivo.py, que es el único que lee ≥ 2005).

Indicadores (orientados: alto = más parecido a una recesión):
K1 curva (C1, baja = riesgo) · K2 difusión de curvas invertidas (C4) · K3 bolsa real 12 m (C6, baja = riesgo) ·
K4 Δ5 años crédito/PIB (C2, signo de INT-4) · K5 difusión de la producción industrial (% de los otros del núcleo con IP
interanual < 0) · K6 regla tipo Sahm con el paro. El fechado trimestral se muestra aparte y NO entra en la combinación.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.intl import lags as Lg
from src.intl import panel as P
from src.intl import termometro as T

# (clave, etiqueta, unidad, factor para enseñarlo, signo: +1 alto = riesgo, −1 bajo = riesgo)
COMPONENTES = [("K1", "Curva 10a−3m (media 12 m)", "pp", 1.0, -1),
               ("K2", "Difusión de curvas invertidas", "% países", 100.0, +1),
               ("K3", "Bolsa real 12 m (precio)", "%", 100.0, -1),
               ("K4", "Δ5 años crédito/PIB (BIS)", "pp PIB", 1.0, +1),
               ("K5", "Difusión de IP interanual < 0", "% países", 100.0, +1),
               ("K6", "Regla tipo Sahm (paro)", "pp", 1.0, +1)]
CLAVES = [k for k, *_ in COMPONENTES]
SIGNO = {k: s for k, *_, s in COMPONENTES}
REF_DESDE, REF_HASTA = pd.Timestamp("1960-01-31"), pd.Timestamp("2004-12-31")
MIN_MESES = 60              # historia mínima (meses 1960-2004) para el percentil de un indicador o del índice
MIN_COMPONENTES = 4         # de 6, para el índice del país
MIN_PAISES_AGREGADO = 10    # de 14 (núcleo), para el agregado
MIN_PAISES_DIFUSION = 5     # como C4 del termómetro
BANDAS = [(50, "bajo"), (80, "medio"), (95, "alto")]    # percentil < 50 bajo … ≥ 95 muy alto


# ---------------------------------------------------------------- indicadores
def sahm(paro: pd.Series) -> pd.Series:
    """Media de 3 meses del paro menos el mínimo de esa media en los 12 meses anteriores (pp), sobre la rejilla mensual
    completa de observación (huecos = NaN)."""
    m3 = paro.rolling(3, min_periods=3).mean()
    return m3 - m3.shift(1).rolling(12, min_periods=12).min()


def paro_util(c: str, paro: pd.Series) -> pd.Series:
    """Paro en rejilla mensual completa, sin el tramo interpolado (antes de 1998) de los 9 países de src/intl/panel.py."""
    s = P._mensual_completa(paro.dropna())
    if c in P.PARO_INTERPOLADO and not s.empty:
        s = s[s.index >= P.PARO_DESDE]
    return s


def sahm_asof(paro: dict, rejilla: pd.DatetimeIndex, paises: list[str]) -> pd.DataFrame:
    """K6 "as of": se calcula en el mes de observación y se desplaza entera con el retraso del paro (75 días)."""
    out = {}
    for c in paises:
        s = paro.get(c)
        if s is None or s.dropna().empty:
            out[c] = pd.Series(np.nan, index=rejilla)
            continue
        out[c] = Lg.asof(sahm(paro_util(c, s)), f"oecd_unemp_{c.lower()}", rejilla)
    return pd.DataFrame(out, index=rejilla)


def difusion(base: pd.DataFrame, nucleo: list[str], paises: list[str]) -> pd.DataFrame:
    """% de los OTROS países del núcleo con `base` < 0 (≥ 5 con dato), como C4 en src/intl/termometro.mensuales."""
    neg = (base < 0).astype(float).where(base.notna())
    out = {}
    for c in paises:
        otros = [o for o in nucleo if o != c and o in neg]
        out[c] = neg[otros].mean(axis=1).where(neg[otros].notna().sum(axis=1) >= MIN_PAISES_DIFUSION)
    return pd.DataFrame(out, index=base.index)


def componentes(pm: pd.DataFrame, bis: dict, pib: dict, paro: dict, nucleo: list[str], paises: list[str]) -> dict:
    """Paneles (fin de mes × países) de K1-K6 sin orientar. `pm` = bloque mensual "as of" con al menos curva, tipo_3m,
    ipc_yoy, bolsa_12m e ip_yoy (src/intl/panel.mensual o src/report/nowcast_vivo.cargar); `bis`, `pib`: país → serie
    trimestral; `paro`: país → paro mensual en su fecha de observación."""
    mens = T.mensuales(pm, bis, pib, nucleo, paises)
    rej = mens["C1"].index
    ip = pm["ip_yoy"].unstack(0).reindex(index=rej, columns=paises)
    return {"K1": mens["C1"], "K2": mens["C4"], "K3": mens["C6"], "K4": mens["C2"],
            "K5": difusion(ip, nucleo, paises), "K6": sahm_asof(paro, rej, paises)}


# ---------------------------------------------------------------- percentiles y combinación
def percentil(hist, v) -> np.ndarray:
    """Percentil de rango medio de `v` (escalar o vector) frente a `hist` (con empates, el centro de su bloque). NaN si
    `v` no es finito o si `hist` tiene menos de MIN_MESES valores finitos."""
    h = np.sort(np.asarray(hist, float))
    h = h[np.isfinite(h)]
    v = np.atleast_1d(np.asarray(v, float))
    out = np.full(v.shape, np.nan)
    if len(h) < MIN_MESES:
        return out
    ok = np.isfinite(v)
    out[ok] = (np.searchsorted(h, v[ok], "left") + np.searchsorted(h, v[ok], "right")) / (2 * len(h)) * 100
    return out


def _ref(s: pd.Series) -> list[float]:
    s = s[(s.index >= REF_DESDE) & (s.index <= REF_HASTA)]
    return sorted(float(x) for x in s.to_numpy() if np.isfinite(x))


def orientados(comp: dict, ref_ind: dict, paises: list[str]) -> dict:
    """Percentiles orientados (alto = riesgo) de cada indicador frente a la distribución congelada del propio país."""
    out = {}
    for k in CLAVES:
        p = pd.DataFrame({c: percentil(ref_ind[k].get(c, []), comp[k][c].to_numpy()) for c in paises},
                         index=comp[k].index)
        out[k] = p if SIGNO[k] > 0 else 100 - p
    return out


def indice(pct: dict) -> pd.DataFrame:
    """N(c, t): media simple de los percentiles orientados disponibles, si hay ≥ MIN_COMPONENTES."""
    pila = np.stack([pct[k].to_numpy() for k in CLAVES])
    ok = np.isfinite(pila)
    n = ok.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        m = np.where(ok, pila, 0.0).sum(axis=0) / n
    m = np.where(n >= MIN_COMPONENTES, m, np.nan)
    ref = pct[CLAVES[0]]
    return pd.DataFrame(m, index=ref.index, columns=ref.columns)


def agregado(N: pd.DataFrame, nucleo: list[str]) -> pd.Series:
    """A(t): media de N de los países del núcleo con dato, si hay ≥ MIN_PAISES_AGREGADO."""
    x = N[nucleo]
    return x.mean(axis=1).where(x.notna().sum(axis=1) >= MIN_PAISES_AGREGADO)


def banda(p: float | None) -> str | None:
    if p is None or not np.isfinite(p):
        return None
    for lim, nom in BANDAS:
        if p < lim:
            return nom
    return "muy alto"


def referencias(comp: dict, nucleo: list[str], paises: list[str]) -> dict:
    """Distribuciones 1960-2004 (solo para congelarlas con datos de desarrollo): de cada indicador por país, del índice N
    por país y del agregado A."""
    ind = {k: {c: _ref(comp[k][c]) for c in paises} for k in CLAVES}
    N = indice(orientados(comp, ind, paises))
    return {"desde": str(REF_DESDE.date()), "hasta": str(REF_HASTA.date()), "indicadores": ind,
            "indice": {c: _ref(N[c]) for c in paises}, "agregado": _ref(agregado(N, nucleo))}


def calcular(comp: dict, refs: dict, nucleo: list[str], paises: list[str]) -> dict:
    """Paneles completos: percentiles orientados, N, su percentil y A con su percentil (todo frente a las referencias)."""
    pct = orientados(comp, refs["indicadores"], paises)
    N = indice(pct)
    pN = pd.DataFrame({c: percentil(refs["indice"].get(c, []), N[c].to_numpy()) for c in paises}, index=N.index)
    A = agregado(N, nucleo)
    pA = pd.Series(percentil(refs["agregado"], A.to_numpy()), index=A.index)
    return {"pct": pct, "N": N, "pN": pN, "A": A, "pA": pA}
