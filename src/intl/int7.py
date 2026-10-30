"""P-DEV-INT7 v1.0 (docs/int/INT7_prerregistro_v1.md, congelado 2026-10-29T18:34:16Z): valoración → rentabilidad.
Funciones puras sobre matrices año × unidad (unidad = país; una sola columna en las series de EE. UU.). La carga y la
corrida están en scripts/int7_corrida.py; las lecturas de las ambigüedades, en docs/int/INT7_notas_implementacion.md.

Convenciones: Z[t, j] = indicador del año (o mes) t; Y[s, j] = rentabilidad (log) del año s; una "fila" (t, j) une Z[t]
con Y[t+1] + … + Y[t+h]. Los efectos fijos se quitan con Frisch-Waugh (mismo b y misma varianza sándwich que con
variables ficticias).

- `FE`, `hac`: efectos fijos de unidad (y de año) y errores Driscoll-Kraay por año (Newey-West con una unidad).
- `ar1_kendall`: AR(1) por unidad con φ corregida por Kendall, φ_c = φ̂ + (1 + 3φ̂)/T, y sus innovaciones.
- `Diseno`: filas, horizonte, efectos fijos, retardos; t de la MCO y pendiente de Amihud-Hurvich (regresión aumentada con
  la innovación corregida del indicador).
- `bootstrap`: nulo que conserva δ (§3.2): años enteros en bloques de 5, pares (ê, v̂) de todas las unidades juntos,
  x* reconstruido con el AR(1) corregido desde el valor inicial real, mismos huecos.
- `placebo`, `por_unidad`, `hodrick_1b`, `oos`, `interaccion`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.intl import int3 as I

DESFASE_MIN = I.DESFASE_MIN
PHI_MAX = 0.999


def lags_def(T: int) -> int:
    return int(np.floor(4 * (T / 100) ** (2 / 9)))


# ------------------------------------------------------------------ efectos fijos y errores
class FE:
    """Residualizador de efectos fijos para un conjunto FIJO de filas (unidad; y año si `año`)."""

    def __init__(self, unidad: np.ndarray, anio: np.ndarray, año: bool):
        self.gu = pd.factorize(np.asarray(unidad))[0]
        self.nu = int(self.gu.max()) + 1 if len(self.gu) else 0
        self.cnt = np.bincount(self.gu, minlength=self.nu).astype(float)
        self.año = año
        if año:
            ga = pd.factorize(np.asarray(anio))[0]
            Dm = np.column_stack([np.eye(self.nu)[self.gu], np.eye(int(ga.max()) + 1)[ga]])
            self.M = np.eye(len(Dm)) - Dm @ np.linalg.pinv(Dm)

    def __call__(self, A: np.ndarray) -> np.ndarray:
        A = np.asarray(A, float)
        if self.año:
            return self.M @ A
        if A.ndim == 1:
            return A - (np.bincount(self.gu, A, self.nu) / self.cnt)[self.gu]
        return np.column_stack([self(A[:, k]) for k in range(A.shape[1])])


def hac(X: np.ndarray, y: np.ndarray, anio: np.ndarray, L: int, corr: str = "dk") -> dict:
    """MCO de y sobre X (ya sin efectos fijos). Varianza Driscoll-Kraay: puntuaciones sumadas por año (años del rango sin
    filas = 0), Bartlett con L retardos. corr = "dk": × T/(T − 1) (como src/intl/int3.driscoll_kraay); "nw": × T/(T − 1 − k)
    (como src/intl/int3b.nw con una regresora)."""
    X = np.asarray(X, float)
    X = X[:, None] if X.ndim == 1 else X
    y = np.asarray(y, float)
    k = X.shape[1]
    XtX = X.T @ X
    inv = np.linalg.inv(XtX)
    b = inv @ (X.T @ y)
    e = y - X @ b
    a = np.asarray(anio).astype(int)
    a0 = a.min()
    h = np.zeros((a.max() - a0 + 1, k))
    np.add.at(h, a - a0, X * e[:, None])
    S = h.T @ h
    for l in range(1, L + 1):
        G = h[l:].T @ h[:-l]
        S += (1 - l / (L + 1)) * (G + G.T)
    T = int(len(np.unique(a)))
    V = inv @ S @ inv * (T / (T - 1) if corr == "dk" else T / (T - 1 - k))
    se = np.sqrt(np.maximum(np.diag(V), 0))
    t = np.where(se > 0, b / np.where(se > 0, se, 1), np.nan)
    tss = float((y ** 2).sum())
    return {"b": b, "se": se, "t": t, "V": V, "T": T, "L": L, "n": int(len(y)), "e": e,
            "r2": float(1 - (e ** 2).sum() / tss) if tss > 0 else float("nan")}


def resumen(r: dict, i: int = 0) -> dict:
    T = r["T"]
    q = stats.t.ppf(0.975, T - 1)
    b, se, t = float(r["b"][i]), float(r["se"][i]), float(r["t"][i])
    return {"b": b, "se": se, "t": t, "p_student": float(2 * stats.t.sf(abs(t), T - 1)),
            "ic95_student": [b - q * se, b + q * se], "n": r["n"], "años": T, "lags": r["L"], "r2_dentro": r["r2"]}


# ------------------------------------------------------------------ AR(1) con corrección de Kendall
def ar1_kendall(Z: np.ndarray) -> dict:
    """Por columna: pares consecutivos (Z[t−1], Z[t]) con los dos datos; φ̂ MCO con constante; φ_c = mín(φ̂ + (1 + 3φ̂)/T,
    PHI_MAX); c = media(Z[t]) − φ_c·media(Z[t−1]); V[t] = Z[t] − c − φ_c·Z[t−1] (NaN sin par)."""
    Z = np.asarray(Z, float)
    n, N = Z.shape
    prev, cur = Z[:-1], Z[1:]
    ok = np.isfinite(prev) & np.isfinite(cur)
    c, phic, phi, T = np.full(N, np.nan), np.full(N, np.nan), np.full(N, np.nan), ok.sum(0)
    V = np.full((n, N), np.nan)
    for j in range(N):
        m = ok[:, j]
        if m.sum() < 5:
            continue
        xp, xc = prev[m, j], cur[m, j]
        dp = xp - xp.mean()
        phi[j] = float(dp @ (xc - xc.mean()) / (dp @ dp))
        phic[j] = min(phi[j] + (1 + 3 * phi[j]) / m.sum(), PHI_MAX)
        c[j] = xc.mean() - phic[j] * xp.mean()
        V[1:, j][m] = xc - c[j] - phic[j] * xp
    return {"c": c, "phi_c": phic, "phi": phi, "T": T, "V": V}


# ------------------------------------------------------------------ diseño de una pregunta
class Diseno:
    """Filas (t, j) con Z[t, j] y Y[t+1..t+h, j] (las decide quien llama: `filas` es una máscara año × unidad).
    `limpio`: celdas del indicador que entran en su AR(1) (Amihud-Hurvich y bootstrap)."""

    def __init__(self, filas: np.ndarray, h: int, año: bool, años: np.ndarray, limpio: np.ndarray, L: int | None = None,
                 corr: str = "dk"):
        self.filas = filas
        self.ti, self.tj = np.nonzero(filas)
        self.h, self.año, self.corr = h, año, corr
        self.años = np.asarray(años)
        self.anio = self.años[self.ti]
        self.fe = FE(self.tj, self.anio, año)
        T = int(len(np.unique(self.anio)))
        self.L = lags_def(T) if L is None else L
        self.limpio = limpio
        self._fe_ah: dict = {}

    def y(self, Y: np.ndarray) -> np.ndarray:
        return sum(Y[self.ti + k, self.tj] for k in range(1, self.h + 1))

    def ols(self, Z: np.ndarray, Y: np.ndarray) -> dict:
        return hac(self.fe(Z[self.ti, self.tj]), self.fe(self.y(Y)), self.anio, self.L, self.corr)

    def t_ols(self, Z: np.ndarray, Y: np.ndarray) -> tuple[float, float]:
        r = self.ols(Z, Y)
        return float(r["b"][0]), float(r["t"][0])

    def ah(self, Z: np.ndarray, Y: np.ndarray) -> dict | None:
        """Amihud-Hurvich (2004) en panel: y = FE + b·z_t + γ·v̂c_{t+1} + e, con v̂c la innovación del AR(1) corregido
        por Kendall del indicador de cada unidad (celdas `limpio`). Solo h = 1. Filas sin v̂c_{t+1}: fuera."""
        if self.h != 1:
            return None
        Zc = np.where(self.limpio, Z, np.nan)
        ar = ar1_kendall(Zc)
        vn = np.full(len(self.ti), np.nan)
        ok_t = self.ti + 1 < Z.shape[0]
        vn[ok_t] = ar["V"][self.ti[ok_t] + 1, self.tj[ok_t]]
        m = np.isfinite(vn)
        clave = m.tobytes()
        if clave not in self._fe_ah:                      # mismas filas en todas las réplicas: se reutiliza
            self._fe_ah = {clave: FE(self.tj[m], self.anio[m], self.año)}
        fe = self._fe_ah[clave]
        X = fe(np.column_stack([Z[self.ti[m], self.tj[m]], vn[m]]))
        r = hac(X, fe(self.y(Y)[m]), self.anio[m], self.L, self.corr)
        r["filas_ah"] = int(m.sum())
        r["ar1"] = ar
        return r


# ------------------------------------------------------------------ bootstrap nulo que conserva δ (§3.2)
def residuos_pares(dis: Diseno, Z: np.ndarray, Y: np.ndarray, b: float = 0.0) -> dict:
    """Pares (ê_s, v̂_s) por año de RESULTADO s = t + 1 y unidad, sobre las filas de `dis` (h = 1):
    ê = residuo de y − b·z con los efectos fijos del diseño; v̂ = innovación del AR(1) de Kendall del indicador.
    alpha_j = media por unidad de y − b·z (nivel al que se suma ê*)."""
    assert dis.h == 1
    Zc = np.where(dis.limpio, Z, np.nan)
    ar = ar1_kendall(Zc)
    z = Z[dis.ti, dis.tj]
    y = dis.y(Y) - b * z
    e = dis.fe(y)
    n, N = Z.shape
    E = np.full((n, N), np.nan)
    E[dis.ti + 1, dis.tj] = e
    alpha = np.array([y[dis.tj == j].mean() if (dis.tj == j).any() else np.nan for j in range(N)])
    return {"E": E, "V": ar["V"], "c": ar["c"], "phi_c": ar["phi_c"], "alpha": alpha, "Zc": Zc}


def generar(par: dict, b: float, rng: np.random.Generator, bloque: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Una réplica: años de resultado remuestreados en bloques de `bloque` años consecutivos (de los años con algún par
    válido), el vector (ê, v̂) de todas las unidades juntas. Celda sin par válido en el año sorteado → par de un año
    válido de la misma unidad, al azar. x* desde el primer valor real (celdas `Zc`) con el AR(1) corregido;
    y*_s = alpha + b·x*_{s−1} + ê*_s."""
    E, V, Zc = par["E"], par["V"], par["Zc"]
    n, N = E.shape
    valido = np.isfinite(E) & np.isfinite(V)
    pool = np.nonzero(valido.any(1))[0]
    nb = int(np.ceil(n / bloque))
    starts = rng.integers(0, len(pool) - bloque + 1, size=nb)
    src = pool[(starts[:, None] + np.arange(bloque)).ravel()][:n]
    Es, Vs = E[src].copy(), V[src].copy()
    malo = ~valido[src]
    for j in range(N):
        k = int(malo[:, j].sum())
        if k:
            vj = np.nonzero(valido[:, j])[0]
            if len(vj) == 0:
                continue
            pick = rng.choice(vj, k)
            Es[malo[:, j], j], Vs[malo[:, j], j] = E[pick, j], V[pick, j]
    fin = np.isfinite(Zc)
    f0 = np.where(fin.any(0), fin.argmax(0), n)
    x0 = Zc[np.minimum(f0, n - 1), np.arange(N)]
    X = np.full((n, N), np.nan)
    c, phi = par["c"], par["phi_c"]
    for s in range(n):
        nuevo = c + phi * X[s - 1] + Vs[s] if s > 0 else np.full(N, np.nan)
        X[s] = np.where(s == f0, x0, np.where(s > f0, nuevo, np.nan))
    Yg = np.full((n, N), np.nan)
    Yg[1:] = par["alpha"] + b * X[:-1] + Es[1:]
    return X, Yg


def bootstrap(par: dict, diseños: dict, B: int, rng: np.random.Generator, b: float = 0.0, bloque: int = 5,
              que: str = "t") -> dict:
    """B réplicas; para cada diseño (mismas filas que los datos) la t de la MCO (que = "t") o la pendiente de
    Amihud-Hurvich (que = "ah")."""
    out = {k: np.empty(B) for k in diseños}
    for r in range(B):
        X, Yg = generar(par, b, rng, bloque)
        for k, d in diseños.items():
            if que == "t":
                out[k][r] = d.t_ols(X, Yg)[1]
            else:
                out[k][r] = float(d.ah(X, Yg)["b"][0])
    return out


def p_bootstrap(t0: float, tb: np.ndarray) -> float:
    """p = 2·mín(P(t* ≥ t), P(t* ≤ t)), cada P = (1 + #)/(1 + B); como mucho 1."""
    tb = tb[np.isfinite(tb)]
    B = len(tb)
    return float(min(1.0, 2 * min((1 + (tb >= t0).sum()) / (1 + B), (1 + (tb <= t0).sum()) / (1 + B))))


# ------------------------------------------------------------------ placebo desplazado (criterio 3, regla de INT-3b)
def placebo(dis: Diseno, Z: np.ndarray, Y: np.ndarray) -> dict:
    """z desplazado k años en círculo dentro de [mín, máx] del año de las filas (misma k en todas las unidades),
    k = 6 … T − 6; filas sin valor desplazado fuera; t de DK con los retardos por defecto de cada submuestra."""
    zrow = np.full(Z.shape, np.nan)
    zrow[dis.ti, dis.tj] = Z[dis.ti, dis.tj]
    a0, a1 = int(dis.ti.min()), int(dis.ti.max())
    Lr = a1 - a0 + 1
    ts = []
    for k in range(DESFASE_MIN, Lr - DESFASE_MIN + 1):
        src = a0 + (dis.ti - a0 - k) % Lr
        z = zrow[src, dis.tj]
        m = np.isfinite(z)
        fe = FE(dis.tj[m], dis.anio[m], dis.año)
        an = dis.anio[m]
        r = hac(fe(z[m]), fe(dis.y(Y)[m]), an, lags_def(len(np.unique(an))), dis.corr)
        ts.append(float(r["t"][0]))
    ts = np.array(ts)
    return {"desplazamientos": int(len(ts)), "p95_abs_t": float(np.quantile(np.abs(ts), 0.95)), "t": ts}


# ------------------------------------------------------------------ por unidad (criterio 5)
def por_unidad(dis: Diseno, Z: np.ndarray, Y: np.ndarray, nombres: list[str]) -> dict:
    """Pendiente MCO de cada unidad sin encoger (y sobre z) y DerSimonian-Laird sobre pendientes de y sin la media de
    cada año (media sobre las filas del año), con varianza MCO clásica."""
    z, y = Z[dis.ti, dis.tj], dis.y(Y)
    ysa = y - pd.Series(y).groupby(dis.anio).transform("mean").to_numpy()

    def pend(yy):
        filas = []
        for j in np.unique(dis.tj):
            m = dis.tj == j
            if m.sum() < 10:
                continue
            zc, yc = z[m] - z[m].mean(), yy[m] - yy[m].mean()
            b = float(zc @ yc / (zc @ zc))
            e = yc - b * zc
            filas.append({"pais": nombres[j], "efecto": b, "var": float(e @ e / (m.sum() - 2) / (zc @ zc))})
        return pd.DataFrame(filas)
    sin = pend(y)
    dl, mu, tau2 = I.encoger(pend(ysa))
    return {"sin_encoger": dict(zip(sin.pais, sin.efecto)), "dl_sin_año": dict(zip(dl.pais, dl.encogido)),
            "dl_media": mu, "dl_tau2": tau2}


# ------------------------------------------------------------------ Hodrick (1992) 1B
def hodrick_1b(Z: np.ndarray, Y: np.ndarray, filas1: np.ndarray, h: int, años: np.ndarray, año: bool,
               corr: str = "dk") -> dict:
    """Regresión inversa: y_{t+1} (1 periodo) sobre Σ_{j<h} z_{t−j}, con los efectos fijos; errores DK/NW con 0
    retardos (bajo H0 los errores de 1 periodo no están autocorrelados). `filas1`: filas válidas a 1 periodo."""
    n = Z.shape[0]
    Zs = np.full(Z.shape, np.nan)
    for t in range(h - 1, n):
        Zs[t] = Z[t - h + 1: t + 1].sum(0)
    m = filas1 & np.isfinite(Zs)
    d = Diseno(m, 1, año, años, np.isfinite(Z), L=0, corr=corr)
    return resumen(d.ols(Zs, Y))


# ------------------------------------------------------------------ fuera de muestra (Goyal-Welch, §4.4)
def oos(Z: np.ndarray, Y: np.ndarray, filas: np.ndarray, años: np.ndarray, desde: int, relativo: bool,
        min_filas: int = 10) -> dict:
    """Ventana creciente: para cada año de resultado s ≥ `desde`, se estima con las filas cuyo resultado es ≤ s − 1 y se
    predice y_s con z_{s−1}. Modelo: MCO con efecto fijo de país (α_j = media de y − b·z en el tramo). Referencia: media
    histórica de y del país en el tramo. Unidades con < `min_filas` filas en el tramo: sin predicción ese año.
    relativo: y y z sin la media de las filas del año (de su año de resultado y de su año de indicador)."""
    ti, tj = np.nonzero(filas)
    z, y = Z[ti, tj].astype(float), Y[ti + 1, tj].astype(float)
    if relativo:
        z = z - pd.Series(z).groupby(ti).transform("mean").to_numpy()
        y = y - pd.Series(y).groupby(ti).transform("mean").to_numpy()
    año_res = años[ti + 1]
    reg = []
    for s in sorted(set(año_res[año_res >= desde])):
        tr, te = año_res <= s - 1, año_res == s
        cnt = np.bincount(tj[tr], minlength=Z.shape[1])
        ok_u = cnt >= min_filas
        tr &= ok_u[tj]
        te &= ok_u[tj]
        if not te.any():
            continue
        fe = FE(tj[tr], ti[tr], False)
        zt, yt = fe(z[tr]), fe(y[tr])
        b = float(zt @ yt / (zt @ zt))
        for i in np.nonzero(te)[0]:
            mj = tr & (tj == tj[i])
            ybar = y[mj].mean()
            yhat = ybar + b * (z[i] - z[mj].mean())
            reg.append((s, tj[i], y[i], yhat, ybar))
    r = pd.DataFrame(reg, columns=["s", "j", "y", "yhat", "ybar"])
    sse_m, sse_b = float(((r.y - r.yhat) ** 2).sum()), float(((r.y - r.ybar) ** 2).sum())
    f = (r.y - r.ybar) ** 2 - ((r.y - r.yhat) ** 2 - (r.ybar - r.yhat) ** 2)
    cw = hac(np.ones(len(f)), f.to_numpy(), r.s.to_numpy(), lags_def(r.s.nunique()))
    t = float(cw["t"][0])
    return {"r2_oos": 1 - sse_m / sse_b, "predicciones": int(len(r)), "años": int(r.s.nunique()),
            "clark_west_t": t, "clark_west_p_unilateral": float(stats.t.sf(t, cw["T"] - 1))}


# ------------------------------------------------------------------ interacción (V5)
def interaccion(dis: Diseno, Z: np.ndarray, Y: np.ndarray, S: np.ndarray) -> dict:
    """y = FE + b0·z + b1·z·S + g·S + e en las filas con estado S (0/1) en t. Pendiente en S = 1 (b0 + b1), en S = 0
    (b0) y diferencia b1, con DK."""
    s = S[dis.ti, dis.tj]
    m = np.isfinite(s)
    fe = FE(dis.tj[m], dis.anio[m], dis.año)
    z = Z[dis.ti[m], dis.tj[m]]
    X = fe(np.column_stack([z, z * s[m], s[m]]))
    an = dis.anio[m]
    r = hac(X, fe(dis.y(Y)[m]), an, lags_def(len(np.unique(an))), dis.corr)
    T = r["T"]
    q = stats.t.ppf(0.975, T - 1)
    V = r["V"]
    out = {}
    for nom, w in (("pendiente_estanflacion", np.array([1, 1, 0])), ("pendiente_resto", np.array([1, 0, 0])),
                   ("diferencia", np.array([0, 1, 0]))):
        b, se = float(w @ r["b"]), float(np.sqrt(w @ V @ w))
        out[nom] = {"b": b, "ic95": [b - q * se, b + q * se], "p_student": float(2 * stats.t.sf(abs(b / se), T - 1))}
    out["filas_estanflacion"] = int(s[m].sum())
    out["filas_resto"] = int((s[m] == 0).sum())
    out["años_estanflacion"] = int(len(np.unique(an[s[m] == 1])))
    return out
