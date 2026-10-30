"""Validador INT-11 v2 (30-oct; A POSTERIORI; ver docs/validation/2026-10-30_int11v2.md). Diagnósticos sin cruzar
resultados con el régimen:
  iid      reproduce el experimento iid del diseño §1 (t ν = 4,5) que fijó c = 4: cobertura del p5-p95 de la
           predictiva "bootstrap bayesiano + ruido t5 de varianza c/n" para n = 20 … 1000 y c = 0 … 6
  curtosis el error de medida del factor de país usa la curtosis AGRUPADA del panel; con países de distinta escala la
           mezcla infla la curtosis. Se compara con la curtosis de la desviación estandarizada por país y se recalcula
           el posterior (solo Y, ≤ 2004, sin régimen)
Uso: .venv/bin/python -m scripts.val_int11v2_diag {iid|curtosis}
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

from scripts.int11_corrida import cargar_real
from src.intl import data as D
from src.intl import escenarios as E
from src.intl.procedencia import procedencia

OUT = Path(__file__).resolve().parents[1] / "research/int/val_int11v2"


def iid(R=3000, seed=11):
    rng = np.random.default_rng(seed)
    out = {}
    for n in (20, 34, 65, 150, 400, 1000):
        for c in (0, 1, 2, 3, 4, 5, 6):
            dentro = 0
            for _ in range(R):
                x = rng.standard_t(4.5, n + 1)
                s, y = x[:n], x[n]
                sd = np.std(s, ddof=1)
                draws = []
                for _b in range(20):                                # 20 lotes × 100 (bootstrap bayesiano)
                    w = rng.dirichlet(np.ones(n))
                    v = s[np.searchsorted(np.cumsum(w), rng.random(100) * w.sum()).clip(0, n - 1)]
                    if c:
                        v = v + rng.standard_t(5, 100) * np.sqrt(3 / 5) * sd * np.sqrt(c / n)
                    draws.append(v)
                q = np.quantile(np.concatenate(draws), [.05, .95])
                dentro += q[0] <= y <= q[1]
            out[f"n={n}|c={c}"] = round(dentro / R, 4)
        print(n, {k: v for k, v in out.items() if k.startswith(f"n={n}|")}, flush=True)
    return out


def curtosis():
    f = cargar_real(D.connect())
    assert f["año"].max() <= 2004
    g = E.Generador(E.Config.v2()).ajustar(f)
    A = len(E.ACTIVOS)
    L = g.L
    dev = (L - g.ybar)
    # misma corrección n/(n − 1) que el motor
    cnt = np.zeros((len(g.años_u), A))
    np.add.at(cnt, g.año_idx, np.isfinite(L))
    k = cnt[g.año_idx]
    dev = dev * np.sqrt(np.where(k > 1, k / np.maximum(k - 1, 1), np.nan))
    rms = np.sqrt(np.nanmean(dev ** 2, 0))
    z = dev / rms
    kurt_pool = np.nanmean(z ** 4, 0) / np.nanmean(z ** 2, 0) ** 2 - 3
    zc = np.full_like(dev, np.nan)
    for c in g.paises:
        m = g.pais == c
        zc[m] = dev[m] / np.sqrt(np.nanmean(dev[m] ** 2, 0))
    kurt_c = np.nanmean(zc ** 4, 0) / np.nanmean(zc ** 2, 0) ** 2 - 3
    # recalcular el posterior con la curtosis por país (resto idéntico al motor)
    res = {}
    for nombre, kurt in (("agrupada (motor)", kurt_pool), ("estandarizada por país", kurt_c)):
        lf, se2 = [], []
        for c in g.paises:
            m = g.pais == c
            n_c = np.isfinite(dev[m]).sum(0)
            sd_c = np.sqrt(np.nanmean(dev[m] ** 2, 0)) / rms
            lf.append(np.log(sd_c))
            se2.append((np.maximum(kurt, 0) + 2) / (4 * np.maximum(n_c, 1)))
        lf, se2 = np.array(lf), np.array(se2)
        mm = lf.mean(0)
        tau2 = np.maximum(lf.var(0, ddof=1) - se2.mean(0), 0)
        B = tau2 / (tau2 + se2)
        post = np.exp(mm + B * (lf - mm))
        res[nombre] = {"curtosis": kurt.round(2).tolist(), "tau": np.sqrt(tau2).round(3).tolist(),
                       "B_medio": B.mean(0).round(3).tolist(),
                       "factor_bolsa": dict(zip(g.paises, post[:, 0].round(3).tolist())),
                       "factor_bruto_bolsa": dict(zip(g.paises, np.exp(lf[:, 0]).round(3).tolist()))}
    res["motor_escala_resumen"] = g.escala_resumen
    return res


if __name__ == "__main__":
    t0 = time.time()
    modo = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    o = {"procedencia": procedencia(), "modo": modo, "res": iid() if modo == "iid" else curtosis(),
         "segundos": round(time.time() - t0)}
    (OUT / f"diag_{modo}.json").write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
    print(json.dumps(o, ensure_ascii=False, default=float)[:4000])
