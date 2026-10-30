"""Validador INT-12: sensibilidades A POSTERIORI (no cambian ningún veredicto). Requiere scripts/val_int12_repro.py antes."""
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits
import numpy as np, pandas as pd
from scipy.stats import norm
from scipy.optimize import minimize_scalar
P = pd.read_pickle("research/int/val_int12/P.pkl"); T = pd.read_pickle("research/int/val_int12/T.pkl")
HARc = ["l5","l21","l63"]; Xc = ["cred","curva","corto","rinf","rbre"]
ok = T[HARc+Xc].notna().all(axis=1); y_all = np.log(T.rv/T.n)
def ql(f, rv): q = rv/f; return q-np.log(q)-1
def dmt(d, L=6):
    d=np.asarray(d); n=len(d); u=d-d.mean(); s=u@u/n
    for k in range(1,L+1): s+=2*(1-k/(L+1))*(u[k:]@u[:-k])/n
    return d.mean()/np.sqrt(s/n)
# oráculo de escala para B1 (ex post)
res = minimize_scalar(lambda c: ql(c*P.b1, P.rv).mean(), bounds=(0.1,5), method="bounded")
print("B1 escala oráculo c=%.3f qlike=%.4f vs B1 %.4f HAR %.4f -> C1 gan %.3f" % (res.x, res.fun, ql(P.b1,P.rv).mean(), ql(P.har,P.rv).mean(), 1-ql(P.har,P.rv).mean()/res.fun))
def run(cols, desde="1934-02"):
    f=[]; cur=None
    for m in P.index:
        if cur is None or m.month==1:
            tr=T[(T.index>=pd.Period(desde))&(T.index<=m-1)&ok]; y=y_all[tr.index].values
            A=np.column_stack([np.ones(len(tr)),tr[cols].values]); b=np.linalg.lstsq(A,y,rcond=None)[0]; s=np.mean(np.exp(y-A@b)); cur=(b,s)
        b,s=cur; row=T.loc[m]; f.append(row.n*np.exp(b[0]+b[1:]@row[cols].values.astype(float))*s)
    return np.array(f)
base = ql(P.har, P.rv)
for name, cols, desde in [("HAR+cred",HARc+["cred"],"1934-02"),("HAR+curva",HARc+["curva"],"1934-02"),("HAR+corto",HARc+["corto"],"1934-02"),
    ("HAR+reg",HARc+["rinf","rbre"],"1934-02"),("HAR-X todo",HARc+Xc,"1934-02")]:
    f = run(cols, desde); l = ql(f, P.rv)
    ref = base
    print(f"{name:22s} gan vs HAR(mismo entreno) {1-l.mean()/ref.mean():+.3%}  t {dmt(ref-l):+.2f}")
# coeficientes del HAR-X en el primer y último ajuste
for m in (pd.Period("1950-01"), pd.Period("2004-01")):
    tr=T[(T.index>=pd.Period("1934-02"))&(T.index<=m-1)&ok]; A=np.column_stack([np.ones(len(tr)),tr[HARc+Xc].values])
    print(m, np.round(np.linalg.lstsq(A,y_all[tr.index].values,rcond=None)[0],3))
print("credito medio 1934-49 / 1950-04:", T.loc["1934-02":"1949-12","cred"].mean(), T.loc["1950-01":"2004-11","cred"].mean())
d = (ql(P.harx,P.rv)-base); print("peores 5 meses de C2 (pérdida HAR-X - HAR):"); print(d.sort_values().tail(5))
print("C2 sin el peor 1%:", 1-ql(P.harx,P.rv)[d< d.quantile(.99)].mean()/base[d<d.quantile(.99)].mean())

print(P.loc[[pd.Period("1987-09"), pd.Period("1987-10")], ["rv","b1","har","harx","gb"]])
def ql1(f): q=P.rv/f; return q-np.log(q)-1
m = P.index != pd.Period("1987-09")
for a,b in (("b1","har"),("har","harx"),("harx","gb")):
    print(a,b,"sin 1987-09:", round(1-ql1(P[b])[m].mean()/ql1(P[a])[m].mean(),4))
c=["l5","l21","l63","cred","curva","corto","rinf","rbre"]; tr=T[T[c].notna().all(axis=1)]
X=tr[c].values; y=np.log(tr.rv/tr.n).values
kw=dict(loss="squared_error",learning_rate=0.05,max_iter=300,max_depth=3,min_samples_leaf=20,l2_regularization=1.0,early_stopping=False,random_state=20261030)
p1=HistGradientBoostingRegressor(**kw).fit(X,y).predict(X)
with threadpool_limits(limits=1): p2=HistGradientBoostingRegressor(**kw).fit(X,y).predict(X)
print("GB multi vs 1 hilo, max |dif|:", np.abs(p1-p2).max())
