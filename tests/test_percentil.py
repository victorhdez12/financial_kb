"""Percentil común del panel (src/report/_percentil.py) y coherencia del HY OAS entre pestañas (sin warehouse,
salvo el último test, que se salta si no hay warehouse)."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.report import _percentil as PC
from src.report import liquidez_vivo as LV
from src.report import manos_fuertes as MF
from src.report import panel_hoy as PH
from src.report import pulso_paises as PP
from src.report import weekly as W


def _d(vals, start="2023-10-09"):
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)), dtype=float)


# ------------------------------------------------------------------ definición
def test_proporcion_menor_o_igual():
    s = _d(range(1, 31))
    assert PC.percentil(s) == 100
    assert PC.percentil(s, 15) == 50                       # 15 de 30 son ≤ 15
    assert PC.percentil(_d([1.0] * 30)) == 100             # empates cuentan como ≤
    assert PC.percentil(s, 0.5) == 0
    assert PC.percentil(s, 15, dec=None) == pytest.approx(50.0)


def test_nan_y_min_obs():
    s = _d([np.nan] * 10 + list(range(20)))
    assert PC.percentil(s) is None                         # 20 obs válidas < 24
    assert PC.percentil(s, min_obs=20) == 100
    p = PC.calcular(s, min_obs=20)
    assert p.n == 20 and p.desde == s.dropna().index[0] and p.frecuencia == "nativa" and p.ventana is None


def test_hasta_ventana_y_frecuencia():
    s = _d(range(100))
    # corte: el «valor actual» pasa a ser el del día de corte
    assert PC.percentil(s, hasta=s.index[49]) == 100
    assert PC.calcular(s, hasta=s.index[49]).n == 50
    # ventana en observaciones y en tiempo
    assert PC.calcular(s, ventana=30).n == 30
    b = PC.base(s, ventana=pd.DateOffset(months=1))
    assert b.index[0] > s.index[-1] - pd.DateOffset(months=1)
    assert PC.calcular(s, ventana=pd.DateOffset(years=3)).ventana == "3 años"
    # mensual: un dato por mes, el último del mes
    m = PC.base(s, frecuencia="M")
    assert len(m) == len(s.index.to_period("M").unique())
    assert m.iloc[0] == s[s.index.to_period("M") == s.index[0].to_period("M")].iloc[-1]
    with pytest.raises(ValueError):
        PC.base(s, frecuencia="W")


def test_etiqueta():
    assert PC.etiqueta(78.6, pd.Timestamp("2023-10-09")) == "p79 · desde 2023-10"
    assert PC.etiqueta(99.4, ventana="3 años") == "p99 · 3 años"
    assert PC.etiqueta(34, "1950-01", frecuencia="mensual") == "p34 · mensual desde 1950-01"
    assert PC.etiqueta(None, "2000") == "p—"


# ------------------------------------------------------------------ módulos que la usan
def test_modulos_usan_la_misma_definicion():
    rng = np.random.default_rng(0)
    s = _d(rng.normal(size=300).round(1))      # con empates
    ref = PC.percentil(s)
    assert PH.percentil(s) == ref
    assert LV._percentil(s) == ref
    assert W.percentile(s) == ref
    assert MF.percentil(s, float(s.iloc[-1])) == pytest.approx(PC.percentil(s, dec=None))
    assert PP._pct_hist(s, float(s.iloc[-1]))[0] == int(ref)


def _rm(nat: pd.Series, extra: pd.Series | None = None) -> pd.DataFrame:
    """regime_monthly mínimo: la columna hy_oas es el último dato de cada mes de la serie nativa."""
    m = nat.groupby(nat.index.to_period("M")).last()
    idx = m.index.to_timestamp("M")
    df = pd.DataFrame({"date": idx, "cutoff": idx, "hy_oas": m.values})
    df.loc[df.index[-1], "cutoff"] = nat.index[-1]
    if extra is not None:
        df["baa_spread"] = extra.reindex(idx).values
    return df


def test_hy_oas_igual_en_hoy_liquidez_e_indicadores():
    """Misma serie, misma ventana (toda la historia, diaria) y mismo corte → la misma cifra en las tres tablas."""
    rng = np.random.default_rng(1)
    hy = _d(np.round(3.3 + np.cumsum(rng.normal(0, 0.03, 800)), 2))
    hoy = pd.Timestamp(hy.index[-1])
    p_hoy = PH.ficha("hy", PH.serie_indicador("hy", {"BAMLH0A0HYM2": hy}))["percentil"]
    vacia = pd.Series(dtype=float)
    series = {k: vacia for k in ("BAA10Y", "AAA10Y", "BAMLH0A3HYC", "VIXCLS")} | {"BAMLH0A0HYM2": hy}
    p_liq = LV.credito(series, hoy)["hy"]["percentil"]
    meta = {"sources": {"hy_oas": {"series_id": "BAMLH0A0HYM2", "last_obs": str(hoy.date())}}}
    fila = next(r for r in W.indicator_rows(_rm(hy), meta, {"hy_oas": hy}) if r["indicador"] == "HY OAS")
    assert p_hoy == p_liq == fila["percentil_hist"] == PC.percentil(hy)
    assert fila["percentil_base"] == "nativa" and fila["desde"] == f"{hy.index[0]:%Y-%m}"
    # sin la serie nativa, la tabla de indicadores cae a la base mensual y lo dice
    fila_m = next(r for r in W.indicator_rows(_rm(hy), meta) if r["indicador"] == "HY OAS")
    assert fila_m["percentil_base"] == "mensual"
    assert fila_m["percentil_hist"] == PC.percentil(hy, frecuencia="M")


def test_indicadores_mantienen_la_historia_mensual_mas_larga():
    """Baa−10a: la columna mensual empieza décadas antes que la diaria → ventana distinta intencionada, rotulada."""
    rng = np.random.default_rng(2)
    diaria = _d(np.round(1.5 + rng.normal(0, 0.1, 600), 2), start="2024-01-01")
    fechas = pd.date_range("1950-01-31", diaria.index[-1], freq="ME")
    vals = rng.normal(2, 0.5, len(fechas) + 1)
    fechas = fechas.append(pd.DatetimeIndex([diaria.index[-1]]))
    vals[-1] = diaria.iloc[-1]
    rm = pd.DataFrame({"date": fechas, "cutoff": fechas, "baa_spread": vals})
    meta = {"sources": {"baa10y": {"series_id": "BAA10Y"}, "hy_oas": {"series_id": "BAMLH0A0HYM2"}}}
    fila = next(r for r in W.indicator_rows(rm, meta, {"baa_spread": diaria}) if r["indicador"] == "Diferencial Baa−10a")
    assert fila["percentil_base"] == "mensual" and fila["desde"] == "1950-01"


def test_hy_oas_real_mismo_corte():
    """Con el warehouse: el HY OAS de «Hoy», de la tabla de liquidez y de la de indicadores coincide al mismo corte."""
    try:
        from src.warehouse import db
        con = db.connect()
        hy = db.series(con, "BAMLH0A0HYM2")
        con.close()
    except Exception:  # noqa: BLE001
        pytest.skip("sin warehouse")
    if len(hy) < 100:
        pytest.skip("sin historia de HY OAS")
    corte = hy.index[-2]
    x = hy[hy.index <= corte]
    p_hoy = PH.ficha("hy", PH.serie_indicador("hy", {"BAMLH0A0HYM2": x}))["percentil"]
    vacia = pd.Series(dtype=float)
    p_liq = LV.credito({k: vacia for k in ("BAA10Y", "AAA10Y", "BAMLH0A3HYC", "VIXCLS")} | {"BAMLH0A0HYM2": x},
                       pd.Timestamp(date.today()))["hy"]["percentil"]
    meta = {"sources": {"hy_oas": {"series_id": "BAMLH0A0HYM2"}}}
    fila = next(r for r in W.indicator_rows(_rm(x), meta, {"hy_oas": hy}) if r["indicador"] == "HY OAS")
    assert p_hoy == p_liq == fila["percentil_hist"]
