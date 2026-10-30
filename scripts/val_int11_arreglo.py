"""Validador INT-11 (30-oct; A POSTERIORI salvo la reproducción; ver docs/validation/2026-10-30_int11.md): efecto del arreglo de Generador.ajustar (sucesor) y comprobaciones de fuga en LOCO."""
import sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from src.intl.procedencia import procedencia
print("procedencia", procedencia())
from src.intl import data as D, escenarios as E, int11 as Q
from scripts.int11_corrida import cargar_real, SEED
con = D.connect(); f = cargar_real(con)
# (1) bug antiguo sin recalcular: sucesor de un subconjunto LOCO
for c in ["BEL", "DEU", "USA"]:
    sub = f[f.pais != c].reset_index(drop=True)          # comportamiento previo de ajustar
    s = sub["sucesor"].to_numpy(); i = np.flatnonzero(s >= 0)
    malo = (s[i] >= len(sub)) | (sub.pais.to_numpy()[np.minimum(s[i], len(sub)-1)] != sub.pais.to_numpy()[i]) | \
           (sub.año.to_numpy()[np.minimum(s[i], len(sub)-1)] != sub.año.to_numpy()[i] + 1)
    print(f"sin arreglo, fuera {c}: sucesores erróneos {malo.mean():.3f} de {len(i)}")
# (2) corrida oficial (H = 5) con el ajustar ANTIGUO: ¿cambia algo?
orig = E.Generador.ajustar
def ajustar_viejo(self, filas):
    g = orig(self, filas)                     # recalcula; luego deshacemos para imitar el viejo (reset_index sin recalcular)
    return g
ev_new = Q.evaluar_motor(f, "loco", 200, 100, SEED, H=5)
src = E.recalcular_sucesor
E.recalcular_sucesor_backup = src
def ajustar_viejo2(self, filas):
    rs = E.recalcular_sucesor
    E.recalcular_sucesor = lambda d: d.reset_index(drop=True)
    try:
        return orig(self, filas)
    finally:
        E.recalcular_sucesor = rs
E.Generador.ajustar = ajustar_viejo2
ev_old = Q.evaluar_motor(f, "loco", 200, 100, SEED, H=5)
E.Generador.ajustar = orig
for k in ("crps1", "dentro90", "crps1_5", "dentro90_5"):
    a, b = ev_new[k], ev_old[k]
    print(k, "idéntico:", np.array_equal(np.nan_to_num(a, nan=-9), np.nan_to_num(b, nan=-9)))
# (3) fuga: perturbar los datos del país excluido no cambia su predictiva
c = "ESP"; tr = f.pais.values != c
g1 = E.Generador(E.Config()).ajustar(f[tr])
f2 = f.copy(); f2.loc[f2.pais == c, list(E.ACTIVOS)] *= 3; f2.loc[f2.pais == c, "s"] = 0
g2 = E.Generador(E.Config()).ajustar(f2[tr])
e1 = g1.simular(c, 1, horizonte=5, n_lotes=20, por_lote=100, semilla=5).rent
e2 = g2.simular(c, 1, horizonte=5, n_lotes=20, por_lote=100, semilla=5).rent
print("fuga LOCO (predictiva cambia al perturbar el excluido):", not np.array_equal(np.nan_to_num(e1), np.nan_to_num(e2)),
      "| excluido en pool:", c in g1.paises, "| kappa", g1.kappa)
