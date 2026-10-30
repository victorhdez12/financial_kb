"""INT-13 (EXPLORATORIO): corrida ÚNICA (docs/int/INT13_plan_exploratorio.md, congelado en d315777).

XGBoost por paquetes como corrección de un logit clásico; 4 objetivos (E1-6, E1-12, E2, E3) × 6 paquetes; V1 dejar un
país fuera (principal) y V2 temporal ≤ 1989 → 1990-2004 con embargo; log-loss / Brier / AUC con IC por bloques de 24
meses; Holm-32. Datos ≤ 2004; nada ≥ 2005.

Uso: .venv/bin/python -m scripts.int13_corrida              (puerta: árbol limpio; se niega si ya existe la salida)
     .venv/bin/python -m scripts.int13_corrida --sintetico  (datos SINTÉTICOS; comprueba la tubería; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import int13 as M

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int13_resultado.json"
SALIDA_MD = REPO / "research/int/int13_resultado.md"
PLAN = "docs/int/INT13_plan_exploratorio.md (d315777)"
COLS_W = ["ipc_yoy", "ipc_6m_anual", "sub_yoy", "tipo_10a", "ip_yoy", "ventas_yoy", "paro_d12", "confianza_emp",
          "bolsa_12m", "r_bolsa_precio", "inflacion_mes"]
CORTO_3M = {"FIN", "IRL"}       # sin tipo oficial BIS → letra a 3 m de la OCDE (fuente única por país, plan §1)
FRASE = ("exploratorio: cualquier hallazgo necesita prerregistro y confirmación en vivo o en el bloqueado")


# ---------------------------------------------------------------- datos
def cargar_real() -> dict:
    from src.intl import data as D
    from src.intl import int8b as K
    from src.intl import panel as P
    con = D.connect()
    try:
        pm = P.mensual(con)
        rej = pm.index.get_level_values("fecha").unique().sort_values()
        w = {c: pm[c].unstack(0).reindex(index=rej, columns=D.PAISES) for c in COLS_W}
        corto = {}
        for c in D.PAISES:
            sid = f"oecd_ir3m_{c.lower()}" if c in CORTO_3M else f"bis_cbpol_{D.ISO2[c]}"
            s = P._mensual_completa(D.load_dev(con, sid))
            corto[c] = pd.Series(s.values, index=M._me(s.index)).reindex(rej) if not s.empty else pd.Series(np.nan,
                                                                                                         index=rej)
        bis = {c: s for c in D.PAISES if not (s := D.load_dev(con, f"bis_creditgap_{D.ISO2[c]}_ratio")).empty}
        paro = {c: s for c in D.PAISES if not (s := D.load_dev(con, f"oecd_unemp_{c.lower()}")).empty}
        a = P.anual(con)
    finally:
        con.close()
    pib = {c: D.load_dev_curado(f"oecd_gdpq_{c.lower()}") for c in D.PAISES}
    mp = D.load_dev_curado("aqr_clr_ew_spot_m")
    jst = a["d_credito_pib"].unstack(0)
    for s in [mp, *pib.values(), *bis.values(), *paro.values()]:
        D.check(s)
    if jst.index.max() > 2004 or rej.max() > M.FIN_DEV:
        raise D.FactorCutoffError("datos posteriores a 2004")
    return {"w": w, "corto_ref": pd.DataFrame(corto), "bis": bis, "jst_cred": jst, "mp": mp, "pib": pib,
            "sahm": K.sahm_asof(paro, rej, D.PAISES)}


def cargar_sintetico(seed: int = 7, n_paises: int = 10) -> dict:
    """Panel inventado con un ciclo común y señales plantadas (curva → recesión, materias primas → inflación,
    inflación → tipos). Solo para comprobar la tubería; no informa de nada real."""
    rng = np.random.default_rng(seed)
    rej = pd.date_range("1955-01-31", "2004-12-31", freq="ME")
    n = len(rej)
    paises = ["USA", "DEU", "FRA", "GBR", "JPN", "ITA", "CAN", "ESP", "SWE", "NLD", "BEL", "AUS"][:n_paises]

    def ar(phi, sd, m=0.0, k=1):
        x = np.zeros((n, k))
        for t in range(1, n):
            x[t] = m + phi * (x[t - 1] - m) + rng.standard_normal(k) * sd
        return x
    comun = ar(0.97, 0.3)[:, 0]
    mp = pd.Series(ar(0.3, 3.0)[:, 0], index=rej - pd.offsets.MonthBegin(1))
    lmp = np.log1p(mp.to_numpy() / 100)
    mp12 = pd.Series(lmp).rolling(12, min_periods=1).sum().to_numpy()
    infl = 0.003 + 0.002 * np.tanh(comun)[:, None] + 0.004 * np.roll(mp12, 6)[:, None] / 0.3 + ar(0.6, 0.002,
                                                                                                    k=len(paises))
    corto = 4 + 2 * comun[:, None] + ar(0.98, 0.25, k=len(paises))
    corto = corto + 60 * pd.DataFrame(infl).rolling(12, min_periods=1).mean().to_numpy()
    largo = corto + 1.5 - 0.8 * comun[:, None] + ar(0.9, 0.2, k=len(paises))
    W = lambda x: pd.DataFrame(x, index=rej, columns=paises)  # noqa: E731
    pi = W(infl).rolling(12, min_periods=12).sum()
    curva = W(largo) - W(corto)
    # PIB: crecimiento trimestral que cae cuando la curva de hace ~3 trimestres estaba invertida
    q = pd.period_range("1955Q1", "2004Q4", freq="Q")
    cq = curva.groupby(curva.index.to_period("Q")).mean().reindex(q)
    g = 0.006 - 0.012 * (cq.shift(3) < 0.2).astype(float) + rng.standard_normal(cq.shape) * 0.006
    pib = {c: pd.Series(100 * np.exp(np.cumsum(g[c].fillna(0.006).to_numpy())), index=q.to_timestamp(how="start"))
           for c in paises}
    ip = W(ar(0.8, 0.02, k=len(paises))) + 0.02 * np.tanh(comun)[:, None]
    w = {"ipc_yoy": pi.shift(2), "ipc_6m_anual": (2 * W(infl).rolling(6, min_periods=6).sum()).shift(2),
         "sub_yoy": pi.shift(2) * 0.8, "tipo_10a": W(largo).shift(1), "ip_yoy": ip.shift(3),
         "ventas_yoy": ip.shift(3) + W(ar(0.5, 0.01, k=len(paises))), "paro_d12": -10 * ip.shift(3),
         "confianza_emp": 100 + 50 * ip.shift(1), "bolsa_12m": W(ar(0.9, 0.05, k=len(paises))),
         "r_bolsa_precio": W(rng.standard_normal((n, len(paises))) * 0.04), "inflacion_mes": W(infl)}
    bis = {c: pd.Series(1 + np.cumsum(rng.standard_normal(len(q)) * 0.01), index=q.to_timestamp(how="start"))
           for c in paises}
    jst = pd.DataFrame(rng.standard_normal((50, len(paises))) * 0.01, index=range(1955, 2005), columns=paises)
    return {"w": w, "corto_ref": W(corto), "bis": bis, "jst_cred": jst, "mp": mp, "pib": pib,
            "sahm": W(ar(0.9, 0.1, k=len(paises)))}


# ---------------------------------------------------------------- evaluación
def evaluar_objetivo(S: pd.DataFrame, obj: str, reps: int, n_arboles: int) -> dict:
    modelos = ["clima", "base", *M.PAQUETES, M.COMBO]
    comps = {"base_vs_clima": ("base", "clima"), **{f"{p}_vs_base": (p, "base") for p in M.PAQUETES},
             f"{M.COMBO}_vs_base": (M.COMBO, "base")}
    res = {"filas": int(len(S)), "eventos": int(S[f"y_{obj}"].sum()), "paises": sorted(S.pais.unique().tolist()),
           "meses_con_evento": int(S.loc[S[f"y_{obj}"] == 1, "fecha"].nunique()),
           "desde": str(S.fecha.min().date()), "hasta": str(S.fecha.max().date())}
    for nom, fn in (("V1_loco", M.loco), ("V2_temporal", M.temporal)):
        P = fn(S, obj, n_arboles)
        boot = M.bloques_meses(P["fecha"], reps=reps)
        res[nom] = {"filas": int(len(P)), "eventos": int(P.y.sum()),
                    "meses_con_evento": int(P.loc[P.y == 1, "fecha"].nunique()),
                    "metricas": {m: M.metricas(P, m, boot) for m in modelos},
                    "comparaciones": {k: M.comparar(P, a, b, boot) for k, (a, b) in comps.items()}}
    res["importancias_descriptivas"] = M.importancias(S, obj, n_arboles)
    return res


def decidir(res: dict) -> dict:
    ps = {f"{o}|{k}": v["V1_loco"]["comparaciones"][k]["dlogloss"]["p_mejora"]
          for o, v in res.items() for k in v["V1_loco"]["comparaciones"]}
    hz = M.holm(ps)
    filas = []
    for clave, h in hz.items():
        o, k = clave.split("|")
        mod = k.split("_vs_")[0]
        c1 = res[o]["V1_loco"]["comparaciones"][k]["dlogloss"]
        c2 = res[o]["V2_temporal"]["comparaciones"][k]["dlogloss"]
        pend = res[o]["V1_loco"]["metricas"][mod]["calibracion"]["pendiente"]
        cand = bool(h["rechaza"] and c2["est"] < 0 and pend is not None and 0.5 <= pend <= 1.5)
        filas.append({"objetivo": o, "comparacion": k, "dlogloss_V1": c1["est"], "ic95_V1": c1["ic95"],
                      "p_V1": ps[clave], "p_holm": h["p_holm"], "rechaza_holm": h["rechaza"],
                      "dlogloss_V2": c2["est"], "ic95_V2": c2["ic95"], "pendiente_cal_V1": pend,
                      "candidato": cand,
                      "potencia_bloqueado_20a": M.potencia(c1["est"], c1["dt_boot"]),
                      "potencia_bloqueado_20a_mitad": M.potencia(c1["est"] / 2, c1["dt_boot"])})
    filas.sort(key=lambda r: (np.nan_to_num(r["p_V1"], nan=1.0)))
    return {"n_pruebas": len(ps), "familia": "Holm sobre Δlog-loss en V1 (dejar un país fuera)", "tabla": filas,
            "candidatos": [r for r in filas if r["candidato"]]}


def _limpio(v):
    if isinstance(v, dict):
        return {str(k): _limpio(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_limpio(x) for x in v]
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else round(float(v), 6)
    if isinstance(v, (np.integer, np.bool_)):
        return v.item()
    return v


def correr(crudo: dict, reps: int, n_arboles: int = M.N_ARBOLES) -> dict:
    df = M.construir(crudo)
    if df.fecha.max() > M.FIN_DEV:
        raise RuntimeError("filas posteriores a 2004")
    res = {}
    for obj in M.OBJETIVOS:
        t = time.time()
        res[obj] = evaluar_objetivo(M.muestra(df, obj), obj, reps, n_arboles)
        print(f"{obj}: {res[obj]['filas']} filas, {res[obj]['eventos']} eventos, {time.time() - t:.0f} s", flush=True)
    return {"objetivos": res, "decision": decidir(res)}


# ---------------------------------------------------------------- informe
def _f(x, k=4):
    return "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:+.{k}f}"


def _ic(ic, k=4):
    return "—" if not ic else f"[{ic[0]:+.{k}f}; {ic[1]:+.{k}f}]"


def informe(out: dict) -> str:
    L = ["---", "documento: Resultado INT-13 (EXPLORATORIO): XGBoost por paquetes como corrección de un logit clásico",
         f"plan: {PLAN}", f"procedencia: {out['procedencia']}",
         "datos: panel OCDE mensual de 18 países, orígenes 1960-01 … 2004-12 − h. NADA ≥ 2005", "---", "",
         "# INT-13: qué paquete de datos aporta a qué objetivo (exploratorio)", "",
         f"> **{FRASE[0].upper() + FRASE[1:]}.** Los datos ≤ 2004 ya se usaron en INT-4, INT-4-ML, INT-8 e INT-12.", "",
         f"**Número de pruebas:** {out['decision']['n_pruebas']} (4 objetivos × [base frente a clima + 6 paquetes + "
         "combinación frente a la base]) en V1, corregidas con Holm; V2 repite las mismas como comprobación.", ""]
    L += ["## Muestras", "", "| objetivo | filas | eventos | meses con evento | países | V2 (1990-2004): filas / eventos |",
          "|---|---|---|---|---|---|"]
    for o, v in out["objetivos"].items():
        L.append(f"| {o} | {v['filas']} | {v['eventos']} | {v['meses_con_evento']} | {len(v['paises'])} | "
                 f"{v['V2_temporal']['filas']} / {v['V2_temporal']['eventos']} |")
    L += ["", "## Calidad de la probabilidad (V1, dejar un país fuera)", "",
          "| objetivo | modelo | log-loss [IC 95 %] | Brier | AUC [IC 95 %] | pendiente calibración |", "|---|---|---|---|---|---|"]
    for o, v in out["objetivos"].items():
        for m, r in v["V1_loco"]["metricas"].items():
            L.append(f"| {o} | {m} | {r['logloss']:.4f} {_ic(r['logloss_ic95'])} | {r['brier']:.4f} | "
                     f"{_f(r['auc'], 3)} {_ic(r['auc_ic95'], 3)} | {_f(r['calibracion']['pendiente'], 2)} |")
    L += ["", "## Contrastes (Δ = modelo − listón; log-loss negativo = mejor). Ordenados por p de V1", "",
          "| objetivo | comparación | Δlog-loss V1 [IC 95 %] | p V1 | p Holm-32 | Δlog-loss V2 [IC 95 %] | pend. cal. | ¿candidato? | potencia 20 a (Δ / Δ½) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in out["decision"]["tabla"]:
        L.append(f"| {r['objetivo']} | {r['comparacion']} | {_f(r['dlogloss_V1'])} {_ic(r['ic95_V1'])} | "
                 f"{_f(r['p_V1'], 3)} | {_f(r['p_holm'], 3)} | {_f(r['dlogloss_V2'])} {_ic(r['ic95_V2'])} | "
                 f"{_f(r['pendiente_cal_V1'], 2)} | {'**sí**' if r['candidato'] else 'no'} | "
                 f"{_f(r['potencia_bloqueado_20a'], 2)} / {_f(r['potencia_bloqueado_20a_mitad'], 2)} |")
    L += ["", "## Δ AUC y Δ Brier frente a la base (V1; descriptivo)", "",
          "| objetivo | paquete | Δ AUC [IC 95 %] | Δ Brier [IC 95 %] |", "|---|---|---|---|"]
    for o, v in out["objetivos"].items():
        for k, c in v["V1_loco"]["comparaciones"].items():
            L.append(f"| {o} | {k} | {_f(c['dauc']['est'], 3)} {_ic(c['dauc']['ic95'], 3)} | "
                     f"{_f(c['dbrier']['est'], 5)} {_ic(c['dbrier']['ic95'], 5)} |")
    L += ["", "## Importancias (descriptivas; |SHAP| medio, modelo ajustado con todo ≤ 2004)", ""]
    for o, v in out["objetivos"].items():
        partes = []
        for pq, d in v["importancias_descriptivas"].items():
            top = sorted(d.items(), key=lambda kv: -kv[1]["shap_abs_medio"])[:2]
            partes.append(f"{pq}: " + ", ".join(f"{k} {x['shap_abs_medio']:.3f}" for k, x in top))
        L.append(f"- **{o}** — " + "; ".join(partes))
    cands = out["decision"]["candidatos"]
    L += ["", "## Candidatos para prerregistro", ""]
    if cands:
        for r in cands:
            L.append(f"- {r['objetivo']} · {r['comparacion']}: Δlog-loss V1 {_f(r['dlogloss_V1'])}, V2 "
                     f"{_f(r['dlogloss_V2'])}; potencia aproximada en 20 años del bloqueado "
                     f"{_f(r['potencia_bloqueado_20a'], 2)} (con la mitad del efecto, {_f(r['potencia_bloqueado_20a_mitad'], 2)}).")
    else:
        L.append("- Ninguna comparación cumple la regla (Holm-32 en V1, mejora en V2 y pendiente de calibración 0,5-1,5).")
    L += ["", f"_{FRASE[0].upper() + FRASE[1:]}._", ""]
    return "\n".join(L)


def main() -> None:
    sint = "--sintetico" in sys.argv
    if sint:
        t = time.time()
        out = correr(cargar_sintetico(), reps=50, n_arboles=M.N_ARBOLES)
        d = out["decision"]
        print(f"[sintético] {d['n_pruebas']} pruebas; {time.time() - t:.0f} s")
        for r in d["tabla"][:8]:
            print(r["objetivo"], r["comparacion"], round(r["dlogloss_V1"], 4), round(r["p_V1"] or 1, 4))
        out["procedencia"] = {"sintetico": True}
        informe(out)
        return
    from src.intl.procedencia import procedencia
    if SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: INT-13 es de una sola corrida")
    proc = procedencia(exigir_limpio=True)
    import xgboost
    t = time.time()
    out = correr(cargar_real(), reps=M.REPS)
    out = {"documento": "INT-13 (exploratorio)", "plan": PLAN, "procedencia": proc, "xgboost": xgboost.__version__,
           "aviso": FRASE, "segundos": round(time.time() - t), **out}
    SALIDA.write_text(json.dumps(_limpio(out), ensure_ascii=False, indent=1))
    SALIDA_MD.write_text(informe(_limpio(out)))
    print(f"escrito {SALIDA} y {SALIDA_MD}")


if __name__ == "__main__":
    main()
