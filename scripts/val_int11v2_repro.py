"""Validador INT-11 v2 (30-oct; ver docs/validation/2026-10-30_int11v2.md). Reproducción de la fase D (≤ 2004):
  oficial  función oficial `Q.evaluar_motor` con las semillas congeladas (LOCO H = 5 y temporal H = 1)
  propio   evaluación LOCO con código propio (CRPS por momentos ponderados, cobertura, raros, Brier), H = 1, 3 semillas
  fuga     LOCO: destrozar los datos del país excluido no cambia ni un sorteo de su predictiva (escala, transiciones, pool)
  nulo     banda nula heterogénea con 60 paneles nuevos (semilla propia) y puntuación propia
Nada ≥ 2005. Uso: .venv/bin/python -m scripts.val_int11v2_repro {oficial|propio|fuga|nulo}
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
from scripts.int11_corrida import NUCLEO, cargar_real, estructura          # noqa: E402
from scripts.int11_v2_potencia import panel_v2                              # noqa: E402
from scripts.val_int11_repro import crps_pwm, dm                            # noqa: E402
from src.intl import data as D                                              # noqa: E402
from src.intl import escenarios as E                                        # noqa: E402
from src.intl import int11 as Q                                             # noqa: E402
from src.intl.procedencia import procedencia                                # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "research/int/val_int11v2"
SEED = 20261101
ACT = list(E.ACTIVOS)


def evaluar_propio(f, seeds_off=0, n_lotes=200, cfg=None):
    """LOCO H = 1 con código propio de puntuación. Semilla por (pliegue, país, estado) = la fórmula congelada + off."""
    cfg = cfg or E.Config.v2()
    f = E.recalcular_sucesor(f)
    V = f[ACT].to_numpy(float)
    infl = np.expm1(f["inflacion"].to_numpy(float))
    paises = sorted(f.pais.unique())
    m = len(f)
    c0 = np.full((m, 5), np.nan)
    c1, d90 = c0.copy(), c0.copy()
    pi1, pi0 = np.full(m, np.nan), np.full(m, np.nan)
    for k, c in enumerate(paises):
        tr, te = f.pais.values != c, f.pais.values == c
        gen = E.Generador(cfg).ajustar(f[tr])
        assert c not in gen.paises
        Vtr = V[tr]
        te_idx = np.flatnonzero(te)
        for s0, pos in f.iloc[te_idx].groupby("s_prev").indices.items():
            idx = te_idx[pos]
            esc = gen.simular(c, int(s0), horizonte=1, n_lotes=n_lotes, por_lote=100,
                              semilla=SEED + 1000 * k + 10 * paises.index(c) + int(s0) + seeds_off)
            R1 = esc.rent[:, 0, :]
            pi1[idx] = np.mean(np.expm1(esc.inflacion[:, 0]) > 0.05)
            it = infl[tr]
            pi0[idx] = np.mean(it[np.isfinite(it)] > 0.05)
            for j in range(5):
                y = V[idx, j]
                ok = np.isfinite(y)
                x1 = R1[np.isfinite(R1[:, j]), j]
                x0 = Vtr[np.isfinite(Vtr[:, j]), j]
                if not ok.any() or len(x0) < 30 or len(x1) < 30:
                    continue
                ii = idx[ok]
                c0[ii, j], c1[ii, j] = crps_pwm(x0, y[ok]), crps_pwm(x1, y[ok])
                q = np.quantile(x1, [.05, .95])
                d90[ii, j] = (y[ok] >= q[0]) & (y[ok] <= q[1])
    usa = np.isfinite(c0).any(1)
    esc_ = np.nanmean(c0[usa], 0)
    d = np.nanmean((c0[usa] - c1[usa]) / esc_, 1)
    fila = np.isfinite(d90).any(1)
    raro = np.isin(f.s_prev.values, (2, 3))
    yb = (infl > 0.05).astype(float)
    okb = np.isfinite(infl)
    b1, b0 = np.mean((pi1[okb] - yb[okb]) ** 2), np.mean((pi0[okb] - yb[okb]) ** 2)
    return {"S5": float(np.mean(np.nanmean(d90[fila], 1))), "Sa": np.nanmean(d90, 0).round(4).tolist(),
            "S_raros": float(np.nanmean(d90[raro])), "S_raros_bolsa": float(np.nanmean(d90[raro, 0])),
            "crpss_medio": float(100 * np.nanmean(1 - np.nanmean(c1[usa], 0) / esc_)), "dm": dm(d, f.año.values[usa]),
            "bss_infl5_%": float(100 * (1 - b1 / b0)),
            "cob_pais": {c: round(float(np.nanmean(np.nanmean(d90[fila & (f.pais.values == c)], 1))), 4)
                         for c in paises}}


def oficial(f):
    cfg = E.Config.v2()
    ev_l = Q.evaluar_motor(f, "loco", 200, 100, SEED, H=5, corte=1950, cfg=cfg)
    ev_t = Q.evaluar_motor(f, "temporal", 200, 100, SEED, H=1, corte=1950, cfg=cfg)
    L, T = Q.resumen_motor(ev_l), Q.resumen_motor(ev_t)
    raro = np.isin(ev_l["s_prev"], (2, 3))
    from scripts.int11_corrida import descriptivos
    return {"loco": {k: L[k] for k in ("S5", "Sb", "S_activo", "crpss_medio_%", "d_media", "dm")},
            "S_raros": float(np.nanmean(ev_l["dentro90"][raro])),
            "temporal": {k: T[k] for k in ("S5", "Sb", "S_activo")},
            "brier": descriptivos(ev_l)["brier"]}


def fuga(f):
    """Para ESP y FIN: el país fuera del pool; destrozar sus filas no cambia nada (sorteos idénticos bit a bit)."""
    out = {}
    cfg = E.Config.v2()
    for c in ("ESP", "FIN"):
        tr = f[f.pais != c]
        g1 = E.Generador(cfg).ajustar(tr)
        e1 = g1.simular(c, 1, horizonte=3, n_lotes=20, por_lote=100, semilla=5)
        f2 = f.copy()
        m = f2.pais == c
        for a in ACT:
            f2.loc[m, a] = f2.loc[m, a] * 5 + 1
        f2.loc[m, "s"] = (f2.loc[m, "s"] + 1) % 4
        f2.loc[m, "s_prev"] = (f2.loc[m, "s_prev"] + 2) % 4
        g2 = E.Generador(cfg).ajustar(f2[f2.pais != c])
        e2 = g2.simular(c, 1, horizonte=3, n_lotes=20, por_lote=100, semilla=5)
        # y con el país DENTRO: la escala del país cambia (control de que el test detectaría una fuga)
        g3 = E.Generador(cfg).ajustar(f)
        out[c] = {"identico_bit_a_bit": bool(np.array_equal(e1.rent, e2.rent, equal_nan=True)
                                             and np.array_equal(e1.regimen, e2.regimen)
                                             and np.array_equal(e1.inflacion, e2.inflacion, equal_nan=True)),
                  "pais_en_pool": c in g1.paises, "escala_usada": "predictiva N(m, tau2)" if c not in g1.escala_post
                  else "posterior propio", "kappa": g1.kappa,
                  "fila_transicion_igual_kappa_p_panel": bool(np.allclose(g1.posterior_transicion(c),
                                                                          g1.kappa * g1.p_panel)),
                  "factor_con_pais_dentro": np.exp(g3.escala_post[c][0]).round(3).tolist()}
    return out


def nulo(f, R=60):
    med = json.loads((REPO / "research/int/int11_potencia.json").read_text())["medicion"]
    med2 = json.loads((REPO / "research/int/int11_v2_potencia.json").read_text())["medicion_v2"]
    años, existe, ok = estructura(f)
    fac = np.array([med2["factor_pais"][c] for c in NUCLEO])
    rng = np.random.default_rng(777)
    res = {"S5": [], "S_raros": [], "S5_20lotes_real_comparable": None}
    for r in range(R):
        reg, Y, infl = panel_v2(med, med2, len(años), rng, fac=fac, fac_raro=1.0)
        fs = Q.filas_sinteticas(reg, Y, NUCLEO, años, existe, ok, infl)
        o = evaluar_propio(fs, seeds_off=900000 + 7 * r, n_lotes=20)
        res["S5"].append(o["S5"])
        res["S_raros"].append(o["S_raros"])
        if r % 10 == 9:
            print(r + 1, np.percentile(res["S5"], [2.5, 50, 97.5]).round(4), flush=True)
    return {k: {"banda_2.5_97.5": np.percentile(v, [2.5, 97.5]).round(4).tolist(), "media": round(float(np.mean(v)), 4),
                "min": round(float(np.min(v)), 4)} for k, v in res.items() if v}


if __name__ == "__main__":
    t0 = time.time()
    modo = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    con = D.connect()
    f = cargar_real(con)
    assert f["año"].max() <= 2004
    o = {"procedencia": procedencia(), "modo": modo}
    if modo == "oficial":
        o["res"] = oficial(f)
    elif modo == "propio":
        o["res"] = {f"semilla+{off}": evaluar_propio(f, off) for off in (0, 300000, 600000)}
        o["res"]["20_lotes"] = evaluar_propio(f, 0, n_lotes=20)
    elif modo == "fuga":
        o["res"] = fuga(f)
    elif modo == "nulo":
        o["res"] = nulo(f)
    o["segundos"] = round(time.time() - t0)
    (OUT / f"repro_{modo}.json").write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
    print(json.dumps(o, ensure_ascii=False, default=float)[:4000])
