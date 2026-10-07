#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp -n .env.example .env || true
printf '\nEnvironment ready. Edit .env, then run the Neo4j schema.\n'
