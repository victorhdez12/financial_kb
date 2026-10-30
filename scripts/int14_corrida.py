"""P-DEV-INT14 v1.0 (docs/int/INT14_prerregistro_v1.md): corrida ÚNICA de desarrollo del estudio de eventos A (≤ 2004).

Con puerta: árbol de git limpio (procedencia) y se niega a correr si research/int/int14_resultado.json ya existe.
Uso: .venv/bin/python -m scripts.int14_corrida            (corrida con puerta; escribe json + md)
     .venv/bin/python -m scripts.int14_corrida --prueba   (sin puerta, sin escribir, pocas réplicas: SOLO para depurar
                                                            el código antes de commitear; imprime solo recuentos)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.int14_potencia import CORTE, GUERRAS, Datos, construir_eventos
from src.intl import eventos as E
from src.intl.data import PAISES

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research" / "int" / "int14_resultado.json"
SEMILLA = 20261030
HM = (1, 3, 6, 12, 24)
HA = (1, 2, 3)
HAMILTON_2011 = ["1947-11", "1953-06", "1957-01", "1969-02", "1973-04", "1979-05", "1980-11", "1990-08", "1999-12",
                 "2002-11"]                      # prerregistro v1.0 §1 (verificado contra la tabla 1 del original)
PRINCIPALES = {"H1": ("panel", "crisis", "vivienda", "H3"), "H2": ("panel", "crisis", "bolsa", "H1"),
               "H3": ("mensual", "vol", "bolsa", "h12"), "H4": ("panel", "petroleo_global", "bolsa", "H1")}
NOMBRES = {"petroleo": "shock del petróleo", "vol": "pico de volatilidad", "dolar": "subida fuerte del dólar",
           "crisis": "crisis bancaria"}


def _r(x, d=4):
    return None if x is None or not np.isfinite(x) else round(float(x), d)


def _pp(x):
    return None if x is None or not np.isfinite(x) else round(100 * float(np.expm1(x)), 2)


# ================================================================ rentabilidades
def mensuales(D: Datos, B: dict) -> dict[str, pd.Series]:
    ult = lambda x: E.a_mensual(x, "ultimo")                                  # noqa: E731
    med = lambda x: E.a_mensual(x, "media")                                   # noqa: E731
    r = B["r_us_d"]
    bolsa = (1 + r).groupby(r.index.to_period("M")).prod() - 1
    rf = D.s("ffx_us_rf_d") / 100
    letras = (1 + rf).groupby(rf.index.to_period("M")).prod() - 1
    y = ult(D.s("shiller_gs10")) / 100
    y0 = y.shift(1)
    bonos = (y0 / y) * (1 - (1 + y / 2) ** -20) + (1 + y / 2) ** -20 - 1 + y0 / 12
    oro = ult(D.s("gold_usd_monthly")).pct_change()
    cfp = ult(D.s("aqr_cfp_commodities_market_m")) / 100
    out = {"bolsa": bolsa, "letras": letras, "bonos_10a_aprox": bonos,
           "oro": oro[oro.index >= pd.Period("1968-04", "M")],
           "materias_aqr_cfp": (cfp + letras.reindex(cfp.index)),
           "materias_aqr_clr_exceso": ult(D.s("aqr_clr_ew_xret_m")) / 100,
           "petroleo": B["oil"].pct_change(),
           "energia_bm": med(D.s("wb_idx_energy")).pct_change(),
           "metales_base_bm": med(D.s("wb_idx_base_metals_ex_iron_ore")).pct_change(),
           "metales_preciosos_bm": med(D.s("wb_idx_precious_metals")).pct_change()}
    res = {}
    for k, v in out.items():
        v = v.dropna()
        res[k] = v.reindex(pd.period_range(v.index.min(), v.index.max(), freq="M"))
    return res


def panel(D: Datos) -> dict[str, pd.DataFrame]:
    cpi = pd.DataFrame({c: D.anual(f"jst_{c.lower()}_cpi") for c in PAISES})
    infl = cpi.pct_change()
    out = {}
    for a, col in (("bolsa", "eq_tr"), ("bonos", "bond_tr"), ("letras", "bill_rate"), ("vivienda", "housing_tr")):
        tr = pd.DataFrame({c: D.anual(f"jst_{c.lower()}_{col}") for c in PAISES})
        x = ((1 + tr) / (1 + infl) - 1).reindex(range(1871, 2005))
        x.loc[x.index.isin(list(GUERRAS))] = np.nan                         # años de guerra fuera (prerregistro §2)
        out[a] = x
    return out


def mundial_anual(D: Datos) -> dict[str, pd.DataFrame]:
    cpi = D.anual("jst_usa_cpi")
    infl = cpi.pct_change()
    g = D.s("gold_usd_monthly")
    g = g[g.index.month == 12]
    g.index = g.index.year
    oro = ((1 + g.pct_change()) / (1 + infl.reindex(g.index)) - 1).loc[1969:2004]
    clr = D.s("aqr_clr_ew_xret_m") / 100
    clr_a = (1 + clr).groupby(clr.index.year).prod() - 1
    clr_a = clr_a[(clr.groupby(clr.index.year).count() == 12).reindex(clr_a.index).fillna(False)].loc[:2004]
    out = {"oro_real_usd": oro, "materias_clr_exceso": clr_a}
    res = {}
    for k, v in out.items():
        v = v.dropna().reindex(range(int(v.index.min()), 2005))
        v.loc[v.index.isin(list(GUERRAS))] = np.nan
        res[k] = v.to_frame("MUNDO")
    return res


# ================================================================ capas
def capa_mensual(R: dict, conjuntos: dict, reps_desc: int, reps_ppal: int) -> dict:
    out = {}
    for ev, (fechas, retraso, sep) in conjuntos.items():
        out[ev] = {}
        for a, r in R.items():
            out[ev][a] = {}
            for h in HM:
                ppal = (ev, a, f"h{h}") == PRINCIPALES["H3"][1:]
                ef = E.efecto_eventos(r, fechas, h, retraso)
                fila = {"n": ef.n_eventos, "efecto_log": _r(ef.efecto), "efecto_pp": _r(100 * ef.efecto, 2),
                        "media_abs_pct": _pp(ef.media_evento), "media_normal_pct": _pp(ef.media_incond),
                        "prop_pos": _r(float((ef.acumuladas > 0).mean()), 3) if ef.n_eventos else None,
                        "fechas": [str(f) for f in ef.fechas]}
                if ef.n_eventos < 5:
                    fila["nota"] = "n insuficiente"
                else:
                    lo, hi = E.ic_bloques(ef, bloque=60, n_boot=2000 if ppal else 1000, semilla=SEMILLA)
                    pl = E.placebo(r, ef.n_eventos, h, retraso, sep, n_rep=reps_ppal if ppal else reps_desc,
                                   semilla=SEMILLA, excluir=list(fechas))
                    fila.update({"ic90_pp": [_r(100 * lo, 2), _r(100 * hi, 2)], "p_placebo": _r(E.p_placebo(ef.efecto, pl)),
                                 "placebos_validos": int(np.isfinite(pl).sum())})
                out[ev][a][f"h{h}"] = fila
        print("mensual", ev, {a: v["h12"]["n"] for a, v in out[ev].items()}, flush=True)
    return out


def capa_panel(P: dict, conjuntos: dict, reps_desc: int, reps_ppal: int, episodio: dict) -> dict:
    out = {}
    for ev, (eventos, comun, sep) in conjuntos.items():
        out[ev] = {}
        for a, r in P.items():
            out[ev][a] = {}
            for nombre, H, desde in [("H0_año_t", 1, 0)] + [(f"H{H}", H, 1) for H in HA]:
                ppal = (ev, a, nombre) == PRINCIPALES["H1"][1:] or (ev, a, nombre) == PRINCIPALES["H2"][1:] \
                    or (ev, a, nombre) == PRINCIPALES["H4"][1:]
                res = E.efecto_panel(r, eventos, H, comun=comun, desde=desde)
                d = res["detalle"]
                n_ind = d["año"].nunique() if len(d) else 0
                fila = {"n_pais_evento": res["n"], "n_años_distintos": int(n_ind), "efecto_log": _r(res["efecto"]),
                        "efecto_pp": _r(100 * res["efecto"], 2) if np.isfinite(res["efecto"]) else None,
                        "media_abs_pct": _pp(res["media_abs"]), "prop_pos": _r(res["prop_pos"], 3)}
                if n_ind < 5 or res["n"] < 5:
                    fila["nota"] = "n insuficiente"
                else:
                    if comun:
                        d = d.assign(cong=d["año"])
                    else:
                        d = d.assign(cong=d["año"].map(episodio))
                    lo, hi = E.ic_panel(d, n_boot=2000 if ppal else 1000, semilla=SEMILLA, conglomerado="cong")
                    pl = E.placebo_panel(r, eventos, H, comun, sep, n_rep=reps_ppal if ppal else reps_desc,
                                         semilla=SEMILLA, excluir_años=frozenset(GUERRAS), desde=desde)
                    fila.update({"ic90_pp": [_r(100 * lo, 2), _r(100 * hi, 2)],
                                 "p_placebo": _r(E.p_placebo(res["efecto"], pl)),
                                 "placebos_validos": int(np.isfinite(pl).sum())})
                out[ev][a][nombre] = fila
        print("panel", ev, {a: v["H1"]["n_pais_evento"] for a, v in out[ev].items()}, flush=True)
    return out


# ================================================================ tabla "qué activo protege"
def tabla_protege(mens: dict, pan: dict, mund: dict) -> list[dict]:
    filas = []
    def etiqueta(f, ref):
        if f.get("nota") or f.get("media_abs_pct") is None:
            return "n insuficiente"
        ic = f.get("ic90_pp") or [None, None]
        if ic[1] is not None and ic[1] < 0:
            return "sufre"
        if f["media_abs_pct"] > 0 and (ref is None or f["media_abs_pct"] > ref):
            return "protege"
        return "—"
    for ev in ("petroleo", "vol", "dolar"):
        ref = mens[ev]["bolsa"]["h12"].get("media_abs_pct")
        for a, v in mens[ev].items():
            f = v["h12"]
            filas.append({"evento": ev, "capa": "mensual EE. UU./mundo, 12 m (nominal)", "activo": a, "n": f["n"],
                          "media_tras_evento_pct": f["media_abs_pct"], "efecto_vs_normal_pp": f["efecto_pp"],
                          "ic90_pp": f.get("ic90_pp"), "etiqueta": etiqueta(f, None if a == "bolsa" else ref)})
    for ev in ("crisis", "petroleo_global", "vol_global", "dolar_global"):
        ref = pan[ev]["bolsa"]["H3"].get("media_abs_pct")
        for a, v in pan[ev].items():
            f = v["H3"]
            filas.append({"evento": ev, "capa": "panel JST real, t+1..t+3", "activo": a, "n": f["n_pais_evento"],
                          "media_tras_evento_pct": f["media_abs_pct"], "efecto_vs_normal_pp": f["efecto_pp"],
                          "ic90_pp": f.get("ic90_pp"), "etiqueta": etiqueta(f, None if a == "bolsa" else ref)})
        evm = {"crisis": "crisis_episodios", "petroleo_global": "petroleo", "vol_global": "vol",
               "dolar_global": "dolar"}[ev]
        for a, v in mund[evm].items():
            f = v["H3"]
            filas.append({"evento": ev, "capa": "mundial anual (USD), t+1..t+3", "activo": a,
                          "n": f["n_pais_evento"], "media_tras_evento_pct": f["media_abs_pct"],
                          "efecto_vs_normal_pp": f["efecto_pp"], "ic90_pp": f.get("ic90_pp"),
                          "etiqueta": etiqueta(f, ref)})
    return filas


# ================================================================ informe
def informe_md(res: dict) -> str:
    L = ["# INT-14: qué les pasa a los activos tras cuatro tipos de evento (corrida única de desarrollo, ≤ 2004)", "",
         f"Prerregistro: `docs/int/INT14_prerregistro_v1.md` (v1.0). Procedencia: commit `{res['procedencia']['commit'][:7]}`, "
         f"árbol limpio, {res['procedencia']['hora_utc']}. Nada ≥ 2005. Unidades: % acumulado (pp para diferencias); "
         "capa mensual nominal en USD; panel JST real por país.", "",
         "## 1. Contrastes principales (Holm, α = 5 %)", "",
         "| id | pregunta | n | efecto frente a lo normal | IC 90 % | p placebo | p Holm | veredicto |",
         "|---|---|---|---|---|---|---|---|"]
    for k, v in res["principales"].items():
        L.append(f"| {k} | {v['pregunta']} | {v['n']} | {v['efecto_pp']} pp | {v['ic90_pp']} | {v['p_placebo']} | "
                 f"{v['p_holm']} | **{v['veredicto']}** |")
    L += ["", "\"Establecido\" = p Holm < 0,05 y el IC 90 % no contiene 0. \"No establecido\" no prueba que no haya "
          "efecto: el MDE (80 %) era 7-13 pp.", ""]
    L += ["## 2. Qué activo protege en cada evento (descriptivo; orientativo con n pequeño)", "",
          "\"protege\" = rentabilidad media tras el evento > 0 y mayor que la de la bolsa en la misma capa; "
          "\"sufre\" = efecto frente a lo normal con IC 90 % entero < 0.", "",
          "| evento | capa | activo | n | media tras evento | frente a lo normal | IC 90 % | etiqueta |",
          "|---|---|---|---|---|---|---|---|"]
    for f in res["tabla_protege"]:
        L.append(f"| {f['evento']} | {f['capa']} | {f['activo']} | {f['n']} | {f['media_tras_evento_pct']} % | "
                 f"{f['efecto_vs_normal_pp']} pp | {f['ic90_pp']} | {f['etiqueta']} |")
    L += ["", "## 3. Trayectoria por horizonte (capa mensual, eventos principales)", ""]
    for ev in ("petroleo", "vol", "dolar"):
        L += [f"### {NOMBRES[ev]} — efecto frente a lo normal (pp) [IC 90 %] (p placebo)", "",
              "| activo | n | " + " | ".join(f"{h} m" for h in HM) + " |", "|---|---|" + "---|" * len(HM)]
        for a, v in res["mensual"][ev].items():
            cel = []
            for h in HM:
                f = v[f"h{h}"]
                cel.append("n<5" if f.get("nota") else f"{f['efecto_pp']} [{f['ic90_pp'][0]}; {f['ic90_pp'][1]}] "
                                                      f"({f['p_placebo']})")
            L.append(f"| {a} | {v['h12']['n']} | " + " | ".join(cel) + " |")
        L.append("")
    L += ["## 4. Panel anual JST (real), efecto frente a lo normal (pp) [IC 90 %] (p placebo)", ""]
    for ev, v0 in res["panel"].items():
        L += [f"### {ev}", "", "| activo | n | año t | t+1 | t+1..t+2 | t+1..t+3 |", "|---|---|---|---|---|---|"]
        for a, v in v0.items():
            cel = []
            for k in ("H0_año_t", "H1", "H2", "H3"):
                f = v[k]
                cel.append("n<5" if f.get("nota") else f"{f['efecto_pp']} [{f['ic90_pp'][0]}; {f['ic90_pp'][1]}] "
                                                      f"({f['p_placebo']})")
            L.append(f"| {a} | {v['H1']['n_pais_evento']} | " + " | ".join(cel) + " |")
        L.append("")
    L += ["## 5. Capa mundial anual (oro real en USD desde 1969; materias CLR exceso desde 1878)", ""]
    for ev, v0 in res["mundial"].items():
        for a, v in v0.items():
            cel = []
            for k in ("H0_año_t", "H1", "H2", "H3"):
                f = v[k]
                cel.append("n<5" if f.get("nota") else f"{f['efecto_pp']} [{f['ic90_pp'][0]}; {f['ic90_pp'][1]}]")
            L.append(f"- {ev} → {a} (n {v['H1']['n_pais_evento']}): año t / t+1 / t+1..2 / t+1..3 = " + " · ".join(cel))
    L += ["", "## 6. Sensibilidades (capa mensual, bolsa a 12 m)", ""]
    for ev, v in res["mensual"].items():
        f = v["bolsa"]["h12"]
        L.append(f"- {ev}: n {f['n']}, efecto {f['efecto_pp']} pp, IC {f.get('ic90_pp')}, p {f.get('p_placebo')}")
    L += ["", "Detalle completo (todas las combinaciones, fechas de cada evento): `research/int/int14_resultado.json`.", ""]
    return "\n".join(L)


# ================================================================ principal
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    prueba = "--prueba" in argv
    if not prueba and SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: P-DEV-INT14 es una corrida ÚNICA (prerregistro v1.0 §0)")
    from src.intl.procedencia import procedencia
    from src.warehouse import db
    reps_desc, reps_ppal = (20, 40) if prueba else (300, 2000)
    t0 = time.time()
    res = {"prerregistro": "docs/int/INT14_prerregistro_v1.md v1.0", "procedencia": procedencia(exigir_limpio=not prueba),
           "corte": str(CORTE.date()), "semilla": SEMILLA, "reps": {"descriptivo": reps_desc, "principal": reps_ppal}}
    con = db.connect(read_only=True)
    D = Datos(con, db)
    B = construir_eventos(D)
    R = mensuales(D, B)
    P = panel(D)
    M = mundial_anual(D)
    con.close()
    for k, v in {**R, **{f"panel_{k}": v for k, v in P.items()}}.items():
        idx = v.index
        assert (idx.max().year if hasattr(idx.max(), "year") else idx.max()) <= 2004, k
    ev = B["ev"]
    f = lambda k: list(ev[k]["fecha"])                                         # noqa: E731
    conj_m = {"petroleo": (f("petroleo"), 1, 24), "vol": (f("vol"), 0, 12), "dolar": (f("dolar"), 1, 24),
              "petroleo_sens_u10": (f("petroleo_sens_u10"), 1, 24), "petroleo_sens_u30": (f("petroleo_sens_u30"), 1, 24),
              "petroleo_sens_domestico": (f("petroleo_sens_domestico"), 1, 24),
              "petroleo_sens_hamilton2011": ([pd.Period(x, "M") for x in HAMILTON_2011], 1, 24),
              "vol_sens_p95": (f("vol_sens_p95"), 0, 12), "vol_sens_sep6": (f("vol_sens_sep6"), 0, 6),
              "vol_sens_racha": (f("vol_sens_racha"), 0, 12), "vol_sens_vix_1990": (f("vix_1990"), 0, 12),
              "dolar_sens_u05": (f("dolar_sens_u05"), 1, 24)}
    c = B["crisis"]
    c_sg = c[~c["año"].isin(list(GUERRAS))].reset_index(drop=True)
    cg = E.conglomerados_globales(c["año"].values)
    episodio = {a: i for i, g in cg.iterrows() for a in range(int(g.inicio), int(g.fin) + 1)}
    años_ev = lambda k: pd.DataFrame({"año": sorted({p.year for p in f(k)} - GUERRAS)})   # noqa: E731
    conj_p = {"crisis": (c_sg, False, 5), "crisis_1946_2004": (c_sg[c_sg.año >= 1946].reset_index(drop=True), False, 5),
              "petroleo_global": (años_ev("petroleo"), True, 2), "vol_global": (años_ev("vol"), True, 2),
              "dolar_global": (años_ev("dolar"), True, 2)}
    conj_w = {"crisis_episodios": (pd.DataFrame({"año": sorted(set(cg.inicio.astype(int)) - GUERRAS)}), True, 2),
              "petroleo": (años_ev("petroleo"), True, 2), "vol": (años_ev("vol"), True, 2),
              "dolar": (años_ev("dolar"), True, 2)}
    res["eventos_usados"] = {"mensual": {k: [str(x) for x in v[0]] for k, v in conj_m.items()},
                             "panel": {k: v[0].to_dict("list") for k, v in conj_p.items()},
                             "mundial": {k: v[0]["año"].tolist() for k, v in conj_w.items()}}
    if prueba:
        print(json.dumps({k: len(v[0]) for k, v in conj_m.items()}), {k: len(v[0]) for k, v in conj_p.items()})
        conj_m = {k: conj_m[k] for k in ("petroleo", "vol", "dolar")}
        conj_p = {k: conj_p[k] for k in ("crisis", "petroleo_global", "vol_global", "dolar_global")}
    res["mensual"] = capa_mensual(R, conj_m, reps_desc, reps_ppal)
    res["panel"] = capa_panel(P, conj_p, reps_desc, reps_ppal, episodio)
    res["mundial"] = capa_panel(M, conj_w, reps_desc, reps_ppal, {})
    # contrastes principales + Holm
    preg = {"H1": "crisis bancaria → vivienda real, t+1..t+3 (panel JST)",
            "H2": "crisis bancaria → bolsa real, t+1 (panel JST)",
            "H3": "pico de volatilidad → bolsa EE. UU., 12 m",
            "H4": "shock del petróleo → bolsa real, t+1 (panel JST, años globales)"}
    prin = {}
    for k, (capa, ev_, a, h) in PRINCIPALES.items():
        x = (res["mensual"] if capa == "mensual" else res["panel"])[ev_][a][h]
        prin[k] = {"pregunta": preg[k], "n": x.get("n", x.get("n_pais_evento")), "efecto_pp": x["efecto_pp"],
                   "ic90_pp": x.get("ic90_pp"), "p_placebo": x.get("p_placebo"), "media_abs_pct": x["media_abs_pct"]}
    ph = E.holm({k: v["p_placebo"] for k, v in prin.items()})
    for k, v in prin.items():
        v["p_holm"] = _r(ph[k])
        ic = v["ic90_pp"]
        v["veredicto"] = ("establecido" if ph[k] < 0.05 and ic and (ic[0] > 0 or ic[1] < 0) else "no establecido")
    res["principales"] = prin
    res["tabla_protege"] = tabla_protege(res["mensual"], res["panel"], res["mundial"])
    res["segundos"] = round(time.time() - t0)
    texto = json.dumps(res, indent=1, ensure_ascii=False, default=str)
    md = informe_md(res)
    if prueba:
        print("prueba OK (no se imprimen efectos)", len(texto), len(md), res["segundos"], "s")
        return None
    SALIDA.write_text(texto)
    SALIDA.with_suffix(".md").write_text(md)
    print(json.dumps(prin, ensure_ascii=False), res["segundos"], "s", flush=True)
    return res


if __name__ == "__main__":
    main()
