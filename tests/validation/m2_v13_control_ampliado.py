"""Validador: control sintético AMPLIADO de M2 v1.3 (protocolo prerregistrado
docs/validation/2026-10-24_m2_v13_control_ampliado_protocolo.md, commit da18753, empujado 16:27:14Z).

SOLO datos sintéticos (tests/m2_synth.py). No carga la etiqueta, ni la base PIT, ni niveles reales; no registra nada.
No modifica el código de producción: reproduce el bucle de `src/models/pool_controls.py::m2_planted` y guarda la serie
mes a mes.

    .venv/bin/python tests/validation/m2_v13_control_ampliado.py run --arm R0 --seed 3
    .venv/bin/python tests/validation/m2_v13_control_ampliado.py run --arm A --seed 1001 [--d3]
    .venv/bin/python tests/validation/m2_v13_control_ampliado.py analyze
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd
from scipy.stats import norm, t as tdist

from src.labels import regime_us as R
from src.models import models_struct as MS
from tests.m2_synth import Synth

OUT = REPO / "research" / "validation" / "m2_v13_control_ampliado"
Q80, Q50, Q95 = norm.ppf(0.9), norm.ppf(0.75), norm.ppf(0.975)
SEEDS_OLD = (3, 7, 11, 21)
SEEDS_NEW = tuple(range(1001, 1041))
LO, HI = 0.75, 0.85


# ------------------------------------------------------------------ réplica del bucle de m2_planted
def vconj_errors(cfg, v, L, feats, T) -> list[dict]:
    """Réplica de models_struct.v_conj que devuelve e_s mes a mes (D3) y el nº de coincidentes de Ĝ^ps y de G."""
    lv = {k: R._cal(x) for k, x in L["levels"].items() if k in MS.COINC and x is not None and len(x.dropna())}
    fullG = MS.label_G(lv)
    full = fullG["G"]
    nfull = fullG["cobertura_g"]
    ell = {k: MS._mdiff(T, x.last_valid_index()) for k, x in lv.items()}
    out = []
    for s_ in pd.date_range(MS.DATA_START, MS._add(T, -MS.S.trend_err_lag), freq="MS"):
        Lp = {"levels": {k: x[x.index <= MS._add(s_, -ell[k])] for k, x in lv.items()},
              "from_vintage": {k: False for k in lv}}
        Lp["levels"] = {k: x for k, x in Lp["levels"].items() if len(x.dropna())}
        fs = feats[feats.index <= s_] if feats is not None else None
        g = MS.ghat(cfg, v, Lp, fs, s_)
        if np.isfinite(g["G"]) and s_ in full.index and np.isfinite(full[s_]):
            out.append({"s": f"{s_:%Y-%m}", "e": float(g["G"] - full[s_]), "n_ps": int(g["n"]),
                        "n_full": int(nfull.get(s_, 0))})
    return out


def run_seed(seed: int, arm: str, d3: bool = False) -> dict:
    t0 = time.time()
    MS.clear_engines()
    s = Synth(seed) if arm in ("R0", "A") else Synth(seed, end="2009-12")
    G = s.true_G()
    m = MS.StructuralG(rev="none")
    key = f"controles{seed}" if arm == "R0" else f"validador_{arm}_{seed}"
    rows, d3rows, seen = [], {}, set()
    for T in pd.date_range("1980-01-01", "2004-08-01", freq="MS"):
        info = s.info(T, data_key=key)
        m.fit_axis_continuous("G", None, None, None, None, info)
        mu, sd = m.predict_axis_continuous("G", pd.DataFrame(index=[T]), info)
        v = m._v
        rows.append({"mes": f"{T:%Y-%m}", "mu": float(mu[0]), "sd": float(sd[0]), "G": float(G[T]),
                     "version": v.id, "v_conj": float(v.v_conj), "n_conj": int(v.n_conj), "v_tend": float(v.v_tend),
                     "conv": bool(v.converged), "kept": bool(v.kept_previous)})
        if d3 and v.id not in seen:
            seen.add(v.id)
            eng = MS.engine_for(info, m.cfg)
            dec = info["decision_calendar"][v.T]
            e = vconj_errors(eng.cfg, v, eng.levels_at(info, dec), eng.feats_upto(info, v.T), v.T)
            mse = float(np.mean([x["e"] ** 2 for x in e]))
            d3rows[v.id] = {"errores": e, "mse_replica": mse, "v_conj": float(v.v_conj),
                            "dif_replica": abs(mse - float(v.v_conj))}
    df = pd.DataFrame(rows)
    z = (df["G"] - df["mu"]) / df["sd"]
    res = {"semilla": seed, "brazo": arm, "cortes": len(df), "cobertura_80": float((z.abs() < Q80).mean()),
           "segundos": round(time.time() - t0, 1), "serie": rows}
    if d3:
        res["d3"] = d3rows
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{arm}_{seed}.json").write_text(json.dumps(res, ensure_ascii=False))
    return {k: v for k, v in res.items() if k not in ("serie", "d3")}


# ------------------------------------------------------------------ análisis
def block_boot_se(x: np.ndarray, b: int, reps: int = 2000, seed: int = 12345) -> float:
    rng = np.random.default_rng(seed)
    n = len(x)
    k = int(np.ceil(n / b))
    starts = rng.integers(0, n - b + 1, size=(reps, k))
    idx = (starts[:, :, None] + np.arange(b)[None, None, :]).reshape(reps, -1)[:, :n]
    return float(x[idx].mean(axis=1).std(ddof=1))


def load(arm: str, seeds) -> dict:
    out = {}
    for sd in seeds:
        p = OUT / f"{arm}_{sd}.json"
        if p.exists():
            out[sd] = json.loads(p.read_text())
    return out


def per_seed(r: dict) -> dict:
    df = pd.DataFrame(r["serie"])
    df["mes"] = pd.to_datetime(df["mes"] + "-01")
    z = ((df["G"] - df["mu"]) / df["sd"]).to_numpy()
    hit = (np.abs(z) < Q80).astype(float)
    c = float(hit.mean())
    out = {"cob80": c, "cob50": float((np.abs(z) < Q50).mean()), "cob95": float((np.abs(z) < Q95).mean()),
           "z2": float(np.mean(z ** 2)), "kurt_exc": float(pd.Series(z).kurt()), "sesgo_medio_z": float(z.mean()),
           "rmse": float(np.sqrt(np.mean((df["G"] - df["mu"]) ** 2))), "sd_media": float(df["sd"].mean()),
           "sin_convergencia": int((~df.drop_duplicates("version")["conv"]).sum())}
    for b in (12, 24, 48):
        se = block_boot_se(hit, b)
        out[f"se_bloque{b}"] = se
        out[f"n_ef_bloque{b}"] = c * (1 - c) / se ** 2 if se > 0 else float("nan")
    ac = [float(pd.Series(hit).autocorr(k)) for k in (1, 3, 6, 12, 24)]
    out["acf_aciertos_1_3_6_12_24"] = ac
    for name, (a, b_) in {"1980_1989": ("1980-01", "1989-12"), "1990_1999": ("1990-01", "1999-12"),
                          "2000_2004": ("2000-01", "2004-08"), "hasta_1999": ("1980-01", "1999-12")}.items():
        msk = (df["mes"] >= a) & (df["mes"] <= b_ + "-01") if False else \
            (df["mes"] >= pd.Timestamp(a + "-01")) & (df["mes"] <= pd.Timestamp(b_ + "-01"))
        out[f"cob80_{name}"] = float(hit[msk.to_numpy()].mean())
        out[f"z2_{name}"] = float(np.mean(z[msk.to_numpy()] ** 2))
    return out


def summary(vals) -> dict:
    x = np.asarray(vals, float)
    n = len(x)
    m, s = float(x.mean()), float(x.std(ddof=1)) if n > 1 else float("nan")
    h = float(tdist.ppf(0.975, n - 1) * s / np.sqrt(n)) if n > 1 else float("nan")
    return {"n": n, "media": m, "sd": s, "ic95": [m - h, m + h], "min": float(x.min()), "max": float(x.max())}


def p_all_in(mu: float, sd: float, k: int = 4) -> float:
    p = norm.cdf((HI - mu) / sd) - norm.cdf((LO - mu) / sd)
    return float(p ** k)


def analyze() -> dict:
    res = {"protocolo": "docs/validation/2026-10-24_m2_v13_control_ampliado_protocolo.md (da18753)"}
    # R0
    ref = json.loads((REPO / "research/trials/m2/controles_m2_v13.json").read_text())["cobertura_80"]
    r0 = load("R0", SEEDS_OLD)
    res["R0"] = {str(sd): {"replica": r["cobertura_80"], "constructor": ref[str(sd)],
                           "dif": abs(r["cobertura_80"] - ref[str(sd)]), "segundos": r["segundos"]}
                 for sd, r in r0.items()}
    res["R0_ok"] = bool(r0) and all(v["dif"] < 1e-9 for v in res["R0"].values())
    res["R0_por_semilla"] = {str(sd): per_seed(r) for sd, r in r0.items()}
    for arm in ("A", "B"):
        rr = load(arm, SEEDS_NEW)
        if not rr:
            continue
        ps = {sd: per_seed(r) for sd, r in rr.items()}
        cov = [p["cob80"] for p in ps.values()]
        sm = summary(cov)
        frac = float(np.mean([(LO <= c <= HI) for c in cov]))
        a = {"semillas": sorted(rr), "cob80": sm, "fraccion_en_rango": frac,
             "principal_cumple": bool(LO <= sm["ic95"][0] and sm["ic95"][1] <= HI),
             "secundario_cumple": bool(frac >= 0.70)}
        for k in ("cob50", "cob95", "z2", "kurt_exc", "sesgo_medio_z", "rmse", "sd_media", "cob80_1980_1989",
                  "cob80_1990_1999", "cob80_2000_2004", "cob80_hasta_1999", "z2_1980_1989", "z2_1990_1999",
                  "z2_2000_2004", "z2_hasta_1999", "se_bloque12", "se_bloque24", "se_bloque48", "n_ef_bloque12",
                  "n_ef_bloque24", "n_ef_bloque48"):
            a[k] = summary([p[k] for p in ps.values()])
        a["sin_convergencia_total"] = int(sum(p["sin_convergencia"] for p in ps.values()))
        a["segundos_medios"] = float(np.mean([r["segundos"] for r in rr.values()]))
        a["p_4_semillas_en_rango_si_media_0.80"] = p_all_in(0.80, sm["sd"])
        a["p_4_semillas_en_rango_si_media_observada"] = p_all_in(sm["media"], sm["sd"])
        a["por_semilla"] = {str(sd): {k: p[k] for k in ("cob80", "cob50", "z2", "cob80_hasta_1999",
                                                         "cob80_2000_2004", "se_bloque24")} for sd, p in ps.items()}
        res[arm] = a
    # D3
    d3 = {}
    for sd, r in load("A", SEEDS_NEW).items():
        if "d3" not in r:
            continue
        for vid, x in r["d3"].items():
            e = pd.DataFrame(x["errores"])
            e["s"] = pd.to_datetime(e["s"] + "-01")
            early = e["s"] < pd.Timestamp("1974-08-01")
            d3.setdefault(vid, []).append({
                "semilla": sd, "dif_replica": x["dif_replica"], "v_conj": x["v_conj"],
                "mse_s_<1974-08": float((e.loc[early, "e"] ** 2).mean()) if early.any() else float("nan"),
                "mse_s_>=1974-08": float((e.loc[~early, "e"] ** 2).mean()) if (~early).any() else float("nan"),
                "frac_s_<1974-08": float(early.mean()),
                "frac_n_ps<n_full": float((e["n_ps"] < e["n_full"]).mean()),
                "mse_n_ps<n_full": float((e.loc[e["n_ps"] < e["n_full"], "e"] ** 2).mean())
                if (e["n_ps"] < e["n_full"]).any() else float("nan"),
                "mse_n_ps=n_full": float((e.loc[e["n_ps"] == e["n_full"], "e"] ** 2).mean()),
                "v_conj_solo_n_igual": float((e.loc[e["n_ps"] == e["n_full"], "e"] ** 2).mean())})
    if d3:
        res["D3_max_dif_replica"] = float(max(x["dif_replica"] for v in d3.values() for x in v))
        res["D3"] = {vid: {k: float(np.nanmean([x[k] for x in v])) for k in v[0] if k != "semilla"}
                     for vid, v in sorted(d3.items())}
        # cobertura contrafactual (diagnóstico, NO elige): σ̂ con V_conj medida solo en los s con n_ps = n_full
        cf = []
        for sd, r in load("A", SEEDS_NEW).items():
            if "d3" not in r:
                continue
            alt = {vid: x for vid, x in r["d3"].items()}
            df = pd.DataFrame(r["serie"])
            va = []
            for vid in df["version"]:
                e = pd.DataFrame(alt[vid]["errores"])
                va.append(float((e.loc[e["n_ps"] == e["n_full"], "e"] ** 2).mean()))
            z = (df["G"] - df["mu"]) / np.sqrt(np.asarray(va))
            z_all = (df["G"] - df["mu"]) / df["sd"]
            msk = pd.to_datetime(df["mes"] + "-01") <= pd.Timestamp("1999-12-01")
            cf.append({"semilla": sd, "cob80_v13": float((z_all.abs() < Q80).mean()),
                       "cob80_contrafactual": float((z.abs() < Q80).mean()),
                       "cob80_v13_hasta_1999": float((z_all[msk].abs() < Q80).mean()),
                       "cob80_contrafactual_hasta_1999": float((z[msk].abs() < Q80).mean())})
        res["D3_contrafactual"] = {"por_semilla": cf,
                                   **{k: summary([c[k] for c in cf]) for k in cf[0] if k != "semilla"}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "resumen.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--arm", required=True, choices=("R0", "A", "B"))
    r.add_argument("--seed", type=int, required=True)
    r.add_argument("--d3", action="store_true")
    sp.add_parser("analyze")
    a = ap.parse_args()
    if a.cmd == "run":
        if a.arm == "R0" and a.seed not in SEEDS_OLD or a.arm != "R0" and a.seed not in SEEDS_NEW:
            raise SystemExit("semilla fuera del protocolo")
        print(json.dumps(run_seed(a.seed, a.arm, a.d3)), flush=True)
    else:
        res = analyze()
        print(json.dumps({k: v for k, v in res.items() if k not in ("R0_por_semilla",)}, indent=1,
                         ensure_ascii=False, default=str)[:20000])


if __name__ == "__main__":
    main()
