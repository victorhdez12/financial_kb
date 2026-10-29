"""Validador del termómetro (docs/validation/2026-10-29_termometro.md): sensibilidades DECLARADAS A POSTERIORI sobre el
2.º intento (scripts/termometro_puerta_v2.py, diseño v1.3 §9). No cambian el veredicto oficial ni escriben sus salidas.

1. Reproducción de la puerta cruzada (debe dar T1 r 0,788 / pend 0,794; T2 r 0,878 / pend 0,943, 31 filas).
2. Bootstrap por años (2.000 réplicas, semilla 0) del r y la pendiente de T2; además, por episodio (país, pico).
3. Puerta agregada de T1 dejando fuera un país cada vez (filas de la puerta; rectas y recalibración como en la oficial).
4. Puerta sin el B1 común: r y pendiente de la parte de indicadores del logit (anual frente a mensual traducida).
5. S4 como dice §8 d (suma de 4 trimestres frente a la de 4 trimestres antes) en lugar de PIB(q) frente a PIB(q − 4).
6. Equivalencia del B1 en vivo (fechado trimestral, b1_vivo) con el B1 anual de JST (int4.liston) en las filas.
7. Lista de países con probabilidad de T2 con la regla corregida (sin DNK/JPN ni países sin filas).
Uso: .venv/bin/python -m scripts.val_termometro_sens   (salida: research/int/val_termometro_sens.json)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from scripts.int4_corrida import NUCLEO, _r
from scripts.termometro_puerta import GIROS, REPO, TODOS, cargar
from scripts.termometro_puerta_v2 import IMPAR, PAR, probs
from src.intl import int4 as M
from src.intl import termometro as T
from src.warehouse import db

B, SEMILLA = 2000, 0


def cruzada(mens, pan, base, b, giros=GIROS):
    """Igual que termometro_puerta_v2.main (pliegues pares↔impares); devuelve pa, pm (sin recalibrar), pc por giro."""
    out = {g: {k: np.full(len(base[g][0]), np.nan) for k in ("pa", "pm", "pc", "xa", "xm")} for g in giros}
    for fit, gate in ((PAR, IMPAR), (IMPAR, PAR)):
        tr = T.traducir(mens, T.rectas(pan, mens, NUCLEO, TODOS, fit, gate), TODOS)
        for giro in giros:
            cols = GIROS[giro]
            f, B1, Xa = base[giro]
            pa, pm, ok = probs(f, B1, Xa, b[giro], tr, cols)
            t = f.t.to_numpy()
            mf, mg = ok & np.array([fit(x) for x in t]), ok & np.array([gate(x) for x in t])
            cal = T.calibrar(pa[mf], pm[mf])
            o = out[giro]
            o["pa"][mg], o["pm"][mg], o["pc"][mg] = pa[mg], pm[mg], T.aplicar_cal(pm[mg], cal)
            nb = B1.shape[1]
            Xm = T.matriz_mensual(f, tr, cols)
            o["xa"][mg] = (Xa @ b[giro][1 + nb:])[mg]          # parte de indicadores del logit
            o["xm"][mg] = (Xm @ b[giro][1 + nb:])[mg]
    return out


def boot(pa, pc, grupos, semilla=SEMILLA):
    ok = np.isfinite(pa) & np.isfinite(pc)
    pa, pc, grupos = pa[ok], pc[ok], grupos[ok]
    u = np.unique(grupos)
    idx = {g: np.flatnonzero(grupos == g) for g in u}
    rng = np.random.default_rng(semilla)
    rs, ps, pasa = [], [], 0
    for _ in range(B):
        k = np.concatenate([idx[g] for g in rng.choice(u, len(u), replace=True)])
        if np.std(pc[k]) == 0:
            continue
        g = T.puerta(pa[k], pc[k])
        rs.append(g["r"]), ps.append(g["pendiente"])
        pasa += g["pasa"]
    q = lambda v: [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.5)), float(np.quantile(v, 0.975))]  # noqa: E731
    return {"grupos": int(len(u)), "replicas": len(rs), "r_ic95": q(rs), "pendiente_ic95": q(ps),
            "frac_pasa": pasa / len(rs)}


def s4_diseno(pib, nucleo, paises, rej):
    """§8 d literal: S(q) < S(q − 4), S = suma de 4 trimestres (conocida 75 días tras q)."""
    g = pd.DataFrame({c: T.asof_q(T._rejilla_q(pib[c]).rolling(4, min_periods=4).sum().pct_change(4, fill_method=None),
                                  T.RETRASO_PIB, rej) if c in pib else np.nan for c in paises}, index=rej)
    neg = (g < 0).astype(float).where(g.notna())
    return pd.DataFrame({c: neg[[o for o in nucleo if o != c]].mean(axis=1)
                         .where(neg[[o for o in nucleo if o != c]].notna().sum(axis=1) >= 5) for c in paises})


def b1_equivalencia(base, pib, rej):
    fq = {c: T.fechado_trimestral(pib[c]) for c in NUCLEO}
    out = {}
    for giro in GIROS:
        f, B1, _ = base[giro]
        filas = []
        for i, (c, t) in enumerate(zip(f.pais, f.t)):
            if t > 2003 or t < 1962:
                continue
            est = T.estado_mensual(fq[c], rej, pib[c].index.min())
            fe = pd.Timestamp(f"{t + 1}-04-30")
            if fe not in est.index or pd.isna(est.loc[fe, "en_rec"]):
                continue
            e = est.loc[[fe]]
            bv = T.b1_vivo(e, giro)[0]
            filas.append({"pais": c, "t": int(t), "en_rec_vivo": float(e["en_rec"].iloc[0]),
                          **{f"anual_{j}": float(B1[i, j]) for j in range(B1.shape[1])},
                          **{f"vivo_{j}": float(bv[j]) for j in range(len(bv))}})
        d = pd.DataFrame(filas)
        res = {"filas": int(len(d)),
               "estado_vivo_coincide": float((d["en_rec_vivo"] == (1.0 if giro == "T2" else 0.0)).mean())}
        for j in range(B1.shape[1]):
            a, v = d[f"anual_{j}"], d[f"vivo_{j}"]
            res[f"col{j}"] = {"corr": float(np.corrcoef(a, v)[0, 1]) if a.std() and v.std() else None,
                              "media_anual": float(a.mean()), "media_vivo": float(v.mean()),
                              "iguales": float((np.abs(a - v) < 1e-9).mean())}
        out[giro] = res
    return out


def main() -> None:
    a, extra, pm_, bis, pib = cargar()
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in TODOS}
    primer = {c: min(v) for c, v in años_pais.items()}
    pan = M.paneles(a, extra, NUCLEO, TODOS, None)
    mens = T.mensuales(pm_, bis, pib, NUCLEO, TODOS)
    rej = mens["C1"].index
    base, b = {}, {}
    for giro, cols in GIROS.items():
        f = (M.obj_entrada if giro == "T1" else M.obj_salida)(rec, años_pais, NUCLEO, 1, 1871, True)
        B1 = M.liston(f, giro, rec, primer, pan)
        Xa = M.matriz(f, pan, cols)
        b[giro] = T.congelar(B1, Xa, f.y.to_numpy(float))
        base[giro] = (f, B1, Xa)
    cz = cruzada(mens, pan, base, b)
    res = {"nota": "sensibilidades a posteriori del Validador; no cambian el veredicto oficial", "reproduccion": {},
           "bootstrap_T2": {}, "loco_T1": {}, "sin_B1": {}, "s4_diseno_T2": {}}
    for g in GIROS:
        res["reproduccion"][g] = T.puerta(cz[g]["pa"], cz[g]["pc"])
        res["sin_B1"][g] = T.puerta(cz[g]["xa"], cz[g]["xm"])
    f2 = base["T2"][0]
    res["bootstrap_T2"]["por_año"] = boot(cz["T2"]["pa"], cz["T2"]["pc"], f2.t.to_numpy())
    res["bootstrap_T2"]["por_episodio"] = boot(cz["T2"]["pa"], cz["T2"]["pc"],
                                               (f2.pais + "_" + f2.pico.astype(str)).to_numpy())
    ok2 = np.isfinite(cz["T2"]["pc"])
    res["T2_filas"] = {"por_pais": f2.pais[ok2].value_counts().to_dict(),
                       "episodios": int((f2.pais + "_" + f2.pico.astype(str))[ok2].nunique()),
                       "años": sorted(int(x) for x in f2.t[ok2].unique()),
                       "pa_rango": [float(np.nanmin(cz["T2"]["pa"])), float(np.nanmax(cz["T2"]["pa"]))]}
    res["bootstrap_T1"] = {"por_año": boot(cz["T1"]["pa"], cz["T1"]["pc"], base["T1"][0].t.to_numpy())}
    f1 = base["T1"][0]
    for c in NUCLEO:
        k = f1.pais.to_numpy() != c
        res["loco_T1"][c] = T.puerta(cz["T1"]["pa"][k], cz["T1"]["pc"][k])
    m2 = dict(mens, S4=s4_diseno(pib, NUCLEO, TODOS, rej))
    cz2 = cruzada(m2, pan, base, b, giros=["T2"])
    res["s4_diseno_T2"] = {"puerta": T.puerta(cz2["T2"]["pa"], cz2["T2"]["pc"]),
                           "sin_recalibrar": T.puerta(cz2["T2"]["pa"], cz2["T2"]["pm"]),
                           "corr_s4_codigo_vs_diseno_abril": float(pd.concat(
                               [T.abril(mens["S4"], range(1961, 2004)).stack(),
                                T.abril(m2["S4"], range(1961, 2004)).stack()], axis=1).corr().iloc[0, 1])}
    res["b1_equivalencia"] = b1_equivalencia(base, pib, rej)
    filas_pais = f2.pais[ok2].value_counts()
    res["paises_T2_regla_corregida"] = [c for c in NUCLEO if c not in T.SIN_BOLSA and filas_pais.get(c, 0) > 0]
    (REPO / "research" / "int" / "val_termometro_sens.json").write_text(json.dumps(_r(res), indent=1, ensure_ascii=False))
    print(json.dumps(_r(res), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
