"""Explicador de los diagnósticos automáticos (docs/panel/diagnosticos_v0.md §4-§5): orquesta disparadores →
paquete (sin IA) → nota con `claude -p` → registro, actualizaciones y seguimiento a 5 y 20 días (sin IA).

DESCRIPTIVO. Límites (§5, aprobados el 19-nov-2026):
- Tope de 3 notas por semana (semana ISO de la ejecución), con marcas en $FIN_DATA_ROOT/logs/.diag_notas. Si hay más
  eventos se queda el de mayor tamaño; el resto queda como línea en «Hoy» (con su paquete de datos, sin hipótesis).
- `claude -p` con un prompt fijo versionado (src/diag/prompt_v1.md), SOLO las herramientas Read y Write: lectura de la
  carpeta del paquete y escritura de UN fichero en obsidian/Diagnosticos/. Sin Bash ni web; denegado leer
  $FIN_DATA_ROOT/config/ y research/paper/; sin ajustes de usuario/proyecto (--restricted) ni MCP. Plazo: 10 min.
- Si Claude falla, no hay red o FIN_DIAG_CLAUDE=0: queda el paquete y la tarjeta de «Hoy» sale sin hipótesis.
- Las notas NO se commitean (obsidian/Diagnosticos/*.md está en .gitignore): así no ensucian el árbol que exigen los
  registros en vivo (E1/B1/B1′ el día 3, INT-11 el día 20). Ver el informe de construcción.
- La primera ejecución (sin estado) solo siembra lo visto; no escribe notas de días pasados.
Uso: .venv/bin/python -m src.diag.explicador [--hoy AAAA-MM-DD] [--fecha AAAA-MM-DD --forzar] [--sin-claude]
     [--seguimiento] [--sin-noticias]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.diag import contexto as C
from src.diag import disparadores as D
from src.diag import noticias as N

REPO = Path(__file__).resolve().parents[2]
PROMPT = Path(__file__).with_name("prompt_v1.md")
PROMPT_VERSION = "v1"
PLAZO_S = 600
SECCIONES = ["## 1. Qué ha pasado", "## 2. Hipótesis de causa", "## 3. Qué dicen los modelos", "## 4. Fuentes",
             "## 5. Comprobaciones automáticas"]
AVISO_NOTA = "Explicación posterior; no es señal de compra o venta"


# ============================================================================================ rutas
def notas_dir() -> Path:
    return Path(os.environ.get("FIN_DIAG_NOTAS", REPO / "obsidian" / "Diagnosticos"))


def logs_dir() -> Path:
    return D.root() / "logs"


def marcas_path() -> Path:
    return logs_dir() / ".diag_notas"


def registro_path() -> Path:
    return D.root() / "diag" / "eventos.jsonl"


def aciertos_path() -> Path:
    return Path(os.environ.get("FIN_DIAG_ACIERTOS", REPO / "research" / "diag" / "aciertos.jsonl"))


def claude_bin() -> str:
    return os.environ.get("FIN_DIAG_CLAUDE_BIN", str(Path.home() / ".local" / "bin" / "claude"))


def claude_activo() -> bool:
    return os.environ.get("FIN_DIAG_CLAUDE", "1").strip().lower() not in ("0", "no", "false", "off")


# ============================================================================================ cupo
def _semana(d) -> str:
    y, w, _ = pd.Timestamp(d).isocalendar()
    return f"{y}-W{w:02d}"


def leer_marcas() -> list[dict]:
    try:
        return [json.loads(x) for x in marcas_path().read_text().splitlines() if x.strip()]
    except Exception:  # noqa: BLE001
        return []


def cupo_restante(hoy) -> int:
    s = _semana(hoy)
    return max(0, D.UMBRALES["tope_semana"] - sum(1 for m in leer_marcas() if m.get("semana") == s))


def marcar(hoy, fecha_evento, nota: str | None) -> None:
    p = marcas_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"semana": _semana(hoy), "fecha_evento": str(pd.Timestamp(fecha_evento).date()),
                            "hora": datetime.now().isoformat(timespec="seconds"), "nota": nota}, ensure_ascii=False) + "\n")


# ============================================================================================ claude
def slug(evento: dict | None) -> str:
    if not evento or not evento.get("disparos"):
        return "ensayo"
    d = max(evento["disparos"], key=lambda d: (not d.get("repetido"), d["tamano"]))
    c = str(d["clave"]).split("|")[0].lower()
    return re.sub(r"[^a-z0-9]+", "_", f"{d['tipo']}_{c}" if d["tipo"] not in ("conjunto", "regimen") else d["tipo"]).strip("_")


def prompt(paquete: Path, nota: Path, fecha) -> str:
    g = paquete.parent / "movimientos_sigma.png"
    return (PROMPT.read_text().replace("{PAQUETE}", str(paquete)).replace("{NOTA}", str(nota))
            .replace("{FECHA}", str(pd.Timestamp(fecha).date())).replace("{GRAFICO}", str(g) if g.exists() else "(no hay)"))


def _regla(herr: str, ruta: Path, todo: bool = False) -> str:
    """Regla de permiso con ruta absoluta («//ruta» en la sintaxis de Claude Code)."""
    r = str(ruta.resolve() if ruta.exists() else ruta)
    return f"{herr}(/{r}{'/**' if todo else ''})"


def argumentos(paquete_dir: Path, nota: Path) -> list[str]:
    cfg = D.root() / "config"
    return [claude_bin(), "-p", "--output-format", "json", "--restricted", "--tools", "Read,Write",
            "--permission-mode", "dontAsk", "--strict-mcp-config", "--no-session-persistence",
            "--disable-slash-commands", "--add-dir", str(nota.parent),
            "--allowedTools", _regla("Read", paquete_dir, True), _regla("Edit", nota),
            "--disallowedTools", "Bash", "WebFetch", "WebSearch",
            _regla("Read", cfg, True), _regla("Edit", cfg, True), _regla("Read", REPO / "research" / "paper", True),
            _regla("Read", D.root() / "alpaca", True)] + (
        ["--model", os.environ["FIN_DIAG_MODELO"]] if os.environ.get("FIN_DIAG_MODELO") else [])


def lanzar(texto: str, paquete_dir: Path, nota: Path, plazo: int = PLAZO_S) -> dict:
    """Ejecuta claude -p (cwd = carpeta del paquete; el prompt va por stdin). Nunca lanza excepción."""
    t0 = time.monotonic()
    try:
        r = subprocess.run(argumentos(paquete_dir, nota), input=texto, capture_output=True, text=True,
                           cwd=str(paquete_dir), timeout=plazo)
        out = {"rc": r.returncode, "segundos": round(time.monotonic() - t0, 1), "stderr": r.stderr[-500:]}
        try:
            j = json.loads(r.stdout)
            out.update({k: j.get(k) for k in ("total_cost_usd", "num_turns", "duration_ms", "is_error", "result")})
            out["uso"] = j.get("usage")
        except Exception:  # noqa: BLE001
            out["stdout"] = r.stdout[-500:]
        return out
    except subprocess.TimeoutExpired:
        return {"rc": None, "error": f"plazo de {plazo} s agotado", "segundos": round(time.monotonic() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"rc": None, "error": f"{type(e).__name__}: {e}", "segundos": round(time.monotonic() - t0, 1)}


def validar(texto: str) -> list[str]:
    """Lo que le falta a una nota para cumplir el formato fijo (§4)."""
    falta = [s for s in SECCIONES if s not in texto]
    if AVISO_NOTA not in texto[:400]:
        falta.insert(0, "aviso inicial")
    if not re.search(r"### H1\.", texto):
        falta.append("hipótesis H1")
    if len(re.findall(r"^### H\d", texto, flags=re.M)) > 4:
        falta.append("máximo 4 hipótesis")
    if comprobaciones(texto) is None:
        falta.append("bloque JSON de comprobaciones")
    return falta


def comprobaciones(texto: str) -> list[dict] | None:
    i = texto.find("## 5. Comprobaciones automáticas")
    if i < 0:
        return None
    m = re.search(r"```json\s*(.*?)```", texto[i:], flags=re.S)
    if not m:
        return None
    try:
        x = json.loads(m.group(1))
        return x if isinstance(x, list) else None
    except json.JSONDecodeError:
        return None


def urls_fuera_del_paquete(texto: str, paquete: dict) -> list[str]:
    """URLs citadas en la nota que no están en el paquete (la nota solo puede citar las del paquete)."""
    n = paquete.get("noticias") or {}
    validas = {a.get("url") for a in (n.get("gdelt") or []) + (n.get("oficiales") or [])}
    validas |= {u for u in (n.get("fuentes") or {}).values()}
    validas |= {c.get("url") for c in n.get("consultas") or []}
    citadas = set(re.findall(r"https?://[^\s\)\]>»\"']+", texto))
    return sorted(u.rstrip(".,;") for u in citadas if u.rstrip(".,;") not in validas)


def cabecera(evento: dict | None, fecha, meta: dict) -> str:
    dis = [d["texto"] for d in (evento or {}).get("disparos", [])] or ["ninguno (ensayo pedido a mano)"]
    lineas = ["---", "tipo: diagnostico", f"fecha_evento: {pd.Timestamp(fecha).date()}",
              f"generado: {datetime.now().isoformat(timespec='minutes')}", f"prompt: {PROMPT_VERSION}",
              f"paquete: {meta.get('paquete')}", f"duracion_s: {meta.get('segundos')}",
              f"coste_usd_estimado: {meta.get('total_cost_usd')}", "disparadores:"]
    lineas += [f"  - {json.dumps(t, ensure_ascii=False)}" for t in dis]
    if meta.get("avisos"):
        lineas.append("avisos_validacion:")
        lineas += [f"  - {json.dumps(a, ensure_ascii=False)}" for a in meta["avisos"]]
    return "\n".join(lineas + ["---", ""]) + "\n"


# ============================================================================================ registro
def registrar(fila: dict) -> None:
    p = registro_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(fila, ensure_ascii=False, default=str) + "\n")


def leer_registro() -> list[dict]:
    try:
        return [json.loads(x) for x in registro_path().read_text().splitlines() if x.strip()]
    except Exception:  # noqa: BLE001
        return []


def nota_abierta(fecha, cal: pd.DatetimeIndex | None = None) -> Path | None:
    """Nota de un evento de las 5 sesiones anteriores (o del mismo día): las actualizaciones van ahí."""
    f = pd.Timestamp(fecha)
    lim = f - pd.offsets.BDay(D.UMBRALES["enfriamiento"])
    cand = []
    for p in notas_dir().glob("*.md"):
        try:
            fp = pd.Timestamp(p.name[:10])
        except Exception:  # noqa: BLE001
            continue
        if lim <= fp <= f:
            cand.append((fp, p))
    return max(cand)[1] if cand else None


def anadir_actualizacion(nota: Path, evento: dict) -> None:
    txt = nota.read_text()
    linea = (f"- **{evento['fecha'].date()}**: " + "; ".join(d["texto"] + (" (repetido)" if d.get("repetido") else "")
                                                             for d in evento["disparos"]))
    marca = "## Actualizaciones (automáticas, sin IA)"
    if marca not in txt:
        txt = txt.rstrip() + f"\n\n{marca}\n"
    nota.write_text(txt.rstrip() + "\n" + linea + "\n")


# ============================================================================================ un evento
def paquete(fecha, evento: dict | None, X: dict, con, con_noticias: bool = True, transporte=None) -> tuple[Path, dict]:
    fecha = pd.Timestamp(fecha)
    dst = C.paquetes_dir() / str(fecha.date())
    ext = C.cargar_extras(con)
    P0 = C.construir(fecha, evento, X, con, None, None, ext)
    nots = None
    if con_noticias:
        try:
            nots = N.recoger(fecha, evento, P0["movimientos"], transporte=transporte, guardar=N.ruta(fecha))
        except Exception as e:  # noqa: BLE001
            nots = {"errores": {"noticias": f"{type(e).__name__}: {e}"}}
    P = C.construir(fecha, evento, X, con, nots, dst, ext)
    return dst / "paquete.json", P


def explicar(fecha, evento: dict | None, pq: Path, P: dict) -> dict:
    """Lanza Claude y valida la nota. Devuelve meta (nota, segundos, coste, avisos)."""
    fecha = pd.Timestamp(fecha)
    nd = notas_dir()
    nd.mkdir(parents=True, exist_ok=True)
    nota = nd / f"{fecha.date()}_{slug(evento)}.md"
    if nota.exists():
        nota = nd / f"{fecha.date()}_{slug(evento)}_{datetime.now().strftime('%H%M')}.md"
    meta = lanzar(prompt(pq, nota, fecha), pq.parent, nota)
    meta["paquete"] = str(pq)
    if not nota.exists():
        meta["nota"] = None
        meta["avisos"] = ["Claude no escribió la nota"]
        return meta
    txt = nota.read_text()
    if txt.startswith("---"):   # si Claude puso su propia cabecera YAML, se quita (la pone el sistema)
        partes = txt.split("---", 2)
        txt = partes[2].lstrip() if len(partes) == 3 else txt
    av = validar(txt) + [f"URL fuera del paquete: {u}" for u in urls_fuera_del_paquete(txt, P)]
    meta["avisos"] = av
    nota.write_text(cabecera(evento, fecha, meta) + txt)
    meta["nota"] = str(nota)
    return meta


# ============================================================================================ seguimiento
def _sesiones_despues(s: pd.Series, fecha: pd.Timestamp, h: int) -> tuple[float, float, pd.Timestamp] | None:
    s = s.dropna()
    a = s[s.index <= fecha]
    b = s[s.index > fecha]
    if not len(a) or len(b) < h:
        return None
    return float(a.iloc[-1]), float(b.iloc[h - 1]), b.index[h - 1]


def seguimiento(X: dict | None = None, extras: dict | None = None, hoy=None) -> list[str]:
    """A los 5 y 20 días hábiles: ¿se movió cada serie de las «comprobaciones» en la dirección esperada? Sin IA.
    Añade una línea a la nota y una fila a research/diag/aciertos.jsonl (fuera de git). Devuelve las líneas."""
    nd = notas_dir()
    if not nd.exists():
        return []
    X = X if X is not None else D.cargar()
    extras = extras if extras is not None else C.cargar_extras()
    ser = C.todas_series(X, extras)
    hechas = []
    for nota in sorted(nd.glob("*.md")):
        txt = nota.read_text()
        m = re.search(r"^fecha_evento: (\d{4}-\d{2}-\d{2})", txt, flags=re.M)
        comp = comprobaciones(txt)
        if not m or not comp:
            continue
        fecha = pd.Timestamp(m.group(1))
        for h in (5, 20):
            marca = f"<!-- seguimiento-{h} -->"
            if marca in txt:
                continue
            filas, lineas, completo = [], [], True
            for c in [c for c in comp if int(c.get("horizonte", 0)) == h]:
                k = c.get("serie")
                if k not in ser:
                    lineas.append(f"  - H{c.get('hipotesis')}: «{k}» no es una serie disponible; no se evalúa")
                    continue
                s, med, nom = ser[k]
                r = _sesiones_despues(s, fecha, h)
                if r is None:
                    completo = False
                    break
                a, b, fb = r
                cam = (b - a) * 100 if med == "pb" else 100 * (a / b - 1) if med == "inv_log" else 100 * (b / a - 1)
                ok = (cam > 0) == (c.get("direccion") == "sube") and cam != 0
                u = "pb" if med == "pb" else "%"
                lineas.append(f"  - H{c.get('hipotesis')}: {nom} {cam:+.2f} {u} hasta el {fb.date()} (esperaba "
                              f"«{c.get('direccion')}»: {'coincide' if ok else 'no coincide'}) — {c.get('que_significa', '')}")
                filas.append({"nota": nota.name, "fecha_evento": str(fecha.date()), "horizonte": h,
                              "hipotesis": c.get("hipotesis"), "serie": k, "direccion": c.get("direccion"),
                              "cambio": round(cam, 3), "coincide": bool(ok), "hasta": str(fb.date()),
                              "evaluado": str(pd.Timestamp(hoy or date.today()).date())})
            if not completo:
                continue
            if not lineas:
                lineas = ["  - (sin comprobaciones a este horizonte)"]
            cab = "## Seguimiento automático (sin IA)"
            if cab not in txt:
                txt = txt.rstrip() + f"\n\n{cab}\nDescriptivo: una dirección que coincide no prueba la hipótesis.\n"
            txt = txt.rstrip() + f"\n- **A {h} días hábiles** {marca}\n" + "\n".join(lineas) + "\n"
            nota.write_text(txt)
            p = aciertos_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a") as f:
                for fi in filas:
                    f.write(json.dumps(fi, ensure_ascii=False) + "\n")
            hechas.append(f"{nota.name} a {h} días")
    return hechas


# ============================================================================================ diario
def _evento_reg(e: dict | None, fecha, estado: str, pq: Path | None, meta: dict | None = None) -> dict:
    return {"fecha": str(pd.Timestamp(fecha).date()), "estado": estado, "ejecutado": datetime.now().isoformat(timespec="seconds"),
            "tamano": round(float(e["tamano"]), 2) if e else None, "tipos": e.get("tipos") if e else [],
            "disparos": [d["texto"] + (" (repetido)" if d.get("repetido") else "") for d in (e or {}).get("disparos", [])],
            "paquete": str(pq) if pq else None, "nota": (meta or {}).get("nota"),
            "segundos": (meta or {}).get("segundos"), "coste_usd": (meta or {}).get("total_cost_usd"),
            "avisos": (meta or {}).get("avisos")}


def flujos_hoy(hoy) -> list[dict]:
    try:
        from src.report import alertas as AL
        R = AL.calcular_seguro(None, hoy)
        return R["eventos"] if R else []
    except Exception:  # noqa: BLE001
        return []


def diario(hoy=None, usar_claude: bool = True, con_noticias: bool = True, transporte=None, con=None,
           X: dict | None = None, flujos: list[dict] | None = None) -> list[str]:
    """Una ejecución diaria. Devuelve líneas de resumen (para el log y la notificación)."""
    hoy = pd.Timestamp(hoy or date.today()).normalize()
    cerrar = False
    if con is None:
        from src.warehouse import db
        con, cerrar = db.connect(read_only=True), True
    try:
        X = X if X is not None else D.cargar(con)
        est = D.leer_estado()
        nuevos, est2 = D.detectar(X, hoy.date(), est, flujos if flujos is not None else flujos_hoy(hoy.date()))
        res = []
        if not est:
            D.guardar_estado(est2)
            return [f"diagnósticos: primera ejecución, estado sembrado ({len(nuevos)} eventos recientes vistos, sin notas)"]
        cupo = cupo_restante(hoy)
        for e in sorted(nuevos, key=lambda e: -e["tamano"]):
            abierta = nota_abierta(e["fecha"])
            solo_vistos = all(d.get("visto") or d.get("repetido") for d in e["disparos"])
            if abierta is not None and (not e["nuevo"] or solo_vistos or pd.Timestamp(abierta.name[:10]) == e["fecha"]):
                anadir_actualizacion(abierta, e)
                registrar(_evento_reg(e, e["fecha"], "actualizacion", None, {"nota": str(abierta)}))
                res.append(f"actualización de {abierta.name}")
                continue
            if not e["nuevo"] or solo_vistos:
                # sin disparador nuevo y no repetido: el evento ya tuvo su oportunidad (nota, tope o fallo) en una
                # ejecución anterior; un disparo tardío en enfriamiento no abre nota ni gasta cupo
                registrar(_evento_reg(e, e["fecha"], "repetido_sin_nota_abierta" if not e["nuevo"]
                                      else "solo_vistos_sin_nota_abierta", None))
                continue
            pq, P = paquete(e["fecha"], e, X, con, con_noticias, transporte)
            if usar_claude and claude_activo() and cupo > 0:
                cupo -= 1
                marcar(hoy, e["fecha"], None)
                meta = explicar(e["fecha"], e, pq, P)
                estado = "nota" if meta.get("nota") else "fallo_claude"
                registrar(_evento_reg(e, e["fecha"], estado, pq, meta))
                res.append(f"{e['fecha'].date()}: " + (f"nota {Path(meta['nota']).name}" if meta.get("nota")
                                                       else f"sin nota ({meta.get('error') or meta.get('avisos')})"))
            else:
                motivo = "tope_semana" if cupo <= 0 else "sin_claude"
                registrar(_evento_reg(e, e["fecha"], motivo, pq))
                res.append(f"{e['fecha'].date()}: paquete sin nota ({motivo.replace('_', ' ')})")
        D.guardar_estado(est2)
        try:
            res += [f"seguimiento: {x}" for x in seguimiento(X, None, hoy)]
        except Exception as ex:  # noqa: BLE001
            res.append(f"seguimiento falló: {type(ex).__name__}: {ex}")
        return res
    finally:
        if cerrar:
            con.close()


def forzado(fecha, usar_claude: bool = True, con_noticias: bool = True, transporte=None) -> dict:
    """Ensayo: paquete (y nota) de un día aunque no haya disparador. Gasta cupo igual (marca)."""
    from src.warehouse import db
    fecha = pd.Timestamp(fecha).normalize()
    con = db.connect(read_only=True)
    try:
        X = D.cargar(con)
        ev = [e for e in D.agrupar(D.todos(X, None, fecha - pd.offsets.BDay(10)), D.calendario(X)) if e["fecha"] == fecha]
        e = ev[0] if ev else {"fecha": fecha, "disparos": [], "tipos": [], "tamano": 0.0, "nuevo": True, "forzado": True}
        e["forzado"] = True
        pq, P = paquete(fecha, e, X, con, con_noticias, transporte)
        if not (usar_claude and claude_activo()):
            registrar(_evento_reg(e, fecha, "forzado_sin_claude", pq))
            return {"paquete": str(pq)}
        marcar(date.today(), fecha, None)
        meta = explicar(fecha, e, pq, P)
        registrar(_evento_reg(e, fecha, "forzado_nota" if meta.get("nota") else "forzado_fallo", pq, meta))
        return meta
    finally:
        con.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Diagnósticos automáticos (descriptivos)")
    ap.add_argument("--hoy", default=None)
    ap.add_argument("--fecha", default=None, help="con --forzar: día del ensayo")
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--sin-claude", action="store_true")
    ap.add_argument("--sin-noticias", action="store_true")
    ap.add_argument("--seguimiento", action="store_true", help="solo el seguimiento a 5 y 20 días")
    a = ap.parse_args(argv)
    if a.seguimiento:
        for x in seguimiento():
            print("seguimiento:", x)
        return
    if a.forzar:
        print(json.dumps(forzado(a.fecha, not a.sin_claude, not a.sin_noticias), ensure_ascii=False, default=str, indent=1))
        return
    for x in diario(a.hoy, not a.sin_claude, not a.sin_noticias):
        print(x)


if __name__ == "__main__":
    main()
