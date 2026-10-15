"""Validación independiente de la etiqueta de régimen v1.1 candidata (commit a806561).

No escribe en data/archive ni toca src/. Lee la instantánea de entradas y los parquet oficiales.

    .venv/bin/python -m tests.validation.label_v1_1_validation salida.json

Bloques:
  1. Reproducción sin warehouse (db.connect bloqueado) → hash oficial, y v1.0 intacta.
  2. Diferencias v1.0 → v1.1 (todas las columnas y parámetros).
  3. Empalme IPC → PCE subyacente: ventanas, transformación, signo, error estándar, meses afectados.
  4. Lista negra: casos adversarios contra assert_no_forbidden.
  5. Política de filas maduras: ¿una instantánea posterior reescribe meses maduros?
  6. Persistencia point-in-time: reimplementación independiente (muestra puntuable).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace

import numpy as np
import pandas as pd

from src.labels import regime_us as R
from src.warehouse import db

OFFICIAL_V11 = "8425b403f14626a1728a0f66446565dd205720993a30e5fa4fe337385329c30b"
OFFICIAL_V10 = "38250f0a"
SNAP_SHA_FILE = "9cc855f86c6375e7dbc0610abd0c47773c27c3d7a804db14cf90acffa9f08238"
PCOLS = [f"p_{q}" for q in R.QUADRANTS]


def scored(df):
    return df[(df["weight"] > 0) & ~df["provisional"]]


# ------------------------------------------------------------------ 1
def reproduction() -> dict:
    def _blocked(*a, **k):
        raise RuntimeError("warehouse bloqueado por el validador")

    orig = db.connect
    db.connect = _blocked
    try:
        df, info = R.build(source="snapshot")
    finally:
        db.connect = orig
    off = pd.read_parquet(R.out_path())
    v10 = pd.read_parquet(R.out_dir() / "regime_us_v1.0.parquet")
    snap = info["meta"]["inputs_snapshot"]
    return {"hash": R.content_hash(df), "hash_ok": R.content_hash(df) == OFFICIAL_V11,
            "equals_official_file": bool(df.equals(off)), "snapshot_sha_file_ok": snap["sha256_file"] == SNAP_SHA_FILE,
            "v10_hash": R.content_hash(v10)[:8], "v10_intact": R.content_hash(v10).startswith(OFFICIAL_V10),
            "code_sha": info["meta"]["code"]["sha256_code"]}


# ------------------------------------------------------------------ 2
def diff_versions() -> dict:
    a = pd.read_parquet(R.out_dir() / "regime_us_v1.0.parquet").set_index("date")
    b = pd.read_parquet(R.out_path()).set_index("date")
    ma = json.loads((R.out_dir() / "regime_us_v1.0.meta.json").read_text())
    mb = json.loads((R.out_dir() / "regime_us_v1.1.meta.json").read_text())
    out = {"same_index": bool(a.index.equals(b.index)), "same_columns": list(a.columns) == list(b.columns)}
    cols = {}
    for c in a.columns:
        x, y = a[c], b[c]
        if pd.api.types.is_float_dtype(x):
            d = (x - y).abs()
            ch = d[d > 1e-12]
        else:
            ch = x[(x.astype(str) != y.astype(str))]
        cols[c] = {"n": int(len(ch)), "from": f"{ch.index.min():%Y-%m}" if len(ch) else None,
                   "to": f"{ch.index.max():%Y-%m}" if len(ch) else None,
                   "max_abs": float(d.max()) if pd.api.types.is_float_dtype(x) else None}
    out["columns"] = cols
    lab = a["label_hard"] != b["label_hard"]
    out["label_changes"] = [f"{d:%Y-%m}: {a.at[d, 'label_hard']}→{b.at[d, 'label_hard']}" for d in a.index[lab]]
    out["label_changes_scored_v11"] = int(lab[scored(b).index].sum())
    pa, pb = ma["params"], mb["params"]
    out["params_changed"] = {k: (pa.get(k), pb.get(k)) for k in sorted(set(pa) | set(pb)) if pa.get(k) != pb.get(k)}
    out["scalars"] = {k: (ma.get(k), mb.get(k)) for k in ("s_G", "s_I", "embargo_months", "provisional_months",
                                                          "first", "last", "sigma_i")}
    out["meta_keys_added"] = sorted(set(mb) - set(ma))
    out["code_git"] = mb["code"]
    return out


# ------------------------------------------------------------------ 3
def splice_study(inputs: dict) -> dict:
    p = R.PARAMS
    lv = inputs["levels"]
    pce = R.ann_change(R._cal(lv["PCEPILFE"]), p)
    cpi = R.ann_change(R._cal(lv["CPILFESL"]), p)
    d = (pce - cpi).dropna()  # convención PCE − IPC = ajuste que se suma al IPC
    t0 = d.index.min()
    res = {"first_overlap": f"{t0:%Y-%m}", "windows": {}}
    for n in (12, 24, 36, 48, 60, 69, 120):
        w = d.iloc[:n]
        # error estándar con autocorrelación: n efectivo ≈ n / 6 (ventanas de 6 m solapadas) — Newey-West simple
        x = w - w.mean()
        L = 6
        lrv = (x ** 2).mean() + 2 * sum((1 - k / (L + 1)) * (x * x.shift(k)).mean() for k in range(1, L + 1))
        res["windows"][n] = {"to": f"{w.index.max():%Y-%m}", "mean_pce_minus_cpi": round(float(w.mean()), 3),
                             "se_nw": round(float(np.sqrt(max(lrv, 0) / len(w))), 3)}
    res["calendar_1959_1964"] = round(float(d.loc["1959":"1964"].mean()), 3)
    res["full_sample"] = round(float(d.mean()), 3)
    # transformación alternativa: interanual (12 m) en lugar de la de I
    yoy_p = R._cal(lv["PCEPILFE"]).pct_change(12, fill_method=None) * 100
    yoy_c = R._cal(lv["CPILFESL"]).pct_change(12, fill_method=None) * 100
    dy = (yoy_p - yoy_c).dropna()
    res["yoy_first24"] = {"from": f"{dy.index.min():%Y-%m}", "mean": round(float(dy.iloc[:24].mean()), 3)}
    # sensibilidad de la etiqueta al ajuste
    base, _ = R.make_label(inputs, p, p.s_G_fixed, p.s_I_fixed)
    b = base.set_index("date")
    sens = {}
    for adj in (-0.4, 0.0, 0.06, 0.204350901, 0.3, 0.5):
        lab, _ = R.make_label(inputs, p, p.s_G_fixed, p.s_I_fixed, splice=adj)
        l = lab.set_index("date")
        ch = l.index[(l["label_hard"] != b["label_hard"])]
        sens[str(adj)] = {"changed_vs_v11": len(ch), "months": [f"{x:%Y-%m}" for x in ch],
                          "I_1959_03": round(float(l.at[pd.Timestamp("1959-03-01"), "I"]), 2)}
    res["label_sensitivity"] = sens
    res["I_1959_04_pce"] = round(float(b.at[pd.Timestamp("1959-04-01"), "I"]), 2)
    # meses del tramo 1957-04 → 1959-03 con |I − κ| < s_I (los que dependen del ajuste)
    seg = b.loc["1957-04":"1959-03"]
    res["segment_near_kappa"] = int(((seg["I"] - p.kappa).abs() < p.s_I_fixed).sum())
    res["segment_n"] = int(len(seg))
    return res


# ------------------------------------------------------------------ 4
def forbidden_probe(meta: dict) -> dict:
    extra = meta["forbidden_features"]["series"]
    cases = ["usrec", "USREC", "label_hard", "p_expansion", "GDPPOT", "fed_ebp_recession_prob", "I", "G",
             # variantes derivadas (desfases / transformaciones)
             "usrec_lag1", "USREC_l12", "p_expansion_lag5", "max_prob_l5", "GDPPOT_yoy", "gap_GDPPOT",
             "nyfed_recprob_target_l1", "G_lag5", "lbl_hard_l5", "regime_label_t5",
             # deben pasar
             "INDPRO", "PAYEMS_yoy", "T10Y3M", "SAHMREALTIME"]
    out = {}
    for c in cases:
        try:
            R.assert_no_forbidden([c], extra=extra)
            out[c] = "pasa"
        except AssertionError:
            out[c] = "bloqueada"
    return out


# ------------------------------------------------------------------ 5
def maturity_policy(inputs: dict) -> dict:
    """Simula la instantánea que se habría congelado 12 y 24 meses antes (niveles truncados; misma
    vintage) y compara sus meses MADUROS con los de la v1.1: si cambian, una v1.2 con instantánea nueva
    reescribirá filas maduras."""
    p = R.PARAMS
    off = pd.read_parquet(R.out_path()).set_index("date")
    out = {}
    for back in (12, 24, 60):
        cut = {sid: s.dropna().index.max() - pd.DateOffset(months=back) for sid, s in inputs["levels"].items()}
        lab, _ = R.make_label(inputs, p, p.s_G_fixed, p.s_I_fixed, cutoff=cut,
                              splice=float(json.loads((R.out_dir() / "regime_us_v1.1.meta.json").read_text())
                                           ["splice_cpi_core"]["adj_pp"]))
        lab = lab.set_index("date")
        lab["provisional"] = False
        lab.iloc[-p.provisional_months:, lab.columns.get_loc("provisional")] = True
        common = lab.index.intersection(off.index)
        mat = [d for d in common if not lab.at[d, "provisional"] and not off.at[d, "provisional"]
               and off.at[d, "weight"] > 0]
        a, b = lab.loc[mat], off.loc[mat]
        tv = 0.5 * (a[PCOLS] - b[PCOLS]).abs().sum(axis=1)
        out[back] = {"mature_common": len(mat), "hard_changes": int((a["label_hard"] != b["label_hard"]).sum()),
                     "dp_mean": round(float(tv.mean()), 4), "dG_max": round(float((a["G"] - b["G"]).abs().max()), 3),
                     "dI_max": round(float((a["I"] - b["I"]).abs().max()), 3),
                     "last_changed": (f"{a.index[a['label_hard'] != b['label_hard']].max():%Y-%m}"
                                      if (a["label_hard"] != b["label_hard"]).any() else None)}
    return out


# ------------------------------------------------------------------ 6
def pit_persistence(inputs: dict, meta: dict) -> dict:
    p = R.PARAMS
    off = pd.read_parquet(R.out_path()).set_index("date")
    m = scored(off)
    ll = R.label_lag(p)
    lag, mb = ll["label_lag"], ll["months_back"]
    # retraso de las series de inflación que no están en months_back: el IPC sale ~día 15 → 1 mes
    mb_full = {sid: mb.get(sid, R.months_back(sid)) for sid in inputs["levels"]}
    hits, n, miss, same_shift = 0, 0, 0, 0
    hits_hold, n_hold = 0, 0
    for t in m.index:
        cut = {sid: t - pd.DateOffset(months=mb_full[sid]) for sid in inputs["levels"]}
        lab, _ = R.make_label(inputs, p, p.s_G_fixed, p.s_I_fixed, cutoff=cut)  # empalme re-medido con datos ≤ t
        lab = lab.set_index("date")
        s = t - pd.DateOffset(months=lag)
        # ¿se podría calcular una etiqueta más reciente que t−lag? (comprobación del lag)
        if len(lab) and lab.index.max() > s:
            miss += 1
        if s not in lab.index:
            continue
        n += 1
        h = lab.at[s, "label_hard"] == m.at[t, "label_hard"]
        hits += h
        same_shift += lab.at[s, "label_hard"] == off["label_hard"].shift(lag).at[t]
        if t >= pd.Timestamp(p.holdout_start):
            n_hold += 1
            hits_hold += h
    return {"label_lag": lag, "months_back": mb_full, "n": n, "acc": hits / n, "acc_holdout": hits_hold / n_hold,
            "n_holdout": n_hold, "months_with_label_after_t_minus_lag": miss,
            "same_as_final_shift": same_shift / n}


def main(path: str) -> None:
    inputs, _ = R.read_snapshot()
    meta = json.loads((R.out_dir() / "regime_us_v1.1.meta.json").read_text())
    res = {"reproduction": reproduction(), "diff": diff_versions(), "splice": splice_study(inputs),
           "forbidden": forbidden_probe(meta), "maturity": maturity_policy(inputs),
           "pit": pit_persistence(inputs, meta)}
    with open(path, "w") as f:
        json.dump(res, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str)[:20000])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "label_v1_1_validation.json")
