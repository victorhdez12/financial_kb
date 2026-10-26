"""Corrida ÚNICA de P-DEV-INT3 v0.1 (docs/int/INT3_prerregistro_v0.md, aprobada y congelada en 444f614).
Exige el árbol limpio (procedencia). Salida: research/int/int3_resultado.json y .md, y una línea en research/trial_log.md.
Uso: .venv/bin/python -m scripts.int3_corrida
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import int3 as I
from src.intl import panel as P
from src.intl import regimes as G
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
PRUEBA_RET = ["AUS", "CHE"]
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
GUERRA = set(range(1914, 1919)) | set(range(1939, 1946))
INFL_ALTA = {"sobrecalentamiento", "estanflacion"}
# id → (variable y, estado, signo esperado)
PREGUNTAS = {
    "Q1": ("bolsa", lambda f: f.cuadrante == "estanflacion", -1),
    "Q2": ("bono", lambda f: f.cuadrante.isin(INFL_ALTA), -1),
    "Q3": ("bono", lambda f: f.cuadrante == "crecimiento_bajo", +1),
    "Q4": ("letra", lambda f: f.cuadrante.isin(INFL_ALTA), -1),
    "Q5": ("bolsa", lambda f: f.recesion, -1),
    "Q6": ("viv_menos_bolsa", lambda f: f.cuadrante.isin(INFL_ALTA), +1),
}


def tabla(anual: pd.DataFrame, et: pd.DataFrame, rec: pd.DataFrame, real: bool = True) -> pd.DataFrame:
    a = anual.reset_index()
    s = "_real" if real else ""
    f = pd.DataFrame({"pais": a.pais, "anio": a["año"], "bolsa": a[f"eq_tr{s}"], "bono": a[f"bond_tr{s}"],
                      "letra": a[f"bill_rate{s}"], "viv": a[f"housing_tr{s}"]})
    f["viv_menos_bolsa"] = f["viv"] - f["bolsa"]
    f = f.merge(et[["pais", "año", "cuadrante", "frontera", "truncada"]].rename(columns={"año": "anio"}),
                on=["pais", "anio"], how="left")
    en_rec, tipo = set(), {}
    for _, r in rec.iterrows():
        for y in range(int(r.pico) + 1, int(r.valle) + 1):
            en_rec.add((r.pais, y)); tipo[(r.pais, y)] = r.tipo
    f["recesion"] = [(p, y) in en_rec for p, y in zip(f.pais, f.anio)]
    f["rec_financiera"] = [tipo.get((p, y)) == "financiera" for p, y in zip(f.pais, f.anio)]
    return f


def evaluar(f: pd.DataFrame, placebo: bool = True, desfase: int = 0) -> dict:
    out = {}
    for q, (yv, est, signo) in PREGUNTAS.items():
        d = est(f).astype(float)
        if desfase:
            d = d.groupby(f.pais).shift(desfase)
        r = I.contraste(f[yv], d, f.pais, f.anio)
        ef, mu, tau2 = I.encoger(I.efectos_pais(f[yv], d, f.pais))
        r["paises_signo_esperado"] = f"{int((np.sign(ef.encogido) == signo).sum())}/{len(ef)}"
        r["frac_paises"] = float((np.sign(ef.encogido) == signo).mean()) if len(ef) else None
        r["media_encogida"], r["tau2"] = mu, tau2
        r["por_pais"] = dict(zip(ef.pais, ef.encogido.round(4)))
        if placebo:
            r["placebo"] = I.placebo_fp(f[yv], d, f.pais, f.anio)
        r["signo_esperado"] = signo
        out[q] = r
    return out


def q5b(f: pd.DataFrame) -> dict:
    g = f[f.recesion]
    return I.contraste(g["bolsa"], g.rec_financiera.astype(float), g.pais, g.anio)


def main() -> None:
    proc = procedencia()
    con = D.connect()
    anual = P.anual(con)
    con.close()
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    base = tabla(anual, et, rec)
    ok = lambda f: f[f.pais.isin(NUCLEO) & f.cuadrante.notna() & ~f.truncada.fillna(True).astype(bool)]  # noqa: E731
    f = ok(base)

    res = {"procedencia": proc, "prerregistro": "docs/int/INT3_prerregistro_v0.md v0.1 (444f614)",
           "muestra": {"pais_años": len(f), "paises": NUCLEO, "años": [int(f.anio.min()), int(f.anio.max())]}}
    principal = evaluar(f)
    ps = {q: v["p"] for q, v in principal.items()}
    h = I.holm(ps)
    f50 = f[f.anio >= 1950]
    s50 = evaluar(f50, placebo=False)
    for q, v in principal.items():
        c1 = np.sign(v["efecto"]) == v["signo_esperado"]
        c2 = bool(h[q]) and (v["ic95"][0] > 0 or v["ic95"][1] < 0)
        c3 = v["frac_paises"] is not None and v["frac_paises"] >= 2 / 3
        c4 = np.sign(s50[q]["efecto"]) == v["signo_esperado"]
        c5 = v["placebo"]["tasa_fp"] is not None and v["placebo"]["tasa_fp"] <= 0.10
        v["criterios"] = {"1_signo": bool(c1), "2_holm_ic": bool(c2), "3_paises_2_3": bool(c3),
                          "4_signo_1950_2004": bool(c4), "5_placebo_fp_10": bool(c5)}
        v["ESTABLECIDO"] = bool(c1 and c2 and c3 and c4 and c5)
        v["efecto_1950_2004"] = s50[q]["efecto"]
    res["principal"] = principal
    res["Q5b_financiera_vs_normal"] = q5b(f)
    res["secundaria_regimen_t_menos_1"] = {q: {k: v[k] for k in ("efecto", "ic95", "p")}
                                           for q, v in evaluar(f, placebo=False, desfase=1).items()}
    # sensibilidades
    sens = {}
    sens["sin_guerras"] = evaluar(f[~f.anio.isin(GUERRA)], placebo=False)
    sens["sin_frontera"] = evaluar(f[~f.frontera.astype(bool)], placebo=False)
    sens["1950_2004"] = s50
    sens["nominal"] = evaluar(ok(tabla(anual, et, rec, real=False)), placebo=False)
    abs3 = []
    for c in D.PAISES:
        if c in anual.index.get_level_values(0):
            a = anual.loc[c]
            e = G.etiqueta(np.log(a["rgdpmad"]), a["inflacion"], G.VENTANA_ANUAL, umbral_i=G.UMBRAL_I_ABSOLUTO, relativa=False)
            abs3.append(e.assign(pais=c).reset_index(names="año"))
    sens["inflacion_abs3"] = evaluar(ok(tabla(anual, pd.concat(abs3), rec)), placebo=False)
    res["sensibilidades"] = {k: {q: {kk: v[kk] for kk in ("efecto", "ic95", "p", "paises_signo_esperado")}
                                 for q, v in s.items()} for k, s in sens.items()}
    # países de prueba (solo signos)
    fp = base[base.pais.isin(PRUEBA_RET) & base.cuadrante.notna() & ~base.truncada.fillna(True).astype(bool)]
    prueba = {}
    for c in PRUEBA_RET:
        g = fp[fp.pais == c]
        prueba[c] = {}
        for q, (yv, est, signo) in PREGUNTAS.items():
            d = est(g)
            y1, y0 = g.loc[d, yv].dropna(), g.loc[~d, yv].dropna()
            if len(y1) >= 3 and len(y0) >= 3:
                prueba[c][q] = {"efecto": float(y1.mean() - y0.mean()), "signo_ok": bool(np.sign(y1.mean() - y0.mean()) == signo),
                                "n_estado": int(len(y1))}
    res["paises_prueba"] = prueba
    (REPO / "research" / "int" / "int3_resultado.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    # resumen legible
    lin = ["# INT-3: resultado de la corrida única", "", f"Procedencia: commit `{proc['commit'][:7]}`, árbol limpio "
           f"{proc['arbol_limpio']}, {proc['hora_utc']}. Muestra: {len(f)} país-años, 14 países, "
           f"{int(f.anio.min())}-{int(f.anio.max())}. Rentabilidades reales anuales (puntos porcentuales).", "",
           "| id | efecto (pp) | IC 95 % | p | Holm | países con el signo | 1950-2004 | placebo FP | ESTABLECIDO |", "|---|---|---|---|---|---|---|---|---|"]
    for q, v in principal.items():
        lin.append(f"| {q} | {100*v['efecto']:+.1f} | [{100*v['ic95'][0]:+.1f}; {100*v['ic95'][1]:+.1f}] | {v['p']:.4f} | "
                   f"{'sí' if h[q] else 'no'} | {v['paises_signo_esperado']} | {100*v['efecto_1950_2004']:+.1f} | "
                   f"{v['placebo']['tasa_fp']:.2f} | **{'sí' if v['ESTABLECIDO'] else 'no'}** |")
    b = res["Q5b_financiera_vs_normal"]
    lin += ["", f"Q5b (bolsa en recesión financiera frente a normal): {100*b['efecto']:+.1f} pp, IC [{100*b['ic95'][0]:+.1f}; "
            f"{100*b['ic95'][1]:+.1f}], p = {b['p']:.4f} (n = {b['n']}, {b['n_estado']} financieras)."]
    (REPO / "research" / "int" / "int3_resultado.md").write_text("\n".join(lin) + "\n")
    ver = {q: v["ESTABLECIDO"] for q, v in principal.items()}
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(f"| {dt.date.today()} | Constructor (P-DEV-INT3 v0.1, corrida única) | commit {proc['commit'][:7]}; "
                 f"núcleo 14 países 1870-2004, {len(f)} país-años; establecidos {json.dumps(ver)}; "
                 f"research/int/int3_resultado.json |\n")
    print("\n".join(lin))


if __name__ == "__main__":
    main()
