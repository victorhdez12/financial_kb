"""Percentil común de las cifras descriptivas del panel (presentación; no lo usa ninguna regla ni registro congelado).

Definición única: percentil empírico de rango = **proporción (0-100) de observaciones ≤ el valor actual**, sobre una
base explícita:

- `hasta`: fecha de corte (incluida). Por defecto, la última observación de la serie.
- `ventana`: `None` = toda la historia disponible hasta el corte; `pd.DateOffset` (p. ej. `years=3`) = solo las
  observaciones posteriores a corte − ventana; `int` = las últimas N observaciones (p. ej. 156 semanas del COT).
- `frecuencia`: `None` = la nativa de la serie (diaria, semanal...); `"M"` = un dato por mes (el último de cada mes;
  el mes en curso, con el último dato disponible).
- NaN: se descartan antes de todo. Con menos de `min_obs` observaciones en la base, no hay percentil (None).
- Valor actual: por defecto el último de la base; se puede pasar otro (`valor`), que se compara con la base tal cual.

Quedan FUERA (congelados, con su propia definición documentada): el nowcast INT-8b y el termómetro (rango medio frente
a 1960-2004, `nowcast_vivo.py`, `termometro_vivo.py`, `revisiones.py`) y el monitor de crédito `src/regime/credit.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Percentil:
    valor: float | None        # 0-100, sin redondear
    desde: pd.Timestamp | None  # primera observación de la base
    n: int                      # observaciones en la base
    frecuencia: str             # "nativa" o "mensual"
    ventana: str | None         # None = toda la historia; si no, texto («3 años», «156 obs.»)

    def redondeado(self, dec: int = 0) -> float | None:
        return None if self.valor is None else round(self.valor, dec)


def _texto_ventana(ventana) -> str | None:
    if ventana is None:
        return None
    if isinstance(ventana, int):
        return f"{ventana} obs."
    años = getattr(ventana, "years", 0) or 0
    meses = getattr(ventana, "months", 0) or 0
    if años and not meses:
        return f"{años} año" + ("s" if años != 1 else "")
    if meses and not años:
        return f"{meses} mes" + ("es" if meses != 1 else "")
    return str(ventana)


def base(s: pd.Series, *, hasta=None, ventana=None, frecuencia: str | None = None) -> pd.Series:
    """Las observaciones sobre las que se calcula el percentil (ordenadas, sin NaN, ≤ hasta, ventana aplicada)."""
    x = pd.Series(s, dtype=float).dropna().sort_index()
    if hasta is not None:
        x = x[x.index <= pd.Timestamp(hasta)]
    if frecuencia == "M":
        x = x.groupby(x.index.to_period("M")).last()
        x.index = x.index.to_timestamp()
    elif frecuencia is not None:
        raise ValueError(f"frecuencia no soportada: {frecuencia!r} (None = nativa, 'M' = mensual)")
    if x.empty or ventana is None:
        return x
    if isinstance(ventana, int):
        return x.iloc[-ventana:] if ventana > 0 else x.iloc[:0]
    return x[x.index > x.index[-1] - ventana]


def calcular(s: pd.Series, valor: float | None = None, *, hasta=None, ventana=None, frecuencia: str | None = None,
             min_obs: int = 24) -> Percentil:
    """Percentil con su base (ver el docstring del módulo)."""
    x = base(s, hasta=hasta, ventana=ventana, frecuencia=frecuencia)
    frec, vent = ("mensual" if frecuencia == "M" else "nativa"), _texto_ventana(ventana)
    if len(x) < max(min_obs, 1):
        return Percentil(None, x.index[0] if len(x) else None, len(x), frec, vent)
    v = float(x.iloc[-1]) if valor is None else float(valor)
    if v != v:   # valor NaN → sin percentil (antes daba 0)
        return Percentil(None, x.index[0], len(x), frec, vent)
    return Percentil(float(100 * (x <= v).mean()), x.index[0], len(x), frec, vent)


def percentil(s: pd.Series, valor: float | None = None, *, hasta=None, ventana=None, frecuencia: str | None = None,
              min_obs: int = 24, dec: int | None = 0) -> float | None:
    """Solo la cifra (redondeada a `dec` decimales; `dec=None` sin redondear)."""
    p = calcular(s, valor, hasta=hasta, ventana=ventana, frecuencia=frecuencia, min_obs=min_obs)
    return p.valor if dec is None else p.redondeado(dec)


def etiqueta(p: float | None, desde=None, ventana: str | None = None, frecuencia: str | None = None) -> str:
    """Texto corto con la base visible: «p79 · desde 2023-10», «p99 · 3 años», «p34 · mensual desde 1950»."""
    if p is None:
        return "p—"
    t = f"p{int(round(float(p)))}"
    if ventana:
        return f"{t} · {ventana}"
    pre = "mensual " if frecuencia in ("M", "mensual") else ""
    if desde is None or desde == "":
        return t + (f" · {pre.strip()}" if pre else "")
    d = desde if isinstance(desde, str) else f"{pd.Timestamp(desde):%Y-%m}"
    return f"{t} · {pre}desde {d}"
