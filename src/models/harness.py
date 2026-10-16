"""Arnés de backtest walk-forward del nowcast de régimen (Fase 3, entregable 3; docs/models/harness.md).

Reglas (docs/PLAN.md "Validación", "Periodo bloqueado y reglas del arnés"; ficha de la etiqueta §7 y §12;
docs/models/pit_base.md §3):

1. Cortes walk-forward con ventana EXPANSIVA; reentreno cada `refit_every` meses (1 = mensual). En el corte de mes m0
   (fecha de decisión T0 = último día hábil de m0) se entrena y se predicen los meses m0 … m0 + k − 1, cada uno con las
   variables de SU fecha de decisión.
2. Embargo ≥ 6 meses: solo entrenan los meses s ≤ m0 − embargo. Purga: la ventana de la etiqueta de s llega a s + 4;
   se exige s + 4 < m0 (lo cubre el embargo; se comprueba en cada corte).
3. ETIQUETA DE ENTRENAMIENTO RECALCULADA con los datos conocidos en T0 (src/models/pit_labels.py, mismo modo que las
   variables). La etiqueta oficial congelada v1.1 solo se usa para PUNTUAR, a través de la caja fuerte (vault.py).
4. Periodo bloqueado 2005-01 → abierto: en `development` no se carga ninguna fila ≥ 2005-01 (ni etiqueta ni
   variables) y cualquier corte o mes de prueba ≥ 2005-01 lanza `HoldoutLocked`. La evaluación única
   (`holdout_evaluation`) exige preregistro + confirmación explícita (vault.py) y NO se ejecuta en desarrollo.
5. Variables solo de la matriz PIT congelada v0.3 (hash fijado), por nombre de columna; estados y fechas según
   `principal_desde_efectivo` (política `principal`) y `assert_no_forbidden()` antes de cada `fit`.
6. Modo principal `vintage`; `latest_truncated` como sensibilidad, puntuados sobre los MISMOS meses.
7. Cada corrida queda en el registro de pruebas (trials.py).

    .venv/bin/python -m src.models.harness --config config/harness/baselines_v1.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.features import pit as P
from src.labels import regime_us as R
from src.models import base as B
from src.models import metrics as M
from src.models.pit_labels import PITLabeler
from src.models.vault import HOLDOUT_START, LABEL_FILE_SHA256, HoldoutLocked, LabelVault, log_access

REPO = Path(__file__).resolve().parents[2]
QUADS, P_COLS, PERS_COLS = M.QUADS, M.P_COLS, B.PERS_COLS
LABEL_FORWARD = R.pace_need(R.PARAMS)            # 4: la etiqueta de s usa niveles hasta s + 4
MIN_EMBARGO = R.PARAMS.embargo_months             # 6
PIT_VERSION = "0.3"
# SHA-256 de las matrices oficiales v0.3 (meta de la base PIT; reproducidas bit a bit por el Validador el 2026-10-16)
MATRIX_SHA256 = {
    "vintage": "6858f6c93bfe692ab7a9452f22db1986ba52f32e1300703c12ae60fb2b9c0fa9",
    "latest_truncated": "3d81ec88b17a5390e8b7c2099ef1a4406009a43b1e1f1751522b7767f9ff025b",
    "vintage_filadelfia_prudente": "b8df88442043edc946b41530e4d24fcfeeb4c81c2bcca0ccc917d1f8fa223f5e",
}
ESTADOS = {"principal": ("principal", "principal_epoca"),
           "sensibilidad": ("principal", "principal_epoca", "condicional")}


def _month(d) -> pd.Timestamp:
    return pd.Timestamp(d).to_period("M").to_timestamp()


def _add(m: pd.Timestamp, k: int) -> pd.Timestamp:
    return m + pd.DateOffset(months=k)


# ------------------------------------------------------------------ configuración
@dataclass(frozen=True)
class HarnessConfig:
    name: str
    models: tuple = ("persistence_pit", "climatology")
    model_params: dict = field(default_factory=dict)
    modes: tuple = ("vintage", "latest_truncated")
    matrix_variant: str = ""                # "" = oficial; "filadelfia_prudente" = S-PIT-001 (solo vintage)
    refit_every: int = 1
    embargo_months: int = MIN_EMBARGO
    min_train_months: int = 12
    test_start: str = "1956-10"
    test_end: str = "2004-12"
    feature_policy: str = "principal"
    exclude_recomputed_provisional: bool = False
    baseline: str = "persistence_pit"
    phase: str = "development"
    prereg_id: str | None = None
    who: str = "Constructor"
    nota: str = ""

    def validate(self) -> None:
        if self.embargo_months < MIN_EMBARGO:
            raise ValueError(f"embargo {self.embargo_months} < {MIN_EMBARGO} meses (ficha §7): no permitido")
        if self.refit_every < 1:
            raise ValueError("refit_every ≥ 1")
        if self.feature_policy not in ESTADOS:
            raise ValueError(f"política de variables desconocida: {self.feature_policy}")
        if self.baseline not in self.models:
            raise ValueError("el baseline tiene que estar entre los modelos (misma muestra)")
        if self.phase == "development" and _month(self.test_end) >= HOLDOUT_START:
            raise HoldoutLocked(f"test_end {self.test_end} dentro del periodo bloqueado (≥ {HOLDOUT_START:%Y-%m})")
        if self.phase not in ("development", "holdout_evaluation"):
            raise ValueError(f"fase desconocida: {self.phase}")

    @classmethod
    def from_yaml(cls, path) -> "HarnessConfig":
        d = yaml.safe_load(Path(path).read_text())
        for k in ("models", "modes"):
            if k in d:
                d[k] = tuple(d[k])
        return cls(**d)


# ------------------------------------------------------------------ datos
class PITData:
    """Matriz PIT congelada + etiqueta de entrenamiento recalculada + etiqueta oficial (caja fuerte), para un modo."""
    kind = "pit"

    def __init__(self, mode: str, variant: str = "", phase: str = "development", prereg_id: str | None = None,
                 policy: str = "principal", vault: LabelVault | None = None):
        self.mode, self.phase, self.policy = mode, phase, policy
        # una sola caja fuerte por corrida (en holdout, abrirla gasta el preregistro: run() la crea y la comparte)
        self.vault = vault or LabelVault(mode=phase, prereg_id=prereg_id)
        if self.vault.mode != phase:
            raise ValueError("la caja fuerte y los datos están en fases distintas")
        name = f"{mode}_{variant}" if variant else mode
        if name not in MATRIX_SHA256:
            raise ValueError(f"matriz desconocida: {name}")
        path = P.out_dir() / f"pit_us_v{PIT_VERSION}_{name}.parquet"
        if P.file_sha(path) != MATRIX_SHA256[name]:
            raise RuntimeError(f"{path.name} no coincide con la matriz congelada v{PIT_VERSION}")
        self.matrix_name, self.matrix_sha = path.name, MATRIX_SHA256[name]
        filters = [("decision_date", "<", HOLDOUT_START.to_datetime64())] if phase == "development" else None
        X = pd.read_parquet(path, filters=filters)
        if phase == "development":
            assert X["decision_date"].max() < HOLDOUT_START
        X["month"] = X["decision_date"].dt.to_period("M").dt.to_timestamp()
        self.decision = X.set_index("month")["decision_date"]
        self.X = X.drop(columns=["decision_date"]).set_index("month")
        self.labeler = PITLabeler(mode, PIT_VERSION)
        wl = self.labeler.wl
        public = set(P.public_columns(wl))
        if set(self.X.columns) != public:
            raise RuntimeError("las columnas de la matriz no coinciden con la lista blanca congelada")
        R.assert_no_forbidden(list(self.X.columns))
        eff = P.effective_principal_desde(wl)
        spec = {v["nombre"]: v for v in wl["variables"]}
        self.colinfo = {}
        for c in self.X.columns:
            first = self.X[c].first_valid_index()
            starts = [first, _month(spec[c]["desde"]) if spec[c].get("desde") else None]
            if policy == "principal" and eff.get(c):
                starts.append(_month(eff[c]))
            starts = [s for s in starts if s is not None]
            self.colinfo[c] = {"estado": spec[c]["estado"], "start": max(starts) if starts else None,
                               "principal_desde_efectivo": eff.get(c)}
        meta = json.loads(R.out_path().with_suffix(".meta.json").read_text())
        last = pd.Timestamp(meta["last"])
        self.first_official_provisional = _add(last, -(meta["provisional_months"] - 1))
        self._pers = None

    def check_cut(self, m0: pd.Timestamp) -> None:
        if self.phase == "development" and (m0 >= HOLDOUT_START or self.decision[m0] >= HOLDOUT_START):
            log_access({"mode": self.phase, "granted": False, "why": f"corte {m0:%Y-%m} en el periodo bloqueado"})
            raise HoldoutLocked(f"corte {m0:%Y-%m} dentro del periodo bloqueado")

    def train_targets(self, m0: pd.Timestamp) -> pd.DataFrame:
        """Etiqueta recalculada SOLO con los datos conocidos en la fecha de decisión de m0."""
        self.check_cut(m0)
        lab = self.labeler.at(self.decision[m0]).set_index("date")
        return lab[lab.index < self.first_official_provisional]    # provisionales oficiales: nunca entrenan

    def pers_rows(self, months) -> pd.DataFrame:
        """Persistencia PIT (pers_*) de los meses pedidos, cada uno en su fecha de decisión (con caché)."""
        self._pers = self._pers if self._pers is not None else {}
        for m in months:
            if m not in self._pers:
                self._pers[m] = self.labeler.persistence(self.decision[m])
        rows = {m: self._pers[m] for m in months if self._pers[m] is not None}
        cols = ["label_month", *PERS_COLS, "pers_hard"]
        return pd.DataFrame.from_dict(rows, orient="index", columns=cols).sort_index() if rows else \
            pd.DataFrame(columns=cols)

    def persistence_frame(self) -> pd.DataFrame:
        return self.pers_rows(self.decision.index)

    def score_labels(self, end) -> pd.DataFrame:
        return self.vault.load(end=end)

    def hashes(self) -> dict:
        return {"matrix": {self.matrix_name: self.matrix_sha}, "pit_snapshot": P.FROZEN[PIT_VERSION],
                "label_snapshot": R.FROZEN[R.PARAMS.version],
                "label_file_sha256": LABEL_FILE_SHA256[R.PARAMS.version]}


class ArrayData:
    """Datos en memoria para el placebo y los tests (NO es evidencia: el registro lo marca con su `kind`).
    `target`: DataFrame mensual con p_* , label_hard, weight, provisional y usrec. La etiqueta de s se considera
    conocida en m0 si s ≤ m0 − label_lag (5), como la etiqueta real; la persistencia de t es el objetivo de t − 5."""

    def __init__(self, X: pd.DataFrame, target: pd.DataFrame, colinfo: dict, kind: str = "placebo",
                 mode: str = "synthetic", label_lag: int = 5):
        if kind == "pit":
            raise ValueError("ArrayData no puede hacerse pasar por datos PIT")
        self.X, self.target, self.colinfo, self.kind, self.mode = X, target, colinfo, kind, mode
        self.phase, self.lag = "development", label_lag
        self.decision = pd.Series(X.index + pd.offsets.MonthEnd(0), index=X.index)
        self.first_official_provisional = pd.Timestamp("2262-01-01")

    def check_cut(self, m0):
        if m0 >= HOLDOUT_START:
            raise HoldoutLocked(f"corte {m0:%Y-%m} dentro del periodo bloqueado")

    def train_targets(self, m0):
        self.check_cut(m0)
        return self.target[self.target.index <= _add(m0, -self.lag)]

    def persistence_frame(self):
        p = self.target[P_COLS].shift(self.lag, freq="MS").reindex(self.X.index)
        p.columns = PERS_COLS
        p["pers_hard"] = self.target["label_hard"].shift(self.lag, freq="MS").reindex(self.X.index)
        return p.dropna()

    def pers_rows(self, months):
        return self.persistence_frame().reindex(months).dropna()

    def score_labels(self, end):
        end = pd.Timestamp(end)
        if end >= HOLDOUT_START:
            raise HoldoutLocked("periodo bloqueado")
        return self.target[self.target.index <= end]

    def hashes(self):
        return {"array_data": hashlib.sha256(pd.util.hash_pandas_object(self.X).values.tobytes()
                                             + pd.util.hash_pandas_object(self.target).values.tobytes()).hexdigest()}


def placebo_data(pit: PITData, seed: int, block: int = 24, leak=None, end: str = "2004-12") -> ArrayData:
    """Placebo (pit_base.md §3, regla 6): las variables PIT reales con la etiqueta oficial ≤ 2004 BARAJADA en bloques
    de `block` meses (filas enteras: p_*, label_hard, usrec). Sin fuga, ningún modelo puede tener habilidad sobre la
    persistencia del objetivo barajado. `leak(target_barajado, rng) -> DataFrame` añade columnas con fuga (tests)."""
    from src.features.placebo import block_shuffle
    rng = np.random.default_rng(seed)
    lab = pit.score_labels(end)
    lab = lab[lab["weight"] > 0][[*P_COLS, "label_hard", "usrec"]]
    order = block_shuffle(np.arange(len(lab)), block, rng)
    tgt = pd.DataFrame(lab.to_numpy()[order], index=lab.index, columns=lab.columns)
    tgt[P_COLS] = tgt[P_COLS].astype(float)
    tgt["weight"], tgt["provisional"] = 1.0, False
    X = pit.X.loc[pit.X.index.isin(lab.index)].copy()
    colinfo = dict(pit.colinfo)
    if leak is not None:
        L = leak(tgt, rng).reindex(X.index)
        X = X.join(L)
        colinfo.update({c: {"estado": "principal", "start": L[c].first_valid_index()} for c in L.columns})
    return ArrayData(X, tgt, colinfo, kind="placebo", mode=f"placebo_{pit.mode}")


# ------------------------------------------------------------------ estabilidad a ambos lados de los saltos
def vintage_breaks(pit: PITData) -> dict[str, list[pd.Timestamp]]:
    """Saltos revisado → primera publicación (`vintage_desde`) y de composición de cada columna (pit_base.md §3,
    regla 3). Solo para diagnosticar: nunca entran como variable."""
    meta = json.loads((P.out_dir() / f"pit_us_v{PIT_VERSION}.meta.json").read_text())["columns"][pit.mode]
    out = {}
    for c, info in meta.items():
        b = [_month(info["vintage_desde"])] if info.get("vintage_desde") else []
        if c in ("growth_rt", "growth_rt_state"):
            b += [pd.Timestamp("1973-04-01"), pd.Timestamp("1981-05-01")]
        out[c] = sorted(b)
    return out


def sign_stability(coefs: pd.DataFrame, breaks: dict[str, list[pd.Timestamp]], min_refits: int = 12) -> pd.DataFrame:
    """`coefs`: coeficiente (o importancia con signo) de cada variable por corte (índice = refit_month). Para cada
    variable y salto con ≥ `min_refits` cortes a cada lado: media antes/después y si conserva el signo."""
    rows = []
    for c in coefs.columns:
        for b in breaks.get(c, []):
            pre, post = coefs.loc[coefs.index < b, c].dropna(), coefs.loc[coefs.index >= b, c].dropna()
            if len(pre) < min_refits or len(post) < min_refits:
                continue
            rows.append({"variable": c, "salto": f"{b:%Y-%m}", "media_antes": pre.mean(), "media_despues": post.mean(),
                         "mismo_signo": bool(np.sign(pre.mean()) == np.sign(post.mean()))})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ selección de variables
def resolve_features(model: B.Model, data, cfg: HarnessConfig, train_months: pd.DatetimeIndex) -> tuple[list, list]:
    """Columnas que el modelo puede usar en este corte y columnas descartadas (con motivo)."""
    if not model.features:
        return [], []
    allowed = ESTADOS[cfg.feature_policy]
    if model.features == "principal":
        req = [c for c in data.X.columns if data.colinfo[c]["estado"] in allowed]
    else:
        req = list(model.features)
        unknown = [c for c in req if c not in data.X.columns]
        if unknown:
            raise KeyError(f"{model.name}: variables fuera de la matriz PIT congelada: {unknown}")
        bad = [c for c in req if data.colinfo[c]["estado"] not in allowed]
        if bad:
            raise ValueError(f"{model.name}: variables no admitidas con la política {cfg.feature_policy}: {bad}")
    use, drop = [], []
    for c in req:
        st = data.colinfo[c]["start"]
        n = int((train_months >= st).sum()) if st is not None else 0
        (use if n >= cfg.min_train_months else drop).append(c if n >= cfg.min_train_months else (c, f"época: {n} m"))
    return use, drop


# ------------------------------------------------------------------ walk-forward
def walk_forward(data, models: list[B.Model], cfg: HarnessConfig, spy=None) -> tuple[pd.DataFrame, list[dict]]:
    """Predicciones fuera de muestra de cada modelo (un modo). `spy(model, info, X, Y)` solo para tests."""
    cfg.validate()
    months = data.X.index
    test = months[(months >= _month(cfg.test_start)) & (months <= _month(cfg.test_end))]
    preds, diag = [], []
    for b in range(0, len(test), cfg.refit_every):
        block = test[b:b + cfg.refit_every]
        m0 = block[0]
        data.check_cut(block[-1])
        lab = data.train_targets(m0)
        cut = _add(m0, -cfg.embargo_months)
        ok = (lab.index <= cut) & (lab["weight"] > 0)
        if cfg.exclude_recomputed_provisional:
            ok &= ~lab["provisional"].astype(bool)
        tr = lab[ok]
        tr = tr[tr.index.isin(months)]
        if len(tr):
            assert tr.index.max() <= cut and _add(tr.index.max(), LABEL_FORWARD) < m0, "embargo/purga violados"
        for model in models:
            use, drop = resolve_features(model, data, cfg, tr.index)
            Xtr = data.X.loc[tr.index if model.needs_training else tr.index[:0], use]
            if use:
                start = max(data.colinfo[c]["start"] for c in use)
                Xtr = Xtr[Xtr.index >= start].dropna()
            if model.uses_persistence:
                Xtr = Xtr.join(data.pers_rows(Xtr.index)[PERS_COLS], how="inner")
            R.assert_no_forbidden(list(Xtr.columns))
            assert set(Xtr.columns) <= set(data.X.columns) | set(PERS_COLS)
            Y, y = tr.loc[Xtr.index, P_COLS].to_numpy(float), tr.loc[Xtr.index, "label_hard"].to_numpy()
            info = {"refit_month": m0, "decision_date": data.decision[m0], "mode": data.mode,
                    "train_months": Xtr.index, "features": use}
            if model.needs_training and len(Xtr) < cfg.min_train_months:
                diag.append({"model": model.name, "refit_month": m0, "n_train": len(Xtr), "skipped": True})
                continue
            if spy is not None:
                spy(model, info, Xtr, Y)
            model.fit(Xtr, Y, y, info)
            Xte = data.X.loc[block, use]
            n_imp = int(Xte.isna().sum().sum())
            if n_imp:
                Xte = Xte.fillna(Xtr[use].mean())
            if model.uses_persistence:
                Xte = Xte.join(data.pers_rows(block)[PERS_COLS], how="inner")
            if len(Xte) == 0:
                continue
            Pm = np.asarray(model.predict_proba(Xte, info), float)
            if Pm.shape != (len(Xte), len(QUADS)) or not np.isfinite(Pm).all():
                raise ValueError(f"{model.name}: predict_proba devolvió {Pm.shape} / no finito")
            out = pd.DataFrame(Pm, columns=P_COLS, index=Xte.index)
            out.insert(0, "refit_month", m0)
            out.insert(0, "model", model.name)
            out.insert(0, "mode", data.mode)
            out["n_train"] = len(Xtr)
            preds.append(out)
            diag.append({"model": model.name, "refit_month": m0, "n_train": len(Xtr), "features": use,
                         "dropped": drop, "imputed_cells": n_imp,
                         "coef": model.coefficients() if hasattr(model, "coefficients") else None})
    P_ = pd.concat(preds).rename_axis("month").reset_index() if preds else pd.DataFrame()
    return P_, diag


# ------------------------------------------------------------------ puntuación
def score(preds: pd.DataFrame, labels: dict[str, pd.DataFrame], cfg: HarnessConfig) -> tuple[pd.DataFrame, dict]:
    """Puntúa contra la etiqueta oficial (por modo) en los meses COMUNES a todos los modelos y modos."""
    end = _month(cfg.test_end)
    rows = []
    for (mode, model), g in preds.groupby(["mode", "model"], sort=True):
        lab = labels[mode]
        lab = lab[(lab["weight"] > 0) & ~lab["provisional"].astype(bool) & (lab.index <= end)]
        if cfg.phase == "development":
            lab = lab[lab.index < HOLDOUT_START]
        g = g.set_index("month")
        common = g.index.intersection(lab.index)
        sc = M.monthly_scores(g.loc[common, P_COLS].to_numpy(), lab.loc[common, P_COLS].to_numpy(),
                              lab.loc[common, "label_hard"].to_numpy())
        sc.insert(0, "month", common)
        sc.insert(0, "model", model)
        sc.insert(0, "mode", mode)
        rows.append(sc)
    S = pd.concat(rows, ignore_index=True)
    n_series = S.groupby(["mode", "model"]).ngroups
    cnt = S.groupby("month").size()
    common = cnt.index[cnt == n_series]
    S = S[S["month"].isin(common)].sort_values(["mode", "model", "month"]).reset_index(drop=True)
    rep = report(S, labels, cfg)
    return S, rep


def report(S: pd.DataFrame, labels: dict, cfg: HarnessConfig) -> dict:
    base = cfg.baseline
    out = {"muestra": {"n": int(S["month"].nunique()), "desde": f"{S['month'].min():%Y-%m}",
                       "hasta": f"{S['month'].max():%Y-%m}"},
           "modelos": {}, "frente_al_baseline": {}, "sensibilidad_modo": {}, "por_decada": {}, "por_episodio": {}}
    S = S.assign(decada=(S["month"].dt.year // 10 * 10))
    for (mode, model), g in S.groupby(["mode", "model"], sort=True):
        out["modelos"][f"{mode}/{model}"] = M.summary(g)
        out["por_decada"][f"{mode}/{model}"] = {int(d): M.summary(x) for d, x in g.groupby("decada")}
    for mode, gm in S.groupby("mode", sort=True):
        ref = gm[gm["model"] == base].set_index("month")
        lab = labels[mode]
        eps = M.episodes(lab[lab.index.isin(ref.index)])
        for model, g in gm.groupby("model", sort=True):
            if model == base:
                continue
            g = g.set_index("month").loc[ref.index]
            key = f"{mode}/{model}"
            out["frente_al_baseline"][key] = {
                "mejora_logloss": M.boot_mean(ref["logloss"].to_numpy() - g["logloss"].to_numpy()),
                "mejora_brier": M.boot_mean(ref["brier"].to_numpy() - g["brier"].to_numpy()),
                "bss": M.boot_bss(g["brier"].to_numpy(), ref["brier"].to_numpy()),
                "dif_acierto": M.boot_mean(g["hit"].to_numpy() - ref["hit"].to_numpy()),
                "por_decada": {int(d): float((ref.loc[x.index, "logloss"] - x["logloss"]).mean())
                               for d, x in g.assign(decada=g.index.year // 10 * 10).groupby("decada")},
            }
            ep = []
            for e in eps:
                sel = (g.index >= e["desde"]) & (g.index <= e["hasta"])
                if sel.sum() == 0:
                    continue
                ep.append({"tipo": e["tipo"], "id": e["id"], "n": int(sel.sum()),
                           "mejora_logloss": float((ref.loc[sel, "logloss"] - g.loc[sel, "logloss"]).mean())})
            out["por_episodio"][key] = {
                "episodios": ep,
                "resumen": {t: {"n_episodios": sum(1 for e in ep if e["tipo"] == t),
                                "gana_al_baseline": sum(1 for e in ep if e["tipo"] == t and e["mejora_logloss"] > 0)}
                            for t in ("recesion_nber", "racha_regimen")}}
    modes = sorted(S["mode"].unique())
    if "vintage" in modes and "latest_truncated" in modes:
        for model in sorted(S["model"].unique()):
            v = S[(S["mode"] == "vintage") & (S["model"] == model)].set_index("month")
            lt = S[(S["mode"] == "latest_truncated") & (S["model"] == model)].set_index("month").loc[v.index]
            out["sensibilidad_modo"][model] = {"latest_menos_vintage_logloss":
                                               M.boot_mean(v["logloss"].to_numpy() - lt["logloss"].to_numpy())}
    return out


def persistence_reference(datas: dict, cfg: HarnessConfig) -> dict:
    """Listón de la ficha/pit_base §6: persistencia PIT en su muestra completa común a los dos modos (≤ 2004)."""
    pers = {m: d.persistence_frame() for m, d in datas.items()}
    out = {}
    common = None
    for m, p in pers.items():
        lab = datas[m].score_labels(cfg.test_end)
        lab = lab[(lab["weight"] > 0) & ~lab["provisional"].astype(bool)]
        idx = p.index.intersection(lab.index)
        common = idx if common is None else common.intersection(idx)
    for m, p in pers.items():
        lab = datas[m].score_labels(cfg.test_end).loc[common]
        sc = M.monthly_scores(p.loc[common, PERS_COLS].to_numpy(), lab[P_COLS].to_numpy(), lab["label_hard"])
        out[m] = {**M.summary(sc), "desde": f"{common.min():%Y-%m}", "hasta": f"{common.max():%Y-%m}"}
    return out


# ------------------------------------------------------------------ corrida completa
def build_models(cfg: HarnessConfig, registry: dict | None = None) -> list[B.Model]:
    reg = registry or B.REGISTRY
    return [reg[n](**cfg.model_params.get(n, {})) for n in cfg.models]


def results_hash(preds: pd.DataFrame, rep: dict) -> str:
    p = preds.sort_values(["mode", "model", "month"]).reset_index(drop=True)
    p = p.assign(**{c: p[c].round(12) for c in P_COLS})
    h = hashlib.sha256(pd.util.hash_pandas_object(p, index=False).values.tobytes())
    h.update(json.dumps(rep, sort_keys=True, default=str).encode())
    return h.hexdigest()


def run(cfg: HarnessConfig, registry: dict | None = None, datas: dict | None = None, record: bool = True,
        spy=None) -> dict:
    """Corrida completa: walk-forward en cada modo, puntuación en meses comunes, informe y registro de pruebas."""
    from src.models import trials
    cfg.validate()
    if datas is None:
        # se niega aquí mismo (antes de leer nada) si falta el preregistro o la confirmación; una sola apertura
        vault = LabelVault(mode=cfg.phase, prereg_id=cfg.prereg_id)
        datas = {m: PITData(m, cfg.matrix_variant if m == "vintage" else "", cfg.phase, cfg.prereg_id,
                            cfg.feature_policy, vault=vault) for m in cfg.modes}
    if any(getattr(d, "phase", "development") != cfg.phase for d in datas.values()):
        raise ValueError("los datos no están en la fase de la configuración")
    preds, diags = [], {}
    for mode, data in datas.items():
        p, d = walk_forward(data, build_models(cfg, registry), cfg, spy=spy)
        preds.append(p)
        diags[mode] = d
    preds = pd.concat(preds, ignore_index=True)
    labels = {m: d.score_labels(cfg.test_end) for m, d in datas.items()}
    S, rep = score(preds, labels, cfg)
    if all(getattr(d, "kind", "") == "pit" for d in datas.values()):
        rep["persistencia_muestra_completa"] = persistence_reference(datas, cfg)
    res = {"config": asdict(cfg), "preds": preds, "scores": S, "report": rep, "diag": diags,
           "results_sha256": results_hash(preds, rep), "kind": sorted({d.kind for d in datas.values()}),
           "data_hashes": {m: d.hashes() for m, d in datas.items()}}
    if record:
        res["entry"] = trials.record(res)
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description="Arnés walk-forward (desarrollo: solo ≤ 2004)")
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = HarnessConfig.from_yaml(a.config)
    res = run(cfg)
    rep = res["report"]
    print(json.dumps({"muestra": rep["muestra"], "modelos": rep["modelos"],
                      "persistencia_muestra_completa": rep.get("persistencia_muestra_completa"),
                      "run_id": res["entry"]["run_id"], "results_sha256": res["results_sha256"]},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
