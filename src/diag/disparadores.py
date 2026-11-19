"""Disparadores de los diagnósticos automáticos (docs/panel/diagnosticos_v0.md §2; umbrales APROBADOS el 19-nov-2026).

DESCRIPTIVO. Los umbrales se fijaron ANTES de mirar qué eventos dispararían y no se ajustan mirando el histórico
(como las alertas v1). Sin IA: solo reglas fijas sobre lo que la diaria ya descarga.

Tipos:
1. «extremo»: |rentabilidad del día| ≥ 3 σ en un activo de referencia (σ = desviación típica de las 63 sesiones
   anteriores); «conjunto»: ≥ 2,5 σ en ≥ 3 activos de referencia el mismo día.
2. «tendencia»: S&P 500, oro o Tesoro 10 a cruzan su media de 200 sesiones y se mantienen 3 sesiones al otro lado
   (salta el 3.er día).
3. «regimen»: cambia el cuadrante del clasificador, o el crédito pasa a rojo, la liquidez a «escasa» o la fase de
   deuda a «desapalancamiento».
4. «macro»: IPC/PCE subyacente, nóminas, paro o PIB real de EE. UU. publicados con un error frente a la previsión del
   propio proyecto (tendencia de 6 meses del dato publicado hasta entonces) ≥ 2 σ de los errores históricos.
5. «flujos»: alertas FUERTES de src/report/alertas.py en «Mis activos» solo si el precio se movió ≥ 2 σ ese día.
Agrupación: todos los disparadores del mismo día forman UN evento. Enfriamiento: el mismo disparador en el mismo
activo no vuelve a abrir nota en 5 sesiones (queda como actualización de la nota abierta).

Activos de referencia (§2, lista aprobada) y SUSTITUTOS declarados (el archivo diario no tiene todos):
  S&P 500 → ETF SPY; Nasdaq → ETF QQQ; Euro Stoxx 50 → ETF VGK (bolsa europea amplia, cotiza en dólares: mezcla
  bolsa y euro); oro → ETF GLD; Tesoro 10 a → FRED DGS10 (cambio diario en pb; llega con 1 día de retraso);
  dólar DXY → dólar frente al euro (inverso del cambio de referencia del BCE, ≈ 58 % del DXY);
  petróleo → futuro WTI CL=F (1.er vencimiento: los cambios de contrato pueden dar saltos falsos);
  bitcoin → SIN DATOS en el archivo y sin sustituto razonable: se omite (7 activos, no 8).
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

UMBRALES = {
    "sigma_ventana": 63, "sigma_min": 40,          # σ de las 63 sesiones anteriores (mínimo 40 para calcular)
    "k_solo": 3.0, "k_conjunto": 2.5, "n_conjunto": 3,
    "ma": 200, "ma_confirma": 3,
    "macro_k": 2.0, "macro_tendencia_meses": 6, "macro_ventana_errores": 120, "macro_min_errores": 24,
    "flujo_k": 2.0,
    "enfriamiento": 5,                               # sesiones
    "tope_semana": 3,                                # notas por semana (lo aplica el explicador)
}

# clave, nombre, fuente ("precio" = precios_diarios de Yahoo; "wh" = warehouse), id, medida, nota de sustituto
REFERENCIA = [
    ("sp500", "S&P 500", "precio", "SPY", "log", "ETF SPY (cierre ajustado)"),
    ("nasdaq", "Nasdaq 100", "precio", "QQQ", "log", "ETF QQQ"),
    ("eurostoxx", "Euro Stoxx 50", "precio", "VGK", "log",
     "SUSTITUTO: ETF VGK (bolsa europea amplia, en dólares); no hay Euro Stoxx 50 diario en el archivo"),
    ("oro", "Oro", "precio", "GLD", "log", "ETF GLD"),
    ("tesoro10", "Tesoro EE. UU. 10 a", "wh", "DGS10", "pb", "FRED DGS10 (cambio diario en pb; 1 día de retraso)"),
    ("dolar", "Dólar", "wh", "ecb_eurusd_d", "inv_log",
     "SUSTITUTO: dólar frente al euro (inverso del cambio de referencia del BCE); el DXY no está en el archivo"),
    ("petroleo", "Petróleo WTI", "precio", "CL=F", "log", "futuro CL=F, 1.er vencimiento (saltos en cambios de contrato)"),
]
OMITIDOS = {"bitcoin": "sin datos diarios en el archivo ni sustituto razonable: se omite"}
TENDENCIA = ["sp500", "oro", "tesoro10"]
NOMBRE = {c: n for c, n, *_ in REFERENCIA}
TIPOS = {"extremo": "movimiento extremo", "conjunto": "movimiento conjunto", "tendencia": "ruptura de tendencia",
         "regimen": "cambio de régimen", "macro": "dato macro sorpresa", "flujos": "flujos fuertes"}

# serie ALFRED → (nombre, transformación). pct_mm: % m/m; dif: diferencia mensual; pct_ann_q: % trimestral anualizado
MACRO = {"CPILFESL": ("IPC subyacente EE. UU.", "pct_mm"), "PCEPILFE": ("PCE subyacente EE. UU.", "pct_mm"),
         "PAYEMS": ("nóminas no agrícolas EE. UU.", "dif"), "UNRATE": ("tasa de paro EE. UU.", "dif"),
         "GDPC1": ("PIB real EE. UU.", "pct_ann_q")}
UNIDAD_MACRO = {"pct_mm": "% m/m", "dif": "", "pct_ann_q": "% trim. anualizado"}
DEUDA_ROJO = {"desapalancamiento"}
TAM_FIJO = 3.0   # «tamaño» de los disparadores sin σ propio (tendencia, régimen) para ordenar dentro del tope


def root() -> Path:
    return Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser()


# ============================================================================================ carga (tolerante)
def cargar(con=None) -> dict:
    """Series de referencia, «Mis activos», régimen mensual y vintages macro. Cada fuente en su try/except."""
    X: dict = {"errores": {}}
    r = root()
    try:
        p = pd.read_parquet(r / "mercados" / "precios_diarios.parquet")
        desc = json.loads((r / "mercados" / "activos.json").read_text()).get("descarga")
        if desc:   # la sesión del día de la descarga está en curso (precio parcial): fuera
            p = p[p.index < pd.Timestamp(str(desc)[:10])]
        X["precios"] = p
    except Exception as e:  # noqa: BLE001
        X["errores"]["precios"] = f"{type(e).__name__}: {e}"
    cerrar = False
    try:
        if con is None:
            from src.warehouse import db
            con, cerrar = db.connect(read_only=True), True
        ids = [i for _, _, f, i, _, _ in REFERENCIA if f == "wh"]
        q = con.execute("select series_id, date, value from obs_latest where series_id in (" +
                        ",".join("?" * len(ids)) + ")", ids).df()
        X["wh"] = {k: g.set_index(pd.to_datetime(g["date"]))["value"].sort_index().astype(float)
                   for k, g in q.groupby("series_id")}
        try:
            X["regimen"] = con.execute("select date, quadrant, credit_light, liquidity, debt_phase, cutoff "
                                       "from regime_monthly order by date").df()
        except Exception as e:  # noqa: BLE001
            X["errores"]["regimen"] = f"{type(e).__name__}: {e}"
        try:
            X["vintages"] = con.execute("select series_id, date, value, realtime_start, realtime_end from vintages "
                                        "where series_id in (" + ",".join("?" * len(MACRO)) + ")", list(MACRO)).df()
        except Exception as e:  # noqa: BLE001
            X["errores"]["vintages"] = f"{type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001
        X["errores"]["warehouse"] = f"{type(e).__name__}: {e}"
    finally:
        if cerrar:
            con.close()
    return X


def series_referencia(X: dict) -> dict[str, pd.Series]:
    """{clave: serie de niveles} de los activos de referencia disponibles (cada una en su propio calendario)."""
    out = {}
    for c, _, f, i, _, _ in REFERENCIA:
        s = None
        if f == "precio" and "precios" in X and i in X["precios"]:
            s = X["precios"][i]
        elif f == "wh" and i in (X.get("wh") or {}):
            s = X["wh"][i]
        if s is not None:
            s = s.dropna()
            s = s[~s.index.duplicated(keep="last")].sort_index()
            if len(s):
                out[c] = s
    return out


# ============================================================================================ 1. movimientos
def movimiento(s: pd.Series, medida: str = "log") -> pd.DataFrame:
    """Por sesión: cambio (log, o pb si medida = «pb»), σ de las 63 sesiones ANTERIORES y k = cambio / σ.

    «ret» es la rentabilidad simple (%) o el cambio en pb; «k» el tamaño en σ. Para «inv_log» se invierte el signo
    (dólar = 1 / EUR-USD)."""
    U = UMBRALES
    s = s.dropna()
    if medida == "pb":
        d = 100 * s.diff()
        ret = d
    else:
        s = s[s > 0]
        d = np.log(s).diff()
        if medida == "inv_log":
            d = -d
        ret = 100 * (np.exp(d) - 1)
    sig = d.shift(1).rolling(U["sigma_ventana"], min_periods=U["sigma_min"]).std()
    return pd.DataFrame({"nivel": s, "cambio": d, "ret": ret, "sigma": sig, "k": d / sig})


def disparos_movimiento(M: dict[str, pd.DataFrame]) -> list[dict]:
    """Extremos (≥ 3 σ en un activo) y conjuntos (≥ 2,5 σ en ≥ 3 activos el mismo día)."""
    U = UMBRALES
    out = []
    ks = pd.DataFrame({c: m["k"] for c, m in M.items()})
    for c, m in M.items():
        x = m[m["k"].abs() >= U["k_solo"]].dropna(subset=["k"])
        for f, r in x.iterrows():
            out.append({"fecha": f, "tipo": "extremo", "clave": c, "tamano": float(abs(r["k"])),
                        "k": float(r["k"]), "ret": float(r["ret"]),
                        "texto": f"{NOMBRE.get(c, c)}: {_fmt(r['ret'], 2, c == 'tesoro10')} ({_fmt(r['k'], 1)} σ)"})
    fuertes = ks.abs() >= U["k_conjunto"]
    for f, fila in fuertes[fuertes.sum(axis=1) >= U["n_conjunto"]].iterrows():
        cl = [c for c in fila.index if fila[c]]
        out.append({"fecha": f, "tipo": "conjunto", "clave": "conjunto", "activos": cl,
                    "tamano": float(ks.loc[f, cl].abs().max()),
                    "texto": "movimiento conjunto ≥ 2,5 σ en " + ", ".join(
                        f"{NOMBRE.get(c, c)} ({_fmt(ks.loc[f, c], 1)} σ)" for c in cl)})
    return out


def _num(v, dec=1, signo=False) -> str:
    if v is None or not np.isfinite(v):
        return "—"
    return (f"{v:+.{dec}f}" if signo else f"{v:.{dec}f}").replace(".", ",").replace("-", "−")


def _fmt(v, dec=1, pb=False) -> str:
    t = _num(v, dec, True)
    return t + (" pb" if pb else " %") if dec == 2 and t != "—" else t


# ============================================================================================ 2. tendencia
def disparos_tendencia(series: dict[str, pd.Series]) -> list[dict]:
    """Cruce de la media de 200 sesiones confirmado 3 sesiones: salta el 3.er día al otro lado."""
    U = UMBRALES
    out = []
    for c in TENDENCIA:
        if c not in series:
            continue
        s = series[c].dropna()
        ma = s.rolling(U["ma"], min_periods=U["ma"]).mean()
        lado = np.sign(s - ma).where(ma.notna())
        n = U["ma_confirma"]
        # lado «confirmado» = el que se ha mantenido ≥ 3 sesiones seguidas; salta cuando el confirmado cambia (una
        # excursión de 1-2 días al otro lado y la vuelta no cuentan como cruce)
        ok = (lado != 0) & lado.notna()
        for j in range(1, n):
            ok &= lado.shift(j) == lado
        conf = lado.where(ok).ffill()
        cruce = ok & conf.shift(1).notna() & (conf != conf.shift(1))
        for f in s.index[cruce.fillna(False).to_numpy()]:
            arriba = lado.loc[f] > 0
            out.append({"fecha": f, "tipo": "tendencia", "clave": c, "tamano": TAM_FIJO, "dir": 1 if arriba else -1,
                        "texto": f"{NOMBRE.get(c, c)} lleva {n} sesiones {'por encima' if arriba else 'por debajo'} de su "
                                 f"media de 200 sesiones (nivel {_num(s.loc[f], 2)}, media {_num(ma.loc[f], 2)})"})
    return out


# ============================================================================================ 3. régimen
def estado_regimen(fila) -> dict:
    return {"cuadrante": fila.get("quadrant"), "credito": fila.get("credit_light"),
            "liquidez": fila.get("liquidity"), "deuda": fila.get("debt_phase")}


def cambios_regimen(prev: dict | None, ahora: dict) -> list[str]:
    """Frases de los cambios que disparan (cuadrante; crédito → rojo; liquidez → escasa; deuda → desapalancamiento)."""
    if not prev:
        return []
    out = []
    if ahora.get("cuadrante") and prev.get("cuadrante") and ahora["cuadrante"] != prev["cuadrante"]:
        out.append(f"cuadrante {prev['cuadrante']} → {ahora['cuadrante']}")
    if ahora.get("credito") == "rojo" and prev.get("credito") != "rojo":
        out.append(f"semáforo de crédito {prev.get('credito')} → rojo")
    if ahora.get("liquidez") == "escasa" and prev.get("liquidez") != "escasa":
        out.append(f"liquidez {prev.get('liquidez')} → escasa")
    if ahora.get("deuda") in DEUDA_ROJO and prev.get("deuda") not in DEUDA_ROJO:
        out.append(f"fase de deuda {prev.get('deuda')} → {ahora['deuda']}")
    return out


def disparos_regimen_historico(reg: pd.DataFrame) -> list[dict]:
    """Histórico: transiciones mes a mes de regime_monthly, fechadas el 1.er día hábil del mes siguiente (cuando el
    mes queda cerrado; aproximación declarada: en vivo salta el día en que el clasificador diario cambia)."""
    out, prev = [], None
    for _, f in reg.sort_values("date").iterrows():
        ahora = estado_regimen(f)
        cam = cambios_regimen(prev, ahora)
        if cam:
            fecha = pd.Timestamp(f["date"]) + pd.offsets.BDay(1)
            out.append({"fecha": fecha, "tipo": "regimen", "clave": "regimen", "tamano": TAM_FIJO,
                        "texto": "; ".join(cam) + f" (mes {pd.Timestamp(f['date']).strftime('%Y-%m')})"})
        prev = ahora
    return out


# ============================================================================================ 4. macro
def _transformar(s: pd.Series, modo: str) -> pd.Series:
    s = s.sort_index()
    if modo == "pct_ann_q":
        q = s.copy()
        q.index = pd.PeriodIndex(q.index, freq="Q")
        prev = q.shift(1, freq="Q").reindex(q.index)
        r = 100 * ((q / prev) ** 4 - 1)
    else:
        m = s.copy()
        m.index = pd.PeriodIndex(m.index, freq="M")
        prev = m.shift(1, freq="M").reindex(m.index)   # por calendario: un mes ausente da NaN, no salta
        r = 100 * (m / prev - 1) if modo == "pct_mm" else m - prev
    r.index = s.index
    return r


def sorpresas_macro(vint: pd.DataFrame) -> pd.DataFrame:
    """Una fila por PRIMERA publicación de cada dato (punto en el tiempo, ALFRED): valor transformado, previsión
    (media de los 6 meses anteriores del dato tal como se conocía ese día), error, σ robusta de los errores ANTERIORES
    (1,4826 × MAD de los últimos 120, mínimo 24; robusta para que 2020 no anule el disparador durante años) y k."""
    U = UMBRALES
    filas = []
    if vint is None or not len(vint):
        return pd.DataFrame()
    v = vint.copy()
    v["date"] = pd.to_datetime(v["date"])
    v["realtime_start"] = pd.to_datetime(v["realtime_start"])
    v["realtime_end"] = pd.to_datetime(v["realtime_end"]).fillna(pd.Timestamp("2262-01-01"))
    for sid, g in v.groupby("series_id"):
        if sid not in MACRO:
            continue
        modo = MACRO[sid][1]
        npre = U["macro_tendencia_meses"] // (3 if modo == "pct_ann_q" else 1)
        primera = g.groupby("date")["realtime_start"].min()
        errores: list[float] = []
        for r in sorted(g["realtime_start"].unique()):
            r = pd.Timestamp(r)
            nuevas = primera[primera == r].index
            if not len(nuevas):
                continue
            snap = g[(g["realtime_start"] <= r) & (g["realtime_end"] >= r)].drop_duplicates("date", keep="last")
            snap = snap.set_index("date")["value"].sort_index()
            t = max(nuevas)
            if t != snap.index.max():
                continue
            tr = _transformar(snap, modo)
            real = tr.get(t)
            prev = tr[tr.index < t].dropna().tail(npre)
            if real is None or not np.isfinite(real) or len(prev) < npre:
                continue
            prevision = float(prev.mean())
            err = float(real) - prevision
            hist = np.array(errores[-U["macro_ventana_errores"]:])
            sig = (1.4826 * float(np.median(np.abs(hist - np.median(hist))))
                   if len(hist) >= U["macro_min_errores"] else np.nan)
            filas.append({"fecha": r, "serie": sid, "periodo": t, "valor": float(real), "prevision": prevision,
                          "error": err, "sigma": sig, "k": err / sig if sig and np.isfinite(sig) and sig > 0 else np.nan})
            errores.append(err)
    return pd.DataFrame(filas)


def disparos_macro(sor: pd.DataFrame) -> list[dict]:
    out = []
    if sor is None or not len(sor):
        return out
    for _, r in sor[sor["k"].abs() >= UMBRALES["macro_k"]].iterrows():
        nom, modo = MACRO[r["serie"]]
        dec = 0 if r["serie"] == "PAYEMS" else 2
        u = " mil" if r["serie"] == "PAYEMS" else (" pp" if modo == "dif" else " " + UNIDAD_MACRO[modo])
        per = pd.Timestamp(r["periodo"])
        per_txt = per.strftime("%Y-%m") if modo != "pct_ann_q" else f"{per.year}T{(per.month - 1) // 3 + 1}"
        out.append({"fecha": pd.Timestamp(r["fecha"]), "tipo": "macro", "clave": r["serie"],
                    "tamano": float(abs(r["k"])), "k": float(r["k"]),
                    "texto": f"{nom} ({per_txt}): {_num(r['valor'], dec)}{u} frente a la tendencia de 6 meses "
                             f"{_num(r['prevision'], dec)}{u} ({_num(r['k'], 1, True)} σ de los errores históricos; "
                             "previsión propia, sin consenso de analistas)"})
    return out


# ============================================================================================ 5. flujos
def disparos_flujos(eventos: list[dict], precios: pd.DataFrame | None) -> list[dict]:
    """Alertas FUERTES (fuerza 2) de src/report/alertas.py en «Mis activos» con |precio| ≥ 2 σ ese día (o la sesión
    siguiente si la alerta cae en día sin sesión)."""
    out = []
    if precios is None:
        return out
    cache: dict[str, pd.DataFrame] = {}
    for e in eventos or []:
        if e.get("fuerza") != 2:
            continue
        t = e.get("ticker")
        if t not in precios:
            continue
        if t not in cache:
            cache[t] = movimiento(precios[t])
        m = cache[t].dropna(subset=["k"])
        f = pd.Timestamp(e["fecha"]).normalize()
        k = m.index.searchsorted(f)
        if k >= len(m) or (m.index[k] - f).days > 4:
            continue
        r = m.iloc[k]
        if abs(r["k"]) < UMBRALES["flujo_k"]:
            continue
        out.append({"fecha": m.index[k], "tipo": "flujos", "clave": f"{t}|{e.get('tipo')}", "tamano": float(abs(r["k"])),
                    "k": float(r["k"]), "ticker": t,
                    "texto": f"{t}: alerta fuerte «{e.get('tipo')}» con precio {_fmt(r['ret'], 2)} ({_fmt(r['k'], 1)} σ)"})
    return out


# ============================================================================================ agrupación
def agrupar(disparos: list[dict], calendario: pd.DatetimeIndex | None = None) -> list[dict]:
    """Un evento por día. Enfriamiento: un disparador (tipo, clave) repetido en las 5 sesiones siguientes a otro
    igual se marca «repetido»; un evento sin ningún disparador nuevo es solo una actualización de la nota abierta."""
    if not disparos:
        return []
    U = UMBRALES
    cal = calendario if calendario is not None else pd.bdate_range(
        min(d["fecha"] for d in disparos), max(d["fecha"] for d in disparos))
    cal = pd.DatetimeIndex(sorted(set(cal) | {pd.Timestamp(d["fecha"]).normalize() for d in disparos}))
    pos = {f: i for i, f in enumerate(cal)}
    ultimo: dict[tuple, int] = {}
    por_dia: dict[pd.Timestamp, list[dict]] = {}
    for d in sorted(disparos, key=lambda d: (d["fecha"], d["tipo"], str(d["clave"]))):
        f = pd.Timestamp(d["fecha"]).normalize()
        i, k = pos[f], (d["tipo"], str(d["clave"]))
        d = {**d, "fecha": f, "repetido": k in ultimo and i - ultimo[k] <= U["enfriamiento"] and i != ultimo[k]}
        if not d["repetido"]:
            ultimo[k] = i
        por_dia.setdefault(f, []).append(d)
    out = []
    for f, ds in sorted(por_dia.items()):
        nuevos = [d for d in ds if not d["repetido"]]
        out.append({"fecha": f, "disparos": ds, "tipos": sorted({d["tipo"] for d in ds}),
                    "tamano": max(d["tamano"] for d in ds), "nuevo": bool(nuevos)})
    return out


def aplicar_tope(eventos: list[dict], tope: int | None = None) -> list[dict]:
    """Tope semanal (semana ISO, lunes-domingo): de los eventos nuevos de la semana se quedan con nota los `tope` de
    mayor tamaño; el resto, «solo_linea». Las actualizaciones no gastan cupo."""
    tope = UMBRALES["tope_semana"] if tope is None else tope
    out = [{**e, "nota": False} for e in eventos]
    sem: dict[tuple, list[int]] = {}
    for i, e in enumerate(out):
        if e["nuevo"]:
            sem.setdefault(tuple(e["fecha"].isocalendar()[:2]), []).append(i)
    for idx in sem.values():
        for i in sorted(idx, key=lambda i: -out[i]["tamano"])[:tope]:
            out[i]["nota"] = True
    return out


def todos(X: dict, eventos_flujos: list[dict] | None = None, desde: pd.Timestamp | None = None) -> list[dict]:
    """Todos los disparadores con los datos cargados (histórico completo, o desde `desde`)."""
    S = series_referencia(X)
    med = {c: movimiento(s, m) for (c, _, _, _, m, _) in REFERENCIA if c in S for s in [S[c]]}
    ds = disparos_movimiento(med) + disparos_tendencia(S)
    if "regimen" in X:
        ds += disparos_regimen_historico(X["regimen"])
    if "vintages" in X:
        ds += disparos_macro(sorpresas_macro(X["vintages"]))
    if eventos_flujos:
        ds += disparos_flujos(eventos_flujos, X.get("precios"))
    if desde is not None:
        ds = [d for d in ds if pd.Timestamp(d["fecha"]) >= desde]
    return ds


def calendario(X: dict) -> pd.DatetimeIndex:
    """Sesiones de EE. UU. (las del SPY) más los días hábiles del final sin cerrar."""
    p = X.get("precios")
    if p is not None and "SPY" in p:
        ix = p["SPY"].dropna().index
        return ix.append(pd.bdate_range(ix[-1] + pd.Timedelta(days=1), periods=10))
    return pd.bdate_range("1990-01-01", pd.Timestamp(date.today()) + pd.Timedelta(days=15))


# ============================================================================================ vivo
def estado_path() -> Path:
    return root() / "diag" / "estado.json"


def leer_estado(p: Path | None = None) -> dict:
    try:
        return json.loads((p or estado_path()).read_text())
    except Exception:  # noqa: BLE001
        return {}


def guardar_estado(est: dict, p: Path | None = None) -> None:
    p = p or estado_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(est, ensure_ascii=False, indent=1, default=str))


def clave_disparo(d: dict) -> str:
    return f"{d['tipo']}|{d['clave']}|{pd.Timestamp(d['fecha']).date()}"


def detectar(X: dict, hoy: date, estado: dict, eventos_flujos: list[dict] | None = None,
             dias_atras: int = 7) -> tuple[list[dict], dict]:
    """Eventos con algún disparador NO visto en ejecuciones anteriores (mira `dias_atras` días hábiles atrás: el
    Tesoro 10 a y el BCE llegan con 1 día de retraso, así que un día ya mirado puede ganar un disparador).

    El régimen en vivo se compara con el último estado visto (estado.json), no con el mes anterior: salta el día en
    que el clasificador diario cambia; esos disparos se guardan en el estado para el enfriamiento.
    Devuelve (eventos agrupados, estado nuevo). Cada disparo lleva «visto» (ya estaba en una ejecución anterior)."""
    h = pd.Timestamp(hoy).normalize()
    desde = h - pd.offsets.BDay(dias_atras)
    hist_desde = desde - pd.offsets.BDay(UMBRALES["enfriamiento"] + 1)   # para el enfriamiento
    ds = todos({k: v for k, v in X.items() if k != "regimen"}, eventos_flujos, hist_desde)
    ds = [d for d in ds if pd.Timestamp(d["fecha"]) <= h]
    est = dict(estado)
    reg = X.get("regimen")
    previos = [{**d, "fecha": pd.Timestamp(d["fecha"])} for d in estado.get("regimen_disparos", [])]
    if reg is not None and len(reg):
        ahora = estado_regimen(reg.sort_values("date").iloc[-1])
        cam = cambios_regimen(estado.get("regimen"), ahora)
        if cam:
            f = h if h.weekday() < 5 else h - pd.offsets.BDay(1)
            previos.append({"fecha": f, "tipo": "regimen", "clave": "regimen", "tamano": TAM_FIJO,
                            "texto": "; ".join(cam) + " (clasificador del día)"})
        est["regimen"] = ahora
    ds += [d for d in previos if d["fecha"] >= hist_desde]
    vistos = set(estado.get("vistos", []))
    ev = agrupar(ds, calendario(X))
    nuevos = []
    for e in ev:
        for d in e["disparos"]:
            d["visto"] = clave_disparo(d) in vistos
        if desde <= e["fecha"] <= h and any(not d["visto"] for d in e["disparos"]):
            nuevos.append(e)
    lim = h - pd.Timedelta(days=40)
    est["vistos"] = sorted({clave_disparo(d) for e in ev for d in e["disparos"] if e["fecha"] >= lim} |
                           {v for v in vistos if pd.Timestamp(v.rsplit("|", 1)[1]) >= lim})
    est["regimen_disparos"] = [{"fecha": str(d["fecha"].date()), "tipo": d["tipo"], "clave": d["clave"],
                                "tamano": d["tamano"], "texto": d["texto"]} for d in previos if d["fecha"] >= lim]
    est["ultima_ejecucion"] = str(h.date())
    return nuevos, est
