"""P-DEV-INT3b v1.0 (docs/int/INT3b_prerregistro_v0.md, congelado en fa6d4c9): contrastes de INT-3b / INT-3c.
Funciones puras; la carga y la corrida están en scripts/int3b_corrida.py.

- `ts_contraste`: serie mundial y_t = a + b·x_t, t de Newey-West (= Driscoll-Kraay con una unidad), lags ⌊4(T/100)^(2/9)⌋,
  t con T − 1 gl; placebo con x desplazado en círculo k = 6 … T − 6; φ = máx(1, dt(t placebo)); p_cal = 2·P(t_{T−1} > |t|/φ);
  criterio |t| > percentil 95 de |t placebo|; pendientes en 1878-1949 y 1950-1999.
- `panel_contraste`: efecto fijo de país + b·D, Driscoll-Kraay por año (src/intl/int3.py) y CR2 al lado; mismo placebo
  (desplazar de int3, misma k en todos los países) con la t de DK; efecto en 1950-1999; signos por país sin encoger y
  DerSimonian-Laird sobre efectos sin la media del año.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.intl import int3 as I

DESFASE_MIN = I.DESFASE_MIN


def lags_nw(T: int) -> int:
    return int(np.floor(4 * (T / 100) ** (2 / 9)))


def nw(y: np.ndarray, x: np.ndarray, lags: int | None = None) -> dict:
    """MCO con constante; t de Newey-West (Bartlett) con corrección T/(T − 2), igual que statsmodels use_correction."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    T = len(y)
    L = lags_nw(T) if lags is None else lags
    xc, yc = x - x.mean(), y - y.mean()
    sxx = (xc ** 2).sum()
    b = float((xc * yc).sum() / sxx)
    u = xc * (yc - b * xc)
    S = (u ** 2).sum()
    for l in range(1, L + 1):
        S += 2 * (1 - l / (L + 1)) * (u[l:] * u[:-l]).sum()
    se = float(np.sqrt(S * T / (T - 2)) / sxx)
    t = b / se if se > 0 else np.nan
    q = stats.t.ppf(0.975, T - 1)
    return {"efecto": b, "se": se, "t": float(t), "p": float(2 * stats.t.sf(abs(t), T - 1)),
            "ic95": [b - q * se, b + q * se], "lags": L, "T": T}


def pendiente(y: np.ndarray, x: np.ndarray) -> float:
    y, x = np.asarray(y, float), np.asarray(x, float)
    if len(x) < 3 or np.var(x) == 0:
        return float("nan")
    return float(np.cov(x, y)[0, 1] / np.var(x, ddof=1))


def calibrar(t0: float, tpl: np.ndarray, gl: int) -> dict:
    tpl = np.asarray(tpl, float)
    tpl = tpl[np.isfinite(tpl)]
    phi = max(1.0, float(np.std(tpl, ddof=1))) if len(tpl) > 2 else float("nan")
    return {"phi": phi, "p_cal": float(2 * stats.t.sf(abs(t0) / phi, gl)), "placebos": int(len(tpl)),
            "p95_abs_t_placebo": float(np.quantile(np.abs(tpl), 0.95)) if len(tpl) else float("nan"),
            "supera_p95": bool(abs(t0) > np.quantile(np.abs(tpl), 0.95)) if len(tpl) else False,
            "p_rangos": float((1 + (np.abs(tpl) >= abs(t0)).sum()) / (1 + len(tpl)))}


def ts_contraste(y: pd.Series, x: pd.Series, placebo: bool = True) -> dict:
    """y, x indexados por año; se usan los años con los dos datos (orden cronológico)."""
    f = pd.concat({"y": y, "x": x}, axis=1).dropna().sort_index()
    r = nw(f.y.to_numpy(), f.x.to_numpy())
    r["años"] = [int(f.index.min()), int(f.index.max())]
    r["n_años"] = int(len(f))
    r["huecos"] = int((np.diff(f.index.to_numpy()) != 1).sum())
    a = f.index.to_numpy()
    r["efecto_1878_1949"] = pendiente(f.y[a <= 1949], f.x[a <= 1949])
    r["efecto_1950_1999"] = pendiente(f.y[a >= 1950], f.x[a >= 1950])
    if placebo:
        T = len(f)
        xv, yv = f.x.to_numpy(), f.y.to_numpy()
        tpl = [nw(yv, np.roll(xv, k), r["lags"])["t"] for k in range(DESFASE_MIN, T - DESFASE_MIN + 1)]
        r["placebo"] = calibrar(r["t"], np.array(tpl), T - 1)
    return r


def panel_contraste(f: pd.DataFrame, ycol: str, dcol: str, placebo: bool = True, paises: bool = True) -> dict:
    """f con columnas pais, año, ycol, dcol (0/1)."""
    g = f[["pais", "año", ycol, dcol]].dropna().reset_index(drop=True)
    y, d, pais, anio = g[ycol], g[dcol].astype(float), g.pais, g["año"]
    r = I.driscoll_kraay(y, d, pais, anio)
    r["cr2"] = {k: v for k, v in I.contraste(y, d, pais, anio).items() if k in ("se", "t", "p", "ic95")}
    r["n"], r["n_estado"] = int(len(g)), int(d.sum())
    r["años_rango"] = [int(anio.min()), int(anio.max())]
    m50 = anio >= 1950
    r["efecto_1950_1999"] = (I.driscoll_kraay(y[m50], d[m50], pais[m50], anio[m50])["efecto"]
                             if d[m50].nunique() > 1 else float("nan"))
    if placebo:
        L = int(anio.max() - anio.min() + 1)
        tpl = []
        for k in range(DESFASE_MIN, L - DESFASE_MIN + 1):
            dk = I.desplazar(d, pais, anio, k)
            ok = dk.notna()
            if dk[ok].sum() >= 10 and (dk[ok] == 0).sum() >= 10:
                tpl.append(I.driscoll_kraay(y[ok], dk[ok], pais[ok], anio[ok])["t"])
        r["placebo"] = calibrar(r["t"], np.array(tpl), r["años"] - 1)
    if paises:
        ef = I.efectos_pais(y, d, pais)
        r["por_pais_sin_encoger"] = dict(zip(ef.pais, ef.efecto.round(4)))
        try:
            esa, mu, tau2 = I.encoger(I.efectos_pais_sin_año(y, d, pais, anio))
            r["por_pais_dl_sin_año"] = dict(zip(esa.pais, esa.encogido.round(4)))
            r["tau2_sin_año"] = tau2
        except Exception:  # noqa: BLE001  (p. ej. un solo país con datos)
            r["por_pais_dl_sin_año"] = {}
    return r


def frac_signo(efectos: dict, signo: int) -> float | None:
    v = [x for x in efectos.values() if np.isfinite(x)]
    return float(np.mean(np.sign(v) == signo)) if v else None


def criterios(r: dict, signo: int, holm_ok: bool, mundial: bool, dos_paises: bool = False) -> dict:
    c = {"1_signo": bool(np.sign(r["efecto"]) == signo),
         "2_holm_p_cal": bool(holm_ok),
         "3_supera_p95_placebo": bool(r["placebo"]["supera_p95"]),
         "4_signo_1950_1999": bool(np.sign(r["efecto_1950_1999"]) == signo)}
    if mundial:
        c["4b_signo_1878_1949"] = bool(np.sign(r["efecto_1878_1949"]) == signo)
    else:
        umbral = 1.0 if dos_paises else 2 / 3
        f1 = frac_signo(r["por_pais_sin_encoger"], signo)
        f2 = frac_signo(r["por_pais_dl_sin_año"], signo)
        c["5a_paises_sin_encoger"] = bool(f1 is not None and f1 >= umbral - 1e-12)
        c["5b_paises_dl_sin_año"] = bool(f2 is not None and f2 >= umbral - 1e-12)
    c["ESTABLECIDO"] = all(c.values())
    return c
