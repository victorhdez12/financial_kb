"""P-DEV-INT11 v1.0: corrida ÚNICA de desarrollo del motor de escenarios (docs/int/INT11_prerregistro_v1.md).

Datos ≤ 2004 (load_dev), 14 países del núcleo; LOCO (principal) y temporal (< 1950 → 1950-2004); puerta de calibración
con valor crítico simulado (200 paneles sintéticos con la medición congelada de research/int/int11_potencia.json y la
misma estructura de huecos); C1 = M1 mejor que M0 en CRPS (DM por años, unilateral, α = 0,05); descriptivos.

Uso: .venv/bin/python -m scripts.int11_corrida              (puerta: árbol limpio; se niega si ya existe la salida)
     .venv/bin/python -m scripts.int11_corrida --sintetico  (panel SINTÉTICO en lugar del real, pocas réplicas;
                                                              comprueba la tubería; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import activos3b as A3
from src.intl import data as D
from src.intl import escenarios as E
from src.intl import int6 as S
from src.intl import int11 as Q
from src.intl import panel as P
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_resultado.json"
POTENCIA = REPO / "research/int/int11_potencia.json"
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
COL = {"bolsa": "eq_tr_real", "bonos": "bond_tr_real", "letras": "bill_rate_real", "vivienda": "housing_tr_real"}
SEED = 20261030
CORTE = 1950
R_NULO = 200
ALFA = 0.05
TOL = 0.05


def cargar_real(con) -> pd.DataFrame:
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
    excluir = set(E.GUERRAS) | set(fuera)
    f = E.preparar_filas(df, excluir=excluir)
    if f["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    return f


def estructura(f: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """años (T,), existe (N, T), activo_ok (N, T, A) del panel real (solo disponibilidad, sin valores)."""
    años = np.arange(int(f["año"].min()) - 1, int(f["año"].max()) + 1)
    ci = {c: i for i, c in enumerate(NUCLEO)}
    existe = np.zeros((len(NUCLEO), len(años)), bool)
    ok = np.zeros((len(NUCLEO), len(años), len(E.ACTIVOS)), bool)
    i, t = f["pais"].map(ci).to_numpy(), (f["año"] - años[0]).to_numpy()
    existe[i, t] = True
    ok[i, t] = np.isfinite(f[list(E.ACTIVOS)].to_numpy(float))
    return años, existe, ok


def panel_sintetico(med: dict, años, existe, ok, rng) -> pd.DataFrame:
    from scripts.int11_potencia import simular_panel
    reg, Y = simular_panel(med, 1.0, len(NUCLEO), len(años), None, rng)
    return Q.filas_sinteticas(reg, Y, NUCLEO, años, existe, ok)


def nulo(med: dict, años, existe, ok, R: int, rng) -> dict:
    out = {"loco": {"S5": [], "Sb": []}, "temporal": {"S5": [], "Sb": []}}
    for r in range(R):
        fs = panel_sintetico(med, años, existe, ok, rng)
        for dis in out:
            ev = Q.evaluar_motor(fs, dis, 20, 100, SEED + 7 * r, H=1, corte=CORTE)
            res = Q.resumen_motor(ev)
            out[dis]["S5"].append(res["S5"])
            out[dis]["Sb"].append(res["Sb"])
    return {dis: {k: {"banda_2.5_97.5": np.percentile(v, [2.5, 97.5]).round(4).tolist(),
                      "media": round(float(np.mean(v)), 4)} for k, v in d.items()} for dis, d in out.items()}


def puerta(res: dict, banda: dict) -> dict:
    dentro = lambda x, b: b[0] <= x <= b[1]  # noqa: E731
    c = {"S5_en_banda": dentro(res["S5"], banda["S5"]["banda_2.5_97.5"]),
         "Sb_en_banda": dentro(res["Sb"], banda["Sb"]["banda_2.5_97.5"]),
         "S5_a_5pp": abs(res["S5"] - 0.90) <= TOL,
         "activos_a_5pp": {a: abs(v - 0.90) <= TOL for a, v in res["S_activo"].items() if np.isfinite(v)}}
    c["pasa"] = bool(c["S5_en_banda"] and c["Sb_en_banda"] and c["S5_a_5pp"] and all(c["activos_a_5pp"].values()))
    return c


def descriptivos(ev: dict) -> dict:
    A = list(E.ACTIVOS)
    pit = {a: np.histogram(ev["pit"][:, j][np.isfinite(ev["pit"][:, j])], bins=10, range=(0, 1))[0].tolist()
           for j, a in enumerate(A)}
    por_reg = {}
    for i, rname in enumerate(E.REGIMENES):
        m = ev["s_prev"] == i
        if m.any():
            por_reg[rname] = {"filas": int(m.sum()),
                              "cobertura_90": dict(zip(A, np.round(np.nanmean(ev["dentro90"][m], 0), 3).tolist())),
                              "crpss_%": dict(zip(A, np.round(100 * (1 - np.nanmean(ev["crps1"][m], 0)
                                                                     / np.nanmean(ev["crps0"][m], 0)), 2).tolist()))}
    brier = {}
    for k, y in (("caida_bolsa_20", ev["y"][:, 0] <= -0.20), ("inflacion_5", ev["infl"] > 0.05)):
        val = np.isfinite(ev["y"][:, 0]) if k.startswith("caida") else np.isfinite(ev["infl"])
        p1 = ev["p_caida_m1" if k.startswith("caida") else "p_infl_m1"][val]
        p0 = ev["p_caida_m0" if k.startswith("caida") else "p_infl_m0"][val]
        yy = y[val].astype(float)
        b1, b0 = float(np.mean((p1 - yy) ** 2)), float(np.mean((p0 - yy) ** 2))
        brier[k] = {"frecuencia": round(float(yy.mean()), 4), "brier_m1": round(b1, 5), "brier_m0": round(b0, 5),
                    "bss_%": round(100 * (1 - b1 / b0), 2)}
    out = {"pit_10": pit, "por_regimen_partida": por_reg, "brier": brier}
    if "crps0_5" in ev:
        c0, c1 = ev["crps0_5"], ev["crps1_5"]
        out["h5"] = {"ventanas_activo": dict(zip(A, np.isfinite(c0).sum(0).astype(int).tolist())),
                     "crpss_%": dict(zip(A, np.round(100 * (1 - np.nanmean(c1, 0) / np.nanmean(c0, 0)), 2).tolist())),
                     "cobertura_90": dict(zip(A, np.round(np.nanmean(ev["dentro90_5"], 0), 3).tolist()))}
    return out


def _f(x, n=3):
    return "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{n}f}".replace(".", ",")


def markdown(o: dict) -> str:
    L, T = o["loco"], o["temporal"]
    g = o["puerta_loco"]
    c1 = o["C1"]
    A = list(E.ACTIVOS)
    filas_act = "\n".join(
        f"| {a} | {_f(L['S_activo'][a])} | {_f(T['S_activo'].get(a))} | {_f(L['cobertura_80_activo'][a])} | "
        f"{_f(L['cobertura_90_m0_activo'][a])} | {_f(L['crpss_%'][a], 2)} | {_f(T['crpss_%'].get(a), 2)} | "
        f"{_f(o['descriptivo_loco'].get('h5', {}).get('crpss_%', {}).get(a), 2)} | "
        f"{_f(o['descriptivo_loco'].get('h5', {}).get('cobertura_90', {}).get(a))} |" for a in A)
    nb = o["nulo"]
    br = o["descriptivo_loco"]["brier"]
    reg = o["descriptivo_loco"]["por_regimen_partida"]
    filas_reg = "\n".join(f"| {r} | {v['filas']} | {_f(v['cobertura_90']['bolsa'])} | {_f(v['crpss_%']['bolsa'], 1)} | "
                          f"{_f(v['crpss_%']['bonos'], 1)} | {_f(v['crpss_%']['letras'], 1)} |" for r, v in reg.items())
    return f"""---
documento: Resultado P-DEV-INT11 v1.0 (corrida única de desarrollo del motor de escenarios)
prerregistro: docs/int/INT11_prerregistro_v1.md (congelado en a9f6279)
procedencia: {o['procedencia']}
datos: JST ≤ 2004, 14 países, sin guerras ni hiperinflación. NADA ≥ 2005. NO confirmatorio para C1 (Atlas §8 ya miró)
---

# INT-11: resultado de la corrida de desarrollo

## En una frase
Puerta de calibración (LOCO): **{'PASA' if g['pasa'] else 'NO PASA'}**. C1 (el régimen mejora la distribución a 1 año
frente a no saberlo): **{c1['clasificacion']}** (CRPSS medio {_f(L['crpss_medio_%'], 2)} %, p = {_f(c1['p'], 4)}).

## 1. Calibración (¿el abanico p5-p95 contiene lo que pasó el 90 % de las veces?)
| | LOCO | banda simulada (2,5-97,5) | temporal 1950-2004 | banda simulada |
|---|---|---|---|---|
| S5 (5 activos) | {_f(L['S5'])} | {nb['loco']['S5']['banda_2.5_97.5']} | {_f(T['S5'])} | {nb['temporal']['S5']['banda_2.5_97.5']} |
| Sb (bolsa) | {_f(L['Sb'])} | {nb['loco']['Sb']['banda_2.5_97.5']} | {_f(T['Sb'])} | {nb['temporal']['Sb']['banda_2.5_97.5']} |

Criterios (LOCO): S5 en banda {g['S5_en_banda']}; Sb en banda {g['Sb_en_banda']}; |S5 − 0,90| ≤ 5 pp {g['S5_a_5pp']};
cada activo a ≤ 5 pp {g['activos_a_5pp']}.

## 2. Por activo
| activo | cobertura 90 % LOCO | temporal | cobertura 80 % LOCO | cobertura 90 % de M0 (LOCO) | CRPSS % LOCO | CRPSS % temporal | CRPSS % h = 5 (desc.) | cobertura 90 % h = 5 (desc.) |
|---|---|---|---|---|---|---|---|---|
{filas_act}

## 3. Contraste C1 (único, α = 0,05 unilateral)
LOCO: media de d = {_f(c1['d_media'], 4)} (mejora media del CRPS normalizado), t = {_f(c1['t'], 2)}, {c1['años']} años,
p = {_f(c1['p'], 4)}. Temporal: media de d = {_f(c1['d_media_temporal'], 4)} (mismo signo: {c1['mismo_signo_temporal']}).
Clasificación: **{c1['clasificacion']}**.

## 4. Descriptivo
**Por régimen de partida (LOCO):**

| régimen conocido | filas | cobertura 90 % bolsa | CRPSS % bolsa | CRPSS % bonos | CRPSS % letras |
|---|---|---|---|---|---|
{filas_reg}

**Eventos (Brier, LOCO):** caída de la bolsa ≥ 20 % (frecuencia {_f(br['caida_bolsa_20']['frecuencia'])}): BSS
{_f(br['caida_bolsa_20']['bss_%'], 1)} %; inflación > 5 % (frecuencia {_f(br['inflacion_5']['frecuencia'])}): BSS
{_f(br['inflacion_5']['bss_%'], 1)} %. (BSS > 0: el motor mejora a la frecuencia histórica.)

**PIT (10 casillas, LOCO):** {o['descriptivo_loco']['pit_10']}

## 5. Lectura
{o['lectura']}
"""


def lectura(o: dict) -> str:
    L, T, g, c1 = o["loco"], o["temporal"], o["puerta_loco"], o["C1"]
    peor = max(L["S_activo"], key=lambda a: abs(L["S_activo"][a] - 0.9))
    t = []
    t.append(f"- **Calibración:** el abanico p5-p95 del motor contuvo lo realizado el {100 * L['S5']:.1f} % de las veces "
             f"(5 activos, dejando el país fuera; nominal 90 %); la bolsa, el {100 * L['Sb']:.1f} %. "
             f"El activo más desviado es {peor} ({100 * L['S_activo'][peor]:.1f} %). "
             + ("Los abanicos tienen la anchura correcta." if g["pasa"] else
                "La puerta NO pasa: los abanicos no tienen la anchura correcta en algún criterio (ver §1)."))
    t.append(f"- **Finura:** frente a no saber el régimen, el CRPS mejora un {L['crpss_medio_%']:.2f} % de media "
             f"(bolsa {L['crpss_%']['bolsa']:.2f} %, bonos {L['crpss_%']['bonos']:.2f} %, letras "
             f"{L['crpss_%']['letras']:.2f} %). Era lo esperado por la potencia: mejoras pequeñas, sobre todo en "
             f"bonos y letras.")
    t.append(f"- **C1: {c1['clasificacion']}.** Recordatorio: no es confirmatorio (el Atlas ya cruzó régimen y "
             f"rentabilidad con estos datos).")
    t.append(f"- **Temporal (entrenar ≤ 1949, evaluar 1950-2004):** cobertura {100 * T['S5']:.1f} %, CRPSS "
             f"{T['crpss_medio_%']:.2f} %.")
    return "\n".join(t)


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    sint = "--sintetico" in sys.argv
    if not sint:
        if SALIDA.exists():
            raise SystemExit(f"{SALIDA} ya existe: P-DEV-INT11 es de corrida ÚNICA; no se repite")
        proc = procedencia()
    else:
        proc = {"sintetico": True}
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    med = json.loads(POTENCIA.read_text())["medicion"]
    con = D.connect()
    f_real = cargar_real(con)
    años, existe, ok = estructura(f_real)
    if sint:
        f = panel_sintetico(med, años, existe, ok, np.random.default_rng(99))
        n_lotes, R = 20, 5
    else:
        f, n_lotes, R = f_real, 200, R_NULO
    ev_l = Q.evaluar_motor(f, "loco", n_lotes, 100, SEED, H=5, corte=CORTE)
    ev_t = Q.evaluar_motor(f, "temporal", n_lotes, 100, SEED, H=1, corte=CORTE)
    L, T = Q.resumen_motor(ev_l), Q.resumen_motor(ev_t)
    nb = nulo(med, años, existe, ok, R, rng)
    g = puerta(L, nb["loco"])
    gt = puerta(T, nb["temporal"])
    p = L["dm"]["p_unilateral"]
    est = g["pasa"] and p < ALFA and L["d_media"] > 0 and T["d_media"] > 0
    clas = ("establecido" if est else
            "no establecido (motor no calibrado)" if not g["pasa"] and p < ALFA and L["d_media"] > 0 else
            "no establecido")
    o = {"procedencia": proc, "prerregistro": "docs/int/INT11_prerregistro_v1.md (a9f6279)", "semilla": SEED,
         "filas": int(len(f)), "años": [int(f["año"].min()), int(f["año"].max())],
         "loco": L, "temporal": T, "nulo": nb, "puerta_loco": g, "puerta_temporal_informativa": gt,
         "C1": {"d_media": L["d_media"], "t": L["dm"]["t"], "p": p, "años": L["dm"]["años"],
                "d_media_temporal": T["d_media"], "mismo_signo_temporal": bool(T["d_media"] > 0),
                "clasificacion": clas},
         "descriptivo_loco": descriptivos(ev_l), "descriptivo_temporal": descriptivos(ev_t)}
    o["lectura"] = lectura(o)
    o["segundos"] = round(time.time() - t0)
    print(json.dumps({k: o[k] for k in ("loco", "temporal", "nulo", "puerta_loco", "C1")}, ensure_ascii=False,
                     indent=1, default=float)[:6000])
    if not sint:
        SALIDA.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
        SALIDA.with_suffix(".md").write_text(markdown(o))
    else:
        print(markdown(o)[:3000])
    print("segundos", o["segundos"])


if __name__ == "__main__":
    main()
