"""Ingesta BoE de tipos a 3 meses (src/ingest/boe_rates.py): sintéticos, sin red."""
import numpy as np
import pandas as pd
import pytest

from src.ingest import boe_rates as B


def test_mensual_solo_meses_completos():
    d = pd.bdate_range("2026-01-01", "2026-03-10")
    s = pd.Series(np.arange(len(d), dtype=float), index=d)
    s = s.drop(s.loc["2026-02-05":"2026-02-27"].index)            # febrero con < 10 días
    m = B.mensual_completa(s)
    assert list(m.index) == [pd.Timestamp("2026-01-01")]          # febrero (pocos días) y marzo (en curso) fuera
    assert m.iloc[0] == pytest.approx(s.loc["2026-01"].mean())


def test_iadb_fecha_a_inicio_de_mes():
    raw = b"DATE,IUMASOIA\r\n31 Jan 2026,3.725\r\n28 Feb 2026,3.7274\r\n"
    s = B.iadb_monthly(raw, "IUMASOIA")
    assert list(s.index) == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")]
    with pytest.raises(ValueError):
        B.iadb_monthly(raw, "IUMAJNB")
