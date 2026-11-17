"""Tabla DESCRIPTIVA de las alertas de volumen de un día (docs/panel/alertas_v1.md, sección «Historia»).

    .venv/bin/python scripts/alertas_descriptivo.py [--anios 10]

Con los umbrales YA FIJADOS en src/report/alertas.py (no se cambian aquí ni a la vista de esto): cuántas alertas de
volumen (moderadas + fuertes, sin días especiales) habría dado cada activo por año en los últimos `--anios` años y qué
hizo el precio 1, 5 y 20 sesiones después (media ± desviación típica, n), por clase. NO es una validación: sin grupo de
control emparejado, con solapes entre ventanas, muchos activos correlacionados y pocos casos por clase (ruido).
Imprime Markdown (los números del doc salen de aquí; datos de terceros solo en $FIN_DATA_ROOT).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.report import alertas as AL  # noqa: E402


def _f(x, k=1):
    return "—" if x is None else f"{100 * x:+.{k}f}".replace(".", ",").replace("-", "−")


def main(anios: int = 10) -> None:
    X = AL.cargar()
    filas, tot = [], {"sube": [], "baja": [], "plano": []}
    for t, (nom, grupo) in AL.activos().items():
        if t.endswith("=F") or t not in X["volumen"]:
            continue
        c = X["cierre"][t].dropna()
        d = AL.senal_volumen(X["volumen"][t], c, X["alto"].get(t), X["bajo"].get(t))
        esp = AL.dias_especiales(d.index, (X.get("resultados") or {}).get(t), (X.get("splits") or {}).get(t))
        h = AL.historico_volumen(d, esp, anios)
        if not h:
            continue
        cl = h["clases"]
        filas.append((t, h))
        for k in tot:
            tot[k].append(cl[k]["n"])
    print(f"| Activo | desde | alertas (≈/año) | sube: n · 1 s · 5 s · 20 s | baja: n · 1 s · 5 s · 20 s | plano: n · 20 s | cualquier día 20 s |")
    print("|---|---|---|---|---|---|---|")
    for t, h in filas:
        cl, b = h["clases"], h["base"]

        def ms(c, k):
            x = cl[c][k]
            return f"{_f(x['media'])} ± {_f(x['sd'], 1).lstrip('+')}" if x["media"] is not None and x["sd"] is not None else "—"
        print(f"| {t} | {h['desde'][:7]} | {h['n']} ({h['n'] / h['anios']:.1f}) | {cl['sube']['n']} · {_f(cl['sube'][1]['media'])} · "
              f"{_f(cl['sube'][5]['media'])} · {ms('sube', 20)} | {cl['baja']['n']} · {_f(cl['baja'][1]['media'])} · "
              f"{_f(cl['baja'][5]['media'])} · {ms('baja', 20)} | {cl['plano']['n']} · {ms('plano', 20)} | "
              f"{_f(b[20]['media'])} ± {_f(b[20]['sd']).lstrip('+')} |")
    print(f"\nTotal: sube {sum(tot['sube'])}, baja {sum(tot['baja'])}, plano {sum(tot['plano'])} alertas en {len(filas)} activos.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anios", type=int, default=10)
    main(ap.parse_args().anios)
