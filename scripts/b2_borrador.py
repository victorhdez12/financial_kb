"""BORRADOR de B2 «compra en caídas» (docs/factors/B2_spec_borrador.md). NO ES VALIDACIÓN.

Qué hace (solo datos ≤ 2004, vía src/factors/data.py; el periodo bloqueado ≥ 2005 no se toca):
1. Calibra el umbral X con la regla fijada ANTES de mirar (spec §3): X = −(percentil 20 de la caída desde el máximo de
   12 cierres de mes de la RV en EUR, 1963-07 … 2004-12), redondeado a 0,1 pp. Solo propiedad de la señal.
2. Propiedades de la señal (% de meses en COMPRA, cambios al año) con X y, como referencia, con los percentiles 10 y 30
   (sin rentabilidades: para ver la sensibilidad sin elegir por resultados).
3. Comportamiento en desarrollo 1975-01 … 2004-12 de B0, B1 (regla en vivo: σ* = 17,02 % congelado) y B2 con las
   métricas del informe 5f + caídas por episodio. Rotulado como NO validación: el mismo periodo sirve para calibrar.
4. Potencia: años de paper trading que harían falta para distinguir B2 de B1 (y de B0) en rentabilidad media, analítico
   y por bootstrap de bloques de 12 meses.
5. Prueba de estrés 1927-1962 en USD (RV + letras, sin oro ni RF en EUR): caídas que siguen (1929-32).

No escribe nada en el repositorio, no registra, no congela. Uso: .venv/bin/python -m scripts.b2_borrador [--json]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ regla (pura; tests en tests/test_b2_borrador.py)
NORMAL = {"rv": 0.70, "rf": 0.15, "oro": 0.15}       # = B0
COMPRA = {"rv": 0.80, "rf": 0.05, "oro": 0.15}       # +10 pp de RV, salen de la RF; oro fijo
VENTANA_MAX = 12                                     # máximo de los últimos 12 cierres de mes (incluido t)
PERCENTIL = 0.20                                     # regla de calibración fijada a priori
SALIDA_FRAC = 0.5                                    # sale cuando la caída se recupera a −X/2 (histéresis fija)
CALIB = ("1963-07", "2004-12")
PUNTUA = ("1975-01", "2004-12")
SIGMA_STAR_B1, RV_MIN_B1, UMBRAL_B1 = 0.1702, 0.55, 0.025


def caida_desde_maximo(nivel: pd.Series, ventana: int = VENTANA_MAX) -> pd.Series:
    """DD_t = P_t / max(P_{t−ventana+1} … P_t) − 1 con cierres de mes (≤ 0). NaN hasta tener `ventana` cierres."""
    return nivel / nivel.rolling(ventana, min_periods=ventana).max() - 1


def calibrar_umbral(dd: pd.Series, percentil: float = PERCENTIL) -> float:
    """X > 0 = −percentil de DD (incluidos los meses en máximo, DD = 0), redondeado a 0,1 pp."""
    x = -float(np.nanquantile(dd.dropna().to_numpy(), percentil))
    if x <= 0:
        raise ValueError("el percentil no da una caída: revisa la serie")
    return round(x, 3)


def estado_compra(dd: pd.Series, x: float, salida_frac: float = SALIDA_FRAC, inicial: bool = False) -> pd.Series:
    """True = COMPRA. Entra al cierre de t si DD_t ≤ −X; sale si DD_t ≥ −X·salida_frac; si no, mantiene.
    Sin dato (NaN) mantiene el estado (en vivo: falla cerrado antes de llegar aquí)."""
    out, cur = [], inicial
    for v in dd:
        if not np.isnan(v):
            if not cur and v <= -x + 1e-12:
                cur = True
            elif cur and v >= -x * salida_frac - 1e-12:
                cur = False
        out.append(cur)
    return pd.Series(out, index=dd.index, dtype=bool)


def pesos_b2(compra: bool) -> dict:
    return dict(COMPRA if compra else NORMAL)


def decision_b2(nivel_cierres: pd.Series, x: float, previo: bool) -> dict:
    """Decisión de UN cierre de mes (como sería en vivo): `nivel_cierres` = los últimos ≥ 12 cierres de mes (el último es
    t); `previo` = estado registrado el mes anterior. Falla cerrado si faltan cierres."""
    s = nivel_cierres.dropna()
    if len(s) < VENTANA_MAX:
        raise RuntimeError(f"solo {len(s)} cierres de mes: hacen falta {VENTANA_MAX}")
    dd = float(s.iloc[-1] / s.iloc[-VENTANA_MAX:].max() - 1)
    est = bool(estado_compra(pd.Series([dd]), x, inicial=previo).iloc[0])
    return {"dd_12m": round(dd, 5), "umbral": x, "compra": est, "cambio": est != previo, "pesos": pesos_b2(est)}


def objetivo_b2(estado: pd.Series) -> pd.DataFrame:
    return pd.DataFrame([pesos_b2(e) for e in estado], index=estado.index)[["rv", "rf", "oro"]]


def objetivo_b1_vivo(rv_eur: pd.Series, idx) -> pd.DataFrame:
    """B1 tal como corre en vivo (src/paper/live.py): σ̂ 12 m, σ* = 17,02 % congelado, RV en [55 %, 70 %], umbral 2,5 pp."""
    sig = rv_eur.rolling(12).std() * np.sqrt(12)
    cur, filas = NORMAL["rv"], []
    for t in idx:
        s = sig.get(t, np.nan)
        if not np.isnan(s):
            bruta = float(np.clip(NORMAL["rv"] * min(1.0, SIGMA_STAR_B1 / s), RV_MIN_B1, NORMAL["rv"]))
            if abs(bruta - cur) >= UMBRAL_B1 - 1e-12:
                cur = bruta
        filas.append({"rv": cur, "rf": 1 - NORMAL["oro"] - cur, "oro": NORMAL["oro"]})
    return pd.DataFrame(filas, index=idx)[["rv", "rf", "oro"]]


def propiedades_senal(estado: pd.Series) -> dict:
    e = estado.astype(int)
    entradas = int(((e == 1) & (e.shift(1, fill_value=0) == 0)).sum())
    rachas = e.groupby((e != e.shift()).cumsum()).sum()
    return {"pct_meses_compra": round(float(e.mean()), 3), "entradas": entradas,
            "cambios_al_año": round(float((e != e.shift()).iloc[1:].sum()) / (len(e) / 12), 2),
            "duracion_media_compra_meses": round(float(rachas[rachas > 0].mean()), 1) if entradas else None}


# ------------------------------------------------------------------ potencia
def anios_para_distinguir(mu_anual: float, te_anual: float, z_a: float = 1.645, z_b: float = 0.8416) -> float:
    """Años de datos mensuales i.i.d. para detectar una diferencia media anual `mu` con error de seguimiento `te`
    (contraste unilateral al 5 %, potencia 80 %): T = ((z_a + z_b) · te / mu)²."""
    if mu_anual == 0:
        return float("inf")
    return float(((z_a + z_b) * te_anual / abs(mu_anual)) ** 2)


def potencia_bootstrap(d: pd.Series, anios: int, n: int = 4000, bloque: int = 12, mu_objetivo: float | None = None,
                       semilla: int = 20261118) -> float:
    """Fracción de remuestreos (bloques móviles de 12 meses de la diferencia mensual `d`) de `anios` años en los que la
    media es > 0 con t unilateral al 5 %. `mu_objetivo` (anual) recentra la media de `d` (None = la observada)."""
    x = d.dropna().to_numpy().copy()
    if mu_objetivo is not None:
        x = x - x.mean() + mu_objetivo / 12
    rng = np.random.default_rng(semilla)
    T = anios * 12
    nb = int(np.ceil(T / bloque))
    ok = 0
    for _ in range(n):
        st = rng.integers(0, len(x) - bloque + 1, nb)
        m = x[(st[:, None] + np.arange(bloque)).ravel()[:T]]
        t = m.mean() / (m.std(ddof=1) / np.sqrt(T))
        ok += t > 1.645
    return float(ok / n)


# ------------------------------------------------------------------ datos (≤ 2004)
def _per(s: pd.Series) -> pd.Series:
    s = s.copy(); s.index = s.index.to_period("M"); return s[~s.index.duplicated(keep="last")]


def datos(con) -> dict:
    from src.factors import data as F
    rv_usd = _per((F.load_dev(con, "ff_mkt_rf_m") + F.load_dev(con, "ff_rf_m")) / 100)
    rf_usd_letra = _per(F.load_dev(con, "ff_rf_m") / 100)
    fin = lambda s: s.groupby(s.index.to_period("M")).last()                       # noqa: E731
    dem = fin(F.load_dev(con, "bundesbank_usd_dem_d")) / 1.95583                    # EUR por USD
    ecb = 1 / fin(F.load_dev(con, "ecb_eurusd_d"))
    fx = pd.concat([dem[dem.index < pd.Period("1999-01", "M")], ecb[ecb.index >= pd.Period("1999-01", "M")]])
    rv_eur = ((1 + rv_usd) * (fx / fx.shift(1)).reindex(rv_usd.index) - 1).dropna()    # misma medida que σ* de B1
    y5 = _per(F.load_dev(con, "bundesbank_bund_zero_5y_m"))
    rf_eur = y5.shift(1) / 1200 - 5 * (y5 - y5.shift(1)) / 100
    oro_eur = _per(F.gold_eur_dev(con)).pct_change()
    caja_eur = _per(F.load_dev(con, "oecd_ir3m_deu")).shift(1) / 1200
    for s in (rv_eur, rf_eur, oro_eur, caja_eur):
        F.check(s.to_timestamp())
    return dict(rv_usd=rv_usd, letra_usd=rf_usd_letra, rv_eur=rv_eur, rf_eur=rf_eur, oro_eur=oro_eur, caja_eur=caja_eur)


def _metricas5f(res, caja, B) -> dict:
    m = B.metricas(res, caja)
    r = res.neto
    return {"rent_anual": round(m["rent_anual"], 4), "rent_acumulada": round(float((1 + r).prod() - 1), 3),
            "vol_anual": round(m["vol_anual"], 4), "caida_max": round(m["caida_max"], 4),
            "cvar5_mensual": round(m["cvar5_mensual"], 4), "sharpe_anual": round(m["sharpe_anual"], 3),
            "rotacion_anual": round(m["rotacion_anual"], 3), "costes_anual_pb": round(m["costes_anual"] * 1e4, 1),
            "caidas_episodio": {k: round(v, 4) for k, v in m["caidas_episodio"].items()},
            "rv_media": round(float(res.pesos["rv"].mean()), 3)}


def _ventana(r: pd.Series, a: str, b: str) -> float:
    return round(float((1 + r[(r.index >= pd.Period(a, "M")) & (r.index <= pd.Period(b, "M"))]).prod() - 1), 4)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--n-boot", type=int, default=4000)
    a = ap.parse_args()
    from src.factors import backtest as B
    from src.factors import data as F
    con = F.connect()
    d = datos(con)
    con.close()

    # 1. calibración (solo señal)
    nivel = (1 + d["rv_eur"]).cumprod()
    dd = caida_desde_maximo(nivel)
    dd_cal = dd[(dd.index >= pd.Period(CALIB[0], "M")) & (dd.index <= pd.Period(CALIB[1], "M"))]
    X = calibrar_umbral(dd_cal)
    # sensibilidad de la medida: precio en vez de total (dividendo constante aprox. 3 %/año restado; declarado)
    nivel_px = (1 + d["rv_eur"] - 0.03 / 12).cumprod()
    dd_px = caida_desde_maximo(nivel_px)
    X_px = calibrar_umbral(dd_px[dd_cal.index])

    # 2. propiedades de la señal
    props = {}
    for p in (0.10, PERCENTIL, 0.30):
        xp = calibrar_umbral(dd_cal, p)
        props[f"p{int(p * 100)}"] = {"umbral": xp, **propiedades_senal(estado_compra(dd_cal, xp))}
    props["p20_75_75"] = {"umbral": X, "salida": "en −X (sin histéresis)",
                          **propiedades_senal(estado_compra(dd_cal, X, salida_frac=1.0))}

    # 3. desarrollo 1975-2004 (NO validación)
    idx = pd.period_range(*PUNTUA, freq="M")
    r = pd.DataFrame({"rv": d["rv_eur"], "rf": d["rf_eur"], "oro": d["oro_eur"]}).reindex(idx)
    assert not r.isna().any().any()
    est = estado_compra(dd, X).reindex(idx)
    objs = {"B0": B.objetivo_fijo(idx, NORMAL), "B1": objetivo_b1_vivo(d["rv_eur"], idx), "B2": objetivo_b2(est)}
    res = {k: B.simular(r, o, pesos_base=NORMAL) for k, o in objs.items()}
    met = {k: _metricas5f(v, d["caja_eur"], B) for k, v in res.items()}
    tramos = {"2000-03 (caída que sigue)": ("2000-04", "2003-03"), "1987 (rebote rápido)": ("1987-09", "1988-12"),
              "1990": ("1990-07", "1991-06"), "1998": ("1998-07", "1999-06"), "2003-04 (recuperación)": ("2003-04", "2004-12")}
    por_tramo = {n: {k: _ventana(res[k].neto, *ab) for k in res} for n, ab in tramos.items()}
    # rentabilidad de la RV en los 12 meses siguientes a cada entrada en COMPRA (lo que la hipótesis espera > media)
    ent = est[(est) & (~est.shift(1, fill_value=False))].index
    fwd = [float((1 + d["rv_eur"][(d["rv_eur"].index > t) & (d["rv_eur"].index <= t + 12)]).prod() - 1) for t in ent]
    rv12 = (1 + d["rv_eur"].reindex(idx)).rolling(12).apply(np.prod, raw=True) - 1
    entradas = {"n": len(ent), "fechas": [str(t) for t in ent], "rv_12m_siguientes": [round(x, 3) for x in fwd],
                "media_12m_siguientes": round(float(np.mean(fwd)), 3) if fwd else None,
                "error_tipico_media": round(float(np.std(fwd, ddof=1) / np.sqrt(len(fwd))), 3) if len(fwd) > 1 else None,
                "media_incondicional_12m": round(float(rv12.dropna().mean()), 3)}

    # 4. potencia
    pot = {}
    for ref in ("B1", "B0"):
        dif = res["B2"].neto - res[ref].neto
        mu, te = float(dif.mean() * 12), float(dif.std(ddof=1) * np.sqrt(12))
        pot[f"B2_vs_{ref}"] = {
            "dif_media_anual_dev": round(mu, 4), "error_seguimiento_anual": round(te, 4),
            "anios_80pct_con_dif_dev": round(anios_para_distinguir(mu, te), 1),
            "anios_80pct_si_dif_0p5pp": round(anios_para_distinguir(0.005, te), 1),
            "anios_80pct_si_dif_1pp": round(anios_para_distinguir(0.01, te), 1),
            "potencia_bootstrap_dif_dev": {h: round(potencia_bootstrap(dif, h, a.n_boot), 3) for h in (3, 5, 10, 20, 30)},
            "potencia_bootstrap_dif_0p5pp": {h: round(potencia_bootstrap(dif, h, a.n_boot, mu_objetivo=0.005), 3)
                                             for h in (3, 5, 10, 20, 30)},
            "falso_positivo_si_dif_0": {h: round(potencia_bootstrap(dif, h, a.n_boot, mu_objetivo=0.0), 3)
                                         for h in (5, 30)},
        }
    vol_dif = float(met["B2"]["vol_anual"] - met["B1"]["vol_anual"])

    # 5. estrés 1927-1962 en USD: RV + letras (sin oro, sin RF en EUR, sin divisa). B0' 70/30, B2' 80/20.
    idx_s = pd.period_range("1927-07", "1962-12", freq="M")
    niv_u = (1 + d["rv_usd"]).cumprod()
    est_s = estado_compra(caida_desde_maximo(niv_u), X).reindex(idx_s)
    rs = pd.DataFrame({"rv": d["rv_usd"], "rf": d["letra_usd"], "oro": 0.0}).reindex(idx_s)
    base_s = {"rv": 0.70, "rf": 0.30, "oro": 0.0}
    comp_s = {"rv": 0.80, "rf": 0.20, "oro": 0.0}
    o0 = B.objetivo_fijo(idx_s, base_s)
    o2 = pd.DataFrame([comp_s if e else base_s for e in est_s], index=idx_s)[["rv", "rf", "oro"]]
    s0, s2 = B.simular(rs, o0, pesos_base=base_s), B.simular(rs, o2, pesos_base=base_s)
    estres = {"B0_70_30": {"caida_max": round(B.caida_max(s0.neto), 3), "1929-09_1932-06": _ventana(s0.neto, "1929-09", "1932-06"),
                           "1932-07_1937-02": _ventana(s0.neto, "1932-07", "1937-02"),
                           "rent_anual": round(float((1 + s0.neto).prod() ** (12 / len(idx_s)) - 1), 4)},
              "B2_80_20": {"caida_max": round(B.caida_max(s2.neto), 3), "1929-09_1932-06": _ventana(s2.neto, "1929-09", "1932-06"),
                           "1932-07_1937-02": _ventana(s2.neto, "1932-07", "1937-02"),
                           "rent_anual": round(float((1 + s2.neto).prod() ** (12 / len(idx_s)) - 1), 4)},
              "pct_meses_compra": round(float(est_s.mean()), 3)}

    out = {"AVISO": "BORRADOR, NO VALIDACIÓN: desarrollo ≤ 2004; el mismo periodo calibra y muestra. No registra nada.",
           "umbral_X": X, "umbral_X_sens_precio_aprox": X_px, "salida": f"DD ≥ −{X * SALIDA_FRAC:.3f}",
           "senal_1963_2004": props, "desarrollo_1975_2004": met, "por_tramo": por_tramo, "entradas_compra": entradas,
           "potencia": pot, "vol_B2_menos_B1": round(vol_dif, 4), "estres_1927_1962_usd": estres}
    if a.json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return
    print(out["AVISO"])
    print(f"\nUmbral X = {X:.1%} (P20 de DD 12 m, 1963-07…2004-12); salida en −{X * SALIDA_FRAC:.1%}. "
          f"Sensibilidad medida precio (≈ −3 %/año): {X_px:.1%}")
    print("\nSeñal (sin rentabilidades):")
    for k, v in props.items():
        print(f"  {k:10s} {v}")
    print("\nDesarrollo 1975-01…2004-12 (NO validación):")
    cols = ["rent_anual", "vol_anual", "caida_max", "cvar5_mensual", "sharpe_anual", "rotacion_anual", "costes_anual_pb", "rv_media"]
    print("  " + " ".join(f"{c:>15s}" for c in ["cartera"] + cols))
    for k, m in met.items():
        print("  " + f"{k:>15s}" + " ".join(f"{m[c]:>15}" for c in cols))
    for k, m in met.items():
        print(f"  episodios {k}: {m['caidas_episodio']}")
    print("\nPor tramo (rentabilidad acumulada):")
    for n, v in por_tramo.items():
        print(f"  {n:28s} {v}")
    print(f"\nEntradas en COMPRA: {entradas}")
    print("\nPotencia:")
    for k, v in pot.items():
        print(f"  {k}: {v}")
    print(f"\nEstrés 1927-1962 USD: {estres}")


if __name__ == "__main__":
    main()
