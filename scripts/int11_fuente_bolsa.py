"""INT-11 D9: medir las fuentes candidatas de la bolsa en vivo (docs/int/INT11_fuente_bolsa_vivo.md).

A) Histórico ≤ 2004 (permitido): rentabilidad NOMINAL anual (año natural) en moneda local de cada candidata frente a JST
   `eq_tr` (la fuente con la que se estimó el motor): correlación, sesgo, dt de la diferencia. JST y el tipo de cambio
   JST (`xrusd`, fin de año) se leen con `src.intl.data.load_dev` (≤ 2004).
B) Continuidad ENTRE FUENTES VIVAS ≥ 2005 (sin JST ≥ 2005 y sin ningún resultado del motor): AQR→local (FRED H.10 de fin
   de mes) frente a JKP→local, OCDE precio (+ dividendo implícito) y, en EE. UU., French, Shiller y Damodaran; años
   naturales y ventanas móviles de 12 meses con origen mensual (como el registro).
C) Disponibilidad: último dato de cada fuente en el warehouse y retraso respecto a hoy.

Uso: .venv/bin/python -m scripts.int11_fuente_bolsa   → research/int/int11_fuente_bolsa.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.report import bolsa_vivo as B
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_fuente_bolsa.json"
CACHE_FX = db.DATA_ROOT / "raw" / "int11_fx_fred"
JKP = {"DEU", "ESP", "FRA", "GBR", "ITA", "NLD", "USA"}   # países JKP ingeridos en el warehouse
CACHE_FF = db.DATA_ROOT / "raw" / "int11_french_paises"
URL_FF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_International_Countries{}.zip"


def french_paises(refrescar: bool = False) -> dict[str, dict[str, pd.Series]]:
    """{"tr"|"precio": {país: rentabilidad mensual local en %}} desde los zip de French (caché local)."""
    import urllib.request
    import zipfile
    CACHE_FF.mkdir(parents=True, exist_ok=True)
    out = {}
    for k, suf in (("tr", ""), ("precio", "_Wout_Div")):
        f = CACHE_FF / f"F-F_International_Countries{suf}.zip"
        if refrescar or not f.exists():
            with urllib.request.urlopen(URL_FF.format(suf), timeout=120) as r:  # noqa: S310 (URL fija)
                f.write_bytes(r.read())
        with zipfile.ZipFile(f) as z:
            out[k] = {c: B.french_pais_local(z.read(f"{n}.Dat").decode("latin-1")) for c, n in B.FRENCH_PAIS.items()}
    return out


def fx_diarias(refrescar: bool = False) -> dict[str, pd.Series]:
    CACHE_FX.mkdir(parents=True, exist_ok=True)
    out = {}
    for sid in sorted({s for s, _ in B.FX_FRED.values()}):
        f = CACHE_FX / f"{sid}.csv"
        if refrescar or not f.exists():
            B.fx_fred(sid).rename("value").to_csv(f, index_label="date")
        s = pd.read_csv(f, parse_dates=["date"], index_col="date")["value"]
        out[sid] = s.rename(sid)
    return out


def _anual_usd_a_local(r_usd_anual: pd.Series, xr: pd.Series) -> pd.Series:
    """TR anual en USD → local con el tipo de cambio de FIN DE AÑO (unidades locales por USD) indexado por año."""
    rx = xr / xr.shift(1)
    rx = rx[xr.index.to_series().diff() == 1]
    j = pd.concat([r_usd_anual, rx], axis=1, join="inner").dropna()
    return (1 + j.iloc[:, 0]) * j.iloc[:, 1] - 1


def _anual_jst(con, c: str, v: str) -> pd.Series:
    s = D.load_dev(con, f"jst_{c.lower()}_{v}")
    return pd.Series(s.values, index=s.index.year, name=v)


def historico(con, ff: dict) -> dict:
    """Parte A (≤ 2004)."""
    rf = B.leer_obs(con, "aqr_rf_risk_free_rate_m", hasta="2004-12-31")
    out = {}
    for c in B.NUCLEO:
        lc = c.lower()
        jst = _anual_jst(con, c, "eq_tr")
        xr = _anual_jst(con, c, "xrusd")
        dp = _anual_jst(con, c, "eq_dp")
        res = {}
        ex = D.load_dev(con, f"aqr_mkt_{lc}_m")
        usd = B.anual(B.tr_local_desde_usd(ex, rf, None))
        loc = usd if c == "USA" else _anual_usd_a_local(usd, xr)
        res["aqr_local"] = B.comparar(loc, jst)
        if c in ff["tr"]:
            f_tr = ff["tr"][c][ff["tr"][c].index <= "2004-12-01"] / 100
            f_pr = ff["precio"][c][ff["precio"][c].index <= "2004-12-01"] / 100
            res["french_local_tr"] = B.comparar(B.anual(f_tr), jst)
            res["french_local_precio"] = B.comparar(B.anual(f_pr), jst)
        if c in JKP:
            jk = B.leer_obs(con, f"jkp_{lc}_mkt_m", hasta="2004-12-31")
            jusd = B.anual(B.tr_local_desde_usd(jk, rf, None))
            res["jkp_local"] = B.comparar(jusd if c == "USA" else _anual_usd_a_local(jusd, xr), jst)
        pr = B.anual_precio(D.load_dev(con, f"oecd_share_{lc}"))
        pr86 = pr[pr.index >= 1986]
        res["oecd_precio"] = B.comparar(pr, jst)
        res["oecd_precio_desde_1986"] = B.comparar(pr86, jst)
        j = pd.concat([pr, dp], axis=1, join="inner").dropna()
        res["oecd_precio_mas_dp_jst"] = B.comparar((1 + j.iloc[:, 0]) * (1 + j.iloc[:, 1]) - 1, jst)
        cte = float(dp[(dp.index >= 1986) & (dp.index <= 2004)].mean())
        res["oecd_precio_mas_dp_constante_86_04"] = {**B.comparar((1 + pr86) * (1 + cte) - 1, jst), "dp": round(cte, 4)}
        if c == "USA":
            ff = B.anual(B.tr_local_desde_usd(B.leer_obs(con, "ff_mkt_rf_m", hasta="2004-12-31"),
                                              B.leer_obs(con, "ff_rf_m", hasta="2004-12-31"), None))
            res["french_mkt"] = B.comparar(ff, jst)
            sh = B.leer_obs(con, "shiller_nominal_stock_tr_ret_m", hasta="2004-12-31")
            res["shiller_tr"] = B.comparar(B.anual(sh * 100 / 100), jst)
            dm = B.leer_obs(con, "damodaran_sp500_tr", hasta="2004-12-31")
            res["damodaran_tr"] = B.comparar(pd.Series(dm.values, index=dm.index.year), jst)
            res["aqr_local_1927_2004"] = B.comparar(usd, jst)
        out[c] = res
    return out


def _ipc_jst_vs_ocde(con) -> dict:
    """Deflactor: inflación de la media anual del IPC OCDE frente a la JST (≤ 2004)."""
    out = {}
    for c in B.NUCLEO:
        o = D.load_dev(con, f"oecd_cpi_{c.lower()}_idx")
        g = o.groupby(o.index.year)
        m = g.mean()[g.count() == 12]
        oi = (m / m.shift(1) - 1)[m.index.to_series().diff() == 1]
        cpi = _anual_jst(con, c, "cpi")
        out[c] = B.comparar(oi, cpi / cpi.shift(1) - 1)
    return out


def _movil(r_m: pd.Series) -> pd.Series:
    """Ventanas móviles de 12 meses (origen mensual) a partir de la mensual: índice = último mes de la ventana."""
    r = B._mes(r_m)
    r = r.reindex(pd.date_range(r.index.min(), r.index.max(), freq="MS"))
    return np.exp(np.log1p(r).rolling(12, min_periods=12).sum()) - 1


def _comp_m(a: pd.Series, b: pd.Series) -> dict:
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(j) < 12:
        return {"n": int(len(j))}
    d = j.iloc[:, 0] - j.iloc[:, 1]
    return {"n_ventanas": int(len(j)), "desde": str(j.index.min().date())[:7], "hasta": str(j.index.max().date())[:7],
            "corr": round(float(j.corr().iloc[0, 1]), 4), "sesgo_pp": round(100 * float(d.mean()), 2),
            "dt_dif_pp": round(100 * float(d.std(ddof=1)), 2),
            "p95_abs_dif_pp": round(100 * float(d.abs().quantile(0.95)), 2)}


def vivo(con, fx: dict, ff: dict) -> dict:
    """Parte B (≥ 2005; solo fuentes vivas entre sí)."""
    desde = "2004-01-01"   # el mes anterior hace falta para el primer cambio de tipo de cambio / índice
    rf = B.leer_obs(con, "aqr_rf_risk_free_rate_m", desde=desde)
    out = {}
    for c in B.NUCLEO:
        lc = c.lower()
        x = B.fx_lpu_pais(c, fx)
        aqr = B.tr_local_desde_usd(B.leer_obs(con, f"aqr_mkt_{lc}_m", desde=desde), rf, x)
        aqr = aqr[aqr.index >= "2005-01-01"]
        pr = B.leer_obs(con, f"oecd_share_{lc}", desde=desde)
        pm = B._mes(pr)
        pr_m = (pm / pm.shift(1, freq="MS") - 1).reindex(pm.index).dropna()
        pr_m = pr_m[pr_m.index >= "2005-01-01"]
        res = {}
        a_an = B.anual(aqr)
        p_an = B.anual_precio(pr)
        p_an = p_an[p_an.index >= 2005]
        res["aqr_vs_oecd_precio_anual"] = B.comparar(a_an, p_an)
        res["aqr_vs_oecd_precio_movil12"] = _comp_m(_movil(aqr), _movil(pr_m))
        # dividendo implícito (TR AQR / precio OCDE), por tramos, para el respaldo
        res["div_implicito"] = {f"{h - 9}-{h}": (round(v, 4) if (v := B.rend_div_implicito(aqr, pr, f"{h}-12-31"))
                                                 is not None else None) for h in (2014, 2024)}
        dv = res["div_implicito"]["2005-2014"]
        if dv is not None:
            p_tr = (1 + p_an[p_an.index >= 2015]) * (1 + dv) - 1
            res["aqr_vs_oecd_mas_div05_14_2015_"] = B.comparar(a_an[a_an.index >= 2015], p_tr)
        if c in ff["tr"]:
            f_tr = ff["tr"][c][ff["tr"][c].index >= "2005-01-01"] / 100
            f_pr = ff["precio"][c][ff["precio"][c].index >= "2005-01-01"] / 100
            res["aqr_vs_french_local_anual"] = B.comparar(a_an, B.anual(f_tr))
            res["aqr_vs_french_local_movil12"] = _comp_m(_movil(aqr), _movil(f_tr))
            res["aqr_vs_french_local_mensual"] = _comp_m(aqr, f_tr)
            fa, fp = B.anual(f_tr), B.anual(f_pr)
            dy = ((1 + fa) / (1 + fp) - 1)
            res["french_rend_div"] = {"2005-2014": round(float(dy.loc[2005:2014].mean()), 4),
                                      "2015-2025": round(float(dy.loc[2015:2025].mean()), 4)}
            res["french_precio_vs_oecd_precio_anual"] = B.comparar(fp, p_an)
        if c in JKP:
            jk = B.tr_local_desde_usd(B.leer_obs(con, f"jkp_{lc}_mkt_m", desde=desde), rf, x)
            jk = jk[jk.index >= "2005-01-01"]
            res["aqr_vs_jkp_anual"] = B.comparar(a_an, B.anual(jk))
            res["aqr_vs_jkp_movil12"] = _comp_m(_movil(aqr), _movil(jk))
            res["aqr_vs_jkp_mensual"] = _comp_m(aqr, jk)
        if c == "USA":
            ff = B.tr_local_desde_usd(B.leer_obs(con, "ff_mkt_rf_m", desde="2005-01-01"),
                                      B.leer_obs(con, "ff_rf_m", desde="2005-01-01"), None)
            res["aqr_vs_french_anual"] = B.comparar(a_an, B.anual(ff))
            res["aqr_vs_french_movil12"] = _comp_m(_movil(aqr), _movil(ff))
            sh = B.leer_obs(con, "shiller_nominal_stock_tr_ret_m", desde="2005-01-01")
            res["aqr_vs_shiller_anual"] = B.comparar(a_an, B.anual(sh))
            dm = B.leer_obs(con, "damodaran_sp500_tr", desde="2005-01-01")
            res["aqr_vs_damodaran_anual"] = B.comparar(a_an, pd.Series(dm.values, index=dm.index.year))
            sp = B.leer_obs(con, "SP500")
            res["sp500_fred_precio_desde"] = str(sp.index.min().date())
        out[c] = res
    return out


def rupturas_ocde(con) -> dict:
    """Saltos mensuales |Δlog| > 25 % del índice OCDE (≤ hoy), por país: señales de ruptura o cambio de base."""
    out = {}
    for c in B.NUCLEO:
        s = B._mes(B.leer_obs(con, f"oecd_share_{c.lower()}"))
        d = np.log(s).diff()
        big = d[d.abs() > 0.25]
        out[c] = {str(k.date())[:7]: round(float(v), 3) for k, v in big.items()}
    return out


def disponibilidad(con, fx: dict, hoy) -> dict:
    hoy = pd.Timestamp(hoy)
    sids = {"aqr_mkt_<pais>_m": "aqr_mkt_deu_m", "aqr_rf_risk_free_rate_m": "aqr_rf_risk_free_rate_m",
            "oecd_share_<pais>": "oecd_share_deu", "oecd_cpi_<pais>_idx": "oecd_cpi_deu_idx",
            "jkp_<pais>_mkt_m": "jkp_deu_mkt_m", "ff_mkt_rf_m": "ff_mkt_rf_m",
            "shiller_nominal_stock_tr_ret_m": "shiller_nominal_stock_tr_ret_m", "SP500 (FRED, diario)": "SP500"}
    out = {}
    for k, sid in sids.items():
        u = con.execute("select max(date) from obs_latest where series_id = ?", [sid]).fetchone()[0]
        fin = pd.Timestamp(u) + pd.offsets.MonthEnd(0)
        out[k] = {"ultimo": str(pd.Timestamp(u).date()), "dias_desde_fin_de_ese_mes": int((hoy - fin).days)}
    for sid, s in fx.items():
        out[f"FRED {sid}"] = {"ultimo": str(s.index.max().date()), "dias_desde_fin_de_ese_mes": int((hoy - s.index.max()).days)}
    por_pais = {c: con.execute("select max(date) from obs_latest where series_id = ?", [f"oecd_share_{c.lower()}"])
                .fetchone()[0] for c in B.NUCLEO}
    out["oecd_share_ultimo_por_pais"] = {c: str(v) for c, v in por_pais.items()}
    out["aqr_mkt_ultimo_por_pais"] = {c: str(con.execute("select max(date) from obs_latest where series_id = ?",
                                                         [f"aqr_mkt_{c.lower()}_m"]).fetchone()[0]) for c in B.NUCLEO}
    return out


def resumen(tabla: dict, clave: str, campo: str) -> dict:
    v = [r[clave][campo] for r in tabla.values() if clave in r and campo in r[clave]]
    return {"n_paises": len(v), "mediana": round(float(np.median(v)), 3) if v else None,
            "min": round(float(np.min(v)), 3) if v else None, "max": round(float(np.max(v)), 3) if v else None}


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    con = D.connect()
    fx = fx_diarias("--refrescar" in sys.argv)
    ff = french_paises("--refrescar" in sys.argv)
    h, v = historico(con, ff), vivo(con, fx, ff)
    res = {"hoy": str(pd.Timestamp.today().date()), "historico_vs_jst_hasta_2004": h,
           "ipc_ocde_vs_jst_hasta_2004": _ipc_jst_vs_ocde(con), "vivo_entre_fuentes_desde_2005": v,
           "rupturas_ocde": rupturas_ocde(con), "disponibilidad": disponibilidad(con, fx, pd.Timestamp.today()),
           "resumen": {f"{k}.{c}": resumen(h, k, c) for k in ("aqr_local", "jkp_local", "french_local_tr", "oecd_precio_desde_1986",
                                                              "oecd_precio_mas_dp_constante_86_04")
                       for c in ("corr", "sesgo_pp", "dt_dif_pp")}
           | {f"vivo.{k}.{c}": resumen(v, k, c) for k in ("aqr_vs_jkp_anual", "aqr_vs_jkp_movil12", "aqr_vs_french_local_anual",
                                                          "aqr_vs_french_local_movil12", "aqr_vs_french_local_mensual",
                                                          "aqr_vs_oecd_precio_anual", "aqr_vs_oecd_precio_movil12",
                                                          "aqr_vs_oecd_mas_div05_14_2015_")
              for c in ("corr", "sesgo_pp", "dt_dif_pp")}}
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    print(json.dumps(res["resumen"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
