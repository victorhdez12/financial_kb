"""S1 en vivo (docs/factors/S1_rotacion_sectorial_spec.md v1.0 §3 y §6): decisión mensual de la tercera cuenta paper.
Misma regla que el desarrollo (src/factors/s1.py: SECTORES, objetivo, 50/50), sin parámetros nuevos:
- Cuadrante = el de la diaria del cierre de mes: fila `regime_monthly` con fecha = fin de mes, construida con corte
  (cutoff) = ese fin de mes (es decir, por una diaria del mismo día o posterior; si la última construcción es anterior
  al cierre, la fila aún no es la del cierre y no se decide).
- Si el cuadrante cambia respecto al vigente del registro → `opera` = true y pesos objetivo nuevos. Si no cambia, o
  falta → `opera` = false y se repiten los pesos vigentes (el espejo no opera: los pesos derivan, como en la regla).
- Registro propio e inmutable research/paper/decisiones_s1.jsonl (una línea por cierre); las reglas de registro
  (último fin de mes, sin saltos, árbol limpio, commit) son las de B1 (scripts/paper_decision.py) y están en
  scripts/paper_decision_s1.py.

**S1 NO pasó el desarrollo** (docs/factors/S1_resultado_desarrollo.md). Este código está hecho por si el usuario decide
llevarla como observación; para registrar hace falta además research/paper/S1_ACTIVO (no existe).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from src.factors.s1 import NUCLEO, SECTORES, objetivo

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "research" / "paper" / "decisiones_s1.jsonl"
ACTIVO_S1 = REPO / "research" / "paper" / "S1_ACTIVO"
SPEC = "docs/factors/S1_rotacion_sectorial_spec.md v1.0"


class SinCuadrante(RuntimeError):
    """No hay fila de la diaria para el cierre (o aún no está construida con ese corte)."""


@dataclass
class DecisionS1:
    cierre: str
    cuadrante: str | None            # el de la diaria del cierre (None si falta)
    vigente: str                     # el que rige el mes siguiente
    opera: bool
    s1: dict[str, float]             # pesos por tramo (claves de config/alpaca_etfs_s1.json)
    motivo: str
    diaria: dict = field(default_factory=dict)   # G, estados, modo de vintage, corte y hora de construcción
    spec: str = SPEC


def pesos(cuadrante: str) -> dict[str, float]:
    w = objetivo(cuadrante)
    return {k: float(v) for k, v in w[w > 0].items()}


def leer_registro(ruta: Path = LOG) -> list[dict]:
    if not ruta.exists():
        return []
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def fila_diaria(con, cierre: pd.Timestamp) -> dict:
    """Fila de `regime_monthly` del cierre, exigiendo que su corte sea el propio fin de mes."""
    r = con.execute("select date, quadrant, G, G_state, I_state, vintage_mode, cutoff from regime_monthly "
                    "where date = ?", [cierre.date()]).df()
    if r.empty:
        raise SinCuadrante(f"regime_monthly no tiene fila para {cierre.date()}")
    x = r.iloc[0]
    if pd.Timestamp(x["cutoff"]).normalize() != cierre.normalize():
        raise SinCuadrante(f"la fila de {cierre.date()} tiene corte {pd.Timestamp(x['cutoff']).date()}: "
                           "la diaria aún no ha corrido después del cierre")
    meta = con.execute("select built_at from regime_meta").fetchone()
    q = x["quadrant"] if isinstance(x["quadrant"], str) else None
    return {"quadrant": q, "G": None if pd.isna(x["G"]) else round(float(x["G"]), 4), "G_state": x["G_state"],
            "I_state": x["I_state"], "vintage_mode": x["vintage_mode"], "cutoff": str(pd.Timestamp(x["cutoff"]).date()),
            "regime_built_at": str(meta[0]) if meta else None}


def decidir(cierre: pd.Timestamp, diaria: dict, previos: list[dict]) -> DecisionS1:
    """Pura: la decisión del cierre dada la fila de la diaria y el registro anterior."""
    q = diaria.get("quadrant")
    if q is not None and q not in SECTORES:
        raise ValueError(f"cuadrante desconocido {q!r}")
    vigente = previos[-1]["vigente"] if previos else None
    if q is not None and q != vigente:
        motivo = "arranque" if vigente is None else f"cambio de cuadrante {vigente} → {q}"
        return DecisionS1(str(cierre.date()), q, q, True, pesos(q), motivo, diaria)
    if vigente is None:
        raise SinCuadrante("sin cuadrante en el primer cierre: no hay pesos que mantener")
    motivo = "sin cambio de cuadrante" if q is not None else "sin cuadrante (dato ausente): se mantienen los pesos"
    return DecisionS1(str(cierre.date()), q, vigente, False, dict(previos[-1]["s1"]), motivo, diaria)


def registrar(d: DecisionS1, extra: dict, ruta: Path = LOG) -> None:
    if abs(sum(d.s1.values()) - 1) > 1e-9 or abs(d.s1.get("mkt", 0) - NUCLEO) > 1e-9:
        raise ValueError(f"pesos no válidos: {d.s1}")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({**asdict(d), **extra}, ensure_ascii=False) + "\n")
