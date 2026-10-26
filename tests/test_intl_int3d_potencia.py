"""Tests sintéticos del script de potencia de INT-3d (sin datos reales)."""
import numpy as np

from scripts import int3d_potencia as S


def _panel(valor=0.0):
    x = np.full((len(S.NUCLEO), S.L), valor)
    return x


def test_suma_ventana_y_huecos():
    x = _panel(0.1)
    x[0, 10] = np.nan
    ac = S.Acum(x)
    ci = np.array([0, 1, 1])
    s = ac.suma(ci, np.array([1875, 1875, 2003]), np.array([1881, 1881, 2005]))
    assert np.isnan(s[0]) and np.isclose(s[1], 0.7) and np.isnan(s[2])      # hueco; completa; se sale de 2004


def test_espera_salida_usa_cuatro_meses():
    ac = S.Acum(_panel(0.12))
    ev = {"ci": np.array([2]), "P": np.array([1900]), "V": np.array([1901]), "fin": np.array([0])}
    assert np.isclose(S.estadistico("C1_espera_salida", ac, ev), 0.12 + 0.12 * 4 / 12)


def test_agregacion_por_año():
    x, g = np.array([1.0, 1.0, 1.0, 4.0]), np.array([1900, 1900, 1900, 1950])
    assert np.isclose(S.agregar(x, g), 2.5) and np.isclose(S.agregar(x, g, por_año=False), 1.75)


def test_fondo_en_el_valle():
    x = _panel(0.05)
    x[3, 1900 - S.A0: 1903 - S.A0] = -0.2          # caídas en 1900-1902, valle 1902
    ac = S.Acum(x)
    ev = {"ci": np.array([3]), "P": np.array([1899]), "V": np.array([1902]), "fin": np.array([0])}
    assert S.estadistico("C7_fondo_bolsa", ac, ev) == 0.0


def test_desplazar_conserva_duracion_y_es_circular():
    ev = {"ci": np.array([0, 1]), "P": np.array([1929, 2000]), "V": np.array([1932, 2001]), "fin": np.array([1, 0])}
    d = S.desplazar(ev, 10)
    assert list(d["P"]) == [1939, 1875] and list(d["V"] - d["P"]) == [3, 1]
