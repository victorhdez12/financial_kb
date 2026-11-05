"""INT-16 (borrador): potencia de "la prima por plazo a 10 años (ACM) frente a la pendiente de la curva" para la
rentabilidad en exceso del bono a 10 años de EE. UU. a 12 meses, ANTES de construir nada y SIN ninguna regresión
predictiva sobre datos reales (docs/int/INT16_prima_plazo_v0.md).

Qué usa de los datos reales ≤ 2004 (y nada más):
  (i)  dinámica de los PREDICTORES: VAR(1) mensual de (pendiente = GSW 10a − 1a, prima ACM 10a) 1971-08 … 2004-12,
       sus residuos y su correlación; para el bloque de bolsa (opcional), los cambios mensuales de la prima y del
       rendimiento neutral al riesgo ACM a 10 años 1961-06 … 2004-12;
  (ii) el SHOCK de rentabilidad mensual del bono a 10 años aproximado por −(119/12)·Δy10 (GSW), solo para conservar su
       correlación contemporánea con las innovaciones de los predictores (sesgo de Stambaugh) y su heterocedasticidad
       (1979-82). Se remuestrea por bloques de 12 meses junto con los residuos del VAR, así que su alineación con los
       predictores retardados es aleatoria: NINGÚN coeficiente predictivo real (β, R²) se estima ni se usa.
El tamaño del efecto (R² poblacional a 12 meses) es un PARÁMETRO de la simulación (rejilla), no una estimación.
Nada ≥ 2005 se lee: todo pasa por src/factors/data.load_dev (corte DEV_END, falla cerrado).

DGP: x_t = (s_t, p_t) VAR(1) con residuos reales remuestreados; z_t = w_s·s̃_t + w_p·p̃_t (estandarizados);
rx12_t = c·z_t + Σ_{k=1..12} u_{t+k} (solapamiento de 12 meses y Stambaugh por construcción). w = (cos θ, sin θ):
θ = 45° → misma precisión poblacional de "solo prima" y "solo pendiente" (nula del contraste no anidado);
θ = 0° → la prima no añade nada a la pendiente (nula del anidado). c se fija para un R² poblacional conjunto dado.
Previsión fuera de muestra con MCO de ventana creciente (en el origen t solo pares con s ≤ t − 12) frente a la media
histórica. Contrastes: (a) no anidado ΔR²_OS = (ECM_pend − ECM_prima)/ECM_media; (b) anidado Clark-West de
pendiente + prima frente a pendiente; valores críticos empíricos (nula simulada) y tamaño real de los nominales
(Diebold-Mariano / Clark-West con Newey-West de 12 retardos).

Uso: .venv/bin/python -m scripts.int16_potencia            (con puerta: árbol limpio; escribe research/int/int16_potencia.json)
     .venv/bin/python -m scripts.int16_potencia --prueba   (sin puerta; pocas réplicas; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import data as D
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int16_potencia.json"
SEMILLA = 20261105
H = 12                     # horizonte (meses) y retardos de Newey-West
BLOQUE = 12                # bloques del remuestreo de residuos
R2S = (0.05, 0.10, 0.20, 0.30)              # R² poblacional conjunto a 12 meses (rejilla; literatura: §6 del doc)
THETAS_NN = (45, 55, 65, 75, 90)            # no anidado: 45 = nula (misma precisión), 90 = solo la prima predice
THETAS_AN = (0, 15, 30, 45, 60, 90)         # anidado: 0 = nula (la prima no añade)
KAPPA_TR = 0.25            # sensibilidad: ruido de añada de la prima en tiempo real (var ruido / var prima), AR(1) 0,95
# muestras: (filas con objetivo, primera fila fuera de muestra)
MUESTRAS = {
    "dev_TR_1981_2003": (389, 120),        # orígenes 1971-08…2003-12; ACM-TR desde 1981-08 (10 años de arranque) → 269
    "dev_publicado_1971_2003": (511, 120), # ACM publicado 1961-06…, objetivo ACM ajustado; OOS 1971-06…2003-12 → 391
    "bloqueado_2005_2023": (629, 401),     # historia 1971-08…2004-12; OOS 2005-01…2023-12 → 228 (hipotético; no se lee)
}
VIVO_AÑOS = (10, 20, 30, 40)               # en vivo: historia 1971-08…2026-10 (663 filas) + años nuevos


def _r(x, k=3):
    return None if x is None or not np.isfinite(x) else round(float(x), k)


def mensual(s: pd.Series) -> pd.Series:
    """Diaria → último dato de cada mes, fechado el día 1 (como nyfed_acm_*_m)."""
    return s.resample("MS").last()


def datos():
    con = D.connect()
    try:
        y10 = mensual(D.load_dev(con, "gsw_sveny10"))
        y1 = mensual(D.load_dev(con, "gsw_sveny01"))
        tp = D.load_dev(con, "nyfed_acm_tp10_m")
        rny = D.load_dev(con, "nyfed_acm_rny10_m")
    finally:
        con.close()
    df = pd.concat({"s": y10 - y1, "p": tp, "y10": y10}, axis=1).dropna()
    D.check(df)
    df["u"] = -(119 / 12) * df["y10"].diff()            # shock aproximado de la rentabilidad mensual del bono 10a (pp)
    eq = pd.concat({"dtp": tp.diff(), "drny": rny.diff()}, axis=1).dropna()
    D.check(eq)
    return df, eq, tp, rny


def var1(df):
    X = df[["s", "p"]].to_numpy()
    Z = np.column_stack([np.ones(len(X) - 1), X[:-1]])
    B = np.linalg.lstsq(Z, X[1:], rcond=None)[0]
    res = X[1:] - Z @ B
    u = df["u"].to_numpy()[1:]
    E = np.column_stack([res - res.mean(0), u - np.nanmean(u)])
    return B[0], B[1:].T, E                              # a, A (x_t = a + A x_{t-1} + ε), residuos [ε_s, ε_p, u]


def remuestreo(rng, E, n):
    k = -(-n // BLOQUE)
    ini = rng.integers(0, len(E), k)
    idx = (ini[:, None] + np.arange(BLOQUE)[None, :]).ravel() % len(E)
    return E[idx[:n]]


def simular_x(rng, a, A, E, n, quemar=240):
    ee = remuestreo(rng, E, n + quemar + H)
    mu = np.linalg.solve(np.eye(2) - A, a)
    x = np.empty((n + quemar + H, 2))
    x[0] = mu
    for t in range(1, len(x)):
        x[t] = a + A @ x[t - 1] + ee[t, :2]
    return x[quemar:], ee[quemar:, 2]


def momentos(rng, a, A, E):
    """Media/dt poblacionales de s, p, Δ12 p; correlaciones; varianza del error de 12 meses (simulación larga)."""
    x, u = simular_x(rng, a, A, E, 200_000)
    d12 = np.r_[np.full(12, np.nan), x[12:, 1] - x[:-12, 1]]
    e12 = np.convolve(u, np.ones(H), "valid")[1:]          # e_t = Σ_{k=1..12} u_{t+k}
    m = {"s": (x[:, 0].mean(), x[:, 0].std()), "p": (x[:, 1].mean(), x[:, 1].std()),
         "dp": (np.nanmean(d12), np.nanstd(d12))}
    return m, float(np.var(e12)), float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]), \
        float(np.corrcoef(x[12:, 0], d12[12:])[0, 1])


def ols_creciente(X, y, n0):
    """Previsión en cada origen t ≥ n0 con MCO sobre pares s ≤ t − H (X con constante). Vectorizado por sumas acumuladas."""
    n, k = X.shape
    XX = np.cumsum(X[:, :, None] * X[:, None, :], axis=0)
    Xy = np.cumsum(X * y[:, None], axis=0)
    t = np.arange(n0, n)
    j = t - H
    b = np.linalg.solve(XX[j], Xy[j][..., None])[..., 0]
    return np.einsum("ij,ij->i", X[t], b)


def nw_var(d, L=H):
    d = d - d.mean()
    n = len(d)
    v = d @ d / n
    for l in range(1, L + 1):
        v += 2 * (1 - l / (L + 1)) * (d[l:] @ d[:-l]) / n
    return v / n


def simular_celda(rng, a, A, E, mom, Ve, rho, n, n0, w, r2, reps, var_p="nivel", ruido=0.0):
    """Devuelve estadísticos OOS por réplica: ΔR²_OS no anidado, R²_OS de cada modelo, DM y CW nominales."""
    ws, wp = w
    varz = ws ** 2 + wp ** 2 + 2 * ws * wp * rho
    c = np.sqrt(r2 / (1 - r2) * Ve / varz) if r2 > 0 else 0.0
    out = np.empty((reps, 6))
    for i in range(reps):
        x, u = simular_x(rng, a, A, E, n + 12)
        s = (x[12:n + 12, 0] - mom["s"][0]) / mom["s"][1]
        if var_p == "nivel":
            p = (x[12:n + 12, 1] - mom["p"][0]) / mom["p"][1]
        else:
            p = ((x[12:n + 12, 1] - x[:n, 1]) - mom["dp"][0]) / mom["dp"][1]
        e = np.convolve(u[12:], np.ones(H), "valid")[1:n + 1]
        y = c * (ws * s + wp * p) + e
        pobs = p
        if ruido > 0:                                 # ruido de añada de la prima en tiempo real
            eta = np.empty(n)
            eta[0] = rng.normal()
            z = rng.normal(size=n) * np.sqrt(1 - 0.95 ** 2)
            for t in range(1, n):
                eta[t] = 0.95 * eta[t - 1] + z[t]
            pobs = p + np.sqrt(ruido) * eta
        one = np.ones(n)
        f_s = ols_creciente(np.column_stack([one, s]), y, n0)
        f_p = ols_creciente(np.column_stack([one, pobs]), y, n0)
        f_sp = ols_creciente(np.column_stack([one, s, pobs]), y, n0)
        cy = np.cumsum(y)
        t = np.arange(n0, n)
        f_m = cy[t - H] / (t - H + 1)
        yo = y[n0:]
        es, ep, esp, em = yo - f_s, yo - f_p, yo - f_sp, yo - f_m
        mm = em @ em
        r2s, r2p = 1 - es @ es / mm, 1 - ep @ ep / mm
        d = es ** 2 - ep ** 2                          # DM: > 0 favorece a la prima
        dm = d.mean() / np.sqrt(nw_var(d))
        fcw = es ** 2 - (esp ** 2 - (f_s[:] - f_sp[:]) ** 2)   # Clark-West (anidado: pendiente ⊂ pendiente + prima)
        cw = fcw.mean() / np.sqrt(nw_var(fcw))
        r2sp = 1 - esp @ esp / mm
        out[i] = (r2p - r2s, r2s, r2p, dm, cw, r2sp - r2s)
    return out, c


def r2_pob(w, rho, r2):
    ws, wp = w
    varz = ws ** 2 + wp ** 2 + 2 * ws * wp * rho
    k = r2 / varz                                      # c²/(c² varz + Ve) · varz = r2  →  c²/(…) = r2/varz
    return k * (ws + rho * wp) ** 2, k * (wp + rho * ws) ** 2


def mde(xs, pots, nivel=0.8):
    pares = list(zip(xs, pots))
    if pares and pares[0][1] >= nivel:
        return f"≤ {pares[0][0]:.3f}"
    for (d0, p0), (d1, p1) in zip(pares, pares[1:]):
        if p0 < nivel <= p1:
            return _r(d0 + (nivel - p0) * (d1 - d0) / (p1 - p0))
    return f"> {pares[-1][0]:.3f}"


def bloque_muestra(rng, a, A, E, mom, Ve, rho_lvl, rho_d, n, n0, reps, var_p, ruido=0.0):
    rho = rho_lvl if var_p == "nivel" else rho_d
    res = {"filas": n, "oos": n - n0, "por_r2": {}}
    for r2 in R2S:
        # no anidado
        nula, _ = simular_celda(rng, a, A, E, mom, Ve, rho, n, n0, (np.cos(np.pi / 4), np.sin(np.pi / 4)), r2, reps,
                                var_p, ruido)
        crit = float(np.quantile(nula[:, 0], 0.95))
        crit_dm = float(np.quantile(nula[:, 3], 0.95))
        celdas = []
        for th in THETAS_NN:
            w = (np.cos(np.radians(th)), np.sin(np.radians(th)))
            r2s_p, r2p_p = r2_pob(w, rho, r2)
            sim = nula if th == 45 else simular_celda(rng, a, A, E, mom, Ve, rho, n, n0, w, r2, reps, var_p, ruido)[0]
            celdas.append({"theta": th, "dR2_pob": _r(r2p_p - r2s_p), "R2_pend_pob": _r(r2s_p), "R2_prima_pob": _r(r2p_p),
                           "pot_empirica": _r((sim[:, 0] > crit).mean()), "pot_DM_nominal": _r((sim[:, 3] > 1.645).mean()),
                           "media_dR2_OS": _r(sim[:, 0].mean()), "media_R2OS_pend": _r(sim[:, 1].mean()),
                           "media_R2OS_prima": _r(sim[:, 2].mean()), "P_dR2OS_pos": _r((sim[:, 0] > 0).mean())})
        nn = {"crit95_dR2_OS": _r(crit), "tamano_DM_nominal_5pct": _r((nula[:, 3] > 1.645).mean()),
              "crit95_DM_empirico": _r(crit_dm), "celdas": celdas,
              "MDE80_dR2_pob": mde([c["dR2_pob"] for c in celdas], [c["pot_empirica"] for c in celdas])}
        # anidado (la prima añade a la pendiente)
        nula_a, _ = simular_celda(rng, a, A, E, mom, Ve, rho, n, n0, (1.0, 0.0), r2, reps, var_p, ruido)
        crit_cw = float(np.quantile(nula_a[:, 4], 0.95))
        ca = []
        for th in THETAS_AN:
            w = (np.cos(np.radians(th)), np.sin(np.radians(th)))
            r2s_p, _ = r2_pob(w, rho, r2)
            sim = nula_a if th == 0 else simular_celda(rng, a, A, E, mom, Ve, rho, n, n0, w, r2, reps, var_p, ruido)[0]
            ca.append({"theta": th, "dR2_parcial_pob": _r(r2 - r2s_p), "pot_CW_empirica": _r((sim[:, 4] > crit_cw).mean()),
                       "pot_CW_nominal": _r((sim[:, 4] > 1.645).mean()), "media_dR2OS_anidado": _r(sim[:, 5].mean())})
        an = {"tamano_CW_nominal_5pct": _r((nula_a[:, 4] > 1.645).mean()), "crit95_CW_empirico": _r(crit_cw),
              "celdas": ca, "MDE80_dR2_parcial_pob": mde([c["dR2_parcial_pob"] for c in ca],
                                                          [c["pot_CW_empirica"] for c in ca])}
        res["por_r2"][str(r2)] = {"no_anidado": nn, "anidado": an}
        print(f"  n={n} oos={n - n0} {var_p} ruido={ruido} R2={r2}: MDE no anidado {nn['MDE80_dR2_pob']} "
              f"(tamaño DM {nn['tamano_DM_nominal_5pct']}), anidado {an['MDE80_dR2_parcial_pob']} "
              f"(tamaño CW {an['tamano_CW_nominal_5pct']})", flush=True)
    return res


def stambaugh(rng, a, A, E, mom, Ve, n, reps):
    """Sin predictibilidad (c = 0): R² dentro de muestra a 12 m y tamaño del t de Newey-West (12) con cada predictor."""
    out = {}
    for var_p in ("pendiente", "prima_nivel", "prima_d12"):
        r2, tt, bb = [], [], []
        for _ in range(reps):
            x, u = simular_x(rng, a, A, E, n + 12)
            e = np.convolve(u[12:], np.ones(H), "valid")[1:n + 1]
            if var_p == "pendiente":
                z = x[12:n + 12, 0]
            elif var_p == "prima_nivel":
                z = x[12:n + 12, 1]
            else:
                z = x[12:n + 12, 1] - x[:n, 1]
            zc = z - z.mean()
            b = zc @ (e - e.mean()) / (zc @ zc)
            res = e - e.mean() - b * zc
            r2.append(1 - res @ res / ((e - e.mean()) @ (e - e.mean())))
            se = np.sqrt(nw_var(zc * res)) * n / (zc @ zc)      # NW(12) del β
            tt.append(b / se)
            bb.append(b * z.std() / e.std())
        r2, tt = np.array(r2), np.array(tt)
        out[var_p] = {"R2_dentro_media": _r(r2.mean()), "R2_dentro_p95": _r(np.quantile(r2, 0.95)),
                      "tamano_tNW_bilateral_5pct": _r((np.abs(tt) > 1.96).mean()),
                      "sesgo_beta_estandarizado_media": _r(np.mean(bb))}
    return out


def bolsa(rng, eq, n, reps, sd_m=4.4):
    """Opcional: rentabilidad de la bolsa h meses tras un cambio de 3 meses del tipo a 10 años, separado en prima (ACM)
    y expectativas (rny). Cambios mensuales reales remuestreados por bloques; shocks de bolsa iid N(0, sd_m) (15 % anual,
    supuesto de literatura: NO se lee la bolsa). Contraste b_prima = b_rny con NW(h). MDE en pp de rentabilidad por 1 pp
    de cambio del tipo."""
    Ed = eq[["dtp", "drny"]].to_numpy()
    out = {"sd_dTP3_pp": _r(eq["dtp"].rolling(3).sum().std()), "sd_dRNY3_pp": _r(eq["drny"].rolling(3).sum().std()),
           "corr_dTP3_dRNY3": _r(eq["dtp"].rolling(3).sum().corr(eq["drny"].rolling(3).sum())), "por_h": {}}
    for h in (3, 6, 12):
        dif = []
        for _ in range(reps):
            d = remuestreo(rng, Ed, n + 3)
            x3 = np.column_stack([np.convolve(d[:, 0], np.ones(3), "valid"), np.convolve(d[:, 1], np.ones(3), "valid")])
            x3 = x3[:n]
            r = rng.normal(0, sd_m, n + h)
            y = np.convolve(r, np.ones(h), "valid")[1:n + 1]
            X = np.column_stack([np.ones(n), x3])
            b = np.linalg.lstsq(X, y, rcond=None)[0]
            dif.append(b[1] - b[2])
        sd = float(np.std(dif))
        out["por_h"][str(h)] = {"sd_dif_b": _r(sd, 2), "MDE80_bilateral_pp_por_pp": _r(2.80 * sd, 2),
                                "MDE80_en_pp_por_1dt_dTP3": _r(2.80 * sd * out["sd_dTP3_pp"], 2)}
        print("  bolsa h", h, out["por_h"][str(h)], flush=True)
    return out


def main():
    prueba = "--prueba" in sys.argv
    t0 = time.time()
    prov = procedencia(exigir_limpio=not prueba)
    rng = np.random.default_rng(SEMILLA)
    reps = 60 if prueba else 1500
    df, eq, tp, rny = datos()
    a, A, E = var1(df)
    mom, Ve, rho_lvl, rho_d = momentos(rng, a, A, E)
    ev = np.linalg.eigvals(A)
    res = {"procedencia": prov, "documento": "docs/int/INT16_prima_plazo_v0.md", "semilla": SEMILLA, "reps": reps,
           "supuestos": {
               "datos_reales": "solo dinámica de predictores (VAR(1) de pendiente GSW 10a−1a y prima ACM 10a, "
                               f"{df.index.min():%Y-%m}…{df.index.max():%Y-%m}) y shock −(119/12)Δy10 remuestreado "
                               "por bloques de 12 junto a los residuos; ningún β ni R² predictivo real",
               "efecto": "R² poblacional conjunto a 12 m = parámetro (rejilla R2S), reparto por ángulo θ",
               "prima": "ACM publicado (no PIT) para calibrar la dinámica; el ACM-TR real tendrá otra (ruido de añada: "
                        f"sensibilidad κ = {KAPPA_TR})",
               "objetivo": "rx12 = c·z + Σ12 shocks mensuales (solapamiento 12, Stambaugh por construcción)",
               "contraste_no_anidado": "ΔR²_OS (pendiente − prima)/media histórica; crítico empírico de la nula θ=45°",
               "contraste_anidado": "Clark-West pendiente+prima frente a pendiente; crítico empírico de la nula θ=0°"},
           "calibracion": {"meses": len(df), "A": np.round(A, 4).tolist(), "autovalores": np.round(np.abs(ev), 4).tolist(),
                           "AR1_pendiente": _r(df["s"].autocorr(1)), "AR1_prima": _r(df["p"].autocorr(1)),
                           "corr_pendiente_prima": _r(rho_lvl), "corr_pendiente_dprima12": _r(rho_d),
                           "corr_innov_u_pend": _r(np.corrcoef(E[:, 0], E[:, 2])[0, 1]),
                           "corr_innov_u_prima": _r(np.corrcoef(E[:, 1], E[:, 2])[0, 1]),
                           "corr_innov_pend_prima": _r(np.corrcoef(E[:, 0], E[:, 1])[0, 1]),
                           "dt_pob": {k: _r(v[1]) for k, v in mom.items()},
                           "corr_tp10_rny10_1961_2004": _r(pd.concat([tp, rny], axis=1).dropna().corr().iloc[0, 1])}}
    print(json.dumps(res["calibracion"], ensure_ascii=False), flush=True)
    res["stambaugh_sin_efecto_dev"] = stambaugh(rng, a, A, E, mom, Ve, 389, reps)
    print("stambaugh", res["stambaugh_sin_efecto_dev"], flush=True)
    res["muestras"] = {}
    for nombre, (n, n0) in MUESTRAS.items():
        for var_p in ("nivel", "d12"):
            if var_p == "d12" and nombre != "dev_TR_1981_2003":
                continue
            clave = f"{nombre}|prima_{var_p}"
            print(clave, flush=True)
            res["muestras"][clave] = bloque_muestra(rng, a, A, E, mom, Ve, rho_lvl, rho_d, n, n0, reps, var_p)
    print("ruido de añada", flush=True)
    res["muestras"][f"dev_TR_1981_2003|prima_nivel|ruido{KAPPA_TR}"] = bloque_muestra(
        rng, a, A, E, mom, Ve, rho_lvl, rho_d, 389, 120, reps, "nivel", KAPPA_TR)
    res["vivo"] = {}
    for años in VIVO_AÑOS:
        n0 = 663
        print("vivo", años, flush=True)
        res["vivo"][str(años)] = bloque_muestra(rng, a, A, E, mom, Ve, rho_lvl, rho_d, n0 + 12 * años, n0,
                                                max(reps // 3, 40), "nivel")
    print("bolsa", flush=True)
    res["bolsa_opcional_1961_2004"] = bolsa(rng, eq, len(eq) - 12, reps)
    res["segundos"] = round(time.time() - t0, 1)
    if prueba:
        print(json.dumps(res, ensure_ascii=False, indent=1, default=str)[:4000])
        return
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("escrito", SALIDA)


if __name__ == "__main__":
    main()
