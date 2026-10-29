"""Corrida ÚNICA de P-DEV-INT6 v1.0 (docs/int/INT6_prerregistro_v1.md, congelado 2026-10-29T18:01:03Z).
Confirmatorias (una familia Holm-6 sobre p calibrados con placebo): G2 (oro y tipo real, EE. UU. mensual 1973-2004),
M1 / M2 (dinero real → bolsa / bonos reales de t + 1, panel JST), K1 (auge de crédito → crisis bancaria), K2 (Δ diferencial
corporativo del centro financiero → entrada en recesión), X1 (contagio: % de otros países con el PIB cayendo → entrada).
Descriptivas e informativas (§4, sin Holm ni veredicto): G1 (oro como refugio), M3 (dinero → recesión), ICC por décadas.
Sensibilidades del §3 (no deciden). Concreciones: docs/int/INT6_notas_implementacion.md; motor: src/intl/int6.py.
Datos: solo src/intl/data.load_dev (≤ 2004-12). Exige el árbol limpio.
Salida: research/int/int6_resultado.json y .md, y una línea en research/trial_log.md.
Uso: .venv/bin/python -m scripts.int6_corrida              (corrida única, con puerta)
     .venv/bin/python -m scripts.int6_corrida --informe    (rehace el .md desde el JSON; no recalcula)
     .venv/bin/python -m scripts.int6_corrida --comprobar  (sin puerta: solo carga datos y cuenta filas y eventos; no
                                                            cruza ningún indicador con ningún resultado ni escribe nada)
"""
from __future__ import annotations

import datetime as dt
import json
import sys

import numpy as np
import pandas as pd

from scripts.int4_corrida import _r
from scripts.int4_potencia import icc_anova
from src.intl import activos3b as A3
from src.intl import data as D
from src.intl import int3 as I
from src.intl import int3b as B
from src.intl import int4 as M
from src.intl import int6 as S
from src.intl import panel as P
from src.intl.procedencia import REPO, procedencia
from src.warehouse import db

NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
PRUEBA_BOLSA, PRUEBA_SIN_BOLSA = ["AUS", "CHE"], ["CAN", "IRL"]
PRUEBA = PRUEBA_BOLSA + PRUEBA_SIN_BOLSA
TODOS = NUCLEO + PRUEBA
AÑOS = range(M.A0, M.A1 + 1)
C_INT4 = ["C1", "C2", "C4", "C5", "C6"]
PRERREGISTRO = "docs/int/INT6_prerregistro_v1.md (v1.0, congelado 2026-10-29T18:01:03Z, 1bdecf8)"
FRASE_G1 = "con datos ≤ 2004 esto no puede distinguir un refugio de +10-20 pp de cero"
OMITIDAS = {
    "G2_oro_en_EUR": "no hay EUR/USD (ni ECU) antes de 1999 en las familias permitidas de src/intl/data.py y el "
                     "prerregistro solo autoriza añadir boe_uk_corp_bond_spread_m (notas §B.6)",
    "K2_EBP": "fed_ebp_* no está en las familias permitidas (la decisión 4 no lo añade); solo descriptivo, 4 entradas, "
              "no es 'as of' (notas §E.4)",
}


# ---------------------------------------------------------------- carga
def ancho(a: pd.DataFrame, col: str) -> pd.DataFrame:
    return a[col].unstack(0).reindex(index=AÑOS)


def jst_extra(con, var: str) -> pd.Series:
    s = {c: D.load_dev(con, f"jst_{c.lower()}_{var}") for c in D.PAISES}
    s = pd.concat({c: x.set_axis(x.index.year) for c, x in s.items() if not x.empty})
    s.index.names = ["pais", "año"]
    return s


def largo(w: pd.DataFrame, paises: list[str], nombre: str) -> pd.DataFrame:
    v = w.reindex(columns=paises)
    return pd.DataFrame({"año": np.repeat(v.index.to_numpy(), len(paises)), "pais": np.tile(paises, len(v)),
                         nombre: v.to_numpy(float).ravel()})


def cargar(con) -> dict:
    a = P.anual(con)
    if a.index.get_level_values(1).max() > 2004:
        raise D.FactorCutoffError("panel anual con años > 2004")
    extra = pd.DataFrame({v: jst_extra(con, v) for v in ("hpnom", "money", "wage", "narrowm", "pop", "crisisjst_old")})
    if extra.index.get_level_values(1).max() > 2004:
        raise D.FactorCutoffError("JST extra con años > 2004")
    mc = P._mensual_completa
    m = {k: mc(D.load_dev(con, sid)) for k, sid in (("oro", "gold_wb_usd_m"), ("ir3m", "oecd_ir3m_usa"),
                                                      ("cpi", "oecd_cpi_usa_idx"), ("gs10", "GS10"),
                                                      ("bolsa", "oecd_share_usa"), ("baa", "BAA"), ("aaa", "AAA"),
                                                      ("uk", "boe_uk_corp_bond_spread_m"))}
    for k, s in m.items():
        if s.index.max() > D.DEV_END:
            raise D.FactorCutoffError(f"{k}: fechas > 2004")
    oro_usd = A3.oro_usd_fin_de_año(con)
    oro_usd_real = A3._real(oro_usd / oro_usd.shift(1) - 1, A3.inflacion_jst(con, "USA"))
    oro_panel = A3.oro_panel(con, NUCLEO)
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    return {"a": a, "extra": extra, "m": m, "oro_usd_real": oro_usd_real[oro_usd_real.index <= 2004],
            "oro_panel": oro_panel, "rec": rec}


def preparar(d: dict) -> dict:
    a, extra, rec = d["a"], d["extra"], d["rec"]
    W = {c: ancho(a, c) for c in ("cpi", "rgdpmad", "tloans", "gdp", "eq_tr_real", "bond_tr_real", "bill_rate_real",
                                  "crisisjst", "pib_real_g")}
    for v in ("money", "narrowm", "pop", "crisisjst_old"):
        W[v] = extra[v].unstack(0).reindex(index=AÑOS)
    infl_log = np.log(W["cpi"]).diff()
    infl_simple = np.expm1(infl_log)
    fuera = S.hiper_fuera(pd.Series({(c, int(t)): v for c in infl_simple.columns
                                     for t, v in infl_simple[c].dropna().items()}, dtype=float))
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in TODOS}
    primer = {c: min(v) for c, v in años_pais.items()}
    # dinero real (M1, M2, M3); winsorización con los p1 / p99 del núcleo sin hiperinflación (notas §C.2)
    x_din = (np.log(W["money"]).diff() - infl_log).replace([np.inf, -np.inf], np.nan)
    fuera_w = pd.DataFrame(False, index=x_din.index, columns=x_din.columns)
    for c, t in fuera:
        if c in fuera_w.columns and t in fuera_w.index:
            fuera_w.loc[t, c] = True

    def wins(x: pd.DataFrame) -> pd.DataFrame:
        ref = x[NUCLEO].where(~fuera_w[NUCLEO]).stack()
        lo, hi = np.nanquantile(ref.to_numpy(float), [0.01, 0.99])
        return x.clip(lo, hi), [float(lo), float(hi)]

    x_din_w, lim_din = wins(x_din)
    pib_total = W["rgdpmad"] * W["pop"]
    x_exceso_w, _ = wins((np.log(W["money"]).diff() - np.log(pib_total).diff()).replace([np.inf, -np.inf], np.nan))
    x_estrecho_w, _ = wins((np.log(W["narrowm"]).diff() - infl_log).replace([np.inf, -np.inf], np.nan))
    crisis = {c: W["crisisjst"][c].dropna() for c in TODOS}
    crisis_old = {c: W["crisisjst_old"][c].dropna() for c in TODOS}
    m = d["m"]
    sp_us = (m["baa"] - m["aaa"]).dropna()
    dsp = S.empalme(S.delta_diciembre(m["uk"].dropna()), S.delta_diciembre(sp_us))
    pan = M.paneles(a, extra[["hpnom", "money", "wage"]], NUCLEO, TODOS, None)
    cae = (W["pib_real_g"] < 0).astype(float).where(W["pib_real_g"].notna())
    return {"W": W, "fuera": fuera, "años_pais": años_pais, "primer": primer, "infl_log": infl_log,
            "x_din_w": x_din_w, "lim_din": lim_din, "x_exceso_w": x_exceso_w, "x_estrecho_w": x_estrecho_w,
            "crisis": crisis, "crisis_old": crisis_old, "sp_us": sp_us, "dsp": dsp, "pan": pan, "cae": cae,
            "pib_total": pib_total, "rec": rec}


def sin_fuera(f: pd.DataFrame, fuera: set) -> pd.DataFrame:
    return f[[(p, t) not in fuera for p, t in zip(f.pais, f.t)]].reset_index(drop=True)


# ---------------------------------------------------------------- G2
def g2_datos(m: dict, largo_plazo: bool = False) -> pd.DataFrame:
    idx = pd.date_range("1955-01-01", "2004-12-01", freq="MS")
    oro, cpi = m["oro"].reindex(idx), m["cpi"].reindex(idx)
    tipo = (m["gs10"] if largo_plazo else m["ir3m"]).reindex(idx)
    infl = np.log(cpi).diff(12)
    real = tipo / 100 - infl.shift(1)
    f = pd.DataFrame({"y": np.log(oro).diff(), "x": real.diff(), "real": real, "oro": oro}, index=idx)
    return f


def g2(m: dict) -> dict:
    f = g2_datos(m)
    g = f.loc["1973-01-01":"2004-12-01", ["y", "x"]].dropna()
    r = S.ts_mensual(g.y.to_numpy(), g.x.to_numpy())
    r["meses"] = [str(g.index.min().date()), str(g.index.max().date())]
    r["pct_oro_por_pp"] = r["efecto"]
    yr = g.index.year
    r["pendiente_1973_1988"] = B.pendiente(g.y[yr <= 1988], g.x[yr <= 1988])
    r["pendiente_1989_2004"] = B.pendiente(g.y[yr >= 1989], g.x[yr >= 1989])
    dic = f[f.index.month == 12]
    an = pd.DataFrame({"y": np.log(dic.oro).diff().values, "x": dic.real.diff().values}, index=dic.index.year)
    an = an.loc[1973:2004].dropna()
    r["anual_dic_dic"] = {"años": int(len(an)), "pendiente": B.pendiente(an.y, an.x)}
    sen = {}
    fl = g2_datos(m, largo_plazo=True).loc["1973-01-01":"2004-12-01", ["y", "x"]].dropna()
    sen["tipo_real_largo_GS10"] = {k: v for k, v in S.ts_mensual(fl.y.to_numpy(), fl.x.to_numpy(), placebo=False).items()}
    g7 = g[~g.index.year.isin([1979, 1980])]
    sen["sin_1979_1980"] = {k: v for k, v in S.ts_mensual(g7.y.to_numpy(), g7.x.to_numpy(), placebo=False).items()}
    sen["oro_en_EUR"] = {"omitida": OMITIDAS["G2_oro_en_EUR"]}
    r["sensibilidades"] = sen
    return r


# ---------------------------------------------------------------- M1 / M2
def m_filas(pr: dict, ycol: str, xw: pd.DataFrame, paises: list[str], h: int = 1) -> pd.DataFrame:
    y = pr["W"][ycol].shift(-h)
    f = largo(xw, paises, "x").merge(largo(y, paises, "y"), on=["año", "pais"])
    f = f[[(p, int(t)) not in pr["fuera"] for p, t in zip(f.pais, f["año"])]]
    return f.dropna().assign(año=lambda d: d["año"].astype(int)).reset_index(drop=True)


def m_pregunta(pr: dict, ycol: str, prueba: list[str]) -> dict:
    f = m_filas(pr, ycol, pr["x_din_w"], NUCLEO)
    r = S.panel_continuo(f, "y", "x")
    r["winsor_p1_p99"] = pr["lim_din"]
    sen = {}
    g = f[~(f["año"].isin(M.GUERRAS) | (f["año"] + 1).isin(M.GUERRAS))]
    sen["sin_guerras"] = S.panel_continuo(g, "y", "x", placebo=False, completo=False)
    sen["exceso_de_dinero"] = S.panel_continuo(m_filas(pr, ycol, pr["x_exceso_w"], NUCLEO), "y", "x", placebo=False,
                                               completo=False)
    sen["dinero_estrecho_real"] = S.panel_continuo(m_filas(pr, ycol, pr["x_estrecho_w"], NUCLEO), "y", "x",
                                                   placebo=False, completo=False)
    sen["t_mas_2"] = S.panel_continuo(m_filas(pr, ycol, pr["x_din_w"], NUCLEO, h=2), "y", "x", placebo=False,
                                      completo=False)
    sen["letras_reales_informativa"] = S.panel_continuo(m_filas(pr, "bill_rate_real", pr["x_din_w"], NUCLEO), "y", "x",
                                                        placebo=False, completo=False)
    r["sensibilidades"] = sen
    fp = m_filas(pr, ycol, pr["x_din_w"], prueba)
    fp["z"] = (fp.x - r["media_x"]) / r["dt_x"]
    ef = S.pendientes_pais(fp.y, fp.z, fp.pais)
    r["paises_prueba_pendiente_con_z_del_nucleo"] = {c: {"pendiente": float(e), "filas": int((fp.pais == c).sum())}
                                                     for c, e in zip(ef.pais, ef.efecto)}
    return r


# ---------------------------------------------------------------- objetivos de giro
def filas_t1(pr: dict, paises: list[str], desde: int = 1871, sg: bool = True) -> pd.DataFrame:
    return sin_fuera(M.obj_entrada(pr["rec"], pr["años_pais"], paises, 1, desde, sg), pr["fuera"])


def filas_k1(pr: dict, paises: list[str], h: int = 1, crisis: dict | None = None, excluir_tras: int = 4) -> pd.DataFrame:
    return S.objetivo_crisis(crisis or pr["crisis"], pr["años_pais"], paises, h, 1871, True, excluir_tras, pr["fuera"])


def b1_t1(pr: dict, f: pd.DataFrame) -> np.ndarray:
    return M.liston(f, "T1", pr["rec"], pr["primer"], {})


def base_int4(pr: dict, f: pd.DataFrame) -> np.ndarray:
    return np.column_stack([b1_t1(pr, f), S.mirar(f, [pr["pan"][c] for c in C_INT4])])


def recuentos(pr: dict) -> dict:
    """Para --comprobar: solo filas y eventos (nada cruzado con ningún indicador)."""
    t1, k1 = filas_t1(pr, NUCLEO), filas_k1(pr, NUCLEO)
    return {"T1_filas_eventos": [len(t1), int(t1.y.sum())], "K1_filas_eventos": [len(k1), int(k1.y.sum())],
            "K1_años_con_inicio": int(k1[k1.y == 1].t.nunique()),
            "dsp_años": [int(pr["dsp"].dropna().index.min()), int(pr["dsp"].dropna().index.max()),
                         int(pr["dsp"].notna().sum())],
            "M_filas_x": int(pr["x_din_w"][NUCLEO].notna().sum().sum()), "hiper_fuera": len(pr["fuera"])}


# ---------------------------------------------------------------- G1, ICC
def estados(pr: dict, a_idx: list[tuple]) -> pd.DataFrame:
    rec = pr["rec"]
    en, fin = set(), set()
    for _, x in rec.iterrows():
        for y in range(int(x.pico) + 1, int(x.valle) + 1):
            en.add((x.pais, y))
            if x.tipo == "financiera":
                fin.add((x.pais, y))
    cri = {(c, t) for c, s in pr["crisis"].items() for t in S.inicios_crisis(s)}
    cri2 = cri | {(c, t + 1) for c, t in cri}
    return pd.DataFrame({"pais": [p for p, _ in a_idx], "año": [t for _, t in a_idx],
                         "recesion": [float(k in en) for k in a_idx], "recesion_financiera": [float(k in fin) for k in a_idx],
                         "crisis_inicio_y_siguiente": [float(k in cri2) for k in a_idx]})


def g1(d: dict, pr: dict) -> dict:
    pot = json.loads((REPO / "research" / "int" / "int6_potencia.json").read_text())["Q1_oro_refugio"]
    o = d["oro_panel"].copy()
    o["año"] = o["año"].astype(int)
    o = o[[(p, t) not in pr["fuera"] for p, t in zip(o.pais, o["año"])]]
    o = o.merge(estados(pr, list(zip(o.pais, o["año"]))), on=["pais", "año"])
    out = {"frase_obligatoria": FRASE_G1, "panel_moneda_local": {}}
    for tramo, (a0, a1) in {"1972_2004": (1972, 2004), "1877_1971": (1877, 1971), "1877_2004": (1877, 2004)}.items():
        g = o[o["año"].between(a0, a1)]
        for est in ("recesion", "recesion_financiera", "crisis_inicio_y_siguiente"):
            r = B.panel_contraste(g, "oro_real_local", est, placebo=False, paises=False)
            out["panel_moneda_local"][f"{tramo}|{est}"] = {
                "efecto": r["efecto"], "ic95_dk": r["ic95"], "p_dk": r["p"], "n": r["n"], "n_estado": r["n_estado"],
                "mde_pp_1_contraste": pot[tramo][est]["mde_pp_z1"], "mde_pp_holm6": pot[tramo][est]["mde_pp_zholm6"]}
    nuc = [(p, t) for p in NUCLEO for t in AÑOS if t in pr["años_pais"][p]]
    e = estados(pr, nuc)
    cuota = e.groupby("año").recesion.mean()
    for tramo, a0 in (("1972_2004", 1972), ("1877_2004", 1877)):
        y = d["oro_usd_real"][d["oro_usd_real"].index >= a0]
        r = B.ts_contraste(y, cuota, placebo=False)
        mde = pot[f"mundial_usd_{tramo}"]["cuota_recesion"]
        out[f"oro_usd_real_cuota_recesion_{tramo}"] = {
            "efecto_0_a_100": r["efecto"], "ic95": r["ic95"], "p_nw": r["p"], "n_años": r["n_años"],
            "efecto_por_dt_cuota": r["efecto"] * float(cuota.reindex(y.dropna().index).std()),
            "mde_pp_0a100_1_contraste": mde["mde_pp_0a100_z1"], "mde_pp_0a100_holm6": mde["mde_pp_0a100_zholm6"]}
    m = d["m"]
    idx = pd.date_range("1972-12-01", "2004-12-01", freq="MS")
    f = pd.DataFrame({"oro": np.log(m["oro"].reindex(idx)).diff(), "bolsa": np.log(m["bolsa"].reindex(idx)).diff()})
    f = f.loc["1973-01-01":].dropna()
    for u in (5, 8):
        st = (f.bolsa <= -u / 100).astype(float)
        r = B.nw(f.oro.to_numpy(), st.to_numpy(), S.LAGS_G2)
        mde = pot[f"mensual_caida_bolsa_usa_{u}pc_1973_2004"]
        out[f"oro_meses_caida_bolsa_usa_{u}pc_1973_2004"] = {
            "meses_estado": int(st.sum()), "meses": int(len(st)), "diferencia_pp_mes": 100 * r["efecto"],
            "ic95_pp": [100 * v for v in r["ic95"]], "p_nw": r["p"],
            "mde_pp_mes_1_contraste": mde["mde_pp_mes_z1"], "mde_pp_mes_holm6": mde["mde_pp_mes_zholm6"]}
    return out


def icc_decadas(pr: dict) -> dict:
    nuc = [(p, t) for p in NUCLEO for t in AÑOS if t in pr["años_pais"][p]]
    e = estados(pr, nuc)
    e["crec"] = [pr["W"]["pib_real_g"].at[t, p] for p, t in nuc]
    out = {}
    for d0 in range(1870, 2001, 10):
        g = e[e["año"].between(d0, d0 + 9)]
        gc = g.dropna(subset=["crec"])
        out[f"{d0}s"] = {"filas": int(len(gc)), "icc_crecimiento": icc_anova(gc.crec, gc["año"])[0],
                         "icc_recesion": icc_anova(g.recesion, g["año"])[0]}
    return out


# ---------------------------------------------------------------- corrida
def main() -> None:
    if "--informe" in sys.argv:          # solo rehace el .md desde el JSON ya escrito (no recalcula nada)
        R = json.loads((REPO / "research" / "int" / "int6_resultado.json").read_text())
        (REPO / "research" / "int" / "int6_resultado.md").write_text(informe(R))
        return
    comprobar = "--comprobar" in sys.argv
    proc = procedencia(exigir_limpio=not comprobar)
    con = D.connect()
    d = cargar(con)
    con.close()
    pr = preparar(d)
    if comprobar:
        print(json.dumps(recuentos(pr), indent=1))
        return
    pan = pr["pan"]
    res: dict = {"procedencia": proc, "prerregistro": PRERREGISTRO,
                 "notas": "docs/int/INT6_notas_implementacion.md", "omitidas_declaradas": OMITIDAS,
                 "recuentos": recuentos(pr), "confirmatorias": {}}
    C = res["confirmatorias"]

    # ---- G2
    C["G2"] = g2(d["m"])
    print("G2", round(C["G2"]["efecto"], 4), flush=True)

    # ---- M1, M2
    C["M1"] = m_pregunta(pr, "eq_tr_real", PRUEBA_BOLSA)
    C["M2"] = m_pregunta(pr, "bond_tr_real", PRUEBA)
    print("M1/M2 hechos", flush=True)

    # ---- K1
    x_k1 = (pr["W"]["tloans"] / pr["W"]["gdp"]).diff(5) * 100
    f = filas_k1(pr, NUCLEO)
    base = S.liston_crisis(f, pr["crisis"], pr["primer"])
    per = {"1871_1913": (1871, 1913), "1919_2004": (1919, 2004), "1950_2004": (1950, 2004)}
    r = S.evaluar(f, base, [x_k1], periodos=per)
    sen = {}
    f2 = filas_k1(pr, NUCLEO, h=2)
    sen["h2"] = S.evaluar(f2, S.liston_crisis(f2, pr["crisis"], pr["primer"]), [x_k1], h=2, placebo=False)
    fo = filas_k1(pr, NUCLEO, crisis=pr["crisis_old"])
    sen["crisisjst_old"] = S.evaluar(fo, S.liston_crisis(fo, pr["crisis_old"], pr["primer"]), [x_k1], placebo=False)
    sen["credito_en_log"] = S.evaluar(f, base, [np.log(pr["W"]["tloans"]).diff(5)], placebo=False)
    f3 = filas_k1(pr, NUCLEO, excluir_tras=2)
    sen["exclusion_3_años"] = S.evaluar(f3, S.liston_crisis(f3, pr["crisis"], pr["primer"]), [x_k1], placebo=False)
    r["sensibilidades"] = sen
    fp = filas_k1(pr, PRUEBA)
    r["paises_prueba"] = S.congelado(f, base, [x_k1], fp, S.liston_crisis(fp, pr["crisis"], pr["primer"]), [x_k1])
    C["K1"] = r
    print("K1", round(r["d_auc"], 4), flush=True)

    # ---- K2
    x_k2 = S.comun(pr["dsp"], TODOS)
    f = filas_t1(pr, NUCLEO)
    base = b1_t1(pr, f)
    r = S.evaluar(f, base, [x_k2], periodos={"1950_2004": (1950, 2004)})
    sen = {}
    sen["solo_EEUU_1919_2004"] = S.evaluar(f[f.t >= 1919].reset_index(drop=True), base[f.t.to_numpy() >= 1919],
                                           [x_k2], placebo=False)
    sen["RU_todos_los_años"] = S.evaluar(f, base, [S.comun(S.delta_diciembre(d["m"]["uk"].dropna()), TODOS)],
                                         placebo=False)
    niv = S.empalme(S.nivel_mediana10(d["m"]["uk"].dropna()), S.nivel_mediana10(pr["sp_us"]))
    sen["nivel_menos_mediana_10_años"] = S.evaluar(f, base, [S.comun(niv, TODOS)], placebo=False)
    sen["sobre_logit_INT4_informativo"] = S.evaluar(f, base_int4(pr, f), [x_k2], placebo=False)
    fu = f[f.pais == "USA"].reset_index(drop=True)
    xu = S.mirar(fu, [S.comun(S.delta_diciembre(pr["sp_us"]), TODOS)])
    bu = b1_t1(pr, fu)
    ok = np.isfinite(xu).all(axis=1) & np.isfinite(bu).all(axis=1)
    yu = fu.y.to_numpy(float)[ok]
    p1 = M.logit_pred(M.logit_fit(np.column_stack([bu[ok], xu[ok]]), yu), np.column_stack([bu[ok], xu[ok]]))
    p0 = M.logit_pred(M.logit_fit(bu[ok], yu), bu[ok])
    sen["EEUU_propio_diferencial_descriptivo_dentro_de_muestra"] = {
        "filas": int(ok.sum()), "eventos": int(yu.sum()), "auc_liston": M.auc(yu, p0), "auc_modelo": M.auc(yu, p1),
        "d_auc": M.auc(yu, p1) - M.auc(yu, p0)}
    sen["EBP"] = {"omitida": OMITIDAS["K2_EBP"]}
    r["sensibilidades"] = sen
    fp = filas_t1(pr, PRUEBA)
    r["paises_prueba"] = S.congelado(f, base, [x_k2], fp, b1_t1(pr, fp), [x_k2])
    C["K2"] = r
    print("K2", round(r["d_auc"], 4), flush=True)

    # ---- X1
    x_x1 = pan["S4"]
    r = S.evaluar(f, base, [x_x1], periodos={"1950_2004": (1950, 2004)})
    sen = {}
    fo = f[f.pais != "USA"].reset_index(drop=True)
    usa = pd.DataFrame({c: pr["cae"]["USA"] for c in TODOS if c != "USA"}).reindex(index=AÑOS)
    sen["EEUU_con_PIB_cayendo_otros_13"] = S.evaluar(fo, base[f.pais.to_numpy() != "USA"], [usa], placebo=False)
    sen["cuota_ponderada_PIB"] = S.evaluar(f, base, [S.cuota_otros(pr["cae"], NUCLEO, TODOS, pr["pib_total"])],
                                           placebo=False)
    sen["sobre_logit_INT4_informativo"] = S.evaluar(f, base_int4(pr, f), [x_x1], placebo=False)
    f50 = filas_t1(pr, NUCLEO, desde=1950, sg=False)
    sen["1950_2004"] = S.evaluar(f50, b1_t1(pr, f50), [x_x1], placebo=False)
    r["sensibilidades"] = sen
    r["paises_prueba"] = S.congelado(f, base, [x_x1], fp, b1_t1(pr, fp), [x_x1])
    C["X1"] = r
    print("X1", round(r["d_auc"], 4), flush=True)

    # ---- multiplicidad y veredictos (§5; notas §G)
    p_main = {"G2": C["G2"]["placebo"]["p_cal"], "M1": C["M1"]["placebo"]["p_cal"], "M2": C["M2"]["placebo"]["p_cal"],
              **{q: C[q]["placebo"]["p_z"] for q in ("K1", "K2", "X1")}}
    p_i = {**{q: p_main[q] for q in ("G2", "M1", "M2")}, **{q: C[q]["p_bloques"] for q in ("K1", "K2", "X1")}}
    h_main, h_i = I.holm(p_main), I.holm(p_i)
    orden = sorted(p_main, key=p_main.get)
    res["holm6"] = {"alfa": S.ALFA, "p": p_main, "pasa": h_main,
                    "umbral_por_rango": {q: S.ALFA / (6 - i) for i, q in enumerate(orden)},
                    "criterio_i_auc": {"p": p_i, "pasa": h_i}}
    g = C["G2"]
    cg = {"1_b_negativo": bool(g["efecto"] < 0), "2_holm6_p_cal": bool(h_main["G2"]),
          "3_supera_p95_placebo": bool(g["placebo"]["supera_p95"]),
          "4_signo_1973_1988_y_1989_2004": bool(g["pendiente_1973_1988"] < 0 and g["pendiente_1989_2004"] < 0),
          "5_signo_anual_dic_dic": bool(g["anual_dic_dic"]["pendiente"] < 0)}
    cg["ESTABLECIDO"] = all(cg.values())
    ver = {"G2": cg, "M1": S.criterios_panel(C["M1"], +1, h_main["M1"]),
           "M2": S.criterios_panel(C["M2"], +1, h_main["M2"])}
    k1 = C["K1"]
    ver["K1"] = S.criterios_auc(k1, h_i["K1"], h_main["K1"],
                                k1["periodo_1871_1913"]["d_auc"] > 0 and k1["periodo_1919_2004"]["d_auc"] > 0,
                                "dauc_1871_1913_y_1919_2004_pos")
    for q in ("K2", "X1"):
        ver[q] = S.criterios_auc(C[q], h_i[q], h_main[q], C[q]["temporal_1950_2004"]["d_auc"] > 0,
                                 "temporal_1950_2004_pos")
    res["veredicto"] = ver
    print("confirmatorias hechas", flush=True)

    # ---- descriptivas e informativas (§4)
    desc = {"G1_oro_refugio": g1(d, pr)}
    f = filas_t1(pr, NUCLEO)
    desc["M3_dinero_recesion"] = {
        "frente_a_B1": S.evaluar(f, b1_t1(pr, f), [pr["x_din_w"]], periodos={"1950_2004": (1950, 2004)}),
        "sobre_logit_INT4": S.evaluar(f, base_int4(pr, f), [pr["x_din_w"]], periodos={"1950_2004": (1950, 2004)})}
    desc["ICC_por_decadas"] = icc_decadas(pr)
    res["descriptivas"] = desc
    res["hora_fin_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    R = _r(res)
    out = REPO / "research" / "int"
    (out / "int6_resultado.json").write_text(json.dumps(R, indent=1, ensure_ascii=False))
    est = {q: v["ESTABLECIDO"] for q, v in ver.items()}
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(f"| {dt.date.today().isoformat()} | Constructor (P-DEV-INT6 v1.0, corrida única) | commit "
                 f"{proc['commit'][:7]}; G2, M1, M2, K1, K2, X1, Holm-6 sobre p calibrados con placebo; establecidos "
                 f"{json.dumps(est)}; G1 y M3 descriptivas; research/int/int6_resultado.json |\n")
    print(json.dumps(est, indent=1), flush=True)
    (out / "int6_resultado.md").write_text(informe(R))    # el .md se puede rehacer desde el JSON con --informe


# ---------------------------------------------------------------- informe
def _f(v, k=3):
    return "–" if v is None else f"{v:+.{k}f}"


def _si(b):
    return "sí" if b else "no"


def informe(r: dict) -> str:
    p, C, V, H = r["procedencia"], r["confirmatorias"], r["veredicto"], r["holm6"]
    L = ["# INT-6: resultado de la corrida única (oro, dinero, crédito y relaciones entre países)", "",
         f"Procedencia: commit `{p['commit'][:7]}`, árbol limpio {p['arbol_limpio']}, {p['hora_utc']}. "
         f"Prerregistro: {r['prerregistro']}. Concreciones: `{r['notas']}`. Datos ≤ 2004 (nada de JST ≥ 2005).", "",
         "## Resumen", "",
         "| id | pregunta | efecto | IC 95 % | p_cal (placebo) | umbral Holm-6 | pasa Holm | veredicto |",
         "|---|---|---|---|---|---|---|---|"]
    preg = {"G2": "oro frente a Δ tipo real (EE. UU., mensual 1973-2004; signo −)",
            "M1": "dinero real en t → bolsa real en t + 1 (signo +)",
            "M2": "dinero real en t → bonos reales en t + 1 (signo +)",
            "K1": "Δ5 crédito/PIB → inicio de crisis bancaria en t + 1 (signo +)",
            "K2": "Δ diferencial corporativo del centro (R. U. ≤ 1918, EE. UU. ≥ 1919) → entrada en recesión (signo +)",
            "X1": "% de otros países con el PIB cayendo → entrada en recesión (signo +)"}
    for q in ("G2", "M1", "M2", "K1", "K2", "X1"):
        c = C[q]
        if q == "G2":
            ef = f"{c['efecto']:+.3f} % de oro por pp (r = {c['r_estandarizada']:+.3f})"
            ic = f"[{c['ic95'][0]:+.3f}; {c['ic95'][1]:+.3f}]"
        elif q in ("M1", "M2"):
            ef = f"{100 * c['efecto']:+.2f} pp por 1 dt"
            ic = f"[{100 * c['ic95'][0]:+.2f}; {100 * c['ic95'][1]:+.2f}]"
        else:
            ef = f"ΔAUC estrat. {_f(c['d_auc'])} ({c['auc_liston']:.3f} → {c['auc_modelo']:.3f})"
            ic = f"[{_f(c['d_auc_ic95'][0])}; {_f(c['d_auc_ic95'][1])}]"
        pc = H["p"][q]
        L.append(f"| {q} | {preg[q]} | {ef} | {ic} | {pc:.4f} | {H['umbral_por_rango'][q]:.4f} | {_si(H['pasa'][q])} | "
                 f"**{'establecido' if V[q]['ESTABLECIDO'] else 'no establecido'}** |")
    L += ["", "p_cal: G2, M1 y M2, p bilateral con la t dividida por φ = máx(1, dt de las t placebo) (INT-3b); K1, K2 y X1, "
          "p unilateral de la z del placebo de la ΔAUC estratificada (INT-4-ML). Holm-6 sobre estos seis p (α = 0,05).", "",
          "## Detalle por pregunta", ""]
    g = C["G2"]
    L += ["### G2: oro y tipo real", "",
          f"- {g['T']} meses ({g['meses'][0]} a {g['meses'][1]}). b = {g['efecto']:+.3f} (% de oro por 1 pp de Δ tipo real), "
          f"IC 95 % [{g['ic95'][0]:+.3f}; {g['ic95'][1]:+.3f}], t de Newey-West (6 retardos) {g['t']:+.2f}, p {g['p']:.4f}; "
          f"r = {g['r_estandarizada']:+.3f}.",
          f"- Placebo ({g['placebo']['placebos']} desplazamientos): φ = {g['placebo']['phi']:.2f}, p_cal = "
          f"{g['placebo']['p_cal']:.4f}, p95 de |t| placebo = {g['placebo']['p95_abs_t_placebo']:.2f}, p por rangos "
          f"{g['placebo']['p_rangos']:.3f} (sin Holm).",
          f"- Mitades: 1973-1988 {_f(g['pendiente_1973_1988'])}, 1989-2004 {_f(g['pendiente_1989_2004'])}; anual "
          f"diciembre a diciembre ({g['anual_dic_dic']['años']} años) {_f(g['anual_dic_dic']['pendiente'])}.",
          f"- Criterios: {V['G2']}.",
          f"- Sensibilidades (no deciden): tipo real largo b {_f(g['sensibilidades']['tipo_real_largo_GS10']['efecto'])} "
          f"(p {g['sensibilidades']['tipo_real_largo_GS10']['p']:.4f}); sin 1979-1980 b "
          f"{_f(g['sensibilidades']['sin_1979_1980']['efecto'])} (p {g['sensibilidades']['sin_1979_1980']['p']:.4f}); "
          f"oro en EUR: omitida ({r['omitidas_declaradas']['G2_oro_en_EUR']}).", ""]
    for q, nom in (("M1", "bolsa"), ("M2", "bonos")):
        c = C[q]
        s = c["sensibilidades"]
        n1 = sum(v > 0 for v in c["por_pais_sin_encoger"].values())
        n2 = sum(v > 0 for v in c["por_pais_dl_sin_año"].values())
        L += [f"### {q}: dinero real → {nom} real del año siguiente", "",
              f"- {c['n']} filas, {c['paises']} países, {c['años_rango'][0]}-{c['años_rango'][1]}. b = "
              f"{100 * c['efecto']:+.2f} pp por 1 dt de dinero real (dt = {100 * c['dt_x']:.1f} pp), IC 95 % DK "
              f"[{100 * c['ic95'][0]:+.2f}; {100 * c['ic95'][1]:+.2f}], t {c['t']:+.2f}, p {c['p']:.4f}.",
              f"- Placebo ({c['placebo']['placebos']}): φ = {c['placebo']['phi']:.2f}, p_cal = {c['placebo']['p_cal']:.4f}, "
              f"p por rangos {c['placebo']['p_rangos']:.3f}.",
              f"- 1950-2004: {100 * c['efecto_1950_2004']:+.2f} pp; con efectos de año: {100 * c['efecto_efectos_de_año']:+.2f} "
              f"pp; países con signo +: {n1}/{len(c['por_pais_sin_encoger'])} sin encoger, {n2}/{len(c['por_pais_dl_sin_año'])} "
              "DL sin la media del año.",
              f"- Criterios: {V[q]}.",
              "- Sensibilidades (pp por 1 dt [IC]): " + "; ".join(
                  f"{k} {100 * v['efecto']:+.2f} [{100 * v['ic95'][0]:+.2f}; {100 * v['ic95'][1]:+.2f}]" for k, v in s.items()),
              "- Países de prueba (pendiente con la z del núcleo, pp): " + "; ".join(
                  f"{k} {100 * v['pendiente']:+.2f} ({v['filas']} filas)"
                  for k, v in c["paises_prueba_pendiente_con_z_del_nucleo"].items()), ""]
    for q in ("K1", "K2", "X1"):
        c = C[q]
        pl = c["placebo"]
        L += [f"### {q}", "",
              f"- {c['filas']} filas, {c['eventos']} eventos en {c['años_eventos']} años. AUC estratificada B1 "
              f"{c['auc_liston']:.3f} → modelo {c['auc_modelo']:.3f}: ΔAUC {_f(c['d_auc'])} [{_f(c['d_auc_ic95'][0])}; "
              f"{_f(c['d_auc_ic95'][1])}], p bloques {c['p_bloques']:.4f}; ΔAUC agrupada {_f(c['d_auc_agrupada'])}; "
              f"Δlog-loss {_f(c['d_logloss'], 4)}; pendiente de calibración {c['calibracion']['pendiente']:.2f}.",
              f"- Placebo ({pl['desplazamientos']}): media {_f(pl['media'])}, dt {pl['dt']:.3f}, z {pl['z']:+.2f}, "
              f"p_z {pl['p_z']:.4f}, p por rangos {pl['p_rangos']:.3f} (sin Holm).",
              "- Periodos (ΔAUC estratificada): " + "; ".join(
                  f"{k.replace('periodo_', '')} {_f(v['d_auc'])} ({v['eventos']} ev.)" for k, v in c.items()
                  if k.startswith("periodo_")) + f"; temporal 1950-2004 {_f(c['temporal_1950_2004']['d_auc'])}.",
              f"- Criterios: {V[q]}.",
              "- Sensibilidades (ΔAUC estratificada; no deciden): " + "; ".join(
                  f"{k} {_f(v['d_auc'])}" + (f" [{_f(v['d_auc_ic95'][0])}; {_f(v['d_auc_ic95'][1])}]" if "d_auc_ic95" in v else "")
                  for k, v in c["sensibilidades"].items() if "d_auc" in v)]
        pp = c["paises_prueba"]
        if pp.get("eventos"):
            L.append(f"- Países de prueba (modelo congelado): {pp['filas']} filas / {pp['eventos']} eventos, ΔAUC estrat. "
                     f"{_f(pp['d_auc'])} [{_f(pp['d_auc_ic95'][0])}; {_f(pp['d_auc_ic95'][1])}].")
        L.append("")
    if "omitida" in C["K2"]["sensibilidades"]["EBP"]:
        L += [f"K2, EBP: omitido ({r['omitidas_declaradas']['K2_EBP']}).", ""]
    D_ = r["descriptivas"]
    G = D_["G1_oro_refugio"]
    L += ["## Descriptivas e informativas (sin Holm, sin veredicto)", "", "### G1: oro como refugio", "",
          f"**{G['frase_obligatoria'][0].upper() + G['frase_obligatoria'][1:]}.**", "",
          "| tramo · estado | efecto (pp/año) | IC 95 % DK | n (en el estado) | MDE 1 / Holm-6 (pp) |", "|---|---|---|---|---|"]
    for k, v in G["panel_moneda_local"].items():
        L.append(f"| {k} | {100 * v['efecto']:+.1f} | [{100 * v['ic95_dk'][0]:+.1f}; {100 * v['ic95_dk'][1]:+.1f}] | "
                 f"{v['n']} ({v['n_estado']}) | {v['mde_pp_1_contraste']} / {v['mde_pp_holm6']} |")
    for k in ("1972_2004", "1877_2004"):
        v = G[f"oro_usd_real_cuota_recesion_{k}"]
        L.append(f"- Oro real en USD frente a la cuota del núcleo en recesión, {k}: {100 * v['efecto_0_a_100']:+.1f} pp de 0 % "
                 f"a 100 % [{100 * v['ic95'][0]:+.1f}; {100 * v['ic95'][1]:+.1f}] ({100 * v['efecto_por_dt_cuota']:+.1f} pp por "
                 f"1 dt de la cuota; MDE 0→100 {v['mde_pp_0a100_1_contraste']} / {v['mde_pp_0a100_holm6']}).")
    for u in (5, 8):
        v = G[f"oro_meses_caida_bolsa_usa_{u}pc_1973_2004"]
        L.append(f"- Oro en los {v['meses_estado']} meses con la bolsa de EE. UU. ≤ −{u} % (1973-2004): "
                 f"{v['diferencia_pp_mes']:+.2f} pp en el mes frente al resto [{v['ic95_pp'][0]:+.2f}; {v['ic95_pp'][1]:+.2f}] "
                 f"(MDE {v['mde_pp_mes_1_contraste']} / {v['mde_pp_mes_holm6']}).")
    L += ["", "### M3: dinero → entrada en recesión (informativa)", ""]
    for k, v in D_["M3_dinero_recesion"].items():
        L.append(f"- {k}: {v['filas']} filas / {v['eventos']} eventos; ΔAUC estratificada {_f(v['d_auc'])} "
                 f"[{_f(v['d_auc_ic95'][0])}; {_f(v['d_auc_ic95'][1])}]; z placebo {v['placebo']['z']:+.2f}; "
                 f"temporal 1950-2004 {_f(v['temporal_1950_2004']['d_auc'])}.")
    L += ["", "### ICC por décadas (parte común entre países; solo descriptiva)", "",
          "| década | filas | ICC crecimiento | ICC recesión |", "|---|---|---|---|"]
    for k, v in D_["ICC_por_decadas"].items():
        L.append(f"| {k} | {v['filas']} | {v['icc_crecimiento']:.2f} | {v['icc_recesion']:.2f} |")
    L += ["", "\"No establecido\" no es \"no existe\": varias preguntas tenían una potencia de ≈ 40-80 % (§2 del prerregistro).",
          "Detalle completo en `research/int/int6_resultado.json`."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
