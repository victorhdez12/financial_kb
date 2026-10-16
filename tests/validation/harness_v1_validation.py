"""Validador (auditoría del arnés walk-forward v1, commit b01e7ee). Solo ≤ 2004; nunca el periodo bloqueado.

Todas las pruebas de la caja fuerte que necesitan filas ≥ 2005 usan etiquetas SINTÉTICAS en un directorio temporal.
No se define FKB_HOLDOUT_UNLOCK: el camino de desbloqueo se prueba cambiando el NOMBRE de la variable que mira la caja
fuerte (V.UNLOCK_ENV) y solo sobre ficheros sintéticos. Registro, artefactos y trial log redirigidos a un temporal.

Ejecutar: .venv/bin/python tests/validation/harness_v1_validation.py <salida.json> [secciones...]
secciones: hash labeler vault vars metrics power episodes (por defecto, todas)
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="fkb_val_harness_"))
os.environ["FKB_TRIALS_DIR"] = str(TMP / "trials")
os.environ["FKB_RUNS_DIR"] = str(TMP / "runs")
os.environ["FKB_TRIAL_LOG"] = str(TMP / "trial_log.md")
os.environ.pop("FKB_HOLDOUT_UNLOCK", None)
(TMP / "trial_log.md").write_text("| cabecera |\n")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.features import pit as P  # noqa: E402
from src.features.placebo import PLACEBO_TOL, fit_logit, predict_logit  # noqa: E402
from src.labels import regime_us as R  # noqa: E402
from src.models import base as B  # noqa: E402
from src.models import harness as H  # noqa: E402
from src.models import metrics as M  # noqa: E402
from src.models import vault as V  # noqa: E402
from src.models.pit_labels import PITLabeler  # noqa: E402

HOLD = pd.Timestamp(R.PARAMS.holdout_start)
OUT: dict = {"tmp": str(TMP)}
DATAS: dict = {}


def datas(mode):
    if mode not in DATAS:
        DATAS[mode] = H.PITData(mode)
    return DATAS[mode]


def official_dev():
    lab = V.LabelVault().load()
    assert lab.index.max() < HOLD
    return lab


# ------------------------------------------------------------------ 1. hash de resultados frente a flotantes
def sec_hash():
    cfg = H.HarnessConfig.from_yaml(H.REPO / "config" / "harness" / "baselines_v1.yaml")
    res = H.run(cfg, datas={m: datas(m) for m in P.MODES}, record=False)
    out = {"hash": res["results_sha256"], "n": res["report"]["muestra"]}
    labels = {m: datas(m).score_labels(cfg.test_end) for m in P.MODES}
    for name, eps in (("1_ulp", None), ("1e-13", 1e-13), ("1e-10", 1e-10)):
        p = res["preds"].copy()
        sel = p["model"] == "climatology"
        v = p.loc[sel, "p_expansion"].to_numpy()
        p.loc[sel, "p_expansion"] = np.nextafter(v, 2) if eps is None else v + eps
        S, rep = H.score(p, labels, cfg)
        out[f"perturb_{name}"] = {"hash_igual": H.results_hash(p, rep) == res["results_sha256"],
                                  "dif_max_logloss": abs(rep["modelos"]["vintage/climatology"]["logloss"]
                                                         - res["report"]["modelos"]["vintage/climatology"]["logloss"])}
    # cifras independientes (mi propio cálculo) a partir de las predicciones del arnés
    lab = official_dev()
    indep = {}
    for (mode, model), g in res["preds"].groupby(["mode", "model"]):
        g = g.set_index("month")
        g = g.loc[(g.index >= "1956-10-01") & (g.index <= "2004-12-01")]
        Pm = np.clip(g[M.P_COLS].to_numpy(float), 1e-4, 1)
        Pm /= Pm.sum(1, keepdims=True)
        T = lab.loc[g.index, M.P_COLS].to_numpy(float)
        indep[f"{mode}/{model}"] = {"n": len(g), "logloss": float(-(T * np.log(Pm)).sum(1).mean()),
                                    "brier": float(((Pm - T) ** 2).sum(1).mean()),
                                    "acierto": float((np.array(M.QUADS)[Pm.argmax(1)] ==
                                                      lab.loc[g.index, "label_hard"].to_numpy()).mean())}
    out["independiente"] = indep
    out["reportado"] = res["report"]["modelos"]
    S = res["scores"]
    bss = {}
    for mode in P.MODES:
        b = S[(S["mode"] == mode) & (S["model"] == "persistence_pit")]["brier"].to_numpy()
        c = S[(S["mode"] == mode) & (S["model"] == "climatology")]["brier"].to_numpy()
        bss[mode] = {"ratio_sumas": float(1 - c.sum() / b.sum()), "media_ratios": float(np.mean(1 - c / b)),
                     "reportado": res["report"]["frente_al_baseline"][f"{mode}/climatology"]["bss"]}
    out["bss"] = bss
    idx = M.block_indices(579, 12, 3, 1)
    d = np.diff(idx, axis=1) % 579
    out["bootstrap_bloques"] = {"saltos_por_fila": [int((d != 1).sum(axis=1)[i]) for i in range(3)],
                                "esperado_max": int(np.ceil(579 / 12)) - 1}
    OUT["hash"] = out


# ------------------------------------------------------------------ 2. etiqueta recalculada con datos ≤ T
def _perturbed_labeler(base: PITLabeler, t: pd.Timestamp, after: bool) -> PITLabeler:
    """Copia del labeler con los datos publicados DESPUÉS de t (after=True) o ANTES (after=False) multiplicados."""
    lb = copy.copy(base)
    lb._cache = {}
    lv = {}
    for sid, s in base.levels.items():
        av = base.av[sid].reindex(s.index)
        m = (av > t) if after else (av <= t) & (s.index >= t - pd.DateOffset(months=30))
        lv[sid] = s.where(~m.to_numpy(), s * 1.07)
    lb.levels = lv
    sv = {}
    for sid, vs in base.snapv.items():
        v = vs.v.copy()
        m = (v["realtime_start"] > t) if after else ((v["realtime_start"] <= t) & (v["date"] >= t - pd.DateOffset(months=30)))
        v.loc[m, "value"] = v.loc[m, "value"] * 1.07
        sv[sid] = type(vs)(v, sid)
    lb.snapv = sv
    return lb


def sec_labeler():
    out = {}
    cuts = [pd.Timestamp(x) for x in ("1962-06-29", "1975-03-31", "1984-11-30", "1996-08-30", "2004-12-31")]
    for mode in P.MODES:
        base = datas(mode).labeler
        r = []
        for t in cuts:
            a = base.at(t)
            b = _perturbed_labeler(base, t, after=True).at(t)
            c = _perturbed_labeler(base, t, after=False).at(t)
            same = a.shape == b.shape and np.allclose(a[M.P_COLS].to_numpy(float), b[M.P_COLS].to_numpy(float),
                                                      rtol=0, atol=0)
            changed = not (a.shape == c.shape and np.array_equal(a[M.P_COLS].to_numpy(float),
                                                                 c[M.P_COLS].to_numpy(float)))
            r.append({"T": f"{t:%Y-%m-%d}", "filas": len(a), "ultima": f"{a['date'].iloc[-1]:%Y-%m}",
                      "inmune_a_datos_posteriores": bool(same), "sensible_a_datos_previos": bool(changed)})
        out[f"perturbacion_{mode}"] = r
    # spy en TODOS los cortes mensuales 1957-01 → 2004-12, dos modos
    lab = official_dev()

    class Spy(B.Model):
        name, features, uses_persistence = "spy", (), False

        def __init__(self):
            self.calls = []

        def fit(self, X, Y, y, info):
            self.calls.append((info["refit_month"], info["decision_date"], X.index, Y, y))

        def predict_proba(self, X, info):
            return np.full((len(X), 4), 0.25)

    for mode in P.MODES:
        d = datas(mode)
        spy = Spy()
        cfg = H.HarnessConfig(name="val", models=("persistence_pit",), test_start="1957-01", test_end="2004-12")
        H.walk_forward(d, [spy], cfg)
        bad_emb, bad_Y, bad_y, n_eq_off, n_rows, gap = 0, 0, 0, 0, 0, []
        for m0, T, idx, Y, y in spy.calls:
            bad_emb += int(idx.max() > m0 - pd.DateOffset(months=6) or idx.max() + pd.DateOffset(months=4) >= m0)
            at = d.labeler.at(T).set_index("date")
            bad_Y += int(not np.array_equal(Y, at.loc[idx, M.P_COLS].to_numpy(float)))
            bad_y += int(not np.array_equal(y, at.loc[idx, "label_hard"].to_numpy()))
            eq = np.abs(Y - lab.loc[idx, M.P_COLS].to_numpy(float)).max(axis=1) < 1e-12
            n_eq_off += int(eq.sum())
            n_rows += len(idx)
            last = at.index.max()
            gap.append((m0.year - last.year) * 12 + m0.month - last.month)
        g = pd.Series(gap).value_counts().sort_index()
        out[f"spy_{mode}"] = {"cortes": len(spy.calls), "violaciones_embargo_purga": bad_emb,
                              "Y_distinto_de_at(T)": bad_Y, "y_distinto_de_at(T)": bad_y,
                              "filas_entrenamiento": n_rows, "filas_identicas_a_la_oficial": n_eq_off,
                              "m0_menos_ultima_fila_at(T)": {int(k): int(v) for k, v in g.items()}}
        # concordancia de la etiqueta recalculada con la oficial según la distancia al corte (≤ 2004)
        rows = []
        for m0, T, idx, Y, y in spy.calls[::12]:
            k = [(m0.year - s.year) * 12 + m0.month - s.month for s in idx]
            rows.append(pd.DataFrame({"k": k, "hit": y == lab.loc[idx, "label_hard"].to_numpy(),
                                      "dp": np.abs(Y - lab.loc[idx, M.P_COLS].to_numpy(float)).max(axis=1)}))
        rr = pd.concat(rows)
        rr["tramo"] = pd.cut(rr["k"], [5, 12, 24, 36, 59, 120, 2000])
        out[f"madurez_{mode}"] = {str(k): {"n": int(len(g)), "concordancia_dura": float(g["hit"].mean()),
                                           "dp_max_medio": float(g["dp"].mean())}
                                  for k, g in rr.groupby("tramo", observed=True)}
    OUT["labeler"] = out


# ------------------------------------------------------------------ 3. caja fuerte (todo sintético)
def _fake_label(path: Path, start="1990-01-01", end="2012-12-01"):
    idx = pd.date_range(start, end, freq="MS")
    df = pd.DataFrame({"date": idx, **{c: 0.25 for c in M.P_COLS}, "label_hard": "expansion", "weight": 1.0,
                       "provisional": False, "usrec": 0})
    df.to_parquet(path, index=False)
    return df


def sec_vault():
    out = {}
    fake = TMP / "fake_label.parquet"
    _fake_label(fake)
    # D1: la "caja fuerte" de desarrollo se abre cambiando un atributo
    v = V.LabelVault(path=fake)
    v.limit = None
    df = v.load()
    out["D1_limit_None_en_desarrollo"] = {"max_fecha_leida": f"{df.index.max():%Y-%m}", "excepcion": False}
    # D2: la evaluación única se repite redirigiendo FKB_TRIALS_DIR (nombre de la variable de desbloqueo cambiado)
    V.UNLOCK_ENV = "FKB_VALIDADOR_SINTETICO"
    os.environ["FKB_VALIDADOR_SINTETICO"] = "EVALUACION-UNICA P-EVAL-MOD"
    opened = []
    for i in range(3):
        os.environ["FKB_TRIALS_DIR"] = str(TMP / f"trials_redir_{i}")
        try:
            V.LabelVault(mode="holdout_evaluation", prereg_id="P-EVAL-MOD", path=fake).load()
            opened.append(True)
        except V.HoldoutLocked:
            opened.append(False)
    os.environ["FKB_TRIALS_DIR"] = str(TMP / "trials_redir_0")
    try:
        V.LabelVault(mode="holdout_evaluation", prereg_id="P-EVAL-MOD", path=fake)
        same_dir = "abierta"
    except V.HoldoutLocked as e:
        same_dir = f"denegada: {e}"
    out["D2_redireccion_FKB_TRIALS_DIR"] = {"aperturas_con_el_mismo_prereg": opened,
                                            "cuarto_intento_mismo_directorio": same_dir}
    os.environ["FKB_TRIALS_DIR"] = str(TMP / "trials")
    # D3: una caja fuerte abierta sirve para N corridas en el mismo proceso

    class HoldoutArray(H.ArrayData):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.phase = "holdout_evaluation"

        def check_cut(self, m0):
            return None

        def score_labels(self, end):
            return self.target[self.target.index <= pd.Timestamp(end)]

    idx = pd.date_range("1990-01-01", "2012-12-01", freq="MS")
    tgt = pd.read_parquet(fake).set_index("date")
    ad = HoldoutArray(pd.DataFrame({"x": 0.0}, index=idx), tgt, {"x": {"estado": "principal", "start": None}},
                      kind="synthetic")
    cfg = H.HarnessConfig(name="val_holdout", models=("persistence_pit", "climatology"), modes=("synthetic",),
                          test_start="2000-01", test_end="2012-12", phase="holdout_evaluation", prereg_id="NO-EXISTE")
    runs = []
    for _ in range(3):
        r = H.run(cfg, datas={"synthetic": ad}, record=False)
        runs.append(r["report"]["muestra"])
    out["D3_run_con_datas_en_fase_holdout_sin_caja_fuerte"] = {
        "corridas": len(runs), "muestra": runs[0], "prereg_id_usado": "NO-EXISTE (no está en hypotheses.yaml)"}
    # D3b: PITData acepta cualquier objeto con .mode == 'holdout_evaluation' como caja fuerte y lee la matriz SIN filtro
    seen = {}
    real = H.pd.read_parquet

    class Stop(Exception):
        pass

    def spy_read(path, *a, **k):
        seen["path"], seen["filters"] = Path(path).name, k.get("filters")
        raise Stop

    class Duck:
        mode = "holdout_evaluation"

    H.pd.read_parquet = spy_read
    try:
        H.PITData("vintage", phase="holdout_evaluation", vault=Duck())
    except Stop:
        pass
    finally:
        H.pd.read_parquet = real
    out["D3b_PITData_con_caja_falsa"] = {"lectura_interceptada": seen.get("path"), "filtro": seen.get("filters"),
                                         "nota": "interceptada antes de decodificar; sin preregistro ni confirmación"}
    # D4: PITLabeler.at(T) no tiene barrera: con niveles recortados a ≤ 2004 (sin datos del bloqueado) acepta T = 2010
    lb = copy.copy(datas("latest_truncated").labeler)
    lb._cache = {}
    lb.levels = {sid: s[s.index < HOLD] for sid, s in lb.levels.items()}
    lb.av = {sid: a for sid, a in lb.av.items()}
    n_log0 = _n_access()
    try:
        r = lb.at(pd.Timestamp("2010-06-30"))
        d4 = {"excepcion": None, "filas": len(r), "ultima": f"{r['date'].max():%Y-%m}"}
    except Exception as e:  # noqa: BLE001
        d4 = {"excepcion": repr(e)}
    d4["lineas_nuevas_en_label_access"] = _n_access() - n_log0
    out["D4_PITLabeler_at_T_2010_sin_barrera"] = d4
    # D5: pit.score_training con una etiqueta sintética: el assert usa <= 2005-01-01 (deja pasar 2005-01)
    real_out = R.out_path
    R.out_path = lambda p=R.PARAMS: fake
    try:
        pred = pd.DataFrame({"month": pd.date_range("2000-01-01", "2005-01-01", freq="MS")})
        for c in P.PRED_COLS:
            pred[c] = 0.25
        pred["pers_hard"], pred["lag_months"] = "expansion", 5
        try:
            s = P.score_training(pred, end="2005-01-01")
            out["D5_score_training_2005_01"] = {"puntuado_hasta": s["hasta"], "assert_salta": False}
        except AssertionError:
            out["D5_score_training_2005_01"] = {"assert_salta": True}
    finally:
        R.out_path = real_out
    # D6: comprobación de árbol limpio cuando git no está disponible / no es un repo
    real_repo = V.REPO
    V.REPO = TMP
    out["D6_git_fuera_de_repo"] = {"status_porcelain": repr(V._git("status", "--porcelain")),
                                   "la_condicion_de_arbol_sucio_se_cumple": bool(V._git("status", "--porcelain"))}
    V.REPO = real_repo
    # D7: ficheros con información del periodo bloqueado legibles sin la caja fuerte (solo METADATOS de parquet)
    import pyarrow.parquet as pq
    files = {}
    cand = [R.out_path(), R.out_dir() / "regime_us_v1.0.parquet",
            *sorted(P.out_dir().glob("baseline_persistence_v0.3_*.parquet")),
            *sorted(P.out_dir().glob("pit_us_v0.3_*.parquet")), R.snapshot_path()]
    for f in cand:
        if not Path(f).exists():
            continue
        pf = pq.ParquetFile(f)
        names = pf.schema_arrow.names
        col = next((c for c in ("date", "decision_date", "month") if c in names), None)
        mx = None
        if col is not None:
            i = names.index(col)
            st = [pf.metadata.row_group(g).column(i).statistics for g in range(pf.num_row_groups)]
            mx = max((s.max for s in st if s is not None and s.has_min_max), default=None)
        files[Path(f).name] = {"filas": pf.metadata.num_rows, "max_" + str(col): str(mx)}
    out["D7_ficheros_con_meses_bloqueados_(metadatos)"] = files
    OUT["vault"] = out


def _n_access():
    f = Path(os.environ["FKB_TRIALS_DIR"]) / "label_access.jsonl"
    return len(f.read_text().splitlines()) if f.exists() else 0


# ------------------------------------------------------------------ 4. variables
def sec_vars():
    out = {}
    for mode in P.MODES:
        d = datas(mode)
        rows = {}
        for c, info in d.colinfo.items():
            st = info["start"]
            s = d.X[c]
            after = s[s.index >= st] if st is not None else s
            rows[c] = {"estado": info["estado"], "start": f"{st:%Y-%m}" if st is not None else None,
                       "nan_tras_start": int(after.isna().sum()),
                       "ultimo_dato": f"{s.last_valid_index():%Y-%m}" if s.notna().any() else None}
        out[f"columnas_{mode}"] = {c: r for c, r in rows.items() if r["nan_tras_start"] or
                                   (r["ultimo_dato"] and r["ultimo_dato"] < "2004-12")}

    class SpyP(B.Model):
        name, features, uses_persistence = "spy_principal", "principal", False

        def __init__(self):
            self.calls = []

        def fit(self, X, Y, y, info):
            self.calls.append((info["refit_month"], X.index.min(), len(X), tuple(X.columns)))

        def predict_proba(self, X, info):
            return np.full((len(X), 4), 0.25)

    for mode in P.MODES:
        d = datas(mode)
        spy = SpyP()
        cfg = H.HarnessConfig(name="val", models=("persistence_pit", "climatology"), test_start="1957-01",
                              test_end="2004-12", min_train_months=120)
        _, diag = H.walk_forward(d, [spy], cfg)
        dg = pd.DataFrame([x for x in diag if x["model"] == "spy_principal" and not x.get("skipped")])
        sk = [x for x in diag if x.get("skipped")]
        ev = pd.DataFrame(spy.calls, columns=["m0", "inicio", "n", "cols"])
        ev["k"] = ev["cols"].map(len)
        cambios = ev[ev["cols"] != ev["cols"].shift()]
        out[f"epocas_{mode}"] = {
            "cortes_con_fit": len(ev), "cortes_saltados_(<120)": len(sk),
            "primer_fit": f"{ev['m0'].min():%Y-%m}" if len(ev) else None,
            "celdas_imputadas_total": int(dg["imputed_cells"].sum()) if len(dg) else 0,
            "cortes_con_imputacion": int((dg["imputed_cells"] > 0).sum()) if len(dg) else 0,
            "cambios_de_epoca": [{"m0": f"{r.m0:%Y-%m}", "n_cols": int(r.k), "inicio_ventana": f"{r.inicio:%Y-%m}",
                                  "n_train": int(r.n)} for r in cambios.itertuples()],
            "n_train_min_max": [int(ev["n"].min()), int(ev["n"].max())]}
        if len(dg):
            imp = dg[dg["imputed_cells"] > 0]
            out[f"epocas_{mode}"]["imputacion_por_anio"] = {int(k): int(v) for k, v in
                                                            imp.groupby(imp["refit_month"].dt.year)["imputed_cells"]
                                                            .sum().items()}
    OUT["vars"] = out


# ------------------------------------------------------------------ 5. muestra común (¿se reduce en silencio?)
def sec_metrics():
    out = {}
    cfg = H.HarnessConfig(name="val_muestra", models=("persistence_pit", "climatology"), min_train_months=120)
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        r = H.run(cfg, datas={m: datas(m) for m in P.MODES}, record=False)
    out["climatologia_min_train_120"] = {"muestra": r["report"]["muestra"], "avisos": [str(x.message) for x in w],
                                         "persistencia_en_la_muestra_comun": r["report"]["modelos"][
                                             "vintage/persistence_pit"],
                                         "persistencia_muestra_completa": r["report"]["persistencia_muestra_completa"][
                                             "vintage"]}
    OUT["metrics"] = out


# ------------------------------------------------------------------ 6. episodios
def sec_episodes():
    lab = official_dev()
    lab = lab[(lab["weight"] > 0) & (lab.index >= "1956-10-01")]
    eps = M.episodes(lab)
    rr = [e for e in eps if e["tipo"] == "racha_regimen"]
    ln = pd.Series([(e["hasta"].year - e["desde"].year) * 12 + e["hasta"].month - e["desde"].month + 1 for e in rr])
    rec = [e for e in eps if e["tipo"] == "recesion_nber"]
    ov = sum(1 for a, b in zip(rec, rec[1:]) if b["desde"] <= a["hasta"])
    OUT["episodes"] = {"rachas": len(rr), "rachas_1m": int((ln == 1).sum()), "rachas_<=3m": int((ln <= 3).sum()),
                       "rachas_<6m": int((ln < 6).sum()), "mediana_meses": float(ln.median()),
                       "recesiones": len(rec), "recesiones_solapadas_±6": ov}


# ------------------------------------------------------------------ 7. potencia del placebo
class Logit(B.Model):
    def __init__(self, name, features=(), lam=0.05):
        self.name, self.features, self.uses_persistence, self.lam = name, features, True, lam

    def _design(self, X):
        Z = X[B.PERS_COLS[1:]].to_numpy(float)
        if self.cols:
            Z = np.hstack([Z, (X[self.cols].to_numpy(float) - self.mu) / self.sd])
        return Z

    def fit(self, X, Y, y, info):
        self.cols = [c for c in X.columns if c not in B.PERS_COLS]
        F = X[self.cols].to_numpy(float)
        self.mu, self.sd = F.mean(axis=0), F.std(axis=0) + 1e-9
        self.W = fit_logit(self._design(X), np.array([M.QUADS.index(v) for v in y]), 4, self.lam, per_obs=False)

    def predict_proba(self, X, info):
        return predict_logit(self.W, self._design(X))


PLACEBO_VARS = ("curve_10y3m", "payems_3m_ann", "indpro_3m_ann", "unrate_sahm", "headline_cpi_6m_ann", "ppi_yoy",
                "baa_spread", "ff_d12m")


def leak_future(sd, k=1):
    def f(tgt, rng):
        x = tgt[M.P_COLS[1:]].shift(-k)
        return pd.DataFrame(x.to_numpy() + rng.normal(0, sd, x.shape), index=x.index, columns=["la", "lb", "lc"])
    return f


def leak_lag(k):
    def f(tgt, rng):
        oh = pd.get_dummies(tgt["label_hard"]).reindex(columns=list(M.QUADS), fill_value=0).astype(float)
        x = oh[list(M.QUADS[1:])].shift(k)
        return pd.DataFrame(x.to_numpy(), index=x.index, columns=["la", "lb", "lc"])
    return f


def skill(pit, seed, leak):
    data = H.placebo_data(pit, seed, leak=leak)
    feats = PLACEBO_VARS + (("la", "lb", "lc") if leak else ())
    reg = {"logit_base": lambda: Logit("logit_base"), "logit_vars": lambda: Logit("logit_vars", feats)}
    cfg = H.HarnessConfig(name="val_placebo", models=("logit_base", "logit_vars"), modes=(data.mode,),
                          test_start="1975-01", refit_every=12, min_train_months=60, baseline="logit_base")
    r = H.run(cfg, registry=reg, datas={data.mode: data}, record=False)
    return r["report"]["frente_al_baseline"][f"{data.mode}/logit_vars"]["mejora_logloss"]["mean"]


def sec_power(seeds=tuple(range(1, 9))):
    pit = datas("vintage")
    cases = {"sin_fuga": None,
             **{f"futura_t+1_ruido_{sd}": leak_future(sd) for sd in (0.3, 1.0, 2.0, 4.0)},
             **{f"contemporanea_t_ruido_{sd}": leak_future(sd, 0) for sd in (1.0, 2.0, 4.0)},
             **{f"calendario_t-{k}": leak_lag(k) for k in (1, 3, 4)},
             "control_t-5_(sin_fuga)": leak_lag(5)}
    out = {}
    for name, lk in cases.items():
        t0 = time.time()
        s = np.array([skill(pit, sd, lk) for sd in seeds])
        out[name] = {"skills": [round(float(x), 4) for x in s], "media": float(s.mean()),
                     "media_semillas_1_3": float(s[:3].mean()),
                     "falla_placebo_media_1_3_>tol": bool(s[:3].mean() > PLACEBO_TOL),
                     "frac_semillas_>tol": float((s > PLACEBO_TOL).mean()),
                     "frac_semillas_>0.10": float((s > 0.10).mean()), "seg": round(time.time() - t0, 1)}
        print(name, out[name], flush=True)
    OUT["power"] = out


def sec_power2(seeds=tuple(range(1, 21))):
    """20 semillas y diseño PAREADO: habilidad con la columna sospechosa − habilidad sin ella, misma permutación."""
    pit = datas("vintage")
    cases = {"futura_t+1_ruido_0.3": leak_future(0.3), "futura_t+1_ruido_1.0": leak_future(1.0),
             "futura_t+1_ruido_2.0": leak_future(2.0), "contemporanea_t_ruido_1.0": leak_future(1.0, 0),
             "contemporanea_t_ruido_2.0": leak_future(2.0, 0), "contemporanea_t_ruido_4.0": leak_future(4.0, 0),
             "calendario_t-1": leak_lag(1), "calendario_t-3": leak_lag(3), "calendario_t-4": leak_lag(4),
             "control_t-5_(sin_fuga)": leak_lag(5)}
    clean = np.array([skill(pit, sd, None) for sd in seeds])
    out = {"sin_fuga": {"media": float(clean.mean()), "sd": float(clean.std(ddof=1)),
                        "frac_>tol": float((clean > PLACEBO_TOL).mean()),
                        "frac_media_de_3_>tol": float(np.mean([clean[i:i + 3].mean() > PLACEBO_TOL
                                                               for i in range(0, 18, 3)]))}}
    for name, lk in cases.items():
        s = np.array([skill(pit, sd, lk) for sd in seeds])
        d = s - clean
        out[name] = {"media": float(s.mean()), "frac_>tol": float((s > PLACEBO_TOL).mean()),
                     "frac_media_de_3_>tol": float(np.mean([s[i:i + 3].mean() > PLACEBO_TOL for i in range(0, 18, 3)])),
                     "pareado_media": float(d.mean()), "pareado_frac_>0": float((d > 0).mean()),
                     "pareado_frac_>0.02": float((d > PLACEBO_TOL).mean())}
        print(name, out[name], flush=True)
    OUT["power2"] = out


SECS = {"power2": sec_power2, "hash": sec_hash, "labeler": sec_labeler, "vault": sec_vault, "vars": sec_vars, "metrics": sec_metrics,
        "episodes": sec_episodes, "power": sec_power}

if __name__ == "__main__":
    dest = Path(sys.argv[1])
    for s in (sys.argv[2:] or list(SECS)):
        t0 = time.time()
        SECS[s]()
        print(f"[{s}] {time.time() - t0:.0f} s", flush=True)
        dest.write_text(json.dumps(OUT, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: v for k, v in OUT.items() if k != "power"}, indent=1, ensure_ascii=False, default=str))
