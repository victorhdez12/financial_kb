"""Carga idempotente del esqueleto estructural en Neo4j (MERGE + UNWIND por lotes).

    .venv/bin/python -m src.graph.load                 # schema + carga + recuento
    .venv/bin/python -m src.graph.load --export DIR    # sin Neo4j: CSV de nodos/relaciones
    .venv/bin/python -m src.graph.load --wipe          # borra TODO el grafo antes de cargar

Relaciones derivadas (PRECEDED, TRANSITIONED_TO, OCCURRED_DURING, NEXT, IN_REGIME) se borran y
recalculan en cada carga para no dejar aristas obsoletas si cambian los datos o los parámetros.
Credenciales: NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE desde .env.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from src.graph.build import ROOT, UNIVERSE, WAREHOUSE, Graph, build_all

SCHEMA = ROOT / "schema" / "schema.cypher"
BATCH = 1000
DERIVED_RELS = ["PRECEDED", "TRANSITIONED_TO", "OCCURRED_DURING", "NEXT", "IN_REGIME"]


def driver_from_env():
    from neo4j import GraphDatabase
    load_dotenv(ROOT / ".env")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.getenv("NEO4J_USERNAME", "neo4j"), os.environ["NEO4J_PASSWORD"])
    return GraphDatabase.driver(uri, auth=auth), os.getenv("NEO4J_DATABASE", "neo4j")


def wait_for_neo4j(timeout=120):
    drv, db = driver_from_env()
    t0 = time.time()
    while True:
        try:
            drv.verify_connectivity()
            return drv, db
        except Exception as e:  # noqa: BLE001
            if time.time() - t0 > timeout:
                raise SystemExit(f"Neo4j no responde tras {timeout}s: {type(e).__name__}")
            time.sleep(3)


def schema_statements(path: Path = SCHEMA):
    text = re.sub(r"//[^\n]*", "", path.read_text())
    return [s.strip() for s in text.split(";") if s.strip()]


def _chunks(rows, n=BATCH):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def write_graph(g: Graph, drv, db: str, wipe=False, log=print):
    with drv.session(database=db) as s:
        if wipe:
            log("[graph] --wipe: borrando el grafo")
            s.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS").consume()
        for stmt in schema_statements():
            s.run(stmt).consume()
        s.run("CALL db.awaitIndexes(300)").consume()
        for rt in DERIVED_RELS:
            s.run(f"MATCH ()-[r:{rt}]->() CALL (r) {{ DELETE r }} IN TRANSACTIONS OF 10000 ROWS").consume()

        for label, rows in g.nodes.items():
            q = f"UNWIND $rows AS r MERGE (n:`{label}` {{id: r.id}}) SET n += r.props"
            for b in _chunks(rows):
                s.execute_write(lambda tx, b=b: tx.run(q, rows=b).consume())
            log(f"[graph] nodos {label}: {len(rows)}")
        for rel in g.rels.values():
            q = (f"UNWIND $rows AS r "
                 f"MATCH (a:`{rel.src_label}` {{id: r.src}}) MATCH (b:`{rel.dst_label}` {{id: r.dst}}) "
                 f"MERGE (a)-[x:`{rel.type}`]->(b) SET x += r.props")
            for b in _chunks(rel.rows):
                s.execute_write(lambda tx, b=b: tx.run(q, rows=b).consume())
            log(f"[graph] rel ({rel.src_label})-[:{rel.type}]->({rel.dst_label}): {len(rel.rows)}")


def counts(drv, db):
    with drv.session(database=db) as s:
        nodes = s.run("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY l").data()
        rels = s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY t").data()
    return nodes, rels


def _csv_val(v):
    if isinstance(v, (list, tuple)):
        return ";".join(map(str, v))
    if isinstance(v, date):
        return v.isoformat()
    return "" if v is None else v


def export_csv(g: Graph, out: Path, log=print):
    """Exporta a CSV (una tabla por label / tipo de relación) + un import.cypher para LOAD CSV."""
    out.mkdir(parents=True, exist_ok=True)
    cy = []
    for label, rows in g.nodes.items():
        keys = sorted({k for r in rows for k in r["props"]})
        f = out / f"nodes_{label}.csv"
        with f.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", *keys])
            for r in rows:
                w.writerow([r["id"], *[_csv_val(r["props"].get(k)) for k in keys]])
        sets = ", ".join(f"n.`{k}` = row.`{k}`" for k in keys)
        cy.append(f"LOAD CSV WITH HEADERS FROM 'file:///{f.name}' AS row "
                  f"MERGE (n:`{label}` {{id: row.id}})" + (f" SET {sets}" if sets else "") + ";")
    for rel in g.rels.values():
        keys = sorted({k for r in rel.rows for k in r["props"]})
        f = out / f"rels_{rel.type}_{rel.src_label}_{rel.dst_label}.csv"
        with f.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["src", "dst", *keys])
            for r in rel.rows:
                w.writerow([r["src"], r["dst"], *[_csv_val(r["props"].get(k)) for k in keys]])
        sets = ", ".join(f"x.`{k}` = row.`{k}`" for k in keys)
        cy.append(f"LOAD CSV WITH HEADERS FROM 'file:///{f.name}' AS row "
                  f"MATCH (a:`{rel.src_label}` {{id: row.src}}) MATCH (b:`{rel.dst_label}` {{id: row.dst}}) "
                  f"MERGE (a)-[x:`{rel.type}`]->(b)" + (f" SET {sets}" if sets else "") + ";")
    (out / "import.cypher").write_text(
        "// Generado por src.graph.load --export. Copiar los CSV a ~/financial_archive/neo4j/import/\n"
        "// Nota: LOAD CSV carga todo como string (las fechas/números habría que convertirlos).\n"
        + "\n".join(cy) + "\n")
    log(f"[graph] export CSV en {out}: {len(g.nodes)} labels, {len(g.rels)} tipos de relación")


def summary(g: Graph):
    return ({k: len(v) for k, v in g.nodes.items()},
            {f"{r.src_label}-{r.type}->{r.dst_label}": len(r.rows) for r in g.rels.values()})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--warehouse", type=Path, default=WAREHOUSE)
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    ap.add_argument("--export", type=Path, help="exporta CSV + import.cypher en vez de escribir en Neo4j")
    ap.add_argument("--wipe", action="store_true", help="DETACH DELETE de todo el grafo antes de cargar")
    a = ap.parse_args(argv)

    t0 = time.time()
    g = build_all(a.warehouse, a.universe)
    n, r = summary(g)
    print("[graph] construido:", json.dumps(n, ensure_ascii=False))
    if a.export:
        export_csv(g, a.export)
        return 0
    drv, db = wait_for_neo4j()
    try:
        write_graph(g, drv, db, wipe=a.wipe)
        nodes, rels = counts(drv, db)
    finally:
        drv.close()
    print("\n== Neo4j: nodos por label ==")
    for x in nodes:
        print(f"  {x['l']:<16} {x['c']:>7}")
    print("== Neo4j: relaciones por tipo ==")
    for x in rels:
        print(f"  {x['t']:<16} {x['c']:>7}")
    print(f"[graph] hecho en {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
