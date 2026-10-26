# Fase 1 — pipeline macro. Usa siempre el Python del venv.
PY := .venv/bin/python

.PHONY: all warehouse regime validate weekly clean-warehouse

all: warehouse regime validate weekly

warehouse:            ## DuckDB desde macro/{fred,bls} legacy + curated/*/*.parquet + events/*.parquet
	$(PY) -m src.warehouse.build

regime: warehouse     ## regime_monthly (1950 -> hoy), point-in-time
	$(PY) -m src.regime.run

validate: regime      ## docs/phase1_validation.md
	$(PY) -m src.regime.validate

weekly: regime        ## obsidian/Reports/AAAA-MM-DD_semanal.md + _signal.json
	$(PY) -m src.report.weekly

clean-warehouse:
	rm -f data/warehouse.duckdb data/warehouse.tmp.duckdb

# Fase 2 — grafo Neo4j local (docker-compose.yml; credenciales en .env)
.PHONY: graph-up graph-load graph-down

graph-up:             ## arranca Neo4j (Docker) y espera a que esté healthy
	mkdir -p $(HOME)/financial_archive/neo4j/data $(HOME)/financial_archive/neo4j/logs $(HOME)/financial_archive/neo4j/import $(HOME)/financial_archive/neo4j/plugins
	docker compose up -d
	@for i in $$(seq 1 60); do [ "$$(docker inspect -f '{{.State.Health.Status}}' financial_kb_neo4j 2>/dev/null)" = healthy ] && echo "neo4j healthy" && exit 0; sleep 3; done; echo "neo4j no está healthy" && exit 1

graph-load:           ## esqueleto estructural del grafo desde warehouse.duckdb (idempotente)
	$(PY) -m src.graph.load

graph-down:           ## para Neo4j (los datos persisten en ~/financial_archive/neo4j)
	docker compose down

# Fase de datos — ingesta y auditoría
# Orden: ecb antes que bundesbank (el empalme del tipo oficial alemán usa ecb_mro_d).
INGEST := fred_extended alfred_vintages fred_us fed_yieldcurve us_treasury nyfed_hhdc nber_macrohistory \
          shiller shiller_housing us_hist_labor ken_french damodaran wb_pinksheet measuringworth gold \
          fred_banking_1914 fed_z1 nyfed_repo us_liquidity cb_balance_sheets \
          ken_french_intl aqr jkp cftc_cot cboe fed_ebp \
          cboe_vx eia_futures atl_mpt clev_inflexp mpls_mpd \
          cycle_nyfed cycle_rtdsm cycle_spf umich \
          ecb eurostat bde ine bundesbank ifo zew \
          cycle_bis bis_ext oecd oecd_qna aqr_clr imf_weo imf_ifs imf_gdd imf_hpdd wb_wdi jst_macrohistory boe_millennium_uk cycle_worldorder \
          events_nber events_wars events_financial_crises events_gpr events_curated
.PHONY: ingest audit data ingest-daily daily semanal

# Fuentes con datos diarios o semanales (actualización diaria automática, ver scripts/actualizar.sh)
INGEST_DAILY := fred_extended fed_yieldcurve us_liquidity nyfed_repo ecb bundesbank cboe cboe_vx atl_mpt umich

ingest:               ## descarga/actualiza todas las fuentes curadas (lento; idempotente)
	@for s in $(INGEST); do echo "== $$s"; $(PY) -m src.ingest.$$s || echo "FALLO $$s"; done

audit:                ## docs/data/audit_<hoy>.md + CSV (solo lectura)
	$(PY) -m src.audit.run

data: ingest warehouse regime audit   ## ciclo completo de la fase de datos

ingest-daily:         ## solo las fuentes diarias (minutos)
	@for s in $(INGEST_DAILY); do echo "== $$s"; $(PY) -m src.ingest.$$s || echo "FALLO $$s"; done

daily: ingest-daily warehouse regime   ## actualización diaria (launchd, lun-sáb)

semanal: data weekly  ## actualización completa + auditoría + reporte (launchd, domingo)
