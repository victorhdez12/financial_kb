"""«Manos fuertes»: quién está comprando o vendiendo (cálculo; el HTML está en panel_manos_fuertes.py).

DESCRIPTIVO y NO VALIDADO. Ninguna de estas medidas tiene un historial de aciertos medido en este proyecto: un
posicionamiento extremo es un dato de contexto, no una señal de compra o venta.

1. Futuros (CFTC Commitments of Traders, src/ingest/cftc_cot.py, ya en el warehouse): posición neta (largos − cortos)
   en % del interés abierto de
   * financieros (informe TFF, desde 2006-06): gestoras de activos («dinero real»: fondos de pensiones, de inversión,
     aseguradoras) y fondos apalancados (hedge funds, CTA);
   * materias primas (informe desagregado, desde 2006-06): «managed money» (fondos especulativos) y productores/
     comerciantes (quien produce o consume la materia prima y se cubre).
   Percentil del último dato en sus 3 últimos años (156 semanas) y en toda su historia; cambio en 1 y 4 semanas.
   Dato del martes, publicado el viernes siguiente (≈ +3 días).
2. Directivos (SEC Form 4, src/ingest/sec_insiders.py): solo compras (P) y ventas (S) en mercado abierto de
   consejeros y directivos (se excluyen los que solo son accionistas del 10 %). Agregado de todo el mercado cotizado
   (no hay lista histórica del S&P 500 en el proyecto) hasta el último trimestre publicado por la SEC; y, para las
   acciones de «Mis activos», también lo presentado después (Form 4 recientes).
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

VENTANA_3A = 156
P_ALTO, P_BAJO = 90, 10       # regla del panel (no validada) para llamar «extremo» a un posicionamiento

# slug, nombre, familia (fin = TFF, com = desagregado), nota de lectura
MERCADOS = [
    ("sp500_emini", "S&P 500 (e-mini)", "fin", ""),
    ("nasdaq_mini", "Nasdaq-100 (mini)", "fin", ""),
    ("vix", "VIX (futuros)", "fin", "Neto corto = apuesta a que la volatilidad baja (o cobra la prima por venderla)."),
    ("ust2y", "Bono EE. UU. 2 años", "fin", "En bonos, el corto de los fondos apalancados es sobre todo el «basis trade» "
     "(compran el bono al contado y venden el futuro): arbitraje, no una apuesta direccional."),
    ("ust5y", "Bono EE. UU. 5 años", "fin", "Ídem: el corto apalancado refleja en gran parte el «basis trade»."),
    ("ust10y", "Bono EE. UU. 10 años", "fin", "Ídem: el corto apalancado refleja en gran parte el «basis trade»."),
    ("ust_bond", "Bono EE. UU. 30 años", "fin", "Ídem: el corto apalancado refleja en gran parte el «basis trade»."),
    ("sofr3m", "SOFR 3 meses (tipos a corto)", "fin", "Largo = se espera que bajen los tipos. Desde 2018."),
    ("dxy", "Índice dólar (DXY)", "fin", "Contrato pequeño: poco interés abierto."),
    ("eur", "Euro / dólar", "fin", ""),
    ("jpy", "Yen / dólar", "fin", ""),
    ("gbp", "Libra / dólar", "fin", ""),
    ("chf", "Franco suizo / dólar", "fin", ""),
    ("gold", "Oro (COMEX)", "com", ""),
    ("silver", "Plata (COMEX)", "com", ""),
    ("copper", "Cobre (COMEX)", "com", ""),
    ("wti", "Petróleo WTI (NYMEX)", "com", "Solo el contrato NYMEX físico: parte del posicionamiento está en ICE (Brent) "
     "y en otros contratos de WTI."),
    ("natgas", "Gas natural (NYMEX)", "com", ""),
]
GRUPOS = {"fin": [("am", "Gestoras («dinero real»)"), ("lev", "Fondos apalancados")],
          "com": [("mm", "Fondos especulativos"), ("prodmerc", "Productores y comerciantes")]}


def _serie_pct(con, slug: str, clave: str) -> pd.Series:
    from src.warehouse import db
    if clave in ("lev", "mm"):
        return db.series(con, f"cftc_{slug}_{clave}_net_pct_oi")
    net, oi = db.series(con, f"cftc_{slug}_{clave}_net"), db.series(con, f"cftc_{slug}_oi")
    d = pd.concat([net, oi], axis=1, join="inner").dropna()
    d = d[d.iloc[:, 1] > 0]
    return 100 * d.iloc[:, 0] / d.iloc[:, 1]


def percentil(x: pd.Series, v: float) -> float | None:
    x = x.dropna()
    return None if x.empty else float(100 * (x <= v).mean())


def senal(p3: float | None, ph: float | None) -> str | None:
    """Etiqueta descriptiva del extremo (regla fija del panel, no validada)."""
    if p3 is None:
        return None
    if p3 >= P_ALTO:
        return "extremo alto" + (" (también en toda su historia)" if ph is not None and ph >= P_ALTO else "")
    if p3 <= P_BAJO:
        return "extremo bajo" + (" (también en toda su historia)" if ph is not None and ph <= P_BAJO else "")
    return None


def resumen_serie(s: pd.Series) -> dict | None:
    s = s.dropna().sort_index()
    if len(s) < 10:
        return None
    v = float(s.iloc[-1])
    w3 = s.iloc[-VENTANA_3A:]
    p3, ph = percentil(w3, v), percentil(s, v)
    f = s.index[-1]
    return {"fecha": str(f.date()), "publicado": str((f + pd.Timedelta(days=3)).date()), "valor": v,
            "d1": v - float(s.iloc[-2]), "d4": v - float(s.iloc[-5]) if len(s) >= 5 else None,
            "p3a": p3, "phist": ph, "desde": str(s.index[0].date()), "senal": senal(p3, ph),
            "p10_3a": float(np.percentile(w3, 10)), "p90_3a": float(np.percentile(w3, 90)),
            "min_3a": float(w3.min()), "max_3a": float(w3.max()),
            "spark": [round(float(x), 2) for x in w3.values]}


def cot(con) -> list[dict]:
    out = []
    for slug, nombre, fam, nota in MERCADOS:
        g = {}
        for clave, etq in GRUPOS[fam]:
            try:
                r = resumen_serie(_serie_pct(con, slug, clave))
            except Exception:  # noqa: BLE001
                r = None
            if r:
                g[clave] = {**r, "etiqueta": etq}
        if g:
            out.append({"slug": slug, "nombre": nombre, "familia": fam, "nota": nota, "grupos": g})
    return out


# ----------------------------------------------------------------------------------------------- directivos
def insiders_dir() -> Path:
    return Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser() / "curated" / "sec_insiders"


def limpiar(d: pd.DataFrame) -> pd.DataFrame:
    """Consejeros/directivos, empresas con ticker, precio ≥ 1 $; importe recortado en 50 M$ por línea (hay errores
    de tecleo en los Form 4: precios de 180 000 $ por acción, etc.)."""
    if d.empty:
        return d
    d = d[(d["director"] | d["officer"]) & d["code"].isin(["P", "S"])]
    d = d[~d["ticker"].fillna("").str.upper().isin(["", "NONE", "N/A", "NA", "-"])]
    d = d[(d["price"] >= 1) & (d["shares"] > 0)].copy()
    d["value"] = (d["shares"] * d["price"]).clip(upper=50e6)
    return d


def ventana(d: pd.DataFrame, fin: pd.Timestamp, dias: int) -> dict:
    x = d[(d["filing_date"] > fin - pd.Timedelta(days=dias)) & (d["filing_date"] <= fin)]
    c, v = x[x["code"] == "P"], x[x["code"] == "S"]
    ec, ev = c["issuer_cik"].nunique(), v["issuer_cik"].nunique()
    vc, vv = float(c["value"].sum()), float(v["value"].sum())
    return {"empresas_compra": int(ec), "empresas_venta": int(ev),
            "amplitud": 100 * ec / (ec + ev) if ec + ev else None,
            "directivos_compra": int(c["owner_cik"].nunique()), "directivos_venta": int(v["owner_cik"].nunique()),
            "importe_compra": vc, "importe_venta": vv,
            "pct_importe_compra": 100 * vc / (vc + vv) if vc + vv else None}


def historico_ventanas(d: pd.DataFrame, fin: pd.Timestamp, dias: int) -> pd.DataFrame:
    """Misma ventana, terminando cada 7 días hacia atrás desde `fin` (sin solapar el inicio de los datos)."""
    d = (d.groupby(["filing_date", "code", "issuer_cik", "owner_cik"], as_index=False)["value"].sum()
         .sort_values("filing_date"))
    ini = d["filing_date"].min() + pd.Timedelta(days=dias)
    filas, f = [], fin
    while f >= ini:
        filas.append({"fin": f, **ventana(d, f, dias)})
        f -= pd.Timedelta(days=7)
    return pd.DataFrame(filas).set_index("fin").sort_index()


def insiders_agregado(d: pd.DataFrame) -> dict | None:
    if d.empty:
        return None
    fin = d["filing_date"].max()
    out = {"hasta": str(fin.date()), "desde": str(d["filing_date"].min().date()), "ventanas": {}}
    for k, dias in (("4s", 28), ("13s", 91)):
        h = historico_ventanas(d, fin, dias)
        act = h.iloc[-1].to_dict()
        r = {kk: (float(vv) if isinstance(vv, (int, float, np.integer, np.floating)) else vv) for kk, vv in act.items()}
        r["p_amplitud"] = percentil(h["amplitud"], act["amplitud"]) if act["amplitud"] is not None else None
        r["p_pct_importe"] = percentil(h["pct_importe_compra"], act["pct_importe_compra"])
        r["media_amplitud"] = float(h["amplitud"].mean())
        r["media_pct_importe"] = float(h["pct_importe_compra"].mean())
        r["n_hist"] = len(h)
        if k == "13s":
            r["spark"] = [round(float(x), 2) for x in h["amplitud"].iloc[-VENTANA_3A * 2:].values]
            r["spark_desde"] = str(h.index[-min(len(h), VENTANA_3A * 2)].date())
        out["ventanas"][k] = r
    return out


def insiders_tickers(d: pd.DataFrame, tickers: dict[str, tuple[str, str]], hoy: pd.Timestamp) -> list[dict]:
    """tickers = {ticker: (nombre, cik)}; se casa por CIK del emisor (Alphabet declara a veces como GOOG)."""
    out = []
    for t, (nombre, cik) in tickers.items():
        x = d[d["issuer_cik"] == str(cik).lstrip("0")]
        fila = {"ticker": t, "nombre": nombre}
        for k, dias in (("13s", 91), ("12m", 365)):
            y = x[x["filing_date"] > hoy - pd.Timedelta(days=dias)]
            c, v = y[y["code"] == "P"], y[y["code"] == "S"]
            fila[k] = {"n_compra": int(c["accession"].nunique()), "n_venta": int(v["accession"].nunique()),
                       "importe_compra": float(c["value"].sum()), "importe_venta": float(v["value"].sum()),
                       "plan_venta": int(v[v["plan_10b5_1"].astype(bool)]["accession"].nunique())}
        c = x[x["code"] == "P"]
        fila["ultima_compra"] = str(c["filing_date"].max().date()) if len(c) else None
        fila["ultimo_form4"] = str(x["filing_date"].max().date()) if len(x) else None
        out.append(fila)
    return out


def insiders(hoy: date | None = None) -> dict:
    p = insiders_dir()
    if not (p / "trans_ps.parquet").exists():
        return {"error": "sin datos de directivos: ejecuta .venv/bin/python -m src.ingest.sec_insiders"}
    hoy_ts = pd.Timestamp(hoy or date.today())
    base = limpiar(pd.read_parquet(p / "trans_ps.parquet"))
    meta = {}
    try:
        meta = json.loads((p / "meta.json").read_text())
    except Exception:  # noqa: BLE001
        pass
    rec = pd.DataFrame()
    if (p / "recientes_ps.parquet").exists():
        rec = limpiar(pd.read_parquet(p / "recientes_ps.parquet"))
    todo = pd.concat([base, rec[~rec["accession"].isin(set(base["accession"]))]] if len(rec) else [base],
                     ignore_index=True)
    try:
        from src.ingest.yahoo_precios import ACTIVOS
        ciks = meta.get("recientes_ciks") or {}
        tk = {t: (v[0], ciks[t]) for t, v in ACTIVOS.items() if t in ciks}
    except Exception:  # noqa: BLE001
        tk = {}
    return {"agregado": insiders_agregado(base), "tickers": insiders_tickers(todo, tk, hoy_ts), "meta": meta,
            "recientes_hasta": str(rec["filing_date"].max().date()) if len(rec) else None}


def calcular(hoy: date | None = None) -> dict:
    from src.warehouse import db
    out: dict = {}
    try:
        con = db.connect(read_only=True)
        try:
            out["cot"] = cot(con)
        finally:
            con.close()
    except Exception as e:  # noqa: BLE001
        out["cot_error"] = f"{type(e).__name__}: {e}"
    try:
        out["insiders"] = insiders(hoy)
    except Exception as e:  # noqa: BLE001
        out["insiders"] = {"error": f"{type(e).__name__}: {e}"}
    return out

