"""Constructor del panel internacional armonizado (INT-0, tarea 3). Todo pasa por src/intl/data.load_dev (≤ 2004-12).

- `anual(con)`: país × año (JST). Valores del año tal cual (para describir regímenes ex post) y la fecha en que se
  habrían conocido (`disponible` = fin de año + 120 días).
- `mensual(con)`: país × fin de mes. Dos bloques:
  * variables "as of" (lo que se sabía al cierre de cada mes, con los retrasos de src/intl/lags.py): crecimiento
    (producción industrial, ventas, paro), inflación (IPC y subyacente), tipos, curva, bolsa, CLI y confianza;
  * resultados del mes (sin retraso; son lo que se mide, no lo que se usa para decidir): bolsa (precio OCDE, media
    mensual → suavizada, declarado), bono y letra construidos con src/intl/returns.py, y mercado AQR en USD.
Moneda local en todo; la conversión a EUR se hará con la divisa de cada país cuando se use.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import lags as Lg
from src.intl import returns as R

# Decisiones de INT-0 tras el Validador (docs/validation/2026-10-27_int0_datos.md, verificadas en local con
# research/int/diagnostico.json):
# - paro mensual OCDE de 9 países europeos interpolado desde encuestas trimestrales/anuales antes de ~1998 (A2) → se
#   excluye antes de 1998-01 (el crecimiento mensual de esos países usa la producción industrial);
# - CLI y crisisjst: filtros de dos lados / clasificación ex post → NO se usan como variables "as of" en desarrollo;
# - bolsa: el índice OCDE de FRA ya es de rentabilidad total (no se suma dividendo); los de DNK y JPN tienen rupturas →
#   sin rentabilidad mensual OCDE (se usa AQR desde 1986); bono mensual de ESP fuera antes de 1992 (el tipo largo no era
#   a 10 años).
PARO_INTERPOLADO = {"BEL", "DNK", "FRA", "GBR", "IRL", "ITA", "NLD", "PRT", "SWE"}
PARO_DESDE = pd.Timestamp("1998-01-01")
NO_TIEMPO_REAL = ("cli", "cli_d6")
BOLSA_OCDE_TR = {"FRA"}
BOLSA_OCDE_ROTA = {"DNK", "JPN"}
BONO_DESDE = {"ESP": pd.Timestamp("1992-01-01")}

JST_VARS = ["rgdpmad", "cpi", "unemp", "tloans", "gdp", "ltrate", "stir", "crisisjst", "eq_tr", "bond_tr", "bill_rate",
            "housing_tr", "eq_tr_real", "bond_tr_real", "bill_rate_real", "housing_tr_real", "eq_dp"]


def anual(con) -> pd.DataFrame:
    filas = []
    for c in D.PAISES:
        cols = {v: D.load_dev(con, f"jst_{c.lower()}_{v}") for v in JST_VARS}
        df = pd.DataFrame(cols)
        if df.empty:
            continue
        df.index = df.index.year
        df["pib_real_g"] = np.log(df["rgdpmad"]).diff()
        df["inflacion"] = np.log(df["cpi"]).diff()
        df["credito_pib"] = df["tloans"] / df["gdp"]
        df["d_credito_pib"] = df["credito_pib"].diff()
        df["disponible"] = pd.to_datetime(df.index.astype(str) + "-12-31") + pd.Timedelta(days=Lg.RETRASO_DIAS["jst"])
        df["pais"] = c
        filas.append(df.reset_index(names="año"))
    out = pd.concat(filas, ignore_index=True).set_index(["pais", "año"]).sort_index()
    if out.index.get_level_values("año").max() > D.DEV_END.year:
        raise D.FactorCutoffError("panel anual con años posteriores a DEV_END")
    return out


def _m(con, sid: str) -> pd.Series:
    return _mensual_completa(D.load_dev(con, sid))


def _mensual_completa(s: pd.Series) -> pd.Series:
    """Rejilla mensual completa (huecos = NaN), fechada a inicio de mes: así diff(k) es k MESES y no k observaciones
    (IPC trimestral de IRL hasta ~1975, meses sueltos que faltan en tipos). Falla si hay dos datos en el mismo mes."""
    if s.empty:
        return s
    p = s.index.to_period("M")
    if p.duplicated().any():
        raise ValueError(f"{s.name}: dos observaciones en el mismo mes")
    s = pd.Series(s.values, index=p, name=s.name).reindex(pd.period_range(p.min(), p.max(), freq="M"))
    return s.set_axis(s.index.to_timestamp(how="start"))


def mensual(con, desde: str = "1950-01-31") -> pd.DataFrame:
    rejilla = pd.date_range(desde, D.DEV_END, freq="ME")
    filas = []
    for c in D.PAISES:
        lc, i2 = c.lower(), D.ISO2[c]
        ip, retail = _m(con, f"oecd_ip_{lc}"), _m(con, f"oecd_retail_{lc}")
        unemp, cpi, core = _m(con, f"oecd_unemp_{lc}"), _m(con, f"oecd_cpi_{lc}_idx"), _m(con, f"oecd_cpicore_{lc}_idx")
        y10, y3m, share = _m(con, f"oecd_irlt_{lc}"), _m(con, f"oecd_ir3m_{lc}"), _m(con, f"oecd_share_{lc}")
        cli, bci, pol = _m(con, f"oecd_cli_{lc}"), _m(con, f"oecd_bci_{lc}"), _m(con, f"bis_cbpol_{i2}")
        if c in PARO_INTERPOLADO:
            unemp = unemp[unemp.index >= PARO_DESDE]
        dp = D.load_dev(con, f"jst_{lc}_eq_dp")
        # transformaciones sobre el índice de observación (regla 2), después "as of"
        v = {
            "ip_yoy": (np.log(ip).diff(12), f"oecd_ip_{lc}"),
            "ventas_yoy": (np.log(retail).diff(12), f"oecd_retail_{lc}"),
            "paro": (unemp, f"oecd_unemp_{lc}"),
            "paro_d12": (unemp.diff(12), f"oecd_unemp_{lc}"),
            "ipc_yoy": (np.log(cpi).diff(12), f"oecd_cpi_{lc}_idx"),
            "ipc_6m_anual": (2 * np.log(cpi).diff(6), f"oecd_cpi_{lc}_idx"),
            "sub_yoy": (np.log(core).diff(12), f"oecd_cpicore_{lc}_idx"),
            "tipo_10a": (y10, f"oecd_irlt_{lc}"),
            "tipo_3m": (y3m, f"oecd_ir3m_{lc}"),
            "tipo_oficial": (pol, f"bis_cbpol_{i2}"),
            "bolsa_12m": (np.log(share).diff(12), f"oecd_share_{lc}"),
            "cli": (cli, f"oecd_cli_{lc}"),
            "cli_d6": (cli.diff(6), f"oecd_cli_{lc}"),
            "confianza_emp": (bci, f"oecd_bci_{lc}"),
        }
        df = pd.DataFrame({k: Lg.asof(s, sid, rejilla) for k, (s, sid) in v.items()}, index=rejilla)
        df["curva"] = df["tipo_10a"] - df["tipo_3m"]
        # resultados del mes (fechados al fin de mes de referencia, sin retraso)
        fm = lambda s: s.set_axis(s.index + pd.offsets.MonthEnd(0)).reindex(rejilla)  # noqa: E731
        df["r_bolsa_precio"] = fm(np.log(share).diff())
        if c in BOLSA_OCDE_ROTA:
            df["r_bolsa_tr"] = np.nan
        elif c in BOLSA_OCDE_TR:
            df["r_bolsa_tr"] = df["r_bolsa_precio"]
        else:   # precio + dividendo anual de JST repartido por meses
            dp_m = pd.Series(dp.values, index=dp.index.year).reindex(df.index.year).to_numpy() / 12
            df["r_bolsa_tr"] = df["r_bolsa_precio"] + np.log1p(dp_m)
        bono = R.bono_tr_mensual(y10)
        if c in BONO_DESDE:
            bono = bono[bono.index >= BONO_DESDE[c]]
        df["r_bono"] = fm(bono)
        df["r_letra"] = fm(R.letra_tr_mensual(y3m))
        df["r_aqr_mkt_usd"] = fm(_m(con, f"aqr_mkt_{lc}_m"))
        df["inflacion_mes"] = fm(np.log(cpi).diff())
        df["pais"] = c
        filas.append(df.reset_index(names="fecha"))
    out = pd.concat(filas, ignore_index=True).set_index(["pais", "fecha"]).sort_index()
    D.check(out.reset_index(level=0, drop=True))
    return out
