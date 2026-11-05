"""P-K1v: los coeficientes congelados no se han tocado."""
import json
from pathlib import Path

from scripts.k1_corrida import sha

REPO = Path(__file__).resolve().parents[1]


def test_k1_modelos_congelados():
    j = json.loads((REPO / "research/int/k1_modelos.json").read_text())
    assert sha(j["modelos"]) == j["modelos_sha256"] and j["estado"] == "congelado"
    assert j["modelos"]["K"]["b"][2] > 0


def test_k1_no_registra_sin_revisar_inicios():
    """Validador 2026-11-05: t > INICIOS_REVISADOS_HASTA exige declarar antes los inicios de crisis (B1, en riesgo)."""
    from scripts.k1_vivo import puede_registrar
    assert puede_registrar([2025.0] * 3, 2025)[0] == 10          # t < PRIMER_T: aún no toca
    assert puede_registrar([2026.0, 2025.0], 2026)[0] == 10      # t mezclados
    assert puede_registrar([2026.0, float("nan")], 2025)[0] == 6  # sin revisar los inicios de 2026
    assert puede_registrar([2026.0, 2026.0], 2026) == (0, "")


def test_paper_mensual_no_corta_e1_k1():
    """Validador 2026-11-05: la marca del paper no impide reintentar E1/K1, y "ya registrado" no cierra el año de K1."""
    s = (REPO / "scripts/paper_mensual.sh").read_text()
    assert s.index('.paper_hecho_$MES" ] && exit 0') > s.index("scripts.k1_vivo") > s.index("scripts.e1_vivo")
    linea = next(x for x in s.splitlines() if "touch" in x and ".k1_hecho_" in x)
    assert "ya registrado" not in linea
