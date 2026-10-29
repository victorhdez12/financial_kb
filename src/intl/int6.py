"""P-DEV-INT6 v1.0 (docs/int/INT6_prerregistro_v1.md, congelado 2026-10-29T18:01:03Z): motor de la corrida única.
Funciones puras; la carga y la corrida están en scripts/int6_corrida.py. Concreciones: docs/int/INT6_notas_implementacion.md.

- `ts_mensual` (G2): MCO y = a + b·x, Newey-West con 6 retardos, placebo en círculo k = 12 … T − 12, φ y p_cal de INT-3b.
- `panel_continuo` (M1, M2): efecto fijo de país + b·z, Driscoll-Kraay por año, placebo `int3.desplazar` k = 6 … L − 6,
  1950-2004, pendientes por país sin encoger y DerSimonian-Laird sin la media del año, signo con efectos de año.
- `objetivo_crisis`, `liston_crisis` (K1); `evaluar` (K1, K2, X1, M3): logit, dejar un país fuera, AUC estratificada,
  bootstrap por bloques de año, placebo con el panel del candidato desplazado (z calibrada, unilateral).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata

from src.intl import int3 as I
from src.intl import int3b as B
from src.intl import int4 as M

GUERRAS = M.GUERRAS
HIPER = 0.5
LAGS_G2 = 6
KMIN_G2 = 12
ALFA = 0.05


# ---------------------------------------------------------------- reglas comunes
def hiper_fuera(infl_simple: pd.Series) -> set:
    """infl_simple indexada por (pais, año). Devuelve {(pais, t)} con inflación > 50 % en t o en t + 1."""
    alta = {(p, int(a)) for (p, a), v in infl_simple.items() if np.isfinite(v) and v > HIPER}
    return alta | {(p, a - 1) for p, a in alta}


def winsor(x: pd.Series, ref: pd.Series | None = None) -> pd.Series:
    ref = x if ref is None else ref
    lo, hi = np.nanquantile(ref.to_numpy(float), [0.01, 0.99])
    return x.clip(lo, hi)


# ---------------------------------------------------------------- G2: serie mensual
def ts_mensual(y: np.ndarray, x: np.ndarray, lags: int = LAGS_G2, kmin: int = KMIN_G2, placebo: bool = True) -> dict:
    y, x = np.asarray(y, float), np.asarray(x, float)
    r = B.nw(y, x, lags)
    T = len(y)
    r["r_estandarizada"] = float(r["efecto"] * x.std(ddof=1) / y.std(ddof=1))
    r["ic95_estandarizada"] = [float(v * x.std(ddof=1) / y.std(ddof=1)) for v in r["ic95"]]
    if placebo:
        tpl = np.array([B.nw(y, np.roll(x, k), lags)["t"] for k in range(kmin, T - kmin + 1)])
        r["placebo"] = B.calibrar(r["t"], tpl, T - 1)
    return r


# ---------------------------------------------------------------- M1 / M2: panel continuo
def pendientes_pais(y: pd.Series, z: pd.Series, pais: pd.Series, min_filas: int = 10) -> pd.DataFrame:
    filas = []
    for c in sorted(pais.unique()):
        m = (pais == c).to_numpy()
        yy, zz = y.to_numpy(float)[m], z.to_numpy(float)[m]
        if len(yy) < min_filas or np.var(zz) == 0:
            continue
        zc = zz - zz.mean()
        b = float((zc * (yy - yy.mean())).sum() / (zc ** 2).sum())
        e = yy - yy.mean() - b * zc
        filas.append({"pais": c, "efecto": b, "var": float((e ** 2).sum() / (len(yy) - 2) / (zc ** 2).sum())})
    return pd.DataFrame(filas)


def efecto_dos_vias(y: pd.Series, z: pd.Series, pais: pd.Series, anio: pd.Series) -> float:
    X = np.column_stack([z.to_numpy(float), pd.get_dummies(pais).to_numpy(float),
                         pd.get_dummies(anio).to_numpy(float)[:, 1:]])
    return float(np.linalg.lstsq(X, y.to_numpy(float), rcond=None)[0][0])


def estandarizar(x: pd.Series) -> pd.Series:
    return (x - x.mean()) / x.std(ddof=1)


def panel_continuo(f: pd.DataFrame, ycol: str, xcol: str, placebo: bool = True, completo: bool = True) -> dict:
    """f con columnas pais, año (= t), ycol (resultado de t + h ya alineado en la fila t), xcol (indicador ya
    winsorizado). z = x estandarizada en estas filas; b en unidades de y por 1 dt de x."""
    g = f[["pais", "año", ycol, xcol]].dropna().reset_index(drop=True)
    y, pais, anio = g[ycol].astype(float), g.pais, g["año"].astype(int)
    z = estandarizar(g[xcol].astype(float))
    r = I.driscoll_kraay(y, z, pais, anio)
    r.update({"n": int(len(g)), "paises": int(pais.nunique()), "años_rango": [int(anio.min()), int(anio.max())],
              "dt_x": float(g[xcol].std(ddof=1)), "media_x": float(g[xcol].mean())})
    if not completo:
        return r
    m50 = anio >= 1950
    r["efecto_1950_2004"] = I.driscoll_kraay(y[m50], z[m50], pais[m50], anio[m50])["efecto"] if m50.sum() > 20 else np.nan
    r["efecto_efectos_de_año"] = efecto_dos_vias(y, z, pais, anio)
    ef = pendientes_pais(y, z, pais)
    r["por_pais_sin_encoger"] = dict(zip(ef.pais, ef.efecto))
    yd = y - y.groupby(anio).transform("mean")
    esa, mu, tau2 = I.encoger(pendientes_pais(yd, z, pais))
    r["por_pais_dl_sin_año"] = dict(zip(esa.pais, esa.encogido))
    r["dl_sin_año_media"], r["tau2_sin_año"] = mu, tau2
    if placebo:
        L = int(anio.max() - anio.min() + 1)
        tpl = []
        for k in range(I.DESFASE_MIN, L - I.DESFASE_MIN + 1):
            zk = I.desplazar(z, pais, anio, k)
            ok = zk.notna()
            if ok.sum() > 20:
                tpl.append(I.driscoll_kraay(y[ok], zk[ok], pais[ok], anio[ok])["t"])
        r["placebo"] = B.calibrar(r["t"], np.array(tpl), r["años"] - 1)
    return r


def criterios_panel(r: dict, signo: int, holm_ok: bool) -> dict:
    f1 = B.frac_signo(r["por_pais_sin_encoger"], signo)
    f2 = B.frac_signo(r["por_pais_dl_sin_año"], signo)
    c = {"1_signo": bool(np.sign(r["efecto"]) == signo),
         "2_holm6_p_cal": bool(holm_ok),
         "3_supera_p95_placebo": bool(r["placebo"]["supera_p95"]),
         "4_signo_1950_2004": bool(np.sign(r["efecto_1950_2004"]) == signo),
         "5a_paises_sin_encoger_2_3": bool(f1 is not None and f1 >= 2 / 3 - 1e-12),
         "5b_paises_dl_sin_año_2_3": bool(f2 is not None and f2 >= 2 / 3 - 1e-12),
         "6_signo_efectos_de_año": bool(np.sign(r["efecto_efectos_de_año"]) == signo)}
    c["ESTABLECIDO"] = all(c.values())
    return c


# ---------------------------------------------------------------- K1: crisis bancarias
def inicios_crisis(cr: pd.Series) -> set:
    return set(cr[cr == 1].index.astype(int))


def objetivo_crisis(crisis: dict, años_pais: dict, paises: list[str], h: int, desde: int, sin_guerras: bool,
                    excluir_tras: int = 4, fuera: set = frozenset()) -> pd.DataFrame:
    """Como scripts/int6_potencia.objetivo_crisis, con la lista de países y la cronología (crisis[c] = serie anual 0/1)
    como parámetros, y las filas de `fuera` (hiperinflación) quitadas."""
    filas = []
    for c in paises:
        ini = inicios_crisis(crisis[c])
        años = años_pais[c]
        for t in sorted(años):
            if t < desde or t + h > M.A1 or any(t + k not in años for k in range(1, h + 1)):
                continue
            if any(t - k in ini for k in range(0, excluir_tras + 1)):
                continue
            if sin_guerras and any(y in GUERRAS for y in range(t, t + h + 1)):
                continue
            if (c, t) in fuera:
                continue
            E = [y for y in range(t + 1, t + h + 1) if y in ini]
            filas.append({"pais": c, "t": t, "y": int(bool(E)), "E": E[0] if E else None})
    return pd.DataFrame(filas)


def liston_crisis(filas: pd.DataFrame, crisis: dict, primer: dict) -> np.ndarray:
    """B1 = log(1 + años desde el último inicio ≤ t); sin inicio previo, desde el primer año del país (censura)."""
    out = []
    for c, t in zip(filas.pais, filas.t):
        prev = [a for a in inicios_crisis(crisis[c]) if a <= t]
        ref = max(prev) if prev else primer[c]
        out.append(np.log1p(max(t - ref, 0)))
    return np.array(out, float).reshape(-1, 1)


# ---------------------------------------------------------------- evaluación de un candidato (K1, K2, X1, M3)
def auc_estrat(y, p, g) -> float:
    """Igual que scripts/int4_sensibilidad_liston.auc_estrat (un test lo comprueba)."""
    num = den = 0.0
    for c in np.unique(g):
        f = g == c
        yy, pp = y[f].astype(bool), p[f]
        n1, n0 = yy.sum(), (~yy).sum()
        if n1 == 0 or n0 == 0:
            continue
        r = rankdata(pp)
        num += r[yy].sum() - n1 * (n1 + 1) / 2
        den += n1 * n0
    return num / den if den else np.nan


def boot(y, p1, p0, t, g, B_: int = 2000, semilla: int = 0) -> dict:
    """Bootstrap por bloques de año sobre predicciones fijas: ΔAUC estratificada, Δlog-loss, ΔAUC agrupada."""
    años = np.unique(t)
    idx = {a: np.flatnonzero(t == a) for a in años}
    rng = np.random.default_rng(semilla)
    d = np.empty((B_, 3))
    for b in range(B_):
        s = np.concatenate([idx[a] for a in rng.choice(años, len(años), replace=True)])
        d[b] = (auc_estrat(y[s], p1[s], g[s]) - auc_estrat(y[s], p0[s], g[s]),
                M.logloss(y[s], p1[s]) - M.logloss(y[s], p0[s]), M.auc(y[s], p1[s]) - M.auc(y[s], p0[s]))
    obs = auc_estrat(y, p1, g) - auc_estrat(y, p0, g)
    da = d[:, 0][np.isfinite(d[:, 0])]
    lado = (da <= 0).sum() if obs > 0 else (da >= 0).sum()
    q = lambda v: [float(np.quantile(v[np.isfinite(v)], 0.025)), float(np.quantile(v[np.isfinite(v)], 0.975))]  # noqa: E731
    return {"auc_modelo": auc_estrat(y, p1, g), "auc_liston": auc_estrat(y, p0, g), "d_auc": float(obs),
            "d_auc_ic95": q(d[:, 0]), "p_bloques": float(min(1.0, 2 * (1 + lado) / (1 + len(da)))),
            "d_logloss": M.logloss(y, p1) - M.logloss(y, p0), "d_logloss_ic95": q(d[:, 1]),
            "d_auc_agrupada": M.auc(y, p1) - M.auc(y, p0), "d_auc_agrupada_ic95": q(d[:, 2]), "años": int(len(años))}


def z_placebo(obs: float, ds: np.ndarray) -> dict:
    ds = np.asarray(ds, float)
    ds = ds[np.isfinite(ds)]
    mu, sd = float(ds.mean()), float(ds.std(ddof=1))
    z = (obs - mu) / sd if sd > 0 else np.nan
    return {"desplazamientos": int(len(ds)), "media": mu, "dt": sd, "z": float(z), "p_z": float(norm.sf(z)),
            "p_rangos": float((1 + (ds >= obs).sum()) / (1 + len(ds)))}


def mirar(filas: pd.DataFrame, paneles: list[pd.DataFrame], k: int = 0) -> np.ndarray:
    """Valores (país, t) de los paneles años × países (índice A0 … A1), desplazados k años en círculo si k ≠ 0."""
    cols = []
    for p in paneles:
        p = p.reindex(index=range(M.A0, M.A1 + 1))
        q = p if k == 0 else M.desplazar_panel(p, k)
        cols.append(M._mira(q, filas.pais.to_numpy(), filas.t.to_numpy()))
    return np.column_stack(cols) if cols else np.empty((len(filas), 0))


def _ok(*mats) -> np.ndarray:
    return np.all([np.isfinite(m).all(axis=1) for m in mats], axis=0)


def evaluar(filas: pd.DataFrame, base: np.ndarray, cand: list[pd.DataFrame], h: int = 1, placebo: bool = True,
            periodos: dict | None = None, temporal: bool = True, B_: int = 2000) -> dict:
    """Modelo (base + candidatos) frente a la base, en las filas completas: dejar un país fuera, AUC estratificada,
    bootstrap, calibración, periodos (sobre las predicciones ya hechas), temporal 1950-2004, placebo."""
    Xc = mirar(filas, cand)
    ok = _ok(base, Xc)
    f = filas[ok].reset_index(drop=True)
    y, g, t = f.y.to_numpy(float), f.pais.to_numpy(), f.t.to_numpy()
    X0, X1 = base[ok], np.column_stack([base[ok], Xc[ok]])
    p1, p0 = M.loco(X1, y, g), M.loco(X0, y, g)
    out = {"filas": int(len(y)), "eventos": int(y.sum()), "paises": int(np.unique(g).size),
           "años_eventos": int(np.unique(t[y == 1]).size), **boot(y, p1, p0, t, g, B_),
           "calibracion": M.calibracion(y, p1)}
    for nom, (a, b) in (periodos or {}).items():
        m = (t >= a) & (t <= b)
        out[f"periodo_{nom}"] = {"filas": int(m.sum()), "eventos": int(y[m].sum()),
                                 "d_auc": auc_estrat(y[m], p1[m], g[m]) - auc_estrat(y[m], p0[m], g[m])}
    if temporal:
        q1, q0 = M.temporal(X1, y, t, h), M.temporal(X0, y, t, h)
        v = np.isfinite(q1) & np.isfinite(q0)
        out["temporal_1950_2004"] = {"filas": int(v.sum()), "eventos": int(y[v].sum()),
                                     "d_auc": auc_estrat(y[v], q1[v], g[v]) - auc_estrat(y[v], q0[v], g[v]),
                                     "d_auc_agrupada": M.auc(y[v], q1[v]) - M.auc(y[v], q0[v])}
    if placebo:
        ds = []
        y_all = filas.y.to_numpy(float)
        for k in M.KS:
            Xk = mirar(filas, cand, k)
            okk = _ok(base, Xk)
            yk, gk = y_all[okk], filas.pais.to_numpy()[okk]
            if yk.sum() < 10 or (1 - yk).sum() < 10:
                continue
            a1 = auc_estrat(yk, M.loco(np.column_stack([base[okk], Xk[okk]]), yk, gk), gk)
            ds.append(a1 - auc_estrat(yk, M.loco(base[okk], yk, gk), gk))
        out["placebo"] = z_placebo(out["d_auc"], np.array(ds))
    return out


def congelado(fn: pd.DataFrame, base_n: np.ndarray, cand_n: list, fp: pd.DataFrame, base_p: np.ndarray,
              cand_p: list, B_: int = 2000) -> dict:
    """Países de prueba: modelo y base ajustados una vez con todo el núcleo; predicción de los países de prueba."""
    Xn = mirar(fn, cand_n)
    okn = _ok(base_n, Xn)
    yn = fn.y.to_numpy(float)[okn]
    b1 = M.logit_fit(np.column_stack([base_n[okn], Xn[okn]]), yn)
    b0 = M.logit_fit(base_n[okn], yn)
    Xp = mirar(fp, cand_p)
    okp = _ok(base_p, Xp)
    yp = fp.y.to_numpy(float)[okp]
    if okp.sum() == 0 or yp.sum() == 0:
        return {"filas": int(okp.sum()), "eventos": int(yp.sum())}
    g, t = fp.pais.to_numpy()[okp], fp.t.to_numpy()[okp]
    p1 = M.logit_pred(b1, np.column_stack([base_p[okp], Xp[okp]]))
    p0 = M.logit_pred(b0, base_p[okp])
    out = {"filas": int(len(yp)), "eventos": int(yp.sum()), **boot(yp, p1, p0, t, g, B_)}
    out["por_pais"] = {c: {"filas": int((g == c).sum()), "eventos": int(yp[g == c].sum()),
                           "d_auc": M.auc(yp[g == c], p1[g == c]) - M.auc(yp[g == c], p0[g == c])}
                       for c in np.unique(g)}
    return out


def criterios_auc(r: dict, holm_i: bool, holm_ii: bool, iv: bool, nombre_iv: str) -> dict:
    pend = r["calibracion"]["pendiente"]
    c = {"i_dauc_estrat_ic_holm6": bool(r["d_auc"] > 0 and holm_i), "ii_z_placebo_holm6": bool(holm_ii),
         "iii_dlogloss_neg": bool(r["d_logloss"] < 0), f"iv_{nombre_iv}": bool(iv),
         "v_pendiente_0.5_1.5": bool(0.5 <= pend <= 1.5)}
    c["ESTABLECIDO"] = all(c.values())
    return c


# ---------------------------------------------------------------- indicadores
def delta_diciembre(s: pd.Series) -> pd.Series:
    """Serie mensual → valor de diciembre de t menos el de diciembre de t − 1 (años consecutivos), indexada por t."""
    d = s[s.index.month == 12]
    d = pd.Series(d.values, index=d.index.year)
    return (d - d.shift(1)).where(pd.Series(d.index, index=d.index).diff() == 1)


def nivel_mediana10(s: pd.Series) -> pd.Series:
    d = s[s.index.month == 12]
    d = pd.Series(d.values, index=d.index.year).reindex(range(int(d.index.year.min()), int(d.index.year.max()) + 1))
    return (d - d.rolling(10, min_periods=10).median()).dropna()


def empalme(uk: pd.Series, us: pd.Series, corte: int = 1918) -> pd.Series:
    """R. U. para t ≤ corte y EE. UU. para t > corte (series anuales ya transformadas dentro de cada una)."""
    return pd.concat([uk[uk.index <= corte], us[us.index > corte]]).sort_index()


def comun(s: pd.Series, paises: list[str]) -> pd.DataFrame:
    """Panel años × países con el mismo valor para todos (variable común)."""
    s = s.reindex(range(M.A0, M.A1 + 1))
    return pd.DataFrame({c: s for c in paises})


def cuota_otros(cae: pd.DataFrame, nucleo: list[str], paises: list[str], pesos: pd.DataFrame | None = None,
                minimo: int = 5) -> pd.DataFrame:
    """% (o cuota ponderada) de los otros países del núcleo con caída en t; NaN si < `minimo` con dato."""
    out = {}
    for c in paises:
        otros = [k for k in nucleo if k != c and k in cae.columns]
        v = cae[otros]
        n = v.notna().sum(axis=1)
        if pesos is None:
            s = v.mean(axis=1)
        else:
            w = pesos[otros].where(v.notna())
            s = (v * w).sum(axis=1) / w.sum(axis=1)
        out[c] = s.where(n >= minimo)
    return pd.DataFrame(out).reindex(index=range(M.A0, M.A1 + 1))
