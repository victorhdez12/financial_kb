"""Validador INT-6 (29-oct): reproducción INDEPENDIENTE de G2 y X1 con código propio mínimo, comprobaciones de datos
("as of", corte ≤ 2004, X1 sin el propio país) y lecturas alternativas del criterio (i) de K1/K2/X1.

NO toca la corrida oficial ni sus resultados (research/int/int6_resultado.*): solo los lee para comparar.
Código propio: no importa src/intl/int3*, int4, int6 ni scripts/int6_corrida; solo el cargador con corte
(src/intl/data.load_dev) y el fechado de recesiones de INT-1 (insumo, data/intl/recesiones_anuales_dev.parquet).
Logit con scikit-learn (sin penalización), AUC con sklearn.metrics, Newey-West y placebo escritos aquí.

Uso: .venv/bin/python -m scripts.val_int6_repro   → research/int/int6_validador.json (y resumen por pantalla)
"""
from __future__ import annotations

import json
import subprocess
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from src.intl import data as D
from src.warehouse import db

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[1]
NUC = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
GUERRAS = set(range(1914, 1919)) | set(range(1939, 1946))
A0, A1 = 1870, 2004
OFICIAL = json.loads((REPO / "research" / "int" / "int6_resultado.json").read_text())


# ================================================================ utilidades propias
def mensual(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = pd.DatetimeIndex(s.index).to_period("M").to_timestamp()
    assert not s.index.duplicated().any()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="MS"))


def ols_nw(y, x, L=6):
    y, x = np.asarray(y, float), np.asarray(x, float)
    X = np.column_stack([np.ones_like(x), x])
    b = np.linalg.solve(X.T @ X, X.T @ y)
    e = y - X @ b
    u = X * e[:, None]
    S = u.T @ u
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        G = u[l:].T @ u[:-l]
        S += w * (G + G.T)
    Q = np.linalg.inv(X.T @ X)
    V = Q @ S @ Q
    se = np.sqrt(V[1, 1])
    T = len(y)
    t = b[1] / se
    return {"b": float(b[1]), "se": float(se), "t": float(t), "p": float(2 * stats.t.sf(abs(t), T - 1)),
            "ic95": [float(b[1] - stats.t.ppf(0.975, T - 1) * se), float(b[1] + stats.t.ppf(0.975, T - 1) * se)], "T": T}


def auc_estrat(y, p, g):
    num = den = 0.0
    for c in np.unique(g):
        f = g == c
        n1 = y[f].sum()
        n0 = f.sum() - n1
        if n1 == 0 or n0 == 0:
            continue
        num += roc_auc_score(y[f], p[f]) * n1 * n0
        den += n1 * n0
    return num / den


def lr_fit(X, y):
    return LogisticRegression(penalty=None, solver="lbfgs", max_iter=5000, tol=1e-10).fit(X, y)


def loco(X, y, g):
    p = np.empty(len(y))
    for c in np.unique(g):
        f = g == c
        p[f] = lr_fit(X[~f], y[~f]).predict_proba(X[f])[:, 1]
    return p


# ================================================================ datos
def cargar():
    con = D.connect()
    m = {k: mensual(D.load_dev(con, sid)) for k, sid in (("oro", "gold_wb_usd_m"), ("ir3m", "oecd_ir3m_usa"),
                                                          ("cpi", "oecd_cpi_usa_idx"))}
    jst = {}
    for v in ("rgdpmad", "cpi"):
        jst[v] = pd.DataFrame({c: (lambda s: pd.Series(s.values, index=s.index.year))(D.load_dev(con, f"jst_{c.lower()}_{v}"))
                               for c in NUC}).reindex(range(A0, A1 + 1))
    con.close()
    chequeo = {"max_fecha_mensual": {k: str(s.dropna().index.max().date()) for k, s in m.items()},
               "max_año_jst": {v: int(df.dropna(how="all").index.max()) for v, df in jst.items()}}
    assert all(v <= 2004 for v in chequeo["max_año_jst"].values())
    assert all(s.dropna().index.max() <= pd.Timestamp("2004-12-31") for s in m.values())
    return m, jst, chequeo


# ================================================================ G2
def g2(m):
    idx = pd.date_range("1955-01-01", "2004-12-01", freq="MS")
    oro, ir, cpi = (m[k].reindex(idx) for k in ("oro", "ir3m", "cpi"))
    infl = np.log(cpi) - np.log(cpi.shift(12))
    real = ir / 100 - infl.shift(1)
    f = pd.DataFrame({"y": np.log(oro).diff(), "x": real.diff()}).loc["1973-01-01":"2004-12-01"].dropna()
    r = ols_nw(f.y, f.x)
    r["r"] = float(np.corrcoef(f.y, f.x)[0, 1])
    T = len(f)
    tpl = np.array([ols_nw(f.y.values, np.roll(f.x.values, k))["t"] for k in range(12, T - 12 + 1)])
    phi = max(1.0, tpl.std(ddof=1))
    r["placebo"] = {"n": len(tpl), "phi": float(phi), "p_cal": float(2 * stats.t.sf(abs(r["t"]) / phi, T - 1)),
                    "p95_abs_t": float(np.quantile(np.abs(tpl), 0.95))}
    yr = f.index.year
    r["mitades"] = {"1973_1988": ols_nw(f.y[yr <= 1988], f.x[yr <= 1988]),
                    "1989_2004": ols_nw(f.y[yr >= 1989], f.x[yr >= 1989])}
    dic = pd.DataFrame({"oro": oro, "real": real})
    dic = dic[dic.index.month == 12]
    an = pd.DataFrame({"y": np.log(dic.oro).diff().values, "x": dic.real.diff().values}, index=dic.index.year).loc[1973:2004].dropna()
    r["anual"] = {"n": len(an), "b": float(np.polyfit(an.x, an.y, 1)[0])}
    return r, f


# ================================================================ X1
def x1_datos(jst):
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    g = np.log(jst["rgdpmad"]).diff()
    cae = (g < 0).astype(float).where(g.notna())
    x = pd.DataFrame(index=cae.index)
    for c in NUC:
        o = cae[[k for k in NUC if k != c]]                       # el propio país, fuera
        x[c] = o.mean(axis=1).where(o.notna().sum(axis=1) >= 5)
    infl = np.expm1(np.log(jst["cpi"]).diff())
    hiper = {(c, int(t)) for c in NUC for t, v in infl[c].items() if np.isfinite(v) and v > 0.5}
    hiper |= {(c, t - 1) for c, t in hiper}
    filas = []
    for c in NUC:
        r = rec[rec.pais == c]
        en = {y for _, q in r.iterrows() for y in range(int(q.pico) + 1, int(q.valle) + 1)}
        ent = {int(q.pico) + 1 for _, q in r.iterrows()}
        valles = sorted(int(v) for v in r.valle)
        años = set(jst["rgdpmad"][c].dropna().index)
        primer = min(años)
        for t in sorted(años):
            if t < 1871 or t + 1 > A1 or t in en or (t + 1) not in años:
                continue
            if t in GUERRAS or (t + 1) in GUERRAS or (c, t) in hiper:
                continue
            vs = [v for v in valles if v < t]
            ref = max(vs) if vs else primer
            filas.append({"pais": c, "t": t, "y": int(t + 1 in ent), "b_a": float(bool(vs) and t == max(vs) + 1),
                          "b_b": np.log(max(t - ref, 1))})
    return pd.DataFrame(filas), x, cae, g


def mira(f, panel):
    return np.array([panel.at[t, c] if t in panel.index else np.nan for c, t in zip(f.pais, f.t)], float)


def evaluar(f, panel, B=2000, semilla=12345, extra_base=None, placebo=True, temporal=True):
    xv = mira(f, panel)
    base_cols = ["b_a", "b_b"] + (extra_base or [])
    ok = np.isfinite(xv) & np.isfinite(f[base_cols].to_numpy(float)).all(axis=1)
    g = f[ok].reset_index(drop=True)
    y, gr, t = g.y.to_numpy(), g.pais.to_numpy(), g.t.to_numpy()
    X0 = g[base_cols].to_numpy(float)
    X1 = np.column_stack([X0, xv[ok]])
    p1, p0 = loco(X1, y, gr), loco(X0, y, gr)
    d = auc_estrat(y, p1, gr) - auc_estrat(y, p0, gr)
    out = {"filas": int(len(y)), "eventos": int(y.sum()), "auc_b1": auc_estrat(y, p0, gr), "auc_mod": auc_estrat(y, p1, gr),
           "d_auc": float(d)}
    ll = lambda p: -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))  # noqa: E731
    out["d_logloss"] = float(ll(p1) - ll(p0))
    lp = np.log(p1 / (1 - p1)).reshape(-1, 1)
    out["pendiente_calibracion"] = float(lr_fit(lp, y).coef_[0, 0])
    rng = np.random.default_rng(semilla)
    años = np.unique(t)
    idx = {a: np.flatnonzero(t == a) for a in años}
    bs = []
    for _ in range(B):
        s = np.concatenate([idx[a] for a in rng.choice(años, len(años))])
        bs.append(auc_estrat(y[s], p1[s], gr[s]) - auc_estrat(y[s], p0[s], gr[s]))
    bs = np.array(bs)
    out["ic95"] = [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]
    out["p_bloques_bilateral"] = float(min(1, 2 * (1 + (bs <= 0).sum()) / (1 + B)))
    out["_pred"] = (y, p1, p0, gr, t)
    if temporal:
        q1, q0 = np.full(len(y), np.nan), np.full(len(y), np.nan)
        for d0 in range(1950, 2001, 10):
            tr, te = t + 1 < d0, (t >= d0) & (t <= d0 + 9)
            q1[te] = lr_fit(X1[tr], y[tr]).predict_proba(X1[te])[:, 1]
            q0[te] = lr_fit(X0[tr], y[tr]).predict_proba(X0[te])[:, 1]
        v = np.isfinite(q1)
        out["temporal_1950_2004"] = float(auc_estrat(y[v], q1[v], gr[v]) - auc_estrat(y[v], q0[v], gr[v]))
    if placebo:
        ds = []
        vals = panel.reindex(range(A0, A1 + 1)).to_numpy()
        for k in range(6, (A1 - A0 + 1) - 6 + 1):
            pk = pd.DataFrame(np.roll(vals, k, axis=0), index=range(A0, A1 + 1), columns=panel.columns)
            xk = mira(f, pk)
            okk = np.isfinite(xk) & np.isfinite(f[base_cols].to_numpy(float)).all(axis=1)
            yk, gk = f.y.to_numpy()[okk], f.pais.to_numpy()[okk]
            X0k = f[base_cols].to_numpy(float)[okk]
            ds.append(auc_estrat(yk, loco(np.column_stack([X0k, xk[okk]]), yk, gk), gk) - auc_estrat(yk, loco(X0k, yk, gk), gk))
        ds = np.array(ds)
        z = (d - ds.mean()) / ds.std(ddof=1)
        out["placebo"] = {"n": len(ds), "media": float(ds.mean()), "dt": float(ds.std(ddof=1)), "z": float(z),
                          "p_z": float(stats.norm.sf(z)), "p_rangos": float((1 + (ds >= d).sum()) / (1 + len(ds)))}
    return out


# ================================================================ Holm: lecturas del criterio (i)
def holm(ps: dict, a=0.05):
    o = sorted(ps, key=ps.get)
    out, sigue = {}, True
    for i, k in enumerate(o):
        sigue = sigue and ps[k] <= a / (len(ps) - i)
        out[k] = sigue
    return out


def lecturas_criterio_i():
    C, H = OFICIAL["confirmatorias"], OFICIAL["holm6"]
    p_main, p_i = H["p"], H["criterio_i_auc"]["p"]
    pb = {q: C[q]["p_bloques"] for q in ("K1", "K2", "X1")}
    ic = {q: C[q]["d_auc_ic95"] for q in ("K1", "K2", "X1")}
    out = {}
    out["A_oficial_holm6_mixto_p_cal_y_p_bloques"] = {q: holm(p_i)[q] for q in pb}
    # B: nivel de cada IC = el escalón de Holm de la familia principal (p_z); IC a 1 − α/(m − rango)
    o = sorted(p_main, key=p_main.get)
    niv = {q: 0.05 / (6 - o.index(q)) for q in pb}
    out["B_ic_al_nivel_del_escalon_holm6_principal"] = {q: {"alfa_ic": niv[q], "excluye_0_si_p_bloques_<=": pb[q] <= niv[q]}
                                                        for q in pb}
    # C: Bonferroni-6 sobre el IC (lo más conservador)
    out["C_bonferroni6"] = {q: pb[q] <= 0.05 / 6 for q in pb}
    # D: Holm-3 solo sobre las tres AUC (NO es Holm-6; contradice la decisión 2)
    out["D_holm3_solo_auc_NO_literal"] = holm(pb)
    # E: IC 95 % sin ajuste (NO literal: el texto dice "tras Holm-6")
    out["E_ic95_sin_ajuste_NO_literal"] = {q: ic[q][0] > 0 for q in pb}
    # F: p bloques unilateral (mejora) en el Holm-6 mixto (diff propuesto en el Validador de INT-4-ML)
    p_f = dict(p_i)
    for q in pb:
        p_f[q] = pb[q] / 2 if C[q]["d_auc"] > 0 else 1.0
    out["F_holm6_mixto_p_bloques_unilateral"] = {q: holm(p_f)[q] for q in pb}
    otros = {q: all(v for k, v in OFICIAL["veredicto"][q].items() if k not in ("ESTABLECIDO", "i_dauc_estrat_ic_holm6"))
             for q in pb}
    out["resto_de_criterios_ii_v_cumplidos"] = otros
    out["veredicto_por_lectura"] = {lec: {q: bool((v[q] if isinstance(v[q], bool) else v[q]["excluye_0_si_p_bloques_<="])
                                                  and otros[q]) for q in pb}
                                    for lec, v in out.items() if lec[0] in "ABCDEF"}
    return out


def main():
    m, jst, chequeo = cargar()
    res = {"commit_validador": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                              cwd=REPO).stdout.strip(), "chequeo_corte": chequeo}
    r, _ = g2(m)
    o = OFICIAL["confirmatorias"]["G2"]
    res["G2"] = {"propio": r, "oficial": {"b": o["efecto"], "t": o["t"], "p_cal": o["placebo"]["p_cal"],
                                          "1973_1988": o["pendiente_1973_1988"], "1989_2004": o["pendiente_1989_2004"],
                                          "anual": o["anual_dic_dic"]["pendiente"], "r": o["r_estandarizada"]}}
    print("G2 propio", round(r["b"], 4), round(r["t"], 3), "p_cal", round(r["placebo"]["p_cal"], 5),
          "mitades", round(r["mitades"]["1973_1988"]["b"], 4), round(r["mitades"]["1989_2004"]["b"], 4), flush=True)
    f, x, cae, _ = x1_datos(jst)
    # X1 no incluye al propio país: comprobación directa contra la definición
    ok_propio = all(abs(x.at[t, c] - cae.loc[t, [k for k in NUC if k != c]].mean()) < 1e-12
                    for c in NUC for t in x.index if np.isfinite(x.at[t, c]))
    res["X1_sin_propio_pais"] = bool(ok_propio)
    r = evaluar(f, x)
    r.pop("_pred")
    o = OFICIAL["confirmatorias"]["X1"]
    res["X1"] = {"propio": r, "oficial": {"filas": o["filas"], "eventos": o["eventos"], "auc_b1": o["auc_liston"],
                                          "auc_mod": o["auc_modelo"], "d_auc": o["d_auc"], "ic95": o["d_auc_ic95"],
                                          "p_bloques": o["p_bloques"], "z": o["placebo"]["z"],
                                          "temporal": o["temporal_1950_2004"]["d_auc"],
                                          "d_logloss": o["d_logloss"], "pendiente": o["calibracion"]["pendiente"]}}
    print("X1 propio", r["filas"], r["eventos"], round(r["d_auc"], 4), r["ic95"], "z", round(r["placebo"]["z"], 2),
          "temporal", round(r["temporal_1950_2004"], 3), flush=True)
    res["criterio_i_lecturas"] = lecturas_criterio_i()
    (REPO / "research" / "int" / "int6_validador.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    print(json.dumps(res["criterio_i_lecturas"]["veredicto_por_lectura"], indent=1))


if __name__ == "__main__":
    main()
