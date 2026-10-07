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
