"""Alertas de flujos fuertes en los activos de «Mis activos» (panel web: «Hoy», «Mis activos» y cada ficha; y aviso de
macOS tras la actualización diaria).

DESCRIPTIVO. No es una señal de cartera, no entra en ningún modelo y NO se ha validado como predictor. Los umbrales se
fijaron de antemano (docs/panel/alertas_v1.md) y no se ajustan mirando qué alertas «acertaron».

Tipos (umbrales en UMBRALES):
1. Volumen anormal (diario): volumen de la sesión frente a la media de las 63 sesiones anteriores (×) y z robusto del
   log-volumen frente a las 252 anteriores (mediana y rango intercuartílico); dirección y tamaño del movimiento del
   precio (en desviaciones típicas de las 63 sesiones anteriores) y dónde cerró dentro del rango del día. Todo volumen
   tiene comprador y vendedor: solo la dirección del precio sugiere quién tenía prisa. Se marcan y NO alertan: la sesión
   en curso (incompleta), los vencimientos trimestrales (triple witching, rebalanceo del S&P), la reconstitución de
   Russell (último viernes de junio), las revisiones trimestrales de MSCI (último día hábil de feb/may/ago/nov) y los
   resultados trimestrales (día del 8-K 2.02 y la sesión siguiente) y las 5 sesiones desde un split o escisión. Futuros fuera (el volumen es del 1.er vencimiento).
   También volumen alto sostenido de 5 sesiones.
2. Institucionales: 13F (trimestral, hasta 45 días de retraso): gran gestor (20 mayores) que cambia ≥ 50 % o entra/sale,
   y cambio agregado del trimestre (resumen_13f de activos_v2). 13D/13G (participaciones del 5 %+, días de retraso).
   Form 4: compras en mercado abierto (P) de directivos, consejeros y propietarios del 10 %, y ventas grandes SIN plan
   10b5-1 (por importe y por % de su tenencia). Las ventas con plan, concesiones, retenciones, ejercicios: NO alertan.
3. Recompras de la empresa (XBRL de los 10-Q/10-K): importe por trimestre, 12 meses, % de la capitalización (buyback
   yield), variación de acciones en circulación en 12 meses; trimestre fuerte, parón y ampliación del programa
   autorizado.
Cada fuente va en su try/except: si falla, «s/d» y el panel sigue.
Uso: .venv/bin/python -m src.report.alertas [--notificar] [--listar]
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.report import activos_v2 as AV
from src.report.panel_paises import chip, esc, n

UMBRALES = {
    # volumen de una sesión: moderada si × ≥ 2 y z ≥ 2; fuerte si × ≥ 3 y z ≥ 3
    "vol_ratio": (2.0, 3.0), "vol_z": (2.0, 3.0), "vol_media": 63, "vol_z_ventana": 252, "vol_z_min": 126,
    # precio: «subida/caída fuerte» si |rentabilidad| ≥ 1,5 σ diarias (σ de las 63 sesiones anteriores)
    "px_sigma": 1.5, "clv_alto": 0.75, "clv_bajo": 0.25,
    # 5 sesiones: media de las 5 últimas / media de las 63 anteriores a ellas
    "vol5": (1.75, 2.5),
    # 13F: gestor entre los 20 mayores; cambio ≥ 50 % (o entra/sale) y ≥ 0,1 % de las acciones de la empresa; fuerte si
    # mueve ≥ 1 % de la empresa. Agregado (gestoras presentes en los dos trimestres): ≥ 1 % de la empresa; fuerte ≥ 2 %
    "f13_top": 20, "f13_pct": 0.50, "f13_min_circ": 0.001, "f13_fuerte_circ": 0.01, "f13_agregado_circ": (0.01, 0.02),
    # 13D/13G: cambio ≥ 1 punto (fuerte en 13D si ≥ 2 puntos)
    "dg_pp": 1.0, "dg_pp_fuerte": 2.0,
    # Form 4: compra P ≥ 100 mil $ (fuerte ≥ 1 M$); venta sin plan ≥ 10 M$ o (≥ 20 % de su tenencia y ≥ 1 M$);
    # fuerte ≥ 50 M$ o (≥ 50 % y ≥ 5 M$)
    "f4_compra": (1e5, 1e6), "f4_venta": (1e7, 5e7), "f4_venta_pct": ((0.20, 1e6), (0.50, 5e6)),
    # recompras: trimestre ≥ 0,75 % de la capitalización (fuerte ≥ 1,5 %), o ≥ 2× la media de los 4 anteriores y ≥ 0,4 %;
    # parón: < 10 % de la media de los 4 anteriores cuando esa media era ≥ 0,4 % de la capitalización
    "rc_pct": (0.0075, 0.015), "rc_doble": (2.0, 0.004), "rc_paron": (0.10, 0.004),
}
FUERZA = {2: "fuerte", 1: "moderada", 0: "informativa"}
DIAS_RECIENTES, DIAS_LISTA, MESES_FICHA = 7, 90, 12
AVISO = ("Descriptivo: no es una señal de compra o venta, no está validado y los umbrales son reglas fijas elegidas de "
         "antemano (docs/panel/alertas_v1.md). Todo volumen tiene un comprador y un vendedor por cada acción: un volumen "
         "anormal solo dice que alguien tenía prisa; la dirección del precio sugiere quién (si sube con fuerza, "
         "compradores; si cae, vendedores), sin poder saber si eran instituciones.")
TIPOS = {"volumen": "volumen anormal", "volumen_5s": "volumen alto 5 sesiones", "13f": "13F gestora",
         "13f_agregado": "13F agregado", "13dg": "13D/13G (5 %+)", "form4": "Form 4 directivo/10 %",
         "recompra": "recompras de la empresa"}
MESES = AV.MESES


def root() -> Path:
    return AV.root()


# ============================================================================================ carga (tolerante)
def cargar(base: dict | None = None) -> dict:
    """Las fuentes de activos_v2 (volumen, Form 4, 13F) más OHLC, FINRA, 13D/G, resultados y recompras."""
    X = dict(base) if base is not None else AV.cargar()
    r = root()
    dv = r / "mercados" / "volumen"
    for k in ("alto", "bajo"):
        try:
            X[k] = pd.read_parquet(dv / f"{k}_diario.parquet")
        except Exception as e:  # noqa: BLE001
            X[f"error_{k}"] = f"{type(e).__name__}: {e}"
    try:
        X["short"] = pd.read_parquet(r / "finra_short" / "short_diario.parquet")
    except Exception as e:  # noqa: BLE001
        X["error_short"] = f"{type(e).__name__}: {e}"
    try:
        X["dg"] = pd.read_parquet(r / "sec_flujos" / "participaciones.parquet")
        X["meta_flujos"] = json.loads((r / "sec_flujos" / "meta.json").read_text())
    except Exception as e:  # noqa: BLE001
        X["error_dg"] = f"{type(e).__name__}: {e}"
    try:
        X["resultados"] = json.loads((r / "sec_flujos" / "resultados.json").read_text())
    except Exception as e:  # noqa: BLE001
        X["error_resultados"] = f"{type(e).__name__}: {e}"
    try:
        X["recompras"] = json.loads((r / "sec_recompras" / "hechos.json").read_text())
    except Exception as e:  # noqa: BLE001
        X["error_recompras"] = f"{type(e).__name__}: {e}"
    return X


def activos() -> dict[str, tuple[str, str]]:
    from src.ingest.yahoo_precios import ACTIVOS
    return ACTIVOS


# ============================================================================================ días especiales
def _tercer_viernes(y: int, m: int) -> pd.Timestamp:
    d = pd.Timestamp(y, m, 1)
    return d + pd.Timedelta(days=(4 - d.weekday()) % 7 + 14)


def _ultimo_viernes(y: int, m: int) -> pd.Timestamp:
    d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)
    return d - pd.Timedelta(days=(d.weekday() - 4) % 7)


def _sesion_le(ix: pd.DatetimeIndex, f: pd.Timestamp) -> pd.Timestamp | None:
    """Última sesión ≤ f (si el viernes es festivo, el vencimiento pasa al jueves)."""
    k = ix.searchsorted(f, side="right") - 1
    return ix[k] if k >= 0 and (f - ix[k]).days <= 4 else None


def dias_especiales(ix: pd.DatetimeIndex, resultados: list[dict] | None = None,
                    splits: list[dict] | None = None) -> dict[pd.Timestamp, str]:
    """{sesión: motivo} de los días con volumen mecánico o esperado (no alertan; se marcan)."""
    ix = pd.DatetimeIndex(ix).sort_values()
    if not len(ix):
        return {}
    out: dict[pd.Timestamp, str] = {}

    def pon(f, motivo):
        if f is not None:
            out[f] = (out[f] + " + " + motivo) if f in out and motivo not in out[f] else motivo
    for y in range(ix[0].year, ix[-1].year + 1):
        for m in (3, 6, 9, 12):
            pon(_sesion_le(ix, _tercer_viernes(y, m)), "vencimiento trimestral de opciones y futuros (triple witching) "
                                                     "y rebalanceo del S&P")
        pon(_sesion_le(ix, _ultimo_viernes(y, 6)), "reconstitución anual de Russell")
        for m in (2, 5, 8, 11):
            pon(_sesion_le(ix, pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)), "revisión trimestral de índices MSCI")
    for s in splits or []:   # split o escisión (Yahoo trató la de Vylor como split): los índices reajustan días después
        k = ix.searchsorted(pd.Timestamp(s["fecha"]))
        for j in range(k, min(k + 5, len(ix))):
            pon(ix[j], "split o escisión (reajuste de índices y fondos)")
    for r in resultados or []:
        f = pd.Timestamp(r["fecha"])
        k = ix.searchsorted(f)
        for j in (k, k + 1):   # día del 8-K y la sesión siguiente (si los publica tras el cierre, reacciona al otro día)
            if 0 <= j < len(ix) and (ix[j] - f).days <= 5:
                pon(ix[j], "resultados trimestrales")
    return out


# ============================================================================================ 1. volumen
def senal_volumen(v: pd.Series, c: pd.Series, h: pd.Series | None = None, lo: pd.Series | None = None) -> pd.DataFrame:
    """Por sesión: volumen, media de las 63 anteriores, ×, z robusto (252 anteriores), rentabilidad, σ, k = r/σ,
    posición del cierre en el rango del día (0 = mínimo, 1 = máximo), nivel (0/1/2) y clase (sube/baja/plano)."""
    U = UMBRALES
    v = v.dropna()
    v = v[v > 0]
    d = pd.DataFrame({"vol": v})
    d["cierre"] = c.reindex(d.index)
    d = d[d["cierre"].notna() & (d["cierre"] > 0)]
    lv = np.log(d["vol"])
    prev = lv.shift(1)
    w, mn = U["vol_z_ventana"], U["vol_z_min"]
    med = prev.rolling(w, min_periods=mn).median()
    iqr = prev.rolling(w, min_periods=mn).quantile(0.75) - prev.rolling(w, min_periods=mn).quantile(0.25)
    d["z"] = (lv - med) / (iqr / 1.349)
    d["media"] = d["vol"].shift(1).rolling(U["vol_media"], min_periods=40).mean()
    d["ratio"] = d["vol"] / d["media"]
    lr = np.log(d["cierre"]).diff()
    d["ret"] = np.exp(lr) - 1
    d["sigma"] = lr.shift(1).rolling(U["vol_media"], min_periods=40).std()
    d["k"] = lr / d["sigma"]
    if h is not None and lo is not None:
        hh, ll = h.reindex(d.index), lo.reindex(d.index)
        rango = hh - ll
        d["clv"] = ((d["cierre"] - ll) / rango).where(rango > 0).clip(0, 1)
    else:
        d["clv"] = np.nan
    r1, r2 = U["vol_ratio"]
    z1, z2 = U["vol_z"]
    d["nivel"] = np.where((d["ratio"] >= r2) & (d["z"] >= z2), 2, np.where((d["ratio"] >= r1) & (d["z"] >= z1), 1, 0))
    d["clase"] = np.where(d["k"] >= U["px_sigma"], "sube", np.where(d["k"] <= -U["px_sigma"], "baja", "plano"))
    # 5 sesiones
    d["ratio5"] = d["vol"].rolling(5).mean() / d["vol"].shift(5).rolling(U["vol_media"], min_periods=40).mean()
    a, b = U["vol5"]
    d["nivel5"] = np.where(d["ratio5"] >= b, 2, np.where(d["ratio5"] >= a, 1, 0))
    d["ret5"] = d["cierre"] / d["cierre"].shift(5) - 1
    d["k5"] = np.log1p(d["ret5"]) / (d["sigma"].shift(4) * math.sqrt(5))
    return d


def _clv_txt(clv) -> str:
    if clv is None or (isinstance(clv, float) and np.isnan(clv)):
        return ""
    if clv >= UMBRALES["clv_alto"]:
        return ", cierre cerca del máximo del día"
    if clv <= UMBRALES["clv_bajo"]:
        return ", cierre cerca del mínimo del día"
    return ", cierre en mitad del rango del día"


LECTURA = {"sube": "posible compra institucional / acumulación", "baja": "posible venta / distribución",
           "plano": "sin movimiento de precio claro (compradores y vendedores equilibrados, o cruces de bloques)"}
CLASE_TIT = {"sube": "con subida fuerte", "baja": "con caída fuerte", "plano": "sin movimiento de precio"}


def frase_volumen(r: dict) -> str:
    return (f"Volumen anormal {CLASE_TIT[r['clase']]}: × {n(r['ratio'], 1, '')} su media de 3 meses (z {n(r['z'], 1, '')}); "
            f"precio {n(100 * r['ret'], 1, ' %', True)} ({n(r['k'], 1, '', True)} σ){_clv_txt(r.get('clv'))}. "
            f"Lectura: {LECTURA[r['clase']]}.")


def eventos_volumen(t: str, d: pd.DataFrame, esp: dict, incompleta: pd.Timestamp | None, desde: pd.Timestamp,
                    short: pd.DataFrame | None = None) -> list[dict]:
    out = []
    x = d[(d.index >= desde) & ((d["nivel"] > 0) | (d["nivel5"] > 0))]
    for f, r in x.iterrows():
        motivo = "sesión en curso (volumen incompleto)" if incompleta is not None and f >= incompleta else esp.get(f)
        if r["nivel"] > 0:
            rr = r.to_dict()
            fr = frase_volumen(rr)
            if short is not None and f in short.index:
                s = short.loc[f]
                med = f" (media 3 m {n(100 * s['media'], 0)})" if pd.notna(s["media"]) else ""
                fr += f" Ventas en corto FINRA ese día: {n(100 * s['pct'], 0)} de su volumen{med}."
            out.append({"fecha": f, "ticker": t, "tipo": "volumen", "fuerza": 0 if motivo else int(r["nivel"]),
                        "nivel": int(r["nivel"]), "dir": {"sube": 1, "baja": -1}.get(r["clase"], 0), "clase": r["clase"],
                        "frase": fr, "especial": motivo, "precio": float(r["cierre"]),
                        "clave": f"volumen|{t}|{f.date()}"})
    # 5 sesiones: una alerta cuando el nivel sube (no cada día de la racha)
    n5 = d["nivel5"]
    sube = d[(n5 > n5.shift(1).fillna(0)) & (d.index >= desde)]
    for f, r in sube.iterrows():
        k = d.index.get_loc(f)
        ventana = d.index[max(0, k - 4): k + 1]
        motivos = sorted({esp[g] for g in ventana if g in esp and ("resultados" in esp[g] or "split" in esp[g])})
        if incompleta is not None and f >= incompleta:
            motivos.append("sesión en curso (volumen incompleto)")
        lect = ("con subida" if r["k5"] >= UMBRALES["px_sigma"] else "con caída" if r["k5"] <= -UMBRALES["px_sigma"]
                else "sin tendencia clara de precio")
        out.append({"fecha": f, "ticker": t, "tipo": "volumen_5s", "fuerza": 0 if motivos else int(r["nivel5"]),
                    "nivel": int(r["nivel5"]), "dir": 1 if r["k5"] >= UMBRALES["px_sigma"] else -1 if r["k5"] <= -UMBRALES["px_sigma"] else 0,
                    "frase": (f"Volumen alto sostenido: las 5 últimas sesiones promedian × {n(r['ratio5'], 1, '')} la media de "
                              f"los 3 meses anteriores, {lect} ({n(100 * r['ret5'], 1, ' %', True)} en 5 sesiones)."),
                    "especial": "; ".join(motivos) or None, "precio": float(r["cierre"]),
                    "clave": f"volumen_5s|{t}|{f.date()}|{int(r['nivel5'])}"})
    return out


def short_finra(sh: pd.DataFrame | None, t: str) -> pd.DataFrame | None:
    if sh is None or not len(sh):
        return None
    x = sh[sh["ticker"] == t].set_index("fecha").sort_index()
    if x.empty:
        return None
    x = x.assign(pct=x["corto"] / x["total"])
    x["media"] = x["pct"].shift(1).rolling(63, min_periods=20).mean()
    return x


def historico_volumen(d: pd.DataFrame, esp: dict, anios: int = 10) -> dict | None:
    """DESCRIPTIVO (no es una validación): alertas de un día (nivel ≥ 1, sin días especiales) de los últimos `anios`
    años, cuántas por año y qué hizo el precio 1/5/20 sesiones después (media, desviación típica, n), por clase."""
    if d is None or len(d) < 300:
        return None
    c = d["cierre"]
    fw = {k: c.shift(-k) / c - 1 for k in (1, 5, 20)}
    desde = d.index[-1] - pd.DateOffset(years=anios)
    m = (d.index >= desde) & (d["nivel"] > 0) & ~d.index.isin(list(esp))
    ev = d[m]
    ini = d.index[d.index >= desde][0]
    out = {"desde": str(ini.date()), "n": int(len(ev)), "anios": (d.index[-1] - ini).days / 365.25,   # años reales
           "por_anio": {int(y): int(k) for y, k in ev.index.year.value_counts().sort_index().items()},
           "clases": {}, "base": {}}
    base_ix = d.index[d.index >= desde]
    for k, s in fw.items():
        b = s.reindex(base_ix).dropna()
        out["base"][k] = {"media": float(b.mean()), "sd": float(b.std()), "n": int(len(b))}
    for cl in ("sube", "baja", "plano"):
        e = ev[ev["clase"] == cl]
        out["clases"][cl] = {"n": int(len(e))}
        for k, s in fw.items():
            x = s.reindex(e.index).dropna()
            out["clases"][cl][k] = {"media": float(x.mean()) if len(x) else None,
                                   "sd": float(x.std()) if len(x) > 1 else None, "n": int(len(x))}
    return out


# ============================================================================================ 2a. 13F
def _clave_nombre(s: str) -> str:
    w = [x for x in "".join(ch if ch.isalnum() else " " for ch in str(s).upper()).split() if x not in ("THE", "INC", "LLC")]
    return w[0] if w else ""


def _filtro_13f(pos: pd.DataFrame, cierre: pd.Series | None, splits: list | None) -> pd.DataFrame:
    """Mismo filtro de unidades que activos_v2.resumen_13f (valor/acciones a > 50 % del cierre: fuera, salvo miles)."""
    d = pos.copy()
    d["period"] = pd.to_datetime(d["period"])
    if cierre is None or not len(cierre.dropna()):
        return d
    c = cierre.dropna()
    fin = {p: c[c.index <= p].iloc[-1] * AV.factor_split(splits or [], pd.Timestamp(p)) if (c.index <= p).any() else np.nan
           for p in d["period"].unique()}
    ref = d["period"].map(fin)
    imp = d["value"] / d["shares"]
    ok = ref.isna() | ((imp / ref - 1).abs() <= AV.TOL_PRECIO)
    miles = ~ok & ((1000 * imp / ref - 1).abs() <= AV.TOL_PRECIO)
    return d[ok | miles]


def eventos_13f(t: str, pos: pd.DataFrame, cierre: pd.Series | None, splits: list | None,
                acc_circ: float | None, n_trim: int = 4, presentes: dict | None = None) -> list[dict]:
    """`presentes` = {trimestre: CIK que presentaron 13F ese trimestre (con cualquiera de las acciones)}: una gestora que
    «sale» o «entra» sin informe en el otro trimestre es un informe ausente del fichero de la SEC, no una operación."""
    if pos is None or pos.empty:
        return []
    U = UMBRALES
    d = _filtro_13f(pos, cierre, splits)
    pers = sorted(d["period"].dropna().unique())[-(n_trim + 1):]
    d = d[d["period"].isin(pers)]
    if len(pers) < 2:
        return []
    pv = d.pivot_table(index="cik", columns="period", values="shares", aggfunc="sum")
    fil = d.pivot_table(index="cik", columns="period", values="filing_date", aggfunc="max")
    nom = d.sort_values("filing_date").groupby("cik")["gestor"].last()
    out = []
    for a, b in zip(pers[:-1], pers[1:]):
        if a not in pv or b not in pv:
            continue
        grandes = set(pv[a].dropna().nlargest(U["f13_top"]).index) | set(pv[b].dropna().nlargest(U["f13_top"]).index)
        entra = [k for k in grandes if np.isnan(pv.at[k, a]) and not np.isnan(pv.at[k, b])]
        sale = [k for k in grandes if not np.isnan(pv.at[k, a]) and np.isnan(pv.at[k, b])]
        reorg = {_clave_nombre(nom.get(k, "")) for k in entra} & {_clave_nombre(nom.get(k, "")) for k in sale}
        f_b = pd.Timestamp(b) + pd.Timedelta(days=45)   # plazo legal: lo que falta se sabe entonces
        pa_ok = (presentes or {}).get(pd.Timestamp(a))
        pb_ok = (presentes or {}).get(pd.Timestamp(b))
        tri = f"T{(pd.Timestamp(b).month - 1) // 3 + 1}-{pd.Timestamp(b).year}"
        for k in grandes:
            sa, sb = pv.at[k, a], pv.at[k, b]
            g = esc(str(nom.get(k, k)))
            fecha = pd.Timestamp(fil.at[k, b]) if not np.isnan(sb) and pd.notna(fil.at[k, b]) else f_b
            if _clave_nombre(g) in reorg and (k in entra or k in sale):
                continue   # misma gestora con otro CIK (p. ej. Vanguard en 2026): no es compra ni venta
            if (k in sale and pb_ok is not None and k not in pb_ok) or (k in entra and pa_ok is not None and k not in pa_ok):
                continue   # no presentó 13F (de ninguna de las acciones) en el otro trimestre: informe ausente
            if np.isnan(sa) and not np.isnan(sb):
                ds, txt = sb, f"{g} aparece con {AV._num_corto(sb)} acciones en {tri} (posición nueva o sin informe previo con ese CIK)"
            elif not np.isnan(sa) and np.isnan(sb):
                ds, txt = -sa, f"{g} ya no declara la acción en {tri} (tenía {AV._num_corto(sa)}: venta total o informe ausente)"
            else:
                if sa <= 0:
                    continue
                pct = (sb - sa) / sa
                if abs(pct) < U["f13_pct"]:
                    continue
                ds = sb - sa
                txt = f"{g} {'sube' if ds > 0 else 'baja'} su posición un {n(100 * pct, 0, ' %', True)} en {tri} ({AV._num_corto(ds)} acciones)"
            frac = abs(ds) / acc_circ if acc_circ else None
            if frac is not None and frac < U["f13_min_circ"]:
                continue
            fz = 2 if frac is not None and frac >= U["f13_fuerte_circ"] else 1
            if frac is not None:
                txt += f", ≈ {n(100 * frac, 2, ' %')} de la empresa"
            out.append({"fecha": fecha, "ticker": t, "tipo": "13f", "fuerza": fz, "dir": 1 if ds > 0 else -1,
                        "frase": txt + ". Trimestral, con hasta 45 días de retraso.", "especial": None,
                        "clave": f"13f|{t}|{pd.Timestamp(b).date()}|{k}"})
    try:   # agregado: lo calcula resumen_13f (gestoras presentes en los dos trimestres)
        r13 = AV.resumen_13f(pos, cierre, splits=splits)
        ag = (r13 or {}).get("agregado") or []
        for x in ag[-2:]:
            frac = x["delta"] / acc_circ if acc_circ else None
            a1, a2 = U["f13_agregado_circ"]
            fz = 0 if frac is None else (2 if abs(frac) >= a2 else 1 if abs(frac) >= a1 else 0)
            p = pd.Timestamp(x["periodo"])
            fecha = p + pd.Timedelta(days=45)
            out.append({"fecha": fecha, "ticker": t, "tipo": "13f_agregado", "fuerza": fz, "dir": 1 if x["delta"] > 0 else -1,
                        "frase": (f"13F T{(p.month - 1) // 3 + 1}-{p.year}: {x['suben']} gestoras suben y {x['bajan']} bajan "
                                  f"(de {x['gestores_comunes']} presentes en los dos trimestres); neto {AV._num_corto(x['delta'])} "
                                  f"acciones" + (f" ({n(100 * frac, 2, ' %', True)} de la empresa)" if frac is not None else "")
                                  + ". Trimestral, con hasta 45 días de retraso."),
                        "especial": None, "clave": f"13f_agregado|{t}|{p.date()}"})
    except Exception:  # noqa: BLE001
        pass
    return out


# ============================================================================================ 2b. 13D/13G
def eventos_13dg(t: str, dg: pd.DataFrame | None) -> list[dict]:
    if dg is None or dg.empty:
        return []
    U = UMBRALES
    x = dg[(dg["ticker"] == t) & dg["xml"].astype(bool)].sort_values(["filing_date", "accession"])
    prev: dict[str, float] = {}
    out = []
    for r in x.to_dict("records"):
        f, quien, pct = str(r["form"]), esc(r.get("filer") or "?"), r.get("pct")
        es13d, enm = "13D" in f, f.endswith("/A")
        p0 = prev.get(r["filer_cik"])
        if pct is not None and not np.isnan(pct):
            prev[r["filer_cik"]] = float(pct)
        else:
            pct = None
        fz, dirc = 0, 0
        base = f"{quien} ({f.replace('SCHEDULE ', '')})"
        if r.get("reorganizacion") and (pct == 0 or not enm):
            txt = (f"{base}: {n(pct, 2, ' %')} por reorganización interna de la gestora (declara por otras entidades; "
                   "no es compra ni venta)")
        elif pct is None:
            txt = f"{base}: sin porcentaje legible"
        elif not enm:
            if es13d:
                fz, dirc = 2, 1
                txt = (f"{base} declara un {n(pct, 1, ' %')}: el 13D es el formulario de quien NO es inversor pasivo (posible "
                       "activista, socio estratégico o fusión)")
            else:
                fz, dirc = (1, 1) if pct >= 5 else (0, 0)
                txt = f"{base} declara un {n(pct, 1, ' %')} (cruza el 5 %; 13G = inversor pasivo)"
        else:
            dpp = None if p0 is None else pct - p0
            ant = f" (antes {n(p0, 1, ' %')})" if p0 is not None else ""
            if pct < 5 and (p0 is None or p0 >= 5):
                fz, dirc = (2 if es13d and (p0 or 0) >= 10 else 1), -1
                txt = f"{base} baja al {n(pct, 1, ' %')}{ant}: por debajo del 5 %"
            elif dpp is not None and abs(dpp) >= U["dg_pp"]:
                fz = 2 if es13d and abs(dpp) >= U["dg_pp_fuerte"] else 1
                dirc = 1 if dpp > 0 else -1
                txt = f"{base} {'sube' if dpp > 0 else 'baja'} al {n(pct, 1, ' %')}{ant}"
            else:
                txt = f"{base}: {n(pct, 1, ' %')}{ant}, sin cambio relevante"
        ev = pd.Timestamp(r["event_date"]) if pd.notna(r.get("event_date")) else None
        out.append({"fecha": pd.Timestamp(r["filing_date"]), "ticker": t, "tipo": "13dg", "fuerza": fz, "dir": dirc,
                    "frase": txt + (f". Fecha del hecho {AV._fd(ev)}; presentado {AV._fd(r['filing_date'])}." if ev is not None else "."),
                    "especial": None, "clave": f"13dg|{t}|{r['accession']}"})
    return out


# ============================================================================================ 2c. Form 4
def eventos_form4(t: str, ops: pd.DataFrame | None, splits: list | None, cierre: pd.Series | None) -> list[dict]:
    """Compras P (directivos, consejeros y propietarios del 10 %) y ventas S SIN plan 10b5-1 grandes. Nada más."""
    if ops is None or ops.empty:
        return []
    U = UMBRALES
    d = AV.preparar_ops(ops, splits, cierre)
    d = d[d["cat"].isin(["compra", "venta"]) & ~d["descartada"]
          & (d["director"].astype(bool) | d["officer"].astype(bool) | d["ten_pct"].astype(bool))]
    if d.empty:
        return []
    fac = d["trans_date"].map(lambda f: AV.factor_split(splits or [], f))
    oa = d["owned_after"] if "owned_after" in d else pd.Series(np.nan, index=d.index)
    d = d.assign(owned_aj=pd.to_numeric(oa, errors="coerce") * fac,
                 cargo=[AV.cargo(r) for r in d.to_dict("records")])
    out = []
    for (owner, f, cat), g in d.groupby(["owner_cik", "trans_date", "cat"], sort=False):
        imp, acc = float(g["importe"].sum()), float(g["acciones_aj"].sum())
        resto = g["owned_aj"].dropna()
        pct = acc / (acc + float(resto.iloc[-1])) if cat == "venta" and len(resto) and acc + float(resto.iloc[-1]) > 0 else None
        # «owned_after» es la tenencia de ESA forma (directa, fondo, fideicomiso…), no la total: el % no sube a «fuerte»
        # (Validador 17-nov, H1: Andreessen/a16z Fund VIII salía «100 % de lo que tenía»)
        cg = str(g["cargo"].iloc[0])
        quien = esc(f"{g['owner_name'].iloc[0]} ({cg}{'; propietario > 10 %' if g['ten_pct'].any() and 'accionista' not in cg else ''})")
        px = imp / acc if acc else None
        if cat == "compra":
            a, b = U["f4_compra"]
            fz = 2 if imp >= b else 1 if imp >= a else 0
            txt = f"{quien} COMPRA en mercado abierto {AV._num_corto(acc)} acciones a {n(px, 2, '')} (≈ {AV._num_corto(imp)} $)"
            dirc = 1
        else:
            a, b = U["f4_venta"]
            (pa, ia), (pb, ib) = U["f4_venta_pct"]
            fz = 2 if imp >= b else \
                1 if imp >= a or (pct is not None and pct >= pa and imp >= ia) or (pct is not None and pct >= pb and imp >= ib) else 0
            txt = (f"{quien} vende SIN plan 10b5-1 {AV._num_corto(acc)} acciones a {n(px, 2, '')} (≈ {AV._num_corto(imp)} $"
                   + (f"; {n(100 * pct, 0, ' %')} de esa forma de tenencia" if pct is not None else "") + ")")
            dirc = -1
        if fz == 0:
            continue
        fil = pd.Timestamp(g["filing_date"].max())
        out.append({"fecha": fil, "ticker": t, "tipo": "form4", "fuerza": fz, "dir": dirc,
                    "frase": txt + f". Operación del {AV._fd(f)}, declarada el {AV._fd(fil)}.", "especial": None,
                    "precio": px, "fecha_op": f, "clave": f"form4|{t}|{owner}|{pd.Timestamp(f).date()}|{cat}"})
    return out


# ============================================================================================ 3. recompras
CONC_PAGO = ["us-gaap:PaymentsForRepurchaseOfCommonStock", "us-gaap:PaymentsForRepurchaseOfEquity",
             "us-gaap:StockRepurchasedDuringPeriodValue", "us-gaap:StockRepurchasedAndRetiredDuringPeriodValue"]
CONC_ACC = ["dei:EntityCommonStockSharesOutstanding", "us-gaap:CommonStockSharesOutstanding",
            "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"]   # el último, aproximación (media diluida)
CONC_PROG = ["us-gaap:StockRepurchaseProgramAuthorizedAmount1", "srt:StockRepurchaseProgramAuthorizedAmount1"]


def _hechos(h: list[dict]) -> pd.DataFrame:
    d = pd.DataFrame(h)
    if d.empty:
        return d
    for c in ("start", "end", "filed"):
        if c in d:
            d[c] = pd.to_datetime(d[c], errors="coerce")
    if "start" not in d:
        d["start"] = pd.NaT
    d["val"] = pd.to_numeric(d["val"], errors="coerce")
    d = d.dropna(subset=["end", "val"])
    g = d.groupby(["start", "end"], dropna=False)
    ult = d.sort_values("filed").groupby(["start", "end"], dropna=False).tail(1).set_index(["start", "end"])
    ult["primera"] = g["filed"].min()   # cuándo se hizo público por primera vez (las cifras pueden revisarse después)
    return ult.reset_index()


def trimestres(h: list[dict]) -> pd.DataFrame:
    """Importe de cada trimestre fiscal: directo si el hecho dura ~3 meses; si es acumulado del año (6/9/12 meses),
    la diferencia con el acumulado anterior del mismo año fiscal (misma fecha de inicio)."""
    d = _hechos(h)
    if d.empty:
        return pd.DataFrame(columns=["fin", "inicio", "importe", "publicado"])
    d["dias"] = (d["end"] - d["start"]).dt.days
    out = {}
    for r in d[(d["dias"] >= 80) & (d["dias"] <= 100)].to_dict("records"):
        out[r["end"]] = {"fin": r["end"], "inicio": r["start"], "importe": r["val"], "publicado": r["primera"]}
    acum = d[d["dias"] > 100].sort_values("end")
    for r in acum.to_dict("records"):
        if r["end"] in out:
            continue
        mismo = d[(d["start"] == r["start"]) & (d["end"] < r["end"]) & (d["dias"] >= 80)]
        if mismo.empty:
            continue
        p = mismo.sort_values("end").iloc[-1]
        if not 75 <= (r["end"] - p["end"]).days <= 100:
            continue
        out[r["end"]] = {"fin": r["end"], "inicio": p["end"] + pd.Timedelta(days=1), "importe": r["val"] - p["val"],
                         "publicado": r["primera"]}
    return pd.DataFrame(sorted(out.values(), key=lambda x: x["fin"]))


def _serie_acciones(hechos: dict) -> pd.Series:
    for c in CONC_ACC:
        if c in hechos:
            d = _hechos(hechos[c])
            if "WeightedAverage" in c and len(d):
                d = d[(d["end"] - d["start"]).dt.days.between(80, 100)]
            if len(d):
                s = d.groupby("end")["val"].last().sort_index()
                s.index = pd.DatetimeIndex(s.index)
                s.attrs["concepto"] = c
                return s
    return pd.Series(dtype=float, index=pd.DatetimeIndex([]))


def _precio_sin_ajuste(cierre: pd.Series, f: pd.Timestamp, splits: list | None) -> float | None:
    c = cierre.dropna()
    c = c[c.index <= f]
    return float(c.iloc[-1]) * AV.factor_split(splits or [], f) if len(c) else None


def _acciones_en(acc: pd.Series, f: pd.Timestamp) -> float | None:
    a = acc[acc.index <= f + pd.Timedelta(days=60)]   # la portada del 10-Q da las acciones ~1 mes después del cierre
    return float(a.iloc[-1]) if len(a) else None


def recompras(t: str, emp: dict | None, cierre: pd.Series | None, splits: list | None,
              hoy: pd.Timestamp) -> dict | None:
    if not emp or cierre is None or not len(cierre.dropna()):
        return None
    U = UMBRALES
    hechos = emp.get("hechos") or {}
    tri, concepto = None, None
    for c in CONC_PAGO:   # el primer concepto con datos recientes (flujo de caja antes que patrimonio)
        if c in hechos:
            q = trimestres(hechos[c])
            if len(q) and q["fin"].max() >= hoy - pd.DateOffset(months=15):
                tri, concepto = q, c
                break
    acc = _serie_acciones(hechos)
    out = {"concepto": concepto, "eventos": []}
    precio = float(cierre.dropna().iloc[-1])
    if len(acc):
        a_ult = float(acc.iloc[-1])
        f_ult = acc.index[-1]
        out["acciones"], out["acciones_fecha"] = a_ult, str(f_ult.date())
        out["acciones_concepto"] = acc.attrs.get("concepto")
        out["capitalizacion"] = a_ult * AV.factor_split(splits or [], f_ult) * precio   # acciones en la escala de hoy
        prev = acc[acc.index <= f_ult - pd.Timedelta(days=330)]
        if len(prev):
            f0 = prev.index[-1]
            a0 = float(prev.iloc[-1]) * AV.factor_split(splits or [], f0) / AV.factor_split(splits or [], f_ult)
            out["var_acciones_12m"] = a_ult / a0 - 1
            out["acciones_12m_desde"] = str(f0.date())
    if tri is None or tri.empty:
        return out
    tri = tri.copy()
    tri["mcap"] = [(_precio_sin_ajuste(cierre, f, splits) or np.nan) * (_acciones_en(acc, f) or np.nan) for f in tri["fin"]]
    tri["pct"] = tri["importe"] / tri["mcap"]
    out["trimestres"] = tri.tail(8).to_dict("records")
    ult4 = tri.tail(4)
    consecutivos = len(ult4) == 4 and (ult4["fin"].iloc[-1] - ult4["fin"].iloc[0]).days <= 300
    out["ttm"] = float(ult4["importe"].sum()) if consecutivos else None
    out["ttm_hasta"] = str(ult4["fin"].iloc[-1].date()) if len(ult4) else None
    if out.get("ttm") is not None and out.get("capitalizacion"):
        out["yield"] = out["ttm"] / out["capitalizacion"]
    for i in range(len(tri)):
        r = tri.iloc[i]
        if pd.isna(r["publicado"]) or r["publicado"] < hoy - pd.DateOffset(months=24):
            continue
        ant = tri.iloc[max(0, i - 4):i]
        m4 = float(ant["importe"].mean()) if len(ant) else None
        m4p = float(ant["pct"].mean()) if len(ant) and ant["pct"].notna().any() else None
        tri_txt = f"trimestre al {AV._fd(r['fin'])}"
        p = r["pct"] if pd.notna(r["pct"]) else None
        a1, a2 = U["rc_pct"]
        fz, txt = 0, None
        if p is not None and p >= a2:
            fz = 2
        elif p is not None and (p >= a1 or (m4 and r["importe"] >= U["rc_doble"][0] * m4 and p >= U["rc_doble"][1])):
            fz = 1
        if fz:
            txt = (f"Recompra {'fuerte' if fz == 2 else 'alta'}: {AV._num_corto(r['importe'])} $ en el {tri_txt} ({n(100 * p, 2, ' %')} de la "
                   f"capitalización; media de los 4 anteriores {AV._num_corto(m4)} $)")
        elif m4p is not None and m4p >= U["rc_paron"][1] and m4 and r["importe"] < U["rc_paron"][0] * m4:
            fz, txt = 1, (f"Parón de recompras: {AV._num_corto(r['importe'])} $ en el {tri_txt} frente a una media de "
                          f"{AV._num_corto(m4)} $ en los 4 anteriores")
        if fz:
            out["eventos"].append({"fecha": pd.Timestamp(r["publicado"]), "ticker": t, "tipo": "recompra", "fuerza": fz,
                                   "dir": -1 if txt.startswith("Parón") else 1, "especial": None,
                                   "frase": txt + f" (10-Q/10-K presentado el {AV._fd(r['publicado'])}).",
                                   "clave": f"recompra|{t}|{r['fin'].date()}"})
    # programa autorizado: sube el importe autorizado → nuevo programa o ampliación (us-gaap y srt juntos)
    hp = [x for c in CONC_PROG for x in hechos.get(c) or []]
    if hp:
        d = _hechos(hp).sort_values("primera")
        ant = None
        for r in d.to_dict("records"):
            if ant is not None and r["val"] > ant * 1.05 and pd.notna(r["primera"]) and r["primera"] >= hoy - pd.DateOffset(months=24):
                out["eventos"].append({"fecha": pd.Timestamp(r["primera"]), "ticker": t, "tipo": "recompra", "fuerza": 1,
                                       "dir": 1, "especial": None,
                                       "frase": (f"Programa de recompra ampliado o nuevo: autorizado {AV._num_corto(r['val'])} $ "
                                                 f"(antes {AV._num_corto(ant)} $), según el 10-Q/10-K presentado el "
                                                 f"{AV._fd(r['primera'])}."),
                                       "clave": f"recompra_prog|{t}|{pd.Timestamp(r['end']).date()}|{int(r['val'])}"})
            ant = max(ant or 0, r["val"])
        if len(d):
            u = d.sort_values("end").iloc[-1]
            out["autorizado"], out["autorizado_fecha"] = float(u["val"]), str(pd.Timestamp(u["end"]).date())
    rem = hechos.get("us-gaap:StockRepurchaseProgramRemainingAuthorizedRepurchaseAmount1")
    if rem:
        d = _hechos(rem).sort_values("end")
        if len(d):
            out["pendiente"], out["pendiente_fecha"] = float(d["val"].iloc[-1]), str(d["end"].iloc[-1].date())
    return out


# ============================================================================================ todo junto
def calcular(X: dict | None = None, hoy: date | None = None) -> dict:
    """{"activos": {t: {...}}, "eventos": [todas las alertas, 12 meses], "errores": {...}}; nunca lanza por un activo."""
    X = X if X is not None else cargar()
    hoy_ts = pd.Timestamp(hoy or date.today())
    desde = hoy_ts - pd.DateOffset(months=MESES_FICHA)
    A = activos()
    res: dict = {"activos": {}, "eventos": [], "hoy": str(hoy_ts.date()), "errores": {}}
    desc = X.get("descarga_volumen")
    incompleta = pd.Timestamp(str(desc)[:10]) if desc else None
    presentes = None
    if "f13" in X:
        try:
            f13 = X["f13"].assign(period=pd.to_datetime(X["f13"]["period"]))
            presentes = {pd.Timestamp(p): set(g) for p, g in f13.groupby("period")["cik"]}
        except Exception:  # noqa: BLE001
            presentes = None
    for t, (nombre, grupo) in A.items():
        a: dict = {"nombre": nombre, "grupo": grupo, "eventos": [], "errores": {}}
        accion = AV.es_accion(t, {"grupo": grupo, "nombre": nombre})
        cie = X["cierre"][t].dropna() if "cierre" in X and t in X["cierre"] else None
        spl = (X.get("splits") or {}).get(t)
        esp = {}
        try:
            if t.endswith("=F"):
                a["errores"]["volumen"] = "futuro: el volumen es del 1.er vencimiento (cae y salta en cada cambio de contrato); sin alertas de volumen"
            elif "volumen" in X and t in X["volumen"] and cie is not None:
                d = senal_volumen(X["volumen"][t], cie, X.get("alto", {}).get(t) if "alto" in X else None,
                                  X.get("bajo", {}).get(t) if "bajo" in X else None)
                esp = dias_especiales(d.index, (X.get("resultados") or {}).get(t), spl)
                sh = short_finra(X.get("short"), t)
                a["short"] = sh
                a["eventos"] += eventos_volumen(t, d, esp, incompleta, desde, sh)
                a["historico"] = historico_volumen(d, esp)
                dd = d[d.index < incompleta] if incompleta is not None else d   # última sesión COMPLETA
                a["senal"] = dd.tail(1).to_dict("records")[0] | {"fecha": str(dd.index[-1].date())} if len(dd) else None
                a["sin_resultados"] = accion and t not in (X.get("resultados") or {})
            else:
                a["errores"]["volumen"] = X.get("error_volumen") or "sin volumen"
        except Exception as e:  # noqa: BLE001
            a["errores"]["volumen"] = f"{type(e).__name__}: {e}"
        if accion:
            try:
                rc = recompras(t, ((X.get("recompras") or {}).get("empresas") or {}).get(t), cie, spl, hoy_ts)
                a["recompras"] = rc
                if rc:
                    a["eventos"] += rc["eventos"]
                elif "." not in t:
                    a["errores"]["recompras"] = X.get("error_recompras") or "sin datos XBRL"
            except Exception as e:  # noqa: BLE001
                a["errores"]["recompras"] = f"{type(e).__name__}: {e}"
            acc_circ = (a.get("recompras") or {}).get("acciones")
            for k, fn in (("form4", lambda: eventos_form4(t, X["form4"][X["form4"]["ticker"] == t], spl, cie)),
                          ("13f", lambda: eventos_13f(t, X["f13"][X["f13"]["ticker"] == t], cie, spl, acc_circ,
                                                      presentes=presentes)),
                          ("13dg", lambda: eventos_13dg(t, X["dg"]))):
                src = {"form4": "form4", "13f": "f13", "13dg": "dg"}[k]
                if src not in X:
                    a["errores"][k] = X.get(f"error_{src if src != 'f13' else '13f'}") or "sin datos"
                    continue
                try:
                    a["eventos"] += fn()
                except Exception as e:  # noqa: BLE001
                    a["errores"][k] = f"{type(e).__name__}: {e}"
        a["eventos"] = [e for e in a["eventos"] if e["fecha"] >= desde and e["fecha"] <= hoy_ts + pd.Timedelta(days=1)]
        for e in a["eventos"]:
            e.setdefault("nombre", nombre)
            if e.get("precio") is None and cie is not None:
                c = cie[cie.index <= e["fecha"]]
                e["precio"] = float(c.iloc[-1]) if len(c) else None
        a["eventos"].sort(key=lambda e: e["fecha"], reverse=True)
        res["activos"][t] = a
        res["eventos"] += a["eventos"]
    res["eventos"].sort(key=lambda e: (-e["fuerza"], -e["fecha"].value))
    return res


def recientes(R: dict, dias: int = DIAS_RECIENTES, minimo: int = 1) -> list[dict]:
    h = pd.Timestamp(R["hoy"])
    return [e for e in R["eventos"] if e["fuerza"] >= minimo and e["fecha"] > h - pd.Timedelta(days=dias)]


_CACHE: dict = {}


def calcular_seguro(X: dict | None = None, hoy: date | None = None) -> dict | None:
    k = str(hoy or date.today())
    if k in _CACHE:
        return _CACHE[k]
    try:
        R = calcular(cargar(X) if X is not None else cargar(), hoy)
    except Exception:  # noqa: BLE001
        R = None
    _CACHE[k] = R
    return R


# ============================================================================================ HTML
def _chip_f(f: int) -> str:
    return chip({2: "rojo", 1: "ambar"}.get(f, "gris"), FUERZA[f])


def _fila(e: dict, con_activo: bool = True) -> str:
    act = (f"<td><a href='#act-{esc(e['ticker'])}' class='al-link'>{esc(e.get('nombre') or e['ticker'])}</a>"
           f"<span class='muted'> {esc(e['ticker'])}</span></td>") if con_activo else ""
    flecha = {1: "<span class='al-up' aria-label='al alza'>▲</span>", -1: "<span class='al-dn' aria-label='a la baja'>▼</span>"}.get(e.get("dir"), "<span class='muted'>●</span>")
    esp = f" <span class='chip c-gris'>no cuenta: {esc(e['especial'])}</span>" if e.get("especial") else ""
    return (f"<tr><td>{AV._fd(e['fecha'])}</td>{act}<td>{_chip_f(e['fuerza'])}</td><td>{esc(TIPOS.get(e['tipo'], e['tipo']))}</td>"
            f"<td>{flecha} {e['frase']}{esp}</td></tr>")


def bloque_alertas(R: dict | None, donde: str = "hoy") -> str:
    """Bloque «Alertas» (arriba en «Hoy» y en «Mis activos»): últimos 7 días, ordenadas por fuerza; luego 90 días."""
    if not R:
        return '<div class="card al"><h3>Alertas de flujos en tus activos</h3><p class="nd">s/d (no se pudieron calcular).</p></div>'
    rec = recientes(R, DIAS_RECIENTES)
    vis = {e["clave"] for e in rec}
    mas = [e for e in recientes(R, DIAS_LISTA) if e["clave"] not in vis]
    cab = "<thead><tr><th>Fecha</th><th>Activo</th><th>Fuerza</th><th>Tipo</th><th>Qué pasó</th></tr></thead>"
    nf = sum(1 for e in rec if e["fuerza"] == 2)
    if rec:
        t1 = f"<div class='tw'><table class='num al-t' data-no-plegar>{cab}<tbody>{''.join(_fila(e) for e in rec)}</tbody></table></div>"
    else:
        t1 = f"<p>{chip('verde', 'sin alertas')} Ninguna alerta en los últimos {DIAS_RECIENTES} días.</p>"
    t2 = (f"<details><summary>Ver {len(mas)} alertas más (hasta {DIAS_LISTA} días)</summary><div class='tw'><table class='num al-t'>"
          f"{cab}<tbody>{''.join(_fila(e) for e in mas)}</tbody></table></div></details>") if mas else ""
    ult = None
    try:
        ult = max(a["senal"]["fecha"] for a in R["activos"].values() if a.get("senal"))   # última sesión completa
    except Exception:  # noqa: BLE001
        pass
    # fuentes que fallan (en algún activo): se dicen, para no confundir «sin alertas» con «sin datos»
    rotas = sorted({k for a in R.get("activos", {}).values() for k, v in (a.get("errores") or {}).items()
                    if not str(v).startswith("futuro") and not str(v).startswith("sin datos XBRL")})
    if rotas:
        t1 += f"<p class='nd small'>s/d en algún activo: {esc(', '.join(rotas))} (ver «Flujos fuertes» de cada ficha).</p>"
    return (f'<div class="card al" id="alertas-{esc(donde)}"><h3>Alertas de flujos en tus activos <span class="muted">'
            f'({len(rec)} en {DIAS_RECIENTES} días, {nf} fuertes · volumen hasta la sesión completa del {esc(AV._fd(ult) if ult else "s/d")})</span></h3>'
            f'<p class="disc small"><strong>{esc(AVISO)}</strong></p>{t1}{t2}'
            '<p class="note">Volumen: sesión frente a su media de 3 meses (no cuentan la sesión en curso, los vencimientos '
            'trimestrales, Russell, MSCI ni los días de resultados). 13F: carteras trimestrales con hasta 45 días de '
            'retraso. 13D/13G: quien cruza o cambia una participación del 5 %+ (días de retraso; 13D = no pasivo). '
            'Form 4: solo compras en mercado abierto y ventas grandes SIN plan 10b5-1 (las programadas, concesiones y '
            'retenciones no alertan). Recompras: 10-Q/10-K. Pulsa un activo para su ficha («Flujos fuertes»).</p></div>')


def marcas(a: dict | None) -> list[dict]:
    """Marcas para el gráfico de precio de la ficha: ◆ volumen, ■ institucional/recompra (Form 4 ya sale como ▲▼)."""
    if not a:
        return []
    out = []
    for e in a.get("eventos") or []:
        if e["fuerza"] < 1 or e["tipo"] == "form4" or e.get("precio") is None:
            continue
        forma = "rombo" if e["tipo"].startswith("volumen") else "cuadro"
        cls = {1: "al-ms", -1: "al-mb"}.get(e.get("dir"), "al-mn") if forma == "rombo" else "al-mi"
        import html as _h
        import re as _re
        tip = _h.unescape(_re.sub(r"<[^>]+>", "", f"{AV._fd(e['fecha'])} · {TIPOS.get(e['tipo'])} ({FUERZA[e['fuerza']]}): "
                                                   f"{e['frase']}"))   # texto plano: grafico() lo escapa
        out.append({"fecha": e["fecha"], "precio": e["precio"], "forma": forma, "cls": cls, "tip": tip,
                    "fuerte": e["fuerza"] == 2})
    return out


def _tabla_recompras(rc: dict | None, err: str | None) -> str:
    if not rc:
        return f"<p class='nd'>Recompras: s/d ({esc(err or 'sin datos')}).</p>"
    filas = "".join(f"<tr><td>{AV._fd(q['fin'])}</td><td>{AV._num_corto(q['importe'])} $</td>"
                    f"<td>{n(100 * q['pct'], 2, ' %') if q.get('pct') is not None and not np.isnan(q['pct']) else '—'}</td>"
                    f"<td>{AV._fd(q['publicado'])}</td></tr>" for q in reversed(rc.get("trimestres") or []))
    yl = rc.get("yield")
    va = rc.get("var_acciones_12m")
    resumen = (f"<div class='tw'><table class='num'><tbody>"
               f"<tr><td>Recomprado en 12 meses (4 trimestres hasta {AV._fd(rc.get('ttm_hasta'))})</td><td><strong>{AV._num_corto(rc.get('ttm'))} $</strong></td></tr>"
               f"<tr><td data-tip='Recompras de 12 meses / capitalización actual (acciones en circulación × precio)'>Rentabilidad por recompra (buyback yield)</td><td><strong>{n(100 * yl, 2, ' %') if yl is not None else '<span class=nd>s/d</span>'}</strong>"
               f" <span class='muted'>capitalización ≈ {AV._num_corto(rc.get('capitalizacion'))} $</span></td></tr>"
               f"<tr><td data-tip='Recompras menos acciones nuevas (sobre todo pagos en acciones a empleados): si baja, la recompra neta reduce el número de acciones'>Acciones en circulación: cambio 12 meses</td><td><strong>{n(100 * va, 2, ' %', True) if va is not None else '<span class=nd>s/d</span>'}</strong>"
               f" <span class='muted'>{AV._num_corto(rc.get('acciones'))} al {AV._fd(rc.get('acciones_fecha'))} (desde {AV._fd(rc.get('acciones_12m_desde'))})</span></td></tr>"
               + (f"<tr><td>Programa autorizado (último dato, {AV._fd(rc.get('autorizado_fecha'))}) / pendiente ({AV._fd(rc.get('pendiente_fecha'))})</td>"
                  f"<td>{AV._num_corto(rc.get('autorizado'))} $ / {AV._num_corto(rc.get('pendiente'))} $</td></tr>"
                  if rc.get("autorizado") or rc.get("pendiente") else "")
               + "</tbody></table></div>")
    tab = (f"<div class='tw'><table class='num'><thead><tr><th>Trimestre al</th><th>Recompra</th><th>% capitalización</th>"
           f"<th>Publicado</th></tr></thead><tbody>{filas}</tbody></table></div>") if filas else "<p class='muted'>Sin trimestres.</p>"
    return (resumen + tab + f"<p class='small'>SEC XBRL ({esc((rc.get('concepto') or '').split(':')[-1])}): importe pagado en el "
            "trimestre (si la empresa solo da el acumulado del año, diferencia con el trimestre anterior). Capitalización = "
            "acciones en circulación de la portada del 10-Q/10-K × precio. Una recompra también compensa la emisión "
            "a empleados: el cambio de acciones en circulación dice cuánto se reduce de verdad.</p>")


def _nota_historico(hv: dict | None) -> str:
    if not hv:
        return ""
    cl = hv["clases"]

    def m(c, k):
        x = cl[c][k]
        return (f"{n(100 * x['media'], 1, ' %', True)} ± {n(100 * x['sd'], 1, '')}" if x.get("media") is not None and x.get("sd") is not None
                else "—")
    pa = (hv["n"] / hv["anios"]) if hv["anios"] else None
    b = hv["base"]
    return (f"<p class='small al-hist'><strong>Historia (descriptiva, NO es una validación):</strong> desde {AV._fd(hv['desde'])} "
            f"estas reglas habrían dado {hv['n']} alertas de volumen de un día (≈ {n(pa, 1, '')} al año). 20 sesiones después, "
            f"el precio de media (± desv. típica): con subida fuerte {m('sube', 20)} (n = {cl['sube']['n']}); con caída fuerte "
            f"{m('baja', 20)} (n = {cl['baja']['n']}); sin movimiento {m('plano', 20)} (n = {cl['plano']['n']}); cualquier día "
            f"{n(100 * b[20]['media'], 1, ' %', True)} ± {n(100 * b[20]['sd'], 1, '')}. La dispersión es mucho mayor que las "
            "diferencias: con pocos casos, ruido. 1 y 5 sesiones en docs/panel/alertas_v1.md.</p>")


def ficha_flujos(t: str, R: dict | None) -> str:
    """Sección «Flujos fuertes» de la ficha: alertas de 12 meses, recompras, contexto de cortos e historia descriptiva."""
    if not R or t not in R.get("activos", {}):
        return '<div class="dblk wide al"><h4>Flujos fuertes (12 meses)</h4><p class="nd">s/d.</p></div>'
    a = R["activos"][t]
    ev = [e for e in a["eventos"] if e["fuerza"] >= 1 or e.get("especial") or e["tipo"] == "13dg"]
    filas = "".join(_fila(e, False) for e in ev)
    cab = "<thead><tr><th>Fecha</th><th>Fuerza</th><th>Tipo</th><th>Qué pasó</th></tr></thead>"
    tab = (f"<div class='tw'><table class='num al-t'>{cab}<tbody>{filas}</tbody></table></div>" if filas else
           "<p class='muted'>Ninguna alerta en 12 meses.</p>")
    errs = "; ".join(f"{k}: {v}" for k, v in (a.get("errores") or {}).items() if k != "recompras")
    extra = ""
    sh = a.get("short")
    if sh is not None and len(sh):
        u = sh.iloc[-1]
        extra += (f"<p class='small'>Ventas en corto diarias (FINRA Reg SHO, {AV._fd(sh.index[-1])}): {n(100 * u['pct'], 0)} del "
                  f"volumen declarado a FINRA (media 3 meses {n(100 * u['media'], 0) if pd.notna(u['media']) else 's/d'}). Es sobre todo "
                  "contrapartida de creadores de mercado (40-60 % es normal); no son posiciones cortas.</p>")
    s = a.get("senal")
    if s:
        extra += (f"<p class='small'>Última sesión ({AV._fd(s['fecha'])}): × {n(s.get('ratio'), 2, '')} la media de 3 meses, "
                  f"z robusto {n(s.get('z'), 1, '', True)}, precio {n(100 * s['ret'], 1, ' %', True) if pd.notna(s.get('ret')) else 's/d'}.</p>")
    if a.get("sin_resultados"):
        extra += "<p class='small'>Sin fechas de resultados (no presenta 8-K): los días de resultados no se excluyen.</p>"
    rc = ""
    if a.get("recompras") is not None or "recompras" in (a.get("errores") or {}):
        rc = "<h4>Recompras de la empresa</h4>" + _tabla_recompras(a.get("recompras"), (a.get("errores") or {}).get("recompras"))
    leyenda = ('<p class="small">En el gráfico de arriba: <span class="al-k s">◆</span> volumen anormal con subida · '
               '<span class="al-k b">◆</span> con caída · <span class="al-k n">◆</span> sin movimiento · '
               '<span class="al-k i">■</span> institucional o recompra (13F, 13D/G, recompras); los grandes = fuertes. '
               'Los días especiales («no cuenta») no se marcan.</p>')
    return (f'<div class="dblk wide al" id="flujos-{esc(t)}"><h4>Flujos fuertes (12 meses) · alertas descriptivas</h4>'
            f'<p class="disc small">{esc(AVISO)}</p>{leyenda}{tab}'
            + (f"<p class='nd small'>s/d: {esc(errs)}</p>" if errs else "") + extra + _nota_historico(a.get("historico"))
            + rc + "</div>")


CSS = """
.al-t td{vertical-align:top}.al-t td:last-child{min-width:280px;white-space:normal}.al-t td:first-child{white-space:nowrap}
.al-up{color:var(--good)}.al-dn{color:var(--crit)}
.al-ms{fill:var(--s3);stroke:var(--surface);stroke-width:1}.al-mb{fill:var(--s2);stroke:var(--surface);stroke-width:1}
.al-mn{fill:var(--ink2);stroke:var(--surface);stroke-width:1}.al-mi{fill:var(--warn);stroke:var(--ink2);stroke-width:1}
.al-k{font-weight:700}.al-k.s{color:var(--s3)}.al-k.b{color:var(--s2)}.al-k.n{color:var(--ink2)}.al-k.i{color:var(--warn)}
"""
JS = """
(function(){document.addEventListener('click',function(e){var a=e.target.closest('a.al-link');if(!a)return;e.preventDefault();
var id=a.getAttribute('href').slice(1),d=document.getElementById(id);if(!d)return;var s=d.closest('main>section');
if(s&&s.hidden){var b=document.querySelector('nav.tabs button[data-t="'+s.id+'"]');if(b)b.click()}
d.open=true;setTimeout(function(){d.scrollIntoView({behavior:'smooth'});try{history.replaceState(null,'','#'+id)}catch(x){}},30)});})();
"""


# ============================================================================================ notificación macOS
def _estado_path() -> Path:
    return root() / "alertas" / "notificadas.json"


def notificar_activo() -> bool:
    """Se desactiva con FIN_ALERTAS_NOTIFICAR=0 o con {"notificar": false} en $FIN_DATA_ROOT/config/alertas.json."""
    if os.environ.get("FIN_ALERTAS_NOTIFICAR", "").strip().lower() in ("0", "no", "false", "off"):
        return False
    try:
        cfg = json.loads((root() / "config" / "alertas.json").read_text())
        return bool(cfg.get("notificar", True))
    except Exception:  # noqa: BLE001
        return True


def nuevas_para_notificar(eventos: list[dict], estado: dict, hoy: pd.Timestamp, dias: int = 5) -> list[dict]:
    """Alertas FUERTES de los últimos `dias` días que no se han notificado antes (por clave: no se repiten)."""
    return [e for e in eventos if e["fuerza"] == 2 and e["fecha"] > hoy - pd.Timedelta(days=dias)
            and e["clave"] not in estado]


def mensaje(nuevas: list[dict], max_items: int = 3) -> str:
    import html as _html
    import re
    partes = []
    for e in nuevas[:max_items]:
        txt = _html.unescape(re.sub(r"<[^>]+>", "", e["frase"]))
        # primera frase, sin cortar en abreviaturas de sociedades («Inc.», «Corp.», «Co.», «Ltd.»…)
        txt = re.split(r"(?<!\bInc)(?<!\bCorp)(?<!\bCo)(?<!\bLtd)(?<!\bPlc)(?<!\bLLC)(?<!\bL\.P)(?<!\bN\.V)(?<!\bS\.A)\. ", txt)[0]
        partes.append(f"{e['ticker']}: {txt}")
    m = f"{len(nuevas)} alerta{'s' if len(nuevas) != 1 else ''} fuerte{'s' if len(nuevas) != 1 else ''}: " + " · ".join(partes)
    if len(nuevas) > max_items:
        m += f" · y {len(nuevas) - max_items} más (panel, «Hoy»)"
    return m.replace('"', "'").replace("\\", "/").replace("\n", " ").replace("−", "-")[:400]


def notificar(hoy: date | None = None, estado_path: Path | None = None) -> str:
    """Devuelve el texto de la notificación ('' si no hay nada nuevo o está desactivada) y apunta lo notificado."""
    if not notificar_activo():
        return ""
    R = calcular(cargar(), hoy)
    h = pd.Timestamp(R["hoy"])
    p = estado_path or _estado_path()
    try:
        est = json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        est = {}
    nuevas = nuevas_para_notificar(R["eventos"], est, h)
    if not nuevas:
        return ""
    # se apunta ANTES de que actualizar.sh la muestre con osascript: si la notificación falla, esa alerta no se repite
    # (sigue visible en el panel). Elegido a propósito para no avisar dos veces (Validador 17-nov, H4).
    for e in nuevas:
        est[e["clave"]] = str(h.date())
    est = {k: v for k, v in est.items() if pd.Timestamp(v) > h - pd.Timedelta(days=400)}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(est, indent=0))
    return mensaje(nuevas)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Alertas de flujos de «Mis activos» (descriptivas)")
    ap.add_argument("--notificar", action="store_true", help="imprime el texto de la notificación de alertas fuertes nuevas")
    ap.add_argument("--listar", action="store_true", help="lista las alertas de los últimos 7 días")
    a = ap.parse_args(argv)
    if a.notificar:
        print(notificar())
        return
    R = calcular(cargar())
    for e in recientes(R, DIAS_RECIENTES if a.listar else DIAS_LISTA):
        import re
        print(f"{e['fecha'].date()} {e['ticker']:7s} {FUERZA[e['fuerza']]:9s} {e['tipo']:12s} {re.sub(r'<[^>]+>', '', e['frase'])}")


if __name__ == "__main__":
    main()
