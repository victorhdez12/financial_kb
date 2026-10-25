"""M2 `m2_struct_g`: nowcast ESTRUCTURAL del eje G (docs/models/m2_structural_spec.md v1.2, H-M2-001).

Factor dinámico de 1 factor (statsmodels `MLEModel`, `struct_factor.py`) sobre las tasas mensuales PIT de INDPRO,
PAYEMS, W875RX1 y CMRMTSPL frente a su mediana de 120 meses, `claims_4w_yoy` (carga en f_m − f_{m−12}) y
`philly_neworders`, con el ragged edge real; Ĝ = el código de la etiqueta (`R.growth_components`/`R.growth_axis`)
sobre los niveles conocidos en la fecha de decisión extendidos con las tasas previstas hasta t+4;
σ̂² = V_conj + V_rev (v1.3: error conjunto medido sin etiqueta; V_filtro y V_tend, diagnóstico); el arnés (v2.3, §5c) convierte (Ĝ, σ̂) en P(G alto) = Φ(Ĝ/√(σ̂² + s_G²)). Eje I = M0.
M2 NO usa la etiqueta para nada (el objetivo continuo que pasa el arnés solo se guarda para diagnósticos).

Datos que pide al arnés v2.4 (nunca abre ficheros): `info["pit_levels"](fecha)` (niveles conocidos en la fecha de
decisión, `PITLabeler.levels_at`, y si cada serie viene de una vintage), `info["features_history"]` (filas de la
matriz con `claims_4w_yoy`/`philly_neworders` hasta el mes del corte o de la fila), `info["decision_calendar"]`
(fechas de decisión de cada mes ≤ el corte) y `info["data_key"]` (identidad de los datos para la caché compartida
con M3). Todo ≤ la fecha de decisión de la fila que se predice; los parámetros, solo con datos ≤ el corte.

Puntos que la spec deja abiertos y aquí se resuelven de forma PROVISIONAL (lista en `IMPLEMENTATION_CHOICES`, para la
revisión del usuario antes de la primera corrida con la etiqueta; no se ha visto ningún dato de la etiqueta).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.labels import regime_us as R
from src.models import base as B
from src.models import regime_components as C
from src.models import struct_factor as F
from src.models.vault import HoldoutLocked

S = C.STRUCT
COINC = S.coincident                                   # INDPRO, PAYEMS, W875RX1, CMRMTSPL
CLAIMS, PHILLY = S.extra_features                      # claims_4w_yoy, philly_neworders
DATA_START = pd.Timestamp(S.data_start + "-01")        # 1968-06
PHILLY_NAN_BEFORE = pd.Timestamp("1990-07-01")         # S-PIT-001 (si se dispara)
EXPECTED_SIGN = {**{c: 1.0 for c in COINC}, CLAIMS: -1.0, PHILLY: 1.0}
OFFSETS = C.LABEL_PACE_OFFSETS                         # t−3 … t+4
HORIZON = S.horizon_after                              # 4
REPO = Path(__file__).resolve().parents[2]
REVISION_TABLE = REPO / "research" / "trials" / "m2" / "revision_var.json"

IMPLEMENTATION_CHOICES = (
    "arranque: componente principal del panel balanceado CENTRADO (media de columna), matriz de covarianza de las x "
    "estandarizadas; cargas = pendiente MCO con constante de cada x sobre la componente (varianza 1, ddof 0); φ y ρ por "
    "MCO sin constante; residuo = x − (constante + pendiente·regresor); si el φ del arranque no es estacionario se "
    "multiplica por 0,95 hasta que lo sea (se anota)",
    "arranque: si el tramo balanceado de las 6 series y el de las 4 coincidentes tienen < 60 meses (en los primeros "
    "cortes, por el τʳ de CMRMTSPL desde 1974-08), se usa el de las 4 coincidentes igualmente (lectura literal)",
    "inicialización del filtro: estacionaria (verosimilitud exacta); gradiente: el de statsmodels por defecto (paso "
    "complejo); L-BFGS-B con pgtol = gtol = 1e-6 y factr por defecto",
    "sin convergencia: se conserva la VERSIÓN anterior completa (parámetros + d_i + medias/desv. de peticiones y "
    "Filadelfia, que están en sus unidades); V_tend se mide igualmente en la reestimación",
    "τʳ de los meses futuros = τʳ del mes siguiente a la última observación (mediana de los 120 últimos meses "
    "observados, ≥ 90 presentes)",
    "una serie sin τʳ o sin d_i en el tramo (CMRMTSPL antes de 1974-08) no se extiende: su ritmo en t queda NaN y G "
    "se compone con las demás (mínimo 2, como la etiqueta)",
    "V_filtro: covarianza de d_i·(λ_i f + u_i), sin el ε de regularización (1e-4)",
    "Ĝ^rt de un mes anterior a 1968-06 (inicio de la ventana de datos del factor): NaN (M3: ese mes del filtro solo "
    "predice; la emisión se estima con los meses finitos)",
    "V_conj (v1.3): niveles pseudo-tiempo-real con from_vintage = falso (la revisión va en V_rev); meses con Ĝ^ps no "
    "finito excluidos",
    "tabla v(edad): fechas de decisión de la matriz PIT ≤ 2004-12 en las que la serie entra desde una vintage; "
    "todos los meses observados de esa vintage ≤ 2004-12 (el tramo ≥ 13 incluye todos los meses antiguos)",
)


def _m(d) -> pd.Timestamp:
    return pd.Timestamp(d).to_period("M").to_timestamp()


def _add(m: pd.Timestamp, k: int) -> pd.Timestamp:
    return m + pd.DateOffset(months=k)


def _mdiff(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return (a.year - b.year) * 12 + (a.month - b.month)


def age_bucket(age: int) -> str:
    a = max(int(age), 1)
    return str(a) if a <= 6 else ("7-12" if a <= 12 else ">=13")


def rates(level: pd.Series) -> pd.Series:
    lv = R._cal(level)
    return 100 * np.log(lv).diff()


def trend_r(r: pd.Series) -> pd.Series:
    """τʳ_m = mediana de r en m−120 … m−1 con ≥ 90 presentes (si no, NaN)."""
    return r.shift(1).rolling(S.trend_months, min_periods=S.trend_min_obs).median()


def _tau_future(r: pd.Series, last: pd.Timestamp) -> float:
    w = r.loc[:last].iloc[-S.trend_months:]
    return float(w.median()) if w.notna().sum() >= S.trend_min_obs else float("nan")


def label_G(levels: dict) -> pd.DataFrame:
    """G con el código CONGELADO de la etiqueta (R.growth_components + R.growth_axis) y las σ_i."""
    gc = R.growth_components({k: v for k, v in levels.items() if k in COINC})
    ga = R.growth_axis(gc["comp"])
    ga.attrs["sigma"] = {k: c["sigma"] for k, c in gc["comp"].items()}
    ga.attrs["z"] = pd.DataFrame({k: c["z"] for k, c in gc["comp"].items()})
    return ga


def extend_level(lv: pd.Series, rhat: pd.Series) -> pd.Series:
    """Niveles conocidos extendidos con las tasas previstas (spec §4, paso 2): L̂_m = L_último·exp(Σ r̂/100)."""
    lv = R._cal(lv)
    if not len(rhat):
        return lv
    last = lv.last_valid_index()
    Lhat = float(lv[last]) * np.exp(np.cumsum(rhat.to_numpy(float)) / 100.0)
    return pd.concat([lv[lv.index <= last], pd.Series(Lhat, index=rhat.index)])


def compose_G(levels: dict, rhat: dict, mt: pd.Timestamp) -> float:
    """Ĝ_t (spec §4, pasos 1-3): niveles conocidos extendidos con r̂ y el código de la etiqueta."""
    ext = {k: extend_level(v, rhat.get(k, pd.Series(dtype=float))) for k, v in levels.items() if k in COINC}
    return float(label_G(ext)["G"].get(mt, np.nan))


# ------------------------------------------------------------------ configuración de una variante
@dataclass(frozen=True)
class StructCfg:
    coinc_only: bool = False          # sensibilidad m2_struct_g_coinc
    ar_order: int = 2                 # sensibilidad m2_struct_g_ar1 → 1
    philly_pre1990_nan: bool = False  # S-PIT-001 (marca heredada, N-6)
    rev: str = "principal"            # "principal" (tabla fija, no PIT) | "none" (norev) | "pit" (revpit)

    @property
    def cols(self) -> tuple[str, ...]:
        return COINC if self.coinc_only else (*COINC, CLAIMS, PHILLY)

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple("coinc" if c in COINC else ("claims" if c == CLAIMS else "philly") for c in self.cols)

    def factor_key(self) -> tuple:
        """Lo que determina el factor (la tabla de revisión solo afecta a σ̂)."""
        return (self.coinc_only, self.ar_order, self.philly_pre1990_nan)


@dataclass
class FactorVersion:
    T: pd.Timestamp                    # mes de la reestimación
    params: np.ndarray
    d: dict                            # desviación de r − τʳ (coincidentes)
    mean: dict                         # peticiones/Filadelfia
    sd: dict
    converged: bool
    kept_previous: bool
    fit_info: dict
    v_tend: float = float("nan")
    v_conj: float = float("nan")      # v1.3: σ̂² = V_conj + V_rev
    n_conj: int = 0
    start_notes: list = field(default_factory=list)
    from_T: pd.Timestamp | None = None  # mes de la versión de la que vienen los parámetros (si se conservaron)

    @property
    def id(self) -> str:
        return f"{self.T:%Y-%m}"


# ------------------------------------------------------------------ paneles y estandarización
def dev_frame(levels: dict, feats: pd.DataFrame | None, mt: pd.Timestamp, cfg: StructCfg) -> tuple[pd.DataFrame, dict]:
    """Panel SIN estandarizar de los meses DATA_START … mt + 4: r − τʳ de cada coincidente (NaN tras su última
    observación) y las variables de la matriz de su propio mes (NaN tras mt). Todo con lo conocido en mt."""
    months = pd.date_range(DATA_START, _add(mt, HORIZON), freq="MS")
    out, meta = {}, {}
    for sid in COINC:
        lv = levels.get(sid)
        if lv is None or lv.dropna().empty:
            out[sid], meta[sid] = pd.Series(np.nan, index=months), None
            continue
        lv = R._cal(lv)
        lv = lv[lv.index <= mt]
        r = 100 * np.log(lv).diff()
        last = lv.last_valid_index()
        out[sid] = (r - trend_r(r)).reindex(months)
        meta[sid] = {"last": last, "tau_f": _tau_future(r, last), "level": lv}
    for c in cfg.cols[len(COINC):]:
        s = (feats[c] if feats is not None and c in feats else pd.Series(dtype=float)).reindex(months).astype(float)
        s[s.index > mt] = np.nan
        if c == PHILLY and cfg.philly_pre1990_nan:
            s[s.index < PHILLY_NAN_BEFORE] = np.nan
        out[c] = s
    return pd.DataFrame(out, index=months)[list(cfg.cols)], meta


def standardize(dev: pd.DataFrame, v: FactorVersion, cfg: StructCfg) -> pd.DataFrame:
    X = dev.copy()
    for c in cfg.cols:
        X[c] = dev[c] / v.d[c] if c in COINC else (dev[c] - v.mean[c]) / v.sd[c]
    return X


def _longest_run(mask: pd.Series) -> pd.Index:
    best, cur = [], []
    for m, ok in mask.items():
        if ok:
            cur.append(m)
            if len(cur) > len(best):
                best = list(cur)
        else:
            cur = []
    return pd.Index(best)


def _ols(y, x, const=True):
    y, x = np.asarray(y, float), np.asarray(x, float)
    A = np.column_stack([np.ones(len(x)), x]) if const else x.reshape(len(x), -1)
    b = np.linalg.lstsq(A, y, rcond=None)[0]
    return b, y - A @ b


def _stationary_ar(phi: np.ndarray) -> bool:
    if len(phi) == 1:
        return abs(phi[0]) < 1
    roots = np.roots(np.r_[1.0, -np.asarray(phi)])
    return bool(np.all(np.abs(roots) < 1))


def start_values(X: pd.DataFrame, cfg: StructCfg) -> tuple[np.ndarray, list]:
    """Arranque determinista FIJO (spec §3, v1.1 B-2; detalles provisionales en IMPLEMENTATION_CHOICES)."""
    notes = []
    cols = list(cfg.cols)
    run = _longest_run(X[cols].notna().all(axis=1))
    panel_cols = cols
    if len(run) < S.balanced_min_months:
        panel_cols = list(COINC)
        run = _longest_run(X[panel_cols].notna().all(axis=1))
        notes.append(f"panel de las 4 coincidentes ({len(run)} meses)")
    if len(run) < 3:
        raise ValueError(f"M2: panel balanceado vacío ({len(run)} meses)")
    Z = X.loc[run, panel_cols].to_numpy(float)
    Zc = Z - Z.mean(axis=0)
    w, V = np.linalg.eigh(Zc.T @ Zc / len(Zc))
    pc = Zc @ V[:, -1]
    pc = pc / pc.std()
    if np.cov(X.loc[run, "PAYEMS"], pc, ddof=0)[0, 1] < 0:
        pc = -pc
    pc = pd.Series(pc, index=run)
    lam, resid = {}, {}
    for c in cols:
        if c not in panel_cols:
            lam[c] = 0.1 * EXPECTED_SIGN[c]
            y = X.loc[run, c]
            ok = y.notna()
            resid[c] = (y[ok] - lam[c] * pc[ok]).to_numpy()
            continue
        reg = pc - pc.shift(12) if c == CLAIMS else pc
        ok = reg.notna() & X.loc[run, c].notna()
        b, e = _ols(X.loc[run, c][ok], reg[ok])
        lam[c], resid[c] = float(b[1]), e
    p = cfg.ar_order
    f = pc.to_numpy()
    phi = _ols(f[p:], np.column_stack([f[p - k - 1:len(f) - k - 1] for k in range(p)]), const=False)[0]
    k = 0
    while not _stationary_ar(phi):
        phi, k = phi * 0.95, k + 1
    if k:
        notes.append(f"φ del arranque reescalado ×0,95^{k}")
    rho, q = [], []
    for c in cols:
        e = np.asarray(resid[c], float)
        if len(e) < 3:
            rho.append(0.0)
            q.append(max(float(np.nanvar(X[c])) if X[c].notna().any() else 1.0, 1e-3))
            continue
        r_ = float(np.clip(_ols(e[1:], e[:-1], const=False)[0][0], -0.9, 0.9))
        rho.append(r_)
        q.append(max(float(np.var(e[1:] - r_ * e[:-1])), 1e-3))
    return np.r_[[lam[c] for c in cols], phi, rho, q], notes


# ------------------------------------------------------------------ V_tend y tabla de revisión
def v_tend(levels: dict, mT: pd.Timestamp) -> float:
    """V_tend (spec §4): media de e_s² con e_s = G_s(niveles de T truncados en s+4) − G_s(niveles de T), s de 1965-01
    a T − 65, las dos con el código de la etiqueta."""
    lv = {k: R._cal(levels[k]) for k in COINC if k in levels and levels[k] is not None and len(levels[k].dropna())}
    full = label_G(lv)["G"]
    s0, s1 = pd.Timestamp(S.trend_err_start + "-01"), _add(mT, -S.trend_err_lag)
    errs = []
    for s in pd.date_range(s0, s1, freq="MS"):
        cut = _add(s, HORIZON)
        g = label_G({k: v[v.index <= cut] for k, v in lv.items()})["G"]
        if s in g.index and s in full.index and np.isfinite(g[s]) and np.isfinite(full[s]):
            errs.append(g[s] - full[s])
    return float(np.mean(np.square(errs))) if errs else 0.0


def v_conj(cfg: StructCfg, v: "FactorVersion", L: dict, feats: pd.DataFrame | None, T: pd.Timestamp) -> tuple:
    """V_conj (spec v1.3 §4): varianza del error CONJUNTO medida en pseudo-tiempo-real con los niveles de T y la
    versión de T: para s de 1968-06 a T − 65, niveles de T de cada coincidente truncados en s − ℓ_i (ℓ_i = borde
    desigual del corte T), variables ≤ s; e_s = Ĝ^ps_s − G_s(niveles de T); V_conj = media de e_s² (finitos)."""
    lv = {k: R._cal(x) for k, x in L["levels"].items() if k in COINC and x is not None and len(x.dropna())}
    full = label_G(lv)["G"]
    ell = {k: _mdiff(T, x.last_valid_index()) for k, x in lv.items()}
    errs = []
    for s_ in pd.date_range(DATA_START, _add(T, -S.trend_err_lag), freq="MS"):
        Lp = {"levels": {k: x[x.index <= _add(s_, -ell[k])] for k, x in lv.items()},
              "from_vintage": {k: False for k in lv}}
        Lp["levels"] = {k: x for k, x in Lp["levels"].items() if len(x.dropna())}
        fs = feats[feats.index <= s_] if feats is not None else None
        g = ghat(cfg, v, Lp, fs, s_)["G"]
        if np.isfinite(g) and s_ in full.index and np.isfinite(full[s_]):
            errs.append(g - full[s_])
    return (float(np.mean(np.square(errs))) if errs else float("nan")), len(errs)


def revision_errors(vint_levels: dict, ref_rates: pd.Series, s_month: pd.Timestamp, max_month=None) -> pd.DataFrame:
    """Errores r(vintage de s) − r(referencia) por edad = s − m, para los meses observados en la vintage de s."""
    r = rates(vint_levels)
    r = r[r.index < s_month]
    if max_month is not None:
        r = r[r.index <= max_month]
    e = (r - ref_rates.reindex(r.index)).dropna()
    ages = np.array([_mdiff(s_month, m) for m in e.index])
    return pd.DataFrame({"age": ages, "err": e.to_numpy()})


def summarize_rev(errs: dict, var_r: dict, min_pairs: int | None = None) -> dict:
    """v_i(edad) = error cuadrático medio por tramo; ρ̄ = media de v/Var(r) de INDPRO y PAYEMS. Con `min_pairs`
    (sensibilidad PIT), un tramo con < min_pairs pares toma el valor del tramo más joven con ≥ min_pairs."""
    v, n = {}, {}
    for sid, df in errs.items():
        b = df["age"].map(age_bucket)
        v[sid] = {k: float(np.mean(np.square(df.loc[b == k, "err"]))) if (b == k).any() else float("nan")
                  for k in S.rev_age_buckets}
        n[sid] = {k: int((b == k).sum()) for k in S.rev_age_buckets}
        if min_pairs is not None:
            ok = [k for k in S.rev_age_buckets if n[sid][k] >= min_pairs]
            for k in S.rev_age_buckets:
                if n[sid][k] < min_pairs:
                    v[sid][k] = v[sid][ok[0]] if ok else float("nan")
    srcs = [s for s in ("INDPRO", "PAYEMS") if s in v and var_r.get(s)]
    def _rho(k):
        x = [v[s][k] / var_r[s] for s in srcs if np.isfinite(v[s][k])]
        return float(np.mean(x)) if x else float("nan")
    rho = {k: _rho(k) for k in S.rev_age_buckets}
    return {"edades": list(S.rev_age_buckets), "v": v, "n_pares": n, "var_r": var_r, "rho_bar": rho}


def rev_var(table: dict | None, sid: str, age: int) -> float:
    if not table:
        return 0.0
    k = age_bucket(age)
    if sid in table["v"]:
        x = table["v"][sid].get(k, float("nan"))
    else:
        x = table["rho_bar"].get(k, float("nan")) * table["var_r"].get(sid, float("nan"))
    return float(x) if np.isfinite(x) else 0.0


def load_revision_table(path: Path = REVISION_TABLE) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"M2: falta la tabla v(edad) {path} (spec §4: se fija antes de la etiqueta)")
    return json.loads(path.read_text())


def build_revision_table(labeler, decision: pd.Series, end: str = "2004-12") -> dict:
    """Tabla v(edad) PRINCIPAL (spec §4; declarada NO PIT): vintages ALFRED de INDPRO y PAYEMS de la instantánea
    congelada de la etiqueta, fechas de decisión y meses observados ≤ `end`; error = r(vintage de la fecha) − r(última
    vintage); Var(r_i) en la última vintage 1968-06 → 2004-12 (ddof 0). Sin etiqueta."""
    endm = _m(end)
    a, b = (pd.Timestamp(x + "-01") for x in S.rev_var_sample)
    var_r = {}
    for sid in COINC:
        r = rates(labeler.levels[sid])
        var_r[sid] = float(r[(r.index >= a) & (r.index <= b)].dropna().var(ddof=0))
    errs = {}
    for sid in ("INDPRO", "PAYEMS"):
        ref = rates(labeler.levels[sid])
        rows = []
        for mth, dt in decision.items():
            if mth > endm or not labeler.from_vintage(dt).get(sid):
                continue
            lv = labeler.levels_at(dt)[sid]
            rows.append(revision_errors(lv, ref, _m(dt), endm))
        errs[sid] = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame({"age": [], "err": []})
    out = summarize_rev(errs, var_r)
    out.update({"fin": end, "muestra_var_r": list(S.rev_var_sample), "pit": False,
                "definicion": "m2_structural_spec.md v1.2 §4 (V_rev; declarada NO PIT)",
                "elecciones": [IMPLEMENTATION_CHOICES[-1]]})
    return out


def ghat(cfg: StructCfg, v: FactorVersion, L: dict, feats: pd.DataFrame | None, mt: pd.Timestamp) -> dict:
    """Ĝ_t y V_filtro (spec §3-§4) con los niveles L = {"levels", "from_vintage"} y las variables `feats` (≤ mt)."""
    dev, meta = dev_frame(L["levels"], feats, mt, cfg)
    X = standardize(dev, v, cfg)
    mod, a, P = F.filter_last(X.to_numpy(float), cfg.kinds, v.params, ar_order=cfg.ar_order)
    lam = v.params[:len(cfg.cols)]
    win = [_add(mt, k) for k in OFFSETS]
    ext, rows, rowkeys = {}, [], []
    for j, sid in enumerate(COINC):
        mj = meta.get(sid)
        if mj is None:
            continue
        lv, last = mj["level"], mj["last"]
        ok = np.isfinite(mj["tau_f"]) and np.isfinite(v.d.get(sid, np.nan))
        if not ok:
            ext[sid] = lv
            continue
        if last < _add(mt, -4):
            raise ValueError(f"M2: {sid} con última observación {last:%Y-%m} anterior a t−3 ({mt:%Y-%m})")
        fut = pd.date_range(_add(last, 1), _add(mt, HORIZON), freq="MS")
        rhat = []
        for m in fut:
            lag = _mdiff(_add(mt, HORIZON), m)
            vec = np.zeros(len(a))
            vec[lag] = lam[j]
            vec[mod.u_index(j, lag)] += 1.0
            rhat.append(mj["tau_f"] + v.d[sid] * float(vec @ a))
            if m in win:
                rows.append(v.d[sid] * vec)
                rowkeys.append((sid, m))
        ext[sid] = extend_level(lv, pd.Series(rhat, index=fut))
    ga = label_G(ext)
    G = float(ga["G"].get(mt, np.nan))
    n = int(ga["cobertura_g"].get(mt, 0))
    z = ga.attrs["z"]
    incl = [s for s in z.columns if mt in z.index and np.isfinite(z.at[mt, s])]
    sig = ga.attrs["sigma"]

    def coef(sid, m):
        return float(C.pace_rate_coeffs(sig[sid], n)[OFFSETS.index(_mdiff(m, mt))])

    vf = 0.0
    if rows:
        A = np.array(rows)
        Sig = A @ P @ A.T
        c = np.array([coef(s, m) if s in incl else 0.0 for s, m in rowkeys])
        vf = float(c @ Sig @ c)
    rev_terms = [(sid, _mdiff(mt, m), coef(sid, m) ** 2) for sid in incl if L["from_vintage"].get(sid)
                 for m in win if m <= meta[sid]["last"]]
    out = {"G": G, "n": n, "V_filtro": max(vf, 0.0), "f": float(a[HORIZON]), "incluidas": incl,
           "rev_terms": rev_terms}
    return out


# ------------------------------------------------------------------ motor compartido (M2, sus sensibilidades y M3)
class FactorEngine:
    """Estimación del factor por versión (reestimación de un corte) y nowcasts por (versión, mes), cacheados. Las
    entradas llegan SIEMPRE por las funciones del arnés; la clave del motor incluye la identidad de los datos."""

    def __init__(self, cfg: StructCfg):
        self.cfg = cfg
        self.versions: dict[tuple, FactorVersion] = {}
        self.nowcasts: dict[tuple, dict] = {}
        self.levels: dict[pd.Timestamp, dict] = {}
        self.revpit: dict[tuple, dict] = {}

    # entradas ------------------------------------------------------------------
    @staticmethod
    def _check_bound(info: dict, date=None, month=None) -> None:
        """Cota de la llamada ANTES de mirar las cachés (una entrada cacheada por otra corrida o por un corte posterior
        no puede saltarse la barrera de fecha del arnés): fecha ≤ `pit_bound` y mes dentro de `decision_calendar`."""
        b = info.get("pit_bound")
        if date is not None and b is not None and pd.Timestamp(date) > pd.Timestamp(b):
            raise HoldoutLocked(f"M2/M3: niveles PIT pedidos en {pd.Timestamp(date):%Y-%m-%d}, posterior a la cota "
                                f"{pd.Timestamp(b):%Y-%m-%d}")
        if month is not None and pd.Timestamp(month) not in info["decision_calendar"].index:
            raise HoldoutLocked(f"M2/M3: mes {pd.Timestamp(month):%Y-%m} fuera del calendario de decisiones de la llamada")

    def levels_at(self, info: dict, date) -> dict:
        date = pd.Timestamp(date)
        self._check_bound(info, date=date)
        if date not in self.levels:
            self.levels[date] = info["pit_levels"](date)
        return self.levels[date]

    @staticmethod
    def feats_upto(info: dict, mt: pd.Timestamp) -> pd.DataFrame:
        fh = info["features_history"]
        return fh[fh.index <= mt]

    # versiones -----------------------------------------------------------------
    def version(self, T: pd.Timestamp, info: dict, prev: FactorVersion | None) -> FactorVersion:
        self._check_bound(info, month=T)
        key = (T, None if prev is None else (prev.id, prev.from_T))
        if key in self.versions:
            return self.versions[key]
        cfg = self.cfg
        dec = info["decision_calendar"][T]
        lv = self.levels_at(info, dec)["levels"]
        dev, _ = dev_frame(lv, self.feats_upto(info, T), T, cfg)
        seg = dev.loc[:T]
        d = {c: float(seg[c].dropna().std(ddof=0)) if seg[c].notna().sum() > 1 else float("nan") for c in COINC}
        mean = {c: float(seg[c].dropna().mean()) for c in cfg.cols[len(COINC):]}
        sd = {c: float(seg[c].dropna().std(ddof=0)) for c in cfg.cols[len(COINC):]}
        v0 = FactorVersion(T=T, params=np.array([]), d=d, mean=mean, sd=sd, converged=False, kept_previous=False,
                           fit_info={})
        X = standardize(seg, v0, cfg)
        X = X.loc[:, list(cfg.cols)]
        start, notes = start_values(X, cfg)
        params, conv, finfo = F.fit_ml(X.to_numpy(float), cfg.kinds, start, ar_order=cfg.ar_order,
                                       maxiter=S.maxiter, gtol=S.gtol)
        if params[list(cfg.cols).index("PAYEMS")] < 0:          # normalización λ_PAYEMS > 0 (f → −f)
            params = params.copy()
            params[:len(cfg.cols)] *= -1
        vt = v_tend(lv, T)
        if not conv and prev is not None:
            v = FactorVersion(T=T, params=prev.params, d=prev.d, mean=prev.mean, sd=prev.sd, converged=False,
                              kept_previous=True, fit_info=finfo, v_tend=vt, start_notes=notes,
                              from_T=prev.from_T or prev.T)
        else:
            v = FactorVersion(T=T, params=params, d=d, mean=mean, sd=sd, converged=conv, kept_previous=False,
                              fit_info=finfo, v_tend=vt, start_notes=notes)
        v.v_conj, v.n_conj = v_conj(cfg, v, self.levels_at(info, dec), self.feats_upto(info, T), T)
        self.versions[key] = v
        return v

    def revpit_table(self, v: FactorVersion, info: dict) -> dict | None:
        """Sensibilidad m2_struct_g_revpit (spec §4): tabla reestimada en T solo con vintages publicadas ≤ T."""
        if v.id in self.revpit:
            return self.revpit[v.id]
        T = v.T
        decT = info["decision_calendar"][T]
        LT = self.levels_at(info, decT)
        a = pd.Timestamp(S.rev_var_sample[0] + "-01")
        var_r = {}
        for sid in COINC:
            if sid in LT["levels"]:
                r = rates(LT["levels"][sid])
                var_r[sid] = float(r[(r.index >= a) & (r.index <= T)].dropna().var(ddof=0))
        errs = {}
        cal = info["decision_calendar"]
        for sid in ("INDPRO", "PAYEMS"):
            if not LT["from_vintage"].get(sid):
                continue
            ref = rates(LT["levels"][sid])
            rows = []
            for mth, dt in cal.items():
                if mth > _add(T, -S.rev_pit_min_lag):
                    continue
                L = self.levels_at(info, dt)
                if not L["from_vintage"].get(sid):
                    continue
                rows.append(revision_errors(L["levels"][sid], ref, _m(dt)))
            if rows:
                errs[sid] = pd.concat(rows, ignore_index=True)
        tab = summarize_rev(errs, var_r, min_pairs=S.rev_pit_min_pairs) if errs else None
        self.revpit[v.id] = tab
        return tab

    # nowcast -------------------------------------------------------------------
    def nowcast(self, v: FactorVersion, mt: pd.Timestamp, info: dict, table: dict | None = None) -> dict:
        """Ĝ, V_filtro y V_rev del mes mt con la versión v (datos conocidos en la fecha de decisión de mt)."""
        b = self.nowcast_base(v, mt, info)
        vr = float(sum(c2 * rev_var(table, sid, age) for sid, age, c2 in b["rev_terms"])) if table else 0.0
        return {**b, "V_rev": vr}

    def nowcast_base(self, v: FactorVersion, mt: pd.Timestamp, info: dict) -> dict:
        if mt >= DATA_START:
            self._check_bound(info, month=mt)
        key = (v.id, v.from_T, mt)
        if key in self.nowcasts:
            return self.nowcasts[key]
        if mt < DATA_START:      # antes de la ventana de datos del factor (1968-06): sin nowcast
            out = {"G": float("nan"), "n": 0, "V_filtro": float("nan"), "f": float("nan"), "incluidas": [],
                   "rev_terms": []}
            self.nowcasts[key] = out
            return out
        dec = info["decision_calendar"][mt]
        out = ghat(self.cfg, v, self.levels_at(info, dec), self.feats_upto(info, mt), mt)
        self.nowcasts[key] = out
        return out


_ENGINES: dict[tuple, FactorEngine] = {}


def engine_for(info: dict, cfg: StructCfg) -> FactorEngine:
    k = (info.get("data_key"), info.get("pit_mode"), cfg.factor_key())
    if k not in _ENGINES:
        _ENGINES[k] = FactorEngine(StructCfg(*cfg.factor_key(), rev="principal"))
    return _ENGINES[k]


def clear_engines() -> None:
    _ENGINES.clear()


def _check_info(info: dict) -> None:
    miss = [k for k in ("pit_levels", "features_history", "decision_calendar", "data_key", "pit_mode") if k not in info]
    if miss:
        raise RuntimeError(f"M2/M3 necesitan el arnés v2.4 (info sin {miss})")


# ------------------------------------------------------------------ modelos
class StructuralG(B.ContinuousAxisModel):
    """M2 `m2_struct_g` (spec v1.2). Eje G continuo; eje I = M0 (persistencia calibrada, eps 1e-3, L2 1,0)."""
    name = "m2_struct_g"
    continuous_axes = ("G",)
    axis_features = {"G": S.extra_features, "I": ()}
    uses_persistence = True
    uses_pit_levels = True
    m2_dependent = True

    def __init__(self, philly_pre1990_nan: bool = False, coinc_only: bool = False, ar_order: int = 2,
                 rev: str = "principal", name: str | None = None, rev_table: dict | None = None):
        if rev not in ("principal", "none", "pit"):
            raise ValueError(f"rev desconocido: {rev}")
        self.cfg = StructCfg(coinc_only=coinc_only, ar_order=ar_order, philly_pre1990_nan=bool(philly_pre1990_nan),
                             rev=rev)
        self.params = {"philly_pre1990_nan": bool(philly_pre1990_nan), "coinc_only": coinc_only,
                       "ar_order": ar_order, "rev": rev}
        if name:
            self.name = name
        self._table = rev_table
        self._v: FactorVersion | None = None
        self._m0 = B.CalibratedPersistence()
        self._hist: list[dict] = []

    # tabla de revisión -------------------------------------------------------
    def _rev_table(self, eng: FactorEngine, info: dict):
        if self.cfg.rev == "none" or info.get("pit_mode") != "vintage":
            return None
        if self.cfg.rev == "pit":
            return eng.revpit_table(self._v, info)
        if self._table is None:
            self._table = load_revision_table()
        return self._table

    def _ensure_version(self, info: dict) -> FactorEngine:
        _check_info(info)
        eng = engine_for(info, self.cfg)
        m0 = pd.Timestamp(info["refit_month"])
        if self._v is None or (m0.month == S.reestimate_month and m0 != self._v.T):
            self._v = eng.version(m0, info, self._v)
            self._hist.append({"T": f"{m0:%Y-%m}", "fit_converged": bool(self._v.converged),
                               "conserva_anterior": bool(self._v.kept_previous), **self._v.fit_info,
                               "v_tend": self._v.v_tend, "v_conj": self._v.v_conj,
                               "n_conj": self._v.n_conj, "arranque": list(self._v.start_notes)})
        return eng

    def nowcast(self, mt, info) -> dict:
        eng = engine_for(info, self.cfg)
        tab = self._rev_table(eng, info)
        nc = eng.nowcast(self._v, pd.Timestamp(mt), info, table=tab)
        return {**nc, "V_tend": self._v.v_tend, "V_conj": self._v.v_conj,
                "sd": float(np.sqrt(self._v.v_conj + nc["V_rev"]))}     # v1.3

    # interfaz del arnés --------------------------------------------------------
    def fit_axis_continuous(self, axis, X, g, t, w, info):
        self._ensure_version(info)

    def predict_axis_continuous(self, axis, X, info):
        _check_info(info)
        out = [self.nowcast(m, info) for m in X.index]
        return np.array([o["G"] for o in out]), np.array([o["sd"] for o in out])

    def fit_axis(self, axis, X, t, w, info):
        self._m0.fit_axis(axis, X, t, w, info)

    def predict_axis(self, axis, X, info):
        return self._m0.predict_axis(axis, X, info)

    def coefficients(self) -> dict:
        out = {f"I:{k[2:]}": v for k, v in self._m0.coefficients().items()}
        v = self._v
        if v is None:
            return out
        cols = list(self.cfg.cols)
        J, p = len(cols), self.cfg.ar_order
        out.update({f"G:lambda_{c}": float(v.params[i]) for i, c in enumerate(cols)})
        out.update({f"G:phi{i + 1}": float(v.params[J + i]) for i in range(p)})
        out.update({f"G:rho_{c}": float(v.params[J + p + i]) for i, c in enumerate(cols)})
        out.update({f"G:q_{c}": float(v.params[2 * J + p + i]) for i, c in enumerate(cols)})
        out.update({"G:v_tend": float(v.v_tend), "G:v_conj": float(v.v_conj),
                    "G:fit_converged": float(v.converged)})
        return out

    def diagnostics(self) -> dict:
        return {"reestimaciones": list(self._hist),
                "sin_convergencia": int(sum(not h["fit_converged"] for h in self._hist))}


class StructuralGPlatt(B.AxisModel):
    """Sensibilidad `m2_struct_g_platt` (spec §7): Λ(c + b·logit P) sobre la P de M2, L2 = 1 sobre b, eps 1e-3 (como
    M0). La P de cada mes de entrenamiento es la de M2 en tiempo real en su fecha de decisión con los parámetros
    vigentes en el corte (como la emisión de M3; elección provisional anotada)."""
    name = "m2_struct_g_platt"
    axis_features = {"G": S.extra_features, "I": ()}
    uses_persistence = True
    uses_pit_levels = True
    m2_dependent = True

    def __init__(self, philly_pre1990_nan: bool = False, eps: float = 1e-3, l2: float = 1.0):
        self.params = {"philly_pre1990_nan": bool(philly_pre1990_nan), "eps": eps, "l2": l2}
        self._m2 = StructuralG(philly_pre1990_nan=philly_pre1990_nan)
        self._m0 = B.CalibratedPersistence()
        self._b = None

    def _p(self, months, info):
        sc = info["axis_scale"][1]
        out = []
        for m in months:
            nc = self._m2.nowcast(m, info)
            out.append(float(norm.cdf(nc["G"] / np.sqrt(nc["sd"] ** 2 + sc ** 2))))
        return np.array(out)

    def fit_axis(self, axis, X, t, w, info):
        if axis == "I":
            return self._m0.fit_axis(axis, X, t, w, info)
        self._m2._ensure_version(info)
        p = self._p(X.index, info)
        ok = np.isfinite(p)                     # meses sin nowcast (antes de 1968-06) no entran
        z = B.logit(p[ok], self.params["eps"])[:, None]
        self._b = B.fit_binary_logit(z, np.asarray(t, float)[ok], np.asarray(w, float)[ok], self.params["l2"])

    def predict_axis(self, axis, X, info):
        if axis == "I":
            return self._m0.predict_axis(axis, X, info)
        z = B.logit(self._p(X.index, info), self.params["eps"])
        return 1 / (1 + np.exp(-(self._b[0] + self._b[1] * z)))

    def coefficients(self) -> dict:
        out = {f"I:{k[2:]}": v for k, v in self._m0.coefficients().items()}
        if self._b is not None:
            out.update({"G:platt_c": float(self._b[0]), "G:platt_b": float(self._b[1])})
        return out

    def diagnostics(self) -> dict:
        return self._m2.diagnostics()


def _variant(name, **kw):
    def make(philly_pre1990_nan: bool = False, **extra):
        return StructuralG(philly_pre1990_nan=philly_pre1990_nan, name=name, **{**kw, **extra})
    make.m2_dependent = True
    return make


REGISTRY = {
    "m2_struct_g": StructuralG,
    "m2_struct_g_norev": _variant("m2_struct_g_norev", rev="none"),
    "m2_struct_g_revpit": _variant("m2_struct_g_revpit", rev="pit"),
    "m2_struct_g_coinc": _variant("m2_struct_g_coinc", coinc_only=True),
    "m2_struct_g_ar1": _variant("m2_struct_g_ar1", ar_order=1),
    "m2_struct_g_platt": StructuralGPlatt,
}
