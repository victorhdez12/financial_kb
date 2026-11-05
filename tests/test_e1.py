"""P-E1: las variables del registro en vivo (`e1.rasgos`) son idénticas a las de INT-13 (`int13.construir`) con ≤ 2004,
y los modelos congelados se reproducen con su sha256."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.intl import e1 as E

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dev():
    from scripts import int13_corrida as C
    from src.intl import int13 as M
    return M.construir(C.cargar_real())


def test_rasgos_vivo_igual_que_int13(dev):
    from src.intl import data as D
    con = D.connect()
    try:
        rej = pd.date_range("1950-01-31", "2004-12-31", freq="ME")
        r = E.rasgos(lambda sid: D.load_dev(con, sid), rej)
    finally:
        con.close()
    a = dev[dev.pais.isin(E.PAISES)].set_index(["pais", "fecha"])[E.COLS["A"]].sort_index()
    b = r.set_index(["pais", "fecha"])[E.COLS["A"]].reindex(a.index)
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-12)


def test_modelos_congelados(dev):
    from src.intl import int13 as M
    j = json.loads((REPO / "research/int/e1_modelos.json").read_text())
    mod = E.ajustar(E.filas(M.muestra(dev, E.OBJ)))
    assert E.sha(mod) == j["modelos_sha256"] == E.sha(j["modelos"])
