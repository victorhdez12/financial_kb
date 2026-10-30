"""Validador INT-14: reproducción INDEPENDIENTE de H1-H4 (efecto, IC 90 %, placebo corregido) y sensibilidades
A POSTERIORI del placebo de H1. Solo datos <= 2004. No usa efecto_panel / placebo_panel / ic_* de src/intl/eventos.py
(solo el cargador `Datos` y, para el petróleo, la definición de evento ya validada en fase 1).

Uso: .venv/bin/python -m scripts.val_int14_repro  → research/int/val_int14/repro.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from scripts.int14_potencia import Datos, construir_eventos          # noqa: E402  (solo carga + petróleo)
from src.intl.data import PAISES                                     # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "research" / "int" / "val_int14"
SEM = 20261030
WAR = set(range(1914, 1919)) | set(range(1939, 1946))
AÑOS = np.arange(1871, 2005)


# ------------------------------------------------------------------ datos propios
def panel_real(D):
    cpi = pd.DataFrame({c: D.anual(f"jst_{c.lower()}_cpi") for c in PAISES})
    inf = cpi / cpi.shift(1) - 1
    out = {}
    for a, col in (("bolsa", "eq_tr"), ("vivienda", "housing_tr"), ("bonos", "bond_tr"), ("letras", "bill_rate")):
        tr = pd.DataFrame({c: D.anual(f"jst_{c.lower()}_{col}") for c in PAISES})
        x = ((1 + tr) / (1 + inf) - 1).reindex(AÑOS)
        x.loc[[y for y in AÑOS if y in WAR]] = np.nan
        out[a] = x
    return out


def crisis_propias(D):
    filas = []
    for c in PAISES:
        s = D.anual(f"jst_{c.lower()}_crisisjst")
        marcados = sorted(int(y) for y, v in s.items() if v >= 1)
        ult = -99
        for y in marcados:
            if (y - 1) not in marcados and y - ult >= 5:
                filas.append((c, y))
                ult = y
    return pd.DataFrame(filas, columns=["pais", "año"])


def episodios_globales(años):
    a = sorted(int(x) for x in años)
    ep, k, prev = {}, -1, None
    for x in a:
        if prev is None or x - prev > 1:
            k += 1
        ep[x] = k
        prev = x
    return ep


def acum(m: np.ndarray, H: int, desde: int = 1) -> np.ndarray:
    """m: años × países (rentabilidad simple). acc[t] = Σ log(1+r) de t+desde .. t+desde+H−1; NaN si falta alguno."""
    lr = np.log1p(m)
    T = len(lr)
    out = np.full_like(lr, np.nan)
    for t in range(T):
        lo, hi = t + desde, t + desde + H
        if hi <= T:
            out[t] = lr[lo:hi].sum(axis=0)          # NaN se propaga
    return out


def base_pais(acc_c: np.ndarray, marcas_idx, H: int) -> float:
    cerca = np.zeros(len(acc_c), bool)
    for i in marcas_idx:
        cerca[i:i + H] = True                        # orígenes t con evento en (t − H, t]
    v = acc_c[~cerca & np.isfinite(acc_c)]
    return v.mean() if len(v) else np.nan


def efecto_pais(acc, cols, eventos, H):
    """eventos: lista (pais, año). Devuelve filas (pais, año, dif, abs)."""
    idx = {y: i for i, y in enumerate(AÑOS)}
    filas = []
    for c in sorted(set(p for p, _ in eventos)):
        j = cols.index(c)
        mi = [idx[a] for p, a in eventos if p == c and a in idx]
        b = base_pais(acc[:, j], mi, H)
        for i in mi:
            if np.isfinite(acc[i, j]) and np.isfinite(b):
                filas.append((c, int(AÑOS[i]), acc[i, j] - b, acc[i, j]))
    return filas


def efecto_comun(acc, cols, años_ev, H):
    return efecto_pais(acc, cols, [(c, a) for a in años_ev for c in cols], H)


def ic_cluster(dif, grupo, n_boot, semilla, nivel=0.90):
    rng = np.random.default_rng(semilla)
    g = pd.Series(dif).groupby(np.asarray(grupo))
    grupos = [v.to_numpy() for _, v in g]
    meds = np.empty(n_boot)
    for b in range(n_boot):
        tom = rng.integers(0, len(grupos), len(grupos))
        meds[b] = np.concatenate([grupos[i] for i in tom]).mean()
    return np.quantile(meds, [(1 - nivel) / 2, 1 - (1 - nivel) / 2])


def greedy(rng, validos, n, sep):
    el = []
    for i in rng.permutation(validos):
        if not el or min(abs(i - e) for e in el) >= sep:
            el.append(int(i))
            if len(el) == n:
                return el
    return None


def placebo_pais(acc, cols, ev_por_pais, excl_por_pais, H, sep, n_rep, semilla, omitir_sin_validos=False):
    """ev_por_pais: {c: nº de falsos}; excl_por_pais: {c: años verdaderos para la zona de exclusión (> H)}."""
    rng = np.random.default_rng(semilla)
    noguerra = ~np.isin(AÑOS, list(WAR))
    validos = {}
    for c in ev_por_pais:
        j = cols.index(c)
        verd = np.array(sorted(excl_por_pais[c]))
        lejos = np.array([np.abs(verd - y).min() > H if len(verd) else True for y in AÑOS])
        validos[c] = np.flatnonzero(np.isfinite(acc[:, j]) & noguerra & lejos)
    out = np.full(n_rep, np.nan)
    for k in range(n_rep):
        ev, fallo = [], False
        for c in sorted(ev_por_pais):                 # mismo orden que groupby (alfabético)
            if omitir_sin_validos and len(validos[c]) == 0:
                continue
            el = greedy(rng, validos[c], ev_por_pais[c], sep)
            if el is None:
                fallo = True
                break
            ev += [(c, int(AÑOS[i])) for i in el]
        if not fallo:
            f = efecto_pais(acc, cols, ev, H)
            out[k] = np.mean([x[2] for x in f])
    return out


def placebo_comun(acc, cols, años_ev, años_excl, H, sep, n_rep, semilla):
    rng = np.random.default_rng(semilla)
    verd = np.array(sorted(años_excl))
    ok = np.isfinite(acc).any(axis=1) & ~np.isin(AÑOS, list(WAR))
    lejos = np.array([np.abs(verd - y).min() > H for y in AÑOS])
    v = np.flatnonzero(ok & lejos)
    out = np.full(n_rep, np.nan)
    for k in range(n_rep):
        el = greedy(rng, v, len(años_ev), sep)
        if el is not None:
            f = efecto_comun(acc, cols, [int(AÑOS[i]) for i in el], H)
            out[k] = np.mean([x[2] for x in f])
    return out


def placebo_sincronizado(acc, cols, f, ep, H, n_rep, semilla, todos):
    """A POSTERIORI. Conserva la SINCRONÍA entre países: cada episodio global se traslada en bloque a un año ancla
    falso (mismos desfases internos, mismos países). Un falso no válido (sin dato, guerra, a <= H de una crisis
    verdadera del país, o repetido) se descarta; se exige conservar >= 80 % de los eventos."""
    rng = np.random.default_rng(semilla)
    idx = {y: i for i, y in enumerate(AÑOS)}
    noguerra = set(int(y) for y in AÑOS if y not in WAR)
    eps = {}
    for c, y, *_ in f:
        eps.setdefault(ep[y], []).append((c, y))
    n_obj = len(f)
    out = np.full(n_rep, np.nan)
    for k in range(n_rep):
        ev = set()
        for e, lista in eps.items():
            y0 = min(y for _, y in lista)
            for _ in range(200):
                Y = int(rng.choice(AÑOS))
                cand = [(c, y - y0 + Y) for c, y in lista]
                ok = [(c, z) for c, z in cand if z in idx and z in noguerra and np.isfinite(acc[idx[z], cols.index(c)])
                      and min(abs(z - t) for t in todos[c]) > H and (c, z) not in ev
                      and all(abs(z - w) >= 5 for cc, w in ev if cc == c)]
                if len(ok) == len(cand):
                    ev |= set(ok)
                    break
        if len(ev) >= 0.8 * n_obj:
            ff = efecto_pais(acc, cols, sorted(ev), H)
            out[k] = np.mean([x[2] for x in ff])
    return out


def pval(ef, dist):
    d = dist[np.isfinite(dist)]
    return (1 + (np.abs(d) >= abs(ef)).sum()) / (1 + len(d)), int(len(d))


def holm(p):
    k = sorted(p, key=p.get)
    out, acc = {}, 0
    for i, c in enumerate(k):
        acc = max(acc, min(1, (len(k) - i) * p[c]))
        out[c] = acc
    return out


# ------------------------------------------------------------------ mensual (H3) propio
def rv_eventos(r_d: pd.Series):
    r = r_d.dropna().sort_index()
    g = (r ** 2).groupby(r.index.to_period("M"))
    rv = np.sqrt(252 * g.mean()).where(g.count() >= 15) * 100
    rv = rv.reindex(pd.period_range(rv.index.min(), rv.index.max(), freq="M"))
    x = rv.to_numpy()
    marca = np.zeros(len(x), bool)
    for i in range(len(x)):
        prev = x[:i][np.isfinite(x[:i])]
        if len(prev) >= 60 and np.isfinite(x[i]):
            marca[i] = x[i] >= np.quantile(prev, 0.90)
    ini, ult = [], -10 ** 9
    for i in range(len(x)):
        if marca[i] and (i == 0 or not marca[i - 1]) and i - ult >= 12:
            ini.append(rv.index[i])
            ult = i
    return ini


def mensual_h(r_m: pd.Series, fechas, h, retraso, sep, n_rep, semilla, n_boot=2000):
    lr = np.log1p(r_m.to_numpy())
    T = len(lr)
    a = np.full(T, np.nan)
    for t in range(T):
        lo, hi = t + retraso + 1, t + retraso + h + 1
        if hi <= T:
            a[t] = lr[lo:hi].sum()
    pos = [r_m.index.get_loc(f) for f in fechas if f in r_m.index]
    pos = [p for p in pos if np.isfinite(a[p])]

    def ef_de(pp):
        cerca = np.zeros(T, bool)
        for p in pp:
            cerca[p:p + h] = True
        base = a[~cerca & np.isfinite(a)].mean()
        return a[pp].mean() - base, base
    ef, base = ef_de(pos)
    # IC por bloques de calendario de 60 meses
    rng = np.random.default_rng(semilla)
    ords = np.array([r_m.index[p].ordinal for p in pos])
    g = (ords - ords.min()) // 60
    grupos = [a[np.array(pos)[g == u]] for u in np.unique(g)]
    meds = np.array([np.concatenate([grupos[i] for i in rng.integers(0, len(grupos), len(grupos))]).mean()
                     for _ in range(n_boot)])
    ic = np.quantile(meds - base, [0.05, 0.95])
    # placebo
    rng = np.random.default_rng(semilla)
    validos = np.flatnonzero(np.isfinite(a))
    lejos = np.ones(T, bool)
    for p in [r_m.index.get_loc(f) for f in fechas if f in r_m.index]:
        lejos[max(0, p - h):p + h + 1] = False
    validos = validos[lejos[validos]]
    out = np.full(n_rep, np.nan)
    for k in range(n_rep):
        el = greedy(rng, validos, len(pos), sep)
        if el is not None:
            out[k] = ef_de(el)[0]
    return {"n": len(pos), "efecto_pp": 100 * ef, "ic90_pp": list(100 * ic), "p": pval(ef, out)[0]}


def main():
    t0 = time.time()
    from src.warehouse import db
    con = db.connect(read_only=True)
    D = Datos(con, db)
    B = construir_eventos(D)                         # SOLO para el petróleo (y comparar crisis/vol)
    P = panel_real(D)
    r_aqr = D.s("aqr_mkt_usa_d") / 100
    rf_d = D.s("ffx_us_rf_d") / 100
    cr = crisis_propias(D)
    con.close()
    for k, v in P.items():
        assert v.index.max() <= 2004
    assert r_aqr.index.max() <= pd.Timestamp("2004-12-31")
    cols = list(PAISES)
    res = {"nota": "Validador, código propio; sensibilidades A POSTERIORI"}

    # ---------- eventos
    oficial = B["crisis"]
    res["crisis_igual_oficial"] = sorted(map(tuple, cr.values.tolist())) == sorted(map(tuple, oficial.values.tolist()))
    ep = episodios_globales(cr["año"].values)
    cr_sg = cr[~cr["año"].isin(list(WAR))]
    ev_cr = [(c, int(a)) for c, a in cr_sg.values]

    # ---------- H1 / H2
    prin = {}
    for k, (a, H) in {"H1": ("vivienda", 3), "H2": ("bolsa", 1)}.items():
        acc = acum(P[a].to_numpy(float), H)
        f = efecto_pais(acc, cols, ev_cr, H)
        dif = np.array([x[2] for x in f])
        ic = ic_cluster(dif, [ep[x[1]] for x in f], 2000, SEM)
        usados = {}
        for c, y, *_ in f:
            usados.setdefault(c, []).append(y)
        pl = placebo_pais(acc, cols, {c: len(v) for c, v in usados.items()}, usados, H, 5, 2000, SEM)
        p, nv = pval(dif.mean(), pl)
        prin[k] = {"n": len(f), "efecto_pp": 100 * dif.mean(), "ic90_pp": list(100 * ic), "p": p, "validos": nv,
                   "media_abs_pct": 100 * np.expm1(np.mean([x[3] for x in f]))}
        print(k, prin[k], flush=True)

    # ---------- H3
    r_us = r_aqr + rf_d.reindex(r_aqr.index).fillna(0)
    ev_vol = rv_eventos(r_us)
    res["vol_igual_oficial"] = [str(x) for x in ev_vol] == [str(x) for x in B["ev"]["vol"]["fecha"]]
    bolsa_m = (1 + r_us).groupby(r_us.index.to_period("M")).prod() - 1
    bolsa_m = bolsa_m.reindex(pd.period_range(bolsa_m.index.min(), bolsa_m.index.max(), freq="M"))
    prin["H3"] = mensual_h(bolsa_m, ev_vol, 12, 0, 12, 2000, SEM)
    print("H3", prin["H3"], flush=True)

    # ---------- H4
    años_oil = sorted({p.year for p in B["ev"]["petroleo"]["fecha"]} - WAR)
    acc = acum(P["bolsa"].to_numpy(float), 1)
    f = efecto_comun(acc, cols, años_oil, 1)
    dif = np.array([x[2] for x in f])
    ic = ic_cluster(dif, [x[1] for x in f], 2000, SEM)
    usados = sorted({x[1] for x in f})
    pl = placebo_comun(acc, cols, usados, usados, 1, 2, 2000, SEM)
    prin["H4"] = {"n": len(f), "años": usados, "efecto_pp": 100 * dif.mean(), "ic90_pp": list(100 * ic),
                  "p": pval(dif.mean(), pl)[0]}
    print("H4", prin["H4"], flush=True)
    ph = holm({k: v["p"] for k, v in prin.items()})
    for k in prin:
        prin[k]["p_holm"] = ph[k]
    res["principales"] = prin

    # ---------- sensibilidad A POSTERIORI del placebo de H1
    H = 3
    acc = acum(P["vivienda"].to_numpy(float), H)
    f = efecto_pais(acc, cols, ev_cr, H)
    ef = np.mean([x[2] for x in f])
    usados = {}
    for c, y, *_ in f:
        usados.setdefault(c, []).append(y)
    todos = {}
    for c, y in ev_cr:
        todos.setdefault(c, []).append(y)
    otros = {k: v["p"] for k, v in prin.items() if k != "H1"}

    def fila(pl):
        p, nv = pval(ef, pl)
        return {"p": round(p, 4), "validos": nv, "p_holm_H1": round(holm({**otros, "H1": p})["H1"], 4),
                "frac_placebo_mas_negativo": round(float(np.mean(pl[np.isfinite(pl)] <= ef)), 4)}
    sens = {}
    pl0 = placebo_pais(acc, cols, {c: len(v) for c, v in usados.items()}, usados, H, 5, 2000, SEM)
    q = np.quantile(pl0, [0.005, 0.025, 0.5, 0.975, 0.995])
    sens["distribucion_placebo_oficial_pp"] = {"media": round(100 * pl0.mean(), 2), "sd": round(100 * pl0.std(), 2),
                                               "cuantiles_0.5_2.5_50_97.5_99.5": [round(100 * x, 2) for x in q]}
    pls = placebo_sincronizado(acc, cols, f, ep, H, 2000, SEM, todos)
    sens["sincronizado_por_episodio"] = {**fila(pls), "media_pp": round(100 * np.nanmean(pls), 2),
                                         "sd_pp": round(100 * np.nanstd(pls), 2)}
    nf = {c: len(v) for c, v in usados.items()}
    sens["oficial_corregido_semilla"] = fila(placebo_pais(acc, cols, nf, usados, H, 5, 2000, SEM))
    semillas = []
    for s in range(1, 11):
        semillas.append(fila(placebo_pais(acc, cols, nf, usados, H, 5, 2000, SEM + s))["p"])
    sens["semillas_10x2000"] = {"p": semillas, "media": float(np.mean(semillas)), "min": min(semillas),
                                "max": max(semillas)}
    big = placebo_pais(acc, cols, nf, usados, H, 5, 20000, 7)
    sens["oficial_20000_semilla7"] = fila(big)
    # (b) lectura literal: un falso por CADA crisis verdadera (también sin dato), omitiendo solo países sin años válidos
    sens["literal_todas_crisis_omitir_CAN"] = fila(placebo_pais(acc, cols, {c: len(v) for c, v in todos.items()},
                                                                todos, H, 5, 2000, SEM, omitir_sin_validos=True))
    # (c) falsos solo para eventos con dato, pero exclusión (> H) respecto de TODAS las crisis verdaderas del país
    sens["exclusion_todas_crisis"] = fila(placebo_pais(acc, cols, nf, {c: todos[c] for c in nf}, H, 5, 2000, SEM))
    # (d) separación entre falsos 3 y 1 (sin separación)
    sens["separacion_3"] = fila(placebo_pais(acc, cols, nf, usados, H, 3, 2000, SEM))
    sens["separacion_1"] = fila(placebo_pais(acc, cols, nf, usados, H, 1, 2000, SEM))
    # (e) zona de exclusión 0 (falsos pueden caer cerca de crisis verdaderas: placebo "contaminado")
    sens["sin_exclusion"] = fila(placebo_pais(acc, cols, nf, {c: [] for c in nf}, H, 5, 2000, SEM))
    # (f) unilateral (efecto negativo): fracción de placebos <= efecto
    # (g) contrastes no de placebo: t por conglomerados (episodio global) y bootstrap de conglomerados
    d = pd.DataFrame(f, columns=["pais", "año", "dif", "abs"])
    d["ep"] = d["año"].map(ep)
    gm = d.groupby("ep")["dif"].agg(["sum", "count"])
    G = len(gm)
    u = (gm["sum"] - gm["count"] * d["dif"].mean()).to_numpy()
    se = np.sqrt(G / (G - 1) * (u ** 2).sum()) / len(d)
    from scipy import stats
    tt = d["dif"].mean() / se
    sens["t_conglomerados_episodio"] = {"G": G, "t": round(float(tt), 3),
                                        "p_bilateral_tG-1": round(float(2 * stats.t.sf(abs(tt), G - 1)), 4)}
    # (h) sin la crisis más influyente (jackknife por episodio)
    jk = {}
    for e in sorted(d["ep"].unique()):
        jk[int(e)] = round(100 * d.loc[d["ep"] != e, "dif"].mean(), 2)
    sens["jackknife_episodio_efecto_pp"] = {"min": min(jk.values()), "max": max(jk.values())}
    sens["por_periodo_pp"] = {"<1914": round(100 * d.loc[d.año < 1914, "dif"].mean(), 2),
                              "1919-1938": round(100 * d.loc[(d.año > 1918) & (d.año < 1939), "dif"].mean(), 2),
                              "1946-2004": round(100 * d.loc[d.año > 1945, "dif"].mean(), 2),
                              "n": [int((d.año < 1914).sum()), int(((d.año > 1918) & (d.año < 1939)).sum()),
                                    int((d.año > 1945).sum())]}
    res["sens_placebo_H1"] = sens
    res["segundos"] = round(time.time() - t0)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "repro.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    print(json.dumps(res["sens_placebo_H1"], ensure_ascii=False, default=float), res["segundos"], "s")


if __name__ == "__main__":
    main()
