"""Paquete del día de C1 «Claude gestor» (docs/factors/C1_claude_gestor_spec.md v1.0 §1.2). SIN IA: solo Python.

Contenido (cada parte es tolerante: si falla, queda `{"error": …}` y el resto sale igual):
- `cuenta`: efectivo, valor, posiciones y órdenes abiertas de la cuenta PAPER del perfil `C1` (o una cuenta SIMULADA de
  100 000 $ en efectivo en los ensayos sin claves, marcada `simulada: true`), y su máximo y caída desde máximo
  (historial diario de Alpaca) para la regla de −35 %;
- `precios`: instantánea de Alpaca (feed IEX / indicative / cripto) de las posiciones y de una lista fija de vigilados
  (VIGILADOS, versionada aquí; no restringe el universo), y los últimos cierres del warehouse (yfinance) de «Mis activos»;
- `regimen`: régimen y capas del último signal semanal (cuadrante, ciclo de deuda, ciclo largo, liquidez, crédito);
- `alertas`: alertas de flujos de los últimos días (src/report/alertas.py), resumidas;
- `diagnosticos`: notas de `obsidian/Diagnosticos/` de los últimos 7 días, si existen (recortadas);
- `panel`: el resumen de reglas fijas de arriba del panel (src/report/panel.py `resumen`);
- `diario`: las últimas decisiones de C1 (research/paper/decisiones_c1.jsonl): nota, órdenes con su razón, rechazos y
  ejecuciones.
El hash (`sha256` del JSON canónico sin el propio campo) va en el registro; el paquete completo se guarda fuera de git.

Uso: .venv/bin/python -m src.paper.c1_paquete [--simulada] > paquete.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

from src.broker import alpaca as A
from src.broker import c1_guardia as G

REPO = A.REPO
LOG = REPO / "research" / "paper" / "decisiones_c1.jsonl"
DIAGNOSTICOS = REPO / "obsidian" / "Diagnosticos"
REPORTS = REPO / "obsidian" / "Reports"
VERSION = "c1-paquete-1"
VIGILADOS = ["SPY", "QQQ", "IWM", "DIA", "EFA", "VGK", "EWJ", "EEM", "URTH", "TLT", "IEF", "IEI", "SHY", "TIP", "HYG",
             "LQD", "GLD", "SLV", "USO", "DBC", "VNQ", "XLE", "XLK", "XLF", "XLV", "XLU", "XLP", "XLI", "XLB", "XLC",
             "XLY", "XLRE"]
VIGILADOS_CRIPTO = ["BTC/USD", "ETH/USD"]
CUENTA_SIMULADA = 100_000.0
N_DIARIO = 20
DIAS_DIAGNOSTICOS = 7
MAX_DIAGNOSTICOS = 3
MAX_CHARS_DIAGNOSTICO = 4000


def _error(e: Exception) -> dict:
    return {"error": f"{type(e).__name__}: {str(e)[:200]}"}


def hash_paquete(p: dict) -> str:
    sin = {k: v for k, v in p.items() if k != "sha256"}
    return hashlib.sha256(json.dumps(sin, sort_keys=True, ensure_ascii=False, default=str,
                                     separators=(",", ":")).encode()).hexdigest()


def leer_registro(ruta: Path | None = None) -> list[dict]:
    ruta = ruta or LOG
    if not ruta.exists():
        return []
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


# --------------------------------------------------------------------------- partes
def clase_alpaca(asset_class: str | None) -> str:
    return {"us_equity": "accion", "us_option": "opcion", "crypto": "cripto"}.get(str(asset_class or ""), "accion")


def cuenta_alpaca(c: A.Cliente) -> dict:
    cu = c.cuenta()
    pos = c.posiciones()
    out = {"simulada": False, "perfil": c.cred.perfil, "numero": A.enmascara_cuenta(cu.get("account_number")),
           "efectivo": float(cu.get("cash") or 0), "valor": float(cu.get("equity") or 0),
           "poder_de_compra_ignorado": cu.get("buying_power"), "estado": cu.get("status"),
           "posiciones": [{"simbolo": p.get("symbol"), "clase": clase_alpaca(p.get("asset_class")),
                           "cantidad": float(p.get("qty") or 0), "precio_medio": p.get("avg_entry_price"),
                           "precio": p.get("current_price"), "valor": p.get("market_value"),
                           "pl_no_realizado_pct": p.get("unrealized_plpc")} for p in pos],
           "ordenes_abiertas": len(c.ordenes_abiertas())}
    try:
        h = c.historial_cartera()
        eq = [float(x) for x in (h.get("equity") or []) if x is not None]
        if eq:
            out["maximo_valor"] = max(eq + [out["valor"]])
            out["caida_desde_maximo"] = round(out["valor"] / out["maximo_valor"] - 1, 4) if out["maximo_valor"] else None
    except A.AlpacaError as e:
        out["historial"] = _error(e)
    return out


def cuenta_simulada() -> dict:
    return {"simulada": True, "aviso": "ENSAYO sin claves de C1: cuenta ficticia, no es la cuenta paper",
            "efectivo": CUENTA_SIMULADA, "valor": CUENTA_SIMULADA, "posiciones": [], "ordenes_abiertas": 0,
            "maximo_valor": CUENTA_SIMULADA, "caida_desde_maximo": 0.0}


def precios_alpaca(c: A.Cliente, cuenta: dict) -> dict:
    pos = cuenta.get("posiciones") or []
    acc = sorted({p["simbolo"] for p in pos if p["clase"] == "accion"} | set(VIGILADOS))
    opc = sorted({p["simbolo"] for p in pos if p["clase"] == "opcion"})
    cri = sorted({p["simbolo"] for p in pos if p["clase"] == "cripto"} | set(VIGILADOS_CRIPTO))
    out: dict = {"fuente": "Alpaca (acciones feed IEX, no consolidado; opciones feed indicative, retrasado)"}
    try:
        inst = c.instantaneas(acc)
        out["acciones"] = {s: {"precio": A.precio_de(inst.get(s) or {}),
                               "cierre_anterior": ((inst.get(s) or {}).get("prevDailyBar") or {}).get("c")}
                           for s in acc}
    except A.AlpacaError as e:
        out["acciones"] = _error(e)
    if opc:
        try:
            io = c.instantaneas_opciones(opc)
            out["opciones"] = {s: {"bid": ((io.get(s) or {}).get("latestQuote") or {}).get("bp"),
                                   "ask": ((io.get(s) or {}).get("latestQuote") or {}).get("ap")} for s in opc}
        except A.AlpacaError as e:
            out["opciones"] = _error(e)
    try:
        ic = c.instantaneas_cripto(cri)
        out["cripto"] = {s: {"precio": A.precio_de(ic.get(s) or {})} for s in cri}
    except A.AlpacaError as e:
        out["cripto"] = _error(e)
    return out


def cierres_warehouse(X: dict | None = None) -> dict:
    """Últimos cierres de «Mis activos» (yfinance, warehouse local) con su variación a 1, 5 y 21 sesiones."""
    from src.report import alertas as AL
    X = X if X is not None else AL.cargar()
    c = X["cierre"]
    out = {}
    for t in c.columns:
        s = c[t].dropna()
        if len(s) < 22:
            continue
        out[t] = {"fecha": str(s.index[-1].date()), "cierre": round(float(s.iloc[-1]), 4),
                  **{f"var_{n}": round(float(s.iloc[-1] / s.iloc[-1 - n] - 1), 4) for n in (1, 5, 21)}}
    return {"fuente": "warehouse (yfinance; la última fila puede ser de una sesión en curso)", "activos": out}


def ultimo_signal() -> tuple[dict | None, str | None]:
    xs = sorted(REPORTS.glob("*_signal.json"))
    if not xs:
        return None, None
    return json.loads(xs[-1].read_text(encoding="utf-8")), xs[-1].name


def regimen(s: dict | None, nombre: str | None = None) -> dict:
    if not s:
        return {"error": "sin signal semanal"}
    cr = {k: v for k, v in (s.get("credit") or {}).items() if k != "indicators"}
    return {"signal": nombre, "asof": s.get("asof"), "regimen": s.get("regime"), "ciclo_deuda": s.get("debt_cycle"),
            "ciclo_largo": s.get("long_cycle"), "liquidez": s.get("liquidity"), "credito": cr,
            "aviso": "cuadrante descriptivo del proyecto; las reglas de régimen no superaron al ajuste por volatilidad"}


def alertas(hoy: dt.date) -> list[dict]:
    from src.report import alertas as AL
    R = AL.calcular_seguro(None, hoy)
    if not R:
        return [{"error": "alertas no disponibles"}]
    return [{"fecha": str(e["fecha"])[:10], "ticker": e.get("ticker"), "tipo": e.get("tipo"), "fuerza": e.get("fuerza"),
             "frase": e.get("frase")} for e in AL.recientes(R)][:30]


def diagnosticos(hoy: dt.date, carpeta: Path = DIAGNOSTICOS) -> list[dict]:
    """Notas de diagnóstico de los últimos 7 días (por la fecha del nombre AAAA-MM-DD_…). Sin carpeta: lista vacía."""
    if not carpeta.is_dir():
        return []
    out = []
    for p in sorted(carpeta.glob("*.md"), reverse=True):
        try:
            f = dt.date.fromisoformat(p.name[:10])
        except ValueError:
            continue
        if 0 <= (hoy - f).days <= DIAS_DIAGNOSTICOS:
            t = p.read_text(encoding="utf-8")
            out.append({"fichero": p.name, "fecha": str(f), "texto": t[:MAX_CHARS_DIAGNOSTICO],
                        "recortado": len(t) > MAX_CHARS_DIAGNOSTICO})
        if len(out) >= MAX_DIAGNOSTICOS:
            break
    return out


def resumen_panel(s: dict | None) -> list[str]:
    if not s:
        return []
    from src.report import panel as P
    es, _ = P.escenarios_completos(s)
    return [x.replace("**", "") for x in P.resumen(s, es)]


def diario(registro: list[dict], n: int = N_DIARIO) -> list[dict]:
    out = []
    for r in registro[-n:]:
        prop = r.get("propuesta") or {}
        out.append({"fecha": r.get("fecha"), "opera": r.get("opera"), "motivo_no_opera": r.get("motivo_no_opera"),
                    "resumen": prop.get("resumen"), "nota_diario": prop.get("nota_diario"),
                    "ordenes": [{k: o.get(k) for k in ("simbolo", "lado", "cantidad", "importe_usd", "razon",
                                                       "cambiaria_de_opinion")} for o in prop.get("ordenes") or []
                                if isinstance(o, dict)],
                    "rechazadas": [{"simbolo": (x.get("orden") or {}).get("simbolo"), "motivo": x.get("motivo")}
                                   for x in r.get("rechazadas") or []],
                    "ejecuciones": [{k: e.get(k) for k in ("simbolo", "lado", "estado", "qty_ejecutada", "precio_medio")}
                                    for e in r.get("ejecuciones") or []],
                    "valor_cuenta": (r.get("paquete") or {}).get("valor_cuenta")})
    return out


# --------------------------------------------------------------------------- todo junto
def armar(*, fecha: str, mercado: dict | None, cuenta: dict, precios: dict, regimen_: dict, alertas_: list,
          diagnosticos_: list, panel_: list, diario_: list, cierres: dict | None = None) -> dict:
    """Paquete (pura): junta las partes y le pone el hash."""
    p = {"version": VERSION, "mandato": G.VERSION_MANDATO, "fecha": fecha,
         "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "mercado": mercado,
         "cuenta": cuenta, "precios": precios, "cierres_warehouse": cierres, "regimen": regimen_, "alertas": alertas_,
         "diagnosticos": diagnosticos_, "panel": panel_, "diario": diario_,
         "limites": {"max_ordenes_dia": G.MAX_ORDENES, "caida_max_tolerable": -0.35,
                     "compras_hasta": "el efectivo (sin apalancamiento; el poder de compra se ignora)"}}
    p["sha256"] = hash_paquete(p)
    return p


def _seguro(fn, *a, defecto=None):
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001 — una parte que falla no tumba el paquete
        return _error(e) if defecto is None else defecto + [_error(e)]


def recoger(c: A.Cliente | None, hoy: dt.date | None = None, *, registro: list[dict] | None = None) -> dict:
    """Paquete con datos reales. `c` None = ensayo sin claves (cuenta simulada, sin precios de Alpaca)."""
    hoy = hoy or dt.date.today()
    mercado = None
    if c is not None:
        mercado = A.estado_mercado(c.reloj())
        cuenta = cuenta_alpaca(c)
        precios = _seguro(precios_alpaca, c, cuenta)
    else:
        cuenta, precios = cuenta_simulada(), {"error": "sin claves de C1: sin precios de Alpaca (ver cierres_warehouse)"}
    try:
        s, nombre = ultimo_signal()
    except Exception:  # noqa: BLE001
        s, nombre = None, None
    return armar(fecha=hoy.isoformat(), mercado=mercado, cuenta=cuenta, precios=precios,
                 regimen_=_seguro(regimen, s, nombre), alertas_=_seguro(alertas, hoy, defecto=[]),
                 diagnosticos_=_seguro(diagnosticos, hoy, defecto=[]), panel_=_seguro(resumen_panel, s, defecto=[]),
                 diario_=diario(leer_registro() if registro is None else registro), cierres=_seguro(cierres_warehouse))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Paquete del día de C1 (sin IA)")
    ap.add_argument("--simulada", action="store_true", help="cuenta ficticia (ensayo sin claves de C1)")
    a = ap.parse_args(argv)
    c = None if a.simulada else A.cliente("C1")
    print(json.dumps(recoger(c), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
