---
tipo: resumen visual
version: 1.0
actualizado: 2026-10-29
estado: SOLO dibuja resultados ya calculados (ningún contraste nuevo; ningún dato JST ≥ 2005)
---

# Atlas visual

Las tablas de [[Proyecto/Atlas regímenes]] en cinco gráficas. Código: `scripts/atlas_graficas.py` (`.venv/bin/python -m scripts.atlas_graficas`); originales en `research/int/graficas/`, copia aquí en `Proyecto/img/atlas/`. Cada gráfica lleva al pie su fuente y su confianza.

## 1. Qué hace cada activo en cada régimen
![[Proyecto/img/atlas/01_mapa_activo_regimen.png]]

Rojo = ese activo rindió peor de lo normal en ese régimen; azul = mejor. Lo más claro: con inflación alta los bonos y las letras pierden mucho, y la bolsa sufre en la estanflación. **Cuánto fiarse:** mira los puntos de cada celda (●●● establecido, ●● probable, ○ no establecido); los cuadros grises no se contrastaron, y todo usa una etiqueta *ex post* (lo que pasó, no lo que se sabía en el momento).

## 2. Los efectos principales y cuánto queda a tiempo
![[Proyecto/img/atlas/02_efectos_ic_ex_post_vs_a_tiempo.png]]

Cada barra es un intervalo de confianza: si cruza el 0, el efecto podría ser nulo. En azul, lo que pasó; en naranja y verde, lo que habrías visto usando solo datos ya publicados (con uno y con dos años de retraso). **Cuánto fiarse:** con lo que se sabe a tiempo los efectos encogen; solo «bolsa en estanflación observada» pasa la prueba estricta, y con pocos casos, casi todos de los años 70. La ventaja de los bonos en la desinflación desaparece.

## 3. Bolsa, bonos y letras alrededor de una recesión
![[Proyecto/img/atlas/03_trayectorias_recesiones.png]]

Media de unas 230 recesiones: la bolsa y los bonos ya caen en el año del pico, la bolsa tiene su peor año justo antes del fondo y después rebota; las letras casi no se mueven. La banda gris es lo que sale con fechas al azar. **Cuánto fiarse:** es descriptivo (sin contraste) y con datos anuales; el momento exacto del fondo no se distingue del azar.

## 4. Termómetro: aciertos y puerta mensual
![[Proyecto/img/atlas/04_termometro_auc_y_puerta.png]]

Izquierda: el modelo ordena los años de riesgo bastante mejor que el listón, tanto para entrar como para salir de recesión (AUC ≈ 0,73 y 0,77 frente a ≈ 0,53 y 0,58). Derecha: para usarlo cada mes, la versión mensual tiene que parecerse a la anual (dentro del recuadro); la salida (T2) entra, la entrada (T1) se queda justo fuera. **Cuánto fiarse:** entrar es un resultado sólido, salir uno justo; T2 pasa la puerta con solo 31 filas, así que su probabilidad se lee como banda, no como cifra exacta.

## 5. Termómetro hoy
![[Proyecto/img/atlas/05_termometro_hoy.png]]

Cada cuadro dice dónde está hoy un indicador frente a la historia 1960-2004 de ese país (P50 = lo normal). Hoy las curvas están en zona normal, casi ningún país tiene la curva invertida y la bolsa viene de un buen año; Irlanda (país de prueba) figura en recesión. **Cuánto fiarse:** es informativo, no una señal de cartera ni una probabilidad: la probabilidad de entrar no pasó su puerta y los datos son niveles revisados.

Ver también: [[Proyecto/Estado del proyecto]] · [[Proyecto/Bitácora]]
