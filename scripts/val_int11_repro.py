"""Validador INT-11 (30-oct; A POSTERIORI salvo la reproducción; ver docs/validation/2026-10-30_int11.md): reproducción con código propio (datos, régimen, evaluación LOCO, CRPS, cobertura, DM)."""
import sys, json, time, warnings
import numpy as np, pandas as pd
from scipy import stats
warnings.filterwarnings("ignore")
from src.intl.procedencia import procedencia
print("procedencia", procedencia())
from src.intl import data as D, panel as P, activos3b as A3, escenarios as E
from scripts.int11_corrida import cargar_real

NUC = ["BEL","DEU","DNK","ESP","FIN","FRA","GBR","ITA","JPN","NLD","NOR","PRT","SWE","USA"]
ACT = ["bolsa","bonos","letras","vivienda","oro"]
SEED = 20261030

def crps_pwm(x, y):
    x = np.sort(x[np.isfinite(x)]); n = len(x); i = np.arange(1, n+1)
    y = np.atleast_1d(y)
    # CRPS(F_n,y) = 2/n^2 * sum_i (x_i - y) (n*1{y<x_i} - i + 1/2)
    return np.array([2.0/n**2 * np.sum((x - yy) * (n*(yy < x) - i + 0.5)) for yy in y])

def dm(d, años, lags=2):
    d = np.asarray(d); m = d.mean(); u = np.unique(años)
    s = np.array([np.sum(d[años == a] - m) for a in u])
    v = np.sum(s**2) + sum(2*(1-l/(lags+1))*np.sum(s[l:]*s[:-l]) for l in range(1, lags+1))
    se = np.sqrt(v)/len(d); t = m/se
    return dict(m=m, t=t, p=stats.t.sf(t, len(u)-1), años=len(u))

def regimen_propio(con):
    """Régimen operable P3 recalculado a mano desde JST."""
    a = P.anual(con).reset_index()
    a = a[a.pais.isin(NUC)].sort_values(["pais","año"])
    out = {}
    for c, g in a.groupby("pais"):
        g = g.set_index("año")
        lp = np.log(g["rgdpmad"])
        br = {}
        for t in g.index:
            prev = [t-k for k in range(1, 11)]
            if all(p in lp.index and np.isfinite(lp[p]) for p in prev) and np.isfinite(lp[t]):
                br[t] = lp[t] - np.mean([lp[p] for p in prev])
        for t in g.index:
            inf = g.loc[t, "inflacion"]
            if t in br and np.isfinite(inf):
                out[(c, t)] = (2 if inf > .03 else 3) if br[t] < 0 else (1 if inf > .03 else 0)
    return out

def evaluar(f, seeds_off=0, n_lotes=200, cfg=None, diseño="loco", qmethod="linear"):
    f = E.recalcular_sucesor(f)
    V = f[ACT].to_numpy(float); paises = sorted(f.pais.unique())
    m = len(f)
    c0 = np.full((m,5), np.nan); c1 = c0.copy(); d90 = c0.copy(); d90m0 = c0.copy()
    if diseño == "loco":
        folds = [(k, f.pais.values != c, f.pais.values == c) for k, c in enumerate(paises)]
    else:
        folds = [(0, f.año.values < 1950, f.año.values >= 1950)]
    for k, tr, te in folds:
        gen = E.Generador(cfg or E.Config()).ajustar(f[tr])
        assert not set(gen.paises) & set(f.pais.values[te]) if diseño == "loco" else True
        Vtr = V[tr]
        te_idx = np.flatnonzero(te)
        for (c, s0), pos in f.iloc[te_idx].groupby(["pais","s_prev"]).indices.items():
            idx = te_idx[pos]
            sem = SEED + 1000*k + 10*paises.index(c) + int(s0) + seeds_off
            esc = gen.simular(c, int(s0), horizonte=1, n_lotes=n_lotes, por_lote=100, semilla=sem)
            R1 = esc.rent[:,0,:]
            for j in range(5):
                y = V[idx, j]; ok = np.isfinite(y)
                x1 = R1[np.isfinite(R1[:,j]), j]; x0 = Vtr[np.isfinite(Vtr[:,j]), j]
                if not ok.any() or len(x0) < 30 or len(x1) < 30: continue
                ii = idx[ok]
                c0[ii,j] = crps_pwm(x0, y[ok]); c1[ii,j] = crps_pwm(x1, y[ok])
                q = np.quantile(x1, [.05,.95], method=qmethod); q0 = np.quantile(x0, [.05,.95], method=qmethod)
                d90[ii,j] = (y[ok] >= q[0]) & (y[ok] <= q[1]); d90m0[ii,j] = (y[ok] >= q0[0]) & (y[ok] <= q0[1])
    usa = np.isfinite(c0).any(1)
    esc_ = np.nanmean(c0[usa], 0)
    d = np.nanmean((c0[usa]-c1[usa])/esc_, 1)
    r = dm(d, f.año.values[usa])
    fila = np.isfinite(d90).any(1)
    return dict(S5=float(np.mean(np.nanmean(d90[fila],1))), Sa=np.nanmean(d90,0).round(4).tolist(),
                S5_m0=float(np.mean(np.nanmean(d90m0[fila],1))), Sa_m0=np.nanmean(d90m0,0).round(4).tolist(),
                crpss=(100*(1-np.nanmean(c1[usa],0)/esc_)).round(3).tolist(),
                crpss_medio=float(100*np.nanmean(1-np.nanmean(c1[usa],0)/esc_)), dm=r, n=int(usa.sum()),
                cob_pais={c: float(np.nanmean(np.nanmean(d90[fila & (f.pais.values==c)],1))) for c in paises},
                cob_pais_m0={c: float(np.nanmean(np.nanmean(d90m0[fila & (f.pais.values==c)],1))) for c in paises})

if __name__ == "__main__":
    t0 = time.time()
    con = D.connect()
    f = cargar_real(con)
    print("filas", len(f), f.año.min(), f.año.max())
    rp = regimen_propio(con)
    sp = np.array([rp.get((c, a-1), -1) for c, a in zip(f.pais, f.año)])
    ss = np.array([rp.get((c, a), -1) for c, a in zip(f.pais, f.año)])
    print("s_prev coincide:", (sp == f.s_prev.values).mean(), " s coincide:", (ss == f.s.values).mean())
    print("frecuencias s_prev:", np.bincount(f.s_prev, minlength=4))
    modo = sys.argv[1] if len(sys.argv) > 1 else "base"
    res = {}
    if modo == "base":
        res["loco_mismas_semillas"] = evaluar(f)
        print(json.dumps(res, default=float)[:3000]); print(time.time()-t0)
        res["temporal"] = evaluar(f, diseño="temporal")
        for off in (1, 2):
            res[f"loco_semillas+{off}e5"] = evaluar(f, seeds_off=off*100000)
        res["loco_inverted_cdf"] = evaluar(f, qmethod="inverted_cdf")
        res["loco_sin_incertidumbre"] = evaluar(f, cfg=E.Config(incertidumbre=False))
        res["loco_20_lotes"] = evaluar(f, n_lotes=20)
    json.dump(res, open(f"research/int/val_int11_repro_{modo}.json","w"), default=float, indent=1)
    for k, v in res.items():
        print(k, "S5", round(v["S5"],4), "Sa", v["Sa"], "M0", round(v["S5_m0"],4), "CRPSS", round(v["crpss_medio"],3), "d", round(v["dm"]["m"],5), "t", round(v["dm"]["t"],3), "p", round(v["dm"]["p"],4))
    print("seg", time.time()-t0)
