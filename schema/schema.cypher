// =====================================================================
// financial_kb — esquema Neo4j (Neo4j 5 community)
// Ejecutado por src/graph/load.py (cada sentencia separada por ';').
// Todo es idempotente (IF NOT EXISTS).
// =====================================================================

// ---------- Fase 2a: esqueleto estructural (cargado por src/graph/load.py) ----------
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT series_id IF NOT EXISTS FOR (n:DataSeries) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT country_id IF NOT EXISTS FOR (n:Country) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT assetclass_id IF NOT EXISTS FOR (n:AssetClass) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT event_id IF NOT EXISTS FOR (n:Event) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT regime_id IF NOT EXISTS FOR (n:Regime) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT snapshot_id IF NOT EXISTS FOR (n:RegimeSnapshot) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT investor_id IF NOT EXISTS FOR (n:Investor) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT company_id IF NOT EXISTS FOR (n:Company) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sector_id IF NOT EXISTS FOR (n:Sector) REQUIRE n.id IS UNIQUE;

CREATE INDEX series_name_index IF NOT EXISTS FOR (s:DataSeries) ON (s.name);
CREATE INDEX series_category_index IF NOT EXISTS FOR (s:DataSeries) ON (s.category);
CREATE INDEX event_type_index IF NOT EXISTS FOR (e:Event) ON (e.type);
CREATE INDEX event_start_index IF NOT EXISTS FOR (e:Event) ON (e.start_date);
CREATE INDEX regime_kind_index IF NOT EXISTS FOR (r:Regime) ON (r.kind);
CREATE INDEX snapshot_date_index IF NOT EXISTS FOR (s:RegimeSnapshot) ON (s.date);
CREATE INDEX snapshot_quadrant_index IF NOT EXISTS FOR (s:RegimeSnapshot) ON (s.quadrant);
CREATE INDEX company_ticker_index IF NOT EXISTS FOR (c:Company) ON (c.ticker);

// Modelo (Fase 2a):
// (:DataSeries)-[:FROM_SOURCE]->(:Source)
// (:DataSeries)-[:IN_COUNTRY]->(:Country)
// (:DataSeries)-[:MEASURES]->(:Concept)
// (:DataSeries)-[:TRACKS]->(:AssetClass)
// (:Event)-[:IN_COUNTRY]->(:Country)
// (:Event)-[:FROM_SOURCE]->(:Source)
// (:Event)-[:PRECEDED {lag_days, window_days}]->(:Event)       crisis encadenadas, mismo país
// (:Event)-[:OCCURRED_DURING {date_precision}]->(:RegimeSnapshot)   eventos USA/WLD >= 1950
// (:RegimeSnapshot)-[:IN_REGIME]->(:Regime)                   un Regime por dimensión (kind)
// (:RegimeSnapshot)-[:NEXT]->(:RegimeSnapshot)
// (:Regime)-[:TRANSITIONED_TO {count, p, p_change}]->(:Regime)  matriz empírica mensual, mismo kind
// (:Regime)-[:DEFINED_BY]->(:Concept)
// (:Concept)-[:RELATED_TO]->(:Concept)
// (:Investor)-[:FOCUSES_ON]->(:Concept)
// (:Company)-[:IN_SECTOR]->(:Sector), (:Company)-[:IN_COUNTRY]->(:Country)

// ---------- Fase 2b: textos (aún NO cargado) ----------
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (n:Claim) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT quote_id IF NOT EXISTS FOR (n:Quote) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT principle_id IF NOT EXISTS FOR (n:Principle) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT rule_id IF NOT EXISTS FOR (n:Rule) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT macrofactor_id IF NOT EXISTS FOR (n:MacroFactor) REQUIRE n.id IS UNIQUE;
CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX document_year_index IF NOT EXISTS FOR (d:Document) ON (d.year);

// Índice vectorial: se creará en Fase 2b cuando se fije el modelo de embeddings
// (PLAN.md: bge-base-en-v1.5 / nomic-embed-text-v1.5 => 768 dims, NO all-MiniLM 384).
// CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS
// FOR (c:Chunk) ON c.embedding
// OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}};

// Modelo (Fase 2b):
// (:Source)-[:DESCRIBES]->(:Document)-[:HAS_CHUNK]->(:Chunk)
// (:Chunk)-[:MENTIONS]->(:Entity|:Event|:Company|:Concept)
// (:Quote {char_start, char_end})-[:FROM_CHUNK]->(:Chunk); (:Investor)-[:SAID]->(:Quote)
// (:Quote)-[:EXPRESSES]->(:Principle)-[:OPERATIONALIZED_AS]->(:Rule)
// (:Claim)-[:SUPPORTED_BY]->(:Chunk); (:Claim)-[:ABOUT]->(:Entity)
// (:Company)-[:SENSITIVE_TO {beta, window}]->(:MacroFactor)-[:PROXIED_BY]->(:DataSeries)
