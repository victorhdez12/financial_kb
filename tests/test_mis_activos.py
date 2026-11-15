"""«Mis activos»: lista de la ingesta Yahoo y tratamiento de la historia corta (VYLR, desde 1-oct-2026)."""
import json
from datetime import date

import numpy as np
import pandas as pd

from src.ingest.yahoo_precios import ACTIVOS
from src.report import mis_activos as MA


def test_lista_incluye_vylr_junto_a_ctva():
    assert len(ACTIVOS) == 30
    assert "VYLR" in ACTIVOS and ACTIVOS["VYLR"][1] == ACTIVOS["CTVA"][1] == "Agro / pesticidas"
    assert "VYLR" in MA.NOTAS and "CTVA + VYLR" in MA.NOTAS["CTVA"]


def _precios(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    larga = pd.bdate_range("2012-01-02", "2026-11-13")
    corta = pd.bdate_range("2026-10-01", "2026-11-13")
    P = pd.DataFrame({"SPY": 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(larga)))),
                      "AAA": 50 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, len(larga))))}, index=larga)
    P["VYLR"] = pd.Series(70 * np.exp(np.cumsum(rng.normal(0, 0.02, len(corta)))), index=corta)
    P["NUEVA"] = pd.Series([10.0, 10.5], index=larga[-2:])
    P.to_parquet(tmp_path / "precios_diarios.parquet")
    meta = {t: {"nombre": t, "grupo": "Acciones", "moneda": "USD"} for t in P}
    (tmp_path / "activos.json").write_text(json.dumps({"descarga": "x", "activos": meta}))
    monkeypatch.setattr(MA, "DIR", tmp_path)
    monkeypatch.setattr(MA, "N_SIM", 500)
    esc = {"paises": {"USA": {"cuantiles_1_99": {"bolsa": list(np.linspace(-0.3, 0.4, 99))}}}}
    return MA.analizar(None, date(2026, 11, 15), esc, 2.5, 4.0)["activos"]


def test_historia_corta_sin_simulaciones_ni_estadisticos(tmp_path, monkeypatch):
    A = _precios(tmp_path, monkeypatch)
    v = A["VYLR"]
    assert "error" not in v
    assert v["historia_insuficiente"] == "historia insuficiente (desde 2026-10-01)"
    for k in ("sim_historia", "sim_motor", "beta_3a", "por_cuadrante"):
        assert k not in v
    assert v["vol_1a"] is None and v["caida_max52"] is None
    assert v["r_12m"] is None and v["r_ytd"] is None and v["r_3m"] is None  # sin base: no se inventa
    assert v["r_1m"] is not None and v["precio"] > 0
    # activo largo: sigue con todo
    a = A["AAA"]
    assert "historia_insuficiente" not in a and "sim_historia" in a and "sim_motor" in a
    # casi sin datos: solo el mensaje
    assert A["NUEVA"]["error"].startswith("historia insuficiente")


def test_aviso_vylr_menciona_corteva(tmp_path, monkeypatch):
    v = _precios(tmp_path, monkeypatch)["VYLR"]
    assert any("Corteva" in a for a in v["avisos"])


def test_panel_muestra_historia_insuficiente(tmp_path, monkeypatch):
    from src.report import panel_activos as PA
    A = _precios(tmp_path, monkeypatch)
    monkeypatch.setattr(PA, "_datos", lambda s, pul: {"activos": A, "supuestos": {}, "descarga": "x"})
    html = PA.sec_activos({}, None)
    assert "historia insuficiente (desde 2026-10-01)" in html and "act-VYLR" in html
