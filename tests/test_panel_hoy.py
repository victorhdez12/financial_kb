"""Pestaña «Hoy» del panel: percentil, semáforos y detección de datos nuevos con datos sintéticos (sin warehouse)."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.report import panel_hoy as PH


def _m(vals, start="2020-01-01"):
    return pd.Series(vals, index=pd.date_range(start, periods=len(vals), freq="MS"), dtype=float)


def test_percentil():
    assert PH.percentil(_m(range(1, 101))) == 100
    assert PH.percentil(_m(list(range(100, 0, -1)))) == 1
    assert PH.percentil(_m([5] * 10)) is None          # menos de 24 datos
    x = _m(list(range(50)) + [24.5])
    assert PH.percentil(x) == round(26 / 51 * 100)


def test_yoy_y_m2_real():
    m2 = _m([100 * 1.05 ** (i / 12) for i in range(36)])
    cpi = _m([100 * 1.02 ** (i / 12) for i in range(36)])
    y = PH.yoy(m2)
    assert abs(y.iloc[-1] - 5) < 1e-9
    r = PH.serie_indicador("m2_real", {"M2SL": m2, "CPIAUCSL": cpi})
    assert abs(r.iloc[-1] - (1.05 / 1.02 - 1) * 100) < 1e-9


def test_yoy_por_calendario_con_mes_ausente():
    """IPC de EE. UU.: oct-2025 no se publicó. El a/a de oct-2026 compara con oct-2025 (interpolado, solo como base),
    nunca con sep-2025 (13 meses); el mes ausente no tiene a/a propio. Antes salía 4,1 % en vez de 3,9 %."""
    idx = pd.date_range("2024-01-01", "2026-10-01", freq="MS")
    x = pd.Series(100 * 1.03 ** (np.arange(len(idx)) / 12), index=idx)
    x[pd.Timestamp("2025-10-01")] = np.nan
    y = PH.yoy(x)
    assert pd.Timestamp("2025-10-01") not in y.index
    for t in ("2025-11-01", "2026-09-01", "2026-10-01"):
        assert abs(y[pd.Timestamp(t)] - 3.0) < 1e-9, t
    # dos meses seguidos ausentes: no se inventa la base
    x2 = x.copy()
    x2[pd.Timestamp("2025-09-01")] = np.nan
    y2 = PH.yoy(x2)
    assert pd.Timestamp("2026-09-01") not in y2.index and pd.Timestamp("2026-10-01") not in y2.index
    assert abs(y2[pd.Timestamp("2026-08-01")] - 3.0) < 1e-9


def test_semaforos_umbrales():
    d = lambda v: pd.Series([v], index=[pd.Timestamp("2026-11-13")])  # noqa: E731
    assert PH.regla_vix(d(31))[0] == "rojo" and PH.regla_vix(d(22))[0] == "ambar" and PH.regla_vix(d(15))[0] == "verde"
    assert PH.regla_m2(d(-1))[0] == "rojo" and PH.regla_m2(d(1))[0] == "ambar" and PH.regla_m2(d(5))[0] == "verde"
    assert PH.regla_m2(d(12))[0] == "ambar"
    assert PH.regla_infl(d(6))[0] == "rojo" and PH.regla_infl(d(2))[0] == "verde"
    assert PH.regla_stlfsi(d(1.2))[0] == "rojo" and PH.regla_stlfsi(d(0.1))[0] == "ambar"
    assert PH.regla_bolsa(d(-21))[0] == "rojo" and PH.regla_bolsa(d(-12))[0] == "ambar"
    assert PH.regla_vix(pd.Series(dtype=float))[0] == "gris"


def test_hy_regla_del_monitor_por_cambio_3m():
    idx = pd.date_range("2026-01-01", "2026-11-13", freq="D")
    x = pd.Series(np.linspace(3.0, 3.0, len(idx)), index=idx)
    assert PH.regla_hy(x)[0] == "verde"
    x.iloc[-1] = 4.6                                     # nivel ≥ 4,5 → ámbar (y Δ3m 1,6 → rojo)
    assert PH.regla_hy(x)[0] == "rojo"
    x.iloc[-1] = 3.9                                     # Δ3m 0,9 ≥ 0,75 → ámbar
    assert PH.regla_hy(x)[0] == "ambar"


def test_curva_invertida_y_reempinamiento():
    inv = _m([1.0] * 12 + [-0.5] * 12)
    assert PH.regla_curva(inv)[0] == "ambar"
    reemp = _m([-1.0] * 10 + [-0.4, 0.0, 0.3])
    assert PH.regla_curva(reemp)[0] == "rojo"
    assert PH.regla_curva(_m([1.0] * 24))[0] == "verde"


def test_ficha_y_sparkline():
    x = _m(list(range(30)))
    f = PH.ficha("vix", x)
    assert f["valor"] == 29 and f["anterior"] == 28 and f["cambio"] == 1 and f["percentil"] == 100
    assert f["fecha"] == "2022-06-01" and f["color"] == "ambar" and f["fija"]
    s = PH.sparkline(x)
    assert s.startswith("<svg") and "polyline" in s
    assert PH.sparkline(pd.Series(dtype=float)) == ""


def _ult(rows):
    return pd.DataFrame(rows, columns=["series_id", "d1", "v1", "d2", "v2", "nombre", "freq"])


def test_novedades_estado_nuevo_revisado_y_siembra():
    hoy = date(2026, 11, 14)
    ult = _ult([["A", "2026-10-01", 10.0, "2026-09-01", 9.5, "serie A", "M"],
                ["B", "2026-10-01", 5.0, "2026-09-01", 4.0, "serie B", "M"],
                ["C", "2026-09-01", 1.0, "2026-08-01", 1.0, "serie C", "M"],
                ["D", "2026-09-01", 2.2, "2026-08-01", 2.0, "serie D", "M"]])
    # primera vez: sin estado → solo siembra con fecha de publicación reciente
    ev, est = PH.novedades_estado(ult, {}, hoy, publicado={"A": date(2026, 11, 13), "C": date(2026, 10, 1)})
    assert [e["series_id"] for e in ev] == ["A"] and ev[0]["revisado"] is None
    assert est["series"]["B"] == ["2026-10-01", 5.0]
    # día siguiente con estado de ayer: B tiene dato nuevo y su anterior se revisó (4,2 → 4,0); D revisa su último
    prev = {"series": {"A": ["2026-10-01", 10.0], "B": ["2026-09-01", 4.2], "C": ["2026-09-01", 1.0],
                       "D": ["2026-09-01", 2.0]}, "eventos": []}
    ev, est = PH.novedades_estado(ult, prev, hoy)
    porid = {e["series_id"]: e for e in ev}
    assert set(porid) == {"B", "D"}
    assert porid["B"]["revisado"] is True and porid["B"]["valor_ant_antes"] == 4.2 and porid["B"]["valor_ant"] == 4.0
    assert porid["D"].get("solo_revision")
    # los eventos se conservan 7 días y luego caen
    ev2, _ = PH.novedades_estado(ult, est, date(2026, 11, 20))
    assert {e["series_id"] for e in ev2} == {"B", "D"}
    ev3, _ = PH.novedades_estado(ult, est, date(2026, 11, 25))
    assert ev3 == []


def test_novedades_vintages():
    hoy = date(2026, 11, 14)
    v = pd.DataFrame([
        ["M2SL", "2026-08-01", 100.0, "2026-09-22"],
        ["M2SL", "2026-08-01", 99.0, "2026-11-10"],     # revisión del anterior
        ["M2SL", "2026-09-01", 101.0, "2026-11-10"],    # dato nuevo
        ["UNRATE", "2026-09-01", 4.0, "2026-10-03"],    # vintage de hace > 7 días → no sale
    ], columns=["series_id", "date", "value", "realtime_start"])
    ev = PH.novedades_vintages(v, hoy)
    assert len(ev) == 1
    e = ev[0]
    assert e["series_id"] == "M2SL" and e["fecha"] == "2026-09-01" and e["valor"] == 101.0
    assert e["revisado"] is True and e["valor_ant_antes"] == 100.0 and e["valor_ant"] == 99.0
    assert e["detectado"] == "2026-11-10"


def test_orden_clave_primero():
    ev = [{"series_id": "ZZZ", "detectado": "2026-11-14"}, {"series_id": "CPIAUCSL", "detectado": "2026-11-10"},
          {"series_id": "M2SL", "detectado": "2026-11-09"}]
    assert [e["series_id"] for e in PH.ordenar_novedades(ev)] == ["M2SL", "CPIAUCSL", "ZZZ"]


def test_avisos_reporte():
    s = {"credit": {"light": "ámbar", "reds": 0, "ambers": 2, "indicators": {"hy_oas": {"status": "ámbar", "value": 4.6}}},
         "regime": {"sahm_trigger": True, "sahm": 0.55},
         "pulso_paises": {"paises": {"USA": {"nombre": "EE. UU.", "colores": {"fiscal": {"color": "rojo"}}}}}}
    av = PH.avisos_reporte(s)
    colores = [c for c, _ in av]
    assert "rojo" in colores and "ambar" in colores and len(av) == 4
    assert PH.avisos_reporte({}) == []
