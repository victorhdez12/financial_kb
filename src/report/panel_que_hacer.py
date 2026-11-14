"""Pestaña «Qué hacer» del panel web: la recomendación de hoy en una frase, con qué seguridad y por qué.

Solo REUTILIZA piezas ya validadas o registradas; no estima nada nuevo ni toca registros:
- Exposición a bolsa = regla B1 (σ̂ 12 meses frente a σ* 17,02 %) y B1′ (previsión HAR frente a σ*′ 16,67 %), con las
  mismas funciones del paper trading (src/paper/live.py, src/paper/b1prima.py) en modo LECTURA (sin --registrar).
- Abanicos a 12 meses = motor INT-11 v3.1 congelado (los del signal semanal) con su cobertura medida ≤ 2004 (fase D).
- Inclinación por activo = reglas FIJAS declaradas aquí (ver `inclinaciones`): B1 para la bolsa; para el resto, solo una
  fila del atlas «con lo que se sabe a tiempo» con estado «establecido» puede mover la flecha. Si no, ► neutral.
- Motor frente al consenso: la distribución de inflación del motor (re-simulada con la misma semilla y el mismo estado del
  signal; el motor no cambia) frente a la implícita de mercado, Cleveland Fed y Michigan. El error histórico de las
  encuestas se mide SOLO con previsiones hechas ≤ 2003 (inflación realizada ≤ 2004): nada del periodo bloqueado.
No es asesoramiento financiero; uso personal.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

PAISES_ABANICO = ["USA", "ESP", "DEU", "GBR"]
ACTIVOS = [("bolsa", "Bolsa"), ("bonos", "Bonos"), ("letras", "Letras"), ("vivienda", "Vivienda"), ("oro", "Oro")]
RV_BASE = 0.70
FRASE_B1 = ("la única regla de cartera que ninguna alternativa batió en las pruebas de desarrollo (1975-2004; su "
            "previsión de volatilidad diaria, B1′, se contrastó en 1950-2004); en seguimiento en vivo desde oct-2026")
CONSENSO = [("EXPINF1YR", "Cleveland Fed (modelo, 1 año)"), ("umich_px1_md", "Encuesta de Michigan (hogares, 1 año)"),
            ("T5YIE", "Mercado: implícita a 5 años (TIPS)"), ("T5YIFR", "Mercado: 5 años dentro de 5 (5a5a)")]
ERROR_HASTA = pd.Timestamp("2003-12-31")   # previsión ≤ 2003 → inflación realizada ≤ 2004 (periodo bloqueado intacto)
NIVEL = {"establecido": "establecido", "frágil": "frágil", "no validado": "no validado"}


# ----------------------------------------------------------------------------------------------- cálculo (puro)
def umbral_recorte(sigma_star: float, rv: float = RV_BASE, paso: float = 0.025) -> float:
    """Volatilidad a partir de la cual la regla de B1 recorta (al menos `paso`) la renta variable desde `rv`:
    70 % × σ*/σ̂ ≤ 70 % − 2,5 pp  ⇔  σ̂ ≥ 70 % × σ* / 67,5 %."""
    return rv * sigma_star / (rv - paso)


def nivel_evidencia(estado: str | None) -> str:
    """Estado del atlas / prerregistro → establecido / frágil / no validado."""
    e = (estado or "").strip().lower()
    if e.startswith("establecido") and "frágil" not in e:
        return "establecido"
    if e.startswith("establecido") or e.startswith("probable"):
        return "frágil"
    return "no validado"


def recomendacion(b1: dict | None, b1_prev: dict | None, b1p: dict | None, sigma_star: float, sigma_star_p: float) -> dict:
    """Resumen de la regla de hoy. b1 / b1_prev: {"sigma_hat", "rv", "cierre"}; b1p: {"sigma_hat", "rv", "cierre"}."""
    if not b1:
        return {"ok": False}
    rv = float(b1["rv"])
    d = {"ok": True, "rv": rv, "rf": round(1 - 0.15 - rv, 4), "oro": 0.15, "delta_base": rv - RV_BASE,
         "sigma_hat": b1.get("sigma_hat"), "sigma_star": sigma_star, "cierre": b1.get("cierre"),
         "sigma_recorte": umbral_recorte(sigma_star), "recorta": rv < RV_BASE - 1e-9}
    if b1_prev:
        d["delta_mes"] = rv - float(b1_prev["rv"])
        d["sigma_prev"] = b1_prev.get("sigma_hat")
        d["cierre_prev"] = b1_prev.get("cierre")
    if b1p:
        d["b1p"] = {**b1p, "sigma_star": sigma_star_p, "sigma_recorte": umbral_recorte(sigma_star_p)}
    if d["recorta"]:
        d["frase"] = (f"Bolsa al {_pc(rv, 1)} (base 70 %): la volatilidad ({_pc(d['sigma_hat'], 1)}) supera el "
                      f"umbral de {_pc(sigma_star, 2)}, así que la regla recorta {_pc(RV_BASE - rv, 1)[:-2]} pp hacia renta fija.")
    else:
        d["frase"] = (f"Mantén la cartera base: bolsa 70 %, renta fija 15 %, oro 15 %. La volatilidad de la bolsa "
                      f"({_pc(d['sigma_hat'], 1)}) está por debajo del umbral de {_pc(sigma_star, 2)}: no toca recortar.")
    return d


def _pc(x: float, dec: int) -> str:
    """0,1069 → «10,7 %» (coma decimal)."""
    return f"{100 * x:.{dec}f}".replace(".", ",") + " %"


def filas_atlas_hoy(atlas: dict, ids: list[str]) -> list[dict]:
    out = []
    for r in atlas.get("regimenes", []):
        if r["id"] in ids:
            out += [{**f, "regimen": r["nombre"]} for f in r["filas"]]
    return out


def _de_activo(fila: dict, nombre: str) -> bool:
    return fila["activo"].lower().startswith(nombre.lower()) and fila.get("lado") != "mecanismo"


def inclinaciones(rec: dict, abanicos: dict, atlas: dict, ids_hoy: list[str]) -> list[dict]:
    """Flecha por activo con reglas fijas (declaradas antes de ver el resultado de hoy):
    1. Bolsa: la de B1. Si recorta → ▼ infraponderar; si no → ► neutral (B1 nunca sube de 70 %: no hay ▲).
    2. Resto: SOLO una fila del atlas de los regímenes de hoy «con lo que se sabe a tiempo» y estado «establecido» mueve la
       flecha (sufre → ▼, gana/aguanta → ▲). Una fila ex post (etiqueta centrada), «probable» o «descriptiva» se muestra
       como señal no validada, pero la flecha se queda en ►.
    3. El motor (P(pérdida real), mediana) se muestra como contexto de riesgo: no mueve flechas (no se validó para elegir activos).
    """
    filas = filas_atlas_hoy(atlas, ids_hoy)
    out = []
    for k, nom in ACTIVOS:
        a = abanicos.get(k) or {}
        d = {"activo": k, "nombre": nom, "p_perdida": a.get("p_neg"), "p50": a.get("p50"), "p5": a.get("p5"),
             "p95": a.get("p95"), "flecha": "►", "accion": "neutral", "evidencia": "no validado", "senales": []}
        if k == "bolsa" and rec.get("ok"):
            if rec["recorta"]:
                d.update(flecha="▼", accion="infraponderar",
                         fundamento=f"B1 recorta la bolsa al {_pc(rec['rv'], 1)} (volatilidad por encima del umbral).")
            else:
                d.update(fundamento=f"B1: volatilidad {_pc(rec['sigma_hat'], 1)} < umbral {_pc(rec['sigma_star'], 2)} → "
                                    "mantener el 70 % de la base.")
            d["evidencia"] = "establecido"
        rel = [f for f in filas if _de_activo(f, nom)]
        movida = False
        for f in rel:
            a_tiempo = "a tiempo" in f["activo"].lower()
            niv = nivel_evidencia(f["estado"])
            d["senales"].append({"texto": f"{f['activo']}: {f['lado']} {f['efecto']} ({f['regimen']})", "estado": f["estado"],
                                 "a_tiempo": a_tiempo, "nivel": niv})
            if k != "bolsa" and a_tiempo and niv == "establecido" and not movida and f["lado"] in ("sufre", "gana", "aguanta"):
                sube = f["lado"] != "sufre"
                d.update(flecha="▲" if sube else "▼", accion="sobreponderar" if sube else "infraponderar",
                         fundamento=f"Atlas, con lo que se sabe a tiempo: {f['activo']} {f['lado']} ({f['efecto']}).",
                         evidencia="establecido")
                movida = True
        if "fundamento" not in d:
            if rel:
                mejor = max(rel, key=lambda f: ["no validado", "frágil", "establecido"].index(nivel_evidencia(f["estado"])))
                d["fundamento"] = ("Ninguna regla validada con lo que se sabe a tiempo. Lo más sólido del atlas para hoy: "
                                   f"{mejor['activo'].lower()} {mejor['lado']} ({mejor['efecto']}, {mejor['estado']}"
                                   + (", etiqueta ex post: no se pudo aprovechar a tiempo" if "a tiempo" not in mejor["activo"].lower() else "")
                                   + ").")
                d["evidencia"] = nivel_evidencia(mejor["estado"]) if "a tiempo" in mejor["activo"].lower() else "no validado"
                d["direccion_no_validada"] = "▼" if mejor["lado"] == "sufre" else ("▲" if mejor["lado"] in ("gana", "aguanta") else "?")
            else:
                d["fundamento"] = "El atlas no tiene nada contrastado para este activo en el régimen de hoy."
        out.append(d)
    return out


def p_cola_normal(centro: float, sd: float, umbral: float = 5.0) -> float:
    """P(X > umbral) con X ~ Normal(centro, sd) (en pp)."""
    return 0.5 * math.erfc((umbral - centro) / (sd * math.sqrt(2)))


def error_previsiones(prev: pd.Series, ipc: pd.Series, hasta: pd.Timestamp = ERROR_HASTA) -> dict | None:
    """Error de una previsión de inflación a 1 año: realizada (IPC 12 m, 12 meses después) − prevista, con previsiones
    hechas ≤ `hasta`. prev en pp, mensual (índice = mes de la previsión); ipc = índice de precios mensual."""
    infl = (ipc / ipc.shift(12) - 1) * 100
    fut = infl.shift(-12)
    p = prev.groupby(prev.index.to_period("M")).last()
    p.index = p.index.to_timestamp()
    df = pd.concat([p.rename("e"), fut.rename("r")], axis=1, sort=True).dropna()
    df = df[df.index <= hasta]
    if len(df) < 24:
        return None
    err = df["r"] - df["e"]
    return {"n": int(len(df)), "desde": str(df.index.min().date())[:7], "hasta": str(df.index.max().date())[:7],
            "sesgo": float(err.mean()), "rmse": float(np.sqrt((err ** 2).mean()))}


def cuantiles(x: np.ndarray, ps=(5, 25, 50, 75, 95)) -> dict:
    q = np.nanpercentile(x, ps)
    return {f"p{p}": float(v) for p, v in zip(ps, q)}


# ----------------------------------------------------------------------------------------------- datos (lectura)
def datos_cartera() -> dict:
    """Decisión registrada de B1 y ensayos en modo lectura (sin registrar) del mes anterior, del mes en curso y de B1′."""
    from dataclasses import asdict

    from src.paper import b1prima as B
    from src.paper import live as L
    from src.report import panel as P
    reg = P._jsonl(P.REG["paper_b1"])
    hoy = pd.Timestamp(date.today())
    ult_cierre = (hoy.replace(day=1) - pd.Timedelta(days=1)).normalize()
    prev_cierre = (ult_cierre.replace(day=1) - pd.Timedelta(days=1)).normalize()
    out = {"errores": []}
    if reg:
        r = reg[-1]
        out["b1"] = {"sigma_hat": r["sigma_hat"], "rv": r["b1"]["rv"], "cierre": r["cierre"], "registrada": True}
    for clave, c in (("b1_prev", prev_cierre), ("b1_prov", hoy)):
        try:
            d = L.decidir(c)
            out[clave] = {"sigma_hat": d.sigma_hat, "rv": d.b1["rv"], "rv_bruta": d.rv_b1_bruta, "cierre": d.cierre}
        except Exception as e:  # noqa: BLE001
            out["errores"].append(f"B1 {c.date()}: {e}")
    if "b1" not in out and "b1_prev" in out:
        out["b1"] = {**out["b1_prev"], "registrada": False}
    for clave, c in (("b1p", ult_cierre), ("b1p_prev", prev_cierre)):
        try:
            d = asdict(B.decidir(c))
            out[clave] = {"sigma_hat": d["sigma_hat_prima"], "rv": d["b1prima"]["rv"], "cierre": d["cierre"]}
        except Exception as e:  # noqa: BLE001
            out["errores"].append(f"B1′ {c.date()}: {e}")
    b1p_log = P._jsonl(P.REG["paper_b1p"])
    out["b1p_registrada"] = bool(b1p_log)
    ss = P._json(P.REG["sigma_star"]) or {}
    bc = P._json(P.REG["b1p_congelado"]) or {}
    out["sigma_star"] = ss.get("sigma_star_nuevo") or L.SIGMA_STAR
    out["sigma_star_p"] = P.g(bc, "parametros", "sigma_star_prima")
    return out


def inflacion_motor(es_usa: dict) -> dict | None:
    """Re-simula SOLO la inflación de EE. UU. con el motor v3.1 congelado (filas ≤ 2004), el estado del signal y la misma
    semilla que la emisión semanal (scripts/int11_v3_hoy.py). Devuelve cuantiles en pp y P(> 5 %) (comprobación)."""
    from scripts import int11_v3_hoy as H
    from scripts.int11_corrida import NUCLEO
    from scripts.int11_v3_corrida import cargar_real_v3
    from src.intl import data as D
    from src.intl import escenarios as E
    e = es_usa.get("estado") or {}
    if e.get("inflacion") is None or e.get("brecha") is None:
        return None
    con = D.connect()
    try:
        filas = cargar_real_v3(con)
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001
            pass
    if filas["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    gen = E.Generador(E.Config.v3_1()).ajustar(filas)
    esc = gen.simular_suave("USA", e["inflacion"], e["brecha"], horizonte=1, n_lotes=200, por_lote=H.POR_LOTE,
                            semilla=H.SEED + list(NUCLEO).index("USA"))
    x = 100 * np.expm1(esc.inflacion[:, 0])
    return {**cuantiles(x), "p_mayor_5": float((x > 5).mean()), "p_menor_0": float((x < 0).mean()),
            "p_signal": (es_usa.get("p_inflacion_5") or {}).get("p")}


def datos_consenso() -> dict:
    from src.warehouse import db
    con = db.connect(read_only=True)
    try:
        def serie(sid):
            df = con.execute("select date, value from obs_latest where series_id = ? and value is not null order by date",
                             [sid]).df()
            return pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]))
        ipc = serie("CPIAUCSL")
        out = {"fuentes": []}
        for sid, nom in CONSENSO:
            s = serie(sid)
            if s.empty:
                continue
            f = {"id": sid, "nombre": nom, "valor": float(s.iloc[-1]), "fecha": str(s.index[-1].date())}
            if sid in ("EXPINF1YR", "umich_px1_md"):
                f["error"] = error_previsiones(s, ipc)
                if f["error"]:
                    f["p_mayor_5"] = p_cola_normal(f["valor"], f["error"]["rmse"])
            out["fuentes"].append(f)
        a = (ipc / ipc.shift(12) - 1).dropna()
        if len(a):
            out["ipc"] = {"valor": float(100 * a.iloc[-1]), "mes": str(a.index[-1].date())[:7]}
        return out
    finally:
        con.close()


# ----------------------------------------------------------------------------------------------- gráficos
def _escala(lo: float, hi: float, paso: float = 0.1) -> tuple[float, float]:
    return math.floor(lo / paso) * paso, math.ceil(hi / paso) * paso


def svg_abanico(a: dict, titulo: str, ymin: float, ymax: float, w: int = 300, h: int = 180) -> str:
    """Abanico de hoy (mes 0, valor 0) a 12 meses: bandas p5-p95 y p25-p75, mediana y cero. El motor solo da el punto
    de 12 meses: el tramo intermedio une hoy con ese punto (ilustrativo, no una senda mensual)."""
    from src.report.panel import esc, pct
    L, R, T, B = 40, 64, 18, 22

    def X(m):
        return L + (w - L - R) * m / 12

    def Y(v):
        return T + (h - T - B) * (ymax - v) / (ymax - ymin)
    x0, x1, y0 = X(0), X(12), Y(0)
    p = [f'<svg class="chart qh-fan" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(titulo)}: mediana {pct(a["p50"])}, '
         f'rango 90 % {pct(a["p5"])} a {pct(a["p95"])}">']
    paso = 0.2 if ymax - ymin > 0.8 else 0.1
    v = ymin
    while v <= ymax + 1e-9:
        p.append(f'<line class="grid" x1="{L}" x2="{x1:.1f}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 f'<text class="tick" x="{L - 4}" y="{Y(v) + 4:.1f}" text-anchor="end">{pct(v)}</text>')
        v += paso
    p.append(f'<polygon class="qh-f95" points="{x0:.1f},{y0:.1f} {x1:.1f},{Y(a["p95"]):.1f} {x1:.1f},{Y(a["p5"]):.1f}"/>'
             f'<polygon class="qh-f50" points="{x0:.1f},{y0:.1f} {x1:.1f},{Y(a["p75"]):.1f} {x1:.1f},{Y(a["p25"]):.1f}"/>'
             f'<line class="qh-zero" x1="{L}" x2="{x1:.1f}" y1="{y0:.1f}" y2="{y0:.1f}"/>'
             f'<line class="qh-med" x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{Y(a["p50"]):.1f}"/>'
             f'<circle class="med" cx="{x1:.1f}" cy="{Y(a["p50"]):.1f}" r="4"/>')
    # etiquetas directas en el extremo (evitando solapes mínimos)
    etq, ult = [], None
    for k in ("p95", "p75", "p50", "p25", "p5"):
        yy = Y(a[k]) + 4
        if ult is not None and yy - ult < 11:
            yy = ult + 11
        etq.append(f'<text class="{"lab" if k == "p50" else "val"}" x="{x1 + 6:.1f}" y="{yy:.1f}">{k} {pct(a[k])}</text>')
        ult = yy
    p += etq
    p.append(f'<text class="tick" x="{x0:.1f}" y="{h - 6}">hoy</text><text class="tick" x="{x1:.1f}" y="{h - 6}" '
             f'text-anchor="end">12 meses</text><text class="lab" x="{L}" y="12">{esc(titulo)}</text></svg>')
    return "".join(p)


def svg_inflacion(m: dict, fuentes: list[dict], ipc: dict | None, w: int = 640) -> str:
    """Una fila por fuente sobre el mismo eje de inflación (pp): el motor como banda p5-p95 / p25-p75 + mediana; el
    consenso como puntos. Línea vertical en el 5 %."""
    from src.report.panel import esc, num
    filas = [("Motor INT-11 (12 meses)", m)] + [(f["nombre"], f) for f in fuentes]
    if ipc:
        filas.append((f"IPC actual (12 m, {ipc['mes']})", {"valor": ipc["valor"]}))
    lo, hi = min(-2.0, m["p5"]), max(8.0, m["p95"], *[f.get("valor", 0) for _, f in filas[1:]])
    lo, hi = _escala(lo, hi, 2.0)
    L, R, fila, T = 250, 20, 30, 22
    h = T + fila * len(filas) + 20

    def X(v):
        return L + (w - L - R) * (v - lo) / (hi - lo)
    p = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Inflación a 12 meses: motor frente al consenso">']
    v = lo
    while v <= hi + 1e-9:
        p.append(f'<line class="grid" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T - 6}" y2="{h - 18}"/>'
                 f'<text class="tick" x="{X(v):.1f}" y="{h - 4}" text-anchor="middle">{num(v, 0)} %</text>')
        v += 2.0
    p.append(f'<line class="qh-cinco" x1="{X(5):.1f}" x2="{X(5):.1f}" y1="{T - 10}" y2="{h - 18}"/>'
             f'<text class="val" x="{X(5) + 4:.1f}" y="{T - 10}">umbral 5 %</text>')
    for i, (nom, f) in enumerate(filas):
        y = T + fila * i + fila / 2
        p.append(f'<text class="lab" x="{L - 8}" y="{y + 4:.1f}" text-anchor="end">{esc(nom)}</text>')
        if "p50" in f:
            p.append(f'<rect class="qh-f95" x="{X(f["p5"]):.1f}" y="{y - 8:.1f}" width="{X(f["p95"]) - X(f["p5"]):.1f}" height="16" rx="3"/>'
                     f'<rect class="qh-f50" x="{X(f["p25"]):.1f}" y="{y - 8:.1f}" width="{X(f["p75"]) - X(f["p25"]):.1f}" height="16" rx="3"/>'
                     f'<circle class="med" cx="{X(f["p50"]):.1f}" cy="{y:.1f}" r="5"/>'
                     f'<text class="val" x="{X(f["p95"]) + 4:.1f}" y="{y + 4:.1f}">mediana {num(f["p50"], 1)} %</text>')
        else:
            p.append(f'<circle class="qh-pt" cx="{X(f["valor"]):.1f}" cy="{y:.1f}" r="5"/>'
                     f'<text class="val" x="{X(f["valor"]) + 8:.1f}" y="{y + 4:.1f}">{num(f["valor"], 2)} %</text>')
    p.append("</svg>")
    return "".join(p)


# ----------------------------------------------------------------------------------------------- sección
def _ids_hoy(s: dict, es: dict | None) -> tuple[list[str], str]:
    from src.report import panel as P
    hl = P.atlas_resaltados(s, es)
    motivos = list(dict.fromkeys(m for v in hl.values() for m in v.split("; ")))
    return list(hl), "; ".join(motivos)


def sec_que_hacer(s: dict, es: dict | None) -> str:
    from src.report import panel as P
    esc, num, pct, tabla = P.esc, P.num, P.pct, P.tabla
    out = []
    # 1. recomendación principal ------------------------------------------------------------------------------
    try:
        dc = datos_cartera()
    except Exception as e:  # noqa: BLE001
        dc = {"errores": [f"{type(e).__name__}: {e}"], "sigma_star": 0.1702, "sigma_star_p": 0.16674}
    rec = recomendacion(dc.get("b1"), dc.get("b1_prev"), dc.get("b1p"), dc["sigma_star"], dc.get("sigma_star_p") or 0.16674)
    if rec["ok"]:
        dm = rec.get("delta_mes")
        cambio = ("sin cambio frente al mes pasado" if dm is not None and abs(dm) < 1e-9 else
                  f"{num(100 * dm, 1, ' pp', True)} frente al mes pasado" if dm is not None else "primer mes registrado")
        bp = rec.get("b1p")
        prov = dc.get("b1_prov")
        mov = (f"σ̂ pasó de {pct(rec.get('sigma_prev'), 1)} ({esc(rec.get('cierre_prev'))}) a {pct(rec['sigma_hat'], 1)} "
               f"({esc(rec['cierre'])})" if rec.get("sigma_prev") is not None else "")
        out.append(
            f'<div class="card qh-rec"><p class="muted">Recomendación de hoy · regla B1 · cierre {esc(rec["cierre"])}'
            f'{" (registrada)" if g_(dc, "b1", "registrada") else " (ensayo, sin registrar)"}</p>'
            f'<p class="qh-num">Bolsa <strong>{num(100 * rec["rv"], 0)} %</strong> <span class="muted">· renta fija '
            f'{num(100 * rec["rf"], 0)} % · oro {num(100 * rec["oro"], 0)} %</span></p>'
            f'<p class="big">{esc(rec["frase"])}</p>'
            f'<p>Frente a la base 70/15/15: <strong>{num(100 * rec["delta_base"], 1, " pp", True)}</strong> de bolsa · '
            f'{esc(cambio)}{" (" + mov + ")" if mov else ""}. Recortaría si la volatilidad pasara de '
            f'<strong>{pct(rec["sigma_recorte"], 1)}</strong> (umbral {pct(rec["sigma_star"], 2)} + margen de 2,5 pp).</p>'
            f'<p><span class="badge b-ok"><span aria-hidden="true">●</span> B1 es {esc(FRASE_B1)}</span></p>'
            + P.barra_segmentada({"rv": rec["rv"], "rf": rec["rf"], "oro": rec["oro"]}, "Cartera sugerida hoy")
            + '<ul class="legend inline"><li><i class="sw s1"></i>Renta variable</li><li><i class="sw s2"></i>Renta fija</li>'
              '<li><i class="sw s3"></i>Oro</li></ul>'
            + P.medidor(rec["sigma_hat"], rec["sigma_star"], "B1: volatilidad de 12 meses (bolsa EE. UU. en EUR)")
            + (P.medidor(bp["sigma_hat"], bp["sigma_star"], f"B1′: previsión HAR del mes siguiente (cierre {bp['cierre']})")
               + f'<p class="small">B1′ dice bolsa <strong>{num(100 * bp["rv"], 0)} %</strong>'
                 + (f' (el mes anterior su σ̂′ era {pct(g_(dc, "b1p_prev", "sigma_hat"), 1)})' if dc.get("b1p_prev") else "")
                 + f'; recortaría con σ̂′ ≥ {pct(bp["sigma_recorte"], 1)}. '
                 + ("Registro en vivo de B1′ activo." if dc.get("b1p_registrada") else
                    "B1′ aún no registra en vivo (primer cierre registrable 2026-11-30): es un ensayo en modo lectura.")
                 + "</p>" if bp else "")
            + (f'<p class="small">Lectura provisional si el mes cerrara hoy ({esc(prov["cierre"])}): σ̂ '
               f'{pct(prov["sigma_hat"], 1)} → bolsa {num(100 * prov["rv"], 0)} %. La decisión oficial es la del cierre de mes.</p>' if prov else "")
            + '<p class="small">Por qué esta regla y no otra: en las pruebas de desarrollo (P-DEV-FACT, 1975-2004, en EUR) B1 '
              'tuvo una caída máxima de −33 % frente a −42 % de la cartera estática y menos volatilidad (12,7 % frente a 14,4 %), '
              'a cambio de ≈ 0,8 pp menos de rentabilidad al año; ninguna regla de régimen (V1-V3) la mejoró. No promete '
              'más rentabilidad: promete caer menos cuando la bolsa se agita.</p>'
            + "".join(f'<p class="small nd">{esc(x)}</p>' for x in dc.get("errores", [])) + "</div>")
    else:
        out.append(f'<div class="card"><p>Recomendación de cartera: {P.ND}.</p>'
                   + "".join(f'<p class="small nd">{esc(x)}</p>' for x in dc.get("errores", [])) + "</div>")

    # 2. abanicos ----------------------------------------------------------------------------------------------
    paises = (es or {}).get("paises") or {}
    acf = (es or {}).get("acierto_medido_fase_D") or {}
    if paises:
        ps = [c for c in PAISES_ABANICO if c in paises and (paises[c].get("abanicos"))]
        opts = "".join(f'<option value="{esc(c)}">{esc(P.NOMBRE_PAIS.get(c, c))}</option>' for c in ps)
        bloques = []
        for c in ps:
            ab = paises[c]["abanicos"]
            vals = [v for a in ab.values() for v in (a["p5"], a["p95"])]
            ymin, ymax = _escala(min(min(vals), -0.1), max(vals), 0.1)
            cub = P.g(acf, "pais", c, default={}) or {}
            celdas = []
            for k, etq in ACTIVOS:
                a = ab.get(k)
                if not a:
                    continue
                celdas.append(f'<div class="qh-cel">{svg_abanico(a, etq, ymin, ymax)}'
                              f'<p class="small"><strong>P(pérdida real) {pct(a.get("p_neg"))}</strong> · '
                              f'acierto pasado del rango 90 %: <strong>{pct(cub.get(k))}</strong></p></div>')
            r = paises[c]
            bloques.append(
                f'<div class="qh-blk" data-qh="{esc(c)}"{"" if c == ps[0] else " hidden"}>'
                f'<p class="small">Partida: {esc(P.REGIMEN_NOMBRE.get(r.get("regimen_dominante"), r.get("regimen_dominante") or "—"))} · '
                f'P(bolsa real ≤ −20 %) {pct(P.g(r, "p_caida_bolsa_20", "p"))} · P(inflación &gt; 5 %) {pct(P.g(r, "p_inflacion_5", "p"))}</p>'
                f'<div class="qh-grid">{"".join(celdas)}</div></div>')
        v = (es or {}).get("ventana") or {}
        out.append(
            '<div class="card"><h3>Con qué seguridad: abanicos a 12 meses</h3>'
            f'<p>Rentabilidad <strong>real</strong> (descontada la inflación, moneda local) de {esc(v.get("desde") or "—")} a '
            f'{esc(v.get("hasta") or "—")}. Banda clara = 90 % de los escenarios (p5-p95); banda oscura = 50 % (p25-p75); '
            'línea = mediana. «Acierto pasado» = cuántas veces el rango del 90 % contuvo lo que de verdad pasó en ese país '
            f'(desarrollo 1876-2004, sin usar sus propios datos); global {pct(acf.get("global"), 0)}: si fuera perfecto sería 90 %.</p>'
            f'<label class="sel">País <select id="qh-pais">{opts}</select></label>{"".join(bloques)}'
            '<p class="small">El motor solo da el punto de 12 meses; el tramo intermedio une hoy con ese punto (no es una senda '
            'mensual). Validado solo en el pasado, no confirmado fuera de muestra.</p></div>')

    # 3. inclinación por activo -----------------------------------------------------------------------------
    try:
        atlas = P._json(P.ATLAS) or {}
        ids, porque = _ids_hoy(s, es)
        usa_ab = P.g(es or {}, "paises", "USA", "abanicos", default={}) or {}
        inc = inclinaciones(rec, usa_ab, atlas, ids)
        filas = []
        for d in inc:
            cls = {"▲": "qh-up", "▼": "qh-down"}.get(d["flecha"], "qh-flat")
            nv = d.get("direccion_no_validada")
            filas.append([f'<span class="qh-arr {cls}" aria-hidden="true">{d["flecha"]}</span> <strong>{esc(d["nombre"])}</strong>',
                          f'<strong>{esc(d["accion"])}</strong>',
                          esc(d["fundamento"]) + (f' <span class="muted">(dirección no validada: {nv})</span>' if nv and nv != "?" else ""),
                          _badge_nivel(d["evidencia"]),
                          f'{pct(d["p_perdida"])}<br><span class="muted">mediana {pct(d["p50"])}</span>'])
        filas.append(['<span class="qh-arr qh-flat" aria-hidden="true">►</span> <strong>Tus acciones y ETF</strong>',
                      "<strong>neutral</strong>",
                      "Sin regla validada para valores concretos: su peso dentro de la renta variable no lo decide ninguna "
                      "prueba. La parte de bolsa total la marca B1 (pestaña «Mis activos» para su riesgo y beta).",
                      _badge_nivel("no validado"), "—"])
        out.append('<div class="card"><h3>Inclinación por activo (EE. UU.)</h3>'
                   f'<p class="small">Regímenes de hoy que aplican: {esc(porque or "ninguno")}. Reglas fijas: la bolsa sigue a B1; '
                   'el resto solo se mueve si el atlas tiene un resultado <em>establecido con lo que se sabe a tiempo</em> '
                   'para el régimen de hoy. Nada se ha ajustado con datos de 2005 en adelante. Si no hay evidencia, ►.</p>'
                   + tabla(["activo", "qué hacer", "por qué", "evidencia", "P(pérdida real 12 m) · motor"], filas)
                   + '<p class="small">P(pérdida real) y la mediana vienen del motor y son contexto de riesgo, no una señal de '
                     'compra o venta: el motor no se validó para elegir activos. Recordatorio honesto: ninguna regla de régimen '
                     'batió a B1 (P-DEV-FACT) y la línea de aprendizaje automático está cerrada.</p></div>')
    except Exception as e:  # noqa: BLE001
        out.append(f'<div class="card"><p>Inclinación por activo: {P.ND} ({esc(type(e).__name__)}: {esc(e)}).</p></div>')

    # 4. motor frente al consenso ---------------------------------------------------------------------------
    out.append(P.seccion_segura(sec_consenso, es))
    out.append(f'<p class="disc"><strong>No es asesoramiento financiero; uso personal.</strong> {esc(P.AVISO_GENERAL)}</p>')
    return "\n".join(out)


def _val(fuentes: list[dict], sid: str):
    return next((f["valor"] for f in fuentes if f["id"] == sid), None)


def g_(d, *ks):
    from src.report.panel import g
    return g(d, *ks)


def _badge_nivel(n: str) -> str:
    from src.report.panel import esc
    cls, ico = {"establecido": ("ok", "●"), "frágil": ("warn", "◐")}.get(n, ("no", "○"))
    return f'<span class="badge b-{cls}"><span aria-hidden="true">{ico}</span> {esc(n)}</span>'


def sec_consenso(es: dict | None) -> str:
    from src.report import panel as P
    esc, num, pct = P.esc, P.num, P.pct
    usa = P.g(es or {}, "paises", "USA", default={}) or {}
    m = inflacion_motor(usa)
    cons = datos_consenso()
    if not m:
        return f'<div class="card"><h3>El motor frente al consenso</h3><p>{P.ND}.</p></div>'
    fu = cons["fuentes"]
    filas = [["<strong>Motor INT-11</strong> (14 países, 1870-2004)", f"<strong>{num(m['p50'], 1)} %</strong> "
              f"<span class='muted'>(p5 {num(m['p5'], 1)} · p95 {num(m['p95'], 1)})</span>",
              f"<strong>{pct(m['p_mayor_5'])}</strong>", "simulación del motor"]]
    for f in fu:
        er = f.get("error")
        filas.append([esc(f["nombre"]), f"{num(f['valor'], 2)} % <span class='muted'>({esc(f['fecha'][:7])})</span>",
                      pct(f.get("p_mayor_5")) if f.get("p_mayor_5") is not None else "—",
                      (f"error típico {num(er['rmse'], 2)} pp (sesgo {num(er['sesgo'], 2, ' pp', True)}), {er['n']} previsiones "
                       f"{esc(er['desde'])} → {esc(er['hasta'])}" if er else
                       "media de 5 años: no es una previsión a 12 meses")])
    ac = P.acierto_int11().get("infl5") or {}
    cle = next((f for f in fu if f["id"] == "EXPINF1YR"), {})
    mi = next((f for f in fu if f["id"] == "umich_px1_md"), {})
    aviso_rep = ("" if m.get("p_signal") is None or abs(m["p_mayor_5"] - m["p_signal"]) < 0.005 else
                 f' (la re-simulación da {pct(m["p_mayor_5"])} y el signal {pct(m["p_signal"])}: diferencia de muestreo)')
    return ('<div class="card"><h3>El motor frente al consenso: inflación de EE. UU. a 12 meses</h3>'
            + svg_inflacion(m, fu, cons.get("ipc"))
            + P.tabla(["fuente", "inflación esperada", "P(inflación > 5 %)", "cómo se calcula la probabilidad"], filas, "num")
            + f'<p><strong>Por qué difieren.</strong> El motor dice P(&gt; 5 %) = {pct(m["p_mayor_5"])}{aviso_rep}, con mediana '
              f'{num(m["p50"], 1)} %. La Fed de Cleveland prevé {num(cle.get("valor"), 1)} % y, con su error histórico, eso deja '
              f'la probabilidad en ≈ {pct(cle.get("p_mayor_5"))}; el mercado descuenta {num(_val(fu, "T5YIE"), 1)} % de media a '
              f'5 años. Los hogares de Michigan ({num(mi.get("valor"), 1)} %) la ponen en ≈ {pct(mi.get("p_mayor_5"))}: son '
              'la única fuente que se acerca al motor. El motor aprendió de 14 países desde 1870, con guerras, los años 70 y '
              'bancos centrales sin credibilidad; en esa historia, una inflación por encima del 3 % se escapaba a menudo. Por '
              f'eso tiene <strong>colas anchas</strong> (p95 {num(m["p95"], 1)} %) y no ve lo que el mercado sí pone en '
              'precio hoy (expectativas ancladas, un banco central independiente).</p>'
            + f'<p><strong>¿Debería ser mayor?</strong> La evidencia apunta a lo contrario: en desarrollo (≤ 2004), cuando la '
              f'inflación estaba cerca del 3 % como hoy, el motor daba de media {pct(ac.get("p_media_cerca"))} y la inflación '
              f'pasó del 5 % solo el {pct(ac.get("frec_cerca"))} de las veces: <strong>sobrestima</strong> esta probabilidad. '
              'Una cifra más alta solo se justificaría con información que el motor no usa (aranceles, déficit, presión '
              'sobre la Fed), y el mercado, que sí la ve, apunta más abajo. El motor no se cambia: se compara.</p>'
            + '<p class="small">Probabilidad del consenso = Normal centrada en la previsión con su error típico (raíz del error '
              'cuadrático medio) medido con previsiones hechas hasta 2003 frente a la inflación realizada 12 meses después '
              '(IPC de EE. UU.). Supuesto simple y declarado; no es una probabilidad que publiquen ellos. La implícita del '
              'mercado incluye primas (liquidez, riesgo de inflación) y mira a 5 años.</p></div>')


CSS = """
.qh-rec{border-color:var(--s1);box-shadow:inset 4px 0 0 var(--s1)}.qh-num{font-size:20px;margin:4px 0}.qh-num strong{font-size:40px;font-weight:700}
.qh-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;margin:8px 0}
.qh-cel{border:1px solid var(--grid);border-radius:6px;padding:6px 8px}
.chart .qh-f95{fill:var(--band2)}.chart .qh-f50{fill:var(--band3)}.chart .qh-med{stroke:var(--s1);stroke-width:2;fill:none}
.chart .qh-zero{stroke:var(--ink2);stroke-width:1;stroke-dasharray:3 3}.chart .qh-cinco{stroke:var(--crit);stroke-width:1.5;stroke-dasharray:4 3}
.chart .qh-pt{fill:var(--s2);stroke:var(--surface);stroke-width:2}
.qh-arr{display:inline-block;width:1.2em;font-size:16px}.qh-up{color:var(--good)}.qh-down{color:var(--crit)}.qh-flat{color:var(--muted)}
"""
JS = """
(function(){var s=document.getElementById('qh-pais');if(!s)return;
function f(c){[].forEach.call(document.querySelectorAll('.qh-blk'),function(d){d.hidden=d.dataset.qh!==c})}
s.addEventListener('change',function(){f(s.value)});f(s.value);})();
"""
