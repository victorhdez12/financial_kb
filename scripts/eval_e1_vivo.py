"""Evaluación (CONGELADA antes de que exista ningún realizado) del registro en vivo de P-E1 (12 meses) y P-E1b (6 meses).

Prerregistros: docs/int/E1_prerregistro_v1.md (§5 métrica, §7 criterios, §8 placebos, M4, §11 decisiones) con
docs/int/E1_enmienda_1.md, y docs/int/E1b_6m_prerregistro_v1.md. Ambigüedades resueltas: docs/int/EVAL_registros_vivo.md.

Qué hace:
- Lee `research/int/e1_vivo.jsonl` (scripts/e1_vivo.py) y se queda con los orígenes con la ventana CERRADA por
  calendario (fin del trimestre que contiene M + h + 75 días de retraso del PIB ≤ hoy). Si no hay ninguno: imprime
  "sin ventanas cerradas", NO conecta al warehouse y NO escribe nada.
- Objetivo realizado: fechado trimestral del termómetro sobre el PIB OCDE (`oecd_gdpq_*`, última añada; el PIB revisado
  a propósito, §2) con `src/intl/int13.entradas_recesion` + `objetivo_e1` (idéntico a INT-13 / al ajuste).
- Métricas con las funciones de `src/intl/e1.py` (coeficientes congelados, sin reajuste): ΔAUC (principal), Δlog-loss,
  ΔBrier, calibración de A, P1 (p del contraste), P2, P3, M4, ΔAUC por episodio y AUC frente a 0,5.
- Episodios nuevos: entradas posteriores al primer origen (2026-11-30) agrupadas entre países (≤ 6 meses = mismo
  episodio, la definición de scripts/e1_potencia.py). Con < 12 episodios: solo DESCRIPTIVO, sin veredicto. Con ≥ 12:
  veredicto de §7 una sola vez (se niega si el fichero de veredicto ya existe).

Uso: .venv/bin/python -m scripts.eval_e1_vivo [--sintetico] [--hoy AAAA-MM-DD]
Salidas (solo modo real con ventanas cerradas; árbol limpio): research/int/eval_e1_vivo.json (revisión descriptiva,
se reescribe) y research/int/eval_e1_vivo_veredicto_{12,6}m.json (una vez).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import e1 as E
from src.intl import int4 as M4
from src.intl import int13 as M13

REPO = Path(__file__).resolve().parents[1]
LOG = REPO / "research/int/e1_vivo.jsonl"
MODELOS = {12: REPO / "research/int/e1_modelos.json", 6: REPO / "research/int/e1_6_modelos.json"}
SALIDA = REPO / "research/int/eval_e1_vivo.json"
VEREDICTO = {h: REPO / f"research/int/eval_e1_vivo_veredicto_{h}m.json" for h in (12, 6)}

# por horizonte: columna y del modelo congelado, columnas p registradas, clave del sha256 en el registro, horizonte de M4
CFG = {12: {"y": "y_E1_12", "pL": "p_L", "pA": "p_A", "sha": "modelos_sha256", "m4": 6},
       6: {"y": "y_E1_6", "pL": "p_L6", "pA": "p_A6", "sha": "modelos6_sha256", "m4": 3}}
MIN_EPISODIOS = 12                    # §11.2 / P-E1b §4
GAP_EPISODIO = 6                      # meses; scripts/e1_potencia.episodios
RETRASO_PIB_DIAS = 75                 # src/intl/termometro.RETRASO_PIB
ALFA = 0.05
CALIB = (0.5, 1.5)
TOL_P = 1e-4                          # p recalculada con los rasgos registrados (6 decimales) frente a la registrada
# §11.7: choques exógenos futuros fuera del principal SOLO si se declaran antes de ver la predicción. Ninguno declarado.
# Formato: {"desde": "AAAA-MM-DD", "hasta": "AAAA-MM-DD", "declarado": ISO UTC, "motivo": "..."}; un origen solo se
# excluye si se REGISTRÓ después de `declarado` (resolución conservadora, EVAL_registros_vivo.md §E1-3).
CHOQUES_DECLARADOS: list[dict] = []


# ---------------------------------------------------------------- registro y calendario
def leer_registro(path: Path = LOG) -> pd.DataFrame:
    """Filas con predicción (las "sin dato" no entran). Duplicados (origen, país): vale la primera línea."""
    if not path.exists():
        return pd.DataFrame()
    d = pd.DataFrame([json.loads(x) for x in path.read_text().splitlines() if x.strip()])
    if d.empty:
        return d
    if "sin_dato" in d:
        d = d[d.sin_dato.ne(True)]
    d = d.drop_duplicates(["origen", "pais"], keep="first").copy()
    d["fecha"] = pd.to_datetime(d.origen) + pd.offsets.MonthEnd(0)
    return d.reset_index(drop=True)


def fin_ventana_pib(origen: pd.Timestamp, h: int) -> pd.Timestamp:
    """Día desde el que el PIB del trimestre que contiene M + h debería estar publicado."""
    m = (pd.Timestamp(origen) + pd.offsets.MonthEnd(h)).to_period("Q").to_timestamp(how="end").normalize()
    return m + pd.Timedelta(days=RETRASO_PIB_DIAS)


def cerrados(reg: pd.DataFrame, h: int, hoy) -> pd.DataFrame:
    if reg.empty:
        return reg
    ok = (reg.fecha >= E.PRIMER_ORIGEN) & reg.fecha.map(lambda f: fin_ventana_pib(f, h) <= pd.Timestamp(hoy))
    return reg[ok].reset_index(drop=True)


# ---------------------------------------------------------------- objetivo realizado
def objetivos(pib: dict, h: int, h_m4: int) -> pd.DataFrame:
    """(fecha, pais, y_h, y_m4, entrada) con el fechado trimestral sobre el PIB (int13: mismo objetivo que el ajuste).
    `entrada` = primer mes de entrada en (M, M + h] (para asignar episodios)."""
    out = []
    for c, p in pib.items():
        if p is None or p.dropna().empty:
            continue
        en, ent = M13.entradas_recesion(p)
        ent = ent.fillna(0.0)
        y = M13.objetivo_e1(en, ent, h)
        y4 = M13.objetivo_e1(en, ent, h_m4)
        meses_ent = ent.index[ent == 1]
        primera = [next((m for m in meses_ent if f < m <= f + pd.offsets.MonthEnd(h)), pd.NaT) for f in y.index]
        out.append(pd.DataFrame({"fecha": y.index, "pais": c, "y": y.values, "y_m4": y4.values,
                                 "entrada": primera}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["fecha", "pais", "y", "y_m4", "entrada"])


def episodios(entradas: pd.Series, gap: int = GAP_EPISODIO) -> pd.Series:
    """Entrada (mes) → nº de episodio: entradas de cualquier país a ≤ `gap` meses de la anterior = mismo episodio."""
    u = np.sort(pd.Series(entradas.dropna().unique()))
    if not len(u):
        return pd.Series(dtype=int)
    o = pd.DatetimeIndex(u).to_period("M").astype("int64")
    ide = np.cumsum(np.r_[0, np.diff(o) > gap])
    return pd.Series(ide, index=pd.DatetimeIndex(u))


def tabla(reg: pd.DataFrame, pib: dict, h: int) -> pd.DataFrame:
    c = CFG[h]
    ob = objetivos(pib, h, c["m4"]).rename(columns={"y": c["y"], "y_m4": f"y_m4_{c['m4']}"})
    d = reg.merge(ob, on=["fecha", "pais"], how="left")
    d = d[d[c["y"]].notna()].reset_index(drop=True)          # fechado cubre M y M + h, y M en riesgo
    d = d[d[E.COLS["A"]].notna().all(axis=1)].reset_index(drop=True)
    ep = episodios(d.loc[d[c["y"]] == 1, "entrada"])
    d["episodio"] = d.entrada.map(ep).where(d[c["y"]] == 1)
    if h == 12:
        d["y_E1_6"] = d[f"y_m4_{c['m4']}"]                    # e1.evaluar → M4 con la entrada en (M, M + 6]
    return d


def choques(d: pd.DataFrame, declarados: list[dict] = CHOQUES_DECLARADOS) -> pd.Series:
    fuera = pd.Series(False, index=d.index)
    reg = pd.to_datetime(d.get("registrado"), utc=True, errors="coerce") if "registrado" in d else None
    for x in declarados:
        en = d.fecha.between(pd.Timestamp(x["desde"]), pd.Timestamp(x["hasta"]))
        if reg is not None:
            en &= reg > pd.Timestamp(x["declarado"])
        fuera |= en
    return fuera


# ---------------------------------------------------------------- integridad
def comprobar(d: pd.DataFrame, mod: dict, sha: str, h: int) -> dict:
    """Modelos del registro = congelados y p recalculada con los rasgos registrados ≈ p registrada."""
    c = CFG[h]
    if c["sha"] in d and (d[c["sha"]].dropna() != sha).any():
        raise SystemExit(f"{h} m: hay filas registradas con otro sha256 de modelos")
    out = {}
    for m, col in (("L", c["pL"]), ("A", c["pA"])):
        if col in d:
            dif = np.abs(E.predecir(mod, d, m) - d[col].to_numpy(float))
            if np.nanmax(dif, initial=0) > TOL_P:
                raise SystemExit(f"{h} m: p_{m} recalculada ≠ registrada (máx {np.nanmax(dif):.2e})")
            out[f"max_dif_p_{m}"] = float(np.nanmax(dif, initial=0))
    return out


# ---------------------------------------------------------------- evaluación
def _f(x):
    if isinstance(x, dict):
        return {k: _f(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_f(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 6)
    if isinstance(x, np.integer):
        return int(x)
    return x


def por_episodio(mod: dict, d: pd.DataFrame, y: str) -> dict:
    """ΔAUC de cada episodio (sus positivos frente a todos los negativos) y ΔAUC quitando sus positivos."""
    out = {}
    neg = d[d[y] == 0]
    for e, g in d[d[y] == 1].groupby("episodio"):
        ini = g.entrada.min()
        out[int(e)] = {"desde": str(ini.date())[:7], "eventos": int(len(g)), "paises": int(g.pais.nunique()),
                       "dauc": E._delta(mod, pd.concat([neg, g]))["dauc"],
                       "dauc_sin_el": E._delta(mod, d[~((d[y] == 1) & (d.episodio == e))])["dauc"]}
    return out


def veredicto(r: dict) -> dict:
    """§7 (muestra principal). Antes de MIN_EPISODIOS: sin veredicto."""
    p = r["principal"]
    if r["episodios_nuevos"] < MIN_EPISODIOS:
        return {"veredicto": "DESCRIPTIVO (sin veredicto)",
                "motivo": f"{r['episodios_nuevos']} episodios nuevos < {MIN_EPISODIOS}"}
    eps = sorted(r["por_episodio"].values(), key=lambda v: -v["eventos"])
    iv = (len(eps) >= 2 and all(v["dauc"] > 0 for v in eps[:2]) and all(v["dauc_sin_el"] > 0 for v in eps))
    c = {"i_dauc_pos_p1": bool(p["dauc"] > 0 and r["p1"]["p"] < ALFA), "ii_dlogloss_neg": bool(p["dlogloss"] < 0),
         "iii_pendiente_calib": bool(CALIB[0] <= p["calib_A"]["pendiente"] <= CALIB[1]),
         "iv_dos_mayores_episodios_y_sin_cada_uno": bool(iv)}
    if p["dauc"] <= 0 or p["dlogloss"] >= 0:
        v = "REFUTADO"
    elif all(c.values()):
        v = "CONFIRMADO"
    else:
        v = "NI REFUTADO NI CONFIRMADO (no contradicho; sin potencia para confirmar)"
    return {"veredicto": v, "criterios": c}


def evaluar_h(reg: pd.DataFrame, pib: dict, mod: dict, sha: str, h: int) -> dict:
    c = CFG[h]
    d = tabla(reg, pib, h)
    out = {"horizonte_meses": h, "filas": int(len(d)), "eventos": int(d[c["y"]].sum()) if len(d) else 0,
           "origenes": [str(d.fecha.min().date()), str(d.fecha.max().date())] if len(d) else None}
    if d.empty or d[c["y"]].nunique() < 2:
        out["episodios_nuevos"] = int(d.episodio.nunique()) if len(d) else 0
        out["nota"] = "sin las dos clases en la muestra cerrada: nada que medir"
        out.update(veredicto_fijo(out))
        return out
    out["integridad"] = comprobar(d, mod, sha, h)
    fuera = choques(d)
    base = d[~fuera].reset_index(drop=True)
    out["choques_excluidos_filas"] = int(fuera.sum())
    out["episodios_nuevos"] = int(base.loc[base[c["y"]] == 1, "episodio"].nunique())
    r = E.evaluar(mod, base, sin_2020=False)
    out.update(r)
    if h == 6:
        out["m4"] = E.m4_anticipacion(mod, base, base[f"y_m4_{c['m4']}"])
    yb = base[c["y"]].to_numpy(float)
    out["auc_registrada"] = {"A": M4.auc(yb, base[c["pA"]].to_numpy(float)),
                             "L": M4.auc(yb, base[c["pL"]].to_numpy(float))}
    out["por_episodio"] = por_episodio(mod, base, c["y"])
    if fuera.any():
        out["con_choques"] = E._delta(mod, d)
    out.update(veredicto(out))
    return out


def veredicto_fijo(r: dict) -> dict:
    return {"veredicto": "DESCRIPTIVO (sin veredicto)", "motivo": f"{r.get('episodios_nuevos', 0)} episodios nuevos"}


def modelos() -> dict:
    out = {}
    for h, p in MODELOS.items():
        j = json.loads(p.read_text())
        if E.sha(j["modelos"]) != j["modelos_sha256"]:
            raise SystemExit(f"{p.name}: sha256 de los modelos no coincide")
        out[h] = (j["modelos"], j["modelos_sha256"])
    return out


def evaluar_todo(reg: pd.DataFrame, pib: dict, hoy) -> dict:
    mods = modelos()
    return {f"E1_{h}": evaluar_h(cerrados(reg, h, hoy), pib, *mods[h], h) for h in (12, 6)}


# ---------------------------------------------------------------- sintético (P4 del prerregistro)
def sintetico(semilla: int = 20261105, señal: float = 1.0, años: int = 36, n_ep: int = 14,
              desde: str = "2030-01-31") -> tuple[pd.DataFrame, dict, pd.Timestamp]:
    """Registro inventado (16 países, orígenes mensuales) + PIB inventado con `n_ep` episodios de recesión (≈ 50 % de
    los países, entradas ± 4 meses). Con `señal` > 0 la actividad (IP, confianza) cae `señal` dt en los 12 meses previos
    a cada entrada; la curva no lleva información. Las p se calculan con los modelos CONGELADOS (como el registro)."""
    rng = np.random.default_rng(semilla)
    mods = modelos()
    paises = E.PAISES
    ini = pd.Timestamp(desde)
    meses = pd.date_range(ini, periods=años * 12, freq="ME")
    qs = pd.period_range((ini - pd.DateOffset(years=4)).to_period("Q"), (meses[-1] + pd.DateOffset(years=2)).to_period("Q"),
                         freq="Q")
    centros = np.sort(rng.choice(np.arange(12, len(meses) - 24, 24), n_ep, replace=False))   # ≥ 24 meses entre episodios
    pib = {}
    for c in paises:
        g = 0.005 + 0.002 * rng.standard_normal(len(qs))
        for ce in centros:
            if rng.random() < 0.5:
                q = (meses[min(len(meses) - 1, max(0, ce + int(rng.integers(-4, 5))))]).to_period("Q")
                s = qs.get_loc(q)
                g[s - 1:s + 1] = -0.02
                g[s + 1] = -0.005
                g[s + 2:s + 5] = 0.012
        lvl = 100 * np.exp(np.cumsum(g))
        pib[c] = pd.Series(lvl, index=qs.to_timestamp(how="start"))
    m12, _ = mods[12]
    mu, sd = np.array(m12["A"]["media"]), np.array(m12["A"]["dt"])
    filas = []
    for c in paises:
        en, ent = M13.entradas_recesion(pib[c])
        y12 = M13.objetivo_e1(en, ent.fillna(0.0), 12).reindex(meses)
        z = np.zeros((len(meses), 4))
        e = rng.standard_normal((len(meses), 4))
        for t in range(len(meses)):
            z[t] = (0.9 * z[t - 1] if t else 0) + np.sqrt(1 - 0.81) * e[t]
        x = mu + sd * z
        plant = (y12 == 1).to_numpy()
        x[plant, 2] -= señal * sd[2]
        x[plant, 3] -= señal * sd[3]
        for t, f in enumerate(meses):
            filas.append({"origen": str(f.date()), "pais": c, **dict(zip(E.COLS["A"], np.round(x[t], 6))),
                          "registrado": (f + pd.Timedelta(days=3)).isoformat() + "+00:00"})
    reg = pd.DataFrame(filas)
    reg["fecha"] = pd.to_datetime(reg.origen)
    for h, (pl, pa) in ((12, ("p_L", "p_A")), (6, ("p_L6", "p_A6"))):
        m, s = mods[h]
        reg[pl], reg[pa] = np.round(E.predecir(m, reg, "L"), 6), np.round(E.predecir(m, reg, "A"), 6)
        reg[CFG[h]["sha"]] = s
    hoy = meses[-1] + pd.DateOffset(years=2)
    return reg, pib, hoy


def resumen(r: dict) -> str:
    lin = []
    for k, v in r.items():
        p = v.get("principal", {})
        lin.append(f"{k}: filas {v['filas']}, eventos {v['eventos']}, episodios nuevos {v.get('episodios_nuevos')}, "
                   f"ΔAUC {p.get('dauc', float('nan')):+.3f}, Δlog-loss {p.get('dlogloss', float('nan')):+.4f}, "
                   f"p P1 {v.get('p1', {}).get('p', float('nan')):.3f} → {v['veredicto']}")
    return "\n".join(lin)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sintetico", action="store_true")
    ap.add_argument("--hoy")
    a = ap.parse_args(argv)
    if a.sintetico:
        ok = True
        for nom, s in (("con señal", 1.0), ("sin señal", 0.0)):
            reg, pib, hoy = sintetico(señal=s)
            r = evaluar_todo(reg, pib, hoy)
            print(f"[sintético {nom}]\n{resumen(r)}")
            v = r["E1_12"]
            if s > 0:
                ok &= v["principal"]["dauc"] > 0 and v["p1"]["p"] < ALFA
            else:
                ok &= v["p1"]["p"] >= ALFA and v["veredicto"] != "CONFIRMADO"
        print("P4 sintético:", "OK" if ok else "FALLA")
        return 0 if ok else 1
    hoy = pd.Timestamp(a.hoy) if a.hoy else pd.Timestamp.today().normalize()
    reg = leer_registro()
    abiertos = {h: cerrados(reg, h, hoy) for h in (12, 6)}
    if all(x.empty for x in abiertos.values()):
        n = 0 if reg.empty else reg.origen.nunique()
        print(f"E1/E1b: sin ventanas cerradas a {hoy.date()} ({n} orígenes registrados); no se lee el PIB ni se escribe nada")
        return 0
    from src.intl.procedencia import procedencia
    from src.report import termometro_vivo as V
    from src.warehouse import db
    proc = procedencia(exigir_limpio=True)
    con = db.connect(read_only=True)
    try:
        construido = str(con.execute("select built_at from build_log").fetchone()[0])
        pib = {c: V._serie(con, f"oecd_gdpq_{c.lower()}", hoy) for c in E.PAISES}
    finally:
        con.close()
    r = evaluar_todo(reg, pib, hoy)
    print(resumen(r))
    out = {"procedencia": proc, "hoy": str(hoy.date()), "warehouse": construido, "documentos": [
        "docs/int/E1_prerregistro_v1.md", "docs/int/E1_enmienda_1.md", "docs/int/E1b_6m_prerregistro_v1.md",
        "docs/int/EVAL_registros_vivo.md"], "resultados": _f(r)}
    for h in (12, 6):
        v = r[f"E1_{h}"]
        if v.get("episodios_nuevos", 0) >= MIN_EPISODIOS:
            if VEREDICTO[h].exists():
                print(f"{VEREDICTO[h].name} ya existe: el veredicto es único (no se reescribe)")
            else:
                VEREDICTO[h].write_text(json.dumps({**out, "resultados": _f(v)}, ensure_ascii=False, indent=1))
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"escrito {SALIDA.relative_to(REPO)} (descriptivo salvo veredicto)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
