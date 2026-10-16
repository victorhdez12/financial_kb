"""Métricas del arnés (docs/models/harness.md §6).

- Probabilidades: se recortan a 1e-4 y se renormalizan (mismo recorte que labels/checks.py y pit.score_training,
  para reproducir el listón de la persistencia PIT).
- log-loss BLANDA de 4 cuadrantes (principal): −Σ_q T_q · log P_q contra las probabilidades de la etiqueta oficial.
- log-loss BINARIA por eje (P-EVAL-MOD): P(G alto) = P_expansion + P_late_cycle frente a `p_g_high`;
  P(I alta) = P_late_cycle + P_stagflation frente a `p_i_high` (recorte binario 1e-4). Como la etiqueta define
  p_q = p_G·p_I (ficha §5), la log-loss de 4 clases de un modelo producto es la suma de las dos binarias.
- Brier multiclase blando: Σ_q (P_q − T_q)²; BSS = 1 − ΣBrier_modelo / ΣBrier_ref (mismos meses, mismo modo).
- Acierto: argmax P = etiqueta dura oficial (se informa, no decide).
- Intervalos: bootstrap por bloques CIRCULAR de 12 meses (24 como sensibilidad), 5.000 réplicas, semilla 20261015,
  percentil 95 % (adenda P-EVAL-MOD). Se publican dos cantidades distintas:
    `frac_rep_le0` = proporción de réplicas con media ≤ 0 (la "p unilateral" preregistrada en P-EVAL-MOD; es un
                     percentil-bootstrap, NO un p-valor bajo H0; antes se llamaba `p_le0`);
    `p_h0`         = p-valor unilateral bajo H0 (media = 0) con la distribución bootstrap centrada:
                     P(m* − x̄ ≥ x̄).
- Holm sobre una familia de p-valores; prueba de signo (binomial bilateral) por episodio/giro.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

QUADS = ("expansion", "late_cycle", "stagflation", "low_growth_disinfl")
P_COLS = [f"p_{q}" for q in QUADS]
CLIP = 1e-4
BOOT = {"block": 12, "n": 5000, "seed": 20261015, "level": 0.95}
BOOT24 = {**BOOT, "block": 24}
G_HIGH = np.array([1.0, 1.0, 0.0, 0.0])        # cuadrantes con G alto (expansion, late_cycle)
I_HIGH = np.array([0.0, 1.0, 1.0, 0.0])        # cuadrantes con I alta (late_cycle, stagflation)


def prep(P: np.ndarray) -> np.ndarray:
    P = np.clip(np.asarray(P, float), CLIP, 1)
    return P / P.sum(axis=1, keepdims=True)


def axis_probs(P: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """P(G alto) y P(I alta) de una predicción de 4 cuadrantes (tras `prep`)."""
    P = prep(P)
    return P @ G_HIGH, P @ I_HIGH


def combine_axes(pg: np.ndarray, pi: np.ndarray) -> np.ndarray:
    """4 cuadrantes como producto de los ejes (independencia condicional; ficha §5): columnas en el orden de QUADS."""
    pg, pi = np.asarray(pg, float), np.asarray(pi, float)
    return np.column_stack([pg * (1 - pi), pg * pi, (1 - pg) * pi, (1 - pg) * (1 - pi)])


def binary_logloss(p: np.ndarray, t: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, float), CLIP, 1 - CLIP)
    t = np.asarray(t, float)
    return -(t * np.log(p) + (1 - t) * np.log(1 - p))


def monthly_scores(P: np.ndarray, T: np.ndarray, hard: np.ndarray) -> pd.DataFrame:
    """Pérdidas mes a mes: log-loss blanda (4 clases), log-loss binaria por eje, Brier blando y acierto."""
    P, T = prep(P), np.asarray(T, float)
    pg, pi = P @ G_HIGH, P @ I_HIGH
    tg, ti = T @ G_HIGH, T @ I_HIGH
    return pd.DataFrame({"logloss": -(T * np.log(P)).sum(axis=1),
                         "ll_g": binary_logloss(pg, tg), "ll_i": binary_logloss(pi, ti),
                         "brier": ((P - T) ** 2).sum(axis=1),
                         "hit": (np.array(QUADS)[P.argmax(axis=1)] == np.asarray(hard)).astype(float),
                         "pg": pg, "pi": pi})


def block_indices(n: int, block: int, n_rep: int, seed: int) -> np.ndarray:
    """Índices del bootstrap por bloques circular (n_rep × n)."""
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(n_rep, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    return idx.reshape(n_rep, -1)[:, :n]


def boot_mean(x: np.ndarray, boot: dict = BOOT) -> dict:
    """Media de una serie mensual con IC por bloques; `frac_rep_le0` (percentil, preregistrado) y `p_h0`."""
    x = np.asarray(x, float)
    if len(x) == 0:
        return {"mean": np.nan, "lo": np.nan, "hi": np.nan, "frac_rep_le0": np.nan, "p_h0": np.nan, "n": 0,
                "block": boot["block"]}
    idx = block_indices(len(x), boot["block"], boot["n"], boot["seed"])
    m = x[idx].mean(axis=1)
    a = (1 - boot["level"]) / 2
    xb = float(x.mean())
    return {"mean": xb, "lo": float(np.quantile(m, a)), "hi": float(np.quantile(m, 1 - a)),
            "frac_rep_le0": float((m <= 0).mean()), "p_h0": float(((m - xb) >= xb).mean()), "n": int(len(x)),
            "block": boot["block"]}


def boot_bss(b_model: np.ndarray, b_ref: np.ndarray, boot: dict = BOOT) -> dict:
    """BSS = 1 − ΣBrier_modelo / ΣBrier_ref, con IC por bloques (mismos índices para los dos)."""
    b_model, b_ref = np.asarray(b_model, float), np.asarray(b_ref, float)
    idx = block_indices(len(b_model), boot["block"], boot["n"], boot["seed"])
    s = 1 - b_model[idx].sum(axis=1) / b_ref[idx].sum(axis=1)
    a = (1 - boot["level"]) / 2
    return {"bss": float(1 - b_model.sum() / b_ref.sum()), "lo": float(np.quantile(s, a)),
            "hi": float(np.quantile(s, 1 - a))}


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """p-valores ajustados por Holm (step-down, monotonía forzada)."""
    items = sorted(((k, v) for k, v in pvals.items() if v == v), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def sign_test(wins: int, n: int) -> float:
    """Prueba de signo bilateral (binomial 1/2)."""
    if n == 0:
        return float("nan")
    k = min(wins, n - wins)
    p = sum(math.comb(n, j) for j in range(0, k + 1)) / 2 ** n
    return float(min(1.0, 2 * p))


def sign_test_greater(wins: int, n: int) -> float:
    """Prueba de signo UNILATERAL: P(Binomial(n, 1/2) ≥ wins)."""
    if n == 0:
        return float("nan")
    return float(sum(math.comb(n, j) for j in range(wins, n + 1)) / 2 ** n)


def summary(sc: pd.DataFrame) -> dict:
    out = {"n": int(len(sc)), "logloss": float(sc["logloss"].mean()), "brier": float(sc["brier"].mean()),
           "acierto": float(sc["hit"].mean())}
    if "ll_g" in sc:
        out["ll_g"], out["ll_i"] = float(sc["ll_g"].mean()), float(sc["ll_i"].mean())
    return out


def calibration(p: np.ndarray, t: np.ndarray, bins: int = 10) -> list[dict]:
    """Fiabilidad por tramo de probabilidad predicha (anchura fija 1/bins): n, media predicha, media observada."""
    p, t = np.asarray(p, float), np.asarray(t, float)
    k = np.minimum((p * bins).astype(int), bins - 1)
    return [{"tramo": f"{b / bins:.1f}-{(b + 1) / bins:.1f}", "n": int((k == b).sum()),
             "pred": float(p[k == b].mean()), "obs": float(t[k == b].mean())} for b in range(bins) if (k == b).any()]


# ------------------------------------------------------------------ cortes y episodios (fijados a priori, §6)
def g_hard(lab: pd.DataFrame) -> pd.Series:
    """Eje G duro de la etiqueta oficial: 1 si p_g_high ≥ 0,5."""
    pg = lab["p_g_high"] if "p_g_high" in lab else lab[P_COLS].to_numpy(float) @ G_HIGH
    return pd.Series((np.asarray(pg, float) >= 0.5).astype(int), index=lab.index)


def runs(s: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp, object, int]]:
    """Rachas (desde, hasta, valor, longitud) de una serie mensual."""
    rid = (s != s.shift()).cumsum()
    return [(g.index[0], g.index[-1], g.iloc[0], len(g)) for _, g in s.groupby(rid)]


def g_smoothed(lab: pd.DataFrame, min_run: int = 6) -> pd.Series:
    """Eje G duro oficial SIN parpadeos (regla fijada a priori, Validador v2 M2-3): una racha de menos de `min_run`
    meses toma el valor de la última racha larga (≥ `min_run`) anterior; las rachas cortas del principio de la muestra
    (sin racha larga previa) conservan su valor. Así dos giros seguidos nunca van en la misma dirección."""
    g = g_hard(lab)
    out, prev_long = g.copy(), None
    for a, b, v, n in runs(g):
        if n >= min_run:
            prev_long = v
        elif prev_long is not None:
            out[(out.index >= a) & (out.index <= b)] = prev_long
    return out


def g_turns(lab: pd.DataFrame, min_run: int = 6) -> list[dict]:
    """Giros del eje G (definición v2.1, fijada a priori; M2-3): cambios de la serie SIN parpadeos (`g_smoothed`).
    El mes del giro es el primer mes de la racha larga (≥ `min_run`) del lado nuevo; `hasta` es el final de esa racha
    (con los parpadeos que absorbe). Los giros alternan de dirección por construcción."""
    out = []
    for i, (a, b, v, n) in enumerate(runs(g_smoothed(lab, min_run))):
        if i == 0:
            continue
        out.append({"mes": a, "hasta": b, "nuevo": int(v), "n": n})
    return out


def turn_windows(turns: list[dict], window=(-3, 6)) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Ventanas SIN solape alrededor de cada giro (M2-3): [mes − 3, mes + 6], y si la ventana posterior de un giro
    alcanza la anterior del siguiente, se recorta para que el siguiente conserve sus 3 meses previos."""
    out = []
    for i, t in enumerate(turns):
        a = t["mes"] + pd.DateOffset(months=window[0])
        b = t["mes"] + pd.DateOffset(months=window[1])
        if i + 1 < len(turns):
            nxt = turns[i + 1]["mes"] + pd.DateOffset(months=window[0])
            b = min(b, nxt - pd.DateOffset(months=1))
        if out:
            a = max(a, out[-1][1] + pd.DateOffset(months=1))
        out.append((a, b))
    return out


def episodes(lab: pd.DataFrame, pad: int = 6, min_run: int = 6, turn_window=(-3, 6)) -> list[dict]:
    """Episodios fijados a priori (decisión del usuario, 2026-10-16; giros redefinidos en la v2.1, M2-3):
    (a) recesiones NBER (`usrec` oficial) ± `pad` meses;
    (b) rachas de la etiqueta dura oficial de ≥ `min_run` meses (los parpadeos ya pesan en el corte de giros);
    (c) giros del eje G (`g_turns`, sin parpadeos), ventana de −3 a +6 meses SIN solape (`turn_windows`).
    `truncado` (B2-5): el episodio empieza o acaba en el borde de la muestra (recesión ya en curso al empezar, o su
    ventana ± pad sale de la muestra; racha que empieza en el primer mes o acaba en el último). Los truncados se
    informan pero NO entran en la prueba de signo."""
    out = []
    first, last = lab.index.min(), lab.index.max()
    u = lab["usrec"].fillna(0).astype(int)
    starts = u.index[(u == 1) & (u.shift(1, fill_value=0) == 0)]
    ends = u.index[(u == 1) & (u.shift(-1, fill_value=0) == 0)]
    for s, e in zip(starts, ends):
        a, b = s - pd.DateOffset(months=pad), e + pd.DateOffset(months=pad)
        out.append({"tipo": "recesion_nber", "id": f"rec {s:%Y-%m}", "desde": a, "hasta": b,
                    "truncado": bool(s == first or a < first or b > last)})
    for a, b, v, n in runs(lab["label_hard"]):
        if n >= min_run:
            out.append({"tipo": "racha_regimen", "id": f"{v} {a:%Y-%m}", "desde": a, "hasta": b,
                        "truncado": bool(a == first or b == last)})
    tt = g_turns(lab, min_run)
    for t, (a, b) in zip(tt, turn_windows(tt, turn_window)):
        out.append({"tipo": "giro_g", "id": f"G{'↑' if t['nuevo'] else '↓'} {t['mes']:%Y-%m}", "desde": a, "hasta": b,
                    "truncado": bool(a < first or b > last)})
    return out


def month_cuts(lab: pd.DataFrame, lag: int = 5) -> pd.DataFrame:
    """Cortes mensuales de la etiqueta oficial: giro (dura(t) ≠ dura(t−lag)), meses desde el último cambio de la dura,
    cuadrante oficial y frontera."""
    h = lab["label_hard"]
    prev = h.shift(lag, freq="MS").reindex(h.index)
    since = []
    c = 0
    for i in range(len(h)):
        c = 0 if i == 0 or h.iloc[i] != h.iloc[i - 1] else c + 1
        since.append(c)
    since = pd.Series(since, index=h.index)
    tramo = pd.cut(since, [-1, 5, 11, 10 ** 6], labels=["0-5", "6-11", "≥12"]).astype(str)
    out = pd.DataFrame({"giro": (h != prev) & prev.notna(), "desde_cambio": tramo, "cuadrante": h}, index=h.index)
    out["frontera"] = lab["frontera"].astype(bool) if "frontera" in lab else False
    return out


def detection(pg: pd.Series, lab: pd.DataFrame, min_run: int = 6, sustain: int = 3, lead: int = 3) -> dict:
    """Retraso de detección de los giros de G y falsas alarmas (Estratega E6; definición v2.1 fijada a priori, M2-3).
    - Giros: `g_turns` (sin parpadeos, alternos) de la etiqueta oficial en la muestra puntuada.
    - Confirmación: primer mes c en el que P(G alto) lleva `sustain` meses seguidos (c − 2, c − 1, c) del lado nuevo
      de 0,5, buscando desde el mes del giro − `lead` (se permite ANTICIPAR) hasta el final de la racha nueva.
    - Retraso = c − mes del giro: va de −`lead` + `sustain` − 1 (= −1 con 3 y 3: confirmado un mes antes del giro)…
      en adelante; NO se acota en 0. Un modelo que confirma antes del giro puntúa mejor que uno que confirma después.
    - Censurado: no se confirma dentro de la racha nueva (o de la muestra). Se cuenta APARTE y NO entra en la media.
    - Falsas alarmas: en la parte estable de las rachas de G ≥ `min_run` (a partir del mes `min_run` de la racha),
      número de veces que P(G alto) pasa al lado contrario al oficial; tasa por año de meses estables (sin cambios)."""
    gh = g_hard(lab).reindex(pg.index)
    side = (pg >= 0.5).astype(int)
    delays = []
    for t in g_turns(lab.loc[lab.index.isin(pg.index)], min_run):
        lo = t["mes"] - pd.DateOffset(months=lead)
        seg = side[(side.index >= lo) & (side.index <= t["hasta"])]
        c = None
        for i in range(sustain - 1, len(seg)):
            if (seg.iloc[i - sustain + 1:i + 1] == t["nuevo"]).all():
                c = seg.index[i]
                break
        rec = {"mes": f"{t['mes']:%Y-%m}", "nuevo": t["nuevo"], "racha_meses": t["n"], "detectado": c is not None,
               "retraso": None}
        if c is not None:
            rec["retraso"] = int((c.year - t["mes"].year) * 12 + c.month - t["mes"].month)
            rec["confirmacion"] = f"{c:%Y-%m}"
        delays.append(rec)
    stable = pd.Series(False, index=pg.index)
    for a, b, _, n in runs(gh.dropna()):
        if n >= min_run:
            stable[(stable.index >= a + pd.DateOffset(months=min_run)) & (stable.index <= b)] = True
    wrong = (side != gh) & stable
    fa = int((wrong & ~wrong.shift(1, fill_value=False)).sum())
    yrs = stable.sum() / 12
    det = [d["retraso"] for d in delays if d["detectado"]]
    return {"definicion": "v2.1 (confirmación, censura aparte, sin parpadeos, anticipación ≤ %d m)" % lead,
            "giros": delays, "n_giros": len(delays), "detectados": len(det), "censurados": len(delays) - len(det),
            "retraso_medio": float(np.mean(det)) if det else np.nan,
            "falsas_alarmas": fa, "meses_estables": int(stable.sum()),
            "falsas_alarmas_por_año": float(fa / yrs) if yrs else np.nan}


def detection_vs(dm: dict, dc: dict) -> dict:
    """Comparación PAREADA del retraso (modelo − comparador) en los giros detectados por los DOS; censurados aparte.
    < 0 = el modelo confirma antes."""
    cm = {g["mes"]: g for g in dc["giros"]}
    pairs = [g["retraso"] - cm[g["mes"]]["retraso"] for g in dm["giros"]
             if g["detectado"] and g["mes"] in cm and cm[g["mes"]]["detectado"]]
    return {"n_pares": len(pairs), "retraso_pareado_medio": float(np.mean(pairs)) if pairs else np.nan,
            "censurados_modelo": dm["censurados"], "censurados_comparador": dc["censurados"],
            "falsas_alarmas_año_modelo_menos_comparador": dm["falsas_alarmas_por_año"] - dc["falsas_alarmas_por_año"]}
