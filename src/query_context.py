from __future__ import annotations
import argparse
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument('question', nargs='+')
    ap.add_argument('--top-k', type=int, default=8)
    args = ap.parse_args()
    question = ' '.join(args.question)

    model = SentenceTransformer(os.getenv('EMBED_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'))
    query_vec = model.encode(question, normalize_embeddings=True).tolist()

    driver = GraphDatabase.driver(os.environ['NEO4J_URI'], auth=(
        os.environ.get('NEO4J_USERNAME', 'neo4j'), os.environ['NEO4J_PASSWORD']))
    database = os.environ.get('NEO4J_DATABASE', 'neo4j')
    with driver.session(database=database) as session:
        records = session.run('''
        CALL db.index.vector.queryNodes('chunk_embedding_index', $k, $embedding)
        YIELD node, score
        MATCH (d:Document)-[:HAS_CHUNK]->(node)
        RETURN node.id AS chunk_id, d.title AS document, node.source_file AS source_file,
               node.page AS page, score, node.text AS text
        ORDER BY score DESC
        ''', k=args.top_k, embedding=query_vec).data()

    for r in records:
        print(f"\n--- {r['document']} p.{r['page']} | score={r['score']:.4f} ---")
        print(r['text'])
    driver.close()

if __name__ == '__main__':
    main()
