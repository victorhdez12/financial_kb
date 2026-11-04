"""Archivo fechado de las descargas raw que se sobrescriben (OCDE: raw/oecd/*.csv, raw/oecd_qna/gdpq.csv).

Por qué: la OCDE revisa en origen series antiguas sin avisar (2-nov-2026: tipos, IP, paro y ventas ≤ 2004) y el raw se
sobrescribía en cada ingesta, así que no quedaba con qué reproducir un cálculo congelado (docs/int/INT8b_nowcast.md,
«Revisiones de datos»). Ahora cada descarga nueva se guarda también, comprimida y con fecha, en
$FIN_DATA_ROOT/raw/<fuente>/archivo/<nombre>_<AAAA-MM-DD>.csv.gz, con una línea en archivo/indice.jsonl
(nombre, fecha, sha256 del CSV sin comprimir, bytes, archivo). Si el contenido es idéntico al último archivado, no se
duplica (solo se apunta en el índice).

Retención declarada (RETENCION_DIAS): todas las copias de los últimos 730 días; de las más antiguas, la primera de cada
mes natural (para siempre), y nunca una a la que apunte una descarga posterior idéntica («igual_a»). Tamaño medido el 4-nov: ≈ 2,5 MB comprimidos por juego semanal de la OCDE (≈ 40:1), ≈ 130 MB
al año; dos años completos permiten reproducir cualquier congelación reciente, y la mensual basta para lo antiguo.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import re
from pathlib import Path

RETENCION_DIAS = 730
_RX = re.compile(r"^(?P<nombre>.+)_(?P<fecha>\d{4}-\d{2}-\d{2})\.csv\.gz$")


def _indice(carpeta: Path) -> list[dict]:
    p = carpeta / "indice.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def archivar(raw: Path, nombre: str, contenido: bytes, hoy: dt.date | None = None) -> Path | None:
    """Guarda `contenido` (la descarga recién escrita en raw/<fuente>/<nombre>.csv) en raw/<fuente>/archivo/. Devuelve
    la ruta archivada, o None si es idéntica a la última copia de ese nombre. Después poda según la retención."""
    hoy = hoy or dt.date.today()
    carpeta = Path(raw) / "archivo"
    carpeta.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(contenido).hexdigest()
    prev = [r for r in _indice(carpeta) if r["nombre"] == nombre and r.get("archivo")]
    dest = None
    if prev and prev[-1]["sha256"] == sha and (carpeta / prev[-1]["archivo"]).exists():
        reg = {"nombre": nombre, "fecha": hoy.isoformat(), "sha256": sha, "bytes": len(contenido),
               "archivo": None, "igual_a": prev[-1]["archivo"]}
    else:
        dest = carpeta / f"{nombre}_{hoy.isoformat()}.csv.gz"
        dest.write_bytes(gzip.compress(contenido, mtime=0))
        reg = {"nombre": nombre, "fecha": hoy.isoformat(), "sha256": sha, "bytes": len(contenido), "archivo": dest.name}
    with open(carpeta / "indice.jsonl", "a") as fh:
        fh.write(json.dumps(reg) + "\n")
    podar(carpeta, hoy)
    return dest


def podar(carpeta: Path, hoy: dt.date | None = None, dias: int = RETENCION_DIAS) -> list[str]:
    """Borra las copias con más de `dias` días salvo la primera de cada mes natural (por nombre). Devuelve las borradas."""
    hoy = hoy or dt.date.today()
    copias: dict[tuple[str, str], list[tuple[dt.date, Path]]] = {}
    for p in Path(carpeta).glob("*.csv.gz"):
        m = _RX.match(p.name)
        if m:
            f = dt.date.fromisoformat(m["fecha"])
            copias.setdefault((m["nombre"], f"{f:%Y-%m}"), []).append((f, p))
    usadas = {r.get("igual_a") for r in _indice(Path(carpeta))}      # una descarga posterior idéntica apunta a ella
    borradas = []
    for lista in copias.values():
        lista.sort()
        for f, p in lista[1:]:                       # la primera del mes se queda siempre
            if (hoy - f).days > dias and p.name not in usadas:
                p.unlink()
                borradas.append(p.name)
    return borradas


def leer(raw: Path, nombre: str, fecha: str) -> bytes:
    """Contenido archivado de `nombre` en `fecha` (sigue los «igual_a» del índice)."""
    carpeta = Path(raw) / "archivo"
    for r in reversed(_indice(carpeta)):
        if r["nombre"] == nombre and r["fecha"] == fecha:
            return gzip.decompress((carpeta / (r["archivo"] or r["igual_a"])).read_bytes())
    raise FileNotFoundError(f"{nombre} {fecha}: no está en {carpeta}/indice.jsonl")
