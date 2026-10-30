"""INT-11: POTENCIA de la evaluación de distribuciones (CRPS, cobertura) con un proceso generador SINTÉTICO.

Nada aquí toca datos reales: el script scripts/int11_potencia.py mide por SEPARADO propiedades de X (frecuencia,
persistencia y concordancia entre países del régimen operable) y de Y (dispersión común y propia de cada activo,
correlaciones, colas) y se las pasa a estas funciones. Los efectos del régimen sobre la rentabilidad se PLANTAN (δ × los
tamaños ya publicados del Atlas §8); nunca se estiman cruzando el régimen real con la rentabilidad real.

Piezas:
  dgp_regimenes   régimen de N países × T años desde dos latentes AR(1) (inflación, brecha) con componente común
  dgp_rent        rentabilidades reales con choque común de año + propio, t multivariante, efecto según s_{t−1}
  evaluar         M1 (distribución empírica por régimen conocido) frente a M0 (incondicional del panel), dejando un
                  país fuera o temporal; CRPS normalizado por activo; Diebold-Mariano con años como conglomerados
  cobertura_sim   cobertura del intervalo p5-p95 (o p10-p90) de un modelo con anchura escalada; contraste por años
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.intl import escenarios as E

K = E.K
ACTIVOS = E.ACTIVOS
# Efectos de referencia (δ = 1), fracción/año, por régimen conocido s_{t−1} = (exp, sobrecal., estanfl., crec. bajo).
# Bolsa, bonos y letras: tamaños del Atlas §8 (versión operable; probablemente INFLADOS por la maldición del ganador).
# Vivienda: supuesto (no hay versión operable); oro: 0 (no sabemos).
EFECTOS_REF = np.array([[0.0, -0.03, -0.12, 0.0],
                        [0.0, -0.06, -0.06, 0.0],
                        [0.0, -0.05, -0.05, 0.0],
                        [0.0, 0.0, -0.03, 0.0],
                        [0.0, 0.0, 0.0, 0.0]])


# ============================================================================ proceso generador
def latente(N: int, T: int, a: float, rho: float, rng) -> np.ndarray:
    """(N, T) AR(1) estacionario de varianza 1 con correlación rho entre países en cada innovación."""
    z = np.zeros((N, T))
    z[:, 0] = np.sqrt(rho) * rng.standard_normal() + np.sqrt(1 - rho) * rng.standard_normal(N)
    s = np.sqrt(1 - a ** 2)
    for t in range(1, T):
        inn = np.sqrt(rho) * rng.standard_normal() + np.sqrt(1 - rho) * rng.standard_normal(N)
        z[:, t] = a * z[:, t - 1] + s * inn
    return z


def dgp_regimenes(N: int, T: int, par: dict, rng, latentes: bool = False):
    """par: q_i (frecuencia de inflación > 3 %), q_g (frecuencia de brecha < 0), a_i, rho_i, a_g, rho_g.
    latentes=True → (reg, zi, zg) para construir una inflación continua coherente (v2, Brier de inflación > 5 %)."""
    zi = latente(N, T, par["a_i"], par["rho_i"], rng)
    zg = latente(N, T, par["a_g"], par["rho_g"], rng)
    alta = zi > stats.norm.ppf(1 - par["q_i"])
    baja = zg < stats.norm.ppf(par["q_g"])
    reg = np.where(baja, np.where(alta, 2, 3), np.where(alta, 1, 0))
    return (reg, zi, zg) if latentes else reg


def inflacion_desde_latente(zi: np.ndarray, q_alta: float, q_5: float, desplaz: float = 0.0) -> np.ndarray:
    """Inflación simple (fracción) lineal en el latente: > 3 % ⇔ zi > Φ⁻¹(1 − q_alta) (coherente con el régimen) y
    P(> 5 %) = q_5 en el estado estacionario. `desplaz` (en dt del latente) mueve todo hacia abajo (escenario
    "tranquilo": menos inflación alta; hipotético, no medido)."""
    u3, u5 = stats.norm.ppf(1 - q_alta), stats.norm.ppf(1 - q_5)
    sd = 0.02 / (u5 - u3)
    return 0.03 + sd * (zi - desplaz - u3)


def indicador_props(x: np.ndarray) -> dict:
    """x (N, T) booleano con NaN permitidos (float). Frecuencia, persistencia P(x_t = x_{t−1}) y concordancia (media
    de las correlaciones entre pares de países)."""
    x = np.asarray(x, float)
    ok = np.isfinite(x[:, 1:]) & np.isfinite(x[:, :-1])
    pers = float((x[:, 1:][ok] == x[:, :-1][ok]).mean())
    cs = []
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            m = np.isfinite(x[i]) & np.isfinite(x[j])
            if m.sum() > 20 and x[i, m].std() > 0 and x[j, m].std() > 0:
                cs.append(np.corrcoef(x[i, m], x[j, m])[0, 1])
    return {"frecuencia": float(np.nanmean(x)), "persistencia": pers, "concordancia": float(np.mean(cs))}


def calibrar_latente(q: float, pers: float, conc: float, N: int = 14, T: int = 400, semilla: int = 0) -> dict:
    """(a, rho) del latente que reproducen la persistencia y la concordancia del indicador (rejilla + simulación)."""
    rng = np.random.default_rng(semilla)
    mejor, err = None, np.inf
    for a in np.linspace(0.3, 0.97, 35):
        for rho in np.linspace(0.0, 0.9, 31):
            props = [indicador_props(latente(N, T, a, rho, rng) > stats.norm.ppf(1 - q)) for _ in range(2)]
            p = np.mean([x["persistencia"] for x in props])
            c = np.mean([x["concordancia"] for x in props])
            e = (p - pers) ** 2 + (c - conc) ** 2
            if e < err:
                mejor, err = (float(a), float(rho), float(p), float(c)), e
    return {"a": mejor[0], "rho": mejor[1], "persistencia_sim": mejor[2], "concordancia_sim": mejor[3]}


def t_multi(n: int, R: np.ndarray, nu: float, rng) -> np.ndarray:
    """(n, A) t multivariante con correlación R y varianza 1."""
    L = np.linalg.cholesky(R)
    z = rng.standard_normal((n, len(R))) @ L.T
    if not np.isfinite(nu):
        return z
    return z * np.sqrt((nu - 2) / rng.chisquare(nu, size=(n, 1)))


def dgp_rent(reg: np.ndarray, efectos: np.ndarray, mu: np.ndarray, sd_comun: np.ndarray, sd_propio: np.ndarray,
             R: np.ndarray, nu: float, rng, fac_pais: np.ndarray | None = None,
             fac_raro: float = 1.0) -> np.ndarray:
    """(N, T, A) rentabilidad real (log) del año t; el efecto depende del régimen CONOCIDO s_{t−1} (t ≥ 1).
    v2: fac_pais (N, A) multiplica el choque PROPIO de cada país (heterogeneidad entre países, nulo heterogéneo);
    fac_raro multiplica el choque propio cuando s_{t−1} es raro (estanflación o crecimiento bajo; sensibilidad)."""
    N, T = reg.shape
    A = len(mu)
    u = t_multi(T, R, nu, rng) * sd_comun                         # (T, A) choque común de año
    e = t_multi(N * T, R, nu, rng).reshape(N, T, A) * sd_propio
    if fac_pais is not None:
        e = e * fac_pais[:, None, :]
    if fac_raro != 1.0:
        prev0 = np.concatenate([np.full((N, 1), 0), reg[:, :-1]], axis=1)
        e = e * np.where(np.isin(prev0, (2, 3)), fac_raro, 1.0)[:, :, None]
    y = mu + u[None] + e
    prev = np.concatenate([np.full((N, 1), 0), reg[:, :-1]], axis=1)
    y = y + efectos.T[prev]                                          # (N, T, A)
    y[:, 0] = np.nan
    return y


# ============================================================================ evaluación de distribuciones
def _pools(Ytr: np.ndarray, Str: np.ndarray, n_min: int) -> tuple[np.ndarray, list]:
    """Ytr (n, A), Str (n,) régimen conocido. Pool incondicional y por régimen (con respaldo al incondicional)."""
    por = [Ytr[Str == i] if (Str == i).sum() >= n_min else Ytr for i in range(K)]
    return Ytr, por


def _crps_filas(Ytr, Str, Yte, Ste, n_min):
    """CRPS de M0 y M1 por fila de prueba y activo: (m, A) cada uno."""
    m, A = Yte.shape
    c0, c1 = np.full((m, A), np.nan), np.full((m, A), np.nan)
    p0, por = _pools(Ytr, Str, n_min)
    for a in range(A):
        ok = np.isfinite(Yte[:, a])
        if np.isfinite(p0[:, a]).sum() < n_min:                    # activo sin pool de entrenamiento (oro < 1972)
            continue
        c0[ok, a] = E.crps_muestra(p0[:, a], Yte[ok, a])
        for i in range(K):
            mi = ok & (Ste == i)
            if mi.any():
                c1[mi, a] = E.crps_muestra(por[i][:, a], Yte[mi, a])
    return c0, c1


def filas_h(Y: np.ndarray, reg: np.ndarray, h: int, inicio: int = 1) -> tuple:
    """Objetivos a horizonte h: suma de log-rentabilidades de t … t + h − 1 (inicios cada h años, sin solape) y estado
    conocido s_{t−1}. Devuelve (pais, año, Y (n, A), S (n,))."""
    N, T, A = Y.shape
    ts = np.arange(inicio, T - h + 1, h)
    P, Tt = np.meshgrid(np.arange(N), ts, indexing="ij")
    P, Tt = P.ravel(), Tt.ravel()
    Yh = np.stack([Y[P, Tt + k] for k in range(h)], 0).sum(0)
    return P, Tt, Yh, reg[P, Tt - 1]


def evaluar(Y: np.ndarray, reg: np.ndarray, diseño: str, h: int = 1, corte: int | None = None, n_min: int = 30,
            prueba_desde: int | None = None) -> dict:
    """diseño "loco" (entrena con los otros países, todos los años) o "temporal" (entrena t < corte, prueba
    t ≥ corte; si prueba_desde, solo t ≥ prueba_desde). Devuelve d por fila (mejora media normalizada de M1 sobre M0),
    años, CRPSS por activo y medio."""
    P, Tt, Yh, S = filas_h(Y, reg, h)
    m, A = Yh.shape
    c0, c1 = np.full((m, A), np.nan), np.full((m, A), np.nan)
    if diseño == "loco":
        for c in np.unique(P):
            te, tr = P == c, P != c
            c0[te], c1[te] = _crps_filas(Yh[tr], S[tr], Yh[te], S[te], n_min)
    else:
        tr = Tt + h - 1 < corte                       # el objetivo de entrenamiento termina antes del corte
        te = Tt >= corte if prueba_desde is None else Tt >= prueba_desde
        c0[te], c1[te] = _crps_filas(Yh[tr], S[tr], Yh[te], S[te], n_min)
    usa = np.isfinite(c0).any(1)
    escala = np.nanmean(c0[usa], 0)
    da = (c0[usa] - c1[usa]) / escala
    d = np.nanmean(da, 1)
    crpss = 1 - np.nanmean(c1[usa], 0) / escala
    return {"d": d, "d_activo": da, "año": Tt[usa], "crpss": crpss, "crpss_medio": float(np.nanmean(crpss))}


def cobertura_sim(Y: np.ndarray, reg: np.ndarray, k: float, lo: float, hi: float, corte: int, prueba: tuple,
                  h: int = 1, n_min: int = 30) -> dict:
    """Modelo M1 entrenado con t < corte cuyo intervalo [q_lo, q_hi] se ensancha/estrecha por k alrededor de la
    mediana (k < 1 → infracobertura). Prueba en t ∈ [prueba[0], prueba[1]). Indicador dentro/fuera por fila."""
    P, Tt, Yh, S = filas_h(Y, reg, h)
    tr = Tt + h - 1 < corte
    te = (Tt >= prueba[0]) & (Tt < prueba[1])
    _, por = _pools(Yh[tr], S[tr], n_min)
    A = Yh.shape[1]
    dentro = np.full((te.sum(), A), np.nan)
    Yte, Ste = Yh[te], S[te]
    for i in range(K):
        mi = Ste == i
        if not mi.any():
            continue
        q = np.nanquantile(por[i], [lo, 0.5, hi], axis=0)          # (3, A)
        a_lo, a_hi = q[1] - k * (q[1] - q[0]), q[1] + k * (q[2] - q[1])
        y = Yte[mi]
        valido = np.isfinite(y) & np.isfinite(a_lo) & np.isfinite(a_hi)        # sin pool de entrenamiento → hueco
        dentro[mi] = np.where(valido, (y >= a_lo) & (y <= a_hi), np.nan)
    return {"dentro": dentro, "año": Tt[te]}


# ============================================================================ corrida de desarrollo (P-DEV-INT11 v1.0)
def filas_sinteticas(reg: np.ndarray, Ylog: np.ndarray, paises: list[str], años: np.ndarray,
                     existe: np.ndarray | None = None, activo_ok: np.ndarray | None = None,
                     infl: np.ndarray | None = None):
    """Filas del motor desde un panel sintético. reg (N, T), Ylog (N, T, A) log-rentabilidades; la fila (c, t) usa
    s_prev = reg[c, t − 1] (t ≥ 1). existe (N, T) y activo_ok (N, T, A): estructura de huecos del panel real (§5 del
    prerregistro). inflación = 5 % con inflación alta y 1 % si no (solo para la coherencia del sorteo)."""
    import pandas as pd
    N, T, A = Ylog.shape
    existe = np.ones((N, T), bool) if existe is None else existe
    activo_ok = np.ones((N, T, A), bool) if activo_ok is None else activo_ok
    c, t = np.nonzero(existe[:, 1:])
    t = t + 1
    R = np.where(activo_ok[c, t], np.expm1(Ylog[c, t]), np.nan)
    s = reg[c, t]
    d = pd.DataFrame({"pais": np.asarray(paises)[c], "año": años[t], "s_prev": reg[c, t - 1], "s": s, "w_prev": -1,
                      "w": -1})
    for j, a in enumerate(ACTIVOS):
        d[a] = R[:, j]
    # inflación = Δlog IPC (como el panel). v1: 5 % / 1 % según el régimen; v2: continua (N, T) en fracción simple
    d["inflacion"] = (np.where(np.isin(s, (1, 2)), 0.05, 0.01) if infl is None else np.log1p(infl[c, t]))
    d["crecimiento"] = 0.02
    d = d.sort_values(["pais", "año"]).reset_index(drop=True)
    sig = d.groupby("pais")["año"].shift(-1)
    d["sucesor"] = np.where(sig == d["año"] + 1, d.index + 1, -1)
    return d


def _acumulada_5(V: np.ndarray, suc: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Rentabilidad simple acumulada de 5 filas consecutivas (cadena de sucesores) desde cada idx; NaN si se corta."""
    out = np.full((len(idx), V.shape[1]), np.nan)
    for k, i in enumerate(idx):
        cad, j = [i], i
        for _ in range(4):
            j = suc[j]
            if j < 0:
                break
            cad.append(j)
        if len(cad) == 5:
            out[k] = np.prod(1 + V[cad], axis=0) - 1
    return out


def evaluar_motor(filas, diseño: str, n_lotes: int, por_lote: int, semilla: int, H: int = 1, corte: int = 1950,
                  cfg=None, n_min_pool: int = 30, k_anchura: tuple = ()) -> dict:
    """Evalúa M1 (motor) y M0 (incondicional del entrenamiento) fila a fila (prerregistro v1.0 §2-§4, §7).
    Devuelve arrays por fila de prueba: pais, año, s_prev, y (m, A), crps0/crps1, dentro90 (p5-p95), dentro80 (p10-p90),
    pit, eventos (Brier) y, si H ≥ 5, lo mismo para la acumulada a 5 años en las filas de inicio de ventana."""
    import pandas as pd
    filas = E.recalcular_sucesor(filas)
    acts = list(ACTIVOS)
    V = filas[acts].to_numpy(float)
    infl = np.expm1(filas["inflacion"].to_numpy(float))
    suc = filas["sucesor"].to_numpy(int)
    paises = sorted(filas["pais"].unique())
    if diseño == "loco":
        pliegues = [(k, filas["pais"].to_numpy() != c, filas["pais"].to_numpy() == c) for k, c in enumerate(paises)]
    elif diseño == "temporal":
        a = filas["año"].to_numpy()
        pliegues = [(0, a < corte, a >= corte)]
    else:
        raise ValueError(diseño)
    m, A = len(filas), len(acts)
    out = {k: np.full((m, A), np.nan) for k in ("crps0", "crps1", "dentro90", "dentro80", "pit", "dentro90_m0")}
    out.update({k: np.full(m, np.nan) for k in ("p_caida_m1", "p_caida_m0", "p_infl_m1", "p_infl_m0")})
    # v2 (potencia de la puerta): cobertura de intervalos p5-p95 ESCALADOS por k alrededor de la mediana (k < 1 →
    # infracobertura conocida), con los mismos sorteos
    dk = np.full((m, A, len(k_anchura)), np.nan)
    prueba = np.zeros(m, bool)
    h5 = {k: np.full((m, A), np.nan) for k in ("y5", "crps0_5", "crps1_5", "dentro90_5")}
    rng_pit = np.random.default_rng(semilla)
    for k, tr, te in pliegues:
        ftr = E.recalcular_sucesor(filas[tr])
        gen = E.Generador(cfg or E.Config()).ajustar(ftr)
        Vtr = V[tr]
        p0 = [Vtr[np.isfinite(Vtr[:, j]), j] for j in range(A)]
        if H >= 5:
            suc_tr = ftr["sucesor"].to_numpy(int)
            pool5 = _acumulada_5(Vtr, suc_tr, np.arange(len(ftr)))
            p05 = [pool5[np.isfinite(pool5[:, j]), j] for j in range(A)]
        infl_tr = infl[tr]
        caida_m0 = float(np.mean(Vtr[np.isfinite(Vtr[:, 0]), 0] <= -0.20))
        infl_m0 = float(np.mean(infl_tr[np.isfinite(infl_tr)] > 0.05))
        te_idx = np.flatnonzero(te)
        prueba[te_idx] = True
        grupos = filas.iloc[te_idx].groupby(["pais", "s_prev"]).indices
        for (c, s0), pos in grupos.items():
            idx = te_idx[pos]
            esc = gen.simular(c, int(s0), horizonte=H, n_lotes=n_lotes, por_lote=por_lote,
                              semilla=semilla + 1000 * k + 10 * paises.index(c) + int(s0))
            R1 = esc.rent[:, 0, :]
            out["p_caida_m1"][idx] = np.mean(R1[:, 0] <= -0.20)
            out["p_infl_m1"][idx] = np.mean(np.expm1(esc.inflacion[:, 0]) > 0.05)
            out["p_caida_m0"][idx], out["p_infl_m0"][idx] = caida_m0, infl_m0
            for j in range(A):
                y = V[idx, j]
                ok = np.isfinite(y)
                x1 = R1[np.isfinite(R1[:, j]), j]
                if not ok.any() or len(p0[j]) < n_min_pool or len(x1) < n_min_pool:
                    continue
                ii = idx[ok]
                out["crps0"][ii, j] = E.crps_muestra(p0[j], y[ok])
                out["crps1"][ii, j] = E.crps_muestra(x1, y[ok])
                q = np.quantile(x1, [0.05, 0.10, 0.90, 0.95])
                out["dentro90"][ii, j] = (y[ok] >= q[0]) & (y[ok] <= q[3])
                out["dentro80"][ii, j] = (y[ok] >= q[1]) & (y[ok] <= q[2])
                q0 = np.quantile(p0[j], [0.05, 0.95])
                out["dentro90_m0"][ii, j] = (y[ok] >= q0[0]) & (y[ok] <= q0[1])
                out["pit"][ii, j] = E.pit(x1, y[ok], rng_pit)
                if k_anchura:
                    med = np.median(x1)
                    for kk, fk in enumerate(k_anchura):
                        dk[ii, j, kk] = ((y[ok] >= med - fk * (med - q[0])) & (y[ok] <= med + fk * (q[3] - med)))
            if H >= 5:
                ini = idx[(filas["año"].to_numpy()[idx] % 5) == 1]
                if len(ini):
                    y5 = _acumulada_5(V, suc, ini)
                    X5 = esc.acumulada()[:, 4, :]
                    for j in range(A):
                        ok = np.isfinite(y5[:, j])
                        x1 = X5[np.isfinite(X5[:, j]), j]
                        if not ok.any() or len(p05[j]) < n_min_pool or len(x1) < n_min_pool:
                            continue
                        ii = ini[ok]
                        h5["y5"][ii, j] = y5[ok, j]
                        h5["crps0_5"][ii, j] = E.crps_muestra(p05[j], y5[ok, j])
                        h5["crps1_5"][ii, j] = E.crps_muestra(x1, y5[ok, j])
                        q = np.quantile(x1, [0.05, 0.95])
                        h5["dentro90_5"][ii, j] = (y5[ok, j] >= q[0]) & (y5[ok, j] <= q[1])
    sel = prueba
    res = {k: v[sel] for k, v in out.items()}
    res.update({"pais": filas["pais"].to_numpy()[sel], "año": filas["año"].to_numpy()[sel],
                "s_prev": filas["s_prev"].to_numpy()[sel], "y": V[sel], "infl": infl[sel]})
    if k_anchura:
        res["dentro_k"] = dk[sel]
    if H >= 5:
        res.update({k: v[sel] for k, v in h5.items()})
    return res


def resumen_motor(ev: dict) -> dict:
    """Estadísticos del prerregistro: d (fila), C1 (DM por años), CRPSS, S5, Sb, S_a, cobertura p10-p90."""
    c0, c1 = ev["crps0"], ev["crps1"]
    usa = np.isfinite(c0).any(1)
    escala = np.nanmean(c0[usa], 0)
    d = np.nanmean((c0[usa] - c1[usa]) / escala, 1)
    crpss = 1 - np.nanmean(c1[usa], 0) / escala
    dm = E.dm_conglomerado(d, ev["año"][usa], lags=2)
    dn = ev["dentro90"]
    fila = np.isfinite(dn).any(1)
    S5 = float(np.mean(np.nanmean(dn[fila], 1)))
    Sa = np.nanmean(dn, 0)
    return {"filas": int(usa.sum()), "años": dm["años"], "d_media": dm["media"], "dm": dm,
            "crpss_%": dict(zip(ACTIVOS, np.round(100 * crpss, 3).tolist())),
            "crpss_medio_%": round(100 * float(np.nanmean(crpss)), 3),
            "S5": S5, "Sb": float(Sa[0]), "S_activo": dict(zip(ACTIVOS, np.round(Sa, 4).tolist())),
            "cobertura_80_activo": dict(zip(ACTIVOS, np.round(np.nanmean(ev["dentro80"], 0), 4).tolist())),
            "cobertura_90_m0_activo": dict(zip(ACTIVOS, np.round(np.nanmean(ev["dentro90_m0"], 0), 4).tolist())),
            "n_activo": dict(zip(ACTIVOS, np.isfinite(dn).sum(0).astype(int).tolist()))}
