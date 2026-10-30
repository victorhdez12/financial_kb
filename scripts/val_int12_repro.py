"""Reproducción independiente de P-DEV-INT12 C1-C3 (validador). Solo datos <= 2004 vía load_dev."""
import sys, json
import numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, ".")
from src.intl import data as D, panel as PA, escenarios as E

con = D.connect()
S = {k: D.load_dev(con, k) for k in ("aqr_mkt_usa_d", "BAA", "AAA", "TB3MS", "shiller_gs10")}
an = PA.anual(con)
con.close()
for k, s in S.items():
    print(k, s.index.min().date(), s.index.max().date(), len(s), float(s.abs().median()))
r = (S["aqr_mkt_usa_d"] / 100).dropna().sort_index()
assert r.index.max() <= pd.Timestamp("2004-12-31")

# ---- objetivo e info diaria, construidos de forma independiente (bucles por mes)
per = r.index.to_period("M")
months = sorted(set(per))
byM = {m: r[per == m] for m in months}
rows = []
for i, m in enumerate(months[:-1]):
    nxt = byM[months[i + 1]]
    hist = r[r.index <= byM[m].index[-1]]
    last = hist.values
    r2 = last ** 2
    mret = [(1 + byM[months[j]]).prod() - 1 for j in range(i - 11, i + 1)] if i >= 11 else None
    rows.append(dict(mes=m, rv=float((nxt.values ** 2).sum()), n=len(nxt),
                     l5=np.log(r2[-5:].mean()), l21=np.log(r2[-21:].mean()), l63=np.log(r2[-63:].mean()) if len(r2) >= 63 else np.nan,
                     b1=float(np.var(mret, ddof=1)) if mret else np.nan,
                     mret=float((1 + byM[m]).prod() - 1)))
T = pd.DataFrame(rows).set_index("mes")

def mon(s):
    s = s.copy(); s.index = s.index.to_period("M"); return s.groupby(level=0).last()
baa, aaa, g10, tb3 = (mon(S[k]) for k in ("BAA", "AAA", "shiller_gs10", "TB3MS"))
prev = T.index - 1
T["cred"] = (baa - aaa).reindex(prev).values
T["curva"] = (g10 - tb3).reindex(prev).values
T["corto"] = tb3.reindex(prev).values
usa = an.loc["USA"].reset_index(); usa["pais"] = "USA"
reg = E.estados_operables(usa[["pais", "año", "inflacion", "rgdpmad"]]).set_index("año")["regimen"].astype(int)
ry = [m.year - 1 if m.month >= 4 else m.year - 2 for m in T.index]
c = reg.reindex(ry).values
T["rinf"] = np.where(c >= 0, np.isin(c, [1, 2]).astype(float), np.nan)
T["rbre"] = np.where(c >= 0, np.isin(c, [2, 3]).astype(float), np.nan)
HARc = ["l5", "l21", "l63"]; Xc = ["cred", "curva", "corto", "rinf", "rbre"]
print("check cred 1950-01 =", T.loc[pd.Period("1950-01"), "cred"], "BAA-AAA 1949-12 =", (baa - aaa)[pd.Period("1949-12")])

ev = T.index[(T.index >= pd.Period("1950-01")) & (T.index <= pd.Period("2004-11"))]
ok = T[HARc + Xc].notna().all(1)
y_all = np.log(T.rv / T.n)

def fit_ols(A, y):
    A1 = np.column_stack([np.ones(len(A)), A]); b = np.linalg.lstsq(A1, y, rcond=None)[0]
    return b, float(np.mean(np.exp(y - A1 @ b)))

F = {k: [] for k in ("b1", "har", "harx", "gb", "b1cal", "harx_z")}
from sklearn.ensemble import HistGradientBoostingRegressor
cur = None
for m in ev:
    if cur is None or m.month == 1:
        tr = T[(T.index >= pd.Period("1934-02")) & (T.index <= m - 1) & ok]   # objetivo de m-1 acaba en el origen de m
        y = y_all[tr.index].values
        bh, sh = fit_ols(tr[HARc].values, y)
        bx, sx = fit_ols(tr[HARc + Xc].values, y)
        gb = HistGradientBoostingRegressor(loss="squared_error", learning_rate=0.05, max_iter=300, max_depth=3,
                                           min_samples_leaf=20, l2_regularization=1.0, early_stopping=False,
                                           random_state=20261030).fit(tr[HARc + Xc].values, y)
        sg = float(np.mean(np.exp(y - gb.predict(tr[HARc + Xc].values))))
        trb = tr[tr.b1.notna()]
        cal = float(np.mean(trb.rv / trb.n) / np.mean(trb.b1 / 21))  # sensibilidad: B1 recalibrado en entreno
        cur = (bh, sh, bx, sx, gb, sg, cal)
    bh, sh, bx, sx, gb, sg, cal = cur
    row = T.loc[m]
    F["b1"].append(row.b1)
    F["b1cal"].append(row.b1 * cal * row.n / 21)
    F["har"].append(row.n * np.exp(bh[0] + bh[1:] @ row[HARc].values.astype(float)) * sh)
    F["harx"].append(row.n * np.exp(bx[0] + bx[1:] @ row[HARc + Xc].values.astype(float)) * sx)
    F["gb"].append(row.n * np.exp(gb.predict(row[HARc + Xc].values.astype(float)[None])[0]) * sg)
P = pd.DataFrame({k: v for k, v in F.items() if v}, index=ev); P["rv"] = T.loc[ev, "rv"]

def ql(f): q = P.rv / f; return q - np.log(q) - 1
def dmt(d, L):
    d = np.asarray(d); n = len(d); u = d - d.mean(); s = u @ u / n
    for k in range(1, L + 1): s += 2 * (1 - k / (L + 1)) * (u[k:] @ u[:-k]) / n
    t = d.mean() / np.sqrt(s / n); return t, 1 - norm.cdf(t)
L = int(np.floor(4 * (len(P) / 100) ** (2 / 9)))
out = {"N": len(P), "L": L}
for c, (b, ch) in {"C1": ("b1", "har"), "C2": ("har", "harx"), "C3": ("harx", "gb"),
                   "S_C1_b1cal": ("b1cal", "har")}.items():
    lb, lc = ql(P[b]), ql(P[ch]); t, p = dmt(lb - lc, L)
    h1 = P.index < pd.Period("1977-07")
    out[c] = dict(gan=round(1 - lc.mean() / lb.mean(), 4), t=round(t, 3), p=p,
                  m1=round(1 - lc[h1].mean() / lb[h1].mean(), 4), m2=round(1 - lc[~h1].mean() / lb[~h1].mean(), 4))
ps = {c: out[c]["p"] for c in ("C1", "C2", "C3")}
o = sorted(ps, key=ps.get); prevp = 0
for i, c in enumerate(o):
    prevp = max(prevp, min(1, (3 - i) * ps[c])); out[c]["p_holm"] = prevp
# sesgo de nivel de B1 frente a RV
out["media_rv"] = float(P.rv.mean()); out["media_b1"] = float(P.b1.mean()); out["media_har"] = float(P.har.mean())
out["ratio_var_mensual/rv_eval"] = float(T.loc[ev, "mret"].var() / (T.loc[ev, "rv"].mean()))
out["autocorr_diaria_1950_77"] = float(r["1950":"1977"].autocorr()); out["autocorr_diaria_1977_04"] = float(r["1977":"2004"].autocorr())
# Mincer-Zarnowitz en logs (escala libre)
for k in ("b1", "har", "harx", "gb"):
    out[f"corr_log_{k}"] = float(np.corrcoef(np.log(P[k]), np.log(P.rv))[0, 1])
out["cond_harx_ultimo"] = float(np.linalg.cond(np.column_stack([np.ones(ok.sum()), T.loc[ok, HARc + Xc].values])))
print(json.dumps(out, indent=1, default=float))
P.to_pickle("research/int/val_int12/P.pkl")
T.to_pickle("research/int/val_int12/T.pkl")
