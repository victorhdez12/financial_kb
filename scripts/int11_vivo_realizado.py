"""INT-11 v3.1, registro en vivo: medir las fuentes del REALIZADO de bonos, letras, vivienda y oro, y fijar el semáforo
de cobertura con su potencia (docs/int/INT11_vivo_realizado_v0.md).

A) Histórico ≤ 2004 (permitido para comparar FUENTES, nunca contra resultados del motor): rentabilidad NOMINAL anual
   (año natural) en moneda local de cada candidata frente a la variable JST con la que aprendió el motor (`bond_tr`,
   `bill_rate`, `housing_capgain` / `housing_tr`, y el oro del motor = oro USD × `xrusd`). JST con `load_dev` (≤ 2004).
B) Entre fuentes vivas ≥ 2005 (sin JST ≥ 2005 ni resultados del motor).
C) Disponibilidad (último dato) por serie y país.
D) Error de medida → pérdida de cobertura esperada del p5-p95.
E) Semáforo: bandas de la cobertura de las emisiones de diciembre bajo H0 (abanico calibrado) por nº de años, con los
   choques comunes del año (medidos ≤ 2004 en research/int/int11_potencia.json), efecto de diseño y potencia frente a
   una cobertura real del 80 % (y del 85 %).

Uso: .venv/bin/python -m scripts.int11_vivo_realizado [--refrescar] [--nsim N]  → research/int/int11_vivo_realizado.json
"""
from __future__ import annotations

import json
import sys
import urllib.request
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.int11_fuente_bolsa import _anual_jst, _comp_m, _movil, fx_diarias
from src.intl import data as D
from src.intl.activos3b import tr_desde_rendimiento
from src.intl.returns import bono_tr_mensual
from src.report import activos_vivo as V
from src.report import bolsa_vivo as B
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_vivo_realizado.json"
SEMAFORO = REPO / "research/int/int11_vivo_semaforo.json"     # tabla congelada que lee scripts/eval_int11_vivo.py
POTENCIA = REPO / "research/int/int11_potencia.json"
CACHE_HP = db.DATA_ROOT / "raw" / "int11_oecd_vivienda"
URL_HP = ("https://sdmx.oecd.org/public/rest/data/OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0/all?"
          "dimensionAtObservation=AllDimensions&format=csvfilewithlabels")
SEMILLA = 20261105
ACT5 = ("bolsa", "bonos", "letras", "vivienda", "oro")


# ---------------------------------------------------------------- utilidades
def oecd_vivienda(refrescar: bool = False) -> dict[str, dict[str, pd.Series]]:
    """{"HPI"|"RPI": {país: serie trimestral}} de OECD Analytical house prices (CC BY 4.0), con caché local."""
    CACHE_HP.mkdir(parents=True, exist_ok=True)
    f = CACHE_HP / "house_prices.csv"
    if refrescar or not f.exists():
        with urllib.request.urlopen(URL_HP, timeout=300) as r:  # noqa: S310 (URL fija de la OCDE)
            f.write_bytes(r.read())
    d = pd.read_csv(f, usecols=["REF_AREA", "FREQ", "MEASURE", "TIME_PERIOD", "OBS_VALUE"])
    d = d[(d.FREQ == "Q") & d.MEASURE.isin(["HPI", "RPI"]) & d.REF_AREA.isin(B.NUCLEO)]
    out: dict = {"HPI": {}, "RPI": {}}
    for (m, c), g in d.groupby(["MEASURE", "REF_AREA"]):
        idx = pd.PeriodIndex(g.TIME_PERIOD.str.replace("-Q", "Q"), freq="Q").to_timestamp(how="start")
        out[m][c] = pd.Series(g.OBS_VALUE.astype(float).values, index=idx, name=f"oecd_{m.lower()}_{c.lower()}_q"
                              ).sort_index()
    return out


def _mensual_completa(s: pd.Series) -> pd.Series:
    s = B._mes(s)
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="MS")) if len(s) else s


def anual_bono(y_pct: pd.Series) -> pd.Series:
    """Rentabilidad de cada año natural del bono a 10 años (encadenando bono_tr_mensual)."""
    y = _mensual_completa(y_pct)
    return B.anual(bono_tr_mensual(y).dropna()) if len(y) else pd.Series(dtype=float)


def anual_media(y_pct: pd.Series) -> pd.Series:
    """Media de los 12 meses de cada año natural / 100 (letras "media")."""
    y = B._mes(y_pct)
    g = y.groupby(y.index.year)
    return (g.mean() / 100)[g.count() == 12]


def anual_encadenada(y_pct: pd.Series) -> pd.Series:
    y = _mensual_completa(y_pct)
    return B.anual((y.shift(1) / 1200).dropna())


def anual_q(precio_q: pd.Series, modo: str) -> pd.Series:
    """Cambio anual de un índice trimestral: "q4" = T4/T4; "media" = media del año / media del anterior."""
    p = V._q(precio_q)
    if modo == "q4":
        x = p[p.index.month == 10]
        x.index = x.index.year
    else:
        g = p.groupby(p.index.year)
        x = g.mean()[g.count() == 4]
    return (x / x.shift(1) - 1)[x.index.to_series().diff() == 1]


def vivienda_total_anual(precio_q, alquiler_q, yd_ancla, año_ancla, hasta=2004, modo="media") -> dict[str, pd.Series]:
    """Vivienda total por años naturales (año_ancla + 1 … hasta) con el método del registro (rent_yd encadenado desde el
    ancla), con rent_yd fijo en el ancla y solo precio."""
    out = {"indice_alquiler": {}, "alquiler_fijo": {}, "solo_precio": {}, "rent_yd_encadenado": {}}
    for a in range(año_ancla + 1, hasta + 1):
        d, h = f"{a}-01-01", f"{a}-12-31"
        r1 = V.rent_vivienda_ventana(precio_q, d, h, yd_ancla=yd_ancla, año_ancla=año_ancla, alquiler_q=alquiler_q,
                                     modo=modo)
        r2 = V.rent_vivienda_ventana(precio_q, d, h, yd_ancla=yd_ancla, año_ancla=año_ancla, modo=modo)
        r3 = V.rent_vivienda_ventana(precio_q, d, h, modo=modo)
        if r1["completo"] and r1["metodo"] == "indice_alquiler":
            out["indice_alquiler"][a] = r1["nominal"]
            out["rent_yd_encadenado"][a] = r1["rent_yd"]
        if r2["completo"]:
            out["alquiler_fijo"][a] = r2["nominal"]
            out["solo_precio"][a] = r3["nominal"]
    return {k: pd.Series(v, dtype=float) for k, v in out.items()}


def oro_local_anual(oro_usd_m: pd.Series, xr_fin_año: pd.Series | None) -> pd.Series:
    """Oro en moneda local por años naturales: media de diciembre en USD × FX de fin de año (índice = año)."""
    g = B._mes(oro_usd_m)
    dic = g[g.index.month == 12]
    dic.index = dic.index.year
    loc = dic if xr_fin_año is None else (dic * xr_fin_año).dropna()
    return (loc / loc.shift(1) - 1)[loc.index.to_series().diff() == 1].dropna()


def fx_fin_año(fx_lpu_m: pd.Series | None) -> pd.Series | None:
    if fx_lpu_m is None:
        return None
    x = B._mes(fx_lpu_m)
    d = x[x.index.month == 12]
    d.index = d.index.year
    return d


def _lim(s: pd.Series, desde=None, hasta=None) -> pd.Series:
    s = s.dropna()
    if desde is not None:
        s = s[s.index >= desde]
    if hasta is not None:
        s = s[s.index <= hasta]
    return s


# ---------------------------------------------------------------- A) histórico ≤ 2004
def historico(con, fx: dict, hp: dict) -> dict:
    out = {}
    oro_wb = D.load_dev(con, "gold_wb_usd_m")
    for c in B.NUCLEO:
        lc, i2 = c.lower(), V.ISO2[c]
        res = {}
        # bonos
        jb = _anual_jst(con, c, "bond_tr")
        irlt = D.load_dev(con, f"oecd_irlt_{lc}")
        res["bonos.irlt_encadenado"] = B.comparar(anual_bono(irlt), jb)
        ym = irlt.groupby(irlt.index.year).mean()
        res["bonos.irlt_media_anual_formula"] = B.comparar(tr_desde_rendimiento(ym, n=10), jb)
        if c == "USA":
            res["bonos.gs10_encadenado"] = B.comparar(anual_bono(D.load_dev(con, "GS10")), jb)
            dgs = B.fin_de_mes(B.leer_obs(con, "DGS10", hasta="2004-12-31"))
            res["bonos.dgs10_fin_de_mes_encadenado"] = B.comparar(anual_bono(dgs), jb)
            dm = D.load_dev(con, "damodaran_tbond_10y_tr")
            res["bonos.damodaran_tbond"] = B.comparar(pd.Series(dm.values, index=dm.index.year), jb)
        # letras
        jl = _anual_jst(con, c, "bill_rate")
        ir3 = D.load_dev(con, f"oecd_ir3m_{lc}")
        res["letras.ir3m_media"] = B.comparar(anual_media(ir3), jl)
        res["letras.ir3m_encadenada"] = B.comparar(anual_encadenada(ir3), jl)
        call = D.load_dev(con, f"oecd_ircall_{lc}")
        res["letras.ircall_media"] = B.comparar(anual_media(call), jl)
        if c == "USA":
            res["letras.tb3ms_media"] = B.comparar(anual_media(D.load_dev(con, "TB3MS")), jl)
        if c == "GBR":
            res["letras.boe_tbill3m_media"] = B.comparar(anual_media(B.leer_obs(con, "boe_tbill3m_m", hasta="2004-12-31")), jl)
        # vivienda: plusvalía
        jcap = _anual_jst(con, c, "housing_capgain")
        jtr = _anual_jst(con, c, "housing_tr")
        bis = B.leer_obs(con, f"bis_spp_{i2}_n", hasta="2004-12-31")
        hpi = _lim(hp["HPI"].get(c, pd.Series(dtype=float)), hasta="2004-12-31")
        rpi = _lim(hp["RPI"].get(c, pd.Series(dtype=float)), hasta="2004-12-31")
        for nom, s in (("bis", bis), ("ocde_hpi", hpi)):
            if len(s):
                for modo in ("q4", "media"):
                    res[f"vivienda.plusvalia_{nom}_{modo}"] = B.comparar(anual_q(s, modo), jcap)
                    res[f"vivienda.plusvalia_{nom}_{modo}_desde_1986"] = B.comparar(_lim(anual_q(s, modo), 1986), jcap)
        # vivienda: total con el alquiler encadenado desde un ancla ≈ 20 años antes (como en vivo: 2004 → ≈ 2027)
        yd = _anual_jst(con, c, "housing_rent_yd")
        if len(bis) and len(rpi):
            ini = max(1984, V._q(bis).index.min().year + 1, V._q(rpi).index.min().year + 1)
            if ini in yd.index and np.isfinite(yd[ini]):
                tot = vivienda_total_anual(bis, rpi, float(yd[ini]), ini)
                tq4 = vivienda_total_anual(bis, rpi, float(yd[ini]), ini, modo="q4")
                res["vivienda.ancla"] = {"año": int(ini), "rent_yd_jst": round(float(yd[ini]), 4)}
                for k in ("indice_alquiler", "alquiler_fijo", "solo_precio"):
                    res[f"vivienda.total_{k}"] = B.comparar(tot[k], jtr)
                    res[f"vivienda.total_{k}_q4"] = B.comparar(tq4[k], jtr)
                ry = tot["rent_yd_encadenado"]
                res["vivienda.rent_yd_encadenado_vs_jst"] = B.comparar(ry, yd)
                if 2004 in ry.index:
                    res["vivienda.rent_yd_2004"] = {"encadenado": round(float(ry[2004]), 4),
                                                    "jst": round(float(yd[2004]), 4),
                                                    "fijo_en_ancla": round(float(yd[ini]), 4)}
        # oro: construcción del motor (FX JST de fin de año) frente a la viva (FX FRED de fin de mes)
        xr_jst = None if c == "USA" else _anual_jst(con, c, "xrusd")
        motor = oro_local_anual(oro_wb, xr_jst)
        x = B.fx_lpu_pais(c, fx)
        vivo = oro_local_anual(oro_wb, fx_fin_año(_lim(x, hasta="2004-12-31")) if x is not None else None)
        res["oro.wb_fx_fred_vs_motor"] = B.comparar(_lim(vivo, 1972), _lim(motor, 1972))
        if x is not None:
            fr = fx_fin_año(_lim(x, hasta="2004-12-31"))
            ch = lambda z: (z / z.shift(1) - 1)[z.index.to_series().diff() == 1]  # noqa: E731
            # cambio anual (los niveles JST del euro van en la moneda antigua: solo cuentan los cambios)
            res["oro.fx_fred_fin_dic_vs_jst_xrusd_cambio"] = B.comparar(ch(fr), ch(xr_jst))
        out[c] = res
    gd = D.load_dev(con, "damodaran_gold_ret")
    oro_us = oro_local_anual(oro_wb, None)
    out["_oro_usd"] = {"wb_dic_vs_damodaran_1961_2004": B.comparar(oro_us, pd.Series(gd.values, index=gd.index.year))}
    return out


# ---------------------------------------------------------------- B) ≥ 2005 entre fuentes vivas
def vivo(con, fx: dict, hp: dict) -> dict:
    d0 = "2003-01-01"
    out = {}
    for c in B.NUCLEO:
        lc, i2 = c.lower(), V.ISO2[c]
        res = {}
        irlt = B.leer_obs(con, f"oecd_irlt_{lc}", desde=d0)
        b_m = bono_tr_mensual(_mensual_completa(irlt)).dropna()
        b_m = b_m[b_m.index >= "2005-01-01"]
        if c == "USA":
            dgs = B.fin_de_mes(B.leer_obs(con, "DGS10", desde=d0))
            d_m = bono_tr_mensual(_mensual_completa(dgs)).dropna()
            d_m = d_m[d_m.index >= "2005-01-01"]
            res["bonos.irlt_vs_dgs10_fin_de_mes_anual"] = B.comparar(B.anual(b_m), B.anual(d_m))
            res["bonos.irlt_vs_dgs10_fin_de_mes_movil12"] = _comp_m(_movil(b_m), _movil(d_m))
            dm = B.leer_obs(con, "damodaran_tbond_10y_tr", desde="2005-01-01")
            res["bonos.irlt_vs_damodaran_anual"] = B.comparar(B.anual(b_m), pd.Series(dm.values, index=dm.index.year))
        if c == "ESP":
            bde = B.leer_obs(con, "bde_es_gov_long_yield_m", desde=d0)
            e_m = bono_tr_mensual(_mensual_completa(bde)).dropna()
            e_m = e_m[e_m.index >= "2005-01-01"]
            res["bonos.irlt_vs_bde_anual"] = B.comparar(B.anual(b_m), B.anual(e_m))
        ir3 = B.leer_obs(con, f"oecd_ir3m_{lc}", desde=d0)
        call = B.leer_obs(con, f"oecd_ircall_{lc}", desde=d0)
        res["letras.ir3m_vs_ircall_media_anual"] = B.comparar(_lim(anual_media(ir3), 2005), _lim(anual_media(call), 2005))
        if c == "GBR":
            ois = B.leer_obs(con, "boe_ois3m_m")
            res["letras.ir3m_vs_ois3m_media_anual"] = B.comparar(anual_media(ir3), anual_media(ois))
        if c == "USA":
            res["letras.ir3m_vs_tb3ms_media_anual"] = B.comparar(
                _lim(anual_media(ir3), 2005), _lim(anual_media(B.leer_obs(con, "TB3MS", desde=d0)), 2005))
        bis = B.leer_obs(con, f"bis_spp_{i2}_n", desde=d0)
        hpi = _lim(hp["HPI"].get(c, pd.Series(dtype=float)), desde=d0)
        if len(hpi):
            res["vivienda.bis_vs_ocde_hpi_q4"] = B.comparar(_lim(anual_q(bis, "q4"), 2005), _lim(anual_q(hpi, "q4"), 2005))
        if c == "USA":
            cs = B._mes(B.leer_obs(con, "CSUSHPINSA", desde=d0))
            cs_d = cs[cs.index.month == 12]
            cs_d.index = cs_d.index.year
            res["vivienda.bis_vs_case_shiller_dic"] = B.comparar(_lim(anual_q(bis, "q4"), 2005),
                                                                 _lim((cs_d / cs_d.shift(1) - 1).dropna(), 2005))
        if c == "ESP":
            res["vivienda.bis_vs_bde_m2_q4"] = B.comparar(
                _lim(anual_q(bis, "q4"), 2005), _lim(anual_q(B.leer_obs(con, "bde_es_house_price_m2_q", desde=d0), "q4"), 2005))
        rpi = _lim(hp["RPI"].get(c, pd.Series(dtype=float)), desde=d0)
        if len(rpi):
            ra = anual_q(rpi, "media")
            res["vivienda.alquiler_ocde_crec_medio_2005_"] = round(float(_lim(ra, 2005).mean()), 4)
        out[c] = res
    wb = B.leer_obs(con, "gold_wb_usd_m", desde=d0)
    dh = B.leer_obs(con, "gold_datahub_usd_m", desde=d0)
    j = pd.concat([B._mes(wb), B._mes(dh)], axis=1, join="inner").dropna()
    out["_oro_usd"] = {"wb_vs_datahub_mensual_max_abs_dif_pct": round(100 * float((j.iloc[:, 0] / j.iloc[:, 1] - 1).abs().max()), 4),
                       "n_meses": int(len(j))}
    return out


# ---------------------------------------------------------------- C) disponibilidad
def disponibilidad(con, hp: dict, hoy) -> dict:
    hoy = pd.Timestamp(hoy)

    def ult(sid):
        u = con.execute("select max(date) from obs_latest where series_id = ?", [sid]).fetchone()[0]
        return None if u is None else str(pd.Timestamp(u).date())
    out = {}
    for c in B.NUCLEO:
        lc, i2 = c.lower(), V.ISO2[c]
        out[c] = {"oecd_irlt": ult(f"oecd_irlt_{lc}"), "oecd_ir3m": ult(f"oecd_ir3m_{lc}"),
                  "bis_spp_n": ult(f"bis_spp_{i2}_n"),
                  "ocde_hpi_q (caché)": str(hp["HPI"][c].index.max().date()) if c in hp["HPI"] else None,
                  "ocde_rpi_q (caché)": str(hp["RPI"][c].index.max().date()) if c in hp["RPI"] else None,
                  "oecd_cpi": ult(f"oecd_cpi_{lc}_idx")}
    out["_comunes"] = {"gold_wb_usd_m": ult("gold_wb_usd_m"), "boe_ois3m_m": ult("boe_ois3m_m"), "hoy": str(hoy.date())}
    return out


# ---------------------------------------------------------------- D-E) error de medida y semáforo
def cobertura_con_error(sd_total: float, dt_error: float, sesgo: float = 0.0) -> float:
    """Cobertura del p5-p95 de una normal de dt `sd_total` cuando el realizado lleva un error de medida independiente
    de dt `dt_error` y media `sesgo` (aproximación normal; las mismas unidades)."""
    from scipy.stats import norm
    s = np.hypot(sd_total, dt_error)
    z = 1.6449 * sd_total
    return float(norm.cdf((z - sesgo) / s) - norm.cdf((-z - sesgo) / s))


PRINCIPAL = {"bonos": "bonos.irlt_encadenado", "letras": "letras.ir3m_media", "vivienda": "vivienda.total_indice_alquiler",
             "oro": "oro.wb_fx_fred_vs_motor"}
ALTERNATIVAS = {"vivienda (alquiler fijo)": "vivienda.total_alquiler_fijo",
                "vivienda (solo precio)": "vivienda.total_solo_precio",
                "vivienda (T4/T4 + alquiler)": "vivienda.total_indice_alquiler_q4",
                "letras (encadenada)": "letras.ir3m_encadenada"}


def efecto_medida(resumen: dict, sd_tot: dict) -> dict:
    """Cobertura esperada del p5-p95 si el error frente a JST (≤ 2004, mediana de países) se repite en vivo."""
    out = {}
    for nom, k in {**PRINCIPAL, **ALTERNATIVAS}.items():
        a = nom.split(" ")[0]
        r = resumen.get(k)
        if r:
            out[nom] = {"medida": k, "sd_total_pp": round(100 * sd_tot[a], 1), "dt_error_pp": r["dt_dif_pp"],
                        "sesgo_pp": r["sesgo_pp"],
                        "cobertura": round(cobertura_con_error(sd_tot[a], r["dt_dif_pp"] / 100, r["sesgo_pp"] / 100), 4)}
    return out


def semaforo_y_potencia(nsim: int, años_max: int = 20, trozo: int = 2000) -> dict:
    """Cobertura acumulada de las emisiones de diciembre (14 países × 5 activos por año) bajo H0 (abanico calibrado) y
    bajo abanicos que cubren el 80 % o el 85 %: bandas 2,5/10/90/97,5 por nº de años, efecto de diseño frente a la
    binomial ingenua (14·años filas independientes) y potencia del contraste bilateral al 5 %."""
    med = json.loads(POTENCIA.read_text())["medicion"]["y"]
    act = med["activos"]
    sc = np.array([act[a]["sd_comun"] for a in ACT5])
    sp = np.array([act[a]["sd_propio"] for a in ACT5])
    R = np.array(med["R"])
    nu = float(np.median([act[a]["nu"] for a in ACT5]))
    rng = np.random.default_rng(SEMILLA)
    umbral = V.umbral_marginal(sc, sp, R, nu, rng)
    esc = {"H0": np.ones(len(ACT5)), "H80": V.escala_para(0.80, sc, sp, R, nu, umbral, rng),
           "H85": V.escala_para(0.85, sc, sp, R, nu, umbral, rng)}
    claves = list(ACT5) + ["S5", "S4_sin_bolsa"]
    acum = {}
    for h, e in esc.items():
        bloques = []
        for _ in range(int(np.ceil(nsim / trozo))):
            d = V.simular_dentro(años_max, sc, sp, R, nu, trozo, rng, escala=e, umbral=umbral)
            c = d.mean(axis=2)                                               # (trozo, años, A)
            bloques.append(np.cumsum(c, axis=1) / np.arange(1, años_max + 1)[None, :, None])
        ca = np.concatenate(bloques)[:nsim]                                  # cobertura acumulada (nsim, años, A)
        acum[h] = {**{a: ca[:, :, i] for i, a in enumerate(ACT5)}, "S5": ca.mean(2), "S4_sin_bolsa": ca[:, :, 1:].mean(2)}
    res = {"entrada": {"fuente": "research/int/int11_potencia.json → medicion.y (JST ≤ 2004, log real; choque común del "
                                 "año y propio del país, t multivariante entre activos)",
                       "sd_comun": dict(zip(ACT5, sc.round(4).tolist())), "sd_propio": dict(zip(ACT5, sp.round(4).tolist())),
                       "rho_comun": dict(zip(ACT5, (sc ** 2 / (sc ** 2 + sp ** 2)).round(3).tolist())), "nu": nu,
                       "escala_realizado_H80": dict(zip(ACT5, esc["H80"].round(4).tolist())),
                       "escala_realizado_H85": dict(zip(ACT5, esc["H85"].round(4).tolist())),
                       "nsim": nsim, "semilla": SEMILLA, "paises": 14},
           "por_años": {}}
    for Y in range(1, años_max + 1):
        fila = {}
        for k in claves:
            n_act = 5 if k == "S5" else 4 if k == "S4_sin_bolsa" else 1
            h0, h80, h85 = (acum[h][k][:, Y - 1] for h in ("H0", "H80", "H85"))
            q = np.quantile(h0, [0.025, 0.10, 0.90, 0.975])
            deff = float(h0.var(ddof=1) / (0.09 / (14 * Y * n_act)))
            nb = V.banda_binomial(14 * Y * n_act)
            ne = V.banda_binomial(14 * Y * n_act / deff)
            fuera = lambda x: float(((x < q[0]) | (x > q[3])).mean())  # noqa: E731
            fila[k] = {"p2_5": round(float(q[0]), 4), "p10": round(float(q[1]), 4), "p90": round(float(q[2]), 4),
                       "p97_5": round(float(q[3]), 4), "media_H0": round(float(h0.mean()), 4),
                       "efecto_diseño": round(deff, 2), "n_eff": round(14 * Y * n_act / deff, 1),
                       "binomial_ingenua_2_5_97_5": [round(nb[0], 4), round(nb[3], 4)],
                       "tamaño_real_binomial_ingenua": round(float(((h0 < nb[0]) | (h0 > nb[3])).mean()), 3),
                       "binomial_neff_2_5_97_5": [round(ne[0], 4), round(ne[3], 4)],
                       "potencia_80": round(fuera(h80), 3), "potencia_85": round(fuera(h85), 3),
                       "verde_bajo_H80": round(float(((h80 >= q[1]) & (h80 <= q[2])).mean()), 3),
                       "media_H80": round(float(h80.mean()), 4)}
        res["por_años"][Y] = fila
    res["años_para_potencia_0_8"] = {
        k: {h: next((Y for Y in range(1, años_max + 1) if res["por_años"][Y][k][f"potencia_{h}"] >= 0.8), None)
            for h in ("80", "85")} for k in claves}
    return res


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    nsim = int(sys.argv[sys.argv.index("--nsim") + 1]) if "--nsim" in sys.argv else 20000
    con = D.connect()
    fx = fx_diarias("--refrescar" in sys.argv)
    hp = oecd_vivienda("--refrescar" in sys.argv)
    h = historico(con, fx, hp)
    v = vivo(con, fx, hp)
    disp = disponibilidad(con, hp, pd.Timestamp.today())
    fb = json.loads((REPO / "research/int/int11_fuente_bolsa.json").read_text())
    resumen = {}
    for k in sorted({k for c in B.NUCLEO for k in h[c] if isinstance(h[c][k], dict) and "corr" in h[c][k]}):
        filas = [h[c][k] for c in B.NUCLEO if k in h[c] and "corr" in h[c][k]]
        resumen[k] = {"n_paises": len(filas), **{f: round(float(np.median([r[f] for r in filas])), 3)
                                                 for f in ("corr", "sesgo_pp", "dt_dif_pp")},
                      "años_mediana": int(np.median([r["n"] for r in filas]))}
    sem = semaforo_y_potencia(nsim)
    sd_tot = {a: float(np.hypot(sem["entrada"]["sd_comun"][a], sem["entrada"]["sd_propio"][a])) for a in ACT5}
    res = {"hoy": str(pd.Timestamp.today().date()), "historico_vs_jst_hasta_2004": h, "resumen_historico": resumen,
           "vivo_entre_fuentes_desde_2005": v, "disponibilidad": disp,
           "ipc_ocde_vs_jst_hasta_2004": fb.get("ipc_ocde_vs_jst_hasta_2004"),
           "sd_total_log_real": sd_tot, "efecto_error_de_medida": efecto_medida(resumen, sd_tot), "semaforo": sem}
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    tabla = {"documento": "docs/int/INT11_vivo_realizado_v0.md §5", "entrada": sem["entrada"],
             "regla": "cobertura p5-p95 acumulada de las emisiones de DICIEMBRE; verde dentro de [p10, p90], ámbar dentro "
                      "de [p2_5, p97_5], rojo fuera (bandas bajo H0 = abanico calibrado, con el choque común del año)",
             "bandas": {Y: {k: {c: f[c] for c in ("p2_5", "p10", "p90", "p97_5", "potencia_80", "potencia_85")}
                            for k, f in fila.items()} for Y, fila in sem["por_años"].items()},
             "años_para_potencia_0_8": sem["años_para_potencia_0_8"]}
    SEMAFORO.write_text(json.dumps(tabla, ensure_ascii=False, indent=1))
    print(json.dumps(resumen, indent=1, ensure_ascii=False))
    print(json.dumps(sem["años_para_potencia_0_8"], ensure_ascii=False))


if __name__ == "__main__":
    main()
