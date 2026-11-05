"""INT-11 v3.1 "hoy" (DESCRIPTIVO; docs/int/INT11_prerregistro_v3.md §8 + docs/int/INT11_v3_1_imputacion.md).

v3.1 = v3 con la imputación condicionada (PMM) de los activos sin dato (cambio de ingeniería declarado; `--v3` emite
con la imputación independiente de v3, solo para comparar). Motor Config.v3_1 estimado con TODAS las filas ≤ 2004; estado actual con ventanas MÓVILES de 12 meses (OCDE en vivo, PIB
per cápita con población Maddison) y PERTENENCIA SUAVE al régimen (σ 0,5 pp en la inflación, 1 pp en la brecha); abanico
de los 12 meses que siguen a la emisión. Cada abanico lleva el ACIERTO MEDIDO en la fase D de v3 (cobertura LOCO ≤ 2004
del país, del activo y del régimen de partida dominante), no el nominal. Aviso del umbral con TODOS los países a < 0,5 pp
del 3 % (o a < 1 pp de brecha 0). Publica además la DEPENDENCIA POR RÉGIMEN (decisión V3 de
docs/int/INT11_v4_correlaciones_v0.md §6): correlaciones bolsa-bonos y bonos-oro de los escenarios (hoy y partiendo de
cada régimen) y la descriptiva ≤ 2004 por régimen (research/int/int11_v4_potencia.json), marcadas "≤ 2004, no
confirmado". El registro en vivo NO se activa aquí (falta fijar la fuente de bolsa); cuando se active, la v3.1 es una
SERIE NUEVA (`SERIE_VIVO`, carpeta propia), que no se mezcla con ninguna emisión de v3.

Uso: .venv/bin/python -m scripts.int11_v3_hoy [AAAA-MM-DD] [--v3]   → research/int/int11_v3_hoy.{json,md}
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.int11_corrida import NUCLEO
from scripts.int11_v3_corrida import cargar_real_v3
from src.intl import data as D
from src.intl import escenarios as E
from src.intl.procedencia import procedencia
from src.report import escenarios_vivo as V
from src.report import registro_vivo as RV

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_v3_hoy.json"
RESULTADO = REPO / "research/int/int11_v3_resultado.json"
INFORMATIVA_V3_1 = REPO / "research/int/int11_v3_1_imputacion.json"      # fase D recalculada con v3.1 (informativa)
DESCRIPTIVA = REPO / "research/int/int11_v4_potencia.json"               # dependencia por régimen ≤ 2004
SERIE_VIVO = "int11_v3_1"                                                # serie del registro en vivo (no mezclar)
VIVO_V3_1 = REPO / "research/int/int11_v3_1_vivo"
MOTORES = {"v3.1": "v3_1", "v3": "v3"}
PARES_DEP = (("bolsa", "bonos"), ("bonos", "oro"))
SEED = 20261105
REJILLA_Q = tuple(range(1, 100))
CERCA_INFL, CERCA_BRECHA = 0.005, 0.01


def _p(x):
    return f"{100 * x:.0f} %"


POR_LOTE = 1000  # Validador 31-oct: con 100/lote el IC de parámetros de "hoy" no es estimable


def acierto_medido(res: dict) -> dict:
    return {"activo": dict(zip(E.ACTIVOS, res["loco"]["S_activo"])), "regimen": res["cobertura_por_regimen_loco"],
            "pais": res["cobertura_por_pais_loco"], "global": res["loco"]["S5"], "puerta_D": res["puerta_D"]["pasa"],
            "cerca_umbral": res["loco"]["S5_cerca"]}


def dependencia(activos, R: np.ndarray) -> dict:
    """Correlación (log 1 + r) de los pares PARES_DEP en los sorteos R (P, A)."""
    acts = list(activos)
    L = np.log1p(R)
    out = {}
    for a, b in PARES_DEP:
        x, y = L[:, acts.index(a)], L[:, acts.index(b)]
        ok = np.isfinite(x) & np.isfinite(y)
        out[f"{a}-{b}"] = round(float(np.corrcoef(x[ok], y[ok])[0, 1]), 3) if ok.sum() >= 5 else None
    return out


def dependencia_por_regimen(gen: E.Generador, c: str, semilla: int) -> dict:
    """Escenarios a 1 año partiendo (régimen duro) de expansión y de sobrecalentamiento: 100 × 100 sorteos."""
    return {E.REGIMENES[s0]: dependencia(gen.cfg.activos, gen.simular(c, s0, horizonte=1, n_lotes=100, por_lote=100,
                                                                      semilla=semilla + 100 + s0).rent[:, 0, :])
            for s0 in (0, 1)}


def descriptiva_regimen() -> dict | None:
    """Tabla ≤ 2004 (núcleo 14; choques sin la media del país en el estado; IC 90 % bootstrap de años) por inflación
    conocida al empezar el año (P3 previa, la que el motor usa como partida)."""
    if not DESCRIPTIVA.exists():
        return None
    d = json.loads(DESCRIPTIVA.read_text())
    a = d["A_anual"]["nucleo14"]
    out = {"fuente": f"research/int/int11_v4_potencia.json (commit {d['procedencia'].get('commit', '?')[:7]})"}
    for p in ("bolsa-bonos", "bonos-oro"):
        v = a[p]["p3_infl_alta_prev"]
        out[p] = {"años": v["años"], "baja": {"rho": v["rho"]["0"], "ic90": v["ic90"]["0"], "n": v["n"]["0"]},
                  "alta": {"rho": v["rho"]["1"], "ic90": v["ic90"]["1"], "n": v["n"]["1"]},
                  "dif": v["dif_1_menos_0"], "dif_ic90": v["dif_ic90"], "paises_mismo_signo": v["paises_mismo_signo"]}
    return out


def pais_escenario(gen: E.Generador, c: str, e: dict, semilla: int) -> dict:
    w = E.pesos_estado(e["inflacion"], e["brecha"], gen.cfg.sigma_infl, gen.cfg.sigma_brecha)
    esc = gen.simular_suave(c, e["inflacion"], e["brecha"], horizonte=1, n_lotes=200, por_lote=POR_LOTE, semilla=semilla)
    R = esc.rent[:, 0, :]
    duro = gen.simular(c, e["codigo"], horizonte=1, n_lotes=200, por_lote=POR_LOTE, semilla=semilla)
    return {"dependencia_hoy": dependencia(esc.activos, R),
            "dependencia_por_regimen": dependencia_por_regimen(gen, c, semilla),
            "pesos_regimen": dict(zip(E.REGIMENES, np.round(w, 4).tolist())),
            "regimen_dominante": E.REGIMENES[int(np.argmax(w))],
            "cuantiles_1_99": {a: np.nanpercentile(R[:, j], REJILLA_Q).round(5).tolist() for j, a in enumerate(esc.activos)},
            "p_caida_bolsa_20": esc.prob_caida("bolsa", -0.20, h=1), "p_inflacion_5": esc.prob_inflacion(0.05, h=1),
            "p_inflacion_5_regimen_duro": duro.prob_inflacion(0.05, h=1)["p"],
            "factor_dispersion": gen.escala_resumen["factor_pais"].get(c),
            "distancia_umbral_pp": round(100 * (e["inflacion"] - E.UMBRAL_INFL), 2),
            "cerca_umbral": bool(abs(e["inflacion"] - E.UMBRAL_INFL) < CERCA_INFL or abs(e["brecha"]) < CERCA_BRECHA)}


def emitir(fecha: str, exigir_limpio: bool = True, motor: str = "v3.1", registro: bool = False) -> dict:
    """`exigir_limpio=False` solo para el reporte semanal (descriptivo; la procedencia anota si el árbol estaba limpio).
    `motor`: "v3.1" (por defecto) o "v3" (imputación independiente; solo para comparar)."""
    if registro:   # registro en vivo (D8/D9 aprobados 5-nov-2026): solo v3.1, fecha = hoy ± 3 días, árbol limpio
        if motor != "v3.1":
            raise SystemExit("el registro en vivo es solo de la serie v3.1")
        RV.comprobar_fecha(fecha)
        proc = RV.procedencia_registro(VIVO_V3_1)
    else:
        proc = procedencia(exigir_limpio)
    if motor not in MOTORES:
        raise ValueError(motor)
    if not RESULTADO.exists():
        raise SystemExit("falta research/int/int11_v3_resultado.json (fase D): la salida v3 se etiqueta con su acierto")
    ac = acierto_medido(json.loads(RESULTADO.read_text()))
    if motor == "v3.1" and INFORMATIVA_V3_1.exists():
        inf = json.loads(INFORMATIVA_V3_1.read_text()).get("C_fase_D_informativa", {}).get("v3_1")
        if inf:
            ac["informativa_v3_1"] = {"global": inf["loco"]["S5"], "activo": dict(zip(E.ACTIVOS, inf["loco"]["S_activo"])),
                                      "cerca_umbral": inf["loco"]["S5_cerca"]}
    con = D.connect()
    filas = cargar_real_v3(con)
    if filas["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    gen = E.Generador(getattr(E.Config, MOTORES[motor])()).ajustar(filas)
    est = V.estado_actual_movil(con, fecha, entradas=registro)
    entradas = RV.huella_entradas(est.pop("_series")) if registro else None
    paises = {}
    for i, c in enumerate(NUCLEO):
        e = est["paises"][c]
        if e.get("regimen") is None:
            paises[c] = {"estado": e, "aviso": "sin datos suficientes"}
            continue
        paises[c] = {"estado": e, **pais_escenario(gen, c, e, SEED + i)}
    return {"procedencia": proc, "version_motor": E.VERSION, "motor": motor,
            "serie_registro": SERIE_VIVO if motor == "v3.1" else "int11_v3",
            **({"entradas": entradas, "fuente_bolsa_evaluacion": "docs/int/INT11_fuente_bolsa_vivo.md (A1-A7 aprobadas)"}
               if registro else {}),
            "dependencia_descriptiva_2004": descriptiva_regimen(), "config": str(gen.cfg), "emision": est["emision"],
            "corte_datos": est["corte"], "ventana_objetivo": est["ventana_objetivo"], "kappa": gen.kappa,
            "kappa_en_borde": gen.kappa_en_borde, "acierto_medido_fase_D": ac, "paises": paises,
            "aviso": f"DESCRIPTIVO. Motor {motor} estimado SOLO con ≤ 2004 (JST, 14 países); estado OCDE en vivo (12 meses móviles,"
                     " PIB per cápita con población Maddison extrapolada) con pertenencia suave al régimen. Calibración "
                     "comprobada solo en desarrollo (contaminado); NO confirmada fuera de muestra. Rentabilidades reales en "
                     "moneda local. No es una recomendación."}


def _ic(d: dict) -> str:
    if not d.get("ic_estimable", True):
        return "[IC no estimable]"
    return f"[{_p(max(d['ic90'][0], 0))}-{_p(min(d['ic90'][1], 1))}]"


def _q(r: dict, a: str, p: int) -> float:
    return r["cuantiles_1_99"][a][p - 1]


def _r(x) -> str:
    return "—" if x is None else f"{x:+.2f}".replace(".", ",")


def md_dependencia(o: dict) -> str:
    """Dependencia por régimen (decisión V3): escenarios del motor y descriptiva ≤ 2004. Vacío si no hay datos."""
    paises = {c: r for c, r in o.get("paises", {}).items() if "dependencia_hoy" in r}
    if not paises:
        return ""
    lin = []
    for c, r in paises.items():
        h, pr = r["dependencia_hoy"], r["dependencia_por_regimen"]
        ex, so = pr["expansion"], pr["sobrecalentamiento"]
        lin.append(f"| {c} | {_r(h['bolsa-bonos'])} / {_r(h['bonos-oro'])} | {_r(ex['bolsa-bonos'])} / "
                   f"{_r(ex['bonos-oro'])} | {_r(so['bolsa-bonos'])} / {_r(so['bonos-oro'])} |")
    d = o.get("dependencia_descriptiva_2004")
    desc = ""
    if d:
        def _f(p):
            x = d[p]
            ic = lambda e: f"[{_r(x[e]['ic90'][0])}; {_r(x[e]['ic90'][1])}]"  # noqa: E731
            return (f"{p} ({x['años'][0]}-{x['años'][1]}): inflación previa ≤ 3 % {_r(x['baja']['rho'])} {ic('baja')} "
                    f"(n {x['baja']['n']}), > 3 % {_r(x['alta']['rho'])} {ic('alta')} (n {x['alta']['n']}); "
                    f"diferencia {_r(x['dif'])} [{_r(x['dif_ic90'][0])}; {_r(x['dif_ic90'][1])}], "
                    f"{x['paises_mismo_signo']} países con el mismo signo")
        desc = (f"\n\n**Descriptiva ≤ 2004** (14 países, choques sin la media del país en cada estado, IC 90 % por "
                f"bootstrap de años; {d['fuente']}): {_f('bolsa-bonos')}. {_f('bonos-oro')}.")
    return f"""

### Dependencia entre activos por régimen (≤ 2004, no confirmado)

Correlación (log) de los escenarios a 12 meses, bolsa-bonos / bonos-oro: hoy (con los pesos de régimen de cada país) y
partiendo de cada régimen. Con inflación alta (sobrecalentamiento) bolsa y bonos se mueven más juntos y el oro se mueve
más contra los bonos. Es la dependencia que el motor hereda de las filas históricas ≤ 2004; **no está confirmada fuera
de muestra** y no se ha contrastado (la potencia no da: docs/int/INT11_v4_correlaciones_v0.md). La correlación
negativa bolsa-bonos de los últimos años (época, no régimen) no la reproduce el motor. La de "hoy" mezcla regímenes
con medias distintas y puede quedar algo por encima de las dos columnas de partida.

| país | hoy | partiendo de expansión | partiendo de sobrecalentamiento |
|---|---|---|---|
{chr(10).join(lin)}{desc}"""


def markdown(o: dict) -> str:
    ac = o["acierto_medido_fase_D"]
    motor = o.get("motor", "v3")
    v = o["ventana_objetivo"]
    filas, cerca = [], []
    for c, r in o["paises"].items():
        if "cuantiles_1_99" not in r:
            filas.append(f"| {c} | — | — | — | — | — | — |")
            continue
        e = r["estado"]
        dom = r["regimen_dominante"]
        acb = ac["regimen"].get(dom, {}).get("bolsa")
        pc, pi = r["p_caida_bolsa_20"], r["p_inflacion_5"]
        pesos = ", ".join(f"{k[:5]} {_p(x)}" for k, x in r["pesos_regimen"].items() if x >= 0.005)
        filas.append(
            f"| {c} | {pesos} (IPC a {e['mes_ipc'][:7]}: {100 * e['inflacion']:.2f} %; brecha pc {100 * e['brecha']:+.1f} %) | "
            f"{_p(_q(r, 'bolsa', 5))} … {_p(_q(r, 'bolsa', 50))} … {_p(_q(r, 'bolsa', 95))} "
            f"(acertó {_p(ac['pais'][c]['bolsa'])} país / {_p(acb) if acb is not None else '—'} régimen) | "
            f"{_p(_q(r, 'bonos', 5))} … {_p(_q(r, 'bonos', 95))} | {_p(_q(r, 'vivienda', 5))} … {_p(_q(r, 'vivienda', 95))} | "
            f"{_p(pc['p'])} {_ic(pc)} | {_p(pi['p'])} {_ic(pi)} |")
        if r["cerca_umbral"]:
            cerca.append(f"{c} (inflación {r['distancia_umbral_pp']:+.2f} pp del 3 %, brecha {100 * e['brecha']:+.1f} %: "
                         f"P(inflación > 5 %) {_p(pi['p'])} suave frente a {_p(r['p_inflacion_5_regimen_duro'])} con la "
                         f"regla dura)")
    act = ", ".join(f"{a} {_p(x)}" for a, x in ac["activo"].items())
    aviso_umbral = ("; ".join(cerca) if cerca else "ninguno")
    inf = ac.get("informativa_v3_1")
    inf_txt = (f" Recalculada con v3.1 (informativo, no es una puerta nueva): {100 * inf['global']:.1f} %." if inf else "")
    nota_v3_1 = ("""
**v3.1** = v3 con un único cambio de ingeniería declarado: cuando la fila histórica sorteada no tiene un activo (oro
antes de 1972, vivienda en ≈ 17 % de las filas), el dato se toma de una fila de la misma celda PARECIDA en el resto de
variables (emparejamiento por la media predicha), no de una al azar; así no se diluye la dependencia entre activos
(docs/int/INT11_v3_1_imputacion.md). Serie nueva del registro en vivo; no se mezcla con v3.
""" if motor == "v3.1" else "")
    return f"""---
documento: INT-11 {motor} "hoy" — abanicos de los próximos 12 meses por país (DESCRIPTIVO)
procedencia: {o['procedencia']}
emision: {o['emision']} (datos en vivo hasta {o['corte_datos']})
ventana: {v['desde']} → {v['hasta']}
aviso: {o['aviso']}
---

# Escenarios para {v['desde'][:7]} … {v['hasta'][:7]} (motor {motor} estimado con ≤ 2004)
{nota_v3_1}
**Cuánto acertaron estos abanicos en el pasado** (fase D de v3, cada país predicho sin sus propios datos, 1876-2004):
el abanico "del 90 %" contuvo lo realizado el **{100 * ac['global']:.1f} %** de las veces ({act}); cerca del umbral del
3 %, el {100 * ac['cerca_umbral']:.1f} %. Puerta de desarrollo: {'pasó' if ac['puerta_D'] else 'NO pasó'}.{inf_txt} Fuera de
muestra todavía **no está comprobado** (confirmación futura K1).

**Aviso del umbral (frontera del 3 % y brecha 0).** Países a menos de 0,5 pp del 3 % de inflación o a menos de 1 pp de
brecha 0: {aviso_umbral}. En v3 su abanico es una MEZCLA de los regímenes vecinos (pesos en la columna "estado"), en
lugar de saltar de uno a otro por décimas: por eso su P(inflación > 5 %) queda entre los dos extremos. Aun así, un dato
nuevo de IPC puede mover bastante esas cifras.

| país | estado: pesos de régimen (12 meses móviles) | bolsa real: p5 … p50 … p95 (acierto medido del p5-p95) | bonos p5 … p95 | vivienda p5 … p95 | P(bolsa ≤ −20 %) [IC 90 % parámetros] | P(inflación > 5 %) [IC] |
|---|---|---|---|---|---|---|
{chr(10).join(filas)}

Cómo leerlo: "p5 … p95" es el abanico nominal del 90 % de la rentabilidad real de los 12 meses de la ventana; entre
paréntesis, con qué frecuencia un abanico así contuvo lo realizado en el pasado para ese país y para su régimen de
partida dominante (si es < 90 %, el abanico es más estrecho de lo que dice). El IC entre corchetes es solo la duda
sobre los parámetros. κ = {o['kappa']:.3g} (en el borde: {o['kappa_en_borde']}). Letras, oro y la rejilla completa de
percentiles en research/int/int11_v3_hoy.json.{md_dependencia(o)}
"""


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fecha = args[0] if args else str(pd.Timestamp.today().date())
    if "--registro" in sys.argv:     # SOLO research/int/int11_v3_1_vivo/AAAA-MM.json (no reescribe la salida "hoy")
        o = emitir(fecha, registro=True)
        print("registro:", RV.registrar(o, VIVO_V3_1))
        return
    o = emitir(fecha, motor="v3" if "--v3" in sys.argv else "v3.1")
    md = markdown(o)
    SALIDA.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
    SALIDA.with_suffix(".md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
