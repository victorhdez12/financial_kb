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
    * bonos, letras, vivienda, oro: PENDIENTE (medida realizada en vivo no fijada; no se inventa).
- Métricas: cobertura p5-p95, PIT (interpolado en los percentiles 1-99), CRPS aproximado por cuantiles (descriptivo),
  Brier K2 de M1 (p guardada) frente a M0 = 26,2 %. Principal: emisiones de DICIEMBRE (ventanas enero-diciembre sin
  solape); todas las emisiones, descriptivo con conglomerados por año de emisión. Sensibilidad sin JPN (A4).
  Semáforo y contraste formal a 10 años: PENDIENTES (bandas de v3.1 por nº de años sin calcular).

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

REPO = Path(__file__).resolve().parents[1]
CARPETA = REPO / "research/int/int11_v3_1_vivo"
REALIZADO = REPO / "research/int/int11_v3_1_realizado"
SALIDA = REPO / "research/int/eval_int11_vivo.json"
SERIE = "int11_v3_1"
ACTIVOS = ("bolsa", "bonos", "letras", "vivienda", "oro")
ACTIVOS_MEDIDOS = ("bolsa",)
PENDIENTES = {a: "medida realizada en vivo no fijada (registro_vivo.md §3 solo la esboza); pendiente de prerregistro"
              for a in ACTIVOS if a not in ACTIVOS_MEDIDOS}
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


def cerrada(o: dict, hoy) -> bool:
    fin = pd.Timestamp(o["ventana_objetivo"]["hasta"])
    return pd.Timestamp(hoy) > fin + pd.offsets.MonthEnd(RETRASO_PRINCIPAL)


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
    out = {"emisiones_evaluadas": sorted(realizados), "activos_pendientes": PENDIENTES,
           "semaforo": "PENDIENTE: bandas simuladas de v3.1 por nº de años sin calcular (las de registro_vivo.md §3.2 "
                       "son del diseño v2)",
           "contraste_formal_10_años": "PENDIENTE: regla de decisión en vivo sin fijar (registro_vivo.md §3)"}
    if d.empty:
        return {**out, "nota": "sin filas evaluables"}
    for nom, m in (("principal_diciembre", d.diciembre), ("todas_las_emisiones", pd.Series(True, index=d.index))):
        b = d[m & (d.activo != "inflacion")]
        k = d[m & (d.activo == "inflacion")]
        out[nom] = {"K1_bolsa": resumen_cobertura(b), "K1_bolsa_sin_JPN": resumen_cobertura(b[b.pais != "JPN"]),
                    "K1_bolsa_por_pais": {c: {"n": int(len(g)), "cobertura": float(g.dentro.mean())}
                                          for c, g in b.groupby("pais")},
                    "K2_inflacion_5": brier_k2(k)}
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


# ---------------------------------------------------------------- sintético
def sintetico(semilla: int = 20261105, años: int = 20, escala_real: float = 1.0, k2_informativa: bool = True):
    """Emisiones mensuales inventadas (14 países) con abanicos N(μ, σ) por activo; bolsa realizada de N(μ, escala·σ)
    (escala 1 = calibrado; > 1 = abanico demasiado estrecho, la descalibración plantada) y K2 con p informativa
    (y ~ Bernoulli(p)) o no (y ~ Bernoulli(M0) independiente de p)."""
    from scipy.stats import norm
    from src.report.bolsa_vivo import NUCLEO
    rng = np.random.default_rng(semilla)
    z = norm.ppf(NIVELES)
    emis, real = [], {}
    for i in range(años * 12):
        em = pd.Timestamp("2026-11-20") + pd.DateOffset(months=i)
        mes = str(em.date())[:7]
        des = em + pd.offsets.MonthBegin(1)
        o = {"_mes": mes, "emision": str(em.date()), "serie_registro": SERIE,
             "ventana_objetivo": {"desde": str(des.date()), "hasta": str((des + pd.offsets.MonthEnd(12)).date())},
             "paises": {}}
        re = {"bolsa": {}, "inflacion": {}}
        for c in NUCLEO:
            mu, sd = rng.normal(0.05, 0.02), rng.uniform(0.15, 0.25)
            p = float(rng.uniform(0.02, 0.7))
            o["paises"][c] = {"cuantiles_1_99": {a: (mu + sd * z).round(5).tolist() for a in ACTIVOS},
                              "p_inflacion_5": {"p": p}}
            re["bolsa"][c] = {"usada": "principal", "real": float(mu + escala_real * sd * rng.standard_normal())}
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
    try:
        for o in cer:
            p = REALIZADO / f"{o['_mes']}.json"
            if not p.exists():          # se lee una sola vez; nunca se reescribe
                p.write_text(json.dumps(_f(leer_realizado_emision(con, o)), ensure_ascii=False, indent=1))
            realizados[o["_mes"]] = json.loads(p.read_text())
    finally:
        con.close()
    r = evaluar(cer, realizados)
    print(resumen(r))
    SALIDA.write_text(json.dumps({"procedencia": proc, "hoy": str(hoy.date()), "documentos": [
        "docs/int/INT11_registro_vivo.md", "docs/int/INT11_fuente_bolsa_vivo.md", "docs/int/INT11_prerregistro_v3.md",
        "docs/int/EVAL_registros_vivo.md"], "resultados": _f(r)}, ensure_ascii=False, indent=1))
    print(f"escrito {SALIDA.relative_to(REPO)} (descriptivo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
