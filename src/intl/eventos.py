"""INT-14: definiciones operativas de EVENTOS (shock del petróleo, crisis bancaria, subida fuerte del dólar, pico de
volatilidad / VIX) y maquinaria del estudio de eventos (diseño: docs/int/INT14_eventos_v0.md; prerregistro en borrador:
docs/int/INT14_prerregistro_v0.md).

Disciplina:
  - Funciones puras: este módulo NO lee datos. Quien lo use le pasa series ya cortadas ≤ 2004 (`exigir_corte`).
  - Las DEFINICIONES de evento solo usan la serie que define el evento (precio del petróleo, índice del dólar, volatilidad,
    indicador de crisis). Nada de rentabilidades de los activos.
  - Todo umbral "móvil" (percentil de la volatilidad) es AS OF: solo usa meses anteriores al mes evaluado.
  - El estudio de eventos (`efecto_eventos`, `placebo`, `ic_bloques`, `efecto_panel`) solo se ha probado con datos
    sintéticos. Correrlo con rentabilidades reales exige el prerregistro congelado (v1) y una ejecución con puerta.

Unidades: precios e índices en nivel; rentabilidades mensuales/anuales simples en fracción; volatilidad anualizada en
fracción; "subida" en log (0,10 ≈ +10,5 %).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from src.intl.data import DEV_END, FactorCutoffError

VERSION = "0.1"
DIAS_AÑO = 252

# ---------------------------------------------------------------------------------------------------- parámetros v0
# Fijados en docs/int/INT14_eventos_v0.md §2 ANTES de mirar ningún efecto. Cambiarlos exige nueva versión del documento.
PETROLEO = dict(ventana=36, acumulacion=12, umbral=0.20, separacion=24, retraso=1)  # Σ12m NOPI(36) ≥ 20 % (log)
PETROLEO_ANUAL = dict(ventana=3, umbral=0.10, separacion=2)             # sensibilidad < 1890: precio medio anual
DOLAR = dict(ventana=12, umbral=0.10, separacion=24, retraso=1)          # Δlog 12 m del índice ≥ 10 %
DOLAR_ANUAL = dict(umbral=0.10, separacion=2)                           # Δlog anual de la cesta JST ≥ 10 %
VOL = dict(cuantil=0.90, min_hist=60, separacion=12, retraso=0)          # RV del mes ≥ P90 de los meses ANTERIORES
CRISIS = dict(separacion=5, hueco_global=1, min_paises_global=3)         # JST crisisJST (año de inicio)


def exigir_corte(s: pd.Series | pd.DataFrame, nombre: str = "serie") -> None:
    """Falla cerrado si hay fechas > DEV_END (2004-12-31)."""
    idx = s.index
    if isinstance(idx, pd.PeriodIndex):
        idx = idx.to_timestamp(how="start")
    if len(idx) and pd.Timestamp(idx.max()) > DEV_END:
        raise FactorCutoffError(f"INT-14: {nombre} tiene fechas > {DEV_END.date()} (periodo ≥ 2005 bloqueado)")


# ---------------------------------------------------------------------------------------------------- utilidades
def a_mensual(s: pd.Series, como: str = "media") -> pd.Series:
    """Serie con índice de fechas → PeriodIndex mensual ('media' o 'ultimo' del mes)."""
    s = s.dropna().sort_index()
    g = s.groupby(s.index.to_period("M"))
    return g.mean() if como == "media" else g.last()


def episodios(marca: pd.Series, separacion: int, modo: str = "cruce") -> pd.Series:
    """marca: booleana con índice ordenado (Period mensual o año entero), SIN huecos de calendario (reindexar antes).
    Devuelve las fechas de INICIO de episodio.
      modo "cruce" (v0, principal): periodo marcado cuyo periodo anterior NO está marcado (cruce fresco del umbral) y
        a ≥ `separacion` periodos del inicio del episodio anterior. Evita que una racha larga (p. ej. volatilidad alta
        1997-2003) se encadene en un solo episodio, y que un mismo cruce cuente dos veces.
      modo "racha": periodo marcado sin ninguna marca en los `separacion` periodos anteriores (encadena rachas;
        sensibilidad)."""
    m = marca.fillna(False).astype(bool).to_numpy()
    ini = np.zeros(len(m), bool)
    if modo == "racha":
        ultimo = -10 ** 9
        for i, v in enumerate(m):
            if v:
                if i - ultimo > separacion:
                    ini[i] = True
                ultimo = i
        return pd.Series(ini, index=marca.index)
    if modo != "cruce":
        raise ValueError(modo)
    ult_ini = -10 ** 9
    for i, v in enumerate(m):
        if v and (i == 0 or not m[i - 1]) and i - ult_ini >= separacion:
            ini[i] = True
            ult_ini = i
    return pd.Series(ini, index=marca.index)


def _completa_mensual(s: pd.Series) -> pd.Series:
    if not isinstance(s.index, pd.PeriodIndex):
        raise ValueError("se espera PeriodIndex mensual")
    return s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"))


# ---------------------------------------------------------------------------------------------------- petróleo
def nopi(p: pd.Series, ventana: int = 36) -> pd.Series:
    """Net oil price increase (Hamilton 1996, 2003): max(0, log p_t − log max(p_{t−1}, …, p_{t−ventana})). NaN si falta
    algún dato de la ventana (no se rellenan huecos: un hueco de 1941-46 deja la serie sin definir hasta 36 meses
    después)."""
    lp = np.log(p.astype(float))
    prev_max = lp.shift(1).rolling(ventana, min_periods=ventana).max()
    return np.maximum(lp - prev_max, 0.0).where(prev_max.notna() & lp.notna())


def eventos_petroleo(p_mensual: pd.Series, ventana: int = PETROLEO["ventana"],
                     acumulacion: int = PETROLEO["acumulacion"], umbral: float = PETROLEO["umbral"],
                     separacion: int = PETROLEO["separacion"]) -> pd.DataFrame:
    """p_mensual: precio nominal del petróleo con PeriodIndex mensual. Intensidad = NOPI(ventana) ACUMULADO en los
    últimos `acumulacion` meses (suma de las subidas netas sobre el máximo de 3 años: si el precio marca máximos
    sucesivos, es la subida total por encima del máximo previo). Evento = cruce fresco de intensidad ≥ umbral, a
    ≥ `separacion` meses del evento anterior. Devuelve fecha, intensidad y NOPI del mes."""
    exigir_corte(p_mensual, "petróleo")
    p = _completa_mensual(p_mensual)
    n = nopi(p, ventana)
    inten = n.rolling(acumulacion, min_periods=acumulacion).sum()
    ini = episodios(inten >= umbral, separacion)
    return pd.DataFrame({"fecha": inten.index[ini.to_numpy()], "intensidad": inten[ini].to_numpy(),
                         "nopi_mes": n[ini].to_numpy()})


def eventos_petroleo_anual(p_anual: pd.Series, ventana: int = PETROLEO_ANUAL["ventana"],
                           umbral: float = PETROLEO_ANUAL["umbral"],
                           separacion: int = PETROLEO_ANUAL["separacion"]) -> pd.Series:
    """p_anual: precio medio anual (índice = año entero). Devuelve los años de inicio de episodio (NOPI a 3 años)."""
    p = p_anual.sort_index()
    if p.index.max() > DEV_END.year:
        raise FactorCutoffError("INT-14: petróleo anual > 2004")
    p = p.reindex(range(int(p.index.min()), int(p.index.max()) + 1))
    n = nopi(p, ventana)
    ini = episodios(n >= umbral, separacion)
    return pd.Series(n[ini].values, index=n.index[ini.to_numpy()], name="nopi")


def mensual_petroleo_encadenado(tramos: list[pd.Series]) -> pd.Series:
    """Encadena tramos mensuales (PeriodIndex) SIN rellenar huecos y SIN reescalar: el NOPI es un cociente dentro de la
    ventana, así que solo importa que la ventana no cruce el empalme. Para eso el empalme se trata como hueco: los
    primeros `ventana` meses tras el inicio de cada tramo nuevo quedan sin NOPI (lo hace `nopi` al ver NaN). Si dos
    tramos se solapan, manda el más reciente."""
    out = pd.Series(dtype=float)
    for k, t in enumerate(tramos):
        t = t.dropna().sort_index()
        if k > 0 and len(out):
            # forzar un hueco de un mes en el empalme para que ninguna ventana mezcle tramos
            out = out[out.index < t.index.min() - 1]
        out = pd.concat([out, t])
    out.index = pd.PeriodIndex(out.index, freq="M")
    return out.sort_index()


# ---------------------------------------------------------------------------------------------------- dólar
def eventos_dolar(indice_mensual: pd.Series, ventana: int = DOLAR["ventana"], umbral: float = DOLAR["umbral"],
                  separacion: int = DOLAR["separacion"]) -> pd.DataFrame:
    """indice_mensual: índice del dólar (más alto = dólar más fuerte), PeriodIndex mensual. Evento = primer mes con
    Δlog a `ventana` meses ≥ umbral, sin otro mes ≥ umbral en los `separacion` previos."""
    exigir_corte(indice_mensual, "dólar")
    x = _completa_mensual(indice_mensual)
    d = np.log(x).diff(ventana)
    ini = episodios(d >= umbral, separacion)
    return pd.DataFrame({"fecha": d.index[ini.to_numpy()], "subida_log": d[ini].to_numpy()})


def cesta_dolar_anual(xrusd: pd.DataFrame) -> pd.Series:
    """xrusd: años × países, moneda local por USD (JST). Índice del dólar = media geométrica igual-ponderada de los
    países con dato en t y t − 1 (cadena de Δlog; sin pesos comerciales, que no existen antes de 1973)."""
    d = np.log(xrusd.astype(float)).diff()
    d = d.where(np.isfinite(d))
    m = d.mean(axis=1, skipna=True).where(d.notna().sum(axis=1) >= 5)
    return m.cumsum().where(m.notna())


def eventos_dolar_anual(dlog_anual: pd.Series, umbral: float = DOLAR_ANUAL["umbral"],
                        separacion: int = DOLAR_ANUAL["separacion"], excluir: frozenset = frozenset()) -> pd.Series:
    d = dlog_anual.copy()
    d[d.index.isin(list(excluir))] = np.nan
    d = d.reindex(range(int(d.index.min()), int(d.index.max()) + 1))
    ini = episodios(d >= umbral, separacion)
    return pd.Series(d[ini].values, index=d.index[ini.to_numpy()], name="subida_log")


# ---------------------------------------------------------------------------------------------------- volatilidad / VIX
def vol_realizada_mensual(r_diaria: pd.Series, min_dias: int = 15) -> pd.Series:
    """Volatilidad realizada anualizada de cada mes = sqrt(252 · media de r²) con los días del mes (rentabilidades
    diarias en fracción). Meses con < min_dias días → NaN. PeriodIndex mensual."""
    exigir_corte(r_diaria, "rentabilidad diaria")
    r = r_diaria.dropna().sort_index()
    g = (r ** 2).groupby(r.index.to_period("M"))
    rv = np.sqrt(DIAS_AÑO * g.mean())
    return rv.where(g.count() >= min_dias)


def umbral_expansivo(x: pd.Series, cuantil: float, min_hist: int) -> pd.Series:
    """Umbral AS OF: cuantil de los valores ESTRICTAMENTE anteriores (ventana creciente); NaN con < min_hist."""
    return x.shift(1).expanding(min_periods=min_hist).quantile(cuantil)


def eventos_vol(x_mensual: pd.Series, cuantil: float = VOL["cuantil"], min_hist: int = VOL["min_hist"],
                separacion: int = VOL["separacion"]) -> pd.DataFrame:
    """x_mensual: volatilidad mensual (realizada o VIX medio del mes), PeriodIndex. Evento = primer mes con x ≥ umbral
    expansivo (cuantil de los meses anteriores) sin otro mes ≥ umbral en los `separacion` previos."""
    exigir_corte(x_mensual, "volatilidad")
    x = _completa_mensual(x_mensual)
    u = umbral_expansivo(x, cuantil, min_hist)
    marca = (x >= u) & u.notna()
    ini = episodios(marca, separacion)
    return pd.DataFrame({"fecha": x.index[ini.to_numpy()], "nivel": x[ini].to_numpy(), "umbral": u[ini].to_numpy()})


def correspondencia_vix_rv(vix_m: pd.Series, rv_m: pd.Series, cuantil: float = VOL["cuantil"]) -> dict:
    """Solape VIX ↔ volatilidad realizada (ambas mensuales, mismo índice). Describe la equivalencia de los DOS
    definidores de evento; no toca ninguna rentabilidad futura. Devuelve: correlación (niveles y logs), nivel medio,
    VIX equivalente al cuantil de la RV (por cuantiles), y acuerdo de los meses "altos" (≥ cuantil de su propia
    muestra): proporción de acuerdo, kappa de Cohen, sensibilidad de RV para meses de VIX alto."""
    d = pd.concat({"vix": vix_m, "rv": rv_m}, axis=1).dropna()
    hv, hr = d.vix >= d.vix.quantile(cuantil), d.rv >= d.rv.quantile(cuantil)
    po = float((hv == hr).mean())
    pe = float(hv.mean() * hr.mean() + (1 - hv.mean()) * (1 - hr.mean()))
    return {"meses": int(len(d)), "desde": str(d.index.min()), "hasta": str(d.index.max()),
            "corr_niveles": float(d.vix.corr(d.rv)), "corr_logs": float(np.log(d.vix).corr(np.log(d.rv))),
            "media_vix_pct": float(d.vix.mean()), "media_rv_pct": float(d.rv.mean()),
            "prima_media_vix_menos_rv_pct": float((d.vix - d.rv).mean()),
            f"rv_p{int(cuantil * 100)}": float(d.rv.quantile(cuantil)),
            f"vix_p{int(cuantil * 100)}": float(d.vix.quantile(cuantil)),
            "acuerdo_meses_altos": po, "kappa_cohen": (po - pe) / (1 - pe) if pe < 1 else np.nan,
            "sens_rv_dado_vix_alto": float(hr[hv].mean()) if hv.any() else np.nan}


# ---------------------------------------------------------------------------------------------------- crisis bancarias
def eventos_crisis(crisis: pd.DataFrame, separacion: int = CRISIS["separacion"]) -> pd.DataFrame:
    """crisis: años × países con 0/1 (JST crisisJST marca el AÑO DE INICIO). Por país, un año marcado a menos de
    `separacion` años del anterior se trata como continuación (JST rara vez lo hace; se informa cuántos caen)."""
    if crisis.index.max() > DEV_END.year:
        raise FactorCutoffError("INT-14: crisis > 2004")
    filas = []
    for c in crisis.columns:
        s = crisis[c].dropna()
        s = s.reindex(range(int(s.index.min()), int(s.index.max()) + 1))
        ini = episodios(s >= 1, separacion)
        for a in s.index[ini.to_numpy()]:
            filas.append({"pais": c, "año": int(a)})
        filas_desc = int((s >= 1).sum() - ini.sum())
        if filas_desc:
            filas.append({"pais": c, "año": -1, "descartadas_por_separacion": filas_desc})
    d = pd.DataFrame(filas)
    if "descartadas_por_separacion" not in d:
        d["descartadas_por_separacion"] = np.nan
    return d


def conglomerados_globales(años: list[int] | np.ndarray, hueco: int = CRISIS["hueco_global"]) -> pd.DataFrame:
    """Agrupa años de evento (de cualquier país) en episodios globales: un año a ≤ `hueco` años del anterior se une al
    mismo episodio (encadenado). Devuelve inicio, fin, n eventos."""
    a = np.sort(np.asarray(años, int))
    if not len(a):
        return pd.DataFrame(columns=["inicio", "fin", "n"])
    grupos, ini, prev, n = [], a[0], a[0], 1
    for x in a[1:]:
        if x - prev <= hueco:
            n += 1
        else:
            grupos.append((ini, prev, n))
            ini, n = x, 1
        prev = x
    grupos.append((ini, prev, n))
    return pd.DataFrame(grupos, columns=["inicio", "fin", "n"])


def n_efectivo(n_por_conglomerado: np.ndarray, icc: float) -> float:
    """Tamaño efectivo con conglomerados de tamaño desigual: Σ m_g / (1 + (m̄* − 1)·ICC), m̄* = Σ m² / Σ m (Kish)."""
    m = np.asarray(n_por_conglomerado, float)
    if not len(m):
        return 0.0
    mbar = (m ** 2).sum() / m.sum()
    return float(m.sum() / (1 + (mbar - 1) * icc))


# ---------------------------------------------------------------------------------------------------- estudio de eventos
@dataclass
class Efecto:
    h: int
    n_eventos: int
    media_evento: float          # media de la rentabilidad acumulada (log) a h tras el evento
    media_incond: float          # media de la acumulada a h en todos los orígenes válidos SIN evento en ventana
    efecto: float                # diferencia (log); en pp ≈ 100·efecto
    acumuladas: np.ndarray       # una por evento
    fechas: list                 # fechas de los eventos usados (con acumulada definida)


def acumulada_futura(r: pd.Series, h: int, retraso: int = 0) -> pd.Series:
    """r: rentabilidad simple por periodo (PeriodIndex completo). Para cada origen t: Σ log(1+r) de t+retraso+1 a
    t+retraso+h (solo periodos POSTERIORES al origen y al retraso de publicación). NaN si falta alguno."""
    lr = np.log1p(r.astype(float))
    s = lr.rolling(h, min_periods=h).sum()
    return s.shift(-(h + retraso))


def efecto_eventos(r: pd.Series, fechas, h: int, retraso: int = 0, excluir_ventana: bool = True) -> Efecto:
    """Efecto medio (log) a h periodos: media de la acumulada tras cada evento menos la media incondicional de los
    orígenes que no tienen ningún evento en (t − h, t] (con excluir_ventana)."""
    acc = acumulada_futura(r, h, retraso)
    fechas = [f for f in fechas if f in acc.index and np.isfinite(acc.loc[f])]
    ev = np.array([acc.loc[f] for f in fechas], float)
    pos = acc.index.get_indexer(fechas)
    marca = np.zeros(len(acc), bool)
    marca[pos] = True
    if excluir_ventana:
        cerca = pd.Series(marca).rolling(h, min_periods=1).max().to_numpy().astype(bool)
    else:
        cerca = marca
    base = acc.to_numpy()[(~cerca) & np.isfinite(acc.to_numpy())]
    mi = float(base.mean()) if len(base) else np.nan
    me = float(ev.mean()) if len(ev) else np.nan
    return Efecto(h, len(ev), me, mi, me - mi, ev, fechas)


def ic_bloques(ef: Efecto, bloque: int, n_boot: int = 2000, nivel: float = 0.90, semilla: int = 0,
               conglomerado=None) -> tuple[float, float]:
    """IC del efecto por bootstrap de BLOQUES DE CALENDARIO: los eventos se agrupan en bloques de `bloque` periodos (o
    por la etiqueta `conglomerado`, p. ej. episodio global) y se remuestrean bloques enteros (eventos cercanos en el
    tiempo comparten choque). La media incondicional se trata como fija (muchos más orígenes)."""
    rng = np.random.default_rng(semilla)
    x = ef.acumuladas
    if len(x) < 2:
        return (np.nan, np.nan)
    if conglomerado is None:
        orden = np.array([f.ordinal if hasattr(f, "ordinal") else int(f) for f in ef.fechas])
        g = (orden - orden.min()) // bloque
    else:
        g = np.asarray(conglomerado)
    ids = np.unique(g)
    grupos = [x[g == i] for i in ids]
    meds = np.empty(n_boot)
    for b in range(n_boot):
        tom = rng.integers(0, len(grupos), len(grupos))
        v = np.concatenate([grupos[i] for i in tom])
        meds[b] = v.mean()
    a = (1 - nivel) / 2
    lo, hi = np.quantile(meds - ef.media_incond, [a, 1 - a])
    return float(lo), float(hi)


def placebo(r: pd.Series, n_eventos: int, h: int, retraso: int, separacion: int, n_rep: int = 1000,
            semilla: int = 0, candidatos: pd.Index | None = None, excluir: list | None = None) -> np.ndarray:
    """Distribución del efecto con FECHAS FALSAS: n_eventos fechas al azar entre los orígenes válidos (o `candidatos`),
    separadas ≥ `separacion` periodos entre sí y lejos (> h) de los eventos verdaderos (`excluir`). Mismo cálculo que
    `efecto_eventos`. El valor p bilateral = proporción de |placebo| ≥ |efecto|."""
    rng = np.random.default_rng(semilla)
    acc = acumulada_futura(r, h, retraso)
    validos = np.flatnonzero(np.isfinite(acc.to_numpy()))
    if candidatos is not None:
        validos = np.intersect1d(validos, acc.index.get_indexer(candidatos))
    if excluir:
        pe = acc.index.get_indexer([f for f in excluir if f in acc.index])
        lejos = np.ones(len(acc), bool)
        for p in pe:
            lejos[max(0, p - h):p + h + 1] = False
        validos = validos[lejos[validos]]
    out = np.full(n_rep, np.nan)
    for k in range(n_rep):
        elegidos = []
        for i in rng.permutation(validos):
            if all(abs(i - j) >= separacion for j in elegidos):
                elegidos.append(i)
                if len(elegidos) == n_eventos:
                    break
        if len(elegidos) < n_eventos:
            continue
        out[k] = efecto_eventos(r, list(acc.index[elegidos]), h, retraso).efecto
    return out


def p_placebo(efecto: float, dist: np.ndarray) -> float:
    d = dist[np.isfinite(dist)]
    return float((1 + (np.abs(d) >= abs(efecto)).sum()) / (1 + len(d)))


def efecto_panel(r: pd.DataFrame, eventos: pd.DataFrame, H: int, comun: bool = False) -> dict:
    """Panel anual país-año. r: años × países (rentabilidad real simple). eventos: columnas pais, año (país-evento) o,
    con comun=True, solo 'año' (evento global: afecta a todos los países). Resultado: para cada evento (país, año) la
    acumulada log de t+1 a t+H menos la media incondicional del país (años sin evento en (t − H, t]); efecto = media.
    Conglomerado = año del evento (eventos del mismo año comparten choque)."""
    lr = np.log1p(r.astype(float))
    acc = lr[::-1].rolling(H, min_periods=H).sum()[::-1].shift(-1)       # t+1..t+H
    marca = pd.DataFrame(False, index=r.index, columns=r.columns)
    pares = ([(c, int(a)) for a in eventos["año"] for c in r.columns] if comun
             else [(c, int(a)) for c, a in zip(eventos["pais"], eventos["año"]) if c in r.columns])
    for c, a in pares:
        if a in marca.index:
            marca.loc[a, c] = True
    cerca = marca.astype(float).rolling(H, min_periods=1).max().astype(bool)
    base = acc.where(~cerca).mean()
    filas = [{"pais": c, "año": a, "acc": float(acc.loc[a, c]) - float(base[c])}
             for c, a in pares if a in acc.index and np.isfinite(acc.loc[a, c]) and np.isfinite(base[c])]
    d = pd.DataFrame(filas, columns=["pais", "año", "acc"])
    return {"H": H, "n": int(len(d)), "efecto": float(d["acc"].mean()) if len(d) else np.nan, "detalle": d}


def ic_panel(d: pd.DataFrame, n_boot: int = 2000, nivel: float = 0.90, semilla: int = 0,
             conglomerado: str = "año") -> tuple[float, float]:
    """Bootstrap por conglomerados (años del evento, o episodio global si se pasa esa columna)."""
    rng = np.random.default_rng(semilla)
    grupos = [g["acc"].to_numpy() for _, g in d.groupby(conglomerado)]
    if len(grupos) < 2:
        return (np.nan, np.nan)
    meds = np.array([np.concatenate([grupos[i] for i in rng.integers(0, len(grupos), len(grupos))]).mean()
                     for _ in range(n_boot)])
    a = (1 - nivel) / 2
    lo, hi = np.quantile(meds, [a, 1 - a])
    return float(lo), float(hi)


def holm(pvals: dict) -> dict:
    """Ajuste de Holm (familia de contrastes principales)."""
    k = sorted(pvals, key=lambda x: pvals[x])
    m, out, acum = len(k), {}, 0.0
    for i, c in enumerate(k):
        acum = max(acum, min(1.0, (m - i) * pvals[c]))
        out[c] = acum
    return out


# ---------------------------------------------------------------------------------------------------- potencia
def mde_media(sd_evento: float, n_eff: float, alfa: float = 0.05, potencia: float = 0.80, colas: int = 2) -> float:
    """Efecto mínimo detectable de una media de n_eff eventos independientes con dispersión sd_evento (aprox. normal)."""
    za = stats.norm.ppf(1 - alfa / colas)
    zb = stats.norm.ppf(potencia)
    return float((za + zb) * sd_evento / np.sqrt(max(n_eff, 1e-9)))


def auc(y: np.ndarray, s: np.ndarray) -> float:
    y = np.asarray(y, bool)
    rk = stats.rankdata(s)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    return float((rk[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def potencia_clasificacion(n_pos: int, n_neg: int, b_liston: float, b_extra: float, alfa: float = 0.05,
                           n_rep: int = 300, n_boot: int = 199, semilla: int = 0) -> dict:
    """Potencia de "anticipar el evento" (uso B) con n_pos eventos independientes y n_neg no-eventos.
    Verdad: logit P(evento) = a + b_liston·x1 + b_extra·x2, x1, x2 ~ N(0, 1) independientes; el LISTÓN ve x1 y el
    MODELO ve x1 y x2; ambos con probabilidades verdaderas (calibración de oráculo: optimista). Se fija la muestra
    caso-control (n_pos, n_neg) como en los datos. Contraste unilateral por bootstrap pareado estratificado
    (percentil) de ΔAUC y de ΔBrier. Devuelve potencia de cada uno y las ganancias medias."""
    rng = np.random.default_rng(semilla)
    base = n_pos / (n_pos + n_neg)

    # intercepto que da la tasa base en la población (búsqueda simple con una muestra grande)
    xg = rng.standard_normal((200_000, 2))
    lo, hi = -15.0, 5.0
    for _ in range(50):
        a = 0.5 * (lo + hi)
        pr = special_expit(a + b_liston * xg[:, 0] + b_extra * xg[:, 1]).mean()
        lo, hi = (a, hi) if pr < base else (lo, a)
    ok_auc = ok_bri = 0
    g_auc, g_bss = [], []
    for _ in range(n_rep):
        pos, neg = [], []
        while len(pos) < n_pos or len(neg) < n_neg:
            x = rng.standard_normal((4 * (n_pos + n_neg), 2))
            p = special_expit(a + b_liston * x[:, 0] + b_extra * x[:, 1])
            y = rng.random(len(p)) < p
            pos.extend(x[y][: n_pos - len(pos)])
            neg.extend(x[~y][: n_neg - len(neg)])
        X = np.vstack([np.array(pos), np.array(neg)])
        y = np.r_[np.ones(n_pos, bool), np.zeros(n_neg, bool)]
        p1 = special_expit((a + b_liston * X[:, 0]) / np.sqrt(1 + np.pi * b_extra ** 2 / 8))   # E[p | x1] (aprox. probit)
        p2 = special_expit(a + b_liston * X[:, 0] + b_extra * X[:, 1])
        d_auc = auc(y, p2) - auc(y, p1)
        d_bri = brier(y, p1) - brier(y, p2)
        g_auc.append(d_auc)
        g_bss.append(d_bri / max(brier(y, np.full(len(y), base)), 1e-12))
        ip, ineg = np.flatnonzero(y), np.flatnonzero(~y)
        da, db = np.empty(n_boot), np.empty(n_boot)
        for b in range(n_boot):
            idx = np.r_[rng.choice(ip, n_pos), rng.choice(ineg, n_neg)]
            da[b] = auc(y[idx], p2[idx]) - auc(y[idx], p1[idx])
            db[b] = brier(y[idx], p1[idx]) - brier(y[idx], p2[idx])
        ok_auc += np.quantile(da, alfa) > 0
        ok_bri += np.quantile(db, alfa) > 0
    return {"potencia_auc": ok_auc / n_rep, "potencia_brier": ok_bri / n_rep,
            "delta_auc_medio": float(np.mean(g_auc)), "delta_bss_medio": float(np.mean(g_bss))}


def special_expit(z):
    return 1.0 / (1.0 + np.exp(-np.asarray(z, float)))
