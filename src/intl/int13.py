"""INT-13 (EXPLORATORIO): XGBoost por "paquetes" de datos relacionados como corrección de un logit clásico, para
anticipar entrada en recesión (E1-6, E1-12), subida de inflación (E2) y subida del tipo corto (E3).
Plan congelado antes del código: docs/int/INT13_plan_exploratorio.md (d315777).

Solo funciones puras: los datos entran ya cargados ("crudo", ver `construir`), por eso los tests pueden usar paneles
sintéticos. La carga real (≤ 2004, load_dev / load_dev_curado) está en scripts/int13_corrida.py.

Convención: paneles "anchos" = fin de mes × país. Los rasgos son "as of" en el fin del mes M; los objetivos se miden
con valores de referencia (ex post).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata

from src.intl import int4 as M4
from src.intl import lags as Lg
from src.intl import termometro as T

SEMILLA = 20261030
FIN_DEV = pd.Timestamp("2004-12-31")
CORTE_TEMPORAL = pd.Timestamp("1989-12-31")
PRUEBA_DESDE = pd.Timestamp("1990-01-31")
ORIGEN_DESDE = pd.Timestamp("1960-01-31")
MIN_OTROS = 5                     # difusiones y medias "de los otros": ≥ 5 países con dato
SIN_BOLSA = T.SIN_BOLSA           # DNK, JPN
RETRASO_BIS = T.RETRASO_BIS       # 183 días
BLOQUE_MESES, REPS = 24, 1000
UMBRAL_E2, UMBRAL_E3 = 0.02, 1.0

OBJETIVOS = {"E1_6": 6, "E1_12": 12, "E2": 12, "E3": 12}
BASE = {"E1_6": ["curva", "d12_corto"], "E1_12": ["curva", "d12_corto"], "E2": ["ipc_yoy", "d12_ipc"],
        "E3": ["ipc_yoy", "tipo_real", "ip_yoy"]}
PAQUETES = {
    "P1_curva_tipos": ["curva", "corto", "d12_corto", "tipo_10a", "d12_10a", "tipo_real"],
    "P2_credito": ["cred_d4", "cred_d20", "cred_jst_d1"],
    "P3_actividad": ["ip_yoy", "d6_ip_yoy", "ventas_yoy", "paro_d12", "sahm", "confianza_emp", "d6_confianza"],
    "P4_precios": ["ipc_yoy", "acel_ipc", "sub_yoy", "d12_ipc", "mp_12m", "mp_3m"],
    "P5_mercados": ["bolsa_real_12m", "bolsa_3m", "vol_12m", "caida_24m"],
    "P6_global": ["dif_curva_inv", "dif_ip_neg", "glob_d12_corto", "glob_ipc", "glob_d12_ipc", "usa_curva",
                  "usa_d12_corto"],
}
_E1_MONO = {"curva": -1, "d12_corto": 1, "cred_d20": 1, "ip_yoy": -1, "paro_d12": 1, "sahm": 1, "bolsa_real_12m": -1,
            "vol_12m": 1, "dif_curva_inv": 1, "dif_ip_neg": 1}
MONOTONIA = {
    "E1_6": _E1_MONO, "E1_12": _E1_MONO,
    "E2": {"ip_yoy": 1, "paro_d12": -1, "acel_ipc": 1, "mp_12m": 1, "mp_3m": 1, "glob_d12_ipc": 1},
    "E3": {"tipo_real": -1, "ip_yoy": 1, "paro_d12": -1, "ipc_yoy": 1, "acel_ipc": 1, "glob_d12_corto": 1},
}
XGB_PARAMS = {"objective": "binary:logistic", "eta": 0.05, "max_depth": 2, "min_child_weight": 10, "subsample": 0.8,
              "colsample_bytree": 1.0, "lambda": 5.0, "alpha": 0.0, "tree_method": "hist", "max_bin": 64,
              "seed": SEMILLA, "nthread": 1, "verbosity": 0}
N_ARBOLES = 100
COMBO = "combinacion"


# ---------------------------------------------------------------- utilidades de paneles
def _me(idx) -> pd.DatetimeIndex:
    """Índice de fechas → fin de mes."""
    return pd.DatetimeIndex(idx) + pd.offsets.MonthEnd(0)


def _otros(w: pd.DataFrame, f) -> pd.DataFrame:
    """Para cada país, f(panel de los OTROS países) por fila, solo si ≥ MIN_OTROS tienen dato."""
    out = {}
    for c in w.columns:
        o = w.drop(columns=c)
        out[c] = f(o).where(o.notna().sum(axis=1) >= MIN_OTROS)
    return pd.DataFrame(out, index=w.index)


def difusion_neg(w: pd.DataFrame) -> pd.DataFrame:
    neg = (w < 0).astype(float).where(w.notna())
    return _otros(neg, lambda o: o.mean(axis=1))


def media_otros(w: pd.DataFrame) -> pd.DataFrame:
    return _otros(w, lambda o: o.mean(axis=1))


def trimestral_asof(s: pd.Series, k: int, rejilla: pd.DatetimeIndex) -> pd.Series:
    """Δk trimestres de una serie trimestral (fechada a inicio de trimestre), "as of" con el retraso del BIS."""
    if s is None or s.dropna().empty:
        return pd.Series(np.nan, index=rejilla)
    return T.asof_q(T._rejilla_q(s.dropna()).diff(k), RETRASO_BIS, rejilla)


def anual_asof(s: pd.Series, rejilla: pd.DatetimeIndex) -> pd.Series:
    """Serie anual (índice = año) "as of": el año Y se conoce a fin de año + 120 días (src/intl/lags.py, JST)."""
    s = s.dropna()
    if s.empty:
        return pd.Series(np.nan, index=rejilla)
    s = pd.Series(s.values, index=pd.to_datetime([f"{int(y)}-01-01" for y in s.index]))
    return Lg.asof(s, "jst_x", rejilla, freq="A")


# ---------------------------------------------------------------- objetivos
def entradas_recesion(pib: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Fechado trimestral del termómetro → (estado mensual ex post `en_rec` del trimestre que contiene cada mes,
    indicador mensual de entrada = último mes del trimestre de entrada). Índices: fin de mes."""
    fq = T.fechado_trimestral(pib.dropna())
    meses = pd.period_range(fq.index.min().asfreq("M", "start"), fq.index.max().asfreq("M", "end"), freq="M")
    qm = meses.asfreq("Q")
    en = fq["en_rec"].reindex(qm).to_numpy()
    entrada_q = {e for e in fq["entrada"].dropna().unique()}
    ent = np.array([(m.asfreq("Q") in entrada_q) and (m == m.asfreq("Q").asfreq("M", "end")) for m in meses], float)
    idx = meses.to_timestamp(how="end").normalize()
    return pd.Series(en, index=idx, dtype=float), pd.Series(ent, index=idx)


def objetivo_e1(en_rec: pd.Series, entrada: pd.Series, h: int) -> pd.Series:
    """y = 1 si hay una entrada en (M, M + h]; NaN si M está en recesión (fuera del conjunto en riesgo) o si el
    fechado no cubre M o M + h."""
    fut = sum(entrada.shift(-k) for k in range(1, h + 1))
    cubre = en_rec.notna() & en_rec.shift(-h).notna()
    y = (fut > 0).astype(float).where(cubre & (en_rec == 0))
    return y


def inflacion_ref(inflacion_mes: pd.DataFrame) -> pd.DataFrame:
    """π(m) = log IPC(m) − log IPC(m − 12) como suma de 12 variaciones mensuales (rejilla completa)."""
    return inflacion_mes.rolling(12, min_periods=12).sum()


def objetivo_e2(pi_ref: pd.DataFrame) -> pd.DataFrame:
    d = pi_ref.shift(-12) - pi_ref
    return (d > UMBRAL_E2).astype(float).where(d.notna())


def objetivo_e3(corto_ref: pd.DataFrame) -> pd.DataFrame:
    d = corto_ref.shift(-12) - corto_ref
    return (d >= UMBRAL_E3 - 1e-9).astype(float).where(d.notna())


# ---------------------------------------------------------------- rasgos y tabla larga
def construir(crudo: dict) -> pd.DataFrame:
    """Tabla larga (pais, fecha) con todos los rasgos "as of" y los 4 objetivos.

    `crudo`:
      w        : dict col → panel ancho (fin de mes × país) de src/intl/panel.mensual: ipc_yoy, ipc_6m_anual, sub_yoy,
                 tipo_10a, ip_yoy, ventas_yoy, paro_d12, confianza_emp, bolsa_12m ("as of"), r_bolsa_precio e
                 inflacion_mes (de referencia, sin retraso)
      corto_ref: panel ancho del tipo corto de referencia (fuente única por país, §1 del plan)
      bis      : país → crédito/PIB BIS trimestral;  jst_cred: panel año × país de Δ crédito/PIB (JST)
      mp       : rentabilidad spot mensual de materias primas (%, índice de fecha del mes)
      pib      : país → PIB trimestral;  sahm: panel ancho de la regla tipo Sahm "as of" (int8b.sahm_asof)
    """
    w = crudo["w"]
    rej = w["ipc_yoy"].index
    paises = list(w["ipc_yoy"].columns)
    al = lambda df: df.reindex(index=rej, columns=paises)  # noqa: E731
    f = {}
    corto = al(crudo["corto_ref"]).shift(1)           # tipos: en el fin de M se conoce M − 1
    pi = al(w["ipc_yoy"])
    f["corto"] = corto
    f["tipo_10a"] = al(w["tipo_10a"])
    f["curva"] = f["tipo_10a"] - corto
    f["d12_corto"] = corto - corto.shift(12)
    f["d12_10a"] = f["tipo_10a"] - f["tipo_10a"].shift(12)
    f["tipo_real"] = corto - 100 * pi
    f["cred_d4"] = pd.DataFrame({c: trimestral_asof(crudo["bis"].get(c), 4, rej) for c in paises}, index=rej)
    f["cred_d20"] = pd.DataFrame({c: trimestral_asof(crudo["bis"].get(c), 20, rej) for c in paises}, index=rej)
    jc = crudo["jst_cred"]
    f["cred_jst_d1"] = pd.DataFrame({c: anual_asof(jc[c], rej) if c in jc else np.nan for c in paises}, index=rej)
    f["ip_yoy"] = al(w["ip_yoy"])
    f["d6_ip_yoy"] = f["ip_yoy"] - f["ip_yoy"].shift(6)
    f["ventas_yoy"] = al(w["ventas_yoy"])
    f["paro_d12"] = al(w["paro_d12"])
    f["sahm"] = al(crudo["sahm"])
    f["confianza_emp"] = al(w["confianza_emp"])
    f["d6_confianza"] = f["confianza_emp"] - f["confianza_emp"].shift(6)
    f["ipc_yoy"] = pi
    f["acel_ipc"] = al(w["ipc_6m_anual"]) - pi
    f["sub_yoy"] = al(w["sub_yoy"])
    f["d12_ipc"] = pi - pi.shift(12)
    lr = np.log1p(crudo["mp"].dropna() / 100)
    lr = pd.Series(lr.values, index=_me(lr.index)).reindex(rej).shift(1)   # mercado: M − 1
    for k, n in (("mp_12m", 12), ("mp_3m", 3)):
        s = lr.rolling(n, min_periods=n).sum()
        f[k] = pd.DataFrame({c: s for c in paises}, index=rej)
    rb = al(w["r_bolsa_precio"]).shift(1)
    rb[[c for c in paises if c in SIN_BOLSA]] = np.nan
    f["bolsa_real_12m"] = al(w["bolsa_12m"]) - pi
    f["bolsa_real_12m"][[c for c in paises if c in SIN_BOLSA]] = np.nan
    f["bolsa_3m"] = rb.rolling(3, min_periods=3).sum()
    f["vol_12m"] = rb.rolling(12, min_periods=10).std()
    lp = rb.cumsum()
    f["caida_24m"] = (lp - lp.rolling(24, min_periods=12).max()).where(rb.notna())
    f["dif_curva_inv"] = difusion_neg(f["curva"])
    f["dif_ip_neg"] = difusion_neg(f["ip_yoy"])
    f["glob_d12_corto"] = media_otros(f["d12_corto"])
    f["glob_ipc"] = media_otros(pi)
    f["glob_d12_ipc"] = media_otros(f["d12_ipc"])
    for k, base in (("usa_curva", "curva"), ("usa_d12_corto", "d12_corto")):
        u = f[base]["USA"] if "USA" in paises else pd.Series(np.nan, index=rej)
        f[k] = pd.DataFrame({c: u for c in paises}, index=rej)
    # objetivos
    y = {}
    e1 = {}
    for c in paises:
        p = crudo["pib"].get(c)
        if p is None or p.dropna().empty:
            continue
        en, ent = entradas_recesion(p)
        e1[c] = (en.reindex(rej), ent.reindex(rej).fillna(0.0))
    for nom in ("E1_6", "E1_12"):
        h = OBJETIVOS[nom]
        y[nom] = pd.DataFrame({c: objetivo_e1(*e1[c], h) if c in e1 else np.nan for c in paises}, index=rej)
    y["E2"] = objetivo_e2(inflacion_ref(al(w["inflacion_mes"])))
    y["E3"] = objetivo_e3(al(crudo["corto_ref"]))
    largo = {k: v.stack(future_stack=True) for k, v in {**f, **{f"y_{k}": v for k, v in y.items()}}.items()}
    df = pd.DataFrame(largo)
    df.index.names = ["fecha", "pais"]
    df = df.reset_index()
    df = df[(df.fecha >= ORIGEN_DESDE) & (df.fecha <= FIN_DEV)].reset_index(drop=True)
    return df


def muestra(df: pd.DataFrame, obj: str) -> pd.DataFrame:
    """Filas con objetivo y con todas las variables de la base de `obj`; el objetivo acaba ≤ 2004-12."""
    h = OBJETIVOS[obj]
    ok = df[f"y_{obj}"].notna() & df[BASE[obj]].notna().all(axis=1)
    ok &= (df.fecha + pd.offsets.MonthEnd(h)) <= FIN_DEV
    return df[ok].reset_index(drop=True)


# ---------------------------------------------------------------- modelos
def _logit(p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return np.log(p / (1 - p))


def _sig(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def base_fit(X: np.ndarray, y: np.ndarray) -> dict:
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    return {"mu": mu, "sd": sd, "b": M4.logit_fit((X - mu) / sd, y)}


def base_margen(m: dict, X: np.ndarray) -> np.ndarray:
    b = m["b"]
    return b[0] + ((X - m["mu"]) / m["sd"]) @ b[1:]


def xgb_fit(X: np.ndarray, y: np.ndarray, margen: np.ndarray, mono: list[int], n_arboles: int = N_ARBOLES):
    import xgboost as xgb
    d = xgb.DMatrix(X, label=y, base_margin=margen, missing=np.nan)
    par = dict(XGB_PARAMS, monotone_constraints="(" + ",".join(str(int(m)) for m in mono) + ")")
    return xgb.train(par, d, num_boost_round=n_arboles)


def xgb_margen(bst, X: np.ndarray, margen: np.ndarray) -> np.ndarray:
    import xgboost as xgb
    return bst.predict(xgb.DMatrix(X, base_margin=margen, missing=np.nan), output_margin=True)


def mono_de(obj: str, cols: list[str]) -> list[int]:
    return [MONOTONIA[obj].get(c, 0) for c in cols]


def ajustar_predecir(tr: pd.DataFrame, te: pd.DataFrame, obj: str, n_arboles: int = N_ARBOLES) -> dict:
    """Clima, base, un XGBoost por paquete (corrección de la base) y la combinación fijada; devuelve probabilidades
    para `te`."""
    y = tr[f"y_{obj}"].to_numpy(float)
    mb = base_fit(tr[BASE[obj]].to_numpy(float), y)
    m_tr, m_te = base_margen(mb, tr[BASE[obj]].to_numpy(float)), base_margen(mb, te[BASE[obj]].to_numpy(float))
    out = {"clima": np.full(len(te), np.clip(y.mean(), 1e-6, 1 - 1e-6)), "base": _sig(m_te)}
    corr = []
    for pq, cols in PAQUETES.items():
        bst = xgb_fit(tr[cols].to_numpy(float), y, m_tr, mono_de(obj, cols), n_arboles)
        z = xgb_margen(bst, te[cols].to_numpy(float), m_te)
        out[pq] = _sig(z)
        corr.append(z - m_te)
    out[COMBO] = _sig(m_te + np.mean(corr, axis=0))
    return out


def loco(df: pd.DataFrame, obj: str, n_arboles: int = N_ARBOLES) -> pd.DataFrame:
    """V1: dejar un país fuera. Devuelve las filas con las probabilidades fuera de muestra."""
    partes = []
    for c in sorted(df.pais.unique()):
        tr, te = df[df.pais != c], df[df.pais == c]
        if tr[f"y_{obj}"].nunique() < 2 or te.empty:
            continue
        p = ajustar_predecir(tr, te, obj, n_arboles)
        partes.append(te[["pais", "fecha", f"y_{obj}"]].assign(**{f"p_{k}": v for k, v in p.items()}))
    return pd.concat(partes, ignore_index=True).rename(columns={f"y_{obj}": "y"})


def temporal(df: pd.DataFrame, obj: str, n_arboles: int = N_ARBOLES) -> pd.DataFrame:
    """V2: entreno con objetivo acabado ≤ 1989-12 (embargo), prueba 1990-01 … 2004-12 − h."""
    h = OBJETIVOS[obj]
    tr = df[(df.fecha + pd.offsets.MonthEnd(h)) <= CORTE_TEMPORAL]
    te = df[df.fecha >= PRUEBA_DESDE]
    p = ajustar_predecir(tr, te, obj, n_arboles)
    return te[["pais", "fecha", f"y_{obj}"]].assign(**{f"p_{k}": v for k, v in p.items()}).rename(
        columns={f"y_{obj}": "y"}).reset_index(drop=True)


# ---------------------------------------------------------------- métricas e incertidumbre
def ll_filas(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def auc(y, p) -> float:
    return M4.auc(np.asarray(y), np.asarray(p))


def bloques_meses(fechas: pd.Series, bloque: int = BLOQUE_MESES, reps: int = REPS, seed: int = SEMILLA) -> list:
    """Bootstrap de bloques móviles sobre los meses de calendario (todos los países del mes juntos). Devuelve, por
    réplica, el vector de índices de fila."""
    rng = np.random.default_rng(seed)
    meses = np.sort(fechas.unique())
    pos = {m: i for i, m in enumerate(meses)}
    filas_mes = [[] for _ in meses]
    for i, f in enumerate(fechas.to_numpy()):
        filas_mes[pos[f]].append(i)
    filas_mes = [np.array(v, int) for v in filas_mes]
    n, L = len(meses), min(bloque, len(meses))
    nb = int(np.ceil(n / L))
    out = []
    for _ in range(reps):
        ini = rng.integers(0, n - L + 1, nb)
        ms = np.concatenate([np.arange(s, s + L) for s in ini])[:n]
        out.append(np.concatenate([filas_mes[m] for m in ms]))
    return out


def comparar(P: pd.DataFrame, mod: str, lis: str, boot: list) -> dict:
    """Δ log-loss, Δ Brier (modelo − listón; negativo = mejor) y Δ AUC (positivo = mejor), con IC 95 % por bloques
    y p unilateral de mejora."""
    y = P["y"].to_numpy(float)
    pm, pl = P[f"p_{mod}"].to_numpy(), P[f"p_{lis}"].to_numpy()
    dll = ll_filas(y, pm) - ll_filas(y, pl)
    dbr = (pm - y) ** 2 - (pl - y) ** 2
    est = {"dlogloss": float(dll.mean()), "dbrier": float(dbr.mean()), "dauc": auc(y, pm) - auc(y, pl)}
    bs = {k: [] for k in est}
    for ix in boot:
        bs["dlogloss"].append(dll[ix].mean())
        bs["dbrier"].append(dbr[ix].mean())
        bs["dauc"].append(auc(y[ix], pm[ix]) - auc(y[ix], pl[ix]))
    out = {}
    for k, v in est.items():
        b = np.asarray(bs[k], float)
        b = b[np.isfinite(b)]
        sd = float(b.std(ddof=1)) if len(b) > 1 else np.nan
        signo = 1.0 if k == "dauc" else -1.0      # dirección de "mejor"
        p = float(1 - norm.cdf(signo * v / sd)) if sd and np.isfinite(sd) and sd > 0 and np.isfinite(v) else np.nan
        out[k] = {"est": v, "ic95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))] if len(b) else None,
                  "dt_boot": sd, "p_mejora": p}
    return out


def metricas(P: pd.DataFrame, mod: str, boot: list) -> dict:
    y = P["y"].to_numpy(float)
    p = P[f"p_{mod}"].to_numpy()
    ll = ll_filas(y, p)
    br = (p - y) ** 2
    a = [auc(y[ix], p[ix]) for ix in boot]
    a = np.asarray([v for v in a if np.isfinite(v)])
    ic = lambda b: [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]  # noqa: E731
    return {"logloss": float(ll.mean()), "logloss_ic95": ic([ll[ix].mean() for ix in boot]),
            "brier": float(br.mean()), "brier_ic95": ic([br[ix].mean() for ix in boot]),
            "auc": auc(y, p), "auc_ic95": ic(a) if len(a) else None, "calibracion": calibracion(y, p)}


def calibracion(y, p, n_bins: int = 10) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    c = M4.calibracion(y, p) if 0 < y.sum() < len(y) else {"intercepto": np.nan, "pendiente": np.nan}
    q = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    b = np.clip(np.searchsorted(q, p, side="right") - 1, 0, max(len(q) - 2, 0))
    tabla = [{"p_media": float(p[b == k].mean()), "frecuencia": float(y[b == k].mean()), "n": int((b == k).sum())}
             for k in range(max(len(q) - 1, 1)) if (b == k).any()]
    return {**c, "fiabilidad": tabla}


def potencia(delta: float, dt: float, años_dev: float = 45.0, años_nuevo: float = 20.0, alfa: float = 0.05) -> float:
    """Potencia aproximada de un contraste unilateral en una muestra nueva de `años_nuevo` años, si el efecto fuese
    `delta` y su dt con `años_dev` años fuese `dt` (escala con √(años_dev / años_nuevo))."""
    if not (np.isfinite(delta) and np.isfinite(dt) and dt > 0):
        return float("nan")
    return float(norm.cdf(abs(delta) / (dt * np.sqrt(años_dev / años_nuevo)) - norm.ppf(1 - alfa)))


def holm(ps: dict, alfa: float = 0.05) -> dict:
    orden = sorted(ps, key=lambda k: (np.nan_to_num(ps[k], nan=1.0)))
    k = len(ps)
    adj, prev = {}, 0.0
    for i, c in enumerate(orden):
        p = 1.0 if not np.isfinite(ps[c]) else ps[c]
        prev = max(prev, min(1.0, (k - i) * p))
        adj[c] = prev
    return {c: {"p_holm": adj[c], "rechaza": bool(adj[c] <= alfa)} for c in ps}


def importancias(df: pd.DataFrame, obj: str, n_arboles: int = N_ARBOLES) -> dict:
    """Ganancia media y |SHAP| medio por rasgo, ajustando con TODAS las filas ≤ 2004 (descriptivo)."""
    import xgboost as xgb
    y = df[f"y_{obj}"].to_numpy(float)
    Xb = df[BASE[obj]].to_numpy(float)
    m = base_margen(base_fit(Xb, y), Xb)
    out = {}
    for pq, cols in PAQUETES.items():
        X = df[cols].to_numpy(float)
        bst = xgb_fit(X, y, m, mono_de(obj, cols), n_arboles)
        g = bst.get_score(importance_type="gain")
        sh = bst.predict(xgb.DMatrix(X, base_margin=m, missing=np.nan), pred_contribs=True)[:, :-1]
        out[pq] = {c: {"ganancia": float(g.get(f"f{i}", 0.0)), "shap_abs_medio": float(np.abs(sh[:, i]).mean())}
                   for i, c in enumerate(cols)}
    return out
