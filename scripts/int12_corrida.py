"""P-DEV-INT12 v1.0: corrida ÚNICA de desarrollo (docs/int/INT12_prerregistro_v1.md, congelado en cba3c5e).

EE. UU., rendimientos diarios 1926-2004 (AQR/CRSP), evaluación 1950-01 … 2004-11 (1 m) y … 2004-09 (3 m), ventana
creciente desde 1934-02 con embargo y re-estimación cada enero. Confirmatorio: C1 HAR > B1-12m, C2 HAR-X > HAR,
C3 GB > HAR-X (QLIKE, 1 m, DM-NW unilateral, Holm-3, signo en las dos mitades). Lo demás, descriptivo.

Uso: .venv/bin/python -m scripts.int12_corrida              (puerta: árbol limpio; se niega si ya existe la salida)
     .venv/bin/python -m scripts.int12_corrida --sintetico  (datos SINTÉTICOS; comprueba la tubería; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import int12 as M

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int12_resultado.json"
PRERREGISTRO = "docs/int/INT12_prerregistro_v1.md (cba3c5e)"
EVAL_DESDE = pd.Period("1950-01", "M")
ENTRENO_DESDE = pd.Period("1934-02", "M")
MITAD = pd.Period("1977-07", "M")
CONFIRMATORIOS = {"C1": ("b1_12m", "har"), "C2": ("har", "harx"), "C3": ("harx", "gb")}
DESCRIPTIVOS = {"D_ewma_vs_har": ("ewma", "har"), "D_mlp_vs_harx": ("harx", "mlp"), "D_gb_vs_har": ("har", "gb"),
                "D_harx_vs_b1": ("b1_12m", "harx")}
MODELOS = ("b1_12m", "ewma", "har", "harx", "gb", "mlp")


# ---------------------------------------------------------------- datos
def cargar_real() -> dict:
    from src.intl import data as D
    from src.intl import escenarios as E
    from src.intl import panel as P
    con = D.connect()
    try:
        s = {k: D.load_dev(con, k) for k in ("aqr_mkt_usa_d", "BAA", "AAA", "TB3MS", "shiller_gs10")}
        a = P.anual(con)
    finally:
        con.close()
    usa = a.loc["USA"].reset_index()
    usa = usa.rename(columns={usa.columns[0]: "año"}) if "año" not in usa.columns else usa
    usa["pais"] = "USA"
    reg = E.estados_operables(usa[["pais", "año", "inflacion", "rgdpmad"]])
    for v in s.values():
        D.check(v)
    if reg["año"].max() > 2004:
        raise D.FactorCutoffError("régimen con años > 2004")
    return {"r": s["aqr_mkt_usa_d"] / 100, "baa": s["BAA"], "aaa": s["AAA"], "tb3": s["TB3MS"],
            "gs10": s["shiller_gs10"], "reg": M.regimen_anual(reg[reg["pais"] == "USA"])}


def cargar_sintetico(seed: int = 7) -> dict:
    """Proceso de la fase 1 (scripts/int12_potencia.simular_camino) en días hábiles 1926-07 … 2004-12 y rasgos X
    sintéticos (AR(1) mensuales, régimen al azar). Solo para comprobar la tubería."""
    from scripts.int12_potencia import Proceso, simular_camino
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("1926-07-01", "2004-12-31")
    r, _ = simular_camino(len(idx), Proceso(vol_anual=0.15, deriva_diaria=0.0003), rng)
    meses = pd.date_range("1919-01-01", "2004-12-01", freq="MS")

    def ar(m, sd):
        x = np.empty(len(meses))
        x[0] = m
        for t in range(1, len(x)):
            x[t] = m + 0.97 * (x[t - 1] - m) + rng.standard_normal() * sd
        return pd.Series(x, index=meses)
    años = np.arange(1870, 2005)
    reg = pd.DataFrame({"reg_infl": (rng.random(len(años)) < 0.4).astype(float),
                        "reg_brecha": (rng.random(len(años)) < 0.06).astype(float)}, index=años)
    tb3 = ar(4, 0.3).clip(lower=0.05)
    tb3 = tb3[tb3.index >= "1934-01-01"]
    return {"r": pd.Series(r, index=idx), "baa": ar(6, 0.2) + 1, "aaa": ar(6, 0.2), "tb3": tb3,
            "gs10": ar(5, 0.2), "reg": reg}


def tabla(d: dict, h: int) -> pd.DataFrame:
    T = M.tabla_objetivos(d["r"], h)
    F = M.rasgos_diarios(d["r"])
    Xf = M.rasgos_x(T.index, d["baa"], d["aaa"], d["gs10"], d["tb3"], d["reg"])
    T = T.join(F, how="left").join(Xf, how="left")
    if T["fin"].max() > pd.Timestamp("2004-12-31"):
        raise RuntimeError("objetivo más allá de 2004")
    return T


# ---------------------------------------------------------------- evaluación
def colas(P: pd.DataFrame, k: str) -> dict:
    exc = (P.ret <= P[f"var_{k}"]).values
    return {"pinball": float(M.pinball(P[f"var_{k}"], P.ret).mean()),
            "fz0": float(M.fz0(P[f"var_{k}"], P[f"es_{k}"], P.ret).mean()),
            "kupiec": M.kupiec(exc), "brier_caida": float(M.brier(P[f"pc_{k}"], P.caida).mean()),
            "logscore_caida": float(-np.mean(P.caida * np.log(P[f"pc_{k}"] + 1e-12)
                                             + (1 - P.caida) * np.log(1 - P[f"pc_{k}"] + 1e-12)))}


def dm_colas(P: pd.DataFrame, base: str, ret: str, h: int) -> dict:
    lg = M.lags_nw(len(P), h)
    out = {}
    for nom, f in (("pinball", lambda k: M.pinball(P[f"var_{k}"], P.ret)),
                   ("fz0", lambda k: M.fz0(P[f"var_{k}"], P[f"es_{k}"], P.ret)),
                   ("brier_caida", lambda k: M.brier(P[f"pc_{k}"], P.caida))):
        d = np.asarray(f(base) - f(ret), float)
        r = M.dm(d, lg)
        out[nom] = {"t": r["t"], "p": r["p"], "media_d": r["media_d"]}
    return out


def evaluar(d: dict, boot_reps: int) -> dict:
    res = {}
    for h in (1, 3):
        T = tabla(d, h)
        ev = T.index[(T.index >= EVAL_DESDE)]
        P, info = M.ventana_creciente(T, ev, ENTRENO_DESDE, h, MODELOS)
        ult = info.pop("ultimo_ajuste")
        bloque = {"n_eval": len(P), "desde": str(P.index.min()), "hasta": str(P.index.max()), "ajustes": info,
                  "caidas_eval": {"origenes_con_evento": int(P.caida.sum())},
                  "qlike_medio": {k: float(M.qlike(P[f"f_{k}"], P.rv).mean()) for k in MODELOS},
                  "colas": {k: colas(P, k) for k in MODELOS}}
        conf = {c: M.contraste(P, b, r, h, MITAD) for c, (b, r) in CONFIRMATORIOS.items()}
        for c, (b, r) in CONFIRMATORIOS.items():
            conf[c]["colas_dm"] = dm_colas(P, b, r, h)
            if h == 1 and boot_reps:
                conf[c]["p_bootstrap_estacionario"] = M.bootstrap_estacionario_p(
                    np.asarray(M.qlike(P[f"f_{b}"], P.rv) - M.qlike(P[f"f_{r}"], P.rv)), reps=boot_reps)
        bloque["contrastes"] = conf
        bloque["descriptivos"] = {c: M.contraste(P, b, r, h, MITAD) for c, (b, r) in DESCRIPTIVOS.items()}
        if h == 1:
            hz = M.holm({c: conf[c]["p"] for c in CONFIRMATORIOS})
            for c in CONFIRMATORIOS:
                v = conf[c]
                v.update(hz[c])
                estable = v["ganancia_mitad1"] > 0 and v["ganancia_mitad2"] > 0
                v["establecido"] = bool(v["rechaza"] and estable)
                v["veredicto"] = ("establecido" if v["establecido"] else
                                  "no establecido (inestable)" if v["rechaza"] else "no establecido")
            try:
                from sklearn.inspection import permutation_importance
                ent = T[(T.index >= ENTRENO_DESDE) & (T.index < P.index.max()) & T[M.HAR + M.X].notna().all(1)
                        & (T["fin"] <= T.loc[P.index.max(), "origen"])]
                y = np.log(ent["rv"].values / ent["n_dias"].values)
                from threadpoolctl import threadpool_limits
                with threadpool_limits(limits=1):
                    pi = permutation_importance(ult["fit"]["gb"].m, ent[M.HAR + M.X].values, y, n_repeats=10,
                                                random_state=M.SEMILLA)
                bloque["importancia_gb_ultimo_ajuste_(dentro_de_muestra)"] = {
                    c: round(float(v), 4) for c, v in zip(M.HAR + M.X, pi.importances_mean)}
            except Exception as e:                                     # descriptivo: no debe tumbar la corrida
                bloque["importancia_gb_ultimo_ajuste_(dentro_de_muestra)"] = f"error: {e}"
            P["anio"] = [m.year for m in P.index]
            bloque["qlike_por_decada"] = {
                f"{dec}s": {k: round(float(M.qlike(g[f"f_{k}"], g.rv).mean()), 4) for k in ("b1_12m", "har", "harx", "gb")}
                for dec, g in P.groupby((P.anio // 10) * 10)}
        res[f"h{h}"] = bloque
    return res


# ---------------------------------------------------------------- informe
def _pc(x):
    return f"{100 * x:,.1f} %".replace(".", ",")


def markdown(o: dict) -> str:
    h1, h3 = o["h1"], o["h3"]
    lin = [f"""---
documento: Resultado P-DEV-INT12 v1.0 (corrida única de desarrollo del modelo de riesgo de mercado)
prerregistro: {o['prerregistro']}
procedencia: {o['procedencia']}
datos: EE. UU. diario 1926-2004 (AQR/CRSP), evaluación {h1['desde']} … {h1['hasta']} (1 m). NADA ≥ 2005
---

# INT-12: resultado de la corrida de desarrollo

## Contrastes confirmatorios (QLIKE, 1 mes, N = {h1['n_eval']}; Holm-3; signo en las dos mitades)
| contraste | ganancia QLIKE | 1950-77 | 1977-2004 | t (NW, {h1['contrastes']['C1']['lags']} retardos) | p | p Holm | p bootstrap | veredicto |
|---|---|---|---|---|---|---|---|---|"""]
    nombres = {"C1": "C1 HAR frente a σ̂ 12 m (B1)", "C2": "C2 HAR-X frente a HAR", "C3": "C3 GB frente a HAR-X"}
    for c, v in h1["contrastes"].items():
        lin.append(f"| {nombres[c]} | {_pc(v['ganancia'])} | {_pc(v['ganancia_mitad1'])} | {_pc(v['ganancia_mitad2'])} | "
                   f"{v['t']:.2f} | {v['p']:.4f} | {v['p_holm']:.4f} | {v.get('p_bootstrap_estacionario', float('nan')):.4f} | "
                   f"**{v['veredicto']}** |")
    lin += ["", "## QLIKE medio por modelo (menos es mejor)", "| modelo | 1 m | 3 m |", "|---|---|---|"]
    for k in MODELOS:
        lin.append(f"| {k} | {h1['qlike_medio'][k]:.4f} | {h3['qlike_medio'][k]:.4f} |")
    lin += ["", "## Descriptivos a 3 meses (mismos contrastes, no deciden)", "| contraste | ganancia | t | p |", "|---|---|---|---|"]
    for c, v in h3["contrastes"].items():
        lin.append(f"| {nombres[c]} | {_pc(v['ganancia'])} | {v['t']:.2f} | {v['p']:.4f} |")
    for c, v in {**h1["descriptivos"]}.items():
        lin.append(f"| {c} (1 m) | {_pc(v['ganancia'])} | {v['t']:.2f} | {v['p']:.4f} |")
    lin += ["", "## Colas (descriptivo): VaR 5 % (Kupiec), FZ0, P(caída ≥ 10 % en 3 m)",
            "| modelo | excedencias VaR 1 m (tasa, p Kupiec) | FZ0 1 m | excedencias VaR 3 m | Brier caída 3 m |", "|---|---|---|---|---|"]
    for k in MODELOS:
        c1, c3 = h1["colas"][k], h3["colas"][k]
        lin.append(f"| {k} | {c1['kupiec']['excedencias']} ({_pc(c1['kupiec']['tasa'])}, {c1['kupiec']['p']:.3f}) | "
                   f"{c1['fz0']:.4f} | {c3['kupiec']['excedencias']} ({_pc(c3['kupiec']['tasa'])}) | {c3['brier_caida']:.4f} |")
    lin += ["", f"Orígenes con caída ≥ 10 % en 3 m en la evaluación: {h3['caidas_eval']['origenes_con_evento']}.",
            "", "## QLIKE por década (1 m)", "| década | B1-12m | HAR | HAR-X | GB |", "|---|---|---|---|---|"]
    for dec, v in h1["qlike_por_decada"].items():
        lin.append(f"| {dec} | {v['b1_12m']:.3f} | {v['har']:.3f} | {v['harx']:.3f} | {v['gb']:.3f} |")
    lin += ["", f"Importancia por permutación de GB (último ajuste, dentro de muestra, descriptiva): "
            f"{h1.get('importancia_gb_ultimo_ajuste_(dentro_de_muestra)')}",
            f"Coeficientes HAR-X del último ajuste (constante, {', '.join(M.HAR + M.X)}): "
            f"{[round(x, 4) for x in h1['ajustes']['coef_harx_ultimo']]}", ""]
    return "\n".join(lin)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    sint = "--sintetico" in argv
    t0 = time.time()
    if sint:
        d, proc = cargar_sintetico(), {"sintetico": True}
    else:
        if SALIDA.exists():
            raise SystemExit(f"{SALIDA} ya existe: P-DEV-INT12 es de corrida ÚNICA; no se repite")
        from src.intl.procedencia import procedencia
        proc = procedencia()
        d = cargar_real()
    res = evaluar(d, boot_reps=200 if sint else 2000)
    import sklearn
    o = {"procedencia": proc, "prerregistro": PRERREGISTRO, "semilla": M.SEMILLA, "sklearn": sklearn.__version__,
         "gb_params": M.GB_PARAMS, "mlp_params": M.MLP_PARAMS, **res, "segundos": round(time.time() - t0)}
    txt = markdown(o)
    if sint:
        print(txt)
        return o
    SALIDA.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=str))
    SALIDA.with_suffix(".md").write_text(txt)
    print(txt)
    return o


if __name__ == "__main__":
    main()
