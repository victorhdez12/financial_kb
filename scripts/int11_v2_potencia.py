"""INT-11 v2: potencia por SIMULACIÓN de la calibración del motor v2 y del Brier de dos eventos (docs/int/INT11_v2_diseno.md).

Ningún resultado real se cruza con el régimen. Del dato real (≤ 2004, núcleo de 14 países, sin guerras ni hiperinflación)
se mide, POR SEPARADO y sin el régimen:
  Y  factor de dispersión propia de cada país y activo (dt de la desviación frente a la media del año, relativa al panel);
  X  frecuencia de "inflación simple > 5 %" (solo la inflación).
El resto del proceso es el congelado de research/int/int11_potencia.json (latentes, dt común/propia, ν, correlaciones,
efectos plantados δ × Atlas §8).

Tres bloques:
  S1  CALIBRACIÓN de v1 frente a v2 (y variantes) bajo tres procesos nulos: homogéneo (el de v1), heterogéneo (factores
      medidos) y heterogéneo + regímenes raros más dispersos (×1,5, hipotético). Diseños LOCO y temporal (≤ 1949 →
      1950-2004). Cobertura p5-p95 global (S5), bolsa (Sb), regímenes raros; CRPSS; BSS de inflación > 5 %.
  S2  POTENCIA DE LA PUERTA de v2: con los mismos sorteos, intervalos escalados por k (cobertura real ≈ 85 % y 80 %);
      banda nula 2,5-97,5 de S5 y probabilidad de salir de ella. Diseños: LOCO y temporal de desarrollo, bloqueado
      (entrena ≤ 2004, prueba 2005-2020, 14 países) y en vivo 5 / 10 / 20 años.
  S3  BRIER de "inflación > 5 % en los 12 meses" y "bolsa ≤ −20 % en el año" (v2 frente a la frecuencia histórica):
      BSS y potencia del contraste DM (años como conglomerados, unilateral, α = 0,05) en los mismos diseños; con el
      proceso estacionario y con un escenario "tranquilo" después de 2004 (menos inflación; hipotético, no medido).

Uso: .venv/bin/python -m scripts.int11_v2_potencia            (árbol limpio; escribe research/int/int11_v2_potencia.json)
     .venv/bin/python -m scripts.int11_v2_potencia --prueba   (sin puerta, réplicas mínimas; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.intl import data as D
from src.intl import escenarios as E
from src.intl import int6 as S
from src.intl import int11 as Q
from src.intl import panel as P
from src.intl.procedencia import procedencia
from scripts.int11_potencia import NUCLEO, cargar, par_dgp

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_v2_potencia.json"
SEED = 20261031
A0 = 1875                                   # año 0 del panel sintético (la primera fila útil es 1876)
K_ANCHO = (1.0, 0.875, 0.78)                # ≈ 90 %, 85 %, 80 % de cobertura real (normal; se informa la realizada)
CONFIGS = {"v1": dict(), "v2": "v2", "v2_sin_mezcla": dict(k_mezcla=0.0), "v2_sin_suavizado": dict(c_suavizado=0.0)}
FAC_RARO = 1.5


def config(nombre: str) -> E.Config:
    c = CONFIGS[nombre]
    if c == "v2":
        return E.Config.v2()
    if nombre == "v1":
        return E.Config()
    return E.Config.v2(**c)


# ---------------------------------------------------------------- medición (Y y X por separado, sin régimen)
def medir(con) -> dict:
    d = cargar(con)
    fac = np.ones((len(NUCLEO), len(E.ACTIVOS)))
    for j, a in enumerate(E.ACTIVOS):
        m = d["Y"][a].to_numpy()                                  # (N, T) log real, NaN fuera
        n_año = np.isfinite(m).sum(0)
        dev = np.where(n_año >= 3, m - np.nanmean(m, 0), np.nan)
        dev = dev * np.sqrt(np.where(n_año > 1, n_año / np.maximum(n_año - 1, 1), np.nan))
        rms = np.sqrt(np.nanmean(dev ** 2))
        fac[:, j] = np.sqrt(np.nanmean(dev ** 2, 1)) / rms
    a = P.anual(con)
    a = a.loc[a.index.get_level_values(0).isin(NUCLEO)]
    if a.index.get_level_values(1).max() > 2004:
        raise D.FactorCutoffError("panel anual con años > 2004")
    infl = np.expm1(a["inflacion"]).dropna()
    fuera = S.hiper_fuera(infl)
    ok = [(p, t) not in fuera and t not in E.GUERRAS for p, t in infl.index]
    infl = infl[ok]
    return {"factor_pais": {c: fac[i].round(3).tolist() for i, c in enumerate(NUCLEO)},
            "tau_log_factor": np.std(np.log(fac), 0, ddof=1).round(3).tolist(),
            "frecuencia_infl_5": float((infl > 0.05).mean()), "frecuencia_infl_3": float((infl > 0.03).mean()),
            "filas_inflacion": int(len(infl))}


# ---------------------------------------------------------------- proceso sintético v2
def panel_v2(med: dict, med2: dict, T: int, rng, fac=None, fac_raro=1.0, tranquilo_desde=None, desplaz=0.0):
    """reg (N, T), Ylog (N, T, A), infl simple (N, T). tranquilo_desde: índice de año desde el que el latente de la
    inflación se desplaza `desplaz` dt hacia abajo (menos inflación alta; el régimen se recalcula)."""
    N = len(NUCLEO)
    lat = med["latente"]
    reg, zi, zg = Q.dgp_regimenes(N, T, lat, rng, latentes=True)
    if tranquilo_desde is not None:
        zi = zi.copy()
        zi[:, tranquilo_desde:] -= desplaz
        alta = zi > stats.norm.ppf(1 - lat["q_i"])
        baja = zg < stats.norm.ppf(lat["q_g"])
        reg = np.where(baja, np.where(alta, 2, 3), np.where(alta, 1, 0))
    infl = Q.inflacion_desde_latente(zi, lat["q_i"], med2["frecuencia_infl_5"])
    p = par_dgp(med, 1.0)
    Y = Q.dgp_rent(reg, p["efectos"], p["mu"], p["sd_comun"], p["sd_propio"], p["R"], p["nu"], rng, fac_pais=fac,
                   fac_raro=fac_raro)
    return reg, Y, infl


def a_filas(reg, Y, infl, años):
    N, T, A = Y.shape
    ok = np.ones((N, T, A), bool)
    ok[:, años < 1972, 4] = False                                   # oro solo ≥ 1972, como en el panel real
    return Q.filas_sinteticas(reg, Y, NUCLEO, años, None, ok, infl)


def estadisticos(ev: dict, sel: np.ndarray | None = None) -> dict:
    sel = np.ones(len(ev["año"]), bool) if sel is None else sel
    dn = ev["dentro90"][sel]
    fila = np.isfinite(dn).any(1)
    out = {"S5": float(np.mean(np.nanmean(dn[fila], 1))), "Sb": float(np.nanmean(dn[:, 0])),
           "S_activo": np.nanmean(dn, 0).tolist()}
    raro = np.isin(ev["s_prev"][sel], (2, 3))
    out["S_raros"] = float(np.nanmean(dn[raro])) if raro.any() else np.nan
    if "dentro_k" in ev:
        dk = ev["dentro_k"][sel]
        out["S5_k"] = [float(np.mean(np.nanmean(dk[fila, :, k], 1))) for k in range(dk.shape[2])]
        out["Sa_k"] = [np.nanmean(dk[:, :, k], 0).tolist() for k in range(dk.shape[2])]
    c0, c1 = ev["crps0"][sel], ev["crps1"][sel]
    usa = np.isfinite(c0).any(1)
    out["crpss_medio"] = float(np.nanmean(1 - np.nanmean(c1[usa], 0) / np.nanmean(c0[usa], 0)))
    años = ev["año"][sel]
    for nombre, y, p1, p0 in (("infl5", np.expm1(ev["infl"][sel]) > 0.05, ev["p_infl_m1"][sel], ev["p_infl_m0"][sel]),
                              ("caida20", ev["y"][sel, 0] <= -0.20, ev["p_caida_m1"][sel], ev["p_caida_m0"][sel])):
        okb = np.isfinite(p1) & np.isfinite(p0) & (np.isfinite(ev["y"][sel, 0]) if nombre == "caida20" else True)
        y = y[okb].astype(float)
        b1, b0 = (p1[okb] - y) ** 2, (p0[okb] - y) ** 2
        dm = E.dm_conglomerado(b0 - b1, años[okb], lags=2)
        out[nombre] = {"frecuencia": float(y.mean()), "bss": float(1 - b1.mean() / max(b0.mean(), 1e-12)),
                       "p": dm["p_unilateral"], "eventos": int(y.sum()), "n": int(len(y))}
    return out


# ---------------------------------------------------------------- S1: calibración v1 frente a v2
def s1(med, med2, R, rng, fac) -> dict:
    T = 2004 - A0 + 1
    años = np.arange(A0, A0 + T)
    procesos = {"homogeneo": dict(), "heterogeneo": dict(fac=fac), "heterogeneo_raros_x1.5": dict(fac=fac,
                                                                                                 fac_raro=FAC_RARO)}
    out = {}
    for pn, kw in procesos.items():
        acc = {(c, d): [] for c in CONFIGS for d in ("loco", "temporal")}
        for r in range(R):
            reg, Y, infl = panel_v2(med, med2, T, rng, **kw)
            fs = a_filas(reg, Y, infl, años)
            for c in CONFIGS:
                for d in ("loco", "temporal"):
                    ev = Q.evaluar_motor(fs, d, 20, 100, SEED + 11 * r, H=1, corte=1950, cfg=config(c))
                    acc[(c, d)].append(estadisticos(ev))
        out[pn] = {f"{c}|{d}": resumir(v) for (c, d), v in acc.items()}
        print(pn, json.dumps({k: {m: v[m]["media"] for m in ("S5", "Sb", "S_raros", "crpss_medio")}
                              for k, v in out[pn].items()}, indent=0))
    return out


def resumir(v: list[dict]) -> dict:
    o = {}
    for m in ("S5", "Sb", "S_raros", "crpss_medio"):
        x = np.array([r[m] for r in v], float)
        o[m] = {"media": round(float(np.nanmean(x)), 4), "banda_2.5_97.5": np.nanpercentile(x, [2.5, 97.5]).round(4).tolist()}
    o["S_activo_media"] = np.nanmean(np.array([r["S_activo"] for r in v], float), 0).round(4).tolist()
    for ev in ("infl5", "caida20"):
        b = np.array([r[ev]["bss"] for r in v])
        o[ev] = {"bss_media": round(float(np.mean(b)), 4), "bss_banda": np.percentile(b, [2.5, 97.5]).round(4).tolist(),
                 "potencia_p05": round(float(np.mean([r[ev]["p"] < 0.05 for r in v])), 3),
                 "frecuencia": round(float(np.mean([r[ev]["frecuencia"] for r in v])), 4),
                 "eventos_medios": round(float(np.mean([r[ev]["eventos"] for r in v])), 1)}
    return o


# ---------------------------------------------------------------- S2 + S3: puerta y Brier en todos los diseños
def s2s3(med, med2, R, rng, fac) -> dict:
    T = 2024 - A0 + 1
    años = np.arange(A0, A0 + T)
    escenarios = {"estacionario": dict(), "tranquilo": dict(tranquilo_desde=2005 - A0, desplaz=0.81)}
    diseños = {"dev_loco": None, "dev_temporal": None, "bloqueado_2005_2020": (2005, 2020),
               "vivo_5": (2005, 2009), "vivo_10": (2005, 2014), "vivo_20": (2005, 2024)}
    out = {}
    for en, kw in escenarios.items():
        acc = {d: [] for d in diseños}
        for r in range(R):
            reg, Y, infl = panel_v2(med, med2, T, rng, fac=fac, **kw)
            fs = a_filas(reg, Y, infl, años)
            dev = fs[fs["año"] <= 2004]
            if en == "estacionario":
                for d, dis in (("dev_loco", "loco"), ("dev_temporal", "temporal")):
                    ev = Q.evaluar_motor(dev, dis, 20, 100, SEED + 13 * r, H=1, corte=1950, cfg=E.Config.v2(),
                                         k_anchura=K_ANCHO)
                    acc[d].append(estadisticos(ev))
            ev = Q.evaluar_motor(fs, "temporal", 20, 100, SEED + 17 * r, H=1, corte=2005, cfg=E.Config.v2(),
                                 k_anchura=K_ANCHO)
            for d, rango in diseños.items():
                if rango is None:
                    continue
                sel = (ev["año"] >= rango[0]) & (ev["año"] <= rango[1])
                acc[d].append(estadisticos(ev, sel))
        out[en] = {d: potencia_puerta(v) for d, v in acc.items() if v}
        print(en, json.dumps({d: {k: x[k] for k in ("S5_k_media", "deteccion_banda", "infl5", "caida20")}
                              for d, x in out[en].items()}, indent=0, default=float)[:3000])
    return out


def potencia_puerta(v: list[dict]) -> dict:
    s5k = np.array([r["S5_k"] for r in v])                        # (R, 3)
    sak = np.array([r["Sa_k"] for r in v], float)                 # (R, 3, A)
    banda = np.percentile(s5k[:, 0], [2.5, 97.5])
    det = {f"k={k}": round(float(np.mean((s5k[:, i] < banda[0]) | (s5k[:, i] > banda[1]))), 3)
           for i, k in enumerate(K_ANCHO)}
    tol = {f"k={k}|tol_{t}pp": round(float(np.mean(np.nanmax(np.abs(sak[:, i] - 0.90), 1) > t / 100)), 3)
           for i, k in enumerate(K_ANCHO) for t in (3, 5)}
    o = {"R": len(v), "banda_nula_S5": banda.round(4).tolist(), "S5_k_media": s5k.mean(0).round(4).tolist(),
         "deteccion_banda": det, "algun_activo_fuera_de_tolerancia": tol,
         "S_raros_media": round(float(np.nanmean([r["S_raros"] for r in v])), 4)}
    for ev in ("infl5", "caida20"):
        b = np.array([r[ev]["bss"] for r in v])
        o[ev] = {"bss_media": round(float(np.mean(b)), 4), "bss_banda": np.percentile(b, [2.5, 97.5]).round(4).tolist(),
                 "potencia_p05": round(float(np.mean([r[ev]["p"] < 0.05 for r in v])), 3),
                 "frecuencia": round(float(np.mean([r[ev]["frecuencia"] for r in v])), 4),
                 "eventos_medios": round(float(np.mean([r[ev]["eventos"] for r in v])), 1)}
    return o


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    prueba = "--prueba" in sys.argv
    proc = {"prueba": True} if prueba else procedencia()
    R1, R2 = (2, 3) if prueba else (100, 200)
    t0 = time.time()
    med = json.loads((REPO / "research/int/int11_potencia.json").read_text())["medicion"]
    con = D.connect()
    med2 = medir(con)
    print(json.dumps(med2, indent=1))
    fac = np.array([med2["factor_pais"][c] for c in NUCLEO])
    rng = np.random.default_rng(SEED)
    o1 = s1(med, med2, R1, rng, fac)
    o2 = s2s3(med, med2, R2, rng, fac)
    out = {"procedencia": proc, "semilla": SEED, "R_s1": R1, "R_s2": R2, "k_anchura": K_ANCHO, "fac_raro": FAC_RARO,
           "configs": {c: str(config(c)) for c in CONFIGS}, "medicion_v2": med2, "s1_calibracion": o1,
           "s2_s3_puerta_y_brier": o2, "segundos": round(time.time() - t0)}
    if not prueba:
        SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    print("segundos", round(time.time() - t0))


if __name__ == "__main__":
    main()
