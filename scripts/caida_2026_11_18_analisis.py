"""Análisis puntual (18-nov-2026): caída del oro y las bolsas frente a su volatilidad, correlaciones, volumen,
episodios parecidos y lo que dicen los modelos del proyecto. DESCRIPTIVO, no validado, no es asesoramiento.

Lee: $FIN_DATA_ROOT/mercados/intradia/<fecha>/ (scripts/caida_2026_11_18_descarga.py), el warehouse (solo lectura),
el signal del 17-nov y los parámetros congelados de B1′ (solo lectura). NO escribe en ningún registro
(research/**/*.jsonl) ni toca modelos congelados: B1/B1′ se recalculan aquí como ENSAYO en memoria.
Escribe: gráficos en obsidian/Reports/img/2026-11-18_*.png y cifras agregadas en un JSON (ruta del 1.er argumento,
por defecto fuera del repo en $FIN_DATA_ROOT/mercados/intradia/<fecha>/resultados.json).
Uso: .venv/bin/python -m scripts.caida_2026_11_18_analisis   (desde la raíz del repo)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FECHA = "2026-11-18"
ULT_US = pd.Timestamp("2026-11-17")      # último cierre completo de EE. UU.
HOY = pd.Timestamp(FECHA)
DIR = Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser() / "mercados" / "intradia" / FECHA
IMG = REPO / "obsidian" / "Reports" / "img"
SIGNAL = REPO / "obsidian" / "Reports" / "2026-11-17_signal.json"
# paleta validada (dataviz; mismo orden que scripts/atlas_graficas.py)
AZUL, NARANJA, AQUA, AMARILLO = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
TINTA, GRIS, GRIS_SUAVE, SUP = "#0b0b0b", "#52514e", "#b9b8b2", "#fcfcfb"
ROJO = "#d03b3b"
TIPOS = {"^TNX", "^IRX"}                 # rentabilidades: se miran cambios en pb, no %

plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRIS_SUAVE, "axes.labelcolor": GRIS, "xtick.color": GRIS,
                     "ytick.color": GRIS, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SUP, "axes.facecolor": SUP, "savefig.facecolor": SUP,
                     "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6})


def r_(x, n=2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


# ------------------------------------------------------------------------------------------------ datos
def cargar():
    P = pd.read_parquet(DIR / "diario.parquet")
    V = pd.read_parquet(DIR / "volumen.parquet")
    I = pd.read_parquet(DIR / "intradia_5m.parquet")
    meta = json.loads((DIR / "meta.json").read_text())
    return P, V, I, meta


def cambios(s: pd.Series, t: str) -> pd.Series:
    s = s.dropna()
    s = s[s > 0] if t not in TIPOS else s
    return (s.diff() * 100 if t in TIPOS else np.log(s).diff()).dropna()   # ^TNX/^IRX vienen en %: Δ·100 = pb


# ------------------------------------------------------------------------------------------------ 1. tamaño
def tamano(P: pd.DataFrame, meta: dict) -> list[dict]:
    """Por activo: movimiento del 17-nov (cierre EE. UU.) y del 18-nov (si hay sesión hoy, parcial) en % (pb en tipos),
    en desviaciones típicas (σ diaria de las 252 sesiones previas y de las 60 previas) y percentil histórico del
    movimiento diario (toda la historia disponible del ticker, excluida la fecha medida)."""
    out = []
    for t in P.columns:
        s = P[t].dropna()
        if len(s) < 300:
            continue
        c = cambios(s, t)
        fila = {"ticker": t, "nombre": meta["activos"][t]["nombre"], "grupo": meta["activos"][t]["grupo"],
                "ultimo": r_(s.iloc[-1], 4), "fecha_ultimo": str(s.index[-1].date()), "desde": str(s.index[0].date()),
                "unidad": "pb" if t in TIPOS else "%"}
        for etq, f in (("d17", ULT_US), ("d18", HOY)):
            if f not in c.index:
                continue
            x = float(c.loc[f])
            prev = c[c.index < f]
            s252, s60 = float(prev.iloc[-252:].std()), float(prev.iloc[-60:].std())
            val = x if t in TIPOS else 100 * np.expm1(x)
            fila[etq] = {"mov": r_(val), "z252": r_(x / s252), "z60": r_(x / s60),
                         "pct_hist": r_(100 * float((prev <= x).mean()), 1), "n_hist": int(len(prev))}
        base = c[c.index <= HOY]
        k5 = base.iloc[-5:].sum()
        k20 = base.iloc[-20:].sum()
        sd = float(base.iloc[-257:-5].std())
        fila["r5"] = r_(k5 if t in TIPOS else 100 * np.expm1(k5))
        fila["z5"] = r_(k5 / (sd * np.sqrt(5)))
        fila["r20"] = r_(k20 if t in TIPOS else 100 * np.expm1(k20))
        if t not in TIPOS:
            w = s[s.index > s.index[-1] - pd.DateOffset(weeks=52)]
            fila["dd52"] = r_(100 * (s.iloc[-1] / w.max() - 1), 1)
            fila["vol_1a"] = r_(100 * float(base.iloc[-252:].std() * np.sqrt(252)), 1)
        out.append(fila)
    return out


# ------------------------------------------------------------------------------------------------ 2. amplitud
def amplitud(tab: list[dict]) -> dict:
    T = {x["ticker"]: x for x in tab}
    sect = [t for t in T if t.startswith("XL")]
    d = {t: T[t]["d17"]["mov"] for t in sect if "d17" in T[t]}
    reg = [t for t in ("^GSPC", "^NDX", "^RUT", "^STOXX50E", "^GDAXI", "^IBEX", "^FTSE", "^N225", "^HSI", "^KS11",
                       "000001.SS", "EEM") if t in T]
    return {"sectores_17nov": d, "sectores_bajan": int(sum(v < 0 for v in d.values())), "sectores_n": len(d),
            "sectores_r5": {t: T[t]["r5"] for t in sect},
            "regiones": {t: {"nombre": T[t]["nombre"], "d17": T[t].get("d17"), "d18": T[t].get("d18"),
                             "r5": T[t]["r5"]} for t in reg}}


# ------------------------------------------------------------------------------------------------ 3. correlaciones
def correlaciones(P: pd.DataFrame, con) -> tuple[dict, pd.DataFrame]:
    from src.warehouse import db
    dfii = db.series(con, "DFII10").dropna()
    X = pd.DataFrame({
        "oro": np.log(P["GLD"].dropna()).diff(), "bolsa": np.log(P["SPY"].dropna()).diff(),
        "dolar": np.log(P["DX-Y.NYB"].dropna()).diff(), "tipo10": P["^TNX"].dropna().diff() * 100,
        "tipo_real": dfii.diff() * 100, "bonos": np.log(P["TLT"].dropna()).diff(),
    }).loc["2007-01-01":ULT_US].dropna(subset=["oro", "bolsa"])
    pares = [("oro", "bolsa"), ("oro", "dolar"), ("oro", "tipo_real"), ("oro", "tipo10"), ("bolsa", "tipo10"),
             ("bolsa", "bonos")]
    roll, res = {}, {}
    for a, b in pares:
        Z = X[[a, b]].dropna()
        rc = Z[a].rolling(60, min_periods=50).corr(Z[b]).dropna()
        roll[f"{a}-{b}"] = rc
        ult = float(rc.iloc[-1])
        z20 = Z.iloc[-20:]
        res[f"{a}-{b}"] = {"c60": r_(ult), "c20": r_(z20[a].corr(z20[b])), "pct_c60": r_(100 * float((rc <= ult).mean()), 0),
                           "mediana_hist": r_(rc.median()), "p10": r_(rc.quantile(.1)), "p90": r_(rc.quantile(.9)),
                           "fecha_ultimo": str(Z.index[-1].date())}
    # regresión del oro sobre tipo real y dólar: últimos 60 días frente a toda la muestra
    Z = X[["oro", "tipo_real", "dolar"]].dropna()

    def ols(D):
        A = np.column_stack([np.ones(len(D)), D["tipo_real"], D["dolar"]])
        b, *_ = np.linalg.lstsq(A, D["oro"].values, rcond=None)
        e = D["oro"].values - A @ b
        return b, 1 - e.var() / D["oro"].var()
    b_all, r2_all = ols(Z)
    b60, r260 = ols(Z.iloc[-60:])
    ult5 = Z.iloc[-5:]
    pred = (b_all[1] * ult5["tipo_real"] + b_all[2] * ult5["dolar"])
    res["regresion_oro"] = {"beta_tipo_real_pb_hist": r_(100 * b_all[1], 3), "beta_dolar_hist": r_(b_all[2]),
                            "r2_hist": r_(r2_all), "beta_tipo_real_pb_60d": r_(100 * b60[1], 3),
                            "beta_dolar_60d": r_(b60[2]), "r2_60d": r_(r260),
                            "ultimos5": [{"fecha": str(i.date()), "oro": r_(100 * ult5.loc[i, "oro"]),
                                          "explicado": r_(100 * pred.loc[i]), "d_real_pb": r_(ult5.loc[i, "tipo_real"], 1),
                                          "dolar": r_(100 * ult5.loc[i, "dolar"])} for i in ult5.index]}
    # tipo real: cambio en 1 m y nivel
    res["tipo_real"] = {"ultimo": r_(dfii.iloc[-1]), "fecha": str(dfii.index[-1].date()),
                        "cambio_20s_pb": r_(100 * (dfii.iloc[-1] - dfii.iloc[-21])),
                        "pct_hist_nivel": r_(100 * float((dfii <= dfii.iloc[-1]).mean()), 0),
                        "desde": str(dfii.index[0].date())}
    return res, pd.DataFrame(roll)


# ------------------------------------------------------------------------------------------------ 4. volumen
def volumen(V: pd.DataFrame, meta: dict) -> list[dict]:
    """z del log-volumen del 17-nov frente a las 60 sesiones previas (equivalente a src/report/alertas.py, que no está
    en esta rama: allí no hay umbral validado; aquí ≥ 2 se rotula «alto» por regla fija)."""
    out = []
    for t in V.columns:
        v = V[t].dropna()
        v = v[v > 0]
        if ULT_US not in v.index or len(v) < 80 or meta["activos"][t]["tipo"] in ("INDEX", "CURRENCY", "FUTURE",
                                                                                   "CRYPTOCURRENCY"):
            continue
        lv = np.log(v)
        prev = lv[lv.index < ULT_US].iloc[-60:]
        z = (lv.loc[ULT_US] - prev.mean()) / prev.std()
        out.append({"ticker": t, "nombre": meta["activos"][t]["nombre"], "z": r_(z),
                    "ratio_mediana60": r_(float(v.loc[ULT_US] / np.exp(prev).median()))})
    return sorted(out, key=lambda x: -x["z"])


# ------------------------------------------------------------------------------------------------ 5. COT
def cot(con) -> list[dict]:
    from src.report import manos_fuertes as M
    out = []
    for x in M.cot(con):
        if x["slug"] not in ("gold", "silver", "sp500_emini", "nasdaq_mini", "ust10y", "dxy", "vix"):
            continue
        for k, g in x["grupos"].items():
            out.append({"mercado": x["nombre"], "grupo": g["etiqueta"], "fecha": g["fecha"], "publicado": g["publicado"],
                        "neto_pct_oi": r_(g["valor"], 1), "cambio_4s": r_(g["d4"], 1),
                        "pct_3a": r_(g["p3a"], 0), "pct_hist": r_(g["phist"], 0),
                        "desde": g["desde"], "senal": g["senal"]})
    return out


# ------------------------------------------------------------------------------------------------ 6. episodios
def episodios(P: pd.DataFrame, umbral: float = -1.0, sep: int = 10) -> tuple[dict, dict]:
    """Ventanas de 5 sesiones (cierre EE. UU.) en que oro (GC=F) Y S&P 500 caen ambos ≥ |umbral| desviaciones típicas
    de 5 días (σ de las 252 sesiones previas). Se agrupan: un episodio = 1.er día que lo cumple, el siguiente ≥ `sep`
    sesiones después. Después: rentabilidad 1/5/20 sesiones de cada activo. Base: todos los días."""
    J = pd.concat([P["GC=F"], P["^GSPC"]], axis=1, keys=["oro", "bolsa"]).dropna()
    J = J[J.index <= ULT_US]
    lr = np.log(J).diff().dropna()
    k5 = lr.rolling(5).sum()
    sd = lr.rolling(252).std().shift(5) * np.sqrt(5)
    z = (k5 / sd).dropna()
    hoy = z.iloc[-1]
    marca = z[(z["oro"] <= umbral) & (z["bolsa"] <= umbral)]
    fechas, prev = [], None
    pos = {d: i for i, d in enumerate(J.index)}
    for d in marca.index:                      # rachas de días marcados → un episodio (su primer día)
        if prev is None or pos[d] - pos[prev] >= sep:
            fechas.append(d)
        prev = d
    fechas = [d for d in fechas if pos[d] + 20 < len(J)]      # con 20 sesiones posteriores conocidas
    res = {"regla": f"oro y S&P 500 con caída en 5 sesiones ≤ {umbral} σ (σ de 5 días con las 252 sesiones previas); "
                    f"episodios separados ≥ {sep} sesiones; datos GC=F y ^GSPC {J.index[0].date()}–{ULT_US.date()}",
           "z5_hoy": {"oro": r_(hoy["oro"]), "bolsa": r_(hoy["bolsa"])}, "n": len(fechas),
           "fechas": [str(d.date()) for d in fechas], "despues": {}, "base": {}}
    caminos = {"oro": [], "bolsa": []}
    for a in ("oro", "bolsa"):
        for h in (1, 5, 20):
            fw = np.array([J[a].iloc[pos[d] + h] / J[a].iloc[pos[d]] - 1 for d in fechas]) * 100
            allfw = (J[a].shift(-h) / J[a] - 1).dropna() * 100
            res["despues"][f"{a}_{h}"] = {"mediana": r_(np.median(fw)), "p25": r_(np.percentile(fw, 25)),
                                          "p75": r_(np.percentile(fw, 75)), "min": r_(fw.min()), "max": r_(fw.max()),
                                          "pos": r_(100 * (fw > 0).mean(), 0), "n": len(fw)}
            res["base"][f"{a}_{h}"] = {"mediana": r_(allfw.median()), "p25": r_(allfw.quantile(.25)),
                                       "p75": r_(allfw.quantile(.75)), "pos": r_(100 * (allfw > 0).mean(), 0),
                                       "n": int(len(allfw))}
        for d in fechas:
            caminos[a].append(J[a].iloc[pos[d]:pos[d] + 21].values / J[a].iloc[pos[d]] * 100 - 100)
    # episodio a episodio (para la tabla)
    res["detalle"] = [{"fecha": str(d.date()), "oro_5s_previas": r_(100 * np.expm1(k5.loc[d, "oro"]), 1),
                       "bolsa_5s_previas": r_(100 * np.expm1(k5.loc[d, "bolsa"]), 1),
                       "oro_20": r_(100 * (J["oro"].iloc[pos[d] + 20] / J["oro"].iloc[pos[d]] - 1), 1),
                       "bolsa_20": r_(100 * (J["bolsa"].iloc[pos[d] + 20] / J["bolsa"].iloc[pos[d]] - 1), 1)}
                      for d in fechas]
    return res, {a: np.array(v) for a, v in caminos.items()}


# ------------------------------------------------------------------------------------------------ 7. modelos
def motor_y_activos(con, P: pd.DataFrame) -> dict:
    """INT-11 v3.1 EE. UU. reproducido en solo lectura (mismo código que el panel) + simulaciones A/B de Mis activos.
    El motor da rentabilidad REAL a 12 m (dic-2026 → nov-2027); el mes en curso NO está en su ventana. Para situar
    noviembre se usa una APROXIMACIÓN declarada: distribución a 1 mes = log-rentabilidad a 12 m con media/12 y
    desviación/√12 (supone paseo aleatorio; no es salida del motor)."""
    from src.report import mis_activos as MA
    sig = json.loads(SIGNAL.read_text())
    ab = sig["escenarios"]["paises"]["USA"]["abanicos"]["bolsa"]
    ref = {p: ab[f"p{p}"] for p in (5, 25, 50, 75, 95)}
    motor = MA.trayectorias_motor(sig["escenarios"]["emision"], con, ref)
    rf = con.execute("select last(value order by date) from obs_latest where series_id = 'DTB3'").fetchone()[0]
    A = MA.analizar(con, date(2026, 11, 18), motor, float(rf))
    out = {"comprobacion_motor": motor["comprobacion"], "ventana_motor": motor["ventana"], "rf": r_(rf)}
    # bolsa nominal a 12 m del motor (bolsa real + inflación de la misma trayectoria)
    l_nom = np.log1p(np.clip(motor["bolsa_real"], -0.999, None)) + motor["inflacion_log"]
    mu, sd = float(np.mean(l_nom)), float(np.std(l_nom))
    sp = P["^GSPC"].dropna()
    oct_ = sp[sp.index <= "2026-10-31"].iloc[-1]
    mtd = float(np.log(sp.loc[ULT_US] / oct_))
    dias = int(((sp.index > "2026-10-31") & (sp.index <= ULT_US)).sum())
    frac = dias / 21
    from scipy.stats import norm
    out["noviembre_sp500"] = {"mtd_pct": r_(100 * np.expm1(mtd)), "sesiones": dias,
                              "pct_aprox_motor_mes_entero": r_(100 * norm.cdf(mtd, mu / 12, sd / np.sqrt(12)), 1),
                              "pct_aprox_motor_fraccion_mes": r_(100 * norm.cdf(mtd, mu / 12 * frac, sd * np.sqrt(frac / 12)), 1),
                              "motor_12m_nominal_mu_log": r_(mu, 4), "motor_12m_nominal_sd_log": r_(sd, 4)}
    # historia: noviembre a la misma altura de mes frente a todos los meses (S&P desde 1928, mismas sesiones)
    lr = np.log(sp).diff().dropna()
    g = lr.groupby(lr.index.to_period("M"))
    hist = g.apply(lambda x: x.iloc[:dias].sum() if len(x) >= dias else np.nan).dropna()
    hist = hist[hist.index < pd.Period("2026-11", "M")]
    out["noviembre_sp500"]["pct_hist_mismas_sesiones"] = r_(100 * float((hist <= mtd).mean()), 1)
    out["noviembre_sp500"]["n_meses_hist"] = int(len(hist))
    out["drawdown_sp500"] = r_(100 * (sp.loc[ULT_US] / sp[sp.index > ULT_US - pd.DateOffset(weeks=52)].max() - 1), 1)
    out["p_motor_bolsa_real_le_m20"] = r_(100 * float((motor["bolsa_real"] <= -0.20).mean()), 1)
    out["activos"] = {}
    for t in ("SPY", "QQQ", "GLD", "GDX", "NEM", "TLT"):
        a = A["activos"].get(t) if "activos" in A else A.get(t)
        if not a:
            continue
        sa, sb = a.get("sim_historia") or {}, a.get("sim_motor") or {}
        out["activos"][t] = {"precio": r_(a.get("precio")), "fecha": a.get("fecha"), "vol_1a": r_(a.get("vol_1a"), 1),
                             "caida_max52": r_(a.get("caida_max52"), 1), "beta_3a": r_(a.get("beta_3a")),
                             "A": {k: r_(100 * sa[k], 1) for k in ("p5", "p50", "p95", "p_perdida", "p_caida20") if k in sa},
                             "B": {k: r_(100 * sb[k], 1) for k in ("p5", "p50", "p95", "p_perdida", "p_caida20") if k in sb},
                             "B_beta": r_(sb.get("beta_10a")),
                             "por_cuadrante": a.get("por_cuadrante")}
    return out


def ensayo_b1(con, P: pd.DataFrame) -> dict:
    """ENSAYO en memoria (no registra nada): σ̂ de B1 y σ̂′ de B1′ si noviembre cerrara hoy (17-nov), y qué haría
    falta para que cambiaran la cartera 70/15/15."""
    from src.paper import b1prima as B
    from src.paper import live as L
    from src.warehouse import db
    sp = db.series(con, "SP500").dropna()
    gs = P["^GSPC"].dropna()
    sp = pd.concat([sp, gs[(gs.index > sp.index[-1]) & (gs.index <= ULT_US)]]).sort_index()   # 17-nov de Yahoo
    fx = db.series(con, "ecb_eurusd_d").dropna()
    fx = fx[fx.index <= ULT_US]
    spm, fxm = sp.groupby(sp.index.to_period("M")).last(), fx.groupby(fx.index.to_period("M")).last()
    r = L.rv_eur_mensual(spm.iloc[-14:], fxm.iloc[-14:]).iloc[-12:]
    sig = float(r.std(ddof=1) * np.sqrt(12))
    bruta, rv, _ = L.rv_b1(sig, 0.70)

    def sig_con(nov_ret):
        rr = r.copy()
        rr.iloc[-1] = nov_ret
        return float(rr.std(ddof=1) * np.sqrt(12))
    # caída de noviembre (en EUR) que llevaría σ̂ a σ* (búsqueda simple)
    grid = np.linspace(0, -0.40, 4001)
    hit = next((g for g in grid if sig_con(g) >= L.SIGMA_STAR), None)
    out = {"b1": {"sigma_hat_si_cierra_hoy": r_(sig, 4), "nov_mtd_eur": r_(100 * r.iloc[-1]), "sigma_star": L.SIGMA_STAR,
                  "rv_bruta": r_(bruta, 4), "nov_eur_para_tocar_sigma_star": r_(100 * hit, 1) if hit is not None else None,
                  "registrado_oct": 0.10688}}
    # B1′: rasgos HAR hasta el 17-nov con los coeficientes congelados (solo lectura)
    p = B.cargar_congelado()
    rd = B.r_eur_diario(B.precio_a_rendimiento(sp[sp.index >= "2026-05-01"]), 1 / fx)
    F = B.rasgos_har(rd)
    x = F.iloc[-1][B.HAR].values.astype(float)
    n = B.sesiones_nyse(pd.Period("2026-12", "M"))
    sp1 = float(B.sigma_prima(B.prevision(x, n, p["beta"], p["duan"])[0]))
    bruta1, _, _ = B.rv_regla(sp1, 0.70, p["sigma_star_prima"])
    # estrés: resto de noviembre (9 días hábiles, incluye Acción de Gracias: aproximación) con movimientos diarios de x % (en EUR; el signo no importa: entra al cuadrado)
    estres = {}
    for caida in (0.003, 0.006, 0.01, 0.02, 0.03):
        resto = pd.Series(-caida, index=pd.bdate_range("2026-11-18", "2026-11-30"))
        F2 = B.rasgos_har(pd.concat([rd, resto]))
        x2 = F2.iloc[-1][B.HAR].values.astype(float)
        s2 = float(B.sigma_prima(B.prevision(x2, n, p["beta"], p["duan"])[0]))
        estres[f"mov_diario_{caida * 100:g}pct"] = {"sigma_prima": r_(s2, 4),
                                                   "rv": r_(B.rv_regla(s2, 0.70, p["sigma_star_prima"])[0], 4)}
    # σ̂′ «si el mes cerrara ese día», sesión a sesión desde septiembre (mismos rasgos HAR, n = sesiones del mes sig.)
    r2 = rd ** 2
    Fd = pd.DataFrame({f"lrv{k}": np.log(r2.rolling(k, min_periods=k).mean() + 1e-12) for k in B.VENTANAS})
    Fd = Fd[Fd.index >= "2026-09-01"].dropna()
    nn = [B.sesiones_nyse(d.to_period("M") + 1) for d in Fd.index]
    serie = B.sigma_prima(B.prevision(Fd[B.HAR].values, nn, p["beta"], p["duan"]))
    cruce = [str(d.date()) for d, v in zip(Fd.index, serie) if v > p["sigma_star_prima"]]
    out["b1prima_serie"] = {"fechas": [str(d.date()) for d in Fd.index], "sigma_prima": [r_(v, 4) for v in serie],
                            "primer_dia_sobre_sigma_star": cruce[0] if cruce else None, "dias_sobre": len(cruce)}
    out["b1prima"] = {"sigma_prima_si_cierra_hoy": r_(sp1, 4), "sigma_star_prima": r_(p["sigma_star_prima"], 4),
                      "rv_bruta": r_(bruta1, 4), "rasgos": {k: r_(v, 3) for k, v in zip(B.HAR, x)},
                      "ultima_sesion": str(rd.index[-1].date()), "estres_resto_noviembre": estres}
    return out


# ------------------------------------------------------------------------------------------------ gráficos
def g_sigmas(tab: list[dict]) -> str:
    """Dos barras por activo: 17-nov (último cierre completo de EE. UU.) y 18-nov (sesión de hoy, parcial)."""
    sel = [("GC=F", "Oro (futuro)"), ("SI=F", "Plata (futuro)"), ("HG=F", "Cobre (futuro)"), ("GDX", "Mineras de oro"),
           ("^GSPC", "S&P 500"), ("ES=F", "S&P 500 (futuro)"), ("^NDX", "Nasdaq 100"), ("^RUT", "Russell 2000"),
           ("^STOXX50E", "Euro Stoxx 50"), ("^GDAXI", "DAX"), ("^IBEX", "IBEX 35"), ("^N225", "Nikkei 225"),
           ("^KS11", "Kospi"), ("DX-Y.NYB", "Dólar (DXY)"), ("^TNX", "Rentab. bono 10a EE. UU."),
           ("HYG", "High yield (HYG)"), ("CL=F", "Petróleo WTI"), ("BTC-USD", "Bitcoin"), ("^VIX", "VIX")]
    T = {x["ticker"]: x for x in tab}
    filas = [(n, T[t].get("d17"), T[t].get("d18"), T[t]["unidad"]) for t, n in sel if t in T][::-1]
    fig, ax = plt.subplots(figsize=(8.6, 8.2))
    y = np.arange(len(filas))
    h = 0.38
    for k, (etq, col, off) in enumerate((("17-nov (cierre completo)", AZUL, h / 2), ("18-nov (hoy, parcial)", NARANJA, -h / 2))):
        for i, f in enumerate(filas):
            d = f[1 + k]
            if not d:
                continue
            z = d["z252"]
            ax.barh(i + off, z, height=h - 0.04, color=col, label=etq if i == 0 or (k == 1 and not any(
                ff[2] for ff in filas[:i])) else None)
            ax.text(z + (0.07 if z >= 0 else -0.07), i + off, f"{d['mov']:+.1f} {f[3]}", va="center",
                    ha="left" if z >= 0 else "right", fontsize=7.5, color=TINTA)
    h1, l1 = ax.get_legend_handles_labels()
    ax.legend(h1, l1, loc="lower right", fontsize=8.5, frameon=False)
    ax.set_yticks(y, [f[0] for f in filas], fontsize=9)
    for v in (-2, 2):
        ax.axvline(v, color=GRIS_SUAVE, ls="--", lw=1)
    ax.axvline(0, color=GRIS, lw=0.8)
    ax.set_xlim(-3.6, 3.6)
    ax.set_xlabel("Movimiento del día en desviaciones típicas (σ diaria de las 252 sesiones previas)")
    ax.set_title("Tamaño de la caída frente a la volatilidad habitual de cada activo", loc="left", fontsize=11,
                 color=TINTA)
    fig.text(0.01, 0.008, "Etiqueta = movimiento en % (pb en la rentabilidad del bono). Fuera de ±2 σ (líneas "
             "discontinuas) ≈ 1 de cada 20 días.\nHoy = hasta ≈ 09:40 h CET; las bolsas de EE. UU. aún no han abierto "
             "(solo futuros). Fuente: Yahoo Finance; cálculo propio.", fontsize=7.5, color=GRIS)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    p = IMG / "2026-11-18_movimiento_sigmas.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p.name


def g_trayectoria(P: pd.DataFrame, con) -> str:
    from src.warehouse import db
    dfii = db.series(con, "DFII10").dropna()
    ini = pd.Timestamp("2026-06-30")
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8.6, 6.4), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    for t, n, c in (("GC=F", "Oro", AMARILLO), ("^GSPC", "S&P 500", AZUL), ("^NDX", "Nasdaq 100", AQUA),
                    ("DX-Y.NYB", "Dólar (DXY)", NARANJA)):
        s = P[t].dropna()
        s = s[s.index >= ini]
        b = 100 * s / s.iloc[0]
        a1.plot(b.index, b.values, color=c, lw=2, label=n)
        a1.text(b.index[-1] + pd.Timedelta(days=2), b.iloc[-1], f"{n} {b.iloc[-1] - 100:+.0f} %", fontsize=8.5,
                va="center", color=TINTA)
    a1.axhline(100, color=GRIS, lw=0.8)
    a1.set_ylabel("Base 100 = 30-jun-2026")
    a1.legend(loc="upper left", fontsize=8.5, frameon=False, ncol=4)
    a1.set_title("Oro, bolsa y dólar desde el verano (arriba) y tipos de interés del bono a 10 años (abajo)",
                 loc="left", fontsize=11, color=TINTA)
    tn = P["^TNX"].dropna()
    tn = tn[tn.index >= ini]
    dr = dfii[dfii.index >= ini]
    a2.plot(tn.index, tn.values, color=AZUL, lw=2, label="Nominal (^TNX)")
    a2.plot(dr.index, dr.values, color=NARANJA, lw=2, label="Real (TIPS, FRED DFII10)")
    a2.text(tn.index[-1] + pd.Timedelta(days=2), tn.iloc[-1], f"{tn.iloc[-1]:.2f} %", fontsize=8.5, va="center")
    a2.text(dr.index[-1] + pd.Timedelta(days=2), dr.iloc[-1], f"{dr.iloc[-1]:.2f} %", fontsize=8.5, va="center")
    a2.set_ylabel("% anual")
    a2.legend(loc="center left", fontsize=8.5, frameon=False)
    a2.set_xlim(ini, HOY + pd.Timedelta(days=22))
    fig.text(0.01, 0.005, "Fuente: Yahoo Finance (precios, último dato 18-nov parcial para futuros), FRED (tipo real, "
             "último 16-nov). Una sola escala por panel.", fontsize=7.5, color=GRIS)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    p = IMG / "2026-11-18_trayectoria.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p.name


def g_correl(roll: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    for k, n, c in (("oro-bolsa", "Oro con bolsa (S&P)", AZUL), ("oro-dolar", "Oro con dólar", NARANJA),
                    ("oro-tipo_real", "Oro con tipo real", AQUA)):
        s = roll[k].dropna()
        s = s[s.index >= "2019-01-01"]
        ax.plot(s.index, s.values, color=c, lw=1.6, label=n)
        ax.text(s.index[-1] + pd.Timedelta(days=20), s.iloc[-1], f"{s.iloc[-1]:+.2f}", fontsize=8.5, va="center")
    ax.axhline(0, color=GRIS, lw=0.8)
    ax.set_ylim(-1, 1)
    ax.set_ylabel("Correlación de 60 sesiones")
    ax.legend(loc="lower left", fontsize=8.5, frameon=False, ncol=3)
    ax.set_title("¿Con qué se mueve el oro? Correlación diaria móvil de 60 sesiones (2019-2026)", loc="left",
                 fontsize=11, color=TINTA)
    fig.text(0.01, 0.01, "Oro = GLD; bolsa = SPY; dólar = DXY; tipo real = FRED DFII10 (cambio diario). Cálculo propio.",
             fontsize=7.5, color=GRIS)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    p = IMG / "2026-11-18_correlaciones.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p.name


def g_episodios(cam: dict, n: int) -> str:
    fig, axs = plt.subplots(1, 2, figsize=(8.6, 4.0), sharey=True)
    for ax, (a, nom, c) in zip(axs, (("bolsa", "S&P 500", AZUL), ("oro", "Oro", AMARILLO))):
        M = cam[a]
        x = np.arange(M.shape[1])
        ax.fill_between(x, np.percentile(M, 10, 0), np.percentile(M, 90, 0), color=c, alpha=0.15, lw=0,
                        label="10-90 % de los episodios")
        ax.fill_between(x, np.percentile(M, 25, 0), np.percentile(M, 75, 0), color=c, alpha=0.35, lw=0,
                        label="25-75 %")
        ax.plot(x, np.median(M, 0), color=c, lw=2, label="Mediana")
        ax.axhline(0, color=GRIS, lw=0.8)
        ax.set_title(nom, loc="left", fontsize=10, color=TINTA)
        ax.set_xlabel("Sesiones después del episodio")
        ax.set_xticks([0, 1, 5, 10, 15, 20])
    axs[0].set_ylabel("% desde el día del episodio")
    axs[0].legend(loc="lower left", fontsize=7.5, frameon=False)
    fig.suptitle(f"Qué pasó después de semanas con caída conjunta de oro y bolsa (n = {n} episodios, 2002-2026)",
                 x=0.01, ha="left", fontsize=11, color=TINTA)
    fig.text(0.01, 0.01, "Descriptivo: pocos episodios y solapados con crisis concretas; no es una previsión. "
             "Fuente: Yahoo (GC=F, ^GSPC); cálculo propio.", fontsize=7.5, color=GRIS)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    p = IMG / "2026-11-18_episodios.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p.name


def g_sectores(amp: dict, tab: list[dict]) -> str:
    T = {x["ticker"]: x for x in tab}
    d = sorted(amp["sectores_17nov"].items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    nom = [T[t]["nombre"].replace("ETF ", "").replace(" EE. UU.", "") for t, _ in d]
    v = [x for _, x in d]
    ax.barh(nom, v, color=[NARANJA if x < 0 else AZUL for x in v], height=0.62)
    for i, x in enumerate(v):
        ax.text(x - 0.05 if x < 0 else x + 0.05, i, f"{x:+.1f} %", va="center", ha="right" if x < 0 else "left",
                fontsize=8.5)
    ax.axvline(0, color=GRIS, lw=0.8)
    ax.set_xlim(min(v) - 0.8, max(0.5, max(v) + 0.5))
    ax.set_xlabel("Variación el 17-nov-2026 (%)")
    ax.set_title(f"Sectores de EE. UU. el 17-nov: bajan {amp['sectores_bajan']} de {amp['sectores_n']}",
                 loc="left", fontsize=11, color=TINTA)
    fig.text(0.01, 0.01, "ETF sectoriales SPDR (XL*), cierre ajustado. Fuente: Yahoo Finance.", fontsize=7.5, color=GRIS)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    p = IMG / "2026-11-18_sectores.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p.name


def main(salida: Path) -> None:
    from src.warehouse import db
    IMG.mkdir(parents=True, exist_ok=True)
    P, V, I, meta = cargar()
    con = db.connect(read_only=True)
    try:
        tab = tamano(P, meta)
        amp = amplitud(tab)
        cor, roll = correlaciones(P, con)
        vol = volumen(V, meta)
        cot_ = cot(con)
        epi, cam = episodios(P)
        epi_15, _ = episodios(P, umbral=-1.5)
        mod = motor_y_activos(con, P)
        b1 = ensayo_b1(con, P)
        graf = [g_sigmas(tab), g_trayectoria(P, con), g_sectores(amp, tab), g_correl(roll), g_episodios(cam, epi["n"])]
    finally:
        con.close()
    res = {"descarga": meta["descarga"], "tamano": tab, "amplitud": amp, "correlaciones": cor, "volumen": vol,
           "cot": cot_, "episodios": epi, "episodios_1_5": {k: epi_15[k] for k in ("n", "despues", "fechas", "regla")},
           "modelos": mod, "ensayo_b1": b1, "graficos": graf}
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("ok →", salida, graf)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DIR / "resultados.json")
