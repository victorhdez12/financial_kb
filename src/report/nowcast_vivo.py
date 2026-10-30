"""INT-8b, parte en vivo: nowcast mensual DESCRIPTIVO de recesión (docs/int/INT8b_nowcast.md; regla congelada en
docs/int/INT8b_regla_v1.md). Percentil y banda frente a la historia 1960-2004 de cada país; NUNCA una probabilidad.

Vive en src/report/ porque lee datos ≥ 2005 (como src/report/termometro_vivo.py, del que reutiliza la carga: OCDE y BIS
de `obs_latest` hasta el fin de mes de corte, sin vintages, nunca JST, con el empalme declarado del tipo a 3 meses de GBR).
Añade la producción industrial (`oecd_ip_*`, interanual en log, retraso 75 días) y el paro (`oecd_unemp_*`, para la regla
tipo Sahm). Las distribuciones de referencia 1960-2004 están congeladas en research/int/int8b_referencias.json
(scripts/int8b_corrida.py, solo datos ≤ 2004) y aquí solo se leen.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import int8b as K
from src.intl import lags as Lg
from src.intl import panel as P
from src.intl import termometro as T
from src.report import termometro_vivo as TV

REPO = Path(__file__).resolve().parents[2]
REFERENCIAS = REPO / "research" / "int" / "int8b_referencias.json"
NUCLEO, PRUEBA, TODOS = TV.NUCLEO, TV.PRUEBA, TV.TODOS

AVISO = ("Informativo, no es una señal de cartera. Nowcast descriptivo: percentil frente a la historia 1960-2004 de cada "
         "país (media con pesos iguales de 6 indicadores conocidos), no una probabilidad de recesión a 3 meses. No se ha "
         "probado que anticipe nada fuera de la muestra; su evaluación en vivo necesitará décadas.")


class ReferenciasIncompletas(RuntimeError):
    """Faltan las referencias congeladas ≤ 2004: no se muestra nada y NO se recalculan con datos ≥ 2005."""


def referencias_congeladas(path: Path = REFERENCIAS) -> dict:
    d = json.loads(Path(path).read_text()) if Path(path).exists() else {}
    r, falta = d.get("referencias") or {}, []
    if not r:
        falta.append(f"sin referencias en {path}")
    else:
        ind = r.get("indicadores") or {}
        falta += [f"distribución {k} {c}" for k in K.CLAVES for c in TODOS if not isinstance((ind.get(k) or {}).get(c), list)]
        falta += [f"índice {c}" for c in TODOS if not isinstance((r.get("indice") or {}).get(c), list)]
        if not isinstance(r.get("agregado"), list):
            falta.append("agregado")
        if (r.get("desde"), r.get("hasta")) != (str(K.REF_DESDE.date()), str(K.REF_HASTA.date())):
            falta.append("periodo de referencia distinto de 1960-01/2004-12")
    if falta:
        raise ReferenciasIncompletas("referencias ≤ 2004 de INT-8b incompletas: " + "; ".join(falta) +
                                     ". Volver a correr scripts/int8b_corrida.py con el árbol limpio (solo ≤ 2004).")
    return r


def cargar(con, fecha) -> tuple[pd.DataFrame, dict, dict, dict, pd.Timestamp]:
    """Bloque del termómetro en vivo + IP interanual "as of" (columna `ip_yoy`, mismas transformaciones que
    src/intl/panel.mensual) y paro mensual en su fecha de observación."""
    pm, bis, pib, corte = TV.cargar(con, fecha)
    rej = pm.index.get_level_values("fecha").unique()
    ip, paro = {}, {}
    for c in TODOS:
        lc = c.lower()
        s = TV._serie(con, f"oecd_ip_{lc}", corte)
        ip[c] = Lg.asof(np.log(P._mensual_completa(s)).diff(12), f"oecd_ip_{lc}", rej) if not s.empty else \
            pd.Series(np.nan, index=rej)
        if not (u := TV._serie(con, f"oecd_unemp_{lc}", corte)).empty:
            paro[c] = u
    pm = pm.copy()
    pm["ip_yoy"] = pd.concat({c: ip[c] for c in TODOS}, names=["pais", "fecha"]).reindex(pm.index)
    pm.attrs = dict(pm.attrs)
    return pm, bis, pib, paro, corte


def _r(v, n=1):
    if v is None or not np.isfinite(v):
        return None
    return int(round(float(v))) if n == 0 else round(float(v), n)


def calcular(pm, bis, pib, paro, corte, refs) -> dict:
    comp = K.componentes(pm, bis, pib, paro, NUCLEO, TODOS)
    res = K.calcular(comp, refs, NUCLEO, TODOS)
    i = len(res["N"].index) - 1
    rej = res["N"].index
    paises = {}
    for c in TODOS:
        ind = {}
        for k, lab, uni, fac, _ in K.COMPONENTES:
            v = float(comp[k][c].iloc[i])
            ind[k] = {"indicador": lab, "unidad": uni, "valor": _r(v * fac, 2),
                      "percentil_orientado": _r(res["pct"][k][c].iloc[i], 0),
                      "meses_hist": len(refs["indicadores"][k][c])}
        en = None
        if c in pib and not pib[c].dropna().empty:
            est = T.estado_mensual(T.fechado_trimestral(pib[c].dropna()), rej, pib[c].dropna().index.min())
            e = est["en_rec"].iloc[i]
            en = None if not np.isfinite(e) else bool(e)
        n_ok = sum(v["percentil_orientado"] is not None for v in ind.values())
        pN = _r(res["pN"][c].iloc[i], 0)
        paises[c] = {"grupo": "usa" if c == "USA" else ("nucleo" if c in NUCLEO else "prueba"),
                     "indice": _r(res["N"][c].iloc[i]), "percentil": pN, "banda": K.banda(pN),
                     "historia_corta": len(refs["indice"][c]) < K.MIN_MESES,
                     "n_indicadores": n_ok, "indicadores": ind, "en_recesion_fechado": en}
    pA = _r(res["pA"].iloc[i], 0)
    nuc = [paises[c] for c in NUCLEO]
    return {"fecha_calculo": str(corte.date()), "aviso": AVISO,
            "agregado": {"indice": _r(res["A"].iloc[i]), "percentil": pA, "banda": K.banda(pA),
                         "paises_con_dato": sum(p["indice"] is not None for p in nuc),
                         "paises_alto": [c for c in NUCLEO if paises[c]["banda"] in ("alto", "muy alto")],
                         "paises_en_recesion": [c for c in NUCLEO if paises[c]["en_recesion_fechado"]]},
            "paises": paises, "empalmes": dict(pm.attrs.get("empalmes", {})),
            "metodo": {"regla": "docs/int/INT8b_regla_v1.md (congelada)",
                       "referencias": str(REFERENCIAS.relative_to(REPO)),
                       "datos": "obs_latest (sin vintages: niveles revisados), retrasos as of de src/intl/lags.py"}}


def nowcast(con, fecha, refs: dict | None = None) -> dict:
    refs = refs or referencias_congeladas()
    pm, bis, pib, paro, corte = cargar(con, fecha)
    return calcular(pm, bis, pib, paro, corte, refs)


# ---------------------------------------------------------------- Markdown
def _f(v, suf=""):
    return "—" if v is None else f"{v}{suf}"


def _fila(c: str, d: dict, nota: str = "") -> str:
    st = {True: "**sí**", False: "no", None: "sin dato"}[d["en_recesion_fechado"]]
    b = d["banda"] or ("historia corta" if d["historia_corta"] and d["indice"] is not None else "—")
    celdas = [c + nota, f"**{b}** (p{_f(d['percentil'])})" if d["banda"] else b, _f(d["indice"]),
              str(d["n_indicadores"])]
    celdas += [f"{_f(v['valor'])} (p{_f(v['percentil_orientado'])})" for v in d["indicadores"].values()]
    celdas.append(st)
    return "| " + " | ".join(celdas) + " |"


def markdown(res: dict, titulo: str = "## 5c. Nowcast de recesión (informativo)") -> str:
    cab = ["país", "banda (percentil del índice)", "índice 0-100", "nº ind."] + \
          [f"{lab} ({uni})" for _, lab, uni, _, _ in K.COMPONENTES] + ["en recesión (fechado PIB, retrasado)"]
    head = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    a, P_ = res["agregado"], res["paises"]
    banda_a = f"**{a['banda']}** (percentil {a['percentil']} frente a 1960-2004)" if a["banda"] else "sin dato"
    out = [f"{titulo} — {res['fecha_calculo']}", "",
           "> [!note] Informativo, no es una señal de cartera", f"> {res['aviso']}", "",
           "Pregunta: ¿está empezando ya una recesión, o empezará en 0-3 meses? Respuesta en **bandas**, no en "
           "porcentajes.", "",
           f"**Agregado del núcleo (14 países):** {banda_a}; índice {_f(a['indice'])} con {a['paises_con_dato']} países. "
           f"En «alto» o «muy alto»: {', '.join(a['paises_alto']) or 'ninguno'}. En recesión según el fechado "
           f"trimestral: {', '.join(a['paises_en_recesion']) or 'ninguno'}.", "",
           *head, _fila("USA", P_["USA"]), *[_fila(c, P_[c]) for c in NUCLEO if c != "USA"],
           *[_fila(c, P_[c], " (prueba)") for c in PRUEBA], ""]
    if res.get("empalmes"):
        out += ["> [!note] Empalmes declarados", *[f"> - {c}: {t}." for c, t in res["empalmes"].items()], ""]
    out.append("Método (regla congelada, docs/int/INT8b_regla_v1.md): cada indicador se pasa a su percentil frente a los "
               "meses 1960-2004 del propio país, orientado para que alto = más parecido a una recesión (entre "
               "paréntesis); el índice es la media con pesos iguales (≥ 4 de 6) y la banda sale de su percentil "
               "(bajo < 50 ≤ medio < 80 ≤ alto < 95 ≤ muy alto). El fechado del PIB no entra en el índice. Sin "
               "probabilidad: con ≈ 3-4 episodios por década no se podrá calibrar en vivo en décadas.")
    return "\n".join(out) + "\n"
