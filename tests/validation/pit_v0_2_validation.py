"""Validador independiente: re-auditoría de la base point-in-time v0.2 (docs/validation/2026-10-15_pit_base_v0.2.md).

NO importa src.features: lee la instantánea congelada (parquet) con DuckDB y aplica a mano el calendario y las
transformaciones. Solo fechas de decisión y valores de variables; la etiqueta no se toca.
Ejecutar: .venv/bin/python tests/validation/pit_v0_2_validation.py
"""
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yaml

ROOT = Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive"))) / "features"
IN = ROOT / "inputs"
SNAP = IN / "pit_us_v0.2_inputs.parquet"
X = {m: pd.read_parquet(ROOT / f"pit_us_v0.2_{m}.parquet").set_index("decision_date")
     for m in ("vintage", "latest_truncated", "vintage_filadelfia_prudente")}
L = {m: pd.read_parquet(ROOT / f"pit_us_v0.2_{m}_lineage.parquet") for m in X}
wl = yaml.safe_load((IN / "pit_us_v0.2_whitelist.yaml").read_text())
cal = yaml.safe_load((IN / "pit_us_v0.2_calendar.yaml").read_text())["series"]
con = duckdb.connect()
con.execute(f"create view snap as select * from read_parquet('{SNAP}')")
print("0) sha256 instantánea", hashlib.sha256(SNAP.read_bytes()).hexdigest()[:16],
      con.execute("select kind, count(*), count(distinct series_id) from snap group by 1 order by 1").fetchall())

pub = [v for v in wl["variables"] if not v["nombre"].startswith("_")]
byname = {v["nombre"]: v for v in wl["variables"]}
print("0) públicas", len(pub), Counter(v["estado"] for v in pub), "| con principal_desde",
      sum(1 for v in pub if v.get("principal_desde")), "| aux", len(wl["variables"]) - len(pub),
      "| rechazadas", len(wl["rechazadas"]), "| series calendario", len(cal))


# ------------------------------------------------------------------ calendario independiente
def pend(d, f):
    d = pd.DatetimeIndex(d)
    if f == "M":
        return d + pd.offsets.MonthEnd(0)
    if f == "Q":
        return d + pd.offsets.QuarterEnd(0)
    return d


def lag_days(sid, d, variant=False):
    tr = sorted((pd.Timestamp(str(x["desde"])), x["dias"])
                for x in cal[sid]["retardo_dias_prudente" if variant and "retardo_dias_prudente" in cal[sid]
                                  else "retardo_dias"])
    out = np.full(len(d), tr[0][1])
    for since, days in tr[1:]:
        out[np.asarray(d >= since)] = days
    return out


_fr = {}


def first_release(sid):
    if sid not in _fr:
        df = con.execute("""select date, min(realtime_start) rs from snap where kind='vintage' and series_id=?
                            and value is not null group by 1""", [sid]).df()
        s0 = con.execute("select min(realtime_start) from snap where kind='vintage' and series_id=?", [sid]).fetchone()[0]
        _fr[sid] = (pd.Series(pd.to_datetime(df["rs"]).to_numpy(), index=pd.to_datetime(df["date"])).sort_index(),
                    None if s0 is None else pd.Timestamp(s0))
    return _fr[sid]


def avail(sid, idx, variant=False):
    # regla 5: una observación cuenta como disponible cuando lo están también todas las ANTERIORES
    return pd.Series(np.maximum.accumulate(pub_raw(sid, idx, variant).to_numpy()), index=idx)


def pub_raw(sid, idx, variant=False):
    e = cal[sid]
    f = e["frecuencia"]
    idx = pd.DatetimeIndex(idx)
    anchor = idx if (f in ("D", "W") or e.get("ancla") == "inicio_periodo") else pend(idx, f)
    calp = pd.Series(anchor + pd.to_timedelta(lag_days(sid, idx, variant), unit="D"), index=idx)
    best = pd.Series(pd.NaT, index=idx, dtype="datetime64[ns]")
    covered = pd.Series(False, index=idx)
    for p in e.get("proxies_publicacion") or []:
        r, s0 = first_release(p)
        if r.empty:
            continue
        rr = pd.Series(r.reindex(idx).to_numpy(), index=idx)
        real = rr.notna() & (rr != s0) & ((rr - pd.Series(anchor, index=idx)).dt.days <= 200)
        cand = rr.where(real, pd.concat([calp, rr], axis=1).min(axis=1)).where(rr.notna())
        best = best.where(best.notna() & (cand.isna() | (best <= cand)), cand)
        covered |= pd.Series(idx >= r.index.min(), index=idx)
    best = best.where(best.notna() | covered, calp).fillna(pd.Timestamp("2262-01-01"))
    if f in ("M", "Q") and e.get("ancla", "fin_periodo") == "fin_periodo" and min(lag_days(sid, idx, variant)) >= 0:
        floor = pd.Series(anchor + pd.Timedelta(days=1), index=idx)
        best = best.where(best >= floor, floor)
    return best


def latest(sid):
    df = con.execute("select date, value from snap where kind='latest' and series_id=? order by date", [sid]).df()
    return pd.Series(df["value"].to_numpy(), index=pd.to_datetime(df["date"]))


def vintage_series(sid, t):
    df = con.execute("""select date, value, realtime_start from snap where kind='vintage' and series_id=?
                        and realtime_start <= ? order by realtime_start""", [sid, t]).df()
    df = df.drop_duplicates("date", keep="last").dropna(subset=["value"])
    s = pd.Series(df["value"].to_numpy(), index=pd.to_datetime(df["date"])).sort_index()
    f = cal[sid]["frecuencia"] if sid in cal else "M"
    return s[pend(s.index, f) + pd.Timedelta(days=1) <= t] if f in ("M", "Q") else s


def transform(s, spec, freq):
    s = s.dropna()
    fr = {"M": "MS", "Q": "QS"}.get(freq)
    if fr and len(s) > 2:
        s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq=fr))
    ppy = {"D": 252, "W": 52, "M": 12, "Q": 4}[freq]
    t = spec["transformacion"]
    fn, k, n = t["fn"], t.get("k"), t.get("n")
    if fn == "level":
        return s
    if fn == "log_diff":
        return 100 * np.log(s / s.shift(k))
    if fn == "log_diff_ann":
        return 100 * np.log(s / s.shift(k)) * ppy / k
    if fn == "pct_ann":
        return ((s / s.shift(k)) ** (ppy / k) - 1) * 100
    if fn == "diff":
        return s - s.shift(k)
    if fn == "rolling_mean":
        return s.rolling(n).mean()
    if fn == "rolling_log_yoy":
        m = s.rolling(n).mean()
        return 100 * np.log(m / m.shift(ppy))
    return None


# ------------------------------------------------------------------ 1. celdas al azar: fecha de la observación y valor
rng = np.random.default_rng(20261015)
res = []
for mode in ("vintage", "latest_truncated"):
    for spec in pub:
        if spec["tipo"] != "serie" or spec["transformacion"]["fn"] == "sahm":
            continue
        col = spec["nombre"]
        xs = X[mode][col]
        ts = xs.dropna().index
        ts = ts[ts <= pd.Timestamp("2026-09-30")]
        if len(ts) == 0:
            continue
        for t in rng.choice(ts, size=min(12, len(ts)), replace=False):
            t = pd.Timestamp(t)
            got = xs.loc[t]
            mine, mine_d, how = np.nan, None, None
            for sid in spec["series"]:      # empalme por prioridad
                f = cal[sid]["frecuencia"]
                vs = (cal[sid].get("vintages") or []) if (mode == "vintage" and spec["modo"] == "vintage") else []
                v0 = next((v for v in vs if first_release(v)[1] is not None and first_release(v)[1] <= t), None)
                if v0 is not None:
                    s = vintage_series(v0, t)
                    s = s[s.index >= t - pd.DateOffset(years=6)]
                    how = f"vintage:{v0}"
                else:
                    s = latest(sid)
                    if s.empty:
                        continue
                    a = avail(sid, s.index)
                    s = s[(a <= t).to_numpy()]
                    how = "latest_truncated"
                x = transform(s * float(spec.get("factor", 1.0)), spec, f)
                if x is None:
                    break
                x = x.dropna()
                if x.empty:
                    continue
                d = x.index[-1]
                pe = d if f in ("D", "W") else pend([d], f)[0]
                stale = {"D": 45, "W": 45, "M": 130, "Q": 280}[f]
                if (t - pe).days > stale:
                    continue
                mine, mine_d = float(x.iloc[-1]), d
                break
            if spec.get("desde") and t < pd.Timestamp(str(spec["desde"])):
                mine = np.nan
            res.append(dict(mode=mode, col=col, t=t, how=how, obs=mine_d, mine=mine, theirs=float(got)))
Rz = pd.DataFrame(res)
Rz["ok"] = np.isclose(Rz["mine"], Rz["theirs"], rtol=1e-9, atol=1e-9, equal_nan=True)
print(f"1) celdas recalculadas (SQL sobre la instantánea, sin src.features): {len(Rz)}; coinciden {int(Rz['ok'].sum())};"
      f" columnas {Rz['col'].nunique()}; ≤2004: {(Rz['t'] <= '2004-12-31').sum()}")
if (~Rz["ok"]).any():
    print(Rz[~Rz["ok"]].to_string()[:4000])
# fecha de la observación frente al linaje
lchk = 0
for _, r in Rz[Rz["ok"] & Rz["obs"].notna()].iterrows():
    li = L[r["mode"]]
    li = li[(li["column"] == r["col"]) & (li["decision_date"] == r["t"])]
    lchk += int(pd.Timestamp(li["obs_date"].iloc[0]) == r["obs"]) if len(li) else 0
print("   fecha de observación igual al linaje:", lchk, "de", int((Rz["ok"] & Rz["obs"].notna()).sum()))

# ------------------------------------------------------------------ 2. linaje: nada posterior a t; vintage publicado ≤ t
for m in L:
    lin = L[m]
    od, t = pd.to_datetime(lin["obs_date"]), pd.to_datetime(lin["decision_date"])
    v = lin[lin["mode"].str.startswith("vintage:")]
    bad = 0
    for vs, g in v.groupby(v["mode"].str.slice(8)):
        r, _ = first_release(vs)
        rs = r.reindex(pd.to_datetime(g["obs_date"])).to_numpy()
        bad += int((pd.to_datetime(rs) > pd.to_datetime(g["decision_date"]).to_numpy()).sum())
    lt = lin[~lin["mode"].str.startswith("vintage:")].drop_duplicates(["decision_date", "series_id", "obs_date"])
    late = 0
    for sid, g in lt.groupby("series_id"):
        variant = m == "vintage_filadelfia_prudente"
        a = pub_raw(sid, latest(sid).dropna().index, variant)
        late += int((a.reindex(pd.to_datetime(g["obs_date"])).to_numpy() > pd.to_datetime(g["decision_date"]).to_numpy()).sum())
    print(f"2) {m}: obs_date > t: {int((od > t).sum())} | vintage con 1.ª publicación > t: {bad} | "
          f"latest_truncated con publicación (calendario propio) > t: {late}")

# ------------------------------------------------------------------ 3. principal_desde: ¿alguna entrada condicional se cuela?
def ancestors(name, seen=None):
    seen = set() if seen is None else seen
    v = byname[name]
    if v["tipo"] == "derivada":
        for e in v["entradas"]:
            if e not in seen:
                seen.add(e)
                ancestors(e, seen)
    return seen


def pdesde(name):
    v = byname[name]
    return pd.Timestamp(str(v["principal_desde"])) if v.get("principal_desde") else None


core_series = {"CPILFESL", "CUSR0000SASLE", "PCEPILFE", "M2SL", "fed_ebp_gz_spread", "fed_ebp_ebp", "NFCI", "CFNAI"}
for v in pub:
    if v["estado"] not in ("principal", "principal_epoca"):
        continue
    mine = pdesde(v["nombre"])
    anc = ancestors(v["nombre"])
    for a in anc:
        pa = pdesde(a)
        if pa and (mine is None or mine < pa):
            print(f"3) {v['nombre']} ({v['estado']}, principal_desde={mine}) usa {a} (principal_desde={pa.date()})")
    sers = {s for a in anc | {v['nombre']} for s in (byname[a].get("series") or [])}
    if sers & core_series and mine is None:
        print(f"3) {v['nombre']}: series {sorted(sers & core_series)} sin principal_desde")

# ------------------------------------------------------------------ 4. calendario: supuestos prudentes en el linaje
def gap_days(lin, col, sid=None):
    x = lin[lin["column"] == col]
    if sid:
        x = x[x["series_id"] == sid]
    return x, (pd.to_datetime(x["decision_date"]) - pd.to_datetime(x["obs_date"])).dt.days


lin = L["vintage"]
for col, sid, until, f, mind in [("spf_rgdp_4q", "spf_mean_rgdp_6", "1990-07-01", "start", 90),
                                 ("spf_anxious", "spf_anxious_index", "1990-07-01", "start", 90),
                                 ("cmrmtspl_3m_ann", "CMRMTSPL", "2000-01-01", "end", 90),
                                 ("usd_neer_yoy", "bis_eer_us_neer_narrow_m", "2100-01-01", "end", 20),
                                 ("umcsent", "umich_ics", "2100-01-01", "end", 20),
                                 ("mich_infl_exp", "umich_px1_md", "2100-01-01", "end", 20)]:
    x = lin[(lin["column"] == col) & (lin["series_id"] == sid)]
    x = x[pd.to_datetime(x["obs_date"]) < pd.Timestamp(until)]
    od = pd.to_datetime(x["obs_date"])
    anc = od if f == "start" else od + pd.offsets.MonthEnd(0)
    d = (pd.to_datetime(x["decision_date"]) - anc).dt.days
    print(f"4) {col} ({sid}, obs < {until}): mín días ancla→t = {d.min()} (exigido ≥ {mind}); n = {len(d)}")
x = L["latest_truncated"]
e = x[x["series_id"] == "ecb_eurosystem_total_assets_w"].drop_duplicates("decision_date")
dd = (pd.to_datetime(e["decision_date"]) - pd.to_datetime(e["obs_date"])).dt.days
print("4) BCE: días semana→t mín", dd.min(), "| día de la semana de la fecha:",
      Counter(pd.to_datetime(e["obs_date"]).dt.dayofweek))
for m in ("vintage", "vintage_filadelfia_prudente"):
    x = L[m]
    x = x[x["column"] == "philly_activity"]
    k = ((pd.to_datetime(x["decision_date"]).dt.to_period("M") - pd.to_datetime(x["obs_date"]).dt.to_period("M"))
         .apply(lambda p: p.n))
    pre = pd.to_datetime(x["obs_date"]) < "1990-07-01"
    print(f"4) Filadelfia {m}: meses t−obs antes de 1990-07 {Counter(k[pre])} | después {Counter(k[~pre])}")
diffcols = [c for c in X["vintage"] if not np.allclose(X["vintage"][c].to_numpy(float),
                                                         X["vintage_filadelfia_prudente"][c].to_numpy(float),
                                                         equal_nan=True)]
print("   columnas que cambian con la variante prudente:", diffcols)

# ------------------------------------------------------------------ 5. derivadas recalculadas a mano (desde columnas públicas)
for m in ("vintage", "latest_truncated"):
    D = X[m]
    out = {}
    # infl_core_pressure / headline_minus_core / core_cpi_dir
    parts = pd.concat([D["core_cpi_6m_ann"], D["core_services_cpi_6m_ann"], D["ahe_yoy"] - 1.5], axis=1)
    out["infl_core_pressure"] = parts.mean(axis=1).where(parts.notna().sum(axis=1) >= 2)
    out["headline_minus_core_6m"] = D["headline_cpi_6m_ann"] - D["core_cpi_6m_ann"]
    out["core_cpi_dir"] = D["core_cpi_6m_ann"] - D["core_cpi_6m_ann"].shift(6)

    def zexp(s):
        return (s - s.expanding(120).mean()) / s.expanding(120).std()
    z = pd.concat([zexp(D["oil_yoy"]), zexp(D["ppi_yoy"]), zexp(D["headline_minus_core_6m"])], axis=1)
    out["infl_energy_pressure"] = z.mean(axis=1).where(z.notna().sum(axis=1) >= 2)
    # growth_rt: (g − mediana de 120 meses hasta t) / (1,4826·MAD expansiva, ≥ 60)
    zs = []
    for c in ("indpro_3m_ann", "payems_3m_ann", "w875rx1_3m_ann", "cmrmtspl_3m_ann"):
        g = D[c].to_numpy()
        dev = np.full(len(g), np.nan)
        for i in range(len(g)):
            w = g[max(0, i - 119):i + 1]
            if np.isfinite(w).sum() >= 108:
                dev[i] = g[i] - np.nanmedian(w)
        mad = np.full(len(g), np.nan)
        for i in range(len(g)):
            a = dev[:i + 1]
            if np.isfinite(a).sum() >= 60:
                mad[i] = np.nanmedian(np.abs(a - np.nanmedian(a)))
        zs.append(dev / (1.4826 * mad))
    Z = np.vstack(zs).T
    out["growth_rt"] = pd.Series(np.where(np.isfinite(Z).sum(axis=1) >= 2, np.nanmean(np.where(np.isfinite(Z), Z, np.nan), axis=1), np.nan), index=D.index)
    # histéresis
    g, sh = D["growth_rt"], D["unrate_sahm"]
    band = 0.5 * g.expanding(60).std()
    st, up, dn, o = 0.0, 0, 0, []
    for gv, bv, sv in zip(g, band, sh):
        if not (np.isfinite(gv) and np.isfinite(bv)):
            o.append(np.nan); up = dn = 0; continue
        up = up + 1 if gv > bv else 0
        dn = dn + 1 if gv < -bv else 0
        if np.isfinite(sv) and sv >= 0.5:
            st = -1.0
        elif up >= 2:
            st = 1.0
        elif dn >= 2:
            st = -1.0
        o.append(st)
    out["growth_rt_state"] = pd.Series(o, index=D.index)
    for c, s in out.items():
        ok = np.isclose(s.to_numpy(float), D[c].to_numpy(float), rtol=1e-9, atol=1e-9, equal_nan=True)
        print(f"5) {m} {c}: {int(ok.sum())}/{len(ok)} iguales")

# curva en 4 estados desde la instantánea (DGS10/DTB3 con retardo de 1 día; GS10/TB3MS mensuales antes)
def daily_at(sid, ts, lag=1):
    s = latest(sid).dropna()
    s.index = s.index + pd.Timedelta(days=lag)
    return s.reindex(s.index.union(ts)).ffill().reindex(ts)


def monthly_at(sid, ts):
    s = latest(sid).dropna()
    av = s.index + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1)
    s = pd.Series(s.to_numpy(), index=av)
    return s.reindex(s.index.union(ts)).ffill().reindex(ts)


ts = X["vintage"].index
d10 = daily_at("DGS10", ts).combine_first(monthly_at("GS10", ts))
d3 = daily_at("DTB3", ts).combine_first(monthly_at("TB3MS", ts))
s10, s3 = d10.diff(3), d3.diff(3)
dc = s10 - s3
leg = s10.where(s10.abs() >= s3.abs(), s3)
mine = {"curve_bear_steep": (dc > .25) & (leg > 0), "curve_bull_steep": (dc > .25) & (leg <= 0),
        "curve_bear_flat": (dc < -.25) & (leg > 0), "curve_bull_flat": (dc < -.25) & (leg <= 0)}
okmask = s10.notna() & s3.notna()
for c, s in mine.items():
    a = s.astype(float).where(okmask)
    ok = np.isclose(a.to_numpy(float), X["vintage"][c].to_numpy(float), equal_nan=True)
    print(f"5) {c}: {int(ok.sum())}/{len(ok)} iguales; frecuencia ≤2004 {X['vintage'].loc[:'2004-12-31', c].mean():.3f}")
st = X["vintage"][list(mine)].loc[:"2004-12-31"].sum(axis=1)
print("   meses con más de un estado activo:", int((st > 1).sum()))
gs = X["vintage"]["growth_rt_state"].loc[:"2004-12-31"].dropna()
print("   growth_rt_state cambios/año ≤2004:", round((gs.diff().fillna(0) != 0).sum() / (len(gs) / 12), 3),
      "| primer valor", gs.index.min().date())
