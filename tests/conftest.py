from __future__ import annotations

import json

import pytest

from src.labels import regime_us as R
from tests.real_data import LABEL_META


@pytest.fixture(scope="module")
def synthetic_label_meta(tmp_path_factory):
    """meta.json SINTÉTICO de la etiqueta para tests sintéticos del arnés: `R.assert_no_forbidden` sin `extra` lo
    exige (src/labels/regime_us.py) aunque las columnas sean inventadas. Si el meta.json oficial existe, no hace nada.
    Si no, `forbidden_features.series` va vacía (esa lista sale del warehouse real); las columnas de la etiqueta,
    USREC y `label_*` siguen prohibidas porque están en el código (R.FORBIDDEN_FEATURES)."""
    if LABEL_META.exists():
        yield
        return
    d = tmp_path_factory.mktemp("label_meta")
    (d / LABEL_META.name).write_text(json.dumps(
        {"forbidden_features": {"label_columns": sorted(R.FORBIDDEN_FEATURES), "series": []}}))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(R, "out_path", lambda p=R.PARAMS: d / f"regime_us_v{p.version}.parquet")
        yield
