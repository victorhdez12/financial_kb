"""P-E1 (docs/int/E1_prerregistro_v1.md, congelado v1.0): logit de CURVA (L) frente a CURVA + ACTIVIDAD (A) para la
entrada en recesión a 12 meses. Funciones puras: ajuste congelado, predicción, evaluación (ΔAUC, Δlog-loss, placebo P1
de desplazamiento circular, P2 países permutados, P3 actividad retrasada 24 m, M4 anticipación pura).
Los datos entran ya construidos por `src/intl/int13.construir` (misma tabla larga que INT-13)."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from src.intl import int4 as M4

OBJ = "E1_12"
Y = f"y_{OBJ}"
COLS = {"L": ["curva", "d12_corto"], "A": ["curva", "d12_corto", "ip_yoy", "confianza_emp"]}
ACTIVIDAD = ["ip_yoy", "confianza_emp"]
SIGNOS = {"curva": -1, "d12_corto": 1, "ip_yoy": -1, "confianza_emp": -1}
ESPERADO_DEV = (3306, 240)            # filas / eventos de E1-12 con las 4 columnas en INT-13 (P5)
SIN_2020 = (pd.Timestamp("2019-01-31"), pd.Timestamp("2021-06-30"))


def _y(mod: dict) -> str:
    return mod.get("y", Y)


def filas(df: pd.DataFrame, y: str = Y) -> pd.DataFrame:
    """Casos completos: objetivo + las 4 columnas (mismas filas para L y A)."""
    ok = df[y].notna() & df[COLS["A"]].notna().all(axis=1)
    return df[ok].reset_index(drop=True)


def ajustar(d: pd.DataFrame, yc: str = Y) -> dict:
    y = d[yc].to_numpy(float)
    out = {} if yc == Y else {"y": yc}   # E1-12: sin clave "y" (sha256 congelado de e1_modelos.json)
    for m, cols in COLS.items():
        X = d[cols].to_numpy(float)
        mu, sd = X.mean(0), X.std(0, ddof=0)
        b = M4.logit_fit((X - mu) / sd, y)
        out[m] = {"cols": cols, "media": mu.tolist(), "dt": sd.tolist(), "b": b.tolist()}
    return out


def signos_ok(mod: dict) -> dict:
    a = mod["A"]
    return {c: bool(np.sign(a["b"][1 + i]) == SIGNOS[c]) for i, c in enumerate(a["cols"])}


def sha(mod: dict) -> str:
    return hashlib.sha256(json.dumps(mod, sort_keys=True).encode()).hexdigest()


def predecir(mod: dict, d: pd.DataFrame, m: str) -> np.ndarray:
    p = mod[m]
    X = (d[p["cols"]].to_numpy(float) - np.array(p["media"])) / np.array(p["dt"])
    return M4.logit_pred(np.array(p["b"]), X)


def _delta(mod, d) -> dict:
    y = d[_y(mod)].to_numpy(float)
    pa, pl = predecir(mod, d, "A"), predecir(mod, d, "L")
    return {"dauc": M4.auc(y, pa) - M4.auc(y, pl), "dlogloss": M4.logloss(y, pa) - M4.logloss(y, pl),
            "dbrier": M4.brier(y, pa) - M4.brier(y, pl), "auc_A": M4.auc(y, pa), "auc_L": M4.auc(y, pl),
            "calib_A": M4.calibracion(y, pa), "n": int(len(y)), "eventos": int(y.sum())}


def _mover_actividad(df: pd.DataFrame, f) -> pd.DataFrame:
    """Aplica f a cada panel ancho (fecha × país) de las columnas de actividad."""
    out = df.copy()
    for c in ACTIVIDAD:
        w = df.pivot(index="fecha", columns="pais", values=c)
        w2 = f(w).rename_axis(index="fecha", columns="pais").stack(future_stack=True).rename(c)
        out = out.drop(columns=c).merge(w2.reset_index(), on=["fecha", "pais"], how="left")
    return out


def p1_circular(mod, df: pd.DataFrame) -> dict:
    """Placebo P1: desplazamiento circular k ∈ [24, T − 24] de la actividad (misma k para todos los países)."""
    fechas = np.sort(df.fecha.unique())
    T = len(fechas)
    yc = _y(mod)
    obs = _delta(mod, filas(df, yc))["dauc"]
    nulos = []
    for k in range(24, T - 23):
        g = lambda w: pd.DataFrame(np.roll(w.reindex(fechas).to_numpy(), k, axis=0), index=fechas,  # noqa: E731
                                   columns=w.columns)
        d = filas(_mover_actividad(df, g), yc)
        if d[yc].sum() > 0 and d[yc].sum() < len(d):
            nulos.append(_delta(mod, d)["dauc"])
    nulos = np.array(nulos)
    return {"dauc_obs": obs, "k": int(len(nulos)), "p": float((1 + (nulos >= obs).sum()) / (1 + len(nulos)))}


def p2_paises(mod, df) -> float:
    paises = sorted(df.pais.unique())
    rot = dict(zip(paises, paises[1:] + paises[:1]))
    g = lambda w: w.rename(columns={v: k for k, v in rot.items()})  # noqa: E731  (cada país recibe la del siguiente)
    return _delta(mod, filas(_mover_actividad(df, g), _y(mod)))["dauc"]


def p3_retraso(mod, df) -> float:
    return _delta(mod, filas(_mover_actividad(df, lambda w: w.shift(24)), _y(mod)))["dauc"]


def m4_anticipacion(mod, df, entrada_6m: pd.Series) -> dict:
    """Quita las filas con entrada en (M, M + 6] (y = 1 solo si la entrada cae en (M + 6, M + 12])."""
    d = filas(df.assign(_e6=entrada_6m.values), _y(mod))
    return _delta(mod, d[d._e6 != 1])


def evaluar(mod, df: pd.DataFrame, sin_2020: bool = True) -> dict:
    """Principal (§5) y secundarios sobre la muestra de evaluación `df` (ya "as of", objetivo cerrado)."""
    base = df
    if sin_2020:
        base = df[~df.fecha.between(*SIN_2020)]
    out = {"principal": _delta(mod, filas(base, _y(mod))), "p1": p1_circular(mod, base), "p2_dauc": p2_paises(mod, base),
           "p3_dauc": p3_retraso(mod, base)}
    if "y_E1_6" in base and _y(mod) == Y:
        out["m4"] = m4_anticipacion(mod, base, base["y_E1_6"])
    return out


# ---------------------------------------------------------------- registro en vivo (§11)
PAISES = ["BEL", "CAN", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "IRL", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
CORTO_3M = {"FIN", "IRL"}
PRIMER_ORIGEN = pd.Timestamp("2026-11-30")   # orígenes posteriores a la congelación (5-nov-2026)


def sids(c: str) -> dict:
    from src.intl import data as D
    lc = c.lower()
    return {"corto": f"oecd_ir3m_{lc}" if c in CORTO_3M else f"bis_cbpol_{D.ISO2[c]}", "irlt": f"oecd_irlt_{lc}",
            "ip": f"oecd_ip_{lc}", "bci": f"oecd_bci_{lc}"}


EURO_BCE = {"BEL", "DEU", "ESP", "FRA", "ITA", "NLD", "PRT"}   # BIS publica su tipo oficial solo hasta 1998-12
BCE_DESDE = pd.Timestamp("1999-01-01")


def rasgos(lee, rej: pd.DatetimeIndex, paises=PAISES, euro_bce: bool = False) -> pd.DataFrame:
    """Las 4 variables "as of" en el fin de cada mes de `rej`, con las MISMAS transformaciones que
    src/intl/panel.mensual + src/intl/int13.construir. `lee(sid)` devuelve la serie cruda (load_dev en el test de
    equivalencia; la tabla de últimas publicaciones hasta el corte, en vivo (scripts/e1_vivo.py))."""
    from src.intl import lags as Lg
    from src.intl import panel as P
    out = []
    for c in paises:
        s = sids(c)
        crudo = {k: lee(v) for k, v in s.items()}
        if euro_bce and c in EURO_BCE:   # enmienda 1 (docs/int/E1_enmienda_1.md): tipo del BCE desde 1999-01
            n, x = crudo["corto"], lee("bis_cbpol_xm")
            crudo["corto"] = pd.concat([n[n.index < BCE_DESDE], x[x.index >= BCE_DESDE]])
        raw = {k: P._mensual_completa(v) for k, v in crudo.items()}
        co = raw["corto"]
        corto = (pd.Series(co.values, index=M13_me(co.index)).reindex(rej) if not co.empty
                 else pd.Series(np.nan, index=rej)).shift(1)
        d = pd.DataFrame({"tipo_10a": Lg.asof(raw["irlt"], s["irlt"], rej),
                          "ip_yoy": Lg.asof(np.log(raw["ip"]).diff(12), s["ip"], rej),
                          "confianza_emp": Lg.asof(raw["bci"], s["bci"], rej)}, index=rej)
        d["curva"] = d["tipo_10a"] - corto
        d["d12_corto"] = corto - corto.shift(12)
        d["pais"] = c
        out.append(d.reset_index(names="fecha"))
    return pd.concat(out, ignore_index=True)


def meses_dato(lee, cierre: pd.Timestamp, pais: str, euro_bce: bool = True) -> dict:
    """Mes de referencia del último dato que entra en las variables "as of" en `cierre` (procedencia del registro en
    vivo; Validador 2026-11-05). Tipos: M − 1; resto: el último mes con fin + retraso ≤ cierre (src/intl/lags.py)."""
    from src.intl import lags as Lg
    s = sids(pais)
    if euro_bce and pais in EURO_BCE:
        s["corto"] = "bis_cbpol_xm"
    out = {}
    for k, sid in s.items():
        x = lee(sid).dropna()
        if k == "corto":
            ok = (x.index + pd.offsets.MonthEnd(0)) <= cierre - pd.offsets.MonthEnd(1)
        else:
            ok = Lg.disponible(x.index, sid) <= cierre
        out[k] = x.index[ok].max().strftime("%Y-%m") if ok.any() else None
    return out


def M13_me(idx):
    from src.intl import int13 as M13
    return M13._me(idx)


def prediccion(mod: dict, r: pd.DataFrame) -> pd.DataFrame:
    """P(entrada en recesión en 12 meses) de L y A para las filas con las 4 variables (no se muestra en el reporte)."""
    d = r[r[COLS["A"]].notna().all(axis=1)].copy()
    d["p_L"], d["p_A"] = predecir(mod, d, "L"), predecir(mod, d, "A")
    return d
