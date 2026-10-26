"""INT-1: régimen ex post por país y fechado de recesiones (docs/int/INT1_diseno_v0.md, decisiones del usuario 27-oct:
inflación relativa + 2 % principal y 3 % absoluto como sensibilidad; Bry-Boschan fase ≥ 6 m, ciclo ≥ 15 m; núcleo de 14
países y 4 de prueba). Funciones puras; los datos llegan del panel (≤ 2004). Parámetros FIJADOS aquí antes de correr.

Etiqueta ex post (describe "dónde estábamos", con datos revisados y ventanas CENTRADAS; no es una señal):
- G alto si el crecimiento está por encima de su tendencia centrada; I alta si la inflación está por encima de su media
  centrada Y del 2 % (principal) o del 3 % (sensibilidad). Probabilística: P = Φ(distancia / s), con s = ESCALA × la
  dispersión robusta (1,4826 · MAD) de la distancia en cada país; "frontera" si la probabilidad del cuadrante más probable
  < 0,55 (como la v1.1). Bordes: si la ventana centrada no está completa (últimos años/meses antes del corte de 2004 o
  primeros de la serie), la observación se marca `truncada`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

# --- parámetros (fijados antes de correr) ---
VENTANA_ANUAL = 11            # años, centrada (t − 5 … t + 5)
VENTANA_MENSUAL = 121         # meses, centrada (≈ 10 años)
SUAVIZADO_MENSUAL = 7         # meses, media centrada de la brecha (t − 3 … t + 3), como la v1.1
ESCALA = 0.5                  # s = 0,5 · dispersión robusta de la distancia
UMBRAL_I_PRINCIPAL, UMBRAL_I_ABSOLUTO = 0.02, 0.03
FRONTERA = 0.55
BB_VENTANA, BB_FASE_MIN, BB_CICLO_MIN, BB_BORDE = 5, 6, 15, 6     # Bry-Boschan mensual
CUADRANTES = {(True, False): "expansion", (True, True): "sobrecalentamiento", (False, True): "estanflacion",
              (False, False): "crecimiento_bajo"}


def _escala(d: pd.Series) -> float:
    mad = (d - d.median()).abs().median() * 1.4826
    return max(ESCALA * float(mad), 1e-6)


def _centrada(s: pd.Series, n: int) -> tuple[pd.Series, pd.Series]:
    media = s.rolling(n, center=True, min_periods=n // 2 + 1).mean()
    completa = s.rolling(n, center=True, min_periods=n).count() == n
    return media, ~completa


def cuadrante(p_g: pd.Series, p_i: pd.Series) -> pd.DataFrame:
    probs = pd.DataFrame({"expansion": p_g * (1 - p_i), "sobrecalentamiento": p_g * p_i,
                          "estanflacion": (1 - p_g) * p_i, "crecimiento_bajo": (1 - p_g) * (1 - p_i)})
    out = probs.copy()
    ok = p_g.notna() & p_i.notna()
    out["cuadrante"] = probs.fillna(-1.0).idxmax(axis=1).where(ok)
    out["p_max"] = probs.max(axis=1)
    out["frontera"] = out["p_max"] < FRONTERA
    return out


def etiqueta(crec: pd.Series, infl: pd.Series, n: int, umbral_i: float = UMBRAL_I_PRINCIPAL,
             relativa: bool = True, suavizado: int = 1) -> pd.DataFrame:
    """crec: crecimiento (anual) o log-nivel (mensual, se compara con su tendencia); infl: inflación en fracción."""
    t_g, trunc_g = _centrada(crec, n)
    dg = crec - t_g
    if suavizado > 1:
        dg = dg.rolling(suavizado, center=True, min_periods=suavizado // 2 + 1).mean()
    p_g = pd.Series(norm.cdf(dg / _escala(dg.dropna())), index=crec.index).where(dg.notna())
    if relativa:
        t_i, trunc_i = _centrada(infl, n)
        di = np.minimum(infl - t_i, infl - umbral_i)
    else:
        trunc_i = pd.Series(False, index=infl.index)
        di = infl - umbral_i
    p_i = pd.Series(norm.cdf(di / _escala(di.dropna())), index=infl.index).where(di.notna())
    out = cuadrante(p_g, p_i)
    out["p_g_alto"], out["p_i_alta"] = p_g, p_i
    out["truncada"] = (trunc_g.reindex(out.index, fill_value=True) | trunc_i.reindex(out.index, fill_value=True))
    return out


# --- recesiones anuales (convención JST: pico = máximo local del PIB real per cápita antes de una caída) ---
def recesiones_anuales(pib_pc: pd.Series, crisis: pd.Series | None = None) -> pd.DataFrame:
    x = pib_pc.dropna()
    filas = []
    i = 1
    v = x.to_numpy()
    while i < len(v) - 1:
        if v[i] > v[i - 1] and v[i + 1] < v[i]:
            j = i + 1
            while j < len(v) - 1 and v[j + 1] < v[j]:
                j += 1
            pico, valle = int(x.index[i]), int(x.index[j])
            fin = crisis is not None and bool(crisis.reindex(range(pico - 2, pico + 3)).fillna(0).max() > 0)
            filas.append({"pico": pico, "valle": valle, "tipo": "financiera" if fin else "normal"})
            i = j
        i += 1
    return pd.DataFrame(filas, columns=["pico", "valle", "tipo"])


# --- Bry-Boschan mensual (versión estándar simplificada) ---
def bry_boschan(log_ip: pd.Series) -> pd.DataFrame:
    """Picos y valles de log_ip (mensual, sin huecos internos): media móvil centrada de 3 meses, extremos locales en
    ± BB_VENTANA meses, alternancia, fase mínima BB_FASE_MIN, ciclo mínimo BB_CICLO_MIN, sin giros a menos de BB_BORDE
    meses de los extremos de la serie."""
    s = log_ip.dropna()
    if len(s) < 2 * BB_VENTANA + 1:
        return pd.DataFrame(columns=["fecha", "tipo"])
    y = s.rolling(3, center=True, min_periods=1).mean().to_numpy()
    n, w = len(y), BB_VENTANA
    cands = []
    for t in range(w, n - w):
        seg = y[t - w:t + w + 1]
        if y[t] == seg.max():
            cands.append((t, "pico"))
        elif y[t] == seg.min():
            cands.append((t, "valle"))
    # alternancia: entre dos del mismo tipo, quedarse con el más extremo
    alt: list[tuple[int, str]] = []
    for t, k in cands:
        if alt and alt[-1][1] == k:
            if (k == "pico" and y[t] > y[alt[-1][0]]) or (k == "valle" and y[t] < y[alt[-1][0]]):
                alt[-1] = (t, k)
        else:
            alt.append((t, k))
    # bordes
    alt = [(t, k) for t, k in alt if BB_BORDE <= t <= n - 1 - BB_BORDE]
    # regla de los extremos (Bry-Boschan): el primer giro tiene que ser más extremo que todo lo anterior y el último
    # más extremo que todo lo posterior (un valle no puede estar por encima del inicio de la serie, etc.)
    def _extremo_ok(t: int, k: str, tramo: np.ndarray) -> bool:
        return (y[t] >= tramo.max()) if k == "pico" else (y[t] <= tramo.min())
    while alt and not _extremo_ok(alt[0][0], alt[0][1], y[:alt[0][0] + 1]):
        alt.pop(0)
    while alt and not _extremo_ok(alt[-1][0], alt[-1][1], y[alt[-1][0]:]):
        alt.pop()
    # fase y ciclo mínimos: quitar el par más corto y repetir
    cambiado = True
    while cambiado and len(alt) >= 2:
        cambiado = False
        for i in range(len(alt) - 1):
            fase_corta = alt[i + 1][0] - alt[i][0] < BB_FASE_MIN
            ciclo_corto = i + 2 < len(alt) and alt[i + 2][0] - alt[i][0] < BB_CICLO_MIN
            if fase_corta or ciclo_corto:
                del alt[i:i + 2]
                cambiado = True
                break
    return pd.DataFrame({"fecha": [s.index[t] for t, _ in alt], "tipo": [k for _, k in alt]})


def concordancia(picos: list[pd.Timestamp], externos: list[pd.Timestamp], tolerancia_meses: int) -> dict:
    """% de picos externos con un pico propio a ± tolerancia, y desfase medio (propio − externo, meses)."""
    desf = []
    for e in externos:
        d = [(p.year - e.year) * 12 + p.month - e.month for p in picos]
        d = [x for x in d if abs(x) <= tolerancia_meses]
        if d:
            desf.append(min(d, key=abs))
    return {"externos": len(externos), "detectados": len(desf),
            "pct": round(len(desf) / len(externos), 3) if externos else None,
            "desfase_medio_meses": round(float(np.mean(desf)), 1) if desf else None}


# --- segundo intento del fechado mensual (declarado, 27-oct): indicador coincidente compuesto ---
def indice_coincidente(log_ip: pd.Series, paro: pd.Series | None) -> pd.Series:
    """Estilo Conference Board: variaciones mensuales de log IP y de −paro (puntos), cada una dividida por su desviación
    típica (en la muestra ≤ 2004 del país), media con pesos iguales de las disponibles cada mes, acumulada. Sin paro (o
    en los meses sin él), solo IP. Se aplica después el mismo Bry-Boschan."""
    comps = [log_ip.diff()]
    if paro is not None and paro.notna().sum() > 24:
        comps.append(-paro.diff())
    z = pd.concat([c / c.std() for c in comps], axis=1)
    m = z.mean(axis=1, skipna=True).where(z.notna().any(axis=1))
    return m.fillna(0.0).cumsum().where(log_ip.notna())
