"""Registro de predicciones (vivo, append-only), retrospectivo (backtest pseudo-tiempo-real) y puntuación.

Ficheros (versionados en git, como los demás registros en vivo):
- research/verif/vivo_v1.jsonl          predicciones EN VIVO; solo se añaden líneas, nunca se reescriben.
- research/verif/retrospectivo_v1.jsonl backtest 2015-hoy con vintages ALFRED — RETROSPECTIVO, NO EN VIVO.
- research/verif/resumen_v1.json        puntuación derivada (se rehace en cada corrida; lo lee el panel).
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.verif import metodo as M
from src.warehouse import db

DIR = Path(os.environ.get("FIN_VERIF_REGISTRO", str(db.REPO / "research" / "verif")))
RUTA_VIVO = DIR / "vivo_v1.jsonl"
RUTA_RETRO = DIR / "retrospectivo_v1.jsonl"
RUTA_RESUMEN = DIR / "resumen_v1.json"
ETIQ_RETRO = "retrospectivo (pseudo-tiempo-real con vintages ALFRED), no en vivo"
HORA_PUBLICACION_UTC = 12   # 8:30 ET = 12:30 UTC en verano (13:30 en invierno): se toma la más temprana
INICIO_RETRO = pd.Timestamp("2015-01-01")


def sha_metodo() -> str:
    return hashlib.sha256(Path(M.__file__).read_bytes()).hexdigest()


def leer(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _anadir(p: Path, reg: dict) -> None:
    """Añade una línea; se niega a duplicar un id ya emitido (nunca sobrescribe)."""
    if any(r["id"] == reg["id"] for r in leer(p)):
        raise ValueError(f"ya existe una predicción {reg['id']} en {p.name}; no se sobrescribe")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False, sort_keys=True) + "\n")


def _r(x, n=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def _registro(var: str, periodo: pd.Timestamp, pred: dict, emision, modo: str, emitida_utc: str | None) -> dict:
    meta = M.VARIABLES[var]
    per = periodo.strftime("%Y-%m") if meta["freq"] == "M" else f"{periodo.year}T{(periodo.month - 1) // 3 + 1}"
    return {"id": f"{var}:{periodo.date().isoformat()}", "modo": modo, "metodo": M.VERSION, "metodo_sha256": sha_metodo(),
            "variable": var, "nombre": meta["nombre"], "unidad": meta["unidad"], "serie": meta["serie"],
            "periodo": periodo.date().isoformat(), "periodo_txt": per,
            "fecha_emision": pd.Timestamp(emision).date().isoformat(), "emitida_utc": emitida_utc,
            "punto": _r(pred["punto"]), "inf80": _r(pred["inf80"]), "sup80": _r(pred["sup80"]), "sigma": _r(pred["sigma"]),
            "bench_ultimo": _r(pred["bench_ultimo"]), "bench_media12": _r(pred["bench_media12"]),
            "n_entreno": pred["n_entreno"], "corte_datos": pred["corte_datos"], "entradas": pred["entradas"]}


# ------------------------------------------------------------------------------------------------ en vivo
def siguiente_periodo(var: str, V, hoy) -> pd.Timestamp | None:
    serie = M.VARIABLES[var]["serie"]
    y = M.transformar(var, V.as_of(serie, pd.Timestamp(hoy) - pd.Timedelta(days=1))).dropna()
    if y.empty:
        return None
    off = pd.DateOffset(months=3) if M.VARIABLES[var]["freq"] == "Q" else pd.DateOffset(months=1)
    return y.index.max() + off


def emitir_vivo(V, hoy: date | None = None, ruta: Path | None = None, ahora_utc: datetime | None = None) -> list[dict]:
    """Emite (como mucho) una predicción por variable y periodo. Devuelve una lista de estados por variable."""
    hoy = pd.Timestamp(hoy or date.today())
    ruta = ruta or RUTA_VIVO
    ahora = (ahora_utc or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    ya = {r["id"] for r in leer(ruta)}
    estados = []
    for var in M.VARIABLES:
        p = siguiente_periodo(var, V, hoy)
        if p is None:
            estados.append({"variable": var, "estado": "sin datos"})
            continue
        rid = f"{var}:{p.date().isoformat()}"
        d = M.fecha_emision(var, p, V)
        base = {"variable": var, "periodo": p.date().isoformat(), "id": rid,
                "emision_prevista": d.date().isoformat() if d is not None else None}
        if rid in ya:
            estados.append({**base, "estado": "ya emitida"})
        elif d is None or hoy < d:
            estados.append({**base, "estado": "esperando a la regla de emisión"})
        else:
            pred = M.predecir(var, p, V, hoy)
            if pred is None:
                estados.append({**base, "estado": "faltan entradas"})
                continue
            reg = _registro(var, p, pred, hoy, "vivo", ahora)
            _anadir(ruta, reg)
            estados.append({**base, "estado": "EMITIDA", "punto": reg["punto"], "inf80": reg["inf80"], "sup80": reg["sup80"]})
    return estados


# ------------------------------------------------------------------------------------------------ retrospectivo
def backtest(V, desde: pd.Timestamp = INICIO_RETRO, hasta=None) -> list[dict]:
    """Aplica el método v1 a cada periodo publicado desde `desde`, con lo que se sabía el día de emisión de la regla."""
    hasta = pd.Timestamp(hasta or date.today())
    out = []
    for var, meta in M.VARIABLES.items():
        df = V.t[meta["serie"]]
        periodos = sorted(df.loc[df["value"].notna(), "date"].unique())
        for p in periodos:
            p = pd.Timestamp(p)
            r = V.publicacion(meta["serie"], p)
            if r is None or r < desde or r > hasta:
                continue
            d = M.fecha_emision(var, p, V)
            if d is None or d > r:   # emitir el mismo día de la publicación vale (la corrida diaria va antes de las 8:30 ET)
                continue
            pred = M.predecir(var, p, V, d)
            if pred is None:
                continue
            reg = _registro(var, p, pred, d, ETIQ_RETRO, None)
            out.append(reg)
    return out


def guardar_retro(regs: list[dict], ruta: Path | None = None) -> Path:
    ruta = ruta or RUTA_RETRO
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".part")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in regs), encoding="utf-8")
    tmp.replace(ruta)
    return ruta


# ------------------------------------------------------------------------------------------------ puntuación
def puntuar(regs: list[dict], V) -> list[dict]:
    out = []
    for r in regs:
        y, pub = M.dato_real(r["variable"], r["periodo"], V)
        s = dict(r)
        s["publicado"] = pub.date().isoformat() if pub is not None else None
        if y is None:
            s["estado"] = "pendiente"
            out.append(s)
            continue
        if r["modo"] == "vivo" and r.get("emitida_utc"):
            lim = pd.Timestamp(pub).tz_localize("UTC") + pd.Timedelta(hours=HORA_PUBLICACION_UTC)
            if pd.Timestamp(r["emitida_utc"]) >= lim:
                s["estado"] = "anulada (emitida después de publicarse)"
                out.append(s)
                continue
        s.update({"estado": "puntuada", "real": _r(y), "error": _r(y - r["punto"]),
                  "err_ultimo": _r(y - r["bench_ultimo"]), "err_media12": _r(y - r["bench_media12"]),
                  "dentro80": bool(r["inf80"] <= y <= r["sup80"])})
        out.append(s)
    return out


def _covid(var: str, per: str) -> bool:
    a, b = M.COVID_T if M.VARIABLES[var]["freq"] == "Q" else M.COVID_M
    return a <= pd.Timestamp(per) <= b


def tabla_resumen(punt: list[dict], sin_covid: bool = True) -> list[dict]:
    filas = []
    for var, meta in M.VARIABLES.items():
        xs = [p for p in punt if p["variable"] == var and p.get("estado") == "puntuada"
              and not (sin_covid and _covid(var, p["periodo"]))]
        if not xs:
            filas.append({"variable": var, "nombre": meta["nombre"], "n": 0})
            continue
        e = np.array([p["error"] for p in xs])
        eu = np.array([p["err_ultimo"] for p in xs])
        em = np.array([p["err_media12"] for p in xs])
        mae, maeu, maem = (float(np.mean(np.abs(a))) for a in (e, eu, em))
        filas.append({"variable": var, "nombre": meta["nombre"], "unidad": meta["unidad"], "n": len(xs),
                      "desde": min(p["periodo"] for p in xs), "hasta": max(p["periodo"] for p in xs),
                      "mae": _r(mae), "rmse": _r(float(np.sqrt(np.mean(e ** 2)))), "sesgo": _r(float(np.mean(e))),
                      "mae_ultimo": _r(maeu), "mae_media12": _r(maem),
                      "rel_ultimo": _r(mae / maeu if maeu else None, 3), "rel_media12": _r(mae / maem if maem else None, 3),
                      "gana_ultimo": _r(float(np.mean(np.abs(e) < np.abs(eu))), 3),
                      "cobertura80": _r(float(np.mean([p["dentro80"] for p in xs])), 3)})
    return filas


def escribir_resumen(V, estados: list[dict] | None = None, ruta: Path | None = None) -> dict:
    vivo = puntuar(leer(RUTA_VIVO), V)
    retro = puntuar(leer(RUTA_RETRO), V)
    res = {"generado": datetime.now().isoformat(timespec="seconds"), "metodo": M.VERSION, "metodo_sha256": sha_metodo(),
           "etiqueta_retro": ETIQ_RETRO, "estados_hoy": estados or [],
           "vivo": {"registros": vivo, "resumen": tabla_resumen(vivo, sin_covid=False)},
           "retro": {"registros": [{k: p.get(k) for k in ("variable", "periodo", "periodo_txt", "punto", "inf80", "sup80",
                                                         "real", "error", "err_ultimo", "dentro80", "estado")}
                                   for p in retro],
                     "resumen_sin_covid": tabla_resumen(retro, True), "resumen_todo": tabla_resumen(retro, False)}}
    ruta = ruta or RUTA_RESUMEN
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res
