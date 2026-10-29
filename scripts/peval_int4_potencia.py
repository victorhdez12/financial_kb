"""P-EVAL-INT4: potencia de la confirmación fuera de muestra (una sola vez) de T1 (entrada en recesión, h = 1) y T2
(salida) de INT-4, congelados con ≤ 2004, en el bloqueado JST (años objetivo 2005-2020). docs/int/PEVAL_INT4_potencia.md
§1 fija ANTES de este script exactamente qué se lee (commit f1b8d15).

Qué lee del bloqueado (y nada más): `jst_{iso}_rgdpmad` (el OBJETIVO: PIB real per cápita) de 18 países, todos los
años, SOLO dentro de `leer_objetivo`, para fechar picos y valles (regla de src/intl/regimes.recesiones_anuales). Ningún
valor del PIB sale de esa función hacia la salida: solo años de pico/valle. Ningún indicador ≥ 2005 (ni su
disponibilidad) se lee nunca; ninguna predicción.

Potencia: (i) fórmula de Hanley-McNeil como scripts/int4_potencia.py (positivos efectivos centrales con efecto de
diseño por año y prudentes = años distintos); (ii) simulación con la ESTRUCTURA REAL de eventos (qué filas son y = 1 y
en qué año) y puntuaciones binormales simuladas para modelo y listón (AUC = Φ(μ/√2), ruido modelo-listón r = 0,5,
componente común por año con ICC ρ), probabilidades calibradas con el intercepto de desarrollo (modelo congelado),
bootstrap por bloques de año (los años se remuestrean con todos sus países: pesos multinomiales por año).

Uso: .venv/bin/python -m scripts.peval_int4_potencia              (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.peval_int4_potencia --sintetico  (sin puerta, sin warehouse: prueba la simulación
                                                                    con eventos inventados; no escribe nada)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts.int4_potencia import icc_anova, mde_auc
from src.intl import data as D
from src.intl import int4 as M
from src.intl import regimes as G
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
PRUEBA = ["AUS", "CAN", "CHE", "IRL"]
T_MIN, T_MAX = 2004, 2019            # orígenes t con año objetivo t + 1 en 2005-2020
Z1 = norm.ppf(0.975) + norm.ppf(0.80)            # 2,80
ZH2 = norm.ppf(1 - 0.025 / 2) + norm.ppf(0.80)   # 3,08 (Holm sobre 2, el primero)
R = 0.5
RHOS = (0.0, 0.3, 0.6)
NSIM, B = 1000, 1000
# desarrollo (research/int/int4_resultado.json y int4_sensibilidad_liston.json): AUC listón → modelo, tasa base del ajuste
DEV = {"T1": {"a0": 0.55, "a1": 0.73, "a1_estrat": 0.75, "pi_dev": 166 / 1090},
       "T2": {"a0": 0.58, "a1": 0.77, "a1_estrat": 0.77, "pi_dev": 163 / 235}}


# ---------------------------------------------------------------- lectura del objetivo (única lectura ≥ 2005)
def leer_objetivo(con, paises: list[str]) -> tuple[pd.DataFrame, dict, dict]:
    """Fecha recesiones con `jst_{iso}_rgdpmad` completo. Devuelve SOLO (recesiones: pais, pico, valle), años con dato
    por país y último año; los valores del PIB no salen de aquí."""
    rec, años, ultimo = [], {}, {}
    for c in paises:
        sid = f"jst_{c.lower()}_rgdpmad"
        df = con.execute("select date, value from obs_latest where series_id = ? and value is not null order by date",
                         [sid]).df()
        s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]).dt.year)
        if s.index.duplicated().any():
            raise SystemExit(f"{sid}: años repetidos")
        r = G.recesiones_anuales(s)[["pico", "valle"]].assign(pais=c)
        rec.append(r)
        años[c] = set(int(a) for a in s.index)
        ultimo[c] = int(s.index.max())
        del s, df
    return pd.concat(rec, ignore_index=True), años, ultimo


def coherencia_dev(rec: pd.DataFrame) -> dict:
    """Compara el fechado con la serie completa con el de desarrollo en los episodios con valle ≤ 2003 (solo ≤ 2004)."""
    dev = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    a = {(r.pais, int(r.pico), int(r.valle)) for r in rec.itertuples() if r.valle <= 2003 and r.pais in set(dev.pais)}
    b = {(r.pais, int(r.pico), int(r.valle)) for r in dev.itertuples() if r.valle <= 2003}
    ult = {(r.pais, int(r.pico), int(r.valle)) for r in dev.itertuples() if r.valle >= 2004}
    ult_full = {(r.pais, int(r.pico), int(r.valle)) for r in rec.itertuples()
                if r.pico <= 2003 and r.valle >= 2004 and r.pais in set(dev.pais)}
    return {"episodios_valle_le_2003_iguales": len(a & b), "solo_completa": sorted(map(list, a - b)),
            "solo_dev": sorted(map(list, b - a)), "dev_valle_2004_truncado": sorted(map(list, ult)),
            "completa_mismos_episodios": sorted(map(list, ult_full))}


# ---------------------------------------------------------------- filas del bloqueado (solo y, t, país)
def filas_bloqueado(rec: pd.DataFrame, años: dict, paises: list[str]) -> dict[str, pd.DataFrame]:
    t1, t2 = [], []
    for c in paises:
        r = rec[rec.pais == c]
        en_rec = {y for x in r.itertuples() for y in range(int(x.pico) + 1, int(x.valle) + 1)}
        entradas = {int(x.pico) + 1 for x in r.itertuples()}
        for t in range(T_MIN, T_MAX + 1):
            if t in años[c] and t + 1 in años[c] and t not in en_rec:
                t1.append({"pais": c, "t": t, "y": int(t + 1 in entradas)})
        for x in r.itertuples():
            for t in range(int(x.pico) + 1, int(x.valle) + 1):
                if T_MIN <= t <= T_MAX and t + 1 in años[c]:
                    t2.append({"pais": c, "t": t, "y": int(t + 1 == int(x.valle) + 1), "pico": int(x.pico)})
    return {"T1": pd.DataFrame(t1), "T2": pd.DataFrame(t2)}


def resumen(f: pd.DataFrame) -> dict:
    pos = f[f.y == 1]
    rho, m, mk = icc_anova(f.y, f.t)
    de = 1 + (mk - 1) * rho
    n1, n0 = len(pos), int((f.y == 0).sum())
    n1c, n0c, n1p = n1 / de, n0 / de, pos.t.nunique()
    mde = {}
    for a0 in (0.50, 0.55, 0.58, 0.60, 0.70):
        mde[f"A0={a0:.2f}"] = {k: {"1_contraste": _r(mde_auc(a0, p1, n0c, Z1)), "holm_2": _r(mde_auc(a0, p1, n0c, ZH2))}
                               for k, p1 in (("central", n1c), ("prudente", n1p))}
    return {"filas": int(len(f)), "eventos": int(n1), "no_eventos": n0, "tasa_base": _r(f.y.mean()),
            "años_distintos_con_evento": int(n1p),
            "eventos_por_año_objetivo": {str(int(t) + 1): int(v) for t, v in pos.groupby("t").size().items()},
            "filas_por_año_objetivo": {str(int(t) + 1): int(v) for t, v in f.groupby("t").size().items()},
            "eventos_por_pais": {c: sorted(int(t) + 1 for t in g.t) for c, g in pos.groupby("pais")},
            "paises_con_evento": int(pos.pais.nunique()),
            "icc_por_año": _r(rho), "m_kish": _r(mk, 2), "efecto_diseño": _r(de, 2),
            "pos_ef_central": _r(n1c, 1), "neg_ef_central": _r(n0c, 1), "pos_ef_prudente": int(n1p),
            "mde_hanley_mcneil": mde}


def _r(x, k=3):
    return None if x is None else round(float(x), k)


# ---------------------------------------------------------------- simulación con la estructura real de eventos
def _auc_w(Mp: np.ndarray, wp: np.ndarray, wn: np.ndarray) -> np.ndarray:
    """AUC con pesos por fila (filas = réplicas): Σ wp_i wn_j M_ij / (Σwp Σwn); M = 1 si s_i > s_j, 0,5 si empate."""
    num = ((wp @ Mp) * wn).sum(1)
    den = wp.sum(1) * wn.sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def _comp(s1: np.ndarray, s0: np.ndarray) -> np.ndarray:
    return (s1[:, None] > s0[None, :]) + 0.5 * (s1[:, None] == s0[None, :])


def simular(f: pd.DataFrame, a0: float, a1: float, rho: float, pi_dev: float, nsim: int = NSIM, nb: int = B,
            semilla: int = 0) -> dict:
    rng = np.random.default_rng(semilla)
    y = f.y.to_numpy(bool)
    años, ti = np.unique(f.t.to_numpy(), return_inverse=True)
    pais = f.pais.to_numpy()
    ny = len(años)
    mismo = (pais[y][:, None] == pais[~y][None, :]).astype(float)       # pares del mismo país (estratificada)
    mu0, mu1 = np.sqrt(2) * norm.ppf(a0), np.sqrt(2) * norm.ppf(a1)
    lpi = np.log(pi_dev / (1 - pi_dev))
    cov = np.array([[1, R], [R, 1]])
    out = {k: [] for k in ("d_auc", "d_auc_lo", "d_auc_lo_h2", "d_est", "d_est_lo", "auc1", "auc1_lo", "d_ll",
                           "d_ll_hi", "pend", "icpt")}
    for _ in range(nsim):
        ea = rng.multivariate_normal([0, 0], cov, ny)[ti]
        ee = rng.multivariate_normal([0, 0], cov, len(y))
        e = np.sqrt(rho) * ea + np.sqrt(1 - rho) * ee
        s1, s0 = mu1 * y + e[:, 0], mu0 * y + e[:, 1]
        p1 = 1 / (1 + np.exp(-(lpi + mu1 * s1 - mu1 ** 2 / 2)))
        p0 = 1 / (1 + np.exp(-(lpi + mu0 * s0 - mu0 ** 2 / 2)))
        M1, M0 = _comp(s1[y], s1[~y]), _comp(s0[y], s0[~y])
        # réplicas por bloques de año: nº de veces que sale cada año (multinomial) → peso de cada fila; réplica 0 = obs.
        cnt = np.vstack([np.ones(ny), rng.multinomial(ny, np.full(ny, 1 / ny), nb)])
        W = cnt[:, ti]
        wp, wn = W[:, y], W[:, ~y]
        A1, A0 = _auc_w(M1, wp, wn), _auc_w(M0, wp, wn)
        # estratificada: Σ sobre pares del mismo país / nº de pares del mismo país
        den_e = ((wp @ mismo) * wn).sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            S1 = ((wp @ (M1 * mismo)) * wn).sum(1) / den_e
            S0 = ((wp @ (M0 * mismo)) * wn).sum(1) / den_e
        ll = lambda p: -(y * np.log(p) + (1 - y) * np.log(1 - p))  # noqa: E731
        L1 = (W * ll(p1)).sum(1) / W.sum(1)
        L0 = (W * ll(p0)).sum(1) / W.sum(1)
        d, ds, dl = A1 - A0, S1 - S0, L1 - L0
        q = lambda v, a: float(np.nanquantile(v[1:], a))  # noqa: E731
        out["d_auc"].append(d[0]); out["d_auc_lo"].append(q(d, 0.025)); out["d_auc_lo_h2"].append(q(d, 0.0125))
        out["d_est"].append(ds[0]); out["d_est_lo"].append(q(ds, 0.025))
        out["auc1"].append(A1[0]); out["auc1_lo"].append(q(A1, 0.025))
        out["d_ll"].append(dl[0]); out["d_ll_hi"].append(q(dl, 0.975))
        c = M.calibracion(y.astype(float), p1)
        out["pend"].append(c["pendiente"]); out["icpt"].append(c["intercepto"])
    o = {k: np.array(v) for k, v in out.items()}
    pend_ok = (o["pend"] >= 0.5) & (o["pend"] <= 1.5)
    crit_a = o["d_auc_lo_h2"] > 0
    return {"a0": a0, "a1": a1, "rho": rho, "nsim": nsim, "B": nb,
            "potencia": {
                "a_dauc_ic95_excluye_0": _r((o["d_auc_lo"] > 0).mean()),
                "a_dauc_ic_excluye_0_holm2": _r(crit_a.mean()),
                "a_estratificada_ic95_excluye_0": _r((o["d_est_lo"] > 0).mean()),
                "b_auc_modelo_ic95_sobre_0.5": _r((o["auc1_lo"] > 0.5).mean()),
                "c_signo_dauc_pos": _r((o["d_auc"] > 0).mean()),
                "d_dlogloss_neg": _r((o["d_ll"] < 0).mean()),
                "d_dlogloss_ic95_bajo_0": _r((o["d_ll_hi"] < 0).mean()),
                "e_pendiente_0.5_1.5": _r(pend_ok.mean()),
                "int4_completo_a_holm2_d_e": _r((crit_a & (o["d_ll"] < 0) & pend_ok).mean())},
            "dauc_mediana": _r(np.median(o["d_auc"])), "dauc_p05_p95": [_r(np.quantile(o["d_auc"], .05)),
                                                                       _r(np.quantile(o["d_auc"], .95))],
            "ancho_ic_mediano": _r(np.median(o["d_auc"] - o["d_auc_lo"]) * 2),
            "pendiente_mediana_p10_p90": [_r(np.median(o["pend"])), _r(np.quantile(o["pend"], .1)),
                                          _r(np.quantile(o["pend"], .9))]}


def mde_sim(f: pd.DataFrame, a0: float, rho: float, pi_dev: float, clave: str, nsim: int) -> dict:
    """Potencia del criterio `clave` en una rejilla de Δ y MDE al 80 % (interpolado)."""
    rej = [d for d in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40) if a0 + d <= 0.97]
    pot = [simular(f, a0, a0 + d, rho, pi_dev, nsim, nsim, semilla=int(d * 100))["potencia"][clave] for d in rej]
    mde = None
    for (d0, p0), (d1, p1) in zip(zip(rej, pot), zip(rej[1:], pot[1:])):
        if p0 < 0.8 <= p1:
            mde = _r(d0 + (0.8 - p0) * (d1 - d0) / (p1 - p0))
            break
    if pot and pot[0] >= 0.8:
        mde = rej[0]
    return {"rejilla_dauc": rej, "potencia": pot, "mde_80": mde}


def escenarios(f: pd.DataFrame, g: str, nsim: int, nb: int) -> dict:
    d = DEV[g]
    efe = {"H0": d["a0"], "mitad": d["a0"] + (d["a1"] - d["a0"]) / 2, "desarrollo": d["a1"],
           "desarrollo_estratificado": d["a1_estrat"]}
    out = {}
    for nom, a1 in efe.items():
        for rho in RHOS:
            out[f"{nom}_rho{rho}"] = simular(f, d["a0"], a1, rho, d["pi_dev"], nsim, nb, semilla=17)
    out["mde_sim_rho0.3_holm2"] = mde_sim(f, d["a0"], 0.3, d["pi_dev"], "a_dauc_ic_excluye_0_holm2", max(nsim // 2, 50))
    out["mde_sim_rho0.3_auc_sobre_0.5"] = mde_sim(f, 0.5, 0.3, d["pi_dev"], "b_auc_modelo_ic95_sobre_0.5",
                                                  max(nsim // 2, 50))
    out["mde_sim_rho0.3_auc_sobre_0.5"]["nota"] = "rejilla en AUC − 0,5 del modelo (no ΔAUC)"
    return out


def sintetico() -> None:
    rng = np.random.default_rng(1)
    f = pd.DataFrame([{"pais": c, "t": t, "y": int(rng.random() < (0.8 if t in (2007, 2008, 2019) else 0.05))}
                      for c in NUCLEO for t in range(T_MIN, T_MAX + 1)])
    print(resumen(f)["eventos"], resumen(f)["mde_hanley_mcneil"]["A0=0.55"])
    for a1 in (0.55, 0.73):
        print(simular(f, 0.55, a1, 0.3, 0.15, 100, 200))


def main() -> None:
    if "--sintetico" in sys.argv:
        return sintetico()
    proc = procedencia(exigir_limpio=True)
    con = D.connect()
    rec, años, ultimo = leer_objetivo(con, NUCLEO + PRUEBA)
    con.close()
    res: dict = {"procedencia": proc, "doc": "docs/int/PEVAL_INT4_potencia.md",
                 "leido_del_bloqueado": "solo jst_{iso}_rgdpmad (objetivo), 18 países; ningún indicador",
                 "supuestos": {"indicadores_completos_2005_2020": True, "r_modelo_liston": R, "rhos": list(RHOS),
                               "z_1": _r(Z1), "z_holm2": _r(ZH2), "nsim": NSIM, "B": B, "desarrollo": DEV},
                 "ultimo_año_rgdpmad": ultimo, "coherencia_fechado_dev": coherencia_dev(rec),
                 "recesiones_bloqueado": {c: [[int(x.pico), int(x.valle)] for x in rec[rec.pais == c].itertuples()
                                              if x.valle >= 2004] for c in NUCLEO + PRUEBA}}
    muestras = {}
    for nom, paises in (("nucleo", NUCLEO), ("nucleo_AUS_CHE", NUCLEO + ["AUS", "CHE"])):
        fb = filas_bloqueado(rec, años, paises)
        for g in ("T1", "T2"):
            muestras[(nom, g, "con_2020")] = fb[g]
            muestras[(nom, g, "sin_2020")] = fb[g][fb[g].t + 1 <= 2019].reset_index(drop=True)
    res["recuentos"] = {f"{n}|{g}|{s}": resumen(f) for (n, g, s), f in muestras.items() if len(f) and f.y.sum()}
    res["simulacion"] = {}
    for (n, g, s), f in muestras.items():
        if f.y.sum() < 2 or (f.y == 0).sum() < 2:
            res["simulacion"][f"{n}|{g}|{s}"] = {"nota": "menos de 2 eventos o no eventos: sin evaluación posible"}
            continue
        nsim = NSIM if n == "nucleo" else NSIM // 4
        res["simulacion"][f"{n}|{g}|{s}"] = escenarios(f, g, nsim, B if n == "nucleo" else B // 2)
        print("hecho", n, g, s, flush=True)
    (REPO / "research" / "int" / "peval_int4_potencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for k, v in res["recuentos"].items():
        print(k, v["filas"], v["eventos"], v["años_distintos_con_evento"], v["eventos_por_año_objetivo"])


if __name__ == "__main__":
    main()
