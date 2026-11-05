"""P-K1v (docs/int/K1_vivo_prerregistro_v1.md, v1.0): ajuste ÚNICO de L (B1) y K (B1 + Δ5 crédito/PIB) con las filas
de K1 de INT-6 (≤ 2004) y congelación con sha256. No evalúa nada (la evaluación es en vivo).

Uso: .venv/bin/python -m scripts.k1_corrida   (puerta: árbol limpio, sha256 del prerregistro; una sola vez)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from scripts import int6_corrida as C
from src.intl import data as D
from src.intl import int4 as M
from src.intl import int6 as S
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs/int/K1_vivo_prerregistro_v1.md"
DOC_SHA = "72696291c9abb70f0c98fbfbfb0589d9dc14f64483357e50bc0f80843952e451"
SALIDA = REPO / "research/int/k1_modelos.json"
ESPERADO = (1137, 49)


def sha(m: dict) -> str:
    return hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()


def main() -> None:
    if SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: el ajuste de K1v es único")
    if hashlib.sha256(DOC.read_bytes()).hexdigest() != DOC_SHA:
        raise SystemExit("el prerregistro no coincide con el congelado v1.0")
    proc = procedencia(exigir_limpio=True)
    con = D.connect()
    pr = C.preparar(C.cargar(con))
    x = (pr["W"]["tloans"] / pr["W"]["gdp"]).diff(5) * 100
    f = C.filas_k1(pr, C.NUCLEO)
    base = S.liston_crisis(f, pr["crisis"], pr["primer"])
    X = S.mirar(f, [x])
    ok = S._ok(base, X)
    y = f.y.to_numpy(float)[ok]
    n, ev = int(ok.sum()), int(y.sum())
    if (n, ev) != ESPERADO:
        raise SystemExit(f"filas/eventos {n}/{ev} ≠ INT-6 {ESPERADO}")
    bK = M.logit_fit(np.column_stack([base[ok], X[ok]]), y)
    bL = M.logit_fit(base[ok], y)
    mod = {"L": {"cols": ["B1"], "b": bL.tolist()}, "K": {"cols": ["B1", "x_d5_credito_pp"], "b": bK.tolist()}}
    out = {"documento": "P-K1v v1.0", "doc_sha256": DOC_SHA, "procedencia": proc, "filas": n, "eventos": ev,
           "paises": C.NUCLEO, "modelos": mod, "modelos_sha256": sha(mod),
           "estado": "congelado" if bK[2] > 0 else "PARADO: coeficiente del crédito ≤ 0",
           "nota": "solo ajuste ≤ 2004; ninguna métrica de desarrollo cuenta; evaluación en vivo (§4)"}
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: out[k] for k in ("filas", "eventos", "estado", "modelos_sha256")}, indent=1), mod)


if __name__ == "__main__":
    main()
