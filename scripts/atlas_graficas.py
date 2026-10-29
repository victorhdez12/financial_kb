"""Atlas visual: gráficas PNG de resultados YA CALCULADOS (ningún contraste nuevo, ningún dato JST ≥ 2005).

Lee solo los JSON de research/int/ (INT-3, INT-3b, INT-3d, INT-4, atlas §8, puerta y termómetro vivo) y la
clasificación fijada en docs/int/ATLAS_regimenes.md (copiada aquí tal cual, con su sección). No recalcula nada:
las trayectorias de INT-3d están guardadas en int3d_resultado.json (descriptivos), así que no se reconstruyen.
La puerta de la traducción no guarda los pares p anual / p mensual: se muestran solo sus cifras (r y pendiente).

Salida: research/int/graficas/*.png y una copia en obsidian/Proyecto/img/atlas/ para incrustarlas en el vault.
Uso: .venv/bin/python -m scripts.atlas_graficas
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
INT = REPO / "research" / "int"
OUT = INT / "graficas"
VAULT_IMG = REPO / "obsidian" / "Proyecto" / "img" / "atlas"

# Paleta (validada: azul / naranja / aqua; divergente azul ↔ rojo con gris neutro en el centro)
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GRIS_TXT, GRIS_SUAVE, NEUTRO, SUPERFICIE = "#52514e", "#b9b8b2", "#f0efec", "#fcfcfb"
TINTA = "#0b0b0b"
DIVERGENTE = LinearSegmentedColormap.from_list(
    "rojo_azul", ["#a32c2b", "#e34948", "#f3b3ad", NEUTRO, "#9ec5f4", "#3987e5", "#184f95"])
SECUENCIAL = LinearSegmentedColormap.from_list("azul", ["#eef4fc", "#9ec5f4", "#3987e5", "#184f95"])

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.edgecolor": GRIS_SUAVE, "axes.labelcolor": TINTA, "xtick.color": GRIS_TXT, "ytick.color": GRIS_TXT,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SUPERFICIE,
    "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE, "axes.grid": False,
})


def cargar(nombre: str) -> dict:
    return json.loads((INT / nombre).read_text())


def pp(x: float) -> float:
    return 100.0 * x


def coma(x: float, d: int = 1, signo: bool = True) -> str:
    s = f"{x:+.{d}f}" if signo else f"{x:.{d}f}"
    return s.replace(".", ",").replace("-", "−")


def nota(fig, texto: str) -> None:
    fig.text(0.01, 0.01, texto, ha="left", va="bottom", fontsize=7.5, color=GRIS_TXT, wrap=True)


def guardar(fig, nombre: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    VAULT_IMG.mkdir(parents=True, exist_ok=True)
    ruta = OUT / nombre
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    shutil.copy2(ruta, VAULT_IMG / nombre)
    return ruta


# Clasificación: docs/int/ATLAS_regimenes.md §1 (fijada por escrito antes de clasificar; no se recalcula aquí).
CONF_MARCA = {"establecido": "●●●", "establecido (frágil)": "●●○", "probable": "●●", "no establecido": "○"}


# ---------------------------------------------------------------------------------------------------------------
# 1. Mapa de calor activo × régimen
# ---------------------------------------------------------------------------------------------------------------
def g1_mapa() -> Path:
    q = cargar("int3_resultado.json")["principal"]
    dk = cargar("int3_sensibilidad_robusta.json")["preguntas"]
    b = cargar("int3b_resultado.json")["principal"]
    c3 = cargar("int3d_resultado.json")["contrastes"]["C3_bonos_recesion"]["principal"]

    regs = ["Expansión", "Sobrecalen-\ntamiento", "Estanflación", "Crecimiento\nbajo", "Inflación alta\n(sobrecal. + estanfl.)",
            "Recesión"]
    activos = ["Bolsa", "Bonos", "Letras", "Vivienda − bolsa", "Bonos − letras", "Oro (moneda local)",
               "Materias primas (mundial)", "Crédito − bono (EE. UU., R. U.)"]
    # (activo, columna, efecto, ic, clasificación, etiqueta)
    celdas = [
        ("Bolsa", 2, q["Q1"]["efecto"], dk["Q1"]["dk"]["ic95"], "establecido", "Q1"),
        ("Bolsa", 5, q["Q5"]["efecto"], dk["Q5"]["dk"]["ic95"], "establecido (frágil)", "Q5"),
        ("Bonos", 4, q["Q2"]["efecto"], dk["Q2"]["dk"]["ic95"], "establecido", "Q2"),
        ("Bonos", 3, q["Q3"]["efecto"], dk["Q3"]["dk"]["ic95"], "probable", "Q3"),
        ("Letras", 4, q["Q4"]["efecto"], dk["Q4"]["dk"]["ic95"], "probable", "Q4"),
        ("Vivienda − bolsa", 4, q["Q6"]["efecto"], dk["Q6"]["dk"]["ic95"], "establecido", "Q6"),
        ("Bonos − letras", 5, c3["efecto"], c3["ic95"], "probable", "3d-C3"),
        ("Oro (moneda local)", 4, b["B3"]["efecto"], b["B3"]["ic95"], "no establecido", "B3"),
        ("Materias primas (mundial)", 4, b["B1"]["efecto"], b["B1"]["ic95"], "no establecido", "B1"),
        ("Materias primas (mundial)", 5, b["B2"]["efecto"], b["B2"]["ic95"], "no establecido", "B2"),
        ("Crédito − bono (EE. UU., R. U.)", 5, b["B4"]["efecto"], b["B4"]["ic95"], "no establecido", "B4"),
    ]
    lim = 12.0
    fig, ax = plt.subplots(figsize=(11.5, 6.6))
    fig.subplots_adjust(left=0.2, right=0.88, top=0.84, bottom=0.2)
    for i in range(len(activos)):
        for j in range(len(regs)):
            ax.add_patch(Rectangle((j, i), 1, 1, facecolor="#e6e5e0", edgecolor=SUPERFICIE, lw=2, hatch="///"))
            ax.text(j + 0.5, i + 0.5, "no contrastado", ha="center", va="center", fontsize=6.5, color="#8a8984")
    for act, j, ef, ic, cl, et in celdas:
        i = activos.index(act)
        v = pp(ef)
        color = DIVERGENTE((np.clip(v, -lim, lim) + lim) / (2 * lim))
        ax.add_patch(Rectangle((j, i), 1, 1, facecolor=color, edgecolor=SUPERFICIE, lw=2))
        if cl == "no establecido":  # se atenúa: el número no es fiable
            ax.add_patch(Rectangle((j, i), 1, 1, facecolor="none", edgecolor="#8a8984", lw=0, hatch="...", alpha=0.6))
        tinta = "white" if abs(v) > 8 else TINTA
        ax.text(j + 0.5, i + 0.34, f"{coma(v)} pp", ha="center", va="center", fontsize=10.5, fontweight="bold",
                color=tinta)
        ax.text(j + 0.5, i + 0.62, f"[{coma(pp(ic[0]), 1)}; {coma(pp(ic[1]), 1)}]", ha="center", va="center",
                fontsize=6.8, color=tinta)
        ax.text(j + 0.5, i + 0.86, f"{CONF_MARCA[cl]} {cl} · {et}", ha="center", va="center", fontsize=6.5,
                color=tinta)
    ax.axvline(4, color=TINTA, lw=1.2)
    ax.set_xlim(0, len(regs))
    ax.set_ylim(len(activos), 0)
    ax.set_xticks(np.arange(len(regs)) + 0.5, regs, fontsize=9)
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(len(activos)) + 0.5, activos, fontsize=9.5)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    fig.suptitle("¿Qué hace cada activo en cada régimen? (rentabilidad real frente al resto de años, pp/año)",
                 x=0.01, ha="left", fontsize=12.5, fontweight="bold")
    fig.text(0.01, 0.905, "Rojo = rinde peor de lo normal; azul = mejor. Cuadros grises = no se contrastó. "
             "Las dos últimas columnas agrupan regímenes (a la derecha de la línea).", fontsize=9, color=GRIS_TXT)
    cax = fig.add_axes([0.9, 0.3, 0.018, 0.45])
    sm = plt.cm.ScalarMappable(cmap=DIVERGENTE, norm=plt.Normalize(-lim, lim))
    cb = fig.colorbar(sm, cax=cax)
    cb.set_label("pp/año (recortado a ±12)", fontsize=8)
    cb.outline.set_visible(False)
    fig.text(0.89, 0.24, "Confianza:\n●●● establecido\n●●○ establecido (frágil)\n●● probable\n○ no establecido\n"
             "(punteado: no fiarse del número)", fontsize=7.2, color=TINTA, va="top")
    nota(fig, "Fuente: docs/int/ATLAS_regimenes.md §1 (clasificación); cifras de research/int/int3_resultado.json, "
         "int3_sensibilidad_robusta.json (IC Driscoll-Kraay), int3b_resultado.json, int3d_resultado.json (C3). "
         "14 países JST, 1870/1877-1999/2004, rentabilidades reales anuales.\n"
         "Confianza: la marcada en cada celda. OJO: el régimen es una etiqueta EX POST (ventana centrada, mira años "
         "futuros); describe lo que pasó, no lo que se podía saber a tiempo (ver la gráfica 2). "
         "Oro: precio fijo hasta 1971 (artefacto).")
    return guardar(fig, "01_mapa_activo_regimen.png")


# ---------------------------------------------------------------------------------------------------------------
# 2. Efectos principales con IC 95 %: ex post frente a lo que se sabe a tiempo
# ---------------------------------------------------------------------------------------------------------------
def g2_efectos() -> Path:
    q = cargar("int3_resultado.json")["principal"]
    dk = cargar("int3_sensibilidad_robusta.json")["preguntas"]
    c4 = cargar("int3b_resultado.json")["principal"]["C4"]
    op = cargar("atlas_operable.json")
    t1, t2, holm = op["t_menos_1"], op["t_menos_2_estricto"], op["t_menos_1_holm_p_cal"]

    filas = [  # (texto, clasificación ex post, ex post (efecto, ic) o None, clave operable o None)
        ("Bolsa en estanflación (Q1)", "establecido", (q["Q1"]["efecto"], dk["Q1"]["dk"]["ic95"]), "Qa2_bolsa_estanfl"),
        ("Bolsa con inflación alta", "solo a tiempo", None, "Qa_bolsa_infl_alta"),
        ("Bonos con inflación alta (Q2)", "establecido", (q["Q2"]["efecto"], dk["Q2"]["dk"]["ic95"]), "Qa_bono_infl_alta"),
        ("Letras con inflación alta (Q4)", "probable", (q["Q4"]["efecto"], dk["Q4"]["dk"]["ic95"]), "Qa_letra_infl_alta"),
        ("Bonos en crecimiento bajo /\ndesinflación (Q3)", "probable", (q["Q3"]["efecto"], dk["Q3"]["dk"]["ic95"]),
         "Qb_bono_desinfl"),
        ("Bolsa en recesión (Q5)", "establecido (frágil)", (q["Q5"]["efecto"], dk["Q5"]["dk"]["ic95"]), None),
        ("Vivienda − bolsa con\ninflación alta (Q6)", "establecido", (q["Q6"]["efecto"], dk["Q6"]["dk"]["ic95"]), None),
        ("Precio de los bonos en\ncrecimiento bajo (C4, INT-3b)", "establecido", (c4["efecto"], c4["ic95"]), None),
    ]
    fig, ax = plt.subplots(figsize=(11, 7.2))
    fig.subplots_adjust(left=0.27, right=0.97, top=0.83, bottom=0.17)
    off = 0.24
    for i, (txt, cl, ex, k) in enumerate(filas):
        if ex is not None:
            ef, ic = pp(ex[0]), [pp(x) for x in ex[1]]
            ax.plot(ic, [i - off] * 2, color=AZUL, lw=2, solid_capstyle="round")
            ax.plot(ef, i - off, "o", color=AZUL, ms=8, mec=SUPERFICIE, mew=1.5)
            ax.text(max(ic) + 0.5, i - off, f"{coma(ef)}", va="center", fontsize=8, color=TINTA)
        if k is not None:
            for d, serie, col, mk in ((0, t1, NARANJA, "s"), (off, t2, AQUA, "D")):
                ef, ic = pp(serie[k]["efecto"]), [pp(x) for x in serie[k]["ic95"]]
                ax.plot(ic, [i + d] * 2, color=col, lw=2, solid_capstyle="round")
                ax.plot(ef, i + d, mk, color=col, ms=7, mec=SUPERFICIE, mew=1.5)
                extra = " · pasa Holm" if (serie is t1 and holm[k]) else ""
                ax.text(max(ic) + 0.5, i + d, f"{coma(ef)}{extra}", va="center", fontsize=8, color=TINTA)
        else:
            ax.text(-23.5, i + off / 2, "sin versión a tiempo", fontsize=7.5, color=GRIS_TXT, va="center",
                    style="italic")
        ax.text(-23.5, i - off - 0.02, CONF_MARCA.get(cl, "") + " " + cl if ex is not None else "", fontsize=7.5,
                color=AZUL, va="center")
    ax.axvline(0, color=TINTA, lw=1)
    ax.set_yticks(range(len(filas)), [f[0] for f in filas], fontsize=9)
    ax.set_ylim(len(filas) - 0.4, -0.6)
    ax.set_xlim(-24, 18)
    ax.set_xlabel("Efecto sobre la rentabilidad real (pp/año) e intervalo de confianza del 95 %")
    ax.grid(axis="x", color="#e6e5e0", lw=0.8)
    ax.set_axisbelow(True)
    fig.suptitle("Los efectos principales y cuánto queda si solo usas lo que se sabía a tiempo", x=0.01, ha="left",
                 fontsize=12.5, fontweight="bold")
    fig.text(0.01, 0.905, "Si la barra cruza el 0, el dato es compatible con «ningún efecto». "
             "Las versiones a tiempo son más pequeñas y casi todas cruzan o rozan el 0 con un año más de retraso.",
             fontsize=9, color=GRIS_TXT)
    ax.legend(handles=[
        Line2D([], [], color=AZUL, marker="o", lw=2, label="Ex post: régimen con ventana centrada (mira el futuro)"),
        Line2D([], [], color=NARANJA, marker="s", lw=2, label="A tiempo: estado observado en t − 1 (atlas §8)"),
        Line2D([], [], color=AQUA, marker="D", lw=2, label="A tiempo estricto: estado observado en t − 2"),
    ], loc="lower right", fontsize=8, frameon=False)
    nota(fig, "Fuente: research/int/int3_resultado.json + int3_sensibilidad_robusta.json (Q1-Q6, IC Driscoll-Kraay), "
         "int3b_resultado.json (C4), atlas_operable.json (§8 de docs/int/ATLAS_regimenes.md). 14 países JST, "
         "1876-1999.\nConfianza: azul = clasificación del atlas §1. Las versiones a tiempo son DESCRIPTIVAS, declaradas "
         "a posteriori; solo «bolsa en estanflación observada» pasa Holm (81 país-años, sobre todo años 70). "
         "Las definiciones a tiempo no son idénticas a las ex post (inflación > 3 %, brecha de un solo lado).")
    return guardar(fig, "02_efectos_ic_ex_post_vs_a_tiempo.png")


# ---------------------------------------------------------------------------------------------------------------
# 3. Trayectorias alrededor de las recesiones (INT-3d, guardadas)
# ---------------------------------------------------------------------------------------------------------------
def g3_trayectorias() -> Path:
    d = cargar("int3d_resultado.json")["descriptivos"]
    activos = [("eq", "Bolsa", AZUL), ("bond", "Bonos", NARANJA), ("bill", "Letras", AQUA)]
    anclas = [("trayectorias_pico", "Alrededor del PICO (0 = año del pico, último de expansión)"),
              ("trayectorias_valle", "Alrededor del VALLE (0 = año del valle, fondo del PIB)")]
    fig, axs = plt.subplots(2, 3, figsize=(12, 7.2), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.84, bottom=0.16, hspace=0.5, wspace=0.08)
    for r, (clave, titulo) in enumerate(anclas):
        for c, (a, nombre, col) in enumerate(activos):
            ax = axs[r, c]
            t = d[clave]["todas"][a]
            tau = np.array(t["tau"])
            ax.fill_between(tau, pp(np.array(t["p05"])), pp(np.array(t["p95"])), color="#e6e5e0", lw=0,
                            label="90 % de fechas al azar")
            ax.axhline(0, color=GRIS_SUAVE, lw=0.8)
            ax.axvline(0, color=GRIS_SUAVE, lw=0.8, ls="--")
            ax.plot(tau, pp(np.array(t["media"])), color=col, lw=2, marker="o", ms=5, mec=SUPERFICIE,
                    label=f"{nombre}: media")
            ax.set_title(f"{nombre} · {t['eventos']} recesiones", fontsize=10, loc="left")
            ax.set_xticks(tau)
            ax.grid(axis="y", color="#eeeeea", lw=0.8)
            ax.set_axisbelow(True)
            if c == 0:
                ax.set_ylabel("Rentabilidad real anómala\n(pp/año frente a la media del país)", fontsize=8.5)
            ax.set_xlabel("años respecto al " + ("pico" if r == 0 else "valle"), fontsize=8.5)
        axs[r, 0].text(0, 1.22, titulo, transform=axs[r, 0].transAxes, fontsize=10.5, fontweight="bold")
    axs[0, 2].legend(handles=[Patch(color="#e6e5e0", label="90 % de las medias con fechas al azar")],
                     loc="lower right", fontsize=7.5, frameon=False)
    fig.suptitle("¿Qué hacen bolsa, bonos y letras alrededor de una recesión?", x=0.01, ha="left", fontsize=12.5,
                 fontweight="bold")
    fig.text(0.01, 0.905, "Fuera de la banda gris = más de lo que dan fechas al azar. La bolsa cae en el año de entrada "
             "y sobre todo el año antes del valle; luego rebota.", fontsize=9, color=GRIS_TXT)
    nota(fig, "Fuente: research/int/int3d_resultado.json (descriptivos → trayectorias_pico / trayectorias_valle, "
         "«todas» las recesiones), guardadas por scripts/int3d_corrida.py; no se reconstruye nada. 14 países JST, "
         "1870-2004, datos anuales.\nConfianza: DESCRIPTIVO (sin contraste). Medias con datos anuales; el momento del "
         "fondo no se distingue de fechas al azar (atlas §3). Las bandas son de la media, no de cada recesión.")
    return guardar(fig, "03_trayectorias_recesiones.png")


# ---------------------------------------------------------------------------------------------------------------
# 4. Termómetro: AUC listón frente a modelo y puerta de la traducción
# ---------------------------------------------------------------------------------------------------------------
def g4_termometro() -> Path:
    sv = cargar("int4_sensibilidad_liston_validador.json")["giros"]
    of = cargar("int4_resultado.json")["principal"]
    pu = cargar("termometro_puerta_v2_corr.json")["puerta"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 6), gridspec_kw={"width_ratios": [1, 1.25]})
    fig.subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.2, wspace=0.28)

    giros = [("T1", "Entrar en recesión\n(a 1 año)"), ("T2", "Salir de recesión\n(a 1 año)")]
    w = 0.36
    for i, (g, txt) in enumerate(giros):
        e = sv[g]["a_estratificada_loco"]
        for d, v, col, lab in ((-w / 2, e["auc_liston"], GRIS_SUAVE, "Listón (solo años desde el giro)"),
                               (w / 2, e["auc_modelo"], AZUL, "Modelo (curva, otros países, bolsa…)")):
            a1.bar(i + d, v - 0.5, bottom=0.5, width=w - 0.04, color=col, label=lab if i == 0 else None)
            a1.text(i + d, v + 0.01, coma(v, 2, False), ha="center", fontsize=9)
        lo, hi = e["ic95"]
        a1.text(i, 0.86, f"mejora {coma(e['d_auc'], 2)}\nIC 95 % [{coma(lo, 2)}; {coma(hi, 2)}]", ha="center",
                fontsize=8.5, color=TINTA)
    a1.axhline(0.5, color=TINTA, lw=1)
    a1.text(1.62, 0.505, "0,5 = azar", fontsize=7.5, color=GRIS_TXT, ha="right", va="bottom")
    a1.set_xticks([0, 1], [g[1] for g in giros])
    a1.set_ylim(0.45, 0.95)
    a1.set_xlim(-0.5, 1.65)
    a1.set_ylabel("AUC (1 = acierta siempre el orden; 0,5 = azar)")
    a1.set_title("¿Ve venir los giros mejor que el listón?", loc="left", fontsize=11)
    a1.legend(loc="upper left", fontsize=7.5, frameon=False)

    # Puerta: r y pendiente (los pares p anual / p mensual no están guardados → solo cifras)
    a2.add_patch(Rectangle((0.8, 0.8), 0.2, 0.45, facecolor="#e3eefb", edgecolor=AZUL, lw=1, ls="--"))
    a2.text(0.995, 1.235, "zona que pasa:\nr ≥ 0,8 y pendiente 0,8-1,25", fontsize=7.5, color=AZUL, ha="right",
            va="top")
    for pais, v in pu["T1"]["por_pais"].items():
        if v.get("r") is None:
            continue
        a2.plot(v["r"], v["pendiente"], "o", color=NARANJA, ms=5, alpha=0.75, mec=SUPERFICIE)
        a2.annotate(pais, (v["r"], v["pendiente"]), xytext=(3, 2), textcoords="offset points", fontsize=6.5,
                    color=GRIS_TXT)
    for g, col, mk, txt in (("T1", NARANJA, "s", "Entrar (T1), agregado"), ("T2", AZUL, "D", "Salir (T2), agregado")):
        ag = pu[g]["agregado"]
        a2.plot(ag["r"], ag["pendiente"], mk, color=col, ms=12, mec=TINTA, mew=1)
        a2.annotate(f"{txt}: {ag['filas']} filas\nr {coma(ag['r'], 2, False)}, pend. {coma(ag['pendiente'], 2, False)}"
                    f" → {'PASA' if ag['pasa'] else 'NO pasa'}", (ag["r"], ag["pendiente"]), xytext=(-10, -30 if g == "T1" else 14),
                    textcoords="offset points", fontsize=8, ha="right", color=TINTA,
                    arrowprops=dict(arrowstyle="-", color=GRIS_SUAVE))
    a2.set_xlim(0.6, 1.0)
    a2.set_ylim(0.4, 1.3)
    a2.set_xlabel("Correlación r entre p anual y p mensual")
    a2.set_ylabel("Pendiente (p anual sobre p mensual)")
    a2.set_title("Puerta: ¿se traduce bien el modelo anual a meses?", loc="left", fontsize=11)
    a2.text(0.605, 0.42, "Puntos pequeños: países (T1). T2 por país no tiene\npuerta propia (pocas filas).",
            fontsize=7.5, color=GRIS_TXT)
    fig.suptitle("Termómetro de recesión: qué aciertos tiene y si se puede usar en meses", x=0.01, ha="left",
                 fontsize=12.5, fontweight="bold")
    fig.text(0.01, 0.885, "Se anticipa la entrada y la salida bastante mejor que el listón, pero la probabilidad de "
             "ENTRAR no pasó la puerta mensual: hoy solo se enseñan sus indicadores.", fontsize=9, color=GRIS_TXT)
    nota(fig, "Fuente: research/int/int4_sensibilidad_liston_validador.json (AUC estratificada por país, dejando un país "
         "fuera, 1871-2004; la corrida oficial daba T2 "
         f"{coma(of['T2']['auc_liston'], 2, False)} → {coma(of['T2']['auc_modelo'], 2, False)}, inflada por un sesgo del "
         "listón) y termometro_puerta_v2_corr.json (validación cruzada pares/impares, datos ≤ 2004).\nConfianza: T1 "
         "establecido sólido, T2 establecido justo (atlas §4). La puerta de T2 pasa con solo 31 filas (IC de r ≈ "
         "[0,49; 0,94]). Los pares p anual / p mensual no están guardados: solo se muestran r y pendiente.")
    return guardar(fig, "04_termometro_auc_y_puerta.png")


# ---------------------------------------------------------------------------------------------------------------
# 5. Termómetro hoy: indicadores por país con su percentil
# ---------------------------------------------------------------------------------------------------------------
def g5_vivo() -> Path:
    v = cargar("termometro_vivo_ultimo.json")
    orden = ["C1", "C4", "C6", "C2", "S4"]
    paises = list(v["paises"])
    nombres = {k: v["paises"][paises[0]]["indicadores"][k]["indicador"] for k in orden}
    unidades = {k: v["paises"][paises[0]]["indicadores"][k]["unidad"] for k in orden}
    fig, ax = plt.subplots(figsize=(11, 9))
    fig.subplots_adjust(left=0.2, right=0.88, top=0.84, bottom=0.12)
    for i, p in enumerate(paises):
        x = v["paises"][p]
        for j, k in enumerate(orden):
            ind = x["indicadores"].get(k, {})
            val, pct = ind.get("valor"), ind.get("percentil_hasta_2004")
            if pct is None:
                ax.add_patch(Rectangle((j, i), 1, 1, facecolor="#e6e5e0", edgecolor=SUPERFICIE, lw=2, hatch="///"))
                txt = "sin dato" if val is None else f"{coma(val, 1, False)}\nsin percentil"
                ax.text(j + 0.5, i + 0.5, txt, ha="center", va="center", fontsize=7, color="#6f6e69")
                continue
            ax.add_patch(Rectangle((j, i), 1, 1, facecolor=SECUENCIAL(pct / 100), edgecolor=SUPERFICIE, lw=2))
            tinta = "white" if pct >= 60 else TINTA
            ax.text(j + 0.5, i + 0.36, f"P{pct}", ha="center", va="center", fontsize=9.5, fontweight="bold",
                    color=tinta)
            ax.text(j + 0.5, i + 0.7, f"{coma(val, 1, False)} {unidades[k]}", ha="center", va="center", fontsize=7,
                    color=tinta)
    etiquetas = []
    for p in paises:
        x = v["paises"][p]
        e = p + (" (prueba)" if x["grupo"] == "prueba" else "")
        if x["estado"]["en_recesion"]:
            e += f"  ■ EN RECESIÓN ({x['estado']['meses_desde_entrada']} m)"
        etiquetas.append(e)
    ax.set_xlim(0, len(orden))
    ax.set_ylim(len(paises), 0)
    ax.set_xticks(np.arange(len(orden)) + 0.5, [f"{k}\n{nombres[k]}" for k in orden], fontsize=8)
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(len(paises)) + 0.5, etiquetas, fontsize=8.5)
    for t, p in zip(ax.get_yticklabels(), paises):
        if v["paises"][p]["estado"]["en_recesion"]:
            t.set_color("#a32c2b")
            t.set_fontweight("bold")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    cax = fig.add_axes([0.9, 0.35, 0.018, 0.35])
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=SECUENCIAL, norm=plt.Normalize(0, 100)), cax=cax)
    cb.set_label("percentil frente a 1960-2004 del país", fontsize=8)
    cb.outline.set_visible(False)
    fig.suptitle(f"Termómetro hoy: dónde está cada indicador frente a su historia (datos a {v['fecha_calculo']})",
                 x=0.01, ha="left", fontsize=12.5, fontweight="bold")
    fig.text(0.01, 0.905, "P50 = lo normal del país; P0 = nunca tan bajo antes de 2005; P100 = nunca tan alto. "
             "No es una probabilidad de recesión.", fontsize=9, color=GRIS_TXT)
    nota(fig, f"Fuente: research/int/termometro_vivo_ultimo.json (calculado {v['procedencia']['hora_utc'][:10]}, commit "
         f"{v['procedencia']['commit'][:7]}); percentil = rango frente a los meses 1960-2004 del propio país (≥ 60 meses).\n"
         "Confianza: INFORMATIVO, no es señal de cartera. La probabilidad de ENTRAR no pasó su puerta: solo se muestran "
         "indicadores. En INT-4, curva baja, más curvas invertidas fuera y bolsa a la baja acompañaron más entradas en "
         "recesión.\nNiveles revisados (sin vintages). «Prueba» = país fuera del núcleo del modelo.")
    return guardar(fig, "05_termometro_hoy.png")


def main() -> None:
    for f in (g1_mapa, g2_efectos, g3_trayectorias, g4_termometro, g5_vivo):
        print(f().relative_to(REPO))


if __name__ == "__main__":
    main()
