"""Alpaca en modo PAPER (cuenta simulada) ÚNICAMENTE: datos de mercado (feed IEX), reloj, cuenta y posiciones.

NUNCA opera con dinero real. El único endpoint de trading admitido es `https://paper-api.alpaca.markets`; el de datos,
`https://data.alpaca.markets` (solo lectura). Cualquier otra URL, y en particular el endpoint REAL
`https://api.alpaca.markets`, hace que el código se niegue (`EndpointNoPermitido`), aunque se configure en el .env o en
el entorno (`ALPACA_BASE_URL`, `APCA_API_BASE_URL`). Las redirecciones HTTP no se siguen.

Claves: `~/financial_archive/config/alpaca.env` (fuera de git; `FIN_ALPACA_ENV` para otra ruta) o variables de entorno
(`ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`; el entorno manda). Perfiles: sufijo `_<PERFIL>` (p. ej.
`ALPACA_API_KEY_ID_B1`), una cuenta paper por cartera (docs/broker/alpaca.md §3). Las claves no salen nunca en logs,
mensajes de error, panel ni registros: `Credenciales.__repr__` las oculta y todo mensaje de error pasa por
`enmascarar`. Si el fichero no tiene permisos 600, se avisa. Sin claves: «Alpaca no configurado» y nada más.

HTTP: `requests` vía `src.ingest._http.request` (plazo TOTAL por petición, no solo por lectura). No usa `alpaca-py`.

Uso:  python -m src.broker.alpaca estado [--perfil B1] [--json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlparse

log = logging.getLogger("broker.alpaca")

PAPER_TRADING = "https://paper-api.alpaca.markets"
DATOS = "https://data.alpaca.markets"
HOST_PAPER = "paper-api.alpaca.markets"
HOST_DATOS = "data.alpaca.markets"
HOST_REAL = "api.alpaca.markets"
FEED = "iex"   # gratuito; NO es todo el volumen consolidado (docs/broker/alpaca.md §6)
REPO = Path(__file__).resolve().parents[2]
MAPEO = REPO / "config" / "alpaca_etfs.json"


class AlpacaError(RuntimeError):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


class EndpointNoPermitido(AlpacaError):
    """URL que no es el paper de Alpaca (o su API de datos). Nunca se captura para seguir adelante."""


class NoConfigurado(AlpacaError):
    pass


# --------------------------------------------------------------------------- seguridad del endpoint
def comprobar_url(url: str, *, solo_trading: bool = False) -> str:
    """Devuelve la URL si es https y su host es el paper de Alpaca (o, si no `solo_trading`, el de datos).
    Se niega a todo lo demás, y con un mensaje explícito si es el endpoint de dinero real."""
    p = urlparse(str(url).strip())
    host = (p.hostname or "").lower()
    if host == HOST_REAL or (host.endswith(".alpaca.markets") and host not in (HOST_PAPER, HOST_DATOS)) \
            or host == "alpaca.markets":
        raise EndpointNoPermitido(f"endpoint de dinero REAL o desconocido de Alpaca ({host}): este código SOLO opera "
                                  f"en paper ({PAPER_TRADING}) y se niega")
    permitidos = {HOST_PAPER} if solo_trading else {HOST_PAPER, HOST_DATOS}
    if p.scheme != "https" or host not in permitidos or p.port not in (None, 443) or p.username or p.password:
        raise EndpointNoPermitido(f"URL no permitida ({p.scheme}://{host}): solo {PAPER_TRADING}"
                                  + ("" if solo_trading else f" y {DATOS}"))
    return str(url).strip().rstrip("/")


# --------------------------------------------------------------------------- credenciales
def ruta_env() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_ALPACA_ENV", "~/financial_archive/config/alpaca.env")))


def leer_env(ruta: Path) -> dict[str, str]:
    """KEY=VALUE por línea (admite `export`, comillas y comentarios `#`). No ejecuta nada."""
    out: dict[str, str] = {}
    try:
        texto = Path(ruta).read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return out
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        if linea.startswith("export "):
            linea = linea[7:].strip()
        k, v = linea.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        elif " #" in v:
            v = v.split(" #", 1)[0].strip()
        out[k.strip()] = v
    return out


def aviso_permisos(ruta: Path) -> str | None:
    """Mensaje si el fichero de claves es legible o escribible por grupo/otros (debe ser 600)."""
    try:
        modo = stat.S_IMODE(Path(ruta).stat().st_mode)
    except OSError:
        return None
    if modo & 0o077:
        return f"{ruta} tiene permisos {oct(modo)[2:]}: deberían ser 600 (chmod 600 {ruta})"
    return None


def normaliza_perfil(perfil: str | None) -> str:
    """'' = perfil por defecto. B1′/B1prima/B1P → B1P."""
    if not perfil:
        return ""
    p = perfil.strip().upper().replace("′", "P").replace("'", "P")
    return "B1P" if p in ("B1PRIMA", "B1PRIME", "B1P") else p


@dataclass(frozen=True)
class Credenciales:
    key_id: str = field(repr=False)
    secret: str = field(repr=False)
    perfil: str = ""
    cartera: str | None = None
    base_url: str = PAPER_TRADING
    origen: str = ""

    def __repr__(self) -> str:   # nunca las claves
        return (f"Credenciales(perfil={self.perfil or 'defecto'!r}, cartera={self.cartera!r}, "
                f"base_url={self.base_url!r}, origen={self.origen!r}, key_id='***', secret='***')")

    __str__ = __repr__

    def enmascarar(self, texto: str) -> str:
        s = str(texto)
        for x in (self.secret, self.key_id):
            if x:
                s = s.replace(x, "***")
        return s


_avisados: set[str] = set()


def cargar_credenciales(perfil: str | None = None, *, ruta: Path | None = None,
                        entorno: dict | None = None) -> Credenciales | None:
    """Credenciales del perfil, o None si no hay claves («Alpaca no configurado»).
    Lanza EndpointNoPermitido si la URL base configurada no es la del paper."""
    entorno = os.environ if entorno is None else entorno
    ruta = ruta_env() if ruta is None else Path(ruta)
    fichero = leer_env(ruta)
    if fichero:
        aviso = aviso_permisos(ruta)
        if aviso and aviso not in _avisados:
            _avisados.add(aviso)
            log.warning(aviso)
            print(f"AVISO: {aviso}", file=sys.stderr)
    p = normaliza_perfil(perfil)
    suf = f"_{p}" if p else ""

    def get(k: str) -> str | None:
        return entorno.get(k + suf) or fichero.get(k + suf) or None

    # cualquier URL base configurada (con o sin perfil, nombres propios o los de Alpaca) tiene que ser la del paper
    for k in ("ALPACA_BASE_URL", "APCA_API_BASE_URL"):
        for kk in {k, k + suf}:
            for fuente in (entorno, fichero):
                if fuente.get(kk):
                    comprobar_url(fuente[kk], solo_trading=True)
    key, sec = get("ALPACA_API_KEY_ID"), get("ALPACA_API_SECRET_KEY")
    if not key or not sec:
        return None
    base = get("ALPACA_BASE_URL") or get("APCA_API_BASE_URL") or PAPER_TRADING
    origen = "entorno" if entorno.get("ALPACA_API_KEY_ID" + suf) else str(ruta)
    cartera = get("ALPACA_CARTERA")
    return Credenciales(key_id=key, secret=sec, perfil=p, cartera=normaliza_perfil(cartera) or None,
                        base_url=comprobar_url(base, solo_trading=True), origen=origen)


def perfiles(ruta: Path | None = None, entorno: dict | None = None) -> list[str]:
    """Perfiles con clave configurada ('' = por defecto), sin leer los valores fuera de aquí."""
    entorno = os.environ if entorno is None else entorno
    claves = set(leer_env(ruta_env() if ruta is None else Path(ruta))) | set(entorno)
    out = []
    for k in sorted(claves):
        if k == "ALPACA_API_KEY_ID":
            out.append("")
        elif k.startswith("ALPACA_API_KEY_ID_"):
            out.append(k[len("ALPACA_API_KEY_ID_"):])
    return out


# --------------------------------------------------------------------------- transporte HTTP
Transporte = Callable[[str, str, dict, dict | None, dict | None, float], tuple[int, object]]


def _transporte_requests(metodo: str, url: str, cabeceras: dict, params: dict | None, cuerpo: dict | None,
                         plazo: float) -> tuple[int, object]:
    from src.ingest._http import request
    r = request(metodo, url, headers=cabeceras, params=params, json=cuerpo, timeout=(5, plazo), total=plazo,
                allow_redirects=False)
    if 300 <= r.status_code < 400:
        return r.status_code, {"message": "redirección no seguida (solo se admite el paper de Alpaca)"}
    try:
        return r.status_code, (r.json() if r.content else {})
    except ValueError:
        import re
        texto = " ".join(re.sub(r"<[^>]+>", " ", r.text).split())
        return r.status_code, {"message": texto[:160]}


class Cliente:
    """Cliente mínimo de la API REST v2 (trading paper + market data). `transporte` se sustituye en los tests."""

    def __init__(self, cred: Credenciales, *, transporte: Transporte | None = None, plazo: float = 20.0):
        self.cred = cred
        self.base = comprobar_url(cred.base_url, solo_trading=True)
        self._t = transporte or _transporte_requests
        self.plazo = plazo

    def __repr__(self) -> str:
        return f"Cliente({self.cred!r})"

    def _pide(self, metodo: str, base: str, ruta: str, params: dict | None = None, cuerpo: dict | None = None):
        url = comprobar_url(base + ruta)
        cab = {"APCA-API-KEY-ID": self.cred.key_id, "APCA-API-SECRET-KEY": self.cred.secret,
               "Accept": "application/json"}
        try:
            status, datos = self._t(metodo, url, cab, params, cuerpo, self.plazo)
        except EndpointNoPermitido:
            raise
        except Exception as e:   # el mensaje de requests puede llevar la URL; nunca las cabeceras, pero se enmascara
            raise AlpacaError(self.cred.enmascarar(f"{metodo} {ruta}: {type(e).__name__}: {e}")) from None
        if status >= 300:
            msg = datos.get("message") if isinstance(datos, dict) else str(datos)
            raise AlpacaError(self.cred.enmascarar(f"{metodo} {ruta}: HTTP {status}: {msg}"), status=status)
        return datos

    # ---- trading (paper)
    def reloj(self) -> dict:
        return self._pide("GET", self.base, "/v2/clock")

    def calendario(self, desde: dt.date, hasta: dt.date) -> list[dict]:
        return self._pide("GET", self.base, "/v2/calendar", {"start": desde.isoformat(), "end": hasta.isoformat()})

    def cuenta(self) -> dict:
        return self._pide("GET", self.base, "/v2/account")

    def posiciones(self) -> list[dict]:
        return self._pide("GET", self.base, "/v2/positions")

    def activo(self, simbolo: str) -> dict:
        return self._pide("GET", self.base, f"/v2/assets/{quote(simbolo.replace('/', ''), safe='')}")

    def enviar_orden(self, orden: dict) -> dict:
        return self._pide("POST", self.base, "/v2/orders", cuerpo=orden)

    def orden(self, orden_id: str) -> dict:
        return self._pide("GET", self.base, f"/v2/orders/{orden_id}")

    def ordenes_abiertas(self) -> list[dict]:
        return self._pide("GET", self.base, "/v2/orders", {"status": "open", "limit": 500})

    def orden_por_cliente(self, client_order_id: str) -> dict:
        return self._pide("GET", self.base, "/v2/orders:by_client_order_id", {"client_order_id": client_order_id})

    def contrato_opcion(self, simbolo: str) -> dict:
        """Contrato de opción (símbolo OCC): tradable, tipo call/put, vencimiento, precio de ejercicio. Solo lectura."""
        return self._pide("GET", self.base, f"/v2/options/contracts/{quote(simbolo, safe='')}")

    def historial_cartera(self, periodo: str = "1A", marco: str = "1D", desde: dt.date | None = None) -> dict:
        """Valor diario de la cuenta paper (timestamp, equity, profit_loss). Con `desde`, desde esa fecha. Solo lectura."""
        params = {"timeframe": marco, **({"start": desde.isoformat()} if desde else {"period": periodo})}
        return self._pide("GET", self.base, "/v2/account/portfolio/history", params)

    # ---- market data (feed IEX)
    def instantaneas(self, simbolos: list[str]) -> dict:
        """Por símbolo: latestTrade, latestQuote, minuteBar, dailyBar, prevDailyBar (feed IEX)."""
        return self._pide("GET", DATOS, "/v2/stocks/snapshots", {"symbols": ",".join(simbolos), "feed": FEED})

    def ultimas_barras(self, simbolos: list[str]) -> dict:
        """Última barra de 1 minuto por símbolo (feed IEX)."""
        d = self._pide("GET", DATOS, "/v2/stocks/bars/latest", {"symbols": ",".join(simbolos), "feed": FEED})
        return d.get("bars", {}) if isinstance(d, dict) else {}

    def instantaneas_opciones(self, simbolos: list[str]) -> dict:
        """Por contrato OCC: latestQuote, latestTrade (feed `indicative`, el gratuito: retrasado 15 min). Solo lectura."""
        d = self._pide("GET", DATOS, "/v1beta1/options/snapshots", {"symbols": ",".join(simbolos), "feed": "indicative"})
        return d.get("snapshots", {}) if isinstance(d, dict) else {}

    def instantaneas_cripto(self, simbolos: list[str]) -> dict:
        """Por par (p. ej. BTC/USD): latestQuote, latestTrade, minuteBar, dailyBar. Solo lectura."""
        d = self._pide("GET", DATOS, "/v1beta3/crypto/us/snapshots", {"symbols": ",".join(simbolos)})
        return d.get("snapshots", {}) if isinstance(d, dict) else {}

    def barras_diarias(self, simbolos: list[str], desde: dt.date, hasta: dt.date) -> dict[str, list[dict]]:
        d = self._pide("GET", DATOS, "/v2/stocks/bars",
                       {"symbols": ",".join(simbolos), "timeframe": "1Day", "start": desde.isoformat(),
                        "end": hasta.isoformat(), "feed": FEED, "adjustment": "raw", "limit": 10000})
        return d.get("bars", {}) if isinstance(d, dict) else {}


def cliente(perfil: str | None = None, **kw) -> Cliente | None:
    cred = cargar_credenciales(perfil)
    return Cliente(cred, **kw) if cred else None


# --------------------------------------------------------------------------- horario de mercado
def _iso(x: str | None) -> dt.datetime | None:
    if not x:
        return None
    return dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))


def estado_mercado(reloj: dict, ahora: dt.datetime | None = None) -> dict:
    """A partir de /v2/clock: abierto, minutos al cierre (si abierto), próxima apertura y cierre."""
    ts = ahora or _iso(reloj.get("timestamp")) or dt.datetime.now(dt.timezone.utc)
    cierre, apertura = _iso(reloj.get("next_close")), _iso(reloj.get("next_open"))
    abierto = bool(reloj.get("is_open"))
    minutos = (cierre - ts).total_seconds() / 60 if (abierto and cierre) else None
    return {"abierto": abierto, "minutos_al_cierre": None if minutos is None else round(minutos, 1),
            "proxima_apertura": apertura.isoformat() if apertura else None,
            "proximo_cierre": cierre.isoformat() if cierre else None, "hora": ts.isoformat()}


def precio_de(inst: dict) -> float | None:
    """Precio de referencia de una instantánea: punto medio de la cotización si es razonable, si no último trade,
    si no cierre de la última barra de 1 minuto."""
    q = inst.get("latestQuote") or {}
    bid, ask = float(q.get("bp") or 0), float(q.get("ap") or 0)
    if bid > 0 and ask > 0 and ask >= bid and (ask - bid) / ((ask + bid) / 2) < 0.01:
        return round((ask + bid) / 2, 4)
    t = inst.get("latestTrade") or {}
    if t.get("p"):
        return float(t["p"])
    b = inst.get("minuteBar") or {}
    return float(b["c"]) if b.get("c") else None


def cargar_mapeo(ruta: Path = MAPEO) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def simbolos_mapeo(mapeo: dict | None = None) -> dict[str, str]:
    m = mapeo or cargar_mapeo()
    return {tramo: v["etf"] for tramo, v in m["tramos"].items()}


def enmascara_cuenta(n: str | None) -> str:
    n = str(n or "")
    return ("…" + n[-4:]) if len(n) > 4 else "…"


# --------------------------------------------------------------------------- comando
def resumen(c: Cliente, simbolos: list[str] | None = None) -> dict:
    simbolos = simbolos or list(simbolos_mapeo().values())
    out: dict = {"perfil": c.cred.perfil or "defecto", "cartera": c.cred.cartera, "endpoint": c.base,
                 "feed": FEED, "mercado": estado_mercado(c.reloj())}
    cu = c.cuenta()
    out["cuenta"] = {k: cu.get(k) for k in ("status", "currency", "equity", "cash", "buying_power",
                                            "last_equity", "pattern_day_trader", "trading_blocked")}
    out["cuenta"]["numero"] = enmascara_cuenta(cu.get("account_number"))
    out["posiciones"] = [{k: p.get(k) for k in ("symbol", "qty", "avg_entry_price", "current_price",
                                                "market_value", "unrealized_pl")} for p in c.posiciones()]
    inst = c.instantaneas(simbolos)
    barras = c.ultimas_barras(simbolos)
    out["precios"] = {s: {"referencia": precio_de(inst.get(s) or {}),
                          "ultimo_trade": (inst.get(s) or {}).get("latestTrade", {}).get("p"),
                          "hora_trade": (inst.get(s) or {}).get("latestTrade", {}).get("t"),
                          "barra_1min": barras.get(s),
                          "cierre_anterior": ((inst.get(s) or {}).get("prevDailyBar") or {}).get("c")}
                      for s in simbolos}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Alpaca PAPER: estado del mercado, cuenta, posiciones y precios IEX")
    ap.add_argument("orden", choices=["estado", "perfiles"])
    ap.add_argument("--perfil", default=None, help="sufijo del perfil en alpaca.env (B0, B1, B1P…)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.orden == "perfiles":
        ps = perfiles()
        print("perfiles: " + (", ".join(p or "defecto" for p in ps) if ps else "ninguno (Alpaca no configurado)"))
        return 0
    try:
        c = cliente(a.perfil)
    except EndpointNoPermitido as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if c is None:
        print(f"Alpaca no configurado (sin claves en el entorno ni en {ruta_env()}): nada que hacer")
        return 0
    try:
        r = resumen(c)
    except AlpacaError as e:
        print(f"ERROR Alpaca: {c.cred.enmascarar(str(e))}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
        return 0
    m, cu = r["mercado"], r["cuenta"]
    print(f"Alpaca PAPER · perfil {r['perfil']} · cartera {r['cartera'] or '(sin declarar)'} · {r['endpoint']}")
    print(f"mercado: {'ABIERTO' if m['abierto'] else 'cerrado'}"
          + (f", cierra en {m['minutos_al_cierre']:.0f} min" if m["minutos_al_cierre"] is not None else
             f", abre {m['proxima_apertura']}"))
    print(f"cuenta {cu['numero']} ({cu['status']}): valor {cu['equity']} {cu['currency']}, efectivo {cu['cash']}, "
          f"poder de compra {cu['buying_power']}")
    for p in r["posiciones"] or []:
        print(f"  {p['symbol']:6s} {str(p['qty']):>12s} × {p['current_price']} = {p['market_value']}")
    if not r["posiciones"]:
        print("  (sin posiciones)")
    print(f"precios (feed {FEED.upper()}, no consolidado):")
    for s, v in r["precios"].items():
        print(f"  {s:6s} ref {v['referencia']} · último {v['ultimo_trade']} ({v['hora_trade']}) · "
              f"cierre anterior {v['cierre_anterior']}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    sys.exit(main())
