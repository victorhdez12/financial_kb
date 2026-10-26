"""Corrida ÚNICA de P-DEV-INT4 v1.0 (docs/int/INT4_prerregistro_v0.md, aprobado y congelado en fa6d4c9).
Familia principal (Holm-4): combinado frente a B1 en T1-T4, h = 1, dejar un país fuera, 1871-2004 sin guerras.
Secundaria (Holm-6): T1, cada C1-C6 añadido a B1. Informativos: candidato a candidato en T2-T4, h = 2 (T1, T3, T4),
financieras / normales (T1), abs3 y sin truncadas (T3, T4), P4 materias primas (T3, T4, sobre el combinado), temporal con
efectos fijos, países de prueba (AUS y CHE con todo; CAN e IRL sin C6 / S3) con el modelo congelado en el núcleo.
Concreciones de la implementación: docstring de src/intl/int4.py. Omitidos (declarado antes de correr): auge crédito ×
vivienda y depreciación frente al dólar (exploratorios, sin modelo fijado) y EE. UU. mensual (el prerregistro v1.0 no
fija un modelo mensual; solo "descriptivo", sin potencia).
P4: índice de materias primas AQR Commodities for the Long Run (spot, cesta equiponderada, USD): suma de log(1 + r) de
los 12 meses del año t (años completos; 1878-2004); variable común a todos los países.
Exige el árbol limpio. Salida: research/int/int4_resultado.json y .md, y una línea en research/trial_log.md.
Uso: .venv/bin/python -m scripts.int4_corrida
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import int3 as I3
from src.intl import int4 as M
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
PRUEBA_TODO, PRUEBA_SIN_BOLSA = ["AUS", "CHE"], ["CAN", "IRL"]
TODOS = NUCLEO + PRUEBA_TODO + PRUEBA_SIN_BOLSA
COLS = {"T1": ["C1", "C2", "C4", "C5", "C6"], "T2": ["S1", "S2", "S3", "S4", "S5"],
        "T3": ["P1", "P2", "P3", "P5"], "T4": ["P1", "P2", "P3", "P5"]}
SIN_BOLSA = {"T1": "C6", "T2": "S3"}
SECUNDARIOS_T1 = ["C1", "C2", "C3", "C4", "C5", "C6"]


def _r(v, k=4):
    if isinstance(v, dict):
        return {a: _r(b, k) for a, b in v.items() if not str(a).startswith("_")}
    if isinstance(v, (list, tuple)):
        return [_r(b, k) for b in v]
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else round(float(v), k)
    if isinstance(v, (np.integer, np.bool_)):
        return v.item()
    return v


def materias_primas() -> pd.Series:
    s = D.load_dev_curado("aqr_clr_ew_spot_m")
    lr = np.log1p(s / 100)
    g = lr.groupby(lr.index.year)
    return g.sum()[g.count() == 12]


def main() -> None:
    proc = procedencia()
    con = D.connect()
    a = P.anual(con)
    extra = {}
    for v in ("hpnom", "money", "wage"):
        s = {c: D.load_dev(con, f"jst_{c.lower()}_{v}") for c in D.PAISES}
        s = pd.concat({c: x.set_axis(x.index.year) for c, x in s.items() if not x.empty})
        s.index.names = ["pais", "año"]
        extra[v] = s
    con.close()
    extra = pd.DataFrame(extra)
    mp = materias_primas()
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in TODOS}
    primer = {c: min(v) for c, v in años_pais.items()}
    pan = M.paneles(a, extra, NUCLEO, TODOS, mp)
    et = M.etiquetas_inflacion(a, TODOS)

    def filas(giro, paises, h=1, desde=1871, sg=True, lab="principal", sin_trunc=False):
        if giro == "T1":
            return M.obj_entrada(rec, años_pais, paises, h, desde, sg)
        if giro == "T2":
            return M.obj_salida(rec, años_pais, paises, h, desde, sg)
        return M.obj_inflacion(et[lab], paises, h, desde, sg, sube=(giro == "T3"), sin_truncadas=sin_trunc)

    def b1(f, giro):
        return M.liston(f, giro, rec, primer, pan)

    res = {"procedencia": proc, "prerregistro": "docs/int/INT4_prerregistro_v0.md (v1.0, fa6d4c9)",
           "principal": {}, "secundaria_T1": {}, "informativos": {}, "paises_prueba": {}}

    # ------------------------------------------------ familia principal
    base = {}
    for giro, cols in COLS.items():
        f = filas(giro, NUCLEO)
        B1 = b1(f, giro)
        r = M.comparar(f, B1, M.matriz(f, pan, cols))
        r["placebo"] = M.placebo(f, B1, pan, cols, r["d_auc"])
        r["indicadores"] = cols
        res["principal"][giro] = r
        base[giro] = (f, B1)
        print(giro, round(r["d_auc"], 4), r["d_auc_ic95"], r["p_bloques"], r["placebo"]["p_placebo"], flush=True)

    def veredicto(bloque: dict) -> dict:
        h_i = I3.holm({k: v["p_bloques"] for k, v in bloque.items()})
        h_ii = I3.holm({k: v["placebo"]["p_placebo"] for k, v in bloque.items()})
        out = {}
        for k, v in bloque.items():
            pend = v["calibracion"]["pendiente"]
            crit = {"i_dauc_ic_holm": bool(v["d_auc"] > 0 and h_i[k]), "ii_placebo_holm": bool(h_ii[k]),
                    "iii_dlogloss_neg": bool(v["d_logloss"] < 0),
                    "iv_temporal_1950_2004_pos": bool(v["temporal_1950_2004"]["d_auc"] > 0),
                    "v_pendiente_0.5_1.5": bool(0.5 <= pend <= 1.5)}
            out[k] = {"criterios": crit, "establecido": all(crit.values())}
        return out

    res["veredicto_principal"] = veredicto(res["principal"])

    # ------------------------------------------------ secundaria T1 (Holm-6)
    f, B1 = base["T1"]
    for c in SECUNDARIOS_T1:
        r = M.comparar(f, B1, M.matriz(f, pan, [c]))
        r["placebo"] = M.placebo(f, B1, pan, [c], r["d_auc"])
        res["secundaria_T1"][c] = r
        print("T1", c, round(r["d_auc"], 4), r["p_bloques"], r["placebo"]["p_placebo"], flush=True)
    res["veredicto_secundaria_T1"] = veredicto(res["secundaria_T1"])

    # ------------------------------------------------ informativos (sin veredicto)
    inf = res["informativos"]
    for giro in ("T2", "T3", "T4"):
        f, B1 = base[giro]
        inf[f"{giro}_candidato_a_candidato"] = {c: M.comparar(f, B1, M.matriz(f, pan, [c]), temporal_ok=False)
                                               for c in COLS[giro]}
    for giro in ("T1", "T3", "T4"):
        f = filas(giro, NUCLEO, h=2)
        inf[f"{giro}_h2"] = M.comparar(f, b1(f, giro), M.matriz(f, pan, COLS[giro]), h=2)
    f, _ = base["T1"]
    for tipo, otro in (("financieras", "normal"), ("normales", "financiera")):
        g = f[~((f.y == 1) & (f.tipo == otro))].reset_index(drop=True)
        inf[f"T1_{tipo}"] = M.comparar(g, b1(g, "T1"), M.matriz(g, pan, COLS["T1"]))
    for giro in ("T3", "T4"):
        g = filas(giro, NUCLEO, lab="abs3")
        inf[f"{giro}_abs3"] = M.comparar(g, b1(g, giro), M.matriz(g, pan, COLS[giro]))
        g = filas(giro, NUCLEO, sin_trunc=True)
        inf[f"{giro}_sin_truncadas"] = M.comparar(g, b1(g, giro), M.matriz(g, pan, COLS[giro]))
        f, B1 = base[giro]
        inf[f"{giro}_P4_sobre_combinado"] = M.comparar(f, np.column_stack([B1, M.matriz(f, pan, COLS[giro])]),
                                                       M.matriz(f, pan, ["P4"]))
    print("informativos hechos", flush=True)

    # ------------------------------------------------ países de prueba (modelo congelado en el núcleo)
    for giro, cols in COLS.items():
        fn, B1n = base[giro]
        d = {}
        fp = filas(giro, PRUEBA_TODO)
        d["AUS_CHE"] = M.congelado(fn, B1n, M.matriz(fn, pan, cols), fp, b1(fp, giro), M.matriz(fp, pan, cols))
        cols_sb = [c for c in cols if c != SIN_BOLSA.get(giro)]
        fp = filas(giro, PRUEBA_SIN_BOLSA)
        d["CAN_IRL_sin_bolsa"] = M.congelado(fn, B1n, M.matriz(fn, pan, cols_sb), fp, b1(fp, giro),
                                             M.matriz(fp, pan, cols_sb))
        d["indicadores_CAN_IRL"] = cols_sb
        res["paises_prueba"][giro] = d

    res["hora_fin_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    R = _r(res)
    out = REPO / "research" / "int"
    (out / "int4_resultado.json").write_text(json.dumps(R, indent=1, ensure_ascii=False))
    (out / "int4_resultado.md").write_text(informe(R))
    est = {k: v["establecido"] for k, v in res["veredicto_principal"].items()}
    est2 = {k: v["establecido"] for k, v in res["veredicto_secundaria_T1"].items()}
    linea = (f"| {dt.date.today().isoformat()} | Constructor (P-DEV-INT4 v1.0, corrida única) | commit {proc['commit'][:7]}; "
             f"núcleo 14 países 1871-2004 sin guerras, dejar un país fuera; principal Holm-4 establecidos {json.dumps(est)}; "
             f"secundaria T1 Holm-6 {json.dumps(est2)}; informativos y países de prueba publicados; "
             f"research/int/int4_resultado.json |\n")
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(linea)
    print(json.dumps(_r(res["veredicto_principal"]), indent=1, ensure_ascii=False))


def _f(v, k=3):
    return "–" if v is None else f"{v:+.{k}f}"


def _fila(n, r, v=None):
    pl = r.get("placebo", {}).get("p_placebo")
    tmp = r.get("temporal_1950_2004", {}).get("d_auc")
    return (f"| {n} | {r['filas']} / {r['eventos']} | {r['auc_liston']:.3f} → {r['auc_modelo']:.3f} | {_f(r['d_auc'])} | "
            f"[{_f(r['d_auc_ic95'][0])}; {_f(r['d_auc_ic95'][1])}] | {r['p_bloques']:.4f} | "
            f"{'–' if pl is None else f'{pl:.3f}'} | {_f(r['d_logloss'], 4)} | {_f(tmp)} | "
            f"{r['calibracion']['pendiente']:.2f} | " + ("" if v is None else f"**{'sí' if v['establecido'] else 'no'}** |"))


def informe(r: dict) -> str:
    p = r["procedencia"]
    H = ("| contraste | filas / eventos | AUC B1 → modelo | ΔAUC | IC 95 % bloques | p bloques | p placebo | Δlog-loss | "
         "ΔAUC temporal 1950-2004 | pendiente | ESTABLECIDO |")
    L = ["# INT-4: resultado de la corrida única", "",
         f"Procedencia: commit `{p['commit'][:7]}`, árbol limpio {p['arbol_limpio']}, {p['hora_utc']}. Prerregistro v1.0 "
         "(fa6d4c9). Núcleo 14 países, 1871-2004 sin guerras, h = 1, dejar un país fuera; bootstrap por bloques de año "
         "(2.000); placebo con indicadores desplazados k = 6 … 129 años. Criterios (i)-(v) del §4.", "",
         "## Familia principal (Holm-4)", "", H, "|---|---|---|---|---|---|---|---|---|---|---|"]
    for g, v in r["principal"].items():
        L.append(_fila(f"{g} ({', '.join(v['indicadores'])})", v, r["veredicto_principal"][g]))
    L += ["", "Criterios: " + "; ".join(f"{g}: {v['criterios']}" for g, v in r["veredicto_principal"].items()), "",
          "## Secundaria T1 (Holm-6, cada indicador añadido a B1)", "", H, "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c, v in r["secundaria_T1"].items():
        L.append(_fila(c, v, r["veredicto_secundaria_T1"][c]))
    L += ["", "## Informativos (sin veredicto)", "",
          "| contraste | filas / eventos | AUC B1 → modelo | ΔAUC | IC 95 % bloques | p bloques | p placebo | Δlog-loss | "
          "ΔAUC temporal | pendiente |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in r["informativos"].items():
        if "candidato_a_candidato" in k:
            for c, w in v.items():
                L.append(_fila(f"{k.split('_')[0]} + {c}", w))
        else:
            L.append(_fila(k, v))
    L += ["", "## Países de prueba (modelo congelado en el núcleo)", "",
          "| giro | grupo | filas / eventos | ΔAUC | IC 95 % | por país |", "|---|---|---|---|---|---|"]
    for g, d in r["paises_prueba"].items():
        for grupo in ("AUS_CHE", "CAN_IRL_sin_bolsa"):
            v = d[grupo]
            if not v.get("eventos"):
                L.append(f"| {g} | {grupo} | {v['filas']} / 0 | – | – | – |")
                continue
            pp = "; ".join(f"{c} {_f(w['d_auc'])} ({w['eventos']} ev.)" for c, w in v["por_pais"].items())
            L.append(f"| {g} | {grupo} | {v['filas']} / {v['eventos']} | {_f(v['d_auc'])} | "
                     f"[{_f(v['d_auc_ic95'][0])}; {_f(v['d_auc_ic95'][1])}] | {pp} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
