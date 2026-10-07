# Financial & Macro Knowledge Engine

A flexible starter architecture for a long-run financial/macro knowledge base (1800-present) built around:

- **Neo4j AuraDB**: knowledge graph + vector index for fast retrieval.
- **DuckDB + Parquet**: historical numeric time series; keep bulk data out of the graph.
- **Obsidian + Git**: human-maintained concepts, theses, assumptions and research notes.
- **PDF ingestion**: PyMuPDF -> chunks -> local embeddings -> Neo4j.
- **Fast agent retrieval**: vector top-k + graph expansion in a single Neo4j round trip.

## 1. Folder layout

```text
financial_kb/
├── config/sources.yaml
├── schema/schema.cypher
├── src/
│   ├── ingest_pdfs.py
│   ├── ingest_tabular.py
│   ├── load_neo4j.py
│   └── query_context.py
├── scripts/
│   └── setup_venv.sh
├── download_financial_archive.py   # SEC 10-K + CompanyFacts, FRED, BLS → $FIN_DATA_ROOT
├── download_berkshire_letters.py   # Berkshire letters 1977-present → $FIN_DATA_ROOT/berkshire_letters
├── data/archive -> ~/financial_archive   # symlink to the raw archive (not in git)
├── data/raw/pdfs/       # put owned/licensed/public-domain PDFs here
├── data/raw/tabular/    # CSV/XLSX data files here
├── data/processed/      # Parquet + extracted text
└── obsidian/             # vault
```

### Raw archive (`~/financial_archive`, via `data/archive`)

```text
sec/10k/<TICKER>/<YEAR>/<ACCESSION>/   # submission.txt, 10k_clean.txt, metadata.json
sec/companyfacts/                      # XBRL facts (2009+)
macro/fred/  macro/bls/  macro/derived/
berkshire_letters/                     # 1977-1999 .txt, 2000-present .pdf
manifests/  logs/
```

Downloads (keys go in `.env`, see `.env.example`):

```bash
python download_financial_archive.py --mode sec     # needs SEC_USER_AGENT
python download_financial_archive.py --mode macro   # needs FRED_API_KEY (BLS_API_KEY optional)
python download_berkshire_letters.py
```

## 2. Neo4j

Create an AuraDB Free instance and copy credentials into `.env`.
Run `schema/schema.cypher` once.

For the first version use the conservative graph-size limits shown on Neo4j's current Free-tier page. Keep document chunks reasonably small and do not put every time-series observation into Neo4j.

## 3. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 4. Ingest PDFs

Put your PDFs in `data/raw/pdfs/` and run:

```bash
python -m src.ingest_pdfs --input data/raw/pdfs --output data/processed/pdf_chunks.parquet
python -m src.load_neo4j --parquet data/processed/pdf_chunks.parquet
```

The extractor stores title, author, year, page, source file and chunk text. It also creates deterministic IDs so re-running ingestion is idempotent.

**Copyright:** ingest books/documents you are entitled to use. The pipeline does not fetch pirated copies.

## 5. Ingest historical datasets

Place CSV/XLSX files in `data/raw/tabular/` and run:

```bash
python -m src.ingest_tabular --input data/raw/tabular --output data/processed/series
```

The numeric values remain in Parquet. Neo4j receives only metadata about each series, source, coverage and file location.

## 6. Fast retrieval for agents

```bash
python -m src.query_context "What normally happens to long-duration equities when real rates rise sharply during a credit tightening?"
```

The query path is intentionally simple:

```text
user question
   ↓
local embedding
   ↓
Neo4j vector index (top-k chunks)
   ↓
graph expansion: entities / concepts / relationships / sources
   ↓
compact context returned to agent
```

This avoids doing a separate vector DB call + graph DB call for every question.

## 7. Recommended expansion path

Phase 1: source ingestion + retrieval.
Phase 2: entity and relationship extraction with provenance.
Phase 3: historical-event layer and macro regime classification.
Phase 4: FRED/ALFRED real-time vintages + market data.
Phase 5: news agent that maps today's news onto historical precedents.
Phase 6: portfolio decision-support agent that separates facts, historical analogies, scenarios and user-specific portfolio rules.

Keep every claim attributable to one or more sources and allow contradictory claims to coexist. Do not overwrite old knowledge when a new source disagrees; add provenance and confidence instead.
