"""Corrida ÚNICA de P-DEV-INT3d v1.0 (docs/int/INT3d_prerregistro_v0.md, aprobado y congelado en fa6d4c9).
Familia {C1, C3} (Holm-2); C2, C4-C8 descriptivos; todos los eventos en el principal; sin guerras y año ancla más
influyente como criterio 4 (§6) y como sensibilidad; 1950-2004 informativo; EE. UU. mensual con anuncios NBER (principal)
y regla de 9 meses (sensibilidad), sin potencia. Exige el árbol limpio (procedencia).
Salida: research/int/int3d_resultado.json y .md, y una línea en research/trial_log.md.
Uso: .venv/bin/python -m scripts.int3d_corrida
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import int3d_potencia as S
from src.intl import data as D
from src.intl import int3 as I3
from src.intl import int3d as M
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
NUC = S.NUCLEO
PRUEBA_RET = ["AUS", "CHE"]
FAMILIA = ["C1_espera_salida", "C3_bonos_recesion"]
GRUPO = {"C2_fin_bolsa", "C6_fin_vivienda"}
INFL_ALTA = S.INFL_ALTA
ACTIVOS = ["eq", "bond", "bill", "viv"]


def _r(v, k=4):
    if isinstance(v, dict):
        return {a: _r(b, k) for a, b in v.items()}
    if isinstance(v, (list, tuple)):
        return [_r(b, k) for b in v]
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else round(float(v), k)
    if isinstance(v, np.integer):
        return int(v)
    return v


def base_eventos(nombre, rec_ev, ei_ev):
    return ei_ev if nombre == "C5_espera_inflac" else rec_ev


def main() -> None:
    proc = procedencia()
    con = D.connect()
    anual = P.anual(con)
    usrec = D.load_dev(con, "USREC")
    con.close()
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    mens = pd.read_parquet(db.DATA_ROOT / "intl" / "panel_mensual_dev.parquet").loc["USA"]

    x = M.panel_log(anual, NUC)
    wq = M.cuantiles_winsor(x)
    xw = M.panel_log(anual, NUC, winsor=wq)
    xh = M.panel_log(anual, NUC, sin_hiper=True)
    rec_ev = M.dic_rec(M.eventos_rec(rec, NUC))
    ei_ev = M.dic_t(M.eventos_transicion(et, NUC, INFL_ALTA))
    ei_nf = M.dic_t(M.eventos_transicion(et, NUC, INFL_ALTA, sin_frontera=True))
    res = {"procedencia": proc, "prerregistro": "docs/int/INT3d_prerregistro_v0.md (v1.0, fa6d4c9)",
           "eventos": {"recesiones": int(len(rec_ev["ci"])), "financieras": int(rec_ev["fin"].sum()),
                       "entradas_inflacion_alta": int(len(ei_ev["ci"]))},
           "winsor_q01_q99": wq, "contrastes": {}, "descriptivos": {}}

    # ------------------------------------------------ contrastes candidatos (familia y descriptivos)
    ps = {}
    for nombre, c in S.CANDIDATOS.items():
        g = nombre in GRUPO
        vf = M.valfun_nombre(nombre)
        ev = base_eventos(nombre, rec_ev, ei_ev)
        evp = M.submuestra(nombre, ev, "principal")
        r = {"signo_esperado": c["signo"], "serie": c["serie"], "principal": M.evaluar(vf, x[c["serie"]], evp, g)}
        r["sin_guerras"] = M.evaluar(vf, x[c["serie"]], M.submuestra(nombre, ev, "sin_guerras"), g)
        r["1950_2004"] = M.evaluar(vf, x[c["serie"]], M.submuestra(nombre, ev, "1950_2004"), g)
        r["por_evento"] = M.evaluar(vf, x[c["serie"]], evp, g, por_año=False)
        if nombre in FAMILIA:
            r["sin_año_influyente"] = M.sin_año_influyente(vf, x[c["serie"]], evp, g)
            r["winsor"] = M.evaluar(vf, xw[c["serie"]], evp, g)
            r["sin_hiperinflacion"] = M.evaluar(vf, xh[c["serie"]], evp, g)
            r["por_pais"] = M.por_pais(vf, x[c["serie"]], evp, NUC, g)
            ps[nombre] = r["principal"]["p"]
        if nombre in GRUPO:
            r["permutacion_etiqueta"] = M.permutacion_etiqueta(vf, x[c["serie"]], evp)
        if nombre == "C5_espera_inflac":
            r["sin_frontera"] = M.evaluar(vf, x[c["serie"]], ei_nf, g)
            r["inflacion_abs_3"] = "no calculado: el parquet de INT-1 solo tiene la etiqueta principal (declarado)"
        res["contrastes"][nombre] = r
        print(nombre, {k: round(r["principal"][k], 4) for k in ("efecto", "p", "p_rangos")}, flush=True)

    # C1: confirmación a 12 y 24 meses (sensibilidad)
    evc1 = M.submuestra("C1_espera_salida", rec_ev, "principal")
    for nom, offs in (("confirmacion_12m", [(1, 1.0)]), ("confirmacion_24m", [(1, 1.0), (2, 1.0)])):
        res["contrastes"]["C1_espera_salida"][nom] = M.evaluar(M.vf_ventana("V", offs), x["eq_x"], evc1)

    holm = I3.holm(ps)
    veredicto = {}
    for nombre in FAMILIA:
        r = res["contrastes"][nombre]
        s = S.CANDIDATOS[nombre]["signo"]
        crit = {"1_signo": bool(np.sign(r["principal"]["efecto"]) == s), "2_holm": bool(holm[nombre]),
                "3_rangos": bool(r["principal"]["p_rangos"] <= 0.05),
                "4_sin_guerras": bool(np.sign(r["sin_guerras"]["efecto"]) == s),
                "4_sin_año_influyente": bool(np.sign(r["sin_año_influyente"]["efecto"]) == s)}
        info = {"5_signo_1950_2004": bool(np.sign(r["1950_2004"]["efecto"]) == s),
                "paises_con_el_signo": f"{sum(np.sign(v['efecto']) == s for v in r['por_pais'].values())}/{len(r['por_pais'])}"}
        veredicto[nombre] = {"criterios": crit, "informativo": info, "establecido": all(crit.values())}
    res["holm"] = holm
    res["veredicto"] = veredicto

    # países de prueba: solo signos de la familia
    xp = M.panel_log(anual, PRUEBA_RET)
    rec_p = M.dic_rec(M.eventos_rec(rec, PRUEBA_RET))
    res["paises_prueba"] = {}
    for nombre in FAMILIA:
        serie = S.CANDIDATOS[nombre]["serie"]
        evp = M.submuestra(nombre, rec_p, "principal")
        r = M.evaluar(M.valfun_nombre(nombre), xp[serie], evp)
        pp = M.por_pais(M.valfun_nombre(nombre), xp[serie], evp, PRUEBA_RET)
        res["paises_prueba"][nombre] = {"conjunto": r["efecto"], "eventos": r["eventos"],
                                        "por_pais": {k: v["efecto"] for k, v in pp.items()}}

    # ------------------------------------------------ descriptivos
    des = res["descriptivos"]
    grupos = {"todas": rec_ev, "normales": M.filtrar(rec_ev, rec_ev["fin"] == 0),
              "financieras": M.filtrar(rec_ev, rec_ev["fin"] == 1)}
    des["trayectorias_pico"] = {gn: {a: M.trayectoria(x[a], ev, "P", range(-3, 6), (-3, 5)) for a in ACTIVOS}
                                for gn, ev in grupos.items()}
    des["trayectorias_valle"] = {gn: {a: M.trayectoria(x[a], ev, "V", range(-3, 4), (-3, 3)) for a in ACTIVOS}
                                 for gn, ev in grupos.items()}
    des["fondo_respecto_al_valle"] = {gn: {a: M.distribucion_fondo(x[a], M.submuestra("C7_fondo_bolsa", ev, "principal"))
                                           for a in ACTIVOS} for gn, ev in grupos.items()}
    esp = {"entrada": ("P", [(1, 1.0), (2, 4 / 12)], [(2, 8 / 12), (3, 1.0)]),
           "salida": ("V", [(1, 1.0), (2, 4 / 12)], [(2, 8 / 12), (3, 1.0)])}
    des["espera_recesion"] = {}
    for fase, (anc, o_esp, o_queda) in esp.items():
        for gn, ev in grupos.items():
            for a in ("eq_x", "bond_x", "viv"):
                des["espera_recesion"][f"{fase}|{gn}|{a}"] = {
                    "espera": M.evaluar(M.vf_ventana(anc, o_esp), x[a], ev),
                    "queda_hasta_fin_3er_año": M.evaluar(M.vf_ventana(anc, o_queda), x[a], ev)}
    trans = {"entrada_inflacion_alta": INFL_ALTA, "entrada_estanflacion": {"estanflacion"},
             "salida_inflacion_alta": {"expansion", "crecimiento_bajo"}, "entrada_crecimiento_bajo": {"crecimiento_bajo"}}
    des["cambios_cuadrante"] = {}
    for tn, dest in trans.items():
        ev = M.dic_t(M.eventos_transicion(et, NUC, dest))
        d = {"eventos": int(len(ev["ci"])),
             "trayectorias": {a: M.trayectoria(x[a], ev, "t", range(-2, 4), (-2, 3)) for a in ACTIVOS}}
        for a in ("eq_x", "bond_x", "viv"):
            d[f"espera|{a}"] = M.evaluar(M.vf_ventana("t", [(0, 1.0), (1, 4 / 12)]), x[a], ev)
            d[f"queda|{a}"] = M.evaluar(M.vf_ventana("t", [(1, 8 / 12), (2, 1.0)]), x[a], ev)
        des["cambios_cuadrante"][tn] = d

    # ------------------------------------------------ EE. UU. mensual (secundario, sin potencia)
    u = M.eeuu_series(mens)
    s = usrec.copy()
    s.index = pd.to_datetime(s.index).to_period("M")
    picos = [p - 1 for p in s.index[(s.diff() == 1).to_numpy()]]
    valles = [p - 1 for p in s.index[(s.diff() == -1).to_numpy()]]
    us = {"picos": [], "valles": []}
    for tipo, lista in (("picos", picos), ("valles", valles)):
        for g in lista:
            an = M.ANUNCIOS_NBER.get(str(g))
            r = M.eeuu_evento(u, g, pd.Period(an, "M") if an else None)
            if r is not None:
                r["anuncio_nber"] = an
                us[tipo].append(r)
    res["eeuu_mensual"] = us

    res["hora_fin_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    out = REPO / "research" / "int"
    (out / "int3d_resultado.json").write_text(json.dumps(_r(res), indent=1, ensure_ascii=False))
    (out / "int3d_resultado.md").write_text(informe(_r(res)))
    linea = (f"| {dt.date.today().isoformat()} | Constructor (P-DEV-INT3d v1.0, corrida única) | commit {proc['commit'][:7]}; "
             f"núcleo 14 países 1870-2004, {res['eventos']['recesiones']} recesiones; familia {{C1, C3}} (Holm-2); "
             f"establecidos {json.dumps({k: v['establecido'] for k, v in veredicto.items()})}; C2, C4-C8 descriptivos; "
             f"EE. UU. mensual informativo; research/int/int3d_resultado.json |\n")
    with open(REPO / "research" / "trial_log.md", "a") as f:
        f.write(linea)
    print(json.dumps(_r(veredicto), indent=1, ensure_ascii=False))


def _pp(v, k=1):
    return "–" if v is None else f"{100 * v:+.{k}f}"


def informe(r: dict) -> str:
    p = r["procedencia"]
    L = ["# INT-3d: resultado de la corrida única", "",
         f"Procedencia: commit `{p['commit'][:7]}`, árbol limpio {p['arbol_limpio']}, {p['hora_utc']}. Prerregistro v1.0 "
         f"(fa6d4c9). Núcleo 14 países, 1870-2004, {r['eventos']['recesiones']} recesiones ({r['eventos']['financieras']} "
         f"financieras), {r['eventos']['entradas_inflacion_alta']} entradas en inflación alta. Log real; efecto = valor en "
         "las fechas reales − media de 124 placebos desplazados (pp, o años en C7/C8).", "",
         "## Familia (Holm-2)", "",
         "| id | efecto | IC 95 % | p (z placebo) | p rangos | Holm | sin guerras | sin año influyente | 1950-2004 | países | ESTABLECIDO |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in FAMILIA:
        c = r["contrastes"][n]
        pr, v = c["principal"], r["veredicto"][n]
        L.append(f"| {n} | {_pp(pr['efecto'])} | [{_pp(pr['ic95'][0])}; {_pp(pr['ic95'][1])}] | {pr['p']:.4f} | "
                 f"{pr['p_rangos']:.3f} | {'sí' if r['holm'][n] else 'no'} | {_pp(c['sin_guerras']['efecto'])} | "
                 f"{_pp(c['sin_año_influyente']['efecto'])} (sin {c['sin_año_influyente']['año']}) | "
                 f"{_pp(c['1950_2004']['efecto'])} | {v['informativo']['paises_con_el_signo']} | "
                 f"**{'sí' if v['establecido'] else 'no'}** |")
    L += ["", "Bruto (sin restar el placebo) y sensibilidades de la familia:", ""]
    for n in FAMILIA:
        c = r["contrastes"][n]
        extra = "".join(f"; {k} {_pp(c[k]['efecto'])}" for k in ("por_evento", "winsor", "sin_hiperinflacion",
                                                                 "confirmacion_12m", "confirmacion_24m") if k in c)
        L.append(f"- {n}: bruto {_pp(c['principal']['T_bruto'])}, placebo medio {_pp(c['principal']['media_placebo'])}"
                 f"{extra}; países de prueba {_r(r['paises_prueba'][n]['por_pais'], 3)}")
    L += ["", "## Descriptivos (sin veredicto)", "", "| id | efecto | IC 95 % | p | p rangos | eventos | sin guerras | 1950-2004 |",
          "|---|---|---|---|---|---|---|---|"]
    for n, c in r["contrastes"].items():
        if n in FAMILIA:
            continue
        pr = c["principal"]
        f = (lambda v: f"{v:+.2f} años") if n.startswith(("C7", "C8")) else _pp
        L.append(f"| {n} | {f(pr['efecto'])} | [{f(pr['ic95'][0])}; {f(pr['ic95'][1])}] | {pr['p']:.4f} | "
                 f"{pr['p_rangos']:.3f} | {pr['eventos']} | {f(c['sin_guerras']['efecto'])} | {f(c['1950_2004']['efecto'])} |")
    L += ["", "Año del fondo respecto al valle (media real / placebo):", ""]
    for gn, d in r["descriptivos"]["fondo_respecto_al_valle"].items():
        L.append(f"- {gn}: " + "; ".join(f"{a} {d[a]['media_real']:+.2f} / {d[a]['media_placebo']:+.2f} (n = {d[a]['eventos']})"
                                         for a in ACTIVOS if d[a]["media_real"] is not None))
    L += ["", "Coste de esperar en bruto (16 meses) y lo que queda hasta el fin del 3.er año, pp (anómalo entre paréntesis):", ""]
    for k, d in r["descriptivos"]["espera_recesion"].items():
        L.append(f"- {k}: espera {_pp(d['espera']['T_bruto'])} ({_pp(d['espera']['efecto'])}); queda "
                 f"{_pp(d['queda_hasta_fin_3er_año']['T_bruto'])} ({_pp(d['queda_hasta_fin_3er_año']['efecto'])})")
    L += ["", "Bolsa real anómala por año respecto al valle (todas; media, banda placebo 5-95 %):", ""]
    t = r["descriptivos"]["trayectorias_valle"]["todas"]["eq"]
    L.append("- " + "; ".join(f"V{tau:+d}: {_pp(m)} [{_pp(a)}; {_pp(b)}]" for tau, m, a, b in zip(t["tau"], t["media"], t["p05"], t["p95"])))
    L += ["", "Cambios de cuadrante (espera bruta 16 meses / anómala):", ""]
    for tn, d in r["descriptivos"]["cambios_cuadrante"].items():
        L.append(f"- {tn} (n = {d['eventos']}): " + "; ".join(
            f"{a} {_pp(d[f'espera|{a}']['T_bruto'])} / {_pp(d[f'espera|{a}']['efecto'])}" for a in ("eq_x", "bond_x", "viv")))
    L += ["", "## EE. UU. mensual (secundario, sin potencia)", "",
          "| giro | fondo bolsa (meses) | fondo bono | espera NBER (meses; bolsa − letras) | espera regla 9 m (bolsa − letras) |",
          "|---|---|---|---|---|"]
    for tipo in ("picos", "valles"):
        for e in r["eeuu_mensual"][tipo]:
            nb = (f"{e['espera_nber_meses']}; {_pp(e['espera_nber_bolsa_x'])}" if "espera_nber_meses" in e else "sin anuncio")
            L.append(f"| {tipo[:-1]} {e['giro']} | {e['fondo_bolsa_meses']:+d} | {e['fondo_bono_meses']:+d} | {nb} | "
                     f"{_pp(e['espera_regla_9m_bolsa_x'])} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
