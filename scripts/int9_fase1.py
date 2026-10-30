"""INT-9 fase 1: estructura común de los INDICADORES (factores, clusters, estabilidad) y potencia para la fase 2.
Descriptivo, sin contraste. Solo datos ≤ 2004 (src/intl/data.load_dev); nada ≥ 2005.

Qué usa:
  (i)  indicadores JST anuales del núcleo (14 países, 1871-2004): crecimiento del PIB real, inflación, Δ crédito/PIB,
       curva (largo − corto), tipo real corto, Δ tipo largo, bolsa real y vivienda real del AÑO t (pasado en t + 1);
       guerras e hiperinflación fuera, winsorización 1/99;
  (ii) indicadores OCDE mensuales "as of" (src/intl/panel.mensual) 1961-2004: IP interanual, IPC interanual, curva,
       bolsa a 12 meses (bloque de contraste);
  (iii) para la POTENCIA, solo propiedades de Y por separado: tasa de entradas en recesión y su agrupamiento por año
       (sobredispersión), y dt de la bolsa real entre años y dentro del año; más la DISPONIBILIDAD de filas.
Qué NO hace nunca: juntar un factor con un objetivo (recesión, rentabilidad futura). Los objetivos de la potencia son
SINTÉTICOS (src/intl/int9.pot_logit / pot_mco).

Uso: .venv/bin/python -m scripts.int9_fase1            (árbol limpio; escribe research/int/int9_fase1.json)
     .venv/bin/python -m scripts.int9_fase1 --prueba   (sin puerta, réplicas reducidas; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import int4 as M
from src.intl import int6 as S
from src.intl import int9 as K
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
AÑOS = range(1870, 2005)
IND = ["pib_real_g", "inflacion", "d_credito_pib", "curva", "tipo_real", "d_ltrate", "eq_tr_real", "housing_tr_real"]
IND_MACRO = IND[:6]
MITADES = {"1871_1949": (1871, 1949), "1950_2004": (1950, 2004)}
R = 3                    # factores que se describen (fijado antes de mirar)
K_PAISES, K_IND = 4, 3   # cortes de los dendrogramas (fijados antes de mirar)
SEED = 20261030
MENS = ["ip_yoy", "ipc_yoy", "curva", "bolsa_12m"]


# ---------------------------------------------------------------- carga (solo X; Y solo para la potencia)
def cargar(con) -> dict:
    a = P.anual(con)
    if a.index.get_level_values(1).max() > 2004:
        raise D.FactorCutoffError("panel anual con años > 2004")
    x = a.copy()
    x["curva"] = x["ltrate"] - x["stir"]
    x["tipo_real"] = x["stir"] / 100 - x["inflacion"]
    x["d_ltrate"] = x.groupby(level=0)["ltrate"].diff()
    ind = {k: x[k].unstack(0).reindex(index=AÑOS, columns=NUCLEO) for k in IND}
    infl_simple = np.expm1(ind["inflacion"])
    fuera = S.hiper_fuera(pd.Series({(c, int(t)): v for c in NUCLEO for t, v in infl_simple[c].dropna().items()},
                                    dtype=float))
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in NUCLEO}
    pan = M.paneles(a, pd.DataFrame(index=a.index, columns=["hpnom", "money", "wage"], dtype=float), NUCLEO, NUCLEO,
                    None)
    bolsa = a["eq_tr_real"].unstack(0).reindex(index=AÑOS, columns=NUCLEO)      # SOLO para la potencia (Y sola)
    return {"ind": ind, "fuera": fuera, "rec": rec, "años_pais": años_pais, "S4": pan["S4"], "bolsa": bolsa}


def cargar_mensual(con) -> pd.DataFrame:
    m = P.mensual(con, desde="1961-01-31")
    m = m.loc[m.index.get_level_values(0).isin(NUCLEO), MENS]
    if m.index.get_level_values(1).max() > D.DEV_END:
        raise D.FactorCutoffError("mensual > 2004")
    return m


# ---------------------------------------------------------------- piezas
def desc_apilado(X: pd.DataFrame, r: int) -> dict:
    e = K.em_pca(X.to_numpy(), r)
    ev = K.autovalores(K.corr_pares(X.to_numpy()))
    L = pd.DataFrame(e["L"], index=X.columns, columns=[f"F{i + 1}" for i in range(r)])
    pais = L.index.str.split("|").str[0]
    ind = L.index.str.split("|").str[1]
    Z = e["Z"]
    o = e["obs"]
    r2 = {f"F1..F{k}": float(1 - np.mean((Z[o] - (e["F"][:, :k] @ e["L"][:, :k].T + e["W"].mean(0))[o]) ** 2)
                             / np.mean(Z[o] ** 2)) for k in range(1, r + 1)}
    return {"e": e, "L": L, "cuota_autovalores": (ev[:6] / ev.sum()).tolist(), "r2_obs": r2,
            "carga_media_por_indicador": L.groupby(ind).mean().round(3).to_dict(),
            "carga_media_por_pais": L.groupby(pais).mean().round(3).to_dict(),
            "F": pd.DataFrame(e["F"], index=X.index, columns=L.columns)}


def r2_por_columna(e: dict, k: int) -> np.ndarray:
    """R² de cada columna con los k primeros factores (en sus celdas observadas)."""
    Z, o = e["Z"], e["obs"]
    fit = e["F"][:, :k] @ e["L"][:, :k].T + e["W"].mean(0)
    num = np.nansum(np.where(o, (Z - fit) ** 2, np.nan), 0)
    den = np.nansum(np.where(o, Z ** 2, np.nan), 0)
    return 1 - num / den


def corr_paises(c: dict, paises: list[str], resid: pd.DataFrame | None = None) -> np.ndarray:
    """Correlación entre países sobre sus bloques (años × indicadores apilados), estandarizados dentro de país."""
    vecs = {}
    for p in paises:
        if resid is not None:
            cols = [col for col in resid.columns if col.startswith(p + "|")]
            vecs[p] = resid[cols].to_numpy().ravel()
        else:
            d = pd.DataFrame({k: c[k][p] for k in c})
            vecs[p] = ((d - d.mean()) / d.std(ddof=1)).to_numpy().ravel()
    return K.corr_pares(np.column_stack([vecs[p] for p in paises]), min_pares=30)


def cuota_regional(resid: pd.DataFrame, grupos: dict[int, list[str]], rng: np.random.Generator, B: int) -> dict:
    """Cuota de la varianza residual (tras los factores globales) que explica el PC1 de cada cluster, frente a la de
    grupos aleatorios del mismo tamaño (referencia de "regional por azar")."""
    paises = sorted({c.split("|")[0] for c in resid.columns})

    def cuota(g):
        cols = [c for c in resid.columns if c.split("|")[0] in g]
        if len(g) < 2:
            return np.nan
        ev = K.autovalores(K.corr_pares(resid[cols].to_numpy(), min_pares=20))
        return float(ev[0] / ev.sum())

    out = {}
    for k, g in grupos.items():
        ob = cuota(g)
        az = np.array([cuota(list(rng.choice(paises, len(g), replace=False))) for _ in range(B)])
        out[str(k)] = {"paises": g, "cuota_pc1": ob, "azar_media": float(np.nanmean(az)),
                       "azar_p95": float(np.nanquantile(az, 0.95)) if len(g) > 1 else None,
                       "p_azar": float((1 + (az >= ob).sum()) / (1 + B)) if len(g) > 1 else None}
    return out


def grupos_de(et: np.ndarray, nombres: list[str]) -> dict[int, list[str]]:
    return {int(k): [n for n, e in zip(nombres, et) if e == k] for k in np.unique(et)}


# ---------------------------------------------------------------- bloque anual
def anual(d: dict, ind: list[str], rng, B_par: int, B_boot: int, B_reg: int, sin_guerras: bool = True) -> dict:
    c = K.cubo({k: d["ind"][k] for k in ind}, d["fuera"], sin_guerras)
    X = K.apilar(c, NUCLEO)
    out = {"filas_años": int(len(X)), "columnas": int(X.shape[1]), "celdas_obs": float(X.notna().mean().mean())}
    # número de factores
    out["bai_ng"] = K.bai_ng(X.to_numpy(), 8)
    pa = K.paralelo(X.to_numpy(), B_par, rng)
    out["paralelo"] = {"retenidos": pa["retenidos"], "autovalores_10": np.round(pa["autovalores"][:10], 3).tolist(),
                       "umbral95_10": np.round(pa["umbral"][:10], 3).tolist()}
    # factores globales (apilado años × país|indicador)
    g = desc_apilado(X, R)
    out["global"] = {k: v for k, v in g.items() if k not in ("e", "L", "F")}
    r2c = pd.Series(r2_por_columna(g["e"], 1), index=X.columns)
    out["global"]["r2_F1_por_indicador"] = r2c.groupby(r2c.index.str.split("|").str[1]).mean().round(3).to_dict()
    out["global"]["r2_F1_por_pais"] = r2c.groupby(r2c.index.str.split("|").str[0]).mean().round(3).to_dict()
    # cuota del PC1 de cada indicador entre países ("lo global de cada variable")
    out["pc1_por_indicador"] = {}
    for k in ind:
        ev = K.autovalores(K.corr_pares(c[k][NUCLEO].to_numpy(), min_pares=20))
        fila = {"todo": float(ev[0] / ev.sum())}
        for nom, (a0, a1) in MITADES.items():
            sub = c[k][NUCLEO].loc[a0:a1].to_numpy()
            ev = K.autovalores(K.corr_pares(sub, min_pares=15))
            fila[nom] = float(ev[0] / ev.sum())
        out["pc1_por_indicador"][k] = fila
    # PCA de los indicadores dentro de país (filas país-año): la estructura entre indicadores
    Fi = K.apilar_filas(c, NUCLEO)
    Rind = K.corr_pares(Fi.to_numpy(), min_pares=50)
    pc = K.pca_corr(Rind, R)
    out["indicadores_dentro_pais"] = {
        "corr": pd.DataFrame(Rind, index=ind, columns=ind).round(3).to_dict(),
        "cargas": pd.DataFrame(pc["L"], index=ind, columns=[f"P{i + 1}" for i in range(R)]).round(3).to_dict(),
        "cuota": np.round(pc["cuota"][:R + 2], 3).tolist()}
    jc = K.jerarquico(Rind, K_IND, absoluta=True)
    out["clusters_indicadores"] = grupos_de(jc["etiquetas"], ind)
    # PCA por país
    porp = {}
    for p in NUCLEO:
        Zp = pd.DataFrame({k: c[k][p] for k in ind})
        pp = K.pca_corr(K.corr_pares(Zp.to_numpy(), min_pares=20), R)
        _, cg = K.alinear(pc["L"], pp["L"])
        porp[p] = {"cuota_pc1": float(pp["cuota"][0]), "congruencia_con_comun": np.round(cg, 3).tolist()}
    out["por_pais"] = porp
    # clusters de países: sobre los bloques y sobre los residuos tras R factores globales (regional)
    Rp = corr_paises(c, NUCLEO)
    jp = K.jerarquico(Rp, K_PAISES)
    out["clusters_paises"] = grupos_de(jp["etiquetas"], NUCLEO)
    out["corr_paises_media"] = float(np.nanmean(Rp[np.triu_indices(len(NUCLEO), 1)]))
    e = g["e"]
    resid = pd.DataFrame(np.where(e["obs"], e["Z"] - e["ajuste"], np.nan), index=X.index, columns=X.columns)
    Rr = corr_paises(c, NUCLEO, resid)
    jr = K.jerarquico(Rr, K_PAISES)
    out["clusters_paises_residuo"] = grupos_de(jr["etiquetas"], NUCLEO)
    out["regional"] = cuota_regional(resid, out["clusters_paises_residuo"], rng, B_reg)
    # estabilidad: dos mitades
    mit = {}
    for nom, (a0, a1) in MITADES.items():
        Xm = X.loc[a0:a1]
        Xm = Xm.loc[:, Xm.notna().sum() >= 15]
        gm = desc_apilado(Xm, R)
        comunes = [col for col in Xm.columns if col in g["L"].index]
        _, cg = K.alinear(g["L"].loc[comunes].to_numpy(), gm["L"].loc[comunes].to_numpy())
        cm = {k: v.loc[a0:a1] for k, v in c.items()}
        pm = K.pca_corr(K.corr_pares(K.apilar_filas(cm, NUCLEO).to_numpy(), min_pares=30), R)
        _, cgi = K.alinear(pc["L"], pm["L"])
        mit[nom] = {"años": int(len(Xm)), "cuota_autovalores": np.round(gm["cuota_autovalores"][:4], 3).tolist(),
                    "congruencia_global_con_todo": np.round(cg, 3).tolist(),
                    "carga_media_por_indicador": gm["carga_media_por_indicador"],
                    "bai_ng": K.bai_ng(Xm.to_numpy(), 6),
                    "cargas_indicadores": pd.DataFrame(pm["L"], index=ind).round(3).to_dict(),
                    "congruencia_indicadores_con_todo": np.round(cgi, 3).tolist(),
                    "clusters_paises": grupos_de(K.jerarquico(corr_paises(cm, NUCLEO), K_PAISES)["etiquetas"],
                                                 NUCLEO),
                    "clusters_indicadores": grupos_de(K.jerarquico(
                        K.corr_pares(K.apilar_filas(cm, NUCLEO).to_numpy(), min_pares=30), K_IND, True)["etiquetas"],
                        ind)}
    e1, e2 = (K.jerarquico(corr_paises({k: v.loc[a0:a1] for k, v in c.items()}, NUCLEO), K_PAISES)["etiquetas"]
              for a0, a1 in MITADES.values())
    i1, i2 = (K.jerarquico(K.corr_pares(K.apilar_filas({k: v.loc[a0:a1] for k, v in c.items()}, NUCLEO).to_numpy(),
                                        min_pares=30), K_IND, True)["etiquetas"] for a0, a1 in MITADES.values())
    mit["ari_paises_entre_mitades"] = K.ari(e1, e2)
    mit["ari_indicadores_entre_mitades"] = K.ari(i1, i2)
    mit["ari_paises_mitad_vs_todo"] = [K.ari(e1, jp["etiquetas"]), K.ari(e2, jp["etiquetas"])]
    out["mitades"] = mit
    # estabilidad: bootstrap de bloques móviles de 10 años
    T = len(X)
    cgs, cuotas, nbn, et_p = [], [], [], []
    for _ in range(B_boot):
        ix = K.bloques(T, 10, rng)
        Xb = X.iloc[ix].reset_index(drop=True)
        Xb = Xb.loc[:, Xb.notna().sum() >= 10]
        eb = K.em_pca(Xb.to_numpy(), R)
        Lb = pd.DataFrame(eb["L"], index=Xb.columns)
        com = [col for col in Xb.columns if col in g["L"].index]
        _, cg = K.alinear(g["L"].loc[com].to_numpy(), Lb.loc[com].to_numpy())
        cgs.append(cg)
        ev = K.autovalores(K.corr_pares(Xb.to_numpy()))
        cuotas.append(ev[:R] / ev.sum())
        nbn.append(K.bai_ng(Xb.to_numpy(), 6)["IC_p2"])
        cb = {k: v.iloc[ix].reset_index(drop=True) for k, v in c.items()}
        et_p.append(K.jerarquico(corr_paises(cb, NUCLEO), K_PAISES)["etiquetas"])
    cgs, cuotas = np.array(cgs), np.array(cuotas)
    co = K.coasignacion(np.array(et_p))
    out["bootstrap"] = {
        "B": B_boot, "bloque_años": 10,
        "congruencia_mediana": np.round(np.median(cgs, 0), 3).tolist(),
        "congruencia_p10": np.round(np.quantile(cgs, 0.10, 0), 3).tolist(),
        "frac_congruencia_ge_0.85": np.round((cgs >= 0.85).mean(0), 3).tolist(),
        "cuota_mediana": np.round(np.median(cuotas, 0), 3).tolist(),
        "cuota_ic90": [np.round(np.quantile(cuotas, 0.05, 0), 3).tolist(),
                       np.round(np.quantile(cuotas, 0.95, 0), 3).tolist()],
        "bai_ng_ICp2_frecuencias": {str(k): int(v) for k, v in zip(*np.unique(nbn, return_counts=True))},
        "coasignacion_paises": pd.DataFrame(co, index=NUCLEO, columns=NUCLEO).round(2).to_dict(),
        "coasignacion_media_dentro_cluster_principal": float(np.mean([co[i, j] for i in range(len(NUCLEO))
                                                                     for j in range(i + 1, len(NUCLEO))
                                                                     if jp["etiquetas"][i] == jp["etiquetas"][j]])),
        "coasignacion_media_entre_clusters": float(np.mean([co[i, j] for i in range(len(NUCLEO))
                                                            for j in range(i + 1, len(NUCLEO))
                                                            if jp["etiquetas"][i] != jp["etiquetas"][j]]))}
    out["_F"] = g["F"]
    out["_Lind"] = pc["L"]
    out["_c"] = c
    return out


# ---------------------------------------------------------------- bloque mensual (OCDE, contraste)
def mensual(m: pd.DataFrame, F_anual: pd.DataFrame) -> dict:
    out = {}
    W = {k: m[k].unstack(0).reindex(columns=NUCLEO) for k in MENS}
    for k in MENS:
        fila = {}
        for nom, (a0, a1) in {"1961_2004": ("1961", "2004"), "1961_1982": ("1961", "1982"),
                              "1983_2004": ("1983", "2004")}.items():
            ev = K.autovalores(K.corr_pares(W[k].loc[a0:a1].to_numpy(), min_pares=60))
            fila[nom] = float(ev[0] / ev.sum())
        out[f"pc1_{k}"] = fila
    X = pd.DataFrame({f"{p}|{k}": W[k][p] for k in MENS for p in NUCLEO})
    X = X.loc[:, X.notna().sum() >= 60]
    X = X.loc[X.notna().mean(axis=1) >= 0.3]
    out["meses"] = int(len(X))
    out["columnas"] = int(X.shape[1])
    out["bai_ng"] = K.bai_ng(X.to_numpy(), 6)
    g = desc_apilado(X, R)
    out["cuota_autovalores"] = np.round(g["cuota_autovalores"][:4], 3).tolist()
    out["carga_media_por_indicador"] = g["carga_media_por_indicador"]
    Fm = g["F"].groupby(g["F"].index.year).mean()
    com = Fm.index.intersection(F_anual.index)
    out["corr_media_anual_mensual_vs_F_anual"] = {
        f"{a}~{b}": float(np.corrcoef(Fm.loc[com, a], F_anual.loc[com, b])[0, 1])
        for a in Fm.columns for b in F_anual.columns}
    out["años_comunes"] = int(len(com))
    return out


# ---------------------------------------------------------------- potencia (objetivos sintéticos)
def potencia(d: dict, F: pd.DataFrame, Lind: np.ndarray, c: dict, rng, nsim: int) -> dict:
    alfa = 0.05 / 3       # Holm con 3 contrastes: el primero se juzga a α/3 (peor caso)
    out = {"alfa": alfa, "nsim": nsim}
    # filas de entrada en recesión h = 1 (núcleo, sin guerras, sin hiperinflación), como INT-4 / INT-6 X1
    f = M.obj_entrada(d["rec"], d["años_pais"], NUCLEO, 1, 1871, True)
    f = f[[(p, t) not in d["fuera"] for p, t in zip(f.pais, f.t)]].reset_index(drop=True)
    Fg = F.reindex(range(1870, 2005))
    # factor propio (dentro de país, P1 de los indicadores): puntuación por fila
    Fi = K.apilar_filas(c, NUCLEO)
    prop = pd.Series(K.puntuar(Fi.to_numpy(), Lind[:, :1], 5)[:, 0], index=Fi.index)
    disp = {
        "F1_global": Fg["F1"].reindex(f.t).to_numpy(),
        "F2_global": Fg["F2"].reindex(f.t).to_numpy(),
        "P1_propio": prop.reindex(list(zip(f.pais, f.t))).to_numpy(),
    }
    s4 = S.mirar(f.assign(t=f.t), [d["S4"]])[:, 0]
    # propiedades de Y SOLA: tasa y agrupamiento por año (sobre todas las filas, sin mirar factores)
    y = f.y.to_numpy(float)
    tasa, sobre = float(y.mean()), K.sobredispersion(y, f.t.to_numpy())
    su = K.calibrar_sigma_u(tasa, f.t.to_numpy(), sobre, rng)
    out["recesion"] = {"filas": int(len(f)), "eventos": int(y.sum()), "tasa": tasa, "sobredispersion_por_año": sobre,
                       "sigma_u_calibrada": su}
    betas = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
    for nom, x in disp.items():
        ok = np.isfinite(x)
        r = K.pot_logit(x[ok], f.pais.to_numpy()[ok], f.t.to_numpy()[ok], tasa, su, betas, nsim, alfa, rng)
        r["filas"] = int(ok.sum())
        out["recesion"][nom] = r
        print("potencia recesión", nom, r["mde80"], flush=True)
    # incremental sobre S4 (X1, establecido): y generada con S4 (efecto plantado ≈ ΔAUC +0,12) y con F1
    ok = np.isfinite(disp["F1_global"]) & np.isfinite(s4)
    s4z = (s4[ok] - s4[ok].mean()) / s4[ok].std(ddof=1)
    gam = 0.75                                       # log-odds por dt de S4 (≈ AUC 0,62 sola; supuesto declarado)
    r = K.pot_logit(disp["F1_global"][ok], f.pais.to_numpy()[ok], f.t.to_numpy()[ok], tasa, su, betas, nsim, alfa,
                    rng, base=s4z.reshape(-1, 1), gamma=np.array([gam]))
    r.update({"filas": int(ok.sum()), "gamma_S4_supuesta": gam,
              "corr_F1_S4": float(np.corrcoef(disp["F1_global"][ok], s4[ok])[0, 1])})
    out["recesion"]["F1_global_sobre_S4"] = r
    print("potencia recesión F1|S4", r["mde80"], flush=True)
    out["recesion"]["corr_entre_candidatos"] = {
        f"{a}~{b}": float(pd.Series(disp[a]).corr(pd.Series(disp[b]))) for a in disp for b in disp if a < b}
    out["recesion"]["corr_con_S4"] = {a: float(pd.Series(disp[a]).corr(pd.Series(s4))) for a in disp}
    # bolsa real t + 1: dt entre años (común) y dentro del año (propia), de Y sola
    b = d["bolsa"].copy()
    b.loc[b.index.isin(list(K.GUERRAS))] = np.nan
    for p, t in d["fuera"]:
        if p in b.columns and t in b.index:
            b.loc[t, p] = np.nan
    yl = b.stack().rename("y").reset_index()
    yl.columns = ["año", "pais", "y"]
    yl = yl[(yl.año >= 1872)]
    lo, hi = np.quantile(yl.y, [0.01, 0.99])
    yl["y"] = yl.y.clip(lo, hi)
    media_año = yl.groupby("año").y.transform("mean")
    sd_c, sd_p = float(yl.groupby("año").y.mean().std(ddof=1)), float((yl.y - media_año).std(ddof=1))
    out["bolsa"] = {"filas": int(len(yl)), "dt_comun_entre_años": sd_c, "dt_propia_dentro_del_año": sd_p}
    yl["t"] = yl.año - 1
    bet = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08]
    for nom in ("F1_global", "F2_global", "P1_propio"):
        x = (Fg[nom[:2]].reindex(yl.t).to_numpy() if nom != "P1_propio"
             else prop.reindex(list(zip(yl.pais, yl.t))).to_numpy())
        ok = np.isfinite(x)
        r = K.pot_mco(x[ok], yl.pais.to_numpy()[ok], yl.t.to_numpy()[ok], sd_c, sd_p, bet, nsim, alfa, 4, rng)
        r["filas"] = int(ok.sum())
        out["bolsa"][nom] = r
        print("potencia bolsa", nom, r["mde80"], flush=True)
    return out


def limpiar(o):
    if isinstance(o, dict):
        return {str(k): limpiar(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [limpiar(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 4)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return limpiar(o.tolist())
    return o


def main() -> None:
    prueba = "--prueba" in sys.argv
    proc = procedencia(exigir_limpio=not prueba)
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    rng = np.random.default_rng(SEED)
    B_par, B_boot, B_reg, nsim = (20, 20, 20, 40) if prueba else (200, 300, 200, 400)
    con = D.connect()
    d = cargar(con)
    m = cargar_mensual(con)
    res = {"procedencia": proc, "semilla": SEED, "indicadores": IND, "paises": NUCLEO, "R": R,
           "k_paises": K_PAISES, "k_indicadores": K_IND}
    a = anual(d, IND, rng, B_par, B_boot, B_reg)
    print("anual listo", flush=True)
    res["anual"] = a
    res["anual_solo_macro"] = anual(d, IND_MACRO, rng, B_par, max(B_boot // 3, 10), B_reg)
    res["anual_con_guerras"] = {k: v for k, v in anual(d, IND, rng, B_par, 10, 10, sin_guerras=False).items()
                                if k in ("bai_ng", "paralelo", "global", "indicadores_dentro_pais")}
    res["mensual_ocde"] = mensual(m, a["_F"])
    res["factores_anuales"] = {str(t): [round(float(v), 3) for v in r] for t, r in a["_F"].iterrows()}
    res["potencia"] = potencia(d, a["_F"], a["_Lind"], a["_c"], rng, nsim)
    out = limpiar(res)
    if prueba:
        print(json.dumps(out["anual"]["global"], indent=1)[:3000])
        return
    (REPO / "research" / "int" / "int9_fase1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("escrito research/int/int9_fase1.json")


if __name__ == "__main__":
    main()
