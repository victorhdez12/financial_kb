"""INT-3, sensibilidad DECLARADA A POSTERIORI (Validador, 27-oct). No cambia P-DEV-INT3 ni la corrida única
(research/int/int3_resultado.json): se publica aparte, no decide y se anota como posterior al resultado.
1) Inferencia robusta a autocorrelación: Driscoll-Kraay (lags por defecto y 8) y p calibrado con el placebo (fracción
   de desplazamientos con |t| ≥ |t real|), con Holm sobre las 6 preguntas.
2) Criterio de países sin el choque común: DerSimonian-Laird sobre efectos por país con la media de cada año quitada,
   y los signos de los efectos por país SIN encoger.
3) Q5b con otras definiciones: recesión con el año del pico incluido; y por episodio (cada recesión pesa 1).
4) Nominal en logaritmos (log(1 + r)): la hiperinflación (DEU 1923) hace inservible la media de rentabilidades nominales.
Uso: .venv/bin/python -m scripts.int3_sensibilidad_robusta
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import int3_corrida as C
from src.intl import data as D
from src.intl import int3 as I
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]


def q5b_alternativas(f: pd.DataFrame, rec: pd.DataFrame) -> dict:
    rec = rec[rec.pais.isin(C.NUCLEO)]
    y = f.set_index(["pais", "anio"])["bolsa"]
    out = {}
    for nom, desde in (("pico_a_valle", 0), ("pico+1_a_valle (corrida)", 1)):
        filas = []
        for _, r in rec.iterrows():
            for a in range(int(r.pico) + desde, int(r.valle) + 1):
                if (r.pais, a) in y.index:
                    filas.append({"pais": r.pais, "anio": a, "y": y[(r.pais, a)], "fin": float(r.tipo == "financiera")})
        g = pd.DataFrame(filas).dropna()
        out[nom] = I.contraste(g.y, g.fin, g.pais, g.anio)
    epi = []
    for _, r in rec.iterrows():
        v = [y.get((r.pais, a)) for a in range(int(r.pico), int(r.valle) + 1)]
        v = [x for x in v if x is not None and not np.isnan(x)]
        if v:
            epi.append({"tipo": r.tipo, "acumulada_log": float(np.sum(np.log1p(v))), "años": len(v)})
    e = pd.DataFrame(epi)
    out["por_episodio"] = {t: {"n": int((e.tipo == t).sum()), "media_acumulada_log": float(e.loc[e.tipo == t, "acumulada_log"].mean()),
                               "años_medios": float(e.loc[e.tipo == t, "años"].mean())} for t in ("normal", "financiera")}
    return out


def main() -> None:
    proc = procedencia()
    con = D.connect()
    anual = P.anual(con)
    con.close()
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    ok = lambda f: f[f.pais.isin(C.NUCLEO) & f.cuadrante.notna() & ~f.truncada.fillna(True).astype(bool)]  # noqa: E731
    f = ok(C.tabla(anual, et, rec))
    res = {"procedencia": proc, "nota": "sensibilidad declarada a posteriori; no decide", "preguntas": {}}
    p_pl = {}
    for q, (yv, est, signo) in C.PREGUNTAS.items():
        d = est(f).astype(float)
        r = {"dk": I.driscoll_kraay(f[yv], d, f.pais, f.anio), "dk_8": I.driscoll_kraay(f[yv], d, f.pais, f.anio, lags=8),
             "placebo": I.p_placebo(f[yv], d, f.pais, f.anio)}
        ef_raw = I.efectos_pais(f[yv], d, f.pais)
        ef_sa, mu, tau2 = I.encoger(I.efectos_pais_sin_año(f[yv], d, f.pais, f.anio))
        r["paises_signo_sin_encoger"] = f"{int((np.sign(ef_raw.efecto) == signo).sum())}/{len(ef_raw)}"
        r["paises_signo_sin_año_encogido"] = f"{int((np.sign(ef_sa.encogido) == signo).sum())}/{len(ef_sa)}"
        r["tau2_sin_año"] = tau2
        p_pl[q] = r["placebo"]["p_empirico"]
        res["preguntas"][q] = r
    res["holm_p_placebo"] = I.holm(p_pl)
    res["holm_dk"] = I.holm({q: v["dk"]["p"] for q, v in res["preguntas"].items()})
    res["Q5b_alternativas"] = q5b_alternativas(f, rec)
    fn = ok(C.tabla(anual, et, rec, real=False))
    for c in ("bolsa", "bono", "letra", "viv"):
        fn[c] = np.log1p(fn[c].clip(lower=-0.99))
    fn["viv_menos_bolsa"] = fn["viv"] - fn["bolsa"]
    res["nominal_log"] = {q: {k: v[k] for k in ("efecto", "ic95", "p")} for q, v in C.evaluar(fn, placebo=False).items()}
    (REPO / "research" / "int" / "int3_sensibilidad_robusta.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    print(json.dumps({q: {"p_dk": round(v["dk"]["p"], 4), "p_placebo": v["placebo"]["p_empirico"],
                          "paises": v["paises_signo_sin_año_encogido"]} for q, v in res["preguntas"].items()}, indent=1))


if __name__ == "__main__":
    main()
