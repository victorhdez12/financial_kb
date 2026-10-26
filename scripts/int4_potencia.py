"""INT-4: cálculo de potencia del termómetro de riesgo (forecast de recesión y de caídas fuertes de bolsa), ANTES de
construir nada. Solo datos ≤ 2004 (src/intl/data.load_dev).

Qué usa (y nada más):
  (i)  RECUENTOS de los objetivos: entradas en recesión por país-año (fechado anual de INT-1, convención JST), años
       distintos con entradas, agrupación entre países en el mismo año (ICC del objetivo por año), tasas base
       incondicionales; entradas en recesión NBER (USREC, solo como objetivo) y caídas fuertes de bolsa (solo recuentos);
  (ii) COBERTURA de los indicadores candidatos (cuántos país-años / meses tienen dato, por país y década).
Qué NO hace nunca: cruzar un indicador con un objetivo (ni AUC, ni correlación, ni medias condicionadas). Las dos partes
están en funciones separadas y no se juntan en ningún DataFrame. Las AUC de los listones NO se miden: se SUPONEN
(rejilla A0 = 0,50 / 0,60 / 0,70 / 0,75).

MDE: mejora mínima detectable de AUC (ΔAUC) de un modelo frente a un listón, 80 % de potencia, bilateral 5 % (z = 2,80)
y con Holm sobre 6 contrastes (z = 3,48); error típico de Hanley-McNeil (1982) para cada AUC y diferencia de AUC
correlacionadas con r = 0,5: var(Â1 − Â0) = v0 + v1 − 2 r √(v0 v1). Positivos y negativos EFECTIVOS:
  - anual, central: eventos / DE y negativos / DE, con DE = 1 + (m* − 1)·ρ, ρ = ICC del objetivo por año, m* = país-años
    medios por año con la corrección de Kish (1 + CV²);
  - anual, prudente: positivos efectivos = nº de años DISTINTOS con algún evento (los eventos del mismo año cuentan uno);
  - mensual EE. UU.: positivos = nº de entradas (cada una ocupa h meses consecutivos), negativos = meses / h.
Uso: .venv/bin/python -m scripts.int4_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int4_potencia --prueba   (sin puerta; no escribe nada)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

from src.intl import data as D
from src.intl import lags as Lg
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
PRUEBA = {"AUS", "CHE", "CAN", "IRL"}
NUCLEO = [c for c in D.PAISES if c not in PRUEBA]
GUERRAS = set(range(1914, 1919)) | set(range(1939, 1946))
UMBRAL_BOLSA_ANUAL = -0.20        # año con rentabilidad real total de la bolsa ≤ −20 %
UMBRAL_DD_MENSUAL, FIN_DD = -0.20, -0.10   # entrada: caída ≥ 20 % desde el máximo previo; episodio acaba si vuelve a > −10 %
A0S = (0.50, 0.60, 0.70, 0.75)
R_AUC = 0.5
Z1 = norm.ppf(0.975) + norm.ppf(0.80)                  # 2,80
Z6 = norm.ppf(1 - 0.05 / 12) + norm.ppf(0.80)          # 3,48 (Holm, 6 contrastes, el más exigente)


# ---------------------------------------------------------------- potencia (fórmulas, sin datos)
def var_hm(a: float, n1: float, n0: float) -> float:
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    return (a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a)) / (n1 * n0)


def mde_auc(a0: float, n1: float, n0: float, z: float, r: float = R_AUC) -> float | None:
    """Menor Δ tal que Δ / ee(Â0+Δ − Â0) = z. None si ni con AUC = 0,99 se alcanza."""
    def f(d):
        v0, v1 = var_hm(a0, n1, n0), var_hm(a0 + d, n1, n0)
        return d - z * np.sqrt(max(v0 + v1 - 2 * r * np.sqrt(v0 * v1), 1e-12))
    top = 0.99 - a0
    if f(top) < 0:
        return None
    return float(brentq(f, 1e-6, top))


def rejilla_mde(n1: float, n0: float) -> dict:
    return {f"A0={a0:.2f}": {"1_contraste": _r(mde_auc(a0, n1, n0, Z1)), "holm_6": _r(mde_auc(a0, n1, n0, Z6))}
            for a0 in A0S}


def _r(x, k=3):
    return None if x is None else round(float(x), k)


def icc_anova(y: pd.Series, grupo: pd.Series) -> tuple[float, float, float]:
    """ICC (ANOVA, grupos desiguales) de una variable binaria por grupo; devuelve (ρ, m̄, m* de Kish)."""
    df = pd.DataFrame({"y": y.to_numpy(float), "g": grupo.to_numpy()})
    g = df.groupby("g")["y"]
    n_i, k, N = g.size(), g.ngroups, len(df)
    media = df["y"].mean()
    ssb = float((n_i * (g.mean() - media) ** 2).sum())
    ssw = float(((df["y"] - g.transform("mean")) ** 2).sum())
    msb, msw = ssb / (k - 1), ssw / (N - k)
    n0 = (N - (n_i ** 2).sum() / N) / (k - 1)
    rho = (msb - msw) / (msb + (n0 - 1) * msw) if (msb + (n0 - 1) * msw) > 0 else 0.0
    m = float(n_i.mean())
    m_kish = m * (1 + (n_i.std(ddof=0) / m) ** 2)
    return max(float(rho), 0.0), m, float(m_kish)


# ---------------------------------------------------------------- objetivos (solo recuentos)
def objetivo_recesion_anual(rec: pd.DataFrame, años_pais: dict, h: int, desde: int, sin_guerras: bool) -> pd.DataFrame:
    """Filas (país, t) en riesgo (t no es año de recesión) con y = 1 si la recesión EMPIEZA (primer año de caída del PIB
    real per cápita, E = pico + 1) en t+1 … t+h. t+h ≤ 2004."""
    filas = []
    for c in NUCLEO:
        r = rec[rec.pais == c]
        en_rec = {y for _, x in r.iterrows() for y in range(int(x.pico) + 1, int(x.valle) + 1)}
        entradas = {int(x.pico) + 1: x.tipo for _, x in r.iterrows()}
        años = años_pais[c]
        for t in años:
            if t < desde or t + h > 2004 or t in en_rec or any(t + k not in años for k in range(1, h + 1)):
                continue
            ventana = range(t, t + h + 1)
            if sin_guerras and any(y in GUERRAS for y in ventana):
                continue
            E = [y for y in range(t + 1, t + h + 1) if y in entradas]
            filas.append({"pais": c, "t": t, "y": int(bool(E)), "E": E[0] if E else None,
                          "tipo": entradas[E[0]] if E else None})
    return pd.DataFrame(filas)


def objetivo_bolsa_anual(eq_real: pd.Series, h: int, desde: int, sin_guerras: bool) -> pd.DataFrame:
    """Filas (país, t) con y = 1 si algún año de t+1 … t+h tiene rentabilidad real total de la bolsa ≤ −20 %."""
    filas = []
    for c in NUCLEO:
        x = eq_real.xs(c, level=0).dropna() if c in eq_real.index.get_level_values(0) else pd.Series(dtype=float)
        ev = set(x[x <= UMBRAL_BOLSA_ANUAL].index.astype(int))
        años = set(x.index.astype(int))
        for t in sorted(años):
            if t < desde or t + h > 2004 or any(t + k not in años for k in range(1, h + 1)):
                continue
            if sin_guerras and any(y in GUERRAS for y in range(t, t + h + 1)):
                continue
            E = [y for y in range(t + 1, t + h + 1) if y in ev]
            filas.append({"pais": c, "t": t, "y": int(bool(E)), "E": E[0] if E else None, "tipo": None})
    return pd.DataFrame(filas)


def resumen_anual(df: pd.DataFrame) -> dict:
    pos = df[df.y == 1]
    eventos = pos[["pais", "E"]].drop_duplicates()                 # cada evento cuenta una vez aunque caiga en h filas
    años_ev = eventos.E.nunique()
    rho, m, m_k = icc_anova(df.y, df.t)
    de = 1 + (m_k - 1) * rho
    n1c, n0c = len(eventos) / de, (df.y == 0).sum() / de
    n1p = años_ev
    out = {"filas_en_riesgo": int(len(df)), "filas_positivas": int(len(pos)), "eventos": int(len(eventos)),
           "años_distintos_con_evento": int(años_ev), "tasa_base_filas": _r(df.y.mean()),
           "icc_por_año": _r(rho), "paises_por_año_medio": _r(m, 2), "m_kish": _r(m_k, 2), "efecto_diseño": _r(de, 2),
           "pos_ef_central": _r(n1c, 1), "neg_ef_central": _r(n0c, 1), "pos_ef_prudente": int(n1p),
           "mde_central": rejilla_mde(n1c, n0c), "mde_prudente": rejilla_mde(n1p, n0c)}
    if pos.tipo.notna().any():
        ti = pos.drop_duplicates(["pais", "E"]).tipo.value_counts()
        out["eventos_por_tipo"] = {k: int(v) for k, v in ti.items()}
        # potencia del subtipo "financiera" (mismo listón, solo esos eventos como positivos)
        nf = int(ti.get("financiera", 0))
        if nf >= 5:
            años_f = pos[pos.tipo == "financiera"].drop_duplicates(["pais", "E"]).E.nunique()
            out["mde_financieras_central"] = rejilla_mde(nf / de, n0c)
            out["mde_financieras_prudente"] = rejilla_mde(años_f, n0c)
            out["años_distintos_financieras"] = int(años_f)
    return out


def objetivo_nber(usrec: pd.Series, h: int, desde: str) -> dict:
    s = usrec.copy()
    s.index = s.index.to_period("M")
    entrada = (s == 1) & (s.shift(1) == 0)
    meses = s.index[(s.index >= pd.Period(desde, "M")) & (s.index <= pd.Period("2004-12", "M") - h)]
    filas = []
    for t in meses:
        if s[t] == 1:
            continue
        fut = [t + k for k in range(1, h + 1)]
        E = [m for m in fut if bool(entrada.get(m, False))]
        filas.append({"t": t, "y": int(bool(E)), "E": E[0] if E else None})
    df = pd.DataFrame(filas)
    ev = sorted({str(e) for e in df.E.dropna()})
    n1, n0 = len(ev), (df.y == 0).sum() / h
    return {"meses_en_riesgo": int(len(df)), "meses_positivos": int(df.y.sum()), "entradas": n1, "fechas_entrada": ev,
            "tasa_base_meses": _r(df.y.mean()), "pos_ef": n1, "neg_ef": _r(n0, 1), "mde": rejilla_mde(n1, n0)}


def objetivo_dd_mensual(precio: pd.Series, h: int, desde: str) -> dict:
    """Entradas en caída fuerte: el índice (precio, media mensual OCDE) cae ≥ 20 % desde su máximo previo; el episodio
    termina cuando vuelve a estar a menos del 10 % del máximo. Meses en riesgo: fuera de episodio."""
    p = precio.dropna()
    p.index = p.index.to_period("M")
    dd = p / p.cummax() - 1
    en_ep, ep, entradas = False, [], []
    for t, v in dd.items():
        if not en_ep and v <= UMBRAL_DD_MENSUAL:
            en_ep = True
            entradas.append(t)
        elif en_ep and v > FIN_DD:
            en_ep = False
        ep.append(en_ep)
    ep = pd.Series(ep, index=dd.index)
    ent = set(entradas)
    meses = dd.index[(dd.index >= pd.Period(desde, "M")) & (dd.index <= pd.Period("2004-12", "M") - h)]
    filas = []
    for t in meses:
        if ep[t]:
            continue
        E = [t + k for k in range(1, h + 1) if (t + k) in ent]
        filas.append({"t": t, "y": int(bool(E)), "E": E[0] if E else None})
    df = pd.DataFrame(filas)
    ev = sorted({str(e) for e in df.E.dropna()})
    n1, n0 = len(ev), (df.y == 0).sum() / h
    return {"meses_en_riesgo": int(len(df)), "meses_positivos": int(df.y.sum()), "entradas": n1, "fechas_entrada": ev,
            "todas_las_entradas_desde_1957": [str(e) for e in entradas], "tasa_base_meses": _r(df.y.mean()),
            "pos_ef": n1, "neg_ef": _r(n0, 1), "mde": rejilla_mde(n1, n0) if n1 >= 2 else None}


# ---------------------------------------------------------------- indicadores (solo cobertura)
def cobertura_anual(con, a: pd.DataFrame) -> dict:
    """Nº de país-años con dato de cada candidato, por país y década (1870-2004). No toca ningún objetivo."""
    hp = {c: D.load_dev(con, f"jst_{c.lower()}_hpnom") for c in D.PAISES}
    hp = pd.concat({c: s.set_axis(s.index.year) for c, s in hp.items() if not s.empty}).rename("hpnom")
    hp.index.names = ["pais", "año"]
    x = a.join(hp, how="left")
    ind = pd.DataFrame(index=x.index)
    ind["C1_curva"] = x["ltrate"] - x["stir"]
    ind["C2_credito_d5"] = x.groupby(level=0)["credito_pib"].diff(5)
    ind["C3_vivienda_real_d3"] = x.groupby(level=0).apply(
        lambda g: np.log(g["hpnom"] / g["cpi"]).diff(3)).reset_index(level=0, drop=True)
    inv = (ind["C1_curva"] < 0).where(ind["C1_curva"].notna())
    nuc = inv[inv.index.get_level_values(0).isin(NUCLEO)].unstack(0)
    # difusión: % de los OTROS países del núcleo con curva invertida en t (exige ≥ 5 con dato)
    dif = {}
    for c in D.PAISES:
        otros = nuc[[k for k in nuc.columns if k != c]]
        dif[c] = (otros.mean(axis=1)).where(otros.notna().sum(axis=1) >= 5)
    ind["C4_difusion_curva"] = pd.concat(dif).reindex(ind.index)
    tr = x["stir"] / 100 - x["inflacion"]
    ind["C5_tipo_real_d1"] = tr.groupby(level=0).diff(1)
    ind["C6_bolsa_real_t"] = x["eq_tr_real"]
    ind = ind.loc[ind.index.get_level_values(1) <= 2004]
    dec = (ind.index.get_level_values(1) // 10) * 10
    out = {}
    for col in ind.columns:
        tab = ind[col].notna().groupby([ind.index.get_level_values(0), dec]).sum().unstack(1).fillna(0).astype(int)
        primero = ind[col].dropna().reset_index().groupby("pais")["año"].min()
        out[col] = {"pais_años_nucleo_1870_2004": int(tab.loc[tab.index.isin(NUCLEO)].to_numpy().sum()),
                    "pais_años_nucleo_1950_2004": int(tab.loc[tab.index.isin(NUCLEO), [d for d in tab.columns
                                                                                       if d >= 1950]].to_numpy().sum()),
                    "primer_año": {k: int(v) for k, v in primero.items()},
                    "por_decada": {p: {str(d): int(v) for d, v in fila.items()} for p, fila in tab.iterrows()}}
    # máscaras de DISPONIBILIDAD (solo si hay dato, nunca su valor): para contar eventos en los país-años utilizables
    sin_viv = [c for c in ind.columns if not c.startswith("C3")]
    mascaras = {"5_sin_vivienda": set(ind.index[ind[sin_viv].notna().all(axis=1)]),
                "las_6": set(ind.index[ind.notna().all(axis=1)])}
    return out, mascaras


def cobertura_mensual_usa(con) -> dict:
    """Primer mes "as of" de cada candidato mensual de EE. UU. (y de la difusión de IP entre los otros 13)."""
    m = P.mensual(con)
    u = m.xs("USA", level=0)
    res = {"C1_curva": u["curva"], "C5_tipo_real_d12": (u["tipo_3m"] / 100 - u["ipc_yoy"]).diff(12),
           "C6_bolsa_12m": u["bolsa_12m"], "listón_vol_12m": u["r_bolsa_precio"].rolling(12).std()}
    ipneg = (m["ip_yoy"] < 0).where(m["ip_yoy"].notna()).unstack(0)
    otros = ipneg[[c for c in NUCLEO if c != "USA"]]
    res["C4_difusion_ip"] = otros.mean(axis=1).where(otros.notna().sum(axis=1) >= 5)
    out = {k: {"primer_mes": str(v.dropna().index.min().date()), "meses": int(v.notna().sum())} for k, v in res.items()}
    for v, col in (("C2_credito_d5", "tloans"), ("C3_vivienda_real_d3", "hpnom")):
        s = D.load_dev(con, f"jst_usa_{col}")
        out[v] = {"fuente": f"jst_usa_{col} (anual, as of con {Lg.RETRASO_DIAS['jst']} días)",
                  "primer_año": int(s.index.year.min())}
    return out


def main() -> None:
    borrador = "--prueba" in sys.argv
    proc = procedencia(exigir_limpio=not borrador)
    con = D.connect()
    a = P.anual(con)
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in NUCLEO}
    res: dict = {"procedencia": proc, "nucleo": NUCLEO, "prueba_no_usados": sorted(PRUEBA),
                 "supuestos": {"A0_listón_supuestas": list(A0S), "r_entre_auc": R_AUC, "z_1": _r(Z1), "z_holm6": _r(Z6),
                               "umbral_bolsa_anual_real": UMBRAL_BOLSA_ANUAL,
                               "dd_mensual": {"entrada": UMBRAL_DD_MENSUAL, "fin": FIN_DD}}}
    # --- objetivos anuales (núcleo)
    anual = {}
    for nom, desde, sg in (("1871_2004_sin_guerras", 1871, True), ("1950_2004", 1950, False)):
        anual[nom] = {}
        for h in (1, 2):
            anual[nom][f"recesion_h{h}"] = resumen_anual(objetivo_recesion_anual(rec, años_pais, h, desde, sg))
            anual[nom][f"bolsa_h{h}"] = resumen_anual(objetivo_bolsa_anual(a["eq_tr_real"], h, desde, sg))
    res["anual"] = anual
    # --- cobertura de los candidatos (aparte; solo se cruza la DISPONIBILIDAD con las filas, nunca los valores)
    res["cobertura_anual"], mascaras = cobertura_anual(con, a)
    res["anual_con_datos"] = {}
    for nom, desde, sg in (("1871_2004_sin_guerras", 1871, True), ("1950_2004", 1950, False)):
        for mk, ms in mascaras.items():
            for h in (1, 2):
                df = objetivo_recesion_anual(rec, años_pais, h, desde, sg)
                df = df[[(p, t) in ms for p, t in zip(df.pais, df.t)]]
                res["anual_con_datos"].setdefault(nom, {}).setdefault(mk, {})[f"recesion_h{h}"] = resumen_anual(df)
    # --- EE. UU. mensual (objetivo NBER y caída fuerte de bolsa); muestra desde que hay curva as of (1964-07)
    usrec = D.load_dev(con, "USREC")
    precio = D.load_dev(con, "oecd_share_usa")
    res["usa_mensual"] = {}
    for desde in ("1964-07", "1957-01"):
        res["usa_mensual"][desde] = {f"nber_h{h}": objetivo_nber(usrec, h, desde) for h in (6, 12)}
        res["usa_mensual"][desde].update({f"caida_bolsa_h{h}": objetivo_dd_mensual(precio, h, desde) for h in (6, 12)})
    res["cobertura_mensual_usa"] = cobertura_mensual_usa(con)
    con.close()
    if not borrador:
        (REPO / "research" / "int" / "int4_potencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for nom, bloque in anual.items():
        print("==", nom)
        for k, v in bloque.items():
            print(f"  {k:14s} filas={v['filas_en_riesgo']} ev={v['eventos']} años_ev={v['años_distintos_con_evento']} "
                  f"base={v['tasa_base_filas']} icc={v['icc_por_año']} DE={v['efecto_diseño']} "
                  f"n1c={v['pos_ef_central']} n0c={v['neg_ef_central']} tipos={v.get('eventos_por_tipo')}")
            print("     central ", v["mde_central"])
            print("     prudente", v["mde_prudente"])
    for desde, b in res["usa_mensual"].items():
        print("== USA mensual desde", desde)
        for k, v in b.items():
            print(f"  {k:14s} riesgo={v['meses_en_riesgo']} entradas={v['entradas']} {v['fechas_entrada']} mde={v['mde']}")
    for nom, b in res["anual_con_datos"].items():
        for mk, bb in b.items():
            for k, v in bb.items():
                print("con datos", nom, mk, k, v["filas_en_riesgo"], v["eventos"], v["años_distintos_con_evento"],
                      v["efecto_diseño"], v["mde_central"]["A0=0.60"], v["mde_prudente"]["A0=0.60"])
    print({k: (v["pais_años_nucleo_1870_2004"], v["pais_años_nucleo_1950_2004"]) for k, v in res["cobertura_anual"].items()})
    print(res["cobertura_mensual_usa"])


if __name__ == "__main__":
    main()
