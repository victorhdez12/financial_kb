"""Validador independiente: base point-in-time v0.1 (docs/validation/2026-10-15_pit_base_v0.1.md).
No importa src.features para recalcular: lee observations con SQL y aplica las transformaciones a mano.
Ejecutar: .venv/bin/python tests/validation/pit_v0_1_validation.py"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd, yaml
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.warehouse import db

con = db.connect()
FD = db.DATA_ROOT / "features"
X = {m: pd.read_parquet(FD / f"pit_us_v0.1_{m}.parquet").set_index("decision_date") for m in ("vintage", "latest_truncated")}
L = {m: pd.read_parquet(FD / f"pit_us_v0.1_{m}_lineage.parquet") for m in X}
wl = yaml.safe_load((REPO / "research/pit_whitelist.yaml").read_text())
cal = yaml.safe_load((REPO / "research/pit_calendar.yaml").read_text())["series"]

# ---------------------------------------------------------------- 0. recuentos
pub = [v for v in wl["variables"] if not v["nombre"].startswith("_")]
from collections import Counter
print("0) públicas", len(pub), Counter(v["estado"] for v in pub), "aux", len(wl["variables"]) - len(pub),
      "rechazadas", len(wl["rechazadas"]), "series calendario", len(cal))

# ---------------------------------------------------------------- 1. recálculo a mano de valores
def pe(d, f):
    d = pd.DatetimeIndex(d)
    return d + (pd.offsets.MonthEnd(0) if f == "M" else pd.offsets.QuarterEnd(0)) if f in "MQ" else d

def tf(s, spec):
    s = s.dropna()
    f = {"M": "MS", "Q": "QS"}.get(cal[spec["series"][0]]["frecuencia"])
    if f and len(s) > 2:
        full = pd.date_range(s.index.min(), s.index.max(), freq=f)
        if s.index.isin(full).all(): s = s.reindex(full)
    ppy = {"D": 252, "W": 52, "M": 12, "Q": 4}[cal[spec["series"][0]]["frecuencia"]]
    t = spec["transformacion"]; fn = t["fn"]
    if fn == "level": return s
    if fn == "log_diff": return 100 * np.log(s / s.shift(t["k"]))
    if fn == "log_diff_ann": return 100 * np.log(s / s.shift(t["k"])) * ppy / t["k"]
    if fn == "pct_ann": return ((s / s.shift(t["k"])) ** (ppy / t["k"]) - 1) * 100
    if fn == "diff": return s - s.shift(t["k"])
    if fn == "rolling_mean": return s.rolling(t["n"]).mean()
    if fn == "rolling_log_yoy":
        m = s.rolling(t["n"]).mean(); return 100 * np.log(m / m.shift(ppy))
    if fn == "sahm":
        m3 = s.rolling(3).mean(); return m3 - m3.rolling(12).min().shift(1) if False else None
    return None

rng = np.random.default_rng(15)
res = []
for mode in X:
    lin = L[mode]
    for spec in pub:
        if spec["tipo"] != "serie" or spec["transformacion"]["fn"] == "sahm": continue
        lc = lin[lin["column"] == spec["nombre"]]
        if lc.empty: continue
        samp = lc.sample(min(12, len(lc)), random_state=int(rng.integers(1e6)))
        for _, r in samp.iterrows():
            t, sid, md = pd.Timestamp(r["decision_date"]), r["series_id"], r["mode"]
            if md.startswith("vintage:"):
                vs = md[8:]
                v = con.execute("""select date, value, realtime_start from observations where series_id=? and
                     realtime_start is not null and realtime_start <= ? order by realtime_start""", [vs, t]).df()
                v = v.drop_duplicates("date", keep="last").dropna(subset=["value"])
                s = pd.Series(v["value"].values, index=pd.to_datetime(v["date"])).sort_index()
                s = s[s.index >= t - pd.DateOffset(years=6)]
            else:
                s = db.series(con, sid)
            s = s * float(spec.get("factor", 1.0))
            s = s[s.index <= pd.Timestamp(r["obs_date"])]
            x = tf(s, spec)
            if x is None or x.dropna().empty: continue
            val = x.dropna()
            ok_date = val.index[-1] == pd.Timestamp(r["obs_date"])
            got = X[mode].loc[t, spec["nombre"]]
            res.append(dict(mode=mode, col=spec["nombre"], t=t, obs=r["obs_date"], src=md,
                            mine=float(val.iloc[-1]), theirs=float(got), date_ok=ok_date))
R = pd.DataFrame(res)
R["ok"] = np.isclose(R["mine"], R["theirs"], rtol=1e-9, atol=1e-9) & R["date_ok"]
print("1) celdas recalculadas", len(R), "coinciden", int(R["ok"].sum()))
print(R[~R["ok"]].to_string()[:3000])

# ---------------------------------------------------------------- 2. ¿se usa la última observación publicada? (vintage)
lt = L["vintage"]; lt = lt[lt["mode"].str.startswith("vintage:")].drop_duplicates(["decision_date", "series_id"])
fr = con.execute("""select series_id, date, min(realtime_start) rs from observations where realtime_start is not null
                    and value is not null group by 1,2""").df()
fr["date"] = pd.to_datetime(fr["date"]); fr["rs"] = pd.to_datetime(fr["rs"])
late = 0; early = 0
for (vsid), g in lt.assign(vs=lt["mode"].str.slice(8)).groupby("vs"):
    f = fr[fr["series_id"] == vsid].set_index("date")["rs"].sort_index()
    fq = cal.get(vsid, cal.get(g["series_id"].iloc[0]))["frecuencia"]
    for _, r in g.iterrows():
        t = pd.Timestamp(r["decision_date"])
        known = f[(f <= t) & (pe(f.index, fq) + pd.Timedelta(days=1) <= t)]
        if len(known) and known.index.max() > pd.Timestamp(r["obs_date"]): early += 1
        if pd.Timestamp(r["obs_date"]) in f.index and f[pd.Timestamp(r["obs_date"])] > t: late += 1
print("2) vintage: celdas con obs no publicada en t", late, "| celdas que no usan la última publicada", early)

# ---------------------------------------------------------------- 3. ALFRED con realtime_start <= fin de periodo (suelo)
for sid in ["PAYEMS", "UNRATE", "INDPRO", "CPIAUCSL", "M2SL", "TCU", "PPIACO"]:
    f = fr[fr["series_id"] == sid].set_index("date")["rs"]
    bad = f[f <= pe(f.index, "M")]
    print(f"3) {sid}: {len(bad)} obs con primera publicación ≤ fin de su mes",
          (bad.index.min().date(), bad.index.max().date()) if len(bad) else "")

# ---------------------------------------------------------------- 4. BCE: convención de fecha semanal
e = db.series(con, "ecb_eurosystem_total_assets_w")
print("4) BCE día de la semana de la fecha:", Counter(e.index.dayofweek))
lb = L["latest_truncated"]; lb = lb[lb["series_id"] == "ecb_eurosystem_total_assets_w"].drop_duplicates("decision_date")
ref = pd.to_datetime(lb["obs_date"]) + pd.Timedelta(days=4)          # viernes de referencia
real = ref + pd.offsets.Week(weekday=1)                                # martes siguiente
n_bad = int((real > pd.to_datetime(lb["decision_date"])).sum())
print(f"   celdas con publicación real (martes tras el viernes) > t: {n_bad} de {len(lb)}")

# ---------------------------------------------------------------- 5. huecos internos (patrón de disponibilidad) <= 2004
for m in X:
    xx = X[m][X[m].index <= "2004-12-31"]
    gaps = {}
    for c in xx:
        s = xx[c]; fv = s.first_valid_index()
        if fv is None: continue
        n = int(s[fv:].isna().sum())
        if n: gaps[c] = n
    print(f"5) {m}: columnas con NaN internos ≤2004:", gaps)
cv = (X["vintage"] - X["latest_truncated"]).abs()
print("   celdas distintas vintage vs latest ≤2004:", int((cv[cv.index <= "2004-12-31"] > 1e-9).sum().sum()))

# ---------------------------------------------------------------- 6. no hay datos posteriores a t por construcción del linaje
for m in X:
    lin = L[m]; od = pd.to_datetime(lin["obs_date"]); t = pd.to_datetime(lin["decision_date"])
    print(f"6) {m}: obs_date > t:", int((od > t).sum()), "| filas linaje", len(lin))
