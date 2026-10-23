"""Arnés de backtest walk-forward del nowcast de régimen (Fase 3, entregable 3; docs/models/harness.md, v2).

Reglas (docs/PLAN.md "Validación", "Periodo bloqueado y reglas del arnés"; ficha de la etiqueta §7, §12 y adenda
2026-10-16; docs/models/pit_base.md §3):

1. Cortes walk-forward con ventana EXPANSIVA; reentreno cada `refit_every` meses. En el corte de mes m0 (fecha de
   decisión T0 = último día hábil de m0) se entrena y se predicen m0 … m0 + k − 1, cada uno con SU fecha de decisión.
2. Embargo ≥ 6 meses (s ≤ m0 − embargo); purga s + 4 < m0 (se comprueba en cada corte).
3. ETIQUETA DE ENTRENAMIENTO RECALCULADA con los datos conocidos en T0 (pit_labels.py, mismo modo que las variables),
   con PESO DE MADUREZ en los meses provisionales recalculados (§3b, función fijada a priori desde el estudio de
   revisión). La etiqueta oficial congelada v1.1 solo PUNTÚA, a través de la caja fuerte (vault.py).
4. Periodo bloqueado 2005-01 →: `run()` solo trabaja en `development`. La evaluación única tiene UN punto de entrada,
   `evaluate_holdout(prereg_id)`, que crea él mismo la caja fuerte (que consume el preregistro) y los datos.
5. Variables solo de la matriz PIT de la versión de la configuración (`pit_version`; v0.3 por defecto), con su hash
   fijado aquí, por nombre; `assert_no_forbidden()` antes de cada fit. Una versión CANDIDATA (p. ej. la v0.4, aún sin el
   ✅ del Validador) solo sirve en desarrollo; la evaluación única exige una versión en `P.FROZEN`.
   Modelos por eje (`AxisModel`): cada eje con sus variables y SU ventana; mínimo de entrenamiento por eje: meses,
   recesiones NBER y cambios de G (§5).
6. Ventana de evaluación FIJA (`eval_window`): todos los modelos deben predecir todos sus meses; si no, error (o aviso
   registrado con `allow_shrink`).
7. Modo principal `vintage`; `latest_truncated` como sensibilidad, puntuados sobre los MISMOS meses.
8. Cada corrida queda en el registro de pruebas (trials.py); con `record=False`, una línea mínima en la ruta fija.

    .venv/bin/python -m src.models.harness --config config/harness/baselines_v2.yaml --official
"""
from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.features import pit as P
from src.labels import regime_us as R
from src.models import base as B
from src.models import metrics as M
from src.models import probes  # noqa: F401  (registra la sonda del ensayo en seco)
from src.models import vault as V
from src.models.pit_labels import PITLabeler
from src.models.vault import HOLDOUT_START, LABEL_FILE_SHA256, HoldoutLocked, LabelVault, log_access

REPO = Path(__file__).resolve().parents[2]
QUADS, P_COLS, PERS_COLS = M.QUADS, M.P_COLS, B.PERS_COLS
LABEL_FORWARD = R.pace_need(R.PARAMS)            # 4: la etiqueta de s usa niveles hasta s + 4
MIN_EMBARGO = R.PARAMS.embargo_months             # 6
PIT_VERSION = "0.3"                               # versión por defecto (congelada; la de M1 v1 y los baselines)
MATRIX_SHA256_BY_VERSION = {
    "0.3": {   # congelada (FROZEN, tag pit-v0.3)
        "vintage": "6858f6c93bfe692ab7a9452f22db1986ba52f32e1300703c12ae60fb2b9c0fa9",
        "latest_truncated": "3d81ec88b17a5390e8b7c2099ef1a4406009a43b1e1f1751522b7767f9ff025b",
        "vintage_filadelfia_prudente": "b8df88442043edc946b41530e4d24fcfeeb4c81c2bcca0ccc917d1f8fa223f5e",
    },
    "0.4": {   # CANDIDATA (2026-10-23): v0.3 + 4 derivadas de riesgo de giro; solo desarrollo hasta el ✅ del Validador
        "vintage": "938d3d361d3a706383e587441f6e1402d43699ae72f625a47ef10e77ec487374",
        "latest_truncated": "58cf9c303266eb5d53528c228a310193b62872e01d089b7eec74f3621f637ab0",
        "vintage_filadelfia_prudente": "ef6121e659ea688f982213084007e6c562fcfe4b81d0f2fe1ac082aa261e70be",
    },
}
MATRIX_SHA256 = MATRIX_SHA256_BY_VERSION[PIT_VERSION]
ESTADOS = {"principal": ("principal", "principal_epoca"),
           "sensibilidad": ("principal", "principal_epoca", "condicional")}
AXES = ("G", "I")
AXIS_VEC = {"G": M.G_HIGH, "I": M.I_HIGH}
_EVAL: dict = {"vault": None}        # contexto de la evaluación única (solo lo fija evaluate_holdout)

# ------------------------------------------------------------------ peso de madurez (harness.md §3b; ficha, adenda)
# Fijado A PRIORI (2026-10-16, antes de correr ningún modelo con variables) desde el estudio de revisión congelado
# (docs/models/label_revision_study.md, "Tabla por k": concordancia de la etiqueta dura recalculada en T con la
# completa, variantes A y B). No usa ningún resultado del arnés ni la tabla del Validador (M-4).
#   c(k)  = min(concordancia A, concordancia B) en cada k de la tabla (la variante más conservadora);
#   c~(k) = min{c(k') : k' de la tabla, k' ≥ k}  (envolvente inferior monótona: nunca premia un k por ruido);
#   w(k)  = c~(k) / c~(60)  (c~(60) = 97,0 % = concordancia madura); w = 1 para los meses NO provisionales.
# k del estudio = meses entre el corte y el mes objetivo; la última fila del estudio es k = 4 y la de at(T) es
# m0 − 5, así que k_estudio = (m0 − s) − 1.
REVISION_STUDY_CONCORDANCE = {   # k: (A %, B %)
    4: (92.6, 89.4), 5: (87.2, 85.1), 6: (84.0, 86.2), 7: (84.0, 85.1), 8: (89.4, 88.3), 9: (90.5, 90.5),
    10: (93.7, 90.5), 11: (88.4, 86.3), 12: (83.2, 86.3), 18: (87.5, 88.5), 24: (89.7, 90.7), 30: (90.8, 90.8),
    36: (89.9, 90.9), 42: (89.0, 87.0), 48: (92.0, 90.0), 54: (96.0, 94.0), 55: (96.0, 95.0), 60: (98.0, 97.0),
    66: (98.0, 97.0), 72: (98.0, 97.0), 78: (98.0, 98.0), 84: (99.0, 97.0)}
_KS = sorted(REVISION_STUDY_CONCORDANCE)


def _cmin(k: int) -> float:
    ks = [x for x in _KS if x >= k] or [_KS[-1]]
    return min(min(REVISION_STUDY_CONCORDANCE[x]) for x in ks)


def maturity_weight(k_study: int) -> float:
    """w(k) del estudio de revisión (k = meses entre el corte y el mes objetivo, convención del estudio)."""
    return _cmin(max(int(k_study), _KS[0])) / _cmin(60)


WEIGHTING = ("madurez", "uno", "excluir")


def _month(d) -> pd.Timestamp:
    return pd.Timestamp(d).to_period("M").to_timestamp()


def _add(m: pd.Timestamp, k: int) -> pd.Timestamp:
    return m + pd.DateOffset(months=k)


def _mdiff(a: pd.Timestamp, b) -> np.ndarray:
    """Meses a − b (b escalar o índice)."""
    b = pd.DatetimeIndex(b) if not isinstance(b, pd.Timestamp) else b
    return (a.year - b.year) * 12 + (a.month - b.month)


def _warn(avisos: list, msg: str) -> None:
    avisos.append(msg)
    warnings.warn(msg, stacklevel=3)


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
    min_train_months: int = 120             # §5: mínimo de entrenamiento (decisión del usuario, 2026-10-16)
    min_train_recessions: int = 2           #     ≥ 2 recesiones NBER (pico ≤ último mes de entrenamiento − 12)
    min_train_g_changes: int = 8            #     ≥ 8 cambios del eje G (etiqueta recalculada) en la ventana
    test_start: str = "1956-10"
    test_end: str = "2004-12"
    eval_window: tuple | None = None        # ventana de evaluación FIJA (desde, hasta); None = (test_start, test_end)
    allow_shrink: bool = False              # True: si un modelo no cubre la ventana, aviso registrado (no error)
    epochs: tuple = (("1956-01", "1979-12"), ("1980-01", "2004-12"))
    subperiods: tuple = ()                  # estabilidad del signo (p. ej. 2005-14 / 2015+ en la evaluación única)
    feature_policy: str = "principal"
    pit_version: str = PIT_VERSION          # matriz PIT (hash en MATRIX_SHA256_BY_VERSION); candidata solo en desarrollo
    provisional_weighting: str = "madurez"  # §3b: "madurez" (principal), "uno" y "excluir" (sensibilidades)
    baseline: str = "persistence_pit"       # comparador principal (M0 en las corridas con modelos)
    reference: str | None = None            # comparador secundario que se informa (p. ej. persistence_pit)
    phase: str = "development"
    prereg_id: str | None = None
    who: str = "Constructor"
    nota: str = ""
    # --- preregistro de la evaluación única (v2.1; harness.md §4e, §6)
    principal: str | None = None            # modelo de la hipótesis principal (p. ej. M1)
    dry_run_window: tuple | None = None     # ventana ≤ 2004 del ENSAYO EN SECO (misma configuración, sin abrir nada)
    sensitivities: tuple = ()               # corridas secundarias en la MISMA evaluación: [{name, modes, matrix_variant,
    #                                         provisional_weighting, models, model_params, …}]
    expected_signs: dict = field(default_factory=dict)   # {modelo: {"<eje>:<variable>": "+"/"-" o {signo, decide}}}
    holm_families: tuple = ()               # [{nombre, modo, comparador, modelos, metrica (str o {modelo: métrica}), p}]

    def validate(self) -> None:
        if self.embargo_months < MIN_EMBARGO:
            raise ValueError(f"embargo {self.embargo_months} < {MIN_EMBARGO} meses (ficha §7): no permitido")
        if self.refit_every < 1:
            raise ValueError("refit_every ≥ 1")
        if self.feature_policy not in ESTADOS:
            raise ValueError(f"política de variables desconocida: {self.feature_policy}")
        if self.provisional_weighting not in WEIGHTING:
            raise ValueError(f"ponderación de provisionales desconocida: {self.provisional_weighting}")
        if self.baseline not in self.models or (self.reference and self.reference not in self.models):
            raise ValueError("el baseline y la referencia tienen que estar entre los modelos (misma muestra)")
        if self.phase not in ("development", "holdout_evaluation"):
            raise ValueError(f"fase desconocida: {self.phase}")
        if self.pit_version not in MATRIX_SHA256_BY_VERSION:
            raise ValueError(f"versión PIT desconocida: {self.pit_version}")
        if self.phase == "holdout_evaluation" and self.pit_version not in P.FROZEN:
            raise HoldoutLocked(f"la evaluación única exige una base PIT congelada: v{self.pit_version} no está en "
                                "FROZEN (falta el ✅ del Validador y la aprobación del usuario)")
        ends = [self.test_end] + ([self.eval_window[1]] if self.eval_window else [])
        if self.phase == "development" and max(_month(e) for e in ends) >= HOLDOUT_START:
            raise HoldoutLocked(f"test_end/eval_window dentro del periodo bloqueado (≥ {HOLDOUT_START:%Y-%m})")
        if self.phase == "holdout_evaluation" and _EVAL["vault"] is None:
            raise HoldoutLocked("la fase holdout_evaluation solo se ejecuta a través de evaluate_holdout(prereg_id)")
        if self.eval_window and (_month(self.eval_window[0]) < _month(self.test_start)
                                 or _month(self.eval_window[1]) > _month(self.test_end)):
            raise ValueError("eval_window fuera de [test_start, test_end]")

    @property
    def window(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        w = self.eval_window or (self.test_start, self.test_end)
        return _month(w[0]), _month(w[1])

    @classmethod
    def from_yaml(cls, path) -> "HarnessConfig":
        d = yaml.safe_load(Path(path).read_text())
        for k in ("models", "modes"):
            if k in d:
                d[k] = tuple(d[k])
        for k in ("eval_window", "dry_run_window"):
            if d.get(k) is not None:
                d[k] = tuple(d[k])
        for k in ("sensitivities", "holm_families"):
            if k in d:
                d[k] = tuple(d[k] or ())
        for k in ("epochs", "subperiods"):
            if k in d:
                d[k] = tuple(tuple(x) for x in d[k])
        return cls(**d)


# ------------------------------------------------------------------ datos
def _pers_extras(p: pd.DataFrame) -> pd.DataFrame:
    """Columnas derivadas de la persistencia PIT: one-hot de la dura y P(eje alto)."""
    p = p.copy()
    for q, c in zip(QUADS, B.PERS_HARD_COLS):
        p[c] = (p["pers_hard"] == q).astype(float)
    P4 = p[PERS_COLS].to_numpy(float)
    for ax, col in B.PERS_AXIS.items():
        p[col] = P4 @ AXIS_VEC[ax]
    return p


class PITData:
    """Matriz PIT congelada + etiqueta de entrenamiento recalculada + etiqueta oficial (caja fuerte), para un modo."""
    kind = "pit"

    def __init__(self, mode: str, variant: str = "", phase: str = "development", prereg_id: str | None = None,
                 policy: str = "principal", vault: LabelVault | None = None, pit_version: str = PIT_VERSION):
        self.mode, self.phase, self.policy, self.pit_version = mode, phase, policy, pit_version
        if pit_version not in MATRIX_SHA256_BY_VERSION:
            raise ValueError(f"versión PIT desconocida: {pit_version}")
        if phase == "holdout_evaluation" and pit_version not in P.FROZEN:
            raise HoldoutLocked(f"la evaluación única exige una base PIT congelada (v{pit_version} no está en FROZEN)")
        if phase == "holdout_evaluation":
            # identidad y tipo exacto, del preregistro y del contexto de evaluate_holdout: ANTES de leer nada (D3b)
            if not V.is_open_holdout_vault(vault, prereg_id) or _EVAL["vault"] is not vault:
                log_access({"mode": phase, "granted": False, "why": "PITData sin la caja fuerte de evaluate_holdout",
                            "prereg_id": prereg_id})
                raise HoldoutLocked("PITData en holdout_evaluation exige la caja fuerte creada por evaluate_holdout")
        elif phase == "development":
            if vault is None:
                vault = LabelVault()
            if type(vault) is not LabelVault or vault.mode != "development":
                raise TypeError("PITData en desarrollo exige una LabelVault de desarrollo")
        else:
            raise ValueError(f"fase desconocida: {phase}")
        self.vault = vault
        name = f"{mode}_{variant}" if variant else mode
        shas = MATRIX_SHA256_BY_VERSION[pit_version]
        if name not in shas:
            raise ValueError(f"matriz desconocida: {name}")
        path = P.out_dir() / f"pit_us_v{pit_version}_{name}.parquet"
        if P.file_sha(path) != shas[name]:
            raise RuntimeError(f"{path.name} no coincide con la matriz registrada de la v{pit_version}")
        self.matrix_name, self.matrix_sha = path.name, shas[name]
        filters = [("decision_date", "<", HOLDOUT_START.to_datetime64())] if phase == "development" else None
        X = pd.read_parquet(path, filters=filters)
        if phase == "development":
            assert X["decision_date"].max() < HOLDOUT_START
        X["month"] = X["decision_date"].dt.to_period("M").dt.to_timestamp()
        self.decision = X.set_index("month")["decision_date"]
        self.X = X.drop(columns=["decision_date"]).set_index("month")
        self.labeler = PITLabeler(mode, pit_version, vault=vault if phase == "holdout_evaluation" else None)
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
        u = self.labeler.inputs["usrec"].dropna()
        u.index = u.index.to_period("M").to_timestamp()
        self.usrec = u[u.index < HOLDOUT_START] if phase == "development" else u
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
        """Persistencia PIT (pers_*, pers_hard_*, pers_axis_*) de los meses pedidos, en su fecha de decisión."""
        self._pers = self._pers if self._pers is not None else {}
        for m in months:
            if m not in self._pers and m in self.decision.index:
                self._pers[m] = self.labeler.persistence(self.decision[m])
        rows = {m: self._pers[m] for m in months if self._pers.get(m) is not None}
        cols = ["label_month", *PERS_COLS, "pers_hard"]
        df = pd.DataFrame.from_dict(rows, orient="index", columns=cols).sort_index() if rows else \
            pd.DataFrame(columns=cols, index=pd.DatetimeIndex([]))
        return _pers_extras(df)

    def persistence_frame(self) -> pd.DataFrame:
        return self.pers_rows(self.decision.index)

    def score_labels(self, end) -> pd.DataFrame:
        return self.vault.load(end=end)

    def hashes(self) -> dict:
        return {"matrix": {self.matrix_name: self.matrix_sha}, "pit_snapshot": P.snapshot_ref(self.pit_version),
                "pit_version": self.pit_version,
                "pit_estado": "congelada" if self.pit_version in P.FROZEN else "candidata",
                "label_snapshot": R.FROZEN[R.PARAMS.version],
                "label_file_sha256": LABEL_FILE_SHA256[R.PARAMS.version]}


class ArrayData:
    """Datos en memoria para el placebo y los tests (NO es evidencia: el registro lo marca con su `kind`). Siempre en
    `development`. `target`: DataFrame mensual con p_*, label_hard, weight, provisional y usrec. La etiqueta de s se
    considera conocida en m0 si s ≤ m0 − label_lag (5); la persistencia de t es el objetivo de t − 5."""

    def __init__(self, X: pd.DataFrame, target: pd.DataFrame, colinfo: dict, kind: str = "placebo",
                 mode: str = "synthetic", label_lag: int = 5):
        if kind == "pit":
            raise ValueError("ArrayData no puede hacerse pasar por datos PIT")
        self.X, self.target, self.colinfo, self.kind, self.mode = X, target, colinfo, kind, mode
        self.lag = label_lag
        self.decision = pd.Series(X.index + pd.offsets.MonthEnd(0), index=X.index)
        self.first_official_provisional = pd.Timestamp("2262-01-01")
        self.usrec = target["usrec"].astype(float) if "usrec" in target else pd.Series(0.0, index=target.index)

    @property
    def phase(self) -> str:          # de solo lectura: ArrayData nunca está en holdout_evaluation
        return "development"

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
        return _pers_extras(p.dropna())

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
    de `block` meses (filas enteras: p_*, label_hard, usrec). `leak(target_barajado, rng) -> DataFrame` añade columnas
    con fuga (tests y tabla de potencia)."""
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
    meta = json.loads((P.out_dir() / f"pit_us_v{getattr(pit, 'pit_version', PIT_VERSION)}.meta.json").read_text()
                      )["columns"][pit.mode]
    out = {}
    for c, info in meta.items():
        b = [_month(info["vintage_desde"])] if info.get("vintage_desde") else []
        if c in ("growth_rt", "growth_rt_state"):
            b += [pd.Timestamp("1973-04-01"), pd.Timestamp("1981-05-01")]
        out[c] = sorted(b)
    return out


def sign_stability(coefs: pd.DataFrame, breaks: dict[str, list[pd.Timestamp]], min_refits: int = 12) -> pd.DataFrame:
    """`coefs`: coeficiente de cada variable por corte (índice = refit_month). Para cada variable y salto con
    ≥ `min_refits` cortes a cada lado: media antes/después y si conserva el signo."""
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
def _check_requested(model_name: str, req, data, cfg) -> None:
    unknown = [c for c in req if c not in data.X.columns]
    if unknown:
        raise KeyError(f"{model_name}: variables fuera de la matriz PIT congelada: {unknown}")
    bad = [c for c in req if data.colinfo[c]["estado"] not in ESTADOS[cfg.feature_policy]]
    if bad:
        raise ValueError(f"{model_name}: variables no admitidas con la política {cfg.feature_policy}: {bad}")


def resolve_features(model: B.Model, data, cfg: HarnessConfig, train_months: pd.DatetimeIndex) -> tuple[list, list]:
    """Columnas que un modelo de 4 cuadrantes puede usar en este corte y columnas descartadas (con motivo).
    Con `features="principal"` la ventana salta a cada nueva columna (política de épocas implícita de la v1; se
    conserva solo para pruebas: los aspirantes son `AxisModel` con variables explícitas y ventana fija por eje)."""
    if not model.features:
        return [], []
    allowed = ESTADOS[cfg.feature_policy]
    if model.features == "principal":
        req = [c for c in data.X.columns if data.colinfo[c]["estado"] in allowed]
    else:
        req = list(model.features)
        _check_requested(model.name, req, data, cfg)
    use, drop = [], []
    for c in req:
        st = data.colinfo[c]["start"]
        n = int((train_months >= st).sum()) if st is not None else 0
        (use if n >= cfg.min_train_months else drop).append(c if n >= cfg.min_train_months else (c, f"época: {n} m"))
    return use, drop


def axis_window_start(feats, data) -> pd.Timestamp | None:
    """Inicio FIJO de la ventana de un eje: el inicio más tardío de SUS variables (no depende de otros ejes)."""
    st = [data.colinfo[c]["start"] for c in feats]
    if any(s is None for s in st):
        raise ValueError(f"variables sin datos: {feats}")
    return max(st) if st else None


def count_recessions(usrec: pd.Series, start: pd.Timestamp, last_train: pd.Timestamp) -> int:
    """Recesiones NBER con pico en [primer mes de entrenamiento, último − 12]: el anuncio del pico llega con 4-12 meses de retraso, así
    que solo cuentan las que se conocían en el corte (umbral de admisión; nunca entra como variable)."""
    u = usrec.fillna(0).astype(int)
    peaks = u.index[(u == 1) & (u.shift(1, fill_value=0) == 0)]
    return int(((peaks >= start) & (peaks <= _add(last_train, -12))).sum())


def count_g_changes(Y: np.ndarray) -> int:
    g = (np.asarray(Y, float) @ M.G_HIGH >= 0.5).astype(int)
    return int((np.diff(g) != 0).sum()) if len(g) > 1 else 0


def train_weights(tr: pd.DataFrame, m0: pd.Timestamp, how: str) -> pd.Series:
    """Peso de cada mes de entrenamiento (§3b): madurez (principal), uno o excluir (provisionales recalculados → 0)."""
    prov = tr["provisional"].astype(bool).to_numpy() if "provisional" in tr else np.zeros(len(tr), bool)
    w = tr["weight"].to_numpy(float).copy()
    if how == "excluir":
        w[prov] = 0.0
    elif how == "madurez":
        k = _mdiff(m0, tr.index) - 1
        w[prov] *= np.array([maturity_weight(x) for x in k[prov]])
    return pd.Series(w, index=tr.index)


# ------------------------------------------------------------------ walk-forward
def _eligible(cfg, n, n_rec, n_gch) -> bool:
    return n >= cfg.min_train_months and n_rec >= cfg.min_train_recessions and n_gch >= cfg.min_train_g_changes


def _check_phase(data, cfg) -> None:
    if data.phase != cfg.phase:
        raise ValueError("los datos no están en la fase de la configuración")
    if cfg.phase == "holdout_evaluation":
        if not isinstance(data, PITData) or type(data) is not PITData or _EVAL["vault"] is None \
                or data.vault is not _EVAL["vault"] or not V.is_open_holdout_vault(data.vault, cfg.prereg_id):
            raise HoldoutLocked("holdout_evaluation exige PITData con la caja fuerte abierta por evaluate_holdout")


def walk_forward(data, models: list[B.Model], cfg: HarnessConfig, spy=None) -> tuple[pd.DataFrame, list[dict]]:
    """Predicciones fuera de muestra de cada modelo (un modo). `spy(model, info, X, Y)` solo para tests."""
    cfg.validate()
    _check_phase(data, cfg)
    months = data.X.index
    test = months[(months >= _month(cfg.test_start)) & (months <= _month(cfg.test_end))]
    preds, diag = [], []
    for b in range(0, len(test), cfg.refit_every):
        block = test[b:b + cfg.refit_every]
        m0 = block[0]
        data.check_cut(block[-1])
        lab = data.train_targets(m0)
        cut = _add(m0, -cfg.embargo_months)
        tr = lab[(lab.index <= cut) & (lab["weight"] > 0)]
        tr = tr[tr.index.isin(months)]
        if len(tr):
            assert tr.index.max() <= cut and _add(tr.index.max(), LABEL_FORWARD) < m0, "embargo/purga violados"
        wts = train_weights(tr, m0, cfg.provisional_weighting)
        tr, wts = tr[wts > 0], wts[wts > 0]
        for model in models:
            if isinstance(model, B.AxisModel):
                out, d = _fit_predict_axes(model, data, cfg, tr, wts, m0, block, spy)
            else:
                out, d = _fit_predict_4(model, data, cfg, tr, wts, m0, block, spy)
            diag.append(d)
            if out is None or len(out) == 0:
                continue
            out.insert(0, "refit_month", m0)
            out.insert(0, "model", model.name)
            out.insert(0, "mode", data.mode)
            preds.append(out)
    P_ = pd.concat(preds).rename_axis("month").reset_index() if preds else pd.DataFrame()
    return P_, diag


def _fit_predict_4(model, data, cfg, tr, wts, m0, block, spy):
    use, drop = resolve_features(model, data, cfg, tr.index)
    Xtr = data.X.loc[tr.index if model.needs_training else tr.index[:0], use]
    n_drop = 0
    if use:
        start = max(data.colinfo[c]["start"] for c in use)
        Xtr = Xtr[Xtr.index >= start]
        n0 = len(Xtr)
        Xtr = Xtr.dropna()
        n_drop = n0 - len(Xtr)
    if model.uses_persistence:
        Xtr = Xtr.join(data.pers_rows(Xtr.index)[PERS_COLS + B.PERS_HARD_COLS], how="inner")
    R.assert_no_forbidden(list(Xtr.columns))
    assert set(Xtr.columns) <= set(data.X.columns) | set(PERS_COLS) | set(B.PERS_HARD_COLS)
    Y, y, w = tr.loc[Xtr.index, P_COLS].to_numpy(float), tr.loc[Xtr.index, "label_hard"].to_numpy(), \
        wts.loc[Xtr.index].to_numpy(float)
    info = {"refit_month": m0, "decision_date": data.decision[m0], "mode": data.mode,
            "train_months": Xtr.index, "features": use}
    n_rec = count_recessions(data.usrec, Xtr.index.min() if len(Xtr) else None, Xtr.index.max()) if len(Xtr) else 0
    n_gch = count_g_changes(Y)
    d = {"model": model.name, "refit_month": m0, "n_train": len(Xtr), "n_recesiones": n_rec, "n_cambios_g": n_gch,
         "dropna_filas": n_drop}
    if model.needs_training and not _eligible(cfg, len(Xtr), n_rec, n_gch):
        return None, {**d, "skipped": True}
    if spy is not None:
        spy(model, info, Xtr, Y)
    model.fit(Xtr, Y, y, info, sample_weight=w)
    Xte = data.X.loc[block, use]
    n_imp = int(Xte.isna().sum().sum())
    if n_imp:
        Xte = Xte.fillna(Xtr[use].mean())
    if model.uses_persistence:
        Xte = Xte.join(data.pers_rows(block)[PERS_COLS + B.PERS_HARD_COLS], how="inner")
    if len(Xte) == 0:
        return None, d
    Pm = np.asarray(model.predict_proba(Xte, info), float)
    if Pm.shape != (len(Xte), len(QUADS)) or not np.isfinite(Pm).all():
        raise ValueError(f"{model.name}: predict_proba devolvió {Pm.shape} / no finito")
    out = pd.DataFrame(Pm, columns=P_COLS, index=Xte.index)
    out["n_train"] = len(Xtr)
    d.update({"features": use, "dropped": drop, "imputed_cells": n_imp, "peso_medio": float(w.mean()) if len(w) else None,
              "coef": model.coefficients() if hasattr(model, "coefficients") else None})
    return out, d


def _fit_predict_axes(model, data, cfg, tr, wts, m0, block, spy):
    """Un modelo por eje con SU ventana (inicio más tardío de sus variables) y SU elegibilidad; producto de ejes."""
    d = {"model": model.name, "refit_month": m0, "ejes": {}}
    pa, ok = {}, True
    pers_te = data.pers_rows(block) if model.uses_persistence else None
    for ax in AXES:
        feats = list(model.axis_features.get(ax, ()))
        _check_requested(model.name, feats, data, cfg)
        start = axis_window_start(feats, data)
        sub = tr if start is None else tr[tr.index >= start]
        Xtr = data.X.loc[sub.index, feats]
        n0 = len(Xtr)
        Xtr = Xtr.dropna()
        n_drop = n0 - len(Xtr)
        if model.uses_persistence:
            Xtr = Xtr.join(data.pers_rows(Xtr.index)[[B.PERS_AXIS[ax]]], how="inner")
        R.assert_no_forbidden(list(Xtr.columns))
        assert set(Xtr.columns) <= set(data.X.columns) | set(B.PERS_AXIS.values())
        Y = sub.loc[Xtr.index, P_COLS].to_numpy(float)
        t, w = Y @ AXIS_VEC[ax], wts.loc[Xtr.index].to_numpy(float)
        n_rec = count_recessions(data.usrec, Xtr.index.min(), Xtr.index.max()) if len(Xtr) else 0
        n_gch = count_g_changes(Y)
        de = {"ventana_desde": None if start is None else f"{start:%Y-%m}",
              "primer_mes": f"{Xtr.index.min():%Y-%m}" if len(Xtr) else None, "n_train": len(Xtr),
              "n_recesiones": n_rec, "n_cambios_g": n_gch, "dropna_filas": n_drop, "features": feats}
        d["ejes"][ax] = de
        if not _eligible(cfg, len(Xtr), n_rec, n_gch):
            de["skipped"], ok = True, False
            continue
        info = {"refit_month": m0, "decision_date": data.decision[m0], "mode": data.mode, "axis": ax,
                "train_months": Xtr.index, "features": feats}
        if spy is not None:
            spy(model, info, Xtr, Y)
        model.fit_axis(ax, Xtr, t, w, info)
        Xte = data.X.loc[block, feats]
        n_imp = int(Xte.isna().sum().sum())
        if n_imp:
            Xte = Xte.fillna(Xtr[feats].mean())
        if model.uses_persistence:
            Xte = Xte.join(pers_te[[B.PERS_AXIS[ax]]], how="inner")
        de["imputed_cells"] = n_imp
        if len(Xte):
            p = np.asarray(model.predict_axis(ax, Xte, info), float)
            if p.shape != (len(Xte),) or not np.isfinite(p).all():
                raise ValueError(f"{model.name}: predict_axis({ax}) devolvió {p.shape} / no finito")
            pa[ax] = pd.Series(p, index=Xte.index)
    if hasattr(model, "coefficients"):
        d["coef"] = model.coefficients()
    if not ok or len(pa) < 2:
        d["skipped"] = not ok
        return None, d
    idx = pa["G"].index.intersection(pa["I"].index)
    out = pd.DataFrame(M.combine_axes(pa["G"].loc[idx], pa["I"].loc[idx]), columns=P_COLS, index=idx)
    out["n_train"] = min(e["n_train"] for e in d["ejes"].values())
    return out, d


# ------------------------------------------------------------------ puntuación
def scorable(lab: pd.DataFrame, cfg: HarnessConfig) -> pd.DataFrame:
    end = _month(cfg.test_end)
    lab = lab[(lab["weight"] > 0) & ~lab["provisional"].astype(bool) & (lab.index <= end)]
    if cfg.phase == "development":
        lab = lab[lab.index < HOLDOUT_START]
    return lab


def score(preds: pd.DataFrame, labels: dict[str, pd.DataFrame], cfg: HarnessConfig) -> tuple[pd.DataFrame, dict]:
    """Puntúa contra la etiqueta oficial (por modo) en la ventana de evaluación FIJA (`eval_window`), común a todos los
    modelos y modos. Si algún modelo no la cubre: error, o con `allow_shrink` aviso registrado y muestra común."""
    w0, w1 = cfg.window
    rows, avisos = [], []
    for (mode, model), g in preds.groupby(["mode", "model"], sort=True):
        lab = scorable(labels[mode], cfg)
        g = g.set_index("month")
        common = g.index.intersection(lab.index)
        sc = M.monthly_scores(g.loc[common, P_COLS].to_numpy(), lab.loc[common, P_COLS].to_numpy(),
                              lab.loc[common, "label_hard"].to_numpy())
        sc.insert(0, "month", common)
        sc.insert(0, "model", model)
        sc.insert(0, "mode", mode)
        rows.append(sc)
    S_all = pd.concat(rows, ignore_index=True)
    target = None
    for mode in labels:
        lab = scorable(labels[mode], cfg)
        tm = set(lab.index[(lab.index >= w0) & (lab.index <= w1)])
        target = tm if target is None else target & tm
    target = sorted(target)
    series = {k: set(g["month"]) for k, g in S_all.groupby(["mode", "model"])}
    missing = {f"{k[0]}/{k[1]}": len(set(target) - v) for k, v in series.items() if set(target) - v}
    expected = {(m, n) for m in labels for n in cfg.models}
    absent = [f"{m}/{n}" for m, n in sorted(expected - set(series))]
    if missing or absent:
        msg = (f"la ventana de evaluación {w0:%Y-%m} → {w1:%Y-%m} ({len(target)} meses) no la cubren todos los "
               f"modelos: faltan meses {missing}; sin predicciones {absent}")
        if not cfg.allow_shrink:
            raise ValueError(msg + " (allow_shrink: false)")
        _warn(avisos, msg + " → muestra común REDUCIDA (allow_shrink)")
    keep = set(target)
    for v in series.values():
        keep &= v
    S = S_all[S_all["month"].isin(keep)].sort_values(["mode", "model", "month"]).reset_index(drop=True)
    rep = report(S, labels, cfg)
    rep["avisos"] = avisos
    rep["ventana_evaluacion"] = {"desde": f"{w0:%Y-%m}", "hasta": f"{w1:%Y-%m}", "meses_puntuables": len(target),
                                 "meses_usados": int(S["month"].nunique()), "reducida": len(keep) < len(target)}
    rep["cobertura_completa_por_modelo"] = {f"{m}/{n}": {**M.summary(g), "desde": f"{g['month'].min():%Y-%m}"}
                                            for (m, n), g in S_all.groupby(["mode", "model"], sort=True)}
    return S, rep


def _cmp(ref: pd.DataFrame, g: pd.DataFrame, cuts: pd.DataFrame, eps: list, cfg: HarnessConfig, lab) -> dict:
    """Comparación mes a mes de un modelo frente a un comparador (mismos meses)."""
    d = ref["logloss"] - g["logloss"]
    out = {"mejora_logloss": M.boot_mean(d.to_numpy()),
           "mejora_logloss_b24": M.boot_mean(d.to_numpy(), M.BOOT24),
           "mejora_ll_g": M.boot_mean((ref["ll_g"] - g["ll_g"]).to_numpy()),
           "mejora_ll_i": M.boot_mean((ref["ll_i"] - g["ll_i"]).to_numpy()),
           "mejora_brier": M.boot_mean((ref["brier"] - g["brier"]).to_numpy()),
           "bss": M.boot_bss(g["brier"].to_numpy(), ref["brier"].to_numpy()),
           "dif_acierto": M.boot_mean((g["hit"] - ref["hit"]).to_numpy()),
           "por_decada": {int(k): float(x.mean()) for k, x in d.groupby(d.index.year // 10 * 10)}}
    per = {}
    for a, b in list(cfg.epochs) + list(cfg.subperiods):
        sel = (d.index >= _month(a)) & (d.index <= _month(b))
        if sel.any():
            per[f"{a}→{b}"] = {"n": int(sel.sum()), "desde_real": f"{d.index[sel].min():%Y-%m}",
                               "hasta_real": f"{d.index[sel].max():%Y-%m}", "mejora_logloss": float(d[sel].mean()),
                               "mejora_ll_g": float((ref["ll_g"] - g["ll_g"])[sel].mean()),
                               "mejora_ll_i": float((ref["ll_i"] - g["ll_i"])[sel].mean())}
    out["por_periodo"] = per
    signs = [np.sign(v["mejora_logloss"]) for k, v in per.items()
             if tuple(k.split("→")) in {tuple(map(str, s)) for s in cfg.subperiods}]
    out["subperiodos_mismo_signo"] = bool(len(set(signs)) == 1) if signs else None
    c = cuts.loc[d.index]
    out["cortes"] = {
        "giro": M.boot_mean(d[c["giro"]].to_numpy()), "estable": M.boot_mean(d[~c["giro"]].to_numpy()),
        "giro_ll_g": float((ref["ll_g"] - g["ll_g"])[c["giro"]].mean()) if c["giro"].any() else None,
        **{f"desde_cambio_{k}": float(x.mean()) for k, x in d.groupby(c["desde_cambio"])},
        **{f"cuadrante_{k}": float(x.mean()) for k, x in d.groupby(c["cuadrante"])},
        "frontera": float(d[c["frontera"]].mean()) if c["frontera"].any() else None,
        "no_frontera": float(d[~c["frontera"]].mean())}
    ep = []
    for e in eps:
        sel = (d.index >= e["desde"]) & (d.index <= e["hasta"])
        if sel.any():
            ep.append({"tipo": e["tipo"], "id": e["id"], "n": int(sel.sum()), "mejora_logloss": float(d[sel].mean()),
                       "truncado": bool(e.get("truncado"))})
    res = {}
    for t in ("recesion_nber", "racha_regimen", "giro_g"):
        xs = [e for e in ep if e["tipo"] == t and not e["truncado"]]      # B2-5: los truncados no deciden
        wins = sum(e["mejora_logloss"] > 0 for e in xs)
        res[t] = {"n_episodios": len(xs), "gana": int(wins), "prueba_signo_p": M.sign_test(wins, len(xs)),
                  "truncados": sum(e["tipo"] == t and e["truncado"] for e in ep)}
    out["por_episodio"] = {"episodios": ep, "resumen": res}
    return out


def report(S: pd.DataFrame, labels: dict, cfg: HarnessConfig) -> dict:
    out = {"muestra": {"n": int(S["month"].nunique()), "desde": f"{S['month'].min():%Y-%m}",
                       "hasta": f"{S['month'].max():%Y-%m}"},
           "modelos": {}, "frente_al_baseline": {}, "frente_a_referencia": {}, "holm": {}, "sensibilidad_modo": {},
           "por_decada": {}, "por_periodo": {}, "calibracion": {}, "deteccion_giros_g": {}, "dependencia_ejes": {},
           "cortes_modelo": {}}
    for mode, gm in S.groupby("mode", sort=True):
        lab = labels[mode]
        months = pd.DatetimeIndex(sorted(gm["month"].unique()))
        lab_s = lab.loc[months]
        cuts = M.month_cuts(lab.loc[lab.index <= months.max()]).loc[months]
        eps = M.episodes(lab_s)
        tg, ti = lab_s[P_COLS].to_numpy(float) @ M.G_HIGH, lab_s[P_COLS].to_numpy(float) @ M.I_HIGH
        by = {m: g.set_index("month").loc[months] for m, g in gm.groupby("model", sort=True)}
        for model, g in by.items():
            key = f"{mode}/{model}"
            out["modelos"][key] = M.summary(g)
            out["por_decada"][key] = {int(k): M.summary(x) for k, x in g.groupby(g.index.year // 10 * 10)}
            out["por_periodo"][key] = {f"{a}→{b}": M.summary(g[(g.index >= _month(a)) & (g.index <= _month(b))])
                                       for a, b in list(cfg.epochs) + list(cfg.subperiods)
                                       if ((g.index >= _month(a)) & (g.index <= _month(b))).any()}
            out["cortes_modelo"][key] = {"giro": M.summary(g[cuts["giro"].to_numpy()]),
                                         "estable": M.summary(g[~cuts["giro"].to_numpy()])}
            out["calibracion"][key] = {"G": M.calibration(g["pg"], tg), "I": M.calibration(g["pi"], ti)}
            out["deteccion_giros_g"][key] = M.detection(g["pg"], lab_s)
            rg, ri = tg - g["pg"].to_numpy(), ti - g["pi"].to_numpy()
            out["dependencia_ejes"][key] = {"corr_residuos_G_I": float(np.corrcoef(rg, ri)[0, 1])
                                            if rg.std() > 0 and ri.std() > 0 else None}
        for comp, slot in ((cfg.baseline, "frente_al_baseline"), (cfg.reference, "frente_a_referencia")):
            if not comp or comp not in by:
                continue
            ref = by[comp]
            for model, g in by.items():
                if model == comp:
                    continue
                r = _cmp(ref, g, cuts, eps, cfg, lab_s)
                dg = out["deteccion_giros_g"]
                r["deteccion_frente_al_comparador"] = M.detection_vs(dg[f"{mode}/{model}"], dg[f"{mode}/{comp}"])
                out[slot][f"{mode}/{model}"] = r
        fam = {k: v["mejora_logloss"]["p_h0"] for k, v in out["frente_al_baseline"].items() if k.startswith(mode + "/")}
        out["holm"][mode] = {"familia": "frente al baseline (p_h0, unilateral)", "ajustado": M.holm(fam)}
        for f in cfg.holm_families:
            if f.get("modo", "vintage") == mode:
                out.setdefault("holm_familias", {})[f["nombre"]] = holm_family(f, by)
    modes = sorted(S["mode"].unique())
    if "vintage" in modes and "latest_truncated" in modes:
        for model in sorted(S["model"].unique()):
            v = S[(S["mode"] == "vintage") & (S["model"] == model)].set_index("month")
            lt = S[(S["mode"] == "latest_truncated") & (S["model"] == model)].set_index("month").loc[v.index]
            out["sensibilidad_modo"][model] = {"latest_menos_vintage_logloss":
                                               M.boot_mean(v["logloss"].to_numpy() - lt["logloss"].to_numpy())}
    return out


HOLM_P = ("frac_rep_le0", "p_h0")
METRICS = ("logloss", "ll_g", "ll_i")


def family_members(f: dict) -> list[dict]:
    """Miembros de una familia de Holm: `miembros: [{id, modelo, metrica, comparador?}]` o, abreviado, `modelos` +
    `metrica` (str o {modelo: métrica}) + `comparador`."""
    if f.get("miembros"):
        return [{"id": x.get("id", f"{x['modelo']}/{x.get('metrica', 'logloss')}"), "modelo": x["modelo"],
                 "metrica": x.get("metrica", "logloss"), "comparador": x.get("comparador", f.get("comparador"))}
                for x in f["miembros"]]
    met = f.get("metrica", "logloss")
    return [{"id": m, "modelo": m, "metrica": met[m] if isinstance(met, dict) else met, "comparador": f["comparador"]}
            for m in f.get("modelos", [])]


def holm_family(f: dict, by: dict) -> dict:
    """Holm sobre una familia PREREGISTRADA (M2-4): cada miembro frente a SU comparador, en SU métrica (p. ej. P-EVAL-MOD:
    M1 + módulo frente a M1, eje G o I según el módulo) con el p preregistrado (`frac_rep_le0` en P-EVAL-MOD)."""
    pname = f.get("p", "frac_rep_le0")
    ps, det = {}, {}
    for x in family_members(f):
        b = M.boot_mean((by[x["comparador"]][x["metrica"]] - by[x["modelo"]][x["metrica"]]).to_numpy())
        ps[x["id"]], det[x["id"]] = b[pname], {**x, **b}
    return {"p": pname, "sin_corregir": ps, "ajustado": M.holm(ps), "detalle": det}


def _sign_spec(v) -> tuple[float, bool]:
    if isinstance(v, dict):
        return (1.0 if str(v["signo"]).startswith("+") else -1.0), bool(v.get("decide", True))
    return (1.0 if str(v).startswith("+") else -1.0), True


def _coef_key(k: str) -> str:
    """Claves de `coefficients()`: "<eje>:<variable>" (sonda) o "<eje>_<variable>" (M1, `models_logit`) → "<eje>:…"."""
    return k if ":" in k else (f"{k[0]}:{k[2:]}" if k[:2] in ("G_", "I_") else k)


def coefficient_signs(diags: dict, datas: dict, cfg: HarnessConfig) -> dict:
    """Criterio 5 del preregistro (M2-4): signo de cada coeficiente preregistrado y su estabilidad a ambos lados de los
    saltos de vintage. Coeficientes = `model.coefficients()` en cada corte (claves "<eje>:<variable>").
    - `signos`: en los cortes cuyo mes cae en la ventana de evaluación: media, fracción de cortes con el signo esperado
      y `coincide` = signo de la media igual al preregistrado.
    - `sign_stability`: con TODOS los cortes del walk-forward (también los anteriores a la ventana), media antes y después
      de cada salto con ≥ 12 cortes a cada lado (`vintage_breaks`; la variable es la parte tras "<eje>:").
    - `criterio_signos_cumple`: todos los que deciden coinciden y conservan el signo en todos sus saltos evaluables."""
    out = {}
    w0, w1 = cfg.window
    for model, exp in (cfg.expected_signs or {}).items():
        for mode, dl in diags.items():
            key = f"{mode}/{model}"
            rows = {x["refit_month"]: x["coef"] for x in dl if x["model"] == model and x.get("coef")}
            if not rows:
                out[key] = {"error": f"{model} no expone coefficients() o no se ajustó"}
                continue
            C = pd.DataFrame.from_dict(rows, orient="index").sort_index().rename(columns=_coef_key)
            Cw = C[(C.index >= w0) & (C.index <= w1)]
            per = {}
            for k, v in exp.items():
                sg, decide = _sign_spec(v)
                if k not in C or Cw[k].dropna().empty:
                    per[k] = {"esperado": "+" if sg > 0 else "-", "decide": decide, "error": "sin coeficiente"}
                    continue
                x = Cw[k].dropna()
                per[k] = {"esperado": "+" if sg > 0 else "-", "decide": decide, "n_cortes": int(len(x)),
                          "media": float(x.mean()), "frac_signo_esperado": float((np.sign(x) == sg).mean()),
                          "coincide": bool(np.sign(x.mean()) == sg)}
            data = datas[mode]
            vb = vintage_breaks(data) if getattr(data, "kind", "") == "pit" else {}
            keys = [k for k in exp if k in C]
            st = sign_stability(C[keys], {k: vb.get(k.split(":", 1)[-1], []) for k in keys})
            st_rows = st.to_dict("records") if len(st) else []
            dec = [k for k, v in exp.items() if _sign_spec(v)[1]]
            ok = all(per[k].get("coincide") is True for k in dec) and \
                all(r["mismo_signo"] for r in st_rows if r["variable"] in dec)
            out[key] = {"signos": per, "sign_stability": [{**r, "media_antes": float(r["media_antes"]),
                                                            "media_despues": float(r["media_despues"])}
                                                           for r in st_rows],
                        "criterio_signos_cumple": bool(ok)}
    return out


def persistence_reference(datas: dict, cfg: HarnessConfig) -> dict:
    """Listón de la ficha/pit_base §6: persistencia PIT cruda en su muestra completa común a los dos modos (≤ 2004)."""
    pers = {m: d.persistence_frame() for m, d in datas.items()}
    out, common = {}, None
    for m, p in pers.items():
        lab = scorable(datas[m].score_labels(cfg.test_end), cfg)
        idx = p.index.intersection(lab.index)
        common = idx if common is None else common.intersection(idx)
    for m, p in pers.items():
        lab = datas[m].score_labels(cfg.test_end).loc[common]
        sc = M.monthly_scores(p.loc[common, PERS_COLS].to_numpy(), lab[P_COLS].to_numpy(), lab["label_hard"])
        out[m] = {**M.summary(sc), "desde": f"{common.min():%Y-%m}", "hasta": f"{common.max():%Y-%m}"}
    return out


# ------------------------------------------------------------------ corrida completa
def model_registry() -> dict:
    """Modelos registrados: los de `base` (+ la sonda) y el `REGISTRY` de cada módulo `src/models/models_*.py` (M1 y
    los demás aspirantes del entregable 4). `evaluate_holdout` y el ensayo en seco usan este registro (no aceptan uno
    externo)."""
    import importlib
    reg = dict(B.REGISTRY)
    for f in sorted(Path(__file__).resolve().parent.glob("models_*.py")):
        mod = importlib.import_module(f"src.models.{f.stem}")
        for k, v in getattr(mod, "REGISTRY", {}).items():
            if k in reg and reg[k] is not v:
                raise ValueError(f"modelo {k!r} registrado dos veces ({f.name})")
            reg[k] = v
    return reg


def build_models(cfg: HarnessConfig, registry: dict | None = None) -> list[B.Model]:
    reg = registry or model_registry()
    return [reg[n](**cfg.model_params.get(n, {})) for n in cfg.models]


def _round(o, nd=10):
    if isinstance(o, float):
        return round(o, nd) if o == o else None
    if isinstance(o, dict):
        return {str(k): _round(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v, nd) for v in o]
    return o


def results_hash(preds: pd.DataFrame, rep: dict, nd: int | None = None) -> str:
    """Hash de predicciones + informe. nd=None: bit a bit (predicciones a 12 decimales, informe tal cual, como la v1);
    nd=10: todo redondeado a 10 decimales (estable entre máquinas y versiones de BLAS)."""
    p = preds.sort_values(["mode", "model", "month"]).reset_index(drop=True)
    p = p.assign(**{c: p[c].round(12 if nd is None else nd) for c in P_COLS})
    h = hashlib.sha256(pd.util.hash_pandas_object(p, index=False).values.tobytes())
    h.update(json.dumps(rep if nd is None else _round(rep, nd), sort_keys=True, default=str).encode())
    return h.hexdigest()


def _run(cfg: HarnessConfig, datas: dict, registry: dict | None, record: bool, spy=None) -> dict:
    from src.models import trials
    cfg.validate()
    for d in datas.values():
        _check_phase(d, cfg)
    preds, diags = [], {}
    for mode, data in datas.items():
        p, d = walk_forward(data, build_models(cfg, registry), cfg, spy=spy)
        preds.append(p)
        diags[mode] = d
    preds = pd.concat(preds, ignore_index=True)
    labels = {m: d.score_labels(cfg.test_end) for m, d in datas.items()}
    S, rep = score(preds, labels, cfg)
    avisos = rep["avisos"]
    for mode, dl in diags.items():
        n_drop = sum(x.get("dropna_filas", 0) + sum(e.get("dropna_filas", 0) for e in x.get("ejes", {}).values())
                     for x in dl)
        if n_drop:
            _warn(avisos, f"{mode}: dropna quitó {n_drop} filas de entrenamiento (suma sobre cortes y modelos)")
    if all(getattr(d, "kind", "") == "pit" for d in datas.values()):
        rep["persistencia_muestra_completa"] = persistence_reference(datas, cfg)
    if cfg.expected_signs:
        rep["signos_coeficientes"] = coefficient_signs(diags, datas, cfg)
    res = {"config": asdict(cfg), "preds": preds, "scores": S, "report": rep, "diag": diags,
           "results_sha256": results_hash(preds, rep), "results_sha256_r10": results_hash(preds, rep, 10),
           "kind": sorted({d.kind for d in datas.values()}), "data_hashes": {m: d.hashes() for m, d in datas.items()}}
    if record:
        res["entry"] = trials.record(res)
    else:
        V.log_unrecorded_run({"name": cfg.name, "phase": cfg.phase, "kind": res["kind"], "models": list(cfg.models),
                              "results_sha256": res["results_sha256"], "muestra": rep["muestra"]})
    return res


def run(cfg: HarnessConfig, registry: dict | None = None, datas: dict | None = None, record: bool = True,
        spy=None) -> dict:
    """Corrida de DESARROLLO (≤ 2004): walk-forward en cada modo, puntuación en la ventana fija, informe y registro.
    La evaluación única no pasa por aquí: `evaluate_holdout(prereg_id)`."""
    if cfg.phase != "development":
        raise HoldoutLocked("run() solo trabaja en development; la evaluación única es evaluate_holdout(prereg_id)")
    cfg.validate()
    if datas is None:
        vault = LabelVault()
        datas = {m: PITData(m, cfg.matrix_variant if m == "vintage" else "", "development", None,
                            cfg.feature_policy, vault=vault, pit_version=cfg.pit_version) for m in cfg.modes}
    return _run(cfg, datas, registry, record, spy)


# ------------------------------------------------------------------ ensayo en seco y evaluación única (§4e, §4b)
DRY_RUNS_REL = "research/holdout/dry_runs.jsonl"     # registro de ensayos en seco (ruta fija, versionado)
SENS_KEYS = {"name", "modes", "matrix_variant", "provisional_weighting", "feature_policy", "models", "model_params",
             "baseline", "reference", "expected_signs", "holm_families", "nota"}
REQUIRED_EVAL = ("mejora_logloss", "mejora_ll_g", "cortes", "subperiodos_mismo_signo", "deteccion_frente_al_comparador")


def suite(cfg: HarnessConfig) -> list[HarnessConfig]:
    """La corrida principal y sus sensibilidades preregistradas (misma evaluación, mismos meses)."""
    out = [replace(cfg, sensitivities=())]
    for sd in cfg.sensitivities:
        sd = dict(sd)
        bad = set(sd) - SENS_KEYS
        if bad or "name" not in sd:
            raise ValueError(f"sensibilidad mal declarada ({sorted(bad)} / sin name): {sd}")
        nm = sd.pop("name")
        for k in ("modes", "models"):
            if k in sd:
                sd[k] = tuple(sd[k])
        out.append(replace(cfg, name=f"{cfg.name}__{nm}", sensitivities=(), **sd))
    return out


def prereg_config_sha(cfg_file) -> str:
    """Hash del ensayo en seco: bytes de la configuración + código de src/models + dependencias de la etiqueta PIT."""
    from src.models import trials
    code = trials.code_sha()
    h = hashlib.sha256(Path(cfg_file).read_bytes())
    h.update(code["src_models"].encode())
    h.update(code["pit_labels_deps"].encode())
    return h.hexdigest()


def _cuts(cfg: HarnessConfig) -> list[pd.Timestamp]:
    """Cortes (primer mes de cada bloque de reentreno) cuyo bloque toca la ventana de evaluación."""
    ms = pd.date_range(_month(cfg.test_start), _month(cfg.test_end), freq="MS")
    w0, w1 = cfg.window
    return [ms[b] for b in range(0, len(ms), cfg.refit_every)
            if ((ms[b:b + cfg.refit_every] >= w0) & (ms[b:b + cfg.refit_every] <= w1)).any()]


def holdout_feature_availability(data: PITData, variant: str, cols: list, end: pd.Timestamp) -> pd.DataFrame:
    """Disponibilidad (SOLO notna, nunca valores) de las variables pedidas en la matriz congelada entre 2005-01 y `end`.
    No toca la etiqueta. Queda en el registro de accesos (descriptivo de variables ≥ 2005: pit_base.md §4c)."""
    name = f"{data.mode}_{variant}" if variant else data.mode
    ver = getattr(data, "pit_version", PIT_VERSION)
    path = P.out_dir() / f"pit_us_v{ver}_{name}.parquet"
    if P.file_sha(path) != MATRIX_SHA256_BY_VERSION[ver][name]:
        raise RuntimeError(f"{path.name} no coincide con la matriz congelada")
    if not cols:
        return pd.DataFrame(index=pd.DatetimeIndex([]))
    X = pd.read_parquet(path, columns=["decision_date", *cols],
                        filters=[("decision_date", ">=", HOLDOUT_START.to_datetime64()),
                                 ("decision_date", "<=", (end + pd.offsets.MonthEnd(0)).to_datetime64())])
    m = X[cols].notna()
    m.index = X["decision_date"].dt.to_period("M").dt.to_timestamp()
    log_access({"mode": "dry_run", "granted": True, "event": "disponibilidad_variables (solo notna, sin etiqueta)",
                "matrix": path.name, "cols": cols, "hasta": f"{end:%Y-%m}"})
    return m


def holdout_eligibility(model: B.Model, data: PITData, cfg: HarnessConfig, variant: str) -> list[dict]:
    """Elegibilidad ANALÍTICA en la ventana bloqueada sin abrir nada (M2-2): en el PRIMER corte que toca la ventana
    (los recuentos crecen con el corte para una ventana de inicio fijo), por eje:
    - meses de entrenamiento = meses ≤ 2004 con todas las variables (matriz de desarrollo) + meses 2005…corte − 6 con
      todas las variables (disponibilidad de la matriz, solo notna); con `excluir`, − 53 provisionales recalculados.
      Supuesto declarado: `weight > 0` después de 2004 (en la etiqueta solo vale 0 en 1950-54, el arranque);
    - recesiones NBER y cambios de G: COTAS INFERIORES con los datos ≤ 2004 (usrec y etiqueta oficial de desarrollo).
    """
    if not model.needs_training:
        return [{"modelo": model.name, "eje": "-", "elegible": True, "motivo": "no entrena"}]
    cuts = _cuts(cfg)
    if not cuts:
        return [{"modelo": model.name, "eje": "-", "elegible": False, "motivo": "ningún corte toca la ventana"}]
    m0 = cuts[0]
    last = _add(m0, -cfg.embargo_months)
    lab = data.vault.load()
    lab = lab[lab["weight"] > 0]
    specs = ({ax: list(model.axis_features.get(ax, ())) for ax in AXES} if isinstance(model, B.AxisModel)
             else {"4c": [] if not model.features or model.features == "principal" else list(model.features)})
    out = []
    for ax, feats in specs.items():
        _check_requested(model.name, feats, data, cfg)
        start = axis_window_start(feats, data) if feats else None
        start = start if start is not None else lab.index.min()
        dev = data.X.loc[(data.X.index >= start) & (data.X.index <= min(last, _add(HOLDOUT_START, -1))), feats]
        dev = dev[dev.index.isin(lab.index)]
        n = int(dev.notna().all(axis=1).sum()) if feats else len(dev)
        if last >= HOLDOUT_START:
            av = holdout_feature_availability(data, variant, feats, last)
            n += int(av.all(axis=1).sum()) if feats else len(pd.date_range(HOLDOUT_START, last, freq="MS"))
        if cfg.provisional_weighting == "excluir":
            n -= 53
        lb_end = min(last, _add(HOLDOUT_START, -1))
        n_rec = count_recessions(data.usrec, start, lb_end)
        Y = lab.loc[(lab.index >= start) & (lab.index <= lb_end), P_COLS].to_numpy(float)
        n_g = count_g_changes(Y)
        ok = _eligible(cfg, n, n_rec, n_g)
        out.append({"modelo": model.name, "eje": ax, "primer_corte": f"{m0:%Y-%m}", "ventana_desde": f"{start:%Y-%m}",
                    "n_train": n, "n_recesiones_cota": n_rec, "n_cambios_g_cota": n_g, "elegible": bool(ok),
                    "holgura_cambios_g": n_g >= 2 * cfg.min_train_g_changes})
    return out


def _check_eval_config(cfg: HarnessConfig, pid: str | None, entry: dict | None) -> list[str]:
    err = []
    if cfg.phase != "holdout_evaluation":
        err.append(f"phase = {cfg.phase} (debe ser holdout_evaluation)")
    if pid and cfg.prereg_id != pid:
        err.append(f"prereg_id {cfg.prereg_id} ≠ {pid}")
    if not str(cfg.prereg_id or "").startswith(V.EVAL_PREFIX):
        err.append(f"prereg_id {cfg.prereg_id!r} no es un id de evaluación ({V.EVAL_PREFIX}…)")
    if cfg.allow_shrink:
        err.append("allow_shrink: true (en la evaluación única la ventana NO se puede reducir)")
    if not cfg.eval_window:
        err.append("falta eval_window (ventana de evaluación explícita)")
    meta = json.loads(R.out_path().with_suffix(".meta.json").read_text())
    fop = _add(pd.Timestamp(meta["last"]), -(meta["provisional_months"] - 1))
    w0, w1 = cfg.window
    if w0 < HOLDOUT_START:
        err.append(f"eval_window empieza en {w0:%Y-%m}, antes del periodo bloqueado")
    if w1 >= fop or _month(cfg.test_end) >= fop:
        err.append(f"eval_window/test_end llegan a provisionales oficiales (desde {fop:%Y-%m})")
    if _month(cfg.test_start) > w0:
        err.append("test_start posterior al inicio de eval_window")
    for a, b in cfg.subperiods:
        if _month(a) < w0 or _month(b) > w1:
            err.append(f"subperiodo {a}→{b} fuera de eval_window")
    if not cfg.dry_run_window or _month(cfg.dry_run_window[1]) >= HOLDOUT_START:
        err.append("falta dry_run_window (≤ 2004) para el ensayo en seco")
    if not cfg.principal or cfg.principal not in cfg.models:
        err.append(f"principal {cfg.principal!r} no está entre los modelos")
    unknown = [m for m in cfg.models if m not in model_registry()]
    if unknown:
        err.append(f"modelos no registrados: {unknown}")
    for m, exp in (cfg.expected_signs or {}).items():
        if m not in cfg.models:
            err.append(f"expected_signs: {m} no está entre los modelos")
        for k in exp:
            if ":" not in k or k.split(":")[0] not in AXES:
                err.append(f"expected_signs[{m}]: clave {k!r} (formato '<G|I>:<variable>')")
    for f in cfg.holm_families:
        try:
            mem = family_members(f)
        except (KeyError, TypeError) as e:
            err.append(f"familia de Holm {f.get('nombre')} mal formada ({e!r})")
            continue
        miss = sorted({y for x in mem for y in (x["modelo"], x["comparador"]) if y not in cfg.models})
        if not mem or miss or f.get("p", "frac_rep_le0") not in HOLM_P or "nombre" not in f:
            err.append(f"familia de Holm {f.get('nombre')}: sin miembros / modelos {miss} / p {f.get('p')}")
        bad = [x["metrica"] for x in mem if x["metrica"] not in METRICS]
        if bad:
            err.append(f"familia de Holm {f.get('nombre')}: métrica desconocida {bad}")
    if entry is not None:
        known = {h.get("id") for h in V._hypotheses()}
        miss = [x for x in entry.get("incluye") or [] if x not in known]
        if miss:
            err.append(f"incluye ids inexistentes: {miss}")
    return err


def dry_run_prereg(prereg_id: str | None = None, cfg_path: str | None = None, record: bool = True,
                   _datas: dict | None = None) -> dict:
    """ENSAYO EN SECO de una evaluación única (M2-2): ejecuta TODA la configuración del preregistro sin abrir la caja ni
    gastar nada.
    1. Comprobaciones estáticas (`_check_eval_config`): fase, id, ventana explícita dentro de los meses puntuables del
       bloqueado, `allow_shrink: false`, subperiodos, modelos registrados, signos y familias de Holm bien formadas.
    2. Elegibilidad ANALÍTICA de cada modelo, eje, modo y sensibilidad en el primer corte de la ventana bloqueada
       (`holdout_eligibility`; variables solo por disponibilidad, recesiones y cambios de G como cotas ≤ 2004).
    3. ENSAYO: la misma configuración (modelos, modos, sensibilidades, pesos, métricas, signos, Holm) en desarrollo sobre
       `dry_run_window` (≤ 2004), subperiodos = sus dos mitades, `allow_shrink: false`; comprueba que el informe trae
       todo lo que pide el preregistro.
    Con `record`, añade una línea a `research/holdout/dry_runs.jsonl` (ruta fija) con el hash de configuración + código:
    `evaluate_holdout` exige una línea `ok` con ese hash, commiteada, y repite el ensayo antes de gastar nada.
    Acepta un borrador (solo `cfg_path`) o un id registrado (`prereg_id`, lee su `config_arnes`)."""
    entry = None
    if cfg_path is None:
        entry = V.eval_entry(prereg_id)
        cfg_path = entry.get("config_arnes")
        if not cfg_path:
            raise HoldoutLocked(f"{prereg_id} no declara `config_arnes`")
    cfg_file = Path(cfg_path) if Path(cfg_path).is_absolute() else REPO / cfg_path
    cfg = HarnessConfig.from_yaml(cfg_file)
    pid = prereg_id or cfg.prereg_id
    errors = _check_eval_config(cfg, pid, entry)
    elig, runs_, avisos = [], [], []
    datas = dict(_datas or {})
    vault = None

    def get(mode, variant, policy):
        nonlocal vault
        k = (mode, variant, policy)
        if k not in datas:
            vault = vault or LabelVault()
            datas[k] = PITData(mode, variant, "development", None, policy, vault=vault, pit_version=cfg.pit_version)
        return datas[k]

    try:
        sts = suite(cfg)
    except ValueError as e:
        errors.append(str(e))
        sts = []
    if not errors:
        for sc in sts:
            for mode in sc.modes:
                var = sc.matrix_variant if mode == "vintage" else ""
                data = get(mode, var, sc.feature_policy)
                for model in build_models(sc):
                    try:
                        rows = holdout_eligibility(model, data, sc, var)
                    except (KeyError, ValueError) as e:
                        errors.append(f"{sc.name}/{mode}/{model.name}: {e}")
                        continue
                    for r in rows:
                        elig.append({"corrida": sc.name, "modo": mode, **r})
                        if not r["elegible"]:
                            errors.append(f"{sc.name}/{mode}/{model.name}/{r['eje']}: NO elegible en el primer corte "
                                          f"de la ventana ({r})")
        d0, d1 = _month(cfg.dry_run_window[0]), _month(cfg.dry_run_window[1])
        mid = _add(d0, (len(pd.date_range(d0, d1, freq="MS")) // 2) - 1)
        for sc in sts:
            dev = replace(sc, phase="development", prereg_id=None, name=f"{sc.name}__ensayo",
                          test_start=f"{min(_month(sc.test_start), d0):%Y-%m}", test_end=f"{d1:%Y-%m}",
                          eval_window=(f"{d0:%Y-%m}", f"{d1:%Y-%m}"), allow_shrink=False,
                          subperiods=((f"{d0:%Y-%m}", f"{mid:%Y-%m}"), (f"{_add(mid, 1):%Y-%m}", f"{d1:%Y-%m}")),
                          nota=f"ENSAYO EN SECO de {pid} (≤ 2004; no abre nada). {sc.nota}".strip())
            try:
                res = run(dev, datas={m: get(m, sc.matrix_variant if m == "vintage" else "", sc.feature_policy)
                                      for m in sc.modes}, record=record)
            except Exception as e:  # noqa: BLE001 — el ensayo informa de cualquier fallo
                errors.append(f"{dev.name}: {type(e).__name__}: {e}")
                continue
            rep = res["report"]
            avisos += [f"{dev.name}: {a}" for a in rep.get("avisos", [])]
            runs_.append({"name": dev.name, "results_sha256": res["results_sha256"],
                          "run_id": res.get("entry", {}).get("run_id")})
            if rep["ventana_evaluacion"]["reducida"]:
                errors.append(f"{dev.name}: ventana reducida")
            for mode in sc.modes:
                if sc.principal and sc.principal != sc.baseline and sc.principal in sc.models:
                    c = rep["frente_al_baseline"].get(f"{mode}/{sc.principal}")
                    miss = [k for k in REQUIRED_EVAL if c is None or c.get(k) is None]
                    if miss:
                        errors.append(f"{dev.name}/{mode}: el informe no calcula {miss} para {sc.principal}")
                for m in sc.expected_signs or {}:
                    sg = rep.get("signos_coeficientes", {}).get(f"{mode}/{m}")
                    if not sg or "error" in sg or any("error" in v for v in sg["signos"].values()):
                        errors.append(f"{dev.name}/{mode}: signos de {m} no calculables ({sg and sg.get('error')})")
            for f in sc.holm_families:
                if f.get("modo", "vintage") in sc.modes and f["nombre"] not in rep.get("holm_familias", {}):
                    errors.append(f"{dev.name}: familia de Holm {f['nombre']} sin calcular")
    out = {"prereg_id": pid, "config": str(cfg_path), "config_sha": prereg_config_sha(cfg_file),
           "ok": not errors, "errores": errors, "avisos": avisos, "elegibilidad": elig, "ensayos": runs_,
           "ventana_evaluacion": [f"{x:%Y-%m}" for x in cfg.window], "dry_run_window": list(cfg.dry_run_window or [])}
    if record:
        from src.models import trials
        V._append(V.REPO / DRY_RUNS_REL, {"ts": pd.Timestamp.now().isoformat(timespec="seconds"),
                                          "git_head": V._git("rev-parse", "HEAD"), "code": trials.code_sha(), **out})
    return out


validate_prereg = dry_run_prereg


def _preflight(prereg_id: str, cfg_path: str) -> dict:
    """Antes de gastar nada: un ensayo en seco `ok` con el MISMO hash (configuración + código) anotado en
    `research/holdout/dry_runs.jsonl` (y commiteado: lo exige el árbol limpio de la caja), y el ensayo REPETIDO ahora
    (sin tocar ningún registro versionado). Cualquier fallo → HoldoutLocked y no se consume nada."""
    sha = prereg_config_sha(REPO / cfg_path)
    f = V.REPO / DRY_RUNS_REL
    recs = [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []
    if not any(r.get("ok") and r.get("config_sha") == sha and r.get("prereg_id") == prereg_id for r in recs):
        raise HoldoutLocked(f"{prereg_id}: no hay ensayo en seco aprobado para esta configuración y este código "
                            f"(hash {sha[:12]}): evaluate_holdout('{prereg_id}', dry_run=True), commitea "
                            f"{DRY_RUNS_REL} y vuelve")
    V._QUIET["on"] = True
    try:
        dr = dry_run_prereg(prereg_id, record=False)
    finally:
        V._QUIET["on"] = False
    if not dr["ok"]:
        raise HoldoutLocked(f"{prereg_id}: el ensayo en seco FALLA; no se gasta nada: {dr['errores'][:5]}")
    return dr


def _commit_results(prereg_id: str, results: dict) -> None:
    """Tras la evaluación: commitea y empuja los resultados (rutas fijas). Si falla, solo avisa: el consumo ya está
    anclado y los resultados quedan en disco."""
    paths = ["research/trials/harness_runs.jsonl", "research/trial_log.md", "research/trials/label_access.jsonl"]
    for r in results.values():
        d = Path(r.get("entry", {}).get("artefactos", ""))
        paths += [str((d / x).relative_to(V.REPO)) for x in ("report.json", "predictions.csv") if (d / x).exists()]
    try:
        V._git_strict("add", "-f", "--", *[x for x in paths if (V.REPO / x).exists()])
        V._git_strict("commit", "-q", "-m", f"Holdout evaluation results: {prereg_id}")
        V._git_strict("push", "-q", V.REMOTE_NAME, f"HEAD:refs/heads/{V._branch()}")
    except HoldoutLocked as e:
        warnings.warn(f"resultados de {prereg_id} NO commiteados/empujados ({e}); súbelos a mano", stacklevel=2)


def evaluate_holdout(prereg_id: str, dry_run: bool = False) -> dict:
    """ÚNICO punto de entrada de la evaluación del periodo bloqueado.
    - `dry_run=True`: ensayo en seco (`dry_run_prereg`), registrado; no abre ni gasta nada.
    - Si no: lee la configuración que fija el preregistro (`config_arnes`, commiteada), exige y REPITE el ensayo en seco
      (`_preflight`; si falla, se niega ANTES de gastar), abre la caja fuerte (que comprueba todo, toma el cerrojo,
      CONSUME el preregistro y lo ancla en el remoto antes de leer), construye él mismo los datos y ejecuta la corrida
      principal y sus sensibilidades, siempre registradas en rutas FIJAS (N7). No acepta datos, modelos ni registros
      externos. Al terminar, la caja se cierra y los resultados se commitean y empujan."""
    if dry_run:
        return dry_run_prereg(prereg_id=prereg_id, record=True)
    entry = V.eval_entry(prereg_id)
    cfg_path = entry.get("config_arnes")
    if not cfg_path:
        raise HoldoutLocked(f"{prereg_id} no declara `config_arnes` (configuración congelada de la corrida)")
    cfg = HarnessConfig.from_yaml(REPO / cfg_path)
    if cfg.phase != "holdout_evaluation" or cfg.prereg_id != prereg_id:
        raise HoldoutLocked(f"{cfg_path}: fase/prereg_id no coinciden con {prereg_id}")
    if _EVAL["vault"] is not None:
        raise HoldoutLocked("ya hay una evaluación única en curso en este proceso")
    _preflight(prereg_id, cfg_path)
    vault = LabelVault(mode="holdout_evaluation", prereg_id=prereg_id, window=cfg.window)   # consume y ancla
    _EVAL["vault"] = vault
    V._FIXED["on"] = True
    try:
        results, cache = {}, {}
        for sc in suite(cfg):
            datas = {}
            for m in sc.modes:
                k = (m, sc.matrix_variant if m == "vintage" else "", sc.feature_policy)
                if k not in cache:
                    cache[k] = PITData(m, k[1], cfg.phase, prereg_id, sc.feature_policy, vault=vault,
                                       pit_version=cfg.pit_version)
                datas[m] = cache[k]
            results[sc.name] = _run(sc, datas, None, record=True)
        _commit_results(prereg_id, results)
        return {"principal": results[cfg.name], "sensibilidades": {k: v for k, v in results.items() if k != cfg.name}}
    finally:
        vault.close()
        _EVAL["vault"] = None
        V._FIXED["on"] = False


def main() -> None:
    ap = argparse.ArgumentParser(description="Arnés walk-forward (desarrollo: solo ≤ 2004)")
    ap.add_argument("--config", help="configuración de desarrollo")
    ap.add_argument("--official", action="store_true",
                    help="corrida oficial: exige src/, config/ y tests/ commiteados (git_dirty = false)")
    ap.add_argument("--dry-run", metavar="CONFIG_O_ID",
                    help="ensayo en seco de una evaluación única (configuración de un borrador o id P-EVAL-…)")
    a = ap.parse_args()
    if a.dry_run:
        arg = a.dry_run
        dr = dry_run_prereg(prereg_id=arg) if arg.startswith(V.EVAL_PREFIX) else dry_run_prereg(cfg_path=arg)
        print(json.dumps({k: dr[k] for k in ("prereg_id", "config", "config_sha", "ok", "errores", "avisos",
                                             "ensayos")}, indent=1, ensure_ascii=False, default=str))
        print(pd.DataFrame(dr["elegibilidad"]).to_string())
        raise SystemExit(0 if dr["ok"] else 1)
    if a.official:
        dirty = V._git_strict("status", "--porcelain", "--", "src", "config", "tests").strip()
        if dirty:
            raise SystemExit(f"--official con código sin commitear:\n{dirty}")
    cfg = HarnessConfig.from_yaml(a.config)
    res = run(cfg)
    rep = res["report"]
    print(json.dumps({"muestra": rep["muestra"], "modelos": rep["modelos"], "avisos": rep["avisos"],
                      "persistencia_muestra_completa": rep.get("persistencia_muestra_completa"),
                      "run_id": res["entry"]["run_id"], "results_sha256": res["results_sha256"],
                      "results_sha256_r10": res["results_sha256_r10"]}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
