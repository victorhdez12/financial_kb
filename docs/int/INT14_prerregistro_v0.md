---
documento: P-DEV-INT14 — prerregistro (BORRADOR) del estudio de eventos A: qué les pasa a los activos tras un shock del petróleo, una crisis bancaria, una subida fuerte del dólar o un pico de volatilidad
version: 0.1-borrador (2026-10-30) — NO congelado. Se congela como v1.0 tras las decisiones D1-D7 de docs/int/INT14_eventos_v0.md §8
parte_de: docs/int/INT14_eventos_v0.md (definiciones, recuentos, potencia: research/int/int14_potencia.json, commit a7bb547, árbol limpio, 2026-10-30T17:38Z)
datos: SOLO ≤ 2004-12-31. El periodo ≥ 2005 está BLOQUEADO y no se toca
---

# P-DEV-INT14 v0.1 (borrador): estudio de eventos de desarrollo

## 0. Naturaleza
- **Descriptivo-confirmatorio**: cuatro contrastes principales con corrección de Holm; todo lo demás es **descriptivo**
  (efecto, IC 90 % por bloques, p de placebo sin titular). Una sola corrida, con puerta (árbol limpio, salida inexistente).
- **Ningún efecto se ha mirado** antes de este documento: las definiciones (v0) y la potencia se fijaron solo con las
  series que definen los eventos y con rentabilidades sintéticas.
- **Potencia esperada:** buena solo si los efectos son grandes (MDE abajo). "No establecido" no significa "no hay efecto".

## 1. Eventos (src/intl/eventos.py, constantes v0; sin cambios tras este documento)
E1 petróleo (Σ12 NOPI36 ≥ 0,20, cadena mundial, sep. 24, retraso 1 m) · E2 crisis bancaria (JST crisisJST, año de
inicio, sep. 5 años) · E3 dólar (Δlog 12 m `TWEXMMTH` ≥ 0,10, 1973-2004, sep. 24, retraso 1 m) · E4 pico de
volatilidad (RV mensual EE. UU. ≥ P90 expansivo, ≥ 60 meses de historia, sep. 12, retraso 0). Un evento solo entra en
un horizonte si **todo** el horizonte cae ≤ 2004-12.

## 2. Resultados (rentabilidades)
- **Mensual** (EE. UU./mundo; nominal; Σ log(1 + r) de t + retraso + 1 a t + retraso + h; h = 1, 3, 6, 12, 24):
  bolsa CRSP total (1926-07), letras, bono 10 a. aproximado (Shiller, bono a la par), oro (≥ 1968-04), materias AQR
  CFP (1926) y CLR (1877, exceso), Banco Mundial energía/metales base/preciosos (1960), precio del petróleo.
- **Anual** (panel JST 17 países, REAL como INT-11; acumulada t+1..t+H, H = 1, 2, 3; el año del evento t se informa
  aparte, descriptivo): bolsa, bonos, letras, vivienda. Años de guerra (1914-18, 1939-45) fuera.
- **Estadístico:** efecto = media de las acumuladas tras los eventos − media de los orígenes sin evento en (t − h, t]
  (del mismo país en el panel). En pp (≈ 100 · log).

## 3. Contrastes principales (familia de 4, Holm, α = 5 %, bilaterales)
| id | evento → activo | muestra | n | MDE 80 % (α 5 % / Holm 1,25 %) | por qué |
|---|---|---|---|---|---|
| **H1** | crisis bancaria → **vivienda real**, t+1..t+3 | panel JST sin guerras | 44 país-evento | 6,9 / 8,2 pp (optimista: autocorrelación; realista ≈ 10-12) | efecto documentado en la literatura y grande; útil para el motor |
| **H2** | crisis bancaria → **bolsa real**, t+1 | panel JST sin guerras | 64 | 8,4 / 10,0 pp | ¿sigue cayendo o rebota tras el año de la crisis? |
| **H3** | pico de volatilidad → **bolsa EE. UU.**, 12 m | 1931-2004 mensual | 16 | 13,0 / 15,5 pp (20 pp si la vol. post-pico es × 1,5) | la pregunta práctica "¿comprar cuando el VIX está alto?" |
| **H4** | shock del petróleo → **bolsa real**, t+1 | panel JST, 12 años globales | 173 país-año (≈ 12 indep.) | 10,6 / 12,6 pp | el efecto del petróleo en la bolsa, en el horizonte del motor |

**Inferencia de cada contraste:** valor p de **placebo** (2.000 juegos de fechas falsas con el mismo número de eventos,
la misma separación mínima y a > h de los eventos verdaderos; en el panel, años falsos por país para H1-H2 y años
globales falsos para H4) → Holm. **IC 90 %** por bootstrap de **bloques de calendario** (mensual: bloques de 60 meses;
panel: conglomerado = episodio global de §3 del diseño para crisis, año para eventos globales). Se declara
"establecido" si p_Holm < 0,05 **y** el IC 90 % no contiene 0.

## 4. Descriptivo (sin titular, sin p ajustada)
Todas las demás combinaciones evento × activo × horizonte (incluidas oro, materias, metales, energía, petróleo), las
sensibilidades de §2 del diseño (umbrales, P95, racha, cadena doméstica, lista de Hamilton, réplica VIX 1990-2004,
crisis 1946-2004) y **todo E3 (dólar, 3 eventos)**: efecto, IC 90 % y p de placebo, con el n al lado.

## 5. Reglas fijas
- Nada se cambia tras ver resultados; una variante nueva exige prerregistro nuevo.
- Si un evento queda con < 5 casos en un horizonte, se informa "n insuficiente" y no se calcula p.
- Los solapes entre eventos (petróleo ~ volatilidad 1971-2000) se declaran; no se separan efectos.
- Semilla 20261030. Salida: research/int/int14_resultado.{json,md}. Registro en el registro de pruebas del proyecto.

## 6. Uso B (anticipar eventos): recomendación
**No** se prerregistra. Con 3-16 eventos independientes solo se demostraría un ΔAUC ≥ 0,18-0,19 (petróleo,
volatilidad) o nada (dólar); para crisis, 0,05-0,13 pero con una pregunta ya muy estudiada y datos ya usados. Si el
usuario lo quiere: INT-14B aparte, solo crisis bancarias, listón = crecimiento del crédito a 5 años, confirmación ≥ 2005.

## 7. Después de la corrida
- Resultados → tabla "qué activo va bien en cada situación" (diseño §6.1) y escenarios condicionados del motor INT-11
  vía `inclinacion` (sin modificar el motor). Los estados de evento dentro del generador (§6.3) son INT-11 v3.
- Confirmación en ≥ 2005 (2007-08, 2011, 2014-15, 2020, 2022) solo con puerta de gasto y prerregistro de confirmación.

## 8. Pendiente para congelar (v1.0)
D1-D7 del diseño; verificar los meses de la lista de Hamilton (2011); decidir si H2 usa t+1 (recomendado) o t+1..t+3.
