"""P-DEV-INT12 v1.0 (docs/int/INT12_prerregistro_v1.md): previsión de la volatilidad del mercado de EE. UU. a 1 y 3
meses. Objetivos mensuales, rasgos "as of", modelos (B1-12m, HAR, HAR-X, GB; EWMA y MLP descriptivos), ventana creciente
con embargo y re-estimación cada enero, pérdidas y contrastes. Sin E/S: el script `scripts/int12_corrida.py` carga los
datos (≤ 2004) y llama aquí."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

SEMILLA = 20261030
ALFA_VAR = 0.05
UMBRAL_CAIDA = -0.10
LAMBDA_EWMA = 0.94
HAR = ["lrv5", "lrv21", "lrv63"]
X = ["credito", "curva", "corto", "reg_infl", "reg_brecha"]
GB_PARAMS = dict(loss="squared_error", learning_rate=0.05, max_iter=300, max_depth=3, min_samples_leaf=20,
                 l2_regularization=1.0, early_stopping=False, random_state=SEMILLA)
MLP_PARAMS = dict(hidden_layer_sizes=(16,), alpha=0.01, max_iter=2000, random_state=SEMILLA)


# ============================================================================ objetivos y rasgos
def tabla_objetivos(r: pd.Series, h: int) -> pd.DataFrame:
    """Una fila por mes M (Period) con origen = último día hábil de M: rv (Σ r² de los h meses siguientes), n_dias,
    ret (compuesta), caida (la trayectoria toca ≤ −10 %), fin (último día del objetivo). Solo meses con h meses
    siguientes completos dentro de la serie."""
    r = r.dropna().sort_index()
    mes = r.index.to_period("M")
    meses = mes.unique()
    vals = {m: r.values[mes == m] for m in meses}
    ult = r.index.to_series().groupby(mes).max()
    filas = []
    for i in range(len(meses) - h):
        m = meses[i]
        fut = np.concatenate([vals[meses[i + k]] for k in range(1, h + 1)])
        cam = np.cumprod(1 + fut)
        filas.append({"mes": m, "origen": ult[m], "fin": ult[meses[i + h]], "rv": float(np.sum(fut ** 2)),
                      "n_dias": len(fut), "ret": float(cam[-1] - 1), "caida": int(cam.min() <= 1 + UMBRAL_CAIDA)})
    return pd.DataFrame(filas).set_index("mes")


def rasgos_diarios(r: pd.Series) -> pd.DataFrame:
    """En el origen de cada mes: log media de r² en 5/21/63 días (HAR), varianza de los 12 últimos rendimientos
    mensuales compuestos (B1-12m) y σ²_{d+1} del EWMA λ = 0,94 (RiskMetrics)."""
    r = r.dropna().sort_index()
    r2 = r ** 2
    feats = pd.DataFrame({f"lrv{n}": np.log(r2.rolling(n, min_periods=n).mean() + 1e-12) for n in (5, 21, 63)})
    s2 = np.empty(len(r))
    s2[0] = r.iloc[:63].var()
    rv = r.values
    for d in range(1, len(r)):
        s2[d] = LAMBDA_EWMA * s2[d - 1] + (1 - LAMBDA_EWMA) * rv[d - 1] ** 2
    feats["ewma_next"] = LAMBDA_EWMA * s2 + (1 - LAMBDA_EWMA) * rv ** 2
    mes = r.index.to_period("M")
    out = feats.groupby(mes).last()
    mens = (1 + r).groupby(mes).prod() - 1
    out["b1_var"] = mens.rolling(12, min_periods=12).var(ddof=1)
    return out


def regimen_anual(df_usa: pd.DataFrame) -> pd.DataFrame:
    """df con año, regimen (código de escenarios.codigo_regimen). Devuelve reg_infl (1 si inflación > 3 %: códigos 1, 2)
    y reg_brecha (1 si brecha P3 < 0: códigos 2, 3) por año; NaN si el código es −1."""
    c = df_usa.set_index("año")["regimen"].astype(int)
    ok = c >= 0
    return pd.DataFrame({"reg_infl": np.where(ok, c.isin([1, 2]).astype(float), np.nan),
                         "reg_brecha": np.where(ok, c.isin([2, 3]).astype(float), np.nan)}, index=c.index)


def rasgos_x(meses: pd.PeriodIndex, baa: pd.Series, aaa: pd.Series, gs10: pd.Series, tb3: pd.Series,
             reg: pd.DataFrame) -> pd.DataFrame:
    """Rasgos de información en el origen del mes M: mensuales del mes M − 1; régimen del último año conocido (Y − 1 si
    M ≥ abril de Y, si no Y − 2)."""
    def mens(s):
        s = s.copy()
        s.index = s.index.to_period("M")
        return s.groupby(level=0).last().shift(1, freq="M")       # valor de M − 1 en el mes M
    b, a, g, t = mens(baa), mens(aaa), mens(gs10), mens(tb3)
    out = pd.DataFrame(index=meses)
    out["credito"] = (b - a).reindex(meses)
    out["curva"] = (g - t).reindex(meses)
    out["corto"] = t.reindex(meses)
    año_ref = np.array([m.year - 1 if m.month >= 4 else m.year - 2 for m in meses])
    for c in ("reg_infl", "reg_brecha"):
        out[c] = reg[c].reindex(año_ref).values
    return out


# ============================================================================ modelos
def _duan(y, ajuste):
    return float(np.mean(np.exp(y - ajuste)))


class Modelo:
    """Ajusta log(rv / n_dias) y prevé f = n_dias · exp(ajuste) · Duan. tipo ∈ {har, harx, gb, mlp}."""

    def __init__(self, tipo: str):
        self.tipo = tipo
        self.cols = HAR if tipo == "har" else HAR + X

    def ajustar(self, F: pd.DataFrame, y: np.ndarray):
        Z = F[self.cols].values
        if self.tipo in ("har", "harx"):
            A = np.column_stack([np.ones(len(Z)), Z])
            self.beta = np.linalg.lstsq(A, y, rcond=None)[0]
            self._pred = lambda Z_: np.column_stack([np.ones(len(Z_)), Z_]) @ self.beta
        elif self.tipo == "gb":
            from sklearn.ensemble import HistGradientBoostingRegressor
            self.m = HistGradientBoostingRegressor(**GB_PARAMS).fit(Z, y)
            self._pred = self.m.predict
        elif self.tipo == "mlp":
            from sklearn.neural_network import MLPRegressor
            mu, sd = Z.mean(0), Z.std(0) + 1e-12
            ym = float(np.mean(y))                  # objetivo centrado (log RV ≈ −9: sin centrar, la red no converge)
            self.m = MLPRegressor(**MLP_PARAMS).fit((Z - mu) / sd, y - ym)
            self._pred = lambda Z_: self.m.predict((Z_ - mu) / sd) + ym
        else:
            raise ValueError(self.tipo)
        self.smear = _duan(y, self._pred(Z))
        return self

    def prever(self, F: pd.DataFrame, n_dias: np.ndarray) -> np.ndarray:
        return n_dias * np.exp(self._pred(F[self.cols].values)) * self.smear


def prevision_fija(tipo: str, F: pd.DataFrame, n_dias: np.ndarray, h: int) -> np.ndarray:
    """Modelos sin estimación: B1-12m (h × varianza de 12 meses) y EWMA (n_dias · σ²_{d+1})."""
    if tipo == "b1_12m":
        return h * F["b1_var"].values
    if tipo == "ewma":
        return n_dias * F["ewma_next"].values
    raise ValueError(tipo)


ESTIMADOS = ("har", "harx", "gb", "mlp")
FIJOS = ("b1_12m", "ewma")


def logit_ajuste(x: np.ndarray, y: np.ndarray, it: int = 30) -> np.ndarray:
    A = np.column_stack([np.ones(len(x)), x])
    b = np.zeros(2)
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(A @ b, -30, 30)))
        W = p * (1 - p) + 1e-9
        b = b + np.linalg.solve(A.T @ (A * W[:, None]) + 1e-8 * np.eye(2), A.T @ (y - p))
    return b


def _logit_p(b, x):
    return 1 / (1 + np.exp(-np.clip(b[0] + b[1] * x, -30, 30)))


def escalas(ret: np.ndarray, f: np.ndarray, a: float = ALFA_VAR) -> tuple[float, float]:
    s = ret / np.sqrt(f)
    kv = -np.quantile(s, a)
    return float(kv), float(-s[s <= -kv].mean())


def ventana_creciente(T: pd.DataFrame, evaluar: pd.PeriodIndex, entreno_desde: pd.Period, h: int,
                      modelos=ESTIMADOS + FIJOS) -> tuple[pd.DataFrame, dict]:
    """Ver `_ventana_creciente`. Un solo hilo de OpenMP/BLAS: con muestras pequeñas, los hilos de sklearn en macOS
    multiplican el tiempo por > 10 sin cambiar el resultado."""
    from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: F401  (cargar OpenMP ANTES de limitar)
    from sklearn.neural_network import MLPRegressor  # noqa: F401
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        return _ventana_creciente(T, evaluar, entreno_desde, h, modelos)


def _ventana_creciente(T: pd.DataFrame, evaluar: pd.PeriodIndex, entreno_desde: pd.Period, h: int,
                       modelos=ESTIMADOS + FIJOS) -> tuple[pd.DataFrame, dict]:
    """T: objetivos + rasgos por mes. Para cada mes de evaluación, re-estima en enero (y en el primero) con las filas
    m ≥ entreno_desde, con rasgos completos y fin del objetivo ≤ origen del mes de re-estimación (embargo).
    Devuelve previsiones f_<modelo>, VaR/ES, P(caída) por mes y la información de cada ajuste."""
    filas, ajustes, cur = [], [], None
    completos = T[HAR + X].notna().all(1)
    for m in evaluar:
        if cur is None or m.month == 1:
            ent = T[(T.index >= entreno_desde) & (T.index < m) & (T["fin"] <= T.loc[m, "origen"]) & completos]
            y = np.log(ent["rv"].values / ent["n_dias"].values)
            cur = {"mes": m, "n": len(ent), "fit": {}, "kv": {}, "ke": {}, "lg": {}}
            for k in modelos:
                if k in ESTIMADOS:
                    mod = Modelo(k).ajustar(ent, y)
                    ftr = mod.prever(ent, ent["n_dias"].values)
                    cur["fit"][k] = mod
                else:
                    ftr = prevision_fija(k, ent, ent["n_dias"].values, h)
                ok = np.isfinite(ftr) & (ftr > 0)
                cur["kv"][k], cur["ke"][k] = escalas(ent["ret"].values[ok], ftr[ok])
                cur["lg"][k] = logit_ajuste(np.log(ftr[ok]), ent["caida"].values[ok].astype(float))
            ajustes.append(cur)
        fila = T.loc[[m]]
        o = {"mes": m, "rv": float(fila.rv.iloc[0]), "ret": float(fila.ret.iloc[0]), "caida": int(fila.caida.iloc[0])}
        for k in modelos:
            f = (cur["fit"][k].prever(fila, fila["n_dias"].values) if k in ESTIMADOS
                 else prevision_fija(k, fila, fila["n_dias"].values, h))[0]
            o[f"f_{k}"] = float(f)
            o[f"var_{k}"] = -cur["kv"][k] * np.sqrt(f)
            o[f"es_{k}"] = -cur["ke"][k] * np.sqrt(f)
            o[f"pc_{k}"] = float(_logit_p(cur["lg"][k], np.log(f)))
        filas.append(o)
    info = {"reajustes": len(ajustes), "n_entreno_primero": ajustes[0]["n"], "n_entreno_ultimo": ajustes[-1]["n"],
            "coef_har_ultimo": [float(x) for x in ajustes[-1]["fit"]["har"].beta] if "har" in ajustes[-1]["fit"] else None,
            "coef_harx_ultimo": [float(x) for x in ajustes[-1]["fit"]["harx"].beta] if "harx" in ajustes[-1]["fit"] else None,
            "ultimo_ajuste": ajustes[-1]}
    return pd.DataFrame(filas).set_index("mes"), info


# ============================================================================ pérdidas y contrastes
def qlike(f, y):
    q = np.asarray(y) / np.asarray(f)
    return q - np.log(q) - 1


def pinball(q, y, a=ALFA_VAR):
    y = np.asarray(y)
    return (a - (y <= q)) * (y - q)


def fz0(v, e, y, a=ALFA_VAR):
    y = np.asarray(y)
    ind = (y <= v).astype(float)
    return -ind * (v - y) / (a * e) + v / e + np.log(-e) - 1


def brier(p, y):
    return (np.asarray(p) - np.asarray(y)) ** 2


def lags_nw(n: int, h: int = 1) -> int:
    return (h - 1) + int(np.floor(4 * (n / 100) ** (2 / 9)))


def dm(d: np.ndarray, lags: int) -> dict:
    """DM unilateral (d > 0 ⇒ el retador pierde menos), varianza HAC Newey-West (Bartlett)."""
    d = np.asarray(d, float)
    n = len(d)
    u = d - d.mean()
    s = u @ u / n
    for k in range(1, lags + 1):
        s += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / n
    ee = np.sqrt(max(s, 1e-300) / n)
    t = d.mean() / ee
    return {"media_d": float(d.mean()), "ee": float(ee), "t": float(t), "p": float(1 - norm.cdf(t)),
            "ic95": [float(d.mean() - 1.96 * ee), float(d.mean() + 1.96 * ee)], "lags": lags, "n": n}


def holm(ps: dict, alfa: float = 0.05) -> dict:
    """p ajustados de Holm y rechazo a nivel familiar alfa."""
    orden = sorted(ps, key=ps.get)
    k = len(ps)
    adj, prev = {}, 0.0
    for i, c in enumerate(orden):
        prev = max(prev, min(1.0, (k - i) * ps[c]))
        adj[c] = prev
    return {c: {"p_holm": adj[c], "rechaza": adj[c] <= alfa} for c in ps}


def bootstrap_estacionario_p(d: np.ndarray, bloque: float = 12, reps: int = 2000, seed: int = SEMILLA) -> float:
    """p unilateral de media(d) > 0 con bootstrap de bloques estacionario (Politis-Romano) sobre d centrada."""
    rng = np.random.default_rng(seed)
    d = np.asarray(d, float)
    n = len(d)
    u = d - d.mean()
    q = 1 / bloque
    cnt = 0
    for _ in range(reps):
        idx = np.empty(n, int)
        idx[0] = rng.integers(n)
        nuevos = rng.random(n) < q
        saltos = rng.integers(n, size=n)
        for i in range(1, n):
            idx[i] = saltos[i] if nuevos[i] else (idx[i - 1] + 1) % n
        cnt += u[idx].mean() >= d.mean()
    return float((cnt + 1) / (reps + 1))


def kupiec(exced: np.ndarray, a: float = ALFA_VAR) -> dict:
    n, x = len(exced), int(np.sum(exced))
    p = x / n
    ll0 = (n - x) * np.log(1 - a) + x * np.log(a)
    ll1 = (n - x) * np.log(1 - p) + x * np.log(p) if 0 < x < n else 0.0
    lr = -2 * (ll0 - ll1)
    return {"n": n, "excedencias": x, "tasa": float(p), "lr": float(lr), "p": float(1 - chi2.cdf(lr, 1))}


def contraste(P: pd.DataFrame, base: str, ret: str, h: int, mitad: pd.Period | None = None) -> dict:
    """QLIKE: ganancia relativa, DM-NW y ganancias por mitad (corte en `mitad`)."""
    lb, lr = qlike(P[f"f_{base}"], P.rv), qlike(P[f"f_{ret}"], P.rv)
    d = np.asarray(lb - lr, float)
    out = {"listón": base, "retador": ret, "ganancia": float(1 - lr.mean() / lb.mean()),
           "qlike_liston": float(lb.mean()), "qlike_retador": float(lr.mean()), **dm(d, lags_nw(len(d), h))}
    if mitad is not None:
        a = P.index < mitad
        out["ganancia_mitad1"] = float(1 - lr[a].mean() / lb[a].mean())
        out["ganancia_mitad2"] = float(1 - lr[~a].mean() / lb[~a].mean())
    return out
