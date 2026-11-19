"""Paquete de contexto de un evento de diagnóstico (docs/panel/diagnosticos_v0.md §3). SIN IA y reproducible.

Arma un JSON (y un gráfico) con lo que el explicador puede citar: movimientos del día en σ, amplitud (¿generalizada o
concentrada?), correlaciones de 20 días frente a 1 año, calendario de publicaciones (vintages ALFRED) y cambios de
tipos oficiales, posicionamiento COT, régimen y capas, qué decían los modelos (sin re-correr nada), episodios
parecidos y noticias (src/diag/noticias.py). Todo es DESCRIPTIVO.

Solo lee: precios del archivo, warehouse y los ficheros de salida de los modelos. No escribe en ningún registro.
Se guarda en $FIN_DATA_ROOT/diag/paquetes/<fecha>/ (fuera de git).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.diag import disparadores as D

REPO = Path(__file__).resolve().parents[2]
AVISO = ("Explicación posterior («ex post»): siempre suena convincente. No es una señal de compra o venta ni "
         "asesoramiento. Los datos son medidos; las hipótesis, inferidas.")
# extras del warehouse para el contexto (no disparan): clave → (id, nombre, medida)
EXTRAS = {"tipo_real10": ("DFII10", "Tipo real 10 a (TIPS)", "pb"), "vix": ("VIXCLS", "VIX", "log"),
          "hy_oas": ("BAMLH0A0HYM2", "Diferencial high yield (OAS)", "pb"),
          "dolar_amplio": ("DTWEXBGS", "Dólar amplio (Fed, semanal con retraso)", "log"),
          "bund10": ("bundesbank_bund_zero_10y_d", "Bund 10 a (cupón cero)", "pb")}
SECTORES = ["XLE", "XLK", "XLV", "XLF", "XLU", "XLP", "XLI", "XLB", "XLC", "XLRE"]
PARES = [("oro", "sp500", "oro – bolsa"), ("sp500", "TLT", "bolsa – bonos largos"), ("oro", "dolar", "oro – dólar"),
         ("sp500", "tesoro10", "bolsa – rentab. 10 a"), ("oro", "tipo_real10", "oro – tipo real 10 a")]
TIPOS_OFICIALES = {"DFEDTARU": "Fed: techo del rango objetivo", "ecb_dfr_d": "BCE: tipo de depósito"}
CALENDARIO_NOMBRES = {"CPIAUCSL": "IPC general", "CPILFESL": "IPC subyacente", "PCEPI": "PCE general",
                      "PCEPILFE": "PCE subyacente", "PAYEMS": "nóminas", "UNRATE": "paro", "GDPC1": "PIB real",
                      "GDP": "PIB nominal", "ICSA": "peticiones de subsidio", "INDPRO": "producción industrial",
                      "TCU": "utilización de capacidad", "PPIACO": "precios de producción", "M2SL": "M2",
                      "CFNAI": "índice de actividad de Chicago"}


def paquetes_dir() -> Path:
    return D.root() / "diag" / "paquetes"


def _f(v, dec=2):
    return None if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), dec)


def cargar_extras(con=None) -> dict[str, pd.Series]:
    cerrar = False
    try:
        if con is None:
            from src.warehouse import db
            con, cerrar = db.connect(read_only=True), True
        ids = [i for i, _, _ in EXTRAS.values()] + list(TIPOS_OFICIALES)
        q = con.execute("select series_id, date, value from obs_latest where series_id in (" +
                        ",".join("?" * len(ids)) + ")", ids).df()
        return {k: g.set_index(pd.to_datetime(g["date"]))["value"].sort_index().astype(float)
                for k, g in q.groupby("series_id")}
    except Exception:  # noqa: BLE001
        return {}
    finally:
        if cerrar:
            con.close()


def todas_series(X: dict, extras: dict[str, pd.Series]) -> dict[str, tuple[pd.Series, str, str]]:
    """{clave: (niveles, medida, nombre)} de referencia, «Mis activos» y extras."""
    from src.ingest.yahoo_precios import ACTIVOS
    out = {}
    S = D.series_referencia(X)
    for c, nom, _, _, med, _ in D.REFERENCIA:
        if c in S:
            out[c] = (S[c], med, nom)
    p = X.get("precios")
    ya = {i for c, _, f, i, _, _ in D.REFERENCIA if f == "precio" and c in out}   # SPY, QQQ… ya están como referencia
    if p is not None:
        for t in p.columns:
            if t in ya:
                continue
            s = p[t].dropna()
            if len(s) > 70:
                out[t] = (s, "log", ACTIVOS.get(t, (t,))[0])
    for c, (i, nom, med) in EXTRAS.items():
        if i in extras and len(extras[i].dropna()) > 70:
            out[c] = (extras[i].dropna(), med, nom)
    return out


def ficha_movimiento(s: pd.Series, medida: str, fecha: pd.Timestamp) -> dict | None:
    m = D.movimiento(s, medida)
    m = m[m.index <= fecha].dropna(subset=["cambio"])
    if len(m) < 70:
        return None
    f = m.index[-1]
    r = m.iloc[-1]
    niv = m["nivel"]
    out = {"fecha_dato": str(f.date()), "nivel": _f(r["nivel"], 3), "cambio": _f(r["ret"]),
           "unidad": "pb" if medida == "pb" else "%", "k_sigma63": _f(r["k"]),
           "percentil_dia_en_historia": _f(100 * float((m["cambio"] <= r["cambio"]).mean()), 1),
           "historia_desde": str(m.index[0].date()), "retraso_dias": int((fecha - f).days)}
    if len(niv) > 5:
        out["cambio_5s"] = _f(100 * (niv.iloc[-1] - niv.iloc[-6])) if medida == "pb" else _f(100 * (niv.iloc[-1] / niv.iloc[-6] - 1))
    if medida != "pb":
        w = niv[niv.index > f - pd.Timedelta(days=365)]
        out["desde_max_52s"] = _f(100 * (niv.iloc[-1] / w.max() - 1))
        out["vol_1a_anual"] = _f(100 * float(np.log(w).diff().std() * np.sqrt(252)), 1)
    return out


def movimientos(series: dict, fecha: pd.Timestamp) -> list[dict]:
    out = []
    for c, (s, med, nom) in series.items():
        try:
            fi = ficha_movimiento(s, med, fecha)
        except Exception:  # noqa: BLE001
            fi = None
        if fi:
            out.append({"clave": c, "nombre": nom, "referencia": c in D.NOMBRE, **fi})
    out.sort(key=lambda x: -abs(x["k_sigma63"] or 0))
    return out


def amplitud(movs: list[dict], fecha: pd.Timestamp) -> dict:
    sec = [m for m in movs if m["clave"] in SECTORES and m["fecha_dato"] == str(fecha.date())]
    baja = sum(1 for m in sec if (m["cambio"] or 0) < 0)
    sube = sum(1 for m in sec if (m["cambio"] or 0) > 0)
    n = len(sec)
    lect = ("sin datos de sectores ese día" if not n else "generalizada a la baja" if baja >= 0.8 * n
            else "generalizada al alza" if sube >= 0.8 * n else "concentrada / mixta")
    return {"sectores_eeuu": n, "bajan": baja, "suben": sube, "lectura": lect,
            "regla": "≥ 80 % de los 10 ETF sectoriales en la misma dirección = generalizada (regla fija, no validada)",
            "sectores": [{k: m[k] for k in ("clave", "nombre", "cambio", "k_sigma63")} for m in sec]}


def correlaciones(series: dict, fecha: pd.Timestamp) -> list[dict]:
    out = []
    for a, b, nom in PARES:
        if a not in series or b not in series:
            continue
        ra = D.movimiento(series[a][0], series[a][1])["cambio"]
        rb = D.movimiento(series[b][0], series[b][1])["cambio"]
        d = pd.concat([ra, rb], axis=1, join="inner").dropna()
        d = d[d.index <= fecha]
        if len(d) < 260:
            continue
        c20 = d.iloc[:, 0].rolling(20).corr(d.iloc[:, 1])
        c252 = d.iloc[:, 0].rolling(252).corr(d.iloc[:, 1])
        h = c20[c20.index >= "2007-01-01"].dropna()
        v = float(c20.iloc[-1])
        out.append({"par": nom, "series": [a, b], "corr_20s": _f(v), "corr_252s": _f(c252.iloc[-1]),
                    "mediana_20s_desde_2007": _f(h.median()) if len(h) else None,
                    "percentil_20s": _f(100 * float((h <= v).mean()), 0) if len(h) else None})
    return out


def calendario(con, fecha: pd.Timestamp, extras: dict[str, pd.Series]) -> dict:
    """Publicaciones con vintage ALFRED el día del evento y el anterior; cambios de tipos oficiales ±3 días."""
    pub = []
    if con is not None:
        try:
            q = con.execute("select series_id, date, value, realtime_start from vintages where realtime_start between ? and ?",
                            [(fecha - pd.offsets.BDay(1)).date(), fecha.date()]).df()
            for (sid, rs), g in q.groupby(["series_id", "realtime_start"]):
                g = g.sort_values("date")
                pub.append({"serie": sid, "nombre": CALENDARIO_NOMBRES.get(sid, sid), "publicado": str(pd.Timestamp(rs).date()),
                            "ultimo_periodo": str(pd.Timestamp(g["date"].iloc[-1]).date()),
                            "valor": _f(g["value"].iloc[-1], 3), "observaciones_nuevas_o_revisadas": len(g)})
        except Exception:  # noqa: BLE001
            pass
    tipos = []
    for sid, nom in TIPOS_OFICIALES.items():
        s = extras.get(sid)
        if s is None:
            continue
        d = s.diff()
        cam = d[(d != 0) & d.notna() & (d.index >= fecha - pd.Timedelta(days=3)) & (d.index <= fecha + pd.Timedelta(days=1))]
        for f, v in cam.items():
            tipos.append({"serie": sid, "nombre": nom, "fecha": str(f.date()), "cambio_pp": _f(v), "nivel": _f(s.loc[f])})
        ult = s[s.index <= fecha].dropna()
        if len(ult):
            tipos.append({"serie": sid, "nombre": nom, "nivel_vigente": _f(ult.iloc[-1]), "desde": str(
                ult[ult != ult.iloc[-1]].index[-1].date() if (ult != ult.iloc[-1]).any() else ult.index[0].date())})
    return {"publicaciones_alfred": pub, "tipos_oficiales": tipos,
            "nota": "Solo las series con vintages ALFRED tienen fecha de publicación exacta; el calendario de reuniones "
                    "de bancos centrales no está en el archivo (ver los comunicados oficiales en «noticias»)."}


def posicionamiento(con, fecha: pd.Timestamp) -> list[dict]:
    try:
        from src.report import manos_fuertes as MF
        out = []
        for m in MF.cot(con):
            for k, g in m["grupos"].items():
                out.append({"mercado": m["nombre"], "grupo": g["etiqueta"], "dato_del": g["fecha"],
                            "neto_pct_interes_abierto": _f(g["valor"], 1), "cambio_4s": _f(g["d4"], 1),
                            "percentil_3a": _f(g["p3a"], 0), "percentil_hist": _f(g["phist"], 0),
                            "lectura_regla_panel": g.get("senal"),
                            "posterior_al_evento": pd.Timestamp(g["fecha"]) > fecha})
        return out
    except Exception as e:  # noqa: BLE001
        return [{"error": f"{type(e).__name__}: {e}"}]


def regimen(X: dict, fecha: pd.Timestamp) -> dict:
    reg = X.get("regimen")
    if reg is None or not len(reg):
        return {"error": "sin regime_monthly"}
    r = reg[pd.to_datetime(reg["date"]) <= fecha + pd.offsets.MonthEnd(0)].sort_values("date")
    if not len(r):
        return {}
    a = r.iloc[-1]
    prev = r.iloc[-2] if len(r) > 1 else None
    return {"mes": str(pd.Timestamp(a["date"]).date()), "corte": str(a.get("cutoff"))[:10], **D.estado_regimen(a),
            "mes_anterior": D.estado_regimen(prev) if prev is not None else None,
            "nota": "Cuadrante mensual de EE. UU. con datos macro que llegan con retraso: va por detrás del mercado."}


def _q(cuantiles: list[float], p: float) -> float:
    return float(np.interp(p, np.arange(1, 100), cuantiles))


def modelos() -> dict:
    """Qué decían los modelos (lectura de sus salidas; NO se re-corre nada)."""
    out: dict = {}
    try:
        h = json.loads((REPO / "research/int/int11_v3_hoy.json").read_text())
        us = h["paises"]["USA"]
        cu = us.get("cuantiles_1_99") or {}
        x = {"emision": h.get("emision"), "corte_datos": h.get("corte_datos"), "ventana": h.get("ventana_objetivo"),
             "regimen_dominante": us.get("regimen_dominante"), "pesos_regimen": us.get("pesos_regimen")}
        for act in ("bolsa", "oro", "bonos"):
            if act in cu:
                c = cu[act]
                x[f"{act}_real_p5_p50_p95"] = [_f(100 * _q(c, 5), 1), _f(100 * _q(c, 50), 1), _f(100 * _q(c, 95), 1)]
                x[f"{act}_P_perdida"] = _f(100 * float(np.interp(0, c, np.arange(1, 100)) / 100), 0)
        if "bolsa" in cu:
            x["P_bolsa_real_menor_-20"] = _f(float(np.interp(-0.20, cu["bolsa"], np.arange(1, 100))), 1)
        x["nota"] = "Abanicos reales a 12 meses (INT-11 v3.1, registro en vivo); calibración no confirmada fuera de muestra."
        out["int11"] = x
    except Exception as e:  # noqa: BLE001
        out["int11"] = {"error": f"{type(e).__name__}: {e}"}
    try:
        p = REPO / "research/int/e1_vivo.jsonl"
        filas = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
        out["e1"] = filas[-1] if filas else {"nota": "sin registros todavía (prerregistro: no se enseñan antes del 1.er cierre)"}
    except Exception as e:  # noqa: BLE001
        out["e1"] = {"error": f"{type(e).__name__}: {e}"}
    try:
        sig = sorted((REPO / "obsidian/Reports").glob("*_signal.json"))[-1]
        s = json.loads(sig.read_text())
        out["signal_semanal"] = {"fichero": sig.name, "asof": s.get("asof"),
                                 "credito": (s.get("credit") or {}).get("light"),
                                 "liquidez": (s.get("liquidity") or {}).get("state"),
                                 "nowcast_agregado": ((s.get("nowcast") or {}).get("agregado") or {}).get("banda")}
    except Exception as e:  # noqa: BLE001
        out["signal_semanal"] = {"error": f"{type(e).__name__}: {e}"}
    out["nota"] = ("Ninguno de estos modelos está validado para el corto plazo; un día no cambia un régimen. La cartera "
                   "de ensayo (paper) no se lee aquí.")
    return out


def episodios(series: dict, fecha: pd.Timestamp, movs: list[dict]) -> dict:
    """Días parecidos desde 2002: los 2 activos de referencia que más se movieron, mismo signo y ≥ 75 % de su tamaño
    de hoy en σ (mínimo 1 σ) a la vez; separación ≥ 10 sesiones; sin las 20 últimas. Qué pasó 1, 5 y 20 sesiones
    después (activos y S&P 500) frente a todos los días."""
    ref = [m for m in movs if m["referencia"] and m["k_sigma63"] is not None and m["clave"] in series][:2]
    if not ref:
        return {"n": 0, "nota": "sin activos de referencia con dato"}
    ks = pd.DataFrame({m["clave"]: D.movimiento(*series[m["clave"]][:2])["k"] for m in ref}).dropna()
    cond = pd.Series(True, index=ks.index)
    regla = []
    for m in ref:
        k0 = m["k_sigma63"]
        lim = max(1.0, 0.75 * abs(k0))
        cond &= (np.sign(ks[m["clave"]]) == np.sign(k0)) & (ks[m["clave"]].abs() >= lim)
        regla.append(f"{m['nombre']} {'≤ −' if k0 < 0 else '≥ +'}{lim:.2f} σ".replace(".", ","))
    ix = ks.index[(ks.index >= "2002-01-01") & (ks.index < fecha - pd.offsets.BDay(20)) & cond.to_numpy()]
    elegidos, ultimo = [], None
    pos = {f: i for i, f in enumerate(ks.index)}
    for f in ix:
        if ultimo is None or pos[f] - pos[ultimo] >= 10:
            elegidos.append(f)
            ultimo = f
    res = {"regla": " y ".join(regla) + " el mismo día; separación ≥ 10 sesiones", "n": len(elegidos),
           "fechas": [str(f.date()) for f in elegidos[-30:]]}
    claves = list(dict.fromkeys([m["clave"] for m in ref] + (["sp500"] if "sp500" in series else [])))
    for c in claves:
        s, med, nom = series[c]
        s = s.dropna()
        fila = {}
        for h in (1, 5, 20):
            fut = (s.shift(-h) - s) * (100 if med == "pb" else 1) if med == "pb" else 100 * (s.shift(-h) / s - 1)
            if med == "inv_log":
                fut = 100 * (s / s.shift(-h) - 1)
            fut = fut[fut.index < fecha]
            e = fut.reindex(elegidos).dropna()
            todo = fut[fut.index >= "2002-01-01"].dropna()
            if len(e) >= 5:
                fila[f"{h}s"] = {"mediana": _f(e.median()), "p25": _f(e.quantile(0.25)), "p75": _f(e.quantile(0.75)),
                                 "pct_al_alza": _f(100 * (e > 0).mean(), 0), "todos_los_dias_mediana": _f(todo.median()),
                                 "todos_los_dias_pct_al_alza": _f(100 * (todo > 0).mean(), 0)}
        res[c] = {"nombre": nom, "unidad": "pb" if med == "pb" else "%", **fila}
    res["nota"] = "Pocos episodios y solapados: no permite prever qué pasará ahora; la dispersión es lo relevante."
    return res


def grafico(movs: list[dict], fecha: pd.Timestamp, destino: Path) -> str | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        sel = [m for m in movs if m["k_sigma63"] is not None and m["fecha_dato"] == str(fecha.date())][:20][::-1]
        if not sel:
            return None
        fig, ax = plt.subplots(figsize=(7, 0.32 * len(sel) + 1))
        ks = [m["k_sigma63"] for m in sel]
        ax.barh([m["clave"] for m in sel], ks, color=["#b2443a" if k < 0 else "#3a7bb2" for k in ks])
        for x in (-3, -2.5, 2.5, 3):
            ax.axvline(x, color="#999", lw=0.6, ls=":")
        ax.set_xlabel("movimiento del día en σ (63 sesiones)")
        ax.set_title(f"Movimientos del {fecha.date()} (20 mayores)")
        fig.tight_layout()
        destino.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(destino, dpi=110)
        plt.close(fig)
        return str(destino)
    except Exception:  # noqa: BLE001
        return None


def construir(fecha, evento: dict | None, X: dict | None = None, con=None, noticias: dict | None = None,
              destino: Path | None = None, extras: dict | None = None) -> dict:
    """Paquete del evento del día `fecha`. Si `destino`, guarda paquete.json (+ gráfico) en esa carpeta."""
    fecha = pd.Timestamp(fecha).normalize()
    X = X if X is not None else D.cargar(con)
    extras = extras if extras is not None else cargar_extras(con)
    ser = todas_series(X, extras)
    movs = movimientos(ser, fecha)
    P = {"version": 1, "fecha_evento": str(fecha.date()),
         "generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "aviso": AVISO,
         "evento": _evento_json(evento),
         "sustitutos": {c: n for c, _, _, _, _, n in D.REFERENCIA} | D.OMITIDOS,
         "movimientos": movs, "amplitud": amplitud(movs, fecha), "correlaciones": correlaciones(ser, fecha),
         "calendario": calendario(con, fecha, extras), "posicionamiento_cot": posicionamiento(con, fecha) if con else [],
         "regimen": regimen(X, fecha), "modelos": modelos(), "episodios": episodios(ser, fecha, movs),
         "noticias": noticias or {"nota": "sin noticias (no se pidieron o no hubo red)"},
         "series_seguimiento": sorted(ser),
         "errores_carga": X.get("errores", {})}
    if destino is not None:
        destino.mkdir(parents=True, exist_ok=True)
        g = grafico(movs, fecha, destino / "movimientos_sigma.png")
        P["graficos"] = [g] if g else []
        (destino / "paquete.json").write_text(json.dumps(P, ensure_ascii=False, indent=1, default=str))
    return P


def _evento_json(e: dict | None) -> dict:
    if not e:
        return {"forzado": True, "disparos": [], "nota": "sin disparador: paquete pedido a mano (ensayo)"}
    return {"forzado": bool(e.get("forzado")), "tipos": e.get("tipos"), "tamano": _f(e.get("tamano")),
            "nuevo": e.get("nuevo"),
            "disparos": [{k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in d.items()} for d in e.get("disparos", [])]}
