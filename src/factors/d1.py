"""Motor de D1 «tendencia y volatilidad diaria multiactivo» (docs/factors/D1_tendencia_diaria_spec.md v1.0, CONGELADA).
Funciones puras sobre tablas diarias (DatetimeIndex de días hábiles, rentabilidades en fracción). Los datos los carga
src/factors/data.py; la corrida única la hace scripts/d1_desarrollo.py. El vivo (src/paper/d1.py) usa estas mismas
funciones: la regla es una sola.

Regla (§2), sin parámetros libres:
1. Tendencia: s = media de 1{rentabilidad compuesta de los últimos 21, 63 y 252 días > 0} ∈ {0, ⅓, ⅔, 1}
   (exactamente 0 cuenta como no positiva → 0).
2. Peso bruto = s × (10 % / N) / σ, σ = desviación típica (ddof = 1) de los últimos 63 días × √252. N = activos con
   historia completa (252 días) ese día (lectura anotada en docs/factors/D1_resultado_desarrollo.md).
3. Tope 40 % por activo; si la suma pasa del 100 %, se escala todo a 100 %. El resto, efectivo (rinde `rf`).
4. Banda: solo se opera un activo si |objetivo − actual| ≥ 3 pp (actual = peso que ha derivado con los precios).
   Si tras la banda la suma pasara del 100 %, se va al objetivo en todos (nunca hay apalancamiento).
5. Costes por lado: 5 pb (bolsa, bonos, oro) y 10 pb (materias primas) sobre |Δw|; se cargan en la rentabilidad del
   día siguiente (el primero con los pesos nuevos): r_neto = (1 − coste)·(1 + r_bruto) − 1.
Cronología: señal con el cierre de d → pesos que rigen la rentabilidad de d + 1.
Un activo sin historia completa tiene peso 0 (aún no está en el universo de ese día).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

VENTANAS = (21, 63, 252)
VENTANA_VOL = 63
OBJ_VOL = 0.10
TOPE = 0.40
BANDA = 0.03
COSTE_LADO = {"us": 0.0005, "xus": 0.0005, "bonos": 0.0005, "oro": 0.0005, "mp": 0.0010}
L1_PESOS = {"us": 0.70, "bonos": 0.15, "oro": 0.15}
BLOQUE_PLACEBO = 63


# ---------------------------------------------------------------- señal y pesos objetivo
def tendencia(r: pd.DataFrame) -> pd.DataFrame:
    """s al cierre de cada día (NaN si el activo no tiene 252 rentabilidades seguidas hasta ese día)."""
    lr = np.log1p(r)
    partes = [(lr.rolling(v, min_periods=v).sum() > 0).astype(float).where(lr.rolling(v, min_periods=v).count() == v)
              for v in VENTANAS]
    return sum(partes) / len(VENTANAS)


def volatilidad(r: pd.DataFrame) -> pd.DataFrame:
    return r.rolling(VENTANA_VOL, min_periods=VENTANA_VOL).std(ddof=1) * np.sqrt(252)


def objetivos(s: pd.DataFrame, sigma: pd.DataFrame) -> pd.DataFrame:
    """Pesos objetivo (pasos 2-3) de cada día. Activos con s o σ NaN → 0 y no cuentan en N."""
    sigma = sigma.reindex(index=s.index, columns=s.columns)
    ok = s.notna() & sigma.notna() & (sigma > 0)
    n = ok.sum(axis=1)
    w = (s * OBJ_VOL / sigma).where(ok, 0.0).div(n.where(n > 0), axis=0).fillna(0.0)
    w = w.clip(upper=TOPE)
    tot = w.sum(axis=1)
    return w.div(tot.where(tot > 1, 1.0), axis=0)


def objetivo(s: pd.Series, sigma: pd.Series) -> pd.Series:
    """Pesos objetivo de un solo día (lo usa el vivo)."""
    return objetivos(s.to_frame().T, sigma.to_frame().T).iloc[0]


def aplica_banda(obj: np.ndarray, actual: np.ndarray, banda: float = BANDA) -> np.ndarray:
    """Paso 4. Nuevo vector de pesos tras operar solo los activos que se separan ≥ banda."""
    nuevo = np.where(np.abs(obj - actual) >= banda - 1e-12, obj, actual)
    return obj.copy() if nuevo.sum() > 1 + 1e-12 else nuevo


# ---------------------------------------------------------------- simulación
@dataclass
class Resultado:
    neto: pd.Series
    bruto: pd.Series
    pesos: pd.DataFrame        # pesos que rigen cada día (tras operar al cierre anterior)
    rotacion: pd.Series        # ½·Σ|Δw| (incluido el efectivo) de la operación que rige ese día
    costes: pd.Series


def simular(r: pd.DataFrame, rf: pd.Series, obj: pd.DataFrame, *, banda: float = BANDA,
            coste_lado: dict | None = None, rebalanceo: pd.Series | None = None) -> Resultado:
    """r: rentabilidades de los días puntuados (consecutivos); obj: pesos objetivo al cierre de cada día de decisión
    (debe incluir el día anterior al primero puntuado). El objetivo del día d − 1 rige d. `rebalanceo` (bool por día
    de decisión): si se da, solo se opera esos días y sin banda (L1)."""
    cl = coste_lado or COSTE_LADO
    cols = list(r.columns)
    R = r.to_numpy(float)
    if np.isnan(R).any():
        raise ValueError("rentabilidades con huecos en el periodo puntuado")
    RF = rf.reindex(r.index).to_numpy(float)
    if np.isnan(RF).any():
        raise ValueError("efectivo con huecos en el periodo puntuado")
    pos = obj.index.get_indexer(r.index)
    if (pos < 1).any() or not (np.diff(pos) == 1).all():
        raise ValueError("los objetivos deben cubrir el día anterior a cada día puntuado, sin saltos")
    O = obj[cols].to_numpy(float)
    c = np.array([cl[k] for k in cols])
    w = np.zeros(len(cols))
    neto, bruto, pesos, rot, cst = [], [], [], [], []
    for i in range(len(r)):
        o = O[pos[i] - 1]
        if rebalanceo is None:
            nuevo = aplica_banda(o, w, banda)
        else:
            nuevo = o.copy() if bool(rebalanceo.iloc[pos[i] - 1]) or i == 0 else w
        dw = nuevo - w
        ro = (np.abs(dw).sum() + abs(dw.sum())) / 2
        co = float(c @ np.abs(dw))
        w = nuevo
        g = float(w @ R[i] + (1 - w.sum()) * RF[i])
        pesos.append(w.copy()); rot.append(ro); cst.append(co); bruto.append(g); neto.append((1 - co) * (1 + g) - 1)
        w = w * (1 + R[i]) / (1 + g)
    S = lambda x, n: pd.Series(x, index=r.index, name=n)   # noqa: E731
    return Resultado(S(neto, "neto"), S(bruto, "bruto"), pd.DataFrame(pesos, index=r.index, columns=cols),
                     S(rot, "rotacion"), S(cst, "costes"))


def l1_objetivos(index: pd.DatetimeIndex, cols: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    """L1 = 70/15/15 bolsa EE. UU./bonos/oro, rebalanceo anual (al último cierre de cada año). Sin costes."""
    o = pd.DataFrame(0.0, index=index, columns=cols)
    for k, v in L1_PESOS.items():
        if k not in cols:
            raise ValueError(f"L1 necesita '{k}'")
        o[k] = v
    yr = pd.Series(index.year, index=index)
    return o, (yr != yr.shift(-1)) & yr.shift(-1).notna()   # el último día de la muestra no es cierre de año


# ---------------------------------------------------------------- métricas
def caida_maxima(r: pd.Series) -> float:
    v = np.concatenate([[1.0], np.cumprod(1 + r.to_numpy())])
    return float((v / np.maximum.accumulate(v) - 1).min())


def sharpe(r: pd.Series, rf: pd.Series) -> float:
    ex = r - rf.reindex(r.index)
    return float(ex.mean() / ex.std(ddof=1) * np.sqrt(252))


def metricas(res_neto: pd.Series, rf: pd.Series, rotacion: pd.Series | None = None) -> dict:
    n = len(res_neto)
    out = {"dias": n, "rent_anual": float(np.prod(1 + res_neto) ** (252 / n) - 1),
           "vol": float(res_neto.std(ddof=1) * np.sqrt(252)), "sharpe": sharpe(res_neto, rf),
           "caida_max": caida_maxima(res_neto)}
    if rotacion is not None:
        out["rotacion_anual"] = float(rotacion.mean() * 252)
    return out


def mitades(idx: pd.DatetimeIndex) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """Primera mitad = los ⌈n/2⌉ primeros días puntuados; segunda = el resto (una sola corrida, partida)."""
    k = (len(idx) + 1) // 2
    return idx[:k], idx[k:]


# ---------------------------------------------------------------- placebos
def barajar_bloques(n: int, bloque: int, rng: np.random.Generator) -> np.ndarray:
    """Índices 0..n−1 partidos en bloques consecutivos de `bloque` (el último más corto) en orden permutado."""
    trozos = [np.arange(i, min(i + bloque, n)) for i in range(0, n, bloque)]
    return np.concatenate([trozos[k] for k in rng.permutation(len(trozos))])


def placebos(r: pd.DataFrame, rf: pd.Series, s: pd.DataFrame, sigma: pd.DataFrame, n: int, semilla: int,
             bloque: int = BLOQUE_PLACEBO) -> pd.Series:
    """Sharpe neto de `n` placebos: la matriz de señales s de los días de decisión del periodo (todas las columnas a
    la vez) barajada por bloques de `bloque` días; σ, rentabilidades, banda y costes reales."""
    dec = s.index[s.index.get_indexer(r.index) - 1]
    S0 = s.loc[dec]
    rng = np.random.default_rng(semilla)
    out = []
    for _ in range(n):
        orden = barajar_bloques(len(dec), bloque, rng)
        sp = pd.DataFrame(S0.to_numpy()[orden], index=dec, columns=S0.columns)
        # un activo sin historia ese día sigue fuera del universo (no se le inventa señal)
        sp = sp.where(S0.notna()).where(sp.notna() | S0.isna(), 0.0)
        res = simular(r, rf, objetivos(sp, sigma.loc[dec]).reindex(s.index))
        out.append(sharpe(res.neto, rf))
    return pd.Series(out, name="sharpe_placebo")


def percentil_placebo(obs: float, plac: pd.Series) -> dict:
    """p conservador = (1 + #placebos ≥ observado) / (N + 1); 'mejor_que' = fracción estrictamente peor."""
    k = int((plac >= obs).sum())
    return {"p": (1 + k) / (len(plac) + 1), "mejor_que": float((plac < obs).mean()), "n": int(len(plac)),
            "p50": float(plac.quantile(0.5)), "p90": float(plac.quantile(0.9))}


def criterios(m_d1: dict, m_l1: dict, m_l2: dict, pct: dict, sh_mitades: list[tuple[float, float]]) -> dict:
    """§5 a)-d) tal cual; c) con el p conservador (p ≤ 0,10) y d) con ≥ en cada mitad (D1, L2)."""
    a = m_d1["sharpe"] >= m_l1["sharpe"] and m_d1["sharpe"] >= m_l2["sharpe"]
    b = m_d1["caida_max"] >= m_l1["caida_max"]          # caídas negativas: ≥ = menos profunda
    c = pct["p"] <= 0.10
    d = all(x >= y for x, y in sh_mitades)
    return {"a": bool(a), "b": bool(b), "c": bool(c), "d": bool(d), "pasa": bool(a and b and c and d)}
