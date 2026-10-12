# Revisión Fase 1 — PM senior + abogado del diablo (2026-10-07)

## Veredicto: el reporte aún no sirve para decidir
- Etiqueta engañosa: "Deflación/recesión" con G=−0,06, CPI a/a 3,7 %, PPI a/a 9,85 % (p89), core 6m 2,66 % (>2,5), I=+0,35z. G↓ es el estado por defecto (63,5 % de meses de expansión).
- Análogos contradicen el régimen (3/5 Goldilocks); oro 0 % en 1955/59/64 (precio fijo); eventos cercanos irrelevantes.
- "Lectura" por plantilla; la fila 2026-10 repite septiembre.

## Estructura ideal del reporte
1. Resumen 3 líneas + cambios vs semana anterior. 2. Probabilidades por cuadrante + distancia a frontera. 3. Posicionamiento: base All Weather → rango por clase de activo (desvío pp, límite IPS). 4. Disparadores de invalidación con umbral y fecha del próximo dato. 5. Calendario de datos. 6. Confianza explícita (N episodios, vintage, acuerdo entre modelos). 7. Visión EUR. 8. Coste de esperar vs actuar.

## 10 modos de fallo → mitigación
1. Rotación de régimen (cambia el 21 % de los meses; 7 cambios en 24m) → histéresis |G|<0,15, 2-3 meses de confirmación, probabilidades HMM.
2. Costes → bandas ±5 pp, ≤1 cambio/mes, operar solo si EV > costes + impuestos.
3. Pocos episodios → shrinkage a la base, tamaño ∝ N_eff.
4. Sobreajuste narrativo → reglas pre-registradas (hash + fecha); LLM solo explica.
5. Datos revisados (608/922 meses 'mixed') → backtest solo meses ALFRED y medir diferencia.
6. Sesgo EE. UU. → capa EUR.
7. Series mal definidas (oro pre-1971, HY OAS 3 años, NFCI años 70) → máscaras de validez.
8. Eventos curados → filtrar por país/gravedad; --check-urls en CI.
9. LLM falla en silencio → alerta visible, modelo con versión fijada.
10. Umbrales no validados → walk-forward + Brier Skill Score.

## Inversor en España
- Modelar en EUR: RV global sin cubrir, renta fija cubierta; coste de cobertura (€STR vs SOFR).
- Faltan: HICP subyacente, BCE, Bund, BTP/Bono-Bund, PMI EZ, crédito SDW, €STR.
- Fiscalidad: fondos traspasables para el núcleo, ETF UCITS acumulación, regla 2 meses, base del ahorro 19-30 %, 720/721; rentabilidad neta tras impuestos por cambio.

## Paso a dinero real
≥ 6-12 meses de paper trading pre-registrado; BSS > 0 vs persistencia; satélite > All Weather estático neto (TE ≤ 3 %, sin violar drawdown IPS); ≤ 4 cambios/año; 0 incidencias de datos; empezar con satélite ≤ 5 %.

## 5 cosas antes de añadir más datos
1. Probabilidades + histéresis, medir rotación. 2. Base All Weather EUR + regla señal→peso con bandas. 3. Backtest walk-forward (ALFRED) vs estático y persistencia, con costes/impuestos. 4. Limpiar análogos (máscara oro, filtro eventos, N_eff). 5. Capa EUR mínima.
