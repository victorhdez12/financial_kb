"""INT-6 (borrador): potencia de las preguntas de oro, dinero, crédito y relaciones entre países, ANTES de prerregistrar y
sin cruzar ningún indicador con ningún resultado. Solo datos ≤ 2004 (src/intl/data.load_dev), núcleo de 14 países.

Qué usa (y nada más):
  (i)   RECUENTOS de los objetivos y de los estados: entradas en recesión (fechado anual de INT-1), inicios de crisis
        bancarias (`crisisjst`, solo como objetivo), años de recesión y de recesión financiera por país, años distintos,
        ICC del objetivo por año;
  (ii)  estadísticos INCONDICIONALES de cada resultado por separado (dt, correlación media entre países, AR(1)) y de cada
        indicador por separado (dt, correlación media entre países, AR(1));
  (iii) DISPONIBILIDAD de los indicadores (si hay dato en el país-año, nunca su valor) para contar filas y eventos.
Qué NO hace nunca: una regresión, correlación, AUC o media condicionada que junte un indicador con un resultado, ni un
resultado con un estado (los estados solo se cuentan). Las AUC de los listones se SUPONEN (rejilla), salvo la del logit
de INT-4, que ya se publicó (T1: 0,732 estratificada, research/int/int4ml_potencia.json).

Fórmulas:
  - pendiente de un indicador continuo en un panel (MDE en pp de rentabilidad por 1 dt del indicador):
        MDE = z · dt_y / √N_ef,  N_ef = N / [1 + (m* − 1)·ρx·ρy] · (1 − φx·φy) / (1 + φx·φy)
    (Moulton con la corrección de Kish del tamaño de grupo; ρ = correlación media entre países; φ = AR(1)). Cota
    prudente: ρx·ρy → ρy (como si el indicador fuera común a todos los países).
  - estado binario en un panel (pp, estado frente al resto): la de INT-2 / INT-3b (Kish + AR(1)).
  - serie temporal: la de INT-3b (Newey-West aproximado con el VIF de AR(1)).
  - correlación entre dos series temporales: MDE_r ≈ z / √(N·(1 − φx·φy)/(1 + φx·φy)).
  - ΔAUC: la de INT-4 (Hanley-McNeil, AUC correlacionadas r); positivos efectivos = años distintos con evento
    (prudente) y negativos = filas negativas / efecto de diseño.
z: un contraste (2,80) y Holm sobre m = 6 (3,48) — la familia de INT-6 tendrá como mucho 6 contrastes confirmatorios.

Uso: .venv/bin/python -m scripts.int6_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int6_potencia --prueba   (sin puerta; no escribe nada)
"""
from __future__ import annotations

import itertools
import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts.int4_potencia import (GUERRAS, NUCLEO, REPO, cobertura_anual, icc_anova, mde_auc,
                                   objetivo_recesion_anual)
from src.intl import activos3b as A3
from src.intl import data as D
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

HIPER = 0.50                      # país-años con inflación > 50 % fuera (regla de INT-3b)
M_FAMILIA = 6
Z = {"1": norm.ppf(0.975) + norm.ppf(0.80), f"holm{M_FAMILIA}": norm.ppf(1 - 0.05 / (2 * M_FAMILIA)) + norm.ppf(0.80)}
AUC_LOGIT_T1 = 0.732              # AUC estratificada del logit de INT-4 en T1 (ya publicada)
R_ANIDADO = (0.8, 0.9, 0.95)      # correlación entre las AUC de dos modelos anidados (logit y logit + 1 indicador)


def _r(x, k=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


# ---------------------------------------------------------------- estadísticos de UNA variable (indicador o resultado)
def st_panel(s: pd.Series) -> dict:
    """s indexada por (pais, año). dt, correlación media entre países (pares con ≥ 20 años comunes), AR(1) medio."""
    s = s.dropna()
    ancho = s.unstack(0)
    pares = [ancho[[i, j]].dropna().corr().iloc[0, 1] for i, j in itertools.combinations(ancho.columns, 2)
             if ancho[[i, j]].dropna().shape[0] >= 20]
    ar1 = [ancho[c].dropna().autocorr(1) for c in ancho.columns if ancho[c].dropna().size > 20]
    return {"n": int(s.size), "sd": float(s.std()), "rho_paises": float(np.nanmean(pares)) if pares else 0.0,
            "ar1": float(np.nanmean(ar1)) if ar1 else 0.0}


def m_kish(años: pd.Index) -> float:
    c = pd.Series(años).value_counts()
    return float(c.mean() * (1 + (c.std(ddof=0) / c.mean()) ** 2))


def mde_pendiente_panel(filas: pd.Index, sx: dict, sy: dict) -> dict:
    """filas = (pais, año) con indicador y resultado disponibles (solo disponibilidad)."""
    n, mk = len(filas), m_kish(filas.get_level_values(1))
    ar = (1 - sx["ar1"] * sy["ar1"]) / (1 + sx["ar1"] * sy["ar1"])
    out = {"filas": int(n), "m_kish": _r(mk, 2)}
    for nom, rho in (("central", sx["rho_paises"] * sy["rho_paises"]), ("prudente", sy["rho_paises"])):
        n_ef = n / (1 + (mk - 1) * max(rho, 0.0)) * ar
        out[nom] = {"n_ef": _r(n_ef, 1), **{f"mde_pp_por_dt_z{k}": _r(100 * z * sy["sd"] / np.sqrt(n_ef), 2)
                                            for k, z in Z.items()}}
    return out


def mde_estado_panel(estado: pd.Series, disp: pd.Index, sy: dict) -> dict:
    """estado (pais, año) ∈ {0,1}; disp = filas con el resultado disponible. Kish + AR(1) como INT-2/INT-3b."""
    e = estado.reindex(disp).dropna()
    out = {"pais_años_estado": int((e == 1).sum()), "pais_años_resto": int((e == 0).sum())}

    def n_ef(idx):
        if len(idx) == 0:
            return np.nan
        mk = m_kish(idx.get_level_values(1))
        return len(idx) / (1 + (mk - 1) * sy["rho_paises"]) * (1 - sy["ar1"]) / (1 + sy["ar1"])

    n1, n0 = n_ef(e.index[e == 1]), n_ef(e.index[e == 0])
    out["n_ef_estado"] = _r(n1, 1)
    out.update({f"mde_pp_z{k}": _r(100 * z * sy["sd"] * np.sqrt(1 / n1 + 1 / n0), 1) for k, z in Z.items()})
    return out


def mde_serie(x: pd.Series, sd_y: float, ar1_y: float) -> dict:
    x = x.dropna()
    rx = float(x.autocorr(1))
    vif = (1 + rx * ar1_y) / (1 - rx * ar1_y)
    out = {"años": int(x.size), "media_x": _r(x.mean()), "dt_x": _r(x.std()), "ar1_x": _r(rx, 2)}
    for k, z in Z.items():
        d = z * sd_y / (np.sqrt(x.size) * x.std()) * np.sqrt(vif)
        out[f"mde_pp_0a100_z{k}"] = _r(100 * d, 1)
        out[f"mde_pp_por_dt_z{k}"] = _r(100 * d * x.std(), 1)
    return out


def mde_correlacion(n: int, fx: float, fy: float) -> dict:
    n_ef = n * (1 - fx * fy) / (1 + fx * fy)
    return {"n": int(n), "ar1_x": _r(fx, 2), "ar1_y": _r(fy, 2), "n_ef": _r(n_ef, 1),
            **{f"mde_r_z{k}": _r(z / np.sqrt(n_ef), 3) for k, z in Z.items()}}


# ---------------------------------------------------------------- objetivos binarios (solo recuentos)
def resumen_auc(df: pd.DataFrame, a0s=(0.55, 0.60), r=0.5, incremental: bool = False) -> dict:
    """df: filas (pais, t, y, E). MDE de ΔAUC frente a un listón de AUC supuesta (r = 0,5) y, si `incremental`, frente al
    logit de INT-4 (AUC 0,732 medida) con r alto (modelos anidados)."""
    if df.empty:
        return {"filas": 0}
    ev = df[df.y == 1][["pais", "E"]].drop_duplicates()
    rho, _, mk = icc_anova(df.y, df.t)
    de = 1 + (mk - 1) * rho
    n1p, n0c = int(ev.E.nunique()), float((df.y == 0).sum() / de)
    out = {"filas": int(len(df)), "eventos": int(len(ev)), "años_distintos": n1p, "tasa_base": _r(df.y.mean()),
           "icc_año": _r(rho), "efecto_diseño": _r(de, 2), "pos_ef_prudente": n1p, "neg_ef": _r(n0c, 1),
           "mde_frente_a_liston": {f"A0={a0}": {k: _r(mde_auc(a0, n1p, n0c, z, r)) for k, z in Z.items()} for a0 in a0s}}
    if incremental:
        out["mde_sobre_logit_INT4"] = {f"r={rr}": {k: _r(mde_auc(AUC_LOGIT_T1, n1p, n0c, z, rr)) for k, z in Z.items()}
                                       for rr in R_ANIDADO}
    return out


def objetivo_crisis(a: pd.DataFrame, años_pais: dict, h: int, desde: int, sin_guerras: bool,
                    excluir_tras: int = 4) -> pd.DataFrame:
    """Filas (país, t) con y = 1 si EMPIEZA una crisis bancaria (`crisisjst` = 1) en t+1 … t+h. En riesgo: t sin crisis
    iniciada en t − excluir_tras … t (tras una crisis el crédito cae por mecánica). t+h ≤ 2004."""
    filas = []
    for c in NUCLEO:
        cr = a.xs(c, level=0)["crisisjst"]
        inicios = set(cr[cr == 1].index.astype(int))
        años = años_pais[c]
        for t in sorted(años):
            if t < desde or t + h > 2004 or any(t + k not in años for k in range(1, h + 1)):
                continue
            if any(t - k in inicios for k in range(0, excluir_tras + 1)):
                continue
            if sin_guerras and any(y in GUERRAS for y in range(t, t + h + 1)):
                continue
            E = [y for y in range(t + 1, t + h + 1) if y in inicios]
            filas.append({"pais": c, "t": t, "y": int(bool(E)), "E": E[0] if E else None})
    return pd.DataFrame(filas)


def filtrar(df: pd.DataFrame, disp: set) -> pd.DataFrame:
    return df[[(p, t) in disp for p, t in zip(df.pais, df.t)]] if len(df) else df


# ---------------------------------------------------------------- indicadores (solo disponibilidad y estadísticos propios)
def money_real(a: pd.DataFrame, con) -> pd.Series:
    m = pd.concat({c: (lambda s: s.set_axis(s.index.year))(D.load_dev(con, f"jst_{c.lower()}_money"))
                   for c in D.PAISES})
    m.index.names = ["pais", "año"]
    x = np.log(m).groupby(level=0).diff() - a["inflacion"].reindex(m.index)
    return x[(a["inflacion"].reindex(x.index).abs() <= HIPER)].rename("dinero_real_g")


def credito_d5(a: pd.DataFrame) -> pd.Series:
    return a.groupby(level=0)["credito_pib"].diff(5).rename("credito_d5")


def disponibilidad_mensual(con, sid: str) -> dict:
    """Solo fechas y recuento (≤ 2004) de una serie que aún no está en las familias permitidas de src/intl/data.py."""
    r = con.execute("select min(date), max(date), count(*) from obs_latest where series_id = ? and value is not null "
                    "and date <= ?", [sid, D.DEV_END.date()]).fetchone()
    return {"serie": sid, "desde": str(r[0]), "hasta": str(r[1]), "meses": int(r[2])}


def main() -> None:
    borrador = "--prueba" in sys.argv
    proc = procedencia(exigir_limpio=not borrador)
    con = D.connect()
    a = P.anual(con)
    a = a[a.index.get_level_values(1) <= 2004]
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in NUCLEO}
    nuc = a[a.index.get_level_values(0).isin(NUCLEO)]
    res: dict = {"procedencia": proc, "nucleo": NUCLEO, "z": {k: _r(v) for k, v in Z.items()},
                 "auc_logit_T1_publicada": AUC_LOGIT_T1, "r_anidado": list(R_ANIDADO)}

    # ---------- estados de recesión por país-año (solo recuentos)
    est_rec, est_fin = {}, {}
    for _, x in rec[rec.pais.isin(NUCLEO)].iterrows():
        for y in range(int(x.pico) + 1, int(x.valle) + 1):
            est_rec[(x.pais, y)] = 1
            if x.tipo == "financiera":
                est_fin[(x.pais, y)] = 1
    idx = nuc.index
    s_rec = pd.Series([est_rec.get(k, 0) for k in idx], index=idx)
    s_fin = pd.Series([est_fin.get(k, 0) for k in idx], index=idx)
    s_crisis = (nuc["crisisjst"] == 1).astype(float).where(nuc["crisisjst"].notna())
    # crisis "activa": año de inicio y el siguiente
    s_crisis2 = (s_crisis.groupby(level=0).transform(lambda g: g.rolling(2, min_periods=1).max()))

    # ---------- Q1: oro como refugio (estado contemporáneo; oro real en moneda local; solo dt/ρ/AR(1) del oro)
    oro = A3.oro_panel(con, NUCLEO).set_index(["pais", "año"])
    oro = oro[oro["inflacion"].abs() <= HIPER]["oro_real_local"]
    q1 = {}
    for nom, (d0, d1) in {"1972_2004": (1972, 2004), "1877_2004": (1877, 2004), "1877_1971": (1877, 1971)}.items():
        o = oro[(oro.index.get_level_values(1) >= d0) & (oro.index.get_level_values(1) <= d1)]
        so = st_panel(o)
        q1[nom] = {"oro_stats": {k: _r(v) for k, v in so.items()},
                   "recesion": mde_estado_panel(s_rec, o.index, so),
                   "recesion_financiera": mde_estado_panel(s_fin, o.index, so),
                   "crisis_inicio_y_siguiente": mde_estado_panel(s_crisis2, o.index, so)}
    # serie mundial: oro real en USD frente a la cuota de países del núcleo en recesión
    mund = A3.mundial(con)["oro_usd_real"].dropna()
    cuota = s_rec.groupby(level=1).mean()
    for nom, d0 in (("mundial_usd_1972_2004", 1972), ("mundial_usd_1877_2004", 1877)):
        g = mund[mund.index >= d0]
        q1[nom] = {"oro_sd": _r(g.std()), "oro_ar1": _r(g.autocorr(1), 2),
                   "cuota_recesion": mde_serie(cuota.reindex(g.index), float(g.std()), float(g.autocorr(1))),
                   "mayoria_recesion": mde_serie((cuota.reindex(g.index) >= 0.5).astype(float), float(g.std()),
                                                 float(g.autocorr(1)))}
    res["Q1_oro_refugio"] = q1

    # ---------- Q2: oro y tipo real (EE. UU.; cada serie por separado)
    gm = D.load_dev(con, "gold_wb_usd_m")
    ir = D.load_dev(con, "oecd_ir3m_usa")
    cpi = D.load_dev(con, "oecd_cpi_usa_idx")
    g_ret = np.log(gm).diff()
    infl = np.log(cpi).diff(12).shift(1)                           # IPC interanual del mes anterior (retraso 45 días)
    real = (ir / 100 - infl.reindex(ir.index))
    q2 = {}
    for nom, d0 in (("mensual_1973_2004", "1973-01-01"), ("mensual_1980_2004", "1980-01-01")):
        gr, dr = g_ret[g_ret.index >= d0].dropna(), real.diff()[real.index >= d0].dropna()
        com = gr.index.intersection(dr.index)
        q2[nom] = {"dt_oro_mensual": _r(gr.std()), "dt_dreal_mensual_pp": _r(100 * dr.std()),
                   **mde_correlacion(len(com), float(dr.autocorr(1)), float(gr.autocorr(1)))}
    dic = gm[gm.index.month == 12]
    g_a = np.log(dic).diff().set_axis(dic.index.year)
    r_dic = real[real.index.month == 12].set_axis(real[real.index.month == 12].index.year)
    for nom, (serie_x, lab) in {"anual_dreal_1973_2004": (r_dic.diff(), "Δ tipo real dic-dic"),
                                "anual_nivel_t_menos_1_1973_2004": (r_dic.shift(1), "nivel del tipo real en dic de t−1")}.items():
        gx = g_a[g_a.index >= 1973].dropna()
        xx = serie_x.reindex(gx.index).dropna()
        q2[nom] = {"x": lab, "dt_oro_anual": _r(gx.std()), **mde_correlacion(len(xx), float(xx.autocorr(1)),
                                                                              float(gx.autocorr(1)))}
    res["Q2_oro_tipo_real"] = q2

    # ---------- Q3: dinero real en t → bolsa / bonos reales en t+1 (panel)
    x_m = money_real(a, con)
    x_m = x_m[x_m.index.get_level_values(0).isin(NUCLEO)]
    sx = st_panel(x_m)
    q3 = {"dinero_real_stats": {k: _r(v) for k, v in sx.items()}}
    for y in ("eq_tr_real", "bond_tr_real", "bill_rate_real"):
        ys = nuc[y][nuc["inflacion"].abs() <= HIPER]
        y_adel = ys.groupby(level=0).shift(-1)                       # resultado de t+1 en la fila t
        for nom, (d0, d1) in {"1871_2004": (1871, 2003), "1950_2004": (1950, 2003)}.items():
            disp = x_m.dropna().index.intersection(y_adel.dropna().index)
            disp = disp[(disp.get_level_values(1) >= d0) & (disp.get_level_values(1) <= d1)]
            sy = st_panel(ys[(ys.index.get_level_values(1) >= d0 + 1)])
            q3.setdefault(y, {})[nom] = {"resultado_stats": {k: _r(v) for k, v in sy.items()},
                                         **mde_pendiente_panel(disp, sx, sy)}
    res["Q3_dinero_activos"] = q3

    # ---------- objetivos de recesión (T1, h = 1, 1871-2004 sin guerras) y máscaras de disponibilidad
    _, mascaras = cobertura_anual(con, a)
    m5 = mascaras["5_sin_vivienda"]
    t1 = objetivo_recesion_anual(rec, años_pais, 1, 1871, True)
    t1_50 = objetivo_recesion_anual(rec, años_pais, 1, 1950, False)
    res["T1_referencia"] = {"todas": resumen_auc(t1), "con_5_de_INT4": resumen_auc(filtrar(t1, m5), incremental=True)}

    # Q4: dinero → entrada en recesión
    disp_m = set(x_m.dropna().index)
    res["Q4_dinero_recesion"] = {"frente_a_B1": resumen_auc(filtrar(t1, disp_m)),
                                 "sobre_logit_INT4": resumen_auc(filtrar(t1, disp_m & m5), incremental=True),
                                 "1950_2004_frente_a_B1": resumen_auc(filtrar(t1_50, disp_m))}

    # Q5: auge de crédito → crisis bancaria (objetivo crisisjst)
    xc = credito_d5(a)
    disp_c = set(xc.dropna().index)
    q5 = {}
    for h in (1, 2):
        cr = objetivo_crisis(a, años_pais, h, 1871, True)
        q5[f"h{h}_1871_2004_sin_guerras"] = resumen_auc(filtrar(cr, disp_c), a0s=(0.50, 0.55, 0.60))
        q5[f"h{h}_1950_2004"] = resumen_auc(filtrar(objetivo_crisis(a, años_pais, h, 1950, False), disp_c),
                                            a0s=(0.50, 0.55, 0.60))
        q5[f"h{h}_todas_las_filas_sin_credito"] = resumen_auc(cr, a0s=(0.50,))
    q5["credito_d5_stats"] = {k: _r(v) for k, v in st_panel(xc[xc.index.get_level_values(0).isin(NUCLEO)]).items()}
    res["Q5_credito_crisis"] = q5

    # Q6: diferenciales de crédito (indicador común) → entrada en recesión
    baa, aaa = D.load_dev(con, "BAA"), D.load_dev(con, "AAA")
    sp_us = (baa - aaa).dropna()
    años_us = set(sp_us[sp_us.index.month == 12].index.year)
    uk = disponibilidad_mensual(con, "boe_uk_corp_bond_spread_m")
    años_uk = set(range(pd.Timestamp(uk["desde"]).year, 2005))
    disp_us = {(p, t) for p in NUCLEO for t in años_us}
    disp_uk = {(p, t) for p in NUCLEO for t in años_uk}
    sp_dic = sp_us[sp_us.index.month == 12]
    res["Q6_diferenciales_recesion"] = {
        "baa_aaa_disponibilidad": {"desde": int(min(años_us)), "hasta": int(max(años_us)),
                                   "dt_pp_dic": _r(sp_dic.std(), 2), "ar1_anual_dic": _r(sp_dic.autocorr(1), 2)},
        "uk_spread_disponibilidad": uk,
        "us_comun_frente_a_B1": resumen_auc(filtrar(t1, disp_us)),
        "us_comun_sobre_logit_INT4": resumen_auc(filtrar(t1, disp_us & m5), incremental=True),
        "us_comun_otros_13_frente_a_B1": resumen_auc(filtrar(t1[t1.pais != "USA"], disp_us)),
        "us_propio_frente_a_B1": resumen_auc(filtrar(t1[t1.pais == "USA"], disp_us)),
        "uk_comun_frente_a_B1": resumen_auc(filtrar(t1, disp_uk)),
        "uk_comun_sobre_logit_INT4": resumen_auc(filtrar(t1, disp_uk & m5), incremental=True),
        "us_propio_desde_1973_EBP": resumen_auc(filtrar(t1[t1.pais == "USA"], {("USA", t) for t in range(1973, 2005)})),
    }

    # Q7: contagio — EE. UU. con el PIB cayendo en t / % de los otros países con el PIB cayendo en t → entrada en t+1
    cae = (nuc["pib_real_g"] < 0).where(nuc["pib_real_g"].notna()).unstack(0)
    dif = {c: cae[[k for k in cae.columns if k != c]].mean(axis=1).where(
        cae[[k for k in cae.columns if k != c]].notna().sum(axis=1) >= 5) for c in NUCLEO}
    disp_dif = {(c, int(t)) for c, s in dif.items() for t in s.dropna().index}
    disp_usa = {(c, int(t)) for c in NUCLEO if c != "USA" for t in cae["USA"].dropna().index}
    res["Q7_contagio"] = {
        "usa_cae_otros_13_frente_a_B1": resumen_auc(filtrar(t1, disp_usa)),
        "usa_cae_otros_13_sobre_logit_INT4": resumen_auc(filtrar(t1, disp_usa & m5), incremental=True),
        "difusion_caidas_frente_a_B1": resumen_auc(filtrar(t1, disp_dif)),
        "difusion_caidas_sobre_logit_INT4": resumen_auc(filtrar(t1, disp_dif & m5), incremental=True),
        "difusion_caidas_1950_2004_frente_a_B1": resumen_auc(filtrar(t1_50, disp_dif)),
        "usa_años_con_caida_1871_2004": int(cae["USA"].sum()),
    }
    con.close()
    if not borrador:
        (REPO / "research" / "int" / "int6_potencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
