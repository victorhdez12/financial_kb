"""Archivo fechado del raw de la OCDE (src/ingest/_archivo_raw.py) y su uso en src/ingest/oecd.py y oecd_qna.py. Sin red."""
import datetime as dt
import gzip
import json

import pandas as pd

from src.ingest import _archivo_raw as A
from src.ingest import oecd, oecd_qna

CSV = b"TIME_PERIOD,OBS_VALUE,REF_AREA,MEASURE\n2004-01,1.0,BEL,IRLT\n"


def test_archiva_con_fecha_y_no_duplica(tmp_path):
    d1, d2, d3 = dt.date(2026, 11, 2), dt.date(2026, 11, 9), dt.date(2026, 11, 16)
    p = A.archivar(tmp_path, "finmark", CSV, d1)
    assert p.name == "finmark_2026-11-02.csv.gz" and gzip.decompress(p.read_bytes()) == CSV
    assert A.archivar(tmp_path, "finmark", CSV, d2) is None                  # idéntico: solo índice
    nuevo = CSV.replace(b"1.0", b"1.1")                                      # revisión en origen
    assert A.archivar(tmp_path, "finmark", nuevo, d3).name == "finmark_2026-11-16.csv.gz"
    idx = [json.loads(x) for x in (tmp_path / "archivo" / "indice.jsonl").read_text().splitlines()]
    assert [r["fecha"] for r in idx] == ["2026-11-02", "2026-11-09", "2026-11-16"]
    assert idx[1]["igual_a"] == "finmark_2026-11-02.csv.gz"
    assert A.leer(tmp_path, "finmark", "2026-11-09") == CSV and A.leer(tmp_path, "finmark", "2026-11-16") == nuevo


def test_retencion(tmp_path):
    """Todo lo de los últimos 730 días; de lo anterior, la primera copia de cada mes (y las referenciadas)."""
    hoy = dt.date(2029, 1, 1)
    for i, f in enumerate(pd.date_range("2026-01-04", "2026-03-29", freq="7D").date):
        A.archivar(tmp_path, "ip", CSV + str(i).encode(), f)
    A.archivar(tmp_path, "ip", CSV + b"reciente", dt.date(2028, 12, 1))
    A.podar(tmp_path / "archivo", hoy)
    quedan = sorted(p.name for p in (tmp_path / "archivo").glob("*.csv.gz"))
    assert quedan == ["ip_2026-01-04.csv.gz", "ip_2026-02-01.csv.gz", "ip_2026-03-01.csv.gz", "ip_2028-12-01.csv.gz"]
    assert A.RETENCION_DIAS == 730


def _sin_red(monkeypatch, tmp_path, mod):
    class R:
        content = CSV
        text = CSV.decode()
    monkeypatch.setattr(mod, "http_get", lambda *a, **k: R())
    monkeypatch.setattr(mod, "raw_dir", lambda src: (tmp_path / src).mkdir(exist_ok=True) or tmp_path / src)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)


def test_oecd_fetch_archiva(monkeypatch, tmp_path):
    _sin_red(monkeypatch, tmp_path, oecd)
    oecd.fetch("finmark", "q", refresh=True)
    assert (tmp_path / "oecd" / "finmark.csv").read_bytes() == CSV            # el raw de siempre
    arch = list((tmp_path / "oecd" / "archivo").glob("finmark_*.csv.gz"))
    assert len(arch) == 1 and gzip.decompress(arch[0].read_bytes()) == CSV
    oecd.fetch("finmark", "q", refresh=False)                                # caché de 20 h: ni descarga ni archivo
    assert len((tmp_path / "oecd" / "archivo" / "indice.jsonl").read_text().splitlines()) == 1


def test_oecd_qna_fetch_archiva(monkeypatch, tmp_path):
    _sin_red(monkeypatch, tmp_path, oecd_qna)
    oecd_qna.fetch(refresh=True)
    assert list((tmp_path / "oecd_qna" / "archivo").glob("gdpq_*.csv.gz"))
    assert json.loads((tmp_path / "oecd_qna" / "provenance.json").read_text())["bytes"] == len(CSV)
