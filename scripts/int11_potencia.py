"""INT-11: potencia de la evaluación de DISTRIBUCIONES (CRPS y cobertura) del motor de escenarios. Sin contraste.

Qué mide del dato real (≤ 2004, núcleo de 14 países, sin guerras ni hiperinflación), SIEMPRE POR SEPARADO:
  X  régimen operable (Atlas §8): frecuencia, persistencia y concordancia entre países de "inflación > 3 %" y de
     "brecha < 0"; matriz de transición agregada del panel (descriptiva, solo X);
  Y  por activo y SIN el régimen: media, dispersión común (entre años) y propia (dentro del año), colas (curtosis →
     grados de libertad de la t) y correlaciones entre activos; y la DISPONIBILIDAD de filas (qué país-años existen).
Nunca junta el régimen real con la rentabilidad real. Los efectos del régimen se PLANTAN: δ × src/intl/int11.EFECTOS_REF.

Uso: .venv/bin/python -m scripts.int11_potencia            (árbol limpio; escribe research/int/int11_potencia.json)
     .venv/bin/python -m scripts.int11_potencia --prueba   (sin puerta, réplicas reducidas; no escribe nada)
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
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
A0, A1, CORTE = 1876, 2004, 1950
AÑOS = np.arange(A0, A1 + 1)
COL = {"bolsa": "eq_tr_real", "bonos": "bond_tr_real", "letras": "bill_rate_real", "vivienda": "housing_tr_real"}
DELTAS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]
ALFA = 0.05 / 3                      # Holm con 3 contrastes, peor caso, unilateral
SEED = 20261030


# ---------------------------------------------------------------- medición (X y Y por separado)
def cargar(con) -> dict:
    a = P.anual(con)
    if a.index.get_level_values(1).max() > 2004:
        raise D.FactorCutoffError("panel anual con años > 2004")
    a = a.loc[a.index.get_level_values(0).isin(NUCLEO)]
    infl_simple = np.expm1(a["inflacion"])
    fuera = S.hiper_fuera(infl_simple.dropna())
    excl = lambda p, t: t in E.GUERRAS or (p, t) in fuera  # noqa: E731
    # ---- X: régimen operable
    x = E.estados_operables(a.reset_index()[["pais", "año", "inflacion", "rgdpmad"]])
    x = x[~x.apply(lambda r: excl(r["pais"], int(r["año"])), axis=1)]
    w = lambda col: x.pivot(index="pais", columns="año", values=col).reindex(index=NUCLEO, columns=AÑOS)  # noqa: E731
    reg = w("regimen").where(lambda d: d >= 0)
    ia = ((w("inflacion") > E.UMBRAL_INFL).astype(float)).where(reg.notna())
    gb = ((w("brecha") < 0).astype(float)).where(reg.notna())
    # ---- Y: rentabilidades reales (log), sin el régimen
    oro = A3.oro_panel(con, NUCLEO)
    oro = oro[oro["año"] >= 1972]
    y = {k: np.log1p(a[c]).unstack(0) for k, c in COL.items()}
    y["oro"] = np.log1p(oro.pivot(index="año", columns="pais", values="oro_real_local"))
    Y = {}
    for k, v in y.items():
        v = v.reindex(index=AÑOS, columns=NUCLEO).T
        m = pd.DataFrame([[excl(p, t) for t in AÑOS] for p in NUCLEO], index=NUCLEO, columns=AÑOS)
        Y[k] = v.where(~m)
    xt = E.estados_operables(a.reset_index()[["pais", "año", "inflacion", "rgdpmad"]], eje="tendencia")
    xt = xt[~xt.apply(lambda r: excl(r["pais"], int(r["año"])), axis=1)]
    reg_t = xt.pivot(index="pais", columns="año", values="regimen").reindex(index=NUCLEO, columns=AÑOS).where(
        lambda d: d >= 0)
    gb_t = ((xt.pivot(index="pais", columns="año", values="brecha").reindex(index=NUCLEO, columns=AÑOS) < 0)
            .astype(float)).where(reg_t.notna())
    return {"reg": reg, "ia": ia, "gb": gb, "Y": Y, "reg_tendencia": reg_t, "gb_tendencia": gb_t}


def props_y(Y: dict) -> dict:
    out, res = {}, {}
    for k, v in Y.items():
        m = v.to_numpy()
        mu_año = np.nanmean(m, 0)
        n_año = np.isfinite(m).sum(0)
        ok = n_año >= 3
        dentro = np.nanvar(m[:, ok], 0, ddof=1)
        var_comun = max(np.nanvar(mu_año[ok], ddof=1) - np.nanmean(dentro / n_año[ok]), 0)
        r = (m - mu_año)[:, ok]
        z = r[np.isfinite(r)]
        kurt = float(((z - z.mean()) ** 4).mean() / z.var() ** 2 - 3)
        out[k] = {"media": float(np.nanmean(m)), "sd_comun": float(np.sqrt(var_comun)),
                  "sd_propio": float(np.sqrt(np.nanmean(dentro))), "curtosis_exceso": kurt,
                  "nu": float(np.clip(4 + 6 / max(kurt, 0.2), 4.5, 30)), "filas": int(np.isfinite(m).sum()),
                  "años_con_3": int(ok.sum())}
        res[k] = (m - mu_año).ravel()
    R = pd.DataFrame(res).corr(min_periods=100).fillna(0).to_numpy()
    v, U = np.linalg.eigh(R)
    R = U @ np.diag(np.clip(v, 1e-3, None)) @ U.T
    d = np.sqrt(np.diag(R))
    return {"activos": out, "R": (R / np.outer(d, d)).round(3).tolist()}


def transiciones(reg: pd.DataFrame) -> dict:
    m = reg.to_numpy()
    n = np.zeros((E.K, E.K))
    ok = np.isfinite(m[:, 1:]) & np.isfinite(m[:, :-1])
    np.add.at(n, (m[:, :-1][ok].astype(int), m[:, 1:][ok].astype(int)), 1)
    freq = np.array([(m == i).sum() for i in range(E.K)]) / np.isfinite(m).sum()
    return {"recuentos": n.astype(int).tolist(), "P": (n / n.sum(1, keepdims=True)).round(3).tolist(),
            "frecuencias": freq.round(3).tolist(), "persistencia_media": float(np.trace(n) / n.sum())}


# ---------------------------------------------------------------- simulación
def par_dgp(med: dict, delta: float) -> dict:
    act = med["y"]["activos"]
    ks = list(E.ACTIVOS)
    return {"efectos": delta * Q.EFECTOS_REF, "mu": np.array([act[k]["media"] for k in ks]),
            "sd_comun": np.array([act[k]["sd_comun"] for k in ks]),
            "sd_propio": np.array([act[k]["sd_propio"] for k in ks]), "R": np.array(med["y"]["R"]),
            "nu": float(np.median([act[k]["nu"] for k in ks]))}


def simular_panel(med: dict, delta: float, N: int, T: int, mascara: np.ndarray | None, rng) -> tuple:
    reg = Q.dgp_regimenes(N, T, med["latente"], rng)
    p = par_dgp(med, delta)
    Y = Q.dgp_rent(reg, p["efectos"], p["mu"], p["sd_comun"], p["sd_propio"], p["R"], p["nu"], rng)
    if mascara is not None:
        Y = np.where(mascara[:N, :T], Y, np.nan)
    return reg, Y


def potencia_crps(med: dict, mascara: np.ndarray, nsim: int, rng) -> dict:
    T = len(AÑOS)
    tc = CORTE - A0
    diseños = {"C1_loco_h1": dict(diseño="loco", h=1), "C1t_temporal_h1": dict(diseño="temporal", h=1, corte=tc),
               "C2_loco_h5": dict(diseño="loco", h=5), "C2t_temporal_h5": dict(diseño="temporal", h=5, corte=tc)}
    bloq = {"B_bloqueado_h1": 1, "B_bloqueado_h5": 5}
    out = {k: {} for k in [*diseños, *bloq]}
    for delta in DELTAS:
        acc = {k: {"rech": [], "rech_bolsa": [], "crpss": [], "crpss_activo": []} for k in out}
        for _ in range(nsim):
            reg, Y = simular_panel(med, delta, 14, T, mascara, rng)
            for k, kw in diseños.items():
                r = Q.evaluar(Y, reg, **kw)
                t = E.dm_conglomerado(r["d"], r["año"], lags=0 if kw["h"] > 1 else 2)
                tb = E.dm_conglomerado(r["d_activo"][:, 0], r["año"], lags=0 if kw["h"] > 1 else 2)
                acc[k]["rech"].append(t["p_unilateral"] < ALFA)
                acc[k]["rech_bolsa"].append(tb["p_unilateral"] < ALFA)
                acc[k]["crpss"].append(r["crpss_medio"])
                acc[k]["crpss_activo"].append(r["crpss"])
            # periodo bloqueado: 18 países, 16 años de prueba (2005-2020), entrena con todo lo anterior
            reg2, Y2 = simular_panel(med, delta, 18, T + 16, None, rng)
            Y2[:14, :T] = np.where(mascara, Y2[:14, :T], np.nan)
            for k, h in bloq.items():
                r = Q.evaluar(Y2, reg2, "temporal", h=h, corte=T)
                if len(r["d"]) < 3:
                    continue
                t = E.dm_conglomerado(r["d"], r["año"], lags=0 if h > 1 else 2)
                tb = E.dm_conglomerado(r["d_activo"][:, 0], r["año"], lags=0 if h > 1 else 2)
                acc[k]["rech"].append(t["p_unilateral"] < ALFA)
                acc[k]["rech_bolsa"].append(tb["p_unilateral"] < ALFA)
                acc[k]["crpss"].append(r["crpss_medio"])
                acc[k]["crpss_activo"].append(r["crpss"])
        for k in out:
            out[k][str(delta)] = {"potencia": float(np.mean(acc[k]["rech"])),
                                  "potencia_solo_bolsa": float(np.mean(acc[k]["rech_bolsa"])),
                                  "crpss_medio_%": round(100 * float(np.mean(acc[k]["crpss"])), 3),
                                  "crpss_activo_%": dict(zip(E.ACTIVOS, np.round(
                                      100 * np.nanmean(acc[k]["crpss_activo"], 0), 3).tolist()))}
    for k in out:
        pot = [out[k][str(d)]["potencia"] for d in DELTAS]
        out[k]["delta_80"] = _cruce(DELTAS, pot, 0.8)
        out[k]["delta_80_solo_bolsa"] = _cruce(DELTAS, [out[k][str(d)]["potencia_solo_bolsa"] for d in DELTAS], 0.8)
        out[k]["crpss_en_delta_80_%"] = _interp(DELTAS, [out[k][str(d)]["crpss_medio_%"] for d in DELTAS],
                                               out[k]["delta_80"])
    return out


def _cruce(x, y, nivel):
    for i in range(1, len(x)):
        if y[i - 1] < nivel <= y[i]:
            return round(x[i - 1] + (nivel - y[i - 1]) * (x[i] - x[i - 1]) / (y[i] - y[i - 1]), 3)
    return None if y[-1] < nivel else x[0]


def _interp(x, y, x0):
    return None if x0 is None else round(float(np.interp(x0, x, y)), 3)


def potencia_cobertura(med: dict, mascara: np.ndarray, nsim: int, rng) -> dict:
    """Intervalo nominal p5-p95 (90 %). k se calibra para que la cobertura REAL sea 0,90 / 0,85 / 0,80 en un piloto
    grande; después: tasa de rechazo de H0 "cobertura = 0,90" (bilateral, α = 0,05, años como conglomerados)."""
    T = len(AÑOS)
    rng_p = np.random.default_rng(1)
    def cob(k, h):  # noqa: E301
        vals = []
        for _ in range(40):
            reg, Y = simular_panel(med, 1.0, 18, T + 40, None, rng_p)
            c = Q.cobertura_sim(Y, reg, k, 0.05, 0.95, corte=T, prueba=(T, T + 40), h=h)
            vals.append(np.nanmean(c["dentro"]))
        return float(np.mean(vals))
    ks = {}
    for h in (1, 5):
        rej = np.linspace(0.4, 1.3, 19)
        cs = np.array([cob(k, h) for k in rej])
        ks[h] = {str(obj): float(np.interp(obj, cs, rej)) for obj in (0.80, 0.85, 0.90)}
        ks[h]["cobertura_k1"] = float(np.interp(1.0, rej, cs))
    diseños = {"1950_2004_14p": (14, CORTE - A0, T), "bloqueado_2005_2020_18p": (18, T, T + 16),
               "vivo_5a_18p": (18, T, T + 5), "vivo_10a_18p": (18, T, T + 10), "vivo_20a_18p": (18, T, T + 20)}
    out = {"k": ks}
    for h in (1, 5):
        for nombre, (N, c, fin) in diseños.items():
            if h == 5 and fin - c < 10:
                continue
            fila, stats_ = {}, {}
            for obj in ("0.9", "0.85", "0.8"):
                rech_b, rech_t, cb, ct = [], [], [], []
                for _ in range(nsim):
                    reg, Y = simular_panel(med, 1.0, N, fin, None, rng)
                    Y[:min(N, 14), :T] = np.where(mascara[:min(N, 14), :min(fin, T)], Y[:min(N, 14), :T], np.nan)
                    r = Q.cobertura_sim(Y, reg, ks[h][obj], 0.05, 0.95, corte=c, prueba=(c, fin), h=h)
                    d = r["dentro"]
                    if np.isfinite(d[:, 0]).sum() < 5:
                        continue
                    lg = 0 if h > 1 else 2
                    tb = E.cobertura_contraste(d[:, 0][np.isfinite(d[:, 0])], r["año"][np.isfinite(d[:, 0])], 0.90, lg)
                    tt = E.cobertura_contraste(np.nanmean(d, 1), r["año"], 0.90, lg)
                    rech_b.append(tb["p_bilateral"] < 0.05)
                    rech_t.append(tt["p_bilateral"] < 0.05)
                    cb.append(tb["cobertura"])
                    ct.append(tt["cobertura"])
                stats_[obj] = (np.array(cb), np.array(ct))
                fila[obj] = {"rechazo_t_bolsa": float(np.mean(rech_b)), "rechazo_t_5_activos": float(np.mean(rech_t)),
                             "cobertura_media_5": round(float(np.mean(ct)), 3),
                             "cobertura_p5_p95_entre_réplicas_5": np.round(np.percentile(ct, [5, 95]), 3).tolist(),
                             "cobertura_p5_p95_entre_réplicas_bolsa": np.round(np.percentile(cb, [5, 95]), 3).tolist()}
            # valor crítico SIMULADO bajo H0 (las réplicas con cobertura real 0,90): corrige el tamaño del t de años
            for obj in ("0.9", "0.85", "0.8"):
                for j, nom in ((0, "bolsa"), (1, "5_activos")):
                    nulo = stats_["0.9"][j]
                    lo, hi = np.percentile(nulo, [2.5, 97.5])
                    x = stats_[obj][j]
                    fila[obj][f"rechazo_simulado_{nom}"] = float(np.mean((x < lo) | (x > hi)))
            out[f"h{h}_{nombre}"] = fila
    return out


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    prueba = "--prueba" in sys.argv
    proc = {"prueba": True} if prueba else procedencia()
    nsim = 20 if prueba else 300
    nsim_cob = 20 if prueba else 300
    rng = np.random.default_rng(SEED)
    t0 = time.time()
    con = D.connect()
    d = cargar(con)
    med = {"x": {"inflacion_alta": Q.indicador_props(d["ia"].to_numpy()),
                 "brecha_negativa": Q.indicador_props(d["gb"].to_numpy()),
                 "transiciones": transiciones(d["reg"]),
                 "alternativa_eje_tendencia": {"brecha_negativa": Q.indicador_props(d["gb_tendencia"].to_numpy()),
                                               "transiciones": transiciones(d["reg_tendencia"])}},
           "y": props_y(d["Y"])}
    li = Q.calibrar_latente(med["x"]["inflacion_alta"]["frecuencia"], med["x"]["inflacion_alta"]["persistencia"],
                            med["x"]["inflacion_alta"]["concordancia"], semilla=1)
    lg = Q.calibrar_latente(med["x"]["brecha_negativa"]["frecuencia"], med["x"]["brecha_negativa"]["persistencia"],
                            med["x"]["brecha_negativa"]["concordancia"], semilla=2)
    med["latente"] = {"q_i": med["x"]["inflacion_alta"]["frecuencia"], "a_i": li["a"], "rho_i": li["rho"],
                      "q_g": med["x"]["brecha_negativa"]["frecuencia"], "a_g": lg["a"], "rho_g": lg["rho"],
                      "ajuste_i": li, "ajuste_g": lg}
    # disponibilidad: país-año con dato en algún activo y régimen definido (sin guerras ni hiperinflación)
    disp = np.stack([d["Y"][k].to_numpy() for k in E.ACTIVOS], -1)
    mascara = np.isfinite(disp) & d["reg"].notna().to_numpy()[:, :, None]
    med["filas_disponibles"] = {k: int(mascara[:, :, i].sum()) for i, k in enumerate(E.ACTIVOS)}
    print(json.dumps(med, ensure_ascii=False, indent=1, default=float)[:3000])
    crps = potencia_crps(med, mascara, nsim, rng)
    print(json.dumps(crps, ensure_ascii=False, indent=1)[:4000])
    cob = potencia_cobertura(med, mascara, nsim_cob, rng)
    print(json.dumps(cob, ensure_ascii=False, indent=1))
    out = {"procedencia": proc, "semilla": SEED, "nsim": nsim, "alfa_crps": ALFA, "deltas": DELTAS,
           "efectos_ref": Q.EFECTOS_REF.tolist(), "medicion": med, "crps": crps, "cobertura": cob,
           "segundos": round(time.time() - t0)}
    if not prueba:
        (REPO / "research/int/int11_potencia.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1, default=float))
    print("segundos", round(time.time() - t0))


if __name__ == "__main__":
    main()
