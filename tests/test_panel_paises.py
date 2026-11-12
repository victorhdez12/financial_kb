"""Panel web: la pestaña Países y las piezas de lectura se generan sin errores (signal real si existe, o vacío)."""
import json
from datetime import date
from pathlib import Path

from src.report import panel as PN
from src.report import panel_paises as PP
from src.report import pulso_paises as PU


def test_colores_reglas_fijas():
    assert PU._color_crec(-0.1, 1.2)[0] == "rojo"
    assert PU._color_crec(0.4, 1.2)[0] == "ambar"
    assert PU._color_crec(2.7, 1.5)[1] == "fuerte"
    assert PU._color_infl(4.9)[0] == "ambar" and PU._color_infl(5.5)[0] == "rojo"
    assert PU._color_fiscal(118, -5.4)[0] == "rojo" and PU._color_fiscal(65, -4.3)[0] == "ambar"
    assert PU._color_bonos("FRA", 1.49, 1.0)[0] == "ambar" and PU._color_bonos("ITA", 1.6, 0)[0] == "rojo"


def test_panel_sin_signal_no_rompe():
    doc = PN.construir({}, date(2026, 11, 12))
    assert "Países" in doc and "¿Cómo leo este panel?" in doc and "Glosario" in doc


def test_panel_con_ultimo_signal():
    sp = PN.ultimo_signal()
    if sp is None:
        return
    doc = PN.construir(json.loads(Path(sp).read_text()), date(2026, 11, 12))
    assert "error al generar" not in doc
    assert doc.count('class="pais"') >= 14


def test_formato_probabilidad():
    assert PP._p({"p": 0.09, "ic90": [0.02, 0.16], "ic_estimable": True}).startswith("9 %")
    assert PP._p(None) == "s/d"
