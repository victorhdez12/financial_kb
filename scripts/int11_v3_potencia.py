"""INT-11 v3: potencia por SIMULACIÓN de la calibración y del Brier de "inflación > 5 %" (docs/int/INT11_v3_diseno.md §5).

Ningún resultado real se cruza con el régimen. Medición real (≤ 2004, solo macro): dt robusta de la brecha P3
(IQR/1,349; núcleo de 14 países, sin guerras). Todo lo demás es la medición CONGELADA de v1 (research/int/
int11_potencia.json: latentes, dt común/propia, ν, R) y v2 (research/int/int11_v2_potencia.json: factores por país,
frecuencia de inflación > 5 %).

Procesos (hipotéticos, fijados antes de correr):
  P0 nulo v2: heterogéneo, inflación y brecha continuas, sin error de medida, estacionario.
  P1 ruido: P0 + error de medida en lo OBSERVADO (inflación N(0; 0,25 pp), brecha N(0; 0,5 pp)); el motor ve el régimen
     observado, la rentabilidad depende del verdadero.
  P2 ruido + época: P1 + choques × 1,3 desde 1950 en todos los activos (no estacionariedad hipotética, no medida).
Configuraciones: v2 (Config.v2, duro), v3 (Config.v3, suave), v3_duro (σ = 0), v3_sin_epoca (semivida 0),
  v3_curt_agrupada (curtosis de v2).
Diseños: LOCO y temporal (< 1950 → 1950-2004) de desarrollo; bloqueado (entrena ≤ 2004, prueba 2005-2020).
Estadísticos: S5, S_raros, S5 cerca del umbral (|π − 3 %| < 0,5 pp), anchura media del p5-p95 de la bolsa, Brier y BSS
de inflación > 5 % (global y cerca) con DM por años; en el bloqueado, potencia de la puerta (intervalos escalados por k)
y del Brier.

Uso: .venv/bin/python -m scripts.int11_v3_potencia P0|P1|P2 [R]   (árbol limpio; research/int/int11_v3_potencia_P*.json)
     .venv/bin/python -m scripts.int11_v3_potencia P1 2 --prueba  (sin puerta; no escribe)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

from scripts.int11_potencia import NUCLEO, par_dgp
from src.intl import data as D
from src.intl import escenarios as E
from src.intl import int11 as Q
from src.intl import int11v3 as V
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
SEED = 20261103
A0 = 1875
K_ANCHO = (1.0, 0.875, 0.78)
PROCESOS = {"P0": dict(ruido=(0.0, 0.0), epoca=None),
            "P1": dict(ruido=(0.0025, 0.005), epoca=None),
            "P2": dict(ruido=(0.0025, 0.005), epoca=(1950, 1.3))}
CONFIGS = {"v2": lambda: E.Config.v2(), "v3": lambda: E.Config.v3(),
           "v3_duro": lambda: E.Config.v3(sigma_infl=0.0, sigma_brecha=0.0),
           "v3_sin_epoca": lambda: E.Config.v3(semivida_epoca=0.0),
           "v3_curt_agrupada": lambda: E.Config.v3(curtosis_escala="agrupada")}


def medir_brecha(con) -> dict:
    from scripts.int11_corrida import cargar_real                     # noqa: F401 (misma carga y exclusiones)
    from src.intl import panel as P
    from src.intl import int6 as S
    a = P.anual(con)
    a = a.loc[a.index.get_level_values(0).isin(NUCLEO)]
    if a.index.get_level_values(1).max() > 2004:
        raise D.FactorCutoffError("panel anual con años > 2004")
    d = E.estados_operables(a.reset_index()[["pais", "año", "inflacion", "rgdpmad"]])
    fuera = S.hiper_fuera(np.expm1(a["inflacion"]).dropna())
    ok = [(p, t) not in fuera and t not in E.GUERRAS for p, t in zip(d["pais"], d["año"])]
    b = d.loc[ok, "brecha"].dropna()
    iqr = float(np.subtract(*np.percentile(b, [75, 25])))
    return {"sd_robusta": iqr / 1.349, "sd": float(b.std()), "frecuencia_negativa": float((b < 0).mean()), "n": int(len(b))}


def panel_v3(med, med2, sd_b, T, rng, ruido, epoca):
    """reg verdadero, Y, inflación verdadera; inflación y brecha OBSERVADAS (con error) y régimen observado."""
    lat = med["latente"]
    fac = np.array([med2["factor_pais"][c] for c in NUCLEO])
    reg, zi, zg = Q.dgp_regimenes(len(NUCLEO), T, lat, rng, latentes=True)
    infl = Q.inflacion_desde_latente(zi, lat["q_i"], med2["frecuencia_infl_5"])
    brecha = V.brecha_desde_latente(zg, lat["q_g"], sd_b)
    p = par_dgp(med, 1.0)
    Y = Q.dgp_rent(reg, p["efectos"], p["mu"], p["sd_comun"], p["sd_propio"], p["R"], p["nu"], rng, fac_pais=fac)
    if epoca is not None:
        Y = V.escalar_epoca(Y, reg, p["efectos"], p["mu"], epoca[0] - A0, epoca[1])
    infl_obs = infl + ruido[0] * rng.standard_normal(infl.shape)
    brecha_obs = brecha + ruido[1] * rng.standard_normal(brecha.shape)
    return reg, Y, infl, infl_obs, brecha_obs, V.observar_regimen(infl_obs, brecha_obs)


def filas(Y, infl, infl_obs, brecha_obs, reg_obs, años):
    N, T, A = Y.shape
    ok = np.ones((N, T, A), bool)
    ok[:, años < 1972, 4] = False
    return V.filas_v3(reg_obs, Y, infl, infl_obs, brecha_obs, NUCLEO, años, None, ok)


def resumir(v: list[dict]) -> dict:
    o = {"R": len(v)}
    for m in ("S5", "Sb", "S_raros", "S5_cerca", "ancho_bolsa"):
        x = np.array([r[m] for r in v], float)
        o[m] = {"media": round(float(np.nanmean(x)), 4), "banda_2.5_97.5": np.nanpercentile(x, [2.5, 97.5]).round(4).tolist()}
    o["S_activo_media"] = np.nanmean(np.array([r["S_activo"] for r in v], float), 0).round(4).tolist()
    b = np.array([r["infl5"]["bss"] for r in v])
    o["infl5"] = {"bss_media": round(float(np.mean(b)), 4), "bss_banda": np.percentile(b, [2.5, 97.5]).round(4).tolist(),
                  "potencia_p05": round(float(np.mean([r["infl5"]["p"] < 0.05 for r in v])), 3)}
    for k in ("brier", "brier_cerca", "p_media_cerca", "frec_cerca"):
        o["infl5"][k] = round(float(np.nanmean([r["infl5"][k] for r in v])), 4)
    if "S5_k" in v[0]:
        s5k = np.array([r["S5_k"] for r in v])
        banda = np.percentile(s5k[:, 0], [2.5, 97.5])
        o["puerta"] = {"banda_nula_S5": banda.round(4).tolist(), "S5_k_media": s5k.mean(0).round(4).tolist(),
                       "deteccion": {f"k={k}": round(float(np.mean((s5k[:, i] < banda[0]) | (s5k[:, i] > banda[1]))), 3)
                                     for i, k in enumerate(K_ANCHO)}}
    return o


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    proceso = args[0]
    R = int(args[1]) if len(args) > 1 else 60
    prueba = "--prueba" in sys.argv
    proc = {"prueba": True} if prueba else procedencia()
    t0 = time.time()
    med = json.loads((REPO / "research/int/int11_potencia.json").read_text())["medicion"]
    med2 = json.loads((REPO / "research/int/int11_v2_potencia.json").read_text())["medicion_v2"]
    mb = medir_brecha(D.connect())
    print(mb, flush=True)
    kw = PROCESOS[proceso]
    rng = np.random.default_rng(SEED + int(proceso[1]))
    T = 2020 - A0 + 1
    años = np.arange(A0, A0 + T)
    acc = {(c, d): [] for c in CONFIGS for d in ("dev_loco", "dev_temporal", "bloqueado")}
    for r in range(R):
        reg, Y, infl, io, bo, ro = panel_v3(med, med2, mb["sd_robusta"], T, rng, **kw)
        fs = filas(Y, infl, io, bo, ro, años)
        dev = fs[fs["año"] <= 2004]
        s = SEED + 101 * r
        for c, mk in CONFIGS.items():
            cfg = mk()
            if c in ("v2", "v3") or proceso == "P1":              # LOCO: todas las variantes solo en P1
                acc[(c, "dev_loco")].append(V.estadisticos(V.evaluar_suave(dev, "loco", cfg, 20, 100, s)))
            acc[(c, "dev_temporal")].append(V.estadisticos(V.evaluar_suave(dev, "temporal", cfg, 20, 100, s + 1,
                                                                             corte=1950)))
            ev = V.evaluar_suave(fs, "temporal", cfg, 20, 100, s + 2, corte=2005, k_anchura=K_ANCHO)
            acc[(c, "bloqueado")].append(V.estadisticos(ev))
        print(r + 1, round(time.time() - t0), {f"{c}|{d}": round(v[-1]["S5"], 3) for (c, d), v in acc.items() if v},
              flush=True)
    out = {"procedencia": proc, "proceso": proceso, "def_proceso": kw, "R": R, "semilla": SEED,
           "medicion_brecha": mb, "configs": {c: str(mk()) for c, mk in CONFIGS.items()},
           "res": {f"{c}|{d}": resumir(v) for (c, d), v in acc.items() if v}, "segundos": round(time.time() - t0)}
    if not prueba:
        (REPO / f"research/int/int11_v3_potencia_{proceso}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1, default=float))
    print(json.dumps(out["res"], ensure_ascii=False, default=float)[:3000])


if __name__ == "__main__":
    main()
