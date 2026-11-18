"""Pulso por país (DESCRIPTIVO, no validado): cómo está HOY cada uno de los 18 países del panel internacional en
crecimiento, inflación, empleo, tipos y bonos, cuentas públicas, bolsa, vivienda y confianza.

Para qué: el motor de escenarios (INT-11) clasifica el régimen con dos ejes congelados con datos ≤ 2004 (inflación
media de 12 meses > 3 % y PIB per cápita frente a la media de sus 10 años anteriores). Ese eje de crecimiento solo
baja de 0 con caídas fuertes del PIB, así que un país estancado (p. ej. Francia, nov-2026: PIB −0,1 % a/a) sigue en
«expansión». Esta sección enseña lo que el régimen no mira (ritmo actual, bonos, deuda, déficit) para leerlo bien.
NO cambia el motor, ni sus probabilidades, ni ninguna señal: son lecturas con reglas fijas y umbrales redondos
escritos aquí, sin ajustar a datos ni historial de aciertos.

Precisión (revisión del 12-nov):
- todas las comparaciones van por FECHA exacta (t − 12 meses, t − 3 meses, t − 4 trimestres…), nunca por posición:
  una serie con un mes ausente (EE. UU., cierre del Gobierno de oct-2025) no desplaza la comparación; si falta la
  fecha de referencia, el dato sale «s/d»;
- el diferencial frente a Alemania se calcula con el MISMO mes en los dos bonos;
- inflación general: el dato MÁS RECIENTE entre el IPC nacional (OCDE), el IPCA (BCE, países del euro) y, en EE. UU.,
  el IPC del BLS (CPIAUCSL, el mismo de «Hoy»); se
  enseñan los dos con su mes. Media de 12 meses (la del motor) con el índice OCDE; un único mes ausente se interpola
  (como INT-11) y se declara;
- deuda y saldo públicos: IMF WEO, proyección del año en curso de la última edición (se dice «previsión»).

Fuentes (warehouse): OCDE (PIB trimestral real SA, IPC, subyacente, paro armonizado, IP, tipos 3 m y 10 años, bolsa,
vivienda, CLI, confianza), BCE (IPCA general y subyacente) e IMF WEO.
Uso: src/report/weekly.py lo guarda en el signal (`pulso_paises`); lo pinta src/report/panel_paises.py.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.report import _percentil as PC

PAISES = ["USA", "DEU", "FRA", "ITA", "ESP", "GBR", "JPN", "NLD", "BEL", "PRT", "IRL", "FIN", "SWE", "DNK", "NOR",
          "CHE", "CAN", "AUS"]
EURO = {"DEU", "FRA", "ITA", "ESP", "NLD", "BEL", "PRT", "IRL", "FIN"}
BCE = {"DEU": "de", "FRA": "fr", "ITA": "it", "ESP": "es", "NLD": "nl", "PRT": "pt", "IRL": "ie", "BEL": "be", "FIN": "fi"}
NOMBRE = {"BEL": "Bélgica", "DEU": "Alemania", "DNK": "Dinamarca", "ESP": "España", "FIN": "Finlandia",
          "FRA": "Francia", "GBR": "Reino Unido", "ITA": "Italia", "JPN": "Japón", "NLD": "Países Bajos",
          "NOR": "Noruega", "PRT": "Portugal", "SWE": "Suecia", "USA": "EE. UU.", "AUS": "Australia", "CHE": "Suiza",
          "CAN": "Canadá", "IRL": "Irlanda"}
NOTAS = {"IRL": "El PIB de Irlanda está muy distorsionado por las multinacionales (el propio Gobierno usa el GNI*); "
                "léase su crecimiento y su «recesión» con cautela."}
DIAS_VIEJO = 200        # dato mensual con más de ≈ 6,5 meses → «con retraso»
DIAS_VIEJO_TRIM = 290   # trimestral (fecha = inicio del trimestre)

REGLAS = {
    "crecimiento": "PIB real frente al mismo trimestre del año anterior: < 0 % contracción (rojo); < 0,5 % o menos de "
                   "la mitad de su media de 10 años, estancado (ámbar); ≥ su media + 1 pp, fuerte (verde); si no, "
                   "normal (verde).",
    "inflacion": "Inflación general a/a (el dato más reciente entre IPC nacional e IPCA): < 1 % muy baja (ámbar); "
                 "1-3 % normal (verde); 3-5 % alta (ámbar); > 5 % muy alta (rojo).",
    "empleo": "Paro frente al mismo mes del año anterior: sube ≥ 0,5 pp (rojo); sube 0,2-0,5 pp (ámbar); si no (verde).",
    "bonos": "Euro (salvo Alemania): diferencial a 10 años frente a Alemania en el mismo mes > 1,5 pp (rojo), > 0,8 pp "
             "(ámbar). Alemania y fuera del euro: el 10 años sube ≥ 0,5 pp en 3 meses (ámbar).",
    "fiscal": "Deuda pública bruta / PIB y saldo público / PIB (FMI): deuda > 100 % y déficit > 4 % (rojo); uno de "
              "los dos (ámbar); deuda > 60 % con déficit > 3 % (ámbar).",
    "bolsa": "Índice de precios de la bolsa (OCDE, media mensual) frente a su máximo de los últimos 12 meses: caída "
             "≥ 20 % (rojo), ≥ 10 % (ámbar).",
    "confianza": "Indicador adelantado CLI de la OCDE (100 = tendencia): < 100 y bajando en 3 meses (ámbar); si no "
                 "(verde). Sin CLI para 9 países pequeños.",
}


# ---------------------------------------------------------------- lectura y aritmética por fecha
def _serie(con, sid: str, hasta: pd.Timestamp, tabla: str = "obs_latest") -> pd.Series:
    d = con.execute(f"select date, value from {tabla} where series_id = ? and date <= ? and value is not null "
                    "order by date", [sid, hasta]).fetchdf()
    if d.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    return pd.Series(d["value"].astype(float).values, index=pd.DatetimeIndex(d["date"]))


def _en(s: pd.Series, f: pd.Timestamp):
    """Valor en la fecha exacta f (o None)."""
    v = s.get(f)
    return None if v is None or not np.isfinite(v) else float(v)


def _ult(s: pd.Series):
    return (float(s.iloc[-1]), s.index[-1]) if len(s) else (None, None)


def _hace(s: pd.Series, meses: int):
    """(valor último, valor exactamente `meses` antes, fecha última)."""
    if not len(s):
        return None, None, None
    f = s.index[-1]
    return float(s.iloc[-1]), _en(s, f - pd.DateOffset(months=meses)), f


def _var(s: pd.Series, meses: int):
    v, a, _ = _hace(s, meses)
    return None if v is None or a is None or a == 0 else 100 * (v / a - 1)


def _dif(s: pd.Series, meses: int):
    v, a, _ = _hace(s, meses)
    return None if v is None or a is None else v - a


def _pct_hist(s: pd.Series, v):
    """(percentil 0-100 del valor de hoy frente a toda la historia de la serie, año de inicio) — descriptivo.
    Definición común del panel (_percentil): proporción de observaciones ≤ el valor (antes era < estricto)."""
    p = None if v is None else PC.percentil(s, v)
    return (None, None) if p is None else (int(p), int(s.dropna().index[0].year))


def _f(ts) -> str | None:
    return None if ts is None else str(pd.Timestamp(ts).date())


def _weo(con, iso: str, ind: str, año: int):
    """WEO: (año, valor) del año en curso proyectado (obs_all_latest, pit_role forecast) y (año, valor) último
    observado/estimado."""
    h = _serie(con, f"imf_weo_{iso.lower()}_{ind}", pd.Timestamp("2100-01-01"))
    p = _serie(con, f"imf_weo_{iso.lower()}_{ind}_proj", pd.Timestamp("2100-01-01"), "obs_all_latest")
    obs = (int(h.index[-1].year), float(h.iloc[-1])) if len(h) else (None, None)
    pr = p[p.index.year == año]
    proj = (año, float(pr.iloc[-1])) if len(pr) else (None, None)
    return obs, proj


def _media12(idx: pd.Series):
    """log-media de 12 meses frente a los 12 anteriores (como el motor), en %; interpola 1 mes suelto (declarado)."""
    if len(idx) < 24:
        return None, 0
    fin = idx.index[-1]
    rej = pd.date_range(fin - pd.DateOffset(months=23), fin, freq="MS")
    s = idx.reindex(rej)
    huecos = int(s.isna().sum())
    if huecos > 1 or s.iloc[[0, -1]].isna().any():
        return None, huecos
    s = np.exp(np.log(s).interpolate())
    return 100 * (s.iloc[12:].mean() / s.iloc[:12].mean() - 1), huecos


# ---------------------------------------------------------------- reglas de color (fijas)
def _color_crec(a, m10):
    if a is None:
        return "gris", "sin dato"
    if a < 0:
        return "rojo", "en contracción"
    if a < 0.5 or (m10 is not None and m10 > 0 and a < 0.5 * m10):
        return "ambar", "estancado"
    if m10 is not None and a >= m10 + 1:
        return "verde", "fuerte"
    return "verde", "normal"


def _color_infl(v):
    if v is None:
        return "gris", "sin dato"
    if v < 1:
        return "ambar", "muy baja"
    if v <= 3:
        return "verde", "normal"
    if v <= 5:
        return "ambar", "alta"
    return "rojo", "muy alta"


def _color_paro(d):
    if d is None:
        return "gris", "sin dato"
    if d >= 0.5:
        return "rojo", "sube con fuerza"
    if d >= 0.2:
        return "ambar", "sube"
    if d <= -0.2:
        return "verde", "baja"
    return "verde", "estable"


def _color_bonos(iso, dif, d3):
    if iso in EURO and iso != "DEU":
        if dif is None:
            return "gris", "sin dato"
        if dif > 1.5:
            return "rojo", "prima alta frente a Alemania"
        if dif > 0.8:
            return "ambar", "prima frente a Alemania"
        return "verde", "prima pequeña"
    if d3 is None:
        return "gris", "sin dato"
    if d3 >= 0.5:
        return "ambar", "el 10 años sube rápido"
    return "verde", "sin tensión"


def _color_fiscal(deuda, saldo):
    if deuda is None or saldo is None:
        return "gris", "sin dato"
    alta, deficit = deuda > 100, saldo < -4
    if alta and deficit:
        return "rojo", "deuda alta y déficit grande"
    if alta:
        return "ambar", "deuda alta"
    if deficit:
        return "ambar", "déficit grande"
    if deuda > 60 and saldo < -3:
        return "ambar", "deuda media y déficit"
    return "verde", "sin tensión"


def _color_bolsa(caida):
    if caida is None:
        return "gris", "sin dato"
    if caida <= -20:
        return "rojo", "mercado bajista"
    if caida <= -10:
        return "ambar", "corrección"
    return "verde", "sin caída relevante"


def _color_cli(v, d3):
    if v is None:
        return "gris", "sin dato"
    if v < 100 and d3 is not None and d3 < 0:
        return "ambar", "bajo tendencia y bajando"
    if v < 100:
        return "verde", "bajo tendencia, mejorando"
    return "verde", "sobre tendencia"


def _fmt(v, dec=1, suf=" %", signo=False):
    if v is None:
        return "s/d"
    if v == v and round(v, dec) == 0:   # sin «−0,0»
        v = 0.0
    s = f"{v:+.{dec}f}" if signo else f"{v:.{dec}f}"
    return s.replace(".", ",").replace("-", "−") + suf


def _mes(ts) -> str:
    MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    if ts is None:
        return "—"
    t = pd.Timestamp(ts)
    return f"{MESES[t.month - 1]}-{t.year}"


def _trim(ts) -> str:
    if ts is None:
        return "—"
    t = pd.Timestamp(ts)
    return f"T{(t.month - 1) // 3 + 1}-{t.year}"


def _dinero(con, iso: str, hoy: pd.Timestamp) -> dict:
    """Crecimiento interanual del dinero amplio: EE. UU. M2 (FRED M2SL); euro M3/M1 y préstamos al sector privado del
    área (BCE; el dinero del euro es común a sus países); resto, dinero amplio nacional del FMI (MFS, con retraso).
    Descriptivo: en INT-6 el dinero (M2) no anticipó inflación ni bolsa (signo contrario, no establecido)."""
    if iso == "USA":
        s = _serie(con, "M2SL", hoy)
        v, f = _var(s, 12), (s.index[-1] if len(s) else None)
        real = _var(_serie(con, "M2REAL", hoy), 12)
        return {"agregado": "M2 (Fed)", "aa": v, "mes": _mes(f), "real_aa": real}
    if iso in EURO:
        out = {"agregado": "M3 de la zona euro (BCE)", "nota": "dinero común del euro, no del país"}
        for k, sid in (("aa", "ecb_m3_yoy_m"), ("m1_aa", "ecb_m1_yoy_m"), ("prestamos_hogares_aa", "ecb_loans_hh_adj_yoy_m"),
                       ("prestamos_empresas_aa", "ecb_loans_nfc_adj_yoy_m")):
            v, f = _ult(_serie(con, sid, hoy))
            out[k] = v
            if k == "aa":
                out["mes"] = _mes(f)
        return out
    s = _serie(con, f"imf_mfs_{iso.lower()}_broad_money_m", hoy)
    if not len(s):
        return {"agregado": "dinero amplio (FMI)", "aa": None, "mes": "—", "nota": "el FMI no lo publica para este país"}
    f = s.index[-1]
    return {"agregado": "dinero amplio nacional (FMI)", "aa": _var(s, 12), "mes": _mes(f),
            "nota": "con retraso" if (hoy - f).days > DIAS_VIEJO else None}


MESES_CURVA_COMUN = 3   # tipo a 3 meses y bono a 10 años de meses distintos: se usa el último mes común si es reciente


def tipo_3m(con, iso: str, r3: pd.Series, hoy: pd.Timestamp) -> tuple[pd.Series, str | None]:
    """Tipo a 3 meses de la OCDE; en GBR (la OCDE dejó de publicarlo tras 2026-02) con el MISMO empalme declarado del
    termómetro (OIS SONIA 3 m del BoE, `termometro_vivo.empalmar`; docs/int/GBR_3m_sustituto.md). Devuelve (serie,
    texto de la fuente si hay empalme)."""
    from src.report import termometro_vivo as TV   # import tardío (pesado)
    if iso not in TV.SUSTITUTOS_3M:
        return r3, None
    sid, etiqueta = TV.SUSTITUTOS_3M[iso]
    serie, info = TV.empalmar(r3, _serie(con, sid, hoy))
    return (serie, f"OCDE hasta {r3.index.max():%Y-%m}; después {etiqueta}") if info else (r3, None)


def ipc_bls_usa(con, hoy: pd.Timestamp):
    """IPC general a/a de EE. UU. (CPIAUCSL, BLS vía FRED) con el MISMO cálculo que la ficha de «Hoy»
    (`panel_hoy.yoy`: por calendario; un mes suelto ausente, oct-2025, solo se interpola como base)."""
    from src.report.panel_hoy import yoy   # import tardío: panel_hoy importa este módulo
    y = yoy(_serie(con, "CPIAUCSL", hoy))
    return _ult(y)


# ---------------------------------------------------------------- un país
def pais(con, iso: str, hoy: pd.Timestamp, bund: pd.Series) -> dict:
    c = iso.lower()
    pib = _serie(con, f"oecd_gdpq_{c}", hoy)
    a = _var(pib, 12)
    qa = None
    if len(pib) >= 2:
        prev = _en(pib, pib.index[-1] - pd.DateOffset(months=3))
        qa = None if prev is None else 100 * ((float(pib.iloc[-1]) / prev) ** 4 - 1)
    p10 = _en(pib, pib.index[-1] - pd.DateOffset(years=10)) if len(pib) else None
    m10 = None if p10 is None else 100 * ((float(pib.iloc[-1]) / p10) ** (1 / 10) - 1)
    f_pib = pib.index[-1] if len(pib) else None

    ipc = _serie(con, f"oecd_cpi_{c}_yoy", hoy)
    sub = _serie(con, f"oecd_cpicore_{c}_yoy", hoy)
    idx = _serie(con, f"oecd_cpi_{c}_idx", hoy)
    ipc_v, f_ipc = _ult(ipc)
    sub_v, f_sub = _ult(sub)
    hicp_v, f_hicp = _ult(_serie(con, f"ecb_hicp_headline_yoy_{BCE[iso]}_m", hoy)) if iso in BCE else (None, None)
    hsub_v, f_hsub = _ult(_serie(con, f"ecb_hicp_core_yoy_{BCE[iso]}_m", hoy)) if iso in BCE else (None, None)
    if hicp_v is not None and (f_ipc is None or f_hicp > f_ipc):
        gen, f_gen, fuente_gen = hicp_v, f_hicp, "IPCA (BCE)"
    else:
        gen, f_gen, fuente_gen = ipc_v, f_ipc, "IPC (OCDE)"
    if iso == "USA":   # mismo dato que «Hoy» (BLS vía FRED) si es más reciente que el de la OCDE (prueba de uso 17-nov, M1)
        bls_v, f_bls = ipc_bls_usa(con, hoy)
        if bls_v is not None and (f_gen is None or f_bls > f_gen):
            gen, f_gen, fuente_gen = bls_v, f_bls, "IPC (BLS)"
    m12, huecos12 = _media12(idx)

    paro = _serie(con, f"oecd_unemp_{c}", hoy)
    paro_v, f_paro = _ult(paro)
    d_paro, paro_ref = _dif(paro, 12), 12
    if d_paro is None and len(paro):       # p. ej. EE. UU.: oct-2025 no se publicó (cierre del Gobierno)
        d_paro, paro_ref = _dif(paro, 13), 13
    ip = _serie(con, f"oecd_ip_{c}", hoy)
    r3 = _serie(con, f"oecd_ir3m_{c}", hoy)
    r10 = _serie(con, f"oecd_irlt_{c}", hoy)
    r10_v, f_r10 = _ult(r10)
    d3_r10 = _dif(r10, 3)
    bund_mismo = _en(bund, f_r10) if f_r10 is not None else None
    dif = (r10_v - bund_mismo) if (iso in EURO - {"DEU"} and r10_v is not None and bund_mismo is not None) else None
    r3, r3_fuente = tipo_3m(con, iso, r3, hoy)
    r3_mismo = _en(r3, f_r10) if f_r10 is not None else None
    curva = (r10_v - r3_mismo) if (r10_v is not None and r3_mismo is not None) else None
    f_r3 = f_r10 if r3_mismo is not None else None
    if r3_mismo is None and f_r10 is not None:   # JPN: el 3 m de la OCDE va un mes por detrás del 10 años → último mes común
        comun = r3.index.intersection(r10.index)
        comun = comun[(comun <= f_r10) & (comun >= f_r10 - pd.DateOffset(months=MESES_CURVA_COMUN))]
        if len(comun):
            f_r3 = comun.max()
            r3_mismo = float(r3[f_r3])
            curva = float(r10[f_r3]) - r3_mismo
    # r − g aproximado: tipo a 10 años − (PIB real a/a + IPC a/a del último trimestre con PIB)
    ipc_trim = _en(ipc, f_pib + pd.DateOffset(months=2)) if f_pib is not None else None
    nominal = (a + ipc_trim) if (a is not None and ipc_trim is not None) else None
    r_g = (r10_v - nominal) if (r10_v is not None and nominal is not None) else None

    (ad, deuda_obs), (pd_, deuda_proj) = _weo(con, iso, "ggxwdg_ngdp", hoy.year)
    (_, saldo_obs), (_, saldo_proj) = _weo(con, iso, "ggxcnl_ngdp", hoy.year)
    (_, prim_obs), (_, prim_proj) = _weo(con, iso, "ggxonlb_ngdp", hoy.year)
    (_, _), (_, crec_weo) = _weo(con, iso, "ngdp_rpch", hoy.year)
    proy = deuda_proj is not None
    deuda = deuda_proj if proy else deuda_obs
    saldo = saldo_proj if saldo_proj is not None else saldo_obs
    prim = prim_proj if prim_proj is not None else prim_obs
    intereses = (prim - saldo) if (prim is not None and saldo is not None) else None

    prevision = {}
    for año in (hoy.year, hoy.year + 1):
        fila = {}
        for k, ind in (("crecimiento", "ngdp_rpch"), ("inflacion", "pcpipch"), ("paro", "lur"),
                       ("deuda", "ggxwdg_ngdp"), ("saldo", "ggxcnl_ngdp")):
            fila[k] = _weo(con, iso, ind, año)[1][1]
        prevision[str(año)] = fila
    dinero = _dinero(con, iso, hoy)

    bolsa = _serie(con, f"oecd_share_{c}", hoy)
    b_v, f_b = _ult(bolsa)
    caida = None
    if b_v is not None:
        ventana = bolsa[bolsa.index > f_b - pd.DateOffset(months=12)]
        caida = 100 * (b_v / float(ventana.max()) - 1) if len(ventana) >= 11 else None
    hpi = _serie(con, f"oecd_hpi_{c}_q", hoy)
    cli = _serie(con, f"oecd_cli_{c}", hoy)
    cli_v, f_cli = _ult(cli)
    d3_cli = _dif(cli, 3)

    col = {"crecimiento": _color_crec(a, m10), "inflacion": _color_infl(gen), "empleo": _color_paro(d_paro),
           "bonos": _color_bonos(iso, dif, d3_r10), "fiscal": _color_fiscal(deuda, saldo),
           "bolsa": _color_bolsa(caida), "confianza": _color_cli(cli_v, d3_cli)}

    # cifra corta de cada celda (lo que se ve en la tabla) y su fecha
    flecha = lambda d: "" if d is None else (" ↑" if d > 0.05 else (" ↓" if d < -0.05 else " ="))  # noqa: E731
    corto = {
        "crecimiento": (_fmt(a, signo=True), _trim(f_pib)),
        "inflacion": (_fmt(gen), _mes(f_gen)),
        "empleo": (_fmt(paro_v) + ("" if d_paro is None else f" ({_fmt(d_paro, 1, '', True)})"), _mes(f_paro)),
        "bonos": (_fmt(r10_v, 2) + (f" ({_fmt(dif, 2, '', True)})" if dif is not None else
                                    (f" ({_fmt(d3_r10, 2, '', True)})" if d3_r10 is not None else "")), _mes(f_r10)),
        "fiscal": ((_fmt(deuda, 0) + " · " + _fmt(saldo, 1, "", True)) if deuda is not None else "s/d",
                   f"{pd_ if proy else ad}{' prev. FMI' if proy else ''}"),
        "bolsa": (_fmt(caida, signo=True) if caida is not None else "s/d", _mes(f_b)),
        "confianza": ((_fmt(cli_v, 1, "") + flecha(d3_cli)) if cli_v is not None else "s/d", _mes(f_cli)),
    }

    partes = [f"Crecimiento {col['crecimiento'][1]}: PIB {_fmt(a, signo=True)} frente a hace un año "
              f"({_trim(f_pib)}; media de 10 años {_fmt(m10)} al año)",
              f"inflación {col['inflacion'][1]}: {_fmt(gen)} ({fuente_gen}, {_mes(f_gen)})",
              f"paro {_fmt(paro_v)} ({col['empleo'][1]}: {_fmt(d_paro, 1, ' pp', True)} en {paro_ref} meses"
              + (", el mes de hace 12 no se publicó" if paro_ref == 13 else "") + ")"]
    if deuda is not None:
        partes.append(f"deuda pública {_fmt(deuda, 0)} del PIB y saldo {_fmt(saldo, 1, ' %', True)} "
                      f"({'previsión FMI ' if proy else ''}{pd_ if proy else ad})")
    if dif is not None:
        partes.append(f"bono a 10 años {_fmt(r10_v, 2)}, {_fmt(dif, 2, ' pp', True)} sobre Alemania ({_mes(f_r10)})")
    elif r10_v is not None:
        partes.append(f"bono a 10 años {_fmt(r10_v, 2)} ({_fmt(d3_r10, 2, ' pp', True)} en 3 meses, {_mes(f_r10)})")
    frase = "; ".join(partes) + "."
    if r_g is not None and r_g > 0 and deuda is not None and deuda > 60:
        frase += (f" El tipo a 10 años supera al crecimiento nominal (r − g ≈ {_fmt(r_g, 1, ' pp', True)}): "
                  + ("la deuda/PIB tiende a subir, y además hay déficit primario." if prim is not None and prim < 0
                     else "la deuda/PIB tiende a subir salvo con superávit primario suficiente."))

    fechas = {"PIB": (f_pib, DIAS_VIEJO_TRIM), "inflación": (f_gen, DIAS_VIEJO), "paro": (f_paro, DIAS_VIEJO),
              "10 años": (f_r10, DIAS_VIEJO), "bolsa": (f_b, DIAS_VIEJO), "CLI": (f_cli, DIAS_VIEJO)}
    viejos = [k for k, (f, lim) in fechas.items() if f is not None and (hoy - pd.Timestamp(f)).days > lim]
    pct_ipc = _pct_hist(ipc, ipc_v)
    pct_paro = _pct_hist(paro, paro_v)
    pct_10 = _pct_hist(r10, r10_v)
    return {
        "pais": iso, "nombre": NOMBRE[iso], "euro": iso in EURO, "frase": frase, "nota": NOTAS.get(iso),
        "colores": {k: {"color": v[0], "texto": v[1], "cifra": corto[k][0], "fecha": corto[k][1]}
                    for k, v in col.items()},
        "datos_antiguos": viejos,
        "crecimiento": {"pib_aa": a, "pib_trim_anualizado": qa, "media_10a": m10, "trimestre": _trim(f_pib),
                        "ip_aa": _var(ip, 12), "ip_mes": _mes(ip.index[-1] if len(ip) else None),
                        "weo_crec_año": crec_weo},
        "inflacion": {"general": gen, "general_fuente": fuente_gen, "general_mes": _mes(f_gen),
                      "ipc_aa": ipc_v, "mes": _mes(f_ipc), "hicp_aa": hicp_v, "mes_hicp": _mes(f_hicp),
                      "ipc_media_12m": m12, "huecos_media_12m": huecos12, "mes_media_12m": _mes(idx.index[-1] if len(idx) else None),
                      "subyacente_aa": sub_v, "mes_sub": _mes(f_sub), "hicp_sub_aa": hsub_v, "mes_hicp_sub": _mes(f_hsub),
                      "pct_ipc": pct_ipc[0], "pct_ipc_desde": pct_ipc[1]},
        "empleo": {"paro": paro_v, "mes": _mes(f_paro), "delta_12m": d_paro, "delta_meses": paro_ref, "pct_paro": pct_paro[0],
                   "pct_paro_desde": pct_paro[1]},
        "tipos": {"corto_3m": r3_mismo, "mes_corto": _mes(f_r3), "fuente_corto": r3_fuente,
                  "largo_10a": r10_v, "mes": _mes(f_r10), "delta_3m_10a": d3_r10,
                  "dif_alemania": dif, "curva_10a_3m": curva, "r_menos_g": r_g, "pct_10a": pct_10[0],
                  "pct_10a_desde": pct_10[1]},
        "fiscal": {"deuda_pib": deuda, "saldo_pib": saldo, "saldo_primario_pib": prim, "intereses_pib": intereses,
                   "año": pd_ if proy else ad, "proyeccion": proy, "deuda_obs": deuda_obs, "año_obs": ad,
                   "saldo_obs": saldo_obs},
        "bolsa": {"aa": _var(bolsa, 12), "caida_max_12m": caida, "mes": _mes(f_b)},
        "prevision_fmi": prevision, "dinero": dinero,
        "vivienda": {"precio_aa": _var(hpi, 12), "trimestre": _trim(hpi.index[-1] if len(hpi) else None)},
        "confianza": {"cli": cli_v, "delta_3m_cli": d3_cli, "mes": _mes(f_cli),
                      "empresas": _ult(_serie(con, f"oecd_bci_{c}", hoy))[0],
                      "consumidores": _ult(_serie(con, f"oecd_cci_{c}", hoy))[0]},
    }


def _redondear(x):
    """Quita el ruido de coma flotante (−0,3000000000000007 → −0,3); 4 decimales bastan para todo lo que se enseña."""
    if isinstance(x, dict):
        return {k: _redondear(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_redondear(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), 4)
    return x


def pulso(con, hoy: date) -> dict:
    t = pd.Timestamp(hoy)
    bund = _serie(con, "oecd_irlt_deu", t)
    out = {}
    for iso in PAISES:
        try:
            out[iso] = pais(con, iso, t, bund)
        except Exception as e:  # noqa: BLE001 — un país sin datos no tumba la sección
            out[iso] = {"pais": iso, "nombre": NOMBRE[iso], "error": f"{type(e).__name__}: {e}"}
    out = _redondear(out)
    return {"fecha": str(hoy), "reglas": REGLAS, "paises": out,
            "aviso": "Descriptivo, con reglas fijas y umbrales redondos; no validado ni usado por ningún modelo."}
