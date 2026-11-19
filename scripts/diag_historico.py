"""Prueba en histórico de los disparadores de diagnósticos (docs/panel/diagnosticos_v0.md §6.1): cuántos eventos
habrían saltado por semana y por tipo desde 2022-01 con los umbrales APROBADOS (no se cambian aquí).

Solo lectura (precios del archivo, warehouse). Flujos: se reutiliza src/report/alertas.py ampliando su ventana a los
años de la prueba (las fuentes de Form 4 / 13F / recompras solo cubren lo que el archivo tenga).
Uso: .venv/bin/python -m scripts.diag_historico [--desde 2022-01-01] [--json SALIDA]
"""
from __future__ import annotations

import argparse
import json
from datetime import date

import pandas as pd

from src.diag import disparadores as D


def eventos_flujos_historicos(desde: pd.Timestamp) -> tuple[list[dict], str | None]:
    try:
        from src.report import alertas as AL
        meses = int((pd.Timestamp(date.today()) - desde).days / 30) + 2
        viejo = AL.MESES_FICHA
        AL.MESES_FICHA = meses
        try:
            R = AL.calcular(AL.cargar())
        finally:
            AL.MESES_FICHA = viejo
        return R["eventos"], None
    except Exception as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {e}"


def resumen(ev: list[dict], desde: pd.Timestamp, hasta: pd.Timestamp) -> dict:
    sem = pd.date_range(desde - pd.Timedelta(days=desde.weekday()), hasta, freq="W-MON")
    n_sem = len(sem)
    nuevos = [e for e in ev if e["nuevo"]]
    con_nota = [e for e in ev if e.get("nota")]
    por_tipo = {}
    for t in D.TIPOS:
        dias = [e for e in nuevos if any(d["tipo"] == t and not d["repetido"] for d in e["disparos"])]
        por_tipo[t] = {"eventos": len(dias), "por_semana": round(len(dias) / n_sem, 2),
                       "solo_este_tipo": sum(1 for e in dias if {d["tipo"] for d in e["disparos"] if not d["repetido"]} == {t})}
    cuenta = pd.Series(1, index=pd.DatetimeIndex([e["fecha"] for e in nuevos])).resample("W-SUN").sum() \
        .reindex(pd.date_range(desde, hasta, freq="W-SUN"), fill_value=0) if nuevos else pd.Series(dtype=int)
    por_anio = {}
    for e in nuevos:
        por_anio[e["fecha"].year] = por_anio.get(e["fecha"].year, 0) + 1
    return {"desde": str(desde.date()), "hasta": str(hasta.date()), "semanas": n_sem,
            "eventos_nuevos": len(nuevos), "media_semana": round(len(nuevos) / n_sem, 2),
            "actualizaciones": len(ev) - len(nuevos), "con_nota_tras_tope": len(con_nota),
            "notas_media_semana": round(len(con_nota) / n_sem, 2),
            "semanas_sin_evento": int((cuenta == 0).sum()) if len(cuenta) else n_sem,
            "semanas_mas_de_3": int((cuenta > 3).sum()) if len(cuenta) else 0,
            "max_semana": int(cuenta.max()) if len(cuenta) else 0,
            "por_tipo": por_tipo, "por_anio": por_anio}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2022-01-01")
    ap.add_argument("--json", default=None)
    ap.add_argument("--sin-flujos", action="store_true")
    a = ap.parse_args(argv)
    desde = pd.Timestamp(a.desde)
    X = D.cargar()
    fl, err = ([], "omitido") if a.sin_flujos else eventos_flujos_historicos(desde)
    ds = D.todos(X, fl)
    cal = D.calendario(X)
    hasta = cal[cal <= pd.Timestamp(date.today())][-1]
    # enfriamiento con historia previa; se cuenta desde `desde`
    ev = [e for e in D.aplicar_tope(D.agrupar(ds, cal)) if desde <= e["fecha"] <= hasta]
    R = resumen(ev, desde, hasta)
    R["errores_carga"] = X["errores"] | ({"flujos": err} if err else {})
    R["sustitutos"] = {c: n for c, _, _, _, _, n in D.REFERENCIA} | D.OMITIDOS
    R["ultimos"] = [{"fecha": str(e["fecha"].date()), "nuevo": e["nuevo"], "nota": e["nota"],
                     "disparos": [d["texto"] + (" (repetido)" if d["repetido"] else "") for d in e["disparos"]]}
                    for e in ev[-15:]]
    txt = json.dumps(R, ensure_ascii=False, indent=1)
    print(txt)
    if a.json:
        open(a.json, "w").write(txt)


if __name__ == "__main__":
    main()
