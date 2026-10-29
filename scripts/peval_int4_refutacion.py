"""P-EVAL-INT4: prueba de REFUTACIÓN (una sola vez) de T1 y T2 de INT-4 en el bloqueado JST (años objetivo 2005-2020).
Prerregistro: docs/int/PEVAL_INT4_refutacion_v1.md (v1.0 CONGELADO, NO EJECUTABLE sin decisión registrada del usuario).

PUERTA DOBLE (lo primero que hace `main`, antes de importar nada que lea datos):
  1. existe `research/int/PEVAL_INT4_AUTORIZADO`, escrito y commiteado por el usuario, con los campos del §7 del
     prerregistro (autoriza: usuario; fecha; motivo; decision), y no existe ya la salida (regla de un solo uso);
  2. árbol de git limpio (src/intl/procedencia.py) con ese fichero rastreado, y el prerregistro y el modelo congelado
     sin cambios (sha256 fijados abajo).
Sin el fichero aborta sin abrir el warehouse: no lee ninguna fila (≤ 2004 ni ≥ 2005) de predictores ni de resultados.

Después, por este orden (cada paso aborta antes del siguiente si algo no cuadra):
  a. Modelo congelado: re-ajuste determinista con datos ≤ 2004 (load_dev) del logit de INT-4 (T1: B1 + C1 C2 C4 C5 C6;
     T2: B1 + S1-S5; núcleo, 1871-2004 sin guerras, todas las filas completas) y comprobación de que sus coeficientes
     son los de research/int/termometro_referencias.json (`final_sin_redondeo.modelo`, b845741) con tolerancia 1e-8.
     El listón B1 se ajusta igual (mismas filas), como `src/intl/int4.congelado`.
  b. Objetivo ≥ 2005: SOLO `jst_{iso}_rgdpmad` (≤ 2020) del núcleo → fechado → filas de T1/T2 con
     scripts/peval_int4_potencia.filas_bloqueado. Si los recuentos no son los de la potencia (178/39, 164/25, 46/25 y los
     mismos años) aborta SIN leer indicadores.
  c. Indicadores ≥ 2005 (≤ 2020): ltrate, stir, tloans, gdp, cpi, eq_tr_real del núcleo; paneles con las fórmulas de
     src/intl/int4.paneles (hasta = 2020).
  d. Predicciones con los coeficientes congelados (sin reajustar nada), estadísticos y veredicto del §5.
Salida: research/int/peval_int4_refutacion.json y .md y una línea en research/trial_log.md.
Uso (solo tras la autorización): .venv/bin/python -m scripts.peval_int4_refutacion
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
AUTORIZACION = REPO / "research" / "int" / "PEVAL_INT4_AUTORIZADO"
SALIDA = REPO / "research" / "int" / "peval_int4_refutacion.json"
DOC = REPO / "docs" / "int" / "PEVAL_INT4_refutacion_v1.md"
DOC_SHA256 = "569bc615305b71085062d387cfbb1930a3213b0f0e36d8aa75d2b74d908435af"   # 93fd9a0
REF_MODELO = REPO / "research" / "int" / "termometro_referencias.json"
REF_MODELO_SHA256 = "6d95d0f309048898f0c491b0cc840373246538ca701a9777d213c6f9a04bfeff"
MOTIVOS = {"decision_B2_B1", "jst_nueva_version"}
CAMPOS = ("autoriza", "fecha", "motivo", "decision")

NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
COLS = {"T1": ["C1", "C2", "C4", "C5", "C6"], "T2": ["S1", "S2", "S3", "S4", "S5"]}
FIN_BLOQUEADO = 2020
VARS_INDICADORES = ["cpi", "tloans", "gdp", "ltrate", "stir", "eq_tr_real"]
TOL_COEF = 1e-8
B_BOOT, SEMILLA = 2000, 0
MIN_EVENTOS, MIN_NO_EVENTOS, MIN_AÑOS_EVENTO = 10, 10, 3
# recuentos del bloqueado ya conocidos (research/int/peval_int4_potencia.json, 10fc87e): (filas, eventos, eventos por
# año objetivo)
ESPERADO = {
    "T1_con_2020": (178, 39, {2008: 10, 2009: 4, 2011: 3, 2012: 6, 2013: 2, 2020: 14}),
    "T1_sin_2020": (164, 25, {2008: 10, 2009: 4, 2011: 3, 2012: 6, 2013: 2}),
    "T2": (46, 25, {2010: 13, 2012: 2, 2013: 3, 2014: 5, 2015: 2}),
}
PRINCIPALES = ("T1_sin_2020", "T2")


class NoAutorizado(SystemExit):
    pass


# ---------------------------------------------------------------- puerta
def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git_rastreado(p: Path) -> bool:
    r = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(p)], capture_output=True)
    return r.returncode == 0


def leer_autorizacion(p: Path) -> dict:
    campos = {}
    for linea in p.read_text().splitlines():
        if ":" in linea and not linea.lstrip().startswith("#"):
            k, v = linea.split(":", 1)
            campos[k.strip().lower()] = v.strip()
    falta = [k for k in CAMPOS if not campos.get(k)]
    if falta:
        raise NoAutorizado(f"{p.name}: faltan campos {falta} (prerregistro §7)")
    if campos["autoriza"].lower() != "usuario":
        raise NoAutorizado(f"{p.name}: solo el usuario autoriza (autoriza: {campos['autoriza']!r})")
    if campos["motivo"] not in MOTIVOS:
        raise NoAutorizado(f"{p.name}: motivo {campos['motivo']!r} no está en {sorted(MOTIVOS)}")
    return campos


def puerta(autorizacion: Path | None = None, salida: Path | None = None) -> dict:
    """Puerta doble. Lanza NoAutorizado (SystemExit) si algo falla. No abre el warehouse."""
    autorizacion = autorizacion or AUTORIZACION
    salida = salida or SALIDA
    if salida.exists():
        raise NoAutorizado(f"{salida.name} ya existe: el bloqueado de P-EVAL-INT4 ya se gastó (un solo uso)")
    if not autorizacion.exists():
        raise NoAutorizado(f"NO AUTORIZADO: falta {autorizacion.relative_to(REPO) if autorizacion.is_relative_to(REPO) else autorizacion} "
                           "(decisión registrada del usuario, prerregistro §7). No se lee nada.")
    campos = leer_autorizacion(autorizacion)
    if not _git_rastreado(autorizacion):
        raise NoAutorizado(f"{autorizacion.name} no está commiteado")
    from src.intl.procedencia import procedencia
    proc = procedencia(exigir_limpio=True)
    if _sha256(DOC) != DOC_SHA256:
        raise NoAutorizado(f"{DOC.name} ha cambiado desde su congelación (sha256 distinto): hace falta una enmienda")
    if _sha256(REF_MODELO) != REF_MODELO_SHA256:
        raise NoAutorizado(f"{REF_MODELO.name} ha cambiado: el modelo congelado no es el prerregistrado")
    return {"autorizacion": campos, "procedencia": proc}


# ---------------------------------------------------------------- (a) modelo congelado (solo ≤ 2004)
def _extra_vacio(a: pd.DataFrame) -> pd.DataFrame:
    """hpnom, money y wage no entran en T1/T2: columnas vacías para no leerlas."""
    return pd.DataFrame(np.nan, index=a.index, columns=["hpnom", "money", "wage"])


def modelo_congelado() -> dict:
    from src.intl import data as D
    from src.intl import int4 as M
    from src.intl import panel as P
    from src.intl import termometro as T
    from src.warehouse import db
    con = D.connect()
    a = P.anual(con)
    con.close()
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in NUCLEO}
    primer = {c: min(v) for c, v in años_pais.items()}
    pan = M.paneles(a, _extra_vacio(a), NUCLEO, NUCLEO, None)
    ref = json.loads(REF_MODELO.read_text())["final_sin_redondeo"]["modelo"]
    out = {}
    for giro, cols in COLS.items():
        f = (M.obj_entrada if giro == "T1" else M.obj_salida)(rec, años_pais, NUCLEO, 1, 1871, True)
        B1, X, y = M.liston(f, giro, rec, primer, pan), M.matriz(f, pan, cols), f.y.to_numpy(float)
        ok = np.isfinite(B1).all(axis=1) & np.isfinite(X).all(axis=1)
        b1 = T.congelar(B1, X, y)
        b0 = M.logit_fit(B1[ok], y[ok])
        dif = float(np.max(np.abs(b1 - np.asarray(ref[giro]))))
        if len(b1) != len(ref[giro]) or dif > TOL_COEF:
            raise SystemExit(f"{giro}: el re-ajuste ≤ 2004 no reproduce el modelo congelado (dif {dif:.2e}); no se "
                             "lee nada ≥ 2005")
        out[giro] = {"b_modelo": b1.tolist(), "b_liston": b0.tolist(), "dif_max_ref": dif,
                     "filas_ajuste": int(ok.sum()), "eventos_ajuste": int(y[ok].sum())}
    return out


# ---------------------------------------------------------------- (b, c) lectura del bloqueado (única, tras la puerta)
LEIDAS: list[str] = []


def leer_bloqueado(con, sid: str) -> pd.Series:
    """Serie anual completa hasta FIN_BLOQUEADO (incluye ≥ 2005). Solo se llama tras la puerta."""
    from src.intl import data as D
    if not D.permitida(sid) or not sid.startswith("jst_"):
        raise SystemExit(f"{sid}: no es una serie JST permitida")
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date <= ? "
                     "order by date", [sid, dt.date(FIN_BLOQUEADO, 12, 31)]).df()
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]).dt.year, name=sid)
    if s.index.duplicated().any():
        raise SystemExit(f"{sid}: años repetidos")
    LEIDAS.append(sid)
    return s


def anual_desde_series(series: dict[str, dict[str, pd.Series]]) -> pd.DataFrame:
    """Panel país × año con las MISMAS derivadas que src/intl/panel.anual (solo las columnas de T1/T2)."""
    filas = []
    for c, cols in series.items():
        df = pd.DataFrame(cols)
        df["pib_real_g"] = np.log(df["rgdpmad"]).diff()
        df["inflacion"] = np.log(df["cpi"]).diff()
        df["credito_pib"] = df["tloans"] / df["gdp"]
        df["pais"] = c
        filas.append(df.reset_index(names="año"))
    return pd.concat(filas, ignore_index=True).set_index(["pais", "año"]).sort_index()


def fechar(rgdp: dict[str, pd.Series]) -> tuple[pd.DataFrame, dict]:
    from src.intl import regimes as G
    rec = pd.concat([G.recesiones_anuales(s).assign(pais=c) for c, s in rgdp.items()], ignore_index=True)
    rec["tipo"] = None                      # el tipo (crisisjst) no se lee ni se usa
    return rec, {c: set(int(a) for a in s.dropna().index) for c, s in rgdp.items()}


def muestras(rec: pd.DataFrame, años: dict) -> dict[str, pd.DataFrame]:
    from scripts.peval_int4_potencia import filas_bloqueado
    fb = filas_bloqueado(rec, años, NUCLEO)
    return {"T1_con_2020": fb["T1"], "T1_sin_2020": fb["T1"][fb["T1"].t + 1 <= 2019].reset_index(drop=True),
            "T2": fb["T2"]}


def comprobar_recuentos(m: dict[str, pd.DataFrame]) -> dict:
    out = {}
    for k, (n, e, por_año) in ESPERADO.items():
        f = m[k]
        obs = {int(t) + 1: int(v) for t, v in f[f.y == 1].groupby("t").size().items()}
        out[k] = {"filas": int(len(f)), "eventos": int(f.y.sum()), "eventos_por_año_objetivo": obs}
        if len(f) != n or int(f.y.sum()) != e or obs != por_año:
            raise SystemExit(f"{k}: recuentos {len(f)}/{int(f.y.sum())} {obs} distintos de la potencia "
                             f"{n}/{e} {por_año}: el objetivo ha cambiado (¿otra versión de JST?); no se leen indicadores")
    return out


# ---------------------------------------------------------------- (d) estadísticos y veredicto
def ic_auc_modelo(y, p1, t, B: int = B_BOOT, semilla: int = SEMILLA) -> list[float]:
    """IC 95 % percentil de la AUC del modelo, bootstrap por bloques de año (mismos remuestreos que int4.bloques)."""
    from src.intl import int4 as M
    años = np.unique(t)
    idx = {a: np.flatnonzero(t == a) for a in años}
    rng = np.random.default_rng(semilla)
    v = np.empty(B)
    for b in range(B):
        sel = np.concatenate([idx[a] for a in rng.choice(años, len(años), replace=True)])
        v[b] = M.auc(y[sel], p1[sel])
    v = v[np.isfinite(v)]
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]


def evaluar(y: np.ndarray, p1: np.ndarray, p0: np.ndarray, t: np.ndarray) -> dict:
    from src.intl import int4 as M
    y = y.astype(float)
    bl = M.bloques(y, p1, p0, t, B=B_BOOT, semilla=SEMILLA)
    return {"filas": int(len(y)), "eventos": int(y.sum()), "no_eventos": int((1 - y).sum()),
            "años_con_evento": int(np.unique(t[y == 1]).size),
            "auc_modelo": M.auc(y, p1), "auc_liston": M.auc(y, p0), **bl,
            "auc_modelo_ic95": ic_auc_modelo(y, p1, t),
            "logloss_modelo": M.logloss(y, p1), "logloss_liston": M.logloss(y, p0),
            "calibracion": M.calibracion(y, p1)}


def veredicto_giro(ev: dict) -> str:
    """§5.2: 'no_concluyente_datos' | 'refutado' | 'no_refutado' | 'no_concluyente'."""
    if (ev["eventos"] < MIN_EVENTOS or ev["no_eventos"] < MIN_NO_EVENTOS
            or ev["años_con_evento"] < MIN_AÑOS_EVENTO or not np.isfinite(ev["d_auc"])):
        return "no_concluyente_datos"
    if ev["d_auc"] <= 0:
        return "refutado"
    if ev["auc_modelo_ic95"][0] > 0.5:
        return "no_refutado"
    return "no_concluyente"


def veredicto_global(v: dict[str, str]) -> dict:
    """§5.3: refutado si algún giro principal lo está; no refutado si los dos lo están; si no, no concluyente."""
    ref = [k for k in PRINCIPALES if v[k] == "refutado"]
    if ref:
        g = "refutado"
    elif all(v[k] == "no_refutado" for k in PRINCIPALES):
        g = "no_refutado"
    else:
        g = "no_concluyente"
    return {"global": g, "giros_refutados": ref}


def informativos(ev: dict) -> dict:
    """§5.4: no cambian el veredicto."""
    from src.intl import int3 as I3
    h = I3.holm({k: ev[k]["p_bloques"] for k in PRINCIPALES})
    return {k: {"dauc_ic_excluye_0_holm2": bool(ev[k]["d_auc"] > 0 and h[k]),
                "dlogloss_neg": bool(ev[k]["d_logloss"] < 0),
                "pendiente_0.5_1.5": bool(0.5 <= ev[k]["calibracion"]["pendiente"] <= 1.5)} for k in PRINCIPALES}


# ---------------------------------------------------------------- corrida
def main() -> None:
    gate = puerta()                                    # 1.º: nada se lee antes de pasarla
    congelado = modelo_congelado()                     # solo ≤ 2004
    from src.intl import data as D
    from src.intl import int4 as M
    from scripts.int4_corrida import _r
    con = D.connect()
    rgdp = {c: leer_bloqueado(con, f"jst_{c.lower()}_rgdpmad") for c in NUCLEO}
    rec, años = fechar(rgdp)
    m = muestras(rec, años)
    try:
        recuentos = comprobar_recuentos(m)
    except SystemExit:
        con.close()
        raise
    series = {c: {"rgdpmad": rgdp[c], **{v: leer_bloqueado(con, f"jst_{c.lower()}_{v}") for v in VARS_INDICADORES}}
              for c in NUCLEO}
    con.close()
    a = anual_desde_series(series)
    pan = M.paneles(a, _extra_vacio(a), NUCLEO, NUCLEO, None, hasta=FIN_BLOQUEADO)
    primer = {c: min(v) for c, v in años.items()}
    ev, completas = {}, {}
    for k, f in m.items():
        giro = k[:2]
        B1, X = M.liston(f, giro, rec, primer, pan), M.matriz(f, pan, COLS[giro])
        ok = np.isfinite(B1).all(axis=1) & np.isfinite(X).all(axis=1)
        b1, b0 = (np.asarray(congelado[giro][x]) for x in ("b_modelo", "b_liston"))
        p1 = M.logit_pred(b1, np.column_stack([B1, X])[ok])
        p0 = M.logit_pred(b0, B1[ok])
        ev[k] = evaluar(f.y.to_numpy(float)[ok], p1, p0, f.t.to_numpy()[ok])
        completas[k] = {"filas_en_riesgo": int(len(f)), "filas_completas": int(ok.sum()),
                        "fraccion": float(ok.mean())}
    v = {k: veredicto_giro(ev[k]) for k in ev}
    res = {"procedencia": gate["procedencia"], "autorizacion": gate["autorizacion"],
           "prerregistro": f"{DOC.relative_to(REPO)} (sha256 {DOC_SHA256})",
           "modelo_congelado": {"ref": f"{REF_MODELO.relative_to(REPO)} (sha256 {REF_MODELO_SHA256})", **congelado},
           "series_leidas_hasta_2020": list(LEIDAS), "recuentos": recuentos, "filas_completas": completas,
           "evaluacion": ev, "veredicto_giro": v, "veredicto": veredicto_global(v), "informativos": informativos(ev),
           "sensibilidad_T1_con_2020": v["T1_con_2020"],
           "hora_fin_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    R = _r(res)
    SALIDA.write_text(json.dumps(R, indent=1, ensure_ascii=False))
    SALIDA.with_suffix(".md").write_text(informe(R))
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(f"| {res['hora_fin_utc']} | peval_int4_refutacion (ÚNICA, bloqueado JST 2005-2020 GASTADO) | "
                 f"{gate['procedencia']['commit'][:7]} | veredicto {res['veredicto']['global']} "
                 f"{json.dumps(v, ensure_ascii=False)} | prerregistro PEVAL_INT4_refutacion_v1 |\n")
    print(json.dumps(R["veredicto"], ensure_ascii=False), json.dumps(v, ensure_ascii=False))


def informe(r: dict) -> str:
    p = r["procedencia"]
    L = ["# P-EVAL-INT4: resultado de la prueba de refutación (bloqueado JST 2005-2020, gastado)", "",
         f"Procedencia: commit `{p['commit'][:7]}`, árbol limpio {p['arbol_limpio']}, {p['hora_utc']}. "
         f"Autorización: {r['autorizacion']}.", "",
         f"**Veredicto global: {r['veredicto']['global']}** (giros refutados: {r['veredicto']['giros_refutados']})", "",
         "| muestra | filas completas / en riesgo | eventos | AUC B1 → modelo | ΔAUC | IC 95 % ΔAUC | IC 95 % AUC modelo | "
         "Δlog-loss | pendiente | veredicto |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, e in r["evaluacion"].items():
        c = r["filas_completas"][k]
        L.append(f"| {k} | {c['filas_completas']} / {c['filas_en_riesgo']} | {e['eventos']} | "
                 f"{e['auc_liston']:.3f} → {e['auc_modelo']:.3f} | {e['d_auc']:+.3f} | "
                 f"[{e['d_auc_ic95'][0]:+.3f}; {e['d_auc_ic95'][1]:+.3f}] | "
                 f"[{e['auc_modelo_ic95'][0]:.3f}; {e['auc_modelo_ic95'][1]:.3f}] | "
                 f"{e['logloss_modelo'] - e['logloss_liston']:+.4f} | {e['calibracion']['pendiente']:.2f} | "
                 f"{r['veredicto_giro'][k]} |")
    L += ["", f"Informativos (no cambian el veredicto): {r['informativos']}", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
