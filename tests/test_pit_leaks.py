"""Tests de la base point-in-time v0.3 (docs/models/pit_base.md §5). Corren sobre la INSTANTÁNEA CONGELADA de entradas.

(h) hashes: la instantánea, la lista blanca y el calendario coinciden con FROZEN; una copia alterada se rechaza; la
    matriz oficial se reproduce bit a bit;
(a) ninguna celda usa un dato publicado después de t (recalculado desde `observations`, sin src.features.calendar);
(v) valores: celdas recalculadas a mano con SQL, sin src.features; retardos y proxies verificados con vintages ALFRED
    (fuente distinta del yaml);
(b) truncamiento: con las entradas truncadas en t, la fila t es idéntica (variables y persistencia);
(c) placebo del walk-forward (src/features/placebo.py): con la etiqueta ≤ 2004 barajada no hay habilidad, y una
    variable con fuga lo hace FALLAR;
(d) señal plantada: habilidad dentro de [0,20; 0,40] (fijado a priori por la simulación del Validador) y control
    positivo con fuga > 0,42;
(e) lista negra; (f) solo series `observed`, expectativas como encuestas fechadas.
Periodo bloqueado: lo que mira la etiqueta (c) solo usa meses ≤ 2004-12 (research/trial_log.md).
"""
from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd
import pytest
import yaml

from pit_helpers import persistence_onehot, synthetic_warehouse, truncated_warehouse, wf_skill
from src.features import pit as P
from src.features import placebo as PL
from src.features.calendar import CAL_PATH, MEASURED_PATH, CalEntry, load_calendar
from src.labels import regime_us as R

HOLDOUT = pd.Timestamp(R.PARAMS.holdout_start)
SNAP = P.snapshot_paths()


@pytest.fixture(scope="module")
def snap():
    con, wl, cal_path, info = P.read_snapshot()
    yield {"con": con, "wl": wl, "cal_path": cal_path, "cal": load_calendar(cal_path), "info": info,
           "grid": P.decision_grid(today=pd.Timestamp(info["grid_end"]))}
    con.close()


@pytest.fixture(scope="module")
def forbidden():
    return json.loads(R.out_path().with_suffix(".meta.json").read_text())["forbidden_features"]["series"]


@pytest.fixture(scope="module")
def full(snap, forbidden):
    return {m: P.build_matrix(snap["con"], m, snap["grid"], wl=snap["wl"], cal=snap["cal"], forbidden=forbidden,
                              raw=False) for m in P.MODES}


# ------------------------------------------------------------------ (h) instantánea congelada / candidata
def test_h_current_version_is_candidate_not_frozen():
    """I-4: una versión entra en FROZEN solo tras el veredicto del Validador. La v0.3 es candidata."""
    assert P.VERSION in P.CANDIDATE and P.VERSION not in P.FROZEN
    assert P.SUPERSEDED.get("0.2") == P.VERSION


HASH_KEYS = ("data_sha256_file", "data_sha256_content", "whitelist_sha256", "calendar_sha256", "info_sha256", "grid_end")


def test_h_frozen_entries_follow_procedure():
    """B-5 (procedimiento de congelación): una versión congelada tras la v0.2 conserva su entrada en CANDIDATE con los
    mismos hashes y apunta a un veredicto del Validador que existe. (La v0.2 se congeló antes del veredicto, I-4.)
    Hoy no hay ninguna: la v0.3 sigue candidata."""
    for version, ref in P.FROZEN.items():
        if version == "0.2":
            continue
        assert {k: ref[k] for k in HASH_KEYS} == {k: P.CANDIDATE[version][k] for k in HASH_KEYS}, version
        assert (P.REPO / ref["veredicto"]).is_file(), version


def test_h_write_snapshot_refuses_shared_data(tmp_path, monkeypatch):
    """H-2: una versión cuya instantánea de datos es de otra versión (DATA_VERSION) no puede reescribirla, ni con
    force=True (`--freeze --force`). En un directorio temporal, nunca sobre los datos reales."""
    monkeypatch.setattr(P, "out_dir", lambda: tmp_path / "features")
    monkeypatch.setattr(P, "DATA_VERSION", {**P.DATA_VERSION, "9.1": "9.0"})
    for version in ("0.3", "9.1"):
        paths = P.snapshot_paths(version)
        assert tmp_path in paths["data"].parents and paths["data"].name != f"pit_us_v{version}_inputs.parquet"
        paths["data"].parent.mkdir(parents=True, exist_ok=True)
        (paths["data"].parent / "backup").mkdir(exist_ok=True)
        files = [paths["data"], paths["data"].parent / "backup" / paths["data"].name]
        for f in files:
            if not f.exists():
                f.write_bytes(b"instantanea compartida")
                f.chmod(0o444)
        before = {f: (P.file_sha(f), f.stat().st_mode) for f in files}
        for force in (False, True):
            with pytest.raises(SystemExit, match="no es suya"):
                P.write_snapshot(None, version=version, force=force)
        assert {f: (P.file_sha(f), f.stat().st_mode) for f in files} == before   # ni contenido ni permisos
        assert not paths["whitelist"].exists() and not paths["info"].exists()
    assert P.DATA_VERSION["0.3"] != "0.3"   # el caso real que protege el guarda


def test_h_write_snapshot_own_data_not_blocked(tmp_path, monkeypatch):
    """El guarda H-2 no bloquea una versión nueva con datos propios: pasa los guardas y solo falla al leer el warehouse
    (con=None). Directorio temporal."""
    monkeypatch.setattr(P, "out_dir", lambda: tmp_path / "features")
    assert P.DATA_VERSION.get("9.2", "9.2") == "9.2" and "9.2" not in P.FROZEN
    with pytest.raises(AttributeError):
        P.write_snapshot(None, version="9.2", force=True)


def test_h_snapshot_matches_registered():
    ref = P.snapshot_ref(P.VERSION)
    assert P.file_sha(SNAP["data"]) == ref["data_sha256_file"]
    assert P.frame_sha(pd.read_parquet(SNAP["data"])) == ref["data_sha256_content"]
    assert P.file_sha(SNAP["whitelist"]) == ref["whitelist_sha256"]
    assert P.file_sha(SNAP["calendar"]) == ref["calendar_sha256"]
    assert P.file_sha(SNAP["info"]) == ref["info_sha256"]
    for p in SNAP.values():   # solo lectura, con copia de respaldo idéntica
        assert not (p.stat().st_mode & 0o222), p
        assert P.file_sha(p.parent / "backup" / p.name) == P.file_sha(p)


@pytest.mark.parametrize("version", sorted(P.FROZEN))
def test_h_frozen_versions_intact(version):
    """Las versiones congeladas (también la v0.2, sustituida) siguen intactas."""
    ref, paths = P.FROZEN[version], P.snapshot_paths(version)
    assert P.file_sha(paths["data"]) == ref["data_sha256_file"]
    assert P.file_sha(paths["whitelist"]) == ref["whitelist_sha256"]
    assert P.file_sha(paths["calendar"]) == ref["calendar_sha256"]


def test_h_same_data_as_v02():
    assert P.CANDIDATE["0.3"]["data_sha256_file"] == P.FROZEN["0.2"]["data_sha256_file"]
    assert P.snapshot_paths("0.3")["data"] == P.snapshot_paths("0.2")["data"]


def test_h_research_files_equal_snapshot():
    """La lista blanca y el calendario de research/ no pueden cambiar sin una versión nueva."""
    ref = P.snapshot_ref(P.VERSION)
    assert P.file_sha(P.WL_PATH) == ref["whitelist_sha256"]
    assert P.file_sha(CAL_PATH) == ref["calendar_sha256"]


def test_h_tampered_snapshot_rejected(tmp_path):
    paths = {k: tmp_path / v.name for k, v in SNAP.items()}
    for k, v in SNAP.items():
        shutil.copyfile(v, paths[k])
    df = pd.read_parquet(paths["data"])
    df.loc[df.index[-1], "value"] = (df["value"].iloc[-1] or 0) + 1.0
    df.to_parquet(paths["data"], index=False)
    with pytest.raises(RuntimeError):
        P.read_snapshot(paths=paths)


@pytest.fixture(scope="module")
def official_rebuild(snap, full, forbidden):
    """Reconstrucción completa: los 2 modos, la variante de Filadelfia y los baselines (misma muestra)."""
    phil = P.build_matrix(snap["con"], "vintage", snap["grid"], wl=snap["wl"],
                          cal=load_calendar(snap["cal_path"], variant="prudente"), forbidden=forbidden, raw=False)
    base = P.common_sample({m: P.persistence(snap["con"], m, snap["grid"], cal=snap["cal"], raw=False)
                            for m in P.MODES})
    return {"vintage": full["vintage"][0], "latest_truncated": full["latest_truncated"][0],
            "vintage_filadelfia_prudente": phil[0]}, base


def test_h_official_outputs_reproducible(official_rebuild):
    mats, base = official_rebuild
    od = P.out_dir()
    meta = json.loads((od / f"pit_us_v{P.VERSION}.meta.json").read_text())
    for name, X in mats.items():
        assert P.frame_sha(X) == meta["files"][f"pit_us_v{P.VERSION}_{name}.parquet"]["sha256_content"], name
    for m, B in base.items():
        f = od / f"baseline_persistence_v{P.VERSION}_{m}.parquet"
        pd.testing.assert_frame_equal(pd.read_parquet(f), B.reset_index(), obj=f.name)
        assert P.file_sha(f) == meta["files"][f.name]["sha256_file"]
    assert meta["instantanea_entradas"]["candidata"] == P.CANDIDATE[P.VERSION]
    assert meta["label_meta_sha256"] == P.LABEL_META_SHA256[R.PARAMS.version]


def test_h_snapshot_writers_refuse_frozen():
    with pytest.raises(SystemExit):
        P.write_snapshot(None, version="0.2")
    with pytest.raises(SystemExit):
        P.write_candidate(version="0.2")


def test_h_label_params_pinned(tmp_path, monkeypatch):
    """M-1: s_G, s_I y el empalme salen de la etiqueta congelada; un meta.json alterado hace fallar."""
    lp = P.label_params()
    assert (lp["s_G"], lp["s_I"]) == (0.40, 0.31) and abs(lp["splice"] - 0.20435090125244157) < 1e-12
    meta = json.loads(R.out_path().with_suffix(".meta.json").read_text())
    meta["s_G"] = 0.41
    fake = tmp_path / R.out_path().name
    fake.with_suffix(".meta.json").write_text(json.dumps(meta))
    monkeypatch.setattr(P.R, "out_path", lambda p=R.PARAMS: fake)
    with pytest.raises(RuntimeError):
        P.label_params()


# ------------------------------------------------------------------ principal_desde: herencia por dependencias (I-1)
def _ancestors(specs: dict, name: str) -> set:
    seen, todo = set(), list(specs[name].get("entradas") or [])
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo += list(specs[n].get("entradas") or [])
    return seen


def test_i1_principal_desde_inherited_through_graph(snap):
    """Recorrido independiente del grafo: el principal_desde efectivo = el más tardío del nodo y de TODOS sus
    ancestros; coincide con el código y con el meta."""
    specs = {v["nombre"]: v for v in snap["wl"]["variables"]}
    meta = json.loads((P.out_dir() / f"pit_us_v{P.VERSION}.meta.json").read_text())["columns"]["vintage"]
    eff = P.effective_principal_desde(snap["wl"])
    for name in P.public_columns(snap["wl"]):
        dates = [str(specs[n]["principal_desde"]) for n in {name} | _ancestors(specs, name)
                 if specs[n].get("principal_desde")]
        want = max(dates) if dates else None
        assert eff[name] == want, name
        assert meta[name]["principal_desde_efectivo"] == want, name
    assert eff["infl_energy_pressure"] == "1978-01-01"            # hereda de headline_minus_core_6m
    assert {n for n in P.public_columns(snap["wl"]) if meta[n]["principal_desde_heredado"]} == {"infl_energy_pressure"}


def test_i2_vix_conditional_before_2003(snap):
    v = next(x for x in snap["wl"]["variables"] if x["nombre"] == "vix")
    assert str(v["principal_desde"]) == "2003-09-22"


def test_h1_tcu_gap_conditional_before_1984(snap):
    """H-1 (decisión del usuario, 2026-10-16): la utilización de la industria total existe desde 1983 (G.17 de la Fed)
    → tcu_gap condicional antes de 1984-01-01. Toda variable que dependa de _tcu/tcu_gap lo hereda (hoy, ninguna)."""
    specs = {v["nombre"]: v for v in snap["wl"]["variables"]}
    assert str(specs["tcu_gap"]["principal_desde"]) == "1984-01-01"
    eff = P.effective_principal_desde(snap["wl"])
    meta = json.loads((P.out_dir() / f"pit_us_v{P.VERSION}.meta.json").read_text())["columns"]
    for mode in meta:
        assert meta[mode]["tcu_gap"]["principal_desde_efectivo"] == "1984-01-01", mode
        assert meta[mode]["tcu_gap"]["principal_desde_heredado"] is False, mode
    users = [n for n in P.public_columns(snap["wl"]) if {"_tcu", "tcu_gap"} & ({n} | _ancestors(specs, n))]
    assert users == ["tcu_gap"]
    assert all(eff[n] is not None and eff[n] >= "1984-01-01" for n in users)


# ------------------------------------------------------------------ (a) publicación ≤ t, recalculada aparte
def _independent_publication(con, raw: dict, lin: pd.DataFrame) -> pd.Series:
    """Fecha de publicación de (series_id, obs_date) SIN src.features.calendar: primera vintage no nula de la serie o
    de sus proxies del yaml si es una primera publicación (≤ 200 días tras el periodo y no en la carga inicial); si
    no, ancla + retardo del yaml."""
    fr = con.execute("""select series_id, date, min(realtime_start) rs from observations
                        where realtime_start is not null and value is not null group by 1, 2""").df()
    start = con.execute("""select series_id, min(realtime_start) s0 from observations
                           where realtime_start is not null group by 1""").df().set_index("series_id")["s0"]
    fr["date"], fr["rs"] = pd.to_datetime(fr["date"]), pd.to_datetime(fr["rs"])
    frd = {k: g.set_index("date")["rs"] for k, g in fr.groupby("series_id")}
    out = pd.Series(pd.NaT, index=lin.index, dtype="datetime64[ns]")
    for sid, g in lin.groupby("series_id"):
        e = raw[sid]
        d = pd.DatetimeIndex(g["obs_date"])
        if e["frecuencia"] in ("D", "W") or e.get("ancla") == "inicio_periodo":
            anchor = d
        else:
            anchor = d + (pd.offsets.MonthEnd(0) if e["frecuencia"] == "M" else pd.offsets.QuarterEnd(0))
        lags = sorted((pd.Timestamp(str(x["desde"])), x["dias"]) for x in e["retardo_dias"])
        lag = np.full(len(d), lags[0][1])
        for since, days in lags[1:]:
            lag[d >= since] = days
        cal = pd.Series(anchor + pd.to_timedelta(lag, unit="D"), index=g.index)
        best = pd.Series(pd.NaT, index=g.index, dtype="datetime64[ns]")
        covered = pd.Series(False, index=g.index)
        for p in e.get("proxies_publicacion") or []:
            if p not in frd:
                continue
            r = pd.Series(frd[p].reindex(d).to_numpy(), index=g.index)
            real = r.notna() & (r != pd.Timestamp(start[p])) & ((r - pd.Series(anchor, index=g.index)).dt.days <= 200)
            cand = r.where(real, pd.concat([cal, r], axis=1).min(axis=1)).where(r.notna())
            best = best.where(best.notna() & (cand.isna() | (best <= cand)), cand)
            covered |= pd.Series(d >= frd[p].index.min(), index=g.index)
        best = best.where(best.notna() | covered, cal)
        if e["frecuencia"] in ("M", "Q") and e.get("ancla", "fin_periodo") == "fin_periodo" \
                and min(x["dias"] for x in e["retardo_dias"]) >= 0:
            floor = pd.Series(anchor + pd.Timedelta(days=1), index=g.index)
            best = best.where(best >= floor, floor)
        out[g.index] = best
    return out


@pytest.mark.parametrize("mode", P.MODES)
def test_a_no_cell_uses_unpublished_data(snap, full, mode):
    con = snap["con"]
    raw = yaml.safe_load(snap["cal_path"].read_text())["series"]
    _, lin, _ = full[mode]
    lin = lin.drop_duplicates(["decision_date", "series_id", "obs_date", "mode"]).reset_index(drop=True)
    t = pd.to_datetime(lin["decision_date"])
    vin = lin["mode"].str.startswith("vintage:")
    if vin.any():
        v = lin[vin].assign(vsid=lin.loc[vin, "mode"].str.slice(8))
        fr = con.execute("""select series_id vsid, date obs_date, min(realtime_start) rs from observations
                            where realtime_start is not null and value is not null group by 1, 2""").df()
        fr["obs_date"], fr["rs"] = pd.to_datetime(fr["obs_date"]), pd.to_datetime(fr["rs"])
        m = v.merge(fr, on=["vsid", "obs_date"], how="left")
        assert m["rs"].notna().all()
        assert (m["rs"] <= pd.to_datetime(m["decision_date"])).all()
    lt = ~vin
    pub = _independent_publication(con, raw, lin[lt])
    bad = lin[lt][pub > t[lt]]
    assert bad.empty, f"{len(bad)} celdas con publicación posterior a t:\n{bad.head(10)}"
    intra = {s for s, e in raw.items() if min(x["dias"] for x in e["retardo_dias"]) < 0
             or e.get("ancla") == "inicio_periodo"}
    od = pd.to_datetime(lin["obs_date"])
    freq = lin["series_id"].map(lambda s: raw[s]["frecuencia"])
    pe = od.where(freq.isin(["D", "W"]), od + pd.offsets.MonthEnd(0))
    pe = pe.where(freq != "Q", od + pd.offsets.QuarterEnd(0))
    assert not ((pe >= t) & ~lin["series_id"].isin(intra)).any()


def test_a_ecb_week_published_after_t(snap, full):
    """BCE (Validador I-3): semana fechada en lunes, publicada el martes siguiente (lunes + 8)."""
    _, lin, _ = full["latest_truncated"]
    e = lin[lin["series_id"] == "ecb_eurosystem_total_assets_w"]
    assert len(e) and ((pd.to_datetime(e["decision_date"]) - pd.to_datetime(e["obs_date"])).dt.days >= 8).all()


# ------------------------------------------------------------------ (v) valores y calendario frente a otra fuente
SIMPLE = {"level", "pct_ann", "log_diff", "log_diff_ann", "diff"}


def _value_at(con, sid: str, d: pd.Timestamp, mode: str, t: pd.Timestamp) -> float:
    if mode.startswith("vintage:"):
        r = con.execute("""select value from observations where series_id = ? and date = ? and realtime_start <= ?
                           order by realtime_start desc limit 1""", [mode[8:], d, t]).fetchone()
    else:
        r = con.execute("select value from observations where series_id = ? and date = ? and realtime_start is null",
                        [sid, d]).fetchone()
    return np.nan if r is None or r[0] is None else float(r[0])


@pytest.mark.parametrize("mode", P.MODES)
def test_v_values_recomputed_by_hand(snap, full, mode):
    """Recalcula celdas al azar con SQL sobre la instantánea y la transformación escrita aquí (sin src.features)."""
    con, raw = snap["con"], yaml.safe_load(snap["cal_path"].read_text())["series"]
    X, lin, _ = full[mode]
    rng = np.random.default_rng(11)
    n = 0
    for spec in snap["wl"]["variables"]:
        tr = spec.get("transformacion") or {}
        if spec["nombre"].startswith("_") or spec["tipo"] != "serie" or tr.get("fn") not in SIMPLE:
            continue
        lc = lin[lin["column"] == spec["nombre"]]
        for i in rng.choice(len(lc), size=min(8, len(lc)), replace=False):
            row = lc.iloc[i]
            sid, d, t, md = row["series_id"], pd.Timestamp(row["obs_date"]), pd.Timestamp(row["decision_date"]), row["mode"]
            f = raw[sid]["frecuencia"]
            if f not in ("M", "Q"):
                continue
            ppy, step = (12, 1) if f == "M" else (4, 3)
            k = tr.get("k", 0)
            x0 = _value_at(con, sid, d, md, t)
            x1 = _value_at(con, sid, d - pd.DateOffset(months=step * k), md, t) if k else np.nan
            want = {"level": x0, "diff": x0 - x1, "log_diff": 100 * np.log(x0 / x1),
                    "log_diff_ann": 100 * np.log(x0 / x1) * ppy / max(k, 1),
                    "pct_ann": ((x0 / x1) ** (ppy / max(k, 1)) - 1) * 100}[tr["fn"]] * spec.get("factor", 1)
            got = X.loc[t, spec["nombre"]]
            np.testing.assert_allclose(got, want, rtol=1e-9, err_msg=f"{spec['nombre']} {t:%Y-%m-%d} {md}")
            n += 1
    assert n >= 150


PROXY_PAIRS = [("AWHMAN", "PAYEMS"), ("AHETPI", "PAYEMS"), ("UNRATE", "PAYEMS"), ("CUSR0000SASLE", "CPIAUCSL"),
               ("CPILFESL", "CPIAUCSL"), ("W875RX1", "PCEPI"), ("PCEPILFE", "PCEPI"), ("TCU", "INDPRO")]


def _real_first_release(con, sid: str) -> pd.Series:
    df = con.execute("""select date, min(realtime_start) rs from observations where series_id = ?
                        and realtime_start is not null and value is not null group by 1""", [sid]).df()
    s0 = con.execute("select min(realtime_start) from observations where series_id = ? and realtime_start is not null",
                     [sid]).fetchone()[0]
    r = pd.Series(pd.to_datetime(df["rs"]).to_numpy(), index=pd.to_datetime(df["date"])).sort_index()
    return r[(r > pd.Timestamp(s0)) & ((r - (r.index + pd.offsets.MonthEnd(0))).dt.days <= 200)]


@pytest.mark.parametrize("sid,proxy", PROXY_PAIRS)
def test_v_proxy_release_verified_with_own_vintages(snap, sid, proxy):
    """'Mismo comunicado de prensa': las vintages propias de la serie nunca la fechan DESPUÉS que su proxy."""
    a, b = _real_first_release(snap["con"], sid), _real_first_release(snap["con"], proxy)
    common = a.index.intersection(b.index)
    assert len(common) >= 150
    assert ((a[common] - b[common]).dt.days <= 0).all()


@pytest.mark.parametrize("sid,lag,until,share", [
    ("GACDFSA066MSFRBPHI", -7, "2100-01-01", 0.95), ("PPCDFSA066MSFRBPHI", -7, "2100-01-01", 0.95),
    ("PERMIT", 23, "2013-01-01", 1.0),        # el retardo de reserva (< 1999) frente a la época medida más antigua
    ("CMRMTSPL", 70, "2100-01-01", 0.90)])
def test_v_assumed_lags_vs_alfred(snap, sid, lag, until, share):
    """Supuestos del yaml frente a las fechas reales de ALFRED donde las hay (fuente distinta del yaml). Después de
    2013 los cierres del Gobierno retrasan comunicados; ahí manda la fecha ALFRED, no el supuesto."""
    r = _real_first_release(snap["con"], sid)
    d = (r - (r.index + pd.offsets.MonthEnd(0))).dt.days
    d = d[d.index < pd.Timestamp(until)]
    assert len(d) > 100 and (d <= lag).mean() >= share, d.describe()


# Regla 3 (pit_calendar.md): retardo de reserva ≥ MÁXIMO medido en la época más antigua con vintages propias, salvo
# excepciones documentadas, donde ese máximo no representa el tramo en que se usa la reserva.
FALLBACK_EXCEPTIONS = {
    "CMRMTSPL": "solo hay medición 2013+, con los cierres de 2013 y 2025 (máx. 114); la reserva se usa antes de 2013 "
                "(90/70 d ≥ p90 66)",
    "GACDFSA066MSFRBPHI": "máx. 18 = vintage ALFRED que falta en 2015-05 (Validador M-7); p90 −10",
    "NOCDFSA066MSFRBPHI": "igual que GACDFSA066MSFRBPHI",
    "PPCDFSA066MSFRBPHI": "igual que GACDFSA066MSFRBPHI",
}


def test_calendar_fallback_lags_cover_measured():
    cal = load_calendar()
    m = pd.read_csv(MEASURED_PATH)
    m = m[m["epoca"] != "todas"]
    for sid, e in cal.items():
        if sid not in e.proxies:
            continue
        mm = m[m["series_id"] == sid]
        if mm.empty:
            continue
        earliest = mm.sort_values("desde").iloc[0]
        need = earliest["p90"] if sid in FALLBACK_EXCEPTIONS else earliest["max"]
        assert e.lags[0][1] >= need, (sid, e.lags, earliest.to_dict())


# ------------------------------------------------------------------ (b) truncamiento
CUTOFFS = ["1962-03-30", "1979-10-31", "1996-12-31", "2004-12-30", "2014-06-30"]


@pytest.mark.parametrize("cut", CUTOFFS)
def test_b_truncation_same_row(snap, full, forbidden, cut):
    t = pd.Timestamp(cut)
    grid = snap["grid"]
    assert t in set(grid["decision_date"])
    mem = truncated_warehouse(snap["con"], t, P.needed_series(snap["wl"], snap["cal"]))
    g = grid[grid["decision_date"] <= t]
    for mode in P.MODES:
        X, _, _ = P.build_matrix(mem, mode, g, wl=snap["wl"], cal=snap["cal"], forbidden=forbidden, raw=False)
        pd.testing.assert_series_equal(X.loc[t], full[mode][0].loc[t], check_names=False, rtol=1e-9, atol=1e-12,
                                       obj=f"fila {cut} ({mode})")
    mem.close()


@pytest.mark.parametrize("cut", ["1979-10-31", "2004-12-30"])
def test_b_truncation_persistence(snap, monkeypatch, cut):
    t = pd.Timestamp(cut)
    g = snap["grid"][snap["grid"]["decision_date"] == t]
    full_rows = {m: P.persistence(snap["con"], m, g, cal=snap["cal"], raw=False) for m in P.MODES}
    inputs, info = R.read_snapshot()
    trunc = {"levels": {k: v[v.index <= t] for k, v in inputs["levels"].items()},
             "usrec": inputs["usrec"][inputs["usrec"].index <= t],
             "vintages": {k: (v[v["realtime_start"] <= t].copy(), o) for k, (v, o) in inputs["vintages"].items()},
             "forbidden_series": inputs["forbidden_series"]}
    monkeypatch.setattr(P.R, "read_snapshot", lambda p=R.PARAMS: (trunc, info))
    mem = truncated_warehouse(snap["con"], t, ["CPIAUCSL", "PCEPI", "PCEPILFE", "CPILFESL", "INDPRO", "PAYEMS",
                                               "W875RX1", "CMRMTSPL"])
    for m in P.MODES:
        pd.testing.assert_frame_equal(P.persistence(mem, m, g, cal=snap["cal"], raw=False), full_rows[m],
                                      obj=f"persistencia {cut} ({m})")
    mem.close()


def test_b_baselines_same_sample():
    od = P.out_dir()
    a = pd.read_parquet(od / f"baseline_persistence_v{P.VERSION}_vintage.parquet")
    b = pd.read_parquet(od / f"baseline_persistence_v{P.VERSION}_latest_truncated.parquet")
    assert a["decision_date"].tolist() == b["decision_date"].tolist()


# ------------------------------------------------------------------ (c) placebo con potencia
PLACEBO_FEATURES = ["curve_10y3m", "payems_3m_ann", "indpro_3m_ann", "unrate_sahm", "headline_cpi_6m_ann",
                    "ppi_yoy", "baa_spread", "ff_d12m"]


def _training_label() -> pd.DataFrame:
    lab = pd.read_parquet(R.out_path())
    lab = lab[(lab["weight"] > 0) & ~lab["provisional"] & (lab["date"] < HOLDOUT)]
    assert lab["date"].max() < HOLDOUT   # periodo bloqueado: nunca
    return lab.set_index("date")


def _leak(ys, rng):
    """Variable con fuga: el objetivo del propio mes con ruido (en t solo se conoce el de t − 5)."""
    return np.eye(4)[ys][:, 1:] + rng.normal(0, 0.5, (len(ys), 3))


def test_c_placebo_detects_leak(full):
    X = full["vintage"][0]
    X = X.set_index(X.index.to_period("M").to_timestamp())[PLACEBO_FEATURES]
    lab = _training_label()
    common = lab.index.intersection(X.dropna().index)
    common = common[common >= pd.Timestamp("1962-01-01")]
    y = np.array([R.QUADRANTS.index(q) for q in lab.loc[common, "label_hard"]])
    F = X.loc[common].to_numpy(float)
    honest = PL.placebo_skills(F, y, common, n_perm=8)
    leaky = PL.placebo_skills(F, y, common, n_perm=8, leak=_leak)
    t4 = PL.placebo_skills(F, y, common, n_perm=8, leak=lambda ys, rng: persistence_onehot(ys, lag=4))
    assert PL.placebo_check(honest), honest           # sin fuga: pasa
    assert not PL.placebo_check(leaky), leaky         # con fuga fuerte (σ = 0,5, elegida tras un fallo): falla
    assert (leaky > PL.PLACEBO_TOL).all(), leaky
    # control a priori (Validador v0.2, definido por el mecanismo): la etiqueta de t−4 en vez de t−5, es decir, una
    # fuga de calendario de 1 mes. Debe hacer fallar el placebo en todas las permutaciones
    assert not PL.placebo_check(t4), t4
    assert (t4 > PL.PLACEBO_TOL).all(), t4


# ------------------------------------------------------------------ (d) señal plantada
def _synthetic(seed: int = 7, leak: bool = False):
    rng = np.random.default_rng(seed)
    months = pd.date_range("1950-01-01", "2004-12-01", freq="MS")
    T = np.full((4, 4), 0.07 / 3) + np.eye(4) * (0.93 - 0.07 / 3)
    y = [0]
    for _ in range(len(months) - 1):
        y.append(rng.choice(4, p=T[y[-1]]))
    y = np.array(y)
    x = np.array([1.5, 0.5, -0.5, -1.5])[y] + rng.normal(0, 0.5, len(y))
    first = x + rng.normal(0, 0.3, len(y))
    noise = rng.normal(0, 1, len(y))
    pe = months + pd.offsets.MonthEnd(0)
    rows = [pd.DataFrame({"date": months, "value": x, "series_id": "SYN_SIGNAL", "source": "syn"}),
            pd.DataFrame({"date": months, "value": noise, "series_id": "SYN_NOISE", "source": "syn"}),
            pd.DataFrame({"date": months, "value": first, "series_id": "SYN_SIGNAL", "source": "syn",
                          "realtime_start": pe + pd.Timedelta(days=20)}),
            pd.DataFrame({"date": months, "value": x, "series_id": "SYN_SIGNAL", "source": "syn",
                          "realtime_start": pe + pd.Timedelta(days=110)})]
    cat = pd.DataFrame({"series_id": ["SYN_SIGNAL", "SYN_NOISE"], "source": "syn", "units": "x",
                        "pit_role": "observed"})
    mem = synthetic_warehouse(pd.concat(rows, ignore_index=True), cat, "2005-03-01")
    one = lambda d: ((pd.Timestamp("1900-01-01"), d),)  # noqa: E731
    if leak:   # control positivo: la serie "se publica" 10 días antes del fin de su mes → el dato de t en t
        cal = {"SYN_SIGNAL": CalEntry("SYN_SIGNAL", "M", "fin_periodo", one(-10), (), (), True, "fuga", ""),
               "SYN_NOISE": CalEntry("SYN_NOISE", "M", "fin_periodo", one(20), (), (), True, "", "")}
        modo = "latest_truncated"
    else:
        cal = {"SYN_SIGNAL": CalEntry("SYN_SIGNAL", "M", "fin_periodo", one(20), ("SYN_SIGNAL",), ("SYN_SIGNAL",),
                                      False, "sintética", ""),
               "SYN_NOISE": CalEntry("SYN_NOISE", "M", "fin_periodo", one(20), (), (), True, "sintética", "")}
        modo = "vintage"
    wl = {"zscore_min_meses": 120, "variables": [
        {"nombre": "syn_signal", "tipo": "serie", "series": ["SYN_SIGNAL"], "transformacion": {"fn": "level"},
         "modo": modo},
        {"nombre": "syn_noise", "tipo": "serie", "series": ["SYN_NOISE"], "transformacion": {"fn": "level"},
         "modo": "latest_truncated"}]}
    return mem, cal, wl, months, y, x, first


def _planted_skill(leak: bool):
    mem, cal, wl, months, y, x, first = _synthetic(leak=leak)
    grid = P.decision_grid(today=pd.Timestamp("2005-01-15"))
    grid = grid[grid["month"] <= months.max()]
    res = {m: P.build_matrix(mem, m, grid, wl=wl, cal=cal, forbidden=[]) for m in P.MODES}
    mem.close()
    Xv = res["vintage"][0]
    mv = Xv.set_index(Xv.index.to_period("M").to_timestamp())
    yy = pd.Series(y, index=months).reindex(mv.index).to_numpy()
    ok = slice(1, None)
    base = persistence_onehot(yy)[ok]
    sk = wf_skill(base, mv["syn_signal"].to_numpy()[ok, None], yy[ok], mv.index[ok], first_test_year=1965)
    sk_noise = wf_skill(base, mv["syn_noise"].to_numpy()[ok, None], yy[ok], mv.index[ok], first_test_year=1965)
    return res, months, x, first, sk, sk_noise


def test_d_planted_signal_in_prior_interval():
    res, months, x, first, sk, sk_noise = _planted_skill(leak=False)
    Xv, lin = res["vintage"][0], res["vintage"][1]
    Xl = res["latest_truncated"][0]
    ls = lin[lin["column"] == "syn_signal"].set_index("decision_date")["obs_date"]
    m_t = pd.DatetimeIndex(ls.index).to_period("M").to_timestamp()
    assert ((m_t - pd.DatetimeIndex(ls)).days.isin([28, 29, 30, 31])).all()          # dato de t−1
    mv = Xv.set_index(Xv.index.to_period("M").to_timestamp())["syn_signal"]
    ml = Xl.set_index(Xl.index.to_period("M").to_timestamp())["syn_signal"]
    np.testing.assert_allclose(mv.iloc[1:], pd.Series(first, index=months).shift(1).reindex(mv.index).iloc[1:])
    np.testing.assert_allclose(ml.iloc[1:], pd.Series(x, index=months).shift(1).reindex(ml.index).iloc[1:])
    assert 0.20 <= sk <= 0.40, sk          # intervalo fijado a priori (Validador, 20 semillas: 0,23-0,34)
    assert sk_noise < 0.02, sk_noise


def test_d_positive_control_leak_detected():
    *_, sk, _ = _planted_skill(leak=True)
    assert sk > 0.42, sk                   # con fuga (dato de t en t) la habilidad sale del intervalo


# ------------------------------------------------------------------ (e) lista negra
@pytest.mark.parametrize("mode", P.MODES)
def test_e_no_forbidden_columns(snap, full, forbidden, mode):
    X, lin, _ = full[mode]
    R.assert_no_forbidden(X.columns, extra=forbidden)
    R.assert_no_forbidden(X.columns)
    assert not set(X.columns) & set(R.LABEL_COLUMNS)
    assert not any(str(c).startswith(("pers_", "label", "p_")) for c in X.columns)
    assert not set(lin["series_id"]) & (set(forbidden) | {"USREC"})
    assert set(X.columns) == set(P.public_columns(snap["wl"]))


def test_e_builder_rejects_forbidden(snap, forbidden):
    cal = dict(snap["cal"])
    cal["USREC"] = CalEntry("USREC", "M", "fin_periodo", ((pd.Timestamp("1900-01-01"), 400),), (), (), True, "", "")
    g = snap["grid"].tail(3)
    bad = {**snap["wl"], "variables": [{"nombre": "recesion", "tipo": "serie", "series": ["USREC"],
                                        "transformacion": {"fn": "level"}, "modo": "latest_truncated"}]}
    with pytest.raises(AssertionError):
        P.build_matrix(snap["con"], "latest_truncated", g, wl=bad, cal=cal, forbidden=forbidden, raw=False)
    v0 = snap["wl"]["variables"][0]
    derived = {**snap["wl"], "variables": [v0, {"nombre": "usrec_lag1", "tipo": "derivada", "funcion": "diff3",
                                                "entradas": [v0["nombre"]]}]}
    with pytest.raises(AssertionError):
        P.build_matrix(snap["con"], "latest_truncated", g, wl=derived, cal=snap["cal"], forbidden=forbidden, raw=False)


# ------------------------------------------------------------------ (f) forecast / lookahead
def test_f_only_observed_series(snap, full):
    sids = P.needed_series(snap["wl"], snap["cal"])
    roles = dict(snap["con"].execute("select series_id, pit_role from catalog").fetchall())
    assert set(sids) <= set(roles) and {roles[s] for s in sids} == {"observed"}
    for mode in P.MODES:
        assert set(full[mode][1]["series_id"]) <= set(sids)
    spf = [s for s in sids if s.startswith("spf_")]
    assert spf and all(snap["cal"][s].anchor == "inicio_periodo" and min(d for _, d in snap["cal"][s].lags) >= 45
                       for s in spf)


def test_f_builder_rejects_forecast_series(snap, forbidden):
    cal = dict(snap["cal"])
    cal["GDPPOT"] = CalEntry("GDPPOT", "Q", "fin_periodo", ((pd.Timestamp("1900-01-01"), 30),), (), (), True, "", "")
    wl = {**snap["wl"], "variables": [{"nombre": "potencial", "tipo": "serie", "series": ["GDPPOT"],
                                       "transformacion": {"fn": "level"}, "modo": "latest_truncated"}]}
    with pytest.raises(AssertionError):   # no está en la instantánea (pit_role ≠ observed) y además es forecast
        P.build_matrix(snap["con"], "latest_truncated", snap["grid"].tail(3), wl=wl, cal=cal, forbidden=forbidden,
                       raw=False)


# ------------------------------------------------------------------ lista blanca
def test_whitelist_documented(snap):
    estados = {"principal", "principal_epoca", "modulo_adicional", "condicional", "auxiliar"}
    for v in snap["wl"]["variables"]:
        assert v["estado"] in estados, v["nombre"]
        assert v.get("mecanismo"), v["nombre"]
        if not v["nombre"].startswith("_"):
            assert {"fuente_viva", "historia", "pit", "disponibilidad"} <= set(v["admision"]), v["nombre"]
        if v["tipo"] == "serie":
            assert all(s in snap["cal"] for s in v["series"]), v["nombre"]
            assert v["transformacion"]["fn"] in P.TRANSFORMS and v["modo"] in P.MODES
        else:
            assert v["funcion"] in P.DERIVED
    # reclasificaciones aprobadas (Validador I-4)
    pd_ = {v["nombre"]: str(v.get("principal_desde")) for v in snap["wl"]["variables"]}
    assert pd_["gz_spread"] == "2012-01-01" and pd_["m2_real_yoy"] == "1980-02-01"
    assert all(pd_[c] == "1978-01-01" for c in ("core_cpi_6m_ann", "core_cpi_yoy", "real_ff"))


def test_desde_columns_empty_before(full):
    X = full["vintage"][0]
    assert X.loc[:"1972-12-31", "copper_gold_6m"].isna().all()
    assert X.loc[:"1973-02-28", "usd_neer_yoy"].isna().all()
    assert X.loc[:"1977-12-31", "umcsent"].isna().all()
