"""Corte técnico del panel internacional (INT-0): en desarrollo, ningún dato con fecha ≥ 2005-01, para ningún país.
Mismo límite y misma comprobación que src/factors/data.py (DEV_END, check). `load_dev` es la única entrada de datos del
warehouse en src/intl/ (un test lo comprueba) y falla cerrado con series fuera de las familias permitidas.

Fuente de desarrollo (`connect(fuente=...)`; por defecto la variable de entorno FIN_DEV_FUENTE o "warehouse"):
- "warehouse": `obs_latest` del warehouse (última publicación; la OCDE revisa en origen series ≤ 2004 sin avisar);
- "instantanea": la instantánea fechada e inmutable de las series ≤ 2004 con las que se congelaron las referencias de
  INT-8b y del termómetro (manifiesto en el repo, research/int/instantanea_dev_2004.json; parquet fuera del repo en
  $FIN_DATA_ROOT/intl/snapshots/; sha256 comprobado al abrirla; docs/int/INT8b_nowcast.md, «Revisiones de datos»).
  Con ella, `load_dev` falla si se pide una serie que la instantánea no cubre (nunca devuelve vacío en silencio).
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
from pathlib import Path

import duckdb
import pandas as pd

from src.factors.data import DEV_END, FactorCutoffError, check  # noqa: F401  (mismo corte para todo el proyecto)
from src.warehouse import db

PAISES = ["AUS", "BEL", "CAN", "CHE", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "IRL", "ITA", "JPN", "NLD", "NOR", "PRT",
          "SWE", "USA"]
ISO2 = {"AUS": "au", "BEL": "be", "CAN": "ca", "CHE": "ch", "DEU": "de", "DNK": "dk", "ESP": "es", "FIN": "fi", "FRA": "fr",
        "GBR": "gb", "IRL": "ie", "ITA": "it", "JPN": "jp", "NLD": "nl", "NOR": "no", "PRT": "pt", "SWE": "se", "USA": "us"}

FAMILIAS: dict[str, str] = {
    r"jst_[a-z]{3}_\w+": "JST Macrohistory R6 (anual, revisado, CC BY-NC-SA)",
    r"oecd_(ip|retail|unemp|irlt|ir3m|ircall|share|cli|bci|cci)_[a-z]{3}": "OCDE mensual (CC BY 4.0)",
    r"oecd_(cpi|cpicore)_[a-z]{3}_(idx|yoy)": "OCDE IPC mensual (CC BY 4.0)",
    r"bis_cbpol_[a-z]{2}": "BIS tipo oficial mensual",
    r"imf_ifs_[a-z]{3}_\w+": "FMI IFS mensual",
    r"aqr_mkt_[a-z]{3}_m": "AQR mercado por país, mensual, USD (sin redistribución)",
    r"USREC": "NBER: recesiones de EE. UU. (solo como contraste externo del fechado, nunca como variable)",
    # INT-3b/INT-3c (docs/int/INT3b_prerregistro_v0.md): activos y componentes de precio mundial o de EE. UU./R. U.
    r"aqr_clr_\w+_m": "AQR Commodities for the Long Run, mensual 1877- (sin redistribución; curado, ver load_dev_curado)",
    r"aqr_cfp_commodities_market_m": "AQR Century of Factor Premia, materias primas largo, mensual 1926- (sin redistribución)",
    r"damodaran_(baa_corp_tr|tbond_10y_tr|tbill_3m|gold_ret|inflation)": "Damodaran histretSP, anual 1928-",
    r"gold_mw_newyork_usd_a|gold_wb_usd_m": "Oro en USD: MeasuringWorth (media anual) y Banco Mundial (media mensual)",
    r"boe_uk_(corp_bond_yield_a|consol_yield_a|oil_price_usd_a|cpi_a)": "BoE A Millennium of Macroeconomic Data (UK), anual",
    r"BAA|AAA|GS10": "FRED: Moody's Baa/Aaa y Tesoro 10 años, mensual",
    # INT-6 (docs/int/INT6_prerregistro_v1.md §10, decisión 4): diferencial corporativo del R. U., mensual 1854- (K2)
    r"boe_uk_corp_bond_spread_m": "BoE A Millennium of Macroeconomic Data (UK), diferencial corporativo mensual, pp",
    # Termómetro de recesión informativo (docs/int/TERMOMETRO_diseno_v1.md)
    r"oecd_gdpq_[a-z]{3}": "OCDE Quarterly National Accounts, PIB real en volumen, trimestral (CC BY 4.0; curado, ver load_dev_curado)",
    r"bis_creditgap_[a-z]{2}_ratio": "BIS crédito total al sector privado no financiero / PIB, trimestral",
    # INT-7 (docs/int/INT7_prerregistro_v1.md §9, decisión 4): Shiller, EE. UU., mensual 1871-
    r"shiller_(cape|real_price|real_earnings|real_dividend|real_stock_tr_ret_m)": "Shiller ie_data (EE. UU., mensual)",
    # P-DEV-INT12 v1.0 (docs/int/INT12_prerregistro_v1.md §1): mercado de EE. UU. diario, letra y tipo largo de Shiller
    r"aqr_mkt_usa_d|TB3MS|shiller_gs10": "INT-12: AQR mercado EE. UU. diario (CRSP), FRED TB3MS, Shiller tipo largo",
}
_RX = [re.compile(f"^(?:{p})$") for p in FAMILIAS]


def permitida(sid: str) -> bool:
    return any(rx.match(sid) for rx in _RX)


def load_dev(con, sid: str) -> pd.Series:
    """Serie `sid` con fechas ≤ DEV_END; vacía si no existe. Error si no es de una familia permitida o si se cuela algo
    posterior (filtro SQL + comprobación). Con la conexión de la instantánea, error si `sid` no está cubierta."""
    if not permitida(sid):
        raise FactorCutoffError(f"{sid}: no está en las familias del panel internacional (src/intl/data.py)")
    if db.has_table(con, "instantanea_cobertura") and not con.execute(
            "select count(*) from instantanea_cobertura where series_id = ?", [sid]).fetchone()[0]:
        raise FactorCutoffError(f"{sid}: no está en la instantánea de desarrollo ({INSTANTANEA.name}); usa el warehouse")
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date <= ? "
                     "order by date", [sid, DEV_END.date()]).df()
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]), name=sid)
    if s.index.duplicated().any():
        raise FactorCutoffError(f"{sid}: fechas repetidas en obs_latest (no se elige una en silencio)")
    check(s)
    return s


def load_dev_curado(sid: str, fuente: str | None = None) -> pd.Series:
    """Como `load_dev`, pero desde la capa curada ($FIN_DATA_ROOT/curated/<fuente>/<sid>.parquet) para series ya
    descargadas que todavía no están en el warehouse (se cargarán en la próxima reconstrucción). Mismo corte y mismas
    familias permitidas. Con `fuente="instantanea"` (o FIN_DEV_FUENTE), el PIB trimestral sale de la instantánea."""
    if not permitida(sid):
        raise FactorCutoffError(f"{sid}: no está en las familias del panel internacional (src/intl/data.py)")
    if _fuente(fuente) == "instantanea" and sid.startswith("oecd_gdpq_"):
        con = connect_instantanea()
        try:
            return load_dev(con, sid)
        finally:
            con.close()
    fuente = {"aqr_clr_": "aqr_clr", "oecd_gdpq_": "oecd_qna"}.get(next((k for k in ("aqr_clr_", "oecd_gdpq_")
                                                                       if sid.startswith(k)), ""))
    if fuente is None:
        raise FactorCutoffError(f"{sid}: sin carpeta curada conocida; usa load_dev")
    df = pd.read_parquet(db.DATA_ROOT / "curated" / fuente / f"{sid}.parquet")
    df = df[pd.to_datetime(df["date"]) <= DEV_END]
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]), name=sid).sort_index()
    if s.index.duplicated().any():
        raise FactorCutoffError(f"{sid}: fechas repetidas en la capa curada")
    check(s)
    return s


# ---------------------------------------------------------------- instantánea de desarrollo (≤ 2004, inmutable)
INSTANTANEA = db.REPO / "research" / "int" / "instantanea_dev_2004.json"
FUENTES = ("warehouse", "instantanea")


class InstantaneaNoDisponible(FileNotFoundError):
    """Falta el parquet de la instantánea (está fuera del repo) o su sha256 no coincide con el manifiesto."""


def _fuente(fuente: str | None) -> str:
    f = fuente or os.environ.get("FIN_DEV_FUENTE") or "warehouse"
    if f not in FUENTES:
        raise ValueError(f"fuente de desarrollo desconocida: {f} (válidas: {FUENTES})")
    return f


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ruta_instantanea(manifiesto: Path = INSTANTANEA) -> Path:
    """Ruta del parquet: `ruta` del manifiesto, relativa a $FIN_DATA_ROOT."""
    return db.DATA_ROOT / json.loads(Path(manifiesto).read_text())["ruta"]


@functools.lru_cache(maxsize=4)
def _leer_instantanea(manifiesto: str, _mtime: float) -> pd.DataFrame:
    if not Path(manifiesto).exists():
        raise InstantaneaNoDisponible(f"falta el manifiesto {manifiesto}")
    man = json.loads(Path(manifiesto).read_text())
    p = db.DATA_ROOT / man["ruta"]
    if not p.exists():
        raise InstantaneaNoDisponible(f"falta la instantánea {p} (fuera del repo; manifiesto {manifiesto})")
    if (h := sha256(p)) != man["sha256"]:
        raise InstantaneaNoDisponible(f"{p}: sha256 {h} ≠ manifiesto {man['sha256']} (la instantánea es inmutable)")
    df = pd.read_parquet(p)
    if pd.to_datetime(df["date"]).max() > DEV_END:
        raise FactorCutoffError(f"{p}: datos posteriores a DEV_END")
    return df


def leer_instantanea(manifiesto: Path = INSTANTANEA) -> pd.DataFrame:
    """Filas (series_id, date, value) de la instantánea, tras comprobar su sha256 con el manifiesto."""
    m = Path(manifiesto)
    return _leer_instantanea(str(m), m.stat().st_mtime if m.exists() else 0.0).copy()


def instantanea_disponible(manifiesto: Path = INSTANTANEA) -> bool:
    try:
        leer_instantanea(manifiesto)
        return True
    except InstantaneaNoDisponible:
        return False


def connect_instantanea(manifiesto: Path = INSTANTANEA) -> duckdb.DuckDBPyConnection:
    """Conexión en memoria con `obs_latest` = la instantánea (misma interfaz que el warehouse para `load_dev`) y la
    tabla `instantanea_cobertura` (series cubiertas: `cobertura` del manifiesto, también las que no tienen datos
    ≤ 2004, que salen vacías como en el warehouse)."""
    df = leer_instantanea(manifiesto)  # noqa: F841  (lo lee duckdb por nombre)
    cob = pd.DataFrame({"series_id": json.loads(Path(manifiesto).read_text()).get("cobertura")  # noqa: F841
                        or sorted(df.series_id.unique())})
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest as select series_id, cast(date as date) as date, value from df")
    con.execute("create table instantanea_cobertura as select distinct series_id from cob")
    return con


def connect(fuente: str | None = None):
    """Conexión de desarrollo: warehouse (por defecto) o la instantánea ≤ 2004 (ver arriba)."""
    if _fuente(fuente) == "instantanea":
        return connect_instantanea()
    return db.connect(read_only=True)
