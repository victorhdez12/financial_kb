"""INT-11: motor de escenarios probabilístico (ESQUELETO v0.1; diseño en docs/int/INT11_diseno.md).

Qué hace (de un vistazo):
  estado actual del país (régimen OPERABLE: inflación observada > 3 % × brecha unilateral < 0, el del Atlas §8)
  → transiciones de régimen (Markov por país con encogimiento jerárquico hacia el panel; contagio opcional vía un
    régimen "mundo" que se simula primero)
  → rentabilidades reales del año condicionadas a la transición (s_{t−1} → s_t): bootstrap por bloques estacionario
    de filas país-año del panel (credibilidad: el país propio pesa n_propio / (n_propio + k)), o modelo paramétrico t
  → trayectorias Monte Carlo a 1-H años con incertidumbre de PARÁMETROS (cada lote: matriz de transición sorteada de su
    posterior Dirichlet y pesos de bootstrap bayesiano por AÑO histórico) además de la de los shocks.

Disciplina:
  - Funciones puras: este módulo NO lee datos (un test lo comprueba). Quien lo use le pasa un DataFrame.
  - `preparar_filas` y `Generador.ajustar` se NIEGAN a recibir años > DEV_END (2004): nada ≥ 2005 en desarrollo.
  - Nada aquí evalúa el modelo con datos reales. Las funciones de puntuación (CRPS, PIT, cobertura, Diebold-Mariano con
    años como conglomerados) solo se prueban con datos sintéticos hasta que exista un prerregistro congelado.

Unidades: rentabilidades reales SIMPLES anuales en fracción (0,05 = 5 %); inflación = Δlog IPC (fracción);
crecimiento = Δlog PIB real per cápita.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import special, stats

from src.intl.data import DEV_END, FactorCutoffError

VERSION = "0.2"
REGIMENES = ("expansion", "sobrecalentamiento", "estanflacion", "crecimiento_bajo")
K = len(REGIMENES)
ACTIVOS = ("bolsa", "bonos", "letras", "vivienda", "oro")
MACRO = ("inflacion", "crecimiento")
UMBRAL_INFL = 0.03            # Atlas §8: inflación observada > 3 %
VENTANA_BRECHA = 10           # brecha = log PIB pc − media de los 10 años anteriores (P3 de INT-4)
GUERRAS = frozenset(range(1914, 1919)) | frozenset(range(1939, 1946))
REJILLA_KAPPA = np.logspace(0, 3.5, 71)          # v1 (κ salió en el borde, 10^3,5: validación 30-oct, hallazgo 5)
REJILLA_KAPPA_V2 = (0.0, 6.0, 121)                # v2: log10 κ ∈ [0, 6]; κ = 10^6 ≈ "todos los países = panel"
C_SUAVIZADO_V2 = 4.0                              # v2: inflado de varianza de la celda 1 + c/n (fijado en sintético iid t)
K_MEZCLA_V2 = 10.0                                # v2: peso del "incondicional" (mismo lado de inflación) k/(n + k)


# ============================================================================ régimen operable
def codigo_regimen(infl, brecha) -> np.ndarray:
    """0 expansión (brecha ≥ 0, infl ≤ 3 %), 1 sobrecalentamiento (≥ 0, > 3 %), 2 estanflación (< 0, > 3 %),
    3 crecimiento bajo (< 0, ≤ 3 %); −1 si falta algo."""
    infl, brecha = np.asarray(infl, float), np.asarray(brecha, float)
    ok = np.isfinite(infl) & np.isfinite(brecha)
    alta, baja = infl > UMBRAL_INFL, brecha < 0
    c = np.where(baja, np.where(alta, 2, 3), np.where(alta, 1, 0))
    return np.where(ok, c, -1).astype(int)


def estados_operables(df: pd.DataFrame, eje: str = "p3") -> pd.DataFrame:
    """df con columnas pais, año, inflacion, rgdpmad (una fila por país-año). Añade brecha y regimen del año t, con
    datos observados HASTA t (se conocen ≈ 30 de abril de t + 1).
    eje "p3" (principal, Atlas §8): brecha = log PIB pc − media de los 10 años anteriores; como el PIB crece, es < 0
      solo en caídas fuertes (≈ 6 % de los país-años) → "estanflación" y "crecimiento bajo" son estados RAROS.
    eje "tendencia" (alternativa, decisión del usuario D1): crecimiento del año − media del crecimiento de los 10 años
      anteriores (≈ 50 % por debajo)."""
    d = df.sort_values(["pais", "año"]).reset_index(drop=True).copy()
    lp = np.log(d["rgdpmad"].astype(float))
    if eje == "p3":
        previa = lp.groupby(d["pais"]).transform(
            lambda s: s.shift(1).rolling(VENTANA_BRECHA, min_periods=VENTANA_BRECHA).mean())
        d["brecha"] = lp - previa
    elif eje == "tendencia":
        g = lp.groupby(d["pais"]).diff()
        previa = g.groupby(d["pais"]).transform(
            lambda s: s.shift(1).rolling(VENTANA_BRECHA, min_periods=VENTANA_BRECHA).mean())
        d["brecha"] = g - previa
    else:
        raise ValueError(eje)
    d["regimen"] = codigo_regimen(d["inflacion"], d["brecha"])
    return d


def _mensual_completa(s: pd.Series, n: int, max_huecos: int = 1) -> pd.Series | None:
    """Últimos n meses consecutivos (índice de inicio de mes) que terminan en el último dato; se interpola en log hasta
    `max_huecos` meses que falten DENTRO de la ventana (p. ej. un IPC no publicado). Si faltan más, se retrocede."""
    s = s.dropna().astype(float)
    if s.empty:
        return None
    s.index = pd.DatetimeIndex(s.index).to_period("M").to_timestamp()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    for fin in s.index[::-1]:
        meses = pd.date_range(end=fin, periods=n, freq="MS")
        w = s.reindex(meses)
        if w.iloc[0] != w.iloc[0] or w.isna().sum() > max_huecos:       # primer mes ausente o demasiados huecos
            continue
        return np.exp(np.log(w).interpolate(limit_area="inside"))
    return None


def estado_movil(ipc_m: pd.Series, pib_q: pd.Series, poblacion_a: pd.Series | None = None) -> dict:
    """Estado operable con VENTANAS MÓVILES de 12 meses que terminan en el último dato publicado (puente JST anual ↔
    mensual; docs/int/INT11_v2_diseno.md §4). Con el último mes = diciembre y el último trimestre = T4 coincide EXACTAMENTE
    con el estado anual (`src/report/escenarios_vivo.estado_pais`, JST: media anual del IPC, PIB del año).
      inflación = log(media IPC de los 12 últimos meses / media de los 12 anteriores)
      brecha    = log PIB de los 4 últimos trimestres − media de log PIB de las 10 ventanas de 4 trimestres anteriores
                  (sin solape, cada una 4 trimestres antes); per cápita si se da la población anual (interpolada en log
                  al centro de cada ventana; extrapolada con el crecimiento de los 10 últimos años con dato).
    pib_q: índice = inicio del trimestre (o cualquier fecha dentro). Devuelve también el mes y trimestre usados."""
    ipc = _mensual_completa(ipc_m, 24)
    q = pib_q.dropna().astype(float)
    if ipc is None or q.empty:
        return {"regimen": None}
    q.index = pd.DatetimeIndex(q.index).to_period("Q").to_timestamp()
    q = q[~q.index.duplicated(keep="last")].sort_index()
    trimestres = pd.date_range(end=q.index[-1], periods=44, freq="QS")
    w = q.reindex(trimestres)
    if w.isna().any():
        return {"regimen": None, "motivo": "faltan trimestres de PIB en los 11 años previos"}
    infl = float(np.log(ipc.iloc[12:].mean() / ipc.iloc[:12].mean()))
    sumas, centros = [], []
    for k in range(11):                                   # k = 0: últimos 4 trimestres; k = 1..10: ventanas anteriores
        bloque = w.iloc[len(w) - 4 * (k + 1): len(w) - 4 * k]
        sumas.append(float(bloque.sum()))
        ini, fin = bloque.index[0], bloque.index[-1] + pd.offsets.QuarterEnd(0)
        centros.append(ini.year + (ini.dayofyear + (fin - ini).days / 2) / 365.25)
    lp = np.log(sumas)
    per_capita = poblacion_a is not None and len(poblacion_a.dropna()) >= 2
    if per_capita:
        pop = poblacion_a.dropna().astype(float)
        años_p = np.array([d.year if hasattr(d, "year") else int(d) for d in pop.index], float) + 0.5
        lpop = np.log(pop.to_numpy())
        o = np.argsort(años_p)
        años_p, lpop = años_p[o], lpop[o]
        ult = años_p >= años_p[-1] - 10
        crec = (lpop[-1] - lpop[ult][0]) / max(años_p[-1] - años_p[ult][0], 1)
        lp_c = np.array([np.interp(c, años_p, lpop) if c <= años_p[-1] else lpop[-1] + crec * (c - años_p[-1])
                         for c in centros])
        lp = lp - lp_c
    brecha = float(lp[0] - lp[1:].mean())
    r = int(codigo_regimen([infl], [brecha])[0])
    originales = set(pd.DatetimeIndex(ipc_m.dropna().index).to_period("M").to_timestamp())
    huecos = int(sum(m not in originales for m in ipc.index))
    mes = ipc.index[-1]
    return {"mes_ipc": str(mes.date()), "trimestre_pib": str(w.index[-1].date()), "inflacion": infl,
            "brecha": brecha, "per_capita": bool(per_capita), "huecos_ipc_interpolados": huecos, "regimen": REGIMENES[r], "codigo": r}


def ventana_objetivo(corte) -> dict:
    """Horizonte MÓVIL de 12 meses: el abanico describe los 12 meses que siguen al corte de información (fin de mes).
    Rótulo obligatorio de la salida "hoy" v2 (no "el próximo año natural")."""
    c = pd.Timestamp(corte) + pd.offsets.MonthEnd(0)
    ini = (c + pd.offsets.MonthBegin(1)).normalize()
    fin = ini + pd.DateOffset(months=12) - pd.Timedelta(days=1)
    return {"desde": str(ini.date()), "hasta": str(fin.date()), "meses": 12}


def _comprobar_corte(años, anio_max: int) -> None:
    if len(años) and int(np.max(años)) > anio_max:
        raise FactorCutoffError(f"INT-11: años hasta {int(np.max(años))} > {anio_max} (periodo bloqueado)")
    if anio_max > DEV_END.year:
        raise FactorCutoffError(f"INT-11: anio_max {anio_max} > DEV_END ({DEV_END.year}); requiere puerta de gasto")


def preparar_filas(df: pd.DataFrame, activos=ACTIVOS, covariables=(), excluir=None,
                   anio_max: int = DEV_END.year, eje: str = "p3") -> pd.DataFrame:
    """Filas país-año del pool. df: pais, año, inflacion, rgdpmad, los `activos` (rentabilidad real simple del año) y
    opcionalmente `crecimiento` y covariables (valor del año; se usan RETARDADAS: z_<col> = valor de t − 1).
    Salida: pais, año, s_prev (régimen de t − 1), s (régimen de t), w_prev / w (régimen mundo), activos, MACRO,
    z_*, sucesor (índice de la fila del mismo país en t + 1 o −1). `excluir`: conjunto de (pais, año) o de años."""
    _comprobar_corte(df["año"].to_numpy(), anio_max)
    d = estados_operables(df, eje)
    if "crecimiento" not in d:
        d["crecimiento"] = np.log(d["rgdpmad"].astype(float)).groupby(d["pais"]).diff()
    g = d.groupby("pais")
    consecutivo = g["año"].diff() == 1
    d["s_prev"] = g["regimen"].shift(1).where(consecutivo).fillna(-1).astype(int)
    for c in covariables:
        d[f"z_{c}"] = g[c].shift(1).where(consecutivo)
    # régimen mundo del año: mayoría de países con inflación > 3 % y mayoría con brecha < 0 (≥ 5 países con dato)
    ok = d["regimen"] >= 0
    agg = d[ok].assign(alta=d["inflacion"] > UMBRAL_INFL, baja=d["brecha"] < 0).groupby("año").agg(
        alta=("alta", "mean"), baja=("baja", "mean"), n=("alta", "size"))
    agg = agg[agg["n"] >= 5]
    mundo = pd.Series(codigo_regimen(np.where(agg["alta"] > 0.5, 1.0, 0.0), np.where(agg["baja"] > 0.5, -1.0, 1.0)),
                      index=agg.index)
    d["w"] = d["año"].map(mundo).fillna(-1).astype(int)
    d["w_prev"] = (d["año"] - 1).map(mundo).fillna(-1).astype(int)
    if excluir:
        ex = set(excluir)
        quita = d.apply(lambda r: (r["pais"], int(r["año"])) in ex or int(r["año"]) in ex, axis=1)
        d = d[~quita]
    d = d[(d["s_prev"] >= 0) & (d["regimen"] >= 0)].rename(columns={"regimen": "s"})
    cols = ["pais", "año", "s_prev", "s", "w_prev", "w", *activos, *MACRO, *[f"z_{c}" for c in covariables]]
    for a in activos:
        if a not in d:
            d[a] = np.nan
    d = d[cols].sort_values(["pais", "año"]).reset_index(drop=True)
    sig = d.groupby("pais")["año"].shift(-1)
    d["sucesor"] = np.where(sig == d["año"] + 1, d.index + 1, -1)
    return d


def recalcular_sucesor(filas: pd.DataFrame) -> pd.DataFrame:
    """Ordena por (pais, año), reinicia el índice y recalcula `sucesor` (fila del mismo país en t + 1, o −1)."""
    d = filas.sort_values(["pais", "año"]).reset_index(drop=True)
    sig = d.groupby("pais")["año"].shift(-1)
    d["sucesor"] = np.where(sig == d["año"] + 1, d.index + 1, -1)
    return d


# ============================================================================ Markov jerárquico
def dm_loglik(n: np.ndarray, alpha: np.ndarray) -> float:
    """Log-verosimilitud Dirichlet-multinomial (sin el coeficiente multinomial, constante en α); última dimensión =
    categorías. n y alpha se emparejan por difusión."""
    n, alpha = np.broadcast_arrays(np.asarray(n, float), np.asarray(alpha, float))
    a0, n0 = alpha.sum(-1), n.sum(-1)
    return float((special.gammaln(a0) - special.gammaln(a0 + n0)).sum()
                 + (special.gammaln(alpha + n) - special.gammaln(alpha)).sum())


def kappa_eb(n: np.ndarray, p: np.ndarray, rejilla=REJILLA_KAPPA) -> float:
    """Fuerza del encogimiento hacia p por Bayes empírico (máxima verosimilitud marginal en una rejilla)."""
    p = np.clip(p, 1e-6, None)
    p = p / p.sum(-1, keepdims=True)
    ll = [dm_loglik(n, k * p) for k in rejilla]
    return float(rejilla[int(np.argmax(ll))])


def recuentos(filas: pd.DataFrame, paises: list[str], contagio: bool) -> np.ndarray:
    """(C, K, K) transiciones s_prev → s por país, o (C, K, K, K) por (s_prev, w, s) con contagio."""
    forma = (len(paises), K, K, K) if contagio else (len(paises), K, K)
    n = np.zeros(forma)
    idx = {c: i for i, c in enumerate(paises)}
    f = filas[filas["pais"].isin(idx)]
    if contagio:
        f = f[f["w"] >= 0]
        np.add.at(n, (f["pais"].map(idx).to_numpy(), f["s_prev"].to_numpy(), f["w"].to_numpy(), f["s"].to_numpy()), 1)
    else:
        np.add.at(n, (f["pais"].map(idx).to_numpy(), f["s_prev"].to_numpy(), f["s"].to_numpy()), 1)
    return n


def recuentos_mundo(filas: pd.DataFrame) -> np.ndarray:
    m = filas[["año", "w"]].drop_duplicates().set_index("año")["w"].sort_index()
    n = np.zeros((K, K))
    for a, w in m.items():
        if a - 1 in m.index and m[a - 1] >= 0 and w >= 0:
            n[m[a - 1], w] += 1
    return n


# ============================================================================ configuración y salida
@dataclass
class Config:
    activos: tuple = ACTIVOS
    modo: str = "bootstrap"            # "bootstrap" (por bloques, por régimen) | "t" (paramétrico t multivariante)
    k_pais: float = 40.0               # credibilidad: peso del país propio = n_propio / (n_propio + k_pais)
    bloque_medio: float = 3.0          # años; continuar el bloque con prob. 1 − 1/bloque_medio si el régimen casa
    n_min_celda: int = 25              # celda (s_prev, s) con menos filas → se usa (·, s); y si no, todo
    contagio: bool = False             # transición del país condicionada al régimen mundo del año siguiente
    incertidumbre: bool = True         # sortear parámetros por lote (posterior Dirichlet + bootstrap bayesiano por año)
    nu_t: float = 5.0                  # grados de libertad del modo "t"
    n0_cov: float = 30.0               # modo "t": encogimiento de la covarianza de la celda hacia la del pool
    anio_max: int = DEV_END.year
    # ---- v2 (docs/int/INT11_v2_diseno.md). Los valores por defecto reproducen v1 BIT A BIT; Config.v2() los activa.
    escala_pais: bool = False          # dispersión propia de cada país (frente al año), encogida hacia el panel (EB)
    min_paises_año: int = 3            # media del año (choque común) solo con ≥ 3 países con dato
    k_mezcla: float = 0.0              # con prob. k/(n_celda + k) la fila sale del "incondicional" del mismo lado de
    #                                    la inflación simulada (respeta la coherencia de la inflación); 0 = v1
    c_suavizado: float = 0.0           # bootstrap suavizado: ruido t de varianza (c/n_celda)·var_celda → la varianza
    #                                    predictiva de la celda pasa a ser (1 + c/n)·var: ensancha donde hay pocas filas
    nu_suavizado: float = 5.0          # grados de libertad del ruido de suavizado (colas)
    rejilla_kappa: tuple = (0.0, 3.5, 71)   # log10 κ mín, máx, puntos (v1: borde en 10^3,5)

    @classmethod
    def v2(cls, **cambios) -> "Config":
        """Configuración v2 propuesta (borrador de prerregistro docs/int/INT11_prerregistro_v2_v0.md)."""
        base = dict(escala_pais=True, k_mezcla=K_MEZCLA_V2, c_suavizado=C_SUAVIZADO_V2, rejilla_kappa=REJILLA_KAPPA_V2)
        base.update(cambios)
        return cls(**base)

    @property
    def es_v2(self) -> bool:
        return bool(self.escala_pais or self.k_mezcla > 0 or self.c_suavizado > 0)


@dataclass
class Escenarios:
    """Salida del generador (formato documentado en docs/int/INT11_diseno.md §6).
    rent (P, H, A) rentabilidad real simple de cada año; inflacion, crecimiento (P, H); regimen (P, H) régimen del país
    al FINAL de cada año (0-3); mundo (P, H) o None; lote (P,) sorteo de parámetros de cada trayectoria."""
    rent: np.ndarray
    inflacion: np.ndarray
    crecimiento: np.ndarray
    regimen: np.ndarray
    mundo: np.ndarray | None
    lote: np.ndarray
    activos: tuple
    meta: dict = field(default_factory=dict)

    @property
    def horizonte(self) -> int:
        return self.rent.shape[1]

    def acumulada(self) -> np.ndarray:
        """(P, H, A) rentabilidad real acumulada desde hoy hasta el final del año h."""
        return np.cumprod(1 + self.rent, axis=1) - 1

    def anualizada(self) -> np.ndarray:
        h = np.arange(1, self.horizonte + 1)[None, :, None]
        return (1 + self.acumulada()) ** (1 / h) - 1

    def abanico(self, percentiles=(5, 10, 25, 50, 75, 90, 95), medida: str = "acumulada") -> pd.DataFrame:
        x = {"acumulada": self.acumulada, "anualizada": self.anualizada, "anual": lambda: self.rent}[medida]()
        q = np.nanpercentile(x, percentiles, axis=0)                         # (len(p), H, A)
        filas = [{"activo": a, "h": h + 1, **{f"p{p}": q[i, h, j] for i, p in enumerate(percentiles)}}
                 for j, a in enumerate(self.activos) for h in range(self.horizonte)]
        return pd.DataFrame(filas)

    def prob(self, evento: np.ndarray) -> dict:
        """evento: booleano (P,). Probabilidad (media de todas las trayectorias = predictiva posterior) y un IC 90 %
        aproximado de la parte de PARÁMETROS: varianza entre lotes menos el ruido Monte Carlo binomial."""
        return _media_e_ic(evento.astype(float), self.lote)

    def prob_caida(self, activo: str, umbral: float = -0.20, h: int = 1, desde_maximo: bool = False) -> dict:
        """P(rentabilidad real acumulada a h años ≤ umbral); con desde_maximo, caída desde el máximo de la trayectoria
        (fin de año) en algún momento hasta h."""
        j = self.activos.index(activo)
        nivel = np.cumprod(1 + self.rent[:, :h, j], axis=1)
        if desde_maximo:
            pico = np.maximum.accumulate(np.concatenate([np.ones((len(nivel), 1)), nivel], axis=1), axis=1)[:, 1:]
            ev = (nivel / pico - 1 <= umbral).any(axis=1)
        else:
            ev = nivel[:, -1] - 1 <= umbral
        return self.prob(ev)

    def prob_inflacion(self, umbral: float = 0.05, h: int = 1, algun_año: bool = True) -> dict:
        x = np.expm1(self.inflacion[:, :h])
        return self.prob((x > umbral).any(axis=1) if algun_año else x[:, -1] > umbral)

    def prob_regimen(self, h: int = 1) -> pd.DataFrame:
        return pd.DataFrame([{"regimen": r, **self.prob(self.regimen[:, h - 1] == i)} for i, r in enumerate(REGIMENES)])

    def a_tabla(self) -> pd.DataFrame:
        """Formato largo para otro modelo: una fila por (trayectoria, h)."""
        P, H = self.regimen.shape
        d = {"trayectoria": np.repeat(np.arange(P), H), "lote": np.repeat(self.lote, H),
             "h": np.tile(np.arange(1, H + 1), P), "regimen": self.regimen.ravel(),
             "inflacion": self.inflacion.ravel(), "crecimiento": self.crecimiento.ravel()}
        if self.mundo is not None:
            d["regimen_mundo"] = self.mundo.ravel()
        for j, a in enumerate(self.activos):
            d[a] = self.rent[:, :, j].ravel()
        return pd.DataFrame(d)

    def guardar(self, ruta: str | Path) -> None:
        ruta = Path(ruta)
        self.a_tabla().to_parquet(ruta.with_suffix(".parquet"), index=False)
        ruta.with_suffix(".json").write_text(json.dumps(self.meta, ensure_ascii=False, indent=1, default=str))


def _media_e_ic(x: np.ndarray, lote: np.ndarray, z: float = 1.645) -> dict:
    """x (P,) valores por trayectoria. IC 90 % de la incertidumbre de PARÁMETROS: var(medias de lote) − var MC."""
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    x, lote = x[ok], lote[ok]
    m = float(x.mean()) if len(x) else np.nan
    ids, inv, n_b = np.unique(lote, return_inverse=True, return_counts=True)
    if len(ids) < 3:
        return {"p": m, "ic90": (np.nan, np.nan)}
    medias = np.bincount(inv, weights=x) / n_b
    var_dentro = np.bincount(inv, weights=(x - medias[inv]) ** 2) / np.maximum(n_b - 1, 1)
    var_par = max(float(np.var(medias, ddof=1) - np.mean(var_dentro / n_b)), 0.0)
    s = np.sqrt(var_par)
    return {"p": m, "ic90": (m - z * s, m + z * s)}


# ============================================================================ generador
class Generador:
    """Uso:
        g = Generador(Config()).ajustar(filas)              # filas de preparar_filas (≤ 2004)
        esc = g.simular("ESP", estado="estanflacion", horizonte=5, n_lotes=200, por_lote=100, semilla=1)
        esc.abanico(); esc.prob_caida("bolsa", -0.2, h=1); g.tabla_regimenes("ESP")
    """

    def __init__(self, config: Config | None = None):
        self.cfg = config or Config()

    # ------------------------------------------------------------ estimación
    def ajustar(self, filas: pd.DataFrame) -> "Generador":
        cfg = self.cfg
        _comprobar_corte(filas["año"].to_numpy(), cfg.anio_max)
        # el sucesor se RECALCULA aquí: un subconjunto de filas (dejar un país fuera, corte temporal) cambia los índices
        self.filas = recalcular_sucesor(filas)
        self.vars = list(cfg.activos) + list(MACRO)
        self.V = self.filas[self.vars].to_numpy(float)
        self.s_prev = self.filas["s_prev"].to_numpy(int)
        self.s = self.filas["s"].to_numpy(int)
        self.anio = self.filas["año"].to_numpy(int)
        self.pais = self.filas["pais"].to_numpy()
        self.suc = self.filas["sucesor"].to_numpy(int)
        self.paises = sorted(self.filas["pais"].unique())
        self.años_u, self.año_idx = np.unique(self.anio, return_inverse=True)
        # Markov: panel → país (Bayes empírico)
        n0 = recuentos(self.filas, self.paises, False)
        self.p_panel = (n0.sum(0) + 1) / (n0.sum(0) + 1).sum(-1, keepdims=True)
        rej = np.logspace(*cfg.rejilla_kappa[:2], int(cfg.rejilla_kappa[2]))
        self.kappa = kappa_eb(n0, self.p_panel[None], rej)
        self.kappa_en_borde = bool(self.kappa >= rej[-1] * (1 - 1e-9) or self.kappa <= rej[0] * (1 + 1e-9))
        self.n_pais = n0
        if cfg.contagio:
            n1 = recuentos(self.filas, self.paises, True)
            npw = n1.sum(0)                                                  # (K, K_w, K)
            self.kappa0 = kappa_eb(npw.transpose(1, 0, 2), self.p_panel[None])
            self.p_panel_w = (npw + self.kappa0 * self.p_panel[:, None, :])
            self.p_panel_w /= self.p_panel_w.sum(-1, keepdims=True)
            self.kappa_w = kappa_eb(n1, self.p_panel_w[None])
            self.n_pais_w = n1
            self.n_mundo = recuentos_mundo(self.filas)
        # celdas (s_prev, s) con respaldo jerárquico: (i, j) → (i, mismo lado de inflación que j) → (i, ·) → (·, j) →
        # todo. Se conserva antes el régimen CONOCIDO (s_prev), que es el que condiciona de verdad la rentabilidad, y
        # después la coherencia de la inflación sorteada con el régimen simulado.
        self.celdas, self.nivel_celda = {}, {}
        alta = np.isin(self.s, (1, 2))
        for i in range(K):
            for j in range(K):
                cands = [(self.s_prev == i) & (self.s == j), (self.s_prev == i) & (alta == (j in (1, 2))),
                         self.s_prev == i, self.s == j, np.ones(len(self.s), bool)]
                for nivel, m in enumerate(cands):
                    idx = np.flatnonzero(m)
                    if len(idx) >= cfg.n_min_celda:
                        break
                self.celdas[(i, j)], self.nivel_celda[(i, j)] = idx, nivel
        # donantes para huecos: misma celda con dato; si no hay ≥ 5, filas con el mismo s; si no, cualquiera con dato
        self.donantes = {}
        for c, idx in self.celdas.items():
            for v in range(len(self.vars)):
                fin = np.isfinite(self.V[:, v])
                d = idx[fin[idx]]
                if len(d) < 5:
                    d = np.flatnonzero(fin & (self.s_prev == c[0]))
                if len(d) < 5:
                    d = np.flatnonzero(fin)
                self.donantes[(c, v)] = d
        if cfg.es_v2:
            self._ajustar_v2(alta)
        return self

    # ------------------------------------------------------------ v2: escala por país, mezcla, suavizado
    def _ajustar_v2(self, alta: np.ndarray) -> None:
        """Piezas de v2 (docs/int/INT11_v2_diseno.md §2). Todo en log(1 + r) para los activos.
        (a) ESCALA POR PAÍS (Bayes jerárquico): dev = y − media del año (choque común); f_c = dt(dev del país)/dt(dev
            del panel) por activo; log f̂_c ~ N(log f_c, se²) con se² = (curtosis + 2)/(4 n_c); log f_c ~ N(m, τ²) entre
            países (τ² por momentos). Posterior por país; país fuera del pool → predictiva N(m, τ²). La fila (c', t)
            se reescala para el país objetivo c: y* = media_t + g_c · dev / f̂_c' con g_c sorteado POR LOTE.
        (b) MEZCLA: padre de la celda (·, j) = filas con s del mismo lado de la inflación que j.
        (c) SUAVIZADO: dt (log) de cada celda y de cada padre y n con dato, por activo."""
        cfg = self.cfg
        A = len(cfg.activos)
        self.L = np.log1p(self.V[:, :A])
        self.padres = {lado: np.flatnonzero(alta == bool(lado)) for lado in (0, 1)}
        self.devn = np.full_like(self.L, np.nan)
        self.ybar = np.full_like(self.L, np.nan)
        self.escala_post = {}                                         # país → (media, var) de log f por activo
        self.escala_pred = (np.zeros(A), np.zeros(A))                 # (m, τ²) para un país fuera del pool
        if cfg.escala_pais:
            ok = np.isfinite(self.L)
            cnt = np.zeros((len(self.años_u), A))
            sm = np.zeros((len(self.años_u), A))
            np.add.at(cnt, self.año_idx, ok)
            np.add.at(sm, self.año_idx, np.where(ok, self.L, 0.0))
            media = np.where(cnt >= cfg.min_paises_año, sm / np.maximum(cnt, 1), np.nan)
            self.ybar = media[self.año_idx]
            dev = self.L - self.ybar
            # corrección de grados de libertad: la media del año incluye la propia fila
            dev = dev * np.sqrt(np.where(cnt[self.año_idx] > 1, cnt[self.año_idx] / np.maximum(cnt[self.año_idx] - 1, 1),
                                         np.nan))
            rms = np.sqrt(np.nanmean(dev ** 2, 0))
            z = dev / rms
            kurt = np.array([np.nanmean(z[:, a] ** 4) / np.nanmean(z[:, a] ** 2) ** 2 - 3 if np.isfinite(z[:, a]).any()
                             else 0.0 for a in range(A)])
            lf, se2, nc = [], [], []
            for c in self.paises:
                mc = self.pais == c
                n_c = np.isfinite(dev[mc]).sum(0)
                sd_c = np.sqrt(np.nanmean(dev[mc] ** 2, 0)) / rms if mc.any() else np.full(A, np.nan)
                lf.append(np.where(n_c >= 5, np.log(np.maximum(sd_c, 1e-6)), np.nan))
                se2.append((np.maximum(kurt, 0) + 2) / (4 * np.maximum(n_c, 1)))
                nc.append(n_c)
            lf, se2 = np.array(lf), np.array(se2)                       # (C, A)
            m = np.nanmean(lf, 0)
            tau2 = np.maximum(np.nanvar(lf, 0, ddof=1) - np.nanmean(np.where(np.isfinite(lf), se2, np.nan), 0), 0.0)
            m, tau2 = np.nan_to_num(m), np.nan_to_num(tau2)
            B = np.where(np.isfinite(lf), tau2 / np.maximum(tau2 + se2, 1e-12), 0.0)
            post_m = m + B * (np.nan_to_num(lf) - m)
            post_v = np.where(np.isfinite(lf), B * se2, tau2)
            for k, c in enumerate(self.paises):
                self.escala_post[c] = (post_m[k], post_v[k])
            self.escala_pred = (m, tau2)
            fila_m = post_m[np.searchsorted(self.paises, self.pais)]
            self.devn = dev / np.exp(fila_m)
            self.escala_resumen = {"m": m.round(4).tolist(), "tau": np.sqrt(tau2).round(4).tolist(),
                                   "curtosis": kurt.round(2).tolist(),
                                   "factor_pais": {c: np.exp(self.escala_post[c][0]).round(3).tolist()
                                                   for c in self.paises}}
        # dispersión y n con dato por celda y por padre (suavizado)
        def _sd_n(idx):
            x = self.L[idx]
            n = np.isfinite(x).sum(0)
            with np.errstate(all="ignore"):
                sd = np.array([np.nanstd(x[:, a], ddof=1) if n[a] >= 2 else 0.0 for a in range(A)])
            return np.nan_to_num(sd), n
        self.sd_celda = {c: _sd_n(idx) for c, idx in self.celdas.items()}
        self.sd_padre = {lado: _sd_n(idx) for lado, idx in self.padres.items()}

    def _factor_lote(self, pais: str, rng) -> np.ndarray:
        """g_c (A,) del lote: sorteo del posterior (país en el pool) o de la predictiva (país nuevo / dejado fuera)."""
        A = len(self.cfg.activos)
        if not self.cfg.escala_pais:
            return np.ones(A)
        m, v = self.escala_post.get(pais, self.escala_pred)
        if not self.cfg.incertidumbre:
            return np.exp(m)
        return np.exp(m + np.sqrt(v) * rng.standard_normal(A))

    def posterior_transicion(self, pais: str) -> np.ndarray:
        """α del posterior Dirichlet de la fila de transición del país: (K, K) o (K, K_w, K) con contagio."""
        if self.cfg.contagio:
            n = self.n_pais_w[self.paises.index(pais)] if pais in self.paises else 0
            return n + self.kappa_w * self.p_panel_w
        n = self.n_pais[self.paises.index(pais)] if pais in self.paises else 0
        return n + self.kappa * self.p_panel

    def _pesos_base(self, pais: str) -> dict:
        """Pesos de credibilidad por celda: con prob. a = n_propio / (n_propio + k_pais) una fila del país propio, si no
        una fila cualquiera del panel (el país propio incluido). País fuera del pool (dejar un país fuera) → panel puro."""
        propio = self.pais == pais
        out = {}
        for c, idx in self.celdas.items():
            n_p = int(propio[idx].sum())
            a = n_p / (n_p + self.cfg.k_pais) if n_p else 0.0
            out[c] = (1 - a) / len(idx) + np.where(propio[idx], a / max(n_p, 1), 0.0)
        if self.cfg.k_mezcla > 0:
            for lado, idx in self.padres.items():
                n_p = int(propio[idx].sum())
                a = n_p / (n_p + self.cfg.k_pais) if n_p else 0.0
                out[("padre", lado)] = (1 - a) / max(len(idx), 1) + np.where(propio[idx], a / max(n_p, 1), 0.0)
        return out

    def _nucleo(self, inclinacion: dict | None) -> np.ndarray:
        """Inclinación (M2): pesos de núcleo gaussiano según covariables conocidas al empezar el año.
        inclinacion = {columna: (valor_actual, ancho_en_dt)}; NaN → mediana de los pesos."""
        if not inclinacion:
            return np.ones(len(self.filas))
        lw = np.zeros(len(self.filas))
        for col, (v, ancho) in inclinacion.items():
            z = self.filas[f"z_{col}"].to_numpy(float)
            sd = np.nanstd(z)
            lw += -0.5 * ((z - v) / (ancho * sd)) ** 2
        w = np.exp(lw - np.nanmax(lw))
        return np.where(np.isfinite(w), w, np.nanmedian(w))

    # ------------------------------------------------------------ simulación
    def simular(self, pais: str, estado, horizonte: int = 5, n_lotes: int = 200, por_lote: int = 100,
                semilla: int = 0, mundo=None, inclinacion: dict | None = None) -> Escenarios:
        cfg = self.cfg
        s0 = REGIMENES.index(estado) if isinstance(estado, str) else int(estado)
        w0 = s0 if mundo is None else (REGIMENES.index(mundo) if isinstance(mundo, str) else int(mundo))
        rng = np.random.default_rng(semilla)
        alpha = self.posterior_transicion(pais)
        base = self._pesos_base(pais)
        nuc = self._nucleo(inclinacion)
        P, H, nv = n_lotes * por_lote, horizonte, len(self.vars)
        X = np.full((P, H, nv), np.nan)
        S = np.zeros((P, H), int)
        W = np.zeros((P, H), int) if cfg.contagio else None
        for b in range(n_lotes):
            sl = slice(b * por_lote, (b + 1) * por_lote)
            if cfg.incertidumbre:
                T = _dirichlet_filas(alpha, rng)
                gy = rng.dirichlet(np.ones(len(self.años_u))) * len(self.años_u)
                Tw = _dirichlet_filas(self.n_mundo + 1, rng) if cfg.contagio else None
            else:
                T = alpha / alpha.sum(-1, keepdims=True)
                gy = np.ones(len(self.años_u))
                Tw = (self.n_mundo + 1) / (self.n_mundo + 1).sum(-1, keepdims=True) if cfg.contagio else None
            g = self._factor_lote(pais, rng) if cfg.es_v2 else None
            Xb, Sb, Wb = self._lote(T, Tw, base, gy[self.año_idx], nuc, s0, w0, por_lote, H, rng, g)
            X[sl], S[sl] = Xb, Sb
            if cfg.contagio:
                W[sl] = Wb
        A = len(cfg.activos)
        meta = {"version": VERSION, "pais": pais, "estado_inicial": REGIMENES[s0],
                "mundo_inicial": REGIMENES[w0] if cfg.contagio else None, "horizonte": H, "n_lotes": n_lotes,
                "por_lote": por_lote, "semilla": semilla, "config": asdict(self.cfg), "inclinacion": inclinacion,
                "kappa": self.kappa, "kappa_en_borde": self.kappa_en_borde, "años_pool": [int(self.años_u.min()), int(self.años_u.max())],
                "filas_pool": int(len(self.filas)), "unidades": "rentabilidad real simple anual (fracción)"}
        return Escenarios(rent=X[:, :, :A], inflacion=X[:, :, A], crecimiento=X[:, :, A + 1], regimen=S, mundo=W,
                          lote=np.repeat(np.arange(n_lotes), por_lote), activos=tuple(cfg.activos), meta=meta)

    def _transicion(self, T, Tw, s, w, rng, ratio=None):
        if self.cfg.contagio:
            w_new = _categorica(Tw[w], rng)
            pr = T[s, w_new]
        else:
            w_new = None
            pr = T[s]
        if ratio is not None:
            pr = pr * ratio[s]
            pr = pr / pr.sum(-1, keepdims=True)
        return _categorica(pr, rng), w_new

    def _ratio_inclinacion(self, nuc: np.ndarray) -> np.ndarray | None:
        """Inclinación de la PRIMERA transición: P(j|i) × (núcleo medio en la celda (i, j) / núcleo medio en la fila i)."""
        if np.allclose(nuc, nuc[0]):
            return None
        r = np.ones((K, K))
        for i in range(K):
            fi = self.s_prev == i
            if not fi.any():
                continue
            mi = nuc[fi].mean()
            for j in range(K):
                c = fi & (self.s == j)
                if c.sum() >= 5:
                    r[i, j] = nuc[c].mean() / mi
        return r

    def _lote(self, T, Tw, base, peso_año, nuc, s0, w0, n, H, rng, g=None):
        cfg = self.cfg
        X = np.full((n, H, len(self.vars)), np.nan)
        S = np.zeros((n, H), int)
        W = np.zeros((n, H), int)
        s = np.full(n, s0)
        w = np.full(n, w0)
        r_prev = np.full(n, -1)
        ratio = self._ratio_inclinacion(nuc)
        pcont = 1 - 1 / cfg.bloque_medio
        if cfg.modo == "t":
            mom = self._momentos(base, peso_año)
        for h in range(H):
            s_new, w_new = self._transicion(T, Tw, s, w, rng, ratio if h == 0 else None)
            if cfg.modo == "bootstrap":
                r = np.full(n, -1)
                sig = np.where(r_prev >= 0, self.suc[np.maximum(r_prev, 0)], -1)
                cont = (sig >= 0) & (rng.random(n) < pcont) & (h > 0)
                cont[cont] &= (self.s[sig[cont]] == s_new[cont]) & (self.s_prev[sig[cont]] == s[cont])
                r[cont] = sig[cont]
                for (i, j), idx in self.celdas.items():
                    m = (~cont) & (s == i) & (s_new == j)
                    if m.any():
                        if cfg.k_mezcla > 0:                                # v2: mezcla con el incondicional
                            lado = int(j in (1, 2))
                            mez = rng.random(m.sum()) < cfg.k_mezcla / (len(idx) + cfg.k_mezcla)
                            mm = np.flatnonzero(m)
                            r[mm[~mez]] = self._sortear(idx, base[(i, j)], peso_año, nuc, h, (~mez).sum(), rng)
                            pidx = self.padres[lado]
                            r[mm[mez]] = self._sortear(pidx, base[("padre", lado)], peso_año, nuc, h, mez.sum(), rng)
                        else:
                            cw = np.cumsum(base[(i, j)] * peso_año[idx] * (nuc[idx] if h == 0 else 1.0))
                            r[m] = idx[np.searchsorted(cw, rng.random(m.sum()) * cw[-1], side="right").clip(0, len(idx) - 1)]
                if cfg.es_v2:
                    X[:, h] = self._valores_v2(r, s, s_new, g, rng)
                else:
                    X[:, h] = self.V[r]
                    self._imputar(X[:, h], s, s_new, rng)
                r_prev = r
            else:
                for (i, j) in self.celdas:
                    m = (s == i) & (s_new == j)
                    if m.any():
                        X[m, h] = self._t(mom[(i, j)], int(m.sum()), rng)
            S[:, h] = s_new
            if w_new is not None:
                W[:, h] = w_new
            s, w = s_new, (w_new if w_new is not None else w)
        return X, S, (W if cfg.contagio else None)

    def _sortear(self, idx, b, peso_año, nuc, h, m, rng):
        if m == 0:
            return np.zeros(0, int)
        cw = np.cumsum(b * peso_año[idx] * (nuc[idx] if h == 0 else 1.0))
        return idx[np.searchsorted(cw, rng.random(m) * cw[-1], side="right").clip(0, len(idx) - 1)]

    def _valores_v2(self, r, s, s_new, g, rng) -> np.ndarray:
        """Valores del año para las filas r (v2): huecos → donante (por variable), reescala por país y suavizado."""
        cfg = self.cfg
        A = len(cfg.activos)
        RI = np.repeat(r[:, None], len(self.vars), 1)
        for v in range(len(self.vars)):
            falta = ~np.isfinite(self.V[r, v])
            if not falta.any():
                continue
            for (i, j) in self.celdas:
                m = falta & (s == i) & (s_new == j)
                if m.any():
                    d = self.donantes[((i, j), v)]
                    if len(d):
                        RI[m, v] = rng.choice(d, m.sum())
        X = self.V[RI, np.arange(len(self.vars))[None, :]]
        cols = np.arange(A)[None, :]
        L = self.L[RI[:, :A], cols]
        if cfg.escala_pais:
            dn = self.devn[RI[:, :A], cols]
            yb = self.ybar[RI[:, :A], cols]
            esc = np.isfinite(dn) & np.isfinite(yb)
            L = np.where(esc, yb + g[None, :] * dn, L)
        if cfg.c_suavizado > 0:
            nu = cfg.nu_suavizado
            ruido = rng.standard_t(nu, size=L.shape) * np.sqrt((nu - 2) / nu)
            sd = np.zeros_like(L)
            for (i, j) in self.celdas:
                m = (s == i) & (s_new == j)
                if m.any():
                    sdc, nc = self.sd_celda[(i, j)]
                    # n efectivo de la celda con la mezcla: n + k (el padre aporta k "pseudofilas")
                    sd[m] = sdc * np.sqrt(cfg.c_suavizado / np.maximum(nc + cfg.k_mezcla, 1))
            L = L + sd * ruido
        X[:, :A] = np.where(np.isfinite(L), np.expm1(L), X[:, :A])
        return X

    def _imputar(self, Xh, s, s_new, rng):
        """Huecos (p. ej. oro antes de su inicio, vivienda): donante al azar de la misma celda con dato."""
        for v in range(Xh.shape[1]):
            falta = ~np.isfinite(Xh[:, v])
            if not falta.any():
                continue
            for (i, j) in self.celdas:
                m = falta & (s == i) & (s_new == j)
                if m.any():
                    d = self.donantes[((i, j), v)]
                    if len(d):
                        Xh[m, v] = self.V[rng.choice(d, m.sum()), v]

    # ------------------------------------------------------------ modo paramétrico t
    def _momentos(self, base, peso_año):
        A = len(self.cfg.activos)
        Y = self.V.copy()
        Y[:, :A] = np.log1p(Y[:, :A])
        todo = _cov_ponderada(Y, peso_año)
        out = {}
        for c, idx in self.celdas.items():
            mu, cov, n = _cov_ponderada(Y[idx], base[c] * peso_año[idx])
            mu = np.where(np.isfinite(mu), mu, todo[0])
            cov = (n * np.nan_to_num(cov) + self.cfg.n0_cov * todo[1]) / (n + self.cfg.n0_cov)
            if self.cfg.c_suavizado > 0:                      # v2: predictiva de muestra finita (1 + c/n)
                cov = cov * (1 + self.cfg.c_suavizado / max(n, 1.0))
            out[c] = (mu, _chol_psd(cov))
        return out

    def _t(self, mom, m, rng):
        mu, L = mom
        nu = self.cfg.nu_t
        z = rng.standard_normal((m, len(mu))) @ L.T
        esc = np.sqrt((nu - 2) / rng.chisquare(nu, size=(m, 1)))
        x = mu + z * esc
        A = len(self.cfg.activos)
        x[:, :A] = np.expm1(x[:, :A])
        return x

    # ------------------------------------------------------------ "qué activo gana en qué régimen"
    def tabla_regimenes(self, pais: str, n_lotes: int = 200, por_lote: int = 100, semilla: int = 0) -> pd.DataFrame:
        """Para cada régimen CONOCIDO al empezar el año (s_{t−1}): rentabilidad real del año siguiente por activo —
        media, p10, p50, p90, P(ser el mejor activo), P(< 0) — con IC 90 % de parámetros."""
        filas = []
        for i, reg in enumerate(REGIMENES):
            e = self.simular(pais, i, horizonte=1, n_lotes=n_lotes, por_lote=por_lote, semilla=semilla + i)
            R = e.rent[:, 0, :]
            ok = np.isfinite(R).all(axis=1)
            mejor = np.argmax(np.where(np.isfinite(R), R, -np.inf), axis=1)
            for j, a in enumerate(e.activos):
                med = _media_e_ic(R[:, j], e.lote)
                pb = _media_e_ic(np.where(ok, mejor == j, np.nan), e.lote)
                pn = _media_e_ic(R[:, j] < 0, e.lote)
                q = np.nanpercentile(R[:, j], [10, 50, 90])
                filas.append({"regimen": reg, "activo": a, "media": med["p"], "media_ic90": med["ic90"],
                              "p10": q[0], "p50": q[1], "p90": q[2], "p_mejor": pb["p"], "p_mejor_ic90": pb["ic90"],
                              "p_negativa": pn["p"]})
        return pd.DataFrame(filas)


# ============================================================================ utilidades
def _dirichlet_filas(alpha: np.ndarray, rng) -> np.ndarray:
    g = rng.standard_gamma(np.maximum(alpha, 1e-9))
    return g / g.sum(-1, keepdims=True)


def _categorica(pr: np.ndarray, rng) -> np.ndarray:
    c = np.cumsum(pr, axis=-1)
    u = rng.random(pr.shape[:-1])[..., None]
    return np.minimum((u * c[..., -1:] > c).sum(-1), pr.shape[-1] - 1)


def _cov_ponderada(Y: np.ndarray, w: np.ndarray):
    """Media y covarianza ponderadas por pares completos; n efectivo de Kish."""
    ok = np.isfinite(Y)
    W = w[:, None] * ok
    mu = np.where(W.sum(0) > 0, np.nansum(W * np.nan_to_num(Y), 0) / np.maximum(W.sum(0), 1e-12), np.nan)
    Z = np.where(ok, Y - mu, 0.0)
    num = (w[:, None] * Z).T @ Z
    den = (w[:, None] * ok).T @ ok.astype(float)
    cov = np.where(den > 0, num / np.maximum(den, 1e-12), 0.0)
    n = float(w.sum() ** 2 / max((w ** 2).sum(), 1e-12))
    return mu, cov, n


def _chol_psd(c: np.ndarray) -> np.ndarray:
    c = (c + c.T) / 2
    v, U = np.linalg.eigh(c)
    return U @ np.diag(np.sqrt(np.clip(v, 1e-10, None)))


# ============================================================================ puntuación (solo sintético hasta congelar)
def crps_muestra(x: np.ndarray, y) -> np.ndarray:
    """CRPS de la distribución empírica de la muestra x (n,) en cada y (m,): E|X − y| − ½ E|X − X'|. Menor = mejor."""
    x = np.sort(np.asarray(x, float)[np.isfinite(x)])
    y = np.atleast_1d(np.asarray(y, float))
    n = len(x)
    cs = np.concatenate([[0.0], np.cumsum(x)])
    k = np.searchsorted(x, y, side="right")
    e_xy = (k * y - cs[k]) + (cs[-1] - cs[k] - (n - k) * y)
    i = np.arange(1, n + 1)
    e_xx = 2.0 * np.sum((2 * i - n - 1) * x) / n ** 2
    return e_xy / n - 0.5 * e_xx


def crps_normal(mu, sd, y) -> np.ndarray:
    z = (np.asarray(y) - mu) / sd
    return sd * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))


def pit(x: np.ndarray, y, rng=None) -> np.ndarray:
    """PIT aleatorizado de y frente a la muestra x: U(0, 1) si el pronóstico está calibrado."""
    x = np.sort(np.asarray(x, float)[np.isfinite(x)])
    y = np.atleast_1d(np.asarray(y, float))
    lo, hi = np.searchsorted(x, y, "left"), np.searchsorted(x, y, "right")
    u = (rng or np.random.default_rng(0)).random(len(y))
    return (lo + u * (hi - lo)) / len(x)


def cobertura(x: np.ndarray, y, lo: float = 0.05, hi: float = 0.95) -> np.ndarray:
    q = np.nanquantile(x, [lo, hi])
    y = np.atleast_1d(np.asarray(y, float))
    return (y >= q[0]) & (y <= q[1])


def log_score(x: np.ndarray, y) -> np.ndarray:
    """−log densidad (núcleo gaussiano, ancho de Silverman) de y bajo la muestra x. Menor = mejor."""
    x = np.asarray(x, float)[np.isfinite(x)]
    y = np.atleast_1d(np.asarray(y, float))
    s = min(np.std(x, ddof=1), stats.iqr(x) / 1.349) if stats.iqr(x) > 0 else np.std(x, ddof=1)
    bw = 0.9 * s * len(x) ** (-0.2)
    dens = stats.norm.pdf((y[:, None] - x[None, :]) / bw).mean(1) / bw
    return -np.log(np.maximum(dens, 1e-300))


def dm_conglomerado(d: np.ndarray, anio: np.ndarray, lags: int = 2) -> dict:
    """Contraste de Diebold-Mariano para d = puntuación(referencia) − puntuación(modelo) (> 0: mejora), con los AÑOS
    como conglomerados (choques comunes entre países) y Newey-West entre años (solapes de horizonte). t con
    (años − 1) g. l.; p unilateral H1: media > 0."""
    d, anio = np.asarray(d, float), np.asarray(anio)
    ok = np.isfinite(d)
    d, anio = d[ok], anio[ok]
    n = len(d)
    m = d.mean()
    años = np.unique(anio)
    s = pd.Series(d - m).groupby(anio).sum().reindex(años, fill_value=0.0).to_numpy()
    v = (s ** 2).sum()
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (s[l:] * s[:-l]).sum()
    se = np.sqrt(max(v, 1e-300)) / n
    t = m / se
    return {"media": float(m), "se": float(se), "t": float(t), "p_unilateral": float(stats.t.sf(t, len(años) - 1)),
            "años": int(len(años)), "n": int(n)}


def cobertura_contraste(dentro: np.ndarray, anio: np.ndarray, nominal: float, lags: int = 2) -> dict:
    """H0: cobertura = nominal (bilateral), errores por conglomerados de año."""
    r = dm_conglomerado(np.asarray(dentro, float) - nominal, anio, lags)
    p = float(2 * stats.t.sf(abs(r["t"]), r["años"] - 1))
    return {"cobertura": r["media"] + nominal, "se": r["se"], "t": r["t"], "p_bilateral": p, "años": r["años"],
            "n": r["n"]}
