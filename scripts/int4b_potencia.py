"""INT-4 ampliado: potencia de los objetivos nuevos (salida de recesión, repunte y vuelta de la inflación), ANTES de
construir nada. Solo datos ≤ 2004. Mismas fórmulas y reglas que scripts/int4_potencia.py (se importan de allí).

Qué usa (y nada más):
  (i)  RECUENTOS de los objetivos nuevos por país-año: salidas de recesión (fechado anual de INT-1), entradas y salidas del
       régimen de inflación alta (etiqueta de INT-1: principal relativa + 2 %, y absoluta 3 % como sensibilidad);
  (ii) COBERTURA de los candidatos nuevos (dinero, salarios, brecha del PIB unilateral, tipo real corto, tipo de cambio).
Qué NO hace nunca: cruzar un indicador con un objetivo. Las dos partes no se juntan salvo la DISPONIBILIDAD (máscaras).
Uso: .venv/bin/python -m scripts.int4b_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int4b_potencia --prueba   (sin puerta; no escribe nada)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.int4_potencia import GUERRAS, NUCLEO, A0S, R_AUC, Z1, Z6, _r, resumen_anual
from src.intl import data as D
from src.intl import panel as P
from src.intl import regimes as G
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
UMBRAL_P = 0.5                    # régimen de inflación alta si p_i_alta ≥ 0,5


def _filtro(t: int, h: int, desde: int, sin_guerras: bool, años: set) -> bool:
    if t < desde or t + h > 2004 or any(t + k not in años for k in range(1, h + 1)):
        return False
    return not (sin_guerras and any(y in GUERRAS for y in range(t, t + h + 1)))


def objetivo_salida_recesion(rec: pd.DataFrame, años_pais: dict, h: int, desde: int, sin_guerras: bool) -> pd.DataFrame:
    """Filas (país, t) EN recesión (pico+1 … valle) con y = 1 si la recesión termina (primer año de crecimiento,
    X = valle + 1) en t+1 … t+h."""
    filas = []
    for c in NUCLEO:
        r = rec[rec.pais == c]
        for _, x in r.iterrows():
            X = int(x.valle) + 1
            for t in range(int(x.pico) + 1, int(x.valle) + 1):
                if not _filtro(t, h, desde, sin_guerras, años_pais[c]):
                    continue
                y = int(t + 1 <= X <= t + h)
                filas.append({"pais": c, "t": t, "y": y, "E": X if y else None, "tipo": x.tipo if y else None})
    return pd.DataFrame(filas)


def objetivo_inflacion(p_i: pd.DataFrame, h: int, desde: int, sin_guerras: bool, sube: bool) -> pd.DataFrame:
    """Filas (país, t) fuera (sube) o dentro (baja) del régimen de inflación alta en t, con y = 1 si el régimen cambia
    en t+1 … t+h (primer año del régimen nuevo)."""
    filas = []
    for c in NUCLEO:
        s = p_i.loc[p_i.pais == c].set_index("año")["p_i_alta"].dropna()
        alta = s >= UMBRAL_P
        años = set(s.index.astype(int))
        cambio = {int(t) for t in alta.index[1:] if alta[t] != alta.get(t - 1, alta[t]) and alta[t] == sube}
        for t in sorted(años):
            if alta[t] == sube or not _filtro(t, h, desde, sin_guerras, años):
                continue
            E = [y for y in range(t + 1, t + h + 1) if y in cambio]
            filas.append({"pais": c, "t": t, "y": int(bool(E)), "E": E[0] if E else None, "tipo": None})
    return pd.DataFrame(filas)


def etiquetas_inflacion(a: pd.DataFrame) -> dict:
    out = {"principal": [], "abs3": []}
    for c in NUCLEO:
        x = a.loc[c]
        for nom, kw in (("principal", {}), ("abs3", {"umbral_i": G.UMBRAL_I_ABSOLUTO, "relativa": False})):
            e = G.etiqueta(np.log(x["rgdpmad"]), x["inflacion"], G.VENTANA_ANUAL, **kw)
            out[nom].append(e[["p_i_alta", "truncada"]].assign(pais=c).reset_index(names="año"))
    return {k: pd.concat(v, ignore_index=True) for k, v in out.items()}


def candidatos_nuevos(con, a: pd.DataFrame) -> pd.DataFrame:
    """Candidatos nuevos (solo valores observados hasta t; brecha unilateral con la media de t−10 … t−1)."""
    extra = {}
    for v in ("money", "wage", "xrusd"):
        s = {c: D.load_dev(con, f"jst_{c.lower()}_{v}") for c in D.PAISES}
        s = pd.concat({c: x.set_axis(x.index.year) for c, x in s.items() if not x.empty})
        s.index.names = ["pais", "año"]
        extra[v] = s
    x = a.join(pd.DataFrame(extra), how="left")
    g = x.groupby(level=0)
    ind = pd.DataFrame(index=x.index)
    ind["P1_dinero_g"] = g["money"].transform(lambda s: np.log(s).diff())
    ind["P2_salario_g"] = g["wage"].transform(lambda s: np.log(s).diff())
    lp = np.log(x["rgdpmad"])
    ind["P3_brecha_unilateral"] = lp - lp.groupby(level=0).transform(lambda s: s.shift(1).rolling(10, min_periods=10).mean())
    ind["P5_tipo_real_corto"] = x["stir"] / 100 - x["inflacion"]
    dep = g["xrusd"].transform(lambda s: np.log(s).diff())
    ind["X_depreciacion_usd"] = dep.where(ind.index.get_level_values(0) != "USA")      # EE. UU.: no definido
    ind["S4_difusion_caidas_pib"] = np.nan
    caida = (x["pib_real_g"] < 0).astype(float).where(x["pib_real_g"].notna()).unstack(0)
    nuc = caida[[k for k in caida.columns if k in NUCLEO]]
    for c in D.PAISES:
        otros = nuc[[k for k in nuc.columns if k != c]]
        v = otros.mean(axis=1).where(otros.notna().sum(axis=1) >= 5)
        idx = ind.index[ind.index.get_level_values(0) == c]
        ind.loc[idx, "S4_difusion_caidas_pib"] = v.reindex(idx.get_level_values(1)).to_numpy(dtype=float)
    return ind.loc[ind.index.get_level_values(1) <= 2004]


def cobertura(ind: pd.DataFrame) -> dict:
    nuc = ind[ind.index.get_level_values(0).isin(NUCLEO)]
    años = nuc.index.get_level_values(1)
    out = {}
    for col in nuc.columns:
        ok = nuc[col].notna()
        primero = nuc[col].dropna().reset_index().groupby("pais")["año"].min()
        out[col] = {"pais_años_nucleo_1870_2004": int(ok.sum()), "pais_años_nucleo_1950_2004": int(ok[años >= 1950].sum()),
                    "primer_año": {k: int(v) for k, v in primero.items()}}
    return out


def main() -> None:
    borrador = "--prueba" in sys.argv
    proc = procedencia(exigir_limpio=not borrador)
    con = D.connect()
    a = P.anual(con)
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in NUCLEO}
    et = etiquetas_inflacion(a)
    ind = candidatos_nuevos(con, a)
    con.close()
    res: dict = {"procedencia": proc, "nucleo": NUCLEO,
                 "supuestos": {"A0_listón_supuestas": list(A0S), "r_entre_auc": R_AUC, "z_1": _r(Z1), "z_holm6": _r(Z6),
                               "umbral_p_inflacion_alta": UMBRAL_P}, "objetivos": {}}
    # máscaras de disponibilidad (nunca valores): núcleo de candidatos de salida e inflación
    m_infl = set(ind.index[ind[["P1_dinero_g", "P2_salario_g", "P3_brecha_unilateral", "P5_tipo_real_corto"]].notna().all(axis=1)])
    for nom, desde, sg in (("1871_2004_sin_guerras", 1871, True), ("1950_2004", 1950, False)):
        b = res["objetivos"].setdefault(nom, {})
        for h in (1, 2):
            b[f"salida_recesion_h{h}"] = resumen_anual(objetivo_salida_recesion(rec, años_pais, h, desde, sg))
            for lab, df in et.items():
                for sube, k in ((True, "repunte"), (False, "vuelta")):
                    obj = objetivo_inflacion(df, h, desde, sg, sube)
                    b[f"inflacion_{k}_{lab}_h{h}"] = resumen_anual(obj)
                    if lab == "principal" and h == 1:
                        tr = df.set_index(["pais", "año"])["truncada"]
                        no_tr = obj[[not bool(tr.get((p, t + 1), True)) for p, t in zip(obj.pais, obj.t)]]
                        b[f"inflacion_{k}_principal_h1_sin_truncadas"] = resumen_anual(no_tr)
                        con_dat = obj[[(p, t) in m_infl for p, t in zip(obj.pais, obj.t)]]
                        b[f"inflacion_{k}_principal_h1_con_P1_P2_P3_P5"] = resumen_anual(con_dat)
    res["cobertura_candidatos_nuevos"] = cobertura(ind)
    if not borrador:
        (REPO / "research" / "int" / "int4b_potencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for nom, b in res["objetivos"].items():
        print("==", nom)
        for k, v in b.items():
            print(f"  {k:44s} filas={v['filas_en_riesgo']} ev={v['eventos']} años_ev={v['años_distintos_con_evento']} "
                  f"base={v['tasa_base_filas']} DE={v['efecto_diseño']} "
                  f"MDE(A0=.6/.7) c={v['mde_central']['A0=0.60']}/{v['mde_central']['A0=0.70']} "
                  f"p={v['mde_prudente']['A0=0.60']}")
    print({k: (v["pais_años_nucleo_1870_2004"], v["pais_años_nucleo_1950_2004"]) for k, v in res["cobertura_candidatos_nuevos"].items()})


if __name__ == "__main__":
    main()
