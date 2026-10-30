"""Validador INT-11 v2 (30-oct; ver docs/validation/2026-10-30_int11v2.md). Comprobaciones de la salida "hoy":
  ventana      ventana_objetivo de la emisión 2026-10-30 y desfase estado → ventana por país
  maddison     brecha per cápita con Maddison extrapolada (≤ 2022) frente a población WDI (≤ 2025; 8 países con dato)
  interp       EE. UU.: mes de IPC interpolado; inflación con la interpolación frente a la ventana anterior completa
  umbral       fragilidad del 3 %: distancia al umbral de los 14 países hoy y de los estados móviles de las 12 últimas
               emisiones posibles (cortes 2025-10 … 2026-09; SOLO el estado, ningún resultado posterior), cambios de
               régimen mes a mes; P(inflación > 5 %) del motor (≤ 2004) por régimen y su versión suave
Lee OCDE/Maddison/WDI en vivo SOLO para el estado (como src/report/escenarios_vivo); el motor sigue con ≤ 2004.
Uso: .venv/bin/python -m scripts.val_int11v2_hoy
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from scripts.int11_corrida import NUCLEO, cargar_real
from src.intl import data as D
from src.intl import escenarios as E
from src.intl.procedencia import procedencia
from src.report import escenarios_vivo as V
from src.report import termometro_vivo as TV

OUT = Path(__file__).resolve().parents[1] / "research/int/val_int11v2"
FECHA = "2026-10-30"
WDI = {"DEU", "ESP", "FRA", "GBR", "ITA", "JPN", "NLD", "USA"}


def _wdi(con, lc, corte):
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date <= ? "
                     "order by date", [f"wdi_{lc}_sp_pop_totl", pd.Timestamp(corte).date()]).df()
    return pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]).dt.year)


def main():
    con = D.connect()
    corte = TV.fin_de_mes(FECHA)
    o = {"ventana": E.ventana_objetivo(FECHA), "corte": str(corte.date())}
    # ---------------- estado de hoy, Maddison frente a WDI, total
    hoy, mad = {}, {}
    for c in NUCLEO:
        lc = c.lower()
        ipc, pib = TV._serie(con, f"oecd_cpi_{lc}_idx", corte), TV._serie(con, f"oecd_gdpq_{lc}", corte)
        pm = V._poblacion(con, lc, corte)
        e = E.estado_movil(ipc, pib, pm)
        et = E.estado_movil(ipc, pib, None)
        r = {"inflacion": e["inflacion"], "brecha_maddison": e["brecha"], "brecha_total": et["brecha"],
             "regimen": e["regimen"], "mes_ipc": e["mes_ipc"], "trimestre_pib": e["trimestre_pib"],
             "huecos": e["huecos_ipc_interpolados"], "maddison_ultimo": int(pm.index.max())}
        if c in WDI:
            pw = _wdi(con, lc, corte)
            ew = E.estado_movil(ipc, pib, pw)
            r["brecha_wdi"] = ew["brecha"]
            r["sesgo_maddison_pp"] = 100 * (e["brecha"] - ew["brecha"])
            r["regimen_wdi"] = ew["regimen"]
            yrs = [y for y in (2022, 2023, 2024, 2025) if y in pw.index]
            r["crec_pob_wdi_2022_2025_%_anual"] = 100 * float(np.log(pw[yrs[-1]] / pw[2022]) / (yrs[-1] - 2022))
            p = pm.dropna()
            r["crec_pob_maddison_extrap_%_anual"] = 100 * float(np.log(p.iloc[-1] / p[p.index >= p.index.max() - 10]
                                                                        .iloc[0]) / 10)
        # desfase: meses entre el último mes de IPC y el primer mes de la ventana
        ini = pd.Timestamp(o["ventana"]["desde"])
        r["meses_ipc_a_ventana"] = (ini.year - pd.Timestamp(e["mes_ipc"]).year) * 12 + ini.month - pd.Timestamp(
            e["mes_ipc"]).month - 1
        r["meses_pib_a_ventana"] = (ini.year - pd.Timestamp(e["trimestre_pib"]).year) * 12 + ini.month - pd.Timestamp(
            e["trimestre_pib"]).month - 3
        hoy[c] = r
        # interpolación de EE. UU.
        if e["huecos_ipc_interpolados"]:
            s = ipc.copy()
            s.index = pd.DatetimeIndex(s.index).to_period("M").to_timestamp()
            todos = pd.date_range(end=s.index[-1], periods=24, freq="MS")
            falta = [str(m.date()) for m in todos if m not in s.index]
            e0 = E.estado_movil(ipc, pib, pm)
            # alternativas: sin interpolación (retroceder hasta una ventana completa) e interpolación lineal en nivel
            ipc_ret = E._mensual_completa(ipc, 24, max_huecos=0)
            inf_ret = float(np.log(ipc_ret.iloc[12:].mean() / ipc_ret.iloc[:12].mean()))
            w = s.reindex(todos)
            lin = w.interpolate()
            inf_lin = float(np.log(lin.iloc[12:].mean() / lin.iloc[:12].mean()))
            o["interp"] = {"pais": c, "meses_faltan": falta, "inflacion_interp_log": e0["inflacion"],
                           "inflacion_interp_nivel": inf_lin, "inflacion_retrocediendo": inf_ret,
                           "mes_final_retrocediendo": str(ipc_ret.index[-1].date()),
                           "regimen_retrocediendo": E.REGIMENES[int(E.codigo_regimen([inf_ret], [e0['brecha']])[0])]}
    o["hoy"] = hoy
    # ---------------- umbral: 12 cortes mensuales (solo estado)
    cortes = pd.date_range("2025-10-31", "2026-09-30", freq="ME")
    tabla = {}
    for c in NUCLEO:
        lc = c.lower()
        fila = []
        for k in cortes:
            ipc, pib = TV._serie(con, f"oecd_cpi_{lc}_idx", k), TV._serie(con, f"oecd_gdpq_{lc}", k)
            e = E.estado_movil(ipc, pib, V._poblacion(con, lc, k))
            fila.append((str(k.date())[:7], round(100 * e["inflacion"], 3) if e.get("regimen") else None,
                         e.get("regimen")))
        tabla[c] = fila
    dist = np.array([abs(x[1] - 3) for v in tabla.values() for x in v if x[1] is not None])
    cambios = sum(sum(a[2] != b[2] for a, b in zip(v[:-1], v[1:]) if a[2] and b[2]) for v in tabla.values())
    dh = np.array([abs(100 * r["inflacion"] - 3) for r in hoy.values()])
    o["umbral"] = {"hoy_a_menos_de": {f"{t}pp": int((dh < t).sum()) for t in (0.1, 0.25, 0.5, 1.0)},
                   "hoy_distancia_pp": {c: round(100 * r["inflacion"] - 3, 2) for c, r in hoy.items()},
                   "pais_meses_12_cortes": int(len(dist)),
                   "a_menos_de": {f"{t}pp": int((dist < t).sum()) for t in (0.1, 0.25, 0.5, 1.0)},
                   "cambios_de_lado_mes_a_mes": int(cambios),
                   "paises_con_algun_cambio": [c for c, v in tabla.items()
                                               if len({x[2] for x in v if x[2]}) > 1],
                   "serie": tabla}
    # ---------------- P(inflación > 5 %) del motor por régimen y versión suave
    f = cargar_real(con)
    assert f["año"].max() <= 2004
    gen = E.Generador(E.Config.v2()).ajustar(f)
    p5 = {}
    for c in ("ESP", "NLD"):
        for s in (0, 1):
            esc = gen.simular(c, s, horizonte=1, n_lotes=200, por_lote=100, semilla=4242 + s)
            p5[f"{c}|{E.REGIMENES[s]}"] = float(np.mean(np.expm1(esc.inflacion[:, 0]) > 0.05))
    o["p_infl5_por_regimen"] = p5
    suave = {}
    for c, r in hoy.items():
        if r["brecha_maddison"] < 0:
            continue
        pe, ps = p5.get(f"{c}|expansion", p5["ESP|expansion"]), p5.get(f"{c}|sobrecalentamiento",
                                                                       p5["ESP|sobrecalentamiento"])
        x = 100 * r["inflacion"]
        suave[c] = {"infl_%": round(x, 2), "duro": round(ps if x > 3 else pe, 3),
                    **{f"sigma={s}pp": round(float((1 - stats.norm.cdf((x - 3) / s)) * pe + stats.norm.cdf((x - 3) / s)
                                                   * ps), 3) for s in (0.25, 0.5)}}
    o["p_infl5_suave_hoy"] = suave
    return o


if __name__ == "__main__":
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    o = {"procedencia": procedencia(), **main(), "segundos": round(time.time() - t0)}
    (OUT / "hoy.json").write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
    print(json.dumps({k: v for k, v in o.items() if k != "umbral"}, ensure_ascii=False, default=float, indent=0)[:6000])
    print(json.dumps({k: v for k, v in o["umbral"].items() if k != "serie"}, ensure_ascii=False, default=float))
