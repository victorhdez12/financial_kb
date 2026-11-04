"""Análisis ANIDADO del HPO exploratorio de INT-11 v3 (ver scripts/hpo_int11.py y docs/int/HPO_INT11_exploratorio.md).

Lee research/int/hpo_int11/corrida_s{0,1}.{npz,json} → research/int/hpo_int11/resultado.{json,md} y registro.csv
(todas las configuraciones probadas, LOCO plano). Árbol limpio (procedencia).
"""
from __future__ import annotations

import json
import warnings

import numpy as np
from scipy import stats

from scripts.hpo_int11 import ACTS, B_BOOT, BLOQUE_AÑOS, SALIDA, TOL_ACT, TOL_S5, A
from scripts.int11_v3_corrida import cargar_real_v3
from src.intl import data as D
from src.intl import escenarios as E
from src.intl.procedencia import procedencia

MET = ("crps", "ls", "pit", "dentro", "ancho")


def cargar(i):
    z = np.load(SALIDA / f"corrida_s{i}.npz")
    meta = json.loads((SALIDA / f"corrida_s{i}.json").read_text())
    return ({k: z[f"{k}_simple"] for k in MET}, {k: z[f"{k}_par"] for k in MET}, meta)


# ---------------------------------------------------------------- estadísticos (con pesos por fila: bootstrap por años)
def s5(d, w):
    fila = np.isfinite(d).any(1)
    return float(np.sum(w[fila] * np.nanmean(d[fila], 1)) / np.sum(w[fila]))


def s_act(d, w):
    ok = np.isfinite(d)
    return np.array([np.sum(w[ok[:, a]] * d[ok[:, a], a]) / max(np.sum(w[ok[:, a]]), 1e-12) for a in range(A)])


def crps_rel(c1, c0, w):
    """media por activo de Σ w·CRPS_1 / Σ w·CRPS_0 − 1 (filas con dato en los dos)."""
    ok = np.isfinite(c1) & np.isfinite(c0)
    r = [np.sum(w[ok[:, a]] * c1[ok[:, a], a]) / np.sum(w[ok[:, a]] * c0[ok[:, a], a]) for a in range(A)]
    return float(np.mean(r) - 1)


def ls_dif(l1, l0, w):
    ok = np.isfinite(l1) & np.isfinite(l0)
    return float(np.mean([np.sum(w[ok[:, a]] * (l1 - l0)[ok[:, a], a]) / np.sum(w[ok[:, a]]) for a in range(A)]))


def pit_chi2(p):
    """χ² de uniformidad del PIT (10 bins) por activo: (estadístico, p)."""
    out = []
    for a in range(A):
        x = p[:, a][np.isfinite(p[:, a])]
        if len(x) < 20:
            out.append((np.nan, np.nan))
            continue
        h = np.histogram(np.clip(x, 0, 1 - 1e-12), bins=10, range=(0, 1))[0]
        r = stats.chisquare(h)
        out.append((round(float(r.statistic), 2), round(float(r.pvalue), 4)))
    return out


def pit_desv(p):
    """máx |frecuencia del decil − 0,10| con todos los activos juntos."""
    x = p[np.isfinite(p)]
    h = np.histogram(np.clip(x, 0, 1 - 1e-12), bins=10, range=(0, 1))[0] / max(len(x), 1)
    return round(float(np.max(np.abs(h - 0.1))), 4)


def elegir(dn, cr, cr0, w):
    """Regla fijada antes: admisibles |S5 − 0,90| ≤ TOL_S5 y |S_a − 0,90| ≤ TOL_ACT; menor CRPS relativo a v3 (θ0)."""
    mejor, val = 0, np.inf
    for t in range(dn.shape[0]):
        if abs(s5(dn[t], w) - 0.90) > TOL_S5 or np.any(np.abs(s_act(dn[t], w) - 0.90) > TOL_ACT):
            continue
        v = crps_rel(cr[t], cr0, w)
        if v < val:
            mejor, val = t, v
    return mejor, val


def anidado(S, P, pais, paises):
    """Para cada país externo c: interno = pares (fuera {c, d}) sobre las filas de d ≠ c; externo = LOCO simple."""
    m = len(pais)
    w1 = np.ones(m)
    eleg, out = {}, {k: np.full((m, A), np.nan) for k in MET}
    for ic, c in enumerate(paises):
        r = pais != c
        dn, cr = P["dentro"][:, ic][:, r], P["crps"][:, ic][:, r]
        t, v = elegir(dn, cr, cr[0], w1[r])
        eleg[c] = {"id": int(t), "crps_rel_interno": round(float(v), 5) if np.isfinite(v) else None,
                   "S5_interno": round(s5(dn[t], w1[r]), 4), "S5_interno_v3": round(s5(dn[0], w1[r]), 4)}
        rc = pais == c
        for k in MET:
            out[k][rc] = S[k][t][rc]
    return out, eleg


def resumen(X, X0, sel, w=None):
    w = np.ones(sel.sum()) if w is None else w
    d, d0 = X["dentro"][sel], X0["dentro"][sel]
    return {"filas": int(sel.sum()), "S5": round(s5(d, w), 4), "S5_v3": round(s5(d0, w), 4),
            "S_activo": dict(zip(ACTS, s_act(d, w).round(4).tolist())),
            "crps": dict(zip(ACTS, np.nanmean(X["crps"][sel], 0).round(5).tolist())),
            "crps_rel_v3": round(crps_rel(X["crps"][sel], X0["crps"][sel], w), 5),
            "ls_dif_v3": round(ls_dif(X["ls"][sel], X0["ls"][sel], w), 5),
            "ls": dict(zip(ACTS, np.nanmean(X["ls"][sel], 0).round(4).tolist())),
            "ancho": dict(zip(ACTS, np.nanmean(X["ancho"][sel], 0).round(4).tolist())),
            "pit_chi2": dict(zip(ACTS, pit_chi2(X["pit"][sel]))), "pit_chi2_v3": dict(zip(ACTS, pit_chi2(X0["pit"][sel]))),
            "pit_desv": pit_desv(X["pit"][sel]), "pit_desv_v3": pit_desv(X0["pit"][sel])}


def boot(X, X0, años, rng):
    """IC 90 % por bloques móviles de años (todas las filas de un año entran juntas: choques comunes)."""
    au = np.unique(años)
    T = len(au)
    pos = np.searchsorted(au, años)
    nb = int(np.ceil(T / BLOQUE_AÑOS))
    est = {"dS5": [], "crps_rel": [], "ls_dif": [], "dS_bolsa": []}
    for _ in range(B_BOOT):
        st = rng.integers(0, T - BLOQUE_AÑOS + 1, nb)
        cnt = np.bincount((st[:, None] + np.arange(BLOQUE_AÑOS)[None]).ravel()[:T], minlength=T).astype(float)
        w = cnt[pos]
        est["dS5"].append(s5(X["dentro"], w) - s5(X0["dentro"], w))
        est["crps_rel"].append(crps_rel(X["crps"], X0["crps"], w))
        est["ls_dif"].append(ls_dif(X["ls"], X0["ls"], w))
        est["dS_bolsa"].append(s_act(X["dentro"], w)[0] - s_act(X0["dentro"], w)[0])
    w1 = np.ones(len(años))
    punto = {"dS5": s5(X["dentro"], w1) - s5(X0["dentro"], w1), "crps_rel": crps_rel(X["crps"], X0["crps"], w1),
             "ls_dif": ls_dif(X["ls"], X0["ls"], w1),
             "dS_bolsa": s_act(X["dentro"], w1)[0] - s_act(X0["dentro"], w1)[0]}
    return {k: {"punto": round(float(punto[k]), 5),
                "ic90": np.percentile(v, [5, 95]).round(5).tolist()} for k, v in est.items()}


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    proc = procedencia()
    f = cargar_real_v3(D.connect())
    f = E.recalcular_sucesor(f)
    pais, años, sprev = f["pais"].to_numpy(), f["año"].to_numpy(), f["s_prev"].to_numpy()
    paises = sorted(set(pais))
    corr = [cargar(i) for i in (0, 1)]
    cands = corr[0][2]["candidatos"]
    todo = np.ones(len(f), bool)
    rng = np.random.default_rng(20261106)
    o = {"procedencia": proc, "semillas": [c[2]["semilla"] for c in corr], "n_candidatos": len(cands),
         "procedencia_corridas": [c[2]["procedencia"] for c in corr]}
    # registro de TODAS las configuraciones (LOCO plano, no anidado: optimista para la mejor)
    reg = []
    for t, cd in enumerate(cands):
        fila = {"id": cd["id"], **{k: cd["params"].get(k, "v3") for k in
                                   ("c_suavizado", "nu_suavizado", "sigma_infl", "sigma_brecha", "n0_curtosis",
                                    "semivida_epoca", "n_min_celda", "log10_kappa")}}
        for i, (S, _, _) in enumerate(corr):
            X = {k: S[k][t] for k in MET}
            X0 = {k: S[k][0] for k in MET}
            fila[f"S5_s{i}"] = round(s5(X["dentro"], np.ones(len(f))), 4)
            sa = s_act(X["dentro"], np.ones(len(f)))
            fila[f"peor_activo_s{i}"] = round(float(np.max(np.abs(sa - 0.9))), 4)
            fila[f"crps_rel_s{i}"] = round(crps_rel(X["crps"], X0["crps"], np.ones(len(f))), 5)
            fila[f"ls_dif_s{i}"] = round(ls_dif(X["ls"], X0["ls"], np.ones(len(f))), 5)
            fila[f"pit_desv_s{i}"] = pit_desv(X["pit"])
        reg.append(fila)
    cols = list(reg[0])
    (SALIDA / "registro.csv").write_text("\n".join([",".join(cols)] + [",".join(str(r[c]) for c in cols) for r in reg]))
    o["registro_resumen"] = {"admisibles_loco_plano_s0": int(sum(abs(r["S5_s0"] - 0.9) <= TOL_S5 and
                                                                 r["peor_activo_s0"] <= TOL_ACT for r in reg))}
    # no anidado (selección y evaluación en las mismas filas LOCO): muestra el optimismo
    for i, (S, P, _) in enumerate(corr):
        t, v = elegir(S["dentro"], S["crps"], S["crps"][0], np.ones(len(f)))
        o[f"plano_s{i}"] = {"id": int(t), "params": cands[t]["params"], "crps_rel": round(float(v), 5) if t else 0.0}
    # anidado
    for i, (S, P, _) in enumerate(corr):
        X0 = {k: S[k][0] for k in MET}
        N, eleg = anidado(S, P, pais, paises)
        o[f"anidado_s{i}"] = {
            "eleccion": eleg, "global": resumen(N, X0, todo), "ic_bloques": boot(N, X0, años, rng),
            "por_pais": {c: resumen(N, X0, pais == c) for c in paises},
            "por_regimen": {r: resumen(N, X0, sprev == k) for k, r in enumerate(E.REGIMENES) if (sprev == k).any()},
            "v3_global": resumen(X0, X0, todo)}
    # ruido MC: v3 con la semilla B frente a v3 con la semilla A (mismas filas)
    V0 = {k: corr[0][0][k][0] for k in MET}
    V1 = {k: corr[1][0][k][0] for k in MET}
    o["ruido_mc_v3"] = boot(V1, V0, años, rng)
    # cruzado: elecciones de la semilla A evaluadas con los sorteos externos de la semilla B (maldición del ganador MC)
    eleg0 = o["anidado_s0"]["eleccion"]
    Nx = {k: np.full((len(f), A), np.nan) for k in MET}
    for c in paises:
        rc = pais == c
        for k in MET:
            Nx[k][rc] = corr[1][0][k][eleg0[c]["id"]][rc]
    o["cruzado_eleccion_s0_eval_s1"] = {"global": resumen(Nx, V1, todo), "ic_bloques": boot(Nx, V1, años, rng)}
    # banda nula por país de la corrida oficial (solo lectura)
    of = json.loads((SALIDA.parent / "int11_v3_resultado.json").read_text())
    o["banda_nula_pais_oficial"] = of["nulo"]["loco"]["pais"]
    (SALIDA / "resultado.json").write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
    print(json.dumps({k: o[k] for k in ("plano_s0", "plano_s1", "ruido_mc_v3")}, ensure_ascii=False, default=float))
    for i in (0, 1):
        a = o[f"anidado_s{i}"]
        print(i, a["global"]["S5"], a["global"]["S5_v3"], a["ic_bloques"],
              {c: v["id"] for c, v in a["eleccion"].items()})
    print("cruzado", o["cruzado_eleccion_s0_eval_s1"]["ic_bloques"])


if __name__ == "__main__":
    main()
