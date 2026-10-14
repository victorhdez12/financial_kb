"""Read-only data-quality audit of the curated layer, legacy CSVs and the DuckDB warehouse.

Run: .venv/bin/python -m src.audit.run [--today YYYY-MM-DD] [--csv PATH] [--json PATH]
Nothing here writes to $FIN_DATA_ROOT or data/warehouse.duckdb (DuckDB is opened read_only).
"""
