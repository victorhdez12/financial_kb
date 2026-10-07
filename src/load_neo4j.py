from __future__ import annotations
import argparse
import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

BATCH = 64


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument('--parquet', required=True)
    ap.add_argument('--batch-size', type=int, default=BATCH)
    args = ap.parse_args()

    df = pd.read_parquet(args.parquet)
    if df.empty:
        raise SystemExit('No chunks found')

    model_name = os.getenv('EMBED_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    model = SentenceTransformer(model_name)

    uri = os.environ['NEO4J_URI']
    user = os.environ.get('NEO4J_USERNAME', 'neo4j')
    password = os.environ['NEO4J_PASSWORD']
    database = os.environ.get('NEO4J_DATABASE', 'neo4j')
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()

    rows = df.to_dict('records')
    for start in range(0, len(rows), args.batch_size):
        batch = rows[start:start + args.batch_size]
        embeddings = model.encode([r['text'] for r in batch], normalize_embeddings=True).tolist()
        payload = []
        for r, emb in zip(batch, embeddings):
            payload.append({**r, 'embedding': emb})

        with driver.session(database=database) as session:
            session.run('''
            UNWIND $rows AS r
            MERGE (d:Document {id:r.document_id})
              ON CREATE SET d.title=r.title, d.source_file=r.source_file
            MERGE (c:Chunk {id:r.chunk_id})
              ON CREATE SET c.text=r.text, c.page=r.page, c.chunk_index=r.chunk_index,
                            c.source_file=r.source_file, c.embedding=r.embedding
              ON MATCH SET c.embedding=r.embedding, c.text=r.text, c.page=r.page
            MERGE (d)-[:HAS_CHUNK]->(c)
            ''', rows=payload)
        print(f'Loaded {min(start + len(batch), len(rows)):,}/{len(rows):,}')

    driver.close()

if __name__ == '__main__':
    main()
