"""Validador independiente (17-nov-2026): panel v2 (UX v2 + «Mis activos» v2). Informe: docs/validation/2026-11-17_panel_v2.md.

Datos SINTÉTICOS (sin red y sin datos de terceros: el repo es público).
Los tests marcados `xfail(strict=True)` documentan HALLAZGOS (comportamiento actual incorrecto); si alguien los arregla,
pasarán y pytest avisará (XPASS → fallo) para quitar la marca.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.ingest import sec_form4_detalle as F4
from src.ingest import yahoo_analistas as YA
from src.report import activos_v2 as AV
from src.report import panel as P

HOY = date(2026, 11, 16)
R_ACC = {"nombre": "Aaa", "grupo": "Acciones", "precio": 11.0, "moneda": "USD"}
REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------------------------- árbol sintético
def _arbol(root: Path) -> None:
    idx = pd.bdate_range(end=pd.Timestamp(HOY), periods=300)
    dv = root / "mercados" / "volumen"
    dv.mkdir(parents=True)
    pd.DataFrame({"AAA": 1000.0}, index=idx).to_parquet(dv / "volumen_diario.parquet")
    pd.DataFrame({"AAA": np.linspace(9, 12, len(idx))}, index=idx).to_parquet(dv / "cierre_diario.parquet")
    (dv / "splits.json").write_text(json.dumps({"descarga": "2026-11-17T07:00:00+00:00", "splits": {"AAA": []}}))
    d4 = root / "sec_form4"
    d4.mkdir()
    ops = pd.DataFrame([{"accession": "a", "filing_date": pd.Timestamp("2026-10-03"), "trans_date": pd.Timestamp("2026-10-01"),
                         "issuer_cik": "1", "ticker": "AAA", "owner_cik": "9", "owner_name": "Ana", "title": "CEO",
                         "director": False, "officer": True, "ten_pct": False, "code": "P", "acq_disp": "A",
                         "shares": 100.0, "price": 11.5, "plan_10b5_1": False, "fuente": "t"}])
    ops.to_parquet(d4 / "operaciones.parquet")
    (d4 / "meta.json").write_text(json.dumps({"desde": "2024-11-17"}))
    d13 = root / "sec_13f"
    d13.mkdir()
    pd.DataFrame([{"ticker": "AAA", "period": pd.Timestamp(p), "cik": "1", "gestor": "Fondo", "shares": s, "value": s * 10.5,
                   "filing_date": pd.Timestamp(p) + pd.Timedelta(days=40)}
                  for p, s in (("2026-03-31", 100.0), ("2026-06-30", 120.0))]).to_parquet(d13 / "posiciones.parquet")
    da = root / "mercados" / "analistas"
    da.mkdir(parents=True)
    da.joinpath("analistas.json").write_text(json.dumps({"descarga": "2026-11-17T07:00:00+00:00", "acciones": {"AAA": {
        "targetMeanPrice": 13.0, "targetHighPrice": 15.0, "targetLowPrice": 10.0, "numberOfAnalystOpinions": 5,
        "recommendationMean": 2.0, "tendencia": [{"period": "0m", "strongBuy": 1, "buy": 2, "hold": 2, "sell": 0, "strongSell": 0}],
        "cambios": []}}}))


FUENTES = {  # fuente → (fichero, texto que debe desaparecer si falla, error esperado en cargar())
    "volumen": ("mercados/volumen/volumen_diario.parquet", "Media 20 sesiones", "error_volumen"),
    "form4": ("sec_form4/operaciones.parquet", "Precio medio ponderado", "error_form4"),
    "13f": ("sec_13f/posiciones.parquet", "Gestora (mayores", "error_13f"),
    "analistas": ("mercados/analistas/analistas.json", "Precio objetivo (12 m)", "error_analistas"),
}


def test_arbol_sintetico_completo(tmp_path, monkeypatch):
    _arbol(tmp_path)
    monkeypatch.setenv("FIN_DATA_ROOT", str(tmp_path))
    h = AV.ficha_v2("AAA", R_ACC, AV.cargar(), HOY)
    for _, (_, marca, _) in FUENTES.items():
        assert marca in h
    assert "s/d" not in h


@pytest.mark.parametrize("modo", ["ausente", "corrupto", "vacio"])
@pytest.mark.parametrize("fuente", list(FUENTES))
def test_fallo_de_cada_fuente_da_sd_y_el_resto_sigue(tmp_path, monkeypatch, fuente, modo):
    _arbol(tmp_path)
    fich, marca, err = FUENTES[fuente]
    f = tmp_path / fich
    if modo == "ausente":
        f.unlink()
    elif modo == "corrupto":
        f.write_bytes(b"\x00basura{no es parquet ni json")
    else:
        f.write_bytes(b"")
    monkeypatch.setenv("FIN_DATA_ROOT", str(tmp_path))
    X = AV.cargar()
    assert err in X
    h = AV.ficha_v2("AAA", R_ACC, X, HOY)
    assert marca not in h and "s/d" in h
    for otra, (_, m2, _) in FUENTES.items():   # los demás bloques siguen
        if otra != fuente and not (fuente == "volumen" and otra in ("form4", "13f")):
            assert m2 in h, (fuente, otra)


def test_json_analistas_con_estructura_inesperada_no_tumba_la_ficha(tmp_path, monkeypatch):
    _arbol(tmp_path)
    (tmp_path / "mercados/analistas/analistas.json").write_text(json.dumps({"acciones": {"AAA": {"tendencia": "x",
                                                                                                    "cambios": [{"sin": "fecha"}]}}}))
    monkeypatch.setenv("FIN_DATA_ROOT", str(tmp_path))
    h = AV.ficha_v2("AAA", R_ACC, AV.cargar(), HOY)
    assert "Media 20 sesiones" in h and "s/d" in h


# --------------------------------------------------------------------------------------------- HTTP / UA / límites
def test_user_agent_generico_y_plazo_total(monkeypatch):
    assert "example.org" in F4.UA and not re.search(r"victor|hdez", F4.UA + YA.UA, re.I)
    vistos = []

    class R:
        status_code, text = 200, "ok"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(F4._http, "get", lambda url, **kw: vistos.append(kw) or R())
    monkeypatch.setattr(F4, "_S", None)
    F4.sec_get("https://example.invalid/x")
    assert vistos[0]["total"] is not None and vistos[0]["timeout"] is not None
    assert vistos[0]["session"].headers["User-Agent"] == F4.UA
    assert F4._LIMITER.interval >= 1 / 10        # ≤ 10 peticiones/s (límite de la SEC)


# --------------------------------------------------------------------------------------------- privacidad
def test_ningun_dato_de_terceros_en_git():
    try:
        fich = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    except Exception:  # noqa: BLE001
        pytest.skip("sin git")
    malos = [f for f in fich if re.search(r"(volumen_diario|cierre_diario|operaciones|posiciones)\.parquet$|analistas\.json$"
                                          r"|sec_form4/|sec_13f/|mercados/", f)]
    assert not malos


# --------------------------------------------------------------------------------------------- HALLAZGOS
def test_form4_conserva_lineas_identicas_de_un_mismo_formulario(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_DATA_ROOT", str(tmp_path))
    fila = {"accession": "x1", "filing_date": "2026-11-03", "trans_date": "2026-11-01", "issuer_cik": "1", "ticker": "AAA",
            "owner_cik": "9", "owner_name": "Ana", "title": "COO", "director": False, "officer": True, "ten_pct": False,
            "code": "S", "acq_disp": "D", "shares": 82.0, "price": 600.0, "plan_10b5_1": True, "fuente": "form4_xml"}
    monkeypatch.setattr(F4, "acciones", lambda: {"AAA": "1"})
    monkeypatch.setattr(F4, "capa_xml", lambda ciks, despues: pd.DataFrame([fila, dict(fila)], columns=F4.COLS))
    F4.run(24)
    d = pd.read_parquet(tmp_path / "sec_form4" / "operaciones.parquet")
    assert len(d) == 2 and d["shares"].sum() == 164


def test_13f_valor_en_miles_no_convierte_la_posicion_en_sin_dato_previo():
    per = pd.to_datetime(["2026-03-31", "2026-06-30"])
    pos = pd.DataFrame([{"ticker": "AAA", "period": per[0], "cik": "1", "gestor": "Fondo", "shares": 36e6, "value": 36e6 * 108 / 1000,
                         "filing_date": per[0] + pd.Timedelta(days=40)},
                        {"ticker": "AAA", "period": per[1], "cik": "1", "gestor": "Fondo", "shares": 32e6, "value": 32e6 * 93,
                         "filing_date": per[1] + pd.Timedelta(days=40)}]
                       + [{"ticker": "AAA", "period": p, "cik": "2", "gestor": "Otro", "shares": 1e6, "value": 1e6 * v,
                           "filing_date": p + pd.Timedelta(days=40)} for p, v in zip(per, (108, 93))])
    cierre = pd.Series(np.r_[np.full(63, 108.0), np.full(130, 93.0)], index=pd.bdate_range("2026-01-01", periods=193))
    ch = AV.resumen_13f(pos, cierre)["top"][0]["cambios"][-1]
    assert not ch["nueva"] and abs(ch["pct"] + 100 * 4 / 36) < 1e-6


def test_enlace_directo_no_reescribe_el_hash():
    m = re.search(r"if\(dp&&dp\.closest\('main>section'\)\)\{show\(([^)]*\)[^)]*)\)", P.JS)
    assert m, "no se encuentra la rama del enlace directo"
    args = m.group(1).split(",")
    assert len(args) >= 3 and args[2].strip() in ("true", "1", "!0")
