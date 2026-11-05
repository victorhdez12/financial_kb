"""P-K1v: los coeficientes congelados no se han tocado."""
import json
from pathlib import Path

from scripts.k1_corrida import sha

REPO = Path(__file__).resolve().parents[1]


def test_k1_modelos_congelados():
    j = json.loads((REPO / "research/int/k1_modelos.json").read_text())
    assert sha(j["modelos"]) == j["modelos_sha256"] and j["estado"] == "congelado"
    assert j["modelos"]["K"]["b"][2] > 0
