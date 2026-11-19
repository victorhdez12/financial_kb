"""D1: SENSIBILIDAD DEL VALIDADOR (diagnóstico de validación, 19-nov-2026). NO es una prueba nueva ni cambia el veredicto
registrado de la corrida única (research/factors/d1_desarrollo.json). Solo ≤ 2004 (src/factors/data.py, DEV_END).
Variantes: +1 día de ejecución; oro y ex-US retrasados un día (la posición decidida en d gana el fixing d+1→d+2);
ambas; autocorrelación de orden 1 por activo y década; coste por lado de equilibrio frente a L2 y L1.
Uso: .venv/bin/python scripts/d1_sensibilidad_validador.py"""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, ".")
from src.factors import d1 as M
from src.factors import data as F

meta = json.loads(open("research/factors/d1_series.json").read())["periodo"]
desde, hasta, activos = pd.Timestamp(meta["desde"]), pd.Timestamp(meta["hasta"]), meta["activos"]
con = F.connect(); r_all, rf = F.d1_dev(con); con.close()
assert r_all.index.max() <= pd.Timestamp("2004-12-31") and rf.index.max() <= pd.Timestamp("2004-12-31")
r_all = r_all[activos]
s, sig = M.tendencia(r_all), M.volatilidad(r_all)
dias = r_all.loc[desde:hasta].index
def prep(r_src, dias):
    r = r_src.loc[dias]
    return r.mask(s.shift(1).loc[dias].isna() & r.isna(), 0.0)
obj = M.objetivos(s, sig); obj2 = M.objetivos(s.where(s.isna(), 1.0), sig)
o1, reb = M.l1_objetivos(r_all.index, activos)

def corre(r, objD, objL2, o1, reb, coste=None):
    d1 = M.simular(r, rf, objD, coste_lado=coste); l2 = M.simular(r, rf, objL2, coste_lado=coste)
    l1 = M.simular(r, rf, o1, rebalanceo=reb, coste_lado={k: 0.0 for k in activos})
    return {"D1": d1, "L1": l1, "L2": l2}
def tabla(res, idx=None):
    out = {}
    for k, x in res.items():
        n = x.neto if idx is None else x.neto.loc[idx]
        out[k] = (round(M.sharpe(n, rf), 3), round(M.caida_maxima(n), 3))
    return out
def informe(nombre, res, dd):
    h1, h2 = M.mitades(dd)
    print(nombre, "total", tabla(res), "| mitad1", tabla(res, h1), "| mitad2", tabla(res, h2))
    print("   rot D1", round(res["D1"].rotacion.mean()*252, 2))

# original
r = prep(r_all, dias); base = corre(r, obj, obj2, o1, reb); informe("ORIGINAL", base, dias)
# +1 día de ejecución
lag = lambda o: o.shift(1).fillna(0.0)
dlag = dias[1:]  # necesita objetivo de t-1 desplazado
r1 = prep(r_all, dlag)
res1 = corre(r1, lag(obj), lag(obj2), lag(o1), reb.shift(1).fillna(False).astype(bool)); informe("+1 DIA", res1, dlag)
# oro y ex-US retrasados un día: la posición decidida en d gana r_oro/xus de d+2 (fixing d+1 -> d+2)
r_sh = r_all.copy()
for c in ("oro", "xus"):
    if c in r_sh: r_sh[c] = r_all[c].shift(-1)
dsh = dias[:-1]
r2 = prep(r_sh, dsh)
r2["xus"] = r2["xus"].where(r2["xus"].notna() | (obj["xus"].shift(1).reindex(dsh) == 0), np.nan).fillna(0.0) if "xus" in r2 else None
res2 = corre(r2, obj, obj2, o1, reb); informe("ORO/XUS +1", res2, dsh)
# combinado de los dos
r3 = prep(r_sh, dlag[:-1]); r3["xus"] = r3["xus"].fillna(0.0)
res3 = corre(r3, lag(obj), lag(obj2), lag(o1), reb.shift(1).fillna(False).astype(bool)); informe("+1 DIA y ORO/XUS +1", res3, dlag[:-1])
# solo us+bonos (sincronos) — diagnóstico
# placebos rápidos para variantes
for nom, rr, ss_shift in (("+1 DIA", r1, 1), ("ORO/XUS +1", r2, 0)):
    ssh = s.shift(ss_shift) if ss_shift else s
    sigh = sig.shift(ss_shift) if ss_shift else sig
    pl = M.placebos(rr, rf, ssh, sigh, 200, 20261119)
    sh = M.sharpe((res1 if ss_shift else res2)["D1"].neto, rf)
    print("placebo200", nom, M.percentil_placebo(sh, pl))

# autocorrelación orden 1 por activo y década (rentabilidades crudas)
print("\nAC1 por década")
rr = r_all.loc["1960":"2004"]
ac = rr.groupby((rr.index.year // 10) * 10).apply(lambda g: g.apply(lambda x: x.dropna().autocorr(1)))
print(ac.round(3))
print("AC1 en periodo puntuado:", r_all.loc[dias].apply(lambda x: x.dropna().autocorr(1)).round(3).to_dict())

# coste de equilibrio frente a L2 y L1 (mismo coste por lado en todo)
def dif(c):
    cc = {k: c for k in activos}
    d = M.simular(r, rf, obj, coste_lado=cc); l2 = M.simular(r, rf, obj2, coste_lado=cc)
    return M.sharpe(d.neto, rf), M.sharpe(l2.neto, rf)
for c in (0.0, 0.0005, 0.001, 0.002, 0.003, 0.005, 0.0075, 0.01):
    a, b = dif(c); print(f"coste {c*1e4:.0f} pb/lado: D1 {a:.3f} L2 {b:.3f}  (L1 {M.sharpe(base['L1'].neto, rf):.3f})")
lo, hi = 0.0, 0.05
for _ in range(30):
    m = (lo + hi)/2; a, b = dif(m)
    lo, hi = (m, hi) if a > b else (lo, m)
print("equilibrio vs L2 pb/lado", round(lo*1e4, 1))
lo, hi = 0.0, 0.05; l1s = M.sharpe(base['L1'].neto, rf)
for _ in range(30):
    m = (lo + hi)/2; a, b = dif(m)
    lo, hi = (m, hi) if a > l1s else (lo, m)
print("equilibrio vs L1 pb/lado", round(lo*1e4, 1))
# contribución por activo (bruto) D1 vs L2
for k in ("D1", "L2"):
    x = base[k]; contrib = (x.pesos * r).mean()*252
    print(k, "contrib anual por activo", contrib.round(4).to_dict())
