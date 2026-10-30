"""Validador INT-11 (30-oct; A POSTERIORI salvo la reproducción; ver docs/validation/2026-10-30_int11.md): nulo simulado de la cobertura (reproducción con evaluación propia + sensibilidad heterogénea)."""
import sys, json, time, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from src.intl.procedencia import procedencia
print("procedencia", procedencia())
from src.intl import data as D, escenarios as E, int11 as Q
from scripts.int11_corrida import cargar_real, estructura, NUCLEO, POTENCIA
from scripts.int11_potencia import par_dgp
from scripts.val_int11_repro import evaluar

modo = sys.argv[1]; R = int(sys.argv[2])
med = json.loads(POTENCIA.read_text())["medicion"]
con = D.connect(); f = cargar_real(con)
años, existe, ok = estructura(f)
N, T = len(NUCLEO), len(años)
p = par_dgp(med, 1.0)
# factores de escala propios por país y activo (dispersión del país frente al año, relativa al panel); SOLO Y, sin régimen
fac = np.ones((N, 5))
if modo == "hetero":
    V = f[["pais","año",*E.ACTIVOS]].copy()
    for j, a in enumerate(E.ACTIVOS):
        x = np.log1p(V[a]); dev = x - x.groupby(V["año"]).transform("mean")
        sdc = dev.groupby(V["pais"]).std(); fac[:, j] = (sdc / np.sqrt((dev**2).mean())).reindex(NUCLEO).fillna(1).to_numpy()
    print("factores", dict(zip(NUCLEO, fac[:,0].round(2))))
rng = np.random.default_rng(int(sys.argv[3]) if len(sys.argv) > 3 else 777)
out = []
t0 = time.time()
for r in range(R):
    reg = Q.dgp_regimenes(N, T, med["latente"], rng)
    u = Q.t_multi(T, p["R"], p["nu"], rng) * p["sd_comun"]
    e = Q.t_multi(N*T, p["R"], p["nu"], rng).reshape(N, T, 5) * p["sd_propio"] * fac[:, None, :]
    prev = np.concatenate([np.zeros((N,1), int), reg[:, :-1]], 1)
    Y = p["mu"] + u[None] + e + p["efectos"].T[prev]; Y[:, 0] = np.nan
    fs = Q.filas_sinteticas(reg, Y, NUCLEO, años, existe, ok)
    rr = evaluar(fs, seeds_off=7*r + 13, n_lotes=20)
    out.append({"S5": rr["S5"], "Sb": rr["Sa"][0], "S5_m0": rr["S5_m0"], "Sa": rr["Sa"]})
    if r % 10 == 0: print(r, round(rr["S5"],4), round(rr["Sa"][0],4), round(rr["S5_m0"],4), round(time.time()-t0))
S5 = np.array([o["S5"] for o in out]); Sb = np.array([o["Sb"] for o in out]); M0 = np.array([o["S5_m0"] for o in out])
res = {"modo": modo, "R": R, "S5_banda": np.percentile(S5, [2.5, 97.5]).tolist(), "S5_media": S5.mean(), "S5_sd": S5.std(),
       "Sb_banda": np.percentile(Sb, [2.5, 97.5]).tolist(), "Sb_media": Sb.mean(), "M0_media": M0.mean(), "M0_sd": M0.std(),
       "prop_S5_le_0886": float((S5 <= 0.8862).mean()), "unicos": len(np.unique(S5.round(8)))}
print(json.dumps(res, indent=1, default=float))
json.dump({"res": res, "rep": out}, open(f"research/int/val_int11_nulo_{modo}.json", "w"), default=float)
