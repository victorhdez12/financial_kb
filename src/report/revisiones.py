"""Deriva de revisión: cuánto ha revisado la fuente (sobre todo la OCDE) las series ≤ 2004 desde la instantánea con la
que se congelaron las referencias de INT-8b y del termómetro (research/int/instantanea_dev_2004.json), y si eso cambiaría
lo que se publica en vivo. Descriptivo: las referencias congeladas siguen siendo la verdad y NO se recalculan
(docs/int/INT8b_nowcast.md y docs/int/TERMOMETRO_diseno_v1.md, «Revisiones de datos»).

Dos medidas, cada una con dos umbrales por familia (aviso y fallo; docs/int/OCDE_deriva_umbrales.md):
1. Datos: por serie de la instantánea, |Δ| máximo (warehouse de hoy − instantánea) en ≤ 2004 en la TRANSFORMACIÓN que
   usa el proyecto (src/intl/panel.py, src/intl/termometro.py): nivel en pp (tipos, paro, crédito/PIB), nivel en puntos
   (CLI, confianza: se usan en nivel), interanual en log ×100 (IP, ventas, IPC, bolsa OCDE, PIB trimestral) y
   rentabilidad mensual en pp (AQR). Más reglas de estructura: fechas ≤ 2004 que desaparecen → fallo (rotura); fechas
   nuevas → aviso; cambio de base puro en una serie que solo se usa en interanual → aviso (inocuo).
2. Efecto: los percentiles ENTEROS publicados hoy (nowcast INT-8b: agregado, índice de cada país y cada indicador;
   termómetro: percentil ≤ 2004 de cada indicador) con las referencias congeladas frente a los que saldrían si se
   recalcularan las referencias con los datos ≤ 2004 de hoy.
Estado: «ok» < «aviso» (revisión normal: se informa) < «fallo» (cambio de base, de definición o rotura: el test falla
y se decide a mano si hay nueva instantánea y nueva congelación declarada).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import int8b as K
from src.intl import panel as P
from src.intl import termometro as T
from src.report import nowcast_vivo as NV
from src.report import termometro_vivo as TV


@dataclass(frozen=True)
class Umbral:
    familia: str
    patron: str          # regex sobre series_id
    metrica: str         # "nivel" | "interanual" (mensual, log ×100) | "interanual_t" (trimestral, log ×100)
    unidad: str
    aviso: float         # |Δ| máx > aviso → «aviso»
    fallo: float         # |Δ| máx > fallo → «fallo»


# PROPUESTA v1 (5-nov-2026), PENDIENTE DE APROBACIÓN DEL USUARIO (docs/int/OCDE_deriva_umbrales.md, §2). Estrictamente
# mayor, con holgura 1e-9. Criterio: «aviso» por encima del redondeo con el que publica la fuente (un retoque de la
# última cifra no avisa); «fallo» ≈ 0,2-0,3 desviaciones típicas ≤ 2004 de la transformación usada en el país con
# menos variación (σ mínima por familia: IP 3,9; ventas 1,9; IPC 1,7; bolsa 14,5; PIB 1,8 pp interanual; CLI/confianza
# 1,3-2,0 puntos; Δ12 de tipos 1,2 y de paro 0,9 pp), el orden de un cambio de base o de definición. Medido el 4/5-nov (revisión OCDE del 2-nov): máximos IP GBR 0,76 pp interanual
# (→ aviso), IP BEL 0,20, ventas GBR 0,20, IP ESP/FIN/SWE/ITA ≤ 0,12, tipo 10 años BEL 0,02 pp, paro IRL/ITA 0,10 pp
# (un dígito), ventas DNK 1e-4 (ruido de decimales): ninguno en fallo. El orden importa (gana el primer patrón).
UMBRALES_FAMILIA: tuple[Umbral, ...] = (
    Umbral("tipos", r"oecd_(irlt|ir3m|ircall)_[a-z]{3}|bis_cbpol_[a-z]{2}", "nivel", "pp", 0.05, 0.25),
    Umbral("paro", r"oecd_unemp_[a-z]{3}", "nivel", "pp", 0.10, 0.25),
    Umbral("ipc_interanual_publicada", r"oecd_(cpi|cpicore)_[a-z]{3}_yoy", "nivel", "pp", 0.05, 0.30),
    Umbral("ipc", r"oecd_(cpi|cpicore)_[a-z]{3}_idx", "interanual", "pp interanual", 0.05, 0.30),
    Umbral("ip", r"oecd_ip_[a-z]{3}", "interanual", "pp interanual", 0.25, 1.0),
    Umbral("ventas", r"oecd_retail_[a-z]{3}", "interanual", "pp interanual", 0.25, 0.50),
    Umbral("bolsa", r"oecd_share_[a-z]{3}", "interanual", "pp interanual", 0.50, 3.0),
    Umbral("cli", r"oecd_cli_[a-z]{3}", "nivel", "puntos", 0.05, 0.30),
    Umbral("confianza", r"oecd_(bci|cci)_[a-z]{3}", "nivel", "puntos", 0.05, 0.30),
    Umbral("pib_trimestral", r"oecd_gdpq_[a-z]{3}", "interanual_t", "pp interanual", 0.10, 0.50),
    Umbral("credito_pib", r"bis_creditgap_[a-z]{2}_ratio", "nivel", "pp PIB", 0.50, 2.0),
    Umbral("bolsa_aqr", r"aqr_mkt_[a-z]{3}_m", "nivel", "pp rent. mensual", 0.05, 0.50),
    Umbral("jst_dp", r"jst_[a-z]{3}_eq_dp", "nivel", "ratio", 0.0005, 0.005),
    Umbral("usrec", r"USREC", "nivel", "0/1", 0.0, 0.0),          # cualquier cambio de fechado NBER → fallo
)
UMBRAL_PERCENTIL = {"aviso": 1, "fallo": 3}   # puntos enteros en cualquier percentil publicado hoy (≥)
# Cambio de base: en una serie usada solo en interanual, log(hoy/instantánea) constante (rango ≤ 0,01 %) y ≠ 0.
BASE_RANGO, BASE_MIN = 0.01, 0.01
HOLGURA = 1e-9
ESTADOS = ("ok", "aviso", "fallo")
_RX = [(re.compile(f"^(?:{u.patron})$"), u) for u in UMBRALES_FAMILIA]


def umbral_de(sid: str) -> Umbral | None:
    return next((u for rx, u in _RX if rx.match(sid)), None)


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


def _serie(df: pd.DataFrame) -> pd.Series:
    return pd.Series(df["value"].astype(float).to_numpy(), index=pd.to_datetime(df["date"])).sort_index()


def _interanual(s: pd.Series, trimestral: bool) -> pd.Series:
    if s.empty:
        return s
    if trimestral:
        p = s.index.to_period("Q")
        g = pd.Series(s.to_numpy(), index=p).reindex(pd.period_range(p.min(), p.max(), freq="Q"))
        return np.log(g).diff(4) * 100
    return np.log(P._mensual_completa(s)).diff(12) * 100


def transformar(s: pd.Series, metrica: str) -> pd.Series:
    return {"nivel": lambda x: x, "interanual": lambda x: _interanual(x, False),
            "interanual_t": lambda x: _interanual(x, True)}[metrica](s).dropna()


def _estado(dmax: float, u: Umbral | None) -> str:
    if u is None:
        return "ok"
    return "fallo" if dmax > u.fallo + HOLGURA else "aviso" if dmax > u.aviso + HOLGURA else "ok"


def _fecha(ix) -> str:
    return str((ix.start_time if isinstance(ix, pd.Period) else pd.Timestamp(ix)).date())


def _peor(*e: str) -> str:
    return max(e, key=ESTADOS.index)


def deriva_datos(con, inst: pd.DataFrame | None = None) -> pd.DataFrame:
    """Una fila por serie de la instantánea: familia, métrica y unidad, comparados, cambiados (|Δ| > 1e-12), |Δ| máximo,
    su fecha y percentil 99 de |Δ|, fechas ≤ 2004 que faltan o sobran hoy, cambio de base, estado y motivo."""
    inst = D.leer_instantanea() if inst is None else inst
    hoy = con.execute("select series_id, date, value from obs_latest where value is not null and date <= ? and "
                      "series_id in (select unnest(?))", [D.DEV_END.date(), sorted(inst.series_id.unique())]).df()
    filas = []
    for sid, a in inst.groupby("series_id"):
        a, b = _serie(a), _serie(hoy[hoy.series_id == sid])
        u = umbral_de(sid)
        metrica = u.metrica if u else "nivel"
        faltan, nuevos = len(a.index.difference(b.index)), len(b.index.difference(a.index))
        ta, tb = transformar(a, metrica), transformar(b, metrica)
        com = ta.index.intersection(tb.index)
        d = (tb[com] - ta[com]).abs()
        dmax = float(d.max()) if len(d) else 0.0
        base = None
        cr = a.index.intersection(b.index)
        if metrica != "nivel" and len(cr) and (a[cr] > 0).all() and (b[cr] > 0).all():
            lr = np.log(b[cr] / a[cr]) * 100
            if float(lr.max() - lr.min()) <= BASE_RANGO and abs(float(lr.mean())) > BASE_MIN:
                base = round(float(lr.mean()), 4)
        motivos, est = [], _estado(dmax, u)
        if est != "ok":
            motivos.append(f"|Δ| {dmax:.4g} {u.unidad} > {u.fallo if est == 'fallo' else u.aviso}")
        if faltan:
            est = _peor(est, "fallo")
            motivos.append(f"rotura: {faltan} fechas ≤ 2004 faltan hoy")
        if nuevos:
            est = _peor(est, "aviso")
            motivos.append(f"{nuevos} fechas ≤ 2004 nuevas")
        if base is not None:
            est = _peor(est, "aviso")
            motivos.append(f"cambio de base {base:+.3f} % (inocuo en interanual)")
        filas.append({"series_id": sid, "familia": u.familia if u else None, "metrica": metrica,
                      "unidad": u.unidad if u else None, "comparados": len(com), "cambiados": int((d > 1e-12).sum()),
                      "dif_max": dmax, "dif_p99": float(d.quantile(0.99)) if len(d) else 0.0,
                      "fecha_dif_max": None if not len(d) or dmax == 0 else _fecha(d.idxmax()),
                      "faltan_hoy": faltan, "nuevos_hoy": nuevos, "cambio_base_pct": base,
                      "aviso": u.aviso if u else None, "fallo": u.fallo if u else None,
                      "estado": est, "motivo": "; ".join(motivos), "grande": est == "fallo"})
    out = pd.DataFrame(filas)
    out["_o"] = out.estado.map(ESTADOS.index)
    return out.sort_values(["_o", "dif_max"], ascending=False).drop(columns="_o").reset_index(drop=True)


def resumen_familias(datos: pd.DataFrame) -> pd.DataFrame:
    """Por familia: series, revisadas, |Δ| máximo (y serie), umbrales y recuento por estado."""
    g = datos.assign(familia=datos.familia.fillna("(sin umbral)")).groupby("familia", sort=False)
    out = g.agg(series=("series_id", "size"), revisadas=("cambiados", lambda x: int((x > 0).sum())),
                dif_max=("dif_max", "max"), unidad=("unidad", "first"), aviso=("aviso", "first"),
                fallo=("fallo", "first"), n_aviso=("estado", lambda x: int((x == "aviso").sum())),
                n_fallo=("estado", lambda x: int((x == "fallo").sum())))
    out["serie_max"] = g.apply(lambda x: x.loc[x.dif_max.idxmax(), "series_id"] if x.dif_max.max() > 0 else None)
    return out.reset_index()


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


def estado_percentiles(d: dict) -> str:
    """«fallo» si algún percentil cambia ≥ UMBRAL_PERCENTIL['fallo'] puntos o pasa de nulo a no nulo (o al revés);
    «aviso» si alguno cambia ≥ UMBRAL_PERCENTIL['aviso']; si no, «ok»."""
    if d["dif_max"] >= UMBRAL_PERCENTIL["fallo"] or d["nulos_distintos"]:
        return "fallo"
    return "aviso" if d["dif_max"] >= UMBRAL_PERCENTIL["aviso"] else "ok"


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
        out[nombre]["estado"] = estado_percentiles(out[nombre])
    return out


def informe(con, fecha, con_percentiles: bool = True) -> dict:
    datos = deriva_datos(con)
    pct = deriva_percentiles(con, fecha) if con_percentiles else {}
    est = _peor("ok", *datos.estado, *(d["estado"] for d in pct.values()))
    return {"fecha": str(pd.Timestamp(fecha).date()), "instantanea": D.ruta_instantanea().name,
            "origen_instantanea": D.origen_instantanea(),
            "umbrales": {u.familia: (u.metrica, u.aviso, u.fallo) for u in UMBRALES_FAMILIA} | {
                "percentil": UMBRAL_PERCENTIL},
            "series_revisadas": datos[(datos.cambiados > 0) | (datos.estado != "ok")].to_dict("records"),
            "familias": resumen_familias(datos).to_dict("records"),
            "series_aviso": datos[datos.estado == "aviso"].series_id.tolist(),
            "series_fallo": datos[datos.estado == "fallo"].series_id.tolist(),
            "percentiles": pct, "estado": est,
            "grande": est == "fallo"}      # compatibilidad: «grande» = fallo


def texto(inf: dict) -> str:
    rev = inf["series_revisadas"]
    lin = [f"Deriva de revisión ≤ 2004 frente a {inf['instantanea']} ({inf['origen_instantanea']}): estado "
           f"{inf['estado'].upper()}; {len(rev)} series revisadas, {len(inf['series_aviso'])} en aviso, "
           f"{len(inf['series_fallo'])} en fallo (umbrales: docs/int/OCDE_deriva_umbrales.md)"]
    for r in rev:
        u = r["unidad"] or "(sin umbral)"
        lin.append(f"  [{r['estado']:5s}] {r['series_id']} ({r['familia']}, {r['metrica']}): {r['cambiados']}/"
                   f"{r['comparados']}, |Δ| máx {r['dif_max']:.4f} {u} ({r['fecha_dif_max']})"
                   f"{' — ' + r['motivo'] if r['motivo'] else ''}")
    for n, d in inf["percentiles"].items():
        lin.append(f"  [{d['estado']:5s}] {n}: {len(d['cambiados'])} de {d['comparados']} percentiles publicados "
                   f"cambiarían (máx {d['dif_max']} puntos)")
    return "\n".join(lin)
