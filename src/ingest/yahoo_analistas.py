"""Opiniones de analistas de las acciones de «Mis activos» (ficha v2 del panel), desde Yahoo Finance.

    .venv/bin/python -m src.ingest.yahoo_analistas

OPINIÓN DE TERCEROS, NO VALIDADA. El consenso de analistas tiene un sesgo optimista conocido (casi nunca recomiendan
vender; los precios objetivo suelen quedar por encima del precio). Solo se enseña como contexto.

Fuente: endpoint público quoteSummary v10 de Yahoo (módulos financialData, recommendationTrend,
upgradeDowngradeHistory; requiere la cookie + «crumb» que da Yahoo a cualquier navegador; uso personal). Una petición
por acción (~11), segundos. Fuera de git: $FIN_DATA_ROOT/mercados/analistas/analistas.json.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.ingest import _http

log = logging.getLogger("yahoo_analistas")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
UA = "Mozilla/5.0 (Macintosh) personal-research"
URL = ("https://query2.finance.yahoo.com/v10/finance/quoteSummary/{t}"
       "?modules=financialData,recommendationTrend,upgradeDowngradeHistory&crumb={c}")
MAX_CAMBIOS = 40


def salida() -> Path:
    d = Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser() / "mercados" / "analistas"
    d.mkdir(parents=True, exist_ok=True)
    return d


def acciones() -> list[str]:
    """Acciones de «Mis activos» (EE. UU. + Bayer); los ETF y futuros no tienen cobertura de analistas."""
    from src.ingest.sec_insiders import tickers_mis_activos
    return tickers_mis_activos() + ["BAYN.DE"]


def _raw(x):
    return x.get("raw") if isinstance(x, dict) else x


def resumir(res: dict) -> dict:
    """Del JSON de quoteSummary a lo que enseña la ficha (sin el resto de datos de Yahoo)."""
    fd = res.get("financialData") or {}
    out = {k: _raw(fd.get(k)) for k in ("currentPrice", "targetMeanPrice", "targetMedianPrice", "targetHighPrice",
                                         "targetLowPrice", "numberOfAnalystOpinions", "recommendationMean",
                                         "recommendationKey", "financialCurrency")}
    out["tendencia"] = [{k: t.get(k) for k in ("period", "strongBuy", "buy", "hold", "sell", "strongSell")}
                        for t in (res.get("recommendationTrend") or {}).get("trend") or []]
    hist = (res.get("upgradeDowngradeHistory") or {}).get("history") or []
    out["cambios"] = [{"fecha": datetime.fromtimestamp(int(h["epochGradeDate"]), timezone.utc).date().isoformat(),
                       "firma": h.get("firm"), "de": h.get("fromGrade"), "a": h.get("toGrade"),
                       "accion": h.get("action"), "objetivo": h.get("currentPriceTarget"),
                       "objetivo_previo": h.get("priorPriceTarget"), "accion_objetivo": h.get("priceTargetAction")}
                      for h in sorted(hist, key=lambda h: -int(h.get("epochGradeDate") or 0))[:MAX_CAMBIOS]
                      if h.get("epochGradeDate")]
    return out


def sesion() -> tuple[requests.Session, str]:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    try:
        _http.get("https://fc.yahoo.com", session=s, timeout=20, total=40)   # pone la cookie (responde 404: normal)
    except Exception:  # noqa: BLE001
        pass
    c = _http.get("https://query1.finance.yahoo.com/v1/test/getcrumb", session=s, timeout=20, total=40)
    c.raise_for_status()
    if not c.text or "<" in c.text:
        raise RuntimeError("Yahoo no dio crumb")
    return s, c.text.strip()


def main() -> None:
    s, crumb = sesion()
    datos, fallos = {}, []
    for t in acciones():
        try:
            r = _http.get(URL.format(t=t, c=crumb), session=s, timeout=30, total=60)
            r.raise_for_status()
            datos[t] = resumir(r.json()["quoteSummary"]["result"][0])
            log.info("%s: %s analistas, objetivo medio %s", t, datos[t]["numberOfAnalystOpinions"], datos[t]["targetMeanPrice"])
        except Exception as e:  # noqa: BLE001
            fallos.append(t)
            log.error("%s: FALLO %s", t, e)
        time.sleep(0.4)
    if not datos:
        raise SystemExit("yahoo_analistas: ninguna descarga")
    (salida() / "analistas.json").write_text(json.dumps(
        {"descarga": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "fuente": "Yahoo Finance quoteSummary (financialData, recommendationTrend, upgradeDowngradeHistory)",
         "acciones": datos, "fallos": fallos}, ensure_ascii=False, indent=1))
    if fallos:
        raise SystemExit(f"yahoo_analistas: fallos {fallos}")


if __name__ == "__main__":
    main()
