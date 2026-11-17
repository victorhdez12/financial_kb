"""Ficha v2 de «Mis activos»: volumen negociado, dónde compraron/vendieron las manos fuertes y opinión de analistas.

DESCRIPTIVO. Nada de esto es una señal de cartera ni se ha validado como predictor en este proyecto. Definiciones y
limitaciones: docs/panel/activos_v2.md. Datos de terceros, guardados FUERA de git ($FIN_DATA_ROOT):
  * mercados/volumen/ (Yahoo: volumen diario, cierre ajustado solo por splits, splits)   ← src/ingest/yahoo_precios.py
  * sec_form4/operaciones.parquet (SEC Form 4, todas las líneas no derivadas)            ← src/ingest/sec_form4_detalle.py
  * sec_13f/posiciones.parquet (SEC 13F, carteras trimestrales de gestoras > 100 M$)     ← src/ingest/sec_13f.py
  * mercados/analistas/analistas.json (Yahoo: consenso, precios objetivo, cambios)       ← src/ingest/yahoo_analistas.py
Si una fuente falla, su bloque dice «s/d» y el resto de la ficha (y del panel) sigue.

1. Volumen: último volumen (sesión del último precio), media de las 20 sesiones ANTERIORES y de las 63 anteriores
   (≈ 3 meses), cociente último / media 20 s, e importe negociado = volumen × cierre (en la moneda del activo; en los
   futuros el volumen son contratos y no se convierte a dinero).
2. Directivos (Form 4): solo consejeros y directivos (los accionistas de > 10 % que no lo son se etiquetan aparte y no
   entran en las medias). Tipos: «compra» = código P (mercado abierto); «venta» = S sin plan; «venta con plan 10b5-1» =
   S con la casilla 10b5-1 o una nota de esa línea que lo menciona (programada de antemano: poco informativa); lo
   demás (ejercicio de opciones M/X/C, concesión A, retención fiscal F, regalo G, otros) se cuenta pero no se pinta.
   Precios y nº de acciones se pasan a la escala de los splits de Yahoo (como el gráfico). Se descartan líneas con
   precio ≤ 0 o a más de un 50 % del cierre de Yahoo de ese día (errores de tecleo). Precio medio PONDERADO por
   acciones de 12 meses (fecha de la operación) de compras, ventas sin plan y todas las ventas.
3. 13F (aproximación): acciones de cada gestora al cierre de cada trimestre (presentado hasta 45 días después);
   cambio de acciones entre trimestres × precio medio de cierre del trimestre = importe aproximado. NO es el precio al
   que operaron (el 13F no lo dice). Se descartan líneas cuyo valor declarado / acciones se aleja > 50 % del cierre
   del trimestre (errores de unidades). Muchos de los mayores son fondos indexados: sus cambios son flujos, no opinión.
4. Analistas (Yahoo): opinión de terceros, no validada; el consenso tiene un sesgo optimista conocido.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.report.panel_paises import esc, n

SESIONES_20, SESIONES_3M = 20, 63
TOL_PRECIO = 0.5
MESES_GRAF = 12
N_TABLA = 15
CAT = {"compra": "compra (P)", "venta": "venta (S)", "venta_plan": "venta con plan 10b5-1", "opciones": "opciones/derivados",
       "concesion": "concesión (A)", "fiscal": "retención fiscal (F)", "regalo": "regalo (G)", "otro": "otras"}
AVISO_ANALISTAS = ("Opinión de terceros, no validada; el consenso de analistas tiene sesgo optimista conocido "
                   "(casi nunca recomiendan vender y los precios objetivo suelen quedar por encima del precio).")
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def root() -> Path:
    return Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser()


def _fd(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    d = pd.Timestamp(x)
    return f"{d.day}-{MESES[d.month - 1]}-{d.year}"


# --------------------------------------------------------------------------------------------- carga (tolerante)
def cargar() -> dict:
    """Cada fuente por separado: si una falla queda {"error": ...} y el resto sigue."""
    r = root()
    out: dict = {}
    try:
        dv = r / "mercados" / "volumen"
        out["volumen"] = pd.read_parquet(dv / "volumen_diario.parquet")
        out["cierre"] = pd.read_parquet(dv / "cierre_diario.parquet")
        sp = json.loads((dv / "splits.json").read_text())
        out["splits"], out["descarga_volumen"] = sp.get("splits") or {}, sp.get("descarga")
    except Exception as e:  # noqa: BLE001
        out["error_volumen"] = f"{type(e).__name__}: {e}"
    try:
        out["form4"] = pd.read_parquet(r / "sec_form4" / "operaciones.parquet")
        out["meta_form4"] = json.loads((r / "sec_form4" / "meta.json").read_text())
    except Exception as e:  # noqa: BLE001
        out["error_form4"] = f"{type(e).__name__}: {e}"
    try:
        out["f13"] = pd.read_parquet(r / "sec_13f" / "posiciones.parquet")
    except Exception as e:  # noqa: BLE001
        out["error_13f"] = f"{type(e).__name__}: {e}"
    try:
        out["analistas"] = json.loads((r / "mercados" / "analistas" / "analistas.json").read_text())
    except Exception as e:  # noqa: BLE001
        out["error_analistas"] = f"{type(e).__name__}: {e}"
    return out


# --------------------------------------------------------------------------------------------- 1. volumen
def volumen_resumen(vol: pd.Series, cierre: pd.Series | None, es_futuro: bool = False) -> dict | None:
    v = vol.dropna()
    v = v[v >= 0]
    if len(v) < SESIONES_20 + 1:
        return None
    ult, f = float(v.iloc[-1]), v.index[-1]
    prev = v.iloc[:-1]
    m20, m3m = float(prev.iloc[-SESIONES_20:].mean()), float(prev.iloc[-SESIONES_3M:].mean())
    out = {"fecha": str(f.date()), "ultimo": ult, "media_20": m20, "media_3m": m3m,
           "ratio_20": ult / m20 if m20 > 0 else None, "ratio_3m": ult / m3m if m3m > 0 else None,
           "n_3m": int(min(len(prev), SESIONES_3M)), "importe": None, "importe_20": None, "es_futuro": es_futuro}
    if cierre is not None and not es_futuro:
        c = cierre.reindex(v.index)
        imp = (v * c).dropna()
        if len(imp) and imp.index[-1] == f:
            out["importe"] = float(imp.iloc[-1])
            out["importe_20"] = float(imp.iloc[:-1].iloc[-SESIONES_20:].mean()) if len(imp) > 1 else None
    return out


# --------------------------------------------------------------------------------------------- 2. directivos
def clasificar(code, plan) -> str:
    c = (code or "").upper()
    if c == "P":
        return "compra"
    if c == "S":
        return "venta_plan" if bool(plan) else "venta"
    if c in ("M", "X", "C", "O", "E", "H"):
        return "opciones"
    return {"A": "concesion", "F": "fiscal", "G": "regalo"}.get(c, "otro")


def factor_split(splits: list[dict], fecha: pd.Timestamp) -> float:
    """Producto de los factores de los splits POSTERIORES a la fecha (para pasar a la escala actual de Yahoo)."""
    f = 1.0
    for s in splits or []:
        if pd.Timestamp(s["fecha"]) > fecha:
            f *= float(s["factor"])
    return f


def preparar_ops(ops: pd.DataFrame, splits: list[dict] | None = None, cierre: pd.Series | None = None) -> pd.DataFrame:
    """Clasifica, pasa a escala de splits y descarta precios absurdos (≤ 0 en P/S o > ±50 % del cierre del día)."""
    if ops is None or ops.empty:
        return pd.DataFrame(columns=list(ops.columns if ops is not None else []) + ["cat", "precio_aj", "acciones_aj"])
    d = ops.copy()
    d["trans_date"] = pd.to_datetime(d["trans_date"], errors="coerce")
    d = d[d["trans_date"].notna()]
    d["cat"] = [clasificar(c, p) for c, p in zip(d["code"], d["plan_10b5_1"])]
    fac = d["trans_date"].map(lambda x: factor_split(splits or [], x))
    d["precio_aj"] = pd.to_numeric(d["price"], errors="coerce") / fac
    d["acciones_aj"] = pd.to_numeric(d["shares"], errors="coerce") * fac
    ps = d["cat"].isin(["compra", "venta", "venta_plan"])
    malo = ps & ~((d["precio_aj"] > 0) & (d["acciones_aj"] > 0))
    if cierre is not None and len(cierre.dropna()):
        c = cierre.dropna().sort_index()
        ref = pd.Series(cierre_en(c, d["trans_date"]), index=d.index)
        dentro = (d["trans_date"] >= c.index[0]) & (d["trans_date"] <= c.index[-1] + pd.Timedelta(days=5))
        malo |= ps & dentro & ((d["precio_aj"] / ref - 1).abs() > TOL_PRECIO)
    d["descartada"] = malo
    d["importe"] = d["precio_aj"] * d["acciones_aj"]
    return d


def cierre_en(c: pd.Series, fechas: pd.Series) -> np.ndarray:
    """Último cierre <= cada fecha (NaN si la fecha es anterior al primer cierre)."""
    ix = np.asarray(c.index.values, dtype="datetime64[ns]")
    f = np.asarray(pd.to_datetime(fechas).values, dtype="datetime64[ns]")
    k = np.searchsorted(ix, f, side="right") - 1
    v = np.asarray(c.values, dtype=float)
    return np.where(k >= 0, v[np.clip(k, 0, len(v) - 1)], np.nan)


def _directivo(d: pd.DataFrame) -> pd.Series:
    return d["director"].astype(bool) | d["officer"].astype(bool)


def media_ponderada(precio: pd.Series, peso: pd.Series) -> float | None:
    m = precio.notna() & peso.notna() & (peso > 0)
    w = peso[m].sum()
    return float((precio[m] * peso[m]).sum() / w) if w > 0 else None


def medias_12m(d: pd.DataFrame, hoy: pd.Timestamp, precio_actual: float | None, dias: int = 365) -> dict:
    x = d[(~d["descartada"]) & _directivo(d) & (d["trans_date"] > hoy - pd.Timedelta(days=dias))
          & (d["trans_date"] <= hoy)]
    out = {}
    for k, cats in (("compras", ["compra"]), ("ventas_sin_plan", ["venta"]), ("ventas", ["venta", "venta_plan"])):
        y = x[x["cat"].isin(cats)]
        pm = media_ponderada(y["precio_aj"], y["acciones_aj"])
        out[k] = {"precio_medio": pm, "acciones": float(y["acciones_aj"].sum()), "importe": float(y["importe"].sum()),
                  "lineas": int(len(y)), "personas": int(y["owner_cik"].nunique()),
                  "vs_actual": (100 * (precio_actual / pm - 1)) if pm and precio_actual else None}
    out["otras"] = {CAT[c]: int((x["cat"] == c).sum()) for c in ("opciones", "concesion", "fiscal", "regalo", "otro")
                    if (x["cat"] == c).any()}
    return out


def cargo(r) -> str:
    t = r.get("title")
    if isinstance(t, str) and t.strip():
        return "directivo (cargo en las notas del Form 4)" if t.strip().lower() == "see remarks" else t.strip()
    if r.get("director"):
        return "consejero"
    if r.get("officer"):
        return "directivo"
    return "accionista > 10 %" if r.get("ten_pct") else "—"


def agrupar(d: pd.DataFrame) -> pd.DataFrame:
    """Una fila por persona, fecha y tipo (un Form 4 trae a menudo muchas líneas a precios distintos el mismo día)."""
    x = d[d["cat"].isin(["compra", "venta", "venta_plan"]) & ~d["descartada"]]
    if x.empty:
        return pd.DataFrame(columns=["trans_date", "cat", "owner_name", "cargo", "precio", "acciones", "importe",
                                     "directivo", "filing_date"])
    x = x.assign(cargo=[cargo(r) for r in x.to_dict("records")], directivo=_directivo(x), pxa=x["precio_aj"] * x["acciones_aj"])
    g = x.groupby(["trans_date", "cat", "owner_cik"], as_index=False).agg(
        owner_name=("owner_name", "first"), cargo=("cargo", "first"), acciones=("acciones_aj", "sum"),
        pxa=("pxa", "sum"), directivo=("directivo", "max"), filing_date=("filing_date", "max"))
    g["precio"] = g["pxa"] / g["acciones"]
    g["importe"] = g["pxa"]
    return g.drop(columns="pxa").sort_values("trans_date", ascending=False)


# --------------------------------------------------------------------------------------------- 3. 13F
def precio_trimestre(cierre: pd.Series, periodo: pd.Timestamp, splits: list[dict] | None = None) -> float | None:
    """Media de los cierres del trimestre, en la escala de ENTONCES (se deshace el ajuste de splits posteriores)."""
    p = pd.Timestamp(periodo).to_period("Q")
    x = cierre.dropna()
    x = x[(x.index.to_period("Q") == p)]
    return float(x.mean()) * factor_split(splits or [], pd.Timestamp(periodo)) if len(x) else None


def resumen_13f(pos: pd.DataFrame, cierre: pd.Series | None, n_top: int = 10, n_trim: int = 4,
                splits: list[dict] | None = None) -> dict | None:
    if pos is None or pos.empty:
        return None
    d = pos.copy()
    d["period"] = pd.to_datetime(d["period"])
    pers = sorted(d["period"].dropna().unique())[-(n_trim + 1):]
    d = d[d["period"].isin(pers)]
    if cierre is not None and len(cierre.dropna()):   # errores de unidades: valor/acciones lejos del cierre del trimestre
        c = cierre.dropna()
        fin = {p: c[c.index <= p].iloc[-1] * factor_split(splits or [], pd.Timestamp(p)) if (c.index <= p).any() else np.nan
               for p in pers}
        ref = d["period"].map(fin)
        imp = d["value"] / d["shares"]
        d = d[ref.isna() | ((imp / ref - 1).abs() <= TOL_PRECIO)]
    if d.empty:
        return None
    pv = d.pivot_table(index="cik", columns="period", values="shares", aggfunc="sum")
    nombres = d.sort_values("filing_date").groupby("cik")["gestor"].last()
    ult = pers[-1]
    if ult not in pv:
        return None
    top = pv[ult].dropna().sort_values(ascending=False).head(n_top).index
    pm = {p: (precio_trimestre(cierre, p, splits) if cierre is not None else None) for p in pers}
    filas = []
    for k in top:
        cambios = []
        for a, b in zip(pers[:-1], pers[1:]):
            sa, sb = pv.at[k, a] if a in pv else np.nan, pv.at[k, b]
            if np.isnan(sb):
                cambios.append(None)
                continue
            ds = sb - (0.0 if np.isnan(sa) else sa)
            cambios.append({"periodo": str(pd.Timestamp(b).date()), "delta": float(ds), "nueva": bool(np.isnan(sa)),
                            "pct": (100 * ds / sa) if not np.isnan(sa) and sa > 0 else None,
                            "importe_aprox": float(ds * pm[b]) if pm.get(b) else None})
        filas.append({"gestor": nombres.get(k, k), "acciones": float(pv.at[k, ult]), "cambios": cambios})
    tot = {str(pd.Timestamp(p).date()): {"gestores": int(pv[p].notna().sum()), "acciones": float(pv[p].sum()),
                                          "precio_medio": pm.get(p)} for p in pers}
    # cambio agregado solo con gestores presentes en los dos trimestres (si no, entra quien empieza a declarar)
    agg = []
    for a, b in zip(pers[:-1], pers[1:]):
        both = pv[[a, b]].dropna()
        ds = both[b] - both[a]
        agg.append({"periodo": str(pd.Timestamp(b).date()), "gestores_comunes": int(len(both)),
                    "suben": int((ds > 0).sum()), "bajan": int((ds < 0).sum()), "delta": float(ds.sum()),
                    "importe_aprox": float(ds.sum() * pm[b]) if pm.get(b) else None, "precio_medio": pm.get(b)})
    return {"ultimo": str(pd.Timestamp(ult).date()), "periodos": [str(pd.Timestamp(p).date()) for p in pers],
            "top": filas, "totales": tot, "agregado": agg}


# --------------------------------------------------------------------------------------------- 4. analistas
def resumen_analistas(a: dict | None, precio: float | None, hoy: pd.Timestamp, dias: int = 90) -> dict | None:
    if not a:
        return None
    tr = next((t for t in a.get("tendencia") or [] if t.get("period") == "0m"), None)
    cons = None
    if tr:
        c = (tr.get("strongBuy") or 0) + (tr.get("buy") or 0)
        m = tr.get("hold") or 0
        v = (tr.get("sell") or 0) + (tr.get("strongSell") or 0)
        cons = {"comprar": c, "mantener": m, "vender": v, "total": c + m + v}
    obj = {}
    for k, src in (("medio", "targetMeanPrice"), ("alto", "targetHighPrice"), ("bajo", "targetLowPrice")):
        x = a.get(src)
        obj[k] = {"precio": x, "vs_actual": 100 * (x / precio - 1) if x and precio else None}
    cambios = [c for c in a.get("cambios") or [] if pd.Timestamp(c["fecha"]) > hoy - pd.Timedelta(days=dias)]
    # primero los que cambian algo (sube/baja/inicia), luego los más recientes; la tabla va por fecha
    clave = sorted(cambios, key=lambda c: (c.get("accion") not in ("up", "down", "init"), c["fecha"]), reverse=False)
    imp = [c for c in clave if c.get("accion") in ("up", "down", "init")]
    resto = sorted([c for c in cambios if c not in imp], key=lambda c: c["fecha"], reverse=True)
    tabla = sorted((imp + resto)[:10], key=lambda c: c["fecha"], reverse=True)
    return {"consenso": cons, "n_analistas": a.get("numberOfAnalystOpinions"), "media_1_5": a.get("recommendationMean"),
            "clave": a.get("recommendationKey"), "objetivo": obj, "cambios": tabla,
            "n_suben": sum(1 for c in cambios if c.get("accion") == "up"),
            "n_bajan": sum(1 for c in cambios if c.get("accion") == "down")}


# --------------------------------------------------------------------------------------------- cálculo por activo
def es_accion(t: str, r: dict) -> bool:
    return r.get("grupo") in ("Acciones", "Agro / pesticidas", "Oro y materias primas") and "ETF" not in (r.get("nombre") or "") \
        and not t.endswith("=F")


def calcular(t: str, r: dict, X: dict, hoy: date | None = None) -> dict:
    hoy_ts = pd.Timestamp(hoy or date.today())
    out: dict = {"accion": es_accion(t, r), "futuro": t.endswith("=F")}
    cie = None
    try:
        if "volumen" in X and t in X["volumen"]:
            cie = X["cierre"][t].dropna() if t in X["cierre"] else None
            out["vol"] = volumen_resumen(X["volumen"][t], cie, out["futuro"])
            f0 = hoy_ts - pd.DateOffset(months=MESES_GRAF)
            v = X["volumen"][t].dropna()
            out["serie_vol"] = v[v.index > f0]
            out["serie_px"] = cie[cie.index > f0] if cie is not None else None
            out["descarga_volumen"] = X.get("descarga_volumen")
        else:
            out["error_vol"] = X.get("error_volumen") or "sin volumen para este activo"
    except Exception as e:  # noqa: BLE001
        out["error_vol"] = f"{type(e).__name__}: {e}"
    if not out["accion"]:
        return out
    precio = r.get("precio")
    try:
        if "form4" not in X:
            out["error_form4"] = X.get("error_form4") or "sin datos"
        else:
            ops = X["form4"][X["form4"]["ticker"] == t]
            if ops.empty:
                out["error_form4"] = ("no presenta Form 4 (no cotiza en EE. UU.)" if "." in t else
                                      "sin Form 4 en el periodo descargado")
            else:
                d = preparar_ops(ops, (X.get("splits") or {}).get(t), cie)
                out["medias"] = medias_12m(d, hoy_ts, precio)
                out["ops"] = agrupar(d)
                out["descartadas"] = int(d["descartada"].sum())
                out["meta_form4"] = X.get("meta_form4") or {}
    except Exception as e:  # noqa: BLE001
        out["error_form4"] = f"{type(e).__name__}: {e}"
    try:
        if "f13" not in X:
            out["error_13f"] = X.get("error_13f") or "sin datos"
        else:
            r13 = resumen_13f(X["f13"][X["f13"]["ticker"] == t], cie, splits=(X.get("splits") or {}).get(t))
            if r13 is None:
                out["error_13f"] = "sin carteras 13F con esta acción (extranjera o cotiza desde hace poco)"
            out["f13"] = r13
    except Exception as e:  # noqa: BLE001
        out["error_13f"] = f"{type(e).__name__}: {e}"
    try:
        a = ((X.get("analistas") or {}).get("acciones") or {}).get(t)
        out["analistas"] = resumen_analistas(a, precio, hoy_ts)
        out["descarga_analistas"] = (X.get("analistas") or {}).get("descarga")
        if out["analistas"] is None:
            out["error_analistas"] = X.get("error_analistas") or "sin cobertura de analistas en Yahoo"
    except Exception as e:  # noqa: BLE001
        out["error_analistas"] = f"{type(e).__name__}: {e}"
    return out


# --------------------------------------------------------------------------------------------- HTML
def _num_corto(v: float | None, dec: int = 1) -> str:
    if v is None:
        return '<span class="nd">s/d</span>'
    a = abs(v)
    for lim, suf in ((1e9, " mil M"), (1e6, " M"), (1e3, " mil")):
        if a >= lim:
            return n(v / lim, dec, suf)
    return n(v, 0, "")


def grafico(px: pd.Series | None, vol: pd.Series | None, marcas: pd.DataFrame | None, medias: dict | None,
            moneda: str = "", titulo: str = "") -> str:
    """SVG: precio (línea) con compras ▲ verdes y ventas ▼ rojas (huecas = con plan 10b5-1) y volumen (barras) debajo."""
    if px is None or len(px.dropna()) < 2:
        return '<p class="nd">s/d (sin precios para el gráfico)</p>'
    px = px.dropna()
    W, H, L, R, T = 680, 300, 52, 12, 10
    HP, G, HV = 190, 18, 62          # alto precio, hueco, alto volumen
    x0, x1 = px.index[0], px.index[-1]
    span = max(1, (x1 - x0).days)

    def X(f):
        return L + (W - L - R) * (pd.Timestamp(f) - x0).days / span
    lo, hi = float(px.min()), float(px.max())
    mk = marcas if marcas is not None and len(marcas) else None
    if mk is not None:
        mk = mk[(mk["trans_date"] >= x0) & (mk["trans_date"] <= x1)]
        if len(mk):
            lo, hi = min(lo, float(mk["precio"].min())), max(hi, float(mk["precio"].max()))
    pad = (hi - lo) * 0.06 or 1
    lo, hi = lo - pad, hi + pad

    def Y(v):
        return T + HP * (1 - (v - lo) / (hi - lo))
    p = [f'<svg class="av-chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(titulo)}"><title>{esc(titulo)}</title>']
    for k in range(5):   # rejilla de precio
        v = lo + (hi - lo) * k / 4
        p.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 f'<text class="tick" x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{n(v, 0 if v >= 100 else 2, "")}</text>')
    m0 = pd.Timestamp(x0.year, x0.month, 1) + pd.DateOffset(months=1)
    while m0 <= x1:      # meses
        if m0.month in (1, 4, 7, 10):
            lab = f"{MESES[m0.month - 1]}{'-' + str(m0.year)[2:] if m0.month == 1 else ''}"
            p.append(f'<text class="tick" x="{X(m0):.1f}" y="{H - 2}" text-anchor="middle">{lab}</text>')
        m0 += pd.DateOffset(months=1)
    for k, cls, lab in (("compras", "av-pm-c", "media compras"), ("ventas", "av-pm-v", "media ventas")):
        pm = ((medias or {}).get(k) or {}).get("precio_medio")
        if pm and lo < pm < hi:
            p.append(f'<line class="{cls}" x1="{L}" x2="{W - R}" y1="{Y(pm):.1f}" y2="{Y(pm):.1f}"><title>Precio medio ponderado '
                     f'de {lab[6:]} de directivos (12 m): {n(pm, 2, " " + moneda)}</title></line>')
    pts = " ".join(f"{X(f):.1f},{Y(v):.1f}" for f, v in px.items())
    p.append(f'<polyline class="av-px" points="{pts}"/>')
    if mk is not None and len(mk):
        imp = mk["importe"].abs()
        mx = float(imp.max()) or 1
        for r in mk.sort_values("importe").to_dict("records"):
            cx, cy = X(r["trans_date"]), Y(r["precio"])
            s = 4 + 5 * np.sqrt(abs(r["importe"]) / mx)
            tip = (f"{_fd(r['trans_date'])} · {esc(r.get('owner_name') or '')} ({esc(r.get('cargo') or '')}): "
                   f"{CAT[r['cat']]} de {n(r['acciones'], 0, '')} acciones a {n(r['precio'], 2, ' ' + moneda)} "
                   f"(≈ {n(r['importe'] / 1e6, 2, ' M')})")
            if r["cat"] == "compra":
                path, cls = f"M{cx:.1f},{cy - s:.1f} L{cx + s:.1f},{cy + s * .8:.1f} L{cx - s:.1f},{cy + s * .8:.1f} Z", "av-c"
            else:
                path = f"M{cx:.1f},{cy + s:.1f} L{cx + s:.1f},{cy - s * .8:.1f} L{cx - s:.1f},{cy - s * .8:.1f} Z"
                cls = "av-vp" if r["cat"] == "venta_plan" else "av-v"
            p.append(f'<path class="{cls}" d="{path}"><title>{tip}</title></path>')
    # volumen
    yv0 = T + HP + G
    if vol is not None and len(vol.dropna()):
        v = vol.dropna()
        v = v[(v.index >= x0) & (v.index <= x1)]
        vm = float(v.max()) if len(v) else 0
        if vm > 0:
            bw = max(1.0, (W - L - R) / max(len(v), 1) * 0.8)
            p.append(f'<text class="tick" x="{L - 6}" y="{yv0 + 9}" text-anchor="end">{_num_corto(vm, 0)}</text>'
                     f'<line class="base" x1="{L}" x2="{W - R}" y1="{yv0 + HV}" y2="{yv0 + HV}"/>')
            m20 = v.rolling(SESIONES_20).mean()
            for i, (f, val) in enumerate(v.items()):
                h = HV * val / vm
                cls = "av-vb last" if i == len(v) - 1 else "av-vb"
                p.append(f'<rect class="{cls}" x="{X(f) - bw / 2:.1f}" y="{yv0 + HV - h:.1f}" width="{bw:.1f}" height="{h:.1f}"/>')
            mpts = " ".join(f"{X(f):.1f},{yv0 + HV - HV * val / vm:.1f}" for f, val in m20.dropna().items())
            if mpts:
                p.append(f'<polyline class="av-vm" points="{mpts}"><title>Media de 20 sesiones</title></polyline>')
            p.append(f'<text class="tick" x="{L}" y="{yv0 - 3}">volumen diario (barras) y media de 20 sesiones (línea)</text>')
    p.append("</svg>")
    return "".join(p)


def _leyenda(hay_marcas: bool) -> str:
    if not hay_marcas:
        return ""
    return ('<p class="small av-ley"><span class="av-k c">▲</span> compra de directivo (P, mercado abierto) · '
            '<span class="av-k v">▼</span> venta sin plan · <span class="av-k vp">▽</span> venta con plan 10b5-1 '
            '(programada) · tamaño ∝ importe · líneas discontinuas: precio medio ponderado de compras (verde) y de '
            'ventas (rojo) de 12 meses. Pasa el ratón por una marca para el detalle.</p>')


def html_volumen(v: dict | None, moneda: str, err: str | None, descarga: str | None = None) -> str:
    if not v:
        return f'<p class="nd">Volumen s/d{(" (" + esc(err) + ")") if err else ""}.</p>'
    u = "contratos" if v["es_futuro"] else "acciones"
    imp = ""
    if v.get("importe") is not None:
        imp = (f'<tr><td>Importe negociado (volumen × cierre)</td><td><strong>{_num_corto(v["importe"])} {esc(moneda)}</strong>'
               f' <span class="muted">media 20 s: {_num_corto(v.get("importe_20"))} {esc(moneda)}</span></td></tr>')
    rt = v.get("ratio_20")
    col = "" if rt is None else (" style='color:var(--serious)'" if rt >= 2 else "")
    curso = ""
    if descarga and v["fecha"] >= str(descarga)[:10]:
        curso = ' <span class="chip c-ambar">sesión en curso: volumen incompleto</span>'
    return (f'<table class="num"><tbody><tr><td>Volumen ({_fd(v["fecha"])}){curso}</td><td><strong>{_num_corto(v["ultimo"])}</strong> {u}</td></tr>'
            f'<tr><td>Media 20 sesiones / 3 meses (63)</td><td><strong>{_num_corto(v["media_20"])} / {_num_corto(v["media_3m"])}</strong></td></tr>'
            f'<tr><td>Último frente a la media</td><td><strong{col}>× {n(rt, 2, "")}</strong> (20 s) · × {n(v.get("ratio_3m"), 2, "")} (3 m)</td></tr>'
            f'{imp}</tbody></table>'
            + ('<p class="small">Futuro de 1.er vencimiento: contratos (no dinero); cae al acercarse el vencimiento y se '
               'traslada al siguiente.</p>' if v["es_futuro"] else
               '<p class="small">Las medias excluyen la última sesión. Si el último dato es del día en curso, el volumen '
               'aún está incompleto.</p>'))


def html_directivos(c: dict, moneda: str, precio: float | None) -> str:
    if c.get("error_form4"):
        return f'<p class="nd">Form 4: s/d ({esc(c["error_form4"])}).</p>'
    m = c.get("medias") or {}

    def fila(k, tit):
        x = m.get(k) or {}
        if not x.get("lineas"):
            return f"<tr><td>{tit}</td><td colspan='4' class='muted'>ninguna en 12 meses</td></tr>"
        return (f"<tr><td>{tit}</td><td><strong>{n(x['precio_medio'], 2, ' ' + esc(moneda))}</strong></td>"
                f"<td>{n(x['vs_actual'], 1, ' %', True)}</td><td>{_num_corto(x['acciones'])}</td>"
                f"<td>{_num_corto(x['importe'])} {esc(moneda)} <span class='muted'>({x['personas']} pers.)</span></td></tr>")
    otras = m.get("otras") or {}
    tx_otras = ("; ".join(f"{k}: {v}" for k, v in otras.items())) or "ninguna"
    tab = ("<table class='num'><thead><tr><th>12 meses (directivos)</th><th>Precio medio ponderado</th>"
           "<th data-tip='Cuánto está el precio actual por encima (+) o por debajo (−) de ese precio medio'>Actual vs. medio</th>"
           "<th>Acciones</th><th>Importe</th></tr></thead><tbody>"
           + fila("compras", "Compras (P)") + fila("ventas_sin_plan", "Ventas sin plan 10b5-1")
           + fila("ventas", "Todas las ventas (S)") + "</tbody></table>"
           f"<p class='small'>Precio actual {n(precio, 2, ' ' + esc(moneda))}. Excluidas (no son compraventas en mercado; "
           f"líneas en 12 meses): {esc(tx_otras)}."
           + (f" {c['descartadas']} líneas descartadas por precio absurdo." if c.get("descartadas") else "") + "</p>")
    ops = c.get("ops")
    filas = []
    if ops is not None and len(ops):
        for r in ops.head(N_TABLA).to_dict("records"):
            cls = {"compra": "av-tc", "venta": "av-tv", "venta_plan": "av-tvp"}[r["cat"]]
            filas.append(f"<tr><td>{_fd(r['trans_date'])}</td><td>{esc(r.get('owner_name'))}</td>"
                         f"<td class='av-cargo'>{esc(r.get('cargo'))}{'' if r.get('directivo') else ' <span class=muted>(no entra en medias)</span>'}</td>"
                         f"<td><span class='{cls}'>{CAT[r['cat']]}</span></td><td>{n(r['precio'], 2, '')}</td>"
                         f"<td>{n(r['acciones'], 0, '')}</td><td>{_num_corto(r['importe'])}</td></tr>")
    tabla_ops = ("<div class='tw'><table class='num av-ops'><thead><tr><th>Fecha</th><th>Quién</th><th>Cargo</th><th>Tipo</th>"
                 f"<th>Precio ({esc(moneda)})</th><th>Acciones</th><th>Importe</th></tr></thead><tbody>{''.join(filas)}"
                 "</tbody></table></div>") if filas else "<p class='muted'>Sin compras ni ventas en mercado abierto en el periodo descargado.</p>"
    mf = c.get("meta_form4") or {}
    return (tab + f"<h4>Últimas compras y ventas ({min(len(ops) if ops is not None else 0, N_TABLA)} más recientes)</h4>" + tabla_ops
            + f"<p class='small'>SEC Form 4 desde {_fd(mf.get('desde'))} (ficheros trimestrales hasta {_fd(mf.get('trimestrales_hasta'))}"
            f" + Form 4 de EDGAR posteriores; actualizado {esc(str(mf.get('actualizado_utc', ''))[:10])}). Una fila = una persona, un día y un tipo"
            " (precio medio ponderado de sus líneas). Las ventas son la norma (cobran en acciones, diversifican); "
            "las compras con su dinero suelen leerse como más informativas. Fecha = la de la operación (se declara "
            "hasta 2 días hábiles después).</p>")


def html_13f(c: dict, moneda: str) -> str:
    r = c.get("f13")
    if not r:
        return f'<p class="nd">13F: s/d ({esc(c.get("error_13f") or "sin datos")}).</p>'
    pers = r["periodos"][1:]

    def tri(p):
        d = pd.Timestamp(p)
        return f"T{(d.month - 1) // 3 + 1}-{d.year}"
    cab = "".join(f"<th>Δ {tri(p)}<br><span class='muted'>≈ {n((r['totales'].get(p) or {}).get('precio_medio'), 2, '')}</span></th>"
                  for p in pers)
    filas = []
    for f in r["top"]:
        cel = []
        for ch in f["cambios"]:
            if ch is None:
                cel.append("<td class='muted'>—</td>")
            elif ch["nueva"]:
                cel.append(f"<td data-tip='No declaraba esta acción con ese CIK el trimestre anterior (posición nueva, "
                           f"cambio de entidad o informe que falta en el fichero de la SEC)'>sin dato previo "
                           f"<span class='muted'>({_num_corto(ch['delta'])})</span></td>")
            else:
                cel.append(f"<td>{n(ch['pct'], 1, ' %', True) if ch['pct'] is not None else '—'}"
                           f"<br><span class='muted'>≈ {_num_corto(ch['importe_aprox'])}</span></td>")
        filas.append(f"<tr><td>{esc(f['gestor'])}</td><td>{_num_corto(f['acciones'])}</td>{''.join(cel)}</tr>")
    agg = r["agregado"]
    tr_agg = "".join(f"<td>{a['suben']} ↑ / {a['bajan']} ↓<br><span class='muted'>neto ≈ {_num_corto(a['importe_aprox'])}</span></td>"
                     for a in agg)
    return (f"<div class='tw'><table class='num av-13f'><thead><tr><th>Gestora (mayores a {_fd(r['ultimo'])})</th>"
            f"<th>Acciones</th>{cab}</tr></thead><tbody>{''.join(filas)}"
            f"<tr class='av-tot'><td>Todas las gestoras presentes en los dos trimestres</td><td></td>{tr_agg}</tr></tbody></table></div>"
            f"<p class='small'><strong>Aproximación:</strong> Δ = cambio de acciones entre dos cierres de trimestre; «≈» = ese "
            f"cambio × el precio medio de cierre del trimestre (bajo cada trimestre, en {esc(moneda)}, en la escala de "
            f"entonces: sin ajustar por splits posteriores). El 13F no dice a qué precio "
            f"ni cuándo operaron. Se presenta hasta 45 días después del trimestre: la última foto es del {_fd(r['ultimo'])}. Solo "
            f"largos en acciones; muchos de los mayores son fondos indexados (sus cambios son entradas y salidas de dinero, "
            f"no opinión). Sin enmiendas 13F-HR/A; líneas con errores de unidades descartadas.</p>")


def html_analistas(c: dict, moneda: str, precio: float | None) -> str:
    a = c.get("analistas")
    aviso = f'<p class="disc small"><strong>{esc(AVISO_ANALISTAS)}</strong></p>'
    if not a:
        return aviso + f'<p class="nd">Analistas: s/d ({esc(c.get("error_analistas") or "sin datos")}).</p>'
    cs = a.get("consenso")
    barra = ""
    if cs and cs["total"]:
        seg = "".join(f'<div class="seg {cl}" style="flex:{cs[k] / cs["total"]:.4f}" tabindex="0" '
                      f'data-tip="{et}: {cs[k]} de {cs["total"]}"></div>'
                      for k, cl, et in (("comprar", "av-sc", "Comprar"), ("mantener", "av-sm", "Mantener"),
                                        ("vender", "av-sv", "Vender")) if cs[k])
        barra = (f'<div class="av-bar">{seg}</div><p class="small">Comprar {cs["comprar"]} · mantener {cs["mantener"]} · '
                 f'vender {cs["vender"]} ({cs["total"]} analistas este mes; media {n(a.get("media_1_5"), 1, "")} en una '
                 f'escala de 1 = compra fuerte a 5 = venta fuerte).</p>')
    o = a["objetivo"]
    obj = ("<table class='num'><thead><tr><th>Precio objetivo (12 m)</th><th>Precio</th><th>vs. actual</th></tr></thead><tbody>"
           + "".join(f"<tr><td>{tit}</td><td><strong>{n(o[k]['precio'], 2, ' ' + esc(moneda))}</strong></td>"
                     f"<td>{n(o[k]['vs_actual'], 1, ' %', True)}</td></tr>"
                     for k, tit in (("medio", "Medio"), ("alto", "Más alto"), ("bajo", "Más bajo")))
           + f"</tbody></table><p class='small'>{n(a.get('n_analistas'), 0, '')} analistas con precio objetivo. "
             f"Precio actual {n(precio, 2, ' ' + esc(moneda))}.</p>")
    ACC = {"up": "sube recomendación", "down": "baja recomendación", "init": "inicia cobertura", "main": "mantiene",
           "reit": "reitera"}
    filas = "".join(f"<tr><td>{_fd(x['fecha'])}</td><td>{esc(x.get('firma'))}</td><td>{esc(ACC.get(x.get('accion'), x.get('accion')))}"
                    f"</td><td>{esc(x.get('de') or '—')} → {esc(x.get('a') or '—')}</td>"
                    f"<td>{n(x.get('objetivo_previo'), 0, '') if x.get('objetivo_previo') else '—'} → {n(x.get('objetivo'), 0, '') if x.get('objetivo') else '—'}</td></tr>"
                    for x in a.get("cambios") or [])
    camb = (f"<h4>Cambios recientes (90 días: {a['n_suben']} suben, {a['n_bajan']} bajan recomendación; "
            f"se enseñan primero subidas, bajadas e inicios de cobertura)</h4>"
            "<div class='tw'><table class='num'><thead><tr><th>Fecha</th><th>Firma</th><th>Acción</th><th>Recomendación</th>"
            f"<th>Objetivo</th></tr></thead><tbody>{filas}</tbody></table></div>") if filas else \
        "<p class='muted'>Sin cambios de recomendación en 90 días.</p>"
    return (aviso + barra + obj + camb + f"<p class='small'>Fuente: Yahoo Finance (descarga {esc(str(c.get('descarga_analistas') or '')[:10])}).</p>")


def ficha_v2(t: str, r: dict, X: dict | None, hoy: date | None = None) -> str:
    """Bloques nuevos de la ficha; nunca lanza (si algo falla, un «s/d» en su sitio)."""
    if X is None:
        return '<div class="dblk wide"><p class="nd">Volumen, directivos y analistas: s/d.</p></div>'
    try:
        c = calcular(t, r, X, hoy)
    except Exception as e:  # noqa: BLE001
        return f'<div class="dblk wide"><p class="nd">Volumen, directivos y analistas: s/d ({esc(type(e).__name__)}).</p></div>'
    mon = r.get("moneda") or ""
    precio = r.get("precio")
    p = []
    try:
        ops = c.get("ops")
        marcas = ops if ops is not None and len(ops) else None
        tit = (f"{r.get('nombre', t)}: precio de cierre de 12 meses" + (" con compras y ventas de directivos" if marcas is not None else "")
               + " y volumen diario")
        g = grafico(c.get("serie_px"), c.get("serie_vol"), marcas, c.get("medias"), mon, tit)
        nota = ("<p class='small'>Cierre ajustado solo por splits (no por dividendos: así se compara con el precio de los "
                "Form 4).</p>") if c["accion"] else ""
        p.append(f'<div class="dblk wide av"><h4>Precio y volumen (12 meses)'
                 + (" · dónde compraron y vendieron los directivos" if c["accion"] else "") + f'</h4>{g}{_leyenda(marcas is not None)}{nota}'
                 + html_volumen(c.get("vol"), mon, c.get("error_vol"), c.get("descarga_volumen")) + "</div>")
    except Exception as e:  # noqa: BLE001
        p.append(f'<div class="dblk wide"><p class="nd">Gráfico/volumen: s/d ({esc(type(e).__name__)}).</p></div>')
    if c["accion"]:
        for tit, fn in (("Directivos (SEC Form 4): compras y ventas en mercado abierto", lambda: html_directivos(c, mon, precio)),
                        ("Grandes gestoras (SEC 13F, trimestral) · aproximación", lambda: html_13f(c, mon)),
                        ("Opinión de analistas", lambda: html_analistas(c, mon, precio))):
            try:
                p.append(f'<div class="dblk wide av"><h4>{tit}</h4>{fn()}</div>')
            except Exception as e:  # noqa: BLE001
                p.append(f'<div class="dblk wide"><h4>{tit}</h4><p class="nd">s/d ({esc(type(e).__name__)}).</p></div>')
    p.append('<p class="small av-desc">Bloques de volumen, directivos, gestoras y analistas: <strong>descriptivos</strong>, '
             'sin señal de cartera ni validación en este proyecto.</p>')
    return "".join(p)


def cargar_seguro() -> dict | None:
    try:
        return cargar()
    except Exception:  # noqa: BLE001
        return None


CSS = """
.av-chart{width:100%;max-width:680px;height:auto;display:block}.av-chart .grid{stroke:var(--grid);stroke-width:1}
.av-chart .base{stroke:var(--axis);stroke-width:1}.av-chart .tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.av-px{fill:none;stroke:var(--s1);stroke-width:1.6}.av-vb{fill:var(--axis)}.av-vb.last{fill:var(--s1)}
.av-vm{fill:none;stroke:var(--ink2);stroke-width:1.2}
.av-c{fill:var(--good);stroke:var(--surface);stroke-width:1}.av-v{fill:var(--crit);stroke:var(--surface);stroke-width:1}
.av-vp{fill:var(--surface);stroke:var(--crit);stroke-width:1.5}
.av-pm-c{stroke:var(--good);stroke-width:1.2;stroke-dasharray:5 4}.av-pm-v{stroke:var(--crit);stroke-width:1.2;stroke-dasharray:5 4}
.av-k{font-weight:700}.av-k.c{color:var(--good)}.av-k.v,.av-k.vp{color:var(--crit)}
.av-tc{color:var(--good);font-weight:600}.av-tv{color:var(--crit);font-weight:600}.av-tvp{color:var(--crit)}
table.av-ops td,table.av-13f td{white-space:nowrap}table.av-ops td.av-cargo{white-space:normal;min-width:120px}
table.av-13f td:first-child{white-space:normal;min-width:160px}tr.av-tot td{border-top:2px solid var(--grid)}
.av-bar{display:flex;height:14px;border-radius:3px;overflow:hidden;max-width:420px;margin:6px 0}
.av-bar .seg{height:100%}.av-sc{background:var(--good)}.av-sm{background:var(--axis)}.av-sv{background:var(--crit)}
"""
