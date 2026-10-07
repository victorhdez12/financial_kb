"""'Lectura' section: Claude narrative over the signal JSON, or a deterministic template.

Principle 1 (PLAN.md): Python computes, the LLM interprets. Claude receives ONLY the signal
JSON and is told not to introduce numbers. A validator then checks that every number in the
narrative appears in the JSON (after rounding); if too many do not, we fall back to the template.
"""
from __future__ import annotations

import json
import os
import re

MODEL = "claude-opus-5-5"
SYSTEM = (
    "Eres el estratega macro de un comité de inversión personal (estilo Bridgewater: cuadrantes de "
    "crecimiento/inflación, ciclos de deuda, liquidez). Escribe en español, 250-400 palabras, en Markdown "
    "sin encabezados de nivel 1-2. Reglas estrictas: (1) usa SOLO cifras que aparezcan literalmente en el "
    "JSON; no calcules ni inventes números nuevos; (2) distingue hechos del JSON de interpretación; "
    "(3) señala explícitamente la baja confianza (pocos episodios, datos revisados si vintage_mode='latest'); "
    "(4) termina con 2-3 'qué vigilar' concretos ligados a indicadores del JSON; (5) no des recomendaciones "
    "de compra/venta: es apoyo a la decisión, no asesoramiento."
)
SMALL_INTS_OK = set(range(0, 13)) | {24}


def numbers_in(text: str) -> list[str]:
    return re.findall(r"(?<![\w.])-?\d+(?:[.,]\d+)?", text)


def json_number_tokens(obj) -> set[str]:
    toks: set[str] = set()
    for tok in numbers_in(json.dumps(obj, ensure_ascii=False)):
        try:
            v = float(tok)
        except ValueError:
            continue
        for n in (0, 1, 2):
            toks.add(f"{round(v, n):.{n}f}")
            toks.add(f"{round(abs(v), n):.{n}f}")
    return toks


def unsupported_numbers(text: str, signal: dict) -> list[str]:
    allowed = json_number_tokens(signal)
    bad = []
    for tok in numbers_in(text):
        norm = tok.replace(",", ".")
        try:
            v = float(norm)
        except ValueError:
            continue
        if v.is_integer() and (int(abs(v)) in SMALL_INTS_OK or 1900 <= abs(v) <= 2100):
            continue
        if norm.lstrip("-") not in allowed and norm not in allowed:
            bad.append(tok)
    return bad


def claude_reading(signal: dict) -> str | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        req = dict(model=MODEL, max_tokens=8000, system=SYSTEM, output_config={"effort": "medium"},
                   messages=[{"role": "user", "content": "JSON de señal:\n```json\n"
                              + json.dumps(signal, ensure_ascii=False, indent=1) + "\n```"}])
        try:  # server-side refusal fallback (routes a safety decline to a fallback model)
            msg = client.beta.messages.create(**req, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        except anthropic.BadRequestError:
            msg = client.messages.create(**req)
        if msg.stop_reason == "refusal":
            return None
        return "".join(b.text for b in msg.content if b.type == "text").strip() or None
    except Exception as exc:  # network/auth/API errors -> deterministic fallback
        print(f"  Claude no disponible ({type(exc).__name__}); se usa plantilla")
        return None


def template_reading(s: dict) -> str:
    r, dc, lq, cr = s["regime"], s["debt_cycle"], s["liquidity"], s["credit"]
    ch = s["changes"]
    lines = [
        f"- **Régimen:** {r['quadrant']} (crecimiento {r['G_state']}, G = {r['G']}, ΔG 6m = {r['G_d6']}; "
        f"inflación {r['I_state']}, subyacente 6m anualizada = {r['core_6m']} %, aceleración 3m = {r['core_accel_3m']} pp).",
        f"- **Cambios:** hace 1 mes {ch['1m']['quadrant']}, hace 3 meses {ch['3m']['quadrant']}, "
        f"hace 6 meses {ch['6m']['quadrant']}.",
        f"- **Ciclo de deuda corto:** {dc['phase']} (curva 10a−3m = {dc['curve']} pp; Δ fed funds 12m = {dc['ff_d12']} pp; "
        f"tipo real = {dc['real_ff']} pp).",
        f"- **Crédito:** semáforo {cr['light']} ({cr['reds']} rojos, {cr['ambers']} ámbar de {cr['n']} indicadores).",
        f"- **Liquidez:** {lq['state']} (score = {lq['score']}).",
        f"- **Ciclo largo:** {s['long_cycle']['stage']} — {s['long_cycle']['flags'] or 'sin alertas'}.",
    ]
    if s["analogs"]:
        a = s["analogs"][0]
        lines.append(f"- **Análogo más cercano:** {a['date']} ({a['quadrant']}, distancia {a['distance']}).")
    lines.append(f"- **Confianza:** baja-media; vintage_mode = {s['vintage_mode']}; los análogos son "
                 f"{len(s['analogs'])} episodios, no una distribución.")
    return "\n".join(lines)


def reading(signal: dict) -> tuple[str, str]:
    """Return (markdown, origin) where origin is 'claude', 'claude+warning' or 'plantilla'."""
    text = claude_reading(signal)
    if text:
        bad = unsupported_numbers(text, signal)
        if len(bad) <= 2:
            note = f"\n\n> Validador: cifras no encontradas en el JSON: {', '.join(bad)}" if bad else ""
            return text + note, "claude" if not bad else "claude+warning"
        print(f"  narrativa descartada: {len(bad)} cifras no respaldadas ({bad[:5]})")
    return template_reading(signal), "plantilla"
