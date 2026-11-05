"""Evaluación (CONGELADA antes de que exista ningún realizado) del registro en vivo de INT-11, serie v3.1.

Documentos: docs/int/INT11_registro_vivo.md §3 (qué se mide), docs/int/INT11_fuente_bolsa_vivo.md §5 y §9 (fuente D9 de
la bolsa, deflactor, sensibilidad sin JPN), docs/int/INT11_prerregistro_v3.md (cobertura p5-p95, PIT, Brier K2).
Ambigüedades resueltas y partes PENDIENTES: docs/int/EVAL_registros_vivo.md (sección INT-11).

- Registro: `research/int/int11_v3_1_vivo/AAAA-MM.json` (scripts/int11_v3_hoy.py --registro; marca SERIE = int11_v3_1),
  con `cuantiles_1_99` por activo y país y `p_inflacion_5`. Se comprueba el sha256 de cada emisión contra indice.csv.
- Ventana cerrada: hoy > fin de la ventana + 3 meses (retraso de la principal, `bolsa_vivo.RETRASO_MESES`). Si no hay
  ninguna: "sin ventanas cerradas", no conecta al warehouse y no escribe nada.
- Realizado (se lee UNA vez por emisión y se guarda en `research/int/int11_v3_1_realizado/AAAA-MM.json`, que no se
  reescribe: AQR revisa la historia y vale lo leído la primera vez):
    * bolsa: `src/report/bolsa_vivo.leer_realizado` (principal AQR + FX fin de mes; si falta un mes, respaldo OCDE +
      dividendo implícito; nunca mezcladas), real con el IPC OCDE "media"; JPN "con medias" solo descriptivo;
    * inflación (K2): media del IPC OCDE de la ventana / media de los 12 anteriores − 1 > 5 % → 1;
    * bonos, letras, vivienda, oro: medida del BORRADOR docs/int/INT11_vivo_realizado_v0.md (src/report/activos_vivo.py),
      leída una vez por activo a su propio retraso (`RETRASO`; vivienda 12 meses) en `.../AAAA-MM_<activo>.json`.
      Mientras `MEDIDAS_NUEVAS_APROBADAS` sea False NO se leen (se anotan como pendientes).
- Métricas: cobertura p5-p95, PIT (interpolado en los percentiles 1-99), CRPS aproximado por cuantiles (descriptivo),
  Brier K2 de M1 (p guardada) frente a M0 = 26,2 %. Principal: emisiones de DICIEMBRE (ventanas enero-diciembre sin
  solape); todas las emisiones, descriptivo con conglomerados por año de emisión. Sensibilidad sin JPN (A4).
  Semáforo (borrador §5): cobertura acumulada de diciembre frente a las bandas congeladas de
  research/int/int11_vivo_semaforo.json (sha256 comprobado); contraste formal único con 10 años de diciembre (S5).

Uso: .venv/bin/python -m scripts.eval_int11_vivo [--sintetico] [--hoy AAAA-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.report import activos_vivo as V

REPO = Path(__file__).resolve().parents[1]
CARPETA = REPO / "research/int/int11_v3_1_vivo"
REALIZADO = REPO / "research/int/int11_v3_1_realizado"
SALIDA = REPO / "research/int/eval_int11_vivo.json"
SERIE = "int11_v3_1"
ACTIVOS = ("bolsa", "bonos", "letras", "vivienda", "oro")
ACTIVOS_NUEVOS = ("bonos", "letras", "vivienda", "oro")
# Interruptor del BORRADOR docs/int/INT11_vivo_realizado_v0.md: hasta que el usuario apruebe las medidas (V1-V7) no se
# lee ni se congela ningún realizado de bonos, letras, vivienda u oro. Cambiarlo es un commit propio con la aprobación.
MEDIDAS_NUEVAS_APROBADAS = False
ACTIVOS_MEDIDOS = ("bolsa", *ACTIVOS_NUEVOS) if MEDIDAS_NUEVAS_APROBADAS else ("bolsa",)
PENDIENTES = {a: "medida en BORRADOR (docs/int/INT11_vivo_realizado_v0.md), pendiente de aprobación"
              for a in ACTIVOS if a not in ACTIVOS_MEDIDOS}
SEMAFORO = REPO / "research/int/int11_vivo_semaforo.json"
SHA_SEMAFORO = "1f3703acd90321d38eb8c304dbe86efb17c246c1c112b7cb86669848df7309ec"   # INT11_vivo_realizado_v0.md §5
VEREDICTO = REPO / "research/int/eval_int11_vivo_veredicto_10a.json"
AÑOS_CONTRASTE = 10
NIVELES = np.arange(1, 100) / 100
I5, I95 = 4, 94                       # índices de p5 y p95 en cuantiles_1_99
UMBRAL_INFL = 0.05
M0_INFL = 0.262                       # registro_vivo.md §3: frecuencia ≤ 2004 de inflación > 5 %
RETRASO_PRINCIPAL = 3                 # meses (src/report/bolsa_vivo.RETRASO_MESES["principal"])
B_BOOT = 2000


# ---------------------------------------------------------------- registro
def leer_emisiones(carpeta: Path = CARPETA) -> list[dict]:
    if not carpeta.exists():
        return []
    marca = carpeta / "SERIE"
    if any(carpeta.glob("*.json")) and (not marca.exists() or marca.read_text().strip() != SERIE):
        raise SystemExit(f"{carpeta}: la marca de serie no es {SERIE}")
    idx = {}
    if (carpeta / "indice.csv").exists():
        idx = pd.read_csv(carpeta / "indice.csv", dtype=str).set_index("archivo")["sha256"].to_dict()
    out = []
    for p in sorted(carpeta.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].json")):
        texto = p.read_text()
        if idx.get(p.name) != hashlib.sha256(texto.encode()).hexdigest():
            raise SystemExit(f"{p.name}: sha256 distinto del de indice.csv (emisión alterada o sin indexar)")
        o = json.loads(texto)
        if o.get("serie_registro") != SERIE:
            raise SystemExit(f"{p.name}: serie {o.get('serie_registro')!r}")
        o["_mes"] = p.stem
        out.append(o)
    return out


RETRASO = {"bolsa": RETRASO_PRINCIPAL, **V.RETRASO_MESES}   # meses tras el fin de la ventana, por activo


def cerrada(o: dict, hoy, activo: str = "bolsa") -> bool:
    fin = pd.Timestamp(o["ventana_objetivo"]["hasta"])
    return pd.Timestamp(hoy) > fin + pd.offsets.MonthEnd(RETRASO[activo])


# ---------------------------------------------------------------- puntuaciones (puras)
def pit(r: float, q) -> float:
    q = np.asarray(q, float)
    if r < q[0]:
        return 0.005
    if r > q[-1]:
        return 0.995
    return float(np.interp(r, q, NIVELES))


def crps_cuantiles(r: float, q) -> float:
    """2 · media de la pérdida de cuantil en τ = 0,01 … 0,99 (aproximación del CRPS con colas truncadas)."""
    q = np.asarray(q, float)
    u = r - q
    return float(2 * np.mean(np.maximum(NIVELES * u, (NIVELES - 1) * u)))


def filas(emisiones: list[dict], realizados: dict) -> pd.DataFrame:
    """Una fila por (emisión, país, activo medido) y una por (emisión, país) para K2 (activo = "inflacion")."""
    out = []
    for o in emisiones:
        re = realizados.get(o["_mes"])
        if re is None:
            continue
        mes = pd.Timestamp(o["emision"])
        for c, x in o["paises"].items():
            if "cuantiles_1_99" not in x:
                continue
            base = {"mes": o["_mes"], "año": mes.year, "diciembre": mes.month == 12, "pais": c}
            for a in ACTIVOS_MEDIDOS:
                r = re.get(a, {}).get(c, {}).get("real")
                q = x["cuantiles_1_99"].get(a)
                if r is None or q is None:
                    continue
                out.append({**base, "activo": a, "real": r, "dentro": float(q[I5] <= r <= q[I95]),
                            "pit": pit(r, q), "crps": crps_cuantiles(r, q),
                            "fuente": re[a][c].get("usada")})
            yi = re.get("inflacion", {}).get(c, {}).get("y")
            pi = (x.get("p_inflacion_5") or {}).get("p")
            if yi is not None and pi is not None:
                out.append({**base, "activo": "inflacion", "y": float(yi), "p": float(pi)})
    return pd.DataFrame(out)


def _boot_años(d: pd.DataFrame, f, semilla: int = 0) -> list | None:
    años = d.año.unique()
    if len(años) < 2:
        return None
    rng = np.random.default_rng(semilla)
    g = {a: d[d.año == a] for a in años}
    v = [f(pd.concat([g[a] for a in rng.choice(años, len(años))])) for _ in range(B_BOOT)]
    v = np.array([x for x in v if x is not None and np.isfinite(x)])
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))] if len(v) else None


def resumen_cobertura(d: pd.DataFrame) -> dict:
    if d.empty:
        return {"n": 0}
    h = np.histogram(d.pit, bins=10, range=(0, 1))[0]
    ks = float(np.max(np.abs(np.sort(d.pit) - (np.arange(1, len(d) + 1) - 0.5) / len(d))))
    return {"n": int(len(d)), "años": int(d.año.nunique()), "paises": int(d.pais.nunique()),
            "cobertura_p5_p95": float(d.dentro.mean()), "cobertura_ic95_años": _boot_años(d, lambda x: x.dentro.mean()),
            "fuera_por_abajo": float((d.pit < 0.05).mean()), "fuera_por_arriba": float((d.pit > 0.95).mean()),
            "pit_deciles": h.tolist(), "pit_ks": ks, "crps_medio": float(d.crps.mean()),
            "fuente_usada": d.fuente.value_counts().to_dict()}


def brier_k2(d: pd.DataFrame) -> dict:
    if d.empty:
        return {"n": 0}
    b1 = lambda x: float(np.mean((x.p - x.y) ** 2))  # noqa: E731
    b0 = lambda x: float(np.mean((M0_INFL - x.y) ** 2))  # noqa: E731
    bss = lambda x: 1 - b1(x) / b0(x) if b0(x) > 0 else np.nan  # noqa: E731
    return {"n": int(len(d)), "años": int(d.año.nunique()), "frecuencia": float(d.y.mean()), "brier_M1": b1(d),
            "brier_M0": b0(d), "bss": float(bss(d)), "bss_ic95_años": _boot_años(d, bss)}


def evaluar(emisiones: list[dict], realizados: dict) -> dict:
    d = filas(emisiones, realizados)
    out = {"emisiones_evaluadas": sorted(realizados), "activos_pendientes": PENDIENTES}
    if d.empty:
        return {**out, "nota": "sin filas evaluables"}
    for nom, m in (("principal_diciembre", d.diciembre), ("todas_las_emisiones", pd.Series(True, index=d.index))):
        b = d[m & (d.activo == "bolsa")]
        k = d[m & (d.activo == "inflacion")]
        out[nom] = {"K1_bolsa": resumen_cobertura(b), "K1_bolsa_sin_JPN": resumen_cobertura(b[b.pais != "JPN"]),
                    "K1_bolsa_por_pais": {c: {"n": int(len(g)), "cobertura": float(g.dentro.mean())}
                                          for c, g in b.groupby("pais")},
                    "K2_inflacion_5": brier_k2(k)}
        for a in ACTIVOS_MEDIDOS[1:]:
            out[nom][f"K1_{a}"] = resumen_cobertura(d[m & (d.activo == a)])
    out["semaforo"] = semaforo_diciembre(d[d.diciembre & (d.activo != "inflacion")])
    return out


# ---------------------------------------------------------------- semáforo y contraste (INT11_vivo_realizado_v0.md §5)
def bandas(ruta: Path = SEMAFORO, sha: str = SHA_SEMAFORO) -> dict:
    """Bandas congeladas (no se recalculan): se comprueba su sha256."""
    texto = ruta.read_text()
    if hashlib.sha256(texto.encode()).hexdigest() != sha:
        raise SystemExit(f"{ruta.name}: sha256 distinto del congelado (las bandas no se recalculan)")
    return json.loads(texto)["bandas"]


def contraste(s5: float, años: int, banda: dict | None) -> dict:
    """Contraste formal ÚNICO (§5.3): con ≥ 10 años de diciembre, S5 fuera de [p2_5, p97_5] de su banda para 10 años →
    "DESCALIBRADO EN VIVO"; dentro → "NO SE RECHAZA LA CALIBRACIÓN". Antes de 10 años: sin contraste."""
    if años < AÑOS_CONTRASTE or banda is None:
        return {"estado": f"sin contraste: {años} < {AÑOS_CONTRASTE} años de diciembre"}
    dentro = banda["p2_5"] <= s5 <= banda["p97_5"]
    return {"estado": "NO SE RECHAZA LA CALIBRACIÓN" if dentro else "DESCALIBRADO EN VIVO", "años": años, "S5": s5,
            "banda_95": [banda["p2_5"], banda["p97_5"]],
            "lado": None if dentro else ("abanico estrecho" if s5 < banda["p2_5"] else "abanico ancho")}


def semaforo_diciembre(d: pd.DataFrame, tabla: dict | None = None) -> dict:
    """Color por activo y de S5 (media de las coberturas de los 5 activos) con la cobertura ACUMULADA de las emisiones
    de diciembre; años = años de emisión de diciembre con dato (con > 20 años se usa la banda de 20). S5 y su contraste,
    solo con los 5 activos medidos."""
    if d.empty:
        return {"nota": "sin emisiones de diciembre evaluadas"}
    tabla = tabla if tabla is not None else bandas()
    out, cob = {}, {}
    for a, g in d.groupby("activo"):
        Y = int(g.año.nunique())
        cob[a] = float(g.dentro.mean())
        b = tabla.get(str(min(Y, 20)), {}).get(a)
        out[a] = {"años": Y, "cobertura": cob[a], "paises_por_año_min": int(g.groupby("año").pais.nunique().min()),
                  "color": V.semaforo(cob[a], b) if b else "sin banda", "banda": b}
    if set(ACTIVOS) <= set(cob):
        Y = int(d.groupby("activo").año.nunique().min())
        s5 = float(np.mean([cob[a] for a in ACTIVOS]))
        b = tabla.get(str(min(Y, 20)), {}).get("S5")
        b10 = tabla.get(str(AÑOS_CONTRASTE), {}).get("S5")
        primeros = sorted(d.año.unique())[:AÑOS_CONTRASTE]          # el contraste usa SOLO los 10 primeros años
        d10 = d[d.año.isin(primeros)]
        s5_10 = float(np.mean([d10[d10.activo == a].dentro.mean() for a in ACTIVOS]))
        out["S5"] = {"años": Y, "cobertura": s5, "color": V.semaforo(s5, b) if b else "sin banda", "banda": b,
                     "contraste_10_años": contraste(s5_10, Y, b10)}
    else:
        out["S5"] = {"nota": "S5 solo con los 5 activos medidos", "activos_medidos": sorted(cob)}
    return out


# ---------------------------------------------------------------- lectura del realizado (impura; una vez por emisión)
def _huella(con, sids: list[str], desde, hasta) -> str:
    from src.report import bolsa_vivo as B
    h = hashlib.sha256()
    for s in sids:
        x = B.leer_obs(con, s, desde=desde, hasta=hasta)
        h.update(s.encode() + x.to_csv().encode())
    return h.hexdigest()


def fx_diarias(con, paises) -> dict:
    """FX diaria FRED H.10 del warehouse (A5); si falta alguna, la caché de scripts/int11_fuente_bolsa."""
    from src.report import bolsa_vivo as B
    sids = {B.FX_FRED[c][0] for c in paises if c != "USA"}
    out = {s: B.leer_obs(con, s) for s in sids}
    if any(v.empty for v in out.values()):
        from scripts.int11_fuente_bolsa import fx_diarias as caché
        c = caché()
        out = {s: (v if not v.empty else c[s]) for s, v in out.items()}
    return out


def leer_realizado_emision(con, o: dict) -> dict:
    from src.report import bolsa_vivo as B
    v = o["ventana_objetivo"]
    desde, hasta = pd.Timestamp(v["desde"]), pd.Timestamp(v["hasta"])
    paises = list(o["paises"])
    fx = fx_diarias(con, paises)
    lect = B.leer_realizado(con, fx, desde, hasta, paises=paises)
    bolsa, infl = {}, {}
    for c, x in lect.items():
        u = x.get("usada")
        bolsa[c] = {"usada": u, "real": x[u]["real"] if u else None, "nominal": x[u]["nominal"] if u else None,
                    "inflacion_media": x["inflacion"], "ultimo_dato": x["ultimo_dato"],
                    "ipc_interpolados": x["ipc_interpolados"],
                    **({"rend_div": x["respaldo"].get("rend_div")} if u == "respaldo" else {})}
        infl[c] = {"inflacion_media": x["inflacion"],
                   "y": None if x["inflacion"] is None else int(x["inflacion"] > UMBRAL_INFL)}
    if "JPN" in paises:          # A4: JPN "con medias" (como JST), SOLO descriptivo
        rf = B.leer_obs(con, "aqr_rf_risk_free_rate_m")
        tr = B.tr_local_desde_usd(B.leer_obs(con, "aqr_mkt_jpn_m"), rf, B.fx_lpu_pais("JPN", fx))
        ix = B.indice(tr)
        m = B.meses_ventana(desde, hasta)
        a, b = ix.reindex(m), ix.reindex(m - pd.DateOffset(months=12))
        nom = None if a.isna().any() or b.isna().any() else float(a.mean() / b.mean() - 1)
        bolsa["JPN"]["descriptiva_medias"] = B.real(nom, infl["JPN"]["inflacion_media"])
    lee = desde - pd.DateOffset(years=12)
    sids = ["aqr_rf_risk_free_rate_m"] + [f"{p}_{c.lower()}{s}" for c in paises
                                          for p, s in (("aqr_mkt", "_m"), ("oecd_share", ""), ("oecd_cpi", "_idx"))]
    return {"emision": o["_mes"], "ventana": v, "leido_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "fuente": B.FUENTE_D9 | {"estado": "APROBADA 5-nov-2026 (INT11_fuente_bolsa_vivo.md §9)"},
            "sha256_series": _huella(con, sids, lee, hasta), "bolsa": bolsa, "inflacion": infl,
            "pendientes": PENDIENTES, "nota": "solo el realizado derivado (A6: no se guardan series de AQR ni French)"}


def leer_realizado_activo(con, o: dict, activo: str) -> dict:
    """Realizado de un activo nuevo (bonos, letras, vivienda u oro) de una emisión; se lee UNA vez, a su retraso."""
    v = o["ventana_objetivo"]
    desde, hasta = pd.Timestamp(v["desde"]), pd.Timestamp(v["hasta"])
    paises = list(o["paises"])
    fx = fx_diarias(con, paises) if activo == "oro" else {}
    lect = V.leer_realizado_activos(con, fx, desde, hasta, paises=paises, activos=(activo,))
    claves = ("real", "nominal", "completo", "faltan", "metodo", "modo", "plusvalia", "rent_yd", "descriptiva_encadenada")
    filas = {c: {**{k: x[activo][k] for k in claves if k in x[activo]},
                 "usada": "principal" if x[activo].get("real") is not None else None,
                 "inflacion_media": x["inflacion"], "ipc_interpolados": x["ipc_interpolados"], "notas": x["notas"]}
             for c, x in lect.items()}
    sids = V.series_leidas(paises, (activo,)) + [f"oecd_cpi_{c.lower()}_idx" for c in paises]
    return {"emision": o["_mes"], "activo": activo, "ventana": v,
            "leido_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "fuente": V.FUENTE[activo],
            "sha256_series": _huella(con, sids, desde - pd.DateOffset(years=2), hasta), activo: filas,
            "nota": "solo el realizado derivado (sin series)"}


# ---------------------------------------------------------------- sintético
def sintetico(semilla: int = 20261105, años: int = 20, escala_real: float = 1.0, k2_informativa: bool = True):
    """Emisiones mensuales inventadas (14 países) con abanicos N(μ, σ) por activo; bolsa realizada de N(μ, escala·σ)
    (escala 1 = calibrado; > 1 = abanico demasiado estrecho, la descalibración plantada) y K2 con p informativa
    (y ~ Bernoulli(p)) o no (y ~ Bernoulli(M0) independiente de p)."""
    from scipy.stats import norm
    from src.report.bolsa_vivo import NUCLEO
    rng = np.random.default_rng(semilla)
    rng2 = np.random.default_rng(semilla + 1)
    z = norm.ppf(NIVELES)
    emis, real = [], {}
    for i in range(años * 12):
        em = pd.Timestamp("2026-11-20") + pd.DateOffset(months=i)
        mes = str(em.date())[:7]
        des = em + pd.offsets.MonthBegin(1)
        o = {"_mes": mes, "emision": str(em.date()), "serie_registro": SERIE,
             "ventana_objetivo": {"desde": str(des.date()), "hasta": str((des + pd.offsets.MonthEnd(12)).date())},
             "paises": {}}
        re = {a: {} for a in ACTIVOS} | {"inflacion": {}}
        for c in NUCLEO:
            mu, sd = rng.normal(0.05, 0.02), rng.uniform(0.15, 0.25)
            p = float(rng.uniform(0.02, 0.7))
            o["paises"][c] = {"cuantiles_1_99": {a: (mu + sd * z).round(5).tolist() for a in ACTIVOS},
                              "p_inflacion_5": {"p": p}}
            re["bolsa"][c] = {"usada": "principal", "real": float(mu + escala_real * sd * rng.standard_normal())}
            for a in ACTIVOS[1:]:        # generador aparte: la bolsa y K2 sintéticas no cambian (EVAL §3)
                re[a][c] = {"usada": "principal", "real": float(mu + escala_real * sd * rng2.standard_normal())}
            re["inflacion"][c] = {"y": int(rng.random() < (p if k2_informativa else M0_INFL))}
        emis.append(o)
        real[mes] = re
    return emis, real


def detecta(r: dict) -> dict:
    """Descriptivo (no es el contraste formal, PENDIENTE): ¿0,90 fuera del IC por años? ¿BSS > 0 con IC > 0?"""
    p = r["principal_diciembre"]
    ic = p["K1_bolsa"]["cobertura_ic95_años"]
    ib = p["K2_inflacion_5"]["bss_ic95_años"]
    return {"descalibracion": bool(ic and not (ic[0] <= 0.90 <= ic[1])), "k2_habilidad": bool(ib and ib[0] > 0)}


def resumen(r: dict) -> str:
    p = r.get("principal_diciembre")
    if not p:
        return r.get("nota", "sin filas")
    b, k = p["K1_bolsa"], p["K2_inflacion_5"]
    return (f"INT-11 v3.1 (diciembre): bolsa n {b['n']}, cobertura p5-p95 {b.get('cobertura_p5_p95', float('nan')):.3f} "
            f"IC {b.get('cobertura_ic95_años')}, sin JPN {p['K1_bolsa_sin_JPN'].get('cobertura_p5_p95', float('nan')):.3f}; "
            f"K2 BSS {k.get('bss', float('nan')):+.3f} IC {k.get('bss_ic95_años')}")


def _f(x):
    if isinstance(x, dict):
        return {str(k): _f(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_f(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 6)
    if isinstance(x, np.integer):
        return int(x)
    return x


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sintetico", action="store_true")
    ap.add_argument("--hoy")
    a = ap.parse_args(argv)
    if a.sintetico:
        ok = True
        for nom, esc, k2, esperado in (("con señal (abanico estrecho, K2 informativa)", 1.7, True, (True, True)),
                                       ("sin señal (calibrado, K2 sin información)", 1.0, False, (False, False))):
            e, re = sintetico(escala_real=esc, k2_informativa=k2)
            r = evaluar(e, re)
            dd = detecta(r)
            print(f"[sintético {nom}] {resumen(r)} → {dd}")
            ok &= (dd["descalibracion"], dd["k2_habilidad"]) == esperado
        print("sintético:", "OK" if ok else "FALLA")
        return 0 if ok else 1
    hoy = pd.Timestamp(a.hoy) if a.hoy else pd.Timestamp.today().normalize()
    emis = leer_emisiones()
    cer = [o for o in emis if cerrada(o, hoy)]
    if not cer:
        print(f"INT-11 v3.1: sin ventanas cerradas a {hoy.date()} ({len(emis)} emisiones registradas); "
              "no se lee ningún realizado ni se escribe nada")
        return 0
    from src.intl.procedencia import procedencia
    from src.warehouse import db
    proc = procedencia(exigir_limpio=True)
    REALIZADO.mkdir(parents=True, exist_ok=True)
    realizados = {}
    con = db.connect(read_only=True)
    sin_leer = []
    try:
        for o in cer:
            p = REALIZADO / f"{o['_mes']}.json"
            if not p.exists():          # se lee una sola vez; nunca se reescribe
                p.write_text(json.dumps(_f(leer_realizado_emision(con, o)), ensure_ascii=False, indent=1))
            realizados[o["_mes"]] = json.loads(p.read_text())
            for a in ACTIVOS_NUEVOS:
                if not cerrada(o, hoy, a):
                    continue
                if a not in ACTIVOS_MEDIDOS:
                    sin_leer.append(f"{o['_mes']}:{a}")
                    continue
                pa = REALIZADO / f"{o['_mes']}_{a}.json"
                if not pa.exists():     # una sola vez por activo, a su propio retraso; nunca se reescribe
                    pa.write_text(json.dumps(_f(leer_realizado_activo(con, o, a)), ensure_ascii=False, indent=1))
                realizados[o["_mes"]][a] = json.loads(pa.read_text())[a]
    finally:
        con.close()
    if sin_leer:
        print(f"sin leer (medidas en borrador, MEDIDAS_NUEVAS_APROBADAS = False): {len(sin_leer)} activo-emisión")
    r = evaluar(cer, realizados)
    print(resumen(r))
    c10 = ((r.get("semaforo") or {}).get("S5") or {}).get("contraste_10_años") or {}
    if c10.get("estado") in ("NO SE RECHAZA LA CALIBRACIÓN", "DESCALIBRADO EN VIVO") and not VEREDICTO.exists():
        VEREDICTO.write_text(json.dumps(_f({"procedencia": proc, "hoy": str(hoy.date()), "contraste": c10,
                                             "documento": "docs/int/INT11_vivo_realizado_v0.md §5.3"}),
                                        ensure_ascii=False, indent=1))
        print(f"veredicto único escrito: {VEREDICTO.relative_to(REPO)} → {c10['estado']}")
    SALIDA.write_text(json.dumps({"procedencia": proc, "hoy": str(hoy.date()), "documentos": [
        "docs/int/INT11_registro_vivo.md", "docs/int/INT11_fuente_bolsa_vivo.md", "docs/int/INT11_prerregistro_v3.md",
        "docs/int/EVAL_registros_vivo.md", "docs/int/INT11_vivo_realizado_v0.md"], "resultados": _f(r)}, ensure_ascii=False, indent=1))
    print(f"escrito {SALIDA.relative_to(REPO)} (descriptivo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
