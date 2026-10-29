"""Validador INT-6 (29-oct): sensibilidad robusta A POSTERIORI, solo informativa (como en INT-3). No cambia ningún
veredicto ni toca research/int/int6_resultado.*. Reutiliza el código propio de scripts/val_int6_repro.py.

G2: inflación simple, IPC del mes m (no "as of", informativo), NW 12, Huber, Spearman, winsorizado 1/99, sin 1973-74,
sin 1979-82, quitar un año cada vez; y en cada variante el signo de 1989-2004 (criterio iv).
X1: quitar un país / una década; + crecimiento propio en t en la base; ≥ 8 otros; caída < −1 %; bloques de 5 años;
sin 1919-1921 y 1929-1932; sin el filtro de hiperinflación; subperiodos.
K2: reproducción propia (Δ diciembre dentro de cada serie, R. U. ≤ 1918, EE. UU. ≥ 1919) y x_1919 con el R. U.

Uso: .venv/bin/python -m scripts.val_int6_sens   → research/int/int6_validador_sens.json
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from scripts import val_int6_repro as V
from src.intl import data as D


def g2_variantes(m):
    idx = pd.date_range("1955-01-01", "2004-12-01", freq="MS")
    oro, ir, cpi = (m[k].reindex(idx) for k in ("oro", "ir3m", "cpi"))
    y = np.log(oro).diff()

    def serie(infl, lag=1):
        return (ir / 100 - infl.shift(lag)).diff()

    il = np.log(cpi) - np.log(cpi.shift(12))
    isimp = cpi / cpi.shift(12) - 1
    xs = {"oficial": serie(il), "inflacion_simple": serie(isimp), "ipc_del_mes_m_no_asof": serie(il, 0),
          "ipc_de_m_menos_2": serie(il, 2)}
    out = {}

    def resumen(f, L=6):
        yr = f.index.year
        r = V.ols_nw(f.y, f.x, L)
        return {"b": r["b"], "t": r["t"], "p": r["p"], "r": float(np.corrcoef(f.y, f.x)[0, 1]),
                "b_1973_1988": V.ols_nw(f.y[yr <= 1988], f.x[yr <= 1988], L)["b"],
                "b_1989_2004": V.ols_nw(f.y[yr >= 1989], f.x[yr >= 1989], L)["b"],
                "t_1989_2004": V.ols_nw(f.y[yr >= 1989], f.x[yr >= 1989], L)["t"]}

    base = pd.DataFrame({"y": y, "x": xs["oficial"]}).loc["1973-01-01":"2004-12-01"].dropna()
    for k, x in xs.items():
        f = pd.DataFrame({"y": y, "x": x}).loc["1973-01-01":"2004-12-01"].dropna()
        out[k] = resumen(f)
    out["nw_12"] = resumen(base, 12)
    w = base.apply(lambda s: s.clip(*np.nanquantile(s, [0.01, 0.99])))
    out["winsor_1_99"] = resumen(w)
    for nom, años in (("sin_1973_1974", [1973, 1974]), ("sin_1979_1982", [1979, 1980, 1981, 1982])):
        out[nom] = resumen(base[~base.index.year.isin(años)])
    yr = base.index.year
    hub = {}
    for nom, msk in (("todo", np.ones(len(base), bool)), ("1973_1988", yr <= 1988), ("1989_2004", yr >= 1989)):
        rl = sm.RLM(base.y[msk], sm.add_constant(base.x[msk]), M=sm.robust.norms.HuberT()).fit()
        hub[nom] = {"b": float(rl.params.iloc[1]), "z": float(rl.tvalues.iloc[1])}
    out["huber"] = hub
    out["spearman"] = {nom: float(stats.spearmanr(base.y[msk], base.x[msk])[0])
                       for nom, msk in (("todo", np.ones(len(base), bool)), ("1973_1988", yr <= 1988), ("1989_2004", yr >= 1989))}
    loyo = [V.ols_nw(base.y[yr != a], base.x[yr != a]) for a in range(1973, 2005)]
    out["quitar_un_año"] = {"b_min": min(r["b"] for r in loyo), "b_max": max(r["b"] for r in loyo),
                            "t_menos_negativo": max(r["t"] for r in loyo),
                            "año_que_mas_pesa": int(1973 + int(np.argmax([r["t"] for r in loyo])))}
    l89 = [V.ols_nw(base.y[(yr >= 1989) & (yr != a)], base.x[(yr >= 1989) & (yr != a)])["b"] for a in range(1989, 2005)]
    out["1989_2004_quitar_un_año"] = {"b_min": min(l89), "b_max": max(l89), "positivos": int(sum(b > 0 for b in l89)),
                                      "de": len(l89)}
    ventanas = {}
    for a in range(1973, 2005, 8):
        msk = (yr >= a) & (yr <= a + 7)
        ventanas[f"{a}_{a + 7}"] = V.ols_nw(base.y[msk], base.x[msk])["b"]
    out["ventanas_8_años"] = ventanas
    return out


def x1_variantes(jst):
    f, x, cae, g = V.x1_datos(jst)
    out = {}
    ev = lambda ff, pan, **kw: {k: v for k, v in V.evaluar(ff, pan, B=500, placebo=False, **kw).items()  # noqa: E731
                                if k in ("filas", "eventos", "d_auc", "ic95", "temporal_1950_2004")}
    full = V.evaluar(f, x, B=0 or 1, placebo=False, temporal=False)
    y, p1, p0, gr, t = full["_pred"]
    out["quitar_un_pais_de_la_evaluacion"] = {c: float(V.auc_estrat(y[gr != c], p1[gr != c], gr[gr != c])
                                                       - V.auc_estrat(y[gr != c], p0[gr != c], gr[gr != c])) for c in V.NUC}
    out["quitar_una_decada"] = {f"{d}s": float(V.auc_estrat(y[(t // 10) * 10 != d], p1[(t // 10) * 10 != d], gr[(t // 10) * 10 != d])
                                               - V.auc_estrat(y[(t // 10) * 10 != d], p0[(t // 10) * 10 != d], gr[(t // 10) * 10 != d]))
                                for d in range(1870, 2001, 10)}
    sub = {}
    for nom, (a, b) in {"1871_1913": (1871, 1913), "1919_1938": (1919, 1938), "1946_2004": (1946, 2004)}.items():
        msk = (t >= a) & (t <= b)
        sub[nom] = {"eventos": int(y[msk].sum()), "d_auc": float(V.auc_estrat(y[msk], p1[msk], gr[msk]) - V.auc_estrat(y[msk], p0[msk], gr[msk]))}
    out["subperiodos_sobre_predicciones"] = sub
    msk = ~np.isin(t, [1919, 1920, 1928, 1929, 1930, 1931])
    out["sin_t_1919_1920_1928_1931"] = float(V.auc_estrat(y[msk], p1[msk], gr[msk]) - V.auc_estrat(y[msk], p0[msk], gr[msk]))
    # bloques de 5 años
    rng = np.random.default_rng(7)
    bl = (t - 1871) // 5
    ub = np.unique(bl)
    idx = {b: np.flatnonzero(bl == b) for b in ub}
    bs = []
    for _ in range(2000):
        s = np.concatenate([idx[b] for b in rng.choice(ub, len(ub))])
        bs.append(V.auc_estrat(y[s], p1[s], gr[s]) - V.auc_estrat(y[s], p0[s], gr[s]))
    out["ic95_bloques_5_años"] = [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]
    # crecimiento propio en t dentro de la base
    f2 = f.copy()
    f2["g_propio"] = [g.at[tt, c] for c, tt in zip(f2.pais, f2.t)]
    out["base_mas_crecimiento_propio_t"] = ev(f2, x, extra_base=["g_propio"])
    # ≥ 8 otros con dato; caída < −1 %
    x8 = pd.DataFrame({c: cae[[k for k in V.NUC if k != c]].mean(axis=1).where(cae[[k for k in V.NUC if k != c]].notna().sum(axis=1) >= 8)
                       for c in V.NUC})
    out["minimo_8_otros"] = ev(f, x8)
    cae1 = (g < -0.01).astype(float).where(g.notna())
    x1p = pd.DataFrame({c: cae1[[k for k in V.NUC if k != c]].mean(axis=1).where(cae1[[k for k in V.NUC if k != c]].notna().sum(axis=1) >= 5)
                        for c in V.NUC})
    out["caida_menor_que_menos_1pc"] = ev(f, x1p)
    out["media_de_crecimiento_de_los_otros_signo_cambiado"] = ev(
        f, -pd.DataFrame({c: g[[k for k in V.NUC if k != c]].mean(axis=1) for c in V.NUC}))
    return out


def k2_propio(jst):
    con = D.connect()
    uk = V.mensual(D.load_dev(con, "boe_uk_corp_bond_spread_m"))
    us = V.mensual(D.load_dev(con, "BAA")) - V.mensual(D.load_dev(con, "AAA"))
    con.close()

    def ddic(s):
        d = s[s.index.month == 12].dropna()
        d = pd.Series(d.values, index=d.index.year)
        return (d - d.shift(1)).where(pd.Series(d.index, index=d.index).diff() == 1)

    duk, dus = ddic(uk), ddic(us)
    oficial = pd.concat([duk[duk.index <= 1918], dus[dus.index >= 1919]]).sort_index()
    con1919 = pd.concat([duk[duk.index <= 1919], dus[dus.index >= 1920]]).sort_index()
    f, _, _, _ = V.x1_datos(jst)
    comun = lambda s: pd.DataFrame({c: s.reindex(range(V.A0, V.A1 + 1)) for c in V.NUC})  # noqa: E731
    r = V.evaluar(f, comun(oficial))
    y, p1, p0, gr, t = r.pop("_pred")
    años = np.unique(t)
    idx = {a: np.flatnonzero(t == a) for a in años}
    pbs = []
    for sem in range(20):                       # dispersión del p bloques (2.000 réplicas) según la semilla
        rng = np.random.default_rng(sem)
        bs = np.array([V.auc_estrat(y[s], p1[s], gr[s]) - V.auc_estrat(y[s], p0[s], gr[s])
                       for s in (np.concatenate([idx[a] for a in rng.choice(años, len(años))]) for _ in range(2000))])
        pbs.append(float(min(1, 2 * (1 + (bs <= 0).sum()) / 2001)))
    r["p_bloques_20_semillas"] = {"min": min(pbs), "mediana": float(np.median(pbs)), "max": max(pbs),
                                  "frac_bilateral_<=_0.0125": float(np.mean(np.array(pbs) <= 0.0125)),
                                  "frac_unilateral_<=_0.0125": float(np.mean(np.array(pbs) / 2 <= 0.0125))}
    r2 = V.evaluar(f, comun(con1919), placebo=False)
    r2.pop("_pred")
    return {"x_1919_oficial_vacio": bool(np.isnan(oficial.get(1919, np.nan))), "propio": r, "con_x1919_RU": r2}


def main():
    m, jst, _ = V.cargar()
    res = {"G2": g2_variantes(m)}
    print("G2 hecho", flush=True)
    res["X1"] = x1_variantes(jst)
    print("X1 hecho", flush=True)
    res["K2"] = k2_propio(jst)
    (V.REPO / "research" / "int" / "int6_validador_sens.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    print(json.dumps(res, indent=1, default=float)[:12000])


if __name__ == "__main__":
    main()
