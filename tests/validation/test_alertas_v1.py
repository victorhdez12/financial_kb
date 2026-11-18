"""Validación independiente de las alertas de flujos v1 (docs/validation/2026-11-17_alertas_v1.md).

Datos SINTÉTICOS, sin red. Los `xfail(strict=True)` documentan hallazgos abiertos: si alguien los arregla, el test pasa
y pytest avisa (XPASS) para quitar la marca.
"""
import json

import numpy as np
import pandas as pd
import pytest

from src.report import alertas as AL

HOY = pd.Timestamp("2026-11-16")


def _serie(n=420, seed=7):
    rng = np.random.default_rng(seed)
    ix = pd.bdate_range(end=HOY, periods=n)
    v = pd.Series(1e6 * np.exp(rng.normal(0, 0.3, n)), index=ix)
    c = pd.Series(50 * np.exp(np.cumsum(rng.normal(0, 0.015, n))), index=ix)
    h, lo = c * (1 + rng.uniform(0.001, 0.02, n)), c * (1 - rng.uniform(0.001, 0.02, n))
    return v, c, h, lo


# ------------------------------------------------------------------------------------------ volumen
def test_volumen_recalculado_a_mano():
    v, c, h, lo = _serie()
    v.iloc[-30] *= 6
    d = AL.senal_volumen(v, c, h, lo)
    for i in (len(v) - 30, len(v) - 1, 300):
        f = v.index[i]
        ratio = v.iloc[i] / v.iloc[i - 63:i].mean()
        lv = np.log(v.iloc[max(0, i - 252):i])
        q1, q3 = np.percentile(lv, [25, 75])
        z = (np.log(v.iloc[i]) - np.median(lv)) / ((q3 - q1) / 1.349)
        lr = np.log(c).diff()
        k = lr.iloc[i] / lr.iloc[i - 63:i].std()
        clv = (c.iloc[i] - lo.iloc[i]) / (h.iloc[i] - lo.iloc[i])
        r5 = v.iloc[i - 4:i + 1].mean() / v.iloc[i - 67:i - 4].mean()
        assert d.at[f, "ratio"] == pytest.approx(ratio)
        assert d.at[f, "z"] == pytest.approx(z)
        assert d.at[f, "k"] == pytest.approx(k)
        assert d.at[f, "clv"] == pytest.approx(clv)
        assert d.at[f, "ratio5"] == pytest.approx(r5)
    assert d.iloc[-30]["nivel"] == 2


def test_volumen_sin_mirada_al_futuro():
    """Cortar la serie en f no cambia nada de lo calculado para f (×, z, σ, k, 5 sesiones, nivel, clase)."""
    v, c, h, lo = _serie()
    full = AL.senal_volumen(v, c, h, lo)
    cols = ["ratio", "z", "sigma", "k", "clv", "ratio5", "k5", "nivel", "nivel5"]
    for i in (200, 333, len(v) - 10):
        f = v.index[i]
        tr = AL.senal_volumen(v[:f], c[:f], h[:f], lo[:f])
        np.testing.assert_allclose(full.loc[f, cols].astype(float), tr.loc[f, cols].astype(float))
        assert full.at[f, "clase"] == tr.at[f, "clase"]


def test_calendario_2026():
    ix = pd.bdate_range("2026-01-01", "2026-12-31").drop(pd.Timestamp("2026-06-19"))   # Juneteenth
    esp = AL.dias_especiales(ix)
    for f in ("2026-03-20", "2026-06-18", "2026-09-18", "2026-12-18"):
        assert "triple witching" in esp[pd.Timestamp(f)]
    assert "Russell" in esp[pd.Timestamp("2026-06-26")]
    for f in ("2026-02-27", "2026-05-29", "2026-08-31", "2026-11-30"):
        assert "MSCI" in esp[pd.Timestamp(f)]


# ------------------------------------------------------------------------------------------ recompras (XBRL)
def _h(s, e, v, filed, form="10-Q"):
    return {"start": s, "end": e, "val": v, "filed": filed, "form": form}


def test_trimestres_uber_real_ytd_y_q4_anual_menos_9m():
    """Cifras de companyfacts de UBER (PaymentsForRepurchaseOfCommonStock, contrastadas con data.sec.gov el 18-nov)."""
    h = [_h("2025-01-01", "2025-03-31", 1785e6, "2025-05-07"), _h("2025-01-01", "2025-06-30", 3148e6, "2025-08-06"),
         _h("2025-01-01", "2025-09-30", 4611e6, "2025-11-04"), _h("2025-01-01", "2025-12-31", 6523e6, "2026-02-13", "10-K"),
         _h("2026-01-01", "2026-03-31", 3011e6, "2026-05-06"), _h("2026-01-01", "2026-06-30", 3529e6, "2026-08-05"),
         _h("2026-01-01", "2026-09-30", 4279e6, "2026-11-04")]
    q = AL.trimestres(h).set_index("fin")["importe"] / 1e6
    assert list(q.round(0)) == [1785, 1363, 1463, 1912, 3011, 518, 750]
    assert q.iloc[-4:].sum() == pytest.approx(6191)


# ------------------------------------------------------------------------------------------ notificación
def _ev(clave, frase="x. y", fuerza=2):
    return {"clave": clave, "fuerza": fuerza, "fecha": HOY, "ticker": "AAA", "frase": frase, "tipo": "13f"}


def test_notificacion_no_escribe_fuera_del_archivo_y_respeta_config(tmp_path, monkeypatch):
    evs = [_ev("a")]
    monkeypatch.setattr(AL, "cargar", lambda base=None: {})
    monkeypatch.setattr(AL, "calcular", lambda X=None, hoy=None: {"hoy": str(HOY.date()), "eventos": evs})
    monkeypatch.setenv("FIN_DATA_ROOT", str(tmp_path))
    for v in ("0", "no", "false", "OFF"):
        monkeypatch.setenv("FIN_ALERTAS_NOTIFICAR", v)
        assert AL.notificar() == ""
    monkeypatch.delenv("FIN_ALERTAS_NOTIFICAR")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "alertas.json").write_text("{roto")   # JSON roto: notifica (no falla)
    assert AL.notificar().startswith("1 alerta")
    assert AL.notificar() == ""
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()) == \
        ["alertas/notificadas.json", "config/alertas.json"]


@pytest.mark.xfail(strict=True, reason="H3: mensaje() quita etiquetas pero no deshace entidades HTML (&amp;)")
def test_mensaje_sin_entidades_html():
    m = AL.mensaje([_ev("a", "JPMORGAN CHASE &amp; CO baja su posición. Resto")])
    assert "&amp;" not in m and "JPMORGAN CHASE & CO" in m


# ------------------------------------------------------------------------------------------ historia descriptiva
@pytest.mark.xfail(strict=True, reason="H2: «≈ al año» divide por 10 años aunque el activo tenga menos historia")
def test_historia_alertas_por_anio_con_historia_corta():
    rng = np.random.default_rng(3)
    ix = pd.bdate_range(end=HOY, periods=5 * 252)
    v = pd.Series(1e6 * np.exp(rng.normal(0, 0.2, len(ix))), index=ix)
    v.iloc[300::100] *= 8
    c = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(ix)))), index=ix)
    d = AL.senal_volumen(v, c)
    hv = AL.historico_volumen(d, {}, 10)
    anios_reales = (ix[-1] - ix[0]).days / 365.25
    txt = AL._nota_historico(hv)
    esperado = f"≈ {hv['n'] / anios_reales:.1f}".replace(".", ",")
    assert esperado in txt


# ------------------------------------------------------------------------------------------ robustez
def test_fuentes_nuevas_rotas_dan_sd(monkeypatch):
    v, c, h, lo = _serie()
    X = {"volumen": pd.DataFrame({"UBER": v}), "cierre": pd.DataFrame({"UBER": c}),
         "error_dg": "roto", "error_recompras": "roto", "error_short": "roto", "error_alto": "roto",
         "error_form4": "roto", "error_13f": "roto"}
    R = AL.calcular(X, HOY.date())
    a = R["activos"]["UBER"]
    assert {"13dg", "form4", "13f"} <= set(a["errores"])
    html = AL.bloque_alertas(R) + AL.ficha_flujos("UBER", R)
    assert "s/d" in html and "Flujos fuertes" in html
