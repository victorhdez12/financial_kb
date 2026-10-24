"""Cálculo de potencia de la evaluación única (docs/models/power_holdout.md). SOLO desarrollo ≤ 2004.

Qué hace (decisión 4 del usuario, 23-oct): con la LONGITUD del periodo bloqueado (2005-01 → 2021-10, 202 meses; dato
público del preregistro) y la estructura de dependencia y varianza de las diferencias mensuales de log-loss de
DESARROLLO (M0 − modelo, ≤ 2004, corridas ya registradas de M1 v1 / M1 v2), simula evaluaciones únicas ficticias y
aplica el MISMO contraste del arnés (`metrics.boot_mean`: bootstrap circular por bloques de 12, 5.000 réplicas, semilla
fija; `p_h0` unilateral; IC 95 %) con el criterio de P-EVAL-BASE (≥ 0,05 nats y límite inferior > 0) y el ajuste de
Holm. Contraste principal (decisión del usuario, 24-oct): el POOL de log-scores {M0, estructural, TVTP} con Holm k = 1
(p < 0,05). Se mantiene k = 2 (dos aspirantes; peor caso p < 0,025) solo como referencia informativa.

No lee nada ≥ 2005 (ni de la etiqueta ni de las variables): solo los `scores.parquet` de corridas de desarrollo ya
registradas y la etiqueta oficial ≤ 2004 por la caja de desarrollo (para marcar los meses de giro, `month_cuts`).
No ajusta ningún modelo.

Simulación (por cada serie fuente d_t, t ≤ 2004, con su marca de giro):
  1. nulo: d0 = d − media, centrando por separado giros y estables (efecto 0 en los dos, dependencia y colas reales);
  2. una evaluación ficticia de n = 202 meses = bootstrap circular por bloques de 12 de los pares (d0_t, giro_t)
     (la proporción de giros varía como en el desarrollo);
  3. efecto: + δ_e en los meses estables y + δ_g en los de giro (escenarios: uniforme; solo en giros);
  4. contraste del arnés sobre la serie simulada → pasa / no pasa.
Potencia = fracción de evaluaciones ficticias que pasan. MDE = efecto verdadero con potencia ≥ 80 %.
Escenarios de ruido: x1 (el de la fuente), x1,5 (colas más gruesas) y x0,5 (supuesto para el pool: al mezclar con M0,
la diferencia mensual M0 − pool se encoge hacia 0; con peso w fuera de M0, d_pool ≈ w·d, desv. ≈ w·desv.). Es un
supuesto, no una medida: el pool aún no existe.
Uso: .venv/bin/python -m src.models.power research/trials/power_holdout.json  (una pasada).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.models import metrics as M

HOLDOUT_N = 202                      # 2005-01 → 2021-10 (P-EVAL-BASE §4; meses de calendario, todos con weight > 0)
RUNS = {                             # corridas de desarrollo ya registradas (research/trials/harness_runs.jsonl)
    "principal": "20261023-111824_m1v2_principal_512ecfcc",      # 1989-10 → 2004-12, 183 meses
    "long": "20261023-112028_m1v2_long_d6d807d6",                # 1978-07 → 2004-12, 318 meses (eje I = M0)
}
SOURCES = {   # nombre → (corrida, modelo, métrica). d = M0 − modelo (positivo = el modelo mejora)
    "M1v1_total": ("principal", "m1_logit_axis", "logloss"),
    "M1v2_total": ("principal", "m1v2_logit_axis", "logloss"),
    "M1v1_ejeG": ("principal", "m1_logit_axis", "ll_g"),
    "M1v2_ejeG": ("principal", "m1v2_logit_axis", "ll_g"),
    "M1v2g_largo": ("long", "m1v2_g", "logloss"),              # eje I de M0 ⇒ d total = d del eje G
}
BASE = "m0_calibrated_persistence"
THRESH = 0.05                        # criterio 1 de P-EVAL-BASE: mejora media ≥ 0,05 nats …
ALPHAS = {"holm_k1": 0.05, "holm_k2_peor": 0.025}   # k=1 (pool, principal): p < α; k=2 (referencia): p(1) < α/2


def runs_dir() -> Path:
    from src.models import trials
    return trials.runs_dir()


def load_dev_series(mode: str = "vintage") -> dict[str, pd.DataFrame]:
    """Diferencias mensuales M0 − modelo de las corridas de desarrollo y marca de giro (etiqueta oficial ≤ 2004)."""
    from src.models.vault import LabelVault
    lab = LabelVault().load(end="2004-12")
    out = {}
    for name, (run, model, metric) in SOURCES.items():
        S = pd.read_parquet(runs_dir() / RUNS[run] / "scores.parquet")
        S = S[S["mode"] == mode]
        a = S[S["model"] == BASE].set_index("month").sort_index()
        b = S[S["model"] == model].set_index("month").sort_index().loc[a.index]
        assert a.index.max() < pd.Timestamp("2005-01-01")
        cuts = M.month_cuts(lab.loc[lab.index <= a.index.max()]).loc[a.index]
        out[name] = pd.DataFrame({"d": (a[metric] - b[metric]).to_numpy(), "giro": cuts["giro"].to_numpy(bool),
                                  "brier": (a["brier"] - b["brier"]).to_numpy()}, index=a.index)
    return out


def lrv_se(x: np.ndarray, n: int, block: int = 12, reps: int = 5000, seed: int = 20261015) -> float:
    """Error típico de la media de n meses con la dependencia de x (bootstrap por bloques; escala 1/√n)."""
    idx = M.block_indices(len(x), block, reps, seed)
    return float(x[idx].mean(axis=1).std(ddof=1) * np.sqrt(len(x) / n))


def harness_test(sims: np.ndarray, boot: dict = M.BOOT, chunk: int = 16) -> dict[str, np.ndarray]:
    """El contraste de `metrics.boot_mean` vectorizado sobre filas (mismos índices y semilla que el arnés)."""
    n = sims.shape[1]
    idx = M.block_indices(n, boot["block"], boot["n"], boot["seed"])
    xb = sims.mean(axis=1)
    lo, ph0 = np.empty(len(sims)), np.empty(len(sims))
    a = (1 - boot["level"]) / 2
    for i in range(0, len(sims), chunk):
        m = sims[i:i + chunk][:, idx].mean(axis=2)                  # (chunk, réplicas)
        lo[i:i + chunk] = np.quantile(m, a, axis=1)
        ph0[i:i + chunk] = ((m - xb[i:i + chunk, None]) >= xb[i:i + chunk, None]).mean(axis=1)
    return {"mean": xb, "lo": lo, "p_h0": ph0}


def simulate(src: pd.DataFrame, delta_e: float, delta_g: float, n: int = HOLDOUT_N, nsim: int = 1000,
             seed: int = 7, scale: float = 1.0, block: int = 12) -> dict:
    d = src["d"].to_numpy(float).copy()
    g = src["giro"].to_numpy(bool)
    d0 = d.copy()
    d0[g] -= d[g].mean()
    d0[~g] -= d[~g].mean()
    d0 *= scale
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, len(d0), size=(nsim, nb))
    idx = ((starts[:, :, None] + np.arange(block)[None, None, :]) % len(d0)).reshape(nsim, -1)[:, :n]
    G = g[idx]
    X = d0[idx] + np.where(G, delta_g, delta_e)
    t = harness_test(X)
    res = {"delta_e": delta_e, "delta_g": delta_g, "efecto_total_esperado": float(np.mean(np.where(G, delta_g, delta_e))),
           "giro_frac_media": float(G.mean())}
    c1 = (t["mean"] >= THRESH) & (t["lo"] > 0)
    res["p_criterio1"] = float(c1.mean())
    for k, al in ALPHAS.items():
        res[f"p_{k}"] = float((c1 & (t["p_h0"] < al)).mean())
        res[f"p_solo_contraste_{k}"] = float((t["p_h0"] < al).mean())
    # contraste principal (decisión del usuario 24-oct): k1_* = un único contraste (pool), Holm k = 1 (p < 0,05);
    #   k2_*: referencia informativa, dos aspirantes, Holm k = 2 (peor caso: el otro no pasa ⇒ p < 0,025)
    #   *_actual: criterio 1 tal cual (≥ 0,05 nats y límite inferior del IC 95 % > 0)
    #   *_ic90: criterio 1 con el IC 90 % (límite inferior > 0 ⇔ p unilateral < 0,05 aprox.) — sería un cambio de
    #   criterio (decisión del usuario, a preregistrar), no lo que está escrito
    res["p_k1_actual"] = res["p_holm_k1"]
    res["p_k2_actual"] = res["p_holm_k2_peor"]
    res["p_k1_ic90"] = float(((t["mean"] >= THRESH) & (t["p_h0"] < 0.05)).mean())
    res["p_k2_ic90"] = float(((t["mean"] >= THRESH) & (t["p_h0"] < 0.025)).mean())
    res["p_k1_ic90_sin_umbral"] = float((t["p_h0"] < 0.05).mean())
    gm = np.array([x[gg].mean() if gg.any() else np.nan for x, gg in zip(X, G)])
    em = np.array([x[~gg].mean() for x, gg in zip(X, G)])
    res["p_criterio2_giros_ge0"] = float(np.nanmean(gm >= 0))
    res["p_criterio3_estables_ge_m005"] = float((em >= -0.05).mean())
    res["p_criterios_1_2_3_k1"] = float((c1 & (t["p_h0"] < 0.05) & (gm >= 0) & (em >= -0.05)).mean())
    res["p_criterios_1_2_3_holm_peor"] = float((c1 & (t["p_h0"] < 0.025) & (gm >= 0) & (em >= -0.05)).mean())
    return res


KEYS = ("p_k1_actual", "p_k2_actual", "p_k1_ic90", "p_k2_ic90", "p_k1_ic90_sin_umbral", "p_criterio1",
        "p_criterios_1_2_3_k1", "p_criterios_1_2_3_holm_peor")


def curve(src, kind: str, grid: np.ndarray, **kw) -> list[dict]:
    """Potencia en una rejilla de efectos. kind: 'uniforme' (δ en todos los meses) o 'giros' (δ solo en los meses de
    giro; estables 0)."""
    return [simulate(src, x if kind == "uniforme" else 0.0, x, **kw) for x in grid]


def mde_from(rows: list[dict], key: str, target: float = 0.8) -> dict:
    """Efecto mínimo con potencia ≥ target (interpolación lineal en la rejilla): δ y efecto total esperado."""
    for r0, r1 in zip(rows[:-1], rows[1:]):
        if r0[key] < target <= r1[key]:
            f = (target - r0[key]) / (r1[key] - r0[key])
            return {"delta": r0["delta_g"] + f * (r1["delta_g"] - r0["delta_g"]),
                    "efecto_total": r0["efecto_total_esperado"] + f * (r1["efecto_total_esperado"]
                                                                       - r0["efecto_total_esperado"])}
    if rows and rows[0][key] >= target:
        return {"delta": rows[0]["delta_g"], "efecto_total": rows[0]["efecto_total_esperado"], "cota": "≤"}
    return {"delta": None, "efecto_total": None, "nota": f"no se alcanza en la rejilla (máx. {rows[-1]['delta_g']})"}


def analytic(src: pd.DataFrame, n: int = HOLDOUT_N) -> dict:
    """Aproximación normal: SE con la varianza de largo plazo del desarrollo, reescalada a n meses."""
    d, g = src["d"].to_numpy(float), src["giro"].to_numpy(bool)
    frac = float(g.mean())
    se = lrv_se(d - d.mean(), n)
    ng = max(int(round(frac * n)), 1)
    se_g = lrv_se(d[g] - d[g].mean(), ng, block=6) if g.sum() > 12 else float("nan")
    se_e = lrv_se(d[~g] - d[~g].mean(), n - ng)
    z80 = norm.ppf(0.8)
    out = {"n_dev": int(len(d)), "giro_frac_dev": frac, "n_giro_esperado_holdout": ng,
           "media_dev": float(d.mean()), "media_dev_giro": float(d[g].mean()), "media_dev_estable": float(d[~g].mean()),
           "sd_mensual": float(d.std(ddof=1)), "se_holdout": se, "se_holdout_giro": se_g, "se_holdout_estable": se_e,
           "brier_media_dev": float(src["brier"].mean()),
           "z_dev_logloss": float(d.mean() / lrv_se(d - d.mean(), len(d))),
           "z_dev_brier": float(src["brier"].mean() / lrv_se(src["brier"].to_numpy() - src["brier"].mean(), len(d)))}
    for k, al in {"a0025": 0.025, "a005": 0.05}.items():
        out[f"mde_{k}"] = float((norm.ppf(1 - al) + z80) * se)
        out[f"mde_giro_{k}"] = float((norm.ppf(1 - al) + z80) * se_g)
        out[f"mde_estable_{k}"] = float((norm.ppf(1 - al) + z80) * se_e)
    # criterio 1 completo (≥ 0,05 y lo > 0): potencia aprox. con δ: P(x̄ ≥ max(0,05, 1,96·SE))
    out["umbral_observado_criterio1"] = float(max(THRESH, norm.ppf(0.975) * se))
    out["mde_criterio1_aprox"] = float(out["umbral_observado_criterio1"] + z80 * se)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Potencia de la evaluación única (solo desarrollo ≤ 2004)")
    ap.add_argument("dest")
    ap.add_argument("--nsim", type=int, default=1000)
    a = ap.parse_args()
    series = load_dev_series()
    out = {"holdout_n": HOLDOUT_N, "boot": M.BOOT, "nsim": a.nsim, "fuentes": {}}
    grid_u = np.round(np.arange(0.0, 0.401, 0.02), 3)
    grid_g = np.round(np.arange(0.0, 1.601, 0.1), 3)
    for name, src in series.items():
        r = {"analitico": analytic(src), "curvas": {}, "mde": {}}
        for cname, kind, grid, kw in (("uniforme", "uniforme", grid_u, {}),
                                      ("uniforme_colas_x1.5", "uniforme", grid_u, {"scale": 1.5}),
                                      ("uniforme_ruido_x0.5", "uniforme", grid_u, {"scale": 0.5}),
                                      ("solo_giros", "giros", grid_g, {})):
            rows = curve(src, kind, grid, nsim=a.nsim, **kw)
            r["curvas"][cname] = rows
            r["mde"][cname] = {k: mde_from(rows, k) for k in KEYS}
        # criterio 2 (giros ≥ 0) si la mejora está solo en los estables (giros 0): probabilidad de cumplirlo por azar
        r["criterio2_con_efecto_giro_0"] = simulate(src, 0.10, 0.0, nsim=a.nsim)
        out["fuentes"][name] = r
        print(name, json.dumps({c: {k: v["efecto_total"] for k, v in m.items()} for c, m in r["mde"].items()}),
              {k: round(v, 3) for k, v in r["analitico"].items() if k.startswith(("mde", "se", "giro", "n_"))},
              flush=True)
    Path(a.dest).parent.mkdir(parents=True, exist_ok=True)
    Path(a.dest).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
