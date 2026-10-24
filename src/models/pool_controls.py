"""Controles SINTÉTICOS de M2, M3 y el pool antes de la etiqueta real (m2_structural_spec.md §6, m3_tvtp_spec.md §5,
pool_spec.md §5). No lee la etiqueta ni datos reales (generadores de tests/m2_synth.py y tests/test_models_tvtp.py).

    .venv/bin/python -m src.models.pool_dev controls      # → research/trials/m2/controles_sinteticos.json
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from src.models import models_pool as MP
from src.models import models_struct as MS
from src.models import pool_dev as PD
from src.models import regime_components as C


def m2_planted(seed: int = 7, start: str = "1980-01", end: str = "2004-08") -> dict:
    """Señal plantada de M2: panel del modelo de §3 con parámetros conocidos; recuperación de λ, φ, ρ (en 2004-01) y
    cobertura del intervalo central del 80 % del G sintético (el de la etiqueta con los datos completos) en todos los
    cortes mensuales de [start, end] (criterio de la spec: entre 0,75 y 0,85)."""
    from scipy.stats import norm
    from tests.m2_synth import SCALE, TRUE, Synth
    s = Synth(seed)
    G = s.true_G()
    m = MS.StructuralG(rev="none")
    rows = []
    for T in pd.date_range(start + "-01", end + "-01", freq="MS"):
        info = s.info(T, data_key=f"controles{seed}")
        m.fit_axis_continuous("G", None, None, None, None, info)
        mu, sd = m.predict_axis_continuous("G", pd.DataFrame(index=[T]), info)
        rows.append({"mes": T, "mu": mu[0], "sd": sd[0], "G": G[T]})
    df = pd.DataFrame(rows).set_index("mes")
    z = (df["G"] - df["mu"]) / df["sd"]
    q = norm.ppf(0.9)
    cov80 = float((z.abs() < q).mean())
    MS.clear_engines()
    m2 = MS.StructuralG(rev="none")
    m2.fit_axis_continuous("G", None, None, None, None, s.info("2004-01", data_key=f"controles{seed}b"))
    v = m2._v
    cols = list(m2.cfg.cols)
    tl = {c: SCALE[c] * TRUE["lam"][c] / v.d[c] for c in MS.COINC}
    tl["claims_4w_yoy"] = 10 * TRUE["lam"]["claims_4w_yoy"] / v.sd["claims_4w_yoy"]
    tl["philly_neworders"] = 12 * TRUE["lam"]["philly_neworders"] / v.sd["philly_neworders"]
    return {"semilla": seed, "cortes": len(df), "cobertura_80": cov80, "cumple_0.75_0.85": 0.75 <= cov80 <= 0.85,
            "cobertura_50": float((z.abs() < norm.ppf(0.75)).mean()), "rmse": float(np.sqrt(((df["G"] - df["mu"]) ** 2).mean())),
            "sd_media": float(df["sd"].mean()), "spec": "m2_structural_spec.md v1.3 (σ̂² = V_conj + V_rev)",
            "lambda": {c: {"est": float(v.params[i]), "verdad": float(tl[c])} for i, c in enumerate(cols)},
            "phi": {"est": [float(x) for x in v.params[6:8]], "verdad": list(TRUE["phi"])},
            "rho": {c: {"est": float(v.params[8 + i]), "verdad": TRUE["rho"][c]} for i, c in enumerate(cols)},
            "convergio": bool(v.converged)}


def m2_variance_decomposition(seed: int = 7, start: str = "1985-01", end: str = "2004-08", step: int = 2) -> dict:
    """Diagnóstico SINTÉTICO de la cobertura de M2: error total Ĝ − G = (Ĝ − Ĝ_oráculo) [filtro] + (Ĝ_oráculo − G)
    [tendencia truncada], con Ĝ_oráculo = composición con las tasas futuras verdaderas y la misma tendencia truncada.
    Compara cada error cuadrático medio con V_filtro y V_tend y mide su correlación (la spec §4 los supone
    independientes)."""
    from tests.m2_synth import Synth
    s = Synth(seed)
    G = s.true_G()
    m = MS.StructuralG(rev="none")
    rows = []
    for T in pd.date_range(start + "-01", end + "-01", freq=f"{step}MS"):
        info = s.info(T, data_key=f"descomp{seed}")
        m.fit_axis_continuous("G", None, None, None, None, info)
        nc = m.nowcast(T, info)
        known = s.pit_levels(s.decision[T])["levels"]
        rh = {c: MS.rates(s.levels[c]).reindex(pd.date_range(lv.index.max() + pd.DateOffset(months=1),
                                                              T + pd.DateOffset(months=4), freq="MS"))
              for c, lv in known.items()}
        rows.append({"Ghat": nc["G"], "Gor": MS.compose_G(known, rh, T), "G": G[T], "Vf": nc["V_filtro"],
                     "Vt": nc["V_tend"]})
    d = pd.DataFrame(rows)
    ef, et = d["Ghat"] - d["Gor"], d["Gor"] - d["G"]
    return {"semilla": seed, "cortes": len(d), "paso_meses": step,
            "filtro": {"mse_real": float((ef ** 2).mean()), "V_filtro_medio": float(d["Vf"].mean())},
            "tendencia": {"mse_real": float((et ** 2).mean()), "V_tend_medio": float(d["Vt"].mean())},
            "total": {"mse_real": float(((d["Ghat"] - d["G"]) ** 2).mean()),
                      "suma_V_media": float((d["Vf"] + d["Vt"]).mean())},
            "corr_error_filtro_error_tendencia": float(np.corrcoef(ef, et)[0, 1])}


def m3_controls() -> dict:
    from tests.test_models_tvtp import GTRUE, SynthTVTP, _info, _ll, simulate
    X, t, x, _ = simulate(n=600, seed=11)
    m = SynthTVTP(x)
    m.fit_axis("G", X, t.to_numpy(), np.ones(len(X)), _info(X, x))
    planted = {"verdad": list(GTRUE), "estimado": [float(m.par[f"gamma{j}"]) for j in range(1, 5)]}
    d, gs = [], []
    for seed in range(20):
        X, t, x, _ = simulate(n=600, seed=100 + seed, z_informative=False)
        tr, te = X.iloc[:400], X.iloc[400:]
        ll = []
        for ctp in (False, True):
            mm = SynthTVTP(x, constant_transitions=ctp)
            mm.fit_axis("G", tr, t.iloc[:400].to_numpy(), np.ones(400), _info(X, x))
            ll.append(_ll(mm.predict_axis("G", te, _info(X, x)), (t.iloc[400:] > 0.5).astype(float).to_numpy()))
            if not ctp:
                gs.append([float(mm.par[f"gamma{j}"]) for j in range(1, 5)])
        d.append(ll[0] - ll[1])
    return {"senal_plantada": planted,
            "ruido": {"ll_tvtp_menos_ctp_media": float(np.mean(d)), "cumple_<=0.005": bool(np.mean(d) <= 0.005),
                      "gamma_media": [float(x) for x in np.mean(gs, axis=0)]}}


def pool_controls() -> dict:
    rng = np.random.default_rng(1)
    n = 3000
    tt = rng.uniform(0.02, 0.98, n)
    P = np.column_stack([np.clip(tt + rng.normal(0, .3, n), .01, .99), tt, np.clip(tt + rng.normal(0, .3, n), .01, .99)])
    st, _ = MP.fit_pool(P, tt, np.ones(n))
    P0 = np.full((300, 3), 0.5)
    s0, _ = MP.fit_pool(P0, np.full(300, 0.5), np.ones(300))
    q = rng.uniform(0.05, 0.95, 300)
    y = (rng.uniform(size=(20, 300)) < C.blp_transform(q, 2.5, 2.5)).astype(float).mean(axis=0)
    s1, _ = MP.fit_pool(np.column_stack([q, q, q]), y, np.ones(300) * 20)
    return {"(i)_oraculo_w": [float(x) for x in st["w"]], "(ii)_sin_info_w": [float(x) for x in s0["w"]],
            "(iii)_infradispersado_a_b": [s1["a"], s1["b"]],
            "(iv)_(v)": "tests/test_harness_v24.py (PIT de los pesos; pool = M0 bit a bit antes de N_min)"}


def main() -> None:
    t0 = time.time()
    out = {"m2": m2_planted(), "m3": m3_controls(), "pool": pool_controls()}
    out["segundos"] = round(time.time() - t0, 1)
    dest = PD.OUT / "controles_sinteticos.json"
    PD._dump(dest, out)
    print({k: v for k, v in out["m2"].items() if k not in ("lambda", "rho")}, out["m3"], out["pool"])
    m2 = out["m2"]
    PD._trial_log("Constructor (M2/M3/pool)", "**Controles sintéticos** (señal plantada de M2 con cobertura del 80 %; "
                  "señal plantada y ruido de M3; pool (i)-(iii)); sin etiqueta ni datos reales", "sintético",
                  f"{m2['cortes']} cortes M2; 20 semillas M3",
                  f"M2 cobertura 80 % = {m2['cobertura_80']:.3f} ({'cumple' if m2['cumple_0.75_0.85'] else 'NO cumple'} "
                  f"0,75-0,85); M3 ruido Δll = {out['m3']['ruido']['ll_tvtp_menos_ctp_media']:+.4f}. "
                  f"`{dest.relative_to(PD.H.REPO)}`")


SEEDS_V13 = (3, 7, 11, 21)          # m2_structural_spec.md v1.3 §6: fijadas antes de correrlo; las 4 en [0,75; 0,85]


def m2_cover_v13(seed: int) -> dict:
    """Control de cobertura de la v1.3 para UNA semilla (se corren en paralelo y se combinan con `combine_v13`)."""
    MS.clear_engines()
    r = m2_planted(seed=seed)
    PD._dump(PD.OUT / f"controles_m2_v13_semilla{seed}.json", r)
    return r


def combine_v13() -> dict:
    import json
    rs = {sd: json.loads((PD.OUT / f"controles_m2_v13_semilla{sd}.json").read_text()) for sd in SEEDS_V13}
    cov = {sd: r["cobertura_80"] for sd, r in rs.items()}
    ok = all(0.75 <= c <= 0.85 for c in cov.values())
    out = {"spec": "m2_structural_spec.md v1.3 §6", "semillas": list(SEEDS_V13), "cobertura_80": cov,
           "cobertura_50": {sd: r["cobertura_50"] for sd, r in rs.items()},
           "rmse": {sd: r["rmse"] for sd, r in rs.items()}, "sd_media": {sd: r["sd_media"] for sd, r in rs.items()},
           "las_cuatro_en_[0.75,0.85]": ok}
    PD._dump(PD.OUT / "controles_m2_v13.json", out)
    PD._trial_log("Constructor (M2 v1.3)", "**Control de señal plantada de M2 v1.3** (σ̂² = V_conj + V_rev; semillas 3, "
                  "7, 11, 21 fijadas en la spec antes de correrlo; sintético, sin etiqueta)", "sintético",
                  "4 semillas × 296 cortes",
                  "cobertura del 80 %: " + ", ".join(f"{sd}: {c:.3f}" for sd, c in cov.items())
                  + f" → {'las cuatro en [0,75; 0,85]' if ok else 'ALGUNA FUERA: parada, pregunta al usuario'}. "
                  "`research/trials/m2/controles_m2_v13.json`")
    return out
