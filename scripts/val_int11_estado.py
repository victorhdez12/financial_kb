"""Validador INT-11 (30-oct; A POSTERIORI salvo la reproducción; ver docs/validation/2026-10-30_int11.md): estado 'hoy' — PIB total frente a per cápita."""
import sys, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from src.intl.procedencia import procedencia
print("procedencia", procedencia())
from src.intl import data as D, escenarios as E, panel as P
from src.report import escenarios_vivo as V, termometro_vivo as TV
NUC = V.NUCLEO
con = D.connect()
corte = TV.fin_de_mes("2026-10-30")
def obs(sid, hasta=None):
    df = con.execute("select date, value from obs_latest where series_id=? and value is not null order by date", [sid]).df()
    s = pd.Series(df.value.astype(float).values, index=pd.to_datetime(df.date))
    return s if hasta is None else s[s.index <= hasta]
# (1) Concordancia en desarrollo (≤ 2004): brecha OCDE total (4 trimestres) frente a JST per cápita
a = P.anual(con).reset_index()
fil = []
for c in NUC:
    pib = np.log(V.anual_completo(obs(f"oecd_gdpq_{c.lower()}", "2004-12-31"), 4))
    g = a[a.pais == c].set_index("año")
    lp = np.log(g.rgdpmad)
    for t in pib.index:
        if all(t-k in pib.index for k in range(1, 11)) and all(t-k in lp.index for k in range(0, 11)) and t <= 2004:
            bt = pib[t] - np.mean([pib[t-k] for k in range(1, 11)])
            bp = lp[t] - np.mean([lp[t-k] for k in range(1, 11)])
            fil.append((c, t, bt, bp, g.inflacion.get(t, np.nan)))
d = pd.DataFrame(fil, columns=["pais","año","b_total","b_pc","infl"])
d["r_t"] = E.codigo_regimen(d.infl, d.b_total); d["r_pc"] = E.codigo_regimen(d.infl, d.b_pc)
print("dev ≤2004: n", len(d), "años", d.año.min(), d.año.max())
print("diferencia media brecha total − pc (pp):", round(100*(d.b_total - d.b_pc).mean(), 2), " mediana", round(100*(d.b_total-d.b_pc).median(),2))
print("P(brecha<0) total", round((d.b_total<0).mean(),3), " pc", round((d.b_pc<0).mean(),3))
print("acuerdo de régimen", round((d.r_t == d.r_pc).mean(), 3))
print(pd.crosstab(d.r_pc, d.r_t))
# (2) Hoy: brecha per cápita aproximada con población Maddison (≤ 2022) extrapolada con su crecimiento 2012-2022
est = V.estado_actual(con, "2026-10-30")
out = {}
for c in NUC:
    e = est["paises"][c]
    pop = obs(f"maddison_{c.lower()}_pop"); pop.index = pop.index.year
    gpop = np.log(pop[2022] / pop[2012]) / 10
    lpop = {t: (np.log(pop[t]) if t in pop.index else np.log(pop[2022]) + gpop*(t-2022)) for t in range(e["año"]-10, e["año"]+1)}
    pib = np.log(V.anual_completo(obs(f"oecd_gdpq_{c.lower()}", corte), 4))
    t = e["año"]
    bpc = (pib[t]-lpop[t]) - np.mean([pib[t-k]-lpop[t-k] for k in range(1, 11)])
    rpc = E.REGIMENES[int(E.codigo_regimen([e["inflacion"]], [bpc])[0])]
    out[c] = (t, round(100*e["inflacion"],2), round(100*e["brecha_pib_total"],2), round(100*bpc,2), e["regimen"], rpc, round(100*gpop,2))
    print(c, out[c])
