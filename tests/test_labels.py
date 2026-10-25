"""Tests de la etiqueta de régimen EE. UU. (docs/models/label_spec.md)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.labels import regime_us as R
from tests.real_data import requires_real_data

PCOLS = [f"p_{q}" for q in R.QUADRANTS]


@pytest.fixture(scope="module")
def built():
    df, info = R.build()
    return df, info


@requires_real_data
def test_columns(built):
    df, _ = built
    expected = ["date", "G", "I", "p_g_high", "p_i_high", *PCOLS, "label_hard", "max_prob", "frontera",
                "provisional", "tendencia_truncada", "cobertura_g", "fuente_i", "usrec", "weight"]
    assert list(df.columns) == expected
    assert df["date"].min() == pd.Timestamp("1950-01-01")
    assert df["date"].is_monotonic_increasing and df["date"].is_unique
    assert (df["date"].diff().dropna().dt.days.between(28, 31)).all()  # mensual sin huecos


@requires_real_data
def test_probabilities_valid(built):
    df, _ = built
    p = df[PCOLS + ["p_g_high", "p_i_high"]]
    assert p.notna().all().all()
    assert ((p >= 0) & (p <= 1)).all().all()
    assert np.allclose(df[PCOLS].sum(axis=1), 1.0, atol=1e-12)


@requires_real_data
def test_no_future_dates(built):
    df, _ = built
    today = pd.Timestamp.today().normalize()
    assert df["date"].max() < today.replace(day=1)  # el mes en curso no puede tener etiqueta
    assert df[["G", "I"]].notna().all().all()


@requires_real_data
def test_hard_label_is_argmax(built):
    df, _ = built
    arg = df[PCOLS].to_numpy().argmax(axis=1)
    assert (df["label_hard"].to_numpy() == np.array(R.QUADRANTS)[arg]).all()
    assert np.allclose(df["max_prob"], df[PCOLS].max(axis=1))
    assert (df["frontera"] == (df["max_prob"] < R.PARAMS.frontier)).all()


@requires_real_data
def test_provisional_last_n(built):
    df, _ = built
    n = R.PARAMS.provisional_months
    assert df["provisional"].sum() == n
    assert df["provisional"].iloc[-n:].all() and not df["provisional"].iloc[:-n].any()


@requires_real_data
def test_truncated_flags(built):
    df, _ = built
    t = df.set_index("date")["tendencia_truncada"]
    assert t.loc["1950":"1954"].all() and not t.loc["1955":"1990"].any() and t.iloc[-60:].all()


@requires_real_data
def test_coverage_and_sources(built):
    df, _ = built
    assert (df["cobertura_g"] >= R.PARAMS.min_growth_ind).all()
    assert (df.set_index("date").loc[:"1958-12", "cobertura_g"] == 2).all()
    assert set(df["fuente_i"]) <= {"pce_core", "cpi_core_adj", "headline"}


@requires_real_data
def test_weights(built):
    df, _ = built
    w = df.set_index("date")["weight"]
    assert set(w.unique()) <= {0.0, 1.0}
    assert (w.loc[:"1954-12"] == 0).all() and (w.loc["1955-01":] == 1).all()


@requires_real_data
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


@requires_real_data
def test_scales(built):
    _, info = built
    m = info["meta"]
    for k in ("s_G", "s_I"):
        assert m[k] >= R.PARAMS.scale_floor
    assert m["s_G"] == pytest.approx(0.40) and m["s_I"] == pytest.approx(0.31)


@requires_real_data
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


@requires_real_data
def test_reproducible(built):
    df1, _ = built
    df2, _ = R.build()
    assert R.content_hash(df1) == R.content_hash(df2)


# ------------------------------------------------------------------ versión congelada (Validador, A-2)
FROZEN = R.FROZEN.get(R.PARAMS.version)
frozen_only = pytest.mark.skipif(FROZEN is None, reason="versión candidata: aún no está en FROZEN")


@requires_real_data
@frozen_only
def test_snapshot_matches_frozen():
    """La instantánea de entradas es la congelada (SHA en git, no solo en el meta.json)."""
    _, info = R.read_snapshot()
    assert info["sha256_file"] == FROZEN["snapshot_sha256_file"]
    assert info["sha256_content"] == FROZEN["snapshot_sha256_content"]


@requires_real_data
def test_read_snapshot_rejects_tampered(tmp_path, monkeypatch):
    """`read_snapshot` falla si la instantánea no es la congelada."""
    if FROZEN is None:
        pytest.skip("versión candidata")
    df = pd.read_parquet(R.snapshot_path())
    df.loc[df.index[0], "value"] = df["value"].iloc[0] + 1.0
    fake = tmp_path / "inputs.parquet"
    df.to_parquet(fake, index=False)
    monkeypatch.setattr(R, "snapshot_path", lambda p=R.PARAMS: fake)
    with pytest.raises(RuntimeError, match="no coincide"):
        R.read_snapshot()


@requires_real_data
@frozen_only
def test_label_hash_is_frozen(built):
    """La etiqueta reconstruida desde la instantánea es bit a bit la congelada."""
    df, _ = built
    assert R.content_hash(df) == FROZEN["label_sha256_content"]


@requires_real_data
@frozen_only
def test_official_file_is_frozen():
    """El parquet oficial en disco no ha sido reescrito."""
    df = pd.read_parquet(R.out_path())
    assert R.content_hash(df) == FROZEN["label_sha256_content"]


@requires_real_data
def test_mature_rows_vs_previous_version(built):
    """Frente a la versión anterior, las filas maduras solo cambian en la ventana declarada (§13).
    Vale también para una candidata, que debe declarar su ventana en `R.CANDIDATE_CHANGES`. Si una
    versión nueva reescribe filas maduras fuera de lo declarado, este test falla."""
    decl = FROZEN["mature_changes_vs"] if FROZEN else getattr(R, "CANDIDATE_CHANGES", None)
    assert decl, "una versión candidata debe declarar CANDIDATE_CHANGES = (versión anterior, desde, hasta)"
    prev, lo, hi = decl
    path = R.out_dir() / f"regime_us_v{prev}.parquet"
    if not path.exists():
        pytest.skip(f"falta {path}")
    old = pd.read_parquet(path).set_index("date")
    new = built[0].set_index("date")
    mature = new.index[~new["provisional"]].intersection(old.index[~old["provisional"]])
    outside = mature[(mature < pd.Timestamp(lo)) | (mature > pd.Timestamp(hi))]
    cols = [c for c in new.columns if c in old.columns]
    a, b = new.loc[outside, cols], old.loc[outside, cols]
    num = a.select_dtypes("number").columns
    assert np.allclose(a[num].astype(float), b[num].astype(float), rtol=0, atol=1e-12, equal_nan=True)
    assert a.drop(columns=num).equals(b.drop(columns=num))


# ------------------------------------------------------------------ todas las versiones congeladas (P-2)
def test_frozen_registry_not_emptied():
    """FROZEN no se puede vaciar ni perder versiones sin que falle algo."""
    assert {"1.1"} <= set(R.FROZEN)


@requires_real_data
@pytest.mark.parametrize("v", sorted(R.FROZEN))
def test_every_frozen_version_on_disk(v):
    """Cada versión congelada sigue intacta en disco (etiqueta e instantánea), aunque ya no sea la actual."""
    lab = R.out_dir() / f"regime_us_v{v}.parquet"
    snap = R.out_dir() / "inputs" / f"regime_us_v{v}_inputs.parquet"
    ref = R.FROZEN[v]
    assert R.content_hash(pd.read_parquet(lab)) == ref["label_sha256_content"]
    assert R.file_sha(snap) == ref["snapshot_sha256_file"]


def test_frozen_snapshot_cannot_be_rewritten():
    if not R.FROZEN:
        pytest.skip("sin versiones congeladas")
    v = sorted(R.FROZEN)[-1]
    p = R.Params(version=v) if "version" in R.Params.__dataclass_fields__ else R.PARAMS
    with pytest.raises(SystemExit):
        R.write_snapshot({}, p, force=True)


@pytest.mark.parametrize("col", ["lag5_G", "d_usrec", "L5.usrec", "yoy_GDPPOT", ("lag1", "usrec"),
                                 ("G", "lag5"), "x_p_expansion_y"])
def test_forbidden_rejects_prefix_and_tuple(col):
    with pytest.raises(AssertionError):
        R.assert_no_forbidden([col], extra=["GDPPOT"])


@pytest.mark.parametrize("col", ["usrec", "USREC_lag1", "G_lag5", "p_expansion_lag5", "label_hard",
                                 "label_anything", "i.ma3", "GDPPOT_yoy", "max_prob-12m"])
def test_forbidden_rejects(col):
    with pytest.raises(AssertionError):
        R.assert_no_forbidden([col], extra=["GDPPOT"])


@pytest.mark.parametrize("col", ["INDPRO", "PAYEMS_yoy", "fed_ebp", "cboe_vx_slope", "GS10", "ice_hy_oas"])
def test_forbidden_allows(col):
    R.assert_no_forbidden([col], extra=["GDPPOT"])


def test_forbidden_uses_official_meta_by_default():
    """Sin `extra`, la lista de series forecast/lookahead sale del meta.json oficial."""
    if not R.out_path().with_suffix(".meta.json").exists():
        pytest.skip("falta el meta.json oficial")
    with pytest.raises(AssertionError):
        R.assert_no_forbidden(["GDPPOT_gap"])
