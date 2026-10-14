# Grafo de conocimiento (Neo4j) — Fase 2a: esqueleto estructural

El grafo **no guarda observaciones**: los números viven en DuckDB (`data/warehouse.duckdb`).
El grafo guarda *qué* existe (series, eventos, regímenes, conceptos, inversores, empresas) y
*cómo se relaciona*, para que los agentes naveguen contexto y luego pidan las cifras a DuckDB.

## Arranque

```bash
make graph-up      # docker compose up -d (neo4j:5-community) y espera a healthy
make graph-load    # .venv/bin/python -m src.graph.load  (idempotente, ~2-4 s)
make graph-down    # docker compose down (los datos persisten)
```

- Browser: <http://localhost:7474> · Bolt: `bolt://localhost:7687` (solo 127.0.0.1).
- Credenciales: `.env` → `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` (aleatoria), `NEO4J_DATABASE`.
  Los valores Aura anteriores quedaron comentados en `.env` como `NEO4J_AURA_*`.
- Memoria: `NEO4J_HEAP` / `NEO4J_PAGECACHE` en `.env` (por defecto 2G / 2G).
- Volúmenes: `~/financial_archive/neo4j/{data,logs,import,plugins}`.
- Sin Docker: `python -m src.graph.load --export DIR` escribe CSV por label/relación + `import.cypher`.
- `--wipe` borra todo el grafo antes de cargar. Sin él, nodos con `MERGE` por `id` y
  `SET n += props`; las relaciones derivadas (`PRECEDED`, `TRANSITIONED_TO`, `OCCURRED_DURING`,
  `NEXT`, `IN_REGIME`) se borran y recalculan en cada carga.

Código: `src/graph/build.py` (lee DuckDB en solo lectura y construye filas),
`src/graph/load.py` (schema + `UNWIND` por lotes de 1000), `src/graph/queries.py` (consultas CLI).
Esquema: `schema/schema.cypher` (constraints de unicidad sobre `id` + índices).

## Modelo

| Nodo | id | origen | nº (2026-10-07) |
|---|---|---|---|
| `Source` | `source_id` | catalog.source, events.source | 20 |
| `DataSeries` | `series_id` | `catalog` (1.842 filas → 1.776 ids; fred/fred_legacy fusionados, `sources` lista ambas) | 1.776 |
| `Country` | ISO3 (`US`→`USA`, `EA`→`EMU`; `WLD`, `EM`, `G7` = agregados; `kind=non_state_or_unknown` para actores no estatales COW/UCDP) | catalog + events | 203 |
| `AssetClass` | equities, govt_bonds, corp_credit, cash, commodities, gold, fx, real_estate | curado | 8 |
| `Concept` | growth, inflation, real_rates, yield_curve, credit, credit_spread, debt_cycle, liquidity, money_supply, monetary_policy, fiscal, financial_conditions, volatility, valuation… | curado | 23 |
| `Event` | `event_id` | `events` (guerras, crisis RR/LV/JST, recesiones NBER, curados, `credit_event`) | 3.269 |
| `Regime` | `<kind>:<valor>`; kinds = quadrant, debt_phase, credit, liquidity, long_cycle | `regime_monthly` | 19 |
| `RegimeSnapshot` | `US-AAAA-MM` (1950-01 → 2026-10, point-in-time; el último mes es parcial, ver `cutoff`) | `regime_monthly` | 922 |
| `Investor` | buffett, dalio, marks, munger, graham, lynch, soros, druckenmiller, templeton, keynes, minsky, fisher, bagehot (sin citas) | curado | 13 |
| `Company`, `Sector` | `CIK##########` (o `TICKER:x`) | `~/financial_archive/sec/universe/universe.parquet` si existe | 0 (fichero aún no creado) |

| Relación | nº | notas |
|---|---|---|
| `(DataSeries)-[:FROM_SOURCE]->(Source)` | 1.842 | |
| `(DataSeries)-[:IN_COUNTRY]->(Country)` | 1.772 | |
| `(DataSeries)-[:MEASURES]->(Concept)` | 1.973 | por categoría + reglas por id (DFII*→real_rates, BAA10Y/OAS→credit_spread, T10Y*→yield_curve, deuda/PIB→debt_cycle, WALCL/RRP/TGA→liquidity) |
| `(DataSeries)-[:TRACKS]->(AssetClass)` | 824 | heurística por categoría/nombre |
| `(Event)-[:FROM_SOURCE]->(Source)` / `[:IN_COUNTRY]->(Country)` | 3.269 / 3.764 | `country` con `;` → varias aristas |
| `(Event)-[:PRECEDED {lag_days, country, window_days, date_precision}]->(Event)` | 849 | ver abajo |
| `(Event)-[:OCCURRED_DURING {date_precision, scope}]->(RegimeSnapshot)` | 126 | eventos con país USA o WLD y `start_date` ≥ 1950 → mes de inicio |
| `(RegimeSnapshot)-[:IN_REGIME {kind}]->(Regime)` | 4.454 | una arista por dimensión (liquidez nula antes de ~1963) |
| `(RegimeSnapshot)-[:NEXT]->(RegimeSnapshot)` | 921 | |
| `(Regime)-[:TRANSITIONED_TO {count, p, p_change}]->(Regime)` | 67 | matriz mensual empírica dentro de cada kind; `p` incluye permanencia, `p_change` = prob. condicionada a cambiar |
| `(Regime)-[:DEFINED_BY]->(Concept)` | 53 | |
| `(Concept)-[:RELATED_TO]->(Concept)` | 21 | curado |
| `(Investor)-[:FOCUSES_ON {basis:'curated_v0'}]->(Concept)` | 31 | curado, sin citas todavía |
| `(Company)-[:IN_SECTOR]->(Sector)`, `[:IN_COUNTRY]`, `[:FROM_SOURCE]` | 0 | loader listo y probado con un parquet sintético |

`Regime` guarda `months`, `spells` y `avg_spell_months` (duración media de cada racha).

**PRECEDED** (crisis encadenadas): tipos `banking_crisis, currency_crisis, sovereign_default,
inflation_crisis, market_crash, credit_event, recession, oil_shock, pandemic` (sin guerras ni
`policy`); mismo país (intersección de códigos; `WLD` solo enlaza con `WLD`); B empieza
después de A con `lag ≤ 365 días`, o `≤ 730` si alguna fecha es anual (Reinhart-Rogoff,
Laeven-Valencia, JST: `start_date` = 1 de enero → `date_precision='year'`, el lag es aproximado).
Por cada A y cada tipo de B solo se enlaza el **primer** B (evita abanicos). Mismo tipo desde otra
fuente se descarta (duplicado probable LV↔RR). Es co-ocurrencia temporal, **no causalidad**.

## Consultas (`.venv/bin/python -m src.graph.queries <nombre>`)

| nombre | qué responde |
|---|---|
| `current` | último snapshot y su régimen en cada dimensión |
| `similar-regime [--match quadrant,credit]` | eventos USA/WLD en meses con el mismo régimen que el actual |
| `after-credit [--country USA]` | qué crisis/recesiones siguieron a cada `credit_event` |
| `transitions` | transiciones más probables desde el régimen actual (por dimensión) |
| `wars-in-regime [--regime Estanflación]` | guerras (cualquier país, ≥1950) iniciadas en meses con ese cuadrante US |
| `chain --event lehman` | cadenas `PRECEDED*1..3` desde un evento (id o texto) |
| `concept --concept debt_cycle` | series que miden un concepto + inversores y regímenes asociados |
| `all` / `list` | ejecutar todas / listar |

Ejemplo (2026-10-07): régimen actual = Deflación/recesión · expansión temprana · crédito verde ·
liquidez neutral · ciclo largo tardío. Desde Deflación/recesión, p(seguir el mes siguiente)=0,81;
si cambia, Goldilocks 0,60 / Estanflación 0,39 / Reflación 0,01.

Cypher directo, p. ej. eventos durante Estanflación con crédito rojo:

```cypher
MATCH (e:Event)-[:OCCURRED_DURING]->(s:RegimeSnapshot)-[:IN_REGIME]->(:Regime {id:'quadrant:Estanflación'}),
      (s)-[:IN_REGIME]->(:Regime {id:'credit:rojo'})
RETURN s.id, e.type, e.name ORDER BY s.id;
```

## Limitaciones

- `OCCURRED_DURING` solo enlaza eventos USA/WLD: los regímenes son de EE. UU. Para otros
  países, `wars-in-regime` cruza por fecha (régimen US como proxy global).
- El régimen de los snapshots es el estimado point-in-time por `src/regime`; si se reconstruye
  `regime_monthly`, basta con `make graph-load`.
- Investor→Concept y Series→AssetClass son mapeos curados/heurísticos (v0), no extraídos de texto.

## Fase 2b (pendiente)

1. **Textos**: `(:Source)-[:DESCRIBES]->(:Document)-[:HAS_CHUNK]->(:Chunk)` para cartas de
   Berkshire, Dalio, memos de Marks, 10-K por secciones (1, 1A, 7, 7A, 9A); chunks de 300-400
   tokens con cabecera; `(:Chunk)-[:MENTIONS]->(:Event|:Company|:Concept|:Investor)`.
2. **Embeddings**: bge-base-en-v1.5 o nomic-embed-text-v1.5 (768 dims) + reranker; el índice
   vectorial está comentado en `schema.cypher` hasta fijar el modelo.
3. **Quote / Principle / Rule**: `(:Investor)-[:SAID]->(:Quote {char_start,char_end})-[:FROM_CHUNK]->(:Chunk)`,
   `(:Quote)-[:EXPRESSES]->(:Principle)-[:OPERATIONALIZED_AS]->(:Rule)` con las reglas comprobables
   de PLAN.md (ROIC, Graham, PEG, Marks/péndulo…).
4. **Empresas**: cargar `universe.parquet` (incluidas quebradas) y
   `(:Company)-[:SENSITIVE_TO {beta, window}]->(:MacroFactor)-[:PROXIED_BY]->(:DataSeries)`
   con betas calculadas en Python sobre DuckDB.
5. Enlaces evento↔serie (`(:Event)-[:MOVED {delta, horizon}]->(:DataSeries)`) calculados en DuckDB.
