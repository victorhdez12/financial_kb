"""M1 «Claude gestor macro» en vivo (docs/factors/M1_cartera_macro_spec.md v1.1): un ciclo al día, 20:45 Madrid.

Misma infraestructura que C1 (src/paper/c1.py `ciclo` con la cartera M1):
1. Paquete del día (src/paper/m1_paquete.py, sin IA): el de C1 + salidas de los modelos con su fecha + sombra.
2. Agente de solo lectura (src/paper/agente.py, rol M1) con el mandato m1-v1 (config/m1_mandato_v1.md) y el
   documento de conocimiento; plazo 15 min; sin cupo o con fallo: no opera y se anota.
3. Guardia de C1 + citas (src/broker/m1_guardia.py): orden sin cita válida → rechazada; no operar sin cita o sin
   declaración modelo por modelo → salida inválida (no opera).
4. Con --registrar: órdenes válidas a la cuenta PAPER del perfil `M1`; registro research/paper/decisiones_m1.jsonl
   (una línea por día, con `uso_modelos`) y la línea de la sombra research/paper/decisiones_m1_sombra.jsonl; diario en
   obsidian/Carteras/M1/AAAA-MM-DD.md (fuera de git); commit y push. Exige research/paper/M1_ACTIVO, árbol limpio,
   claves `_M1` y mercado abierto. Botón de parada: research/paper/M1_PARADA (lo puede crear el supervisor).
Sin --registrar es un ENSAYO: ni órdenes ni registro; todo en ~/financial_archive/m1/ensayos/ (FIN_M1_DIR).

Uso: .venv/bin/python -m src.paper.m1 [--registrar | --auto] [--simulada]
Códigos de salida: como src/paper/c1.py (6 sin M1_ACTIVO, 7 sin claves M1…).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from src.broker import alpaca as A
from src.broker import c1_guardia as G
from src.broker import m1_guardia as MG
from src.paper import agente as AG
from src.paper import c1 as C
from src.paper import m1_paquete as P
from src.paper import m1_sombra as S

REPO = A.REPO
LOG = P.LOG
ACTIVO = REPO / "research" / "paper" / "M1_ACTIVO"
MANDATO = REPO / "config" / "m1_mandato_v1.md"
SPEC = "docs/factors/M1_cartera_macro_spec.md v1.1"
PERFIL = "M1"


def dir_m1() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_M1_DIR", "~/financial_archive/m1")))


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True).stdout.strip()


def _disp(paquete: dict) -> set[str]:
    return set(paquete.get("modelos_disponibles") or [])


class _Lector:
    """`leer` de la cartera: depende de los modelos disponibles del paquete del día (se fija al armar el paquete)."""
    def __init__(self):
        self.disponibles: set[str] = set()

    def __call__(self, texto):
        return MG.lector(self.disponibles)(texto)


def uso_modelos(propuesta: dict | None) -> dict:
    """Para la tabla «uso de modelos» (spec §5): caso declarado por modelo y modelos citados en cada orden."""
    if not propuesta:
        return {"uso_modelos": None}
    dec = {x["modelo"]: x["caso"] for x in propuesta.get("declaracion_modelos") or [] if isinstance(x, dict)}
    citas = [{"indice": i, "simbolo": o.get("simbolo"), "lado": o.get("lado"),
              "modelos": sorted({c.get("modelo") for c in o.get("citas") or [] if isinstance(c, dict)})}
             for i, o in enumerate(propuesta.get("ordenes") or []) if isinstance(o, dict)]
    no_op = sorted({c.get("modelo") for c in propuesta.get("citas_no_operar") or [] if isinstance(c, dict)})
    return {"uso_modelos": {"declaracion": dec, "citas_ordenes": citas, "citas_no_operar": no_op}}


def prompt(paquete: dict, trabajo: Path) -> str:
    extra = ("Los modelos citables y su salida están en paquete.json → `modelos` (con `modelos_disponibles`); la "
             "cartera sombra en `sombra`. Recuerda: cada orden con `citas`, `declaracion_modelos` con los 9 modelos.")
    return C.prompt_agente(paquete, trabajo, nombre=PERFIL, version=MG.VERSION_MANDATO, extra=extra)


def cartera(*, yahoo: bool = True) -> C.Cartera:
    lector = _Lector()

    def recoger(c, hoy, registro=None):
        p = P.recoger(c, hoy, registro=registro, yahoo=yahoo)
        lector.disponibles = _disp(p)
        return p
    return C.Cartera(nombre=PERFIL, spec=SPEC, modo="agente", version=MG.VERSION_MANDATO, mandato=MANDATO,
                     plazo=AG.PLAZO_S, leer=lector, recoger=recoger, leer_registro=lambda: P.leer_registro(),
                     log=lambda: LOG, parada=lambda: MG.PARADA, dir_base=dir_m1, campos_orden=MG.CAMPOS_ORDEN,
                     extra_orden=lambda paq: MG.comprobar_orden(_disp(paq)), prompt_agente=prompt, anexo=uso_modelos)


def ciclo(c: A.Cliente | None, **kw) -> dict:
    """Ciclo de M1 (el de C1 con la cartera M1). La línea de la sombra viaja en el paquete y se copia a `sombra`."""
    yahoo = kw.pop("yahoo", True)
    linea = C.ciclo(c, cartera=cartera(yahoo=yahoo), **kw)
    return linea


def sombra_de(linea: dict) -> dict | None:
    """La línea de la sombra del día, sacada del paquete guardado (es la que vio Claude)."""
    import json
    f = (linea.get("paquete") or {}).get("fichero")
    if not f or not Path(f).exists():
        return None
    s = json.loads(Path(f).read_text(encoding="utf-8")).get("sombra")
    return s if isinstance(s, dict) and "error" not in s else None


def registrar(linea: dict, ruta: Path | None = None) -> None:
    ruta = ruta or LOG
    if linea.get("ensayo"):
        raise ValueError("una línea de ensayo no se registra")
    if linea["fecha"] in {r.get("fecha") for r in P.leer_registro(ruta)}:
        raise ValueError(f"ya hay una línea de M1 para {linea['fecha']} (una por día, inmutable)")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(ruta, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M1 «Claude gestor macro»: un ciclo (ensayo por defecto)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--registrar", action="store_true", help="envía a la cuenta PAPER de M1 y registra (exige M1_ACTIVO)")
    g.add_argument("--auto", action="store_true", help="launchd: --registrar si existe M1_ACTIVO; si no, nada")
    ap.add_argument("--simulada", action="store_true", help="ensayo con cuenta ficticia aunque haya claves")
    a = ap.parse_args(argv)
    if a.auto and not ACTIVO.exists():
        print("M1 no activado (no existe research/paper/M1_ACTIVO): nada que hacer")
        return 0
    registrar_ = a.registrar or a.auto
    hoy = dt.date.today()
    if registrar_:
        if a.simulada:
            print("--simulada no se puede registrar")
            return 1
        if not ACTIVO.exists():
            print("no existe research/paper/M1_ACTIVO: M1 solo ensaya (lo crea el usuario)")
            return 6
        if hoy.isoformat() in {r.get("fecha") for r in P.leer_registro()}:
            print(f"M1 ya registrado hoy ({hoy})")
            return 0 if a.auto else 3
        if git("status", "--porcelain"):
            print("árbol de git sucio: commitea antes de registrar")
            return 5
    try:
        c = None if a.simulada else A.cliente(PERFIL)
    except A.EndpointNoPermitido as e:
        print(f"ERROR: {e}")
        return 1
    if c is not None:
        G.comprobar_cliente(c)
    if registrar_:
        if c is None:
            print("Alpaca no configurado para M1 (faltan ALPACA_API_KEY_ID_M1 / ALPACA_API_SECRET_KEY_M1)")
            return 7
        try:
            m = A.estado_mercado(c.reloj())
            motivo = C.comprobar_cuenta(c, c.cuenta(), PERFIL)
        except A.AlpacaError as e:
            print(f"ERROR Alpaca: {c.cred.enmascarar(str(e))}")
            return 1
        if motivo:
            print(f"M1 no opera: {motivo}")
            return 9
        if not m["abierto"]:
            print(f"mercado cerrado (abre {m['proxima_apertura']}): M1 no opera hoy, sin registro")
            return 0 if a.auto else 8
    linea = ciclo(c, hoy=hoy, enviar=registrar_)
    linea["registrado"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    C._imprime(linea)
    s = sombra_de(linea)
    if s is None and registrar_:
        # con M1_PARADA el ciclo no arma paquete, pero la sombra (sin cuenta) se sigue calculando cada día (§4)
        try:
            sig, _ = P.P.ultimo_signal()
            s, _ = P.sombra_del_dia(c, hoy, sig, S.leer_registro())
        except Exception as e:  # noqa: BLE001
            print(f"sombra no calculada: {type(e).__name__}: {str(e)[:200]}")
            s = None
    if s:
        print(f"sombra: bolsa {s['objetivo'].get('bolsa')} · ajustes {s['objetivo'].get('ajustes')} · valor teórico "
              f"{(s.get('valoracion') or {}).get('valor')} ({(s.get('valoracion') or {}).get('hasta')})")
    if not registrar_:
        return 0
    linea["git_head"] = git("rev-parse", "HEAD")
    registrar(linea)
    rutas = [str(LOG)]
    if s and s["fecha"] not in {r.get("fecha") for r in S.leer_registro()}:
        S.registrar({**s, "git_head": linea["git_head"]})
        rutas.append(str(S.LOG))
    git("add", *rutas)
    git("commit", "-q", "-m", f"Paper M1: decisión del {linea['fecha']} (opera={linea['opera']}, "
                              f"{len(linea.get('enviadas') or [])} enviadas, {len(linea.get('rechazadas') or [])} "
                              "rechazadas) y sombra\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    git("push", "-q", "origin", "main")
    print("registrada y subida")
    return 0


if __name__ == "__main__":
    sys.exit(main())
