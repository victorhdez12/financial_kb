"""INT-11: POTENCIA de la evaluación de distribuciones (CRPS, cobertura) con un proceso generador SINTÉTICO.

Nada aquí toca datos reales: el script scripts/int11_potencia.py mide por SEPARADO propiedades de X (frecuencia,
persistencia y concordancia entre países del régimen operable) y de Y (dispersión común y propia de cada activo,
correlaciones, colas) y se las pasa a estas funciones. Los efectos del régimen sobre la rentabilidad se PLANTAN (δ × los
tamaños ya publicados del Atlas §8); nunca se estiman cruzando el régimen real con la rentabilidad real.

Piezas:
  dgp_regimenes   régimen de N países × T años desde dos latentes AR(1) (inflación, brecha) con componente común
  dgp_rent        rentabilidades reales con choque común de año + propio, t multivariante, efecto según s_{t−1}
  evaluar         M1 (distribución empírica por régimen conocido) frente a M0 (incondicional del panel), dejando un
                  país fuera o temporal; CRPS normalizado por activo; Diebold-Mariano con años como conglomerados
  cobertura_sim   cobertura del intervalo p5-p95 (o p10-p90) de un modelo con anchura escalada; contraste por años
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.intl import escenarios as E

K = E.K
ACTIVOS = E.ACTIVOS
# Efectos de referencia (δ = 1), fracción/año, por régimen conocido s_{t−1} = (exp, sobrecal., estanfl., crec. bajo).
# Bolsa, bonos y letras: tamaños del Atlas §8 (versión operable; probablemente INFLADOS por la maldición del ganador).
# Vivienda: supuesto (no hay versión operable); oro: 0 (no sabemos).
EFECTOS_REF = np.array([[0.0, -0.03, -0.12, 0.0],
                        [0.0, -0.06, -0.06, 0.0],
                        [0.0, -0.05, -0.05, 0.0],
                        [0.0, 0.0, -0.03, 0.0],
                        [0.0, 0.0, 0.0, 0.0]])


# ============================================================================ proceso generador
def latente(N: int, T: int, a: float, rho: float, rng) -> np.ndarray:
    """(N, T) AR(1) estacionario de varianza 1 con correlación rho entre países en cada innovación."""
    z = np.zeros((N, T))
    z[:, 0] = np.sqrt(rho) * rng.standard_normal() + np.sqrt(1 - rho) * rng.standard_normal(N)
    s = np.sqrt(1 - a ** 2)
    for t in range(1, T):
        inn = np.sqrt(rho) * rng.standard_normal() + np.sqrt(1 - rho) * rng.standard_normal(N)
        z[:, t] = a * z[:, t - 1] + s * inn
    return z


def dgp_regimenes(N: int, T: int, par: dict, rng) -> np.ndarray:
    """par: q_i (frecuencia de inflación > 3 %), q_g (frecuencia de brecha < 0), a_i, rho_i, a_g, rho_g."""
    zi = latente(N, T, par["a_i"], par["rho_i"], rng)
    zg = latente(N, T, par["a_g"], par["rho_g"], rng)
    alta = zi > stats.norm.ppf(1 - par["q_i"])
    baja = zg < stats.norm.ppf(par["q_g"])
    return np.where(baja, np.where(alta, 2, 3), np.where(alta, 1, 0))


def indicador_props(x: np.ndarray) -> dict:
    """x (N, T) booleano con NaN permitidos (float). Frecuencia, persistencia P(x_t = x_{t−1}) y concordancia (media
    de las correlaciones entre pares de países)."""
    x = np.asarray(x, float)
    ok = np.isfinite(x[:, 1:]) & np.isfinite(x[:, :-1])
    pers = float((x[:, 1:][ok] == x[:, :-1][ok]).mean())
    cs = []
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            m = np.isfinite(x[i]) & np.isfinite(x[j])
            if m.sum() > 20 and x[i, m].std() > 0 and x[j, m].std() > 0:
                cs.append(np.corrcoef(x[i, m], x[j, m])[0, 1])
    return {"frecuencia": float(np.nanmean(x)), "persistencia": pers, "concordancia": float(np.mean(cs))}


def calibrar_latente(q: float, pers: float, conc: float, N: int = 14, T: int = 400, semilla: int = 0) -> dict:
    """(a, rho) del latente que reproducen la persistencia y la concordancia del indicador (rejilla + simulación)."""
    rng = np.random.default_rng(semilla)
    mejor, err = None, np.inf
    for a in np.linspace(0.3, 0.97, 35):
        for rho in np.linspace(0.0, 0.9, 31):
            props = [indicador_props(latente(N, T, a, rho, rng) > stats.norm.ppf(1 - q)) for _ in range(2)]
            p = np.mean([x["persistencia"] for x in props])
            c = np.mean([x["concordancia"] for x in props])
            e = (p - pers) ** 2 + (c - conc) ** 2
            if e < err:
                mejor, err = (float(a), float(rho), float(p), float(c)), e
    return {"a": mejor[0], "rho": mejor[1], "persistencia_sim": mejor[2], "concordancia_sim": mejor[3]}


def t_multi(n: int, R: np.ndarray, nu: float, rng) -> np.ndarray:
    """(n, A) t multivariante con correlación R y varianza 1."""
    L = np.linalg.cholesky(R)
    z = rng.standard_normal((n, len(R))) @ L.T
    if not np.isfinite(nu):
        return z
    return z * np.sqrt((nu - 2) / rng.chisquare(nu, size=(n, 1)))


def dgp_rent(reg: np.ndarray, efectos: np.ndarray, mu: np.ndarray, sd_comun: np.ndarray, sd_propio: np.ndarray,
             R: np.ndarray, nu: float, rng) -> np.ndarray:
    """(N, T, A) rentabilidad real (log) del año t; el efecto depende del régimen CONOCIDO s_{t−1} (t ≥ 1)."""
    N, T = reg.shape
    A = len(mu)
    u = t_multi(T, R, nu, rng) * sd_comun                         # (T, A) choque común de año
    e = t_multi(N * T, R, nu, rng).reshape(N, T, A) * sd_propio
    y = mu + u[None] + e
    prev = np.concatenate([np.full((N, 1), 0), reg[:, :-1]], axis=1)
    y = y + efectos.T[prev]                                          # (N, T, A)
    y[:, 0] = np.nan
    return y


# ============================================================================ evaluación de distribuciones
def _pools(Ytr: np.ndarray, Str: np.ndarray, n_min: int) -> tuple[np.ndarray, list]:
    """Ytr (n, A), Str (n,) régimen conocido. Pool incondicional y por régimen (con respaldo al incondicional)."""
    por = [Ytr[Str == i] if (Str == i).sum() >= n_min else Ytr for i in range(K)]
    return Ytr, por


def _crps_filas(Ytr, Str, Yte, Ste, n_min):
    """CRPS de M0 y M1 por fila de prueba y activo: (m, A) cada uno."""
    m, A = Yte.shape
    c0, c1 = np.full((m, A), np.nan), np.full((m, A), np.nan)
    p0, por = _pools(Ytr, Str, n_min)
    for a in range(A):
        ok = np.isfinite(Yte[:, a])
        if np.isfinite(p0[:, a]).sum() < n_min:                    # activo sin pool de entrenamiento (oro < 1972)
            continue
        c0[ok, a] = E.crps_muestra(p0[:, a], Yte[ok, a])
        for i in range(K):
            mi = ok & (Ste == i)
            if mi.any():
                c1[mi, a] = E.crps_muestra(por[i][:, a], Yte[mi, a])
    return c0, c1


def filas_h(Y: np.ndarray, reg: np.ndarray, h: int, inicio: int = 1) -> tuple:
    """Objetivos a horizonte h: suma de log-rentabilidades de t … t + h − 1 (inicios cada h años, sin solape) y estado
    conocido s_{t−1}. Devuelve (pais, año, Y (n, A), S (n,))."""
    N, T, A = Y.shape
    ts = np.arange(inicio, T - h + 1, h)
    P, Tt = np.meshgrid(np.arange(N), ts, indexing="ij")
    P, Tt = P.ravel(), Tt.ravel()
    Yh = np.stack([Y[P, Tt + k] for k in range(h)], 0).sum(0)
    return P, Tt, Yh, reg[P, Tt - 1]


def evaluar(Y: np.ndarray, reg: np.ndarray, diseño: str, h: int = 1, corte: int | None = None, n_min: int = 30,
            prueba_desde: int | None = None) -> dict:
    """diseño "loco" (entrena con los otros países, todos los años) o "temporal" (entrena t < corte, prueba
    t ≥ corte; si prueba_desde, solo t ≥ prueba_desde). Devuelve d por fila (mejora media normalizada de M1 sobre M0),
    años, CRPSS por activo y medio."""
    P, Tt, Yh, S = filas_h(Y, reg, h)
    m, A = Yh.shape
    c0, c1 = np.full((m, A), np.nan), np.full((m, A), np.nan)
    if diseño == "loco":
        for c in np.unique(P):
            te, tr = P == c, P != c
            c0[te], c1[te] = _crps_filas(Yh[tr], S[tr], Yh[te], S[te], n_min)
    else:
        tr = Tt + h - 1 < corte                       # el objetivo de entrenamiento termina antes del corte
        te = Tt >= corte if prueba_desde is None else Tt >= prueba_desde
        c0[te], c1[te] = _crps_filas(Yh[tr], S[tr], Yh[te], S[te], n_min)
    usa = np.isfinite(c0).any(1)
    escala = np.nanmean(c0[usa], 0)
    da = (c0[usa] - c1[usa]) / escala
    d = np.nanmean(da, 1)
    crpss = 1 - np.nanmean(c1[usa], 0) / escala
    return {"d": d, "d_activo": da, "año": Tt[usa], "crpss": crpss, "crpss_medio": float(np.nanmean(crpss))}


def cobertura_sim(Y: np.ndarray, reg: np.ndarray, k: float, lo: float, hi: float, corte: int, prueba: tuple,
                  h: int = 1, n_min: int = 30) -> dict:
    """Modelo M1 entrenado con t < corte cuyo intervalo [q_lo, q_hi] se ensancha/estrecha por k alrededor de la
    mediana (k < 1 → infracobertura). Prueba en t ∈ [prueba[0], prueba[1]). Indicador dentro/fuera por fila."""
    P, Tt, Yh, S = filas_h(Y, reg, h)
    tr = Tt + h - 1 < corte
    te = (Tt >= prueba[0]) & (Tt < prueba[1])
    _, por = _pools(Yh[tr], S[tr], n_min)
    A = Yh.shape[1]
    dentro = np.full((te.sum(), A), np.nan)
    Yte, Ste = Yh[te], S[te]
    for i in range(K):
        mi = Ste == i
        if not mi.any():
            continue
        q = np.nanquantile(por[i], [lo, 0.5, hi], axis=0)          # (3, A)
        a_lo, a_hi = q[1] - k * (q[1] - q[0]), q[1] + k * (q[2] - q[1])
        y = Yte[mi]
        valido = np.isfinite(y) & np.isfinite(a_lo) & np.isfinite(a_hi)        # sin pool de entrenamiento → hueco
        dentro[mi] = np.where(valido, (y >= a_lo) & (y <= a_hi), np.nan)
    return {"dentro": dentro, "año": Tt[te]}
