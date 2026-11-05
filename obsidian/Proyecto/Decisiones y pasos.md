# Decisiones y pasos (actualizado 2026-11-05)

Resumen para el usuario. El detalle está en la [[Proyecto/Bitácora]] y en el [[Proyecto/Estado del proyecto]].

## Objetivo inmediato: PRODUCTO a finales de noviembre de 2026
- **Panel web local, solo para mí**: `~/financial_archive/panel/index.html`, regenerado cada domingo con el reporte semanal.
  Abrir con doble clic.
- Pestañas: **Hoy** (régimen, termómetro de recesión, nowcast, liquidez y crédito) · **Escenarios 12 meses** (abanicos por
  país y activo, probabilidades con su acierto medido) · **Qué funciona en cada régimen** (atlas) · **Mi cartera**
  (B0/B1/B1′) · **Estado y avisos**.
- Etiqueta honesta: "validado en el pasado, en seguimiento en vivo". No es asesoramiento.
- Plazos: v1 a mediados de noviembre; versión pulida a final de noviembre.

## Decisiones tomadas el 5-nov-2026
| tema | decisión |
|---|---|
| Ajuste de hiperparámetros | descartado (ya probado el 4-nov en 4 líneas: no ayuda) |
| Datos 2005 en adelante | **Opción A**: NO se gasta el periodo bloqueado ni se reentrena con ≥ 2005; modelos congelados con ≤ 2004 |
| E1 (recesión a 12 m: curva + actividad) | congelado y en registro mensual en vivo |
| E1b (recesión a 6 m) | congelado y en registro mensual en vivo |
| K1v (auge de crédito → crisis bancaria) | congelado y en registro anual en vivo (desde t = 2026) |
| M2 | no aporta (INT-6: signo contrario); solo descriptivo |
| "Golden rules" | crédito, correlaciones por régimen y prima por plazo: sin potencia → no se contrastan; quedan como descriptivo (sección 5e: liquidez y crédito) |
| Motor de escenarios | v3.1 (mejor relleno de datos que faltan) + correlaciones por régimen en "hoy"; registro mensual en vivo |
| Fuente de bolsa en vivo | AQR + tipo de cambio (principal), OCDE + dividendo (respaldo), French (contraste); JPN a fin de mes + análisis sin JPN |
| Medidas en vivo de bonos, letras, vivienda, oro | aprobadas (V1-V8); vivienda con alquiler; EE. UU. alquiler con FRED si la OCDE está parada |
| Umbrales de revisión OCDE | aprobados; recalibrar en mayo de 2027 |
| B1′ (B1 con volatilidad diaria) | implementado en paralelo a B1 |
| Paper trading B0/B1/B1′ | **activado** (ACTIVO creado el 5-nov) |
| Repositorio | público → nunca guardar datos de AQR ni de French, solo resultados derivados |

## Lo que va solo (no hay que hacer nada)
- Datos diarios y reporte semanal (domingo) — con la sección 5f del paper trading.
- Registros mensuales: paper B0/B1/B1′ y E1/E1b (entre el día 3 y el 19), motor v3.1 (entre el 20 y fin de mes).
- Registro anual de K1 (a partir de junio).
- **Solo hace falta encender el Mac con internet 1-2 horas**: un domingo entre el día 3 y el 19 y otro entre el 20 y fin
  de mes. Si algo falla: notificación en el Mac y línea en [[Proyecto/Actualizaciones]].

## Calendario
| cuándo | qué |
|---|---|
| dom 8-nov-2026 | primer reporte semanal con 5e y 5f: revisarlo |
| mediados nov 2026 | panel v1 |
| 22 o 29-nov-2026 | primera emisión del motor v3.1 (encender el Mac) |
| fin nov 2026 | **panel pulido = producto** |
| dom 6-dic-2026 | primeras decisiones B0/B1/B1′ y predicciones E1/E1b (encender el Mac) |
| mayo 2027 | recalibrar umbrales de revisión OCDE |
| antes de junio 2027 (y cada año) | declarar crisis bancarias del año anterior **con su mes** en `scripts/k1_vivo.py` |
| sep 2027 | primera ventana cerrada de E1b (solo descriptivo) |
| mar-abr 2028 | primeras ventanas de E1 y del motor; primer color del semáforo |
| fin 2029 | revisión del paper trading (36 meses: implementación, no ventaja) |
| ≈ 2038 | contraste formal del motor (10 diciembres) |
| ≈ 2060+ | veredictos de E1 y K1 |

## Decisiones abiertas (cuando quiera)
- **Opción B**: gastar el bloqueado una vez y reentrenar con datos hasta 2024 (si algún día quiero usar el motor para
  decidir de verdad).
- Preguntas nuevas: siempre con cálculo de potencia primero.
