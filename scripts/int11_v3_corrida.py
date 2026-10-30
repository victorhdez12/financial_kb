"""P-INT11 v3 v1.0, fase D: corrida ÚNICA de desarrollo del motor v3 (docs/int/INT11_prerregistro_v3.md).

Datos ≤ 2004 (load_dev), 14 países; LOCO (principal; puerta D) y temporal (< 1950 → 1950-2004; descriptivo) con la
predictiva SUAVE (`int11v3.evaluar_suave`, Config.v3); comparación descriptiva con v2 (Config.v2, duro) en los mismos
pliegues y semillas; valor crítico con 200 paneles del proceso P1 (`int11_v3_potencia.panel_v3`).

Uso: .venv/bin/python -m scripts.int11_v3_corrida              (puerta: árbol limpio; se niega si ya existe la salida)
     .venv/bin/python -m scripts.int11_v3_corrida --sintetico  (panel SINTÉTICO, pocas réplicas; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

from scripts.int11_corrida import COL, NUCLEO, _f, estructura
from scripts.int11_v3_potencia import PROCESOS, panel_v3
from src.intl import activos3b as A3
from src.intl import data as D
from src.intl import escenarios as E
from src.intl import int6 as S
from src.intl import int11v3 as V
from src.intl import panel as P
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_v3_resultado.json"
POT1 = REPO / "research/int/int11_potencia.json"
POT2 = REPO / "research/int/int11_v2_potencia.json"
POT3 = REPO / "research/int/int11_v3_potencia_P1.json"
SEED = 20261104
CORTE = 1950
R_NULO = 200
TECHO, TOL_ACT = 0.93, 0.03
PRERREG = "docs/int/INT11_prerregistro_v3.md (v1.0, 00d2019)"


def cargar_real_v3(con):
    """= scripts.int11_corrida.cargar_real (misma carga y exclusiones) + estado observado de t − 1 (estado_previo)."""
    a = P.anual(con)
    a = a.loc[a.index.get_level_values(0).isin(NUCLEO)]
    if a.index.get_level_values(1).max() > 2004:
        raise D.FactorCutoffError("panel anual con años > 2004")
    df = a.reset_index()[["pais", "año", "inflacion", "rgdpmad", *COL.values()]].rename(
        columns={v: k for k, v in COL.items()})
    oro = A3.oro_panel(con, NUCLEO)
    oro = oro[oro["año"] >= 1972][["pais", "año", "oro_real_local"]].rename(columns={"oro_real_local": "oro"})
    df = df.merge(oro, on=["pais", "año"], how="left")
    fuera = S.hiper_fuera(np.expm1(a["inflacion"]).dropna())
    f = E.preparar_filas(df, excluir=set(E.GUERRAS) | set(fuera), estado_previo=True)
    if f["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    return f


def _cob_pais(ev) -> dict:
    out = {}
    for c in sorted(set(ev["pais"])):
        m = ev["pais"] == c
        out[c] = float(np.nanmean(np.nanmean(ev["dentro90"][m], 1)))
    return out


def por_pais(ev) -> dict:
    out = {}
    for c in sorted(set(ev["pais"])):
        m = ev["pais"] == c
        out[c] = {"filas": int(m.sum()), "S5": round(float(np.nanmean(np.nanmean(ev["dentro90"][m], 1))), 4),
                  **{a: round(float(np.nanmean(ev["dentro90"][m, j])), 4) for j, a in enumerate(E.ACTIVOS)}}
    return out


def por_regimen(ev) -> dict:
    out = {}
    for i, r in enumerate(E.REGIMENES):
        m = ev["s_prev"] == i
        if m.any():
            out[r] = {"filas": int(m.sum()),
                      **{a: round(float(np.nanmean(ev["dentro90"][m, j])), 4) for j, a in enumerate(E.ACTIVOS)}}
    return out


def nulo(med, med2, sd_b, años, existe, ok, R, rng, n_lotes=20) -> dict:
    acc = {d: {"S5": [], "S_raros": [], "S_activo": [], "pais": []} for d in ("loco", "temporal")}
    cfg = E.Config.v3()
    for r in range(R):
        _, Y, infl, io, bo, ro = panel_v3(med, med2, sd_b, len(años), rng, **PROCESOS["P1"])
        fs = V.filas_v3(ro, Y, infl, io, bo, NUCLEO, años, existe, ok)
        for d in acc:
            ev = V.evaluar_suave(fs, d, cfg, n_lotes, 100, SEED + 7 * r, corte=CORTE)
            st = V.estadisticos(ev)
            acc[d]["S5"].append(st["S5"])
            acc[d]["S_raros"].append(st["S_raros"])
            acc[d]["S_activo"].append(st["S_activo"])
            if d == "loco":
                acc[d]["pais"].append(_cob_pais(ev))
        print("nulo", r + 1, round(acc["loco"]["S5"][-1], 4), flush=True)
    out = {}
    for d, x in acc.items():
        sa = np.array(x["S_activo"], float)
        out[d] = {k: {"banda_2.5_97.5": np.nanpercentile(x[k], [2.5, 97.5]).round(4).tolist(),
                      "p10": round(float(np.nanpercentile(x[k], 10)), 4), "media": round(float(np.nanmean(x[k])), 4)}
                  for k in ("S5", "S_raros")}
        out[d]["S_activo"] = {a: np.nanpercentile(sa[:, j], [2.5, 97.5]).round(4).tolist()
                              for j, a in enumerate(E.ACTIVOS)}
        if x["pais"]:
            out[d]["pais"] = {c: np.nanpercentile([p[c] for p in x["pais"] if c in p], [2.5, 97.5]).round(4).tolist()
                              for c in NUCLEO}
    return out


def puerta_d(L: dict, nb: dict) -> dict:
    c = {"S5_sobre_p2.5_nulo": bool(L["S5"] >= nb["S5"]["banda_2.5_97.5"][0]),
         "S5_bajo_techo_0.93": bool(L["S5"] <= TECHO),
         "activos_a_3pp": {a: bool(abs(v - 0.90) <= TOL_ACT) for a, v in zip(E.ACTIVOS, L["S_activo"])
                           if np.isfinite(v)},
         "raros_sobre_p10_nulo": bool(L["S_raros"] >= nb["S_raros"]["p10"])}
    c["pasa"] = bool(c["S5_sobre_p2.5_nulo"] and c["S5_bajo_techo_0.93"] and all(c["activos_a_3pp"].values())
                     and c["raros_sobre_p10_nulo"])
    return c


def markdown(o: dict) -> str:
    L, T, L2, T2, g, nb = o["loco"], o["temporal"], o["loco_v2"], o["temporal_v2"], o["puerta_D"], o["nulo"]
    act = "\n".join(
        f"| {a} | {_f(L['S_activo'][j])} | {_f(L2['S_activo'][j])} | {_f(T['S_activo'][j])} | {_f(T2['S_activo'][j])} | "
        f"{nb['loco']['S_activo'][a]} |" for j, a in enumerate(E.ACTIVOS))
    reg = "\n".join(f"| {r} | {v['filas']} | " + " | ".join(_f(v[a]) for a in E.ACTIVOS) + " |"
                    for r, v in o["cobertura_por_regimen_loco"].items())
    pp = o["cobertura_por_pais_loco"]
    pais = "\n".join(f"| {c} | {v['filas']} | {_f(v['S5'])} | {_f(o['cobertura_por_pais_loco_v2'][c]['S5'])} | "
                     f"{_f(v['bolsa'])} | {nb['loco']['pais'].get(c)} |" for c, v in pp.items())
    i3, i2 = L["infl5"], L2["infl5"]
    return f"""---
documento: Resultado P-INT11 v3 v1.0, fase D (corrida única de DESARROLLO del motor v3)
prerregistro: {PRERREG}
procedencia: {o['procedencia']}
datos: JST ≤ 2004, 14 países, sin guerras ni hiperinflación. NADA ≥ 2005. NO confirmatorio (v3 se diseñó tras ver v1 y v2 en estos datos)
---

# INT-11 v3: resultado de la corrida de desarrollo

## En una frase
Puerta D (dejando cada país fuera): **{'PASA' if g['pasa'] else 'NO PASA'}**. Los abanicos del 90 % de v3 contuvieron lo
que pasó el **{100 * L['S5']:.1f} %** de las veces (v2 en los mismos pliegues: {100 * L2['S5']:.1f} %); en los regímenes
raros, el **{100 * L['S_raros']:.1f} %** (v2 {100 * L2['S_raros']:.1f} %); cerca del umbral del 3 %, el
**{100 * L['S5_cerca']:.1f} %** (v2 {100 * L2['S5_cerca']:.1f} %, {L['n_cerca']} filas).
{'v3 sustituye a v2 en la confirmación futura (fase C, D7).' if g['pasa'] else 'v3 NO va a la fase C: va v2 (D7).'}

## 1. Puerta D (LOCO)
| criterio | valor | umbral | ¿cumple? |
|---|---|---|---|
| S5 (5 activos) | {_f(L['S5'], 4)} | ≥ {nb['loco']['S5']['banda_2.5_97.5'][0]} (p2,5 del nulo P1) y ≤ 0,93 | {g['S5_sobre_p2.5_nulo'] and g['S5_bajo_techo_0.93']} |
| cada activo | {", ".join(f"{a} {_f(v)}" for a, v in zip(E.ACTIVOS, L['S_activo']))} | 0,90 ± 0,03 | {all(g['activos_a_3pp'].values())} |
| regímenes raros | {_f(L['S_raros'], 4)} | ≥ {nb['loco']['S_raros']['p10']} (p10 del nulo) | {g['raros_sobre_p10_nulo']} |

Banda nula (P1, 20 × 100) de S5 LOCO {nb['loco']['S5']['banda_2.5_97.5']} (media {nb['loco']['S5']['media']}); raros
{nb['loco']['S_raros']['banda_2.5_97.5']}; temporal S5 {nb['temporal']['S5']['banda_2.5_97.5']}.

## 2. Por activo (cobertura del p5-p95)
| activo | LOCO v3 | LOCO v2 | temporal v3 | temporal v2 | banda nula LOCO por activo |
|---|---|---|---|---|---|
{act}

Temporal (< 1950 → 1950-2004, descriptivo): S5 v3 {_f(T['S5'])} (v2 {_f(T2['S5'])}), bolsa v3 {_f(T['Sb'])} (v2 {_f(T2['Sb'])}).
Anchura media del p5-p95 de la bolsa (LOCO): v3 {_f(L['ancho_bolsa'])} frente a v2 {_f(L2['ancho_bolsa'])}.

## 3. Cobertura por régimen de partida (LOCO, v3)
| régimen conocido | filas | {" | ".join(E.ACTIVOS)} |
|---|---|{"---|" * len(E.ACTIVOS)}
{reg}

## 4. Cobertura por país (LOCO; el país se predice sin sus propios datos)
| país | filas | 5 activos v3 | 5 activos v2 | bolsa v3 | banda nula del país (5 activos) |
|---|---|---|---|---|---|
{pais}

## 5. Descriptivos
- **Inflación > 5 % (Brier, LOCO):** BSS v3 {_f(100 * i3['bss'], 1)} % (v2 {_f(100 * i2['bss'], 1)} %); Brier cerca
  del umbral v3 {_f(i3['brier_cerca'], 4)} (v2 {_f(i2['brier_cerca'], 4)}); p media cerca {_f(i3['p_media_cerca'])}
  frente a frecuencia {_f(i3['frec_cerca'])}. Temporal: BSS v3 {_f(100 * T['infl5']['bss'], 1)} % (v2 {_f(100 * T2['infl5']['bss'], 1)} %).
- **Bolsa ≤ −20 % (Brier, LOCO):** BSS v3 {_f(100 * L['caida20']['bss'], 1)} % (v2 {_f(100 * L2['caida20']['bss'], 1)} %),
  frecuencia {_f(L['caida20']['frecuencia'])}.
- **κ** (motor con todas las filas): {o['kappa']:.3g} (en el borde: {o['kappa_en_borde']}).
- **Factor de dispersión de la bolsa por país** (v3; entre paréntesis v2): {o['factor_bolsa_txt']}.
- **Curtosis (exceso) estandarizada por país, panel:** {o['escala_resumen'].get('curtosis')} (v2 agrupada: {o['curtosis_v2']}).
- **n efectivo de Kish (bolsa) de las celdas raras:** {o['kish_raros']}.

## 6. Lectura
{o['lectura']}
"""


def lectura(o: dict) -> str:
    L, L2, T, g = o["loco"], o["loco_v2"], o["temporal"], o["puerta_D"]
    pp = o["cobertura_por_pais_loco"]
    pmin = min(pp, key=lambda c: pp[c]["S5"])
    fuera = [c for c, v in pp.items() if v["S5"] < o["nulo"]["loco"]["pais"][c][0]]
    t = [f"- **Calibración (desarrollo):** {100 * L['S5']:.1f} % (v2 en los mismos pliegues {100 * L2['S5']:.1f} %); "
         f"raros {100 * L['S_raros']:.1f} %; país peor cubierto {pmin} ({100 * pp[pmin]['S5']:.1f} %); países por debajo "
         f"de su banda nula: {', '.join(fuera) if fuera else 'ninguno'}. "
         + ("La puerta D pasa." if g["pasa"] else "La puerta D NO pasa (ver §1)."),
         f"- **Temporal (≤ 1949 → 1950-2004, descriptivo):** S5 {100 * T['S5']:.1f} %, bolsa {100 * T['Sb']:.1f} % "
         "(v1 80,5 %, v2 81,6 %). La semivida no puede corregir este diseño (pondera 1900-1949); es el riesgo principal "
         "de la confirmación.",
         "- **Qué significa:** NO es una confirmación: v3 se diseñó mirando v1 y v2 en estos mismos datos. Solo dice si los "
         "arreglos hacen lo que se esperaba. La confirmación (K1, K2) está en el prerregistro §6 y se hará una vez, dentro "
         "de la confirmación final del proyecto; el periodo ≥ 2005 sigue sin gastar."]
    return "\n".join(t)


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    sint = "--sintetico" in sys.argv
    if not sint:
        if SALIDA.exists():
            raise SystemExit(f"{SALIDA} ya existe: la fase D de P-INT11 v3 es de corrida ÚNICA; no se repite")
        proc = procedencia()
    else:
        proc = {"sintetico": True}
    t0 = time.time()
    med = json.loads(POT1.read_text())["medicion"]
    med2 = json.loads(POT2.read_text())["medicion_v2"]
    sd_b = json.loads(POT3.read_text())["medicion_brecha"]["sd_robusta"]
    con = D.connect()
    f_real = cargar_real_v3(con)
    años, existe, ok = estructura(f_real)
    if sint:
        _, Y, infl, io, bo, ro = panel_v3(med, med2, sd_b, len(años), np.random.default_rng(99), **PROCESOS["P1"])
        f = V.filas_v3(ro, Y, infl, io, bo, NUCLEO, años, existe, ok)
        n_lotes, R = 10, 2
    else:
        f, n_lotes, R = f_real, 200, R_NULO
    if f["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    cfg3, cfg2 = E.Config.v3(), E.Config.v2()
    ev = {}
    for nombre, cfg in (("v3", cfg3), ("v2", cfg2)):
        for d in ("loco", "temporal"):
            ev[(nombre, d)] = V.evaluar_suave(f, d, cfg, n_lotes, 100, SEED, corte=CORTE)
            print(nombre, d, round(time.time() - t0), flush=True)
    st = {k: V.estadisticos(v) for k, v in ev.items()}
    nb = nulo(med, med2, sd_b, años, existe, ok, R, np.random.default_rng(SEED))
    g = puerta_d(st[("v3", "loco")], nb["loco"])
    gen3, gen2 = E.Generador(cfg3).ajustar(f), E.Generador(cfg2).ajustar(f)
    kish = {E.REGIMENES[i] + "→" + E.REGIMENES[j]: round(float(gen3.sd_celda[(i, j)][1][0]), 1)
            for i in (2, 3) for j in range(E.K) if gen3.nivel_celda[(i, j)] == 0}
    fb3, fb2 = gen3.escala_resumen["factor_pais"], gen2.escala_resumen["factor_pais"]
    o = {"procedencia": proc, "prerregistro": PRERREG, "semilla": SEED, "config": str(cfg3), "filas": int(len(f)),
         "años": [int(f["año"].min()), int(f["año"].max())],
         "loco": st[("v3", "loco")], "temporal": st[("v3", "temporal")],
         "loco_v2": st[("v2", "loco")], "temporal_v2": st[("v2", "temporal")], "nulo": nb, "puerta_D": g,
         "cobertura_por_regimen_loco": por_regimen(ev[("v3", "loco")]),
         "cobertura_por_regimen_temporal": por_regimen(ev[("v3", "temporal")]),
         "cobertura_por_pais_loco": por_pais(ev[("v3", "loco")]),
         "cobertura_por_pais_loco_v2": por_pais(ev[("v2", "loco")]),
         "kappa": gen3.kappa, "kappa_en_borde": gen3.kappa_en_borde, "escala_resumen": gen3.escala_resumen,
         "curtosis_v2": gen2.escala_resumen["curtosis"], "kish_raros": kish,
         "factor_bolsa": {c: [fb3[c][0], fb2[c][0]] for c in fb3},
         "factor_bolsa_txt": ", ".join(f"{c} {fb3[c][0]:.2f} ({fb2[c][0]:.2f})" for c in fb3)}
    o["lectura"] = lectura(o)
    o["segundos"] = round(time.time() - t0)
    print(json.dumps({k: o[k] for k in ("puerta_D",)}, ensure_ascii=False, default=float))
    if not sint:
        SALIDA.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
        SALIDA.with_suffix(".md").write_text(markdown(o))
    else:
        print(markdown(o)[:4000])
    print("segundos", o["segundos"])


if __name__ == "__main__":
    main()
