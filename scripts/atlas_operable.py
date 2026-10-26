"""Atlas §8: versión OPERABLE de la columna t − 1 (DESCRIPTIVO declarado a posteriori; corrección del usuario 26-oct).
La etiqueta principal de INT-1 usa una ventana centrada (t − 5 … t + 5), así que su valor en t − 1 no se conocía a tiempo.
Aquí el estado de t − 1 se define SOLO con datos observados hasta t − 1 (JST anual, conocido el 30 de abril de t;
la rentabilidad del año t empieza en enero: ≈ 4 meses de solape, declarado; sensibilidad estricta con t − 2):
  (a) inflación alta: inflación observada (Δlog IPC) de t − 1 > 3 %  → bonos, letras, bolsa;
  (a') estanflación: (a) y brecha unilateral P3(t − 1) < 0 (log PIB pc − media de t − 11 … t − 2)  → bolsa;
  (b) desinflación / crecimiento bajo: P3(t − 1) < 0 e inflación(t − 1) < inflación(t − 2)  → bonos.
Misma muestra que INT-3 (núcleo, 1876-1999, filas de la corrida). Inferencia: Driscoll-Kraay (src/intl/int3) y p
calibrado con el placebo desplazado: φ = desviación típica de las t de Driscoll-Kraay de los estados desplazados
(k ≥ DESFASE_MIN, misma k en todos los países), p_cal = 2·P(|t_{T−1}| ≥ |t|/φ); y p por rangos. Holm sobre los 5.
No cambia ningún resultado ni prerregistro.
Uso: .venv/bin/python -m scripts.atlas_operable
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from scripts import int3_corrida as C
from src.intl import data as D
from src.intl import int3 as I
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UMBRAL = 0.03


def estados(anual: pd.DataFrame, rezago: int) -> pd.DataFrame:
    a = anual.reset_index().sort_values(["pais", "año"])
    g = a.groupby("pais")
    lp = np.log(a["rgdpmad"])
    brecha = lp - lp.groupby(a.pais).transform(lambda s: s.shift(1).rolling(10, min_periods=10).mean())
    infl = a["inflacion"]
    base = pd.DataFrame({"pais": a.pais, "anio": a["año"], "infl": infl, "brecha": brecha,
                         "infl_baja_vs_prev": infl < g["inflacion"].shift(1)})
    out = base[["pais", "anio"]].copy()
    for c in ("infl", "brecha", "infl_baja_vs_prev"):
        out[c] = base.groupby("pais")[c].shift(rezago)
    ok = out.infl.notna() & out.brecha.notna()
    out["infl_alta"] = (out.infl > UMBRAL).where(ok)
    out["estanfl"] = ((out.infl > UMBRAL) & (out.brecha < 0)).where(ok)
    out["desinfl"] = ((out.brecha < 0) & out.infl_baja_vs_prev.astype(bool)).where(ok & a.groupby("pais")["inflacion"].shift(rezago + 1).notna())
    return out


CONTRASTES = {"Qa_bono_infl_alta": ("bono", "infl_alta", -1), "Qa_letra_infl_alta": ("letra", "infl_alta", -1),
              "Qa_bolsa_infl_alta": ("bolsa", "infl_alta", -1), "Qa2_bolsa_estanfl": ("bolsa", "estanfl", -1),
              "Qb_bono_desinfl": ("bono", "desinfl", +1)}


def evaluar(f: pd.DataFrame) -> dict:
    out = {}
    for q, (yv, est, signo) in CONTRASTES.items():
        m = f[est].notna() & f[yv].notna()
        g = f[m]
        y, d, pais, anio = g[yv], g[est].astype(float), g.pais, g.anio
        r = I.driscoll_kraay(y, d, pais, anio)
        L = int(anio.max() - anio.min() + 1)
        ts = []
        for k in range(I.DESFASE_MIN, L - I.DESFASE_MIN + 1):
            dk = I.desplazar(d, pais, anio, k)
            if dk.sum() >= 10 and (dk == 0).sum() >= 10:
                ts.append(I.driscoll_kraay(y, dk, pais, anio)["t"])
        ts = np.array(ts)
        phi = float(np.std(ts, ddof=1))
        r["phi"] = phi
        r["p_cal"] = float(2 * stats.t.sf(abs(r["t"]) / phi, r["años"] - 1))
        r["p_rangos"] = float((1 + (np.abs(ts) >= abs(r["t"])).sum()) / (1 + len(ts)))
        r["desplazamientos"] = int(len(ts))
        r["años_en_estado"] = int(d.sum())
        r["filas"] = int(len(d))
        r["signo_esperado"] = signo
        ef = I.efectos_pais(y, d, pais)
        r["paises_signo_sin_encoger"] = f"{int((np.sign(ef.efecto) == signo).sum())}/{len(ef)}"
        m50 = anio >= 1950
        r["dk_1950_1999"] = I.driscoll_kraay(y[m50], d[m50], pais[m50], anio[m50])["efecto"]
        out[q] = r
    return out


def main() -> None:
    proc = procedencia()
    con = D.connect()
    anual = P.anual(con)
    con.close()
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    f0 = C.tabla(anual, et, rec)
    f0 = f0[f0.pais.isin(C.NUCLEO) & f0.cuadrante.notna() & ~f0.truncada.fillna(True).astype(bool)]  # filas de INT-3
    res = {"procedencia": proc, "nota": "DESCRIPTIVO declarado a posteriori; no cambia nada", "umbral_inflacion": UMBRAL}
    for nom, rz in (("t_menos_1", 1), ("t_menos_2_estricto", 2)):
        f = f0.merge(estados(anual, rz), on=["pais", "anio"], how="left")
        res[nom] = evaluar(f)
        res[nom + "_holm_p_cal"] = I.holm({q: v["p_cal"] for q, v in res[nom].items()})
    (REPO / "research" / "int" / "atlas_operable.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    for nom in ("t_menos_1", "t_menos_2_estricto"):
        for q, v in res[nom].items():
            print(nom, q, f"{100*v['efecto']:+.1f} [{100*v['ic95'][0]:+.1f}; {100*v['ic95'][1]:+.1f}] p_dk={v['p']:.4f} "
                  f"phi={v['phi']:.2f} p_cal={v['p_cal']:.4f} p_rangos={v['p_rangos']:.3f} n_estado={v['años_en_estado']} "
                  f"paises={v['paises_signo_sin_encoger']} 1950-99={100*v['dk_1950_1999']:+.1f} holm={res[nom+'_holm_p_cal'][q]}")


if __name__ == "__main__":
    main()
