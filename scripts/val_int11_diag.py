"""Validador INT-11 (30-oct; A POSTERIORI salvo la reproducción; ver docs/validation/2026-10-30_int11.md): ¿de dónde sale la estrechez de M1 en LOCO? (a posteriori, informativo)."""
import sys, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from src.intl.procedencia import procedencia
print("procedencia", procedencia())
from src.intl import data as D, escenarios as E, int11 as Q
from scripts.int11_corrida import cargar_real, SEED
from scripts.val_int11_repro import evaluar
con = D.connect(); f = cargar_real(con)
# (0) reproducción exacta con la función oficial (H = 5, mismas semillas)
ev = Q.evaluar_motor(f, "loco", 200, 100, SEED, H=5, corte=1950); r = Q.resumen_motor(ev)
print("OFICIAL repro exacta: S5", r["S5"], "Sb", r["Sb"], "d", r["d_media"], "p", r["dm"]["p_unilateral"], "crpss", r["crpss_medio_%"])
# (a) distribución empírica por régimen conocido s_prev (pool de los otros 13 países), sin motor
A = list(E.ACTIVOS); V = f[A].to_numpy(float); din = np.full_like(V, np.nan)
for c in f.pais.unique():
    tr, te = f.pais.values != c, f.pais.values == c
    for i in range(4):
        pool = V[tr & (f.s_prev.values == i)]
        if len(pool) < 30: pool = V[tr]
        m = te & (f.s_prev.values == i)
        for j in range(5):
            x = pool[np.isfinite(pool[:, j]), j]; y = V[m, j]; ok = np.isfinite(y)
            if len(x) < 30 or not ok.any(): continue
            q = np.quantile(x, [.05, .95]); ii = np.flatnonzero(m)[ok]
            din[ii, j] = (y[ok] >= q[0]) & (y[ok] <= q[1])
fila = np.isfinite(din).any(1)
print("(a) empírica por s_prev: S5", np.mean(np.nanmean(din[fila], 1)), np.nanmean(din, 0).round(4))
for nombre, cfg in [("(b) motor con celdas = todo (n_min 10^6)", E.Config(n_min_celda=10**6)),
                    ("(c) motor sin incertidumbre ni celdas", E.Config(n_min_celda=10**6, incertidumbre=False)),
                    ("(d) motor n_min 200", E.Config(n_min_celda=200))]:
    rr = evaluar(f, n_lotes=50, cfg=cfg)
    print(nombre, "S5", round(rr["S5"], 4), rr["Sa"], "M0", round(rr["S5_m0"], 4), "crpss", round(rr["crpss_medio"], 3))
