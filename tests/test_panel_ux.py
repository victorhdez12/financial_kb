"""Panel UX v2 (17-nov-2026): visor de gráficos, «qué significa esto para ti», navegación. Solo presentación."""
import functools
import re
import shutil
import subprocess
from datetime import date

from src.report import _ui as UI
from src.report import panel as PN


@functools.lru_cache(maxsize=1)
def _doc():
    return PN.construir({}, date(2026, 11, 17))


def test_visor_y_extras_presentes():
    doc = _doc()
    assert '<dialog id="zoom"' in doc and 'id="arriba"' in doc and 'class="navwrap"' in doc
    assert doc.count('role="tab"') == len(PN.PESTANAS)


def test_para_ti_en_cada_pestana_con_3_a_5_frases():
    doc = _doc()
    for k, _ in PN.PESTANAS:
        assert 3 <= len(UI.PARA_TI[k]) <= 5, k
        assert k in UI.PESTANA_INFO, k
    assert doc.count('class="parati"') == len(PN.PESTANAS)


def test_para_ti_sin_cifras():
    # los resúmenes llanos no deben introducir cifras propias (las cifras salen de los cálculos, debajo)
    permitidas = {"p90", "90 %", "3 años", "18 países", "B0", "B1", "B1′", "12 meses"}
    for k, frases in UI.PARA_TI.items():
        t = " ".join(frases)
        for p in permitidas:
            t = t.replace(p, "")
        assert not re.search(r"\d", t), (k, t)


def test_localstorage_protegido():
    js = PN.JS + UI.JS
    for m in re.finditer(r"localStorage\.\w+\(", js):
        antes = js[max(0, m.start() - 12):m.start()]
        assert "try{" in antes, antes


def test_js_sintaxis_con_node():
    node = shutil.which("node")
    if not node:
        return
    doc = _doc()
    js = "\n;\n".join(re.findall(r"<script>(.*?)</script>", doc, re.S))
    r = subprocess.run([node, "--check", "-"], input=js, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
