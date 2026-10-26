"""INT-3d (giros): cálculo de potencia del estudio de eventos ANTES de cruzar ningún activo con ningún evento.
Prerregistro: docs/int/INT3d_prerregistro_v0.md (borrador). Solo datos ≤ 2004 (src/intl/data.load_dev y parquets de INT-1).

Qué usa (y nada más):
  (i)   FECHAS de los eventos: recesiones anuales del núcleo (INT-1, convención JST: pico P, valle V, normal/financiera),
        entradas en inflación alta (etiqueta anual de INT-1) y NBER (USREC, solo fechas), con sus RECUENTOS, la
        agrupación por año común y los solapes de ventanas entre países;
  (ii)  DISPONIBILIDAD de cada activo por país-año (máscara sí/no, nunca el valor) para saber qué eventos tienen ventana
        completa;
  (iii) estadísticos INCONDICIONALES de las rentabilidades reales anuales (log) del panel: desviación típica, AR(1) del
        factor común y del resto, correlación media entre países, curtosis. Se calculan en una función que NO recibe
        fechas de eventos.
Qué NO hace nunca: calcular una rentabilidad real alrededor de un evento real. Los estadísticos de evento se calculan
SOLO sobre paneles SIMULADOS (factor común AR(1) + componente de país AR(1), con los parámetros de (iii) y la máscara
de (ii)), sin efecto o con un efecto inyectado, en las fechas reales y en las desplazadas (placebo).

Salida: MDE (80 %, bilateral 5 %) de cada contraste candidato con 1 contraste y con Bonferroni-Holm de k contrastes;
tamaño empírico y potencia del contraste principal (z calibrada con el placebo); recuentos y solapes; la regla de
selección del §5 del prerregistro aplicada (cuántos contrastes caben).
Uso: .venv/bin/python -m scripts.int3d_potencia            (con puerta: árbol limpio; escribe research/int/int3d_potencia.json)
     .venv/bin/python -m scripts.int3d_potencia --prueba   (sin puerta, pocas simulaciones; no escribe nada)
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.intl import data as D
from src.intl import lags as Lg
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
PRUEBA = {"AUS", "CHE", "CAN", "IRL"}
NUCLEO = [c for c in D.PAISES if c not in PRUEBA]
A0, A1 = 1870, 2004
L = A1 - A0 + 1
GUERRAS = set(range(1914, 1919)) | set(range(1939, 1946))
INFL_ALTA = {"sobrecalentamiento", "estanflacion"}
DESFASE_MIN = 6
SEMILLA = 20261026
Z80 = norm.ppf(0.80)
# fracción del año siguiente que pasa hasta que se publica el dato anual (JST: 120 días tras el fin de año → 4 meses)
F_PUB = round(Lg.RETRASO_DIAS["jst"] / 30) / 12          # = 4/12
MAX_FAMILIA = 6

# Contrastes candidatos, en ORDEN DE PRIORIDAD fijado a priori (§4 del prerregistro). efecto = efecto plausible escrito
# ANTES de calcular la potencia (literatura y mecanismo; unidades: log, ≈ pp); signo = signo esperado.
CANDIDATOS = {
    "C1_espera_salida":  {"serie": "eq_x",   "efecto": 0.08, "signo": +1},
    "C2_fin_bolsa":      {"serie": "eq",     "efecto": 0.10, "signo": -1},
    "C3_bonos_recesion": {"serie": "bond_x", "efecto": 0.03, "signo": +1},
    "C4_espera_entrada": {"serie": "eq_x",   "efecto": 0.06, "signo": -1},
    "C5_espera_inflac":  {"serie": "bond_x", "efecto": 0.05, "signo": -1},
    "C6_fin_vivienda":   {"serie": "viv",    "efecto": 0.08, "signo": -1},
    "C7_fondo_bolsa":    {"serie": "eq",     "efecto": 0.50, "signo": -1},   # años
    "C8_fondo_vivienda": {"serie": "viv",    "efecto": 1.00, "signo": +1},   # años
}
SERIES = {"eq": "eq_tr_real", "bond": "bond_tr_real", "bill": "bill_rate_real", "viv": "housing_tr_real"}


# ---------------------------------------------------------------- (iii) activos: solo incondicional, sin fechas de eventos
def panel_log(anual: pd.DataFrame) -> dict[str, np.ndarray]:
    """Rentabilidades reales en log(1 + r), país × año (NaN si falta). eq_x = bolsa − letras; bond_x = bonos − letras."""
    out = {}
    for k, col in SERIES.items():
        w = anual[col].unstack(0).reindex(index=range(A0, A1 + 1), columns=NUCLEO)
        out[k] = np.log1p(w.clip(lower=-0.99)).to_numpy().T
    out["eq_x"] = out["eq"] - out["bill"]
    out["bond_x"] = out["bond"] - out["bill"]
    return out


def estadisticos_incondicionales(x: np.ndarray) -> dict:
    """sd (desviación típica tras quitar la media de cada país), correlación media entre países, AR(1) del factor común
    (media de cada año) y del resto, curtosis. No recibe ni usa fechas de eventos."""
    xd = x - np.nanmean(x, axis=1, keepdims=True)
    sd = float(np.nanstd(xd))
    df = pd.DataFrame(xd.T)
    pares = [df[[i, j]].dropna().corr().iloc[0, 1] for i, j in itertools.combinations(df.columns, 2)
             if df[[i, j]].dropna().shape[0] >= 20]
    rho = float(np.clip(np.nanmean(pares), 0.0, 0.95))
    f = pd.Series(np.nanmean(xd, axis=0))
    phi_f = float(f.autocorr(1))
    resto = xd - f.to_numpy()[None, :]
    phi_u = float(np.nanmean([pd.Series(r).dropna().autocorr(1) for r in resto if np.isfinite(r).sum() > 20]))
    v = xd[np.isfinite(xd)]
    kurt = float(((v - v.mean()) ** 4).mean() / v.var() ** 2 - 3)
    return {"sd": sd, "rho": rho, "phi_f": float(np.clip(phi_f, -0.9, 0.9)), "phi_u": float(np.clip(phi_u, -0.9, 0.9)),
            "curtosis_exceso": kurt, "n": int(np.isfinite(x).sum())}


def _ar1(n_filas: int, phi: float, rng, gl: float | None) -> np.ndarray:
    e = rng.standard_t(gl, size=(n_filas, L)) / np.sqrt(gl / (gl - 2)) if gl else rng.standard_normal((n_filas, L))
    out = np.empty_like(e)
    out[:, 0] = e[:, 0]
    a = np.sqrt(1 - phi ** 2)
    for t in range(1, L):
        out[:, t] = phi * out[:, t - 1] + a * e[:, t]
    return out


def simular(st: dict, mascara: np.ndarray, rng, gl: float | None = None) -> np.ndarray:
    """Panel sintético SIN efecto: σ·(√ρ·f_t + √(1 − ρ)·u_it), f y u AR(1) de varianza 1; NaN donde no hay dato."""
    f = _ar1(1, st["phi_f"], rng, gl)
    u = _ar1(len(NUCLEO), st["phi_u"], rng, gl)
    x = st["sd"] * (np.sqrt(st["rho"]) * f + np.sqrt(1 - st["rho"]) * u)
    return np.where(mascara, x, np.nan)


# ---------------------------------------------------------------- (i) eventos: solo fechas
def eventos_recesion(rec: pd.DataFrame) -> pd.DataFrame:
    r = rec[rec.pais.isin(NUCLEO)].copy()
    r["ci"] = r.pais.map({c: i for i, c in enumerate(NUCLEO)})
    r["fin"] = (r.tipo == "financiera").astype(int)
    return r[["pais", "ci", "pico", "valle", "fin"]].astype({"pico": int, "valle": int}).reset_index(drop=True)


def eventos_inflacion(et: pd.DataFrame, sin_frontera: bool = False) -> pd.DataFrame:
    """Entrada en inflación alta (sobrecalentamiento ∪ estanflación) en t: I alta en t, I baja en t − 1 y t − 2 (racha
    previa ≥ 2 años), los tres años con etiqueta y sin truncar. Solo fechas."""
    filas = []
    e = et[et.pais.isin(NUCLEO)]
    for c, g in e.groupby("pais"):
        g = g.set_index("año")
        ok = g.cuadrante.notna() & ~g.truncada.fillna(True).astype(bool)
        alta = g.cuadrante.isin(INFL_ALTA)
        for t in g.index:
            if all((y in g.index) and ok[y] for y in (t, t - 1, t - 2)) and alta[t] and not alta[t - 1] and not alta[t - 2]:
                if sin_frontera and bool(g.frontera.get(t, False)):
                    continue
                filas.append({"pais": c, "ci": NUCLEO.index(c), "t": int(t)})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- estadísticos de evento (se aplican a paneles SIMULADOS)
class Acum:
    """Sumas por ventana con comprobación de ventana completa (cumsum de valores y de la máscara)."""

    def __init__(self, x: np.ndarray):
        m = np.isfinite(x)
        self.S = np.concatenate([np.zeros((x.shape[0], 1)), np.cumsum(np.where(m, x, 0.0), axis=1)], axis=1)
        self.N = np.concatenate([np.zeros((x.shape[0], 1)), np.cumsum(m, axis=1)], axis=1)
        self.x = x

    def suma(self, ci, y0, y1):
        """Σ x[c, y0..y1] (años de calendario); NaN si se sale de 1870-2004 o falta algún año."""
        i0, i1 = y0 - A0, y1 - A0
        ok = (i0 >= 0) & (i1 <= L - 1) & (i1 >= i0)
        i0c, i1c = np.clip(i0, 0, L - 1), np.clip(i1, 0, L - 1)
        s = self.S[ci, i1c + 1] - self.S[ci, i0c]
        n = self.N[ci, i1c + 1] - self.N[ci, i0c]
        return np.where(ok & (n == (i1 - i0 + 1)), s, np.nan)


def ventana_anos(nombre: str, P, V, t=None) -> tuple:
    """Años de calendario que usa cada contraste (para la cobertura y para quitar guerras)."""
    if nombre == "C5_espera_inflac":
        return (t, t + 1)
    return {"C1_espera_salida": (V + 1, V + 2), "C4_espera_entrada": (P + 1, P + 2), "C3_bonos_recesion": (P + 1, V),
            "C2_fin_bolsa": (P, V + 1), "C6_fin_vivienda": (P, V + 2), "C7_fondo_bolsa": (P - 1, V + 3),
            "C8_fondo_vivienda": (P - 1, V + 3)}[nombre]


def valores_evento(nombre: str, ac: Acum, ev: dict) -> tuple[np.ndarray, np.ndarray]:
    """Valor por evento y su año de agrupación (pico para entradas y comparaciones, valle para salidas y fondos)."""
    ci, P_, V_ = ev["ci"], ev.get("P"), ev.get("V")
    if nombre == "C1_espera_salida":
        return ac.suma(ci, V_ + 1, V_ + 1) + F_PUB * ac.suma(ci, V_ + 2, V_ + 2), V_
    if nombre == "C4_espera_entrada":
        return ac.suma(ci, P_ + 1, P_ + 1) + F_PUB * ac.suma(ci, P_ + 2, P_ + 2), P_
    if nombre == "C3_bonos_recesion":
        return ac.suma(ci, P_ + 1, V_) / (V_ - P_), P_
    if nombre == "C5_espera_inflac":
        t = ev["t"]
        return ac.suma(ci, t, t) + F_PUB * ac.suma(ci, t + 1, t + 1), t
    if nombre in ("C2_fin_bolsa", "C6_fin_vivienda"):
        if nombre == "C6_fin_vivienda":
            return ac.suma(ci, P_, V_ + 2), P_
        D_ = V_ - P_
        niveles = np.stack([np.where(D_ + 1 >= j, ac.suma(ci, P_, P_ + j), np.inf) for j in range(0, 8)])
        completo = np.isfinite(ac.suma(ci, P_, V_ + 1))
        return np.where(completo, np.minimum(0.0, np.nanmin(niveles, axis=0)), np.nan), P_
    if nombre in ("C7_fondo_bolsa", "C8_fondo_vivienda"):
        D_ = V_ - P_
        largo = D_ + 5                                   # años P−1 … V+3
        niv = [np.zeros(len(ci))] + [np.where(j <= largo - 1, ac.suma(ci, P_ - 1, P_ - 1 + j), np.inf) for j in range(0, 12)]
        niv = np.stack(niv)                             # fila 0 = fin de P−2 (nivel 0); fila j+1 = fin de P−1+j
        completo = np.isfinite(ac.suma(ci, P_ - 1, V_ + 3))
        arg = np.argmin(np.where(np.isnan(niv), np.inf, niv), axis=0)
        año_min = (P_ - 2) + arg
        return np.where(completo, (año_min - V_).astype(float), np.nan), V_
    raise KeyError(nombre)


def agregar(x: np.ndarray, g: np.ndarray, por_año: bool = True) -> float:
    ok = np.isfinite(x)
    x, g = x[ok], g[ok]
    if len(x) == 0:
        return np.nan
    if not por_año:
        return float(x.mean())
    _, inv = np.unique(g, return_inverse=True)
    return float((np.bincount(inv, weights=x) / np.bincount(inv)).mean())


def estadistico(nombre: str, ac: Acum, ev: dict, por_año: bool = True, delta: float = 0.0) -> float:
    x, g = valores_evento(nombre, ac, ev)
    if nombre in ("C2_fin_bolsa", "C6_fin_vivienda"):
        fin = ev["fin"].astype(bool)
        return agregar(x[fin] + delta, g[fin], por_año) - agregar(x[~fin], g[~fin], por_año)
    return agregar(x + delta, g, por_año)


def desplazar(ev: dict, k: int) -> dict:
    """Placebo: todas las fechas k años más tarde, en círculo dentro de 1870-2004, la MISMA k en todos los países
    (conserva la agrupación por año, los solapes y las duraciones)."""
    out = dict(ev)
    if "P" in ev:
        P2 = A0 + (ev["P"] - A0 + k) % L
        out["P"], out["V"] = P2, P2 + (ev["V"] - ev["P"])
    if "t" in ev:
        out["t"] = A0 + (ev["t"] - A0 + k) % L
    return out


# ---------------------------------------------------------------- selección de eventos por muestra (solo fechas)
def seleccionar(nombre: str, rec: pd.DataFrame, inf: pd.DataFrame, muestra: str) -> dict:
    base = inf if nombre == "C5_espera_inflac" else rec
    filas = []
    for _, r in base.iterrows():
        if nombre == "C5_espera_inflac":
            y0, y1 = ventana_anos(nombre, None, None, int(r.t))
        else:
            y0, y1 = ventana_anos(nombre, int(r.pico), int(r.valle))
        if y1 > A1:
            continue
        if muestra == "sin_guerras" and any(y in GUERRAS for y in range(y0, y1 + 1)):
            continue
        if muestra == "1950_2004" and y0 < 1950:
            continue
        filas.append(r)
    b = pd.DataFrame(filas)
    if nombre == "C5_espera_inflac":
        return {"ci": b.ci.to_numpy(int), "t": b.t.to_numpy(int)}
    return {"ci": b.ci.to_numpy(int), "P": b.pico.to_numpy(int), "V": b.valle.to_numpy(int), "fin": b.fin.to_numpy(int)}


def recuentos(nombre: str, ev: dict, mascara: np.ndarray) -> dict:
    """Eventos con ventana completa (solo disponibilidad), años distintos de agrupación, Kish y solape de ventanas."""
    ac = Acum(np.where(mascara, 0.0, np.nan))
    x, g = valores_evento(nombre, ac, ev)
    ok = np.isfinite(x)
    g = g[ok]
    m = pd.Series(g).value_counts()
    out = {"eventos": int(ok.sum()), "años_distintos": int(m.size), "eventos_por_año_medio": round(float(m.mean()), 2),
           "m_kish": round(float(m.mean() * (1 + (m.std(ddof=0) / m.mean()) ** 2)), 2)}
    if "fin" in ev:
        out["financieras"] = int(ev["fin"][ok].sum())
        out["años_distintos_financieras"] = int(pd.Series(g[ev["fin"][ok].astype(bool)]).nunique())
    # solape: fracción de pares de eventos de PAÍSES DISTINTOS cuyas ventanas comparten algún año
    if nombre == "C5_espera_inflac":
        y0, y1 = ev["t"][ok], ev["t"][ok] + 1
    else:
        a, b = ventana_anos(nombre, ev["P"][ok], ev["V"][ok])
        y0, y1 = a, b
    ci = ev["ci"][ok]
    i, j = np.triu_indices(len(ci), 1)
    dist = ci[i] != ci[j]
    sol = (np.maximum(y0[i], y0[j]) <= np.minimum(y1[i], y1[j])) & dist
    out["pares_paises_distintos_con_solape"] = round(float(sol.sum() / max(dist.sum(), 1)), 3)
    return out


# ---------------------------------------------------------------- potencia por simulación
def potencia(nombre: str, ev: dict, st: dict, mascara: np.ndarray, n_sd: int, n_cal: int, rng, gl=None) -> dict:
    """SD del estadístico en las fechas reales con paneles SIN efecto (n_sd simulaciones) → MDE; y, en n_cal
    simulaciones, la z calibrada con el placebo: tamaño empírico (sin efecto) y potencia con el efecto plausible."""
    c = CANDIDATOS[nombre]
    reales, reales_ev = [], []
    for _ in range(n_sd):
        ac = Acum(simular(st, mascara, rng, gl))
        reales.append(estadistico(nombre, ac, ev))
        reales_ev.append(estadistico(nombre, ac, ev, por_año=False))
    sd = float(np.nanstd(reales, ddof=1))
    sd_ev = float(np.nanstd(reales_ev, ddof=1))
    ks = list(range(DESFASE_MIN, L - DESFASE_MIN + 1))
    rech0, rech1, sd_pl, rangos = [], [], [], []
    delta = c["signo"] * c["efecto"]
    for _ in range(n_cal):
        ac = Acum(simular(st, mascara, rng, gl))
        pl = np.array([estadistico(nombre, ac, desplazar(ev, k)) for k in ks])
        pl = pl[np.isfinite(pl)]
        mu, s = pl.mean(), pl.std(ddof=1)
        sd_pl.append(s)
        for d, lista in ((0.0, rech0), (delta, rech1)):
            z = (estadistico(nombre, ac, ev, delta=d) - mu) / s
            lista.append(abs(z) > norm.ppf(0.975))
        x0 = estadistico(nombre, ac, ev)
        rangos.append((1 + (np.abs(pl - mu) >= abs(x0 - mu)).sum()) / (1 + len(pl)))
    mde = {f"k={k}": round(float((norm.ppf(1 - 0.025 / k) + Z80) * sd), 4) for k in range(1, 9)}
    return {"sd_fechas_reales": round(sd, 4), "sd_ponderando_eventos": round(sd_ev, 4),
            "sd_placebo_media": round(float(np.mean(sd_pl)), 4) if sd_pl else None,
            "mde": mde, "efecto_plausible": c["efecto"],
            "potencia_normal_k1": round(float(norm.cdf(c["efecto"] / sd - norm.ppf(0.975))), 3),
            "tamaño_empirico_z_placebo": round(float(np.mean(rech0)), 3) if rech0 else None,
            "potencia_sim_z_placebo_k1": round(float(np.mean(rech1)), 3) if rech1 else None,
            "frac_p_rango_menor_005_sin_efecto": round(float(np.mean(np.array(rangos) <= 0.05)), 3) if rangos else None,
            "desplazamientos": len(ks)}


def regla_familia(pot: dict) -> dict:
    """§5 del prerregistro: k* = mayor k (≤ MAX_FAMILIA) tal que al menos k candidatos tienen MDE con Holm-k ≤ su efecto
    plausible; entran esos (si sobran, los primeros por prioridad). El resto, descriptivo."""
    k_opt, elegidos = 0, []
    for k in range(1, MAX_FAMILIA + 1):
        pasan = [c for c in CANDIDATOS if pot[c]["mde"][f"k={k}"] <= CANDIDATOS[c]["efecto"]]
        if len(pasan) >= k:
            k_opt, elegidos = k, pasan[:k]
    return {"k": k_opt, "familia": elegidos, "descriptivos": [c for c in CANDIDATOS if c not in elegidos]}


# ---------------------------------------------------------------- EE. UU. mensual (secundario, sin potencia): recuentos
def eeuu_mensual(usrec: pd.Series) -> dict:
    m = pd.read_parquet(db.DATA_ROOT / "intl" / "panel_mensual_dev.parquet").loc["USA"]
    ini = max(m[c].dropna().index.min() for c in ("r_bolsa_tr", "r_bono", "r_letra"))
    picos = [d - pd.offsets.MonthBegin(1) for d in usrec.index[(usrec.diff() == 1).to_numpy()]]
    valles = [d - pd.offsets.MonthBegin(1) for d in usrec.index[(usrec.diff() == -1).to_numpy()]]
    ok = lambda d, a, b: d + pd.DateOffset(months=a) >= ini and d + pd.DateOffset(months=b) <= D.DEV_END  # noqa: E731
    x = (m["r_bolsa_tr"] - m["r_letra"]).dropna()          # incondicional (todos los meses), sin fechas de eventos
    sd16 = float(x.std() * np.sqrt(16))
    n = sum(ok(v, -12, 24) for v in valles)
    return {"datos_desde": str(ini.date()), "picos_ventana_completa": [str(p.date())[:7] for p in picos if ok(p, -12, 24)],
            "valles_ventana_completa": [str(v.date())[:7] for v in valles if ok(v, -12, 24)],
            "sd_exceso_bolsa_16_meses": round(sd16, 3),
            "mde_ingenuo_16m_eventos_independientes": round(float((norm.ppf(0.975) + Z80) * sd16 / np.sqrt(max(n, 1))), 3)}


def main() -> None:
    prueba = "--prueba" in sys.argv
    proc = procedencia(exigir_limpio=not prueba)
    n_sd, n_cal = (200, 20) if prueba else (2000, 300)
    rng = np.random.default_rng(SEMILLA)
    con = D.connect()
    anual = P.anual(con)
    usrec = D.load_dev(con, "USREC")
    con.close()
    rec = eventos_recesion(pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet"))
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    inf = eventos_inflacion(et)
    inf_nf = eventos_inflacion(et, sin_frontera=True)

    x = panel_log(anual)                                     # (iii): solo se usa para incondicionales y máscaras
    stats = {k: estadisticos_incondicionales(v) for k, v in x.items()}
    mascaras = {k: np.isfinite(v) for k, v in x.items()}
    del x                                                    # a partir de aquí no queda ninguna rentabilidad real

    res = {"procedencia": proc, "prueba": prueba, "simulaciones": {"sd": n_sd, "calibracion": n_cal}, "semilla": SEMILLA,
           "f_pub": F_PUB, "nucleo": NUCLEO,
           "eventos": {"recesiones": int(len(rec)), "financieras": int(rec.fin.sum()),
                       "años_pico_distintos": int(rec.pico.nunique()), "años_valle_distintos": int(rec.valle.nunique()),
                       "duracion_media": round(float((rec.valle - rec.pico).mean()), 2),
                       "entradas_inflacion_alta": int(len(inf)), "entradas_inflacion_alta_sin_frontera": int(len(inf_nf)),
                       "recesiones_desde_1950": int((rec.pico >= 1950).sum())},
           "incondicional": {k: {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in s.items()}
                             for k, s in stats.items()},
           "muestras": {}}
    for muestra in ("principal", "sin_guerras", "1950_2004"):
        pot, cnt = {}, {}
        for nombre, c in CANDIDATOS.items():
            ev = seleccionar(nombre, rec, inf, muestra)
            cnt[nombre] = recuentos(nombre, ev, mascaras[c["serie"]])
            pot[nombre] = potencia(nombre, ev, stats[c["serie"]], mascaras[c["serie"]], n_sd,
                                   n_cal if muestra == "principal" else 0, rng)
            print(muestra, nombre, cnt[nombre]["eventos"], pot[nombre]["sd_fechas_reales"], pot[nombre]["mde"]["k=1"],
                  pot[nombre]["mde"]["k=4"], pot[nombre]["tamaño_empirico_z_placebo"], flush=True)
        res["muestras"][muestra] = {"recuentos": cnt, "potencia": pot, "regla_familia": regla_familia(pot)}
    # colas gruesas (t de Student, 4 gl), solo SD/MDE de la muestra principal
    colas = {}
    for nombre, c in CANDIDATOS.items():
        ev = seleccionar(nombre, rec, inf, "principal")
        colas[nombre] = potencia(nombre, ev, stats[c["serie"]], mascaras[c["serie"]], n_sd // 2, 0, rng, gl=4)["mde"]
    res["colas_t4_mde"] = colas
    res["eeuu_mensual"] = eeuu_mensual(usrec)
    print(json.dumps({m: v["regla_familia"] for m, v in res["muestras"].items()}, indent=1, ensure_ascii=False))
    print(json.dumps(res["eeuu_mensual"], indent=1, ensure_ascii=False))
    if not prueba:
        (REPO / "research" / "int" / "int3d_potencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
