"""Tarjeta «Diagnósticos» arriba en la pestaña «Hoy» del panel (docs/panel/diagnosticos_v0.md §1 y §5).

Lee el registro de eventos ($FIN_DATA_ROOT/diag/eventos.jsonl) de los últimos 7 días y, si hay nota, sus hipótesis
(títulos «### H…»). Si no hay nota (tope semanal, Claude falló o está apagado) sale el paquete de datos sin
hipótesis: los mayores movimientos en σ del paquete. Descriptivo; nunca lanza excepción.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from src.diag import explicador as E
from src.report.panel_paises import chip, esc

DIAS = 7
AVISO = ("Explicación posterior («ex post»): siempre suena convincente. No es una señal de compra o venta. Los "
         "disparadores son reglas fijas (docs/panel/diagnosticos_v0.md); las hipótesis las escribe Claude a partir "
         "de un paquete de datos y no se han validado.")
ESTADO = {"nota": ("ambar", "con nota"), "forzado_nota": ("gris", "ensayo con nota"),
          "tope_semana": ("gris", "sin nota: tope de 3 por semana"), "sin_claude": ("gris", "sin nota: Claude apagado"),
          "fallo_claude": ("rojo", "sin nota: Claude falló"), "forzado_sin_claude": ("gris", "ensayo sin nota"),
          "forzado_fallo": ("rojo", "ensayo: Claude falló"), "actualizacion": ("gris", "actualización")}


def hipotesis(nota: Path) -> list[str]:
    try:
        return [m.strip() for m in re.findall(r"^### (H\d.*)$", nota.read_text(), flags=re.M)][:4]
    except Exception:  # noqa: BLE001
        return []


def movimientos_paquete(pq: str | None, n: int = 5) -> list[str]:
    try:
        P = json.loads(Path(pq).read_text())
        out = []
        for m in P.get("movimientos", [])[:n]:
            u = "pb" if m.get("unidad") == "pb" else "%"
            out.append(f"{m['nombre']}: {m['cambio']:+.2f} {u} ({m['k_sigma63']:+.1f} σ)".replace(".", ",").replace("-", "−"))
        return out
    except Exception:  # noqa: BLE001
        return []


def recientes(hoy: date | None = None, dias: int = DIAS) -> list[dict]:
    h = pd.Timestamp(hoy or date.today())
    filas = [r for r in E.leer_registro() if pd.Timestamp(r["fecha"]) > h - pd.Timedelta(days=dias)
             and r.get("estado") != "actualizacion"]
    ult: dict[str, dict] = {}
    for r in filas:   # la última fila de cada día manda (p. ej. ensayo repetido)
        ult[r["fecha"]] = r
    return sorted(ult.values(), key=lambda r: r["fecha"], reverse=True)


def bloque_diag(hoy: date | None = None) -> str:
    try:
        ev = recientes(hoy)
    except Exception:  # noqa: BLE001
        ev = []
    if not ev:
        cuerpo = f"<p>{chip('verde', 'sin eventos')} Ningún disparador en los últimos {DIAS} días.</p>"
    else:
        items = []
        for r in ev:
            col, etq = ESTADO.get(r.get("estado"), ("gris", r.get("estado") or ""))
            dis = "; ".join(r.get("disparos") or []) or "sin disparador (ensayo)"
            nota = Path(r["nota"]) if r.get("nota") else None
            if nota is not None and nota.exists():
                hs = hipotesis(nota)
                det = ("<ol>" + "".join(f"<li>{esc(h)}</li>" for h in hs) + "</ol>") if hs else "<p class='nd'>nota sin hipótesis legibles</p>"
                det += f"<p class='small muted'>Nota completa en Obsidian: <code>obsidian/Diagnosticos/{esc(nota.name)}</code></p>"
            else:
                mv = movimientos_paquete(r.get("paquete"))
                det = ("<p class='small'>Sin hipótesis; datos del paquete (mayores movimientos en σ):</p><ul>"
                       + "".join(f"<li>{esc(m)}</li>" for m in mv) + "</ul>") if mv else "<p class='nd small'>sin paquete</p>"
            items.append(f"<li><strong>{esc(r['fecha'])}</strong> {chip(col, etq)} {esc(dis)}{det}</li>")
        cuerpo = "<ul class='diag'>" + "".join(items) + "</ul>"
    return (f'<div class="card diag" id="diagnosticos-hoy"><h3>Diagnósticos: ¿por qué se ha movido? '
            f'<span class="muted">(últimos {DIAS} días)</span></h3><p class="disc small"><strong>{esc(AVISO)}</strong></p>'
            f'{cuerpo}</div>')
