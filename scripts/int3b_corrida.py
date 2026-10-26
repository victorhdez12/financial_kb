"""Corrida ÚNICA de P-DEV-INT3b v1.0 (docs/int/INT3b_prerregistro_v0.md, aprobado y congelado en fa6d4c9).
INT-3b (B1-B4) e INT-3c (C1, C3, C4, C5), descriptivas (§2.3, §4.3) y sensibilidades (§5.2). Exige el árbol limpio.
Salida: research/int/int3b_resultado.json y .md, y una línea en research/trial_log.md.
Uso: .venv/bin/python -m scripts.int3b_corrida
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import activos3b as A
from src.intl import data as D
from src.intl import int3 as I
from src.intl import int3b as B
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
PRUEBA = ["AUS", "CHE"]
INFL_ALTA = {"sobrecalentamiento", "estanflacion"}
GUERRA = set(range(1914, 1919)) | set(range(1939, 1946))
GUERRA_FX = set(range(1914, 1920)) | set(range(1939, 1950))
HIPER = 0.5
DESDE, HASTA = 1877, 1999
ESTADOS = ("infl_alta", "estanflacion", "crec_bajo", "recesion")

# id → (bloque, variable, estado, signo, familia)
PRINCIPAL = {
    "B1": ("mundial", "mp_real", "infl_alta", +1, "INT3b"),
    "B2": ("mundial", "mp_real", "recesion", -1, "INT3b"),
    "B3": ("oro", "oro_log", "infl_alta", +1, "INT3b"),
    "B4": ("credito", "exceso_credito", "recesion", -1, "INT3b"),
    "C1": ("descomp", "eq_valoracion", "estanflacion", -1, "INT3c"),
    "C3": ("descomp", "bono_capital", "infl_alta", -1, "INT3c"),
    "C4": ("descomp", "bono_capital", "crec_bajo", +1, "INT3c"),
    "C5": ("mundial", "mp_spot_exceso_suma", "infl_alta", +1, "INT3c"),
}


# ------------------------------------------------------------------ regímenes
def estados_pais(et: pd.DataFrame, rec: pd.DataFrame, paises: list[str], desde_pico: int = 1) -> pd.DataFrame:
    et = et[et.pais.isin(paises) & et.cuadrante.notna() & ~et.truncada.fillna(True).astype(bool)].reset_index(drop=True)
    en_rec = {(r.pais, y) for _, r in rec.iterrows() for y in range(int(r.pico) + desde_pico, int(r.valle) + 1)}
    return pd.DataFrame({"pais": et.pais.values, "año": et.año.values.astype(int), "cuadrante": et.cuadrante.values,
                         "infl_alta": et.cuadrante.isin(INFL_ALTA).values.astype(float),
                         "estanflacion": (et.cuadrante == "estanflacion").values.astype(float),
                         "crec_bajo": (et.cuadrante == "crecimiento_bajo").values.astype(float),
                         "recesion": np.array([(p, y) in en_rec for p, y in zip(et.pais, et.año)], dtype=float)})


def cuota(pa: pd.DataFrame, pesos: pd.DataFrame | None = None) -> pd.DataFrame:
    n = pa[pa.pais.isin(NUCLEO)]
    if pesos is None:
        return n.groupby("año")[list(ESTADOS)].mean()
    n = n.merge(pesos, on=["pais", "año"], how="inner")
    return n.groupby("año").apply(lambda g: pd.Series({e: np.average(g[e], weights=g.pib) for e in ESTADOS}))


def modal(pa: pd.DataFrame) -> pd.Series:
    return pa[pa.pais.isin(NUCLEO)].groupby("año").cuadrante.agg(lambda s: s.value_counts().idxmax())


def con_estado(f: pd.DataFrame, pa: pd.DataFrame, rezago: int = 0) -> pd.DataFrame:
    e = pa.copy()
    e["año"] = e["año"] + rezago                      # rezago = 1: régimen de t − 1 unido al año t (por año, no por fila)
    return f.merge(e, on=["pais", "año"], how="inner")


def _resumen(r: dict) -> dict:
    out = {k: r[k] for k in ("efecto", "ic95", "p") if k in r}
    if "placebo" in r:
        out["p_cal"] = r["placebo"]["p_cal"]
    return out


def main() -> None:
    proc = procedencia()
    con = D.connect()
    mu = A.mundial(con)
    oro = A.oro_panel(con, NUCLEO + PRUEBA)
    cre = A.credito(con)
    cre10 = A.credito(con, n_uk=10)
    carry = A.credito_carry(con)
    dc = A.descomp(con, NUCLEO + PRUEBA)
    pib = A.pib_nivel(con, NUCLEO)
    letra_us = A._jst(con, "USA", "bill_rate")
    pi_us = A.inflacion_jst(con, "USA")
    con.close()
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    pa = estados_pais(et, rec, NUCLEO + PRUEBA)
    pa_pv = estados_pais(et, rec, NUCLEO + PRUEBA, desde_pico=0)
    S, S_pv, S_pib = cuota(pa), cuota(pa_pv), cuota(pa, pib)
    usa = pa[pa.pais == "USA"].set_index("año")

    # --- datos de cada bloque (reglas de §3)
    mu = mu[(mu.index >= DESDE) & (mu.index <= HASTA)].copy()
    mu["mp_letra_real_resto"] = mu.mp_real - mu.mp_spot_exceso_suma - mu.mp_carry_suma
    oro = oro[~(oro.inflacion > HIPER) & oro.año.between(DESDE, HASTA)].copy()
    oro["oro_log"] = np.log1p(oro.oro_real_local)
    cre = cre[cre.año.between(DESDE, HASTA)]
    cre10 = cre10[cre10.año.between(DESDE, HASTA)]
    dc = dc[~(dc.inflacion > HIPER) & dc.año.between(DESDE, HASTA)].copy()
    dc["viv_menos_bolsa_capital"] = dc.viv_precio_real - (dc.eq_div_real + dc.eq_valoracion)
    bloques = {"oro": oro, "credito": cre, "descomp": dc}

    def panel(bloque: str, col: str, est: str, muestra=NUCLEO, estados=pa, filtro=None, **kw) -> dict:
        f = bloques[bloque] if not isinstance(bloque, pd.DataFrame) else bloque
        f = con_estado(f[f.pais.isin(muestra)], estados)
        if filtro is not None:
            f = f[filtro(f)]
        return B.panel_contraste(f, col, est, **kw)

    def mundial(col: str, est: str, X: pd.DataFrame = S, filtro=None, **kw) -> dict:
        y = mu[col]
        if filtro is not None:
            y = y[filtro(y.index)]
        return B.ts_contraste(y, X[est], **kw)

    res: dict = {"procedencia": proc, "prerregistro": "docs/int/INT3b_prerregistro_v0.md v1.0 (fa6d4c9)",
                 "unidades": "fracción por año (×100 = pp); en las series mundiales, efecto de pasar de 0 % a 100 % de "
                             "países del núcleo en el estado"}

    # --- principal
    princ = {}
    for q, (bl, col, est, signo, fam) in PRINCIPAL.items():
        r = mundial(col, est) if bl == "mundial" else panel(bl, col, est)
        r.update({"bloque": bl, "variable": col, "estado": est, "signo_esperado": signo, "familia": fam})
        if bl == "mundial":
            r["por_dt_cuota"] = r["efecto"] * float(S.loc[mu[col].dropna().index.intersection(S.index), est].std())
            x = (S[est] >= 0.5).astype(float)
            r["lectura_mayoria"] = {k: v for k, v in B.ts_contraste(mu[col], x, placebo=False).items()
                                    if k in ("efecto", "ic95", "p", "n_años")}
            r["lectura_mayoria"]["años_mayoria"] = int(x.loc[mu[col].dropna().index.intersection(x.index)].sum())
        princ[q] = r
    holm = {}
    for fam in ("INT3b", "INT3c"):
        holm.update(I.holm({q: r["placebo"]["p_cal"] for q, r in princ.items() if r["familia"] == fam}))
    for q, r in princ.items():
        r["holm_ok"] = bool(holm[q])
        r["criterios"] = B.criterios(r, r["signo_esperado"], holm[q], mundial=r["bloque"] == "mundial",
                                     dos_paises=r["bloque"] == "credito")
    res["principal"] = princ

    # --- secundaria: régimen de t − 1
    sec = {}
    for q, (bl, col, est, signo, fam) in PRINCIPAL.items():
        if bl == "mundial":
            X1 = S.copy()
            X1.index = X1.index + 1
            sec[q] = _resumen(B.ts_contraste(mu[col], X1[est], placebo=False))
        else:
            f = con_estado(bloques[bl][bloques[bl].pais.isin(NUCLEO)], pa, rezago=1)
            sec[q] = _resumen(B.panel_contraste(f, col, est, placebo=False, paises=False))
    res["secundaria_regimen_t_menos_1"] = sec

    # --- descriptivas INT-3b (§2.3)
    desc = {}
    desc["B5_petroleo_real_infl_alta_cuota"] = _resumen(mundial("petroleo_real", "infl_alta"))
    oro_usd = pd.concat({"y": mu.oro_usd_real, "x": usa.infl_alta}, axis=1).dropna()
    oro_usd = oro_usd[oro_usd.index >= 1972]
    desc["oro_usd_1972_1999_infl_alta_USA"] = _resumen(B.ts_contraste(oro_usd.y, oro_usd.x, placebo=False))
    for q in ("B1", "B2"):
        est = PRINCIPAL[q][2]
        desc[f"{q}_century_1927"] = _resumen(mundial("cfp_real", est))
        desc[f"{q}_regimen_USA"] = _resumen(B.ts_contraste(mu.mp_real, usa[est], placebo=False))
    desc["credito_real_recesion"] = _resumen(panel("credito", "corp_real", "recesion", placebo=False, paises=False))
    desc["credito_exceso_infl_alta"] = _resumen(panel("credito", "exceso_credito", "infl_alta", placebo=False,
                                                      paises=False))
    tabla = {}
    mm = modal(pa)
    for col in ("mp_real", "cfp_real", "petroleo_real", "oro_usd_real", "mp_carry_suma"):
        g = pd.concat({"y": mu[col], "q": mm}, axis=1).dropna().groupby("q").y
        tabla[col + " (cuadrante mundial modal)"] = g.agg(["count", "mean", "std", "min"]).round(4).to_dict("index")
    for bl, col in (("oro", "oro_log"), ("credito", "corp_real"), ("credito", "exceso_credito")):
        f = con_estado(bloques[bl][bloques[bl].pais.isin(NUCLEO)], pa)
        tabla[col] = f.groupby("cuadrante")[col].agg(["count", "mean", "std", "min"]).round(4).to_dict("index")
    desc["tabla_por_cuadrante"] = tabla
    res["descriptivas_INT3b"] = desc

    # --- descriptivas INT-3c (§4.3): reparto de cada efecto total en sus piezas (mismas filas para todas las piezas)
    def reparto(f: pd.DataFrame, est: str, total: str, piezas: list[str], tipo: str) -> dict:
        g = f.dropna(subset=[total] + piezas)
        if tipo == "mundial":
            ef = {c: B.ts_contraste(g[c], S[est], placebo=False)["efecto"] for c in [total] + piezas}
        else:
            ef = {c: B.panel_contraste(g, c, est, placebo=False, paises=False)["efecto"] for c in [total] + piezas}
        return {"estado": est, "total": ef[total], "piezas": {c: ef[c] for c in piezas},
                "pct_del_total": {c: (ef[c] / ef[total] if ef[total] else None) for c in piezas},
                "suma_piezas_menos_total": sum(ef[c] for c in piezas) - ef[total], "n": int(len(g))}

    dcn = con_estado(dc[dc.pais.isin(NUCLEO)], pa)
    rep = {
        "Q1_bolsa_estanflacion": reparto(dcn, "estanflacion", "eq_total", ["eq_ingreso", "eq_div_real", "eq_valoracion"], "p"),
        "Q2_bono_infl_alta": reparto(dcn, "infl_alta", "bono_total", ["bono_cupon_real", "bono_capital"], "p"),
        "Q3_bono_crec_bajo": reparto(dcn, "crec_bajo", "bono_total", ["bono_cupon_real", "bono_capital"], "p"),
    }
    dcn = dcn.assign(viv_menos_bolsa_total=dcn.viv_total - dcn.eq_total,
                     viv_menos_bolsa_ingreso=dcn.viv_alquiler - dcn.eq_ingreso)
    rep["Q6_viv_menos_bolsa_infl_alta"] = reparto(dcn, "infl_alta", "viv_menos_bolsa_total",
                                                  ["viv_menos_bolsa_ingreso", "viv_menos_bolsa_capital"], "p")
    con = D.connect()
    let = []
    for c in NUCLEO:
        b = A._jst(con, c, "bill_rate")
        p = A.inflacion_jst(con, c)
        let.append(pd.DataFrame({"pais": c, "año": b.index, "letra_nominal_log": np.log1p(b).values,
                                 "menos_inflacion_log": -np.log1p(p.reindex(b.index)).values,
                                 "inflacion": p.reindex(b.index).values}))
    con.close()
    let = pd.concat(let, ignore_index=True)
    let = let[~(let.inflacion > HIPER) & let.año.between(DESDE, HASTA)]
    let["letra_real_log"] = let.letra_nominal_log + let.menos_inflacion_log
    rep["Q4_letra_infl_alta"] = reparto(con_estado(let, pa), "infl_alta", "letra_real_log",
                                        ["letra_nominal_log", "menos_inflacion_log"], "p")
    rep["B1_materias_primas_infl_alta"] = reparto(mu.copy(), "infl_alta", "mp_real",
                                                  ["mp_spot_exceso_suma", "mp_carry_suma", "mp_letra_real_resto"],
                                                  "mundial")
    cr = cre.merge(carry, on=["pais", "año"], how="inner")
    cr["precio_diferencial"] = cr.exceso_credito - cr.carry
    rep["B4_credito_recesion (USA desde 1954)"] = reparto(con_estado(cr, pa), "recesion", "exceso_credito",
                                                         ["carry", "precio_diferencial"], "p")
    res["descriptivas_INT3c"] = {
        "reparto": rep,
        "C2_dividendo_real_estanflacion": _resumen(panel("descomp", "eq_div_real", "estanflacion", placebo=False,
                                                         paises=False)),
        "C6_viv_menos_bolsa_capital_infl_alta": _resumen(panel("descomp", "viv_menos_bolsa_capital", "infl_alta",
                                                               placebo=False, paises=False)),
    }

    # --- sensibilidades (§5.2): efecto, IC y p sin calibrar (NW o DK)
    sen: dict = {}
    for q, (bl, col, est, signo, fam) in PRINCIPAL.items():
        s = {}
        if bl == "mundial":
            s["sin_guerra"] = _resumen(mundial(col, est, filtro=lambda a: ~np.isin(a, list(GUERRA)), placebo=False))
            s["mayoria"] = _resumen(B.ts_contraste(mu[col], (S[est] >= 0.5).astype(float), placebo=False))
            s["regimen_USA"] = _resumen(B.ts_contraste(mu[col], usa[est], placebo=False))
            s["cuota_pib"] = _resumen(mundial(col, est, X=S_pib, placebo=False))
            if est == "recesion":
                s["pico_a_valle"] = _resumen(mundial(col, est, X=S_pv, placebo=False))
            if col == "mp_real":
                s["solo_exceso"] = _resumen(mundial("mp_exceso", est, placebo=False))
                s["century_1927"] = _resumen(mundial("cfp_real", est, placebo=False))
        else:
            s["sin_guerra"] = _resumen(panel(bl, col, est, filtro=lambda f: ~f.año.isin(GUERRA), placebo=False,
                                             paises=False))
            if est == "recesion":
                s["pico_a_valle"] = _resumen(panel(bl, col, est, estados=pa_pv, placebo=False, paises=False))
            if bl == "oro":
                s["sin_1914_1919_1939_1949"] = _resumen(panel(bl, col, est, filtro=lambda f: ~f.año.isin(GUERRA_FX),
                                                              placebo=False, paises=False))
                s["aritmetica"] = _resumen(panel(bl, "oro_real_local", est, placebo=False, paises=False))
                s["desde_1972"] = _resumen(panel(bl, col, est, filtro=lambda f: f.año >= 1972, placebo=False,
                                                 paises=False))
            if bl == "credito":
                s["uk_n10"] = _resumen(B.panel_contraste(con_estado(cre10, pa), col, est, placebo=False, paises=False))
            if bl in ("oro", "descomp"):
                pr = {}
                for c in PRUEBA:
                    f = con_estado(bloques[bl][bloques[bl].pais == c], pa).dropna(subset=[col])
                    y1, y0 = f.loc[f[est] == 1, col], f.loc[f[est] == 0, col]
                    pr[c] = float(y1.mean() - y0.mean()) if len(y1) >= 3 and len(y0) >= 3 else None
                s["paises_prueba_diferencia"] = pr
        sen[q] = s
    sen["holm_conjunto_m8"] = I.holm({q: r["placebo"]["p_cal"] for q, r in princ.items()})
    res["sensibilidades"] = sen

    (REPO / "research" / "int" / "int3b_resultado.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False, default=float))

    # --- resumen en markdown
    pp = lambda v: f"{100 * v:+.1f}"  # noqa: E731
    lin = ["# INT-3b / INT-3c: resultado de la corrida única", "",
           f"Procedencia: commit `{proc['commit'][:7]}`, árbol limpio {proc['arbol_limpio']}, {proc['hora_utc']}. "
           "Prerregistro v1.0 (fa6d4c9). Unidades: pp por año; en B1, B2 y C5, efecto de pasar del 0 % al 100 % de "
           "países del núcleo en el estado (entre paréntesis, por 1 dt de la cuota y la lectura por mayoría).", "",
           "| id | pregunta | efecto (pp) | IC 95 % | p (NW/DK) | φ | p_cal | Holm | > p95 placebo | 1950-99 | países | ESTABLECIDO |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for q, r in princ.items():
        c = r["criterios"]
        extra = ""
        if r["bloque"] == "mundial":
            extra = f" ({pp(r['por_dt_cuota'])} por dt; mayoría {pp(r['lectura_mayoria']['efecto'])})"
            paises = f"1878-1949: {pp(r['efecto_1878_1949'])}"
        else:
            paises = (f"{sum(np.sign(v) == r['signo_esperado'] for v in r['por_pais_sin_encoger'].values())}"
                      f"/{len(r['por_pais_sin_encoger'])} sin encoger; "
                      f"{sum(np.sign(v) == r['signo_esperado'] for v in r['por_pais_dl_sin_año'].values())}"
                      f"/{len(r['por_pais_dl_sin_año'])} DL sin año")
        lin.append(f"| {q} | {r['variable']} × {r['estado']} | {pp(r['efecto'])}{extra} | [{pp(r['ic95'][0])}; "
                   f"{pp(r['ic95'][1])}] | {r['p']:.4f} | {r['placebo']['phi']:.2f} | {r['placebo']['p_cal']:.4f} | "
                   f"{'sí' if r['holm_ok'] else 'no'} | {'sí' if c['3_supera_p95_placebo'] else 'no'} | "
                   f"{pp(r['efecto_1950_1999'])} | {paises} | **{'sí' if c['ESTABLECIDO'] else 'no'}** |")
    lin += ["", "Criterios por pregunta: ver `criterios` en el JSON. Descriptivas y sensibilidades: en el JSON (no deciden)."]
    (REPO / "research" / "int" / "int3b_resultado.md").write_text("\n".join(lin) + "\n")
    ver = {q: r["criterios"]["ESTABLECIDO"] for q, r in princ.items()}
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(f"| {dt.date.today()} | Constructor (P-DEV-INT3b v1.0, corrida única) | commit {proc['commit'][:7]}; "
                 f"INT-3b B1-B4 e INT-3c C1, C3-C5, 1877-1999, Holm 4 + 4 sobre p calibrado con placebo; establecidos "
                 f"{json.dumps(ver)}; research/int/int3b_resultado.json |\n")
    print("\n".join(lin))


if __name__ == "__main__":
    main()
