"""A1 «selección de acciones» en vivo (docs/factors/A1_seleccion_acciones_spec.md v1.0): un ciclo al día, 21:00 Madrid.

Misma infraestructura que C1 y M1 (src/paper/c1.py `ciclo` con la cartera A1):
1. Paquete del día (src/paper/a1_paquete.py, sin IA): el de C1 + modelos macro y filtro macro + candidatas con calidad
   XBRL + datos de empresa de «Mis activos» (Form 4, 13F, 13D/13G, alertas) + sombra.
2. Agente de solo lectura (src/paper/agente.py, rol A1) con el mandato a1-v1 (config/a1_mandato_v1.md) y el documento
   de conocimiento; plazo 15 min; sin cupo o con fallo: no opera y se anota.
3. Guardia de C1 + la de A1 (src/broker/a1_guardia.py): solo acciones, cita doble (empresa + macro), universo, y
   límites de cartera (10 % por valor, 35 % por sector, 30 valores, techo de bolsa del filtro macro).
4. Con --registrar: órdenes válidas a la cuenta PAPER del perfil `A1`; registro research/paper/decisiones_a1.jsonl
   (una línea por día, con `uso_citas`) y la línea de la sombra research/paper/decisiones_a1_sombra.jsonl; diario en
   obsidian/Carteras/A1/AAAA-MM-DD.md (fuera de git); commit y push. Exige research/paper/A1_ACTIVO, árbol limpio,
   claves `_A1`, cuenta de A1 (reasignación declarada) y mercado abierto. Parada: research/paper/A1_PARADA.
Sin --registrar es un ENSAYO: ni órdenes ni registro; todo en ~/financial_archive/a1/ensayos/ (FIN_A1_DIR).

Uso: .venv/bin/python -m src.paper.a1 [--registrar | --auto] [--simulada]
Códigos de salida: como src/paper/c1.py (6 sin A1_ACTIVO, 7 sin claves A1, 9 cuenta de otra cartera…).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

from src.broker import a1_guardia as AGd
from src.broker import alpaca as A
from src.broker import c1_guardia as G
from src.paper import a1_candidatas as K
from src.paper import a1_paquete as P
from src.paper import a1_sombra as SA
from src.paper import agente as AG
from src.paper import c1 as C

REPO = A.REPO
LOG = P.LOG
ACTIVO = REPO / "research" / "paper" / "A1_ACTIVO"
MANDATO = REPO / "config" / "a1_mandato_v1.md"
SPEC = "docs/factors/A1_seleccion_acciones_spec.md v1.0"
PERFIL = "A1"


def dir_a1() -> Path:
    return K.dir_a1()


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True).stdout.strip()


class _Ctx:
    """Contexto de la guardia: depende del paquete del día (se fija al armar el paquete)."""
    def __init__(self):
        self.ctx = AGd.Contexto()

    def leer(self, texto):
        return AGd.lector(self.ctx)(texto)


def uso_citas(propuesta: dict | None) -> dict:
    """Para la evaluación (spec §5): por orden, modelos macro y fuentes de empresa citados."""
    if not propuesta:
        return {"uso_citas": None}
    ords = [{"indice": i, "simbolo": o.get("simbolo"), "lado": o.get("lado"),
             "macro": sorted({c.get("modelo") for c in o.get("citas_macro") or [] if isinstance(c, dict)}),
             "empresa": sorted({c.get("fuente") for c in o.get("citas_empresa") or [] if isinstance(c, dict)})}
            for i, o in enumerate(propuesta.get("ordenes") or []) if isinstance(o, dict)]
    no_op = sorted({c.get("modelo") for c in propuesta.get("citas_no_operar") or [] if isinstance(c, dict)})
    return {"uso_citas": {"ordenes": ords, "citas_no_operar": no_op}}


def prompt(paquete: dict, trabajo: Path) -> str:
    extra = ("Las candidatas (calidad XBRL, sector) están en paquete.json → `candidatas`; los datos de «Mis activos» "
             "en `mis_activos`; qué fuentes de empresa tiene hoy cada símbolo en `empresa_disponible`; lo que puedes "
             "comprar en `universo_compra` (más el colchón `colchon`); el filtro macro en `filtro_macro`; los modelos "
             "macro en `macro` (con `macro_disponibles`); la sombra en `sombra`. Recuerda: cada orden con "
             "`citas_empresa` Y `citas_macro`; máx. 10 % por valor y 35 % por sector.")
    return C.prompt_agente(paquete, trabajo, nombre=PERFIL, version=AGd.VERSION_MANDATO, extra=extra)


def cartera(*, yahoo: bool = True, candidatas: dict | None = None) -> C.Cartera:
    k = _Ctx()

    def recoger(c, hoy, registro=None):
        p = P.recoger(c, hoy, registro=registro, yahoo=yahoo, candidatas=candidatas)
        k.ctx = AGd.contexto(p)
        return p
    return C.Cartera(nombre=PERFIL, spec=SPEC, modo="agente", version=AGd.VERSION_MANDATO, mandato=MANDATO,
                     plazo=AG.PLAZO_S, leer=k.leer, recoger=recoger, leer_registro=lambda: P.leer_registro(),
                     log=lambda: LOG, parada=lambda: AGd.PARADA, dir_base=dir_a1, campos_orden=AGd.CAMPOS_ORDEN,
                     extra_orden=lambda paq: AGd.comprobar_orden(AGd.contexto(paq)), prompt_agente=prompt,
                     anexo=uso_citas,
                     post_validar=lambda ver, paq, est: AGd.limites(ver, AGd.contexto(paq), est))


def ciclo(c: A.Cliente | None, **kw) -> dict:
    yahoo = kw.pop("yahoo", True)
    candidatas = kw.pop("candidatas", None)
    return C.ciclo(c, cartera=cartera(yahoo=yahoo, candidatas=candidatas), **kw)


def sombra_de(linea: dict) -> dict | None:
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
        raise ValueError(f"ya hay una línea de A1 para {linea['fecha']} (una por día, inmutable)")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A1 «selección de acciones»: un ciclo (ensayo por defecto)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--registrar", action="store_true", help="envía a la cuenta PAPER de A1 y registra (exige A1_ACTIVO)")
    g.add_argument("--auto", action="store_true", help="launchd: --registrar si existe A1_ACTIVO; si no, nada")
    ap.add_argument("--simulada", action="store_true", help="ensayo con cuenta ficticia aunque haya claves")
    a = ap.parse_args(argv)
    if a.auto and not ACTIVO.exists():
        print("A1 no activado (no existe research/paper/A1_ACTIVO): nada que hacer")
        return 0
    registrar_ = a.registrar or a.auto
    hoy = dt.date.today()
    if registrar_:
        if a.simulada:
            print("--simulada no se puede registrar")
            return 1
        if not ACTIVO.exists():
            print("no existe research/paper/A1_ACTIVO: A1 solo ensaya (lo crea el usuario)")
            return 6
        if hoy.isoformat() in {r.get("fecha") for r in P.leer_registro()}:
            print(f"A1 ya registrado hoy ({hoy})")
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
            print("Alpaca no configurado para A1 (faltan ALPACA_API_KEY_ID_A1 / ALPACA_API_SECRET_KEY_A1)")
            return 7
        try:
            m = A.estado_mercado(c.reloj())
            motivo = C.comprobar_cuenta(c, c.cuenta(), PERFIL)
        except A.AlpacaError as e:
            print(f"ERROR Alpaca: {c.cred.enmascarar(str(e))}")
            return 1
        if motivo:
            print(f"A1 no opera: {motivo}")
            return 9
        if not m["abierto"]:
            print(f"mercado cerrado (abre {m['proxima_apertura']}): A1 no opera hoy, sin registro")
            return 0 if a.auto else 8
    linea = ciclo(c, hoy=hoy, enviar=registrar_)
    linea["registrado"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    C._imprime(linea)
    s = sombra_de(linea)
    if s:
        print(f"sombra: techo {s['filtro'].get('techo_bolsa')} · cesta {len((s.get('objetivo') or {}).get('cesta') or [])} "
              f"valores · valor teórico {(s.get('valoracion') or {}).get('valor')} ({(s.get('valoracion') or {}).get('hasta')})")
    elif registrar_:
        print("sombra no disponible hoy (con A1_PARADA no se arma paquete): no se registra")
    if not registrar_:
        return 0
    linea["git_head"] = git("rev-parse", "HEAD")
    registrar(linea)
    rutas = [str(LOG)]
    if s and s["fecha"] not in {r.get("fecha") for r in SA.leer_registro()}:
        SA.registrar({**s, "git_head": linea["git_head"]})
        rutas.append(str(SA.LOG))
    git("add", *rutas)
    git("commit", "-q", "-m", f"Paper A1: decisión del {linea['fecha']} (opera={linea['opera']}, "
                              f"{len(linea.get('enviadas') or [])} enviadas, {len(linea.get('rechazadas') or [])} "
                              "rechazadas) y sombra\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    git("push", "-q", "origin", "main")
    print("registrada y subida")
    return 0


if __name__ == "__main__":
    sys.exit(main())
