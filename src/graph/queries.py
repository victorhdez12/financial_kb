"""Consultas de ejemplo sobre el grafo estructural.

    .venv/bin/python -m src.graph.queries list
    .venv/bin/python -m src.graph.queries current
    .venv/bin/python -m src.graph.queries similar-regime [--match quadrant,credit]
    .venv/bin/python -m src.graph.queries after-credit [--country USA]
    .venv/bin/python -m src.graph.queries transitions
    .venv/bin/python -m src.graph.queries wars-in-regime [--regime Estanflación]
    .venv/bin/python -m src.graph.queries chain --event lehman_2008
    .venv/bin/python -m src.graph.queries concept --concept debt_cycle
    .venv/bin/python -m src.graph.queries all
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from src.graph.load import driver_from_env

Q = {}


def query(name, help_):
    def deco(fn):
        Q[name] = (fn, help_)
        return fn
    return deco


@query("current", "Último RegimeSnapshot y sus regímenes por dimensión")
def q_current(a):
    return """
    MATCH (s:RegimeSnapshot) WITH s ORDER BY s.date DESC LIMIT 1
    MATCH (s)-[:IN_REGIME]->(r:Regime)
    RETURN s.id AS snapshot, s.cutoff AS cutoff, r.kind AS kind, r.name AS regime,
           r.months AS months_hist, r.avg_spell_months AS avg_spell
    ORDER BY kind""", {}


@query("similar-regime", "Eventos (USA/WLD, >=1950) ocurridos en meses con el mismo régimen que el actual")
def q_similar(a):
    kinds = [k.strip() for k in a.match.split(",") if k.strip()]
    return """
    MATCH (cur:RegimeSnapshot) WITH cur ORDER BY cur.date DESC LIMIT 1
    MATCH (cur)-[:IN_REGIME]->(r:Regime) WHERE r.kind IN $kinds
    WITH cur, collect(r) AS regs
    MATCH (s:RegimeSnapshot) WHERE s <> cur
      AND all(r IN regs WHERE (s)-[:IN_REGIME]->(r))
    MATCH (e:Event)-[:OCCURRED_DURING]->(s)
    RETURN s.id AS month, [r IN regs | r.name] AS regime, e.type AS type, e.name AS event
    ORDER BY month DESC LIMIT $limit""", {"kinds": kinds, "limit": a.limit}


@query("after-credit", "Crisis/recesiones que siguieron a un credit_event (PRECEDED, mismo país, <=365 días; 730 si fecha anual)")
def q_after_credit(a):
    return """
    MATCH (c:Event {type:'credit_event'})-[p:PRECEDED]->(e:Event)
    WHERE ($country IS NULL OR p.country = $country) AND e.type <> 'credit_event'
    RETURN c.start_date AS credit_date, c.name AS credit_event, p.lag_days AS lag_days,
           e.type AS followed_by_type, e.name AS followed_by, p.country AS country,
           p.date_precision AS precision
    ORDER BY credit_date DESC LIMIT $limit""", {"country": a.country, "limit": a.limit}


@query("transitions", "Transiciones empíricas más probables desde el régimen actual (por dimensión)")
def q_transitions(a):
    return """
    MATCH (cur:RegimeSnapshot) WITH cur ORDER BY cur.date DESC LIMIT 1
    MATCH (cur)-[:IN_REGIME]->(r:Regime)-[t:TRANSITIONED_TO]->(n:Regime)
    WITH r, t, n ORDER BY r.kind, t.p DESC
    RETURN r.kind AS kind, r.name AS from_regime, n.name AS to_regime, t.count AS months,
           t.p AS p_next_month, t.p_change AS p_if_changes""", {}


@query("wars-in-regime", "Guerras (cualquier país, >=1950) que empezaron en un mes con ese cuadrante US")
def q_wars(a):
    return """
    MATCH (r:Regime {kind:'quadrant', name:$regime})<-[:IN_REGIME]-(s:RegimeSnapshot)
    MATCH (e:Event {type:'war'})
    WHERE e.start_date >= date('1950-01-01')
      AND e.start_date.year = s.year AND e.start_date.month = s.month
    RETURN s.id AS month, e.name AS war, e.countries AS countries, e.severity AS battle_deaths,
           e.dataset AS dataset
    ORDER BY month LIMIT $limit""", {"regime": a.regime, "limit": a.limit}


@query("chain", "Cadena de crisis que parte de un evento (PRECEDED*1..3)")
def q_chain(a):
    return """
    MATCH (e:Event) WHERE e.id = $event OR toLower(e.name) CONTAINS toLower($event)
    WITH e LIMIT 1
    MATCH path = (e)-[:PRECEDED*1..3]->(x:Event)
    RETURN [n IN nodes(path) | n.start_date + ' ' + n.name] AS chain,
           reduce(d = 0, r IN relationships(path) | d + r.lag_days) AS total_lag_days
    ORDER BY total_lag_days LIMIT $limit""", {"event": a.event, "limit": a.limit}


@query("concept", "Series que miden un concepto + inversores y regímenes asociados")
def q_concept(a):
    return ("""
    MATCH (c:Concept) WHERE c.id = $concept OR toLower(c.name) = toLower($concept)
    OPTIONAL MATCH (i:Investor)-[:FOCUSES_ON]->(c)
    OPTIONAL MATCH (r:Regime)-[:DEFINED_BY]->(c)
    WITH c, collect(DISTINCT i.name) AS investors, collect(DISTINCT r.kind) AS regime_kinds
    MATCH (s:DataSeries)-[:MEASURES]->(c)
    WHERE s.country IN ['USA', 'WLD'] OR $all_countries
    RETURN c.name AS concept, investors, regime_kinds, s.id AS series, s.name AS name,
           s.frequency AS freq, s.start AS start
    ORDER BY s.start LIMIT $limit""",
    {"concept": a.concept, "limit": a.limit, "all_countries": a.all_countries})


def run(name, a, session):
    fn, help_ = Q[name]
    cypher, params = fn(a)
    df = pd.DataFrame(session.run(cypher, **params).data())
    print(f"\n### {name} — {help_}")
    if df.empty:
        print("(sin resultados)")
    else:
        with pd.option_context("display.max_colwidth", 70, "display.width", 220):
            print(df.to_string(index=False))
    return df


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", choices=[*Q, "all", "list"])
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--match", default="quadrant,credit", help="dimensiones para similar-regime")
    ap.add_argument("--country", default=None)
    ap.add_argument("--regime", default="Estanflación")
    ap.add_argument("--event", default="lehman")
    ap.add_argument("--concept", default="debt_cycle")
    ap.add_argument("--all-countries", action="store_true")
    a = ap.parse_args(argv)
    if a.name == "list":
        for k, (_, h) in Q.items():
            print(f"{k:<16} {h}")
        return 0
    drv, db = driver_from_env()
    try:
        with drv.session(database=db) as s:
            for n in (Q if a.name == "all" else [a.name]):
                run(n, a, s)
    finally:
        drv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
