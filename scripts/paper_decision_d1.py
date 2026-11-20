"""Decisión DIARIA de D1 «tendencia y volatilidad diaria» (docs/factors/D1_tendencia_diaria_spec.md §6; src/paper/d1.py).
Uso: .venv/bin/python -m scripts.paper_decision_d1 [--cierre AAAA-MM-DD | --auto] [--fuente alpaca|archivo] [--registrar]
- Sin --registrar es un ensayo: imprime la decisión y no escribe nada.
- Cierre: el de la última sesión de EE. UU. YA cerrada según el reloj y el calendario de Alpaca (perfil D1); con
  --fuente archivo y sin --cierre, el último día del archivo. --auto (launchd, ≈ 22:30 Madrid, lun-vie) usa siempre ese.
- Con --registrar exige: research/paper/D1_ACTIVO (lo crea el usuario), árbol limpio, cierre = última sesión cerrada
  (fuente alpaca), ≥ PRIMER_CIERRE (sin historia retroactiva), no registrado y posterior al último registrado. Añade la
  línea a research/paper/decisiones_d1.jsonl (propio, inmutable), commitea y sube, como B1′/S1.
- Nunca envía órdenes. Desde el 20-nov-2026 D1 es solo papel (sin espejo): usa de Alpaca solo datos (reloj,
  calendario, barras) del primer perfil disponible de PERFILES_DATOS. D1_ACTIVO sigue siendo la marca para registrar.
Códigos de salida: 0 hecho (o ya registrado / antes del arranque con --auto), 2 Alpaca sin configurar, 3 ya
registrado, 4 cierre no válido, 5 árbol sucio, 6 sin research/paper/D1_ACTIVO, 8 sin datos suficientes, 1 otros.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict

import pandas as pd

from scripts.paper_decision import MesNoValido, YaRegistrado, git
from src.paper import d1 as D

PRIMER_CIERRE = pd.Timestamp("2026-11-20")     # primera sesión tras la spec congelada (19-nov-2026)
DIAS_HISTORIA = 420                             # días naturales pedidos (≥ 253 sesiones)


# D1 es SOLO PAPEL desde el 20-nov-2026 (su cuenta …X9F9 pasó a A1): de Alpaca solo usa DATOS (reloj, calendario y
# barras), que dan igual de qué cuenta paper salgan. Nunca envía órdenes (este script no tiene ninguna llamada de órdenes).
PERFILES_DATOS = ("D1", "A1", "C1", "M1")


def cliente_datos():
    """Primer perfil con claves de PERFILES_DATOS (solo para datos de mercado); None si no hay ninguno."""
    from src.broker import alpaca as A
    for p in PERFILES_DATOS:
        c = A.cliente(p)
        if c is not None:
            return c
    return None


def ultima_sesion_cerrada(reloj: dict, calendario: list[dict]) -> pd.Timestamp:
    """Pura. La sesión de hoy cuenta solo si el mercado está cerrado y ya pasó su hora de cierre (hora de Nueva York)."""
    ahora = pd.Timestamp(reloj["timestamp"])
    hoy = ahora.tz_localize("America/New_York") if ahora.tzinfo is None else ahora.tz_convert("America/New_York")
    hoy_d = pd.Timestamp(hoy.date())
    sesiones = {pd.Timestamp(x["date"]): x for x in calendario}
    if hoy_d in sesiones and not reloj.get("is_open"):
        hh, mm = (int(v) for v in str(sesiones[hoy_d].get("close", "16:00")).split(":")[:2])
        if (hoy.hour, hoy.minute) >= (hh, mm):
            return hoy_d
    previas = [d for d in sesiones if d < hoy_d]
    if not previas:
        raise MesNoValido("el calendario no tiene sesiones anteriores")
    return max(previas)


def validar_d1(cierre: pd.Timestamp, esperado: pd.Timestamp | None, previos: list[str]) -> None:
    if esperado is not None and cierre != esperado:
        raise MesNoValido(f"solo se registra la última sesión cerrada ({esperado.date()}), no {cierre.date()}")
    if cierre < PRIMER_CIERRE:
        raise MesNoValido(f"D1 arranca en la sesión {PRIMER_CIERRE.date()} (sin historia retroactiva), no {cierre.date()}")
    if str(cierre.date()) in previos:
        raise YaRegistrado(f"ya hay una decisión de D1 para {cierre.date()} (una por sesión, inmutable)")
    if previos and cierre <= pd.Timestamp(max(previos)):
        raise MesNoValido(f"{cierre.date()} no es posterior al último registrado ({max(previos)})")


def main(argv=None, *, cliente=None, precios: pd.DataFrame | None = None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--cierre")
    g.add_argument("--auto", action="store_true")
    ap.add_argument("--fuente", choices=("alpaca", "archivo"), default="alpaca")
    ap.add_argument("--registrar", action="store_true")
    a = ap.parse_args(argv)
    if a.registrar and a.fuente != "alpaca":
        print("--registrar solo con --fuente alpaca (el cierre lo fija el reloj del mercado)")
        return 4
    esperado = None
    try:
        if a.fuente == "alpaca":
            c = cliente
            if c is None:
                from src.broker import alpaca as A
                c = cliente_datos()
                if c is None:
                    print(f"Alpaca sin configurar (ningún perfil de {PERFILES_DATOS}): nada que hacer")
                    return 0 if a.auto else 2
            hoy = dt.date.today()
            esperado = ultima_sesion_cerrada(c.reloj(), c.calendario(hoy - dt.timedelta(days=10), hoy))
            cierre = pd.Timestamp(a.cierre) if a.cierre else esperado
            if precios is None:
                precios = D.cierres_alpaca(c, (cierre - pd.Timedelta(days=DIAS_HISTORIA)).date(), cierre.date())
        else:
            precios = D.cierres_archivo() if precios is None else precios
            cierre = pd.Timestamp(a.cierre) if a.cierre else precios.index.max()
    except D.SinDatos as e:
        print(f"D1: {e}")
        return 8
    previos = D.leer_registro()
    if a.registrar:
        if a.auto and cierre < PRIMER_CIERRE:
            print(f"D1 aún no arranca: primera sesión registrable {PRIMER_CIERRE.date()} (nada que hacer)")
            return 0
        try:
            validar_d1(cierre, esperado, [d["cierre"] for d in previos])
        except YaRegistrado as e:
            print(e)
            return 0 if a.auto else 3
        except MesNoValido as e:
            print(e)
            return 4
        if not D.ACTIVO_D1.exists():
            print("no existe research/paper/D1_ACTIVO: D1 solo ensaya (decide el usuario)")
            return 6
        if git("status", "--porcelain"):
            print("árbol de git sucio: commitea antes de registrar")
            return 5
    try:
        d = D.decidir(cierre, precios, previos, a.fuente)
    except D.SinDatos as e:
        print(f"D1: {e}")
        return 8
    print(json.dumps(asdict(d), indent=1, ensure_ascii=False))
    if not a.registrar:
        return 0
    D.registrar(d, {"registrado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "git_head": git("rev-parse", "HEAD")})
    git("add", str(D.LOG.relative_to(D.REPO)))
    git("commit", "-q", "-m", f"Paper trading D1: decision for {cierre.date()} (opera={d.opera})\n\n"
                              "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    git("push", "-q", "origin", "main")
    print("registrada y subida")
    return 0


if __name__ == "__main__":
    sys.exit(main())
