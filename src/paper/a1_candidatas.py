"""Candidatas de A1 «selección de acciones» (docs/factors/A1_seleccion_acciones_spec.md v1.0 §3): universo y calidad
XBRL. SIN IA, reglas fijas declaradas aquí (cambiarlas = nueva versión `VERSION`).

Universo: miembros ACTUALES del S&P 500 (`raw/sec_universe/sp500_ticker_start_end.csv`, filas sin fecha de salida),
con su CIK (`sec/companies/sec_company_tickers.json`), más los valores de «Mis activos» y las posiciones de la cuenta.
Para cada empresa, de `raw/sec_bulk/companyfacts.zip` (XBRL de la SEC; fecha = la del fichero) y su sector de
`raw/sec_bulk/submissions.zip` (código SIC → sector amplio, mapa `SECTORES_SIC`):
- ingresos, beneficio neto y resultado operativo del ÚLTIMO año fiscal con marco anual `CYAAAA` (y del anterior);
  activos, pasivos y patrimonio del último marco instantáneo `CYAAAAQnI`;
- métricas: ROA = beneficio / activos; margen operativo = resultado operativo / ingresos; crecimiento de ingresos =
  ingresos / ingresos del año anterior − 1; apalancamiento = pasivos / activos (o 1 − patrimonio / activos);
- calidad = media de los percentiles (dentro del universo) de ROA ↑, margen ↑, crecimiento ↑ y apalancamiento ↓, con
  al menos 3 de las 4 métricas; año fiscal más reciente ≥ año actual − 2 (si no, «sin datos recientes»).
Es una medida DESCRIPTIVA y mecánica (no validada como predictor): la usa la sombra (§4) y la ve el agente.
Caché por versión del zip en ~/financial_archive/a1/candidatas/ (FIN_A1_DIR): se recalcula solo si cambia el zip.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path

VERSION = "a1-candidatas-1"
RE_ANUAL = re.compile(r"^CY(\d{4})$")
RE_INSTANTE = re.compile(r"^CY(\d{4})Q(\d)I$")
CONCEPTOS = {
    "ingresos": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                 "RevenuesNetOfInterestExpense"),
    "beneficio_neto": ("NetIncomeLoss", "ProfitLoss"),
    "resultado_operativo": ("OperatingIncomeLoss",),
    "activos": ("Assets",),
    "pasivos": ("Liabilities",),
    "patrimonio": ("StockholdersEquity",
                   "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
}
INSTANTES = {"activos", "pasivos", "patrimonio"}
# SIC (rango inclusivo) → sector amplio. Declarado por el Constructor (aprox. GICS); el orden importa (el primero manda).
SECTORES_SIC = [
    ((1311, 1389), "Energía"), ((2911, 2999), "Energía"), ((4610, 4619), "Energía"),
    ((2830, 2836), "Salud"), ((3841, 3851), "Salud"), ((8000, 8099), "Salud"), ((6324, 6324), "Salud"),
    ((5122, 5122), "Salud"), ((8731, 8734), "Salud"),
    ((3570, 3579), "Tecnología"), ((3600, 3699), "Tecnología"), ((3810, 3829), "Tecnología"),
    ((7370, 7379), "Tecnología"),
    ((4800, 4899), "Comunicaciones"), ((2710, 2799), "Comunicaciones"), ((7810, 7849), "Comunicaciones"),
    ((4900, 4949), "Servicios públicos"), ((4950, 4991), "Servicios públicos"),
    ((6798, 6798), "Inmobiliario"), ((6500, 6553), "Inmobiliario"),
    ((6000, 6799), "Financiero"),
    ((2000, 2111), "Consumo básico"), ((2840, 2844), "Consumo básico"), ((5400, 5499), "Consumo básico"),
    ((5140, 5149), "Consumo básico"), ((5912, 5912), "Consumo básico"), ((5331, 5331), "Consumo básico"),
    ((5399, 5399), "Consumo básico"),
    ((1000, 1499), "Materiales"), ((2600, 2699), "Materiales"), ((2800, 2829), "Materiales"),
    ((2850, 2899), "Materiales"), ((3200, 3399), "Materiales"), ((2400, 2499), "Materiales"),
    ((3710, 3716), "Consumo discrecional"), ((5000, 5999), "Consumo discrecional"),
    ((7000, 7099), "Consumo discrecional"), ((7900, 7999), "Consumo discrecional"),
    ((2200, 2399), "Consumo discrecional"), ((3140, 3199), "Consumo discrecional"),
    ((3000, 3099), "Consumo discrecional"), ((3100, 3199), "Consumo discrecional"),
    ((3900, 3999), "Consumo discrecional"), ((100, 999), "Materiales"),
    ((7311, 7319), "Comunicaciones"), ((7320, 7329), "Financiero"), ((7300, 7369), "Industria"),
    ((1500, 1799), "Industria"), ((3400, 3569), "Industria"), ((3580, 3599), "Industria"),
    ((3700, 3799), "Industria"), ((3830, 3839), "Industria"), ((4000, 4799), "Industria"),
    ((7380, 7389), "Industria"), ((8700, 8799), "Industria"),
]
MIN_METRICAS = 3


def archivo() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")))


def dir_a1() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_A1_DIR", "~/financial_archive/a1")))


def rutas(raiz: Path | None = None) -> dict[str, Path]:
    r = raiz or archivo()
    return {"sp500": r / "raw" / "sec_universe" / "sp500_ticker_start_end.csv",
            "tickers": r / "sec" / "companies" / "sec_company_tickers.json",
            "hechos": r / "raw" / "sec_bulk" / "companyfacts.zip",
            "envios": r / "raw" / "sec_bulk" / "submissions.zip"}


def sector_sic(sic) -> str | None:
    try:
        s = int(sic)
    except (TypeError, ValueError):
        return None
    for (a, b), nombre in SECTORES_SIC:
        if a <= s <= b:
            return nombre
    return None


def sp500_actual(ruta: Path) -> list[str]:
    with open(ruta, encoding="utf-8") as fh:
        return sorted({r["ticker"].strip().upper() for r in csv.DictReader(fh) if not (r.get("end_date") or "").strip()})


def ciks(ruta: Path) -> dict[str, int]:
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    out = {}
    for v in d.values():
        t = str(v["ticker"]).upper()
        out.setdefault(t, int(v["cik_str"]))
    return out


def _variantes(t: str) -> list[str]:
    return [t, t.replace(".", "-"), t.replace("-", "."), t.replace(".", "")]


# --------------------------------------------------------------------------- hechos (puro)
def _hechos(cf: dict, conceptos: tuple[str, ...], marco: re.Pattern) -> list[dict]:
    """Hechos en USD del concepto alternativo con el marco más reciente (una empresa puede dejar de usar `Revenues` y
    pasar a `RevenueFromContract…`: quedarse con el primero mezclaría años)."""
    g = (cf.get("facts") or {}).get("us-gaap") or {}
    mejor, fin = [], ""
    for c in conceptos:
        hs = [h for h in ((g.get(c) or {}).get("units") or {}).get("USD") or [] if marco.match(str(h.get("frame") or ""))]
        f = max((str(h.get("end") or "") for h in hs), default="")
        if hs and f > fin:
            mejor, fin = hs, f
    return mejor


def extraer(cf: dict) -> dict:
    """Valores anuales (últimos dos años fiscales con marco CYAAAA) e instantáneos (último CYAAAAQnI) por concepto."""
    out: dict = {}
    for k, cs in CONCEPTOS.items():
        hs = _hechos(cf, cs, RE_INSTANTE if k in INSTANTES else RE_ANUAL)
        if k in INSTANTES:
            xs = hs
            if xs:
                h = max(xs, key=lambda h: (h["end"], h.get("filed") or ""))
                out[k] = {"valor": float(h["val"]), "fin": h["end"], "presentado": h.get("filed")}
        else:
            xs = {}
            for h in hs:
                m = RE_ANUAL.match(str(h.get("frame") or ""))
                if m:
                    xs[int(m.group(1))] = h
            if xs:
                a = max(xs)
                out[k] = {"anio": a, "valor": float(xs[a]["val"]), "presentado": xs[a].get("filed"),
                          "anterior": float(xs[a - 1]["val"]) if (a - 1) in xs else None}
    return out


def metricas(x: dict) -> dict:
    def v(k):
        return (x.get(k) or {}).get("valor")

    def anio(k):
        return (x.get(k) or {}).get("anio")
    act = v("activos")
    ni, op, ing = v("beneficio_neto"), v("resultado_operativo"), v("ingresos")
    if op is not None and anio("resultado_operativo") != anio("ingresos"):
        op = None                       # margen solo con el mismo año fiscal en los dos conceptos
    ant = (x.get("ingresos") or {}).get("anterior")
    pas = v("pasivos")
    pat = v("patrimonio")
    m = {"roa": ni / act if ni is not None and act else None,
         "margen_operativo": op / ing if op is not None and ing and ing > 0 else None,
         "crec_ingresos": ing / ant - 1 if ing is not None and ant and ant > 0 else None,
         "apalancamiento": (pas / act if pas is not None and act else (1 - pat / act if pat is not None and act else None))}
    return {k: (round(val, 6) if val is not None else None) for k, val in m.items()}


def _percentiles(vals: dict[str, float], ascendente: bool = True) -> dict[str, float]:
    xs = sorted(vals.items(), key=lambda kv: kv[1])
    n = len(xs)
    if n == 0:
        return {}
    out = {}
    i = 0
    while i < n:   # empates: percentil medio
        j = i
        while j + 1 < n and xs[j + 1][1] == xs[i][1]:
            j += 1
        p = ((i + j) / 2) / (n - 1) if n > 1 else 0.5
        for k in range(i, j + 1):
            out[xs[k][0]] = p if ascendente else 1 - p
        i = j + 1
    return out


def puntuar(filas: dict[str, dict], anio_actual: int) -> dict[str, dict]:
    """Añade `calidad` (0-1) y `rango` a cada fila con datos suficientes y recientes (pura)."""
    validas = {t: f for t, f in filas.items() if f.get("anio_fiscal") and f["anio_fiscal"] >= anio_actual - 2}
    pct = {}
    for k, asc in (("roa", True), ("margen_operativo", True), ("crec_ingresos", True), ("apalancamiento", False)):
        pct[k] = _percentiles({t: f["metricas"][k] for t, f in validas.items() if f["metricas"].get(k) is not None}, asc)
    for t, f in filas.items():
        if t not in validas:
            f["calidad"] = None
            f["motivo_sin_calidad"] = "sin año fiscal reciente en XBRL"
            continue
        ps = [pct[k][t] for k in pct if t in pct[k]]
        if len(ps) < MIN_METRICAS:
            f["calidad"] = None
            f["motivo_sin_calidad"] = f"solo {len(ps)} de 4 métricas"
        else:
            f["calidad"] = round(sum(ps) / len(ps), 4)
    orden = sorted([t for t, f in filas.items() if f.get("calidad") is not None], key=lambda t: (-filas[t]["calidad"], t))
    for i, t in enumerate(orden, 1):
        filas[t]["rango"] = i
    return filas


# --------------------------------------------------------------------------- cálculo con los ficheros (con caché)
def version_fuentes(r: dict[str, Path]) -> str:
    partes = []
    for k in ("sp500", "tickers", "hechos", "envios"):
        p = r[k]
        partes.append(f"{k}:{p.stat().st_mtime_ns if p.exists() else 0}:{p.stat().st_size if p.exists() else 0}")
    return hashlib.sha256(("|".join(partes) + VERSION).encode()).hexdigest()[:16]


def calcular(extra: list[str] | None = None, *, raiz: Path | None = None, hoy: dt.date | None = None,
             cache: bool = True) -> dict:
    """{version, fecha_datos, universo, empresas: {ticker: {cik, nombre, sector, sic, anio_fiscal, metricas, calidad,
    rango, valores}}, sin_datos: [...]}. `extra`: tickers que se añaden al universo (Mis activos, posiciones)."""
    hoy = hoy or dt.date.today()
    r = rutas(raiz)
    faltan = [k for k, p in r.items() if not p.exists()]
    if faltan:
        return {"error": f"faltan ficheros de la SEC: {faltan}", "empresas": {}}
    extra = sorted({x.strip().upper() for x in (extra or []) if x})
    clave = version_fuentes(r) + "_" + hashlib.sha256(",".join(extra).encode()).hexdigest()[:8] + f"_{hoy.year}"
    fc = dir_a1() / "candidatas" / f"{clave}.json"
    if cache and fc.exists():
        return json.loads(fc.read_text(encoding="utf-8"))
    universo = sorted(set(sp500_actual(r["sp500"])) | set(extra))
    mapa = ciks(r["tickers"])
    filas: dict[str, dict] = {}
    sin = []
    zh, ze = zipfile.ZipFile(r["hechos"]), zipfile.ZipFile(r["envios"])
    nombres_h, nombres_e = set(zh.namelist()), set(ze.namelist())
    for t in universo:
        cik = next((mapa[v] for v in _variantes(t) if v in mapa), None)
        if cik is None:
            sin.append({"ticker": t, "motivo": "sin CIK en sec_company_tickers.json"})
            continue
        n = f"CIK{cik:010d}.json"
        if n not in nombres_h:
            sin.append({"ticker": t, "motivo": "sin XBRL en companyfacts.zip"})
            continue
        try:
            cf = json.loads(zh.read(n))
        except (ValueError, KeyError) as e:
            sin.append({"ticker": t, "motivo": f"XBRL ilegible ({type(e).__name__})"})
            continue
        sic, sicd = None, None
        if n in nombres_e:
            try:
                s = json.loads(ze.read(n))
                sic, sicd = s.get("sic"), s.get("sicDescription")
            except (ValueError, KeyError):
                pass
        x = extraer(cf)
        anios = [v.get("anio") for v in x.values() if v.get("anio")]
        filas[t] = {"cik": cik, "nombre": cf.get("entityName"), "sic": sic, "sic_descripcion": sicd,
                    "sector": sector_sic(sic), "anio_fiscal": max(anios) if anios else None,
                    "metricas": metricas(x), "valores": x}
    puntuar(filas, hoy.year)
    out = {"version": VERSION, "fecha_datos": dt.datetime.fromtimestamp(r["hechos"].stat().st_mtime).date().isoformat(),
           "fuente": "SEC companyfacts.zip (XBRL) + submissions.zip (SIC); universo S&P 500 actual + Mis activos",
           "universo": universo, "empresas": filas, "sin_datos": sin,
           "reglas": "calidad = media de percentiles de ROA↑, margen operativo↑, crecimiento de ingresos↑ y "
                     "apalancamiento↓ (≥ 3 de 4; año fiscal ≥ actual − 2); descriptiva, no validada"}
    if cache:
        fc.parent.mkdir(parents=True, exist_ok=True)
        fc.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def mejores(c: dict, n: int, *, max_por_sector: int | None = None) -> list[str]:
    """Las `n` de mayor calidad (desempate por ticker), con como mucho `max_por_sector` por sector (sin sector: fuera)."""
    xs = sorted([t for t, f in (c.get("empresas") or {}).items() if f.get("calidad") is not None and f.get("sector")],
                key=lambda t: (-c["empresas"][t]["calidad"], t))
    out, por = [], {}
    for t in xs:
        s = c["empresas"][t]["sector"]
        if max_por_sector is not None and por.get(s, 0) >= max_por_sector:
            continue
        out.append(t)
        por[s] = por.get(s, 0) + 1
        if len(out) >= n:
            break
    return out
