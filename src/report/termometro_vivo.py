"""Termómetro de recesión INFORMATIVO, parte en vivo (docs/int/TERMOMETRO_diseno_v1.md §3, §4, §8, §9).

Resultado de la puerta (definitivo, `research/int/termometro_puerta_v2.json`): T1 (riesgo de ENTRAR) no pasó → solo sus
indicadores; T2 (probabilidad de SALIR) sí → se muestra solo para los países "en recesión" según el fechado trimestral en
vivo (§3), salvo DNK y JPN (sin bolsa mensual: solo indicadores). Los 4 países de prueba (AUS, CHE, CAN, IRL) no tienen
puerta propia de T2 (la puerta se midió en el núcleo): solo indicadores.

Vive en src/report/ y no en src/intl/ porque lee datos ≥ 2005: el único acceso a datos de src/intl/ sigue siendo
`load_dev` (corte 2004-12; tests/test_intl_panel.py). Aquí:
- Datos: OCDE (tipos, IPC, bolsa, PIB trimestral) y BIS (crédito/PIB) del warehouse, `obs_latest` hasta la fecha de corte,
  SIN corte 2004 y NUNCA JST (`_serie` falla cerrado). No hay vintages de estas series: se usa la última publicación con
  las fechas "as of" de `src/intl/lags.py` y `src/intl/termometro.py` (niveles revisados; declarado en el diseño, §3).
- Traducción y fórmulas: las de `src/intl/termometro.py` (`mensuales`, `traducir`, `fechado_trimestral`,
  `estado_mensual`, `b1_vivo`, `aplicar_cal`) y `src/intl/int4.logit_pred`; el bloque mensual (curva, tipo a 3 meses,
  IPC interanual, bolsa a 12 meses) repite las 4 transformaciones de `src/intl/panel.mensual` sin el corte (un test
  comprueba que con corte 2004-12 sale idéntico).
- Parámetros congelados: `final` del JSON de la puerta (modelo T2, rectas, recalibración, percentiles p50/p80/p95 de T2).
  Nunca se reajustan. Están redondeados a 4 decimales en el JSON (ver `parametros`).
- Referencias ≤ 2004 que no están en el JSON (percentil histórico de cada indicador y media de cada variable de T2 para
  la contribución al logit) se calculan en cada ejecución con los meses 1960-2004 de las mismas series: solo describen
  la historia de desarrollo, no ajustan nada.
- Fecha de cálculo: el último fin de mes ≤ la fecha pedida (la rejilla de la traducción es mensual).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import int4 as M
from src.intl import lags as Lg
from src.intl import panel as P
from src.intl import termometro as T

REPO = Path(__file__).resolve().parents[2]
CONGELADO = REPO / "research" / "int" / "termometro_puerta_v2.json"

NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
PRUEBA = ["AUS", "CHE", "CAN", "IRL"]
TODOS = NUCLEO + PRUEBA
REF_DESDE, REF_HASTA = pd.Timestamp("1960-01-31"), pd.Timestamp("2004-12-31")
MIN_MESES_PCT = 60          # menos meses ≤ 2004 → sin percentil histórico ("historia corta")

AVISO = ("Informativo, no es una señal de cartera. Modelo histórico 1871-2004; el riesgo de ENTRAR en recesión no superó "
         "su puerta y se muestran solo sus indicadores; la probabilidad de SALIR sí (con pocas filas: prudencia). "
         "La inflación no se anticipa.")
AVISO_NIVEL = "nivel no calibrado en vivo"

# indicadores que se enseñan (clave del panel mensual sin traducir, etiqueta, unidad, factor para enseñarlo)
INDICADORES = [("C1", "Curva 10a−3m (media 12 m)", "pp", 1.0),
               ("C4", "Difusión de curvas invertidas", "% países", 100.0),
               ("C6", "Bolsa real 12 m (precio)", "%", 100.0),
               ("C2", "Δ5 años crédito/PIB (BIS)", "pp PIB", 1.0),
               ("S4", "Difusión de PIB cayendo", "% países", 100.0)]
VARS_T2 = ["B1 duración de la recesión", "S1 curva", "S2 Δ tipo real corto", "S3 bolsa real", "S4 difusión de PIB cayendo",
           "S5 Δ5 crédito/PIB al entrar"]
BANDAS = [("bajo", "p50"), ("medio", "p80"), ("alto", "p95")]      # < p50, p50-p80, p80-p95; ≥ p95 → muy alto


class ParametrosIncompletos(RuntimeError):
    """Falta algo del `final` congelado: no se muestra nada y NO se reajusta con datos ≥ 2005."""


# ---------------------------------------------------------------- parámetros congelados
def parametros(path: Path = CONGELADO) -> dict:
    """Lee y valida `final` del JSON de la puerta. Falla explícitamente si falta algo necesario para T2 o para la
    traducción de algún país. Aviso declarado: el JSON se escribió con `_r` (4 decimales); la pendiente de la recta
    agrupada de C2 (0,0054) pierde así hasta ≈ 1 % de precisión relativa. Se usa tal cual (es lo congelado); la
    comprobación con corte 2004-12 mide el efecto (tests/test_termometro_vivo.py)."""
    d = json.loads(Path(path).read_text())
    f, falta = d.get("final") or {}, []
    ver = d.get("veredicto", {}).get("pasa_agregado", {})
    if ver.get("T2") is not True:
        falta.append("veredicto: T2 no consta como aprobado")
    if ver.get("T1") is not False:
        falta.append("veredicto: T1 debería constar como NO aprobado (este módulo solo enseña sus indicadores)")
    b2 = (f.get("modelo") or {}).get("T2")
    if not b2 or len(b2) != 1 + 1 + 5 or any(v is None for v in b2):
        falta.append("modelo T2 (constante + B1 + S1-S5)")
    cal = (f.get("cal") or {}).get("T2")
    if not cal or len(cal) != 2 or any(v is None for v in cal):
        falta.append("recalibración T2 (α, β)")
    pct = (f.get("percentiles_referencia") or {}).get("T2") or {}
    if any(pct.get(k) is None for k in ("p50", "p80", "p95")):
        falta.append("percentiles p50/p80/p95 de T2")
    rl = f.get("rectas") or {}
    for ind in T.LINEALES:
        for c in TODOS:
            r = (rl.get(ind) or {}).get(c) or {}
            if r.get("a") is None or r.get("b") is None:
                falta.append(f"recta {ind} {c}")
    if falta:
        raise ParametrosIncompletos(
            "parámetros congelados incompletos en " + str(path) + ": " + "; ".join(falta) + ". Propuesta: volver a "
            "serializar `final` sin redondeo con el mismo código y los mismos datos ≤ 2004 (rectas con TODO, "
            "recalibración con todas las filas ≤ 2003), comprobar que redondea a lo publicado y fijarlo con un commit; "
            "nunca reajustar con datos ≥ 2005.")
    aprob = set(d["veredicto"]["paises_con_probabilidad"]["T2"])
    return {"b_T2": np.array(b2, float), "cal_T2": (float(cal[0]), float(cal[1])),
            "pct_T2": {k: float(pct[k]) for k in ("p50", "p80", "p95")}, "rectas": rl,
            "paises_T2": [c for c in NUCLEO if c in aprob and c not in T.SIN_BOLSA],
            "fuente": str(path), "procedencia_puerta": d.get("procedencia")}


# ---------------------------------------------------------------- datos en vivo (sin corte 2004, nunca JST)
def _serie(con, sid: str, corte: pd.Timestamp) -> pd.Series:
    if sid.startswith("jst_") or not D.permitida(sid):
        raise D.FactorCutoffError(f"{sid}: el termómetro en vivo solo lee OCDE/BIS (nunca JST)")
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date <= ? "
                     "order by date", [sid, corte.date()]).df()
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]), name=sid)
    if s.index.duplicated().any():
        raise D.FactorCutoffError(f"{sid}: fechas repetidas en obs_latest")
    return s


def fin_de_mes(fecha) -> pd.Timestamp:
    """Último fin de mes ≤ `fecha`."""
    f = pd.Timestamp(fecha).normalize()
    return f if f == f + pd.offsets.MonthEnd(0) else f - pd.offsets.MonthEnd(1)


def cargar(con, fecha) -> tuple[pd.DataFrame, dict, dict, pd.Timestamp]:
    """Bloque mensual "as of" (curva, tipo a 3 meses, IPC interanual, bolsa 12 m; mismas transformaciones que
    src/intl/panel.mensual), crédito/PIB del BIS y PIB trimestral, hasta el fin de mes `corte` ≤ `fecha`."""
    corte = fin_de_mes(fecha)
    rej = pd.date_range("1950-01-31", corte, freq="ME")
    filas, bis, pib = [], {}, {}
    for c in TODOS:
        lc = c.lower()
        m = {k: P._mensual_completa(_serie(con, f"oecd_{k}_{lc}" if k != "cpi" else f"oecd_cpi_{lc}_idx", corte))
             for k in ("irlt", "ir3m", "cpi", "share")}
        v = {"tipo_10a": (m["irlt"], f"oecd_irlt_{lc}"), "tipo_3m": (m["ir3m"], f"oecd_ir3m_{lc}"),
             "ipc_yoy": (np.log(m["cpi"]).diff(12), f"oecd_cpi_{lc}_idx"),
             "bolsa_12m": (np.log(m["share"]).diff(12), f"oecd_share_{lc}")}
        df = pd.DataFrame({k: Lg.asof(s, sid, rej) for k, (s, sid) in v.items()}, index=rej)
        df["curva"] = df["tipo_10a"] - df["tipo_3m"]
        df["pais"] = c
        filas.append(df.reset_index(names="fecha"))
        if not (s := _serie(con, f"bis_creditgap_{D.ISO2[c]}_ratio", corte)).empty:
            bis[c] = s
        pib[c] = _serie(con, f"oecd_gdpq_{lc}", corte)
    pm = pd.concat(filas, ignore_index=True).set_index(["pais", "fecha"]).sort_index()
    return pm, bis, pib, corte


# ---------------------------------------------------------------- cálculo
def prob_salida(tr: dict, est: pd.DataFrame, c: str, b: np.ndarray, cal: tuple) -> tuple[np.ndarray, np.ndarray]:
    """Probabilidad recalibrada de salir (T2) cada mes en recesión (NaN fuera) y la matriz de variables [B1, S1-S5].
    Igual que `referencia_cal` de scripts/termometro_puerta_v2.py: S5 = C2 traducida en el primer mes conocido en
    recesión, arrastrada mientras dure."""
    rej = est.index
    x = {k: tr[k][c].reindex(rej) for k in ("C1", "C2", "C5", "C6", "S4")}
    dentro = (est["en_rec"] == 1).to_numpy()
    inicio = dentro & ~np.r_[False, dentro[:-1]]
    s5 = pd.Series(np.where(inicio, x["C2"].to_numpy(), np.nan), index=rej).ffill().where(dentro)
    Z = np.column_stack([T.b1_vivo(est, "T2"), x["C1"], x["C5"], x["C6"], x["S4"], s5])
    p = T.aplicar_cal(M.logit_pred(b, Z), cal)
    p[~dentro] = np.nan
    return p, Z


def banda(p: float, pct: dict) -> str:
    for nom, k in BANDAS:
        if p < pct[k]:
            return nom
    return "muy alto"


def _pct(hist: np.ndarray, v: float) -> tuple[int | None, int]:
    h = hist[np.isfinite(hist)]
    if not np.isfinite(v) or len(h) < MIN_MESES_PCT:
        return None, int(len(h))
    return int(round(float((h <= v).mean() * 100))), int(len(h))


def _q_conocido(pib: pd.Series, corte: pd.Timestamp):
    q = pib.dropna().index.to_period("Q")
    q = q[(q.to_timestamp(how="end").normalize() + pd.Timedelta(days=T.RETRASO_PIB)) <= corte]
    return q.max() if len(q) else None


def calcular(pm: pd.DataFrame, bis: dict, pib: dict, corte: pd.Timestamp, par: dict) -> dict:
    mens = T.mensuales(pm, bis, pib, NUCLEO, TODOS)
    tr = T.traducir(mens, par["rectas"], TODOS)
    rej = mens["C1"].index
    ref = (rej >= REF_DESDE) & (rej <= REF_HASTA)
    est, p2, Z2 = {}, {}, {}
    for c in TODOS:
        if pib.get(c) is None or pib[c].dropna().empty:
            continue
        fq = T.fechado_trimestral(pib[c].dropna())
        est[c] = T.estado_mensual(fq, rej, pib[c].dropna().index.min())
        p2[c], Z2[c] = prob_salida(tr, est[c], c, par["b_T2"], par["cal_T2"])
    # media ≤ 2004 de las variables de T2 en los meses en recesión con probabilidad (núcleo con T2): centro de las
    # contribuciones al logit
    zs = [Z2[c][ref & np.isfinite(p2[c])] for c in par["paises_T2"] if c in Z2]
    centro = np.concatenate(zs).mean(axis=0) if zs and sum(len(z) for z in zs) else np.full(6, np.nan)
    i = len(rej) - 1
    paises = {}
    for c in TODOS:
        filas_ind = {}
        for k, lab, uni, fac in INDICADORES:
            serie = mens[k][c] if c in mens[k] else pd.Series(np.nan, index=rej)
            v = float(serie.iloc[i])
            pc, n = _pct(serie.to_numpy()[ref], v)
            filas_ind[k] = {"indicador": lab, "unidad": uni, "valor": None if not np.isfinite(v) else round(v * fac, 2),
                            "percentil_hasta_2004": pc, "meses_hist": n}
        e = est.get(c)
        en = None if e is None or not np.isfinite(e["en_rec"].iloc[i]) else bool(e["en_rec"].iloc[i])
        uq = _q_conocido(pib[c], corte) if c in pib else None
        estado = {"en_recesion": en, "ultimo_trimestre_pib": None if uq is None else str(uq),
                  "meses_desde_entrada": None if not en else int(e["meses_desde_entrada"].iloc[i])}
        salida = None
        if en:
            if c not in par["paises_T2"]:
                salida = {"motivo": "sin bolsa mensual (solo indicadores)" if c in T.SIN_BOLSA
                          else "país de prueba: sin puerta propia de T2 (solo indicadores)"}
            elif not np.isfinite(p2[c][i]):
                salida = {"motivo": "falta algún indicador de T2 este mes"}
            else:
                contrib = par["b_T2"][1:] * (Z2[c][i] - centro)
                j = int(np.nanargmax(np.abs(contrib)))
                salida = {"probabilidad": round(float(p2[c][i]), 3), "banda": banda(float(p2[c][i]), par["pct_T2"]),
                          "aviso": AVISO_NIVEL,
                          "empuja_mas": {"variable": VARS_T2[j], "contribucion_logit": round(float(contrib[j]), 3),
                                         "sentido": "a favor de salir" if contrib[j] > 0 else "en contra de salir"},
                          "contribuciones_logit": {VARS_T2[k]: round(float(v), 3) for k, v in enumerate(contrib)}}
        paises[c] = {"grupo": "usa" if c == "USA" else ("nucleo" if c in NUCLEO else "prueba"), "estado": estado,
                     "indicadores": filas_ind, "salida_12m": salida}
    return {"fecha_calculo": str(corte.date()), "aviso": AVISO, "paises": paises,
            "en_recesion": [c for c, v in paises.items() if v["estado"]["en_recesion"]],
            "percentiles_T2": par["pct_T2"], "parametros": par["fuente"],
            "procedencia_puerta": par.get("procedencia_puerta"),
            "metodo": {"contribucion": "b_k · (x_k − media ≤ 2004 de los meses en recesión del núcleo), en unidades "
                                       "del logit antes de recalibrar",
                       "percentil_indicador": f"frente a los meses 1960-2004 del propio país (≥ {MIN_MESES_PCT} meses)",
                       "datos": "obs_latest (sin vintages: niveles revisados), retrasos as of de src/intl/lags.py "
                                "y src/intl/termometro.py"}}


def termometro(con, fecha, par: dict | None = None) -> dict:
    par = par or parametros()
    pm, bis, pib, corte = cargar(con, fecha)
    return calcular(pm, bis, pib, corte, par)


# ---------------------------------------------------------------- Markdown
def _f(v, suf=""):
    return "—" if v is None else f"{v}{suf}"


def _fila(c: str, d: dict) -> str:
    e, ind = d["estado"], d["indicadores"]
    st = {True: "**en recesión**", False: "no", None: "sin dato"}[e["en_recesion"]]
    celdas = [c, f"{st} ({_f(e['ultimo_trimestre_pib'])})"]
    celdas += [f"{_f(ind[k]['valor'])} (p{_f(ind[k]['percentil_hasta_2004'])})" for k, *_ in INDICADORES]
    s = d["salida_12m"]
    if s is None:
        celdas.append("—")
    elif "probabilidad" in s:
        celdas.append(f"{s['banda']} ({s['probabilidad']:.2f})")
    else:
        celdas.append(f"solo indicadores: {s['motivo']}")
    return "| " + " | ".join(celdas) + " |"


def markdown(res: dict) -> str:
    cab = ["país", "en recesión (último PIB)"] + [f"{lab} ({uni})" for _, lab, uni, _ in INDICADORES] + \
          ["prob. de salir ≈ 12 m"]
    head = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    P_ = res["paises"]
    pct = res["percentiles_T2"]
    out = [f"## Termómetro de recesión (informativo) — {res['fecha_calculo']}", "",
           "> [!note] Informativo", f"> {res['aviso']}", "",
           "**EE. UU.**", "", *head, _fila("USA", P_["USA"]), "",
           "**Núcleo (resto de los 14)**", "", *head, *[_fila(c, P_[c]) for c in NUCLEO if c != "USA"], "",
           "**Países de prueba (sin puerta propia: solo indicadores)**", "", *head,
           *[_fila(c, P_[c]) for c in PRUEBA], ""]
    rec = [c for c in res["en_recesion"] if (P_[c]["salida_12m"] or {}).get("probabilidad") is not None]
    if rec:
        out.append("**Probabilidad de salir en ≈ 12 meses** (solo países en recesión; banda frente a los meses en "
                   f"recesión 1960-2004 del núcleo: bajo < {pct['p50']:.2f} ≤ medio < {pct['p80']:.2f} ≤ alto < "
                   f"{pct['p95']:.2f} ≤ muy alto; entre paréntesis la probabilidad, {AVISO_NIVEL}):")
        out.append("")
        for c in rec:
            s = P_[c]["salida_12m"]
            em = s["empuja_mas"]
            out.append(f"- {c}: **{s['banda']}** ({s['probabilidad']:.2f}; {AVISO_NIVEL}), en recesión desde hace "
                       f"{P_[c]['estado']['meses_desde_entrada']} meses; lo que más pesa: {em['variable']} "
                       f"({em['contribucion_logit']:+.2f} en el logit, {em['sentido']}).")
        out.append("")
    elif not res["en_recesion"]:
        out += ["Ningún país está en recesión según el fechado trimestral en vivo: no se muestra ninguna probabilidad "
                "de salir (y la de entrar no superó su puerta).", ""]
    out.append("Método: «en recesión» = la suma de 4 trimestres del PIB real (OCDE) cae dos trimestres seguidos (sale "
               "con dos subidas seguidas), dato conocido 75 días tras el trimestre. Entre paréntesis tras cada "
               "indicador, su percentil frente a los meses 1960-2004 del propio país. Modelo y escalas congelados "
               "(≤ 2004); datos revisados, no de primera publicación.")
    return "\n".join(out) + "\n"
