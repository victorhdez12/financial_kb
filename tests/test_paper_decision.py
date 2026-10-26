"""Reglas de registro del paper trading: nunca el mes equivocado, nunca dos veces el mismo mes (sintético)."""
from __future__ import annotations

import pandas as pd
import pytest

from scripts import paper_decision as P

T = pd.Timestamp


def test_cierre_objetivo():
    assert P.cierre_objetivo(T("2026-11-03")) == T("2026-10-31")
    assert P.cierre_objetivo(T("2026-11-01")) == T("2026-10-31")
    assert P.cierre_objetivo(T("2026-10-31")) == T("2026-09-30")      # el propio día 31 aún no está cerrado
    assert P.cierre_objetivo(T("2027-01-05")) == T("2026-12-31")
    assert P.cierre_objetivo(T("2027-03-10")) == T("2027-02-28")


def test_primera_decision_valida():
    P.validar(T("2026-10-31"), T("2026-11-03"), [])


@pytest.mark.parametrize("cierre,hoy", [
    ("2026-09-30", "2026-11-03"),     # un mes atrasado
    ("2026-11-30", "2026-11-03"),     # mes aún no cerrado
    ("2026-10-15", "2026-11-03"),     # no es fin de mes
])
def test_mes_equivocado(cierre, hoy):
    with pytest.raises(P.MesNoValido):
        P.validar(T(cierre), T(hoy), [])


def test_dos_veces_el_mismo_mes():
    with pytest.raises(P.YaRegistrado):
        P.validar(T("2026-10-31"), T("2026-11-20"), ["2026-10-31"])


def test_sin_saltos():
    P.validar(T("2026-11-30"), T("2026-12-03"), ["2026-10-31"])
    with pytest.raises(P.MesNoValido):
        P.validar(T("2026-12-31"), T("2027-01-03"), ["2026-10-31"])   # falta noviembre
