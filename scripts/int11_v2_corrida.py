"""P-INT11 v2 v1.0, fase D: corrida ÚNICA de desarrollo del motor v2 (docs/int/INT11_prerregistro_v2.md).

Datos ≤ 2004 (load_dev), 14 países; LOCO (principal; puerta D) y temporal (< 1950 → 1950-2004; descriptivo); valor
crítico con 200 paneles del nulo HETEROGÉNEO; descriptivos (C1 sin decisión, Brier, por régimen y país, h = 5).

Uso: .venv/bin/python -m scripts.int11_v2_corrida              (puerta: árbol limpio; se niega si ya existe la salida)
     .venv/bin/python -m scripts.int11_v2_corrida --sintetico  (panel SINTÉTICO, pocas réplicas; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

from scripts.int11_corrida import NUCLEO, _f, cargar_real, descriptivos, estructura
from scripts.int11_v2_potencia import panel_v2
from src.intl import data as D
from src.intl import escenarios as E
from src.intl import int11 as Q
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_v2_resultado.json"
POT1 = REPO / "research/int/int11_potencia.json"
POT2 = REPO / "research/int/int11_v2_potencia.json"
SEED = 20261101
CORTE = 1950
R_NULO = 200
TOL_S5, TOL_ACT = 0.015, 0.03
PRERREG = "docs/int/INT11_prerregistro_v2.md (v1.0)"


def s_raros(ev: dict) -> float:
    m = np.isin(ev["s_prev"], (2, 3))
    return float(np.nanmean(ev["dentro90"][m])) if m.any() else float("nan")


def por_pais(ev: dict) -> dict:
    out = {}
    for c in sorted(set(ev["pais"])):
        m = ev["pais"] == c
        out[c] = {"filas": int(m.sum()), "S5": round(float(np.nanmean(np.nanmean(ev["dentro90"][m], 1))), 4),
                  "bolsa": round(float(np.nanmean(ev["dentro90"][m, 0])), 4)}
    return out


def por_regimen_activo(ev: dict) -> dict:
    out = {}
    for i, r in enumerate(E.REGIMENES):
        m = ev["s_prev"] == i
        if m.any():
            out[r] = {"filas": int(m.sum()),
                      **{a: round(float(np.nanmean(ev["dentro90"][m, j])), 4) for j, a in enumerate(E.ACTIVOS)}}
    return out


def nulo(med, med2, años, existe, ok, R, rng) -> dict:
    T = len(años)
    fac = np.array([med2["factor_pais"][c] for c in NUCLEO])
    out = {d: {"S5": [], "Sb": [], "S_raros": []} for d in ("loco", "temporal")}
    for r in range(R):
        reg, Y, infl = panel_v2(med, med2, T, rng, fac=fac, fac_raro=1.0)
        fs = Q.filas_sinteticas(reg, Y, NUCLEO, años, existe, ok, infl)
        for d in out:
            ev = Q.evaluar_motor(fs, d, 20, 100, SEED + 7 * r, H=1, corte=CORTE, cfg=E.Config.v2())
            res = Q.resumen_motor(ev)
            out[d]["S5"].append(res["S5"])
            out[d]["Sb"].append(res["Sb"])
            out[d]["S_raros"].append(s_raros(ev))
    return {d: {k: {"banda_2.5_97.5": np.nanpercentile(v, [2.5, 97.5]).round(4).tolist(),
                    "media": round(float(np.nanmean(v)), 4)} for k, v in x.items()} for d, x in out.items()}


def puerta_d(L: dict, raros: float, banda: dict) -> dict:
    c = {"S5_a_1.5pp": abs(L["S5"] - 0.90) <= TOL_S5,
         "activos_a_3pp": {a: bool(abs(v - 0.90) <= TOL_ACT) for a, v in L["S_activo"].items() if np.isfinite(v)},
         "raros_sobre_p2.5_nulo": bool(raros >= banda["S_raros"]["banda_2.5_97.5"][0])}
    c["pasa"] = bool(c["S5_a_1.5pp"] and all(c["activos_a_3pp"].values()) and c["raros_sobre_p2.5_nulo"])
    return c


def markdown(o: dict) -> str:
    L, T, g, nb = o["loco"], o["temporal"], o["puerta_D"], o["nulo"]
    v1 = o["comparacion_v1"]
    filas_act = "\n".join(
        f"| {a} | {_f(L['S_activo'][a])} | {_f(v1['S_activo'].get(a))} | {_f(T['S_activo'].get(a))} | "
        f"{_f(L['cobertura_80_activo'][a])} | {_f(L['crpss_%'][a], 2)} | {_f(T['crpss_%'].get(a), 2)} | "
        f"{_f(o['descriptivo_loco'].get('h5', {}).get('cobertura_90', {}).get(a))} |" for a in E.ACTIVOS)
    reg = o["cobertura_por_regimen_loco"]
    filas_reg = "\n".join(f"| {r} | {v['filas']} | " + " | ".join(_f(v[a]) for a in E.ACTIVOS) + " |"
                          for r, v in reg.items())
    pp = o["cobertura_por_pais_loco"]
    filas_pais = "\n".join(f"| {c} | {v['filas']} | {_f(v['S5'])} | {_f(v['bolsa'])} |" for c, v in pp.items())
    br = o["descriptivo_loco"]["brier"]
    c1 = o["C1_descriptivo"]
    return f"""---
documento: Resultado P-INT11 v2 v1.0, fase D (corrida única de DESARROLLO del motor v2)
prerregistro: {PRERREG}
procedencia: {o['procedencia']}
datos: JST ≤ 2004, 14 países, sin guerras ni hiperinflación. NADA ≥ 2005. NO confirmatorio (v2 se diseñó tras ver v1 en estos datos)
---

# INT-11 v2: resultado de la corrida de desarrollo

## En una frase
Puerta D (dejando cada país fuera): **{'PASA' if g['pasa'] else 'NO PASA'}**. Los abanicos del 90 % de v2 contuvieron lo
que pasó el **{100 * L['S5']:.1f} %** de las veces (v1: {100 * v1['S5']:.1f} %); en los regímenes raros, el
**{100 * o['S_raros_loco']:.1f} %** (bolsa: {100 * o['S_raros_bolsa_loco']:.1f} %; v1 solo publicó la bolsa: {100 * v1['S_raros_bolsa']:.1f} %). {'Apto para la confirmación futura (fase C).' if g['pasa'] else 'v2 NO va a la fase C.'}

## 1. Puerta D (LOCO)
| criterio | valor | umbral | ¿cumple? |
|---|---|---|---|
| S5 (5 activos) | {_f(L['S5'], 4)} | 0,90 ± 0,015 | {g['S5_a_1.5pp']} |
| cada activo | {", ".join(f"{a} {_f(v)}" for a, v in L['S_activo'].items())} | 0,90 ± 0,03 | {all(g['activos_a_3pp'].values())} |
| regímenes raros | {_f(o['S_raros_loco'], 4)} | ≥ {nb['loco']['S_raros']['banda_2.5_97.5'][0]} (p2,5 del nulo) | {g['raros_sobre_p2.5_nulo']} |

Informativo: banda nula (heterogénea) de S5 LOCO {nb['loco']['S5']['banda_2.5_97.5']} (media {nb['loco']['S5']['media']}),
Sb {nb['loco']['Sb']['banda_2.5_97.5']}; temporal S5 {nb['temporal']['S5']['banda_2.5_97.5']}, Sb {nb['temporal']['Sb']['banda_2.5_97.5']}.
Real temporal: S5 {_f(T['S5'])}, Sb {_f(T['Sb'])}.

## 2. Por activo
| activo | cobertura 90 % LOCO v2 | v1 | temporal v2 | cobertura 80 % LOCO | CRPSS % LOCO | CRPSS % temporal | cobertura 90 % h = 5 (desc.) |
|---|---|---|---|---|---|---|---|
{filas_act}

## 3. Cobertura 90 % por régimen de partida (LOCO)
| régimen conocido | filas | {" | ".join(E.ACTIVOS)} |
|---|---|{"---|" * len(E.ACTIVOS)}
{filas_reg}

## 4. Cobertura 90 % por país (LOCO; el país se predice sin sus propios datos)
| país | filas | 5 activos | bolsa |
|---|---|---|---|
{filas_pais}

## 5. Descriptivos
- **Finura (C1, sin decisión; contaminado):** CRPSS medio {_f(L['crpss_medio_%'], 2)} % (v1 {_f(v1['crpss_medio_%'], 2)} %);
  DM d = {_f(c1['d_media'], 4)}, t = {_f(c1['t'], 2)}, p = {_f(c1['p'], 4)}; temporal d = {_f(c1['d_media_temporal'], 4)}.
- **Eventos (Brier, LOCO):** inflación > 5 % BSS {_f(br['inflacion_5']['bss_%'], 1)} % (frecuencia
  {_f(br['inflacion_5']['frecuencia'])}); caída de la bolsa ≥ 20 % BSS {_f(br['caida_bolsa_20']['bss_%'], 1)} %
  (frecuencia {_f(br['caida_bolsa_20']['frecuencia'])}).
- **κ** (motor con todas las filas): {o['kappa']:.3g} (en el borde: {o['kappa_en_borde']}).
- **Factores de dispersión por país** (bolsa, motor con todas las filas): {o['factor_bolsa']}.

## 6. Lectura
{o['lectura']}
"""


def lectura(o: dict) -> str:
    L, T, g, v1 = o["loco"], o["temporal"], o["puerta_D"], o["comparacion_v1"]
    peor = max(L["S_activo"], key=lambda a: abs(L["S_activo"][a] - 0.9))
    pp = o["cobertura_por_pais_loco"]
    pmin = min(pp, key=lambda c: pp[c]["S5"])
    t = [f"- **Calibración (desarrollo):** {100 * L['S5']:.1f} % frente al 90 % nominal (v1 {100 * v1['S5']:.1f} %); "
         f"activo más desviado {peor} ({100 * L['S_activo'][peor]:.1f} %); regímenes raros "
         f"{100 * o['S_raros_loco']:.1f} %; país peor cubierto {pmin} ({100 * pp[pmin]['S5']:.1f} %). "
         + ("La puerta D pasa." if g["pasa"] else "La puerta D NO pasa (ver §1)."),
         f"- **Temporal (≤ 1949 → 1950-2004, descriptivo):** S5 {100 * T['S5']:.1f} %, bolsa {100 * T['Sb']:.1f} % "
         f"(v1: bolsa 80,5 %). Es el diseño que más se parece a la confirmación futura.",
         "- **Qué significa:** NO es una confirmación: v2 se diseñó mirando v1 en estos mismos datos. Solo dice si los "
         "arreglos hacen lo que se esperaba. La confirmación (K1 calibración, K2 inflación) está escrita en el "
         "prerregistro §6 y se hará una vez, dentro de la confirmación final del proyecto."]
    return "\n".join(t)


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    sint = "--sintetico" in sys.argv
    if not sint:
        if SALIDA.exists():
            raise SystemExit(f"{SALIDA} ya existe: la fase D de P-INT11 v2 es de corrida ÚNICA; no se repite")
        proc = procedencia()
    else:
        proc = {"sintetico": True}
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    med = json.loads(POT1.read_text())["medicion"]
    med2 = json.loads(POT2.read_text())["medicion_v2"]
    con = D.connect()
    f_real = cargar_real(con)
    años, existe, ok = estructura(f_real)
    if sint:
        fac = np.array([med2["factor_pais"][c] for c in NUCLEO])
        reg, Y, infl = panel_v2(med, med2, len(años), np.random.default_rng(99), fac=fac)
        f = Q.filas_sinteticas(reg, Y, NUCLEO, años, existe, ok, infl)
        n_lotes, R = 20, 3
    else:
        f, n_lotes, R = f_real, 200, R_NULO
    if f["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    cfg = E.Config.v2()
    ev_l = Q.evaluar_motor(f, "loco", n_lotes, 100, SEED, H=5, corte=CORTE, cfg=cfg)
    ev_t = Q.evaluar_motor(f, "temporal", n_lotes, 100, SEED, H=1, corte=CORTE, cfg=cfg)
    L, T = Q.resumen_motor(ev_l), Q.resumen_motor(ev_t)
    nb = nulo(med, med2, años, existe, ok, R, rng)
    raros = s_raros(ev_l)
    g = puerta_d(L, raros, nb["loco"])
    gen = E.Generador(cfg).ajustar(f)
    v1 = {"S5": float("nan"), "S_activo": {}, "crpss_medio_%": float("nan"), "S_raros_bolsa": float("nan")}
    v1_path = REPO / "research/int/int11_resultado.json"
    if v1_path.exists() and not sint:                     # solo se LEEN los números ya publicados de v1
        r1 = json.loads(v1_path.read_text())
        pr = r1["descriptivo_loco"]["por_regimen_partida"]
        raros_v1 = [pr[r] for r in ("estanflacion", "crecimiento_bajo") if r in pr]
        v1 = {"S5": r1["loco"]["S5"], "S_activo": r1["loco"]["S_activo"], "crpss_medio_%": r1["loco"]["crpss_medio_%"],
              "S_raros_bolsa": sum(x["filas"] * x["cobertura_90"]["bolsa"] for x in raros_v1)
              / max(sum(x["filas"] for x in raros_v1), 1)}
    o = {"procedencia": proc, "prerregistro": PRERREG, "semilla": SEED, "config": str(cfg), "filas": int(len(f)),
         "años": [int(f["año"].min()), int(f["año"].max())], "loco": L, "temporal": T, "nulo": nb,
         "S_raros_loco": raros, "S_raros_bolsa_loco": float(np.nanmean(ev_l["dentro90"][np.isin(ev_l["s_prev"], (2, 3)), 0])),
         "S_raros_temporal": s_raros(ev_t), "puerta_D": g,
         "C1_descriptivo": {"d_media": L["d_media"], "t": L["dm"]["t"], "p": L["dm"]["p_unilateral"],
                            "d_media_temporal": T["d_media"]},
         "cobertura_por_regimen_loco": por_regimen_activo(ev_l), "cobertura_por_regimen_temporal": por_regimen_activo(ev_t),
         "cobertura_por_pais_loco": por_pais(ev_l), "descriptivo_loco": descriptivos(ev_l),
         "descriptivo_temporal": descriptivos(ev_t), "kappa": gen.kappa, "kappa_en_borde": gen.kappa_en_borde,
         "factor_bolsa": {c: v[0] for c, v in gen.escala_resumen["factor_pais"].items()},
         "escala_resumen": gen.escala_resumen, "comparacion_v1": v1}
    o["lectura"] = lectura(o)
    o["segundos"] = round(time.time() - t0)
    print(json.dumps({k: o[k] for k in ("loco", "nulo", "puerta_D", "S_raros_loco")}, ensure_ascii=False, indent=1,
                     default=float)[:5000])
    if not sint:
        SALIDA.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
        SALIDA.with_suffix(".md").write_text(markdown(o))
    else:
        print(markdown(o)[:3000])
    print("segundos", o["segundos"])


if __name__ == "__main__":
    main()
