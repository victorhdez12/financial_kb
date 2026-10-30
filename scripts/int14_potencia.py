"""INT-14 fase 1: inventario de EVENTOS, recuentos y POTENCIA (docs/int/INT14_eventos_v0.md). Datos reales solo ≤ 2004.

Qué usa, en partes que NUNCA se juntan:
  (i)   INVENTARIO: cobertura de las series que definen eventos y de las de resultado (fechas, nº obs ≤ 2004).
  (ii)  EVENTOS: definiciones v0 de src/intl/eventos.py aplicadas SOLO a la serie que define cada evento (petróleo,
        índice del dólar, volatilidad realizada / VIX, crisisJST). Recuentos, episodios independientes, solapes entre
        tipos de evento y la correspondencia VIX ↔ volatilidad realizada (dos definidores, ninguna rentabilidad futura).
  (iii) RESULTADOS: solo momentos MARGINALES de cada activo (desviación típica mensual / anual de log(1 + r), y
        correlación contemporánea media entre países del panel anual). Nunca una rentabilidad cruzada con un evento.
  (iv)  POTENCIA del uso A: rentabilidades SINTÉTICAS (t de 5 g. l. con la sd marginal de (iii); panel con choque común
        de correlación ρ de (iii)) en las FECHAS REALES de los eventos → sd del estadístico bajo la nula → MDE (80 %)
        a α = 5 % y a α = 1,25 % (Holm, el más exigente de 4). Variante: vol. post-evento × 1,5.
        Potencia del uso B: caso-control sintético con nº real de eventos independientes (src/intl/eventos.py).

Uso: .venv/bin/python -m scripts.int14_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int14_potencia --prueba   (sin puerta; no escribe nada; pocas réplicas)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.intl import eventos as E
from src.intl.data import PAISES, check

REPO = Path(__file__).resolve().parents[1]
CORTE = pd.Timestamp("2004-12-31")
HM = (1, 3, 6, 12, 24)            # horizontes mensuales
HA = (1, 2, 3)                    # horizontes anuales (t+1..t+H)
Z80 = stats.norm.ppf(0.80)
ALFAS = {"a5": 0.05, "holm_1de4": 0.0125}
GUERRAS = set(range(1914, 1919)) | set(range(1939, 1946))

INVENTARIO = {
    "petroleo": ["nber_m04079", "WPU0561", "wb_crude_oil_average", "MCOILWTICO", "boe_uk_oil_price_usd_a",
                 "eia_wti_fut_c1"],
    "dolar": ["TWEXMMTH", "TWEXBMTH", "DTWEXBGS", "jst_usa_xrusd", "jst_deu_xrusd", "bundesbank_usd_dem_d"],
    "volatilidad": ["aqr_mkt_usa_d", "ffx_us_mkt_rf_d", "VIXCLS"],
    "crisis": ["jst_usa_crisisjst", "jst_gbr_crisisjst", "jst_irl_crisisjst"],
    "resultado_mensual": ["ffx_us_rf_d", "shiller_gs10", "gold_usd_monthly", "aqr_clr_ew_xret_m",
                          "aqr_cfp_commodities_market_m", "wb_idx_energy", "wb_idx_base_metals_ex_iron_ore",
                          "wb_idx_precious_metals"],
    "resultado_anual": ["jst_usa_eq_tr", "jst_usa_bond_tr", "jst_usa_bill_rate", "jst_usa_housing_tr", "jst_usa_cpi",
                        "damodaran_gold_ret"],
}


def _r(x, d=4):
    return None if x is None or not np.isfinite(x) else round(float(x), d)


# ================================================================ carga (≤ 2004)
class Datos:
    def __init__(self, con, db):
        self.con, self.db = con, db

    def s(self, sid):
        x = self.db.series(self.con, sid)
        if not len(x):
            return pd.Series(dtype=float, index=pd.DatetimeIndex([]), name=sid)
        x = x[x.index <= CORTE].dropna()
        x.name = sid
        check(x)
        return x

    def anual(self, sid):
        x = self.s(sid)
        x.index = x.index.year
        return x


def inventario(con) -> dict:
    out = {}
    for rol, ids in INVENTARIO.items():
        out[rol] = {}
        for s in ids:
            q = ("select min(date), max(date) filter (where date <= ?), count(*) filter (where date <= ?) "
                 "from obs_latest where series_id = ? and value is not null")
            d0, d1, n = con.execute(q, [CORTE.date(), CORTE.date(), s]).fetchone()
            out[rol][s] = {"desde": str(d0) if d0 else None, "ultimo_le_2004": str(d1) if d1 else None,
                           "obs_le_2004": int(n)}
    return out


# ================================================================ (ii) eventos
def construir_eventos(D: Datos) -> dict:
    pm = lambda x: E.a_mensual(x, "media")                                   # noqa: E731
    w = D.s("WPU0561")
    oil_mundo = E.mensual_petroleo_encadenado([pm(D.s("nber_m04079")), pm(w[w.index < "1960-01-01"]),
                                               pm(D.s("wb_crude_oil_average"))])
    oil_dom = E.mensual_petroleo_encadenado([pm(D.s("nber_m04079")), pm(w)])
    r_us = D.s("aqr_mkt_usa_d") / 100 + D.s("ffx_us_rf_d").reindex(D.s("aqr_mkt_usa_d").index).fillna(0) / 100
    rv = E.vol_realizada_mensual(r_us) * 100
    vix = pm(D.s("VIXCLS"))
    tw = pm(D.s("TWEXMMTH"))
    xr = pd.DataFrame({c: D.anual(f"jst_{c.lower()}_xrusd") for c in PAISES if c != "USA"})
    cr = pd.DataFrame({c: D.anual(f"jst_{c.lower()}_crisisjst") for c in PAISES})
    oa = D.anual("boe_uk_oil_price_usd_a")

    ev = {
        "petroleo": E.eventos_petroleo(oil_mundo),
        "petroleo_sens_u10": E.eventos_petroleo(oil_mundo, umbral=0.10),
        "petroleo_sens_u30": E.eventos_petroleo(oil_mundo, umbral=0.30),
        "petroleo_sens_domestico": E.eventos_petroleo(oil_dom),
        "vol": E.eventos_vol(rv),
        "vol_sens_p95": E.eventos_vol(rv, cuantil=0.95),
        "vol_sens_sep6": E.eventos_vol(rv, separacion=6),
        "vol_sens_racha": None,
        "vix_1990": E.eventos_vol(vix, min_hist=24),
        "rv_1990_mismo_metodo": E.eventos_vol(rv[rv.index >= pd.Period("1990-01", "M")], min_hist=24),
        "dolar": E.eventos_dolar(tw),
        "dolar_sens_u05": E.eventos_dolar(tw, umbral=0.05),
        "dolar_sens_u15": E.eventos_dolar(tw, umbral=0.15),
    }
    x = E._completa_mensual(rv)
    u = E.umbral_expansivo(x, 0.90, 60)
    ini = E.episodios((x >= u) & u.notna(), 12, modo="racha")
    ev["vol_sens_racha"] = pd.DataFrame({"fecha": x.index[ini.to_numpy()]})
    crisis = E.eventos_crisis(cr)
    descartadas = int(crisis["descartadas_por_separacion"].sum())
    crisis = crisis[crisis["año"] > 0][["pais", "año"]].reset_index(drop=True)
    dl = E.cesta_dolar_anual(xr).diff()
    anual = {
        "petroleo_anual_<1890_boe": [int(a) for a in E.eventos_petroleo_anual(oa).index],
        "dolar_anual_jst_todas": [int(a) for a in E.eventos_dolar_anual(dl).index],
        "dolar_anual_jst_sin_guerras": [int(a) for a in E.eventos_dolar_anual(dl, excluir=frozenset(GUERRAS)).index],
    }
    corr = E.correspondencia_vix_rv(vix, rv)
    return {"ev": ev, "crisis": crisis, "crisis_descartadas": descartadas, "anual": anual, "corr_vix_rv": corr,
            "oil": oil_mundo, "rv": rv, "r_us_d": r_us}


def resumen_eventos(B: dict) -> dict:
    out = {}
    for k, d in B["ev"].items():
        f = list(d["fecha"])
        out[k] = {"n": len(f), "fechas": [str(x) for x in f],
                  "n_desde_1926_07": sum(x >= pd.Period("1926-07", "M") for x in f),
                  "n_con_24m_completos_le_2004": sum(x <= pd.Period("2002-11", "M") for x in f)}
        if "intensidad" in d:
            out[k]["intensidad"] = [_r(v, 3) for v in d["intensidad"]]
    c = B["crisis"]
    cg = E.conglomerados_globales(c["año"].values)
    out["crisis_jst"] = {
        "n_pais_evento": int(len(c)), "descartadas_por_separacion_5a": B["crisis_descartadas"],
        "por_pais": c.groupby("pais")["año"].apply(list).to_dict(),
        "años_distintos": int(c["año"].nunique()), "episodios_globales_hueco1": int(len(cg)),
        "episodios_globales": cg.to_dict("records"),
        "por_periodo": {p: {"n": int(((c.año >= a) & (c.año <= b)).sum()),
                            "episodios": int(len(E.conglomerados_globales(c.año[(c.año >= a) & (c.año <= b)].values)))}
                        for p, (a, b) in {"1870-1913": (1870, 1913), "1914-1945": (1914, 1945),
                                          "1946-2004": (1946, 2004), "1973-2004": (1973, 2004)}.items()},
        "en_guerras": int(c["año"].isin(list(GUERRAS)).sum()),
    }
    out["anual"] = B["anual"]
    return out


def solapes(B: dict, ventana: int = 12) -> dict:
    """Coincidencias entre tipos de evento (|Δ| ≤ ventana meses); la crisis de EE. UU. con su año (julio)."""
    tipos = {k: list(B["ev"][k]["fecha"]) for k in ("petroleo", "vol", "dolar")}
    us = B["crisis"][B["crisis"].pais == "USA"]["año"]
    tipos["crisis_EEUU"] = [pd.Period(f"{a}-07", "M") for a in us]
    out = {}
    ks = list(tipos)
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            pares = [(str(x), str(y)) for x in tipos[a] for y in tipos[b] if abs((x - y).n) <= ventana]
            out[f"{a}~{b}"] = pares
    return out


# ================================================================ (iii) marginales de resultados
def resultados_mensuales(D: Datos, B: dict) -> dict[str, pd.Series]:
    """Rentabilidades mensuales simples (fracción) de EE. UU./mundo. Solo para la sd marginal (y, tras congelar, para
    el estudio)."""
    pm_last = lambda x: E.a_mensual(x, "ultimo")                             # noqa: E731
    r = B["r_us_d"]
    mes = r.index.to_period("M")
    bolsa = (1 + r).groupby(mes).prod() - 1
    rf = D.s("ffx_us_rf_d") / 100
    letras = (1 + rf).groupby(rf.index.to_period("M")).prod() - 1
    y = pm_last(D.s("shiller_gs10")) / 100                                   # bono 10 a. a la par, revalorizado
    y0 = y.shift(1)
    precio = (y0 / y) * (1 - (1 + y / 2) ** -20) + (1 + y / 2) ** -20
    bonos = (precio - 1 + y0 / 12).dropna()
    oro = pm_last(D.s("gold_usd_monthly")).pct_change()
    out = {"bolsa": bolsa, "letras": letras, "bonos_aprox": bonos,
           "oro_desde_1968": oro[oro.index >= pd.Period("1968-04", "M")],
           "materias_clr_exceso": pm_last(D.s("aqr_clr_ew_xret_m")) / 100,
           "materias_cfp": pm_last(D.s("aqr_cfp_commodities_market_m")) / 100,
           "petroleo_precio": B["oil"].pct_change(),
           "energia_wb": E.a_mensual(D.s("wb_idx_energy"), "media").pct_change(),
           "metales_base_wb": E.a_mensual(D.s("wb_idx_base_metals_ex_iron_ore"), "media").pct_change(),
           "metales_preciosos_wb": E.a_mensual(D.s("wb_idx_precious_metals"), "media").pct_change()}
    return {k: v.dropna() for k, v in out.items()}


def panel_anual(D: Datos) -> dict[str, pd.DataFrame]:
    """Rentabilidades REALES anuales JST (como INT-11): (1 + tr)/(1 + inflación) − 1."""
    cpi = pd.DataFrame({c: D.anual(f"jst_{c.lower()}_cpi") for c in PAISES})
    infl = cpi.pct_change()
    out = {}
    for a, col in (("bolsa", "eq_tr"), ("bonos", "bond_tr"), ("letras", "bill_rate"), ("vivienda", "housing_tr")):
        tr = pd.DataFrame({c: D.anual(f"jst_{c.lower()}_{col}") for c in PAISES})
        out[a] = ((1 + tr) / (1 + infl) - 1).reindex(range(1871, 2005))
    return out


def marginales(mens: dict, panel: dict) -> dict:
    out = {"mensual": {}, "panel": {}}
    for k, r in mens.items():
        lr = np.log1p(r)
        out["mensual"][k] = {"desde": str(r.index.min()), "meses": int(len(r)), "sd_mensual_log": _r(lr.std()),
                             "sd_12m_log_solapada": _r(lr.rolling(12).sum().std()),
                             "media_mensual_log": _r(lr.mean())}
    for k, df in panel.items():
        lr = np.log1p(df)
        c = lr.corr(min_periods=20).to_numpy()
        rho = np.nanmean(c[np.triu_indices_from(c, 1)])
        dm = (lr - lr.mean()).drop(index=[a for a in GUERRAS if a in lr.index]).to_numpy().ravel()
        dm = dm[np.isfinite(dm)]
        lo, hi = np.quantile(dm, [0.01, 0.99])
        out["panel"][k] = {"filas": int(lr.notna().sum().sum()), "sd_anual_log_pool_bruta": _r(np.std(dm)),
                           "sd_anual_log_pool": _r(np.std(np.clip(dm, lo, hi))),
                           "nota_sd": "sin años de guerra y winsorizada 1-99 % (hiperinflaciones); el ruido t5 "
                                      "devuelve colas gruesas",
                           "corr_contemporanea_media": _r(rho)}
    return out


# ================================================================ (iv) potencia A
def _stat_mensual(L: np.ndarray, pos: np.ndarray, h: int, retraso: int) -> np.ndarray:
    """L (R, T) log-rentabilidades sintéticas; efecto = media de las acumuladas tras los eventos − media de los
    orígenes sin evento en (t − h, t]. Vectorizado sobre réplicas."""
    R, T = L.shape
    cs = np.concatenate([np.zeros((R, 1)), np.cumsum(L, 1)], 1)
    t = np.arange(T)
    ini, fin = t + 1 + retraso, t + 1 + retraso + h
    ok = fin <= T
    acc = np.full((R, T), np.nan)
    acc[:, ok] = cs[:, fin[ok]] - cs[:, ini[ok]]
    marca = np.zeros(T, bool)
    marca[pos] = True
    cerca = pd.Series(marca).rolling(h, min_periods=1).max().to_numpy().astype(bool)
    pos = pos[ok[pos]]
    base = ok & ~cerca
    return np.nanmean(acc[:, pos], 1) - np.nanmean(acc[:, base], 1), len(pos)


def potencia_mensual(r: pd.Series, fechas: list, sd: float, reps: int, rng, retraso: int = 0,
                     infla_post: float = 1.0) -> dict:
    idx = pd.period_range(r.index.min(), r.index.max(), freq="M")
    T = len(idx)
    pos = idx.get_indexer([f for f in fechas if f in idx])
    pos = pos[pos >= 0]
    out = {}
    escala = sd / np.sqrt(5 / 3)                             # t5 con sd = sd marginal
    for h in HM:
        L = rng.standard_t(5, (reps, T)) * escala
        if infla_post != 1.0:
            for p in pos:
                L[:, p + 1:p + 1 + 24] *= infla_post
        st, n = _stat_mensual(L, pos, h, retraso)
        s = float(np.std(st))
        out[f"h{h}"] = {"n_eventos": int(n), "sd_nula_log": _r(s, 5),
                        **{f"mde_pp_{k}": _r(100 * (stats.norm.ppf(1 - a / 2) + Z80) * s, 2) for k, a in ALFAS.items()}}
    return out


def potencia_panel(panel: pd.DataFrame, pares: list[tuple[str, int]], sd: float, rho: float, reps: int, rng) -> dict:
    """Panel sintético con la MISMA disponibilidad (máscara país-año) y las mismas fechas reales de los eventos."""
    años, paises = panel.index.to_numpy(), list(panel.columns)
    mask = panel.notna().to_numpy()
    T, C = mask.shape
    ia = {a: i for i, a in enumerate(años)}
    ic = {c: j for j, c in enumerate(paises)}
    ev = [(ia[a], ic[c]) for c, a in pares if a in ia and c in ic]
    out = {}
    for H in HA:
        st = np.empty(reps)
        n_ok = 0
        for k in range(reps):
            f = rng.standard_t(5, (T, 1)) * np.sqrt(rho) * sd / np.sqrt(5 / 3)
            e = rng.standard_t(5, (T, C)) * np.sqrt(1 - rho) * sd / np.sqrt(5 / 3)
            L = np.where(mask, f + e, np.nan)
            acc = np.full((T, C), np.nan)
            for t in range(T - H):
                acc[t] = L[t + 1:t + 1 + H].sum(0)
            marca = np.zeros((T, C), bool)
            for t, c in ev:
                marca[t, c] = True
            cerca = pd.DataFrame(marca).rolling(H, min_periods=1).max().to_numpy().astype(bool)
            with np.errstate(all="ignore"):
                base = np.nanmean(np.where(cerca, np.nan, acc), 0)
            v = np.array([acc[t, c] - base[c] for t, c in ev])
            v = v[np.isfinite(v)]
            n_ok = len(v)
            st[k] = v.mean() if len(v) else np.nan
        s = float(np.nanstd(st))
        out[f"H{H}"] = {"n_pais_evento": n_ok, "sd_nula_log": _r(s, 5),
                        **{f"mde_pp_{k}": _r(100 * (stats.norm.ppf(1 - a / 2) + Z80) * s, 2) for k, a in ALFAS.items()}}
    return out


# ================================================================ (iv) potencia B
def potencia_b(escenarios: dict, reps: int, rng) -> dict:
    out = {}
    rejilla = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5)
    for nombre, (n_pos, n_neg) in escenarios.items():
        filas = []
        for b in rejilla:
            res = E.potencia_clasificacion(n_pos, n_neg, b_liston=0.8, b_extra=b, n_rep=reps, n_boot=199,
                                           semilla=int(rng.integers(1 << 31)))
            filas.append({"b_extra": b, **{k: _r(v, 3) for k, v in res.items()}})
        pw = np.array([f["potencia_auc"] for f in filas])
        g = np.array([f["delta_auc_medio"] for f in filas])
        pb = np.array([f["potencia_brier"] for f in filas])
        gb = np.array([f["delta_bss_medio"] for f in filas])
        out[nombre] = {"n_pos": n_pos, "n_neg": n_neg, "rejilla": filas,
                       "mde_delta_auc_80": _r(float(np.interp(0.8, pw, g))) if pw.max() >= 0.8 else None,
                       "mde_delta_bss_80": _r(float(np.interp(0.8, pb, gb))) if pb.max() >= 0.8 else None}
        print("B", nombre, out[nombre]["mde_delta_auc_80"], out[nombre]["mde_delta_bss_80"], flush=True)
    return out


# ================================================================ principal
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    borrador = "--prueba" in argv
    reps, reps_panel, reps_b = (60, 20, 20) if borrador else (2000, 300, 200)
    rng = np.random.default_rng(20261030)
    from src.intl.procedencia import procedencia
    from src.warehouse import db
    res = {"procedencia": procedencia(exigir_limpio=not borrador), "borrador": borrador,
           "reps": {"mensual": reps, "panel": reps_panel, "B": reps_b}}
    t0 = time.time()
    con = db.connect(read_only=True)
    res["inventario"] = inventario(con)
    D = Datos(con, db)
    B = construir_eventos(D)
    res["eventos"] = resumen_eventos(B)
    res["solapes_12m"] = solapes(B)
    res["correspondencia_vix_rv_1990_2004"] = B["corr_vix_rv"]
    print(json.dumps({k: v.get("n") for k, v in res["eventos"].items() if isinstance(v, dict) and "n" in v}),
          flush=True)
    mens = resultados_mensuales(D, B)
    panel = panel_anual(D)
    con.close()
    res["marginales"] = marginales(mens, panel)

    # ---- A mensual: (evento, activo) principales y descriptivos
    fe = {k: list(B["ev"][k]["fecha"]) for k in ("petroleo", "vol", "dolar", "vix_1990")}
    combos = {"petroleo": ["bolsa", "bonos_aprox", "oro_desde_1968", "materias_cfp", "materias_clr_exceso",
                           "metales_base_wb"],
              "vol": ["bolsa", "bonos_aprox", "letras", "oro_desde_1968", "materias_cfp"],
              "dolar": ["bolsa", "oro_desde_1968", "materias_cfp", "petroleo_precio", "metales_base_wb"],
              "vix_1990": ["bolsa"]}
    retrasos = {"petroleo": 1, "vol": 0, "dolar": 1, "vix_1990": 0}
    A = {}
    for ev, activos in combos.items():
        for a in activos:
            r = mens[a]
            sd = float(np.log1p(r).std())
            k = f"{ev}->{a}"
            A[k] = potencia_mensual(r, fe[ev], sd, reps, rng, retrasos[ev])
            if ev == "vol" and a == "bolsa":
                A[k + "_volpost_x1.5"] = potencia_mensual(r, fe[ev], sd, reps, rng, 0, infla_post=1.5)
            print("A", k, {h: (v["n_eventos"], v["mde_pp_a5"]) for h, v in A[k].items()}, flush=True)
    res["potencia_A_mensual"] = A

    # ---- A panel anual (17 países, real): crisis (país-evento) y eventos globales (todos los países)
    c = B["crisis"]
    sin_guerra = c[~c["año"].isin(list(GUERRAS))]
    pares = {"crisis": list(zip(sin_guerra.pais, sin_guerra.año)),
             "crisis_1946_2004": list(zip(c[c.año >= 1946].pais, c[c.año >= 1946].año))}
    for ev in ("petroleo", "vol", "dolar"):
        años = sorted({f.year for f in fe[ev]} - GUERRAS)
        pares[f"{ev}_global"] = [(p, a) for a in años for p in PAISES]
    P = {}
    for ev, pr in pares.items():
        for a, df in panel.items():
            m = res["marginales"]["panel"][a]
            P[f"{ev}->{a}"] = potencia_panel(df, pr, m["sd_anual_log_pool"], max(m["corr_contemporanea_media"], 0),
                                             reps_panel, rng)
            print("P", ev, a, {h: (v["n_pais_evento"], v["mde_pp_a5"]) for h, v in P[f"{ev}->{a}"].items()},
                  flush=True)
    res["potencia_A_panel"] = P

    # ---- B: anticipar el evento (eventos independientes frente a periodos sin evento)
    n_cr = res["eventos"]["crisis_jst"]
    esc_b = {"vol_12m_anual_1931_2004": (len(fe["vol"]), 74 - len(fe["vol"])),
             "petroleo_12m_anual_1890_2004": (len(fe["petroleo"]), 109 - len(fe["petroleo"])),
             "dolar_12m_anual_1974_2004": (len(fe["dolar"]), 31 - len(fe["dolar"])),
             "crisis_pais_año_n_eventos": (n_cr["n_pais_evento"], 1900),
             "crisis_pais_año_n_episodios": (n_cr["episodios_globales_hueco1"], 1900 // 4)}
    res["potencia_B"] = potencia_b(esc_b, reps_b, rng)
    res["supuestos"] = {"horizontes_mensuales": HM, "horizontes_anuales": HA, "alfas": ALFAS, "potencia": 0.80,
                        "ruido": "t de 5 g. l. con la sd marginal", "guerras_excluidas_panel": sorted(GUERRAS),
                        "B": "logit; listón b=0,8 (AUC≈0,70); el modelo añade x2 con b_extra; oráculo de calibración; "
                             "bootstrap pareado estratificado, unilateral 5 %"}
    res["segundos"] = round(time.time() - t0)
    if not borrador:
        (REPO / "research" / "int" / "int14_potencia.json").write_text(
            json.dumps(res, indent=1, ensure_ascii=False, default=str))
    print("fin", res["segundos"], "s", flush=True)
    return res


if __name__ == "__main__":
    main()
