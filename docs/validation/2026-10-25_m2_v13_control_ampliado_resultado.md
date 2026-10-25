---
documento: resultado del control sintético ampliado de M2 v1.3 (protocolo prerregistrado, da18753)
fecha: 2026-10-25
objeto: m2_structural_spec.md v1.3 (d8eb113), implementación 90f408f
datos: solo sintéticos (tests/m2_synth.py). Sin etiqueta, sin base PIT, sin niveles reales. Nada registrado en harness_runs ni en el trial log
salida: research/validation/m2_v13_control_ampliado/ (A_<semilla>.json, B_<semilla>.json, resumen.json, R0_*.json, logs/)
estado: cifras calculadas a partir de resumen.json por el Constructor; el veredicto formal del Validador queda pendiente de su ratificación
---

# Resultado del control ampliado de M2 v1.3

## 1. Réplica de control (R0)

Las semillas 3, 7, 11 y 21 reproducen las coberturas del control de 4 semillas (`research/trials/m2/controles_m2_v13.json`)
con diferencia < 5e-11. R0 ✅ (`D3_max_dif_replica` = 0,0).

## 2. Brazo principal A (semillas 1001–1040, generador hasta 2004-12)

| estadístico | valor |
|---|---|
| media de la cobertura del 80 % (c̄) | **0,8099** |
| sd entre semillas (ddof 1) | 0,0491 |
| IC 95 % entre semillas (t₀,₉₇₅;₃₉ = 2,0227) | **[0,7942; 0,8256]** |
| semillas con cobertura en [0,75; 0,85] | 28 / 40 (**70 %**) |
| sin convergencia | 0 |

**Criterio principal (protocolo §3): el IC entero queda dentro de [0,75; 0,85] → CUMPLE.**
**Criterio secundario (≥ 0,70 de semillas en rango) → CUMPLE** (justo en el umbral).

## 3. Brazo diagnóstico B (generador hasta 2009-12)

| estadístico | valor |
|---|---|
| media de la cobertura del 80 % | 0,8011 |
| IC 95 % entre semillas | [0,7844; 0,8178] |
| semillas en rango | 24 / 40 (60 %) |

Principal: cumple. Secundario: **no cumple** (60 % < 70 %). Informativo, sin criterio de decisión.

## 4. Lectura

- El límite superior del IC de A queda a 2,4 pp del techo del rango (0,8256 frente a 0,85), dentro de él.
  Eso no equivale a "sin sesgo apreciable": ver la sección 7.
- Las cuatro semillas del control original (3/7/11/21) cayeron por encima de la media de A (0,845 frente a
  0,810). Con n = 4 eso no basta para decir nada: el control de 4 semillas tenía poca potencia para su criterio.
  Su fallo queda declarado tal cual, como pedía la spec.
- Con la media observada de A, la probabilidad de que 4 semillas caigan todas en [0,75; 0,85] es ≈ 0,22
  (`p_4_semillas_en_rango_si_media_observada` = 0,217). Eso explica por qué el control de 4 semillas era un mal criterio.
- Calibración de la varianza (z²) e intervalos del 50 % y 95 % están en `resumen.json` (campos `A.*` y `R0_por_semilla`).
  No se usaron como criterio.

## 5. Consecuencia prevista por el protocolo (§5, fila 1)

M2 v1.3 puede usarse tal cual para `m2_long` (corrida 6a, desarrollo ≤ 2004). El control de 4 semillas queda
declarado como no superado y su regla se considera demasiado estricta para 4 semillas. No se cambia la spec.

## 6. Pendiente

- Veredicto formal del Validador independiente sobre este documento.
- Decisión del usuario para lanzar `m2_long` (usa la etiqueta de desarrollo ≤ 2004).

## 7. Reservas del Validador (revisión en la nube, solo lectura, 25-oct)

Informe de un agente remoto que actuó como Validador sobre el repo público (commit `73cca17`). Veredicto: **CUMPLE CON RESERVA**.
Las cifras de las secciones 2 y 3 coinciden con las recalculadas desde los 40 `A_<semilla>.json`.

- **Verdad truncada en A (alta).** En A la muestra acaba en 2004-12, así que para T ≥ 2000-01 la verdad (mediana centrada ±60 meses,
  recortada al final) queda más cerca del nowcast. Cobertura 2000-04 en A = 0,853 frente a 0,800 en 1980-99; z² 2000-04 = 0,81.
  Es la predicción H-a y no se discutía aquí. B (generador hasta 2009-12), que es lo que pide el texto de la spec §6, da 2000-04 = 0,808
  y secundario 60 % (no cumple).
- **Margen del secundario (media).** 28/40 cumple el 70 %; con 27/40 no. Margen de una semilla.
- **Gobernanza (alta).** La spec §9 dice que `m2_long` sigue parado hasta decisión del usuario. El protocolo §5 dice que puede correr.
- **Preregistro (media).** El script se commiteó junto con los resultados (`89a4e69`). No hay hash previo al primer resultado.
- **H-b no confirmada en A (media).** La sobrecobertura no es mayor en 1980-89 que en 1990-99 (0,789 frente a 0,810).
- **Contrafactual omitido (baja).** Con 10 semillas, 0,773 [0,733; 0,813] frente a 0,796 de la v1.3 (`resumen.json`, `D3_contrafactual`).
- **Independencia (baja).** El mismo rol escribió el protocolo y valida el resultado.
- **Control de 4 semillas.** Sigue declarado como no superado; la regla era demasiado estricta (con un M2 calibrado, ≈ 0,23 de probabilidad de pasarla).

Opciones que quedan para el usuario: (a) aceptar A según el protocolo y anotar estas reservas en la spec §9; (b) antes de `m2_long`,
un control nuevo preregistrado con la verdad construida con datos completos (generador hasta ≥ 2009-12), con hash del script fijado antes.
