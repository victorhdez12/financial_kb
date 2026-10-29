"""INT-8 (borrador): potencia de una "probabilidad mensual de ENTRAR en recesión" a h = 3 y 6 meses, con datos mensuales y
trimestrales de la OCDE (18 países; desarrollo ≤ 2004). ANTES de construir nada (docs/int/INT8_diseno_v0.md).

Qué usa (y nada más), en partes separadas que NUNCA se juntan:
  (i)   OBJETIVOS (solo recuentos): cuatro fechados de "entrar en recesión" —
        O1 PIB-a: fechado trimestral del termómetro (src/intl/termometro.fechado_trimestral: suma de 4 trimestres cae dos
              trimestres seguidos), ya implementado y contrastado con JST (40/45 entradas ± 1 año);
        O2 PIB-t: "recesión técnica": dos caídas trimestrales seguidas del PIB real (q/q); entra en la 1.ª caída, sale
              con la 1.ª subida (no validado; solo recuentos);
        O3 BB-IP: picos de Bry-Boschan sobre el indicador IP + paro (INT-1 v2, giros_mensuales_v2_dev.parquet): FALLÓ su
              puerta dos veces, se cuenta solo como referencia;
        O4 NBER (USREC), solo EE. UU.
        CLI/ECRI: no hay series de puntos de giro en el warehouse (se comprueba y se publica la lista).
  (ii)  INDICADORES (solo propiedades de cada serie por separado): AR(1) por país y correlación media entre países de la
        misma serie; y su DISPONIBILIDAD (máscara "con curva"), nunca su valor junto a un objetivo.
  (iii) POTENCIA: (a) Hanley-McNeil con positivos/negativos efectivos (Kish por agrupación de eventos en el mismo mes);
        (b) simulación con la estructura REAL de eventos y puntuaciones SIMULADAS (binormales, componente común entre
        países y AR(1) en el tiempo, tomados de (ii)), ΔAUC con varianza por bloques de tiempo de 24 meses (DeLong
        agrupado; contrastado con un bootstrap por bloques de verdad en un caso); (c) calibración.
Las AUC de los listones NO se miden: se suponen (A0 = 0,55 / 0,60 / 0,70).

Uso: .venv/bin/python -m scripts.int8_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int8_potencia --prueba   (sin puerta; no escribe nada; pocas réplicas)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts.int4_potencia import icc_anova, mde_auc
from src.intl import data as D
from src.intl import panel as P
from src.intl import termometro as T
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
PRUEBA = {"AUS", "CHE", "CAN", "IRL"}
NUCLEO = [c for c in D.PAISES if c not in PRUEBA]
DESDE, HASTA = pd.Period("1960-01", "M"), pd.Period("2004-12", "M")
HS = (3, 6, 12)                     # 12 solo como comparación con INT-4
A0S = (0.55, 0.60, 0.70)
Z1 = norm.ppf(0.975) + norm.ppf(0.80)                 # 2,80
ZH2 = norm.ppf(1 - 0.05 / 4) + norm.ppf(0.80)         # 3,08 (Holm sobre h = 3 y 6, el más exigente)
GAP_EPISODIO = 6                    # meses: entradas de cualquier país a ≤ 6 meses de la anterior = mismo episodio
BLOQUE = 24                         # meses por bloque de tiempo (todos los países juntos)
R_MB = 0.5                          # correlación del ruido modelo-listón
INDICADORES = ("curva", "ip_yoy", "bolsa_12m", "paro_d12", "cli_d6", "confianza_emp")


def _r(x, k=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


# ================================================================ (i) OBJETIVOS (solo recuentos)
def _meses_q(per: pd.Period) -> list[pd.Period]:
    m0 = per.asfreq("M", "start")
    return [m0, m0 + 1, m0 + 2]


def fechado_pib_t(pib: pd.Series) -> pd.DataFrame:
    """Recesión técnica: entra si caen dos trimestres seguidos (q/q); el primero de ellos es el de entrada; sale con la
    primera subida. Devuelve por trimestre `en_rec` (ex post) y la lista de trimestres de entrada."""
    q = T._rejilla_q(pib)
    d = np.log(q).diff()
    en, estado, entradas = False, {}, []
    idx = list(d.index)
    for i, per in enumerate(idx):
        if not np.isfinite(d.iloc[i]):
            estado[per] = np.nan
            continue
        if not en and i and np.isfinite(d.iloc[i - 1]) and d.iloc[i - 1] < 0 and d.iloc[i] < 0:
            en = True
            entradas.append(idx[i - 1])
            estado[idx[i - 1]] = True
        elif en and d.iloc[i] > 0:
            en = False
        estado[per] = en
    return pd.DataFrame({"en_rec": pd.Series(estado)}), entradas


def a_mensual(estado_q: pd.Series, entradas_q: list) -> tuple[pd.Series, set]:
    """Estado trimestral ex post → mensual (cada mes hereda su trimestre); entrada = primer mes del trimestre."""
    filas = {}
    for per, v in estado_q.items():
        for m in _meses_q(per):
            filas[m] = v
    return pd.Series(filas, dtype=float).sort_index(), {_meses_q(e)[0] for e in entradas_q}


def objetivos(con) -> dict:
    """{objetivo: {país: (estado mensual ex post 1/0/NaN, set de meses de entrada)}}."""
    out = {"O1_PIB_a": {}, "O2_PIB_t": {}, "O3_BB_IP": {}, "O4_NBER": {}}
    for c in D.PAISES:
        pib = D.load_dev_curado(f"oecd_gdpq_{c.lower()}")
        fq = T.fechado_trimestral(pib)
        ent = sorted({e for e in fq["entrada"].dropna().unique()})
        out["O1_PIB_a"][c] = a_mensual(fq["en_rec"].astype(float), ent)
        est, ent_t = fechado_pib_t(pib)
        out["O2_PIB_t"][c] = a_mensual(est["en_rec"].astype(float), ent_t)
    g = pd.read_parquet(db.DATA_ROOT / "intl" / "giros_mensuales_v2_dev.parquet")
    pm = P.mensual(con)
    for c, gc in g.groupby("pais"):
        ip = pm.xs(c, level=0)["ip_yoy"].dropna() if c in pm.index.get_level_values(0) else pd.Series(dtype=float)
        if ip.empty:
            continue
        rej = pd.period_range(ip.index.min().to_period("M"), HASTA, freq="M")
        gc = gc.sort_values("fecha")
        est = pd.Series(np.nan, index=rej)
        estado = np.nan
        giros = {pd.Timestamp(f).to_period("M"): t for f, t in zip(gc.fecha, gc.tipo)}
        for m in rej:   # antes del primer giro: NaN; el mes del pico es expansión y el del valle, recesión
            if m in giros:
                est[m] = 0.0 if giros[m] == "pico" else 1.0
                estado = 1.0 if giros[m] == "pico" else 0.0
            else:
                est[m] = estado
        ent = {m + 1 for m, t in giros.items() if t == "pico"}
        out["O3_BB_IP"][c] = (est, ent)
    u = D.load_dev(con, "USREC")
    u.index = u.index.to_period("M")
    ent = set(u.index[(u == 1) & (u.shift(1) == 0)])
    out["O4_NBER"]["USA"] = (u.astype(float), ent)
    return out


def filas_en_riesgo(est: pd.Series, ent: set, h: int, mascara: set | None = None, pais: str = "") -> pd.DataFrame:
    """Meses m fuera de recesión (ex post), con estado conocido en m … m + h, DESDE ≤ m ≤ HASTA − h; y = 1 si hay una
    entrada en (m, m + h]."""
    filas = []
    for m, v in est.items():
        if m < DESDE or m > HASTA - h or not np.isfinite(v) or v == 1:
            continue
        if mascara is not None and (pais, m) not in mascara:
            continue
        fut = [m + k for k in range(1, h + 1)]
        if any((f not in est.index) or not np.isfinite(est[f]) for f in fut):
            continue
        E = [f for f in fut if f in ent]
        filas.append({"pais": pais, "m": m, "y": int(bool(E)), "E": E[0] if E else None})
    return pd.DataFrame(filas, columns=["pais", "m", "y", "E"])


def episodios(fechas: list[pd.Period], gap: int = GAP_EPISODIO) -> list[list[str]]:
    fs = sorted(fechas)
    out: list[list[pd.Period]] = []
    for f in fs:
        if out and (f - out[-1][-1]).n <= gap:
            out[-1].append(f)
        else:
            out.append([f])
    return [[str(x) for x in e] for e in out]


def mde_rejilla(n1, n0) -> dict:
    return {f"A0={a:.2f}": {"1_contraste": _r(mde_auc(a, n1, n0, Z1)), "holm_2": _r(mde_auc(a, n1, n0, ZH2))}
            for a in A0S}


def resumen(df: pd.DataFrame, h: int) -> dict:
    if df.empty or df.y.sum() == 0:
        return {"filas_en_riesgo": int(len(df)), "eventos": 0}
    pos = df[df.y == 1]
    ev = pos[["pais", "E"]].drop_duplicates()
    eps = episodios(list(ev.E))
    años = sorted({e.year for e in ev.E})
    rho, mbar, mk = icc_anova(df.y, df.m.astype(str)) if df.pais.nunique() > 1 else (0.0, 1.0, 1.0)
    de = 1 + (mk - 1) * rho
    n0 = (df.y == 0).sum() / h
    n1c, n0c = len(ev) / de, n0 / de
    out = {"filas_en_riesgo": int(len(df)), "filas_positivas": int(len(pos)), "tasa_base_filas": _r(df.y.mean()),
           "eventos": int(len(ev)), "paises_con_evento": int(ev.pais.nunique()),
           "años_distintos": len(años), "episodios_agrupados": len(eps),
           "episodios": [f"{e[0]}…{e[-1]} ({len(e)})" for e in eps],
           "icc_por_mes": _r(rho), "paises_por_mes": _r(mbar, 2), "m_kish": _r(mk, 2), "efecto_diseño": _r(de, 2),
           "pos_ef_central": _r(n1c, 1), "neg_ef_central": _r(n0c, 1), "pos_ef_prudente": len(eps),
           "mde_central": mde_rejilla(n1c, n0c), "mde_prudente": mde_rejilla(len(eps), n0c)}
    return out


def eventos_por_pais(obj: dict) -> dict:
    out = {}
    for c, (est, ent) in obj.items():
        e = sorted(x for x in ent if DESDE <= x <= HASTA)
        out[c] = {"n": len(e), "fechas": [str(x) for x in e],
                  "primer_mes_con_estado": str(est.dropna().index.min()) if est.notna().any() else None}
    return out


# ================================================================ (ii) INDICADORES (cada serie por separado)
def propiedades_indicadores(pm: pd.DataFrame) -> dict:
    out = {}
    for col in INDICADORES:
        w = pm[col].unstack(0).reindex(columns=NUCLEO)
        w = w[w.index <= D.DEV_END]
        ar = {c: _r(w[c].dropna().autocorr(1)) for c in NUCLEO if w[c].notna().sum() >= 60}
        cors = []
        for i, a in enumerate(NUCLEO):
            for b in NUCLEO[i + 1:]:
                ok = w[a].notna() & w[b].notna()
                if ok.sum() >= 60:
                    cors.append(np.corrcoef(w.loc[ok, a], w.loc[ok, b])[0, 1])
        v = [x for x in ar.values() if x is not None]
        out[col] = {"ar1_por_pais": ar, "ar1_mediana": _r(np.median(v)) if v else None,
                    "corr_media_entre_paises": _r(np.mean(cors)) if cors else None, "pares": len(cors),
                    "tiempo_real": col not in P.NO_TIEMPO_REAL}
    return out


def ar1_objetivo(df: pd.DataFrame) -> float | None:
    v = [g.sort_values("m").y.autocorr(1) for _, g in df.groupby("pais") if len(g) > 24 and g.y.std() > 0]
    v = [x for x in v if np.isfinite(x)]
    return _r(np.median(v)) if v else None


def mascara_curva(pm: pd.DataFrame) -> set:
    s = pm["curva"].dropna()
    return {(p, f.to_period("M")) for p, f in s.index}


def cli_en_warehouse(con) -> dict:
    df = con.execute("select series_id, min(date) d0 from obs_latest where series_id like 'oecd_cli_%' "
                     "and date <= ? group by 1 order by 1", [D.DEV_END.date()]).df()
    gir = con.execute("select count(distinct series_id) from obs_latest where lower(series_id) like '%turn%' "
                      "or lower(series_id) like '%ecri%' or lower(series_id) like '%cepr%'").fetchone()[0]
    return {"cli_series": {r.series_id: str(r.d0)[:7] for r in df.itertuples()},
            "series_de_puntos_de_giro_(ecri/cepr/turning)": int(gir)}


# ================================================================ (iii) POTENCIA por simulación
def matriz_y(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Filas en riesgo → (y, índice de mes, índice de país, bloque) para la simulación."""
    meses = pd.period_range(DESDE, HASTA, freq="M")
    im = meses.get_indexer(pd.PeriodIndex(df.m, freq="M"))
    paises = sorted(df.pais.unique())
    ic = pd.Index(paises).get_indexer(df.pais)
    return df.y.to_numpy(int), im, ic, im // BLOQUE


def _ar1(rng, nt: int, k: int, phi: float) -> np.ndarray:
    e = rng.standard_normal((nt, k))
    out = np.empty_like(e)
    out[0] = e[0]
    s = np.sqrt(1 - phi ** 2)
    for t in range(1, nt):
        out[t] = phi * out[t - 1] + s * e[t]
    return out


def ruido(rng, nt: int, npais: int, phi: float, rho: float) -> np.ndarray:
    """Ruido de varianza 1 con un componente común entre países (fracción rho) y AR(1) phi en el tiempo."""
    com = _ar1(rng, nt, 1, phi)
    idi = _ar1(rng, nt, npais, phi)
    return np.sqrt(rho) * com + np.sqrt(1 - rho) * idi


def influencia_auc(s: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray]:
    """AUC y su función de influencia (proyección de Hoeffding/DeLong) por fila: Â − A ≈ Σ infl."""
    pos, neg = s[y == 1], s[y == 0]
    n1, n0 = len(pos), len(neg)
    ns, ps = np.sort(neg), np.sort(pos)
    v10 = (np.searchsorted(ns, pos, "left") + np.searchsorted(ns, pos, "right")) / (2 * n0)
    v01 = 1 - (np.searchsorted(ps, neg, "left") + np.searchsorted(ps, neg, "right")) / (2 * n1)
    a = float(v10.mean())
    infl = np.empty(len(s))
    infl[y == 1] = (v10 - a) / n1
    infl[y == 0] = (v01 - a) / n0
    return a, infl


def delta_ee(sm, sb, y, bloque) -> tuple[float, float]:
    am, im = influencia_auc(sm, y)
    ab, ib = influencia_auc(sb, y)
    g = np.bincount(bloque, weights=im - ib)
    nb = (np.bincount(bloque) > 0).sum()
    return am - ab, float(np.sqrt((g ** 2).sum() * nb / max(nb - 1, 1)))


def puntuaciones(rng, y, im, ic, a0, a1, phi, rho):
    nt, npais = im.max() + 1, ic.max() + 1
    em = ruido(rng, nt, npais, phi, rho)[im, ic]
    ex = ruido(rng, nt, npais, phi, rho)[im, ic]
    eb = R_MB * em + np.sqrt(1 - R_MB ** 2) * ex
    mu = lambda a: np.sqrt(2) * norm.ppf(a)  # noqa: E731
    return mu(a1) * y + em, mu(a0) * y + eb


def simular(df, a0, deltas, phi, rho, reps, rng) -> dict:
    y, im, ic, bl = matriz_y(df)
    res = {}
    for d in deltas:
        z = np.empty(reps)
        dd = np.empty(reps)
        for r in range(reps):
            sm, sb = puntuaciones(rng, y, im, ic, a0, a0 + d, phi, rho)
            dd[r], ee = delta_ee(sm, sb, y, bl)
            z[r] = dd[r] / ee
        res[d] = (z, dd)
    z0 = res[0.0][0]
    c1, ch = np.quantile(z0, 0.975), np.quantile(z0, 1 - 0.05 / 4)
    out = {"tamaño_nominal_1": _r(np.mean(z0 > norm.ppf(0.975))), "z_critico_empirico_1": _r(c1),
           "z_critico_empirico_holm2": _r(ch), "por_delta": {}}
    for d in deltas:
        z, dd = res[d]
        out["por_delta"][f"{d:.2f}"] = {"potencia_1": _r(np.mean(z > norm.ppf(0.975))),
                                       "potencia_holm2": _r(np.mean(z > norm.ppf(1 - 0.05 / 4))),
                                       "potencia_1_ajust": _r(np.mean(z > c1)), "potencia_holm2_ajust": _r(np.mean(z > ch)),
                                       "sd_delta_hat": _r(np.std(dd))}
    for k in ("potencia_1_ajust", "potencia_holm2_ajust"):
        xs = [(d, out["por_delta"][f"{d:.2f}"][k]) for d in deltas]
        mde = None
        for (d0, p0), (d1, p1) in zip(xs, xs[1:]):
            if p0 < 0.8 <= p1:
                mde = d0 + (0.8 - p0) * (d1 - d0) / (p1 - p0)
                break
        out[f"mde_{k.replace('potencia_', '')}"] = _r(mde) if mde is not None else (
            f"> {deltas[-1]:.2f}" if xs[-1][1] < 0.8 else f"≤ {deltas[1]:.2f}")
    return out


def bootstrap_bloques(df, a0, d, phi, rho, reps, nboot, rng) -> dict:
    """Comprobación: bootstrap por bloques de tiempo de verdad (se remuestrean bloques de 24 meses con todos los países)."""
    y, im, ic, bl = matriz_y(df)
    ub = np.unique(bl)
    filas_b = {b: np.flatnonzero(bl == b) for b in ub}
    ok = 0
    for _ in range(reps):
        sm, sb = puntuaciones(rng, y, im, ic, a0, a0 + d, phi, rho)
        ds = []
        for _ in range(nboot):
            idx = np.concatenate([filas_b[b] for b in rng.choice(ub, len(ub))])
            if y[idx].min() == y[idx].max():
                continue
            ds.append(influencia_auc(sm[idx], y[idx])[0] - influencia_auc(sb[idx], y[idx])[0])
        ok += np.quantile(ds, 0.025) > 0
    return {"potencia_bootstrap_bloques_1": _r(ok / reps), "reps": reps, "nboot": nboot}


# ================================================================ calibración
def _logit_fit(x, y, it=30):
    X = np.column_stack([np.ones_like(x), x])
    b = np.zeros(2)
    for _ in range(it):
        p = 1 / (1 + np.exp(-X @ b))
        W = p * (1 - p)
        b = b + np.linalg.solve(X.T @ (X * W[:, None]) + 1e-9 * np.eye(2), X.T @ (y - p))
    return b


def calibracion(n1: int, n0: int, auc: float, reps: int, rng) -> dict:
    """Modelo bien calibrado (AUC dada) con n1 eventos y n0 no eventos INDEPENDIENTES (los efectivos): distribución de la
    pendiente de calibración estimada y del cociente eventos observados / predichos."""
    mu = np.sqrt(2) * norm.ppf(auc)
    pend, cociente = [], []
    for _ in range(reps):
        x = np.r_[rng.standard_normal(n1) + mu, rng.standard_normal(n0)]
        y = np.r_[np.ones(n1), np.zeros(n0)]
        lp = mu * x - mu ** 2 / 2 + np.log(n1 / n0)     # logit verdadero
        b = _logit_fit(lp, y)
        pend.append(b[1])
        # calibración en lo grande: con eventos ~ Poisson alrededor de lo predicho
        cociente.append(rng.poisson(n1) / n1)
    pend = np.array(pend)
    return {"n1": n1, "n0": n0, "auc": auc, "pendiente_sd": _r(np.std(pend)),
            "pendiente_ic95": [_r(np.quantile(pend, 0.025)), _r(np.quantile(pend, 0.975))],
            "p_pendiente_en_0.5_1.5": _r(np.mean((pend >= 0.5) & (pend <= 1.5))),
            "cociente_obs_pred_ic95": [_r(np.quantile(cociente, 0.025)), _r(np.quantile(cociente, 0.975))]}


# ================================================================ main
def main() -> None:
    borrador = "--prueba" in sys.argv
    proc = procedencia(exigir_limpio=not borrador)
    reps = 60 if borrador else 400
    rng = np.random.default_rng(20261029)
    con = D.connect()
    obj = objetivos(con)
    pm = P.mensual(con)
    props = propiedades_indicadores(pm)          # (ii): indicadores, por separado
    masc = mascara_curva(pm)                     # solo disponibilidad
    cli = cli_en_warehouse(con)
    con.close()

    res: dict = {"procedencia": proc, "nucleo": NUCLEO, "prueba": sorted(PRUEBA),
                 "supuestos": {"A0_supuestas": list(A0S), "z1": _r(Z1), "z_holm2": _r(ZH2), "r_modelo_liston": R_MB,
                               "bloque_meses": BLOQUE, "gap_episodio_meses": GAP_EPISODIO,
                               "muestra": f"{DESDE} … {HASTA} (meses en riesgo; objetivo ex post, datos revisados)"},
                 "cli_y_puntos_de_giro": cli, "indicadores": props, "eventos_por_pais": {}, "recuentos": {}}
    for k, o in obj.items():
        res["eventos_por_pais"][k] = eventos_por_pais(o)

    dfs = {}
    for k, o in obj.items():
        grupos = {"nucleo": [c for c in NUCLEO if c in o], "todos_18": list(o)} if k != "O4_NBER" else {"usa": ["USA"]}
        for g, paises in grupos.items():
            for mk in ("todo", "con_curva"):
                for h in HS:
                    df = pd.concat([filas_en_riesgo(o[c][0], o[c][1], h, masc if mk == "con_curva" else None, c)
                                    for c in paises], ignore_index=True)
                    r = resumen(df, h)
                    r["ar1_objetivo_mediana"] = ar1_objetivo(df)
                    res["recuentos"].setdefault(k, {}).setdefault(g, {}).setdefault(mk, {})[f"h{h}"] = r
                    dfs[(k, g, mk, h)] = df

    # parámetros del ruido desde las propiedades de las series (tiempo real; sin CLI, que no lo es)
    tr = [v for c, v in props.items() if v["tiempo_real"] and v["ar1_mediana"] is not None]
    phi_c = float(np.median([v["ar1_mediana"] for v in tr]))
    rho_c = float(np.median([v["corr_media_entre_paises"] for v in tr if v["corr_media_entre_paises"] is not None]))
    res["supuestos"]["phi_central_(mediana_ar1_indicadores)"] = _r(phi_c)
    res["supuestos"]["rho_central_(mediana_corr_entre_paises)"] = _r(max(rho_c, 0.0))
    deltas = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35]
    escenarios = {"central": (phi_c, max(rho_c, 0.0)), "optimista_phi0.5_rho0": (0.5, 0.0)}
    sim = {}
    for k in ("O1_PIB_a", "O2_PIB_t"):
        for mk in ("todo", "con_curva"):
            for h in (3, 6):
                df = dfs[(k, "nucleo", mk, h)]
                for a0 in (0.55, 0.60):
                    for esc, (phi, rho) in escenarios.items():
                        if esc != "central" and a0 != 0.60:
                            continue
                        sim[f"{k}|{mk}|h{h}|A0={a0:.2f}|{esc}"] = simular(df, a0, deltas, phi, rho, reps, rng)
                        print(k, mk, h, a0, esc, sim[f"{k}|{mk}|h{h}|A0={a0:.2f}|{esc}"]["mde_holm2_ajust"], flush=True)
    res["simulacion"] = sim
    base = sim["O1_PIB_a|todo|h6|A0=0.60|central"]["por_delta"]
    res["comprobacion_bootstrap"] = {"caso": "O1_PIB_a|nucleo|todo|h6|A0=0.60|central (IC 95 % percentil > 0)"}
    for d in (0.0, 0.20):
        res["comprobacion_bootstrap"][f"delta={d:.2f}"] = {
            **bootstrap_bloques(dfs[("O1_PIB_a", "nucleo", "todo", 6)], 0.60, d, phi_c, max(rho_c, 0.0),
                                20 if borrador else 100, 100 if borrador else 400, rng),
            "delong_agrupado_nominal_mismo_caso": base[f"{d:.2f}"]["potencia_1"]}

    # calibración: con los eventos efectivos (central y prudente) de O1 núcleo h = 6
    cal = {}
    for mk in ("todo", "con_curva"):
        r = res["recuentos"]["O1_PIB_a"]["nucleo"][mk]["h6"]
        n0 = int(round(r["neg_ef_central"]))
        for nom, n1 in (("central", int(round(r["pos_ef_central"]))), ("prudente", r["pos_ef_prudente"])):
            cal[f"{mk}|{nom}"] = calibracion(max(n1, 2), max(n0, 10), 0.75, 2000 if not borrador else 200, rng)
    for n1 in (10, 20, 40):
        cal[f"referencia|n1={n1}"] = calibracion(n1, 20 * n1, 0.75, 2000 if not borrador else 200, rng)
    res["calibracion"] = cal
    eps = res["recuentos"]["O1_PIB_a"]["nucleo"]["todo"]["h6"]["episodios_agrupados"]
    años_dev = (HASTA.year - DESDE.year + 1)
    res["vivo"] = {"episodios_por_decada_dev": _r(10 * eps / años_dev, 2),
                   "años_para_10_episodios": _r(10 / (eps / años_dev), 0),
                   "años_para_20_episodios": _r(20 / (eps / años_dev), 0)}

    if not borrador:
        (REPO / "research" / "int" / "int8_potencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False,
                                                                                default=str))
    for k, b in res["recuentos"].items():
        for g, bb in b.items():
            for mk, bbb in bb.items():
                for h, v in bbb.items():
                    if v.get("eventos"):
                        print(f"{k:9s} {g:8s} {mk:9s} {h:3s} filas={v['filas_en_riesgo']} ev={v['eventos']} "
                              f"años={v['años_distintos']} epis={v['episodios_agrupados']} icc={v['icc_por_mes']} "
                              f"DE={v['efecto_diseño']} n1c={v['pos_ef_central']} "
                              f"mdeC={v['mde_central']['A0=0.60']} mdeP={v['mde_prudente']['A0=0.60']}")
    print(json.dumps({k: v["ar1_mediana"] for k, v in props.items()}), json.dumps(
        {k: v["corr_media_entre_paises"] for k, v in props.items()}))
    print(json.dumps(res["comprobacion_bootstrap"]), json.dumps(res["vivo"]))
    print(json.dumps(cal, indent=0))


if __name__ == "__main__":
    main()
