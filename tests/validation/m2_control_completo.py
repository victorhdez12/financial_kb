"""Validador: control sintético COMPLETO de M2 v1.3 (protocolo prerregistrado
docs/validation/2026-10-25_m2_control_completo_protocolo.md, commit 7587fd0).

Copia de tests/validation/m2_v13_control_ampliado.py con SOLO estos cambios (§6 del protocolo): brazo C
(Synth(seed, end="2009-12")), semillas 2001-2040, salida nueva, aserción de integridad, sin rama D3 y veredicto
de §4.

SOLO datos sintéticos (tests/m2_synth.py). No carga la etiqueta, ni la base PIT, ni niveles reales; no registra nada.
No modifica el código de producción: reproduce el bucle de `src/models/pool_controls.py::m2_planted` y guarda la serie
mes a mes.

    .venv/bin/python tests/validation/m2_control_completo.py run --arm R0 --seed 3
    .venv/bin/python tests/validation/m2_control_completo.py run --arm C --seed 2001
    .venv/bin/python tests/validation/m2_control_completo.py analyze
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

OUT = REPO / "research" / "validation" / "m2_control_completo"
Q80, Q50, Q95 = norm.ppf(0.9), norm.ppf(0.75), norm.ppf(0.975)
SEEDS_OLD = (3, 7, 11, 21)
SEEDS_NEW = tuple(range(2001, 2041))
N_SEEDS = 40
LO, HI = 0.75, 0.85
N_CORTES = 296


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


def run_seed(seed: int, arm: str) -> dict:
    t0 = time.time()
    MS.clear_engines()
    s = Synth(seed) if arm == "R0" else Synth(seed, end="2009-12")
    G = s.true_G()
    m = MS.StructuralG(rev="none")
    key = f"controles{seed}" if arm == "R0" else f"validador_{arm}_{seed}"
    rows = []
    for T in pd.date_range("1980-01-01", "2004-08-01", freq="MS"):
        info = s.info(T, data_key=key)
        m.fit_axis_continuous("G", None, None, None, None, info)
        mu, sd = m.predict_axis_continuous("G", pd.DataFrame(index=[T]), info)
        v = m._v
        rows.append({"mes": f"{T:%Y-%m}", "mu": float(mu[0]), "sd": float(sd[0]), "G": float(G[T]),
                     "version": v.id, "v_conj": float(v.v_conj), "n_conj": int(v.n_conj), "v_tend": float(v.v_tend),
                     "conv": bool(v.converged), "kept": bool(v.kept_previous)})
    df = pd.DataFrame(rows)
    # §3 integridad: antes de contar y antes de escribir nada
    ok = (len(df) == N_CORTES and np.isfinite(df[["G", "mu", "sd"]].to_numpy()).all() and (df["sd"] > 0).all())
    if not ok:
        raise SystemExit(f"integridad §3 fallida en {arm}_{seed}: cortes={len(df)}; no se escribe nada")
    z = (df["G"] - df["mu"]) / df["sd"]
    res = {"semilla": seed, "brazo": arm, "cortes": len(df), "cobertura_80": float((z.abs() < Q80).mean()),
           "segundos": round(time.time() - t0, 1), "serie": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{arm}_{seed}.json").write_text(json.dumps(res, ensure_ascii=False))
    return {k: v for k, v in res.items() if k != "serie"}


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


def veredicto(principal: bool, secundario: bool) -> str:
    """Tabla de §4 del protocolo."""
    if not principal:
        return "NO CUMPLE"
    return "CUMPLE" if secundario else "CUMPLE CON RESERVA (dispersión entre semillas)"


def analyze() -> dict:
    res = {"protocolo": "docs/validation/2026-10-25_m2_control_completo_protocolo.md (7587fd0)"}
    # R0 (precondición §2)
    ref = json.loads((REPO / "research/trials/m2/controles_m2_v13.json").read_text())["cobertura_80"]
    r0 = load("R0", SEEDS_OLD)
    res["R0"] = {str(sd): {"replica": r["cobertura_80"], "constructor": ref[str(sd)],
                           "dif": abs(r["cobertura_80"] - ref[str(sd)]), "segundos": r["segundos"]}
                 for sd, r in r0.items()}
    res["R0_ok"] = bool(r0) and len(r0) == len(SEEDS_OLD) and all(v["dif"] < 1e-9 for v in res["R0"].values())
    res["R0_por_semilla"] = {str(sd): per_seed(r) for sd, r in r0.items()}
    # Brazo C (criterio §4)
    rr = load("C", SEEDS_NEW)
    if rr:
        ps = {sd: per_seed(r) for sd, r in rr.items()}
        for sd, r in rr.items():
            ps[sd]["sd_G"] = float(pd.DataFrame(r["serie"])["G"].std(ddof=1))
        cov = [p["cob80"] for p in ps.values()]
        sm = summary(cov)
        frac = float(np.mean([(LO <= c <= HI) for c in cov]))
        principal = bool(LO <= sm["ic95"][0] and sm["ic95"][1] <= HI)
        secundario = bool(frac >= 0.70)
        a = {"semillas": sorted(rr), "n_semillas": len(rr), "cob80": sm, "fraccion_en_rango": frac,
             "principal_cumple": principal, "secundario_cumple": secundario,
             "veredicto": veredicto(principal, secundario) if len(rr) == N_SEEDS else "INCOMPLETO: no hay 40 semillas"}
        for k in ("cob50", "cob95", "z2", "kurt_exc", "sesgo_medio_z", "rmse", "sd_media", "sd_G", "cob80_1980_1989",
                  "cob80_1990_1999", "cob80_2000_2004", "cob80_hasta_1999", "z2_1980_1989", "z2_1990_1999",
                  "z2_2000_2004", "z2_hasta_1999", "se_bloque12", "se_bloque24", "se_bloque48", "n_ef_bloque12",
                  "n_ef_bloque24", "n_ef_bloque48"):
            a[k] = summary([p[k] for p in ps.values()])
        a["sin_convergencia_total"] = int(sum(p["sin_convergencia"] for p in ps.values()))
        a["segundos_medios"] = float(np.mean([r["segundos"] for r in rr.values()]))
        a["por_semilla"] = {str(sd): {k: p[k] for k in ("cob80", "cob50", "z2", "cob80_hasta_1999",
                                                         "cob80_2000_2004", "se_bloque24")} for sd, p in ps.items()}
        res["C"] = a
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "resumen.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--arm", required=True, choices=("R0", "C"))
    r.add_argument("--seed", type=int, required=True)
    sp.add_parser("analyze")
    a = ap.parse_args()
    if a.cmd == "run":
        if a.arm == "R0" and a.seed not in SEEDS_OLD or a.arm == "C" and a.seed not in SEEDS_NEW:
            raise SystemExit("semilla fuera del protocolo")
        print(json.dumps(run_seed(a.seed, a.arm)), flush=True)
    else:
        res = analyze()
        print(json.dumps({k: v for k, v in res.items() if k not in ("R0_por_semilla",)}, indent=1,
                         ensure_ascii=False, default=str)[:20000])


if __name__ == "__main__":
    main()
