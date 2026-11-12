"""Pulso por país (DESCRIPTIVO, no validado): cómo está HOY cada uno de los 18 países del panel internacional en
crecimiento, inflación, empleo, tipos y bonos, cuentas públicas, bolsa, vivienda y confianza.

Para qué: el motor de escenarios (INT-11) clasifica el régimen con dos ejes congelados con datos ≤ 2004 (inflación
> 3 % y PIB per cápita frente a la media de sus 10 años anteriores). Ese eje de crecimiento solo baja de 0 con caídas
fuertes del PIB, así que un país estancado (p. ej. Francia, nov-2026: PIB −0,1 % a/a) sigue en «expansión». Esta
sección enseña lo que el régimen no mira (ritmo actual, bonos, deuda, déficit) para leerlo bien. NO cambia el motor,
ni sus probabilidades, ni ninguna señal: son lecturas con reglas fijas y umbrales redondos escritos aquí, sin ajustar
a datos ni historial de aciertos.

Fuentes (warehouse, `obs_latest`): OCDE (PIB trimestral, IPC, subyacente, paro, IP, tipos 3 m y 10 años, bolsa,
vivienda, CLI, confianza empresarial y del consumidor) e IMF WEO (deuda bruta, saldo, saldo primario, crecimiento;
último año observado y proyección del año en curso de la última edición del WEO).
Uso: src/report/weekly.py lo guarda en el signal (`pulso_paises`); lo pinta src/report/panel.py.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

PAISES = ["USA", "DEU", "FRA", "ITA", "ESP", "GBR", "JPN", "NLD", "BEL", "PRT", "IRL", "FIN", "SWE", "DNK", "NOR",
          "CHE", "CAN", "AUS"]
EURO = {"DEU", "FRA", "ITA", "ESP", "NLD", "BEL", "PRT", "IRL", "FIN"}
NOMBRE = {"BEL": "Bélgica", "DEU": "Alemania", "DNK": "Dinamarca", "ESP": "España", "FIN": "Finlandia",
          "FRA": "Francia", "GBR": "Reino Unido", "ITA": "Italia", "JPN": "Japón", "NLD": "Países Bajos",
          "NOR": "Noruega", "PRT": "Portugal", "SWE": "Suecia", "USA": "EE. UU.", "AUS": "Australia", "CHE": "Suiza",
          "CAN": "Canadá", "IRL": "Irlanda"}
DIAS_VIEJO = 200        # dato mensual con más de ≈ 6,5 meses → se marca «antiguo»
DIAS_VIEJO_TRIM = 290   # PIB: fecha = inicio del trimestre; T2 publicado en agosto sigue siendo el último en noviembre

# Reglas de lectura (fijas, redondas, NO validadas). Colores: verde / ámbar / rojo / gris (sin dato).
REGLAS = {
    "crecimiento": "PIB real a/a: < 0 % contracción (rojo); < 0,5 % o < mitad de su media de 10 años estancado (ámbar); "
                   "si no, normal o fuerte (verde; fuerte si supera su media de 10 años en ≥ 1 pp).",
    "inflacion": "IPC a/a: < 1 % muy baja (ámbar); 1-3 % en zona normal (verde); 3-5 % alta (ámbar); > 5 % muy alta (rojo).",
    "empleo": "Paro frente a hace 12 meses: sube ≥ 0,5 pp (rojo); sube 0,2-0,5 pp (ámbar); si no (verde).",
    "bonos": "Tipo a 10 años: diferencial frente a Alemania (euro) > 1,5 pp (rojo), > 0,8 pp (ámbar); fuera del euro, "
             "subida ≥ 0,5 pp en 3 meses (ámbar). r − g = tipo 10a − crecimiento nominal (≈ PIB real + IPC): > 0 la "
             "deuda tiende a subir sola.",
    "fiscal": "Deuda pública bruta/PIB y saldo público (WEO): deuda > 100 % o déficit < −4 % (ámbar); ambos (rojo); "
              "deuda > 60 % con déficit < −3 % (ámbar).",
    "bolsa": "Índice de precios OCDE: caída ≥ 20 % frente a su máximo de 12 meses (rojo), ≥ 10 % (ámbar).",
    "confianza": "CLI OCDE (100 = tendencia): < 100 y bajando (ámbar); ≥ 100 o subiendo (verde).",
}


def _serie(con, sid: str, hoy: pd.Timestamp) -> pd.Series:
    d = con.execute("select date, value from obs_latest where series_id = ? and date <= ? order by date",
                    [sid, hoy]).fetchdf()
    if d.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    return pd.Series(d["value"].astype(float).values, index=pd.DatetimeIndex(d["date"])).dropna()


def _ult(s: pd.Series):
    return (float(s.iloc[-1]), str(s.index[-1].date())) if len(s) else (None, None)


def _pct_hist(s: pd.Series, v) -> int | None:
    """Percentil (0-100) del valor de hoy frente a toda la historia disponible de la serie (descriptivo)."""
    if v is None or len(s) < 24:
        return None
    return int(round(100 * float((s < v).mean())))


def _yoy(s: pd.Series, periodos: int):
    if len(s) <= periodos:
        return None
    return 100 * (s.iloc[-1] / s.iloc[-1 - periodos] - 1)


def _weo(con, iso: str, ind: str, hoy: pd.Timestamp):
    """(último año observado, valor) y (año en curso proyectado, valor) del WEO; None si falta. Las proyecciones
    (pit_role forecast) no están en obs_latest: se leen de obs_all_latest."""
    h = _serie(con, f"imf_weo_{iso.lower()}_{ind}", pd.Timestamp("2100-01-01"))
    d = con.execute("select date, value from obs_all_latest where series_id = ? order by date",
                    [f"imf_weo_{iso.lower()}_{ind}_proj"]).fetchdf()
    p = pd.Series(d["value"].astype(float).values, index=pd.DatetimeIndex(d["date"])) if len(d) else \
        pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    obs = (int(h.index[-1].year), float(h.iloc[-1])) if len(h) else (None, None)
    pr = p[p.index.year == hoy.year]
    proj = (hoy.year, float(pr.iloc[-1])) if len(pr) else (None, None)
    return obs, proj


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
        return "verde", "en zona normal"
    if v <= 5:
        return "ambar", "alta"
    return "rojo", "muy alta"


def _color_paro(d):
    if d is None:
        return "gris", "sin dato"
    if d >= 0.5:
        return "rojo", "el paro sube con fuerza"
    if d >= 0.2:
        return "ambar", "el paro sube"
    if d <= -0.2:
        return "verde", "el paro baja"
    return "verde", "el paro estable"


def _color_bonos(iso, dif, d3):
    if iso in EURO and iso != "DEU" and dif is not None:
        if dif > 1.5:
            return "rojo", "el mercado pide una prima alta frente a Alemania"
        if dif > 0.8:
            return "ambar", "el mercado pide prima frente a Alemania"
        return "verde", "prima pequeña frente a Alemania"
    if d3 is None:
        return "gris", "sin dato"
    if d3 >= 0.5:
        return "ambar", "el tipo a 10 años sube rápido"
    return "verde", "sin tensión visible"


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
    return "verde", "cuentas sin tensión"


def _color_bolsa(caida):
    if caida is None:
        return "gris", "sin dato"
    if caida <= -20:
        return "rojo", "en mercado bajista"
    if caida <= -10:
        return "ambar", "en corrección"
    return "verde", "sin caída relevante"


def _color_cli(v, d3):
    if v is None:
        return "gris", "sin dato"
    if v < 100 and d3 is not None and d3 < 0:
        return "ambar", "por debajo de tendencia y bajando"
    if v < 100:
        return "verde", "por debajo de tendencia pero mejorando"
    return "verde", "por encima de tendencia"


def _fmt(v, dec=1, suf=" %", signo=False):
    if v is None:
        return "s/d"
    s = f"{v:+.{dec}f}" if signo else f"{v:.{dec}f}"
    return s.replace(".", ",").replace("-", "−") + suf


def pais(con, iso: str, hoy: pd.Timestamp, bund: pd.Series) -> dict:
    c = iso.lower()
    pib = _serie(con, f"oecd_gdpq_{c}", hoy)
    a = _yoy(pib, 4)
    qa = 100 * ((pib.iloc[-1] / pib.iloc[-2]) ** 4 - 1) if len(pib) > 2 else None
    m10 = 100 * ((pib.iloc[-1] / pib.iloc[-41]) ** (1 / 10) - 1) if len(pib) > 41 else None
    ipc = _serie(con, f"oecd_cpi_{c}_yoy", hoy)
    sub = _serie(con, f"oecd_cpicore_{c}_yoy", hoy)
    paro = _serie(con, f"oecd_unemp_{c}", hoy)
    ip = _serie(con, f"oecd_ip_{c}", hoy)
    r3 = _serie(con, f"oecd_ir3m_{c}", hoy)
    r10 = _serie(con, f"oecd_irlt_{c}", hoy)
    bolsa = _serie(con, f"oecd_share_{c}", hoy)
    hpi = _serie(con, f"oecd_hpi_{c}_q", hoy)
    cli = _serie(con, f"oecd_cli_{c}", hoy)
    bci = _serie(con, f"oecd_bci_{c}", hoy)
    cci = _serie(con, f"oecd_cci_{c}", hoy)
    (ad, deuda_obs), (pd_, deuda_proj) = _weo(con, iso, "ggxwdg_ngdp", hoy)
    (asl, saldo_obs), (ps, saldo_proj) = _weo(con, iso, "ggxcnl_ngdp", hoy)
    (_, prim_obs), (_, prim_proj) = _weo(con, iso, "ggxonlb_ngdp", hoy)
    (_, crec_weo) = _weo(con, iso, "ngdp_rpch", hoy)[1]

    ipc_v, ipc_f = _ult(ipc)
    idx = _serie(con, f"oecd_cpi_{c}_idx", hoy)
    ipc_12m = (100 * (idx.iloc[-12:].mean() / idx.iloc[-24:-12].mean() - 1)) if len(idx) >= 24 else None
    sub_v, sub_f = _ult(sub)
    paro_v, paro_f = _ult(paro)
    d_paro = (paro_v - float(paro.iloc[-13])) if len(paro) > 13 else None
    r10_v, r10_f = _ult(r10)
    r3_v, _ = _ult(r3)
    d3_r10 = (r10_v - float(r10.iloc[-4])) if len(r10) > 4 else None
    dif = (r10_v - float(bund.iloc[-1])) if (r10_v is not None and len(bund) and iso in EURO - {"DEU"}) else None
    curva = (r10_v - r3_v) if (r10_v is not None and r3_v is not None) else None
    nominal = (a + ipc_v) if (a is not None and ipc_v is not None) else None
    r_g = (r10_v - nominal) if (r10_v is not None and nominal is not None) else None
    deuda = deuda_proj if deuda_proj is not None else deuda_obs
    saldo = saldo_proj if saldo_proj is not None else saldo_obs
    prim = prim_proj if prim_proj is not None else prim_obs
    intereses = (prim - saldo) if (prim is not None and saldo is not None) else None
    b_v, b_f = _ult(bolsa)
    caida = (100 * (b_v / float(bolsa.iloc[-13:].max()) - 1)) if len(bolsa) > 13 else None
    b12 = _yoy(bolsa, 12)
    cli_v, cli_f = _ult(cli)
    d3_cli = (cli_v - float(cli.iloc[-4])) if len(cli) > 4 else None

    col = {"crecimiento": _color_crec(a, m10), "inflacion": _color_infl(ipc_v), "empleo": _color_paro(d_paro),
           "bonos": _color_bonos(iso, dif, d3_r10), "fiscal": _color_fiscal(deuda, saldo),
           "bolsa": _color_bolsa(caida), "confianza": _color_cli(cli_v, d3_cli)}

    # Frase en lenguaje llano, con reglas fijas
    partes = [f"Crecimiento {col['crecimiento'][1]} (PIB {_fmt(a, signo=True)} a/a; media de 10 años "
              f"{_fmt(m10)} al año)",
              f"inflación {col['inflacion'][1]} ({_fmt(ipc_v)} a/a; media de 12 meses {_fmt(ipc_12m)})",
              f"{col['empleo'][1]} ({_fmt(paro_v)}, {_fmt(d_paro, suf=' pp', signo=True)} en 12 meses)"]
    if deuda is not None:
        partes.append(f"deuda pública {_fmt(deuda, 0)} del PIB y saldo {_fmt(saldo, signo=True)}")
    if dif is not None:
        partes.append(f"su bono a 10 años paga {_fmt(r10_v, 2)}, {_fmt(dif, 2, ' pp', True)} frente a Alemania")
    elif r10_v is not None:
        partes.append(f"su bono a 10 años paga {_fmt(r10_v, 2)}")
    frase = "; ".join(partes) + "."
    if r_g is not None and r_g > 0 and deuda is not None and deuda > 60:
        frase += (f" Con el tipo a 10 años por encima del crecimiento nominal (r − g {_fmt(r_g, 1, ' pp', True)}), "
                  + ("la deuda tiende a subir, y además hay déficit primario." if prim is not None and prim < 0
                     else "la deuda tiende a subir salvo que haya superávit primario suficiente."))

    viejos = [n for n, f in (("PIB", str(pib.index[-1].date()) if len(pib) else None), ("IPC", ipc_f),
                             ("paro", paro_f), ("10 años", r10_f), ("bolsa", b_f), ("CLI", cli_f))
              if f and (hoy - pd.Timestamp(f)).days > (DIAS_VIEJO_TRIM if n == "PIB" else DIAS_VIEJO)]
    return {
        "pais": iso, "nombre": NOMBRE[iso], "euro": iso in EURO, "frase": frase,
        "colores": {k: {"color": v[0], "texto": v[1]} for k, v in col.items()},
        "datos_antiguos": viejos,
        "crecimiento": {"pib_aa": a, "pib_trim_anualizado": qa, "media_10a": m10,
                        "trimestre": str(pib.index[-1].date()) if len(pib) else None,
                        "ip_aa": _yoy(ip, 12), "ip_mes": str(ip.index[-1].date()) if len(ip) else None,
                        "weo_crec_año": crec_weo,
                        "pct_pib_aa": _pct_hist(100 * (pib / pib.shift(4) - 1).dropna(), a)},
        "inflacion": {"ipc_aa": ipc_v, "mes": ipc_f, "ipc_media_12m": ipc_12m, "subyacente_aa": sub_v, "mes_sub": sub_f,
                      "pct_ipc": _pct_hist(ipc, ipc_v)},
        "empleo": {"paro": paro_v, "mes": paro_f, "delta_12m": d_paro, "pct_paro": _pct_hist(paro, paro_v)},
        "tipos": {"corto_3m": r3_v, "largo_10a": r10_v, "mes": r10_f, "delta_3m_10a": d3_r10,
                  "dif_alemania": dif, "curva_10a_3m": curva, "r_menos_g": r_g,
                  "pct_10a": _pct_hist(r10, r10_v)},
        "fiscal": {"deuda_pib": deuda, "saldo_pib": saldo, "saldo_primario_pib": prim, "intereses_pib": intereses,
                   "año": pd_ if deuda_proj is not None else ad, "proyeccion": deuda_proj is not None,
                   "deuda_obs": deuda_obs, "año_obs": ad, "saldo_obs": saldo_obs},
        "bolsa": {"aa": b12, "caida_max_12m": caida, "mes": b_f},
        "vivienda": {"precio_aa": _yoy(hpi, 4), "trimestre": str(hpi.index[-1].date()) if len(hpi) else None},
        "confianza": {"cli": cli_v, "delta_3m_cli": d3_cli, "mes": cli_f, "empresas": _ult(bci)[0],
                      "consumidores": _ult(cci)[0]},
    }


def pulso(con, hoy: date) -> dict:
    t = pd.Timestamp(hoy)
    bund = _serie(con, "oecd_irlt_deu", t)
    out = {}
    for iso in PAISES:
        try:
            out[iso] = pais(con, iso, t, bund)
        except Exception as e:  # noqa: BLE001 — un país sin datos no tumba la sección
            out[iso] = {"pais": iso, "nombre": NOMBRE[iso], "error": f"{type(e).__name__}: {e}"}
    return {"fecha": str(hoy), "reglas": REGLAS, "paises": out,
            "aviso": "Descriptivo, con reglas fijas y umbrales redondos; no validado ni usado por ningún modelo."}
