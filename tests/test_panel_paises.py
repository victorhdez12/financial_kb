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


def test_mis_activos_simulacion_reproducible():
    import numpy as np
    from src.report import mis_activos as MA
    r = np.full(120, 0.01)                                   # +1 % al mes constante
    a = MA._bootstrap(r, 1000, 12, np.random.default_rng(1))
    assert np.allclose(a, 0.12)                              # 12 meses de +1 % log
    s = MA._resumen(np.expm1(a))
    assert s["p_perdida"] == 0 and abs(s["p50"] - np.expm1(0.12)) < 1e-12
    es = {"paises": {"USA": {"cuantiles_1_99": {"bolsa": list(np.linspace(-0.3, 0.4, 99))}}}}
    m = MA._mercado_motor(es, 2.0, 5000, np.random.default_rng(2))
    assert m.min() >= (1 - 0.3) * 1.02 - 1 - 1e-9 and m.max() <= 1.4 * 1.02 - 1 + 1e-9


def test_pulso_por_fecha_no_por_posicion():
    import pandas as pd
    from src.report import pulso_paises as PU
    idx = pd.date_range("2024-01-01", "2026-10-01", freq="MS").drop(pd.Timestamp("2025-10-01"))   # mes ausente
    s = pd.Series(range(len(idx)), index=idx, dtype=float)
    assert PU._dif(s, 12) is None                            # oct-2025 no existe → s/d, no compara con otro mes
    assert PU._dif(s, 13) == float(s.iloc[-1] - s[pd.Timestamp("2025-09-01")])
