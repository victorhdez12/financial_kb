"""Tests de fugas de la base point-in-time (docs/models/pit_base.md §5).

(a) ninguna celda usa un dato publicado después de t (comprobación independiente desde `observations`);
(b) truncamiento: con el warehouse truncado en t, la fila t es idéntica (variables y persistencia);
(c) placebo: con la etiqueta barajada en bloques, la logística no gana a la persistencia;
(d) señal plantada: una variable sintética con relación conocida se recupera; sin relación, no aparece;
(e) ninguna variable de la lista negra ni derivada;
(f) ninguna serie forecast/lookahead (las expectativas solo como encuesta fechada).

Periodo bloqueado: los tests que miran la etiqueta (c) solo usan meses ≤ 2004-12 (anotado en
research/trial_log.md). (b) compara datos, no relaciones, e incluye un corte posterior.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import yaml

from pit_helpers import (persistence_onehot, synthetic_warehouse, truncated_warehouse, wf_skill)
from src.features import pit as P
from src.features.calendar import CAL_PATH, MEASURED_PATH, CalEntry, load_calendar
from src.labels import regime_us as R
from src.warehouse import db

HOLDOUT = pd.Timestamp(R.PARAMS.holdout_start)


@pytest.fixture(scope="module")
def con():
    c = db.connect()
    yield c
    c.close()


@pytest.fixture(scope="module")
def forbidden():
    return json.loads(R.out_path().with_suffix(".meta.json").read_text())["forbidden_features"]["series"]


@pytest.fixture(scope="module")
def grid():
    return P.decision_grid()


@pytest.fixture(scope="module")
def full(con, grid, forbidden):
    return {m: P.build_matrix(con, m, grid, forbidden=forbidden) for m in P.MODES}


# ------------------------------------------------------------------ (a) publicación ≤ t, recalculada aparte
def _independent_publication(con, lin: pd.DataFrame) -> pd.Series:
    """Fecha de publicación de (series_id, obs_date) recalculada SIN el módulo calendar: primera vintage no nula
    en `observations` de la serie o de sus proxies del yaml si es una primera publicación (≤ 200 días tras el
    periodo y no en la carga inicial); si no, ancla + retardo del yaml."""
    raw = yaml.safe_load(CAL_PATH.read_text())["series"]
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
            real = r.notna() & (r != start[p]) & ((r - pd.Series(anchor, index=g.index)).dt.days <= 200)
            cand = r.where(real, pd.concat([cal, r], axis=1).min(axis=1)).where(r.notna())
            best = best.where(best.notna() & (cand.isna() | (best <= cand)), cand)
            covered |= pd.Series(d >= frd[p].index.min(), index=g.index)
        best = best.where(best.notna() | covered, cal)   # antes del archivo: calendario
        if e["frecuencia"] in ("M", "Q") and e.get("ancla", "fin_periodo") == "fin_periodo" \
                and min(x["dias"] for x in e["retardo_dias"]) >= 0:
            floor = pd.Series(anchor + pd.Timedelta(days=1), index=g.index)
            best = best.where(best >= floor, floor)
        out[g.index] = best
    return out


@pytest.mark.parametrize("mode", P.MODES)
def test_a_no_cell_uses_unpublished_data(con, full, mode):
    _, lin, _ = full[mode]
    lin = lin.drop_duplicates(["decision_date", "series_id", "obs_date", "mode"]).reset_index(drop=True)
    t = pd.to_datetime(lin["decision_date"])
    # vintage: la vintage usada existía en t (primera fila no nula de esa fecha con realtime_start ≤ t)
    vin = lin["mode"].str.startswith("vintage:")
    if vin.any():
        v = lin[vin].assign(vsid=lin.loc[vin, "mode"].str.slice(8))
        fr = con.execute("""select series_id vsid, date obs_date, min(realtime_start) rs from observations
                            where realtime_start is not null and value is not null group by 1, 2""").df()
        fr["obs_date"], fr["rs"] = pd.to_datetime(fr["obs_date"]), pd.to_datetime(fr["rs"])
        m = v.merge(fr, on=["vsid", "obs_date"], how="left")
        assert m["rs"].notna().all()
        assert (m["rs"] <= pd.to_datetime(m["decision_date"])).all()
    # latest_truncated: publicación independiente ≤ t
    lt = ~vin
    pub = _independent_publication(con, lin[lt])
    bad = lin[lt][pub > t[lt]]
    assert bad.empty, f"{len(bad)} celdas con publicación posterior a t:\n{bad.head(10)}"
    # sin calendario: nunca un dato de un periodo de referencia que no ha terminado (salvo encuestas del mes)
    raw = yaml.safe_load(CAL_PATH.read_text())["series"]
    intra = {s for s, e in raw.items() if min(x["dias"] for x in e["retardo_dias"]) < 0
             or e.get("ancla") == "inicio_periodo"}
    od = pd.to_datetime(lin["obs_date"])
    freq = lin["series_id"].map(lambda s: raw[s]["frecuencia"])
    pe = od.where(freq.isin(["D", "W"]), od + pd.offsets.MonthEnd(0))
    pe = pe.where(freq != "Q", od + pd.offsets.QuarterEnd(0))
    assert not ((pe >= t) & ~lin["series_id"].isin(intra)).any()


# ------------------------------------------------------------------ (b) truncamiento
CUTOFFS = ["1962-03-30", "1979-10-31", "1996-12-31", "2004-12-30", "2011-05-31"]


@pytest.mark.parametrize("cut", CUTOFFS)
def test_b_truncation_same_row(con, grid, full, forbidden, cut):
    t = pd.Timestamp(cut)
    assert t in set(grid["decision_date"]), "el corte debe ser una fecha de decisión"
    sids = P.needed_series(P.load_whitelist(), load_calendar())
    mem = truncated_warehouse(con, t, sids)
    g = grid[grid["decision_date"] <= t]
    for mode in P.MODES:
        X, _, _ = P.build_matrix(mem, mode, g, forbidden=forbidden)
        a, b = X.loc[t], full[mode][0].loc[t]
        pd.testing.assert_series_equal(a, b, check_names=False, rtol=1e-9, atol=1e-12,
                                       obj=f"fila {cut} ({mode})")
    mem.close()


@pytest.mark.parametrize("cut", ["1979-10-31", "2004-12-30"])
def test_b_truncation_persistence(con, grid, monkeypatch, cut):
    """La persistencia point-in-time en t no cambia si la instantánea de la etiqueta y las vintages del
    warehouse se truncan en t."""
    t = pd.Timestamp(cut)
    g = grid[grid["decision_date"] == t]
    full_rows = {m: P.persistence(con, m, g) for m in P.MODES}
    inputs, info = R.read_snapshot()
    trunc = {"levels": {k: v[v.index <= t] for k, v in inputs["levels"].items()},
             "usrec": inputs["usrec"][inputs["usrec"].index <= t],
             "vintages": {k: (v[v["realtime_start"] <= t].copy(), o) for k, (v, o) in inputs["vintages"].items()},
             "forbidden_series": inputs["forbidden_series"]}
    monkeypatch.setattr(P.R, "read_snapshot", lambda p=R.PARAMS: (trunc, info))
    mem = truncated_warehouse(con, t, ["CPIAUCSL", "PCEPI", "PCEPILFE", "CPILFESL", "INDPRO", "PAYEMS"])
    for m in P.MODES:
        a = P.persistence(mem, m, g)
        pd.testing.assert_frame_equal(a, full_rows[m], obj=f"persistencia {cut} ({m})")
    mem.close()


# ------------------------------------------------------------------ (c) placebo
PLACEBO_FEATURES = ["curve_10y3m", "payems_3m_ann", "indpro_3m_ann", "unrate_sahm", "core_cpi_6m_ann",
                    "ppi_yoy", "baa_spread", "ff_d12m"]


def _training_label() -> pd.DataFrame:
    lab = pd.read_parquet(R.out_path())
    lab = lab[(lab["weight"] > 0) & ~lab["provisional"] & (lab["date"] < HOLDOUT)]
    assert lab["date"].max() < HOLDOUT   # periodo bloqueado: nunca
    return lab.set_index("date")


def test_c_placebo_block_shuffled_label(full):
    X = full["latest_truncated"][0]
    X = X.set_index(X.index.to_period("M").to_timestamp())[PLACEBO_FEATURES]
    lab = _training_label()
    common = lab.index.intersection(X.dropna().index)
    common = common[common >= pd.Timestamp("1962-01-01")]
    y0 = np.array([R.QUADRANTS.index(q) for q in lab.loc[common, "label_hard"]])
    F = X.loc[common].to_numpy(float)
    rng = np.random.default_rng(20261015)
    block = 24
    nb = int(np.ceil(len(y0) / block))
    skills = []
    for _ in range(10):
        order = rng.permutation(nb)
        y = np.concatenate([y0[i * block:(i + 1) * block] for i in order])[:len(y0)]
        skills.append(wf_skill(persistence_onehot(y), F, y, common, first_test_year=1975))
    skills = np.array(skills)
    # sin relación real: las variables no mejoran la persistencia (sobreajuste → habilidad ≤ 0)
    assert skills.mean() < 0.02, skills
    assert (skills < 0.08).all(), skills


# ------------------------------------------------------------------ (d) señal plantada
def _synthetic(seed: int = 7):
    rng = np.random.default_rng(seed)
    months = pd.date_range("1950-01-01", "2004-12-01", freq="MS")
    P_ = np.full((4, 4), 0.07 / 3) + np.eye(4) * (0.93 - 0.07 / 3)
    y = [0]
    for _ in range(len(months) - 1):
        y.append(rng.choice(4, p=P_[y[-1]]))
    y = np.array(y)
    mu = np.array([1.5, 0.5, -0.5, -1.5])
    x = mu[y] + rng.normal(0, 0.5, len(y))
    first = x + rng.normal(0, 0.3, len(y))
    noise = rng.normal(0, 1, len(y))
    pe = months + pd.offsets.MonthEnd(0)
    rows = [pd.DataFrame({"date": months, "value": x, "series_id": "SYN_SIGNAL", "source": "syn"}),
            pd.DataFrame({"date": months, "value": noise, "series_id": "SYN_NOISE", "source": "syn"}),
            # vintages: primera publicación ruidosa a los 20 días; revisión al valor final a los 110 días
            pd.DataFrame({"date": months, "value": first, "series_id": "SYN_SIGNAL", "source": "syn",
                          "realtime_start": pe + pd.Timedelta(days=20)}),
            pd.DataFrame({"date": months, "value": x, "series_id": "SYN_SIGNAL", "source": "syn",
                          "realtime_start": pe + pd.Timedelta(days=110)})]
    cat = pd.DataFrame({"series_id": ["SYN_SIGNAL", "SYN_NOISE"], "source": "syn", "units": "x",
                        "pit_role": "observed"})
    mem = synthetic_warehouse(pd.concat(rows, ignore_index=True), cat, "2005-03-01")
    lag = ((pd.Timestamp("1900-01-01"), 20),)
    cal = {"SYN_SIGNAL": CalEntry("SYN_SIGNAL", "M", "fin_periodo", lag, ("SYN_SIGNAL",), ("SYN_SIGNAL",),
                                  False, "sintética", ""),
           "SYN_NOISE": CalEntry("SYN_NOISE", "M", "fin_periodo", lag, (), (), True, "sintética", "")}
    wl = {"zscore_min_meses": 120, "histeresis_banda": 0.15, "variables": [
        {"nombre": "syn_signal", "tipo": "serie", "series": ["SYN_SIGNAL"], "transformacion": {"fn": "level"},
         "modo": "vintage"},
        {"nombre": "syn_noise", "tipo": "serie", "series": ["SYN_NOISE"], "transformacion": {"fn": "level"},
         "modo": "latest_truncated"}]}
    return mem, cal, wl, months, y, x, first


def test_d_planted_signal_recovered_and_noise_not():
    mem, cal, wl, months, y, x, first = _synthetic()
    grid = P.decision_grid(today=pd.Timestamp("2005-01-15"))
    grid = grid[grid["month"] <= months.max()]
    res = {m: P.build_matrix(mem, m, grid, wl=wl, cal=cal, forbidden=[]) for m in P.MODES}
    Xv, lin = res["vintage"][0], res["vintage"][1]
    Xl = res["latest_truncated"][0]
    # calendario: en el último día hábil de t se conoce el dato de t−1 (publicado el día 20 de t)
    ls = lin[lin["column"] == "syn_signal"].set_index("decision_date")["obs_date"]
    m_t = pd.DatetimeIndex(ls.index).to_period("M").to_timestamp()
    assert ((m_t - pd.DatetimeIndex(ls)).days.isin([28, 29, 30, 31])).all()
    # modos: vintage = primera publicación; latest_truncated = valor revisado
    s_first = pd.Series(first, index=months).shift(1)
    s_final = pd.Series(x, index=months).shift(1)
    mv = Xv.set_index(Xv.index.to_period("M").to_timestamp())["syn_signal"]
    ml = Xl.set_index(Xl.index.to_period("M").to_timestamp())["syn_signal"]
    np.testing.assert_allclose(mv.iloc[1:], s_first.reindex(mv.index).iloc[1:])
    np.testing.assert_allclose(ml.iloc[1:], s_final.reindex(ml.index).iloc[1:])
    # habilidad: la señal (dato de t−1, régimen persistente) se recupera; el ruido no aporta
    yy = pd.Series(y, index=months).reindex(mv.index).to_numpy()
    ok = slice(1, None)
    base = persistence_onehot(yy)[ok]
    idx = mv.index[ok]
    sk_sig = wf_skill(base, mv.to_numpy()[ok, None], yy[ok], idx, first_test_year=1965)
    sk_noise = wf_skill(base, Xv["syn_noise"].to_numpy()[ok, None], yy[ok], idx, first_test_year=1965)
    assert sk_sig > 0.10, sk_sig      # 5 veces el techo del placebo (0,02)
    assert sk_noise < 0.02, sk_noise
    mem.close()


# ------------------------------------------------------------------ (e) lista negra
@pytest.mark.parametrize("mode", P.MODES)
def test_e_no_forbidden_columns(full, forbidden, mode):
    X, lin, _ = full[mode]
    R.assert_no_forbidden(X.columns, extra=forbidden)
    R.assert_no_forbidden(X.columns)                      # también con el meta.json oficial
    assert not set(X.columns) & set(R.LABEL_COLUMNS)
    assert not any(str(c).startswith(("pers_", "label", "p_")) for c in X.columns)
    used = set(lin["series_id"])
    assert not used & (set(forbidden) | {"USREC"})
    assert set(X.columns) == set(P.public_columns(P.load_whitelist()))   # solo la lista blanca


def test_e_builder_rejects_forbidden(con, grid, forbidden):
    cal = load_calendar()
    cal["USREC"] = CalEntry("USREC", "M", "fin_periodo", ((pd.Timestamp("1900-01-01"), 400),), (), (), True, "", "")
    wl = P.load_whitelist()
    g = grid.tail(3)
    bad = {**wl, "variables": [{"nombre": "recesion", "tipo": "serie", "series": ["USREC"],
                                "transformacion": {"fn": "level"}, "modo": "latest_truncated"}]}
    with pytest.raises(AssertionError):
        P.build_matrix(con, "latest_truncated", g, wl=bad, cal=cal, forbidden=forbidden)
    derived = {**wl, "variables": [wl["variables"][0],
                                   {"nombre": "usrec_lag1", "tipo": "derivada", "funcion": "diff3",
                                    "entradas": [wl["variables"][0]["nombre"]]}]}
    with pytest.raises(AssertionError):
        P.build_matrix(con, "latest_truncated", g, wl=derived, forbidden=forbidden)


# ------------------------------------------------------------------ (f) forecast / lookahead
def test_f_only_observed_series(con, full):
    wl, cal = P.load_whitelist(), load_calendar()
    sids = P.needed_series(wl, cal)
    roles = dict(con.execute("select series_id, pit_role from catalog where series_id in (select unnest(?))",
                             [sids]).fetchall())
    assert set(roles) == set(sids)
    assert {r for r in roles.values()} == {"observed"}, roles
    for mode in P.MODES:
        assert set(full[mode][1]["series_id"]) <= set(sids)
    # expectativas: solo encuestas fechadas en su publicación (SPF anclada al inicio del trimestre + retardo)
    spf = [s for s in sids if s.startswith("spf_")]
    assert spf and all(cal[s].anchor == "inicio_periodo" and min(d for _, d in cal[s].lags) >= 45 for s in spf)


def test_f_builder_rejects_forecast_series(con, grid, forbidden):
    cal = load_calendar()
    cal["GDPPOT"] = CalEntry("GDPPOT", "Q", "fin_periodo", ((pd.Timestamp("1900-01-01"), 30),), (), (), True, "", "")
    wl = {**P.load_whitelist(), "variables": [{"nombre": "potencial", "tipo": "serie", "series": ["GDPPOT"],
                                               "transformacion": {"fn": "level"}, "modo": "latest_truncated"}]}
    with pytest.raises(AssertionError):
        P.build_matrix(con, "latest_truncated", grid.tail(3), wl=wl, cal=cal, forbidden=forbidden)


# ------------------------------------------------------------------ calendario y lista blanca
def test_calendar_fallback_lags_cover_measured():
    """El retardo de reserva (fechas sin vintages) no es menor que el p90 medido en la época más antigua."""
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
        assert e.lags[0][1] >= earliest["p90"], (sid, e.lags, earliest.to_dict())


def test_whitelist_documented():
    wl = P.load_whitelist()
    cal = load_calendar()
    estados = {"principal", "principal_epoca", "modulo_adicional", "condicional", "auxiliar"}
    for v in wl["variables"]:
        assert v["estado"] in estados, v["nombre"]
        assert v.get("mecanismo"), v["nombre"]
        if not v["nombre"].startswith("_"):
            assert {"fuente_viva", "historia", "pit", "disponibilidad"} <= set(v["admision"]), v["nombre"]
        if v["tipo"] == "serie":
            assert all(s in cal for s in v["series"]), v["nombre"]
            assert v["transformacion"]["fn"] in P.TRANSFORMS
            assert v["modo"] in P.MODES
        else:
            assert v["funcion"] in P.DERIVED
