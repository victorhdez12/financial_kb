"""Corrida ÚNICA de P-DEV-INT7 v1.0 (docs/int/INT7_prerregistro_v1.md, congelado 2026-10-29T18:34:16Z, 711dcd9).
Lecturas de las ambigüedades del texto congelado: docs/int/INT7_notas_implementacion.md (fijadas antes de correr).

- Confirmatorias V1 y V2 (§3): MCO con efectos fijos y Driscoll-Kraay; efecto leído = Amihud-Hurvich; p principal =
  bootstrap nulo que conserva δ (§3.2, 4.999 réplicas, bloques de 5 años); Holm-2; criterios 1-5; sensibilidades.
- Informativas y descriptivas (§4, §11): V3 (5 años), V4 (CAPE de EE. UU.), §4.3 (dividendo), §4.4 (fuera de muestra),
  V5 (× estanflación), V6 (EE. UU. mensual, 3 y 6 meses).
Datos: solo src/intl/data.load_dev (≤ 2004-12); JST núcleo de 14 países (+ AUS, CHE en una sensibilidad) y Shiller.

Uso: .venv/bin/python -m scripts.int7_corrida               (con puerta: árbol limpio; UNA vez; escribe la salida)
     .venv/bin/python -m scripts.int7_corrida --sintetico   (datos SINTÉTICOS, 19 réplicas, sin puerta, no escribe)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import int3 as I
from src.intl import int7 as V
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
PRUEBA = ["AUS", "CHE"]
HIPER = 0.50
GUERRA = set(range(1914, 1919)) | set(range(1939, 1946))
AÑOS = np.arange(1870, 2005)
B = 4999
SEED = 20261029
PRERREG = "docs/int/INT7_prerregistro_v1.md v1.0 (711dcd9)"
MDE_V5 = {"1 contraste": 5.67, "Holm-2": 6.24, "Holm-3": 6.54}      # research/int/int7_potencia.json (pp por dt)
FRASE_V5 = "con 237 país-años en estanflación esto no puede distinguir una modulación de 1-3 pp de cero"
FRASE_V6 = ("a horizontes cortos la valoración explica muy poco de la rentabilidad; su información se acumula con el "
            "horizonte")


# ------------------------------------------------------------------ carga
def cargar_real() -> dict:
    from src.intl import panel as P
    from src.warehouse import db
    con = D.connect()
    a = P.anual(con)
    a = a[a.index.get_level_values(1) <= 2004]
    cg = {c: D.load_dev(con, f"jst_{c.lower()}_eq_capgain") for c in NUCLEO + PRUEBA}
    cg = pd.concat({c: pd.Series(s.values, index=s.index.year) for c, s in cg.items()}, names=["pais", "año"])
    sh = {k: D.load_dev(con, f"shiller_{k}") for k in ("cape", "real_price", "real_earnings", "real_dividend",
                                                         "real_stock_tr_ret_m")}
    con.close()
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    return {"anual": a, "capgain": cg, "shiller": sh, "regimen": et}


def cargar_sintetico(rng: np.random.Generator) -> dict:
    """Misma estructura que cargar_real, valores inventados (solo para comprobar que el código corre)."""
    filas = []
    for c in NUCLEO + PRUEBA + ["CAN"]:
        n = len(AÑOS)
        x = np.empty(n)
        x[0] = -3.3
        for t in range(1, n):
            x[t] = -3.3 + 0.8 * (x[t - 1] + 3.3) + 0.3 * rng.standard_normal()
        cpi = np.exp(np.cumsum(0.03 + 0.05 * rng.standard_normal(n)))
        if c == "DEU":
            cpi[52] = cpi[51] * 3                                   # una "hiperinflación"
        filas.append(pd.DataFrame({"pais": c, "año": AÑOS, "eq_dp": np.exp(x),
                                   "eq_tr_real": np.exp(0.06 + 0.2 * rng.standard_normal(n)) - 1,
                                   "bill_rate_real": 0.01 + 0.03 * rng.standard_normal(n), "cpi": cpi}))
    a = pd.concat(filas).set_index(["pais", "año"]).sort_index()
    a.loc[("FIN", slice(1870, 1911)), "eq_dp"] = np.nan
    a.loc[("ITA", 1945), "eq_dp"] = -0.01
    cg = pd.Series(0.05 + 0.2 * rng.standard_normal(len(a)), index=a.index)
    m = pd.date_range("1871-01-01", "2004-12-01", freq="MS")
    xm = np.cumsum(0.01 * rng.standard_normal(len(m)))
    sh = {"real_price": pd.Series(np.exp(4 + xm), index=m), "real_earnings": pd.Series(np.exp(1.3 + 0.002 * np.arange(
        len(m)) * 0.1 + 0.05 * rng.standard_normal(len(m))), index=m),
        "real_dividend": pd.Series(np.exp(1 + 0.03 * rng.standard_normal(len(m))), index=m),
        "real_stock_tr_ret_m": pd.Series(0.005 + 0.04 * rng.standard_normal(len(m)), index=m)}
    sh["cape"] = pd.Series(np.exp(2.8 + xm), index=m)[m >= "1881-01-01"]
    reg = []
    for c in NUCLEO + PRUEBA:
        for y in range(1870, 2005):
            reg.append({"pais": c, "año": y, "cuadrante": rng.choice(["expansion", "estanflacion", "crecimiento_bajo",
                                                                      "sobrecalentamiento"]) if y <= 1999 else None,
                        "truncada": y > 1999})
    return {"anual": a, "capgain": cg, "shiller": sh, "regimen": pd.DataFrame(reg)}


# ------------------------------------------------------------------ matrices año × país
def mat(s: pd.Series, paises: list[str]) -> np.ndarray:
    if not isinstance(s.index, pd.MultiIndex):
        assert paises == ["USA"]
        return s.reindex(AÑOS).to_numpy(float)[:, None]
    return s.unstack(0).reindex(index=AÑOS, columns=paises).to_numpy(float)


def construir(a: pd.DataFrame, cg: pd.Series, paises: list[str]) -> dict:
    a = a[a.index.get_level_values(0).isin(paises)]
    dp, cpi = mat(a["eq_dp"], paises), mat(a["cpi"], paises)
    infl = np.full(cpi.shape, np.nan)
    infl[1:] = cpi[1:] / cpi[:-1] - 1
    H = infl > HIPER                                                    # NaN → no es hiperinflación
    with np.errstate(invalid="ignore", divide="ignore"):
        X = np.log(np.where(dp > 0, dp, np.nan))
        Y = np.log1p(mat(a["eq_tr_real"], paises))
        Yb = np.log1p(mat(a["bill_rate_real"], paises))
        G = np.full(dp.shape, np.nan)                                   # crecimiento real del dividendo en s (§4.3)
        G[1:] = X[1:] - X[:-1] + np.log1p(mat(cg, paises))[1:] - np.log(cpi[1:] / cpi[:-1])
    return {"dp": np.where(dp > 0, dp, np.nan), "X": X, "Y": Y, "Yex": Y - Yb, "G": G, "H": H, "paises": paises}


def filas_h(Xm: np.ndarray, Ym: np.ndarray, H: np.ndarray | None, h: int = 1, rez_x: int = 0) -> np.ndarray:
    """Fila t: indicador en t − rez_x, resultados en t+1 … t+h, sin hiperinflación en ninguno de esos años (con H)."""
    n = Xm.shape[0]
    f = np.zeros(Xm.shape, bool)
    for t in range(rez_x, n - h):
        ok = np.isfinite(Xm[t - rez_x]) & np.all(np.isfinite(Ym[t + 1: t + h + 1]), axis=0)
        if H is not None:
            ok &= ~np.any(H[t - rez_x: t + h + 1], axis=0)
        f[t] = ok
    return f


def estandarizar(Xm: np.ndarray, filas: np.ndarray) -> tuple[np.ndarray, float, float]:
    v = Xm[filas]
    mu, sd = float(v.mean()), float(v.std(ddof=1))
    return (Xm - mu) / sd, mu, sd


def relativo(Z: np.ndarray, limpio: np.ndarray) -> np.ndarray:
    """z sin efectos de país ni de año (proyección exacta sobre las celdas limpias)."""
    ti, tj = np.nonzero(limpio)
    out = np.full(Z.shape, np.nan)
    out[ti, tj] = V.FE(tj, ti, True)(Z[ti, tj])
    return out


def desplazar(M: np.ndarray, k: int) -> np.ndarray:
    """M[t] → M[t − k] (k > 0: valor de k años antes en la fila t)."""
    out = np.full(M.shape, np.nan)
    if k > 0:
        out[k:] = M[:-k]
    else:
        out[:k] = M[-k:]
    return out


def r(x, k=5):
    if isinstance(x, dict):
        return {kk: r(v, k) for kk, v in x.items()}
    if isinstance(x, np.ndarray):
        return r(x.tolist(), k)
    if isinstance(x, (list, tuple)):
        return [r(v, k) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), k)
    return x


# ------------------------------------------------------------------ contraste de una variante (sin bootstrap)
def variante(Z: np.ndarray, Y: np.ndarray, filas: np.ndarray, limpio: np.ndarray, año: bool, ah: bool = True) -> dict:
    Zu = relativo(Z, limpio) if año else Z
    d = V.Diseno(filas, 1, año, AÑOS, limpio)
    out = {"mco": V.resumen(d.ols(Zu, Y))}
    if ah:
        a = d.ah(Zu, Y)
        out["amihud_hurvich_b"] = float(a["b"][0])
    return out


def confirmatoria(nom: str, M: dict, año: bool, rng: np.random.Generator, B: int, extra: dict | None = None) -> dict:
    X, Y, H = M["X"], M["Y"], M["H"]
    limpio = np.isfinite(X) & ~H
    f1 = filas_h(X, Y, H)
    Z, mu, sd = estandarizar(X, f1)
    Zu = relativo(Z, limpio) if año else Z
    d = V.Diseno(f1, 1, año, AÑOS, limpio)
    ols = d.ols(Zu, Y)
    ah = d.ah(Zu, Y)
    t0, b_ah = float(ols["t"][0]), float(ah["b"][0])
    res: dict = {"filas": int(f1.sum()), "años_rango": [int(AÑOS[d.ti].min()), int(AÑOS[d.ti].max())],
                 "paises": int(len(np.unique(d.tj))), "log_dp_media": mu, "log_dp_dt": sd,
                 "mco": V.resumen(ols), "amihud_hurvich": {"b": b_ah, "gamma_v": float(ah["b"][1]),
                                                           "filas": ah["filas_ah"],
                                                           "phi_c_media": float(np.nanmean(ah["ar1"]["phi_c"])),
                                                           "phi_mco_media": float(np.nanmean(ah["ar1"]["phi"]))}}
    if año:
        res["dt_relativa_sobre_total"] = float(np.nanstd(Zu[f1], ddof=1))
    # p principal: bootstrap nulo (§3.2); con V1 se usa el mismo generador para V3 (informativa, 5 años, DK 5 retardos)
    t_ini = time.time()
    par0 = V.residuos_pares(d, Zu, Y)
    dis = {nom: d}
    if extra:
        dis.update(extra["diseños"](Zu, Y, H, limpio))
    tb = V.bootstrap(par0, dis, B, rng)
    res["bootstrap_nulo"] = {"p": V.p_bootstrap(t0, tb[nom]), "replicas": B, "t_obs": t0,
                             "t_nula_media": float(np.mean(tb[nom])), "t_nula_dt": float(np.std(tb[nom])),
                             "t_nula_p2.5_p97.5": [float(np.quantile(tb[nom], 0.025)),
                                                   float(np.quantile(tb[nom], 0.975))],
                             "segundos": round(time.time() - t_ini, 1)}
    # IC del efecto corregido: bootstrap con b̂ (Amihud-Hurvich) impuesta, percentiles 2,5-97,5 de b̂_AH*
    par1 = V.residuos_pares(d, Zu, Y, b=b_ah)
    bb = V.bootstrap(par1, {nom: d}, B, rng, b=b_ah, que="ah")[nom]
    res["amihud_hurvich"]["ic95_bootstrap"] = [float(np.quantile(bb, 0.025)), float(np.quantile(bb, 0.975))]
    res["amihud_hurvich"]["media_bootstrap"] = float(np.mean(bb))
    # criterio 3: placebo desplazado
    pl = V.placebo(d, Zu, Y)
    res["placebo"] = {"desplazamientos": pl["desplazamientos"], "p95_abs_t": pl["p95_abs_t"],
                      "supera_p95": bool(abs(t0) > pl["p95_abs_t"])}
    # criterio 4: dos mitades (año del indicador t ≤ 1949 / ≥ 1950), v̂ del AR(1) de toda la muestra
    mit = {}
    for lab, m in (("1871_1949", AÑOS <= 1949), ("1950_2004", AÑOS >= 1950)):
        fm = f1 & m[:, None]
        dm = V.Diseno(fm, 1, año, AÑOS, limpio)
        mit[lab] = {"mco": float(dm.ols(Zu, Y)["b"][0]), "amihud_hurvich": float(dm.ah(Zu, Y)["b"][0]),
                    "filas": int(fm.sum())}
    res["mitades"] = mit
    # criterio 5: por país
    pu = V.por_unidad(d, Zu, Y, M["paises"])
    res["por_pais"] = pu
    if extra:
        res["_tb_extra"] = {k: v for k, v in tb.items() if k != nom}
    res["_Z"] = (Z, Zu, f1, limpio)
    return res


def criterios(res: dict, holm_ok: bool) -> dict:
    sin, dl = res["por_pais"]["sin_encoger"].values(), res["por_pais"]["dl_sin_año"].values()
    f_sin = float(np.mean([v > 0 for v in sin])) if sin else 0.0
    f_dl = float(np.mean([v > 0 for v in dl])) if dl else 0.0
    c = {"1_signo_mas_mco_y_corregida": bool(res["mco"]["b"] > 0 and res["amihud_hurvich"]["b"] > 0),
         "2_holm2_bootstrap_nulo": bool(holm_ok),
         "3_supera_p95_placebo": bool(res["placebo"]["supera_p95"]),
         "4_signo_mas_en_las_dos_mitades": bool(all(v["amihud_hurvich"] > 0 for v in res["mitades"].values())),
         "5a_paises_sin_encoger_2_3": bool(f_sin >= 2 / 3 - 1e-12),
         "5b_paises_dl_sin_año_2_3": bool(f_dl >= 2 / 3 - 1e-12)}
    c["ESTABLECIDO"] = all(c.values())
    c["fraccion_sin_encoger"], c["fraccion_dl"] = f_sin, f_dl
    return c


def sensibilidades(M: dict, Mext: dict, año: bool) -> dict:
    X, Y, H = M["X"], M["Y"], M["H"]
    limpio = np.isfinite(X) & ~H
    f1 = filas_h(X, Y, H)
    Z, _, _ = estandarizar(X, f1)
    s: dict = {}
    guerra = np.isin(AÑOS, list(GUERRA))
    sg = f1 & ~guerra[:, None] & ~np.r_[guerra[1:], False][:, None]
    s["sin_guerras"] = variante(Z, Y, sg, limpio, año)
    fe_ = filas_h(X, Y, H, rez_x=1)                                     # x_{t−1} → y_{t+1}
    s["estricta_x_t_menos_1"] = variante_desplazada(Z, Y, fe_, limpio, año, 1)
    Zn, _, _ = estandarizar(M["dp"], f1)
    s["dp_en_niveles"] = variante(Zn, Y, f1, limpio, año)
    fx = f1 & filas_h(X, M["Yex"], H)
    s["exceso_sobre_letras"] = variante(Z, M["Yex"], fx, limpio, año)
    lo, hi = np.quantile(X[f1], [0.01, 0.99])
    Zw, _, _ = estandarizar(np.clip(X, lo, hi), f1)
    s["winsor_1_99"] = variante(Zw, Y, f1, limpio, año)
    fnh = filas_h(X, Y, None)
    Znh, _, _ = estandarizar(X, fnh)
    s["sin_regla_hiperinflacion"] = variante(Znh, Y, fnh, np.isfinite(X), año)
    Xe, Ye, He = Mext["X"], Mext["Y"], Mext["H"]
    fe2 = filas_h(Xe, Ye, He)
    Ze, _, _ = estandarizar(Xe, fe2)
    le = np.isfinite(Xe) & ~He
    s["con_AUS_CHE"] = variante(Ze, Ye, fe2, le, año)
    Zeu = relativo(Ze, le) if año else Ze
    pr = {}
    for c in PRUEBA:
        j = Mext["paises"].index(c)
        m = fe2[:, j]
        t = np.nonzero(m)[0]
        z, y = Zeu[t, j], Ye[t + 1, j]
        pr[c] = {"pendiente_mco": float(np.cov(z, y)[0, 1] / np.var(z, ddof=1)), "filas": int(m.sum())}
    s["paises_prueba"] = pr
    Zc = np.where(limpio, relativo(Z, limpio) if año else Z, np.nan)
    s["hodrick_1b_en_lugar_de_dk"] = V.hodrick_1b(Zc, Y, f1, 1, AÑOS, año)
    H2 = np.zeros(H.shape, bool)                                        # x_t → y_{t+2}; sin hiperinflación en t … t+2
    H2[:-2] = H[2:]
    f2 = filas_h(X, desplazar(Y, -1), H) & ~H2
    s["t_mas_2"] = variante(Z, desplazar(Y, -1), f2, limpio, año, ah=False)
    return s


def variante_desplazada(Z, Y, filas, limpio, año, k):
    """x_{t−k} como regresora de la fila t (sin Amihud-Hurvich: la innovación no es la del año del resultado)."""
    Zu = relativo(Z, limpio) if año else Z
    d = V.Diseno(filas, 1, año, AÑOS, limpio)
    return {"mco": V.resumen(d.ols(desplazar(Zu, k), Y))}


# ------------------------------------------------------------------ EE. UU. (V4 anual, V6 mensual)
def anual_shiller(sh: dict) -> dict:
    rp, re, cape, ret = sh["real_price"], sh["real_earnings"], sh["cape"], sh["real_stock_tr_ret_m"]
    asof, dic = {}, {}
    for y in range(1871, 2005):
        p = rp.get(pd.Timestamp(f"{y}-12-01"))
        e = re[(re.index >= pd.Timestamp(f"{y - 10}-07-01")) & (re.index <= pd.Timestamp(f"{y}-06-01"))]
        if p is not None and len(e) == 120 and e.notna().all():
            asof[y] = np.log(p / e.mean())
        cv = cape.get(pd.Timestamp(f"{y}-12-01"))
        if cv is not None and np.isfinite(cv):
            dic[y] = np.log(cv)
    lr = np.log1p(ret)
    g = lr.groupby(lr.index.year).agg(["sum", "count"])
    yr = g.loc[g["count"] == 12, "sum"]
    return {"cape_asof": pd.Series(asof), "cape_shiller_dic": pd.Series(dic), "y": yr}


def serie_us(nom: str, x: pd.Series, y: pd.Series, signo: int, rng, B: int) -> dict:
    Xm, Ym = mat(x, ["USA"]), mat(y, ["USA"])
    limpio = np.isfinite(Xm)
    out = {"indicador": nom, "signo_esperado": signo}
    f1 = filas_h(Xm, Ym, None, 1)
    f10 = filas_h(Xm, Ym, None, 10)
    Z, _, sd = estandarizar(Xm, f1)
    d1 = V.Diseno(f1, 1, False, AÑOS, limpio, corr="nw")
    d10 = V.Diseno(f10, 10, False, AÑOS, limpio, L=10, corr="nw")
    par = V.residuos_pares(d1, Z, Ym)
    tb = V.bootstrap(par, {"h1": d1, "h10": d10}, B, rng)
    for h, d in (("h1", d1), ("h10", d10)):
        o = d.ols(Z, Ym)
        rr = V.resumen(o)
        rr["años_indicador"] = [int(AÑOS[d.ti].min()), int(AÑOS[d.ti].max())]
        rr["p_bootstrap_nulo"] = V.p_bootstrap(float(o["t"][0]), tb[h])
        rr["hodrick_1b"] = V.hodrick_1b(np.where(limpio, Z, np.nan), Ym, f1, int(h[1:]), AÑOS, False, corr="nw")
        if h == "h1":
            rr["amihud_hurvich_b"] = float(d.ah(Z, Ym)["b"][0])
        else:
            rr["observaciones_no_solapadas"] = int(f10.sum() // 10)
            rr["b_por_año_simple"] = rr["b"] / 10
        out[h] = rr
    out["dt_log_indicador"] = sd
    return out


def mensual_us(sh: dict, rng, B: int) -> dict:
    idx = pd.date_range("1881-01-01", "2004-12-01", freq="MS")
    meses = np.arange(len(idx))
    y = np.log1p(sh["real_stock_tr_ret_m"].reindex(idx)).to_numpy()[:, None]
    ind = {"log_cape": np.log(sh["cape"].reindex(idx)).to_numpy()[:, None],
           "log_dp": np.log((sh["real_dividend"] / sh["real_price"]).reindex(idx)).to_numpy()[:, None]}
    out = {"meses": [str(idx[0].date()), str(idx[-1].date())]}
    for nom, Xm in ind.items():
        limpio = np.isfinite(Xm)
        fh = {h: filas_h(Xm, y, None, h) for h in (1, 3, 6)}
        Z, _, sd = estandarizar(Xm, fh[1])
        d1 = V.Diseno(fh[1], 1, False, meses, limpio, corr="nw")
        ds = {h: V.Diseno(fh[h], h, False, meses, limpio, L=h, corr="nw") for h in (3, 6)}
        par = V.residuos_pares(d1, Z, y)
        tb = V.bootstrap(par, {f"h{h}": d for h, d in ds.items()}, B, rng, bloque=60)
        o = {"dt_log": sd}
        for h, d in ds.items():
            rr = V.resumen(d.ols(Z, y))
            rr["p_bootstrap_nulo"] = V.p_bootstrap(rr["t"], tb[f"h{h}"])
            rr["b_por_año"] = rr["b"] * 12 / h
            rr["r2"] = rr["r2_dentro"]
            o[f"h{h}_meses"] = rr
        out[nom] = o
    return out


# ------------------------------------------------------------------ principal
def main() -> None:
    sint = "--sintetico" in sys.argv
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    proc = procedencia(exigir_limpio=not sint)
    rng = np.random.default_rng(SEED)
    nb = 19 if sint else B
    dat = cargar_sintetico(np.random.default_rng(1)) if sint else cargar_real()
    a = dat["anual"]
    if a.index.get_level_values(1).max() > 2004 or any(s.index.max() > D.DEV_END for s in dat["shiller"].values()):
        raise D.FactorCutoffError("dato posterior a 2004")
    M = construir(a, dat["capgain"], NUCLEO)
    Mext = construir(a, dat["capgain"], NUCLEO + PRUEBA)
    res: dict = {"procedencia": proc, "prerregistro": PRERREG, "replicas_bootstrap": nb, "semilla": SEED,
                 "sintetico": sint,
                 "unidades": "b = log-rentabilidad real (fracción; ×100 = pp) por 1 dt del indicador (log D/P o log CAPE)"}

    # V3 se calcula con las mismas réplicas nulas que V1 (mismo generador; su propio diseño)
    def dis_v3(Zu, Y, H, limpio):
        f5 = filas_h(M["X"], Y, H, h=5)
        return {"V3": V.Diseno(f5, 5, False, AÑOS, limpio, L=5)}

    t0 = time.time()
    v1 = confirmatoria("V1", M, False, rng, nb, extra={"diseños": dis_v3})
    v2 = confirmatoria("V2", M, True, rng, nb)
    holm = I.holm({"V1": v1["bootstrap_nulo"]["p"], "V2": v2["bootstrap_nulo"]["p"]})
    conf = {}
    for q, v in (("V1", v1), ("V2", v2)):
        v["holm2_ok"] = bool(holm[q])
        v["criterios"] = criterios(v, holm[q])
        conf[q] = v
    # V3 (informativa)
    Z1, _, f1, limpio = v1["_Z"]
    f5 = filas_h(M["X"], M["Y"], M["H"], h=5)
    d5 = V.Diseno(f5, 5, False, AÑOS, limpio, L=5)
    o5 = V.resumen(d5.ols(Z1, M["Y"]))
    phi_bar = v1["amihud_hurvich"]["phi_mco_media"]
    o5["p_bootstrap_nulo"] = V.p_bootstrap(o5["t"], v1["_tb_extra"]["V3"])
    o5["hodrick_1b"] = V.hodrick_1b(np.where(limpio, Z1, np.nan), M["Y"], f1, 5, AÑOS, False)
    o5["b_unidades_1_año (×(1−φ)/(1−φ^5), φ = AR(1) MCO medio)"] = o5["b"] * (1 - phi_bar) / (1 - phi_bar ** 5)
    o5["b_por_año_simple"] = o5["b"] / 5
    o5["mde_prerregistro"] = "3,4-3,5 pp por dt en unidades de 1 año (≈ 11-12 pp acumulados), Holm-2"
    res["V3_informativa"] = o5
    res["confirmatorias"] = {q: {k: v for k, v in c.items() if not k.startswith("_")} for q, c in conf.items()}
    res["sensibilidades"] = {"V1": sensibilidades(M, Mext, False), "V2": sensibilidades(M, Mext, True)}

    # §4.3 la otra mitad de la identidad: D/P → crecimiento real del dividendo
    fg = filas_h(M["X"], M["G"], M["H"])
    Zg, _, _ = estandarizar(M["X"], fg)
    res["dividendo_4_3"] = variante(Zg, M["G"], fg, limpio, False)
    # §4.4 fuera de muestra
    res["fuera_de_muestra_4_4"] = {"V1": V.oos(Z1, M["Y"], f1, AÑOS, 1950, False),
                                   "V2": V.oos(Z1, M["Y"], f1, AÑOS, 1950, True)}
    # §4.5 V5 × estanflación (etiquetas de INT-1, ≤ 1999, no truncadas; estado en t)
    et = dat["regimen"]
    et = et[et.pais.isin(NUCLEO) & et.cuadrante.notna() & ~et.truncada.fillna(True).astype(bool) & (et.año <= 1999)]
    S = mat(pd.Series((et.cuadrante == "estanflacion").astype(float).values,
                      index=pd.MultiIndex.from_arrays([et.pais.values, et.año.astype(int).values])), NUCLEO)
    v5 = V.interaccion(V.Diseno(f1, 1, False, AÑOS, limpio), Z1, M["Y"], S)
    v5["mde_pp_por_dt_diferencia"] = MDE_V5
    v5["frase_obligatoria"] = FRASE_V5
    res["V5_descriptiva"] = v5
    # V4 (descriptiva): CAPE de EE. UU.
    us = anual_shiller(dat["shiller"])
    dpu = pd.Series(M["X"][:, NUCLEO.index("USA")], index=AÑOS).dropna()
    res["V4_descriptiva"] = {
        "cape_asof (principal)": serie_us("log CAPE as of dic. (beneficios hasta junio)", us["cape_asof"], us["y"], -1,
                                          rng, nb),
        "cape_shiller (sensibilidad)": serie_us("log shiller_cape de diciembre", us["cape_shiller_dic"], us["y"], -1,
                                                rng, nb),
        "dp_jst_usa (puente con V1)": serie_us("log D/P JST de EE. UU.", dpu, us["y"], +1, rng, nb)}
    # V6 (informativa): EE. UU. mensual, 3 y 6 meses
    v6 = mensual_us(dat["shiller"], rng, nb)
    v6["frase_obligatoria"] = FRASE_V6
    res["V6_informativa"] = v6
    res["segundos"] = round(time.time() - t0, 1)
    res = r(res)

    lin = informe(res)
    if sint:
        print("\n".join(lin))
        print("[sintético: no se escribe nada]")
        return
    (REPO / "research" / "int" / "int7_resultado.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    (REPO / "research" / "int" / "int7_resultado.md").write_text("\n".join(lin) + "\n")
    ver = {q: c["criterios"]["ESTABLECIDO"] for q, c in res["confirmatorias"].items()}
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(f"| {proc['hora_utc']} | Constructor (P-DEV-INT7 v1.0, corrida única) | {proc['commit'][:7]} | "
                 f"V1-V2 Holm-2 sobre p del bootstrap nulo que conserva δ; establecidos {json.dumps(ver)} | "
                 f"research/int/int7_resultado.json |\n")
    print("\n".join(lin))


def informe(res: dict) -> list[str]:
    """Resumen automático (tabla); la lectura en español claro se añade a mano en el .md tras la corrida."""
    pp = lambda v: "—" if v is None else f"{100 * v:+.2f}"  # noqa: E731
    p = res["procedencia"]
    lin = ["# INT-7: resultado de la corrida única (tablas automáticas)", "",
           f"Procedencia: commit `{p['commit'][:7]}`, árbol limpio {p['arbol_limpio']}, {p['hora_utc']}. "
           f"Prerregistro {res['prerregistro']}. Réplicas del bootstrap: {res['replicas_bootstrap']}. Unidades: pp de "
           "rentabilidad real (log) por 1 dt del indicador.", "",
           "## Confirmatorias (Holm-2 sobre el p del bootstrap nulo)", "",
           "| id | MCO | Amihud-Hurvich (efecto leído) | IC 95 % (bootstrap) | t DK | p bootstrap nulo | Holm-2 | "
           "> p95 placebo | ≤1949 / ≥1950 (AH) | países sin encoger / DL | ESTABLECIDO |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for q, c in res["confirmatorias"].items():
        k = c["criterios"]
        ic = c["amihud_hurvich"]["ic95_bootstrap"]
        lin.append(f"| {q} | {pp(c['mco']['b'])} | {pp(c['amihud_hurvich']['b'])} | [{pp(ic[0])}; {pp(ic[1])}] | "
                   f"{c['mco']['t']:.2f} | {c['bootstrap_nulo']['p']:.4f} | {'sí' if c['holm2_ok'] else 'no'} | "
                   f"{'sí' if k['3_supera_p95_placebo'] else 'no'} | {pp(c['mitades']['1871_1949']['amihud_hurvich'])}"
                   f" / {pp(c['mitades']['1950_2004']['amihud_hurvich'])} | {k['fraccion_sin_encoger']:.2f} / "
                   f"{k['fraccion_dl']:.2f} | **{'sí' if k['ESTABLECIDO'] else 'no'}** |")
    v3 = res["V3_informativa"]
    lin += ["", "## Informativas y descriptivas (sin Holm, sin veredicto)", "",
            f"- V3 (5 años): b acumulado {pp(v3['b'])}, t DK(5) {v3['t']:.2f}, p bootstrap nulo "
            f"{v3['p_bootstrap_nulo']:.4f}, Hodrick 1B t {v3['hodrick_1b']['t']:.2f}."]
    for k, v in res["V4_descriptiva"].items():
        lin.append(f"- V4 {k}: 1 año b {pp(v['h1']['b'])} (AH {pp(v['h1']['amihud_hurvich_b'])}), t NW "
                   f"{v['h1']['t']:.2f}, p bootstrap {v['h1']['p_bootstrap_nulo']:.4f}, R² {v['h1']['r2_dentro']:.3f}; "
                   f"10 años b {pp(v['h10']['b'])}, t NW {v['h10']['t']:.2f}, p bootstrap "
                   f"{v['h10']['p_bootstrap_nulo']:.4f}, Hodrick 1B t {v['h10']['hodrick_1b']['t']:.2f}.")
    for k in ("V1", "V2"):
        o = res["fuera_de_muestra_4_4"][k]
        lin.append(f"- Fuera de muestra {k} (1950-2004): R² {100 * o['r2_oos']:+.2f} %, Clark-West t "
                   f"{o['clark_west_t']:.2f} (p unilateral {o['clark_west_p_unilateral']:.3f}).")
    d = res["dividendo_4_3"]
    lin.append(f"- §4.3 D/P → crecimiento real del dividendo: MCO {pp(d['mco']['b'])}, t DK {d['mco']['t']:.2f}; AH "
               f"{pp(d['amihud_hurvich_b'])}.")
    v5 = res["V5_descriptiva"]
    lin.append(f"- V5: pendiente en estanflación {pp(v5['pendiente_estanflacion']['b'])}, resto "
               f"{pp(v5['pendiente_resto']['b'])}, diferencia {pp(v5['diferencia']['b'])} "
               f"[{pp(v5['diferencia']['ic95'][0])}; {pp(v5['diferencia']['ic95'][1])}]; "
               f"{v5['filas_estanflacion']} filas en estanflación. {v5["frase_obligatoria"][0].upper() + v5["frase_obligatoria"][1:]}.")
    v6 = res["V6_informativa"]
    for k in ("log_cape", "log_dp"):
        for h in ("h3_meses", "h6_meses"):
            o = v6[k][h]
            lin.append(f"- V6 {k} {h}: b {pp(o['b'])} (por año {pp(o['b_por_año'])}), R² {o['r2']:.4f}, t NW "
                       f"{o['t']:.2f}, p bootstrap {o['p_bootstrap_nulo']:.4f}.")
    lin.append(f"- V6: {v6["frase_obligatoria"][0].upper() + v6["frase_obligatoria"][1:]}.")
    return lin


if __name__ == "__main__":
    main()
