---
documento: P-K1v — auge de crédito → inicio de crisis bancaria al año siguiente: registro prospectivo en vivo
version: 1.0 (congelado 2026-11-05, antes del ajuste; petición del usuario de tener en cuenta el crédito)
estado: CONGELADO. Nace de INT-6 K1 (docs/int/INT6_prerregistro_v1.md §K1; resultado research/int/int6_resultado.md):
  ΔAUC estratificada +0,113 [−0,007; +0,231], z placebo 3,15, NO establecido (criterio i). El bloqueado no tiene
  potencia para K1 (10 crisis en 8 años, docs/int/INT6 §potencia) → confirmación solo en vivo.
---

# P-K1v: ¿el auge de crédito anticipa crisis bancarias? (registro en vivo)

## 1. Modelos (congelados con ≤ 2004, sin reajuste)
- **Listón L:** logit(B1), B1 = log(1 + años desde el último inicio de crisis ≤ t) (INT-6).
- **Candidato K:** logit(B1, x), x = Δ5 del crédito bancario al sector privado no financiero en pp del PIB.
- Ajuste único, agrupado, sin estandarizar (como `src/intl/int6.congelado`), con las filas de K1 de INT-6 (14 países del
  núcleo, 1871-2004, sin guerras, sin hiperinflación, sin inicio en t − 4 … t): se exige reproducir 1.137 filas / 49
  eventos. Coeficientes con sha256 en `research/int/k1_modelos.json`. Si el coeficiente de x sale ≤ 0, se para.

## 2. Datos en vivo (declarado: cambio de fuente)
- **x en vivo = BIS** `bis_tc_XX_pb_m` (crédito de bancos al sector privado no financiero, % del PIB), valor del
  4.º trimestre de t menos el del 4.º trimestre de t − 5. JST (`tloans`/`gdp`) termina en 2020 y no se actualiza.
- **Puente comprobado antes de congelar** (solo ≤ 2004, sin cruzar con crisis): correlación del Δ5 JST frente al Δ5 BIS
  0,72-1,00 por país (mediana ≈ 0,94), pendiente 0,80-1,53 (mediana ≈ 0,97). Se usa el BIS tal cual con los
  coeficientes de JST (sin reescalar). Sensibilidad declarada: FIN y NLD (pendiente ≈ 1,5).
- **"As of":** una predicción para el año t + 1 solo cuando el dato del 4.º trimestre de t está publicado.
- **B1 en vivo:** inicios de crisis de `crisisjst` (JST) hasta 2020 — **se lee el periodo 2005-2020 de la cronología de
  crisis solo como entrada de B1**, lo que contamina para siempre una evaluación de K1 en el bloqueado (que ya era
  inalcanzable). Desde 2021: ningún inicio declarado en los 14 países hasta 2025 (el episodio de bancos regionales de
  EE. UU. de 2023 NO cuenta como inicio sistémico; sensibilidad: contarlo).

## 3. Registro
- Orígenes t ≥ 2026 (predicción del inicio de crisis en 2027 en adelante). Una línea por país y año en
  `research/int/k1_vivo.jsonl` (p_L, p_K, x, B1, procedencia). No se muestra como probabilidad en el reporte.
- Filas no en riesgo (inicio en t − 4 … t) se registran como "no en riesgo".

## 4. Objetivo futuro y evaluación (fijado ahora)
- **Inicio de crisis bancaria sistémica en t + 1** según la próxima versión de JST (`crisisjst`); si JST no se
  actualiza, Laeven-Valencia (última actualización del FMI) y, para Europa, la base de crisis del BCE/JERS; en
  desacuerdo, prima JST > Laeven-Valencia > BCE. Se fecha ex post, sin mirar las predicciones.
- **Contraste único:** ΔAUC estratificada por país de K frente a L sobre las predicciones registradas; p del placebo
  circular (como INT-6). **Solo cuando haya ≥ 20 inicios de crisis nuevos** (con una ola cada 15-30 años en los 14
  países, décadas). Antes: solo descriptivo. Declarado: no dará respuesta en un horizonte útil; es barato y deja la
  pregunta abierta de forma honesta.
