"""Tests de la base PIT v0.4 (candidata hasta el 23-oct; congelada, tag pit-v0.4) (docs/models/pit_base.md §9, v0.4): las 4 derivadas de riesgo de giro del
Estratega (revisión de M1 §5) y los mismos controles que la v0.3, aplicados a las columnas nuevas.

(s) superconjunto: las 58 columnas de la v0.3, sus linajes y los baselines son idénticos bit a bit en la v0.4;
(v) valores: las 4 derivadas recalculadas a mano (numpy, sin src.features) desde las columnas base de la matriz;
(p) PIT: perturbar el futuro de las entradas no cambia ninguna derivada en t (causalidad), y en la matriz oficial las
    derivadas en t solo dependen de filas ≤ t (truncamiento de la rejilla);
(c) placebo con las columnas nuevas: sin fuga pasa; con fuga fuerte y con la etiqueta de t−4 falla;
(d) señal plantada: en datos sintéticos con calendario conocido, las derivadas reproducen exactamente la transformación
    de la primera publicación de t−1; con una fuga de calendario (dato de t en t) se detecta.
Periodo bloqueado: lo que mira la etiqueta (c) solo usa meses ≤ 2004-12.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from pit_helpers import persistence_onehot, synthetic_warehouse
from src.features import pit as P
from src.features import placebo as PL
from src.features.calendar import CalEntry
from src.labels import regime_us as R

HOLDOUT = pd.Timestamp(R.PARAMS.holdout_start)
NEW = {"curve_min12": ("rolling_min", ["curve_10y3m"], "+"), "baa_gap10y": ("gap_median_prev", ["baa_spread"], "-"),
       "baa_d6m": ("diff6", ["baa_spread"], "-"), "sahm_d3m": ("diff3", ["unrate_sahm"], "-")}
MATS = ("vintage", "latest_truncated", "vintage_filadelfia_prudente")


def _read(version: str, name: str) -> pd.DataFrame:
    return pd.read_parquet(P.out_dir() / f"pit_us_v{version}_{name}.parquet").set_index("decision_date")


@pytest.fixture(scope="module")
def mats():
    return {n: _read("0.4", n) for n in MATS}


# ------------------------------------------------------------------ (s) superconjunto de la v0.3
@pytest.mark.parametrize("name", MATS)
def test_s_v03_columns_identical(name, mats):
    old, new = _read("0.3", name), mats[name]
    assert set(new.columns) - set(old.columns) == set(NEW)
    pd.testing.assert_frame_equal(new[old.columns], old)
    lo = pd.read_parquet(P.out_dir() / f"pit_us_v0.3_{name}_lineage.parquet")
    ln = pd.read_parquet(P.out_dir() / f"pit_us_v0.4_{name}_lineage.parquet")
    ln = ln[ln["column"].isin(old.columns)].reset_index(drop=True)
    pd.testing.assert_frame_equal(ln, lo)


@pytest.mark.parametrize("mode", P.MODES)
def test_s_baselines_bit_identical(mode):
    od = P.out_dir()
    assert P.file_sha(od / f"baseline_persistence_v0.4_{mode}.parquet") == \
        P.file_sha(od / f"baseline_persistence_v0.3_{mode}.parquet")


def test_s_meta_registers_candidate():
    """El meta se escribió con la v0.4 candidata (23-oct, 10:58) y no se regenera al congelar (B-5, paso 2 opcional,
    igual que la v0.3): registra los hashes de CANDIDATE, que son los mismos que los de FROZEN["0.4"]."""
    meta = json.loads((P.out_dir() / "pit_us_v0.4.meta.json").read_text())
    assert meta["instantanea_entradas"]["estado"].startswith("candidata")
    assert meta["instantanea_entradas"]["candidata"] == P.CANDIDATE["0.4"] and meta["instantanea_entradas"]["frozen"] is None
    assert {k: v for k, v in P.FROZEN["0.4"].items() if k != "veredicto"} == P.CANDIDATE["0.4"]
    for name in MATS:
        assert P.file_sha(P.out_dir() / f"pit_us_v0.4_{name}.parquet") == meta["files"][f"pit_us_v0.4_{name}.parquet"]["sha256_file"]


# ------------------------------------------------------------------ lista blanca
def test_whitelist_v04_entries():
    wl = P.load_whitelist()
    specs = {v["nombre"]: v for v in wl["variables"]}
    eff = P.effective_principal_desde(wl)
    assert str(wl["version"]) == "0.4"
    assert len(P.public_columns(wl)) == 62
    for name, (fn, ins, sign) in NEW.items():
        v = specs[name]
        assert (v["tipo"], v["funcion"], v["entradas"], v["estado"]) == ("derivada", fn, ins, "principal"), name
        assert v["signo_esperado"].startswith(sign) and v.get("mecanismo"), name
        assert not v.get("principal_desde") and eff[name] is None and not v.get("desde"), name
    assert specs["curve_min12"]["n"] == 12
    R.assert_no_forbidden(list(NEW))


# ------------------------------------------------------------------ (v) valores a mano
def _hand(base: np.ndarray, fn: str) -> np.ndarray:
    n = len(base)
    out = np.full(n, np.nan)
    for i in range(n):
        if fn == "rolling_min":
            w = base[i - 11:i + 1] if i >= 11 else np.array([np.nan])
            out[i] = np.nan if np.isnan(w).any() else w.min()
        elif fn in ("diff3", "diff6"):
            k = int(fn[-1])
            out[i] = base[i] - base[i - k] if i >= k else np.nan
        elif fn == "gap_median_prev":
            w = base[max(0, i - 120):i]
            w = w[~np.isnan(w)]
            out[i] = base[i] - np.median(w) if i >= 1 and len(w) >= 108 else np.nan
    return out


@pytest.mark.parametrize("name", MATS)
def test_v_new_columns_by_hand(name, mats):
    X = mats[name]
    for col, (fn, ins, _) in NEW.items():
        want = _hand(X[ins[0]].to_numpy(float), fn)
        got = X[col].to_numpy(float)
        np.testing.assert_array_equal(np.isnan(got), np.isnan(want), err_msg=col)
        ok = ~np.isnan(want)
        np.testing.assert_allclose(got[ok], want[ok], rtol=1e-12, atol=1e-12, err_msg=col)


def test_v_first_dates(mats):
    X = mats["vintage"]
    first = {c: f"{X[c].first_valid_index():%Y-%m}" for c in NEW}
    assert first == {"curve_min12": "1954-04", "baa_gap10y": "1962-05", "baa_d6m": "1953-11", "sahm_d3m": "1950-04"}


# ------------------------------------------------------------------ (p) PIT: causalidad
@pytest.mark.parametrize("col", sorted(NEW))
def test_p_derived_are_causal(col):
    """Cambiar los valores de las entradas DESPUÉS de t no cambia la derivada en t (ni en ningún mes ≤ t)."""
    fn, _, _ = NEW[col]
    rng = np.random.default_rng(3)
    idx = pd.date_range("1950-01-31", periods=400, freq="ME")
    x = pd.Series(rng.normal(size=len(idx)), index=idx)
    x[rng.random(len(idx)) < 0.03] = np.nan
    wl = {"tendencia_meses": 120}
    spec = {"n": 12}
    base = P.DERIVED[fn](pd.DataFrame({"a": x}), ["a"], wl, spec)
    for t in (130, 200, 333):
        y = x.copy()
        y.iloc[t + 1:] = rng.normal(5, 3, len(y) - t - 1)
        alt = P.DERIVED[fn](pd.DataFrame({"a": y}), ["a"], wl, spec)
        pd.testing.assert_series_equal(alt.iloc[:t + 1], base.iloc[:t + 1], check_names=False)


@pytest.mark.parametrize("cut", ["1979-10-31", "2004-12-30"])
def test_p_truncated_grid_same_row(mats, cut):
    """En la matriz oficial: recalcular las derivadas solo con las filas de la rejilla ≤ t da el mismo valor en t."""
    t = pd.Timestamp(cut)
    for name in P.MODES:
        X = mats[name]
        Xt = X[X.index <= t]
        for col, (fn, ins, _) in NEW.items():
            v = P.DERIVED[fn](Xt[[ins[0]]], ins, {"tendencia_meses": 120}, {"n": 12}).iloc[-1]
            np.testing.assert_allclose(v, X.loc[t, col], rtol=1e-12, err_msg=f"{col} {name}")


# ------------------------------------------------------------------ (c) placebo con las columnas nuevas
PLACEBO_FEATURES = ["curve_10y3m", "payems_3m_ann", "indpro_3m_ann", "unrate_sahm", "headline_cpi_6m_ann",
                    "ppi_yoy", "baa_spread", "ff_d12m", *NEW]


def _training_label() -> pd.DataFrame:
    lab = pd.read_parquet(R.out_path(), filters=[("date", "<", HOLDOUT.to_datetime64())])
    lab = lab[(lab["weight"] > 0) & ~lab["provisional"] & (lab["date"] < HOLDOUT)]
    assert lab["date"].max() < HOLDOUT   # periodo bloqueado: nunca
    return lab.set_index("date")


def _leak(ys, rng):
    return np.eye(4)[ys][:, 1:] + rng.normal(0, 0.5, (len(ys), 3))


def test_c_placebo_v04(mats):
    X = mats["vintage"]
    X = X[X.index < HOLDOUT]
    X = X.set_index(X.index.to_period("M").to_timestamp())[PLACEBO_FEATURES]
    lab = _training_label()
    common = lab.index.intersection(X.dropna().index)
    common = common[common >= pd.Timestamp("1963-01-01")]
    y = np.array([R.QUADRANTS.index(q) for q in lab.loc[common, "label_hard"]])
    F = X.loc[common].to_numpy(float)
    honest = PL.placebo_skills(F, y, common, n_perm=8)
    leaky = PL.placebo_skills(F, y, common, n_perm=8, leak=_leak)
    t4 = PL.placebo_skills(F, y, common, n_perm=8, leak=lambda ys, rng: persistence_onehot(ys, lag=4))
    assert PL.placebo_check(honest), honest
    assert not PL.placebo_check(leaky) and (leaky > PL.PLACEBO_TOL).all(), leaky
    # control a priori t−4 (fuga de calendario de 1 mes): la media falla (> 0,02) y, PAREADO con la misma permutación
    # (el control no consume el generador: mismas permutaciones que `honest`), gana en las 8. Con 12 columnas el sesgo
    # del L2 es mayor (honest ≈ −0,24) y la lectura robusta es la pareada (en la v0.3, con 8 columnas, bastaba la media)
    assert not PL.placebo_check(t4) and t4.mean() > PL.PLACEBO_TOL, t4
    assert ((t4 - honest) > PL.PLACEBO_TOL).all(), t4 - honest


# ------------------------------------------------------------------ (d) señal plantada en las derivadas
def _synthetic(leak: bool):
    rng = np.random.default_rng(7)
    months = pd.date_range("1950-01-01", "2004-12-01", freq="MS")
    x = np.cumsum(rng.normal(0, 0.3, len(months)))
    first = x + rng.normal(0, 0.3, len(months))
    pe = months + pd.offsets.MonthEnd(0)
    rows = [pd.DataFrame({"date": months, "value": x, "series_id": "SYN_SIGNAL", "source": "syn"}),
            pd.DataFrame({"date": months, "value": first, "series_id": "SYN_SIGNAL", "source": "syn",
                          "realtime_start": pe + pd.Timedelta(days=20)}),
            pd.DataFrame({"date": months, "value": x, "series_id": "SYN_SIGNAL", "source": "syn",
                          "realtime_start": pe + pd.Timedelta(days=110)})]
    cat = pd.DataFrame({"series_id": ["SYN_SIGNAL"], "source": "syn", "units": "x", "pit_role": "observed"})
    mem = synthetic_warehouse(pd.concat(rows, ignore_index=True), cat, "2005-03-01")
    one = lambda d: ((pd.Timestamp("1900-01-01"), d),)  # noqa: E731
    if leak:
        cal = {"SYN_SIGNAL": CalEntry("SYN_SIGNAL", "M", "fin_periodo", one(-10), (), (), True, "fuga", "")}
    else:
        cal = {"SYN_SIGNAL": CalEntry("SYN_SIGNAL", "M", "fin_periodo", one(20), ("SYN_SIGNAL",), ("SYN_SIGNAL",),
                                      False, "sintética", "")}
    wl = {"tendencia_meses": 120, "variables": [
        {"nombre": "syn", "tipo": "serie", "series": ["SYN_SIGNAL"], "transformacion": {"fn": "level"},
         "modo": "latest_truncated" if leak else "vintage"},
        *[{"nombre": f"syn_{c}", "tipo": "derivada", "funcion": fn, "entradas": ["syn"], "n": 12}
          for c, (fn, _, _) in NEW.items()]]}
    grid = P.decision_grid(today=pd.Timestamp("2005-01-15"))
    grid = grid[grid["month"] <= months.max()]
    X, lin, _ = P.build_matrix(mem, "vintage", grid, wl=wl, cal=cal, forbidden=[])
    mem.close()
    return X.set_index(X.index.to_period("M").to_timestamp()), months, x, first


@pytest.mark.parametrize("leak", [False, True])
def test_d_planted_derived(leak):
    X, months, x, first = _synthetic(leak)
    # sin fuga, la columna base en t es la PRIMERA publicación de t − 1; con la fuga, el dato de t
    src = pd.Series(x if leak else first, index=months).shift(0 if leak else 1).reindex(X.index)
    honest = pd.Series(first, index=months).shift(1).reindex(X.index)
    for c, (fn, _, _) in NEW.items():
        got = X[f"syn_{c}"].to_numpy(float)
        want = _hand(src.to_numpy(float), fn)
        ok = ~np.isnan(want) & ~np.isnan(got)
        assert ok.sum() > 400, c
        np.testing.assert_allclose(got[ok], want[ok], rtol=1e-9, atol=1e-12, err_msg=c)
        ref = _hand(honest.to_numpy(float), fn)
        diff = np.nanmax(np.abs(got[ok] - ref[ok]))
        assert (diff > 0.05) if leak else (diff < 1e-9), (c, diff)     # la fuga de calendario se ve en la derivada
