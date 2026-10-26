---
tipo: plan_fase
estado: BORRADOR (aprobado con ajustes por el usuario el 2026-10-26; sin backtests de cartera)
actualizado: 2026-10-26
---

# Fase de factores y cartera — plan (borrador)

> [!warning] Estado
> Aprobado con 6 ajustes del usuario (26-oct). Hecho: paso 0, corte técnico y cálculo de potencia. **No se ha hecho ningún backtest de cartera ni se ha cruzado ningún rendimiento con un régimen.** La cartera de referencia (IPS) la elige el usuario.

## 1. Qué usa de la etiqueta, de M0 y del clasificador

- **Señal de las reglas de cartera: el clasificador de reglas** (`src/regime/`), reconstruido con vintages, **también en desarrollo**. Las reglas de cartera **nunca** se prueban con la etiqueta.
- **Etiqueta v1.1, solo ≤ 2004 y solo para describir** cómo se comportan los factores en cada régimen, con shrinkage hacia la media. No mueve pesos.
- **M0, solo como comparación en desarrollo.** Desde 2005 necesitaría la etiqueta de ese periodo (la persistencia es la etiqueta conocida en t − 5) y la caja fuerte lo impide, tanto en backtest como en vivo.

## 2. Datos

- Factores de EE. UU.: Ken French (5 factores desde 1963-07; mercado, tamaño, value y momentum desde 1926-27), AQR (QMJ, BAB, VME, TSMOM). JKP solo como contraste (CC BY-NC).
- Renta fija: curva cupón cero GSW (diaria, 1961-06 →) y GS1/2/5/10/30, TB3MS.
- Divisa: marco alemán (EUR equivalente) del BIS desde 1953 (`bis_xru_de_eur_m`) → EUR/USD sintético antes de 1999; EUR/USD real desde 1999.
- Costes: 5-10 pb por cambio (PLAN). ETFs UCITS: solo existen en el periodo bloqueado → la prueba con instrumentos invertibles en EUR solo cabe ≥ 2005 o en paper trading.
- Licencias: AQR sin redistribución, JKP no comercial → si se comercializa, versión final con French + datos propios.

## 3. Periodos

- **Desarrollo: 1963-07 → 2004-12** (walk-forward con embargo dentro).
- **Sin tocar: 2005-01 →.**
- **Corte técnico (hecho, ajuste 2):** `src/factors/data.py`. `load_dev` es la única entrada de datos de mercado en `src/factors/`; filtra `date ≤ 2004-12-31` en SQL, comprueba la fecha máxima y falla cerrado (`FactorCutoffError`); una serie fuera de las familias permitidas también es un error. Test `tests/test_factor_cutoff.py` (5 en verde): filtro, serie no permitida, `check` con un dato de 2005, ningún otro módulo de `src/factors/` lee el warehouse directamente, y las series reales (French, AQR, GSW, GS10, TB3MS, BIS, EUR/USD) acaban ≤ 2004 aunque en el warehouse lleguen a 2026.

## 4. Contaminación declarada

- **Conocimiento posterior a 2005 (ajuste 6):** la historia de los factores después de 2004 es conocida (crash del momentum en 2009, década perdida del value en los 2010, subida de calidad y beta baja). No se ha leído ningún dato ≥ 2005 en esta fase, pero el diseñador sabe lo que pasó. Defensa: reglas de cartera prerregistradas antes de mirar nada; **P-EVAL-FACT, si llega, se prerregistra antes de mirar nada.**
- **Diseño del clasificador (paso 0b):** ver §5.

## 5. Paso 0 (hecho, sin resultados de cartera)

### 0a. Vintages del clasificador ≤ 2004 (`research/factors/paso0a_vintages.json`)

% de meses con dato que salen de vintages ALFRED:

| entrada | serie | 1950s | 1960s | 1970s | 1980s | 1990s | 2000s |
|---|---|---|---|---|---|---|---|
| indpro_yoy (G) | INDPRO | 100 | 100 | 100 | 100 | 100 | 100 |
| payems_yoy (G) | PAYEMS | 47 | 100 | 100 | 100 | 100 | 100 |
| gdp_qoq_ann (G) | GDPC1 | 0 | 0 | 0 | 0 | 81 | 100 |
| unrate_d12, sahm (G) | UNRATE | 0 | 98 | 100 | 100 | 100 | 100 |
| core_cpi_6m (I) | CPILFESL | 0 | 0 | 0 | 0 | 31 | 100 |
| core_pce_6m (I) | PCEPILFE | 0 | 0 | 0 | 0 | 0 | 87 |
| headline_cpi_6m | CPIAUCSL | 0 | 0 | 75 | 100 | 100 | 100 |
| ppi_yoy | PPIACO | 0 | 0 | 0 | 0 | 31 | 100 |
| m2_yoy | M2SL | — | 0 | 0 | 99 | 100 | 100 |
| tcu / cfnai | TCU / CFNAI | — | 0 | 0 | 0 | 32 / 0 | 100 / 0 |

`vintage_mode`: **"alfred" (todas las entradas del núcleo con vintage) solo desde 2000-08**; antes, "mixed" el 100 % de los meses.

**Lectura:** el eje **G** es casi todo tiempo real desde los 60, salvo el PIB (revisado hasta ~1991). El eje **I** (inflación subyacente) sale de **datos revisados hasta mediados de los 90**: las fechas son honestas (retardos de publicación), pero los niveles incluyen revisiones posteriores. El IPC subyacente se revisa poco (solo factores estacionales); el PCE, más. Hay que tratarlo como sesgo declarado del desarrollo.

### 0b. Cuándo y con qué datos se fijó el clasificador

- `src/regime/classify.py` y `credit.py`: **un único commit** (`9c3f887`, 2026-10-07), sin cambios después. `features.py` y `asof.py`: cambios el 12-oct solo de datos (arreglo del hueco del IPC), sin tocar reglas.
- Umbrales, ventanas e histéresis copiados del "Marco de regímenes" del PLAN (Estratega macro); `docs/phase1_validation.md`: "no están optimizados: no hay ajuste in-sample". La validación de la Fase 1 (contra USREC, incluidos 2008 y 2020) no llevó a cambiar ningún parámetro.
- **Contaminación de diseño: sí, declarada.** Sin ajuste a los datos, pero las reglas se eligieron en 2026 conociendo toda la historia:
  - regla de **Sahm** (0,5 pp): publicada en 2019;
  - umbrales de inflación del **2 % / 2,5 %**: objetivo oficial de la Fed desde 2012; anacrónico para 1963-1995;
  - **NFCI** (desapalancamiento NFCI > 0): índice creado en 2011 y reconstruido hacia atrás;
  - liquidez WALCL − TGA − RRP: concepto posterior a 2008 (no existe ≤ 2002);
  - inversión de la curva (T10Y3M < 0 ≥ 3 m) y Baa: conocidos antes de 2005 (Estrella-Mishkin 1996), sin problema.

## 6. Cálculo de potencia (hecho, `research/factors/potencia_factores.json`)

Solo con estadísticos **incondicionales** de los factores 1963-07 → 2004-12 (σ, curtosis, AR(1)) y con cuántos meses y episodios hay en cada estado del clasificador. **No se ha calculado ninguna media por régimen.** Efecto mínimo detectable (MDE) con 80 % de potencia, bilateral al 5 %; τ = dispersión anualizada de la media entre episodios (escenario).

**Estados del clasificador ≤ 2004 (498 meses):** G↓ 332 meses en 31 rachas; Deflación/recesión 142 m / 32; Estanflación 190 m / 32; Goldilocks 85 m / 21; Reflación 81 m / 19. **Ojo:** el clasificador dice "G↓" el 67 % del tiempo y cambia de cuadrante a menudo (rachas de 4-11 meses): sus "episodios" no son independientes. Por eso se usa también **K = 6 recesiones** (1969-70, 1973-75, 1980, 1981-82, 1990-91, 2001), como pidió el usuario.

| factor (σ anual) | MDE rentabilidad anual, G↓ frente al resto, K = 31 | K = 6, τ = 5 % | K = 6, τ = 10 % | MDE Sharpe (K = 6, τ = 10 %) | MDE cociente de volatilidad |
|---|---|---|---|---|---|
| mercado (15,6 %) | 15 pp | 16 pp | 19 pp | 1,2 | 1,32 |
| value HML (9,8 %) | 10,5 pp | 12 pp | 15,5 pp | 1,6 | 1,35 |
| momentum (14,1 %) | 13 pp | 14 pp | 17 pp | 1,2 | 1,43 |
| calidad QMJ (7,4 %) | 7,7 pp | 9,6 pp | 14 pp | 1,9 | 1,41 |
| beta baja BAB (12 %) | 12,7 pp | 14 pp | 17 pp | 1,4 | 1,47 |
| rentabilidad RMW / inversión CMA | 8,8 / 7,7 pp | 10,5 / 9,6 pp | 14,4 / 13,8 pp | 1,8 / 1,9 | 1,8 / 1,31 |

En los cuadrantes pequeños (Goldilocks, Reflación) el MDE de rentabilidad sube a 10-19 pp y el de Sharpe a 1,1-1,4 ya con K de rachas.

**Lectura:**
- Para distinguir del ruido una diferencia de **rentabilidad media** por régimen hace falta una diferencia de **≥ 10-19 pp al año**, o de **≥ 1-2 de Sharpe**. Eso es enorme: no se puede esperar demostrar "ganar más" por régimen.
- **Caída máxima por régimen:** con 6 recesiones es estadísticamente una muestra de 6; no se puede contrastar como tal. Se mide a través de la volatilidad y de la caída en cada recesión, contada por episodios.
- La **volatilidad** se mide mucho mejor: basta un cociente de ~1,3-1,5 entre estados (cota optimista: no corrige la agrupación de la volatilidad).
- **Conclusión (ajuste 4):** el objetivo de la fase pasa a ser **reducir caídas y volatilidad frente a la cartera de referencia**, no ganar más. El criterio de éxito tendrá que definirse sobre volatilidad o caídas (por episodio), con su propio cálculo de potencia en el prerregistro.

## 7. Cartera de referencia (IPS): opciones para que elija el usuario (no elegida)

Inversor en EUR, España; vehículos: fondos indexados traspasables (sin peaje fiscal al cambiar) o ETFs UCITS. El tramo táctico se mueve dentro de bandas alrededor de la referencia (PLAN: máx. un cambio al mes).

| parámetro | A. Conservadora | B. Equilibrada | C. Crecimiento |
|---|---|---|---|
| horizonte | 5-7 años | 10 años | 15+ años |
| renta variable / renta fija | 40 / 60 | 60 / 40 | 80 / 20 |
| renta variable | global (MSCI World/ACWI) | global | global |
| renta fija | gobierno euro / agregado global cubierto, duración 5-7 | ídem | ídem |
| cobertura de divisa | RF 100 % cubierta; RV 50 % cubierta | RF 100 %; RV sin cubrir | RF 100 %; RV sin cubrir |
| caída máxima tolerable | −15 % | −25 % | −35 / −40 % |
| desviación táctica máxima | ± 10 pp de RV | ± 10 pp | ± 15 pp |
| costes | TER ≤ 0,20 %; 5-10 pb por cambio | ídem | ídem |
| rebalanceo | anual o bandas ± 5 pp | ídem | ídem |

Pendiente del usuario: elegir (o ajustar) una. Con un objetivo de reducir caídas, la opción B o C es donde un tramo táctico tiene más margen; la A ya tiene poca renta variable que reducir.

## 8. Cómo se evaluaría sin gastar el periodo bloqueado de la etiqueta

1. **Desarrollo ≤ 2004:** walk-forward con embargo, todas las pruebas en el registro, Deflated Sharpe, placebos con el régimen del clasificador barajado en bloques. Listón: la cartera de referencia, después de costes.
2. **≥ 2005, una sola vez:** P-EVAL-FACT, prerregistrado antes de mirar nada, con la señal del clasificador (sin etiqueta: no abre la caja fuerte). Gasta el ≥ 2005 **para la fase de factores**; se declara.
3. **Paper trading** desde que se apruebe la regla (la única muestra limpia de verdad).

## 9. Siguiente (pendiente de aprobación)

Elegir IPS → criterio de éxito sobre volatilidad/caídas con su potencia → descripción de factores por régimen con la etiqueta ≤ 2004 (shrinkage) → reglas de cartera prerregistradas → backtest de desarrollo con el clasificador.
