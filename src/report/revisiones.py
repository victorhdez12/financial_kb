"""Deriva de revisión: cuánto ha revisado la fuente (sobre todo la OCDE) las series ≤ 2004 desde la instantánea con la
que se congelaron las referencias de INT-8b y del termómetro (research/int/instantanea_dev_2004.json), y si eso cambiaría
lo que se publica en vivo. Descriptivo: las referencias congeladas siguen siendo la verdad y NO se recalculan
(docs/int/INT8b_nowcast.md y docs/int/TERMOMETRO_diseno_v1.md, «Revisiones de datos»).

Dos medidas (umbrales declarados; ver UMBRALES):
1. Datos: por serie de la instantánea, |Δ| máximo (warehouse de hoy − instantánea) en ≤ 2004: en pp para tipos, paro y
   crédito/PIB; en pp de la interanual en log para los índices (IP, ventas, IPC, bolsa, PIB, CLI, confianza), que es lo
   único que usan los indicadores.
2. Efecto: los percentiles ENTEROS publicados hoy (nowcast INT-8b: agregado, índice de cada país y cada indicador;
   termómetro: percentil ≤ 2004 de cada indicador) con las referencias congeladas frente a los que saldrían si se
   recalcularan las referencias con los datos ≤ 2004 de hoy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import int8b as K
from src.intl import panel as P
from src.intl import termometro as T
from src.report import nowcast_vivo as NV
from src.report import termometro_vivo as TV

# Umbrales de «diferencia grande» (estrictamente mayor; holgura 1e-9 por coma flotante). Razones:
# - tipos y paro, 0,10 pp: la OCDE los publica con 2-3 decimales; los retoques de redondeo o de rebase observados
#   (2-nov: BEL 10 años ≤ 0,02 pp; paro IRL/ITA 0,1 pp en 3 meses) no mueven distribuciones de 45 años; una revisión
#   mayor ya es un cambio de fuente o de definición (p. ej. otro bono de referencia) y hay que mirarla;
# - crédito/PIB (BIS), 1,0 pp de PIB: K4/C2 usan su variación a 5 años, que se mueve decenas de pp;
# - índices, 1,0 pp en la interanual: la revisión del 2-nov movió la IP interanual de GBR hasta 0,76 pp; 1 pp ya
#   puede cambiar el signo de la IP en meses cercanos a 0 (K5);
# - percentiles enteros: cualquier cambio (≥ 1 punto) de un percentil publicado hoy. Es la consecuencia que importa
#   y el 2-nov fue 0 en todos (medido el 4-nov).
UMBRALES = {"pp": 0.10, "pp_pib": 1.0, "pp_interanual": 1.0, "percentil": 1}
HOLGURA = 1e-9
_NIVEL = ("irlt", "ir3m", "unemp", "cbpol")


def con_instantanea_mas_vivo(con_vivo, inst: pd.DataFrame | None = None):
    """`obs_latest` en memoria = instantánea (≤ 2004) + lo posterior a 2004 del warehouse para sus series y los
    sustitutos del tipo a 3 meses: lo que habría leído la carga en vivo sin la revisión de ≤ 2004."""
    import duckdb
    inst = D.leer_instantanea() if inst is None else inst
    sids = sorted(set(inst.series_id) | {s for s, _ in TV.SUSTITUTOS_3M.values()})
    vivo = con_vivo.execute("select series_id, date, value from obs_latest where value is not null and date > ? and "
                            "series_id in (select unnest(?))", [D.DEV_END.date(), sids]).df()
    df = pd.concat([inst[["series_id", "date", "value"]], vivo], ignore_index=True)  # noqa: F841
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest as select series_id, cast(date as date) as date, value from df")
    return con


def tipo_serie(sid: str) -> str | None:
    """'pp' (nivel en pp), 'pp_pib', 'pp_interanual' (índice) o None (fuera de umbral: solo se informa)."""
    if sid.startswith("bis_creditgap_"):
        return "pp_pib"
    if sid.startswith("bis_cbpol_") or (sid.startswith("oecd_") and sid.split("_")[1] in _NIVEL):
        return "pp"
    if sid.startswith("oecd_"):
        return "pp_interanual"
    return None


def _serie(df: pd.DataFrame) -> pd.Series:
    return pd.Series(df["value"].astype(float).to_numpy(), index=pd.to_datetime(df["date"]))


def _interanual(s: pd.Series, trimestral: bool) -> pd.Series:
    if trimestral:
        p = s.index.to_period("Q")
        g = pd.Series(s.to_numpy(), index=p).reindex(pd.period_range(p.min(), p.max(), freq="Q"))
        return np.log(g).diff(4) * 100
    return np.log(P._mensual_completa(s)).diff(12) * 100


def deriva_datos(con, inst: pd.DataFrame | None = None) -> pd.DataFrame:
    """Una fila por serie de la instantánea: tipo, meses comparados, meses con |Δ| > 1e-12, |Δ| máximo y su fecha,
    fechas que faltan o sobran, y si supera el umbral."""
    inst = D.leer_instantanea() if inst is None else inst
    hoy = con.execute("select series_id, date, value from obs_latest where value is not null and date <= ? and "
                      "series_id in (select unnest(?))", [D.DEV_END.date(), sorted(inst.series_id.unique())]).df()
    filas = []
    for sid, a in inst.groupby("series_id"):
        a, b = _serie(a), _serie(hoy[hoy.series_id == sid])
        tipo = tipo_serie(sid)
        if tipo == "pp_interanual":
            q = sid.startswith("oecd_gdpq_")
            a, b = _interanual(a, q).dropna(), _interanual(b, q).dropna() if not b.empty else b
        com = a.index.intersection(b.index)
        d = (b[com] - a[com]).abs()
        dmax = float(d.max()) if len(d) else 0.0
        filas.append({"series_id": sid, "tipo": tipo, "comparados": len(com), "cambiados": int((d > 1e-12).sum()),
                      "dif_max": dmax, "fecha_dif_max": None if not len(d) or dmax == 0 else str(d.idxmax().date()),
                      "faltan_hoy": int(len(a.index.difference(b.index))),
                      "nuevos_hoy": int(len(b.index.difference(a.index))),
                      "grande": tipo is not None and dmax > UMBRALES[tipo] + HOLGURA})
    return pd.DataFrame(filas).sort_values(["grande", "dif_max"], ascending=False).reset_index(drop=True)


def _refs_hoy(con) -> tuple[dict, dict]:
    """Referencias que saldrían HOY con los datos ≤ 2004 del warehouse (solo para medir la deriva; nunca se publican)."""
    pm, bis, pib, paro, _ = NV.cargar(con, str(D.DEV_END.date()))
    r8 = K.referencias(K.componentes(pm, bis, pib, paro, NV.NUCLEO, NV.TODOS), NV.NUCLEO, NV.TODOS)
    par = TV.parametros()
    mens = T.mensuales(pm, bis, pib, TV.NUCLEO, TV.TODOS)
    return r8, TV.referencias(mens, T.traducir(mens, par["rectas"], TV.TODOS), pib, par)


def _percentiles_nowcast(res: dict) -> dict:
    out = {"agregado": res["agregado"]["percentil"]}
    for c, d in res["paises"].items():
        out[f"{c} índice"] = d["percentil"]
        out |= {f"{c} {k}": v["percentil_orientado"] for k, v in d["indicadores"].items()}
    return out


def _percentiles_termometro(res: dict) -> dict:
    return {f"{c} {k}": v["percentil_hasta_2004"] for c, d in res["paises"].items() for k, v in d["indicadores"].items()}


def deriva_percentiles(con, fecha) -> dict:
    """Percentiles enteros publicados hoy con las referencias congeladas vs. recalculadas con los datos de hoy."""
    r8, rt = _refs_hoy(con)
    out = {}
    for nombre, f, pct, refs in (("nowcast", NV.nowcast, _percentiles_nowcast, r8),
                                 ("termometro", TV.termometro, _percentiles_termometro, rt)):
        a, b = pct(f(con, fecha)), pct(f(con, fecha, refs=refs))
        cambios = {k: (a[k], b[k]) for k in a if a[k] != b[k] and not (a[k] is None and b[k] is None)}
        dmax = max((abs(x - y) for x, y in cambios.values() if x is not None and y is not None), default=0)
        out[nombre] = {"comparados": len(a), "cambiados": cambios, "dif_max": dmax,
                       "nulos_distintos": sum((x is None) != (y is None) for x, y in cambios.values())}
    return out


def informe(con, fecha) -> dict:
    datos = deriva_datos(con)
    pct = deriva_percentiles(con, fecha)
    grandes = datos[datos.grande].series_id.tolist()
    pct_grande = [n for n, d in pct.items() if d["dif_max"] >= UMBRALES["percentil"] or d["nulos_distintos"]]
    return {"fecha": str(pd.Timestamp(fecha).date()), "instantanea": D.ruta_instantanea().name,
            "umbrales": UMBRALES, "series_revisadas": datos[datos.cambiados > 0].to_dict("records"),
            "series_grandes": grandes, "percentiles": pct, "percentiles_grandes": pct_grande,
            "grande": bool(grandes or pct_grande)}


def texto(inf: dict) -> str:
    rev = inf["series_revisadas"]
    lin = [f"Deriva de revisión ≤ 2004 frente a {inf['instantanea']} ({len(rev)} series revisadas; umbrales "
           f"{inf['umbrales']}):"]
    for r in rev:
        u = {"pp": "pp", "pp_pib": "pp PIB", "pp_interanual": "pp interanual", None: "(sin umbral)"}[r["tipo"]]
        lin.append(f"  {r['series_id']}: {r['cambiados']}/{r['comparados']} meses, |Δ| máx {r['dif_max']:.4f} {u}"
                   f" ({r['fecha_dif_max']}){' ← GRANDE' if r['grande'] else ''}")
    for n, d in inf["percentiles"].items():
        lin.append(f"  {n}: {len(d['cambiados'])} de {d['comparados']} percentiles publicados cambiarían "
                   f"(máx {d['dif_max']} puntos){' ← GRANDE' if n in inf['percentiles_grandes'] else ''}")
    return "\n".join(lin)
