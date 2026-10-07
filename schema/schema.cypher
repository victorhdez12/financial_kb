// Core IDs
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT series_id IF NOT EXISTS FOR (n:DataSeries) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (n:Claim) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT event_id IF NOT EXISTS FOR (n:Event) REQUIRE n.id IS UNIQUE;

// Vector index for fast semantic retrieval.
// Current starter uses all-MiniLM-L6-v2 => 384 dimensions.
CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS
FOR (c:Chunk) ON c.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
}};

CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX document_year_index IF NOT EXISTS FOR (d:Document) ON (d.year);
CREATE INDEX series_name_index IF NOT EXISTS FOR (s:DataSeries) ON (s.name);

// Suggested core graph model:
// (:Source)-[:DESCRIBES]->(:Document)-[:HAS_CHUNK]->(:Chunk)
// (:Chunk)-[:MENTIONS]->(:Entity)
// (:Claim)-[:SUPPORTED_BY]->(:Chunk)
// (:Claim)-[:ABOUT]->(:Entity)
// (:Entity)-[:RELATES_TO|CAUSES|AFFECTS|PRECEDES]->(:Entity)
// (:Event)-[:INVOLVES]->(:Entity)
// (:DataSeries)-[:MEASURES]->(:Entity)
// (:DataSeries)-[:FROM_SOURCE]->(:Source)
