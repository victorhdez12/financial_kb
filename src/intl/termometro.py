"""Termómetro de recesión INFORMATIVO (docs/int/TERMOMETRO_diseno_v1.md, v1.2 `e9ec71d`): traducción mensual de los
indicadores de INT-4, rectas de escala (pares ≤ 2004), puerta de la traducción (impares), fechado "en recesión" con el PIB
trimestral y percentiles de referencia. Solo desarrollo (≤ 2004): la parte en vivo va aparte y solo si pasa la puerta.

Concreciones (las del §8 del diseño; aquí solo las de código):
- Rejilla: fin de mes. Una fila anual (país, t) se lee en el fin de abril de t + 1 (origen de INT-4); como el panel
  mensual acaba en 2004-12, las filas usables son t ≤ 2003 (las de INT-4 ya acaban en t + 1 ≤ 2004).
- Trimestrales (BIS, PIB): fechados a inicio de trimestre; las transformaciones se hacen sobre la rejilla trimestral
  completa (huecos = NaN) y después se pasan a "as of" (fin de trimestre + retraso); un dato más viejo que 200 días cuenta
  como ausente.
- Fechado trimestral: d(q) = S(q) − S(q − 1) con S la suma de 4 trimestres (= PIB(q) − PIB(q − 4)). Entra en el trimestre
  de la 2.ª caída seguida (fuera de recesión) y sale en el de la 2.ª subida seguida (dentro). Se conoce 75 días después.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.intl import int4 as M

LINEALES = ["C1", "C2", "C5", "C6"]          # con recta de escala; C4 y S4 sin recta (§8 a, d)
SIN_BOLSA = {"DNK", "JPN"}                   # índices OCDE rotos (src/intl/panel.py) → sin C6 mensual
RETRASO_BIS, RETRASO_PIB, MAX_VIEJO_Q = 183, 75, 200
MIN_AÑOS_MITAD, MIN_FILAS_PUERTA = 15, 8
PUERTA_R, PUERTA_PEND = 0.8, (0.8, 1.25)
ALIAS = {"S1": "C1", "S2": "C5", "S3": "C6"}


# ---------------------------------------------------------------- trimestrales "as of"
def _rejilla_q(s: pd.Series) -> pd.Series:
    p = s.index.to_period("Q")
    if p.duplicated().any():
        raise ValueError(f"{s.name}: dos observaciones en el mismo trimestre")
    return pd.Series(s.values, index=p).reindex(pd.period_range(p.min(), p.max(), freq="Q"))


def asof_q(s: pd.Series, retraso: int, rejilla: pd.DatetimeIndex) -> pd.Series:
    """`s` indexada por periodo trimestral → valor conocido en cada fin de mes de la rejilla."""
    s = s.dropna()
    if s.empty:
        return pd.Series(np.nan, index=rejilla)
    disp = s.index.to_timestamp(how="end").normalize() + pd.Timedelta(days=retraso)
    obs = pd.DataFrame({"disp": disp, "v": s.values}).sort_values("disp")
    m = pd.merge_asof(pd.DataFrame({"t": rejilla}), obs, left_on="t", right_on="disp")
    m.loc[(m["t"] - m["disp"]).dt.days > MAX_VIEJO_Q, "v"] = np.nan
    return pd.Series(m["v"].values, index=rejilla)


def fechado_trimestral(pib: pd.Series) -> pd.DataFrame:
    """Entradas y salidas de recesión con la regla de dos trimestres (§3). Devuelve una fila por trimestre con `en_rec`
    y los trimestres de entrada y de la última salida (NaT si no hay)."""
    q = _rejilla_q(pib)
    d = q.rolling(4, min_periods=4).sum().diff()
    en, filas = False, []
    entrada = salida = None
    for i, per in enumerate(d.index):
        a, b = (d.iloc[i - 1] if i else np.nan), d.iloc[i]
        if np.isfinite(a) and np.isfinite(b):
            if not en and a < 0 and b < 0:
                en, entrada = True, per
            elif en and a > 0 and b > 0:
                en, salida = False, per
        filas.append({"q": per, "en_rec": en if np.isfinite(b) else np.nan, "entrada": entrada, "salida": salida})
    return pd.DataFrame(filas).set_index("q")


def estado_mensual(fq: pd.DataFrame, rejilla: pd.DatetimeIndex, primer: pd.Timestamp) -> pd.DataFrame:
    """Estado conocido cada fin de mes: en recesión, meses desde la entrada y desde la última salida (o desde `primer`,
    el primer trimestre con PIB, si no hubo salida)."""
    disp = fq.index.to_timestamp(how="end").normalize() + pd.Timedelta(days=RETRASO_PIB)
    obs = fq.reset_index(drop=True).assign(disp=disp).sort_values("disp")
    m = pd.merge_asof(pd.DataFrame({"t": rejilla}), obs, left_on="t", right_on="disp")
    mes = (m["t"].dt.year * 12 + m["t"].dt.month).to_numpy()
    fin_q = lambda per: per.year * 12 + per.quarter * 3  # noqa: E731  (mes de cierre del trimestre)
    ini = primer.to_period("Q")
    out = pd.DataFrame(index=rejilla)
    out["en_rec"] = m["en_rec"].to_numpy(float)
    out["meses_desde_entrada"] = [np.nan if pd.isna(e) else mes[i] - fin_q(e) for i, e in enumerate(m["entrada"])]
    out["meses_desde_salida"] = [mes[i] - fin_q(ini if pd.isna(s) else s) for i, s in enumerate(m["salida"])]
    out["hubo_salida"] = m["salida"].notna().to_numpy()
    viejo = ((m["t"] - m["disp"]).dt.days > MAX_VIEJO_Q) | m["disp"].isna()
    out.loc[viejo.to_numpy(), "en_rec"] = np.nan
    return out


# ---------------------------------------------------------------- indicadores mensuales sin traducir
def mensuales(pm: pd.DataFrame, bis: dict, pib: dict, nucleo: list[str], paises: list[str]) -> dict:
    """Paneles (fin de mes × países). `pm` = src/intl/panel.mensual (ya "as of"); `bis`, `pib`: país → serie
    trimestral (fechas de inicio de trimestre)."""
    w = lambda col: pm[col].unstack(0).reindex(columns=paises)  # noqa: E731
    rej = w("curva").index
    c1 = w("curva").rolling(12, min_periods=9).mean()
    r = w("tipo_3m").rolling(12, min_periods=9).mean() / 100 - w("ipc_yoy")
    c6 = w("bolsa_12m") - w("ipc_yoy")
    c6[[c for c in paises if c in SIN_BOLSA]] = np.nan
    c2 = pd.DataFrame({c: asof_q(_rejilla_q(bis[c]).diff(20), RETRASO_BIS, rej) if c in bis else np.nan
                       for c in paises}, index=rej)
    g4 = pd.DataFrame({c: asof_q(np.log(_rejilla_q(pib[c])).diff(4), RETRASO_PIB, rej) if c in pib else np.nan
                       for c in paises}, index=rej)
    out = {"C1": c1, "C2": c2, "C5": r - r.shift(12), "C6": c6}
    for k, base in (("C4", c1), ("S4", g4)):
        neg = (base < 0).astype(float).where(base.notna())
        out[k] = pd.DataFrame({c: neg[[o for o in nucleo if o != c]].mean(axis=1)
                               .where(neg[[o for o in nucleo if o != c]].notna().sum(axis=1) >= 5) for c in paises})
    return out


def abril(mp: pd.DataFrame, años) -> pd.DataFrame:
    """Valor mensual en el fin de abril de t + 1, como panel años t × países."""
    idx = pd.to_datetime([f"{a + 1}-04-30" for a in años])
    return mp.reindex(idx).set_axis(list(años))


# ---------------------------------------------------------------- rectas de escala
def _mco(x, y):
    b, a = np.polyfit(x, y, 1)
    return float(a), float(b)


def rectas(pan: dict, mens: dict, nucleo: list[str], paises: list[str], par_fit=lambda t: t % 2 == 0,
           par_puerta=lambda t: t % 2 == 1) -> dict:
    """x_anual(t) ≈ a + b · x_mensual(abril t + 1). Propia si ≥ 15 años con ambos en cada mitad; si no, agrupada (los
    años de ajuste de todo el núcleo). Devuelve {indicador: {"agrupada": (a, b, n), país: {"a", "b", "tipo", ...}}}."""
    años = list(range(1950, 2004))
    out = {}
    for ind in LINEALES:
        xa = pan[ind].reindex(index=años)
        xm = abril(mens[ind], años)
        par = {}
        for c in paises:
            df = pd.DataFrame({"a": xa.get(c), "m": xm.get(c)}).dropna() if c in xa and c in xm else pd.DataFrame()
            par[c] = df
        pool = pd.concat([par[c][[par_fit(t) for t in par[c].index]] for c in nucleo if not par[c].empty])
        ag = _mco(pool["m"], pool["a"]) if len(pool) >= 3 else (np.nan, np.nan)
        res = {"agrupada": {"a": ag[0], "b": ag[1], "n": int(len(pool))}}
        for c, df in par.items():
            fit = df[[par_fit(t) for t in df.index]] if not df.empty else df
            n_f = len(fit)
            n_p = int(sum(par_puerta(t) for t in df.index)) if not df.empty else 0
            if n_f >= MIN_AÑOS_MITAD and n_p >= MIN_AÑOS_MITAD:
                a, b = _mco(fit["m"], fit["a"])
                res[c] = {"a": a, "b": b, "tipo": "propia", "n_ajuste": n_f, "n_puerta": n_p}
            else:
                res[c] = {"a": ag[0], "b": ag[1], "tipo": "agrupada", "n_ajuste": n_f, "n_puerta": n_p}
        out[ind] = res
    return out


def traducir(mens: dict, rec: dict, paises: list[str]) -> dict:
    """Paneles mensuales en la escala anual de JST (C4 y S4 tal cual)."""
    out = {k: mens[k] for k in ("C4", "S4")}
    for ind in LINEALES:
        out[ind] = pd.DataFrame({c: rec[ind][c]["a"] + rec[ind][c]["b"] * mens[ind][c] for c in paises},
                                index=mens[ind].index)
    return out


def matriz_mensual(filas: pd.DataFrame, tr: dict, cols: list[str]) -> np.ndarray:
    """Como int4.matriz, pero leyendo los paneles traducidos en abril de t + 1 (S5: abril del año del pico + 1)."""
    out = []
    for c in cols:
        base = "C2" if c == "S5" else ALIAS.get(c, c)
        años = filas["pico"].to_numpy() if c == "S5" else filas["t"].to_numpy()
        fechas = pd.to_datetime([f"{a + 1}-04-30" for a in años])
        p = tr[base]
        ri, ci = p.index.get_indexer(fechas), p.columns.get_indexer(filas["pais"].to_numpy())
        v = np.full(len(filas), np.nan)
        ok = (ri >= 0) & (ci >= 0)
        v[ok] = p.to_numpy()[ri[ok], ci[ok]]
        out.append(v)
    return np.column_stack(out)


# ---------------------------------------------------------------- modelo congelado y puerta
def congelar(B1: np.ndarray, X: np.ndarray, y: np.ndarray) -> np.ndarray:
    ok = np.isfinite(B1).all(axis=1) & np.isfinite(X).all(axis=1)
    return M.logit_fit(np.column_stack([B1, X])[ok], y[ok])


def puerta(pa: np.ndarray, pm: np.ndarray) -> dict:
    ok = np.isfinite(pa) & np.isfinite(pm)
    pa, pm = pa[ok], pm[ok]
    if len(pa) < 3 or np.std(pm) == 0:
        return {"filas": int(len(pa)), "r": None, "pendiente": None, "pasa": False}
    r = float(np.corrcoef(pa, pm)[0, 1])
    pend = float(np.polyfit(pm, pa, 1)[0])
    return {"filas": int(len(pa)), "r": r, "pendiente": pend,
            "pasa": bool(r >= PUERTA_R and PUERTA_PEND[0] <= pend <= PUERTA_PEND[1])}


# ---------------------------------------------------------------- B1 en vivo (fechado trimestral)
def b1_vivo(est: pd.DataFrame, giro: str) -> np.ndarray:
    if giro == "T1":
        primero = (est["hubo_salida"] & (est["meses_desde_salida"] < 12)).astype(float)
        return np.column_stack([primero, np.log(np.maximum(est["meses_desde_salida"] / 12, 1))])
    return np.log(np.maximum(est["meses_desde_entrada"].to_numpy(float) / 12, 1)).reshape(-1, 1)


def concordancia(rec: pd.DataFrame, fq: dict, desde: int = 1961, hasta: int = 2003) -> dict:
    """Fechado trimestral frente al anual de JST (≤ 2004, sin rentabilidades): una recesión JST (pico p, valle v) está
    'cazada' si hay una entrada trimestral en el año p + 1 ± 1; su salida, si hay una salida en v + 1 ± 1. Entradas
    trimestrales sin recesión JST en ± 1 = falsas."""
    out = {}
    for c, f in fq.items():
        ent = sorted({p.year for p in f["entrada"].dropna().unique() if desde <= p.year <= hasta})
        sal = sorted({p.year for p in f["salida"].dropna().unique() if desde <= p.year <= hasta})
        r = rec[(rec.pais == c) & (rec.pico + 1 >= max(desde, f.index.min().year + 2)) & (rec.pico + 1 <= hasta)]
        cz_e = [int(any(abs(e - (p + 1)) <= 1 for e in ent)) for p in r.pico]
        cz_s = [int(any(abs(s - (v + 1)) <= 1 for s in sal)) for v in r.valle]
        falsas = [e for e in ent if not any(abs(e - (p + 1)) <= 1 for p in r.pico)]
        out[c] = {"recesiones_jst": int(len(r)), "entradas_cazadas": int(sum(cz_e)), "salidas_cazadas": int(sum(cz_s)),
                  "entradas_trimestrales": len(ent), "falsas": falsas}
    tot = {k: sum(v[k] for v in out.values()) for k in ("recesiones_jst", "entradas_cazadas", "salidas_cazadas",
                                                       "entradas_trimestrales")}
    tot["falsas"] = sum(len(v["falsas"]) for v in out.values())
    return {"por_pais": out, "total": tot}


# ---------------------------------------------------------------- recalibración (v1.3, §9)
def _lg(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def calibrar(pa: np.ndarray, pm: np.ndarray) -> tuple[float, float]:
    """MCO de logit(p anual) sobre logit(p mensual) → (α, β). Solo las dos probabilidades, nunca el objetivo."""
    ok = np.isfinite(pa) & np.isfinite(pm)
    b, a = np.polyfit(_lg(pm[ok]), _lg(pa[ok]), 1)
    return float(a), float(b)


def aplicar_cal(pm: np.ndarray, cal: tuple[float, float]) -> np.ndarray:
    return 1 / (1 + np.exp(-(cal[0] + cal[1] * _lg(pm))))
