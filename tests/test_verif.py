"""Tests del registro de verificación a corto plazo (src/verif). Datos sintéticos; sin red ni warehouse."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src.verif import correlaciones as C
from src.verif import datos as D
from src.verif import metodo as M
from src.verif import panel_verif as PV
from src.verif import registro as R


def _serie_vintages(sid, niveles: pd.Series, lag_dias: int, revision: float = 0.0) -> pd.DataFrame:
    """Cada periodo se publica `lag_dias` tras su fin; con `revision`, se revisa un mes después (+revision)."""
    filas = []
    for d, v in niveles.items():
        fin = d + (pd.offsets.QuarterEnd(0) if sid == "GDPC1" else pd.offsets.MonthEnd(0))
        pub = fin + pd.Timedelta(days=lag_dias)
        if revision:
            rev = pub + pd.Timedelta(days=30)
            filas.append((d, v, pub, rev - pd.Timedelta(days=1)))
            filas.append((d, v + revision, rev, pd.NaT))
        else:
            filas.append((d, v, pub, pd.NaT))
    return pd.DataFrame(filas, columns=["date", "value", "realtime_start", "realtime_end"])


@pytest.fixture(scope="module")
def V():
    rng = np.random.default_rng(0)
    m = pd.date_range("2000-01-01", "2026-10-01", freq="MS")
    q = pd.date_range("2000-01-01", "2026-07-01", freq="QS")
    cpi = pd.Series(100 * np.exp(np.cumsum(0.002 + 0.002 * rng.standard_normal(len(m)))), index=m)
    core = pd.Series(100 * np.exp(np.cumsum(0.002 + 0.001 * rng.standard_normal(len(m)))), index=m)
    pay = pd.Series(130000 + np.cumsum(150 + 80 * rng.standard_normal(len(m))), index=m)
    ur = pd.Series(5 + np.cumsum(0.1 * rng.standard_normal(len(m))), index=m)
    ip = pd.Series(100 * np.exp(np.cumsum(0.001 + 0.005 * rng.standard_normal(len(m)))), index=m)
    gdp = pd.Series(15000 * np.exp(np.cumsum(0.005 + 0.004 * rng.standard_normal(len(q)))), index=q)
    w = pd.date_range("2000-01-08", "2026-11-07", freq="W-SAT")
    icsa = pd.Series(300000 * np.exp(0.05 * rng.standard_normal(len(w))), index=w)
    tablas = {"CPIAUCSL": _serie_vintages("CPIAUCSL", cpi, 12, revision=0.01),
              "CPILFESL": _serie_vintages("CPILFESL", core, 12), "PAYEMS": _serie_vintages("PAYEMS", pay, 6, revision=20),
              "UNRATE": _serie_vintages("UNRATE", ur, 6), "INDPRO": _serie_vintages("INDPRO", ip, 16),
              "GDPC1": _serie_vintages("GDPC1", gdp, 29),
              "ICSA": pd.DataFrame({"date": w, "value": icsa.values, "realtime_start": w + pd.Timedelta(days=5),
                                    "realtime_end": pd.NaT})}
    dias = pd.date_range("1999-12-01", "2026-11-13", freq="B")
    wti = pd.Series(60 * np.exp(np.cumsum(0.01 * rng.standard_normal(len(dias)))), index=dias)
    return D.Vintages(tablas=tablas, diarias={"DCOILWTICO": wti})


def test_metodo_congelado_coincide_con_documento():
    doc = (R.db.REPO / "docs/verif/metodo_v1.md").read_text(encoding="utf-8")
    sha_doc = re.search(r"sha256 del método:\*\* `([0-9a-f]{64})`", doc).group(1)
    assert hashlib.sha256((R.db.REPO / "src/verif/metodo.py").read_bytes()).hexdigest() == sha_doc == R.sha_metodo()


def test_as_of_y_primera_publicacion(V):
    p = pd.Timestamp("2020-05-01")
    pub = V.publicacion("CPIAUCSL", p)
    assert pub == pd.Timestamp("2020-06-12")
    assert p not in V.as_of("CPIAUCSL", pub - pd.Timedelta(days=1)).index
    v0 = V.as_of("CPIAUCSL", pub)[p]
    assert V.as_of("CPIAUCSL", pub + pd.Timedelta(days=40))[p] == pytest.approx(v0 + 0.01)
    y, r = M.dato_real("nominas", p, V)    # primera publicación, no la revisada
    s = V.as_of("PAYEMS", r)
    assert y == pytest.approx(s[p] - s[pd.Timestamp("2020-04-01")])


def test_prediccion_usa_solo_lo_publicado_antes(V):
    p = pd.Timestamp("2018-03-01")
    d = M.fecha_emision("ipc", p, V)
    assert d == pd.Timestamp("2018-04-01")      # fin de mes + 1 (el mes anterior salió el 12-mar)
    a = M.predecir("ipc", p, V, d)
    assert a["corte_datos"] == "2018-03-31" and a["inf80"] < a["punto"] < a["sup80"]
    # cambiar datos publicados el día de emisión o después no puede mover la predicción
    t = {k: v.copy() for k, v in V.t.items()}
    late = t["CPIAUCSL"]["realtime_start"] >= d
    t["CPIAUCSL"].loc[late, "value"] *= 1.5
    V2 = D.Vintages(tablas=t, diarias=V.d)
    assert M.predecir("ipc", p, V2, d)["punto"] == pytest.approx(a["punto"])


def test_pib_espera_a_las_entradas(V):
    p = pd.Timestamp("2019-07-01")
    d = M.fecha_emision("pib", p, V)
    assert d == pd.Timestamp("2019-10-17")      # industria de septiembre (16 días tras fin de mes) + 1
    assert M.predecir("pib", p, V, d - pd.Timedelta(days=1)) is None
    assert M.predecir("pib", p, V, d) is not None


def test_emision_vivo_append_only(V, tmp_path):
    ruta = tmp_path / "vivo.jsonl"
    est = R.emitir_vivo(V, hoy=pd.Timestamp("2026-11-14").date(), ruta=ruta)
    assert all(e["estado"] != "EMITIDA" for e in est)        # noviembre aún no ha acabado
    assert not ruta.exists()
    est = R.emitir_vivo(V, hoy=pd.Timestamp("2026-12-01").date(), ruta=ruta,
                        ahora_utc=datetime(2026, 12, 1, 6, 30, tzinfo=timezone.utc))
    emit = [e for e in est if e["estado"] == "EMITIDA"]
    assert {e["variable"] for e in emit} >= {"ipc_sub", "nominas"}
    antes = ruta.read_text()
    est2 = R.emitir_vivo(V, hoy=pd.Timestamp("2026-12-02").date(), ruta=ruta)
    assert ruta.read_text() == antes and all(e["estado"] != "EMITIDA" for e in est2)
    with pytest.raises(ValueError):
        R._anadir(ruta, json.loads(antes.splitlines()[0]))


def test_puntuacion_y_anulacion(V):
    p = pd.Timestamp("2021-09-01")
    d = M.fecha_emision("nominas", p, V)
    reg = R._registro("nominas", p, M.predecir("nominas", p, V, d), d, "vivo", "2021-10-01T06:00:00+00:00")
    tarde = dict(reg, emitida_utc=f"{V.publicacion('PAYEMS', p).date()}T13:00:00+00:00")
    a, b = R.puntuar([reg, tarde], V)
    assert a["estado"] == "puntuada" and a["error"] == pytest.approx(a["real"] - a["punto"], abs=1e-3)
    assert b["estado"].startswith("anulada")
    fut = dict(reg, periodo="2027-01-01", id="nominas:2027-01-01")
    assert R.puntuar([fut], V)[0]["estado"] == "pendiente"


def test_backtest_y_resumen(V):
    regs = R.backtest(V, desde=pd.Timestamp("2015-01-01"), hasta=pd.Timestamp("2026-11-14"))
    assert regs and all(r["modo"] == R.ETIQ_RETRO for r in regs)
    assert all(pd.Timestamp(r["fecha_emision"]) <= V.publicacion(r["serie"], r["periodo"]) for r in regs)
    filas = R.tabla_resumen(R.puntuar(regs, V))
    f = {x["variable"]: x for x in filas}
    assert f["ipc"]["n"] > 100 and 0.5 < f["ipc"]["cobertura80"] <= 1


def test_monitor_correlaciones_signo():
    idx = pd.date_range("2010-01-01", periods=120, freq="MS")
    rng = np.random.default_rng(1)
    a = rng.standard_normal(120)
    r = pd.DataFrame({"bolsa": a, "bonos": -a + 0.3 * rng.standard_normal(120), "oro": rng.standard_normal(120),
                      "dolar": rng.standard_normal(120)}, index=idx)
    mon = C.monitor(r, {"emision": "x", "valores": {"bolsa-bonos": 0.34, "bonos-oro": -0.2}}, desde="2010-01-01")
    bb = next(q for q in mon["pares"] if q["par"] == "bolsa-bonos")
    assert bb["c36"] < -0.5 and bb["difiere_signo"] is True
    assert next(q for q in mon["pares"] if q["par"] == "bolsa-oro")["motor"] is None
    html = PV.sec_correlaciones(mon)
    assert "signo distinto" in html and "<svg" in html


def test_seccion_panel_sin_resumen(tmp_path):
    mon = {"pares": [], "series": {}, "nota": "", "motor_emision": None}
    h = PV.sec_verificacion(tmp_path / "no_existe.json", mon)
    assert "Qué se verifica aquí y qué no" in h and "Sin resumen" in h
