"""Tests de la etiqueta de régimen EE. UU. (docs/models/label_spec.md)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.labels import regime_us as R

PCOLS = [f"p_{q}" for q in R.QUADRANTS]


@pytest.fixture(scope="module")
def built():
    df, info = R.build()
    return df, info


def test_columns(built):
    df, _ = built
    expected = ["date", "G", "I", "p_g_high", "p_i_high", *PCOLS, "label_hard", "max_prob", "frontera",
                "provisional", "tendencia_truncada", "cobertura_g", "fuente_i", "usrec", "weight"]
    assert list(df.columns) == expected
    assert df["date"].min() == pd.Timestamp("1950-01-01")
    assert df["date"].is_monotonic_increasing and df["date"].is_unique
    assert (df["date"].diff().dropna().dt.days.between(28, 31)).all()  # mensual sin huecos


def test_probabilities_valid(built):
    df, _ = built
    p = df[PCOLS + ["p_g_high", "p_i_high"]]
    assert p.notna().all().all()
    assert ((p >= 0) & (p <= 1)).all().all()
    assert np.allclose(df[PCOLS].sum(axis=1), 1.0, atol=1e-12)


def test_no_future_dates(built):
    df, _ = built
    today = pd.Timestamp.today().normalize()
    assert df["date"].max() < today.replace(day=1)  # el mes en curso no puede tener etiqueta
    assert df[["G", "I"]].notna().all().all()


def test_hard_label_is_argmax(built):
    df, _ = built
    arg = df[PCOLS].to_numpy().argmax(axis=1)
    assert (df["label_hard"].to_numpy() == np.array(R.QUADRANTS)[arg]).all()
    assert np.allclose(df["max_prob"], df[PCOLS].max(axis=1))
    assert (df["frontera"] == (df["max_prob"] < R.PARAMS.frontier)).all()


def test_provisional_last_24(built):
    df, _ = built
    n = R.PARAMS.provisional_months
    assert df["provisional"].sum() == n
    assert df["provisional"].iloc[-n:].all() and not df["provisional"].iloc[:-n].any()


def test_truncated_flags(built):
    df, _ = built
    t = df.set_index("date")["tendencia_truncada"]
    assert t.loc["1950":"1954"].all() and not t.loc["1955":"1990"].any() and t.iloc[-60:].all()


def test_coverage_and_sources(built):
    df, _ = built
    assert (df["cobertura_g"] >= R.PARAMS.min_growth_ind).all()
    assert (df.set_index("date").loc[:"1958-12", "cobertura_g"] == 2).all()
    assert set(df["fuente_i"]) <= {"pce_core", "cpi_core_adj", "headline"}


def test_weights(built):
    df, _ = built
    w = df.set_index("date")["weight"]
    assert set(w.unique()) <= {0.0, 1.0}
    assert (w.loc[:"1954-12"] == 0).all() and (w.loc["1955-01":] == 1).all()


def test_quadrant_names(built):
    df, _ = built
    assert "p_slowdown" not in df.columns and "p_low_growth_disinfl" in df.columns
    assert set(df["label_hard"]) <= set(R.QUADRANTS)
    assert R.ALIASES["p_slowdown"] == "p_low_growth_disinfl"


def test_centered_windows():
    """G e I en t usan datos de t−4…t+4 / t−3…t+3. Un salto de nivel entre los meses s−1 y s
    (centrado en s−0,5) mueve el ritmo en s−4…s+3 y la inflación en s−3…s+2: simétrico."""
    idx = pd.date_range("2000-01-01", periods=40, freq="MS")
    lv = pd.Series(100.0, index=idx)
    lv.iloc[20:] = 110.0
    g = R.pace(lv)
    moved = g[g.abs() > 1e-9].index
    assert moved.min() == idx[20 - 4] and moved.max() == idx[20 + 3]
    i = R.ann_change(lv)
    moved_i = i[i.abs() > 1e-9].index
    assert moved_i.min() == idx[20 - 3] and moved_i.max() == idx[20 + 2]


def test_scales(built):
    _, info = built
    m = info["meta"]
    for k in ("s_G", "s_I"):
        assert m[k] >= R.PARAMS.scale_floor
    assert m["s_G"] == pytest.approx(0.40) and m["s_I"] == pytest.approx(0.31)


def test_usage_metadata(built):
    _, info = built
    m = info["meta"]
    assert m["embargo_months"] == 6 and m["usage"]["embargo_months"] == 6
    assert "provisional" in m["usage"]["score_and_train_mask"] and "weight" in m["usage"]["score_and_train_mask"]
    assert len(m["code"]["sha256_code"]) == 64


def test_provisional_covers_revision_study():
    """`provisional` debe cubrir los meses que el estudio de revisión considera inmaduros:
    month T−k es inmaduro si k < k*; la etiqueta termina en T−lag, así que hacen falta k* − lag filas."""
    import json

    f = R.out_dir() / "revision_study.json"
    if not f.exists():
        pytest.skip("falta revision_study.json: ejecutar python -m src.labels.revision_study")
    st = json.loads(f.read_text())
    need = st["k_final"] - st["lag"]
    assert R.PARAMS.provisional_months >= need
    assert R.PARAMS.provisional_months == st["provisional_months"]
    assert R.PARAMS.provisional_months % 6 == 0


def test_reproducible(built):
    df1, _ = built
    df2, _ = R.build()
    assert R.content_hash(df1) == R.content_hash(df2)
