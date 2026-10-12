"""Construye las filas de nodos y relaciones del esqueleto estructural del grafo.

Lee data/warehouse.duckdb en modo SOLO LECTURA (catalog, events, regime_monthly) y, si existe,
~/financial_archive/sec/universe/universe.parquet. No toca Neo4j: devuelve un `Graph` con
listas de dicts que load.py escribe (MERGE + UNWIND) o exporta a CSV.

No se cargan observaciones: el grafo apunta a las series; los números viven en DuckDB.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
FIN_DATA_ROOT = Path(os.path.expanduser(os.getenv("FIN_DATA_ROOT", "~/financial_archive")))
UNIVERSE = FIN_DATA_ROOT / "sec" / "universe" / "universe.parquet"

# Ventana para (Event)-[:PRECEDED]->(Event): crisis encadenadas en el mismo país.
# 365 días si ambas fechas son diarias; 730 si alguna es anual (Reinhart-Rogoff, Laeven-Valencia, JST:
# start_date = 1 de enero, el desfase real es incierto en +-1 año).
PRECEDED_WINDOW_DAYS = 365
PRECEDED_WINDOW_DAYS_YEARLY = 730
CHAIN_TYPES = {
    "banking_crisis", "currency_crisis", "sovereign_default", "inflation_crisis",
    "market_crash", "credit_event", "recession", "oil_shock", "pandemic",
}
# Fuentes con fechas anuales (start_date = 1 de enero del año)
YEARLY_SOURCES = {"reinhart_rogoff", "laeven_valencia_2018", "jst_macrohistory"}
SNAPSHOT_SCOPE = {"USA", "WLD"}          # eventos que se cuelgan de RegimeSnapshot (US)
SNAPSHOT_FROM = date(1950, 1, 1)


# ----------------------------------------------------------------------------- contenedor
@dataclass
class Rel:
    type: str
    src_label: str
    dst_label: str
    rows: list = field(default_factory=list)   # {"src","dst","props"}


@dataclass
class Graph:
    nodes: dict = field(default_factory=lambda: defaultdict(list))   # label -> [{"id", "props"}]
    rels: dict = field(default_factory=dict)                         # key -> Rel

    def node(self, label, id_, **props):
        self.nodes[label].append({"id": id_, "props": {k: _clean(v) for k, v in props.items()}})

    def rel(self, type_, src_label, src, dst_label, dst, **props):
        key = (type_, src_label, dst_label)
        if key not in self.rels:
            self.rels[key] = Rel(type_, src_label, dst_label)
        self.rels[key].rows.append({"src": src, "dst": dst,
                                    "props": {k: _clean(v) for k, v in props.items()}})

    def dedupe(self):
        for label, rows in self.nodes.items():
            seen = {}
            for r in rows:
                seen.setdefault(r["id"], r)
            self.nodes[label] = list(seen.values())
        for rel in self.rels.values():
            seen = {}
            for r in rel.rows:
                seen.setdefault((r["src"], r["dst"]), r)
            rel.rows = list(seen.values())
        return self


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    if isinstance(v, datetime):
        return v.date()
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):   # numpy scalars
        try:
            return _clean(v.item())
        except (ValueError, AttributeError):
            pass
    return v


# ----------------------------------------------------------------------------- vocabularios
AGGREGATES = {
    "WLD": "World", "EM": "Emerging markets", "EMU": "Euro area", "G7": "G7",
}
ALIASES = {"EA": "EMU", "UK": "GBR"}


def norm_country(code):
    if code is None or (isinstance(code, float) and pd.isna(code)):
        return None
    c = str(code).strip().upper()
    if not c:
        return None
    c = ALIASES.get(c, c)
    if len(c) == 2 and c not in AGGREGATES:
        try:
            import pycountry
            hit = pycountry.countries.get(alpha_2=c)
            if hit:
                return hit.alpha_3
        except Exception:
            pass
    return c


def country_name(iso3):
    if iso3 in AGGREGATES:
        return AGGREGATES[iso3]
    try:
        import pycountry
        hit = pycountry.countries.get(alpha_3=iso3)
        if hit:
            return getattr(hit, "common_name", None) or hit.name
        hist = pycountry.historic_countries.get(alpha_3=iso3)
        if hist:
            return hist.name
    except Exception:
        pass
    return iso3


CONCEPTS = {
    # id: (name, description)
    "growth": ("Growth", "Actividad real: PIB, producción industrial, consumo."),
    "inflation": ("Inflation", "Nivel y cambio de precios; expectativas de inflación."),
    "employment": ("Employment", "Mercado laboral: empleo, paro, salarios."),
    "interest_rates": ("Interest Rates", "Tipos nominales de mercado y oficiales."),
    "monetary_policy": ("Monetary Policy", "Tipo oficial, balance del banco central."),
    "real_rates": ("Real Rates", "Tipos reales (TIPS, tipo oficial menos inflación)."),
    "yield_curve": ("Yield Curve", "Pendiente de la curva (10a-3m, 10a-2a)."),
    "credit": ("Credit", "Volumen de crédito bancario y privado."),
    "credit_spread": ("Credit Spread", "Diferencial de crédito corporativo (BAA-10a, OAS)."),
    "debt_cycle": ("Debt Cycle", "Ciclo de deuda corto/largo (Dalio, Minsky): apalancamiento/PIB."),
    "money_supply": ("Money Supply", "Agregados monetarios M1/M2/base."),
    "liquidity": ("Liquidity", "Liquidez neta: balance Fed - TGA - RRP, M2 vs PIB."),
    "fiscal": ("Fiscal & Sovereign Debt", "Déficit, deuda pública, intereses."),
    "financial_conditions": ("Financial Conditions", "Índices de condiciones/estrés financiero."),
    "volatility": ("Volatility", "Volatilidad implícita/realizada (VIX)."),
    "equity_market": ("Equity Market", "Precios y rentabilidades de renta variable."),
    "valuation": ("Valuation", "Valoración (CAPE, dividend yield, P/E)."),
    "commodities": ("Commodities", "Materias primas y energía."),
    "gold": ("Gold", "Oro como activo monetario."),
    "fx": ("FX", "Tipos de cambio y regímenes cambiarios."),
    "housing": ("Housing", "Vivienda: precios, hipotecas, rentas."),
    "geopolitical_risk": ("Geopolitical Risk", "Riesgo geopolítico (GPR Caldara-Iacoviello)."),
    "financial_crisis": ("Financial Crisis", "Crisis bancarias, cambiarias, impagos soberanos."),
}
CATEGORY_CONCEPT = {
    "growth": ["growth"], "consumption": ["growth"], "consumer_sentiment": ["growth"],
    "business_cycle": ["growth"],
    "inflation": ["inflation"], "inflation_expectations": ["inflation"],
    "employment": ["employment"], "wages": ["employment"],
    "rates": ["interest_rates"], "interest_rates": ["interest_rates"], "housing_rates": ["housing", "interest_rates"],
    "yield_curve": ["yield_curve"],
    "credit": ["credit"],
    "money": ["money_supply"],
    "liquidity": ["liquidity"],
    "fiscal": ["fiscal"],
    "financial_conditions": ["financial_conditions"],
    "markets": ["equity_market"], "equity_returns": ["equity_market"],
    "bond_returns": ["interest_rates"],
    "valuation": ["valuation"],
    "commodities": ["commodities"], "gold": ["gold"], "fx": ["fx"],
    "housing": ["housing"],
    "geopolitics": ["geopolitical_risk"],
    "crisis": ["financial_crisis"],
}
CONCEPT_RELATED = [
    ("debt_cycle", "credit"), ("debt_cycle", "fiscal"), ("debt_cycle", "financial_crisis"),
    ("credit", "credit_spread"), ("credit_spread", "financial_conditions"),
    ("credit_spread", "financial_crisis"), ("liquidity", "money_supply"),
    ("liquidity", "financial_conditions"), ("liquidity", "monetary_policy"),
    ("real_rates", "inflation"), ("real_rates", "interest_rates"), ("real_rates", "gold"),
    ("monetary_policy", "interest_rates"), ("monetary_policy", "yield_curve"),
    ("yield_curve", "growth"), ("inflation", "commodities"), ("valuation", "equity_market"),
    ("geopolitical_risk", "commodities"), ("volatility", "financial_conditions"),
    ("housing", "credit"), ("growth", "employment"),
]


def series_concepts(sid: str, name: str, category: str | None):
    out = set(CATEGORY_CONCEPT.get(category or "", []))
    s, n = sid.upper(), (name or "").lower()
    if s.startswith("DFII") or "inflation-indexed" in n or "(real, cpi-deflated)" in n and "rate" in n:
        out.add("real_rates")
    if ("spread" in n or "option-adjusted" in n or s in {"AAA10Y", "BAA10Y"}) and "corporate" in n \
            or s in {"AAA10Y", "BAA10Y"}:
        out.add("credit_spread")
    if s.startswith("T10Y") and s not in {"T10YIE"}:
        out.add("yield_curve")
    if s in {"FEDFUNDS", "DFF", "INTDSRUSM193N", "M13009USM156NNBR", "SOFR", "WALCL", "WRESBAL"} \
            or s.endswith("_STIR"):
        out.add("monetary_policy")
    if s in {"WALCL", "WTREGEN", "RRPONTSYD", "WRESBAL", "M2SL", "BOGMBASE"}:
        out.add("liquidity")
    if s in {"GFDEGDQ188S", "FYGFDPUN", "GFDEBTN"} or s.endswith("_DEBTGDP") \
            or (category == "credit" and "/ gdp" in n) or s.endswith("_BDEBT"):
        out.add("debt_cycle")
    if s in {"VIXCLS"} or "volatility" in n:
        out.add("volatility")
        out.discard("equity_market")
    if s in {"NFCI", "ANFCI", "NFCICREDIT", "STLFSI4", "KCFSI"}:
        out.add("financial_conditions")
    return sorted(out)


ASSET_CLASSES = {
    "equities": "Equities", "govt_bonds": "Government Bonds", "corp_credit": "Corporate Credit",
    "cash": "Cash / T-Bills", "commodities": "Commodities", "gold": "Gold",
    "fx": "Currencies", "real_estate": "Real Estate",
}
CASH_IDS = {"TB3MS", "DTB3", "TB6MS", "DGS3MO", "SOFR", "M13001USM156NNBR"}


def series_asset_classes(sid, name, category):
    s, n = sid.upper(), (name or "").lower()
    out = set()
    if category in {"equity_returns", "valuation"} or (category == "markets" and s != "VIXCLS"):
        if not any(k in n for k in ("housing", "safe assets", "on wealth")):
            out.add("equities")
    if category == "bond_returns" or "safe assets" in n:
        out.add("govt_bonds")
    if category in {"rates", "interest_rates"}:
        if s in CASH_IDS or "bill" in n or "short-term" in n:
            out.add("cash")
        elif any(k in n for k in ("treasury", "government bond", "long-term", "gov bonds")) \
                and "inflation-indexed" not in n:
            out.add("govt_bonds")
    if "corporate" in n and any(k in n for k in ("spread", "yield", "return", "bond")):
        out.add("corp_credit")
    if category == "commodities":
        out.add("commodities")
    if category == "gold":
        out.add("gold")
    if category == "fx" and "peg" not in n:
        out.add("fx")
    if category == "housing" and any(k in n for k in ("price", "return", "capital gain", "rent")):
        out.add("real_estate")
    return sorted(out)


INVESTORS = [
    # id, name, born, died, affiliation, style, known_for, concepts
    ("buffett", "Warren Buffett", 1930, None, "Berkshire Hathaway", "value/quality",
     "Foso económico, asignación de capital, cartas anuales.", ["valuation", "equity_market"]),
    ("dalio", "Ray Dalio", 1949, None, "Bridgewater Associates", "global macro",
     "Ciclos de deuda corto/largo, All Weather, máquina económica.",
     ["debt_cycle", "liquidity", "inflation", "real_rates"]),
    ("marks", "Howard Marks", 1946, None, "Oaktree Capital", "credit/distressed",
     "Ciclos de mercado, el péndulo, memos.", ["credit_spread", "credit", "valuation"]),
    ("munger", "Charlie Munger", 1924, 2023, "Berkshire Hathaway / Daily Journal", "quality",
     "Modelos mentales, incentivos, inversión en calidad.", ["valuation"]),
    ("graham", "Benjamin Graham", 1894, 1976, "Graham-Newman", "deep value",
     "Margen de seguridad; Security Analysis, The Intelligent Investor.", ["valuation"]),
    ("lynch", "Peter Lynch", 1944, None, "Fidelity Magellan", "GARP",
     "PEG, invertir en lo que conoces.", ["equity_market", "valuation"]),
    ("soros", "George Soros", 1930, None, "Quantum Fund", "global macro",
     "Reflexividad; ataque a la libra 1992.", ["fx", "financial_crisis"]),
    ("druckenmiller", "Stanley Druckenmiller", 1953, None, "Duquesne Capital", "global macro",
     "Liquidez y la Fed como motor de los mercados.", ["liquidity", "monetary_policy"]),
    ("templeton", "John Templeton", 1912, 2008, "Templeton Funds", "global contrarian value",
     "Comprar en el punto de máximo pesimismo.", ["valuation", "financial_crisis"]),
    ("keynes", "John Maynard Keynes", 1883, 1946, "King's College Cambridge", "economist/investor",
     "Teoría General; concurso de belleza; espíritus animales.",
     ["interest_rates", "money_supply", "growth"]),
    ("minsky", "Hyman Minsky", 1919, 1996, "Washington University / Levy Institute", "economist",
     "Hipótesis de inestabilidad financiera; momento Minsky.",
     ["debt_cycle", "credit", "financial_crisis"]),
    ("fisher", "Irving Fisher", 1867, 1947, "Yale", "economist",
     "Teoría de la deflación por deuda (1933); ecuación cuantitativa.",
     ["debt_cycle", "inflation", "money_supply"]),
    ("bagehot", "Walter Bagehot", 1826, 1877, "The Economist", "economist/journalist",
     "Lombard Street (1873): prestamista de última instancia.",
     ["financial_crisis", "liquidity", "monetary_policy"]),
]

REGIME_KINDS = {
    # kind: (columna regime_monthly, conceptos que lo definen)
    "quadrant": ("quadrant", ["growth", "inflation"]),
    "debt_phase": ("debt_phase", ["debt_cycle", "yield_curve", "monetary_policy", "credit_spread"]),
    "credit": ("credit_light", ["credit_spread", "financial_conditions"]),
    "liquidity": ("liquidity", ["liquidity", "money_supply", "real_rates"]),
    "long_cycle": ("long_cycle", ["debt_cycle", "fiscal"]),
}
SNAPSHOT_COLS = [
    "quadrant", "debt_phase", "debt_phase_reason", "credit_light", "liquidity", "long_cycle",
    "G", "G_state", "I", "I_state", "sahm_trigger", "liquidity_score", "credit_reds",
    "credit_ambers", "infl_yoy", "core_6m", "unrate", "fedfunds", "real_ff", "curve",
    "baa_spread", "hy_oas", "nfci", "vix", "debt_gdp", "inverted_months", "vintage_mode", "cutoff",
]

SOURCES_META = {
    "fred": ("FRED (St. Louis Fed)", "https://fred.stlouisfed.org"),
    "fred_legacy": ("FRED (legacy download)", "https://fred.stlouisfed.org"),
    "alfred": ("ALFRED vintages", "https://alfred.stlouisfed.org"),
    "bls_legacy": ("BLS", "https://www.bls.gov"),
    "jst_macrohistory": ("Jordà-Schularick-Taylor Macrohistory", "https://www.macrohistory.net"),
    "ken_french": ("Ken French Data Library", "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"),
    "shiller": ("Robert Shiller data", "http://www.econ.yale.edu/~shiller/data.htm"),
    "damodaran": ("Damodaran Online", "https://pages.stern.nyu.edu/~adamodar/"),
    "wb_pinksheet": ("World Bank Pink Sheet", "https://www.worldbank.org/en/research/commodity-markets"),
    "boe_millennium_uk": ("Bank of England — A millennium of macroeconomic data", "https://www.bankofengland.co.uk"),
    "nber_macrohistory": ("NBER Macrohistory", "https://www.nber.org/research/data/nber-macrohistory-database"),
    "gold": ("Gold prices", None),
    "gpr": ("Geopolitical Risk Index (Caldara-Iacoviello)", "https://www.matteoiacoviello.com/gpr.htm"),
    "cow": ("Correlates of War", "https://correlatesofwar.org"),
    "ucdp_prio": ("UCDP/PRIO Armed Conflict Dataset", "https://ucdp.uu.se"),
    "laeven_valencia_2018": ("Laeven & Valencia (2018) Systemic Banking Crises", "https://www.imf.org"),
    "reinhart_rogoff": ("Reinhart-Rogoff Global Crises Data", "https://www.hbs.edu/behavioral-finance-and-financial-stability/data/Pages/global.aspx"),
    "nber": ("NBER Business Cycle Dating", "https://www.nber.org/research/business-cycle-dating"),
    "curated": ("Lista curada financial_kb", None),
    "sec_edgar": ("SEC EDGAR", "https://www.sec.gov"),
    "regime_engine": ("financial_kb src/regime (regime_monthly)", None),
}


# ----------------------------------------------------------------------------- builders
def _source(g: Graph, sid: str, license_=None):
    name, url = SOURCES_META.get(sid, (sid, None))
    g.node("Source", sid, name=name, url=url, license=license_)


def _country(g: Graph, iso3: str):
    name = country_name(iso3)
    kind = "aggregate" if iso3 in AGGREGATES else ("country" if name != iso3 else "non_state_or_unknown")
    g.node("Country", iso3, name=name, aggregate=iso3 in AGGREGATES, kind=kind)


def build_reference(g: Graph):
    for cid, (name, desc) in CONCEPTS.items():
        g.node("Concept", cid, name=name, description=desc)
    for a, b in CONCEPT_RELATED:
        g.rel("RELATED_TO", "Concept", a, "Concept", b)
    for aid, name in ASSET_CLASSES.items():
        g.node("AssetClass", aid, name=name)
    for (iid, name, born, died, aff, style, known, concepts) in INVESTORS:
        g.node("Investor", iid, name=name, born=born, died=died, affiliation=aff,
               style=style, known_for=known)
        for c in concepts:
            g.rel("FOCUSES_ON", "Investor", iid, "Concept", c, basis="curated_v0")


def build_series(g: Graph, con):
    cat = con.execute("select * from catalog").fetchdf()
    # fuente preferida para propiedades: no-legacy primero
    cat["_rank"] = cat["source"].str.contains("legacy").astype(int)
    cat = cat.sort_values(["series_id", "_rank"])
    for sid, grp in cat.groupby("series_id", sort=False):
        r = grp.iloc[0]
        iso = norm_country(r["country"])
        g.node("DataSeries", sid, name=r["name"], category=r["category"], frequency=r["frequency"],
               units=r["units"], country=iso, start=r["start"], end=r["end"], url=r["url"],
               license=r["license"], transform_notes=r["transform_notes"],
               sources=sorted(grp["source"].dropna().unique().tolist()))
        for _, rr in grp.iterrows():
            _source(g, rr["source"], rr["license"])
            g.rel("FROM_SOURCE", "DataSeries", sid, "Source", rr["source"])
        if iso:
            _country(g, iso)
            g.rel("IN_COUNTRY", "DataSeries", sid, "Country", iso)
        for c in series_concepts(sid, r["name"], r["category"]):
            g.rel("MEASURES", "DataSeries", sid, "Concept", c)
        for a in series_asset_classes(sid, r["name"], r["category"]):
            g.rel("TRACKS", "DataSeries", sid, "AssetClass", a)


def _countries(raw):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    return [c for c in (norm_country(x) for x in re.split(r"[;,]", str(raw))) if c]


def build_events(g: Graph, con, snapshot_ids: set):
    ev = con.execute("select * from events").fetchdf()
    ev["start_date"] = pd.to_datetime(ev["start_date"])
    ev["end_date"] = pd.to_datetime(ev["end_date"])
    rows = []
    for _, r in ev.iterrows():
        cs = _countries(r["country"])
        sd = r["start_date"].date() if pd.notna(r["start_date"]) else None
        precision = "year" if (r["source"] in YEARLY_SOURCES and sd and sd.month == 1 and sd.day == 1) else "day"
        g.node("Event", r["event_id"], name=r["name"], type=r["type"], countries=cs,
               start_date=sd, end_date=r["end_date"], year=sd.year if sd else None,
               severity=None if pd.isna(r["severity"]) else str(r["severity"]),
               url=r["url"], notes=r["notes"], dataset=r["dataset"], date_precision=precision)
        _source(g, r["source"])
        g.rel("FROM_SOURCE", "Event", r["event_id"], "Source", r["source"])
        for c in cs:
            _country(g, c)
            g.rel("IN_COUNTRY", "Event", r["event_id"], "Country", c)
        rows.append((r["event_id"], r["type"], r["source"], sd, set(cs), precision))
        # (Event)-[:OCCURRED_DURING]->(RegimeSnapshot)
        if sd and sd >= SNAPSHOT_FROM and (set(cs) & SNAPSHOT_SCOPE):
            sid = f"US-{sd.year:04d}-{sd.month:02d}"
            if sid in snapshot_ids:
                g.rel("OCCURRED_DURING", "Event", r["event_id"], "RegimeSnapshot", sid,
                      date_precision=precision,
                      scope="USA" if "USA" in cs else "WLD")

    # (Event)-[:PRECEDED {lag_days}]->(Event): mismo país, A empieza antes que B, lag <= ventana.
    # Por cada A y cada tipo de B se enlaza solo el primer B (evita abanicos).
    # Mismo tipo desde otra fuente = probable duplicado (LV vs RR) -> se excluye.
    by_country = defaultdict(list)
    prec = {}
    for eid, typ, src, sd, cs, pr in rows:
        prec[eid] = pr
        if typ in CHAIN_TYPES and sd:
            for c in cs:
                by_country[c].append((sd, eid, typ, src))
    for c, lst in by_country.items():
        lst.sort()
        for i, (sa, ea, ta, srca) in enumerate(lst):
            first_by_type = {}
            for sb, eb, tb, srcb in lst[i + 1:]:
                lag = (sb - sa).days
                if lag > PRECEDED_WINDOW_DAYS_YEARLY:
                    break
                yearly = "year" in (prec[ea], prec[eb])
                win = PRECEDED_WINDOW_DAYS_YEARLY if yearly else PRECEDED_WINDOW_DAYS
                if lag <= 0 or eb == ea or lag > win:
                    continue
                if ta == tb and srca != srcb:
                    continue
                if tb not in first_by_type:
                    first_by_type[tb] = (eb, lag, yearly, win)
            for tb, (eb, lag, yearly, win) in first_by_type.items():
                g.rel("PRECEDED", "Event", ea, "Event", eb, lag_days=lag, country=c,
                      window_days=win, date_precision="year" if yearly else "day")


def build_regimes(g: Graph, con):
    rm = con.execute("select * from regime_monthly order by date").fetchdf()
    rm["date"] = pd.to_datetime(rm["date"])
    _source(g, "regime_engine")
    ids = []
    for kind, (col, concepts) in REGIME_KINDS.items():
        vals = rm[col].dropna().unique().tolist()
        for v in vals:
            rid = f"{kind}:{v}"
            seq = (rm[col] == v)
            n_months = int(seq.sum())
            spells = int(((seq) & (~seq.shift(1, fill_value=False))).sum())
            g.node("Regime", rid, kind=kind, name=v, months=n_months, spells=spells,
                   avg_spell_months=round(n_months / spells, 2) if spells else None)
            for c in concepts:
                g.rel("DEFINED_BY", "Regime", rid, "Concept", c)
        # matriz de transición empírica mensual
        s = rm[col]
        pairs = pd.DataFrame({"a": s.iloc[:-1].values, "b": s.iloc[1:].values}).dropna()
        cnt = pairs.value_counts().reset_index(name="count")
        tot = cnt.groupby("a")["count"].transform("sum")
        nonself = cnt[cnt.a != cnt.b].groupby("a")["count"].sum()
        for (_, r), t in zip(cnt.iterrows(), tot):
            p_change = None
            if r.a != r.b and nonself.get(r.a, 0):
                p_change = round(r["count"] / nonself[r.a], 4)
            g.rel("TRANSITIONED_TO", "Regime", f"{kind}:{r.a}", "Regime", f"{kind}:{r.b}",
                  count=int(r["count"]), p=round(r["count"] / t, 4), p_change=p_change,
                  kind=kind, from_month=rm["date"].iloc[0].date(), to_month=rm["date"].iloc[-1].date())
    prev = None
    for _, r in rm.iterrows():
        d = r["date"]
        sid = f"US-{d.year:04d}-{d.month:02d}"
        ids.append(sid)
        props = {c: r[c] for c in SNAPSHOT_COLS if c in rm.columns}
        g.node("RegimeSnapshot", sid, date=d.date(), year=d.year, month=d.month, country="USA", **props)
        g.rel("FROM_SOURCE", "RegimeSnapshot", sid, "Source", "regime_engine")
        for kind, (col, _) in REGIME_KINDS.items():
            if pd.notna(r[col]):
                g.rel("IN_REGIME", "RegimeSnapshot", sid, "Regime", f"{kind}:{r[col]}", kind=kind)
        if prev:
            g.rel("NEXT", "RegimeSnapshot", prev, "RegimeSnapshot", sid)
        prev = sid
    return set(ids)


def build_companies(g: Graph, path: Path = UNIVERSE):
    """Carga el universo de empresas si existe. Devuelve nº de filas o None si no hay fichero."""
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    cols = {c.lower(): c for c in df.columns}
    pick = lambda *names: next((cols[n] for n in names if n in cols), None)  # noqa: E731
    c_cik, c_tic = pick("cik", "cik_str"), pick("ticker", "symbol")
    c_name = pick("name", "company", "company_name", "title", "entity_name")
    c_sector = pick("gics_sector", "sector", "sic_description", "industry")
    c_country = pick("country", "country_iso3")
    _source(g, "sec_edgar")
    n = 0
    for _, r in df.iterrows():
        cik = r[c_cik] if c_cik else None
        tic = r[c_tic] if c_tic else None
        if cik is not None and pd.notna(cik):
            try:
                cid = f"CIK{int(cik):010d}"
            except (TypeError, ValueError):
                cid = f"CIK{cik}"
        elif tic is not None and pd.notna(tic):
            cid = f"TICKER:{tic}"
        else:
            continue
        props = {}
        for c in df.columns:
            v = r[c]
            if isinstance(v, (list, dict)) or (hasattr(v, "shape") and getattr(v, "shape", ()) != ()):
                continue
            props[re.sub(r"\W+", "_", str(c)).lower()] = _clean(v)
        props["name"] = r[c_name] if c_name else props.get("name")
        props["ticker"] = tic if tic is not None and pd.notna(tic) else None
        g.node("Company", cid, **props)
        g.rel("FROM_SOURCE", "Company", cid, "Source", "sec_edgar")
        if c_sector and pd.notna(r[c_sector]):
            sec = str(r[c_sector])
            sec_id = re.sub(r"\W+", "_", sec.lower()).strip("_")
            g.node("Sector", sec_id, name=sec, taxonomy=c_sector)
            g.rel("IN_SECTOR", "Company", cid, "Sector", sec_id)
        iso = norm_country(r[c_country]) if c_country and pd.notna(r[c_country]) else "USA"
        _country(g, iso)
        g.rel("IN_COUNTRY", "Company", cid, "Country", iso)
        n += 1
    return n


def build_all(warehouse: Path = WAREHOUSE, universe: Path = UNIVERSE, log=print) -> Graph:
    g = Graph()
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        build_reference(g)
        snaps = build_regimes(g, con)
        build_series(g, con)
        build_events(g, con, snaps)
    finally:
        con.close()
    n = build_companies(g, universe)
    log(f"[graph] universo de empresas: {'no encontrado (' + str(universe) + ')' if n is None else f'{n} filas'}")
    return g.dedupe()
