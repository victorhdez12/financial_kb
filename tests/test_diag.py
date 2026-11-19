"""Diagnósticos automáticos (src/diag/, docs/panel/diagnosticos_v0.md) con datos SINTÉTICOS, SIN red y SIN lanzar
`claude -p` de verdad (se sustituye por un falso que escribe una nota)."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from src.diag import contexto as C
from src.diag import disparadores as D
from src.diag import explicador as E
from src.diag import noticias as N
from src.diag import tarjeta as T

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_DATA_ROOT", str(tmp_path / "archivo"))
    monkeypatch.setenv("FIN_DIAG_NOTAS", str(tmp_path / "notas"))
    monkeypatch.setenv("FIN_DIAG_ACIERTOS", str(tmp_path / "aciertos.jsonl"))
    monkeypatch.setenv("FIN_DIAG_CLAUDE_BIN", "/no/existe/claude")   # por si algo intentara lanzarlo


def _paseo(n=400, fin="2026-11-18", sigma=0.01, seed=0, nivel=100.0):
    rng = np.random.default_rng(seed)
    ix = pd.bdate_range(end=fin, periods=n)
    return pd.Series(nivel * np.exp(np.cumsum(rng.normal(0, sigma, n))), index=ix)


def _salto(s, k_dias_antes, ret):
    s = s.copy()
    i = len(s) - 1 - k_dias_antes
    s.iloc[i:] = s.iloc[i:] * (1 + ret)
    return s


def _X(fin="2026-11-18", **cambios):
    precios = pd.DataFrame({t: _paseo(seed=i, fin=fin) for i, t in enumerate(["SPY", "QQQ", "VGK", "GLD", "CL=F", "TLT", "XLK", "XLE"])})
    for t, s in cambios.items():
        precios[t] = s
    dgs = pd.Series(4 + np.cumsum(np.random.default_rng(9).normal(0, 0.05, 400)), index=precios.index)
    eur = _paseo(seed=11, sigma=0.004, nivel=1.1, fin=fin)
    return {"precios": precios, "wh": {"DGS10": dgs, "ecb_eurusd_d": eur}, "errores": {}}


# ============================================================================================ disparadores
def test_extremo_3_sigma_y_no_por_debajo():
    X = _X(SPY=_salto(_paseo(seed=0), 0, -0.05), QQQ=_salto(_paseo(seed=1), 0, -0.02))
    S = D.series_referencia(X)
    M = {c: D.movimiento(S[c]) for c in ("sp500", "nasdaq")}
    ds = [d for d in D.disparos_movimiento(M) if d["fecha"] == S["sp500"].index[-1]]
    assert [d["clave"] for d in ds if d["tipo"] == "extremo"] == ["sp500"]   # −5 % con σ 1 % sí; −2 % no
    assert ds[0]["k"] < -3


def test_sigma_es_de_las_63_sesiones_anteriores_sin_el_dia():
    s = _salto(_paseo(seed=3), 0, 0.10)
    m = D.movimiento(s)
    previa = np.log(s).diff().iloc[-64:-1].std()
    assert m["sigma"].iloc[-1] == pytest.approx(previa)


def test_conjunto_25_sigma_en_3_activos():
    X = _X(SPY=_salto(_paseo(seed=0), 0, -0.04), QQQ=_salto(_paseo(seed=1), 0, -0.04),
           GLD=_salto(_paseo(seed=3), 0, 0.04))
    S = D.series_referencia(X)
    M = {c: D.movimiento(S[c], m) for c, _, _, _, m, _ in D.REFERENCIA if c in S}
    conj = [d for d in D.disparos_movimiento(M) if d["tipo"] == "conjunto" and d["fecha"] == S["sp500"].index[-1]]
    assert len(conj) == 1 and set(conj[0]["activos"]) >= {"sp500", "nasdaq", "oro"}


def test_tendencia_confirma_3_sesiones_y_cruces_de_un_dia_no():
    ix = pd.bdate_range(end="2026-11-18", periods=260)
    base = np.linspace(110, 100, 260)   # bajando: siempre por debajo de su media
    s = pd.Series(base, index=ix)
    s.iloc[-10] = 120          # cruce de un día: no
    s.iloc[-3:] = 130          # tres sesiones por encima: salta el 3.º día
    ds = D.disparos_tendencia({"sp500": s})
    assert [d["fecha"] for d in ds] == [ix[-1]]
    assert ds[0]["dir"] == 1


def test_cambios_regimen():
    a = {"cuadrante": "Goldilocks", "credito": "verde", "liquidez": "neutral", "deuda": "techo"}
    assert D.cambios_regimen(None, a) == []
    assert D.cambios_regimen(a, a) == []
    b = {**a, "cuadrante": "Estanflación", "credito": "rojo", "liquidez": "escasa", "deuda": "desapalancamiento"}
    assert len(D.cambios_regimen(a, b)) == 4
    assert D.cambios_regimen(b, {**b, "credito": "ámbar"}) == []   # salir de rojo no dispara


def test_regimen_historico_fechado_tras_el_mes():
    reg = pd.DataFrame({"date": pd.to_datetime(["2026-09-30", "2026-10-31"]), "quadrant": ["A", "B"],
                        "credit_light": ["verde"] * 2, "liquidity": ["neutral"] * 2, "debt_phase": ["x"] * 2})
    ds = D.disparos_regimen_historico(reg)
    assert len(ds) == 1 and ds[0]["fecha"] == pd.Timestamp("2026-11-02")


def _vintages_payems(sorpresa: float):
    """Nóminas con +100 mil/mes; cada mes una publicación nueva (sin revisiones); la última, con sorpresa."""
    filas = []
    meses = pd.date_range("2010-01-01", "2026-10-01", freq="MS")
    nivel = 130000.0
    for i, m in enumerate(meses):
        nivel += 100 + np.random.default_rng(i).normal(0, 20) + (sorpresa if i == len(meses) - 1 else 0)
        filas.append({"series_id": "PAYEMS", "date": m, "value": nivel, "realtime_start": m + pd.DateOffset(months=1, days=4),
                      "realtime_end": None})
    return pd.DataFrame(filas)


def test_macro_sorpresa_frente_a_tendencia_6_meses():
    sor = D.sorpresas_macro(_vintages_payems(400))
    ult = sor.iloc[-1]
    assert ult["periodo"] == pd.Timestamp("2026-10-01")
    assert ult["k"] > 2 and abs(ult["prevision"] - 100) < 30
    ds = D.disparos_macro(sor)
    assert ds[-1]["fecha"] == pd.Timestamp("2026-11-05") and "sin consenso" in ds[-1]["texto"]
    assert not [d for d in D.disparos_macro(D.sorpresas_macro(_vintages_payems(0))) if d["fecha"] == pd.Timestamp("2026-11-05")]


def test_macro_usa_el_dato_tal_como_se_conocia():
    """Una revisión posterior no cambia el error de la publicación original (punto en el tiempo)."""
    v = _vintages_payems(400)
    rev = v.iloc[[-1]].copy()
    v.loc[v.index[-1], "realtime_end"] = pd.Timestamp("2026-12-03")
    rev["value"] -= 400
    rev["realtime_start"] = pd.Timestamp("2026-12-04")
    a = D.sorpresas_macro(v)
    b = D.sorpresas_macro(pd.concat([v, rev]))
    assert a.iloc[-1]["k"] == pytest.approx(b[b["periodo"] == pd.Timestamp("2026-10-01")].iloc[0]["k"])


def test_flujos_solo_con_precio_2_sigma():
    p = pd.DataFrame({"UNH": _salto(_paseo(seed=5), 0, -0.08), "MSFT": _paseo(seed=6)})
    f = p.index[-1]
    ev = [{"fecha": f, "ticker": "UNH", "tipo": "volumen", "fuerza": 2},
          {"fecha": f, "ticker": "MSFT", "tipo": "volumen", "fuerza": 2},
          {"fecha": f, "ticker": "UNH", "tipo": "form4", "fuerza": 1}]
    ds = D.disparos_flujos(ev, p)
    assert [d["ticker"] for d in ds] == ["UNH"]


def test_agrupar_enfriamiento_y_tope():
    f0 = pd.Timestamp("2026-11-02")
    ds = [{"fecha": f0, "tipo": "extremo", "clave": "oro", "tamano": 3.5, "texto": "a"},
          {"fecha": f0, "tipo": "tendencia", "clave": "oro", "tamano": 3.0, "texto": "b"},
          {"fecha": f0 + pd.offsets.BDay(3), "tipo": "extremo", "clave": "oro", "tamano": 3.2, "texto": "c"},
          {"fecha": f0 + pd.offsets.BDay(3), "tipo": "extremo", "clave": "sp500", "tamano": 4.0, "texto": "d"},
          {"fecha": f0 + pd.offsets.BDay(1), "tipo": "macro", "clave": "PAYEMS", "tamano": 2.1, "texto": "e"},
          {"fecha": f0 + pd.offsets.BDay(2), "tipo": "macro", "clave": "UNRATE", "tamano": 2.5, "texto": "f"},
          {"fecha": f0 + pd.offsets.BDay(8), "tipo": "extremo", "clave": "oro", "tamano": 3.1, "texto": "g"}]
    ev = D.agrupar(ds)
    assert len(ev) == 5   # un evento por día
    d3 = ev[3]
    assert {d["clave"]: d["repetido"] for d in d3["disparos"]} == {"oro": True, "sp500": False}
    assert ev[-1]["disparos"][0]["repetido"] is False   # pasadas 5 sesiones vuelve a abrir nota
    tope = D.aplicar_tope(ev)
    sem = [e for e in tope if e["fecha"].isocalendar()[1] == f0.isocalendar()[1]]
    assert len(sem) == 4 and sum(e["nota"] for e in sem) == 3
    assert [e["nota"] for e in sem] == [True, False, True, True]   # se cae el de menor tamaño (2,1)


def test_detectar_vistos_y_dato_tardio():
    X = _X(SPY=_salto(_paseo(seed=0), 0, -0.06))
    hoy = X["precios"].index[-1] + pd.offsets.BDay(1)
    ev, est = D.detectar(X, hoy.date(), {}, [])
    assert any(d["clave"] == "sp500" for e in ev for d in e["disparos"])
    ev2, est2 = D.detectar(X, hoy.date(), est, [])
    assert ev2 == []            # ya visto: no se repite
    # al día siguiente llega el Tesoro 10 a de AYER con un salto: el mismo día gana un disparador nuevo
    X["wh"]["DGS10"] = X["wh"]["DGS10"].copy()
    X["wh"]["DGS10"].iloc[-1] += 1.0
    ev3, _ = D.detectar(X, hoy.date(), est2, [])
    assert any(d["clave"] == "tesoro10" and not d["visto"] for e in ev3 for d in e["disparos"])


def test_sustitutos_declarados_y_bitcoin_omitido():
    nombres = {c: n for c, _, _, _, _, n in D.REFERENCIA}
    assert "VGK" in nombres["eurostoxx"] and "SUSTITUTO" in nombres["dolar"]
    assert "bitcoin" in D.OMITIDOS and "bitcoin" not in nombres


def test_umbrales_aprobados_sin_cambios():
    U = D.UMBRALES
    assert (U["k_solo"], U["k_conjunto"], U["n_conjunto"], U["ma"], U["ma_confirma"], U["macro_k"], U["flujo_k"],
            U["sigma_ventana"], U["enfriamiento"], U["tope_semana"]) == (3.0, 2.5, 3, 200, 3, 2.0, 2.0, 63, 5, 3)


# ============================================================================================ contexto
def test_contexto_paquete_sin_red(tmp_path):
    X = _X(SPY=_salto(_paseo(seed=0), 0, -0.05))
    f = X["precios"].index[-1]
    P = C.construir(f, None, X, None, None, tmp_path / "pq", {})
    assert P["evento"]["forzado"] and P["movimientos"][0]["clave"] == "sp500"
    s = X["precios"]["SPY"]
    assert P["movimientos"][0]["cambio_20s"] == pytest.approx(100 * (s.iloc[-1] / s.iloc[-21] - 1), abs=0.01)
    dol = next(m for m in P["movimientos"] if m["clave"] == "dolar")
    e = X["wh"]["ecb_eurusd_d"]
    assert dol["cambio_5s"] == pytest.approx(100 * (e.iloc[-6] / e.iloc[-1] - 1), abs=0.01)   # dólar = 1 / EUR-USD
    assert P["amplitud"]["sectores_eeuu"] == 2
    assert {"oro – bolsa", "bolsa – bonos largos"} <= {c["par"] for c in P["correlaciones"]}
    assert "sp500" in P["series_seguimiento"] and "SPY" not in P["series_seguimiento"]
    assert (tmp_path / "pq" / "paquete.json").exists()
    assert "n" in P["episodios"]


# ============================================================================================ noticias
GDELT_OK = json.dumps({"articles": [
    {"url": "https://ejemplo.com/a", "title": "Gold slides as dollar firms", "seendate": "20261118T101500Z",
     "domain": "ejemplo.com", "sourcecountry": "US"},
    {"url": "https://ejemplo.com/a", "title": "duplicado", "seendate": "x"}]}).encode()
RSS2 = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Minutes of the FOMC</title><link>https://www.federalreserve.gov/x.htm</link>
<pubDate>Wed, 18 Nov 2026 19:00:00 GMT</pubDate></item>
<item><title>Viejo</title><link>https://www.federalreserve.gov/viejo.htm</link><pubDate>Mon, 02 Nov 2026 19:00:00 GMT</pubDate></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>ECB press release</title>
<link href="https://www.ecb.europa.eu/p.html"/><updated>2026-11-18T13:00:00Z</updated></entry></feed>"""


def test_noticias_transporte_simulado():
    pedidas = []

    def tr(url):
        pedidas.append(url)
        if "gdeltproject" in url:
            return 200, GDELT_OK
        if "federalreserve" in url:
            return 200, RSS2
        if "ecb.europa" in url:
            return 200, ATOM
        return 503, b""
    ev = {"disparos": [{"clave": "oro"}]}
    r = N.recoger("2026-11-18", ev, [], transporte=tr, espera=0)
    assert [a["url"] for a in r["gdelt"]] == ["https://ejemplo.com/a"]   # deduplicado
    assert {o["fuente"] for o in r["oficiales"]} == {"Fed", "BCE"}
    assert all("viejo" not in o["url"] for o in r["oficiales"])          # fuera de la ventana
    assert set(r["errores"]) == {"rss:BLS", "rss:BEA"}
    assert r["consultas"][0]["activo"] == "oro" and r["consultas"][-1]["activo"] == "general"
    assert "startdatetime=20261118000000" in pedidas[0] and "enddatetime=20261119120000" in pedidas[0]


def test_noticias_gdelt_texto_de_error_y_excepcion_de_red():
    def tr(url):
        if "gdelt" in url:
            return 200, b"Please limit requests to one every 5 seconds"
        raise TimeoutError("plazo total")
    r = N.recoger("2026-11-18", None, [], transporte=tr, espera=0)
    assert r["gdelt"] == [] and "gdelt:general" in r["errores"] and len([k for k in r["errores"] if k.startswith("rss")]) == 4


def test_noticias_usa_plazo_total(monkeypatch):
    from src.ingest import _http
    vistos = {}

    class R:
        status_code, content = 200, b"{}"

    def falso(url, **kw):
        vistos.update(kw)
        return R()
    monkeypatch.setattr(_http, "get", falso)
    N.transporte_http("https://x")
    assert vistos["total"] == N.PLAZO["total"] and vistos["timeout"] == N.PLAZO["timeout"]


# ============================================================================================ explicador
NOTA_OK = """> [!warning] Explicación posterior; no es señal de compra o venta.
> Línea.

# Caída de prueba

## 1. Qué ha pasado (datos)
- S&P 500 −5 %.

## 2. Hipótesis de causa (de más a menos probable)
### H1. Tipos al alza — confianza: media
- **A favor:** x
- **En contra:** y
- **Qué la confirmaría o descartaría en los próximos días:** z
### H2. Ruido — confianza: baja
- **A favor:** x

## 3. Qué dicen los modelos del proyecto (sin re-correr)
Nada.

## 4. Fuentes
- https://ejemplo.com/a

## 5. Comprobaciones automáticas
```json
[{"hipotesis": 1, "serie": "sp500", "direccion": "baja", "horizonte": 5, "que_significa": "sigue la caída"},
 {"hipotesis": 2, "serie": "sp500", "direccion": "sube", "horizonte": 20, "que_significa": "rebote"}]
```
"""


def _falso_claude(tmp_path, cuerpo=NOTA_OK, dormir=0):
    p = tmp_path / "claude_falso.py"
    p.write_text(f"""#!{sys.executable}
import re, sys, json, time
time.sleep({dormir})
txt = sys.stdin.read()
open({str(tmp_path / 'argv.json')!r}, 'w').write(json.dumps(sys.argv))
m = re.search(r"Escribe SOLO el fichero `([^`]+)`", txt)
open(m.group(1), 'w').write({cuerpo!r})
print(json.dumps({{"result": "hecho", "total_cost_usd": 0.12, "num_turns": 3, "duration_ms": 1000, "is_error": False}}))
""")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def _pq(tmp_path):
    d = tmp_path / "archivo" / "diag" / "paquetes" / "2026-11-18"
    d.mkdir(parents=True)
    P = {"noticias": {"gdelt": [{"url": "https://ejemplo.com/a"}], "oficiales": []}}
    (d / "paquete.json").write_text(json.dumps(P))
    return d / "paquete.json", P


def test_explicar_con_claude_falso(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_DIAG_CLAUDE_BIN", str(_falso_claude(tmp_path)))
    pq, P = _pq(tmp_path)
    ev = {"fecha": pd.Timestamp("2026-11-18"), "disparos": [{"tipo": "extremo", "clave": "oro", "tamano": 3.2,
                                                             "texto": "Oro −4 %"}]}
    meta = E.explicar("2026-11-18", ev, pq, P)
    nota = Path(meta["nota"])
    assert nota.name == "2026-11-18_extremo_oro.md" and meta["avisos"] == []
    txt = nota.read_text()
    assert txt.startswith("---\ntipo: diagnostico\nfecha_evento: 2026-11-18") and "Oro −4 %" in txt
    assert meta["total_cost_usd"] == 0.12
    argv = json.loads((tmp_path / "argv.json").read_text())
    i = argv.index("--tools")
    assert argv[i + 1] == "Read,Write" and "--restricted" in argv and "dontAsk" in argv
    assert "Bash" in argv[argv.index("--disallowedTools"):]
    assert any("config/**" in a and a.startswith("Read(") for a in argv)
    assert any("research/paper/**" in a for a in argv)
    assert any(a.startswith("Edit(/") and a.endswith("2026-11-18_extremo_oro.md)") for a in argv)


def test_explicar_avisa_formato_y_urls_ajenas(tmp_path, monkeypatch):
    malo = NOTA_OK.replace("## 4. Fuentes\n- https://ejemplo.com/a", "## 4. Fuentes\n- https://inventada.com/z")
    malo = malo.replace("## 3. Qué dicen los modelos del proyecto", "## 3. Otra cosa")
    monkeypatch.setenv("FIN_DIAG_CLAUDE_BIN", str(_falso_claude(tmp_path, malo)))
    pq, P = _pq(tmp_path)
    meta = E.explicar("2026-11-18", None, pq, P)
    assert any("inventada.com" in a for a in meta["avisos"]) and "## 3. Qué dicen los modelos" in meta["avisos"]


def test_explicar_plazo_y_fallo(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_DIAG_CLAUDE_BIN", str(_falso_claude(tmp_path, dormir=5)))
    pq, P = _pq(tmp_path)
    monkeypatch.setattr(E, "PLAZO_S", 1)
    t = E.lanzar("x", pq.parent, tmp_path / "n.md", plazo=1)
    assert t["rc"] is None and "plazo" in t["error"]
    monkeypatch.setenv("FIN_DIAG_CLAUDE_BIN", "/no/existe")
    meta = E.explicar("2026-11-18", None, pq, P)
    assert meta["nota"] is None and "error" in meta


def test_cupo_semanal_con_marcas():
    hoy = pd.Timestamp("2026-11-19")
    assert E.cupo_restante(hoy) == 3
    for _ in range(3):
        E.marcar(hoy, hoy, None)
    assert E.cupo_restante(hoy) == 0
    assert E.cupo_restante(hoy + pd.Timedelta(days=7)) == 3   # semana nueva
    assert E.marcas_path().parent.name == "logs"


def _con_vacia():
    con = duckdb.connect()
    con.execute("create table obs_latest(series_id varchar, date date, value double, source varchar)")
    con.execute("create table vintages(series_id varchar, date date, value double, source varchar, realtime_start date, realtime_end date)")
    return con


def test_diario_siembra_luego_nota_y_tope(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_DIAG_CLAUDE_BIN", str(_falso_claude(tmp_path)))
    X = _X(SPY=_salto(_paseo(seed=0), 0, -0.06))
    hoy = X["precios"].index[-1] + pd.offsets.BDay(1)
    con = _con_vacia()
    r = E.diario(hoy, con=con, X=X, flujos=[], con_noticias=False)
    assert "sembrado" in r[0] and not Path(os.environ["FIN_DIAG_NOTAS"]).exists()
    # un salto nuevo al día siguiente: nota
    X2 = _X(fin=hoy, SPY=_salto(_paseo(seed=0, fin=hoy), 0, -0.06))
    r2 = E.diario(hoy + pd.offsets.BDay(1), con=con, X=X2, flujos=[], con_noticias=False)
    assert any("nota" in x for x in r2), r2
    reg = E.leer_registro()
    assert reg[-1]["estado"] == "nota" and Path(reg[-1]["nota"]).exists()
    # sin cupo: queda el paquete sin nota
    for _ in range(3):
        E.marcar(hoy + pd.offsets.BDay(2), hoy, None)
    X3 = _X(fin=hoy + pd.offsets.BDay(8), SPY=_salto(_paseo(seed=0, fin=hoy + pd.offsets.BDay(8)), 0, 0.07))
    r3 = E.diario(hoy + pd.offsets.BDay(9), con=con, X=X3, flujos=[], con_noticias=False)
    assert E.cupo_restante(hoy + pd.offsets.BDay(9)) == 3 - sum(1 for x in r3 if ": nota " in x)
    hoy4 = hoy + pd.offsets.BDay(2)   # misma semana que las 3 marcas: sin cupo
    X4 = _X(fin=hoy4 - pd.offsets.BDay(1), SPY=_salto(_paseo(seed=0, fin=hoy4 - pd.offsets.BDay(1)), 0, 0.08))
    est = D.leer_estado()
    est["vistos"] = []
    D.guardar_estado(est)
    for p in Path(os.environ["FIN_DIAG_NOTAS"]).glob("*.md"):
        p.unlink()
    r4 = E.diario(hoy4, con=con, X=X4, flujos=[], con_noticias=False)
    assert any("tope semana" in x for x in r4), r4
    assert E.leer_registro()[-1]["estado"] == "tope_semana"


def test_seguimiento_5_y_20(tmp_path):
    X = _X()
    f = X["precios"].index[-30]
    nd = Path(os.environ["FIN_DIAG_NOTAS"])
    nd.mkdir(parents=True)
    nota = nd / f"{f.date()}_extremo_sp500.md"
    nota.write_text(f"---\ntipo: diagnostico\nfecha_evento: {f.date()}\n---\n\n" + NOTA_OK)
    hechas = E.seguimiento(X, {}, X["precios"].index[-1])
    assert len(hechas) == 2
    txt = nota.read_text()
    assert "<!-- seguimiento-5 -->" in txt and "<!-- seguimiento-20 -->" in txt and "coincide" in txt
    assert E.seguimiento(X, {}, X["precios"].index[-1]) == []   # no se repite
    filas = [json.loads(x) for x in Path(os.environ["FIN_DIAG_ACIERTOS"]).read_text().splitlines()]
    assert {x["horizonte"] for x in filas} == {5, 20}
    s = X["precios"]["SPY"]
    cam = 100 * (s.iloc[-30 + 5] / s.iloc[-30] - 1)
    assert filas[0]["cambio"] == pytest.approx(cam, abs=1e-3)


def test_actualizacion_en_nota_abierta():
    nd = Path(os.environ["FIN_DIAG_NOTAS"])
    nd.mkdir(parents=True)
    n = nd / "2026-11-16_extremo_oro.md"
    n.write_text(NOTA_OK)
    assert E.nota_abierta("2026-11-18") == n
    assert E.nota_abierta("2026-11-30") is None
    E.anadir_actualizacion(n, {"fecha": pd.Timestamp("2026-11-18"), "disparos": [{"texto": "Oro −3 σ", "repetido": True}]})
    assert "## Actualizaciones (automáticas, sin IA)\n- **2026-11-18**: Oro −3 σ (repetido)" in n.read_text()


# ============================================================================================ tarjeta y enganche
def test_tarjeta_con_y_sin_nota(tmp_path):
    nd = Path(os.environ["FIN_DIAG_NOTAS"])
    nd.mkdir(parents=True)
    n = nd / "2026-11-18_extremo_oro.md"
    n.write_text(NOTA_OK)
    pq = tmp_path / "p.json"
    pq.write_text(json.dumps({"movimientos": [{"nombre": "Oro", "cambio": -3.2, "k_sigma63": -2.2, "unidad": "%"}]}))
    E.registrar({"fecha": "2026-11-18", "estado": "nota", "disparos": ["Oro −4 %"], "nota": str(n), "paquete": str(pq)})
    E.registrar({"fecha": "2026-11-17", "estado": "tope_semana", "disparos": ["S&P −3 σ"], "nota": None, "paquete": str(pq)})
    h = T.bloque_diag(pd.Timestamp("2026-11-19").date())
    assert "H1. Tipos al alza" in h and "Sin hipótesis" in h and "Oro: −3,20 % (−2,2 σ)" in h and "tope de 3" in h
    assert "sin eventos" in T.bloque_diag(pd.Timestamp("2027-01-19").date())


def test_tarjeta_en_hoy_del_panel():
    from src.report import panel
    html = panel.construir({}, pd.Timestamp("2026-11-19").date())
    assert 'id="diagnosticos-hoy"' in html


def test_enganche_actualizar_no_afecta_a_la_diaria():
    s = (REPO / "scripts/actualizar.sh").read_text()
    i = s.index("scripts/diagnostico.sh")
    linea = s[i:s.index("\n", i)]
    assert "|| true" in linea and 'FIN_DIAG:-1' in s[i - 200:i]
    assert s.rstrip().endswith("exit $RC") and s.index("diagnostico.sh") < s.rindex("exit $RC")
    r = subprocess.run(["bash", str(REPO / "scripts/diagnostico.sh")], env={**os.environ, "FIN_DIAG": "0"},
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and "apagados" in r.stdout


def test_notas_fuera_de_git():
    r = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "obsidian/Diagnosticos/2026-11-18_x.md"])
    assert r.returncode == 0
    r = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "research/diag/aciertos.jsonl"])
    assert r.returncode == 0


def test_prompt_versionado_restricciones():
    t = E.PROMPT.read_text()
    for k in ("{PAQUETE}", "{NOTA}", "{FECHA}", "SOLO titulares", "## 5. Comprobaciones automáticas", "máximo 4"):
        assert k in t


def test_noticias_reintenta_429_de_gdelt():
    vistas = {}

    def tr(url):
        vistas[url] = vistas.get(url, 0) + 1
        if "gdelt" in url:
            return (429, b"Please limit requests") if vistas[url] == 1 else (200, GDELT_OK)
        return 404, b""
    r = N.recoger("2026-11-18", None, [], transporte=tr, espera=0)
    assert r["gdelt"] and not [k for k in r["errores"] if k.startswith("gdelt")]


def test_evento_ya_visto_con_disparo_tardio_repetido_no_abre_nota(tmp_path, monkeypatch):
    """Validador 19-nov: un evento cuyo único disparador no repetido ya se vio (p. ej. se quedó sin nota por el tope)
    no abre nota ni gasta cupo porque llegue tarde un disparador en enfriamiento (DGS10 con 1 día de retraso)."""
    monkeypatch.setenv("FIN_DIAG_CLAUDE_BIN", str(_falso_claude(tmp_path)))
    f = pd.Timestamp("2026-11-17")
    ev = {"fecha": f, "tipos": ["extremo"], "tamano": 3.5, "nuevo": True,
          "disparos": [{"fecha": f, "tipo": "extremo", "clave": "sp500", "tamano": 3.5, "texto": "S&P", "visto": True,
                        "repetido": False},
                       {"fecha": f, "tipo": "extremo", "clave": "tesoro10", "tamano": 3.1, "texto": "10 a",
                        "visto": False, "repetido": True}]}
    monkeypatch.setattr(D, "detectar", lambda *a, **k: ([ev], {"vistos": ["x"]}))
    D.guardar_estado({"vistos": ["x"]})
    r = E.diario("2026-11-18", con=_con_vacia(), X=_X(), flujos=[], con_noticias=False)
    assert not any("nota" in x for x in r), r
    assert E.cupo_restante(pd.Timestamp("2026-11-18")) == 3
    assert E.leer_registro()[-1]["estado"] == "solo_vistos_sin_nota_abierta"
