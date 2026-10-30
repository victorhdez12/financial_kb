"""INT-10 (borrador): ¿con qué palanca LEGÍTIMA tendría potencia un modelo de ML frente al logit? Estudio de potencia
ANTES de construir nada (docs/int/INT10_ml_potencia_v0.md). Datos ≤ 2004 (src/intl/data.load_dev); nada ≥ 2005.

Contexto: INT-4-ML (cerrada) no batió al logit (ΔAUC −0,05 … +0,02). Prohibido: otros modelos / hiperparámetros sobre la
misma pregunta y los mismos datos. Aquí solo se mide cuánta potencia darían palancas que añaden INFORMACIÓN o EVENTOS:
  L1 objetivos más frecuentes (bolsa bajista, inflación, crisis bancaria; anual JST y mensual OCDE / Shiller);
  L2 multitarea (apilar objetivos) y su tamaño efectivo;
  L3 más unidades (16 países JST: núcleo + CAN, IRL; AUS y CHE fuera);
  L4 rasgos nuevos ya establecidos (X1 contagio, D/P, crédito): SOLO cobertura y propiedades de cada serie;
  L5 horizonte (h = 1, 2, 3): recuentos.

Qué usa (y nada más), en partes que NUNCA se juntan:
  (i)   OBJETIVOS: solo recuentos (eventos, años distintos, ICC por año, efecto de diseño, coincidencias ENTRE objetivos).
  (ii)  INDICADORES: cobertura, AR(1) y correlación entre países de CADA serie por separado. Nunca junto a un objetivo.
  (iii) POTENCIA: estructura REAL de eventos (país × periodo en riesgo) y puntuaciones SIMULADAS (binormales) para el
        "ML" y el "logit" con ruido correlacionado (r_mb), AR(1) en el tiempo y componente común entre países tomados de
        (ii). ΔAUC (Hoeffding/DeLong agrupado por bloques de tiempo) y Δlog-loss (probabilidades bien calibradas del
        binormal) con valor crítico ajustado por la nula simulada. r_mb se calibra con el error típico de ΔAUC YA
        PUBLICADO por INT-4-ML (corrida cerrada), no con datos nuevos.
Las AUC de los listones NO se miden: se suponen (A0 = 0,70 ≈ logit de INT-4).

Uso: .venv/bin/python -m scripts.int10_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int10_potencia --prueba   (sin puerta; no escribe nada; pocas réplicas)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts.int4_potencia import icc_anova, mde_auc
from scripts.int8_potencia import _ar1, influencia_auc
from src.intl import data as D
from src.intl import int4 as M
from src.intl import int6 as S
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
AMPLIADO = NUCLEO + ["CAN", "IRL"]                 # L3: AUS y CHE siguen fuera (prueba)
GUERRAS = M.GUERRAS
A0_LOGIT = 0.70
DELTAS = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15]
REALISTAS = (0.02, 0.03)                           # ganancia de ML frente a logit con la MISMA información (literatura)
# Error típico de ΔAUC estratificada (ML − logit) publicado por INT-4-ML (IC 95 % / 3,92), T1, 166 eventos
EE_INT4ML = {"M-L2|T1": (0.016 + 0.019) / 3.92, "M-GB|T1": (0.049 + 0.011) / 3.92}
RS_MB = (0.6, 0.8, 0.9, 0.95)
BAJISTA, FIN_BAJISTA = -0.20, -0.10
BLOQUE_M = 24


def _r(x, k=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


# ================================================================ (i) OBJETIVOS (solo recuentos)
def bajista_por_nivel(nivel: pd.Series, entrada: float = BAJISTA, fin: float = FIN_BAJISTA) -> tuple[pd.Series, set]:
    """Mercado bajista sobre un índice de nivel (real): entra cuando cae ≥ 20 % desde su máximo previo; el episodio acaba
    cuando vuelve a estar a menos del 10 % del máximo. Devuelve (estado 1/0 por periodo, periodos de entrada)."""
    x = nivel.dropna()
    dd = x / x.cummax() - 1
    en, est, ent = False, [], set()
    for t, v in dd.items():
        if not en and v <= entrada:
            en = True
            ent.add(t)
        elif en and v > fin:
            en = False
        est.append(float(en))
    return pd.Series(est, index=dd.index), ent


def filas_estado(est: pd.Series, ent: set, h: int, pais: str, periodos_ok=None) -> pd.DataFrame:
    """Periodos t fuera del estado, con t+1 … t+h observados; y = 1 si hay una entrada en (t, t+h]."""
    idx = list(est.index)
    pos = {t: i for i, t in enumerate(idx)}
    filas = []
    for t in idx:
        if est[t] == 1 or (periodos_ok is not None and not periodos_ok(t)):
            continue
        i = pos[t]
        if i + h >= len(idx):
            continue
        fut = idx[i + 1:i + h + 1]
        E = [f for f in fut if f in ent]
        filas.append({"pais": pais, "t": t, "y": int(bool(E)), "E": E[0] if E else None})
    return pd.DataFrame(filas, columns=["pais", "t", "y", "E"])


def _anual_ok(h: int):
    return lambda t: 1871 <= t and t + h <= 2004 and not any(y in GUERRAS for y in range(t, t + h + 1))


def objetivos_anuales(a: pd.DataFrame, paises: list[str], h: int) -> dict:
    """{objetivo: filas en riesgo (pais, t, y, E)} — JST, 1871-2004 sin guerras."""
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in paises}
    out = {}
    t1 = M.obj_entrada(rec, años_pais, paises, h, 1871, True)
    out["T1_recesion"] = _con_E(t1, h, {c: {int(x.pico) + 1 for _, x in rec[rec.pais == c].iterrows()} for c in paises})
    et = M.etiquetas_inflacion(a, paises)["principal"]
    t3 = M.obj_inflacion(et, paises, h, 1871, True, sube=True)
    ini_inf = {}
    for c in paises:
        s = et[et.pais == c].set_index("año")["p_i_alta"].dropna() >= M.UMBRAL_P
        ini_inf[c] = {int(t) for t in s.index[1:] if s[t] and not s.get(t - 1, True)}
    out["T3_inflacion"] = _con_E(t3, h, ini_inf)
    crisis = {c: a.xs(c, level=0)["crisisjst"].dropna() for c in paises}
    out["K_crisis_bancaria"] = S.objetivo_crisis(crisis, años_pais, paises, h, 1871, True)
    eq = a["eq_tr_real"]
    filas_b, filas_d = [], []
    for c in paises:
        x = eq.xs(c, level=0).dropna() if c in eq.index.get_level_values(0) else pd.Series(dtype=float)
        if x.empty:
            continue
        x.index = x.index.astype(int)
        x = x.reindex(range(x.index.min(), x.index.max() + 1))
        ev = set(x.index[x <= BAJISTA])
        est0 = pd.Series(0.0, index=x.index[x.notna()])
        filas_b.append(filas_estado(est0, ev, h, c, _anual_ok(h)))
        nivel = np.exp(np.log1p(x.fillna(0)).cumsum()).where(x.notna())
        # nivel solo en tramos sin huecos: se corta en el primer hueco interior
        nivel = nivel.loc[_tramo_sin_huecos(x)]
        est, ent = bajista_por_nivel(nivel)
        filas_d.append(filas_estado(est, ent, h, c, _anual_ok(h)))
    out["B1_bolsa_real_año_le_-20"] = pd.concat(filas_b, ignore_index=True)
    out["B2_bajista_drawdown_20"] = pd.concat(filas_d, ignore_index=True)
    return out


def _tramo_sin_huecos(x: pd.Series) -> pd.Index:
    """Índice del tramo más largo de años consecutivos con dato."""
    ok = x.notna().to_numpy()
    mejor, ini = (0, 0), None
    for i, v in enumerate(list(ok) + [False]):
        if v and ini is None:
            ini = i
        if not v and ini is not None:
            if i - ini > mejor[1] - mejor[0]:
                mejor = (ini, i)
            ini = None
    return x.index[mejor[0]:mejor[1]]


def _con_E(df: pd.DataFrame, h: int, inicios: dict) -> pd.DataFrame:
    if df.empty:
        return df.assign(E=None)
    E = []
    for c, t, y in zip(df.pais, df.t, df.y):
        e = [k for k in range(int(t) + 1, int(t) + h + 1) if k in inicios.get(c, set())]
        E.append(e[0] if (y and e) else None)
    return df[["pais", "t", "y"]].assign(E=E)


def objetivos_mensuales(con, h: int) -> dict:
    """Bajistas mensuales: OCDE (precio / IPC, 1957-2004, países con bolsa OCDE utilizable) y Shiller EE. UU. 1871-2004."""
    filas = []
    for c in AMPLIADO:
        if c in P.BOLSA_OCDE_ROTA:
            continue
        p = D.load_dev(con, f"oecd_share_{c.lower()}")
        i = D.load_dev(con, f"oecd_cpi_{c.lower()}_idx")
        if p.empty or i.empty:
            continue
        p.index, i.index = p.index.to_period("M"), i.index.to_period("M")
        r = (p / i.reindex(p.index)).dropna()
        r = r[r.index >= pd.Period("1957-01", "M")]
        if len(r) < 120:
            continue
        r = r.reindex(pd.period_range(r.index.min(), r.index.max(), freq="M"))
        r = r.loc[_tramo_sin_huecos(r)]
        est, ent = bajista_por_nivel(r)
        filas.append(filas_estado(est, ent, h, c, lambda t: t <= pd.Period("2004-12", "M")))
    out = {"BM_ocde_real": pd.concat(filas, ignore_index=True)}
    s = D.load_dev(con, "shiller_real_price")
    s.index = s.index.to_period("M")
    est, ent = bajista_por_nivel(s)
    out["BM_shiller_usa"] = filas_estado(est, ent, h, "USA")
    return out


def episodios(fechas: list, gap: int) -> int:
    fs = sorted(fechas)
    n, prev = 0, None
    for f in fs:
        d = None if prev is None else ((f - prev).n if isinstance(f, pd.Period) else f - prev)
        if prev is None or d > gap:
            n += 1
        prev = f
    return n


def resumen(df: pd.DataFrame, h: int, anual: bool = True) -> dict:
    if df.empty or df.y.sum() == 0:
        return {"filas_en_riesgo": int(len(df)), "eventos": 0}
    ev = df[df.y == 1][["pais", "E"]].dropna().drop_duplicates()
    años = ev.E.map(lambda e: e if anual else e.year).nunique()
    rho, mbar, mk = icc_anova(df.y, df.t.astype(str)) if df.pais.nunique() > 1 else (0.0, 1.0, 1.0)
    de = 1 + (mk - 1) * rho
    n1c, n0c = len(ev) / de, (df.y == 0).sum() / (de if anual else h)
    return {"filas_en_riesgo": int(len(df)), "filas_positivas": int(df.y.sum()), "tasa_base": _r(df.y.mean()),
            "eventos": int(len(ev)), "paises_con_evento": int(ev.pais.nunique()), "años_distintos": int(años),
            "episodios_agrupados": episodios(list(ev.E), 1 if anual else 6),
            "icc_por_periodo": _r(rho), "efecto_diseño": _r(de, 2),
            "pos_ef_central": _r(n1c, 1), "pos_ef_prudente": int(min(años, len(ev))), "neg_ef": _r(n0c, 1),
            "mde_hm_frente_a_B1_A0=0.60": _r(mde_auc(0.60, max(n1c, años), n0c, 2.80))}


def solape_objetivos(obj: dict, ventana: int = 1) -> dict:
    """Coincidencias ENTRE objetivos (no se toca ningún indicador): para cada par, % de eventos de A con un evento de B en
    el mismo país a ≤ `ventana` años; y nº de país-años con ≥ 1 evento de cualquier objetivo (unión)."""
    ev = {k: set(zip(v[v.y == 1].pais, v[v.y == 1].E.astype(int))) for k, v in obj.items() if v.y.sum()}
    out = {"pares": {}}
    for a, ea in ev.items():
        for b, eb in ev.items():
            if a >= b:
                continue
            hit = sum(any((c, t + d) in eb for d in range(-ventana, ventana + 1)) for c, t in ea)
            out["pares"][f"{a}~{b}"] = {"pct_de_A_con_B": _r(hit / len(ea)), "n_A": len(ea), "n_B": len(eb)}
    union = set().union(*ev.values())
    out["eventos_suma"] = int(sum(len(v) for v in ev.values()))
    out["pais_años_union"] = len(union)
    out["años_distintos_union"] = len({t for _, t in union})
    return out


# ================================================================ (ii) INDICADORES (cada serie por separado)
def indicadores_anuales(a: pd.DataFrame, paises: list[str]) -> dict:
    """Inventario L4 + parámetros del ruido: cobertura (país-años 1871-2004), AR(1) mediana y correlación media entre
    países de cada serie. Ningún objetivo interviene."""
    g = a.groupby(level=0)
    caida = (a["pib_real_g"] < 0).where(a["pib_real_g"].notna()).unstack(0)
    x1 = S.cuota_otros(caida.reindex(range(M.A0, M.A1 + 1)), NUCLEO, paises).stack()
    x1.index.names = ["año", "pais"]
    x1 = x1.swaplevel().sort_index()
    series = {
        "curva_(INT-4)": a["ltrate"] - a["stir"],
        "credito_pib_d5_(K1)": g["credito_pib"].diff(5),
        "bolsa_real_t_(INT-4)": a["eq_tr_real"],
        "inflacion": a["inflacion"],
        "D/P_(INT-7)": a["eq_dp"],
        "X1_cuota_otros_PIB_cae_(INT-6)": x1.reindex(a.index),
    }
    out = {}
    for k, s in series.items():
        w = s.astype(float).unstack(0).reindex(columns=paises)
        w = w[(w.index >= 1870) & (w.index <= 2004)]
        ar = [w[c].dropna().autocorr(1) for c in paises if w[c].notna().sum() >= 30]
        cors = []
        for i, p in enumerate(paises):
            for q in paises[i + 1:]:
                ok = w[p].notna() & w[q].notna()
                if ok.sum() >= 30:
                    cors.append(np.corrcoef(w.loc[ok, p], w.loc[ok, q])[0, 1])
        out[k] = {"pais_años": int(w.notna().to_numpy().sum()),
                  "pais_años_1950_2004": int(w[w.index >= 1950].notna().to_numpy().sum()),
                  "ar1_mediana": _r(np.nanmedian(ar)) if ar else None,
                  "corr_media_entre_paises": _r(np.nanmean(cors)) if cors else None}
    return out


# ================================================================ (iii) POTENCIA por simulación
def ruido(rng, nt: int, k: int, phi: float, rho: float) -> np.ndarray:
    return np.sqrt(rho) * _ar1(rng, nt, 1, phi) + np.sqrt(1 - rho) * _ar1(rng, nt, k, phi)


def codificar(df: pd.DataFrame, bloque: int = 1, compartir: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray,
                                                                                   np.ndarray]:
    """Filas → (y, índice de tiempo, índice de unidad, bloque de tiempo). Unidad = país, o tarea × país si hay `tarea`
    (ruido independiente entre tareas, optimista); con `compartir`, el mismo ruido para todas las tareas del mismo
    país-año (pesimista: los errores del modelo vienen de los mismos indicadores)."""
    t = df.t
    if isinstance(t.iloc[0], pd.Period):
        tt = np.array([p.ordinal for p in t])
    else:
        tt = t.to_numpy(int)
    it = tt - tt.min()
    u = df.pais if ("tarea" not in df or compartir) else df.tarea.astype(str) + "|" + df.pais
    iu = pd.Index(sorted(u.unique())).get_indexer(u)
    return df.y.to_numpy(int), it, iu, it // bloque


def _ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def un_ensayo(rng, y, it, iu, bl, a0, a1, phi, rho, r_mb):
    nt, nu = it.max() + 1, iu.max() + 1
    em = ruido(rng, nt, nu, phi, rho)[it, iu]
    ex = ruido(rng, nt, nu, phi, rho)[it, iu]
    eb = r_mb * em + np.sqrt(1 - r_mb ** 2) * ex
    mu1, mu0 = np.sqrt(2) * norm.ppf(a1), np.sqrt(2) * norm.ppf(a0)
    sm, sb = mu1 * y + em, mu0 * y + eb
    am, im = influencia_auc(sm, y)
    ab, ib = influencia_auc(sb, y)
    nb = np.bincount(bl).astype(bool).sum()
    g = np.bincount(bl, weights=im - ib)
    ee_auc = np.sqrt((g ** 2).sum() * nb / max(nb - 1, 1))
    lo = np.log(y.mean() / (1 - y.mean()))
    pm = 1 / (1 + np.exp(-(mu1 * sm - mu1 ** 2 / 2 + lo)))     # probabilidades bien calibradas del binormal
    pb = 1 / (1 + np.exp(-(mu0 * sb - mu0 ** 2 / 2 + lo)))
    d = _ll(pm, y) - _ll(pb, y)
    gl = np.bincount(bl, weights=d - d.mean())
    ee_ll = np.sqrt((gl ** 2).sum() * nb / max(nb - 1, 1)) / len(y)
    return am - ab, ee_auc, d.mean(), ee_ll


def simular(df: pd.DataFrame, phi: float, rho: float, r_mb: float, reps: int, rng, bloque: int = 1,
            a0: float = A0_LOGIT, deltas=DELTAS, nholm: int = 1, compartir: bool = False) -> dict:
    """Potencia de ΔAUC > 0 y Δlog-loss < 0 (bilateral 5 %, Holm-`nholm` el más exigente), con el valor crítico de la
    nula simulada. MDE = Δ con 80 %."""
    y, it, iu, bl = codificar(df, bloque, compartir)
    res = {}
    for d in deltas:
        z_a, z_l, dd, dl = [], [], [], []
        for _ in range(reps):
            da, ea, dll, el = un_ensayo(rng, y, it, iu, bl, a0, a0 + d, phi, rho, r_mb)
            z_a.append(da / ea)
            z_l.append(-dll / el)
            dd.append(da)
            dl.append(dll)
        res[d] = tuple(map(np.array, (z_a, z_l, dd, dl)))
    q = 1 - 0.05 / (2 * nholm)
    ca, cl = np.quantile(res[0.0][0], q), np.quantile(res[0.0][1], q)
    out = {"tamaño_nominal_auc": _r(np.mean(res[0.0][0] > norm.ppf(q))), "z_crit_auc": _r(ca), "z_crit_ll": _r(cl),
           "por_delta": {}}
    for d in deltas:
        za, zl, dd, dl = res[d]
        out["por_delta"][f"{d:.2f}"] = {"pot_auc": _r(np.mean(za > ca)), "pot_ll": _r(np.mean(zl > cl)),
                                       "ee_dauc": _r(np.std(dd), 4), "dlogloss_medio": _r(np.mean(dl), 4)}
    for k in ("pot_auc", "pot_ll"):
        xs = [(d, out["por_delta"][f"{d:.2f}"][k]) for d in deltas]
        mde = None
        for (d0, p0), (d1, p1) in zip(xs, xs[1:]):
            if p0 < 0.8 <= p1:
                mde = d0 + (0.8 - p0) * (d1 - d0) / (p1 - p0)
                break
        out[f"mde_{k[4:]}"] = _r(mde) if mde is not None else (f"> {deltas[-1]:.2f}" if xs[-1][1] < 0.8 else "≤ 0.01")
    mde = out["mde_auc"]
    if isinstance(mde, float):   # Δlog-loss esperado en la MDE de ΔAUC (interpolado)
        ds = np.array(deltas)
        out["dlogloss_en_mde_auc"] = _r(np.interp(mde, ds, [out["por_delta"][f"{d:.2f}"]["dlogloss_medio"]
                                                             for d in deltas]), 4)
    for d in REALISTAS:
        out[f"potencia_auc_en_{d:.2f}"] = out["por_delta"].get(f"{d:.2f}", {}).get("pot_auc")
    return out


def calibrar_r_mb(df: pd.DataFrame, phi: float, rho: float, reps: int, rng) -> dict:
    """ee(ΔAUC) simulado con Δ = 0,02 para cada r_mb, frente al publicado por INT-4-ML (T1, misma muestra de filas)."""
    y, it, iu, bl = codificar(df, 1)
    out = {}
    for r in RS_MB:
        ds = [un_ensayo(rng, y, it, iu, bl, A0_LOGIT, A0_LOGIT + 0.02, phi, rho, r)[0] for _ in range(reps)]
        out[f"r_mb={r}"] = _r(np.std(ds), 4)
    out["publicado_INT4ML"] = {k: _r(v, 4) for k, v in EE_INT4ML.items()}
    return out


def apilar(obj: dict, claves: list[str]) -> pd.DataFrame:
    return pd.concat([obj[k][["pais", "t", "y"]].assign(tarea=k) for k in claves], ignore_index=True)


# ================================================================ main
def main() -> None:
    borrador = "--prueba" in sys.argv
    proc = procedencia(exigir_limpio=not borrador)
    reps = 40 if borrador else 300
    rng = np.random.default_rng(20261030)
    con = D.connect()
    a = P.anual(con)
    res: dict = {"procedencia": proc, "nucleo": NUCLEO, "ampliado_L3": AMPLIADO, "fuera": ["AUS", "CHE"],
                 "supuestos": {"A0_logit": A0_LOGIT, "deltas": DELTAS, "realistas": list(REALISTAS),
                               "bajista": {"entrada": BAJISTA, "fin": FIN_BAJISTA}, "bloque_anual": 1,
                               "bloque_mensual_meses": BLOQUE_M, "rs_mb": list(RS_MB)}}

    # (ii) indicadores, por separado
    ind = indicadores_anuales(a, NUCLEO)
    res["L4_inventario_indicadores"] = ind
    tr = [v for v in ind.values() if v["ar1_mediana"] is not None]
    phi = float(np.median([v["ar1_mediana"] for v in tr]))
    rho = float(max(np.median([v["corr_media_entre_paises"] for v in tr]), 0.0))
    res["supuestos"]["phi_anual_(mediana_ar1)"], res["supuestos"]["rho_anual_(mediana_corr)"] = _r(phi), _r(rho)

    # (i) objetivos: recuentos, por horizonte y por grupo de países
    obj = {(g, h): objetivos_anuales(a, paises, h) for g, paises in (("nucleo", NUCLEO), ("ampliado", AMPLIADO))
           for h in (1, 2, 3)}
    res["L1_L3_L5_recuentos_anuales"] = {f"{g}|h{h}": {k: resumen(v, h) for k, v in o.items()}
                                         for (g, h), o in obj.items()}
    mens = {h: objetivos_mensuales(con, h) for h in (6, 12)}
    con.close()
    res["L1_recuentos_mensuales"] = {f"h{h}": {k: resumen(v, h, anual=False) for k, v in o.items()}
                                     for h, o in mens.items()}
    res["L2_solape_entre_objetivos_nucleo_h1"] = solape_objetivos(obj[("nucleo", 1)])

    # (iii) calibración de r_mb con el ee publicado de INT-4-ML (T1)
    t1 = obj[("nucleo", 1)]["T1_recesion"]
    res["calibracion_r_mb"] = calibrar_r_mb(t1, phi, rho, max(reps // 2, 20), rng)

    # (iii) potencia por palanca
    sim = {}
    o1, o3 = obj[("nucleo", 1)], obj[("ampliado", 1)]
    casos = {
        "L0_T1_referencia_(como_INT-4-ML)": (o1["T1_recesion"], 1),
        "L1_T3_inflacion": (o1["T3_inflacion"], 1),
        "L1_K_crisis_bancaria": (o1["K_crisis_bancaria"], 1),
        "L1_B1_bolsa_real_año": (o1["B1_bolsa_real_año_le_-20"], 1),
        "L1_B2_bajista_drawdown": (o1["B2_bajista_drawdown_20"], 1),
        "L2_apilado_T1+T3+B2+K": (apilar(o1, ["T1_recesion", "T3_inflacion", "B2_bajista_drawdown_20",
                                              "K_crisis_bancaria"]), 1),
        "L2_apilado_T3+B1+K_(sin_T1_cerrada)": (apilar(o1, ["T3_inflacion", "B1_bolsa_real_año_le_-20",
                                                            "K_crisis_bancaria"]), 1),
        "L3_T1_16_paises": (o3["T1_recesion"], 1),
        "L3+L2_apilado_16_paises": (apilar(o3, ["T1_recesion", "T3_inflacion", "B2_bajista_drawdown_20",
                                                "K_crisis_bancaria"]), 1),
        "L1_BM_ocde_mensual_h12": (mens[12]["BM_ocde_real"], BLOQUE_M),
    }
    for nom, (df, bloque) in casos.items():
        variantes = [(0.9, False), (0.6, False)] + ([(0.9, True)] if "apilado" in nom else [])
        for r_mb, comp in variantes:
            ph = 0.95 if bloque > 1 else phi            # mensual: AR(1) de las series mensuales (INT-8)
            rh = 0.5 if bloque > 1 else rho
            k = f"{nom}|r_mb={r_mb}" + ("|ruido_compartido" if comp else "")
            sim[k] = simular(df, ph, rh, r_mb, reps, rng, bloque=bloque, compartir=comp)
            print(k, sim[k]["mde_auc"], sim[k]["mde_ll"], sim[k].get("dlogloss_en_mde_auc"),
                  sim[k]["potencia_auc_en_0.02"], sim[k]["potencia_auc_en_0.03"], flush=True)
    res["simulacion"] = sim

    if not borrador:
        (REPO / "research" / "int" / "int10_potencia.json").write_text(
            json.dumps(res, indent=1, ensure_ascii=False, default=str))
    for gh, b in res["L1_L3_L5_recuentos_anuales"].items():
        for k, v in b.items():
            print(gh, k, {kk: v.get(kk) for kk in ("filas_en_riesgo", "eventos", "años_distintos", "efecto_diseño",
                                                   "pos_ef_central", "pos_ef_prudente", "mde_hm_frente_a_B1_A0=0.60")})
    for h, b in res["L1_recuentos_mensuales"].items():
        for k, v in b.items():
            print(h, k, {kk: v.get(kk) for kk in ("filas_en_riesgo", "eventos", "paises_con_evento",
                                                  "episodios_agrupados", "efecto_diseño", "pos_ef_central")})
    print(json.dumps(res["L2_solape_entre_objetivos_nucleo_h1"], ensure_ascii=False))
    print(json.dumps(res["calibracion_r_mb"]), json.dumps(ind, ensure_ascii=False))
    print(res["supuestos"])


if __name__ == "__main__":
    main()
