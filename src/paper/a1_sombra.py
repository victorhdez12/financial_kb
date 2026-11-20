"""Filtro macro y sombra teórica de A1 «selección de acciones» (docs/factors/A1_seleccion_acciones_spec.md v1.0 §4).

Filtro macro (lo usa la guardia: techo de lo invertido fuera del colchón): las MISMAS entradas y ajustes que el paso 1
de la sombra de M1 (src/paper/m1_sombra.bolsa: crédito ámbar −10 pp / rojo −25 pp; E1 P(recesión) > 30 % −15 pp,
> 50 % −30 pp; liquidez escasa −5 pp / abundante +5 pp; INT-11 P(pérdida 12 m) de la bolsa de EE. UU. > 60 % −10 pp,
< 35 % +5 pp; G↑ +10 pp, G↓ −10 pp) con base 90 %, suelo 30 % y techo 100 % (A1 es una cartera de acciones: por
defecto casi todo en bolsa; el filtro solo recorta). Sin dato, esa entrada no ajusta (neutral).

Sombra (mecánica, sin cuenta): cada mes (primera decisión del mes natural) la cesta = las 20 acciones de mayor calidad
XBRL (src/paper/a1_candidatas.py) con como mucho 7 por sector (35 % de 20), a partes iguales; peso total = el techo
del filtro macro de cada día; el resto en SGOV (colchón). Colchón de efectivo 0,5 %. Valoración teórica con la de M1
(src/paper/m1_sombra.valorar: al cierre del día de la decisión, sesiones completas, 5 pb × Σ|Δw|; reequilibra si
cambia el objetivo —cesta o techo— o si un peso deriva ≥ 5 pp). Registro research/paper/decisiones_a1_sombra.jsonl
(una línea por día; lo escribe src/paper/a1.py junto a la de A1).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from src.paper import a1_candidatas as K
from src.paper import m1_sombra as S

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "research" / "paper" / "decisiones_a1_sombra.jsonl"
VERSION = "a1-sombra-1"
SPEC = "docs/factors/A1_seleccion_acciones_spec.md v1.0 §4"
BASE, SUELO, TECHO = 0.90, 0.30, 1.00
N_CESTA = 20
MAX_SECTOR_CESTA = 7
REFUGIO = "SGOV"
COLCHON = 0.005


def filtro_macro(x: dict) -> dict:
    """{techo_bolsa, ajustes, entradas, reglas} (pura)."""
    b, aj = S.bolsa(x, base=BASE, suelo=SUELO, techo=TECHO)
    return {"techo_bolsa": b, "ajustes": aj, "entradas": x,
            "reglas": f"base {BASE:.0%}, suelo {SUELO:.0%}, techo {TECHO:.0%}; ajustes del paso 1 de la sombra de M1"}


def cesta(cand: dict, n: int = N_CESTA, max_sector: int = MAX_SECTOR_CESTA) -> list[str]:
    return K.mejores(cand, n, max_por_sector=max_sector)


def objetivo(techo: float, simbolos: list[str]) -> dict:
    if not simbolos:
        return {"pesos": None, "motivo": "sin candidatas con calidad XBRL"}
    w = {t: round(techo * (1 - COLCHON) / len(simbolos), 6) for t in simbolos}
    resto = round((1 - techo) * (1 - COLCHON), 6)
    if resto > 1e-9:
        w[REFUGIO] = resto
    w["efectivo"] = round(1 - sum(w.values()), 6)
    return {"pesos": w, "techo_bolsa": techo, "cesta": list(simbolos)}


def leer_registro(ruta: Path | None = None) -> list[dict]:
    return S.leer_registro(ruta or LOG)


def cesta_del_dia(fecha: str, cand: dict, previas: list[dict]) -> tuple[list[str], str]:
    """La cesta se fija la primera decisión de cada mes natural; el resto del mes se mantiene."""
    ult = next((r for r in reversed(previas) if (r.get("objetivo") or {}).get("cesta")), None)
    if ult and str(ult["fecha"])[:7] == fecha[:7]:
        return list(ult["objetivo"]["cesta"]), f"cesta del mes (fijada el {ult.get('cesta_fijada') or ult['fecha']})"
    return cesta(cand), "cesta nueva (primera decisión del mes)"


def linea_del_dia(fecha: str, x: dict, cand: dict, previas: list[dict], precios: pd.DataFrame | None,
                  fuente: str) -> dict:
    f = filtro_macro(x)
    simbolos, motivo = cesta_del_dia(fecha, cand, previas)
    obj = objetivo(f["techo_bolsa"], simbolos)
    ult = next((r for r in reversed(previas) if (r.get("objetivo") or {}).get("cesta")), None)
    fijada = (ult.get("cesta_fijada") or ult["fecha"]) if ult and str(ult["fecha"])[:7] == fecha[:7] else fecha
    ln = {"fecha": fecha, "spec": SPEC, "version": VERSION, "filtro": {k: f[k] for k in ("techo_bolsa", "ajustes")},
          "entradas": x, "candidatas": {"version": cand.get("version"), "fecha_datos": cand.get("fecha_datos")},
          "cesta_motivo": motivo, "cesta_fijada": fijada, "objetivo": obj}
    val = S.valorar(previas + [ln], precios if precios is not None else pd.DataFrame())
    ln["valoracion"] = {"hasta": val.get("hasta"), "valor": val.get("valor"), "rebalanceos": val["rebalanceos"],
                        "rotacion": val["rotacion"], "costes": val["costes"], "sin_cierre": val["sin_cierre"],
                        "fuente_cierres": fuente, "valor_inicial": S.VALOR_INICIAL}
    return ln


def simbolos_historicos(previas: list[dict], hoy: list[str]) -> list[str]:
    xs = set(hoy) | {REFUGIO}
    for r in previas:
        xs |= {k for k in ((r.get("objetivo") or {}).get("pesos") or {}) if k != "efectivo"}
    return sorted(xs)


def sombra_del_dia(c, hoy: dt.date, x: dict, cand: dict, previas: list[dict], *, yahoo: bool = True) -> dict:
    simbolos, _ = cesta_del_dia(hoy.isoformat(), cand, previas)
    desde = min([dt.date.fromisoformat(r["fecha"]) for r in previas] + [hoy - dt.timedelta(days=10)])
    px, fuente = S.cierres(simbolos_historicos(previas, simbolos), desde, hoy - dt.timedelta(days=1), c, yahoo=yahoo)
    return linea_del_dia(hoy.isoformat(), x, cand, previas, px, fuente)


def registrar(linea: dict, ruta: Path | None = None) -> None:
    ruta = ruta or LOG
    if linea["fecha"] in {r.get("fecha") for r in leer_registro(ruta)}:
        raise ValueError(f"ya hay una línea de la sombra de A1 para {linea['fecha']} (una por día, inmutable)")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")
