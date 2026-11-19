"""D1 en vivo (docs/factors/D1_tendencia_diaria_spec.md v1.0 §2 y §6): decisión DIARIA tras el cierre de EE. UU.
Misma regla que el desarrollo (src/factors/d1.py: tendencia, volatilidad, objetivo, aplica_banda), sin parámetros nuevos:
- Cierres AJUSTADOS (dividendos y splits) de los 5 ETF de config/alpaca_etfs_d1.json (SPY, VEA, TLT, GLD, DBC):
  barras diarias de Alpaca (feed IEX, `adjustment=all`) o el archivo (~/financial_archive/mercados/
  precios_diarios.parquet, cierre ajustado de Yahoo) si tiene los 5. La última barra debe ser la del cierre decidido.
- s y σ con los cierres hasta el del día d (incluido); objetivo = pasos 2-3; banda de 3 pp frente a los pesos
  TEÓRICOS vigentes (los de la última decisión registrada, derivados con los cierres hasta d; el efectivo de la cuenta no
  rinde: deriva con 0). `opera` = algún activo cruza la banda. El espejo (src/broker/espejo.py) lleva la cuenta a `d1`.
- Registro propio e inmutable research/paper/decisiones_d1.jsonl (una línea por sesión); reglas de registro en
  scripts/paper_decision_d1.py (exige research/paper/D1_ACTIVO, árbol limpio, commit + push).
Diferencias declaradas con el desarrollo: precios de ETF (no índices), feed IEX, órdenes en d + 1 (no al cierre de d),
el efectivo de Alpaca no rinde.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import d1 as M

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "research" / "paper" / "decisiones_d1.jsonl"
ACTIVO_D1 = REPO / "research" / "paper" / "D1_ACTIVO"
MAPEO = REPO / "config" / "alpaca_etfs_d1.json"
ARCHIVO = Path("~/financial_archive/mercados/precios_diarios.parquet").expanduser()
SPEC = "docs/factors/D1_tendencia_diaria_spec.md v1.0"
TRAMOS = ("us", "xus", "bonos", "oro", "mp")
HISTORIA = max(M.VENTANAS) + 1                # cierres necesarios (252 rentabilidades)


class SinDatos(RuntimeError):
    """Faltan cierres (historia corta, activo ausente o la última barra no es la del cierre)."""


@dataclass
class DecisionD1:
    cierre: str
    opera: bool
    d1: dict[str, float]                 # pesos tras la banda (los que rigen desde d + 1); el resto, efectivo
    objetivo: dict[str, float]           # pasos 2-3 antes de la banda
    actual: dict[str, float]             # pesos teóricos vigentes derivados hasta el cierre
    s: dict[str, float]
    sigma: dict[str, float]
    motivo: str
    fuente: str
    ultimo_cierre_previo: str | None = None
    spec: str = SPEC
    extra: dict = field(default_factory=dict)


def mapeo() -> dict:
    return json.loads(MAPEO.read_text(encoding="utf-8"))


def simbolos() -> dict[str, str]:
    return {k: v["etf"] for k, v in mapeo()["tramos"].items()}


def leer_registro(ruta: Path = LOG) -> list[dict]:
    if not ruta.exists():
        return []
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


# ---------------------------------------------------------------- cierres
def cierres_alpaca(c, desde: dt.date, hasta: dt.date) -> pd.DataFrame:
    """Cierres ajustados (adjustment=all, feed IEX) por tramo. Usa el cliente de src/broker/alpaca.py sin cambiarlo
    (barras_diarias pide `raw`; aquí hace falta el ajustado por dividendos para la tendencia)."""
    from src.broker import alpaca as A
    sim = simbolos()
    barras: dict[str, list] = {}
    token = None
    while True:
        p = {"symbols": ",".join(sim.values()), "timeframe": "1Day", "start": desde.isoformat(),
             "end": hasta.isoformat(), "feed": A.FEED, "adjustment": "all", "limit": 10000}
        if token:
            p["page_token"] = token
        d = c._pide("GET", A.DATOS, "/v2/stocks/bars", p)
        for s, xs in (d.get("bars") or {}).items():
            barras.setdefault(s, []).extend(xs)
        token = d.get("next_page_token")
        if not token:
            break
    cols = {}
    for tramo, s in sim.items():
        xs = barras.get(s) or []
        cols[tramo] = pd.Series({pd.Timestamp(str(x["t"])[:10]): float(x["c"]) for x in xs}, dtype=float)
    return pd.DataFrame(cols).sort_index()


def cierres_archivo(ruta: Path = ARCHIVO) -> pd.DataFrame:
    df = pd.read_parquet(ruta)
    sim = simbolos()
    faltan = [s for s in sim.values() if s not in df.columns]
    if faltan:
        raise SinDatos(f"el archivo no tiene {faltan}: usa --fuente alpaca")
    out = df[[sim[t] for t in sim]].copy()
    out.columns = list(sim)
    out.index = pd.to_datetime(out.index).normalize()
    return out.sort_index()


# ---------------------------------------------------------------- decisión (pura)
def deriva(w: dict[str, float], precios: pd.DataFrame, desde: str, hasta: pd.Timestamp) -> dict[str, float]:
    """Pesos `w` fijados al cierre `desde`, derivados con los precios hasta `hasta` (efectivo a 0 %)."""
    p = precios.loc[pd.Timestamp(desde):hasta]
    if p.empty or p.index[0] != pd.Timestamp(desde):
        raise SinDatos(f"no hay cierre de {desde} para derivar los pesos vigentes")
    g = (p.iloc[-1] / p.iloc[0]).reindex(list(w)).to_numpy(float)
    v = np.array([w[k] for k in w]) * g
    tot = v.sum() + (1 - sum(w.values()))
    return {k: float(x / tot) for k, x in zip(w, v)}


def decidir(cierre: pd.Timestamp, precios: pd.DataFrame, previos: list[dict], fuente: str) -> DecisionD1:
    precios = precios.loc[:cierre, list(TRAMOS)]
    if precios.empty or precios.index[-1] != cierre:
        raise SinDatos(f"la última barra no es la del cierre {cierre.date()}")
    p = precios.dropna()
    if len(p) < HISTORIA or p.index[-1] != cierre:
        raise SinDatos(f"historia insuficiente: {len(p)} cierres completos (hacen falta {HISTORIA})")
    r = p.pct_change().iloc[1:]
    s, sig = M.tendencia(r).iloc[-1], M.volatilidad(r).iloc[-1]
    if s.isna().any() or sig.isna().any():
        raise SinDatos("señal o volatilidad incompletas")
    obj = M.objetivo(s, sig)
    prev = previos[-1] if previos else None
    if prev:
        if pd.Timestamp(prev["cierre"]) >= cierre:
            raise ValueError(f"el cierre {cierre.date()} no es posterior al último registrado ({prev['cierre']})")
        actual = deriva(prev["d1"], p, prev["cierre"], cierre)
    else:
        actual = {k: 0.0 for k in TRAMOS}
    a = np.array([actual[k] for k in TRAMOS])
    nuevo = M.aplica_banda(obj.reindex(list(TRAMOS)).to_numpy(float), a)
    cruzan = [k for k, x, y in zip(TRAMOS, nuevo, a) if abs(x - y) > 1e-12]
    motivo = ("arranque" if prev is None else
              (f"cruzan la banda de {M.BANDA:.0%}: {cruzan}" if cruzan else "ningún activo cruza la banda"))
    R = lambda x: {k: round(float(v), 6) for k, v in x.items()}   # noqa: E731
    return DecisionD1(str(cierre.date()), bool(cruzan), R(dict(zip(TRAMOS, nuevo))), R(obj.to_dict()), R(actual),
                      R(s.to_dict()), R(sig.to_dict()), motivo, fuente, prev["cierre"] if prev else None)


def registrar(d: DecisionD1, extra: dict, ruta: Path = LOG) -> None:
    w = d.d1
    if set(w) != set(TRAMOS) or any(v < -1e-12 or v > 1 + 1e-6 for v in w.values()) or sum(w.values()) > 1 + 1e-6:
        raise ValueError(f"pesos no válidos: {w}")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({**asdict(d), **extra}, ensure_ascii=False) + "\n")
