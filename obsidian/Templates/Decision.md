---
tipo: decision
fecha: {{date:YYYY-MM-DD}}
estado: propuesta   # propuesta | ejecutada | descartada | cerrada
activo:
direccion:          # sobreponderar | infraponderar | neutral | rebalanceo
tamano_pct_cartera:
senal: "[[Reports/AAAA-MM-DD_signal.json]]"
reporte: "[[Reports/AAAA-MM-DD_semanal]]"
revision: {{date+90d:YYYY-MM-DD}}
---

# Decisión — {{title}}

> Apoyo a la decisión, no asesoramiento. Comprueba el IPS (`config/ips.yaml`) y el coste fiscal antes de ejecutar.

## Contexto (copiado del reporte, sin reinterpretar cifras)
- Régimen / cuadrante:
- Ciclo de deuda corto / largo:
- Semáforo de crédito:
- Liquidez:
- Análogos relevantes:

## Tesis
<!-- Qué creo que va a pasar, en qué horizonte y por qué (mecanismo causal, no solo correlación). -->

## Alternativa descartada
<!-- La mejor opción que NO elijo (incluido "no hacer nada") y por qué pierde. -->

## Criterios de invalidación
<!-- Hechos observables y fechados que me obligan a deshacer la posición. Ej.: "Baa−10a > 3 pp", "Sahm ≥ 0,5", "subyacente 6m > 3,5 %". -->
- [ ]
- [ ]

## Tamaño y riesgo
- Tamaño (% cartera, ≤ 5 % táctico según IPS):
- Pérdida máxima aceptada / stop lógico:
- Probabilidad subjetiva de acierto (%):
- Coste estimado (comisiones + fiscalidad):

## Abogado del diablo
<!-- El mejor argumento en contra. ¿Qué tendría que ser cierto para que me equivoque? -->

## Revisión a 3 meses ({{date+90d:YYYY-MM-DD}})
- ¿Se cumplió la tesis? (sí / no / parcial):
- ¿Se activó algún criterio de invalidación?:
- Resultado vs. alternativa descartada:
- ¿Acerté por las razones correctas? Lección:
