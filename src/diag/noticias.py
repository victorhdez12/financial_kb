"""Noticias para el paquete de diagnóstico (docs/panel/diagnosticos_v0.md §3, fuente aprobada el 19-nov-2026).

1. GDELT (API DOC 2.0, gratis y sin clave): titulares en inglés del día del evento, filtrados por los activos que se
   movieron. GDELT pide ≤ 1 petición cada 5 s: se espera entre consultas.
2. Comunicados oficiales por RSS: Fed, BLS, BEA y BCE (los del día del evento y los 2 anteriores).
Cada petición con plazo TOTAL (src/ingest/_http.py): un servidor que gotea bytes no cuelga la diaria. Si una fuente
falla se apunta en «errores» y el resto sigue. Se guarda con su URL en $FIN_DATA_ROOT/diag/noticias/<fecha>.json
(fuera de git). La nota solo puede citar titulares que estén aquí. No se verifica el contenido de las noticias.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from src.diag import disparadores as D

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
UA = "Mozilla/5.0 (Macintosh) personal-research"
PLAZO = {"timeout": 20, "total": 45}         # s por lectura y total por petición
ESPERA_GDELT = 5.5
MAX_CONSULTAS_GDELT = 4
MAX_ARTICULOS = 20
REINTENTOS_429 = 3
RSS = {"Fed": "https://www.federalreserve.gov/feeds/press_all.xml",
       "BLS": "https://www.bls.gov/feed/bls_latest.rss",
       "BEA": "https://apps.bea.gov/rss/rss.xml",
       "BCE": "https://www.ecb.europa.eu/rss/press.html"}
# activo de referencia → consulta GDELT (frases entre comillas, OR entre paréntesis)
CONSULTAS = {"sp500": '("stock market" OR "Wall Street" OR "S&P 500")',
             "nasdaq": '("Nasdaq" OR "tech stocks")',
             "eurostoxx": '("European stocks" OR "Stoxx 600" OR "Euro Stoxx")',
             "oro": '("gold price" OR "gold prices")',
             "tesoro10": '("Treasury yields" OR "bond yields")',
             "dolar": '("US dollar" OR "dollar index")',
             "petroleo": '("oil prices" OR "crude oil")'}
GENERAL = '("Federal Reserve" OR "central bank")'

Transporte = Callable[[str], tuple[int, bytes]]


def transporte_http(url: str) -> tuple[int, bytes]:
    from src.ingest import _http
    r = _http.get(url, headers={"User-Agent": UA}, timeout=PLAZO["timeout"], total=PLAZO["total"])
    return r.status_code, r.content


def url_gdelt(consulta: str, fecha: pd.Timestamp, maxrec: int = MAX_ARTICULOS) -> str:
    """Ventana: del día del evento a las 00:00 UTC hasta el día siguiente a las 12:00 UTC (cubre el cierre de EE. UU.)."""
    ini = fecha.normalize()
    fin = ini + pd.Timedelta(hours=36)
    q = {"query": f"{consulta} sourcelang:english", "mode": "artlist", "format": "json", "maxrecords": str(maxrec),
         "sort": "hybridrel", "startdatetime": ini.strftime("%Y%m%d%H%M%S"), "enddatetime": fin.strftime("%Y%m%d%H%M%S")}
    return GDELT + "?" + urllib.parse.urlencode(q)


def parse_gdelt(cuerpo: bytes) -> list[dict]:
    """Artículos {titulo, url, dominio, fecha_vista_utc, pais}. GDELT responde texto plano (no JSON) a los errores."""
    txt = cuerpo.decode("utf-8", errors="replace").strip()
    if not txt:
        return []
    try:
        d = json.loads(txt)
    except json.JSONDecodeError as e:
        raise ValueError(f"respuesta no JSON de GDELT: {txt[:120]}") from e
    out = []
    for a in d.get("articles") or []:
        if not a.get("url") or not a.get("title"):
            continue
        out.append({"titulo": a["title"].strip(), "url": a["url"], "dominio": a.get("domain"),
                    "fecha_vista_utc": a.get("seendate"), "pais": a.get("sourcecountry")})
    return out


def _texto(el, *nombres) -> str | None:
    for n in nombres:
        x = el.find(n)
        if x is not None:
            if x.text and x.text.strip():
                return x.text.strip()
            if x.get("href"):
                return x.get("href")
    return None


def _fecha_rss(t: str | None) -> pd.Timestamp | None:
    if not t:
        return None
    try:
        return pd.Timestamp(parsedate_to_datetime(t)).tz_convert("UTC").tz_localize(None)
    except Exception:  # noqa: BLE001
        pass
    try:
        f = pd.Timestamp(t)
        return f.tz_convert("UTC").tz_localize(None) if f.tzinfo else f
    except Exception:  # noqa: BLE001
        return None


def parse_rss(cuerpo: bytes) -> list[dict]:
    """Ítems de RSS 2.0, RSS 1.0 (RDF) o Atom: {titulo, url, fecha_utc}."""
    raiz = ET.fromstring(cuerpo)
    out = []
    ns_atom = "{http://www.w3.org/2005/Atom}"
    ns_rss1 = "{http://purl.org/rss/1.0/}"
    ns_dc = "{http://purl.org/dc/elements/1.1/}"
    items = (raiz.findall(".//item") + raiz.findall(f".//{ns_rss1}item") + raiz.findall(f".//{ns_atom}entry"))
    for it in items:
        tit = _texto(it, "title", f"{ns_rss1}title", f"{ns_atom}title")
        url = _texto(it, "link", f"{ns_rss1}link", f"{ns_atom}link")
        f = _fecha_rss(_texto(it, "pubDate", f"{ns_dc}date", f"{ns_atom}updated", f"{ns_atom}published"))
        if tit and url:
            out.append({"titulo": " ".join(tit.split()), "url": url, "fecha_utc": str(f) if f is not None else None})
    return out


def oficiales(fecha: pd.Timestamp, transporte: Transporte, dias_antes: int = 2) -> tuple[list[dict], dict]:
    out, err = [], {}
    ini = fecha.normalize() - pd.Timedelta(days=dias_antes)
    fin = fecha.normalize() + pd.Timedelta(days=1, hours=12)
    for fuente, url in RSS.items():
        try:
            st, cuerpo = transporte(url)
            if st != 200:
                raise RuntimeError(f"HTTP {st}")
            for it in parse_rss(cuerpo):
                f = pd.Timestamp(it["fecha_utc"]) if it["fecha_utc"] else None
                if f is not None and ini <= f <= fin:
                    out.append({"fuente": fuente, **it})
        except Exception as e:  # noqa: BLE001
            err[fuente] = f"{type(e).__name__}: {e}"[:200]
    return out, err


def consultas_para(evento: dict | None, movs: list[dict] | None = None) -> list[tuple[str, str]]:
    """Activos que se movieron (los del disparo y, si no hay, los de referencia con mayor |σ|) + una general."""
    claves: list[str] = []
    for d in (evento or {}).get("disparos", []):
        for c in [d.get("clave")] + list(d.get("activos") or []):
            if c in CONSULTAS and c not in claves:
                claves.append(c)
    for m in movs or []:
        if m.get("referencia") and m["clave"] in CONSULTAS and m["clave"] not in claves and abs(m.get("k_sigma63") or 0) >= 1.5:
            claves.append(m["clave"])
    sel = [(c, CONSULTAS[c]) for c in claves[:MAX_CONSULTAS_GDELT - 1]]
    return sel + [("general", GENERAL)]


def recoger(fecha, evento: dict | None = None, movs: list[dict] | None = None, transporte: Transporte | None = None,
            espera: float = ESPERA_GDELT, guardar: Path | None = None) -> dict:
    """{gdelt: [...], oficiales: [...], errores: {...}, consultas: [...]} y, si `guardar`, el JSON en esa ruta."""
    fecha = pd.Timestamp(fecha)
    tr = transporte or transporte_http
    res: dict = {"fecha_evento": str(fecha.date()), "descarga_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "fuentes": {"gdelt": GDELT, **RSS}, "gdelt": [], "oficiales": [], "errores": {}, "consultas": [],
                 "aviso": "Titulares de prensa y comunicados sin verificar uno a uno; no son datos propios."}
    vistos = set()
    for i, (c, q) in enumerate(consultas_para(evento, movs)):
        if i and espera:
            time.sleep(espera)
        url = url_gdelt(q, fecha)
        res["consultas"].append({"activo": c, "consulta": q, "url": url})
        try:
            st, cuerpo = tr(url)
            for k in range(REINTENTOS_429):   # GDELT limita a 1 petición / 5 s por IP y responde 429
                if st != 429:
                    break
                if espera:
                    time.sleep(espera * (2 + 2 * k))
                st, cuerpo = tr(url)
            if st != 200:
                raise RuntimeError(f"HTTP {st}")
            for a in parse_gdelt(cuerpo):
                if a["url"] not in vistos:
                    vistos.add(a["url"])
                    res["gdelt"].append({"activo": c, **a})
        except Exception as e:  # noqa: BLE001
            res["errores"][f"gdelt:{c}"] = f"{type(e).__name__}: {e}"[:200]
    res["oficiales"], err = oficiales(fecha, tr)
    res["errores"].update({f"rss:{k}": v for k, v in err.items()})
    if guardar is not None:
        guardar.parent.mkdir(parents=True, exist_ok=True)
        guardar.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def ruta(fecha) -> Path:
    return D.root() / "diag" / "noticias" / f"{pd.Timestamp(fecha).date()}.json"
