"""INT-3 (P-DEV-INT3 v0.1, docs/int/INT3_prerregistro_v0.md): contrastes régimen → rentabilidad real anual.
Funciones puras sobre un DataFrame país-año; la carga y la corrida están en scripts/int3_corrida.py.

- `contraste`: y = efecto fijo de país + b·D + e, con errores agrupados por año CR2 (Bell-McCaffrey) y t con G − 1 gl.
- `efectos_pais` + `encoger`: diferencia (estado − resto) en cada país y encogimiento empírico de Bayes hacia el común
  (DerSimonian-Laird): sustituto declarado del modelo jerárquico (PyMC no está instalado).
- `holm`, `placebo_fp`: Holm-Bonferroni y tasa de falsos positivos con los estados desplazados ≥ 6 años.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

DESFASE_MIN = 6


def _inv_sqrt(m: np.ndarray) -> np.ndarray:
    w, v = np.linalg.eigh((m + m.T) / 2)
    w = np.clip(w, 1e-12, None)
    return v @ np.diag(w ** -0.5) @ v.T


def contraste(y: pd.Series, d: pd.Series, pais: pd.Series, anio: pd.Series) -> dict:
    """Coeficiente de D (estado = 1 frente al resto = 0) con efectos fijos de país; CR2 agrupado por año."""
    ok = y.notna() & d.notna()
    y, d, pais, anio = y[ok].to_numpy(float), d[ok].to_numpy(float), pais[ok].to_numpy(), anio[ok].to_numpy()
    dums = pd.get_dummies(pais).to_numpy(float)
    X = np.column_stack([d, dums])
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    meat = np.zeros((X.shape[1], X.shape[1]))
    grupos = pd.Series(np.arange(len(y))).groupby(anio).indices
    for idx in grupos.values():
        Xg = X[idx]
        Hgg = Xg @ XtX_inv @ Xg.T
        Ag = _inv_sqrt(np.eye(len(idx)) - Hgg)
        ug = Xg.T @ (Ag @ e[idx])
        meat += np.outer(ug, ug)
    V = XtX_inv @ meat @ XtX_inv
    se = float(np.sqrt(V[0, 0]))
    G = len(grupos)
    t = float(b[0] / se) if se > 0 else np.nan
    p = float(2 * stats.t.sf(abs(t), G - 1))
    q = stats.t.ppf(0.975, G - 1)
    return {"efecto": float(b[0]), "se": se, "t": t, "p": p, "ic95": [float(b[0] - q * se), float(b[0] + q * se)],
            "n": int(len(y)), "n_estado": int(d.sum()), "años": int(G)}


def efectos_pais(y: pd.Series, d: pd.Series, pais: pd.Series) -> pd.DataFrame:
    filas = []
    for c in sorted(pais.unique()):
        m = (pais == c) & y.notna() & d.notna()
        y1, y0 = y[m & (d == 1)], y[m & (d == 0)]
        if len(y1) >= 3 and len(y0) >= 3:
            filas.append({"pais": c, "efecto": y1.mean() - y0.mean(),
                          "var": y1.var(ddof=1) / len(y1) + y0.var(ddof=1) / len(y0)})
    return pd.DataFrame(filas)


def encoger(ef: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    """Encogimiento empírico de Bayes (DerSimonian-Laird): devuelve efectos encogidos, media común y tau²."""
    k = len(ef)
    w = 1 / ef["var"]
    mu_fe = (w * ef["efecto"]).sum() / w.sum()
    Q = (w * (ef["efecto"] - mu_fe) ** 2).sum()
    tau2 = max(0.0, (Q - (k - 1)) / (w.sum() - (w ** 2).sum() / w.sum())) if k > 1 else 0.0
    w_re = 1 / (ef["var"] + tau2)
    mu = float((w_re * ef["efecto"]).sum() / w_re.sum())
    lam = tau2 / (tau2 + ef["var"])
    out = ef.assign(encogido=mu + lam * (ef["efecto"] - mu))
    return out, mu, float(tau2)


def holm(ps: dict, alfa: float = 0.05) -> dict:
    orden = sorted(ps, key=ps.get)
    out, m, sigue = {}, len(ps), True
    for i, k in enumerate(orden):
        sigue = sigue and ps[k] <= alfa / (m - i)
        out[k] = sigue
    return out


def desplazar(d: pd.Series, pais: pd.Series, anio: pd.Series, k: int) -> pd.Series:
    """Estado desplazado k años en círculo dentro de [min, max] del año (mismo k en todos los países)."""
    a0, a1 = int(anio.min()), int(anio.max())
    L = a1 - a0 + 1
    clave = dict(zip(zip(pais, anio), d))
    return pd.Series([clave.get((p, a0 + (a - a0 - k) % L), np.nan) for p, a in zip(pais, anio)], index=d.index)


def placebo_fp(y, d, pais, anio, alfa: float = 0.05) -> dict:
    """Fracción de desplazamientos (k ≥ DESFASE_MIN, sin el real) con p < alfa."""
    L = int(anio.max() - anio.min() + 1)
    ps = []
    for k in range(DESFASE_MIN, L - DESFASE_MIN + 1):
        dk = desplazar(d, pais, anio, k)
        if dk.sum() >= 10 and (dk == 0).sum() >= 10:
            ps.append(contraste(y, dk, pais, anio)["p"])
    ps = np.array(ps)
    return {"desplazamientos": int(len(ps)), "tasa_fp": float((ps < alfa).mean()) if len(ps) else None}


# --- sensibilidad DECLARADA A POSTERIORI (Validador, 27-oct): inferencia robusta a autocorrelación. No cambia el
# --- prerregistro ni la corrida única; se publica aparte y no decide.
def driscoll_kraay(y: pd.Series, d: pd.Series, pais: pd.Series, anio: pd.Series, lags: int | None = None) -> dict:
    """Mismo modelo que `contraste` (efecto fijo de país + b·D), con errores Driscoll-Kraay: suma por año de los
    productos x·e (robusta a cualquier correlación entre países en el mismo año) y núcleo de Bartlett sobre `lags` años
    (robusta a autocorrelación). lags por defecto = floor(4·(T/100)^(2/9)); t con T − 1 gl."""
    ok = y.notna() & d.notna()
    y, d, pais, anio = y[ok].to_numpy(float), d[ok].to_numpy(float), pais[ok].to_numpy(), anio[ok].to_numpy()
    X = np.column_stack([d, pd.get_dummies(pais).to_numpy(float)])
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    años = np.arange(int(anio.min()), int(anio.max()) + 1)
    h = np.zeros((len(años), X.shape[1]))                       # años sin datos: fila de ceros
    np.add.at(h, anio.astype(int) - int(anio.min()), X * e[:, None])
    T = int(len(np.unique(anio)))
    L = int(np.floor(4 * (T / 100) ** (2 / 9))) if lags is None else int(lags)
    S = h.T @ h
    for l in range(1, L + 1):
        G = h[l:].T @ h[:-l]
        S += (1 - l / (L + 1)) * (G + G.T)
    V = XtX_inv @ S @ XtX_inv * T / (T - 1)
    se = float(np.sqrt(V[0, 0]))
    t = float(b[0] / se) if se > 0 else np.nan
    q = stats.t.ppf(0.975, T - 1)
    return {"efecto": float(b[0]), "se": se, "t": t, "p": float(2 * stats.t.sf(abs(t), T - 1)),
            "ic95": [float(b[0] - q * se), float(b[0] + q * se)], "lags": L, "años": T}


def p_placebo(y, d, pais, anio) -> dict:
    """p empírico: fracción de desplazamientos (k ≥ DESFASE_MIN) con |t| ≥ |t real| (CR2). Calibra el contraste con la
    distribución nula observada en vez de con la t de Student."""
    t0 = abs(contraste(y, d, pais, anio)["t"])
    L = int(anio.max() - anio.min() + 1)
    ts = []
    for k in range(DESFASE_MIN, L - DESFASE_MIN + 1):
        dk = desplazar(d, pais, anio, k)
        if dk.sum() >= 10 and (dk == 0).sum() >= 10:
            ts.append(abs(contraste(y, dk, pais, anio)["t"]))
    ts = np.array(ts)
    return {"p_empirico": float((1 + (ts >= t0).sum()) / (1 + len(ts))), "desplazamientos": int(len(ts))}


def efectos_pais_sin_año(y: pd.Series, d: pd.Series, pais: pd.Series, anio: pd.Series) -> pd.DataFrame:
    """Como `efectos_pais`, pero sobre y sin la media de cada año (quita el choque global común): las estimaciones por
    país dejan de estar correladas por los años compartidos, que es lo que lleva τ² de DerSimonian-Laird a 0."""
    ok = y.notna() & d.notna()
    yd = y - y[ok].groupby(anio[ok]).transform("mean")
    return efectos_pais(yd, d, pais)
