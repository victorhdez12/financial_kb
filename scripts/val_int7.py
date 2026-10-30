"""Validador INT-7 (30-oct): reproducción INDEPENDIENTE de V1 y V2, bootstrap nulo propio (§3.2 literal), simulación del
desplazamiento del nulo, comprobación del "as of" de `eq_dp` (§3) y sensibilidades A POSTERIORI (solo informativas).

NO toca la corrida oficial ni sus resultados (research/int/int7_resultado.*): solo los lee para comparar.
Código propio: no importa src/intl/int7, int3* ni scripts/int7_corrida; solo el cargador con corte
(src/intl/data.load_dev). MCO con variables ficticias (lstsq) para la reproducción; Driscoll-Kraay, AR(1) de Kendall,
Amihud-Hurvich y bootstrap escritos aquí.

Uso: .venv/bin/python -m scripts.val_int7 [--rapido]  → research/int/int7_validador.json (y resumen por pantalla)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl.procedencia import procedencia

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[1]
NUC = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
ANIOS = np.arange(1870, 2005)


# ------------------------------------------------------------------ datos
def cargar() -> pd.DataFrame:
    con = D.connect()
    out = []
    for c in NUC:
        s = {v: D.load_dev(con, f"jst_{c.lower()}_{v}")
             for v in ("eq_dp", "eq_tr_real", "cpi", "eq_capgain", "eq_div_rtn", "eq_tr", "bill_rate_real")}
        df = pd.DataFrame(s)
        df.index = df.index.year
        df["pais"] = c
        out.append(df)
    sh = {k: D.load_dev(con, f"shiller_{k}") for k in ("real_dividend", "real_price")}
    con.close()
    df = pd.concat(out).reset_index(names="anio")
    assert df.anio.max() <= 2004 and all(s.index.max() <= D.DEV_END for s in sh.values())
    df.attrs["shiller"] = sh
    return df


def celdas(df: pd.DataFrame, hiper: bool = True):
    W = {v: df.pivot(index="anio", columns="pais", values=v).reindex(index=ANIOS, columns=NUC)
         for v in ("eq_dp", "eq_tr_real", "cpi")}
    x = np.log(W["eq_dp"].where(W["eq_dp"] > 0))
    y = np.log1p(W["eq_tr_real"])
    infl = W["cpi"] / W["cpi"].shift(1) - 1
    H = (infl > 0.5) & infl.notna() if hiper else pd.DataFrame(False, index=x.index, columns=x.columns)
    return x, y, H, x.notna() & ~H


# ------------------------------------------------------------------ estimadores propios
def dk(Xf: np.ndarray, y: np.ndarray, anio: np.ndarray, k: int = 0, L: int | None = None) -> tuple[float, float]:
    """MCO con la matriz completa (ficticias incluidas); DK: puntuaciones por año, Bartlett, × T/(T − 1)."""
    beta, *_ = np.linalg.lstsq(Xf, y, rcond=None)
    e = y - Xf @ beta
    inv = np.linalg.pinv(Xf.T @ Xf)
    a = np.asarray(anio) - np.min(anio)
    h = np.zeros((a.max() + 1, Xf.shape[1]))
    np.add.at(h, a, Xf * e[:, None])
    T = len(np.unique(a))
    L = int(np.floor(4 * (T / 100) ** (2 / 9))) if L is None else L
    S = h.T @ h
    for l in range(1, L + 1):
        G = h[l:].T @ h[:-l]
        S += (1 - l / (L + 1)) * (G + G.T)
    V = inv @ S @ inv * T / (T - 1)
    return float(beta[k]), float(beta[k] / np.sqrt(V[k, k]))


def ar1k(Zw: pd.DataFrame, clean: pd.DataFrame):
    V = pd.DataFrame(np.nan, index=Zw.index, columns=Zw.columns)
    info = {}
    for c in Zw.columns:
        x = Zw[c].where(clean[c])
        ok = x.shift(1).notna() & x.notna()
        a, b = x.shift(1)[ok], x[ok]
        phi = float(((a - a.mean()) * (b - b.mean())).sum() / ((a - a.mean()) ** 2).sum())
        phic = min(phi + (1 + 3 * phi) / int(ok.sum()), 0.999)
        cc = float(b.mean() - phic * a.mean())
        V[c] = (x - cc - phic * x.shift(1)).where(ok)
        info[c] = (phi, phic, cc)
    return V, info


def filas(x, y, H, rez_x: int = 0, y_mas: int = 1) -> pd.DataFrame:
    """Fila t: x_{t−rez_x} y y_{t+y_mas}; sin hiperinflación en t − rez_x … t + y_mas."""
    out = []
    for c in x.columns:
        for t in range(1870 + rez_x, 2005 - y_mas):
            if (np.isfinite(x.at[t - rez_x, c]) and np.isfinite(y.at[t + y_mas, c])
                    and not H.loc[t - rez_x: t + y_mas, c].any()):
                out.append((c, t))
    return pd.DataFrame(out, columns=["pais", "t"])


def dos_vias(vals, pais, anio):
    Dm = np.column_stack([pd.get_dummies(pais).to_numpy(float), pd.get_dummies(anio).to_numpy(float)])
    b, *_ = np.linalg.lstsq(Dm, vals, rcond=None)
    return vals - Dm @ b


def ficticias(F: pd.DataFrame, anio: bool) -> np.ndarray:
    d = pd.get_dummies(F.pais).to_numpy(float)
    if anio:
        d = np.column_stack([d, pd.get_dummies(F.t).to_numpy(float)[:, 1:]])
    return d


def ajustar(x, y, H, clean, anio: bool, X_niveles=None, rez_x: int = 0, y_mas: int = 1) -> dict:
    F = filas(x, y, H, rez_x, y_mas)
    xs = x if X_niveles is None else X_niveles
    xv = np.array([xs.at[t, c] for c, t in zip(F.pais, F.t)]) if rez_x == 0 else \
        np.array([xs.at[t - rez_x, c] for c, t in zip(F.pais, F.t)])
    mu, sd = xv.mean(), xv.std(ddof=1)
    Z = (xs - mu) / sd
    if anio:
        st = Z.where(clean).stack().dropna()
        Zu = pd.Series(dos_vias(st.to_numpy(), st.index.get_level_values(1), st.index.get_level_values(0)),
                       index=st.index).unstack().reindex(index=Z.index, columns=Z.columns)
    else:
        Zu = Z
    V, info = ar1k(Zu, clean)
    F["z"] = [Zu.at[t - rez_x, c] for c, t in zip(F.pais, F.t)]
    F["y"] = [y.at[t + y_mas, c] for c, t in zip(F.pais, F.t)]
    F["v"] = [V.at[t + 1, c] if t + 1 <= 2004 else np.nan for c, t in zip(F.pais, F.t)]
    b, t = dk(np.column_stack([F.z, ficticias(F, anio)]), F.y.to_numpy(), F.t.to_numpy())
    out = {"filas": int(len(F)), "log_dp_media": mu, "log_dp_dt": sd, "b_mco": b, "t_dk": t}
    if rez_x == 0 and y_mas == 1 and X_niveles is None:
        G = F[F.v.notna()]
        Xa = np.column_stack([G.z, G.v, ficticias(G, anio)])
        out["b_ah"] = dk(Xa, G.y.to_numpy(), G.t.to_numpy(), 0)[0]
        out["gamma_v"] = dk(Xa, G.y.to_numpy(), G.t.to_numpy(), 1)[0]
        out["filas_ah"] = int(len(G))
        out["phi_mco_media"] = float(np.mean([v[0] for v in info.values()]))
        out["phi_c_media"] = float(np.mean([v[1] for v in info.values()]))
        if anio:
            out["dt_relativa_sobre_total"] = float(np.std(F.z, ddof=1))
    out["_F"], out["_Zu"], out["_V"], out["_info"] = F, Zu, V, info
    return out


# ------------------------------------------------------------------ bootstrap nulo (§3.2) escrito aquí
class TStat:
    """t DK de b con efectos fijos por Frisch-Waugh sobre un conjunto fijo de filas (rápido para el bootstrap)."""

    def __init__(self, pi, ti, anio: bool):
        self.pi, self.ti, self.anio = pi, ti, anio
        if anio:
            Dm = np.column_stack([np.eye(pi.max() + 1)[pi], np.eye(ti.max() + 1)[ti]])
            self.M = np.eye(len(pi)) - Dm @ np.linalg.pinv(Dm)
        self.cnt = np.bincount(pi).astype(float)
        self.T = len(np.unique(ti))
        self.L = int(np.floor(4 * (self.T / 100) ** (2 / 9)))
        self.ny = ti.max() + 1

    def res(self, a):
        return self.M @ a if self.anio else a - (np.bincount(self.pi, a) / self.cnt)[self.pi]

    def __call__(self, z, y):
        zt, yt = self.res(z), self.res(y)
        b = zt @ yt / (zt @ zt)
        h = np.bincount(self.ti, zt * (yt - b * zt), minlength=self.ny)
        S = h @ h
        for l in range(1, self.L + 1):
            S += 2 * (1 - l / (self.L + 1)) * (h[l:] @ h[:-l])
        return b, b / np.sqrt(S / (zt @ zt) ** 2 * self.T / (self.T - 1))


def pares(F, Zu, V, info, clean, anio: bool, ts: TStat, irrestricto: bool = False) -> dict:
    pi = np.array([NUC.index(c) for c in F.pais])
    ti = F.t.to_numpy() - 1870
    yv, zv = F.y.to_numpy(), F.z.to_numpy()
    if irrestricto:                                    # A POSTERIORI: residuo sin la parte predecible, luego b = 0
        yv = yv - ts(zv, yv)[0] * zv
    e = ts.res(yv)
    n, N = len(ANIOS), len(NUC)
    E = np.full((n, N), np.nan)
    E[ti + 1, pi] = e
    return {"E": E, "V": V.to_numpy(), "Zc": Zu.where(clean).to_numpy(), "pi": pi, "ti": ti, "ts": ts,
            "phic": np.array([info[c][1] for c in NUC]), "c": np.array([info[c][2] for c in NUC]),
            "alpha": np.bincount(pi, yv) / np.bincount(pi)}


def replica(P: dict, rng, bloque: int) -> float:
    E, Vm, Zc = P["E"], P["V"], P["Zc"]
    n, N = E.shape
    val = np.isfinite(E) & np.isfinite(Vm)
    pool = np.nonzero(val.any(1))[0]
    st = rng.integers(0, len(pool) - bloque + 1, -(-n // bloque))
    src = pool[(st[:, None] + np.arange(bloque)).ravel()][:n]
    Es, Vs = E[src].copy(), Vm[src].copy()
    bad = ~val[src]
    for j in range(N):
        if bad[:, j].any():
            pk = rng.choice(np.nonzero(val[:, j])[0], bad[:, j].sum())
            Es[bad[:, j], j], Vs[bad[:, j], j] = E[pk, j], Vm[pk, j]
    X = np.full((n, N), np.nan)
    for j in range(N):
        f = np.nonzero(np.isfinite(Zc[:, j]))[0]
        if len(f):
            X[f[0], j] = Zc[f[0], j]
            for s in range(f[0] + 1, n):
                X[s, j] = P["c"][j] + P["phic"][j] * X[s - 1, j] + Vs[s, j]
    z = X[P["ti"], P["pi"]]
    y = P["alpha"][P["pi"]] + Es[P["ti"] + 1, P["pi"]]
    return float(P["ts"](z, y)[1])


def p_boot(t0: float, tb: np.ndarray) -> float:
    B = len(tb)
    return float(min(1.0, 2 * min((1 + (tb >= t0).sum()) / (B + 1), (1 + (tb <= t0).sum()) / (B + 1))))


def bootstrap_real(x, y, H, clean, anio: bool, B: int, semillas: list[int]) -> dict:
    r = ajustar(x, y, H, clean, anio)
    F = r["_F"]
    ts = TStat(np.array([NUC.index(c) for c in F.pais]), F.t.to_numpy() - 1870, anio)
    t0 = r["t_dk"]
    out = {}
    for irr in (False, True):
        P = pares(F, r["_Zu"], r["_V"], r["_info"], clean, anio, ts, irr)
        for bl in (5, 1):
            for sd in (semillas if (not irr and bl == 5) else semillas[:1]):
                rng = np.random.default_rng(sd)
                tb = np.array([replica(P, rng, bl) for _ in range(B)])
                k = f"{'irrestricto' if irr else 'literal'}_bloque{bl}_semilla{sd}"
                out[k] = {"p": p_boot(t0, tb), "t_nula_media": float(tb.mean()),
                          "t_nula_p2.5_p97.5": [float(np.quantile(tb, .025)), float(np.quantile(tb, .975))]}
    return {"t_obs": t0, "B": B, "variantes": out}


# ------------------------------------------------------------------ simulación del mecanismo
def panel_sint(rng, n, N, phi, delta, bpp, rho=0.35, sy=0.20):
    f, g = rng.standard_normal(n), rng.standard_normal((n, N))
    v = np.sqrt(rho) * f[:, None] + np.sqrt(1 - rho) * g
    fw, gw = rng.standard_normal(n), rng.standard_normal((n, N))
    e = delta * v + np.sqrt(1 - delta ** 2) * (np.sqrt(rho) * fw[:, None] + np.sqrt(1 - rho) * gw)
    X = np.empty((n, N))
    X[0] = rng.standard_normal(N) / np.sqrt(1 - phi ** 2)
    for t in range(1, n):
        X[t] = phi * X[t - 1] + v[t]
    Y = np.full((n, N), np.nan)
    Y[1:] = bpp * X[:-1] * np.sqrt(1 - phi ** 2) + sy * e[1:]
    return X, Y


def pares_sint(X, Y, irrestricto: bool) -> dict:
    n, N = X.shape
    ti, pi = np.nonzero(np.ones((n - 1, N), bool))
    ts = TStat(pi, ti, False)
    z = (X - X[:-1].mean()) / X[:-1].std(ddof=1)
    zv, yv = z[ti, pi], Y[ti + 1, pi]
    t0 = ts(zv, yv)[1]
    if irrestricto:
        yv = yv - ts(zv, yv)[0] * zv
    E = np.full((n, N), np.nan)
    E[ti + 1, pi] = ts.res(yv)
    V = np.full((n, N), np.nan)
    c, pc = np.zeros(N), np.zeros(N)
    for j in range(N):
        a, b = z[:-1, j], z[1:, j]
        ph = np.cov(a, b)[0, 1] / np.var(a, ddof=1)
        pc[j] = min(ph + (1 + 3 * ph) / len(a), 0.999)
        c[j] = b.mean() - pc[j] * a.mean()
        V[1:, j] = b - c[j] - pc[j] * a
    return {"E": E, "V": V, "Zc": z, "phic": pc, "c": c, "alpha": np.bincount(pi, yv) / np.bincount(pi), "pi": pi,
            "ti": ti, "ts": ts, "t0": t0}


def simular(R: int, B: int, n: int = 130, N: int = 14) -> list[dict]:
    casos = [(0.8, -0.8, 0.0), (0.9, -0.9, 0.0), (0.8, -0.8, 0.01), (0.8, -0.8, 0.015), (0.8, -0.8, 0.02),
             (0.8, -0.8, 0.03)]
    variantes = {"literal_bloque5 (prerregistro)": (False, 5), "literal_bloque1 (Nelson-Kim)": (False, 1),
                 "irrestricto_bloque5": (True, 5)}
    out = []
    for i, (phi, delta, bpp) in enumerate(casos):
        rng = np.random.default_rng(1000 + i)
        acc = {k: {"tm": [], "p": []} for k in variantes}
        t0s = []
        for _ in range(R):
            X, Y = panel_sint(rng, n, N, phi, delta, bpp)
            for k, (irr, bl) in variantes.items():
                P = pares_sint(X, Y, irr)
                tb = np.array([replica(P, rng, bl) for _ in range(B)])
                acc[k]["tm"].append(tb.mean())
                acc[k]["p"].append(p_boot(P["t0"], tb))
            t0s.append(P["t0"])
        o = {"phi": phi, "delta": delta, "b_pp_por_dt": round(100 * bpp, 2), "paneles": R, "B": B,
             "paises_x_años": [N, n], "t_obs_media": float(np.mean(t0s)),
             "rechazo_t_ingenuo_1.96": float(np.mean(np.abs(t0s) > 1.96))}
        for k, v in acc.items():
            p = np.array(v["p"])
            o[k] = {"t_nula_media": float(np.mean(v["tm"])), "rechazo_0.05": float(np.mean(p <= 0.05)),
                    "rechazo_0.025": float(np.mean(p <= 0.025)), "rechazo_0.0125": float(np.mean(p <= 0.0125))}
        print(json.dumps(o), flush=True)
        out.append(o)
    return out


# ------------------------------------------------------------------ "as of" de eq_dp (§3, aviso pendiente)
def eq_dp_asof(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["eq_dp", "eq_div_rtn", "eq_capgain"])
    a = (d.eq_div_rtn - d.eq_dp).abs()
    b = (d.eq_div_rtn - d.eq_dp * (1 + d.eq_capgain)).abs()
    d2 = df.dropna(subset=["eq_tr", "eq_capgain", "eq_div_rtn"])
    sh = df.attrs["shiller"]
    rd, rp = sh["real_dividend"], sh["real_price"]
    u = df[df.pais == "USA"].set_index("anio").eq_dp
    filas_ = []
    for yv in range(1872, 2005):
        Dy = rd[rd.index.year == yv].mean()
        filas_.append({"anio": yv, "jst": u.get(yv, np.nan),
                       "precio_diciembre_t": Dy / rp[pd.Timestamp(f"{yv}-12-01")],
                       "precio_medio_t": Dy / rp[rp.index.year == yv].mean(),
                       "precio_diciembre_t_menos_1": Dy / rp[pd.Timestamp(f"{yv - 1}-12-01")],
                       "precio_enero_t": Dy / rp[pd.Timestamp(f"{yv}-01-01")]})
    S = pd.DataFrame(filas_).dropna()
    comp = {k: {"mediana_abs_log_ratio": float(np.median(np.abs(np.log(S.jst / S[k])))),
                "corr_log": float(np.corrcoef(np.log(S.jst), np.log(S[k]))[0, 1])}
            for k in ("precio_diciembre_t", "precio_medio_t", "precio_diciembre_t_menos_1", "precio_enero_t")}
    return {"pais_años": int(len(d)),
            "identidad_div_rtn_igual_dp_por_(1+capgain)": {"max_abs": float(b.max()), "mediana_abs": float(b.median())},
            "alternativa_div_rtn_igual_dp": {"mediana_abs": float(a.median()), "max_abs": float(a.max())},
            "identidad_eq_tr_igual_capgain_mas_div_rtn_mediana_abs": float((d2.eq_tr - d2.eq_capgain - d2.eq_div_rtn)
                                                                           .abs().median()),
            "usa_frente_a_shiller_1872_2004": {"años": int(len(S)), **comp}}


# ------------------------------------------------------------------ sensibilidades a posteriori
def sensibilidades(df) -> dict:
    x, y, H, clean = celdas(df)
    out = {}
    for nom, anio in (("V1", False), ("V2", True)):
        o = {}
        # 1) qué filas quita la regla de hiperinflación y cuánto pesan
        x0, y0, H0, c0 = celdas(df, hiper=False)
        F0 = filas(x0, y0, H0)
        F1 = filas(x, y, H)
        quitadas = sorted(set(map(tuple, F0[["pais", "t"]].values)) - set(map(tuple, F1[["pais", "t"]].values)))
        o["hiperinflacion_filas_quitadas"] = [f"{c} {t}" for c, t in quitadas]
        # 2) sin la regla, pero quitando solo DEU 1922-1924 (t) — para ver si es un único episodio
        Hd = H0.copy()
        for t in (1921, 1922, 1923, 1924):
            Hd.at[t, "DEU"] = True
        r = ajustar(x0, y0, Hd, x0.notna() & ~Hd, anio)
        o["sin_regla_salvo_DEU_1921_1924"] = {"b_mco": r["b_mco"], "t_dk": r["t_dk"], "filas": r["filas"]}
        # 3) dos mitades (MCO, t) para ver de dónde sale el efecto
        r = ajustar(x, y, H, clean, anio)
        F = r["_F"]
        for lab, m in (("t<=1949", F.t <= 1949), ("t>=1950", F.t >= 1950), ("t>=1950_sin_1995_2003", (F.t >= 1950) &
                                                                              (F.t < 1995))):
            G = F[m]
            b, t = dk(np.column_stack([G.z, ficticias(G, anio)]), G.y.to_numpy(), G.t.to_numpy())
            o[f"mitad_{lab}"] = {"b_mco": b, "t_dk": t, "filas": int(len(G))}
        # 4) dejar un país fuera (MCO): rango
        bs = {}
        for c in NUC:
            G = F[F.pais != c]
            bs[c] = dk(np.column_stack([G.z, ficticias(G, anio)]), G.y.to_numpy(), G.t.to_numpy())
        o["dejar_un_pais_fuera"] = {"b_min": min(v[0] for v in bs.values()), "b_max": max(v[0] for v in bs.values()),
                                    "t_min": min(v[1] for v in bs.values()), "t_max": max(v[1] for v in bs.values()),
                                    "pais_t_min": min(bs, key=lambda k: bs[k][1])}
        out[nom] = o
    # 5) estricta x_{t-1} → y_{t+1} y x_t → y_{t+2}: comprobación de que son la misma regresión (nota del Constructor)
    a = ajustar(x, y, H, clean, False, rez_x=1)
    b = ajustar(x, y, H, clean, False, y_mas=2)
    out["estricta_vs_t_mas_2_V1"] = {"estricta": [a["b_mco"], a["t_dk"], a["filas"]],
                                     "t_mas_2": [b["b_mco"], b["t_dk"], b["filas"]]}
    return out


def limpiar(o):
    if isinstance(o, dict):
        return {k: limpiar(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [limpiar(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 5)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def main() -> None:
    rapido = "--rapido" in sys.argv
    t_ini = time.time()
    proc = procedencia(exigir_limpio=False)
    oficial = json.loads((REPO / "research" / "int" / "int7_resultado.json").read_text())["confirmatorias"]
    df = cargar()
    x, y, H, clean = celdas(df)
    res = {"procedencia": proc, "a_posteriori": "todo salvo 'reproduccion' es A POSTERIORI y no cambia veredictos"}
    rep = {}
    for nom, anio in (("V1", False), ("V2", True)):
        r = ajustar(x, y, H, clean, anio)
        o = oficial[nom]
        rep[nom] = {"validador": {k: v for k, v in r.items() if not k.startswith("_")},
                    "oficial": {"filas": o["filas"], "b_mco": o["mco"]["b"], "t_dk": o["mco"]["t"],
                                "b_ah": o["amihud_hurvich"]["b"], "gamma_v": o["amihud_hurvich"]["gamma_v"],
                                "filas_ah": o["amihud_hurvich"]["filas"],
                                "t_nula_media": o["bootstrap_nulo"]["t_nula_media"], "p": o["bootstrap_nulo"]["p"]}}
        print(nom, json.dumps(limpiar(rep[nom])), flush=True)
    res["reproduccion"] = rep
    res["eq_dp_asof"] = eq_dp_asof(df)
    print("eq_dp", json.dumps(limpiar(res["eq_dp_asof"])), flush=True)
    B = 499 if rapido else 4999
    res["bootstrap_real"] = {nom: bootstrap_real(x, y, H, clean, anio, B, [20261030, 1, 2])
                             for nom, anio in (("V1", False), ("V2", True))}
    print("boot", json.dumps(limpiar(res["bootstrap_real"])), flush=True)
    res["sensibilidades"] = sensibilidades(df)
    print("sens", json.dumps(limpiar(res["sensibilidades"])), flush=True)
    res["simulacion"] = simular(*((20, 49) if rapido else (300, 199)))
    res["segundos"] = round(time.time() - t_ini, 1)
    if rapido:
        print("[rápido: no se escribe]")
        return
    (REPO / "research" / "int" / "int7_validador.json").write_text(json.dumps(limpiar(res), indent=1,
                                                                              ensure_ascii=False))


if __name__ == "__main__":
    main()
