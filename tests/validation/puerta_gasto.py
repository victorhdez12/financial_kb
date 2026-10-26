"""PUERTA DE GASTO del bloqueado (pool_spec.md §5, §5b; P-EVAL-BASE v4.3 A7): LECTURA de las corridas de desarrollo
del pool, no criterio. Decide el usuario.

Entrada: los run_id de `pool_dev`, `pool_m1cmp`, `pool_pesos_uno` y `pool_pesos_excluir` (obligatorios) y, si se
quieren evaluar las predicciones de 1980 y 1981-82, los de `m2_long` y `m3_long` (opcionales). Lee
`<runs_dir>/<run_id>/report.json` y `scores.parquet`.

Integridad (antes de leer nada): cada run_id tiene que estar en `research/trials/harness_runs.jsonl` con el mismo
nombre de configuración; la log-loss media de cada modo/modelo recalculada desde scores.parquet coincide con la
registrada (≤ 1e-9); y la mejora del principal frente a M0 recalculada con `metrics.boot_mean` sobre d reproduce el IC
registrado (≤ 1e-12). Si algo no cuadra: error y parada (artefacto viejo o alterado).

Salida (JSON + Markdown): mejora del pool frente a M0 con IC (bloques 12 y 24) en las cuatro corridas; sd_mensual de d
del pool frente a la de cada componente (P8: pool ≈ 0,5-0,8 × M2); subperiodos; giros/estables; trayectoria de pesos
y de (a, b) por corte; las predicciones P1-P11 del Estratega (`pool_spec.md` §5b, cita) con "se cumple / es falsa /
no evaluable" según su columna "falsa si"; y la lectura de la puerta (mejora < 0,05 nats o IC que incluye el 0 → se
recomienda NO registrar todavía) con la potencia de la v4.3 (A7) interpolada en la mejora observada.

Operacionalización declarada (la spec no la fija): los episodios se identifican por el primer giro v2.1 de G del
sentido pedido dentro de una ventana alrededor de la cronología pública del NBER (EPISODIOS, abajo); "entrada" y
"salida" = tramo k = 0 … +4 del estudio de eventos del arnés; P7 = media de la entrada A→B > media de la salida B→A.

    PYTHONPATH=. python tests/validation/puerta_gasto.py --pool-dev ID --pool-m1cmp ID --pool-uno ID \\
        --pool-excluir ID [--m2-long ID] [--m3-long ID] [--runs-dir DIR] [--harness-runs FICHERO] --out DIR
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.models import metrics as M

M0, M2, M3, CTP, POOL = "m0_calibrated_persistence", "m2_struct_g", "m3_tvtp_g", "m3_ctp_g", "pool_g"
MODE = "vintage"
NAMES = {"pool_dev": "pool_dev", "pool_m1cmp": "pool_m1cmp", "pool_uno": "pool_pesos_uno",
         "pool_excluir": "pool_pesos_excluir", "m2_long": "m2_long", "m3_long": "m3_long"}
PRINCIPAL = {"pool_dev": POOL, "pool_m1cmp": POOL, "pool_uno": POOL, "pool_excluir": POOL, "m2_long": M2,
             "m3_long": M3}
# ventana [desde, hasta] del primer giro v2.1 de G del sentido pedido (cronología pública del NBER ± margen)
EPISODIOS = {"1980": {"A→B": ("1979-06", "1980-06"), "B→A": ("1980-03", "1981-03")},
             "1981-82": {"A→B": ("1981-01", "1982-03"), "B→A": ("1982-06", "1983-06")},
             "1990-91": {"A→B": ("1989-06", "1991-03"), "B→A": ("1991-01", "1992-06")},
             "2001": {"A→B": ("2000-06", "2001-12"), "B→A": ("2001-09", "2003-06")}}
# claves de la configuración que tienen que coincidir con el YAML commiteado (lo que cambia la corrida)
CLAVES_CONFIG = ("models", "model_params", "modes", "matrix_variant", "refit_every", "embargo_months",
                 "min_train_months", "min_train_recessions", "min_train_g_changes", "test_start", "test_end",
                 "eval_window", "allow_shrink", "feature_policy", "pit_version", "provisional_weighting", "baseline",
                 "phase")
# potencia de P-EVAL-BASE v4.3 (A7, estructural): Δ verdadera → potencia
POT_V43 = ([0.0, 0.03, 0.05, 0.07, 0.10], [0.024, 0.41, 0.66, 0.80, 0.89])


class Integridad(RuntimeError):
    pass


# ------------------------------------------------------------------ carga e integridad
def _registro(harness_runs: Path) -> dict:
    out = {}
    for line in harness_runs.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            out[e["run_id"]] = e
    return out


def _norm(x):
    return json.loads(json.dumps(x, default=str))


def cargar(run_id: str, clave: str, runs_dir: Path, reg: dict) -> dict:
    from dataclasses import asdict
    from src.models import harness as H
    if run_id not in reg:
        raise Integridad(f"{run_id} no está en harness_runs.jsonl")
    e = reg[run_id]
    if e["config"]["name"] != NAMES[clave]:
        raise Integridad(f"{run_id}: configuración {e['config']['name']!r}, se esperaba {NAMES[clave]!r}")
    if e.get("phase") != "development" or e["config"].get("phase") != "development":
        raise Integridad(f"{run_id}: fase {e.get('phase')!r} (solo corridas de desarrollo)")
    if e.get("code", {}).get("git_dirty") is not False:
        raise Integridad(f"{run_id}: git_dirty = {e.get('code', {}).get('git_dirty')!r} (no es una corrida oficial)")
    otras = sorted(k for k, v in reg.items() if v["config"]["name"] == NAMES[clave] and k != run_id)
    if otras:
        raise Integridad(f"{run_id}: hay más corridas registradas de {NAMES[clave]} ({otras}): una sola pasada")
    yml = asdict(H.HarnessConfig.from_yaml(H.REPO / "config" / "harness" / f"{NAMES[clave]}.yaml"))
    dif = [k for k in CLAVES_CONFIG if _norm(e["config"].get(k)) != _norm(yml.get(k))]
    if dif:
        raise Integridad(f"{run_id}: la configuración registrada no es la commiteada en {NAMES[clave]}.yaml: {dif}")
    d = runs_dir / run_id
    rj = json.loads((d / "report.json").read_text())
    S = pd.read_parquet(d / "scores.parquet")
    S["month"] = pd.to_datetime(S["month"])
    for key, m in e["modelos"].items():
        mode, model = key.split("/", 1)
        x = S[(S["mode"] == mode) & (S["model"] == model)]["logloss"]
        if len(x) != m["n"] or abs(float(x.mean()) - m["logloss"]) > 1e-9:
            raise Integridad(f"{run_id}: log-loss de {key} no coincide con el registro")
    p = PRINCIPAL[clave]
    reg_ci = e["frente_al_baseline"][f"{MODE}/{p}"]["mejora_logloss"]
    b = M.boot_mean(serie_d(S, p).to_numpy())
    if max(abs(b["lo"] - reg_ci["lo"]), abs(b["hi"] - reg_ci["hi"]), abs(b["mean"] - reg_ci["mean"])) > 1e-12:
        raise Integridad(f"{run_id}: boot_mean(d de {p}) no reproduce el IC registrado")
    rj_ci = rj["report"]["frente_al_baseline"][f"{MODE}/{p}"]["mejora_logloss"]
    if any(rj_ci[k] != reg_ci[k] for k in ("mean", "lo", "hi")):
        raise Integridad(f"{run_id}: report.json no corresponde a la corrida registrada (IC de {p} distinto)")
    return {"run_id": run_id, "rep": rj["report"], "diag": rj.get("diag", {}), "S": S, "entrada": e}


def serie_d(S: pd.DataFrame, model: str, mode: str = MODE) -> pd.Series:
    v = S[S["mode"] == mode]
    a = v[v["model"] == M0].set_index("month")["logloss"].sort_index()
    b = v[v["model"] == model].set_index("month")["logloss"].sort_index()
    return (a - b).dropna()


# ------------------------------------------------------------------ piezas de la lectura
def resumen_corrida(r: dict, model: str = POOL) -> dict:
    c = r["rep"]["frente_al_baseline"].get(f"{MODE}/{model}")
    if c is None:
        return {"disponible": False}
    ml = c["mejora_logloss"]
    out = {"disponible": True, "mejora": ml["mean"], "ic95": [ml["lo"], ml["hi"]], "p_h0": ml["p_h0"],
           "ic95_b24": [c["mejora_logloss_b24"]["lo"], c["mejora_logloss_b24"]["hi"]],
           "mejora_ll_g": c["mejora_ll_g"]["mean"], "sd_mensual_d": ml.get("sd_mensual"),
           "acf_d_1_3": (ml.get("acf_1_24") or [None] * 3)[:3],
           "giro": {"media": c["cortes"]["giro"]["mean"], "ic95": [c["cortes"]["giro"]["lo"], c["cortes"]["giro"]["hi"]],
                    "n": c["cortes"]["giro"]["n"]},
           "estable": {"media": c["cortes"]["estable"]["mean"],
                       "ic95": [c["cortes"]["estable"]["lo"], c["cortes"]["estable"]["hi"]], "n": c["cortes"]["estable"]["n"]},
           "subperiodos": {k: v["mejora_logloss"] for k, v in c["por_periodo"].items()},
           "subperiodos_mismo_signo": c["subperiodos_mismo_signo"]}
    det = r["rep"].get("deteccion_giros_g", {}).get(f"{MODE}/{model}")
    if det:
        out["falsas_alarmas_por_año"] = det["falsas_alarmas_por_año"]
    out["deteccion_v21_frente_a_M0"] = c.get("deteccion_frente_al_comparador")          # pool_spec §5 (detección v2.1)
    out["episodios_prueba_signo"] = c.get("por_episodio", {}).get("resumen")             # episodios
    out["deteccion_8020"] = r["rep"].get("deteccion_declarada_8020", {}).get(f"{MODE}/{model}")   # 3 m × 80/20
    out["calibracion_G"] = r["rep"].get("calibracion", {}).get(f"{MODE}/{model}", {}).get("G")    # calibración
    return out


def sd_frente_componentes(r: dict) -> dict:
    out = {}
    for m in (POOL, M2, M3, CTP):
        d = serie_d(r["S"], m)
        if len(d):
            out[m] = float(d.std(ddof=1))
    if POOL in out and M2 in out and out[M2] > 0:
        out["ratio_pool_m2"] = out[POOL] / out[M2]
    return out


def trayectoria_pesos(r: dict) -> list[dict]:
    rows = []
    for x in r["diag"].get(MODE, []):
        if x.get("model") == POOL and x.get("coef") and "G:w_m0" in x["coef"]:
            c = x["coef"]
            rows.append({"corte": str(x["refit_month"])[:7], "w_m0": c["G:w_m0"], "w_m2": c["G:w_m2"],
                         "w_m3": c["G:w_m3"], "a": c["G:blp_a"], "b": c["G:blp_b"], "n_est": c["G:n_est"]})
    return rows


def _episodio(r: dict | None, model: str, nombre: str, sentido: str) -> dict | None:
    if r is None:
        return None
    es = r["rep"].get("estudio_eventos", {}).get(f"{MODE}/{model}")
    if not es:
        return None
    a, b = (pd.Timestamp(x + "-01") for x in EPISODIOS[nombre][sentido])
    for e in es["episodios"]:
        if e["sentido"] == sentido and a <= pd.Timestamp(e["giro"] + "-01") <= b:
            return e
    return None


def _estado(cumple: bool | None, falsa: bool | None) -> str:
    if cumple is None and falsa is None:
        return "no evaluable"
    if falsa:
        return "es falsa"
    return "se cumple" if cumple else "no se cumple del todo (no es falsa por su regla)"


def predicciones(runs: dict) -> dict:
    pdv, m2l, m3l = runs["pool_dev"], runs.get("m2_long"), runs.get("m3_long")
    out = {}

    def entrada(r, model, ep, sentido="A→B"):
        e = _episodio(r, model, ep, sentido)
        return None if e is None or e.get("entrada_salida") is None else e["entrada_salida"]

    # P1 (1980; M2, M3): d > 0 en la entrada y en la salida; falsa si d medio ≤ 0 en una de las dos
    p1 = {}
    for model, r in ((M2, m2l), (M3, m3l)):
        en, sa = entrada(r, model, "1980"), entrada(r, model, "1980", "B→A")
        p1[model] = {"entrada": en, "salida": sa,
                     "estado": "no evaluable" if en is None or sa is None else _estado(en > 0 and sa > 0,
                                                                                      en <= 0 or sa <= 0)}
    out["P1"] = p1
    # P2 (1981-82; M3): entrada > 0 y salida > 0; falsa si ≤ 0 en una de las dos
    e2 = _episodio(m3l, M3, "1981-82", "A→B")
    en, sa = entrada(m3l, M3, "1981-82"), entrada(m3l, M3, "1981-82", "B→A")
    out["P2"] = {"entrada": en, "salida": sa, "antes": None if e2 is None else e2.get("antes"),
                 "estado": "no evaluable" if en is None or sa is None else _estado(en > 0 and sa > 0,
                                                                                  en <= 0 or sa <= 0)}
    # P3 (1990-91; pool): 0 < entrada < entrada de 2001; 1991-04 … 1992-12 ≥ −0,05
    e90, e01 = entrada(pdv, POOL, "1990-91"), entrada(pdv, POOL, "2001")
    d = serie_d(pdv["S"], POOL)
    post = d[(d.index >= "1991-04-01") & (d.index <= "1992-12-01")]
    m_post = float(post.mean()) if len(post) else None
    if e90 is None or e01 is None or m_post is None:
        out["P3"] = {"estado": "no evaluable"}
    else:
        out["P3"] = {"entrada_1990": e90, "entrada_2001": e01, "media_1991_04_1992_12": m_post,
                     "estado": _estado(0 < e90 < e01 and m_post >= -0.05, m_post < -0.05 or e90 > e01)}
    # P4 (2001; pool, M2, M3): entrada > 0; falsa si ≤ 0
    p4 = {}
    for model in (POOL, M2, M3):
        en = entrada(pdv, model, "2001")
        p4[model] = {"entrada": en, "estado": "no evaluable" if en is None else _estado(en > 0, en <= 0)}
    out["P4"] = p4
    # P5 (estables del pool): −0,03 ≤ d ≤ 0; falsa si < −0,05
    es = pdv["rep"].get("estudio_eventos", {}).get(f"{MODE}/{POOL}", {}).get("estables", {})
    st = es.get("media")
    out["P5"] = {"media_estables": st,
                 "estado": "no evaluable" if st is None else _estado(-0.03 <= st <= 0, st < -0.05)}
    # P6 (1987; M3): falsa si M3 cruza 0,5 hacia G bajo a finales de 1987 sin giro A→B cerca
    r6 = m3l or pdv
    v = r6["S"][(r6["S"]["mode"] == MODE) & (r6["S"]["model"] == M3)].set_index("month")["pg"]
    w = v[(v.index >= "1987-09-01") & (v.index <= "1988-03-01")]
    giros = [pd.Timestamp(e["giro"] + "-01") for e in (r6["rep"].get("estudio_eventos", {})
                                                       .get(f"{MODE}/{M3}", {}).get("episodios", []))
             if e["sentido"] == "A→B"]
    giro_cerca = any(pd.Timestamp("1987-06-01") <= g <= pd.Timestamp("1988-06-01") for g in giros)
    if not len(w):
        out["P6"] = {"estado": "no evaluable"}
    else:
        cruza = bool((w < 0.5).any())
        out["P6"] = {"min_pg_1987_09_1988_03": float(w.min()), "giro_A_B_cerca": giro_cerca,
                     "estado": _estado(not cruza or giro_cerca, cruza and not giro_cerca)}
    # P7: ganancias en las entradas (A→B) > salidas (B→A), pool y M2
    p7 = {}
    for model in (POOL, M2):
        agg = pdv["rep"].get("estudio_eventos", {}).get(f"{MODE}/{model}", {}).get("media_por_sentido", {})
        ab, ba = (agg.get("A→B") or {}).get("entrada_salida"), (agg.get("B→A") or {}).get("entrada_salida")
        p7[model] = {"entrada_A_B": ab, "salida_B_A": ba,
                     "estado": "no evaluable" if ab is None or ba is None else ("se cumple" if ab > ba else
                                                                              "no se cumple")}
    out["P7"] = p7
    # P8: pool − M0 ∈ [+0,01; +0,06]; sd(d pool) ≈ 0,5-0,8 × sd(d M2)
    rs, sd = resumen_corrida(pdv), sd_frente_componentes(pdv)
    ratio = sd.get("ratio_pool_m2")
    out["P8"] = {"mejora_pool": rs.get("mejora"), "ratio_sd_pool_m2": ratio,
                 "estado_media": _estado(0.01 <= rs["mejora"] <= 0.06, None) if rs.get("disponible") else "no evaluable",
                 "estado_sd": "no evaluable" if ratio is None else _estado(0.5 <= ratio <= 0.8, None)}
    # P9: M3 − CTP ≤ +0,02 en total
    r9 = m3l or pdv
    fb = r9["rep"]["frente_al_baseline"]
    if f"{MODE}/{M3}" in fb and f"{MODE}/{CTP}" in fb:
        dif = fb[f"{MODE}/{M3}"]["mejora_logloss"]["mean"] - fb[f"{MODE}/{CTP}"]["mejora_logloss"]["mean"]
        out["P9"] = {"m3_menos_ctp": dif, "corrida": NAMES["m3_long" if m3l else "pool_dev"],
                     "estado": "se cumple" if dif <= 0.02 else "no se cumple (sin regla 'falsa si')"}
    else:
        out["P9"] = {"estado": "no evaluable"}
    # P10: fracción de cortes con γ > 0,01 (γ1 ≥ 50 % con alta probabilidad; γ3 < 50 % con prob. ≈ 0,5)
    sg = r9["rep"].get("signos_coeficientes", {}).get(f"{MODE}/{M3}", {}).get("fraccion_umbral")
    if sg:
        fr = {k: v["frac"] for k, v in sg.items()}
        out["P10"] = {"fracciones": fr, "gamma1_ge_0_5": fr.get("G:gamma1", 0) >= 0.5,
                      "gamma3_lt_0_5": fr.get("G:gamma3", 1) < 0.5, "nota": "predicción probabilística: se informa"}
    else:
        out["P10"] = {"estado": "no evaluable"}
    # P11: pesos en 2004-12: w_M0 ∈ [0,35; 0,7]; a, b ≥ 1
    tr = trayectoria_pesos(pdv)
    last = next((x for x in reversed(tr) if x["corte"] == "2004-12"), tr[-1] if tr else None)
    out["P11"] = ({"estado": "no evaluable"} if last is None else
                  {"corte": last["corte"], "w_m0": last["w_m0"], "a": last["a"], "b": last["b"],
                   "estado": _estado(0.35 <= last["w_m0"] <= 0.7 and last["a"] >= 1 and last["b"] >= 1, None)})
    # prueba del mecanismo: si ni 1980 ni 2001 muestran ganancia en la entrada (P1 y P4 falsas), no tiene sentido gastar
    en80 = [v["entrada"] for v in p1.values() if v["entrada"] is not None]        # SOLO la entrada (pool_spec §5b)
    en01 = [v["entrada"] for v in p4.values() if v["entrada"] is not None]
    sin80, sin01 = (bool(en80) and all(x <= 0 for x in en80)), (bool(en01) and all(x <= 0 for x in en01))
    out["prueba_del_mecanismo"] = {"sin_ganancia_entrada_1980": sin80 if en80 else None,
                                   "sin_ganancia_entrada_2001": sin01 if en01 else None,
                                   "mecanismo_falla": (sin80 and sin01) if en80 and en01 else None}
    return out


def puerta(rs: dict) -> dict:
    m, lo = rs["mejora"], rs["ic95"][0]
    pot = float(np.interp(max(m, 0.0), *POT_V43))
    rec = m < 0.05 or lo <= 0
    return {"mejora": m, "ic95": rs["ic95"], "mejora_lt_0_05": m < 0.05, "ic_incluye_0": lo <= 0,
            "potencia_v43_si_esta_fuera_la_mejora_verdadera": pot,
            "lectura": ("se recomienda NO registrar todavía (decide el usuario)" if rec else
                        "la puerta no desaconseja registrar (decide el usuario)"),
            "nota": "lectura, no criterio (pool_spec.md §5; P-EVAL-BASE v4.3 A7); leer junto con el estudio de eventos"}


def lectura(ids: dict, runs_dir: Path, harness_runs: Path) -> dict:
    reg = _registro(harness_runs)
    runs = {k: cargar(v, k, runs_dir, reg) for k, v in ids.items() if v}
    codigos = {runs[k]["entrada"]["code"]["src_models"] for k in runs if k.startswith("pool")}
    res = {"run_ids": {k: v["run_id"] for k, v in runs.items()},
           "pool_frente_a_M0": {k: resumen_corrida(runs[k]) for k in ("pool_dev", "pool_m1cmp", "pool_uno",
                                                                        "pool_excluir")},
           "sd_mensual_d": {k: sd_frente_componentes(runs[k]) for k in ("pool_dev", "pool_m1cmp")},
           "componentes_frente_a_M0_pool_dev": {m: resumen_corrida(runs["pool_dev"], m) for m in (M2, M3, CTP)},
           "trayectoria_pesos": {k: trayectoria_pesos(runs[k]) for k in ("pool_dev", "pool_uno", "pool_excluir")},
           "predicciones_estratega": predicciones(runs),
           "avisos": (["las corridas del pool usan versiones distintas de src/models: "
                       + ", ".join(sorted(c[:12] for c in codigos))] if len(codigos) > 1 else []),
           "operacionalizacion": {"ic_incluye_0": "límite inferior del IC 95 % ≤ 0 (la spec dice 'incluye claramente')",
                                  "episodios": EPISODIOS, "P6": "pg de M3 < 0,5 en 1987-09 … 1988-03 sin giro A→B en "
                                  "1987-06 … 1988-06"}}
    res["puerta_de_gasto"] = puerta(res["pool_frente_a_M0"]["pool_dev"])
    return res


def markdown(res: dict) -> str:
    L = ["# Puerta de gasto (lectura, no criterio)", ""]
    g = res["puerta_de_gasto"]
    L += [f"**Lectura:** {g['lectura']}. Mejora del pool frente a M0 (pool_dev, vintage) = {g['mejora']:+.4f} nats, "
          f"IC 95 % [{g['ic95'][0]:+.4f}; {g['ic95'][1]:+.4f}]. Potencia de la v4.3 si esta fuera la mejora verdadera ≈ "
          f"{g['potencia_v43_si_esta_fuera_la_mejora_verdadera']:.2f}.", "",
          "| corrida | mejora | IC 95 % | IC 95 % (b24) | giros | estables | mismo signo |", "|---|---|---|---|---|---|---|"]
    for k, r in res["pool_frente_a_M0"].items():
        if r.get("disponible"):
            L.append(f"| {k} | {r['mejora']:+.4f} | [{r['ic95'][0]:+.4f}; {r['ic95'][1]:+.4f}] | "
                     f"[{r['ic95_b24'][0]:+.4f}; {r['ic95_b24'][1]:+.4f}] | {r['giro']['media']:+.4f} | "
                     f"{r['estable']['media']:+.4f} | {r['subperiodos_mismo_signo']} |")
    L += ["", "| predicción | estado |", "|---|---|"]
    for k, v in res["predicciones_estratega"].items():
        if k == "prueba_del_mecanismo":
            continue
        partes = [f"{c}: {x}" for c, x in v.items() if c.startswith("estado") and c != "estado"]
        partes += [f"{m}: {x['estado']}" for m, x in v.items() if isinstance(x, dict) and "estado" in x]
        if k == "P10" and "fracciones" in v:
            partes.append("fracciones γ > 0,01: " + ", ".join(f"{g[2:]} {f:.2f}" for g, f in v["fracciones"].items()))
        L.append(f"| {k} | {v.get('estado') or '; '.join(partes) or 'no evaluable'} |")
    return "\n".join(L) + "\n"


def main() -> None:
    from src.models import trials
    ap = argparse.ArgumentParser()
    for k in ("pool-dev", "pool-m1cmp", "pool-uno", "pool-excluir"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--m2-long")
    ap.add_argument("--m3-long")
    ap.add_argument("--runs-dir", default=None)
    ap.add_argument("--harness-runs", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ids = {"pool_dev": a.pool_dev, "pool_m1cmp": a.pool_m1cmp, "pool_uno": a.pool_uno,
           "pool_excluir": a.pool_excluir, "m2_long": a.m2_long, "m3_long": a.m3_long}
    runs_dir = Path(a.runs_dir) if a.runs_dir else trials.runs_dir()
    hr = Path(a.harness_runs) if a.harness_runs else trials.V.trials_dir() / "harness_runs.jsonl"
    res = lectura(ids, runs_dir, hr)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "puerta_gasto.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    (out / "puerta_gasto.md").write_text(markdown(res))
    print(markdown(res))


if __name__ == "__main__":
    main()
