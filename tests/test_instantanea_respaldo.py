"""Respaldo de la instantánea ≤ 2004 (src/intl/data.py; docs/int/OCDE_deriva_umbrales.md, §3): copia xz en el repo con
el mismo sha256; lectura con caída al respaldo si el archivo falta o está corrupto; restauración que nunca toca una
copia válida; y la ruta del warehouse (`load_dev` sobre db.connect) no depende de la instantánea."""
import hashlib
import json
import lzma
import os
import warnings

import pandas as pd
import pytest

from src.intl import data as D
from src.warehouse import db


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Repo y $FIN_DATA_ROOT de juguete: parquet válido en el archivo, manifiesto y respaldo creado con la API."""
    repo, raiz = tmp_path / "repo", tmp_path / "archivo"
    (repo / "research" / "int").mkdir(parents=True)
    monkeypatch.setattr(db, "REPO", repo)
    monkeypatch.setattr(db, "DATA_ROOT", raiz)
    df = pd.DataFrame({"series_id": ["oecd_irlt_bel"] * 3 + ["oecd_ip_gbr"] * 3,
                       "date": pd.to_datetime(["2004-10-01", "2004-11-01", "2004-12-01"] * 2).date,
                       "value": [4.1, 4.0, 3.9, 101.0, 102.0, 103.0]})
    p = raiz / "intl" / "snapshots" / "dev_prueba.parquet"
    p.parent.mkdir(parents=True)
    df.to_parquet(p, index=False)
    os.chmod(p, 0o444)
    man = repo / "research" / "int" / "instantanea_prueba.json"
    man.write_text(json.dumps({"ruta": "intl/snapshots/dev_prueba.parquet", "sha256": D.sha256(p),
                               "cobertura": ["oecd_irlt_bel", "oecd_ip_gbr"]}))
    D._leer_instantanea.cache_clear()
    resp = D.respaldar_instantanea(man)
    yield {"man": man, "p": p, "df": df, "resp": resp, "repo": repo}
    D._leer_instantanea.cache_clear()


def _corromper(p):
    os.chmod(p, 0o644)
    p.write_bytes(p.read_bytes()[:-10] + b"0123456789")


def test_respaldo_declarado_y_reproducible(entorno):
    r, man = entorno["resp"], json.loads(entorno["man"].read_text())
    assert man["respaldo"] == r and r["ruta"] == "research/int/snapshots/dev_prueba.parquet.xz"
    x = entorno["repo"] / r["ruta"]
    assert D.sha256(x) == r["sha256_xz"] and hashlib.sha256(lzma.decompress(x.read_bytes())).hexdigest() == man["sha256"]
    assert D.respaldar_instantanea(entorno["man"]) == r                               # idempotente
    assert all(ok for ok, _ in D.verificar_instantanea(entorno["man"]).values())
    assert D.origen_instantanea(entorno["man"]) == "archivo"


@pytest.mark.parametrize("dano", ["falta", "corrupta"])
def test_lee_del_respaldo_si_el_archivo_falla_y_restaura(entorno, dano):
    p, man = entorno["p"], entorno["man"]
    if dano == "falta":
        os.chmod(p, 0o644)
        p.unlink()
    else:
        _corromper(p)
    assert not D.verificar_instantanea(man)["archivo"][0]
    with pytest.warns(D.InstantaneaDesdeRespaldo):
        df = D.leer_instantanea(man)
    pd.testing.assert_frame_equal(df, entorno["df"])
    assert D.origen_instantanea(man) == "respaldo" and D.instantanea_disponible(man)
    msg = D.restaurar_instantanea(man)
    assert msg.startswith("restaurada")
    assert D.sha256(p) == json.loads(man.read_text())["sha256"] and not p.stat().st_mode & 0o222
    apartadas = list(p.parent.glob("dev_prueba.parquet.corrupta-*"))
    assert len(apartadas) == (1 if dano == "corrupta" else 0)                         # la corrupta no se borra
    assert D.origen_instantanea(man) == "archivo"
    with warnings.catch_warnings():
        warnings.simplefilter("error", D.InstantaneaDesdeRespaldo)
        pd.testing.assert_frame_equal(D.leer_instantanea(man), entorno["df"])


def test_restaurar_no_toca_una_copia_valida(entorno):
    antes = entorno["p"].stat()
    assert D.restaurar_instantanea(entorno["man"]).startswith("nada que hacer")
    assert entorno["p"].stat().st_ino == antes.st_ino and entorno["p"].stat().st_mtime_ns == antes.st_mtime_ns


def test_respaldo_corrupto_no_se_usa(entorno):
    x = entorno["repo"] / entorno["resp"]["ruta"]
    _corromper(x)
    assert not D.verificar_instantanea(entorno["man"])["respaldo"][0]
    assert D.origen_instantanea(entorno["man"]) == "archivo"                          # el archivo sigue valiendo
    _corromper(entorno["p"])
    assert not D.instantanea_disponible(entorno["man"])
    with pytest.raises(D.InstantaneaNoDisponible, match="sin instantánea válida"):
        D.leer_instantanea(entorno["man"])
    with pytest.raises(D.InstantaneaNoDisponible):
        D.restaurar_instantanea(entorno["man"])


def test_connect_instantanea_con_respaldo(entorno):
    os.chmod(entorno["p"], 0o644)
    entorno["p"].unlink()
    with pytest.warns(D.InstantaneaDesdeRespaldo):
        con = D.connect_instantanea(entorno["man"])
    try:
        assert D.load_dev(con, "oecd_irlt_bel").tolist() == [4.1, 4.0, 3.9]
    finally:
        con.close()


def test_respaldo_real_en_el_repo():
    """El respaldo del repo existe y, descomprimido, tiene el sha256 del manifiesto (no necesita $FIN_DATA_ROOT)."""
    man = json.loads(D.INSTANTANEA.read_text())
    r = man["respaldo"]
    x = db.REPO / r["ruta"]
    assert x.exists() and D.sha256(x) == r["sha256_xz"]
    assert hashlib.sha256(lzma.decompress(x.read_bytes())).hexdigest() == man["sha256"]
    assert x.stat().st_size < 1_000_000                                    # cabe en git sin LFS


@pytest.mark.skipif(not db.WAREHOUSE.exists(), reason="sin warehouse real")
def test_load_dev_del_warehouse_no_depende_de_la_instantanea(tmp_path, monkeypatch):
    """Sin ninguna copia de la instantánea (ni archivo ni respaldo), la ruta por defecto sigue funcionando."""
    falso = tmp_path / "no_existe.json"
    monkeypatch.setattr(D, "INSTANTANEA", falso)
    monkeypatch.delenv("FIN_DEV_FUENTE", raising=False)
    con = D.connect()
    try:
        s = D.load_dev(con, "oecd_irlt_bel")
    finally:
        con.close()
    assert not s.empty and s.index.max() <= D.DEV_END
    assert not D.instantanea_disponible(falso)
