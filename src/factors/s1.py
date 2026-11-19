"""Motor de S1 «rotación de sectores por régimen» (docs/factors/S1_rotacion_sectorial_spec.md v1.0, CONGELADA).
Funciones puras sobre tablas mensuales (PeriodIndex); los datos los carga src/factors/data.py y la señal viene de
scripts/s1_senal.py (research/factors/s1_senal.csv, con sha256).

Regla (§3), sin parámetros libres:
- Cuadrante fijado al cierre de t → pesos que rigen la rentabilidad de t + 1.
- Pesos objetivo: 50 % núcleo (mercado, `mkt`) + 50 % inclinación repartido a partes iguales (12,5 %) entre los 4
  sectores favorecidos del cuadrante. Sin cortos ni apalancamiento; siempre invertida al 100 %.
- Solo se opera cuando cambia el cuadrante (como mucho una vez al mes); entre cambios los pesos derivan con los precios
  (comprar y mantener). Sin cuadrante → se mantienen los pesos. «Other» nunca se favorece.
- Costes: 10 pb por lado sobre lo que se compra y lo que se vende: coste = 10 pb × Σ|Δw| = 20 pb × rotación
  (rotación = ½·Σ|Δw|). Se cargan en la rentabilidad del mes siguiente (el primero con los pesos nuevos):
  r_neto = (1 − coste)·(1 + r_bruto) − 1. TER no se descuenta.
- Antes del primer cuadrante la cartera es L0 (100 % mercado): la primera inclinación paga su coste.
L0 = mercado (`mkt`), sin costes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.factors.data import INDUSTRIAS12

SECTORES: dict[str, tuple[str, str, str, str]] = {
    "Goldilocks": ("BusEq", "Durbl", "Shops", "Money"),
    "Reflación": ("Enrgy", "Chems", "Manuf", "Money"),
    "Estanflación": ("Enrgy", "Utils", "NoDur", "Hlth"),
    "Deflación/recesión": ("NoDur", "Hlth", "Utils", "Telcm"),
}
NUCLEO = 0.50
COSTE_LADO = 0.0010
ACTIVOS = ("mkt", *INDUSTRIAS12)


def objetivo(cuadrante: str) -> pd.Series:
    if cuadrante not in SECTORES:
        raise ValueError(f"cuadrante desconocido: {cuadrante!r}")
    w = pd.Series(0.0, index=list(ACTIVOS))
    w["mkt"] = NUCLEO
    for s in SECTORES[cuadrante]:
        w[s] += (1 - NUCLEO) / 4
    return w


@dataclass
class Resultado:
    neto: pd.Series           # rentabilidad mensual neta
    bruto: pd.Series
    pesos: pd.DataFrame       # pesos al inicio de cada mes (tras operar al cierre anterior)
    rotacion: pd.Series       # ½·Σ|Δw| de la operación que rige ese mes
    costes: pd.Series         # fracción de la cartera
    cuadrante: pd.Series      # cuadrante vigente (el de la última operación)


def _nulo(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x)) or x is pd.NA


def simular(r: pd.DataFrame, senal: pd.Series, coste_lado: float = COSTE_LADO) -> Resultado:
    """r: rentabilidades (fracción) de ACTIVOS en los meses puntuados (PeriodIndex mensual consecutivo).
    senal: cuadrante al cierre de cada mes t (PeriodIndex); el del mes m − 1 decide los pesos del mes m."""
    faltan = [a for a in ACTIVOS if a not in r.columns]
    if faltan:
        raise ValueError(f"faltan activos: {faltan}")
    R = r[list(ACTIVOS)].to_numpy(float)
    if np.isnan(R).any():
        raise ValueError("rentabilidades con huecos")
    idx = r.index
    if len(idx) > 1 and not (idx[1:] == idx[:-1] + 1).all():
        raise ValueError("los meses puntuados no son consecutivos")
    w = np.zeros(len(ACTIVOS)); w[0] = 1.0                  # L0 antes del primer cuadrante
    objetivos = {q: objetivo(q).to_numpy() for q in SECTORES}
    vigente = None
    neto, bruto, pesos, rot, cst, cua = [], [], [], [], [], []
    for i, m in enumerate(idx):
        q = senal.get(m - 1)
        c, ro = 0.0, 0.0
        if not _nulo(q) and q != vigente:
            nuevo = objetivos[q] if q in objetivos else objetivo(q).to_numpy()
            d = np.abs(nuevo - w).sum()
            ro, c = d / 2, coste_lado * d
            w, vigente = nuevo.copy(), q
        g = float(w @ R[i])
        pesos.append(w.copy()); rot.append(ro); cst.append(c); cua.append(vigente)
        bruto.append(g); neto.append((1 - c) * (1 + g) - 1)
        w = w * (1 + R[i]) / (1 + g)
    S = lambda x, n: pd.Series(x, index=idx, name=n)   # noqa: E731
    return Resultado(S(neto, "neto"), S(bruto, "bruto"), pd.DataFrame(pesos, index=idx, columns=list(ACTIVOS)),
                     S(rot, "rotacion"), S(cst, "costes"), pd.Series(cua, index=idx, name="cuadrante", dtype=object))


# ---------------------------------------------------------------- métricas
def caida_maxima(r: pd.Series) -> float:
    v = np.concatenate([[1.0], np.cumprod(1 + r.to_numpy())])
    return float((v / np.maximum.accumulate(v) - 1).min())


def metricas(r: pd.Series, rf: pd.Series) -> dict:
    n = len(r)
    ex = r - rf.reindex(r.index)
    return {"meses": n, "rent_anual": float(np.prod(1 + r) ** (12 / n) - 1), "media_arit_anual": float(r.mean() * 12),
            "vol": float(r.std(ddof=1) * np.sqrt(12)),
            "sharpe": float(ex.mean() * 12 / (ex.std(ddof=1) * np.sqrt(12))), "caida_max": caida_maxima(r)}


def activa(s: pd.Series, l0: pd.Series) -> dict:
    """Rentabilidad activa de s frente a l0: aritmética anualizada (12·media de la diferencia mensual), geométrica
    (diferencia de rentabilidades anuales compuestas), error de seguimiento y ratio de información."""
    a = s - l0.reindex(s.index)
    n = len(a)
    te = float(a.std(ddof=1) * np.sqrt(12))
    geo = float(np.prod(1 + s) ** (12 / n) - np.prod(1 + l0.reindex(s.index)) ** (12 / n))
    return {"activa_arit": float(a.mean() * 12), "activa_geo": geo, "error_seguimiento": te,
            "ir": float(a.mean() * 12 / te) if te > 0 else float("nan")}


def mitades(idx: pd.PeriodIndex) -> tuple[pd.PeriodIndex, pd.PeriodIndex]:
    """Primera mitad = los ⌈n/2⌉ primeros meses puntuados; segunda = el resto."""
    k = (len(idx) + 1) // 2
    return idx[:k], idx[k:]


# ---------------------------------------------------------------- placebos
def barajar_bloques(valores: np.ndarray, bloque: int, rng: np.random.Generator) -> np.ndarray:
    """Parte la secuencia en bloques consecutivos de `bloque` meses (el último puede ser más corto) y permuta su orden.
    Conserva exactamente la frecuencia de cada cuadrante y casi todos los cambios (solo cambian los de las fronteras)."""
    trozos = [valores[i:i + bloque] for i in range(0, len(valores), bloque)]
    orden = rng.permutation(len(trozos))
    return np.concatenate([trozos[k] for k in orden])


def placebos(r: pd.DataFrame, senal: pd.Series, l0: pd.Series, n: int, bloque: int, semilla: int,
             coste_lado: float = COSTE_LADO) -> pd.DataFrame:
    """Para cada placebo: la señal de las fechas de decisión del periodo (meses m − 1) barajada por bloques y aplicada
    con la misma regla y costes. Devuelve activa_arit, activa_geo, ir y cambios por placebo."""
    dec = r.index - 1
    base = senal.reindex(dec).to_numpy(dtype=object)
    rng = np.random.default_rng(semilla)
    filas = []
    for _ in range(n):
        s = pd.Series(barajar_bloques(base, bloque, rng), index=dec, dtype=object)
        res = simular(r, s, coste_lado)
        a = activa(res.neto, l0)
        filas.append({"activa_arit": a["activa_arit"], "activa_geo": a["activa_geo"], "ir": a["ir"],
                      "cambios": int((res.rotacion > 0).sum())})
    return pd.DataFrame(filas)


def percentil_placebo(obs: float, plac: pd.Series) -> dict:
    """p conservador = (1 + #placebos ≥ observado) / (N + 1); 'mejor_que' = fracción de placebos estrictamente peores."""
    k = int((plac >= obs).sum())
    return {"p": (1 + k) / (len(plac) + 1), "mejor_que": float((plac < obs).mean()), "n": int(len(plac)),
            "p05": float(plac.quantile(0.05)), "p50": float(plac.quantile(0.50)), "p90": float(plac.quantile(0.90)),
            "p95": float(plac.quantile(0.95))}


def criterios(act: dict, pct: dict, act_mitades: list[dict], dd_s1: float, dd_l0: float) -> dict:
    """§5 a)-d). Lectura conservadora: la rentabilidad activa debe ser > 0 (≥ 0 en las mitades) tanto aritmética como
    geométrica; el placebo con el p conservador."""
    a = act["activa_arit"] > 0 and act["activa_geo"] > 0 and act["ir"] >= 0.20
    b = pct["p"] <= 0.10
    c = all(m["activa_arit"] >= 0 and m["activa_geo"] >= 0 for m in act_mitades)
    d = dd_s1 >= dd_l0 - 0.05
    return {"a": bool(a), "b": bool(b), "c": bool(c), "d": bool(d), "pasa": bool(a and b and c and d)}
