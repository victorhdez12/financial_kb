"""Evaluación (CONGELADA antes de que exista ningún realizado) del registro en vivo de P-K1v.

Prerregistro: docs/int/K1_vivo_prerregistro_v1.md (§4) + docs/int/K1_vivo_enmienda_1.md. Ambigüedades resueltas:
docs/int/EVAL_registros_vivo.md (sección K1).

- Registro: `research/int/k1_vivo.jsonl` (scripts/k1_vivo.py): una línea por país y año t con p_L (B1) y p_K (B1 + Δ5
  crédito/PIB BIS), predicción del inicio de crisis bancaria sistémica en t + 1.
- Realizado: y = 1 si t + 1 es un inicio declarado en `scripts.k1_vivo.INICIOS_DESDE_2021` (la revisión anual de la
  enmienda 1 §2, con la prioridad JST > Laeven-Valencia > BCE de §4). Ventana cerrada solo si
  t + 1 ≤ `INICIOS_REVISADOS_HASTA`. Si no hay ninguna: "sin ventanas cerradas" y no escribe nada.
- Principal: filas en riesgo, con dato, SIN los inicios previos al registro (enmienda 1 §1). Conservador: un inicio en
  t + 1 sin fecha (mes) declarada en `FECHA_INICIO` cuenta como previo al registro.
- Contraste único: ΔAUC estratificada por país (`src/intl/int6.auc_estrat`) de K frente a L con las p REGISTRADAS
  (coeficientes congelados, sin reajuste); p del placebo circular (Δ5 desplazado k años, misma k en todos los países,
  k ∈ [6, T − 6], como INT-6), p = máx(p de la z, p de rangos). Solo con ≥ 20 inicios nuevos en el principal; antes,
  descriptivo.

Uso: .venv/bin/python -m scripts.eval_k1_vivo [--sintetico] [--hoy AAAA-MM-DD]
Salidas (modo real con ventanas cerradas; árbol limpio): research/int/eval_k1_vivo.json (descriptivo, se reescribe) y
research/int/eval_k1_vivo_veredicto.json (una vez).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import int4 as M
from src.intl import int6 as S

REPO = Path(__file__).resolve().parents[1]
LOG = REPO / "research/int/k1_vivo.jsonl"
MODELOS = REPO / "research/int/k1_modelos.json"
SALIDA = REPO / "research/int/eval_k1_vivo.json"
VEREDICTO = REPO / "research/int/eval_k1_vivo_veredicto.json"
MIN_INICIOS = 20                      # §4
K_MIN = 6                             # INT-6 K1: k ≥ 6 años
MIN_CLASE_PLACEBO = 10                # INT-6 (src/intl/int6.evaluar): k con < 10 eventos o no eventos no cuenta
ALFA = 0.05
CALIB = (0.5, 1.5)
TOL_P = 1e-6
# Mes de inicio de cada crisis declarada desde 2021 ((país, año) → "AAAA-MM"), para decidir si fue previo al registro.
# Ninguna declarada. Sin fecha → se trata como previa (fuera del principal).
FECHA_INICIO: dict[tuple[str, int], str] = {}
SENS_FIN_NLD = ("FIN", "NLD")         # §2: pendiente del puente ≈ 1,5
USA_2023 = 2023                       # §2: sensibilidad "contar los bancos regionales de EE. UU. de 2023"


def sig(z):
    return 1 / (1 + np.exp(-z))


def modelos() -> tuple[dict, str]:
    from scripts.k1_corrida import sha
    j = json.loads(MODELOS.read_text())
    if sha(j["modelos"]) != j["modelos_sha256"]:
        raise SystemExit("k1_modelos.json alterado")
    return j["modelos"], j["modelos_sha256"]


def predecir(mod: dict, B1, x) -> tuple[np.ndarray, np.ndarray]:
    bL, bK = np.array(mod["L"]["b"]), np.array(mod["K"]["b"])
    B1, x = np.asarray(B1, float), np.asarray(x, float)
    return sig(bL[0] + bL[1] * B1), sig(bK[0] + bK[1] * B1 + bK[2] * x)


# ---------------------------------------------------------------- registro y realizado
def leer_registro(path: Path = LOG) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    d = pd.DataFrame([json.loads(x) for x in path.read_text().splitlines() if x.strip()])
    return d.drop_duplicates(["pais", "t"], keep="first").reset_index(drop=True) if len(d) else d


def cerrados(reg: pd.DataFrame, revisado_hasta: int) -> pd.DataFrame:
    if reg.empty or "t" not in reg:
        return pd.DataFrame()
    t = pd.to_numeric(reg.t, errors="coerce")
    return reg[t.notna() & (t + 1 <= revisado_hasta)].reset_index(drop=True)


def previo(pais: str, año: int, registrado, fechas: dict = FECHA_INICIO) -> bool:
    """Inicio en `año` anterior (o en el mismo mes) al registro; sin fecha declarada → previo (conservador)."""
    f = fechas.get((pais, año))
    if f is None:
        return True
    r = pd.Timestamp(registrado)
    r = r.tz_convert(None) if r.tzinfo else r
    return pd.Timestamp(f).to_period("M") <= r.to_period("M")


def tabla(reg: pd.DataFrame, inicios: dict, fechas: dict = FECHA_INICIO) -> pd.DataFrame:
    """Filas con predicción, en riesgo y con y; columnas y, previo (inicio en t + 1 anterior al registro)."""
    d = reg.copy()
    if "sin_dato" in d:
        d = d[d.sin_dato.ne(True)]
    d = d[d.en_riesgo.eq(True) & d.p_L.notna() & d.p_K.notna()].copy()
    d["t"] = d.t.astype(int)
    d["y"] = [int(t + 1 in inicios.get(c, [])) for c, t in zip(d.pais, d.t)]
    flag = d.get("inicio_previo_al_registro", pd.Series(False, index=d.index)).fillna(False).astype(bool)
    prev = np.array([previo(c, t + 1, r, fechas) for c, t, r in zip(d.pais, d.t, d.registrado)], bool)
    d["previo"] = (d.y == 1) & (flag.to_numpy() | prev)
    return d.reset_index(drop=True)


# ---------------------------------------------------------------- métricas
def _delta(y, pK, pL, g) -> dict:
    return {"dauc_estrat": S.auc_estrat(y, pK, g) - S.auc_estrat(y, pL, g),
            "auc_estrat_K": S.auc_estrat(y, pK, g), "auc_estrat_L": S.auc_estrat(y, pL, g),
            "dauc_agrupada": M.auc(y, pK) - M.auc(y, pL), "dlogloss": M.logloss(y, pK) - M.logloss(y, pL),
            "dbrier": M.brier(y, pK) - M.brier(y, pL), "filas": int(len(y)), "inicios": int(y.sum()),
            "paises_con_inicio": int(len(np.unique(g[y == 1])))}


def placebo(mod: dict, d: pd.DataFrame, obs: float) -> dict:
    """Δ5 desplazado k años en círculo sobre el panel años × países de la muestra (misma k para todos)."""
    años = np.arange(d.t.min(), d.t.max() + 1)
    T = len(años)
    pan = d.pivot(index="t", columns="pais", values="x").reindex(años)
    ds = []
    for k in range(K_MIN, T - K_MIN + 1):
        q = pd.DataFrame(np.roll(pan.to_numpy(), k, axis=0), index=años, columns=pan.columns)
        xk = np.array([q.at[t, c] for c, t in zip(d.pais, d.t)], float)
        ok = np.isfinite(xk)
        y, g = d.y.to_numpy(float)[ok], d.pais.to_numpy()[ok]
        if y.sum() < MIN_CLASE_PLACEBO or (1 - y).sum() < MIN_CLASE_PLACEBO:
            continue
        pL, pK = predecir(mod, d.B1.to_numpy(float)[ok], xk[ok])
        ds.append(S.auc_estrat(y, pK, g) - S.auc_estrat(y, pL, g))
    if len(ds) < 2:
        return {"desplazamientos": len(ds), "p": 1.0, "nota": "sin desplazamientos suficientes (T < 13 años o pocas clases)"}
    z = S.z_placebo(obs, np.array(ds))
    return {**z, "p": float(max(z["p_z"], z["p_rangos"]))}


def medir(mod: dict, d: pd.DataFrame, placebo_: bool = True, boot: bool = True) -> dict:
    y, g, t = d.y.to_numpy(float), d.pais.to_numpy(), d.t.to_numpy()
    pL, pK = d.p_L.to_numpy(float), d.p_K.to_numpy(float)
    if y.sum() == 0 or y.sum() == len(y):
        return {"filas": int(len(y)), "inicios": int(y.sum()), "nota": "sin las dos clases"}
    out = _delta(y, pK, pL, g)
    out["calibracion_K"] = M.calibracion(y, pK)
    if boot:
        b = S.boot(y, pK, pL, t, g, B_=2000)
        out["boot"] = {k: b[k] for k in ("d_auc_ic95", "p_bloques", "d_logloss_ic95", "años")}
    if placebo_:
        out["placebo"] = placebo(mod, d, out["dauc_estrat"])
    return out


def con_usa_2023(mod: dict, d: pd.DataFrame) -> pd.DataFrame:
    """Sensibilidad §2: 2023 cuenta como inicio en USA → B1 y "en riesgo" de USA recalculados, p de nuevo."""
    d = d.copy()
    u = (d.pais == "USA") & (d.t >= USA_2023)
    d = d[~(u & (d.t - USA_2023 <= 4))].copy()
    u = (d.pais == "USA") & (d.t >= USA_2023)
    ult = pd.to_numeric(d.ultimo_inicio, errors="coerce")
    nuevo = u & (ult.isna() | (ult < USA_2023))
    d.loc[nuevo, "B1"] = np.log1p(d.loc[nuevo, "t"] - USA_2023)
    d["p_L"], d["p_K"] = predecir(mod, d.B1, d.x)
    return d.reset_index(drop=True)


def comprobar(mod: dict, sha: str, d: pd.DataFrame) -> dict:
    if "modelos_sha256" in d and (d.modelos_sha256.dropna() != sha).any():
        raise SystemExit("hay filas registradas con otro sha256 de modelos")
    pL, pK = predecir(mod, d.B1, d.x)
    dif = max(np.nanmax(np.abs(pL - d.p_L.to_numpy(float)), initial=0),
              np.nanmax(np.abs(pK - d.p_K.to_numpy(float)), initial=0))
    if dif > TOL_P:
        raise SystemExit(f"p recalculada ≠ registrada (máx {dif:.2e})")
    return {"max_dif_p": float(dif)}


def veredicto(r: dict) -> dict:
    p = r["principal"]
    if p.get("inicios", 0) < MIN_INICIOS:
        return {"veredicto": "DESCRIPTIVO (sin veredicto)", "motivo": f"{p.get('inicios', 0)} inicios nuevos < {MIN_INICIOS}"}
    c = {"i_dauc_estrat_pos_placebo": bool(p["dauc_estrat"] > 0 and p["placebo"]["p"] < ALFA),
         "ii_dlogloss_neg": bool(p["dlogloss"] < 0),
         "iii_pendiente_calib": bool(CALIB[0] <= p["calibracion_K"]["pendiente"] <= CALIB[1])}
    return {"veredicto": "CONFIRMADO" if all(c.values()) else "NO CONFIRMADO", "criterios": c}


def evaluar(reg: pd.DataFrame, inicios: dict, revisado_hasta: int, fechas: dict = FECHA_INICIO) -> dict:
    mod, sha = modelos()
    c = cerrados(reg, revisado_hasta)
    if c.empty:
        return {"cerradas": 0}
    d = tabla(c, inicios, fechas)
    out = {"cerradas": int(len(c)), "años_t": [int(d.t.min()), int(d.t.max())] if len(d) else None,
           "integridad": comprobar(mod, sha, d) if len(d) else {},
           "inicios_previos_excluidos": int(d.previo.sum())}
    pr = d[~d.previo].reset_index(drop=True)
    out["principal"] = medir(mod, pr)
    out["sens_con_previos"] = medir(mod, d, placebo_=False, boot=False)
    out["sens_usa_2023"] = medir(mod, con_usa_2023(mod, pr), placebo_=False, boot=False)
    out["sens_sin_fin_nld"] = medir(mod, pr[~pr.pais.isin(SENS_FIN_NLD)].reset_index(drop=True), placebo_=False, boot=False)
    out["por_pais"] = {k: {"filas": int(len(g)), "inicios": int(g.y.sum()),
                           "dauc": M.auc(g.y.to_numpy(float), g.p_K.to_numpy(float)) -
                           M.auc(g.y.to_numpy(float), g.p_L.to_numpy(float)) if 0 < g.y.sum() < len(g) else None}
                       for k, g in pr.groupby("pais")}
    out.update(veredicto(out))
    return out


# ---------------------------------------------------------------- sintético
def sintetico(semilla: int = 20261105, señal: float = 1.0, años: int = 70, n_olas: int = 5):
    """Registro inventado (14 países del núcleo, t = 2026 … 2026 + años − 1) con olas de crisis (≈ 70 % de los países,
    ± 1 año) y su cronología. Con `señal` > 0, Δ5 crédito sube 15·señal pp en t − 2 … t antes de cada inicio en t + 1.
    Registro a mediados de julio de t + 1; el mes de cada inicio se sortea (los anteriores a julio quedan como
    previos)."""
    from scripts.int6_corrida import NUCLEO
    rng = np.random.default_rng(semilla)
    mod, sha = modelos()
    ts = np.arange(2026, 2026 + años)
    olas = np.sort(rng.choice(np.arange(2030, 2026 + años - 3, 8), n_olas, replace=False))
    inicios, fechas, filas = {}, {}, []
    for c in NUCLEO:
        ini = sorted({int(o + rng.integers(-1, 2)) for o in olas if rng.random() < 0.7})
        inicios[c] = ini
        for a in ini:
            fechas[(c, a)] = f"{a}-{int(rng.integers(1, 13)):02d}"
        x = rng.normal(0, 8, len(ts))
        for a in ini:
            for k in range(0, 3):
                i = np.flatnonzero(ts == a - 1 - k)
                if len(i):
                    x[i] += 15 * señal
        ult0 = 2008
        for i, t in enumerate(ts):
            prev = [a for a in ini if a <= t] or [ult0]
            en_riesgo = not any(t - k in ini for k in range(0, 5))
            B1 = float(np.log1p(t - prev[-1]))
            pL, pK = predecir(mod, B1, x[i])
            reg = pd.Timestamp(f"{t + 1}-07-15T09:00:00+00:00")
            filas.append({"pais": c, "t": int(t), "x": float(x[i]), "ultimo_inicio": prev[-1], "B1": B1,
                          "en_riesgo": en_riesgo, "p_L": float(pL), "p_K": float(pK), "sin_dato": False,
                          "inicio_previo_al_registro": False, "modelos_sha256": sha, "registrado": reg.isoformat()})
    return pd.DataFrame(filas), inicios, fechas, int(ts[-1] + 1)


def resumen(r: dict) -> str:
    if not r.get("cerradas"):
        return "sin ventanas cerradas"
    p = r["principal"]
    return (f"K1v: filas {p.get('filas')}, inicios nuevos {p.get('inicios')} (previos excluidos "
            f"{r['inicios_previos_excluidos']}), ΔAUC estrat {p.get('dauc_estrat', float('nan')):+.3f}, Δlog-loss "
            f"{p.get('dlogloss', float('nan')):+.4f}, p placebo {p.get('placebo', {}).get('p', float('nan')):.3f} → "
            f"{r['veredicto']}")


def _f(x):
    if isinstance(x, dict):
        return {str(k): _f(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_f(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 6)
    if isinstance(x, np.integer):
        return int(x)
    return x


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sintetico", action="store_true")
    ap.add_argument("--hoy")
    a = ap.parse_args(argv)
    if a.sintetico:
        ok = True
        for nom, s in (("con señal", 1.0), ("sin señal", 0.0)):
            reg, ini, fe, hasta = sintetico(señal=s)
            r = evaluar(reg, ini, hasta, fe)
            print(f"[sintético {nom}] {resumen(r)}")
            p = r["principal"]
            ok &= (p["dauc_estrat"] > 0 and p["placebo"]["p"] < ALFA) if s > 0 else \
                (p["placebo"]["p"] >= ALFA and r["veredicto"] != "CONFIRMADO")
        print("sintético:", "OK" if ok else "FALLA")
        return 0 if ok else 1
    from scripts.k1_vivo import INICIOS_DESDE_2021, INICIOS_REVISADOS_HASTA
    hoy = pd.Timestamp(a.hoy) if a.hoy else pd.Timestamp.today().normalize()
    reg = leer_registro()
    if cerrados(reg, INICIOS_REVISADOS_HASTA).empty:
        n = 0 if reg.empty else int(reg.t.nunique())
        print(f"K1v: sin ventanas cerradas a {hoy.date()} ({n} años t registrados; inicios revisados hasta "
              f"{INICIOS_REVISADOS_HASTA}); no se escribe nada")
        return 0
    from src.intl.procedencia import procedencia
    proc = procedencia(exigir_limpio=True)
    r = evaluar(reg, INICIOS_DESDE_2021, INICIOS_REVISADOS_HASTA)
    print(resumen(r))
    out = {"procedencia": proc, "hoy": str(hoy.date()), "inicios_revisados_hasta": INICIOS_REVISADOS_HASTA,
           "documentos": ["docs/int/K1_vivo_prerregistro_v1.md", "docs/int/K1_vivo_enmienda_1.md",
                          "docs/int/EVAL_registros_vivo.md"], "resultados": _f(r)}
    if r["principal"].get("inicios", 0) >= MIN_INICIOS:
        if VEREDICTO.exists():
            print(f"{VEREDICTO.name} ya existe: el veredicto es único (no se reescribe)")
        else:
            VEREDICTO.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"escrito {SALIDA.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
