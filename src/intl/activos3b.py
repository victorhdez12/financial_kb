"""INT-3b / INT-3c (docs/int/INT3b_prerregistro_v0.md): rentabilidades anuales (≤ 2004) de los activos nuevos y
descomposiciones de la rentabilidad. Todo pasa por src/intl/data.py (corte ≤ 2004-12). Este módulo NO lee regímenes:
solo construye variables de activo; el cruce con los regímenes se hace únicamente en la corrida prerregistrada.

Bloques (rentabilidades en fracción por año natural; "real" = deflactada con el IPC indicado):
- `mundial`: año → materias primas AQR "Commodities for the Long Run" (1877-; cartera de igual peso; exceso sobre letras,
  descompuesto en spot en exceso + carry ajustado por tipos = "roll"), AQR "Century" materias primas (1927-), petróleo
  (precio spot, BoE, 1861-; NO es un activo invertible: es un indicador) y oro en USD. Colateral y deflactor: letras e IPC
  de EE. UU. (JST).
- `oro_panel`: país × año → oro real en moneda local = precio en USD × tipo de cambio JST (moneda local por USD),
  deflactado con el IPC del país.
- `credito`: país (USA, GBR) × año → bono corporativo real y exceso sobre el bono del Estado.
  USA: Damodaran (Baa y T-bond a 10 años; rentabilidades construidas por Damodaran a partir de rendimientos).
  GBR: aproximación propia desde rendimientos anuales del BoE (corporativo y consol), bono a la par a n = 20 años,
  r = y_{t−1} − D·Δy + ½·C·Δy², la MISMA fórmula para los dos (el error de la aproximación se compensa en parte en el
  exceso). Declarado como construido.
- `descomp`: país × año (JST) → descomposición EXACTA en logaritmos de la rentabilidad total real:
  bolsa  = ingreso [ln(1+tr) − ln(1+g)] + dividendo real [ln(1+g) + Δln(D/P) − ln(1+π)] + valoración [−Δln(D/P)]
  bonos  = cupón real [ln(1+y_{t−1}) − ln(1+π)] + capital [ln(1+tr) − ln(1+y_{t−1})]
  vivienda = alquiler [ln(1+tr) − ln(1+g)] + precio real [ln(1+g) − ln(1+π)]
  con g la plusvalía de precio de JST y π la inflación del IPC de JST.
  Materias primas (INT-3c): suma anual de los meses, exacta: exceso = spot en exceso + carry ajustado (identidad de AQR).
- HIPERINFLACIÓN: se devuelve la inflación del año para que la corrida aplique la regla prerregistrada (fuera los
  país-años con inflación > 50 %); este módulo no filtra nada.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl.returns import duracion_convexidad

N_BONO_UK = 20


def _anual(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = s.index.year
    return s


def compuesto_anual(pct_mensual: pd.Series, min_meses: int = 12) -> pd.Series:
    """Rentabilidad anual compuesta (fracción) de una serie mensual en %; NaN si el año no tiene 12 meses."""
    r = pct_mensual / 100
    g = r.groupby(r.index.year)
    out = g.apply(lambda x: float(np.prod(1 + x) - 1))
    return out.where(g.size() >= min_meses)


def suma_anual(pct_mensual: pd.Series, min_meses: int = 12) -> pd.Series:
    r = pct_mensual / 100
    g = r.groupby(r.index.year)
    return g.sum().where(g.size() >= min_meses)


def tr_desde_rendimiento(y_pct: pd.Series, n: int = N_BONO_UK) -> pd.Series:
    """Rentabilidad anual aproximada de un bono a la par a n años con rendimientos anuales en %: cupón y_{t−1} más
    variación de precio por duración y convexidad (pago anual)."""
    y = y_pct.sort_index() / 100
    d, c = duracion_convexidad(y.shift(1).to_numpy(), n=n, f=1)
    dy = y.diff().to_numpy()
    return pd.Series(y.shift(1).to_numpy() - d * dy + 0.5 * c * dy ** 2, index=y.index)


def _real(nominal: pd.Series, inflacion: pd.Series) -> pd.Series:
    return (1 + nominal) / (1 + inflacion.reindex(nominal.index)) - 1


def _jst(con, pais: str, var: str) -> pd.Series:
    return _anual(D.load_dev(con, f"jst_{pais.lower()}_{var}"))


def inflacion_jst(con, pais: str) -> pd.Series:
    cpi = _jst(con, pais, "cpi")
    return cpi / cpi.shift(1) - 1


def oro_usd_fin_de_año(con) -> pd.Series:
    """Precio del oro en USD por año: ≤ 1959 media anual de MeasuringWorth (precio oficial fijo casi todo el periodo:
    20,67 $ 1834-1932 y 35 $ 1934-1967); ≥ 1960 media de diciembre del Banco Mundial (aprox. de fin de año)."""
    mw = _anual(D.load_dev(con, "gold_mw_newyork_usd_a"))
    wb = D.load_dev(con, "gold_wb_usd_m")
    dic = wb[wb.index.month == 12]
    dic.index = dic.index.year
    return pd.concat([mw[mw.index <= 1959], dic[dic.index >= 1960]]).sort_index()


def mundial(con) -> pd.DataFrame:
    pi_us = inflacion_jst(con, "USA")
    letra_us = _jst(con, "USA", "bill_rate")
    clr = {k: D.load_dev_curado(f"aqr_clr_{k}_m") for k in ("ew_xret", "ew_xspot", "ew_carry_adj")}
    f = pd.DataFrame({"mp_exceso": compuesto_anual(clr["ew_xret"]), "mp_exceso_suma": suma_anual(clr["ew_xret"]),
                      "mp_spot_exceso_suma": suma_anual(clr["ew_xspot"]),
                      "mp_carry_suma": suma_anual(clr["ew_carry_adj"])})
    f["mp_real"] = _real(f["mp_exceso"] + letra_us.reindex(f.index), pi_us)
    cfp = compuesto_anual(D.load_dev(con, "aqr_cfp_commodities_market_m"))
    f = f.join(pd.DataFrame({"cfp_exceso": cfp}), how="outer")
    f["cfp_real"] = _real(f["cfp_exceso"] + letra_us.reindex(f.index), pi_us)
    oil = _anual(D.load_dev(con, "boe_uk_oil_price_usd_a"))
    f = f.join(pd.DataFrame({"petroleo_real": _real(oil / oil.shift(1) - 1, pi_us)}), how="outer")
    oro = oro_usd_fin_de_año(con)
    f = f.join(pd.DataFrame({"oro_usd_real": _real(oro / oro.shift(1) - 1, pi_us)}), how="outer")
    f.index.name = "año"
    return f[f.index <= D.DEV_END.year]


def oro_panel(con, paises: list[str]) -> pd.DataFrame:
    oro = oro_usd_fin_de_año(con)
    filas = []
    for c in paises:
        xr = _jst(con, c, "xrusd")
        loc = (oro * xr).dropna()
        r = _real(loc / loc.shift(1) - 1, inflacion_jst(con, c))
        filas.append(pd.DataFrame({"pais": c, "año": r.index, "oro_real_local": r.values,
                                   "inflacion": inflacion_jst(con, c).reindex(r.index).values}))
    return pd.concat(filas, ignore_index=True).dropna()


def credito(con, n_uk: int = N_BONO_UK) -> pd.DataFrame:
    pi = {c: inflacion_jst(con, c) for c in ("USA", "GBR")}
    baa = _anual(D.load_dev(con, "damodaran_baa_corp_tr"))
    tb = _anual(D.load_dev(con, "damodaran_tbond_10y_tr"))
    us = pd.DataFrame({"corp": baa, "gob": tb})
    corp_uk = tr_desde_rendimiento(_anual(D.load_dev(con, "boe_uk_corp_bond_yield_a")), n=n_uk)
    gob_uk = tr_desde_rendimiento(_anual(D.load_dev(con, "boe_uk_consol_yield_a")), n=n_uk)
    uk = pd.DataFrame({"corp": corp_uk, "gob": gob_uk}).dropna()
    filas = []
    for c, f in (("USA", us), ("GBR", uk)):
        f = f.dropna()
        filas.append(pd.DataFrame({"pais": c, "año": f.index, "corp_real": _real(f["corp"], pi[c]).values,
                                   "exceso_credito": (f["corp"] - f["gob"]).values}))
    return pd.concat(filas, ignore_index=True).dropna()


def descomp(con, paises: list[str]) -> pd.DataFrame:
    filas = []
    for c in paises:
        v = {k: _jst(con, c, k) for k in ("eq_tr", "eq_capgain", "eq_dp", "bond_tr", "ltrate", "housing_tr",
                                          "housing_capgain")}
        f = pd.DataFrame(v)
        lpi = np.log1p(inflacion_jst(con, c)).reindex(f.index)
        dlndp = np.log(f["eq_dp"]).diff()
        f2 = pd.DataFrame(index=f.index)
        f2["eq_ingreso"] = np.log1p(f["eq_tr"]) - np.log1p(f["eq_capgain"])
        f2["eq_div_real"] = np.log1p(f["eq_capgain"]) + dlndp - lpi
        f2["eq_valoracion"] = -dlndp
        f2["eq_total"] = np.log1p(f["eq_tr"]) - lpi
        cupon = f["ltrate"].shift(1) / 100
        f2["bono_cupon_real"] = np.log1p(cupon) - lpi
        f2["bono_capital"] = np.log1p(f["bond_tr"]) - np.log1p(cupon)
        f2["bono_total"] = np.log1p(f["bond_tr"]) - lpi
        f2["viv_alquiler"] = np.log1p(f["housing_tr"]) - np.log1p(f["housing_capgain"])
        f2["viv_precio_real"] = np.log1p(f["housing_capgain"]) - lpi
        f2["viv_total"] = np.log1p(f["housing_tr"]) - lpi
        f2 = f2.replace([np.inf, -np.inf], np.nan)          # D/P = 0 o plusvalía = −100 % (guerras, hiperinflación)
        f2["inflacion"] = inflacion_jst(con, c).reindex(f2.index)
        f2["pais"] = c
        filas.append(f2.reset_index(names="año"))
    return pd.concat(filas, ignore_index=True)


def credito_carry(con) -> pd.DataFrame:
    """Parte "carry" del exceso del crédito: diferencial de rendimientos al cierre del año anterior (fracción).
    GBR: corporativo − consol (BoE, anual). USA: Moody's Baa − Tesoro 10 años (FRED BAA y GS10, diciembre); GS10
    empieza en 1953 → carry de USA desde 1954. El resto del exceso es la parte de precio (variación del diferencial)."""
    uk = (_anual(D.load_dev(con, "boe_uk_corp_bond_yield_a")) - _anual(D.load_dev(con, "boe_uk_consol_yield_a"))) / 100
    baa, gs = D.load_dev(con, "BAA"), D.load_dev(con, "GS10")
    sp = (baa - gs).dropna()
    sp = sp[sp.index.month == 12]
    sp.index = sp.index.year
    filas = [pd.DataFrame({"pais": "GBR", "año": uk.index + 1, "carry": uk.values}),
             pd.DataFrame({"pais": "USA", "año": sp.index + 1, "carry": (sp / 100).values})]
    return pd.concat(filas, ignore_index=True).dropna()


def pib_nivel(con, paises: list[str]) -> pd.DataFrame:
    """PIB real en nivel (PIB per cápita de Maddison × población, JST) para ponderar la cuota mundial."""
    filas = []
    for c in paises:
        v = _jst(con, c, "rgdpmad") * _jst(con, c, "pop")
        filas.append(pd.DataFrame({"pais": c, "año": v.index, "pib": v.values}))
    return pd.concat(filas, ignore_index=True).dropna()
