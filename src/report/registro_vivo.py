"""Registro mensual en vivo de INT-11 (docs/int/INT11_registro_vivo.md, v0.2): reglas que lo hacen fiable.

Arreglos de la validación v2 (docs/validation/2026-10-30_int11v2.md, hallazgo 3):
  1. La 2.ª emisión ya no aborta por árbol sucio: la emisión con registro NO reescribe la salida "hoy" (solo escribe en
     la carpeta del registro) y `procedencia_registro` tolera cambios SOLO dentro de esa carpeta (p. ej. el mes anterior
     sin commitear si falló el commit automático); cualquier otro cambio sigue abortando.
  2. Se rechazan las fechas atrasadas (|emisión − hoy| > 3 días): con datos revisados posteriores a la fecha sería una
     fuga. Excepción: `vintage=True`, que solo emite los países con vintages (ALFRED: EE. UU.) leídos "tal como se
     publicaron" en la fecha (`escenarios_vivo.estado_actual_movil(..., vintage=True)`).
  3. Cada emisión guarda una HUELLA de sus entradas (IPC y PIB exactos usados, con su sha256): es la "vintage propia" del
     registro, para que la evaluación futura sepa con qué datos se emitió aunque la OCDE los revise después.
Funciones puras salvo `procedencia_registro` (git) y `registrar` (escribe en la carpeta del registro).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
TOLERANCIA_DIAS = 3


def comprobar_fecha(fecha, hoy=None, tolerancia: int = TOLERANCIA_DIAS, vintage: bool = False) -> None:
    """Emisión en tiempo real: la fecha no puede estar en el futuro ni atrasada más de `tolerancia` días (salvo vintage)."""
    f = pd.Timestamp(fecha).normalize()
    h = pd.Timestamp(hoy if hoy is not None else pd.Timestamp.today()).normalize()
    d = (h - f).days
    if d < -tolerancia:
        raise SystemExit(f"registro en vivo: fecha {f.date()} en el futuro (hoy {h.date()})")
    if d > tolerancia and not vintage:
        raise SystemExit(f"registro en vivo: fecha {f.date()} atrasada {d} días (> {tolerancia}): los datos actuales "
                         "incluyen revisiones posteriores (fuga). Usa vintage=True (solo países con vintages)")


def _sucios() -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"], capture_output=True, text=True,
                         check=True).stdout
    return [ln[3:].strip().strip('"') for ln in out.splitlines() if ln.strip()]


def procedencia_registro(carpeta: Path, sucios: list[str] | None = None) -> dict:
    """Como `src.intl.procedencia.procedencia`, pero tolera cambios sin commitear DENTRO de la carpeta del registro."""
    import datetime as dt
    rel = str(Path(carpeta).resolve().relative_to(REPO)).rstrip("/") + "/"
    sucios = _sucios() if sucios is None else sucios
    ajenos = [p for p in sucios if not (p.rstrip("/") + "/").startswith(rel)]
    if ajenos:
        raise SystemExit("árbol de git sucio fuera del registro: commitea el código antes de emitir\n" + "\n".join(ajenos))
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    return {"commit": commit, "arbol_limpio": not sucios, "pendientes_en_registro": sucios,
            "hora_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}


def huella_entradas(series: dict[str, pd.Series]) -> dict:
    """{nombre: serie} → {"series": {nombre: {fecha: valor}}, "sha256": …} (orden y redondeo fijos)."""
    s = {k: {str(pd.Timestamp(i).date()): round(float(v), 8) for i, v in x.dropna().items()}
         for k, x in sorted(series.items())}
    h = hashlib.sha256(json.dumps(s, sort_keys=True).encode()).hexdigest()
    return {"series": s, "sha256": h}


def registrar(o: dict, carpeta: Path) -> Path:
    """Guarda la emisión del mes (inmutable): carpeta/AAAA-MM.json + línea en indice.csv con sha256, commit, ventana y
    huella de las entradas."""
    carpeta.mkdir(parents=True, exist_ok=True)
    mes = o["emision"][:7]
    ruta = carpeta / f"{mes}.json"
    if ruta.exists():
        raise SystemExit(f"{ruta} ya existe: el registro en vivo no se sobrescribe")
    texto = json.dumps(o, ensure_ascii=False, indent=1, sort_keys=True, default=float)
    ruta.write_text(texto)
    h = hashlib.sha256(texto.encode()).hexdigest()
    idx = carpeta / "indice.csv"
    nuevo = not idx.exists()
    with idx.open("a") as f:
        if nuevo:
            f.write("mes,archivo,sha256,commit,emision,ventana_desde,ventana_hasta,sha256_entradas\n")
        f.write(f"{mes},{ruta.name},{h},{o['procedencia'].get('commit', '')},{o['emision']},"
                f"{o['ventana_objetivo']['desde']},{o['ventana_objetivo']['hasta']},"
                f"{o.get('entradas', {}).get('sha256', '')}\n")
    return ruta


def comprobaciones_ensayo(fecha, carpeta: Path, vintage: bool = False, hoy=None, sucios: list[str] | None = None) -> dict:
    """Modo ENSAYO: las mismas comprobaciones que una emisión real (`comprobar_fecha`, `procedencia_registro`, que no
    exista ya el mes), pero ANOTADAS en lugar de abortar. Devuelve {"procedencia": …, "fecha_ok", "arbol_ok",
    "mes_libre", "abortaria": [motivos]}."""
    motivos = []
    try:
        comprobar_fecha(fecha, hoy=hoy, vintage=vintage)
        fecha_ok = True
    except SystemExit as e:
        fecha_ok, motivos = False, motivos + [str(e)]
    try:
        proc = procedencia_registro(carpeta, sucios)
        arbol_ok = True
    except SystemExit as e:
        arbol_ok, motivos = False, motivos + [str(e).splitlines()[0]]
        s = _sucios() if sucios is None else sucios
        proc = {"commit": None, "arbol_limpio": False, "pendientes_en_registro": s, "ensayo": True}
    mes = str(pd.Timestamp(fecha).date())[:7]
    libre = not (Path(carpeta) / f"{mes}.json").exists()
    if not libre:
        motivos.append(f"{mes}.json ya existe en el registro")
    return {"procedencia": proc, "fecha_ok": fecha_ok, "arbol_ok": arbol_ok, "mes_libre": libre,
            "abortaria": motivos}


def resumen_ensayo(o: dict, carpeta: Path, plan_bolsa: dict | None = None) -> dict:
    """Lo que el ensayo habría registrado (sin escribir): archivo, sha256 del contenido, ventana, países emitidos y,
    si se da, el plan de evaluación de la bolsa (fuente D9)."""
    mes = o["emision"][:7]
    texto = json.dumps(o, ensure_ascii=False, indent=1, sort_keys=True, default=float)
    paises = {c: ("ok" if "cuantiles_1_99" in r else r.get("aviso", "?")) for c, r in o["paises"].items()}
    return {"modo": "ENSAYO (no se ha escrito nada)", "archivo_que_se_escribiria": str(Path(carpeta) / f"{mes}.json"),
            "sha256_contenido": hashlib.sha256(texto.encode()).hexdigest(), "bytes": len(texto),
            "sha256_entradas": o.get("entradas", {}).get("sha256"), "ventana_objetivo": o["ventana_objetivo"],
            "comprobaciones": o.get("ensayo"), "paises": paises, "bolsa_evaluacion": plan_bolsa}
