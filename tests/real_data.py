"""Separación de los tests que necesitan datos reales (fuera de git, en FIN_DATA_ROOT) de los sintéticos.

- `requires_real_data`: marca de los tests que leen la etiqueta oficial, sus entradas, la base PIT o los baselines
  congelados. Sin esos ficheros se saltan con una razón explícita; con ellos corren igual que antes.
- `FKB_REQUIRE_REAL_DATA=1`: en la máquina con datos, convierte la falta de datos en un error de recogida en vez de
  saltos silenciosos (que los tests de fugas PIT no dejen de correr sin que nadie lo note).
- `synthetic_label_meta` (fixture en tests/conftest.py): solo para tests sintéticos que pasan por
  `R.assert_no_forbidden` sin `extra`/`meta` (src/labels/regime_us.py), que exige el meta.json oficial.
"""
from __future__ import annotations

import os

import pytest

from src.features import pit as P
from src.labels import regime_us as R

LABEL_META = R.out_path().with_suffix(".meta.json")
REAL_DATA = R.out_path().exists() and LABEL_META.exists() and P.out_dir().exists()

if os.environ.get("FKB_REQUIRE_REAL_DATA") == "1" and not REAL_DATA:
    raise RuntimeError(f"FKB_REQUIRE_REAL_DATA=1 pero faltan datos reales ({R.out_path()}, {LABEL_META}, {P.out_dir()})")

requires_real_data = pytest.mark.skipif(
    not REAL_DATA,
    reason=(f"necesita datos reales fuera de git (etiqueta oficial {R.out_path().name} y su meta.json, entradas de "
            f"la etiqueta, base PIT y baselines en {P.out_dir()}); no están en este entorno"))
