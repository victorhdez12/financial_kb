"""E1 (borrador): potencia de "logit de actividad frente a logit de curva" para la ENTRADA en recesión a 12 meses
(OCDE mensual), ANTES de escribir el prerregistro definitivo y SIN ninguna corrida sobre resultados
(docs/int/E1_prerregistro_v0.md).

Qué usa (y nada más), en partes que NUNCA cruzan un indicador con el objetivo:
  (i)   DESARROLLO ≤ 2004 (solo estructura): filas en riesgo y eventos del objetivo E1-12 de INT-13 (fechado trimestral
        del termómetro sobre el PIB OCDE) y la DISPONIBILIDAD de las columnas de cada modelo (máscara de casos
        completos). Ningún valor de un indicador se usa junto al objetivo.
  (ii)  CALIBRACIÓN del ruido con una cifra YA PUBLICADA: el IC de ΔAUC de INT-13 (P3 actividad frente a la base, E1-12,
        V1: +0,167 [+0,100; +0,226] → error típico ≈ 0,032). Se elige el (ρ, r) de la simulación que reproduce ese error
        típico en la estructura de desarrollo (como INT-10 con INT-4-ML).
  (iii) BLOQUEADO 2005-2024 SIN LEERLO: estructuras de eventos SUPUESTAS (de memoria, historia pública: Gran Recesión,
        crisis del euro, 2020, 2023) en escenarios pesimista / central / con 2020. NO se lee ninguna serie con fecha
        ≥ 2005 (ni el PIB, ni su disponibilidad). Si el usuario lo aprueba, un paso aparte contaría los eventos reales
        leyendo SOLO el PIB (como P-EVAL-INT4).
  (iv)  EN VIVO: MDE en función del número de episodios nuevos (estructuras sintéticas; ≈ 3,6 episodios por década).
Puntuaciones SIMULADAS binormales (s | y ~ N(μ·y, 1), AUC = Φ(μ/√2)) con ruido AR(1) en el tiempo y un componente común
entre países; modelo y listón con ruido correlacionado r. Probabilidades "congeladas" bien calibradas para la tasa de
desarrollo (para Δlog-loss). ΔAUC con error típico agrupado por bloques de 24 meses (DeLong agrupado) y valor crítico
nominal y empírico (de la nula simulada).

Uso: .venv/bin/python -m scripts.e1_potencia            (con puerta: árbol limpio; escribe research/int/e1_potencia.json)
     .venv/bin/python -m scripts.e1_potencia --prueba   (sin puerta; pocas réplicas; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/e1_potencia.json"
SEMILLA = 20261104
BLOQUE = 24
PHI = 0.95                       # AR(1) mensual del ruido (INT-8: mediana de curva, bolsa, paro 0,95-0,96)
A0 = 0.661                       # AUC del listón (logit de curva) en INT-13 E1-12, V1 (V2: 0,66)
A1_DEV = 0.828                   # AUC del paquete de actividad (XGBoost) en INT-13 E1-12, V1
EE_PUBLICADO = (0.226 - 0.100) / (2 * 1.96)   # 0,032: IC 95 % publicado de ΔAUC P3 frente a base (INT-13)
PI_DEV = 380 / 5232              # tasa de desarrollo (probabilidades congeladas)
DELTAS = (0.0, 0.04, 0.08, 0.12, 0.167, 0.20, 0.25, 0.30)
LISTON = ["curva", "d12_corto"]
ACT = {"A_ip_conf": ["ip_yoy", "confianza_emp"],                       # recomendado (cobertura)
       "A_ip_paro_conf": ["ip_yoy", "paro_d12", "confianza_emp"],      # alternativa (paro: poca historia)
       "A_conf": ["confianza_emp"]}
PAISES_BLOQ = ["BEL", "CAN", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "IRL", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE",
               "USA"]                                                   # 16 con IP (AUS y CHE sin IP en el warehouse)
ORIG_BLOQ = ("2005-01", "2023-12")                                      # objetivo acaba ≤ 2024-12
EXCL_2020 = ("2019-01", "2021-06")                                      # orígenes cuya ventana toca la pandemia
TAUS = (0.0, 0.4, 0.6, 0.8)          # dt del desplazamiento por episodio (unidades de μ; 0,4 ≈ dt 0,11 de ΔAUC por episodio)
TAU_CENTRAL = 0.4


def _r(x, k=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


# ================================================================ (i) estructura de desarrollo (≤ 2004)
def estructura_dev() -> dict:
    """Filas en riesgo de E1-12 (INT-13) y máscaras de casos completos. Solo (país, mes, y) y disponibilidad."""
    from scripts.int13_corrida import cargar_real
    from src.intl import int13 as M
    df = M.construir(cargar_real())
    if df.fecha.max() > M.FIN_DEV:
        raise SystemExit("dato posterior a 2004")
    s = M.muestra(df, "E1_12")
    out = {"base_int13": s[["pais", "fecha", "y_E1_12"]].rename(columns={"y_E1_12": "y"})}
    for k, cols in ACT.items():
        ok = s[cols].notna().all(axis=1)
        out[k] = s.loc[ok, ["pais", "fecha", "y_E1_12"]].rename(columns={"y_E1_12": "y"})
    return {k: v.assign(m=pd.PeriodIndex(v.fecha, freq="M")).drop(columns="fecha").reset_index(drop=True)
            for k, v in out.items()}


def episodios(df: pd.DataFrame, gap: int = 6) -> int:
    """Entradas (último mes con y = 1 antes de la entrada ≈ mes de entrada − 1) agrupadas: ≤ gap meses = mismo
    episodio. Se usa el primer mes positivo de cada racha + 12 como fecha aproximada de entrada."""
    ent = []
    for _, g in df.sort_values("m").groupby("pais"):
        pos = g.loc[g.y == 1, "m"]
        if pos.empty:
            continue
        o = pos.map(lambda p: p.ordinal).to_numpy()
        ini = o[np.r_[True, np.diff(o) > 1]]
        ent += list(ini + 12)
    ent = np.sort(ent)
    return int(1 + (np.diff(ent) > gap).sum()) if len(ent) else 0


def resumen(df: pd.DataFrame) -> dict:
    return {"filas": int(len(df)), "eventos": int(df.y.sum()), "meses_con_evento": int(df.loc[df.y == 1, "m"].nunique()),
            "paises": int(df.pais.nunique()), "episodios_aprox": episodios(df),
            "desde": str(df.m.min()), "hasta": str(df.m.max())}


# ================================================================ (iii)-(iv) estructuras supuestas / sintéticas
def filas_desde_episodios(eps: list, paises: list, desde: str, hasta: str, excluir: tuple | None = None) -> pd.DataFrame:
    """eps: [(mes de entrada 'AAAA-MM' (último mes del trimestre de entrada), [países], duración en meses)].
    Recesión = desde el primer mes del trimestre de entrada durante `dur` meses (fuera del conjunto en riesgo).
    y = 1 si hay una entrada en (M, M + 12]."""
    meses = pd.period_range(desde, hasta, freq="M")
    filas = []
    for c in paises:
        rec, ent = set(), []
        for e, cs, dur in eps:
            if c not in cs:
                continue
            pe = pd.Period(e, "M")
            ent.append(pe.ordinal)
            rec |= {pe.ordinal - 2 + k for k in range(dur)}
        ent = np.array(ent)
        for m in meses:
            o = m.ordinal
            if o in rec:
                continue
            if excluir and pd.Period(excluir[0], "M") <= m <= pd.Period(excluir[1], "M"):
                continue
            y = int(len(ent) > 0 and np.any((ent > o) & (ent <= o + 12)))
            filas.append((c, m, y))
    return pd.DataFrame(filas, columns=["pais", "m", "y"])


def escenarios_bloqueado() -> dict:
    """SUPUESTOS (de memoria; ninguna serie ≥ 2005 leída). Fechado: entra en el trimestre de la 2.ª caída seguida de la
    suma de 4 trimestres (≈ 2.º trimestre seguido con PIB interanual < 0)."""
    p = PAISES_BLOQ
    gr_pronto = ["DNK", "IRL", "ITA", "JPN", "SWE"]
    gr = [("2008-12", gr_pronto, 15), ("2009-03", [c for c in p if c not in gr_pronto], 15)]
    ez6 = [("2011-12", ["PRT"], 21), ("2012-06", ["ITA", "ESP"], 18), ("2012-09", ["NLD"], 12),
           ("2012-12", ["FIN"], 15), ("2013-03", ["BEL"], 6)]
    ez4 = [("2011-12", ["PRT"], 21), ("2012-06", ["ITA", "ESP"], 18), ("2012-09", ["NLD"], 12)]
    e23 = [("2023-09", ["DEU", "SWE", "FIN"], 12)]
    covid = [("2020-09", [c for c in p if c != "IRL"], 9)]
    d, h = ORIG_BLOQ
    return {
        "B_pesimista_sin2020": filas_desde_episodios(gr + ez4, p, d, h, EXCL_2020),
        "B_central_sin2020": filas_desde_episodios(gr + ez6 + e23, p, d, h, EXCL_2020),
        "B_central_con2020": filas_desde_episodios(gr + ez6 + e23 + covid, p, d, h),
        "B_solo_GR": filas_desde_episodios(gr, p, d, h, EXCL_2020),
    }


def estructura_sintetica(rng, k: int, paises: list, frac: float = 0.6, por_decada: float = 3.6) -> pd.DataFrame:
    """k episodios repartidos al azar en k / (por_decada/10) años; cada uno toca una fracción `frac` de los países con
    entradas dispersas ± 4 meses y duración 9-21 meses."""
    años = max(int(np.ceil(k / por_decada * 10)), 4)
    ini = pd.Period("2030-01", "M")
    n = años * 12
    centros = np.sort(rng.choice(np.arange(18, n - 6), k, replace=False))
    eps = []
    for ce in centros:
        cs = list(rng.choice(paises, max(1, int(round(frac * len(paises)))), replace=False))
        for c in cs:
            m = ini + int(ce + rng.integers(-4, 5))
            eps.append((str(m), [c], int(rng.integers(9, 22))))
    return filas_desde_episodios(eps, paises, str(ini), str(ini + n - 1)), años


# ================================================================ simulación
def matriz(df: pd.DataFrame):
    """(y, índice de mes, índice de país, bloque de 24 meses, episodio de cada fila positiva o −1). Episodio = racha de
    meses con algún positivo (de cualquier país) sin huecos de más de 6 meses."""
    o = df.m.map(lambda p: p.ordinal).to_numpy()
    im = o - o.min()
    ic = pd.Index(sorted(df.pais.unique())).get_indexer(df.pais)
    y = df.y.to_numpy(int)
    mp = np.unique(im[y == 1])
    ide = np.cumsum(np.r_[0, np.diff(mp) > 6])
    ep = np.full(len(y), -1)
    ep[y == 1] = ide[np.searchsorted(mp, im[y == 1])]
    return y, im, ic, im // BLOQUE, ep


def _ar1(rng, nt: int, k: int, phi: float) -> np.ndarray:
    e = rng.standard_normal((nt, k))
    out = np.empty_like(e)
    out[0] = e[0]
    s = np.sqrt(1 - phi ** 2)
    for t in range(1, nt):
        out[t] = phi * out[t - 1] + s * e[t]
    return out


def ruido(rng, nt, npais, rho):
    return np.sqrt(rho) * _ar1(rng, nt, 1, PHI) + np.sqrt(1 - rho) * _ar1(rng, nt, npais, PHI)


def influencia_auc(s, y):
    pos, neg = s[y == 1], s[y == 0]
    n1, n0 = len(pos), len(neg)
    ns, ps = np.sort(neg), np.sort(pos)
    v10 = (np.searchsorted(ns, pos, "left") + np.searchsorted(ns, pos, "right")) / (2 * n0)
    v01 = 1 - (np.searchsorted(ps, neg, "left") + np.searchsorted(ps, neg, "right")) / (2 * n1)
    a = float(v10.mean())
    infl = np.empty(len(s))
    infl[y == 1] = (v10 - a) / n1
    infl[y == 0] = (v01 - a) / n0
    return a, infl


def mu_de(a):
    return np.sqrt(2) * norm.ppf(a)


def prob(s, mu):
    """Probabilidad bien calibrada para la tasa de desarrollo (modelo congelado): logit p = logit π + μ s − μ²/2."""
    z = np.log(PI_DEV / (1 - PI_DEV)) + mu * s - mu ** 2 / 2
    return 1 / (1 + np.exp(-z))


def ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def una(rng, y, im, ic, bl, ep, a0, a1, rho, r, tau):
    nt, npais = im.max() + 1, ic.max() + 1
    em = ruido(rng, nt, npais, rho)[im, ic]
    ex = ruido(rng, nt, npais, rho)[im, ic]
    eb = r * em + np.sqrt(1 - r ** 2) * ex
    m1, m0 = mu_de(a1), mu_de(a0)
    # heterogeneidad del efecto entre episodios: desplazamiento común a todos los positivos de un episodio (N(0, τ))
    d_ep = rng.normal(0.0, tau, ep.max() + 2)[ep] * (y == 1) if tau > 0 else 0.0
    sm, sb = m1 * y + d_ep + em, m0 * y + eb
    am, iM = influencia_auc(sm, y)
    ab, iB = influencia_auc(sb, y)
    g = np.bincount(bl, weights=iM - iB)
    nb = (np.bincount(bl) > 0).sum()
    ee = float(np.sqrt((g ** 2).sum() * nb / max(nb - 1, 1)))
    dll = ll(y, prob(sm, m1)) - ll(y, prob(sb, m0))
    return am - ab, ee, dll


def simular(df, a0, deltas, rho, r, tau, reps, rng) -> dict:
    y, im, ic, bl, ep = matriz(df)
    res = {}
    for d in deltas:
        v = np.array([una(rng, y, im, ic, bl, ep, a0, a0 + d, rho, r, tau) for _ in range(reps)])
        res[d] = v
    z0 = res[0.0][:, 0] / res[0.0][:, 1]
    c_emp = float(np.quantile(z0, 0.95))
    out = {"rho": rho, "r": r, "tau": tau, "episodios_sim": int(ep.max() + 1), "bloques_24m": int(len(np.unique(bl))), "bloques_con_evento": int(len(np.unique(bl[y == 1]))),
           "z_critico_empirico_unilateral_5": _r(c_emp),
           "tamaño_real_z_nominal_1645": _r(np.mean(z0 > norm.ppf(0.95))), "por_delta": {}}
    for d in deltas:
        v = res[d]
        z = v[:, 0] / v[:, 1]
        out["por_delta"][f"{d:.3f}"] = {
            "pot_z_nominal": _r(np.mean(z > norm.ppf(0.95))), "pot_z_empirico": _r(np.mean(z > c_emp)),
            "pot_signo_dAUC": _r(np.mean(v[:, 0] > 0)), "pot_dLL_neg": _r(np.mean(v[:, 2] < 0)),
            "pot_signo_y_dLL": _r(np.mean((v[:, 0] > 0) & (v[:, 2] < 0))),
            "sd_dAUC": _r(np.std(v[:, 0]), 4), "media_ee_agrupado": _r(np.mean(v[:, 1]), 4),
            "media_dLL": _r(np.mean(v[:, 2]), 4)}
    for k in ("pot_z_empirico", "pot_z_nominal"):
        xs = [(d, out["por_delta"][f"{d:.3f}"][k]) for d in deltas]
        mde = f"> {deltas[-1]:.2f}"
        for (d0, p0), (d1, p1) in zip(xs, xs[1:]):
            if p0 < 0.8 <= p1:
                mde = _r(d0 + (0.8 - p0) * (d1 - d0) / (p1 - p0))
                break
        out[f"mde80_{k.replace('pot_', '')}"] = mde
    return out


# ================================================================ main
def main() -> None:
    prueba = "--prueba" in sys.argv
    proc = procedencia(exigir_limpio=not prueba)
    if not prueba and SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: una sola ejecución con puerta")
    reps = 40 if prueba else 600
    rng = np.random.default_rng(SEMILLA)
    t0 = time.time()
    res: dict = {"procedencia": proc, "documento": "docs/int/E1_prerregistro_v0.md",
                 "supuestos": {"phi": PHI, "A0_liston": A0, "A1_dev_int13": A1_DEV, "ee_publicado_int13": _r(EE_PUBLICADO, 4),
                               "pi_dev": _r(PI_DEV, 4), "bloque_meses": BLOQUE, "reps": reps,
                               "nota": "bloqueado: estructuras SUPUESTAS; ninguna serie ≥ 2005 leída"}}
    # (i)
    dev = estructura_dev()
    res["desarrollo"] = {k: resumen(v) for k, v in dev.items()}
    print("desarrollo:", res["desarrollo"], flush=True)
    # (ii) calibración con la cifra publicada (estructura de INT-13, Δ = A1_DEV − A0): para cada τ (heterogeneidad del
    # efecto entre episodios) se elige el (ρ, r) que reproduce el error típico publicado; si ninguno se acerca (±20 %),
    # ese τ no es compatible con INT-13.
    y, im, ic, bl, ep = matriz(dev["base_int13"])
    cal, elegidos = {}, {}
    for tau in TAUS:
        cal[str(tau)] = {}
        for rho in (0.0, 0.15, 0.3, 0.6):
            for r in (0.5, 0.8, 0.9):
                v = np.array([una(rng, y, im, ic, bl, ep, A0, A1_DEV, rho, r, tau) for _ in range(max(reps // 4, 30))])
                cal[str(tau)][f"rho{rho}_r{r}"] = {"sd_dAUC": _r(np.std(v[:, 0]), 4), "media_ee": _r(np.mean(v[:, 1]), 4)}
        k = min(cal[str(tau)], key=lambda q: abs(cal[str(tau)][q]["sd_dAUC"] - EE_PUBLICADO))
        sd = cal[str(tau)][k]["sd_dAUC"]
        elegidos[str(tau)] = {"elegido": k, "rho": float(k.split("_")[0][3:]), "r": float(k.split("_")[1][1:]),
                              "sd_dAUC": sd, "compatible_int13": bool(abs(sd / EE_PUBLICADO - 1) <= 0.2)}
    res["calibracion"] = {"objetivo_ee": _r(EE_PUBLICADO, 4), "episodios_dev_sim": int(ep.max() + 1),
                          "rejilla": cal, "elegidos": elegidos}
    print("calibración:", elegidos, flush=True)
    taus = [t for t in TAUS if elegidos[str(t)]["compatible_int13"]] or [TAUS[0]]
    pc = lambda t: (elegidos[str(t)]["rho"], elegidos[str(t)]["r"])  # noqa: E731
    tc = TAU_CENTRAL if TAU_CENTRAL in taus else taus[-1]
    res["tau_central"] = tc
    res["taus_compatibles"] = taus
    # referencia: desarrollo con el modelo recomendado (cuánta potencia tenía ≤ 2004, LOCO aparte)
    res["potencia_dev_A_ip_conf"] = simular(dev["A_ip_conf"], A0, DELTAS, *pc(tc), tc, reps // 2, rng)
    # (iii) bloqueado supuesto
    res["bloqueado"] = {}
    esc = escenarios_bloqueado()
    for nom, df in esc.items():
        res["bloqueado"][nom] = {"estructura": resumen(df)}
        for t in taus:
            res["bloqueado"][nom][f"tau{t}"] = simular(df, A0, DELTAS, *pc(t), t, reps, rng)
            print(nom, res["bloqueado"][nom]["estructura"]["eventos"], t,
                  res["bloqueado"][nom][f"tau{t}"]["mde80_z_empirico"], flush=True)
    res["bloqueado_A0_0.60_central"] = simular(esc["B_central_sin2020"], 0.60, DELTAS, *pc(tc), tc, reps, rng)
    # (iv) en vivo: MDE frente a número de episodios nuevos (τ central)
    vivo = {}
    for k in (3, 5, 8, 12, 16, 24):
        sims = []
        for _ in range(3 if prueba else 6):
            df, años = estructura_sintetica(rng, k, PAISES_BLOQ)
            sims.append(simular(df, A0, DELTAS, *pc(tc), tc, max(reps // 5, 20), rng))
        pot = {d: float(np.mean([s["por_delta"][f"{d:.3f}"]["pot_z_empirico"] for s in sims])) for d in DELTAS}
        mde = f"> {DELTAS[-1]:.2f}"
        xs = list(pot.items())
        for (d0, p0), (d1, p1) in zip(xs, xs[1:]):
            if p0 < 0.8 <= p1:
                mde = _r(d0 + (0.8 - p0) * (d1 - d0) / (p1 - p0))
                break
        vivo[str(k)] = {"años_aprox": años, "mde80_z_empirico": mde,
                        "pot_dev_0.167": _r(pot[0.167]), "pot_mitad_0.08": _r(pot[0.08])}
        print("vivo", k, vivo[str(k)], flush=True)
    res["vivo_por_episodios"] = vivo
    res["segundos"] = round(time.time() - t0, 1)
    if prueba:
        print(json.dumps(res, ensure_ascii=False, indent=1, default=str)[:3000])
        return
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("escrito", SALIDA)


if __name__ == "__main__":
    main()
