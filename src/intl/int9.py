"""INT-9 fase 1: factores comunes y clusters "sin mirar resultados" (docs/int/INT9_fase1.md).

Funciones puras sobre matrices de INDICADORES (X). Ninguna función de este módulo recibe un objetivo ni una
rentabilidad futura, salvo las de potencia (§ potencia), que trabajan con objetivos SINTÉTICOS generados aquí a partir
de propiedades de Y que no tocan los factores (tasa de eventos, varianza entre años y dentro del año).
La carga de datos (≤ 2004) está en scripts/int9_fase1.py; aquí no se lee nada.

Piezas:
- `cubo`: indicadores país × año → paneles años × países, con winsorización 1/99 conjunta, guerras e hiperinflación fuera.
- `estandarizar`, `em_pca` (Stock-Watson 2002: PCA con huecos por EM), `corr_pares` (correlación con pares completos).
- Número de factores: `bai_ng` (IC_p1, IC_p2, IC_p3), `autovalores`, `paralelo` (Horn: columnas permutadas en el tiempo,
  mismo patrón de huecos).
- Estabilidad: `congruencia` (Tucker), `alinear` (emparejar factores por |congruencia|), `bloques` (bootstrap de
  bloques móviles de años), `ari` (índice de Rand ajustado).
- Clusters: `jerarquico` (enlace medio sobre 1 − correlación).
- Potencia: `pot_logit` (entrada en recesión) y `pot_mco` (bolsa real), valor crítico SIMULADO bajo la nula.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import squareform
from scipy.stats import rankdata

GUERRAS = set(range(1914, 1919)) | set(range(1939, 1946))   # como src/intl/int4.GUERRAS


# ------------------------------------------------------------------ preparación
def cubo(ind: dict[str, pd.DataFrame], fuera: set | None = None, sin_guerras: bool = True,
         wins: float = 0.01) -> dict[str, pd.DataFrame]:
    """ind: {indicador: DataFrame años × países}. Pone NaN en guerras (si `sin_guerras`) y en {(país, año)} de `fuera`;
    después winsoriza cada indicador con sus percentiles `wins`/1 − `wins` conjuntos (todos los países)."""
    out = {}
    for k, p in ind.items():
        p = p.astype(float).replace([np.inf, -np.inf], np.nan).copy()
        if sin_guerras:
            p.loc[p.index.isin(list(GUERRAS))] = np.nan
        for c, t in (fuera or set()):
            if c in p.columns and t in p.index:
                p.loc[t, c] = np.nan
        v = p.to_numpy().ravel()
        v = v[np.isfinite(v)]
        if v.size:
            lo, hi = np.quantile(v, [wins, 1 - wins])
            p = p.clip(lo, hi)
        out[k] = p
    return out


def apilar(c: dict[str, pd.DataFrame], paises: list[str], min_col: int = 20) -> pd.DataFrame:
    """Matriz años × (país|indicador); quita columnas con menos de `min_col` datos y años sin ninguno."""
    cols = {f"{p}|{k}": c[k][p] for k in c for p in paises if p in c[k].columns}
    X = pd.DataFrame(cols)
    X = X.loc[:, X.notna().sum() >= min_col]
    return X.loc[X.notna().any(axis=1)]


def apilar_filas(c: dict[str, pd.DataFrame], paises: list[str]) -> pd.DataFrame:
    """Filas país-año, columnas indicadores, cada indicador estandarizado DENTRO de cada país (quita su media y su
    escala: lo que queda es la estructura común de los indicadores)."""
    partes = []
    for p in paises:
        d = pd.DataFrame({k: c[k][p] for k in c if p in c[k].columns})
        d = (d - d.mean()) / d.std(ddof=1)
        d["pais"] = p
        partes.append(d.reset_index(names="año"))
    return pd.concat(partes, ignore_index=True).set_index(["pais", "año"])


def estandarizar(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, float)
    m, s = np.nanmean(X, 0), np.nanstd(X, 0, ddof=1)
    return (X - m) / np.where(s > 0, s, 1)


# ------------------------------------------------------------------ PCA
def corr_pares(X: np.ndarray, min_pares: int = 10) -> np.ndarray:
    """Correlación de Pearson con los pares completos de cada par de columnas (NaN si hay menos de `min_pares`)."""
    X = np.asarray(X, float)
    df = pd.DataFrame(X)
    return df.corr(min_periods=min_pares).to_numpy()


def autovalores(R: np.ndarray) -> np.ndarray:
    """Autovalores (orden descendente) de una matriz de correlación; NaN → 0 fuera de la diagonal."""
    R = np.where(np.isfinite(R), R, 0.0)
    np.fill_diagonal(R, 1.0)
    return np.sort(np.linalg.eigvalsh((R + R.T) / 2))[::-1]


def em_pca(X: np.ndarray, r: int, it: int = 500, tol: float = 1e-7) -> dict:
    """PCA con huecos por EM (Stock-Watson 2002). X se estandariza por columnas con los datos observados; los huecos
    empiezan en 0 y se rellenan con el ajuste de r factores hasta converger. F: T × r con F'F/T = I; L: N × r;
    `ajuste` = F L'. `ssr_obs`: media de residuos² en las celdas observadas."""
    Z = estandarizar(X)
    obs = np.isfinite(Z)
    W = np.where(obs, Z, 0.0)
    T = W.shape[0]
    prev = np.inf
    if r == 0:
        fit = np.zeros_like(W)
        return {"F": np.zeros((T, 0)), "L": np.zeros((W.shape[1], 0)), "ajuste": fit, "Z": Z, "obs": obs,
                "ssr_obs": float(np.mean(Z[obs] ** 2)), "iter": 0}
    for i in range(it):
        U, s, Vt = np.linalg.svd(W - W.mean(0), full_matrices=False)
        F = U[:, :r] * np.sqrt(T)
        L = (Vt[:r].T * s[:r]) / np.sqrt(T)
        fit = F @ L.T + W.mean(0)
        ssr = float(np.mean((Z[obs] - fit[obs]) ** 2))
        W = np.where(obs, Z, fit)
        if abs(prev - ssr) < tol:
            break
        prev = ssr
    # orientación: carga media positiva (la convención de signo no es un resultado)
    sg = np.sign(L.sum(0))
    sg[sg == 0] = 1
    return {"F": F * sg, "L": L * sg, "ajuste": fit, "Z": Z, "obs": obs, "ssr_obs": ssr, "iter": i + 1,
            "W": W}


def bai_ng(X: np.ndarray, rmax: int = 8) -> dict:
    """Criterios IC_p1, IC_p2, IC_p3 de Bai y Ng (2002) con V(k) = media de residuos² en las celdas observadas tras el
    EM-PCA de k factores. N y T: columnas y filas de X."""
    T, N = np.asarray(X).shape
    V = np.array([em_pca(X, k)["ssr_obs"] for k in range(rmax + 1)])
    k = np.arange(rmax + 1)
    c = (N + T) / (N * T)
    pen = {"IC_p1": k * c * np.log(1 / c), "IC_p2": k * c * np.log(min(N, T)),
           "IC_p3": k * np.log(min(N, T)) / min(N, T)}
    out = {"V": V.tolist()}
    for nom, p in pen.items():
        ic = np.log(V) + p
        out[nom] = int(np.argmin(ic))
    return out


def paralelo(X: np.ndarray, B: int, rng: np.random.Generator, q: float = 0.95) -> dict:
    """Análisis paralelo de Horn sobre la correlación con pares completos: en cada réplica se permutan en el tiempo los
    valores observados de cada columna (mismo patrón de huecos). Factores retenidos = autovalores reales por encima del
    percentil q de los permutados, contados desde el primero hasta el primer fallo."""
    X = np.asarray(X, float)
    ev = autovalores(corr_pares(X))
    sims = np.empty((B, len(ev)))
    for b in range(B):
        Xp = X.copy()
        for j in range(X.shape[1]):
            o = np.isfinite(X[:, j])
            Xp[o, j] = rng.permutation(X[o, j])
        sims[b] = autovalores(corr_pares(Xp))
    umbral = np.quantile(sims, q, axis=0)
    n = 0
    while n < len(ev) and ev[n] > umbral[n]:
        n += 1
    return {"autovalores": ev.tolist(), "umbral": umbral.tolist(), "retenidos": n}


def pca_corr(R: np.ndarray, r: int) -> dict:
    """Cargas (autovector × √autovalor) de los r primeros componentes de una matriz de correlación; signo: carga
    media positiva."""
    R = np.where(np.isfinite(R), R, 0.0)
    np.fill_diagonal(R, 1.0)
    w, V = np.linalg.eigh((R + R.T) / 2)
    o = np.argsort(w)[::-1]
    w, V = w[o], V[:, o]
    L = V[:, :r] * np.sqrt(np.maximum(w[:r], 0))
    sg = np.sign(L.sum(0))
    sg[sg == 0] = 1
    return {"L": L * sg, "autovalores": w, "cuota": w / w.sum()}


def puntuar(Z: np.ndarray, L: np.ndarray, min_obs: int) -> np.ndarray:
    """Puntuación de factor por regresión de cada fila sobre las cargas, con las columnas observadas de esa fila
    (NaN si tiene menos de `min_obs`)."""
    Z = np.asarray(Z, float)
    out = np.full((Z.shape[0], L.shape[1]), np.nan)
    for i, z in enumerate(Z):
        o = np.isfinite(z)
        if o.sum() >= max(min_obs, L.shape[1]):
            out[i] = np.linalg.lstsq(L[o], z[o], rcond=None)[0]
    return out


# ------------------------------------------------------------------ estabilidad
def congruencia(a: np.ndarray, b: np.ndarray) -> float:
    """Coeficiente de congruencia de Tucker entre dos vectores de cargas (con huecos fuera)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    o = np.isfinite(a) & np.isfinite(b)
    a, b = a[o], b[o]
    d = np.sqrt((a @ a) * (b @ b))
    return float(a @ b / d) if d > 0 else np.nan


def alinear(Lref: np.ndarray, L: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Empareja las columnas de L con las de Lref maximizando la |congruencia| total y les pone el signo de Lref.
    Devuelve (L reordenada y con signo, congruencias de cada par)."""
    k = Lref.shape[1]
    C = np.array([[congruencia(Lref[:, i], L[:, j]) for j in range(L.shape[1])] for i in range(k)])
    fi, co = linear_sum_assignment(-np.abs(np.nan_to_num(C)))
    out = np.full_like(Lref, np.nan, dtype=float)
    cg = np.full(k, np.nan)
    for i, j in zip(fi, co):
        s = np.sign(C[i, j]) or 1.0
        out[:, i] = L[:, j] * s
        cg[i] = abs(C[i, j])
    return out, cg


def bloques(T: int, largo: int, rng: np.random.Generator) -> np.ndarray:
    """Índices de un bootstrap de bloques móviles de longitud `largo` sobre 0 … T − 1 (longitud T)."""
    n = int(np.ceil(T / largo))
    ini = rng.integers(0, T - largo + 1, n)
    return np.concatenate([np.arange(s, s + largo) for s in ini])[:T]


def ari(a, b) -> float:
    """Índice de Rand ajustado (Hubert-Arabie) entre dos particiones."""
    a, b = pd.factorize(np.asarray(a))[0], pd.factorize(np.asarray(b))[0]
    tab = pd.crosstab(a, b).to_numpy()
    c2 = lambda x: x * (x - 1) / 2  # noqa: E731
    sij, sa, sb, n = c2(tab).sum(), c2(tab.sum(1)).sum(), c2(tab.sum(0)).sum(), c2(tab.sum())
    esp = sa * sb / n
    mx = (sa + sb) / 2
    return float((sij - esp) / (mx - esp)) if mx != esp else 1.0


def jerarquico(R: np.ndarray, k: int, absoluta: bool = False) -> dict:
    """Clusters por enlace medio con distancia 1 − correlación (1 − |correlación| si `absoluta`), cortado en k grupos."""
    R = np.where(np.isfinite(R), R, 0.0)
    D = 1 - (np.abs(R) if absoluta else R)
    D = (D + D.T) / 2
    np.fill_diagonal(D, 0.0)
    Z = linkage(squareform(np.maximum(D, 0), checks=False), method="average")
    return {"etiquetas": fcluster(Z, k, criterion="maxclust"), "enlace": Z}


def coasignacion(etiquetas: np.ndarray) -> np.ndarray:
    """Matriz B × n × n → frecuencia con que cada par cae en el mismo cluster."""
    E = np.asarray(etiquetas)
    return (E[:, :, None] == E[:, None, :]).mean(0)


# ------------------------------------------------------------------ potencia (objetivos SINTÉTICOS)
def auc(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y).astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(p)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def auc_estrat(y, p, g) -> float:
    """AUC estratificada por país (como src/intl/int6.auc_estrat)."""
    num = den = 0.0
    for c in np.unique(g):
        f = g == c
        yy, pp = np.asarray(y)[f].astype(bool), np.asarray(p)[f]
        n1, n0 = yy.sum(), (~yy).sum()
        if n1 == 0 or n0 == 0:
            continue
        r = rankdata(pp)
        num += r[yy].sum() - n1 * (n1 + 1) / 2
        den += n1 * n0
    return num / den if den else np.nan


def _logit(X: np.ndarray, y: np.ndarray, it: int = 50) -> np.ndarray:
    Xc = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(Xc.shape[1])
    m = min(max(y.mean(), 1e-4), 1 - 1e-4)
    b[0] = np.log(m / (1 - m))
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(Xc @ b, -30, 30)))
        H = (Xc * (p * (1 - p))[:, None]).T @ Xc + 1e-8 * np.eye(len(b))
        paso = np.linalg.solve(H, Xc.T @ (y - p))
        b += paso
        if np.max(np.abs(paso)) < 1e-8:
            break
    return b


def loco(X: np.ndarray, y: np.ndarray, g: np.ndarray) -> np.ndarray:
    """Predicción dejando un país fuera (logit con intercepto)."""
    p = np.full(len(y), np.nan)
    for c in np.unique(g):
        f = g == c
        b = _logit(X[~f], y[~f])
        p[f] = 1 / (1 + np.exp(-np.clip(b[0] + X[f] @ b[1:], -30, 30)))
    return p


def sim_eventos(eta: np.ndarray, anio: np.ndarray, sigma_u: float, rng: np.random.Generator) -> np.ndarray:
    """y ~ Bernoulli(logit⁻¹(eta + u_año)), u_año ~ N(0, σ_u²) común a todos los países del año."""
    años, inv = np.unique(anio, return_inverse=True)
    u = rng.standard_normal(len(años)) * sigma_u
    return (rng.random(len(eta)) < 1 / (1 + np.exp(-(eta + u[inv])))).astype(float)


def sobredispersion(y: np.ndarray, anio: np.ndarray) -> float:
    """Var(proporción de eventos por año) / var binomial esperada (1 = sin agrupamiento por año). Propiedad de Y sola."""
    df = pd.DataFrame({"y": y, "a": anio}).groupby("a").y.agg(["mean", "size"])
    p = float(np.average(df["mean"], weights=df["size"]))
    esp = np.mean(p * (1 - p) / df["size"])
    return float(df["mean"].var(ddof=1) / esp) if esp > 0 else np.nan


def calibrar_sigma_u(tasa: float, anio: np.ndarray, objetivo: float, rng: np.random.Generator,
                     rejilla=np.linspace(0, 2.5, 26), nsim: int = 60) -> float:
    """σ_u cuya sobredispersión simulada (sin factores) se acerca más a la observada de Y."""
    a0 = np.log(tasa / (1 - tasa))
    mejor, dist = 0.0, np.inf
    for s in rejilla:
        # intercepto corregido para mantener la tasa media (aproximación logit-normal)
        a = a0 * np.sqrt(1 + np.pi * s ** 2 / 8)
        v = np.mean([sobredispersion(sim_eventos(np.full(len(anio), a), anio, s, rng), anio) for _ in range(nsim)])
        if abs(v - objetivo) < dist:
            mejor, dist = float(s), abs(v - objetivo)
    return mejor


def pot_logit(F: np.ndarray, g: np.ndarray, anio: np.ndarray, tasa: float, sigma_u: float, betas, nsim: int,
              alfa: float, rng: np.random.Generator, base: np.ndarray | None = None,
              gamma: np.ndarray | None = None) -> dict:
    """Potencia del contraste "añadir F (1 columna, estandarizada) mejora la AUC estratificada dejando un país fuera".
    Modelo generador: logit P(y) = a + base·γ + β·F + u_año. Estadístico: ΔAUC = AUC(base + F) − AUC(base) (con
    `base` None, la base es solo el intercepto y su AUC es 0,5). Valor crítico: cuantil 1 − α de ΔAUC simulada con
    β = 0 (unilateral, mejora). Devuelve potencia por β, ΔAUC media y la β mínima con potencia ≥ 0,8."""
    F = np.asarray(F, float).reshape(-1)
    F = (F - F.mean()) / F.std(ddof=1)
    a = np.log(tasa / (1 - tasa)) * np.sqrt(1 + np.pi * sigma_u ** 2 / 8)
    B0 = np.zeros((len(F), 0)) if base is None else np.asarray(base, float).reshape(len(F), -1)
    lin0 = a + (B0 @ gamma if gamma is not None else 0.0)
    X1 = np.column_stack([B0, F])

    def una(beta):
        y = sim_eventos(lin0 + beta * F, anio, sigma_u, rng)
        if y.sum() < 5:
            return np.nan
        p1 = loco(X1, y, g)
        p0 = loco(B0, y, g) if B0.shape[1] else np.zeros(len(y))
        return auc_estrat(y, p1, g) - (auc_estrat(y, p0, g) if B0.shape[1] else 0.5)

    nul = np.array([una(0.0) for _ in range(nsim)])
    crit = float(np.nanquantile(nul, 1 - alfa))
    res = []
    for b in betas:
        d = np.array([una(b) for _ in range(nsim)])
        res.append({"beta": float(b), "odds_ratio_1dt": float(np.exp(b)), "potencia": float(np.nanmean(d > crit)),
                    "d_auc_media": float(np.nanmean(d))})
    mde = next((r for r in res if r["potencia"] >= 0.8), None)
    return {"critico_d_auc": crit, "nula_media": float(np.nanmean(nul)), "rejilla": res, "mde80": mde}


def dk_t(x: np.ndarray, y: np.ndarray, anio: np.ndarray, L: int) -> float:
    """t de la pendiente de y sobre x (ya sin efectos fijos), varianza Driscoll-Kraay por año con Bartlett."""
    b = float(x @ y / (x @ x))
    e = y - b * x
    a = np.asarray(anio).astype(int)
    h = np.bincount(a - a.min(), x * e)
    S = float(h @ h)
    for l in range(1, L + 1):
        S += 2 * (1 - l / (L + 1)) * float(h[l:] @ h[:-l])
    T = len(np.unique(a))
    se = np.sqrt(S * T / (T - 1)) / (x @ x)
    return b / se


def pot_mco(F: np.ndarray, g: np.ndarray, anio: np.ndarray, sd_comun: float, sd_propio: float, betas, nsim: int,
            alfa: float, L: int, rng: np.random.Generator) -> dict:
    """Potencia de la t Driscoll-Kraay (bilateral, α) de y_{t+1} sobre F_t (estandarizado) con efectos de país.
    Generador: y = β·F + u_año + e, u ~ N(0, sd_comun²), e ~ N(0, sd_propio²) (dt de Y solas, sin F). Valor crítico
    simulado con β = 0. MDE en las unidades de y por 1 dt de F."""
    F = np.asarray(F, float).reshape(-1)
    F = (F - F.mean()) / F.std(ddof=1)
    gi = pd.factorize(g)[0]
    dm = lambda v: v - (np.bincount(gi, v) / np.bincount(gi))[gi]  # noqa: E731
    x = dm(F)
    años, inv = np.unique(anio, return_inverse=True)

    def ruido():
        return rng.standard_normal(len(años))[inv] * sd_comun + rng.standard_normal(len(F)) * sd_propio

    t0 = np.array([dk_t(x, dm(ruido()), anio, L) for _ in range(nsim)])
    crit = float(np.quantile(np.abs(t0), 1 - alfa))
    res = []
    for b in betas:
        t = np.array([dk_t(x, dm(b * F + ruido()), anio, L) for _ in range(nsim)])
        res.append({"beta": float(b), "potencia": float(np.mean(np.abs(t) > crit))})
    mde = next((r for r in res if r["potencia"] >= 0.8), None)
    return {"critico_t": crit, "rejilla": res, "mde80": mde}
