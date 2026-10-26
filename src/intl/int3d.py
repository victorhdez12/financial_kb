"""INT-3d (giros): motor del estudio de eventos de P-DEV-INT3d v1.0 (docs/int/INT3d_prerregistro_v0.md, congelado en
fa6d4c9). Las definiciones de ventanas, estadísticos por evento, agrupación por año ancla y placebo son las MISMAS
funciones que usó el cálculo de potencia (scripts/int3d_potencia.py, commit 3c588c1); aquí solo se añaden la evaluación
con datos (z calibrada con el placebo, p por rangos), los criterios, las sensibilidades y los descriptivos.
Todo en log(1 + r) real; nada ≥ 2005 (las ventanas que lo tocarían quedan fuera).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts import int3d_potencia as S

A0, A1, L = S.A0, S.A1, S.L
GUERRAS = S.GUERRAS
KS = list(range(S.DESFASE_MIN, L - S.DESFASE_MIN + 1))      # 124 desplazamientos


# ---------------------------------------------------------------- panel
def panel_log(anual: pd.DataFrame, paises: list[str], winsor: dict | None = None, sin_hiper: bool = False) -> dict:
    """log(1 + r) real por país × año (como S.panel_log, con lista de países). winsor: {serie: (q01, q99)} aplicado a
    eq, bond, bill, viv antes de formar excesos. sin_hiper: quita (NaN) los país-años con inflación > 50 %."""
    out = {}
    for k, col in S.SERIES.items():
        w = anual[col].unstack(0).reindex(index=range(A0, A1 + 1), columns=paises)
        out[k] = np.log1p(w.clip(lower=-0.99)).to_numpy().T
        if winsor and k in winsor:
            lo, hi = winsor[k]
            out[k] = np.where(np.isfinite(out[k]), np.clip(out[k], lo, hi), np.nan)
    if sin_hiper:
        inf = anual["inflacion"].unstack(0).reindex(index=range(A0, A1 + 1), columns=paises).to_numpy().T
        hip = inf > np.log(1.5)
        for k in out:
            out[k] = np.where(hip, np.nan, out[k])
    out["eq_x"] = out["eq"] - out["bill"]
    out["bond_x"] = out["bond"] - out["bill"]
    return out


def cuantiles_winsor(x: dict) -> dict:
    return {k: (float(np.nanquantile(x[k], 0.01)), float(np.nanquantile(x[k], 0.99))) for k in S.SERIES}


# ---------------------------------------------------------------- eventos
def eventos_rec(rec: pd.DataFrame, paises: list[str]) -> pd.DataFrame:
    r = rec[rec.pais.isin(paises)].copy()
    r["ci"] = r.pais.map({c: i for i, c in enumerate(paises)})
    r["fin"] = (r.tipo == "financiera").astype(int)
    return r[["pais", "ci", "pico", "valle", "fin"]].astype({"pico": int, "valle": int}).reset_index(drop=True)


def eventos_transicion(et: pd.DataFrame, paises: list[str], destino: set, sin_frontera: bool = False) -> pd.DataFrame:
    """Entrada en el conjunto de cuadrantes `destino` en t: en destino en t y fuera en t − 1 y t − 2 (racha previa ≥ 2),
    los tres años con etiqueta y sin truncar. Con destino = INFL_ALTA es exactamente S.eventos_inflacion."""
    filas = []
    e = et[et.pais.isin(paises)]
    for c, g in e.groupby("pais"):
        g = g.set_index("año")
        ok = g.cuadrante.notna() & ~g.truncada.fillna(True).astype(bool)
        dentro = g.cuadrante.isin(destino)
        for t in g.index:
            if all((y in g.index) and ok[y] for y in (t, t - 1, t - 2)) and dentro[t] and not dentro[t - 1] \
                    and not dentro[t - 2]:
                if sin_frontera and bool(g.frontera.get(t, False)):
                    continue
                filas.append({"pais": c, "ci": paises.index(c), "t": int(t)})
    return pd.DataFrame(filas, columns=["pais", "ci", "t"])


def dic_rec(df: pd.DataFrame) -> dict:
    return {"ci": df.ci.to_numpy(int), "P": df.pico.to_numpy(int), "V": df.valle.to_numpy(int), "fin": df.fin.to_numpy(int)}


def dic_t(df: pd.DataFrame) -> dict:
    return {"ci": df.ci.to_numpy(int), "t": df.t.to_numpy(int)}


def filtrar(ev: dict, keep: np.ndarray) -> dict:
    return {k: v[keep] for k, v in ev.items()}


def submuestra(nombre: str, ev: dict, muestra: str) -> dict:
    """principal / sin_guerras / 1950_2004 con la ventana de cada contraste (S.ventana_anos), como S.seleccionar."""
    if "t" in ev:
        y0, y1 = ev["t"], ev["t"] + 1
    else:
        y0, y1 = S.ventana_anos(nombre, ev["P"], ev["V"])
    keep = y1 <= A1
    if muestra == "sin_guerras":
        keep &= np.array([not any(y in GUERRAS for y in range(a, b + 1)) for a, b in zip(y0, y1)])
    elif muestra == "1950_2004":
        keep &= y0 >= 1950
    return filtrar(ev, keep)


# ---------------------------------------------------------------- estadístico y placebo
def valfun_nombre(nombre: str):
    return lambda ac, ev: S.valores_evento(nombre, ac, ev)


def stat(valfun, ac: S.Acum, ev: dict, grupo: bool, por_año: bool = True) -> float:
    x, g = valfun(ac, ev)
    if grupo:
        f = ev["fin"].astype(bool)
        return S.agregar(x[f], g[f], por_año) - S.agregar(x[~f], g[~f], por_año)
    return S.agregar(x, g, por_año)


def evaluar(valfun, x: np.ndarray, ev: dict, grupo: bool = False, por_año: bool = True) -> dict:
    """T en las fechas reales; placebo con las 124 fechas desplazadas (misma k en todos los países). Efecto anómalo =
    T − media placebo; z = efecto / sd placebo; p = 2(1 − Φ|z|); p por rangos; IC 95 % = efecto ± 1,96·sd placebo."""
    ac = S.Acum(x)
    xs, g = valfun(ac, ev)
    ok = np.isfinite(xs)
    T = stat(valfun, ac, ev, grupo, por_año)
    pl = np.array([stat(valfun, ac, S.desplazar(ev, k), grupo, por_año) for k in KS])
    pl = pl[np.isfinite(pl)]
    mu, sd = float(pl.mean()), float(pl.std(ddof=1))
    ef = T - mu
    z = ef / sd if sd > 0 else np.nan
    out = {"T_bruto": T, "media_placebo": mu, "sd_placebo": sd, "efecto": ef, "ic95": [ef - 1.96 * sd, ef + 1.96 * sd],
           "z": z, "p": float(2 * norm.sf(abs(z))),
           "p_rangos": float((1 + (np.abs(pl - mu) >= abs(ef)).sum()) / (1 + len(pl))),
           "placebo_p05_p95": [float(np.quantile(pl, 0.05)), float(np.quantile(pl, 0.95))],
           "eventos": int(ok.sum()), "años_ancla": int(np.unique(g[ok]).size), "placebos": int(len(pl))}
    if grupo:
        out["financieras"] = int(ev["fin"][ok].sum())
    return out


def sin_año_influyente(valfun, x: np.ndarray, ev: dict, grupo: bool = False) -> dict:
    """Quita, uno a uno, los eventos de cada año ancla; devuelve el que más mueve el efecto anómalo y el efecto sin él."""
    ac = S.Acum(x)
    xs, g = valfun(ac, ev)
    base = evaluar(valfun, x, ev, grupo)["efecto"]
    mejor = None
    for a in np.unique(g[np.isfinite(xs)]):
        r = evaluar(valfun, x, filtrar(ev, g != a), grupo)
        if mejor is None or abs(r["efecto"] - base) > abs(mejor["efecto"] - base):
            mejor = {"año": int(a), **r}
    return mejor


def por_pais(valfun, x: np.ndarray, ev: dict, paises: list[str], grupo: bool = False) -> dict:
    out = {}
    for i, c in enumerate(paises):
        sub = filtrar(ev, ev["ci"] == i)
        if len(sub["ci"]) == 0 or (grupo and (sub["fin"].sum() == 0 or sub["fin"].sum() == len(sub["fin"]))):
            continue
        r = evaluar(valfun, x, sub, grupo)
        if r["eventos"] > 0 and np.isfinite(r["efecto"]):
            out[c] = {"efecto": r["efecto"], "eventos": r["eventos"]}
    return out


def permutacion_etiqueta(valfun, x: np.ndarray, ev: dict, n: int = 2000, semilla: int = 1) -> dict:
    """Sensibilidad de C2/C6: nula por permutación de la etiqueta financiera / normal entre eventos (fechas reales)."""
    ac = S.Acum(x)
    obs = stat(valfun, ac, ev, True)
    rng = np.random.default_rng(semilla)
    sims = []
    for _ in range(n):
        e2 = dict(ev)
        e2["fin"] = rng.permutation(ev["fin"])
        sims.append(stat(valfun, ac, e2, True))
    sims = np.array(sims)
    return {"diferencia": obs, "p_permutacion": float((1 + (np.abs(sims) >= abs(obs)).sum()) / (1 + n))}


# ---------------------------------------------------------------- funciones de valor adicionales (descriptivos y sensibilidades)
def vf_ventana(ancla: str, offsets: list[tuple[int, float]]):
    """Σ_j peso_j · x[c, ancla + off_j] (ventana con fracciones de año); agrupa por el ancla."""
    def f(ac, ev):
        a = ev[ancla]
        tot = np.zeros(len(a))
        for off, w in offsets:
            tot = tot + w * ac.suma(ev["ci"], a + off, a + off)
        return tot, a
    return f


def vf_fondo():
    return lambda ac, ev: S.valores_evento("C7_fondo_bolsa", ac, ev)      # mismo cálculo para cualquier activo


def trayectoria(x: np.ndarray, ev: dict, ancla: str, taus: range, completa: tuple[int, int]) -> dict:
    """Rentabilidad anómala media (frente a la media de cada país en 1870-2004) por año de evento, ponderando cada año
    ancla 1; solo eventos con la ventana `completa` (offsets) con dato. Bandas 5-95 % de los placebos."""
    y = x - np.nanmean(x, axis=1, keepdims=True)

    def medias(e):
        ac = S.Acum(y)
        a = e[ancla]
        ok = np.isfinite(ac.suma(e["ci"], a + completa[0], a + completa[1]))
        fila = []
        for tau in taus:
            v = ac.suma(e["ci"], a + tau, a + tau)
            fila.append(S.agregar(v[ok], a[ok]))
        return np.array(fila), int(ok.sum())

    real, n = medias(ev)
    pls = np.array([medias(S.desplazar(ev, k))[0] for k in KS])
    return {"tau": list(taus), "media": real.tolist(), "p05": np.nanquantile(pls, 0.05, axis=0).tolist(),
            "p95": np.nanquantile(pls, 0.95, axis=0).tolist(), "eventos": n}


def distribucion_fondo(x: np.ndarray, ev: dict) -> dict:
    ac = S.Acum(x)
    v, _ = vf_fondo()(ac, ev)
    v = v[np.isfinite(v)].astype(int)
    pl = []
    for k in KS:
        w, _ = vf_fondo()(ac, S.desplazar(ev, k))
        pl.extend(w[np.isfinite(w)].astype(int).tolist())
    pl = np.array(pl)
    cuenta = pd.Series(v).value_counts(normalize=True).sort_index()
    cpl = pd.Series(pl).value_counts(normalize=True).sort_index()
    return {"eventos": int(v.size), "frac_real": {int(k): round(float(c), 3) for k, c in cuenta.items()},
            "frac_placebo": {int(k): round(float(c), 3) for k, c in cpl.items()},
            "media_real": float(v.mean()) if v.size else None, "media_placebo": float(pl.mean()) if pl.size else None}


# ---------------------------------------------------------------- EE. UU. mensual (secundario, sin potencia)
ANUNCIOS_NBER = {   # fecha del giro (mes) → fecha del anuncio del Comité de Fechado del NBER
    "1980-01": "1980-06-03", "1980-07": "1981-07-08", "1981-07": "1982-01-06", "1982-11": "1983-07-08",
    "1990-07": "1991-04-25", "1991-03": "1992-12-22", "2001-03": "2001-11-26", "2001-11": "2003-07-17",
}
REGLA_MESES = 9     # 6 meses de fase mínima (Bry-Boschan, INT-1) + 75 días de retraso de la producción industrial


def eeuu_series(m: pd.DataFrame) -> pd.DataFrame:
    """Log real mensual (bolsa ya en log; bono y letra simples → log1p) y exceso bolsa − letras; índice = mes (inicio)."""
    u = pd.DataFrame({"bolsa": m["r_bolsa_tr"] - m["inflacion_mes"],
                      "bono": np.log1p(m["r_bono"]) - m["inflacion_mes"],
                      "letra": np.log1p(m["r_letra"]) - m["inflacion_mes"]})
    u["bolsa_x"] = m["r_bolsa_tr"] - np.log1p(m["r_letra"])
    u["bono_x"] = np.log1p(m["r_bono"]) - np.log1p(m["r_letra"])
    u.index = pd.to_datetime(u.index).to_period("M")
    return u


def eeuu_evento(u: pd.DataFrame, giro: pd.Period, anuncio: pd.Period | None) -> dict | None:
    """Ventana −12 … +24 meses alrededor del mes del giro (pico o valle NBER). Oráculo: mes siguiente al giro.
    Coste de esperar = Σ del exceso desde el mes siguiente al giro hasta el mes de la confirmación (incluido)."""
    meses = pd.period_range(giro - 12, giro + 24, freq="M")
    w = u.reindex(meses)
    if w[["bolsa", "bono", "letra"]].isna().any().any():
        return None
    out = {"giro": str(giro)}
    for a in ("bolsa", "bono"):
        niv = np.concatenate([[0.0], w[a].cumsum().to_numpy()])          # nivel 0 a fin del mes giro − 13
        out[f"fondo_{a}_meses"] = int(np.argmin(niv)) - 13
    for nom, fin in (("nber", anuncio), ("regla_9m", giro + REGLA_MESES)):
        if fin is None:
            continue
        tramo = u.loc[giro + 1: fin]
        out[f"espera_{nom}_meses"] = int(len(tramo))
        out[f"espera_{nom}_bolsa_x"] = float(tramo["bolsa_x"].sum())
        out[f"espera_{nom}_bono_x"] = float(tramo["bono_x"].sum())
        resto = u.loc[fin + 1: giro + 24]
        out[f"queda_{nom}_bolsa_x"] = float(resto["bolsa_x"].sum())
    return out
