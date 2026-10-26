"""INT-3b / INT-3c: cálculo de potencia ANTES de prerregistrar (docs/int/INT3b_prerregistro_v0.md, §6).

Solo usa:
 (i) las etiquetas de régimen de INT-1 (núcleo de 14 países, sin años truncados; ≤ 1999 por la ventana): recuentos de
     años y país-años por estado, cuota mundial de países en cada estado y su persistencia (AR(1) del regresor);
 (ii) estadísticos INCONDICIONALES de cada activo o componente (desviación típica, AR(1), correlación media entre
     países), calculados sobre los años de la muestra sin mirar en qué régimen cae cada año.
NO cruza ningún activo con ningún régimen (ni real ni desplazado): las simulaciones usan rentabilidades SINTÉTICAS con la
varianza y la autocorrelación del activo y la trayectoria real del régimen.

Dos MDE (80 % de potencia, bilateral, umbral de Holm en el peor caso α/m):
 - analítico: serie temporal  MDE = (z_{1−α/2m} + z_{0,8})·σ·√(1/n1 + 1/n0)·√((1+ρx·ρy)/(1−ρx·ρy));
              panel           como INT-2 (n efectivo por agrupación en años con Kish y corrección AR(1)).
 - simulado (solo series mundiales y de EE. UU./R. U. por separado): AR(1) gaussiano y t(4); contraste del
   prerregistro: t de Newey-West (= Driscoll-Kraay con una sola unidad) calibrada con el placebo desplazado
   (φ = máx(1, dt de las t placebo), p = 2·P(t_{T−1} > |t|/φ)), y además |t| por encima del percentil 95 de las
   |t| placebo y el mismo signo en 1950-1999.
Uso: .venv/bin/python -m scripts.int3b_potencia
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.intl import activos3b as A
from src.intl import data as D
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
INFL_ALTA = {"sobrecalentamiento", "estanflacion"}
DESFASE_MIN = 6
HIPER = 0.5
SEED = 20261026
NSIM = 400
FAMILIAS = {"INT3b": 4, "INT3c": 4, "conjunta": 8}   # v2: C2 y C6 pasan a descriptivas (MDE ≈ 8 pp, ver v1)


def z_mde(m: int) -> float:
    return float(stats.norm.ppf(1 - 0.05 / (2 * m)) + stats.norm.ppf(0.8))


# ------------------------------------------------------------------ regímenes (sin activos)
def estados() -> tuple[pd.DataFrame, pd.DataFrame]:
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    et = et[et.pais.isin(NUCLEO + ["AUS", "CHE"]) & et.cuadrante.notna() & ~et.truncada.fillna(True).astype(bool)]
    et = et.reset_index(drop=True)
    en_rec = {(r.pais, y) for _, r in rec.iterrows() for y in range(int(r.pico) + 1, int(r.valle) + 1)}
    pa = pd.DataFrame({"pais": et.pais.values, "año": et.año.values.astype(int),
                       "infl_alta": et.cuadrante.isin(INFL_ALTA).values.astype(float),
                       "estanflacion": (et.cuadrante == "estanflacion").values.astype(float),
                       "crec_bajo": (et.cuadrante == "crecimiento_bajo").values.astype(float),
                       "recesion": np.array([(p, y) in en_rec for p, y in zip(et.pais, et.año)], dtype=float)})
    mundo = pa[pa.pais.isin(NUCLEO)].groupby("año")[["infl_alta", "estanflacion", "crec_bajo", "recesion"]].mean()
    return pa, mundo


# ------------------------------------------------------------------ inferencia (igual que la corrida prevista)
def nw_t(y: np.ndarray, X: np.ndarray, L: int) -> np.ndarray:
    """t de Newey-West de la pendiente para varias columnas de regresor a la vez (y: T, X: T×K)."""
    Xc = X - X.mean(0)
    yc = y - y.mean()
    sxx = (Xc ** 2).sum(0)
    b = (Xc * yc[:, None]).sum(0) / sxx
    e = yc[:, None] - Xc * b
    u = Xc * e
    S = (u ** 2).sum(0)
    for l in range(1, L + 1):
        S = S + 2 * (1 - l / (L + 1)) * (u[l:] * u[:-l]).sum(0)
    T = len(y)
    se = np.sqrt(S * T / (T - 2)) / sxx
    return b / se


def lags_nw(T: int) -> int:
    return int(np.floor(4 * (T / 100) ** (2 / 9)))


def placebo_matriz(x: np.ndarray) -> np.ndarray:
    T = len(x)
    return np.column_stack([np.roll(x, k) for k in range(DESFASE_MIN, T - DESFASE_MIN + 1)])


def potencia_sim(x: np.ndarray, años: np.ndarray, sd: float, ar1: float, efectos: np.ndarray, alfa: float,
                 colas: str, rng: np.random.Generator) -> dict:
    """Potencia del contraste prerregistrado con rentabilidades sintéticas y = μ + δ·x + AR(1)."""
    T = len(x)
    L = lags_nw(T)
    P = placebo_matriz(x)
    sub = años >= 1950
    acierto = {"calibrado": np.zeros(len(efectos)), "completo": np.zeros(len(efectos))}
    for _ in range(NSIM):
        if colas == "t4":
            eps = rng.standard_t(4, T) / np.sqrt(2.0)
        else:
            eps = rng.standard_normal(T)
        u = np.empty(T)
        u[0] = eps[0]
        for t in range(1, T):
            u[t] = ar1 * u[t - 1] + np.sqrt(1 - ar1 ** 2) * eps[t]
        u *= sd
        tp = nw_t(u, P, L)                                  # placebo con δ = 0 (se recalcula para cada δ > 0)
        for j, d in enumerate(efectos):
            y = u + d * x
            t0 = nw_t(y, x[:, None], L)[0]
            tpl = nw_t(y, P, L) if d != 0 else tp
            phi = max(1.0, float(np.std(tpl, ddof=1)))
            p = 2 * stats.t.sf(abs(t0) / phi, T - 1)
            ok = (p <= alfa) and t0 > 0
            acierto["calibrado"][j] += ok
            if ok and abs(t0) > np.quantile(np.abs(tpl), 0.95):
                xs, ys = x[sub], y[sub]
                b_sub = np.cov(xs, ys)[0, 1] / np.var(xs, ddof=1) if np.var(xs) > 0 else np.nan
                acierto["completo"][j] += b_sub > 0
    return {k: (v / NSIM).round(3).tolist() for k, v in acierto.items()}


def mde_de_curva(efectos: np.ndarray, pot: list[float]) -> float | None:
    pot = np.asarray(pot)
    i = np.where(pot >= 0.8)[0]
    if not len(i):
        return None
    i = i[0]
    if i == 0:
        return float(efectos[0])
    e0, e1, p0, p1 = efectos[i - 1], efectos[i], pot[i - 1], pot[i]
    return float(e0 + (0.8 - p0) * (e1 - e0) / (p1 - p0))


# ------------------------------------------------------------------ estadísticos incondicionales de activos
def st_serie(s: pd.Series) -> dict:
    s = s.dropna()
    return {"n": int(s.size), "desde": int(s.index.min()), "hasta": int(s.index.max()), "sd": float(s.std()),
            "ar1": float(s.autocorr(1))}


def st_panel(f: pd.DataFrame, col: str) -> dict:
    x = f.dropna(subset=[col])
    ancho = x.pivot(index="año", columns="pais", values=col)
    pares = [ancho[[i, j]].dropna().corr().iloc[0, 1] for i, j in itertools.combinations(ancho.columns, 2)
             if ancho[[i, j]].dropna().shape[0] >= 20]
    ar1 = float(np.nanmean([ancho[c].dropna().autocorr(1) for c in ancho.columns if ancho[c].dropna().size > 20]))
    return {"n": int(len(x)), "paises": int(ancho.shape[1]), "sd": float(x[col].std()),
            "rho_paises": float(np.nanmean(pares)) if pares else 0.0, "ar1": ar1}


def mde_panel(est: pd.DataFrame, disp: set, st: dict, m: int, penal: float = 1.0) -> dict:
    """MDE de INT-2 (Kish + AR(1)) para un estado país-año, sobre los país-años con dato del activo."""
    g1 = [(p, y) for p, y, v in zip(est.pais, est.año, est.v) if v == 1 and (p, y) in disp]
    g0 = [(p, y) for p, y, v in zip(est.pais, est.año, est.v) if v == 0 and (p, y) in disp]

    def n_ef(g):
        if not g:
            return np.nan
        c = pd.Series([y for _, y in g]).value_counts()
        m_est = c.mean() * (1 + (c.std(ddof=0) / c.mean()) ** 2)
        return len(g) / (1 + (m_est - 1) * st["rho_paises"]) * (1 - st["ar1"]) / (1 + st["ar1"])

    n1, n0 = n_ef(g1), n_ef(g0)
    d = z_mde(m) * st["sd"] * np.sqrt(1 / n1 + 1 / n0) * penal
    return {"pais_años_estado": len(g1), "n_ef_estado": round(float(n1), 1), "mde_pp": round(100 * float(d), 1)}


def mde_ts(x: np.ndarray, st: dict, m: int) -> dict:
    rho_x = float(pd.Series(x).autocorr(1))
    vif = (1 + rho_x * st["ar1"]) / (1 - rho_x * st["ar1"])
    binario = set(np.unique(x)) <= {0.0, 1.0}
    if binario:
        n1, n0 = x.sum(), (1 - x).sum()
        d = z_mde(m) * st["sd"] * np.sqrt(1 / n1 + 1 / n0) * np.sqrt(vif)
        return {"años_estado": int(n1), "años_resto": int(n0), "ar1_estado": round(rho_x, 2), "mde_pp": round(100 * d, 1)}
    d = z_mde(m) * st["sd"] / (np.sqrt(len(x)) * x.std()) * np.sqrt(vif)
    return {"media_cuota": round(float(x.mean()), 3), "dt_cuota": round(float(x.std()), 3), "ar1_cuota": round(rho_x, 2),
            "mde_pp_0a100": round(100 * d, 1), "mde_pp_por_dt_cuota": round(100 * d * x.std(), 1)}


def main() -> None:
    proc = procedencia()
    rng = np.random.default_rng(SEED)
    pa, mundo = estados()
    con = D.connect()
    mu = A.mundial(con)
    oro = A.oro_panel(con, NUCLEO)
    cre = A.credito(con)
    dc = A.descomp(con, NUCLEO)
    con.close()
    oro = oro[~(oro.inflacion > HIPER)].assign(oro_log=lambda f: np.log1p(f.oro_real_local))
    dc = dc[~(dc.inflacion > HIPER)].copy()
    dc["viv_menos_bolsa_capital"] = dc.viv_precio_real - (dc.eq_div_real + dc.eq_valoracion)
    res: dict = {"procedencia": proc, "nota": "potencia sin cruzar activos con regímenes; rentabilidades sintéticas",
                 "z_mde": {k: round(z_mde(m), 3) for k, m in FAMILIAS.items()}}

    # --- recuentos de régimen (solo etiquetas)
    años = mundo.index.to_numpy()
    res["regimen"] = {
        "años_con_etiqueta": [int(años.min()), int(años.max())],
        "cuota_mundial": {c: {"media": round(float(mundo[c].mean()), 3), "dt": round(float(mundo[c].std()), 3),
                              "ar1": round(float(mundo[c].autocorr(1)), 2),
                              "años_mayoria_1877": int((mundo.loc[mundo.index >= 1877, c] >= 0.5).sum()),
                              "años_mayoria_1928": int((mundo.loc[mundo.index >= 1928, c] >= 0.5).sum()),
                              "años_mayoria_1950": int((mundo.loc[mundo.index >= 1950, c] >= 0.5).sum())}
                          for c in mundo.columns},
        "usa_gbr": {p: {c: int(pa[(pa.pais == p) & (pa.año >= d0)][c].sum()) for c in ("infl_alta", "estanflacion",
                                                                                     "crec_bajo", "recesion")}
                    | {"años": int(((pa.pais == p) & (pa.año >= d0)).sum()), "desde": d0}
                    for p, d0 in (("USA", 1928), ("GBR", 1877))},
    }

    # --- B1, B2 (materias primas, mundo) y B5 descriptiva (petróleo): serie temporal
    efectos = np.round(np.arange(0, 0.42, 0.02), 2)
    ts = {}
    preg_ts = {"B1_mp_infl_alta": ("mp_real", "infl_alta", +1), "B2_mp_recesion": ("mp_real", "recesion", -1),
               "B1_cfp_infl_alta (1927-)": ("cfp_real", "infl_alta", +1),
               "B5_petroleo_infl_alta (descriptiva)": ("petroleo_real", "infl_alta", +1),
               "C5_mp_spot_infl_alta": ("mp_spot_exceso_suma", "infl_alta", +1)}
    fam_ts = {q: ("INT3c" if q.startswith("C") else "INT3b") for q in preg_ts}
    for q, (col, est, signo) in preg_ts.items():
        s = mu[col].dropna()
        idx = s.index.intersection(mundo.index)
        idx = idx[idx >= 1877]
        st = st_serie(s.loc[idx])
        fila = {"activo": col, "estado_mundial": est, "estadisticos": {k: round(v, 3) if isinstance(v, float) else v
                                                                          for k, v in st.items()}}
        for forma in ("cuota", "mayoria"):
            x = mundo.loc[idx, est].to_numpy(float)
            if forma == "mayoria":
                x = (x >= 0.5).astype(float)
            fila[forma] = {"analitico": {f: mde_ts(x, st, m) for f, m in FAMILIAS.items()}}
            if forma == "mayoria" and x.sum() < 8:
                fila[forma]["simulado"] = "menos de 8 años en el estado: sin contraste"
                continue
            xs = x if signo > 0 else -x                       # se simula el efecto en la dirección esperada
            sim = {}
            for colas in ("normal", "t4"):
                pot = potencia_sim(xs, idx.to_numpy(), st["sd"], max(st["ar1"], 0.0), efectos, 0.05 / FAMILIAS[fam_ts[q]],
                                   colas, rng)
                sim[colas] = {"mde_calibrado_pp": None if (v := mde_de_curva(efectos, pot["calibrado"])) is None
                              else round(100 * v, 1),
                              "mde_completo_pp": None if (w := mde_de_curva(efectos, pot["completo"])) is None
                              else round(100 * w, 1),
                              "potencia_completo": dict(zip(efectos.tolist(), pot["completo"]))}
            fila[forma]["simulado_m_familia"] = sim
            fila[forma]["unidad"] = ("pp por pasar de 0 % a 100 % de países en el estado" if forma == "cuota"
                                     else "pp: años con ≥ 50 % de países en el estado frente al resto")
        ts[q] = fila
    res["serie_temporal"] = ts

    # --- USA solo (dummy de EE. UU.) para las mismas series: alternativa a la cuota mundial
    usa = pa[pa.pais == "USA"].set_index("año")
    alt = {}
    for q, (col, est, signo) in (("B1_mp_infl_alta_USA", ("mp_real", "infl_alta", 1)),
                                 ("B2_mp_recesion_USA", ("mp_real", "recesion", -1))):
        s = mu[col].dropna()
        idx = s.index.intersection(usa.index)
        idx = idx[idx >= 1877]
        st = st_serie(s.loc[idx])
        alt[q] = {f: mde_ts(usa.loc[idx, est].to_numpy(float), st, m) for f, m in FAMILIAS.items()}
    res["serie_temporal_usa"] = alt

    # --- paneles: oro local (B3), crédito (B4), descomposición (C1-C4, C6)
    pan = {}
    casos = [
        ("B3_oro_infl_alta", oro, "oro_log", "infl_alta", "INT3b"),
        ("B4_credito_exceso_recesion", cre, "exceso_credito", "recesion", "INT3b"),
        ("B4b_credito_real_recesion (descr.)", cre, "corp_real", "recesion", "INT3b"),
        ("C1_valoracion_estanflacion", dc, "eq_valoracion", "estanflacion", "INT3c"),
        ("C2_dividendo_real_estanflacion (descr.)", dc, "eq_div_real", "estanflacion", "INT3c"),
        ("C3_bono_capital_infl_alta", dc, "bono_capital", "infl_alta", "INT3c"),
        ("C4_bono_capital_crec_bajo", dc, "bono_capital", "crec_bajo", "INT3c"),
        ("C6_viv_menos_bolsa_capital_infl_alta (descr.)", dc, "viv_menos_bolsa_capital", "infl_alta", "INT3c"),
        ("ref_bolsa_total_estanflacion (Q1)", dc, "eq_total", "estanflacion", "INT3c"),
        ("ref_bono_total_infl_alta (Q2)", dc, "bono_total", "infl_alta", "INT3c"),
    ]
    for q, f, col, est, fam in casos:
        f = f[f.pais.isin(NUCLEO)]
        if q.startswith("B4"):
            f = f[f.año >= 1877]
        f = f[f.año.isin(años)]
        st = st_panel(f, col)
        disp = set(zip(f.dropna(subset=[col]).pais, f.dropna(subset=[col]).año))
        e = pa[pa.pais.isin(f.pais.unique())].rename(columns={est: "v"})[["pais", "año", "v"]]
        pan[q] = {"activo": col, "estado": est, "familia": fam,
                  "estadisticos": {k: round(v, 3) if isinstance(v, float) else v for k, v in st.items()},
                  "mde": {fm: mde_panel(e, disp, st, m) for fm, m in FAMILIAS.items()},
                  "mde_x1.3_validador": mde_panel(e, disp, st, FAMILIAS[fam], penal=1.3)}
    res["panel"] = pan

    # --- suelo del p empírico del placebo (por qué no se usa el p por rangos bajo Holm)
    res["suelo_p_placebo"] = {f"T={T}": {"desplazamientos": T - 2 * DESFASE_MIN + 1,
                                         "p_minimo": round(1 / (T - 2 * DESFASE_MIN + 2), 4),
                                         "holm_m_max_con_p_rangos": int(np.floor(0.05 * (T - 2 * DESFASE_MIN + 2)))}
                              for T in (72, 123, 124)}
    out = REPO / "research" / "int" / "int3b_potencia.json"
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    print(json.dumps(res["regimen"], indent=1, ensure_ascii=False))
    for q, f in ts.items():
        print(q, {k: (f[k]["analitico"][fam_ts[q]], {c: (v["mde_calibrado_pp"], v["mde_completo_pp"])
                                                   for c, v in f[k].get("simulado_m_familia", {}).items()} if isinstance(
            f[k].get("simulado_m_familia"), dict) else None) for k in ("cuota", "mayoria")})
    for q, f in alt.items():
        print(q, f["INT3b"])
    for q, f in pan.items():
        print(q, f["estadisticos"]["sd"], f["mde"][f["familia"]], "x1.3:", f["mde_x1.3_validador"]["mde_pp"])


if __name__ == "__main__":
    main()
