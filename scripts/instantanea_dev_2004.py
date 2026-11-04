"""Instantánea fechada e inmutable de las series de desarrollo ≤ 2004 con las que se congelaron las referencias de INT-8b
(research/int/int8b_referencias.json, 30-oct) y del termómetro (research/int/termometro_referencias.json, 29-oct).

Por qué: la OCDE revisó en origen series ≤ 2004 en la ingesta semanal del 2-nov (tipo a 10 años de BEL, producción
industrial de GBR/ITA/BEL/ESP/FIN/FRA/SWE, paro de IRL/ITA, ventas de DNK/GBR) y `raw/oecd` se sobrescribía: no queda
ninguna descarga anterior. Lo único que queda de antes es la caché del panel mensual de desarrollo del 26-oct
($FIN_DATA_ROOT/intl/panel_mensual_dev.parquet = src/intl/panel.mensual con los datos de entonces).

Cómo (declarado; docs/int/INT8b_nowcast.md, «Revisiones de datos»):
1. Se parte de `obs_latest` del warehouse de hoy, ≤ 2004, para todas las series que leen src/intl/panel.mensual, la
   carga en vivo de INT-8b y del termómetro (OCDE mensual y PIB trimestral, BIS, AQR, JST eq_dp, USREC).
2. Se recalcula panel.mensual con ellas y se compara con la caché columna a columna y país a país (|Δ| > 1e-12): las
   series cuyas transformaciones difieren son las revisadas.
3. Solo en esas, se reconstruye el valor previo a la revisión invirtiendo la caché:
   - niveles con retraso (tipos, paro): valor del mes m = columna de la caché en el primer fin de mes ≥ disponible(m);
     el último mes de 2004 del tipo a 10 años, que aún no era «conocido» al cierre de 2004, sale de `r_bono` (sin
     retraso) resolviendo la ecuación de duración y convexidad de src/intl/returns.py y redondeando a los decimales
     (2, 3 o 4) con los que `r_bono` se reproduce exactamente;
   - índices usados solo en interanual (producción industrial, ventas): log nivel(m) = log nivel(m − 12) + interanual
     de la caché; donde la interanual no cambia, el nivel de hoy tal cual.
   Lo que la caché no ve (paro interpolado antes de 1998 de los 9 países excluidos, los últimos meses de 2004 de las
   series con retraso, el nivel —no la interanual— de la IP) se queda con el valor de hoy (en los índices, con la
   interanual de hoy encadenada, para no fabricar saltos) y se cuenta en el manifiesto.
4. Comprobaciones (si alguna falla, no se escribe nada): panel.mensual con la instantánea = caché en TODAS las columnas
   (|Δ| ≤ 1e-12); referencias de INT-8b y del termómetro recalculadas con la instantánea (carga en vivo de
   src/report con corte 2004-12) = congeladas, con la tolerancia de los tests (1e-12 en distribuciones; 1e-9 en índice
   y agregado de INT-8b).
5. Se escribe el parquet en $FIN_DATA_ROOT/intl/snapshots/ (solo lectura; nunca se sobrescribe) y el manifiesto
   research/int/instantanea_dev_2004.json (ruta, sha256, fecha, procedencia, series reconstruidas).

Run: .venv/bin/python scripts/instantanea_dev_2004.py [--forzar-manifiesto]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import stat
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.intl import data as D  # noqa: E402
from src.intl import int8b as K  # noqa: E402
from src.intl import lags as Lg  # noqa: E402
from src.intl import panel as P  # noqa: E402
from src.intl import returns as R  # noqa: E402
from src.intl import termometro as T  # noqa: E402
from src.report import nowcast_vivo as NV  # noqa: E402
from src.report import termometro_vivo as V  # noqa: E402
from src.warehouse import db  # noqa: E402

FECHA = "2026-10-26"                                   # fecha de los datos (la de la caché)
CACHE = db.DATA_ROOT / "intl" / "panel_mensual_dev.parquet"
RUTA = f"intl/snapshots/dev_le2004_{FECHA.replace('-', '')}.parquet"     # relativa a $FIN_DATA_ROOT
TOL = 1e-12

# columna de la caché → (plantilla del series_id, tipo de inversión)
COLUMNAS = {"tipo_10a": ("oecd_irlt_{lc}", "nivel"), "tipo_3m": ("oecd_ir3m_{lc}", "nivel"),
            "paro": ("oecd_unemp_{lc}", "nivel"), "tipo_oficial": ("bis_cbpol_{i2}", "nivel"),
            "cli": ("oecd_cli_{lc}", "nivel"), "confianza_emp": ("oecd_bci_{lc}", "nivel"),
            "ip_yoy": ("oecd_ip_{lc}", "log12"), "ventas_yoy": ("oecd_retail_{lc}", "log12"),
            "ipc_yoy": ("oecd_cpi_{lc}_idx", "log12"), "sub_yoy": ("oecd_cpicore_{lc}_idx", "log12"),
            "bolsa_12m": ("oecd_share_{lc}", "log12"), "r_aqr_mkt_usd": ("aqr_mkt_{lc}_m", None)}
# columnas derivadas de otras (no identifican serie por sí solas)
DERIVADAS = {"curva", "paro_d12", "ipc_6m_anual", "cli_d6", "r_bolsa_precio", "r_bolsa_tr", "r_bono", "r_letra",
             "inflacion_mes"}


def series_ids() -> list[str]:
    out = ["USREC"]
    for c in D.PAISES:
        lc, i2 = c.lower(), D.ISO2[c]
        out += [f"oecd_{m}_{lc}" for m in ("ip", "retail", "unemp", "irlt", "ir3m", "share", "cli", "bci", "gdpq")]
        out += [f"oecd_cpi_{lc}_idx", f"oecd_cpicore_{lc}_idx", f"bis_cbpol_{i2}", f"jst_{lc}_eq_dp", f"aqr_mkt_{lc}_m",
                f"bis_creditgap_{i2}_ratio"]
    return out


def leer_hoy() -> pd.DataFrame:
    con = db.connect(read_only=True)
    try:
        df = con.execute("select series_id, date, value from obs_latest where value is not null and date <= ? and "
                         "series_id in (select unnest(?))", [D.DEV_END.date(), series_ids()]).df()
    finally:
        con.close()
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["series_id", "date"]).reset_index(drop=True)


def con_de(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest as select series_id, cast(date as date) as date, value from df")
    return con


def diferencias(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    """{(columna, país): nº de meses con |Δ| > TOL o NaN distinto}."""
    b = b.reindex(a.index)
    out = {}
    for col in a.columns:
        if col == "pais":
            continue
        x, y = a[col].astype(float), b[col].astype(float)
        mal = ((x - y).abs() > TOL) | (x.isna() != y.isna())
        for c, n in mal.groupby(level=0).sum().items():
            if n:
                out[(col, c)] = int(n)
    return out


def _t_conocido(idx: pd.DatetimeIndex, sid: str, rej: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Primer fin de mes ≥ disponible(m) si está en la rejilla de la caché (NaT si cae antes o después: la caché no ve
    ese valor; antes de 1950 el primer fin de mes de la rejilla muestra solo el último dato ya disponible)."""
    t = Lg.disponible(idx, sid).normalize() + pd.offsets.MonthEnd(0)
    return pd.DatetimeIndex([x if x in rej else pd.NaT for x in t])


def reconstruir_nivel(s: pd.Series, col: pd.Series, sid: str, rej) -> tuple[pd.Series, int, int]:
    t = _t_conocido(s.index, sid, rej)
    v = col.reindex(t).to_numpy()
    ok = np.isfinite(v)
    nuevo = s.copy()
    nuevo[ok] = v[ok]
    return nuevo, int((nuevo != s).sum()), int((~ok).sum())


def bono_ultimo(s: pd.Series, r_bono: pd.Series) -> pd.Series:
    """Tipo a 10 años de los meses aún no «conocidos» al cierre de 2004, desde la rentabilidad del bono (sin retraso)."""
    s = s.copy()
    for m in s.index[s.index > D.DEV_END - pd.offsets.MonthBegin(2)]:
        prev = m - pd.offsets.MonthBegin(1)
        r = r_bono.get(m + pd.offsets.MonthEnd(0), np.nan)
        if prev not in s.index or not np.isfinite(r):
            continue
        y0 = s[prev] / 100
        d, c = (x[0] for x in R.duracion_convexidad(np.array([y0])))
        disc = d * d - 2 * c * (y0 / 12 - r)
        dy = (d - np.sqrt(disc)) / c
        for dec in (2, 3, 4):        # la OCDE publica 2 o 3 decimales: el redondeo que reproduce r_bono exactamente
            y = round((y0 + dy) * 100, dec)
            dy_ = y / 100 - y0
            if abs(y0 / 12 - d * dy_ + 0.5 * c * dy_ ** 2 - r) <= TOL:
                s[m] = y
                break
        else:
            raise SystemExit(f"{s.name} {m:%Y-%m}: r_bono no se reproduce con 2-4 decimales")
    return s


def reconstruir_log12(s: pd.Series, col: pd.Series, sid: str, rej) -> tuple[pd.Series, int, int]:
    """Niveles cuya interanual en log (sobre la rejilla mensual completa) = la de la caché donde la caché la ve."""
    g = P._mensual_completa(s)
    t = _t_conocido(g.index, sid, rej)
    yo = pd.Series(col.reindex(t).to_numpy(), index=g.index)
    lg_hoy = np.log(g)
    yo_hoy = lg_hoy.diff(12)
    nuevo = lg_hoy.copy()
    sin_ver = 0
    for i, m in enumerate(g.index):
        if not np.isfinite(lg_hoy.iloc[i]):
            continue
        y = yo.iloc[i]
        if np.isfinite(yo_hoy.iloc[i]) and not np.isfinite(y):
            sin_ver += 1
            y = yo_hoy.iloc[i]          # la caché no lo ve: la interanual de hoy (no el nivel de hoy)
        if i < 12 or not np.isfinite(y) or not np.isfinite(nuevo.iloc[i - 12]):
            continue
        if nuevo.iloc[i - 12] == lg_hoy.iloc[i - 12] and abs(yo_hoy.iloc[i] - y) <= TOL:
            continue
        nuevo.iloc[i] = nuevo.iloc[i - 12] + y
    out = np.exp(nuevo).reindex(s.index)
    out[nuevo.reindex(s.index) == lg_hoy.reindex(s.index)] = s      # sin tocar: exactamente el valor de hoy
    return out, int((out != s).sum()), int(sin_ver)


def refs_int8b(con) -> tuple[dict, list]:
    pm, bis, pib, paro, _ = NV.cargar(con, "2004-12-31")
    rec = K.referencias(K.componentes(pm, bis, pib, paro, NV.NUCLEO, NV.TODOS), NV.NUCLEO, NV.TODOS)
    cong, mal = NV.referencias_congeladas(), []
    dmax = 0.0
    for k in K.CLAVES:
        for c in NV.TODOS:
            a, b = rec["indicadores"][k][c], cong["indicadores"][k][c]
            if len(a) != len(b) or not np.allclose(a, b, rtol=0, atol=1e-12):
                mal.append(f"INT-8b {k} {c}")
            elif len(a):
                dmax = max(dmax, float(np.max(np.abs(np.subtract(a, b)))))
    for c in NV.TODOS:
        if len(rec["indice"][c]) != len(cong["indice"][c]) or not np.allclose(rec["indice"][c], cong["indice"][c], rtol=0, atol=1e-9):
            mal.append(f"INT-8b índice {c}")
    if not np.allclose(rec["agregado"], cong["agregado"], rtol=0, atol=1e-9):
        mal.append("INT-8b agregado")
    return {"dif_max_distribuciones": dmax}, mal


def refs_termometro(con) -> tuple[dict, list]:
    pm, bis, pib, _ = V.cargar(con, "2004-12-31")
    par = V.parametros()
    mens = T.mensuales(pm, bis, pib, V.NUCLEO, V.TODOS)
    rec = V.referencias(mens, T.traducir(mens, par["rectas"], V.TODOS), pib, par)
    cong, mal, dmax = V.referencias_congeladas(), [], 0.0
    if rec["meses_centro"] != cong["meses_centro"] or not np.allclose(rec["centro_T2"], cong["centro_T2"], rtol=0, atol=1e-12):
        mal.append("termómetro centro_T2")
    for k, *_ in V.INDICADORES:
        for c in V.TODOS:
            a, b = rec["indicadores"][k][c], cong["indicadores"][k][c]
            if len(a) != len(b) or not np.allclose(a, b, rtol=0, atol=1e-12):
                mal.append(f"termómetro {k} {c}")
            elif len(a):
                dmax = max(dmax, float(np.max(np.abs(np.subtract(a, b)))))
    return {"dif_max_distribuciones": dmax}, mal


def main() -> None:
    destino = db.DATA_ROOT / RUTA
    if destino.exists():
        sys.exit(f"{destino} ya existe: la instantánea es inmutable (no se sobrescribe).")
    cache = pd.read_parquet(CACHE)
    hoy = leer_hoy()
    con = con_de(hoy)
    pm_hoy = P.mensual(con)
    con.close()
    dif = diferencias(pm_hoy, cache)
    print("columnas que difieren con la caché:", dif)
    rej = pm_hoy.index.get_level_values("fecha").unique()
    revisadas, sin_ver = {}, {}
    nuevo = {sid: g.set_index("date")["value"] for sid, g in hoy.groupby("series_id")}
    for col, c in sorted({k for k in dif if k[0] not in DERIVADAS}):
        plantilla, tipo = COLUMNAS[col]
        sid = plantilla.format(lc=c.lower(), i2=D.ISO2[c])
        if tipo is None:
            raise SystemExit(f"{col} {c}: serie revisada sin inversión declarada")
        f = reconstruir_nivel if tipo == "nivel" else reconstruir_log12
        s, n, nv = f(nuevo[sid], cache[col].xs(c), sid, rej)
        if sid.startswith("oecd_irlt_"):
            s = bono_ultimo(s, cache["r_bono"].xs(c))
            n = int((s != nuevo[sid]).sum())
        nuevo[sid] = s
        revisadas[sid] = {"columna_cache": col, "inversion": tipo, "valores_restaurados": n}
        sin_ver[sid] = nv
    # derivadas que difieren sin que su columna base difiera (p. ej. r_bono por el último mes): comprobación final
    inst = pd.concat([pd.DataFrame({"series_id": sid, "date": s.index, "value": s.to_numpy()}) for sid, s in nuevo.items()],
                     ignore_index=True).sort_values(["series_id", "date"]).reset_index(drop=True)
    con = con_de(inst)
    resto = diferencias(P.mensual(con), cache)
    if resto:
        raise SystemExit(f"la instantánea NO reproduce la caché: {resto}")
    i8, mal8 = refs_int8b(con)
    te, malt = refs_termometro(con)
    con.close()
    if mal8 or malt:
        raise SystemExit(f"la instantánea NO reproduce las referencias congeladas: {mal8 + malt}")
    print("reproduce la caché (todas las columnas, |Δ| ≤ 1e-12) y las referencias congeladas de INT-8b y del termómetro")
    destino.parent.mkdir(parents=True, exist_ok=True)
    inst["date"] = inst["date"].dt.date
    inst.to_parquet(destino, index=False)
    os.chmod(destino, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)        # solo lectura
    man = {
        "descripcion": "Instantánea fechada e inmutable de las series de desarrollo ≤ 2004 (OCDE y resto de entradas de "
                       "src/intl/panel.mensual, de la carga en vivo de INT-8b y del termómetro) con los valores PREVIOS "
                       "a la revisión en origen de la OCDE de la ingesta semanal del 2-nov. La leen "
                       "src/intl/data.connect(fuente='instantanea') y los tests de reproducción.",
        "ruta": RUTA, "raiz": "$FIN_DATA_ROOT", "sha256": D.sha256(destino), "bytes": destino.stat().st_size,
        "fecha_datos": FECHA, "creada": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "hasta": str(D.DEV_END.date()), "series": int(inst.series_id.nunique()), "filas": int(len(inst)),
        "cobertura": series_ids(),      # pedidas (las que no tienen datos ≤ 2004 salen vacías, como en el warehouse)
        "procedencia": {
            "cache": {"ruta": str(CACHE.relative_to(db.DATA_ROOT)), "sha256": D.sha256(CACHE),
                      "modificada": dt.datetime.fromtimestamp(CACHE.stat().st_mtime).isoformat(timespec="seconds"),
                      "que_es": "src/intl/panel.mensual con los datos del 26-oct (antes de la revisión del 2-nov)"},
            "warehouse": {"build_log": _build_log(), "uso": "valores ≤ 2004 de las series no revisadas y de lo que la "
                          "caché no ve"},
            "script": "scripts/instantanea_dev_2004.py",
            "series_revisadas_restauradas": revisadas,
            "valores_no_visibles_en_cache_por_serie_revisada": sin_ver,
            "no_visible_en_cache": ["paro interpolado antes de 1998 de los 9 países de src/intl/panel.PARO_INTERPOLADO "
                                    "(no se usa en desarrollo)", "últimos meses de 2004 de las series con retraso (no "
                                    "conocidos al cierre de 2004; salvo el tipo a 10 años, restaurado con r_bono)",
                                    "nivel de la producción industrial y de las ventas (solo se usa su interanual; el "
                                    "nivel se ancla en el de hoy)", "PIB trimestral y crédito/PIB del BIS (no están en "
                                    "la caché; verificados por la reproducción exacta de las referencias)"]},
        "comprobaciones": {"panel_mensual_igual_a_cache": "todas las columnas, |Δ| ≤ 1e-12",
                           "int8b_referencias": {"archivo": "research/int/int8b_referencias.json", **i8,
                                                 "tolerancia": "1e-12 distribuciones; 1e-9 índice y agregado"},
                           "termometro_referencias": {"archivo": "research/int/termometro_referencias.json", **te,
                                                      "tolerancia": "1e-12"}},
    }
    D.INSTANTANEA.write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n")
    print(f"escrita {destino} ({man['sha256']}) y {D.INSTANTANEA.relative_to(db.REPO)}")


def _build_log() -> str | None:
    con = db.connect(read_only=True)
    try:
        r = con.execute("select * from build_log").df()
        return None if r.empty else str(r.iloc[-1].get("built_at"))
    finally:
        con.close()


if __name__ == "__main__":
    main()
