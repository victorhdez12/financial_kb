---
documento: INT-13 — XGBoost por "paquetes" de datos relacionados para anticipar recesión, subida de inflación y subida de tipos
version: 1.0 (2026-10-30) — CONGELADO en este commit, ANTES de escribir el código de la corrida
naturaleza: EXPLORATORIO declarado (no confirmatorio). Los datos ≤ 2004 ya se usaron en INT-4, INT-4-ML, INT-8, INT-12
datos: SOLO ≤ 2004-12-31 (src/intl/data.load_dev / load_dev_curado). El periodo ≥ 2005 está BLOQUEADO y no se toca
antecedentes: INT4ML (ML anual no batió al logit), INT-8 (mensual a 3-6 m sin potencia: 11-22 episodios), INT-10 (la
             potencia viene de eventos e información, no de capacidad), INT-12 (boosting peor que lineal; macro empeoró)
---

# INT-13: ¿qué "paquete" de datos ayuda a anticipar qué? (plan exploratorio v1.0)

## 0. Qué es y qué no es (leer primero)
- **Pregunta del usuario:** probar XGBoost con **paquetes pequeños** de datos relacionados (no todos los rasgos juntos)
  para **anticipar** recesiones, subidas de inflación y subidas de tipos, dando **probabilidades con incertidumbre**.
- **Exploratorio:** los datos ≤ 2004 ya están vistos (sabemos que la curva, la difusión y la bolsa funcionan a un año;
  que el ML no batió al logit; que añadir macro empeoró la volatilidad). Nada de lo que salga aquí es "establecido".
  **Cualquier hallazgo necesita prerregistro y confirmación en vivo o en el bloqueado.**
- **Para qué sirve:** (a) ordenar qué paquete aporta algo a qué objetivo **por encima de un logit clásico**, con IC;
  (b) elegir, si los hay, **candidatos** para un prerregistro futuro, con su potencia aproximada.
- **Una sola corrida.** Todo lo de este documento (objetivos, paquetes, modelo base, hiperparámetros, combinación,
  validación, métricas, número de pruebas) queda fijado aquí y **no se cambia después de ver resultados**. El script se
  niega a correr con el árbol sucio o si la salida ya existe. Errores que impidan correr se arreglan antes, con
  `--sintetico`; un error descubierto después se documenta y su arreglo es una versión nueva declarada.

## 1. Datos y retrasos de publicación (todo "as of" en el fin de cada mes t)
Panel mensual OCDE de `src/intl/panel.mensual` (18 países de `src/intl/data.PAISES`, rejilla de fin de mes). Retrasos de
`src/intl/lags.py` (conservadores, v0.2): IP, ventas y paro 75 días; IPC 45; confianza 10; tipos y bolsa 1 día (es
decir: en el fin del mes M se conoce el dato de M − 1). Además:
- **PIB trimestral** (`oecd_gdpq_*`, curado): solo para el objetivo E1 (fechado), nunca como rasgo.
- **Crédito BIS / PIB** (`bis_creditgap_*_ratio`, trimestral): "as of" con 183 días tras el fin del trimestre
  (`termometro.RETRASO_BIS`), viejo > 200 días = ausente.
- **Crédito / PIB de JST** (`panel.anual`, `d_credito_pib`): el año Y se conoce a fin de abril de Y + 1 (120 días).
- **Materias primas** (`aqr_clr_ew_spot_m`, curado; rentabilidad spot mensual, cesta mundial de igual peso): se trata
  como precio de mercado: en el fin de M se usa hasta M − 1.
- **Tipo corto de cada país ("corto")**: UNA fuente por país para todo el periodo (para no crear saltos falsos al
  empalmar): **tipo oficial del BIS** (`bis_cbpol_*`) en 16 países; **letra a 3 m de la OCDE** en FIN e IRL (sin tipo
  oficial BIS). **Curva** = `tipo_10a` − corto (así hay curva desde los años 60 en casi todos; el 10a−3m del panel
  empieza en los 80 en muchos países).
- No hay agregados monetarios ni salarios en las familias permitidas: el paquete "crédito/dinero" es solo crédito y el
  de "precios" no tiene salarios (declarado, no se añaden series).
- Bolsa: DNK y JPN sin rasgos de bolsa OCDE (índices rotos, `termometro.SIN_BOLSA`). Paro interpolado (9 países antes
  de 1998) excluido como ya hace `panel.mensual`. El CLI de la OCDE **no** se usa (filtro de dos lados; no es tiempo real).

**Orígenes:** fines de mes 1960-01 … (2004-12 − h). El objetivo acaba siempre ≤ 2004-12. **Nada ≥ 2005.**

## 2. Objetivos (definición operativa; h en meses)
Mes de referencia M = mes del origen t. Los objetivos se miden con valores **de referencia** (ex post, revisados: es lo
que se quiere anticipar); los rasgos, con lo que se sabía en t.
- **E1-6 y E1-12: entrada en recesión en los próximos h = 6 / 12 meses.** Fechado trimestral validado del termómetro
  (`termometro.fechado_trimestral` sobre el PIB OCDE: entra en el trimestre de la 2.ª caída seguida de la suma de 4
  trimestres; 40/45 recesiones JST cazadas). Mes de entrada = último mes del trimestre de entrada. y = 1 si hay una
  entrada en (M, M + h]. **En riesgo**: filas cuyo trimestre (el que contiene M) NO está en recesión según el fechado
  (ex post; es la definición habitual del conjunto en riesgo, no entra en los rasgos). Aviso (INT-8): este fechado va
  2-3 trimestres por detrás del pico, así que a 6 m se parece a un nowcast.
- **E2: subida de la inflación > 2 pp en 12 meses.** π(m) = log IPC(m) − log IPC(m − 12) (suma de 12 `inflacion_mes`).
  y = 1 si π(M + 12) − π(M) > 0,02. Todas las filas con ambos valores (sin AUS: IPC mensual OCDE desde 2024). La
  variante "cruza el 5 %" **no** se prueba (para no duplicar pruebas).
- **E3: subida del tipo corto ≥ 100 pb en 12 meses.** y = 1 si corto(M + 12) − corto(M) ≥ 1,00 pp (medias mensuales de
  referencia de la fuente única del país, §1).

Total: **4 objetivos** (E1-6, E1-12, E2, E3).

## 3. Paquetes de rasgos (todos "as of"; NaN permitido en XGBoost)
| paquete | rasgos (nombre en el código) | restricción monótona (sobre la prob. de E1 / E2 / E3) |
|---|---|---|
| **P1 curva/tipos** | `curva` (10a − corto), `corto`, `d12_corto`, `tipo_10a`, `d12_10a`, `tipo_real` (corto − 100·π_conocida) | E1: curva −, d12_corto + · E3: tipo_real − · resto 0 |
| **P2 crédito** | `cred_d4` (Δ 4 trim. crédito/PIB BIS, pp), `cred_d20` (Δ 20 trim.), `cred_jst_d1` (Δ anual crédito/PIB JST) | E1: cred_d20 + · resto 0 |
| **P3 actividad** | `ip_yoy`, `d6_ip_yoy`, `ventas_yoy`, `paro_d12`, `sahm` (regla tipo Sahm de INT-8b), `confianza_emp`, `d6_confianza` | E1: ip_yoy −, paro_d12 +, sahm + · E2 y E3: ip_yoy +, paro_d12 − |
| **P4 precios** | `ipc_yoy`, `acel_ipc` (ipc 6 m anualizado − ipc 12 m), `sub_yoy`, `d12_ipc`, `mp_12m`, `mp_3m` (materias primas, log, mundo) | E2: acel_ipc +, mp_12m +, mp_3m + · E3: ipc_yoy +, acel_ipc + · resto 0 |
| **P5 mercados** | `bolsa_real_12m` (bolsa 12 m − ipc), `bolsa_3m`, `vol_12m` (dt de 12 rendimientos mensuales de precio), `caida_24m` (log precio − máximo de 24 m) | E1: bolsa_real_12m −, vol_12m + · resto 0 |
| **P6 contagio/global** | `dif_curva_inv` (% de los otros países con curva < 0), `dif_ip_neg` (% con IP interanual < 0), `glob_d12_corto` (media de los otros), `glob_ipc` y `glob_d12_ipc` (media de los otros), `usa_curva`, `usa_d12_corto` | E1: dif_curva_inv +, dif_ip_neg + · E2: glob_d12_ipc + · E3: glob_d12_corto + · resto 0 |

Difusiones y medias "de los otros": sobre los otros 17 países con dato, solo si hay ≥ 5 con dato. Los rasgos de cada
país usan solo sus valores "as of" (por eso la difusión también es "as of").

## 4. Modelos (fijados aquí; sin búsqueda de hiperparámetros)
- **Clima:** tasa de eventos del entreno (referencia).
- **Base (logit clásico, 2-3 variables por objetivo; estandarizadas con media/dt del entreno; `int4.logit_fit`, sin
  penalizar):**
  - E1-6 / E1-12: `curva`, `d12_corto`.
  - E2: `ipc_yoy`, `d12_ipc`.
  - E3: `ipc_yoy`, `tipo_real`, `ip_yoy`.
  Una fila entra en la muestra de un objetivo **solo si tiene todas las variables de su base** (la misma muestra para
  base, paquetes y combinación; los rasgos de los paquetes pueden faltar).
- **XGBoost como corrección de la base, uno por paquete:** `xgboost` 2.1.1, `xgb.train` con `base_margin` = predictor
  lineal (logit) de la base ajustada en el mismo entreno. Parámetros: `objective=binary:logistic`, `eta=0.05`,
  `max_depth=2`, `min_child_weight=10`, `subsample=0.8`, `colsample_bytree=1.0`, `lambda=5`, `alpha=0`,
  `tree_method=hist`, `max_bin=64`, `num_boost_round=100`, `seed=20261030`, `nthread=1`, restricciones monótonas de la
  tabla §3 (0 en las demás). Los rasgos del paquete entran tal cual (sin la base; la base entra solo por el margen).
- **Combinación (fijada):** media de los paquetes en escala logit = margen base + media de las 6 correcciones
  (margen_k − margen base).

## 5. Validación
- **V1 (principal) — dejar un país fuera (LOCO):** para cada uno de los 18 países, entreno con los otros 17 (todos los
  orígenes 1960 … 2004-12 − h) y predicción del país dejado fuera. Aviso: los otros países de las mismas fechas
  informan del ciclo común (por eso existe V2).
- **V2 — temporal con embargo:** entreno con orígenes cuyo objetivo acaba ≤ 1989-12 (origen ≤ 1989-12 − h), prueba con
  orígenes 1990-01 … 2004-12 − h, todos los países.
- En ambos, la base, el clima y cada XGBoost se ajustan solo con el entreno del pliegue.

## 6. Métricas, incertidumbre y multiplicidad
- **Métricas (sobre las predicciones fuera de muestra apiladas):** log-loss (principal; es la que premia probabilidades
  bien calibradas), Brier y AUC. Contraste de cada modelo frente a su listón: Δ = métrica(modelo) − métrica(listón)
  (log-loss y Brier: negativo = mejor; AUC: positivo = mejor).
- **IC por bloques:** bootstrap de bloques móviles de **24 meses de calendario** (todos los países del mes juntos),
  **1.000 réplicas**, semilla 20261030; IC 95 % percentil; p unilateral ("mejora") = 1 − Φ(−Δ̄ / dt_boot) para la
  log-loss (Φ(Δ̄/dt) en AUC, descriptivo).
- **Calibración (fiabilidad):** intercepto y pendiente de calibración (`int4.calibracion`) y tabla por deciles de
  probabilidad predicha (media predicha frente a frecuencia observada), para clima, base, combinación y cada paquete.
- **Familia de pruebas (número que se registra):** por objetivo, 8 comparaciones de log-loss en V1: base frente a clima,
  6 paquetes frente a base, combinación frente a base → **4 × 8 = 32 pruebas**. **Holm-32** con α = 0,05 sobre los p
  de V1. V2 repite las mismas 32 como comprobación (no se suman: no deciden, filtran).
- **Candidato para prerregistro** (no "establecido") = Holm-32 rechaza en V1 **y** Δlog-loss < 0 en V2 **y** pendiente
  de calibración en V1 entre 0,5 y 1,5. Si nada cumple, se dice así. Lo demás es descriptivo.
- **Potencia aproximada de cada candidato** (y de los 3 mejores, aunque no lo sean): con Δ̄ y su dt bootstrap de V1
  (45 años), potencia de un contraste unilateral α = 0,05 en una muestra nueva de T años: Φ(|Δ̄| / (dt·√(45/T)) − 1,645),
  para T = 20 (bloqueado 2005-2024) con Δ̄ tal cual y con Δ̄/2 (maldición del ganador).
- **Importancias (solo descriptivas):** ganancia media de XGBoost por rasgo (modelo ajustado con todas las filas
  ≤ 2004) y |SHAP| medio (`pred_contribs` de XGBoost, TreeSHAP) sobre las mismas filas.

## 7. Qué NO se hace
- Ningún dato ≥ 2005. Ninguna búsqueda de hiperparámetros, ni otro número de árboles, ni otros paquetes, ni "todos los
  rasgos juntos" (salvo la combinación fijada). Ninguna repetición si un resultado no gusta. La variante "inflación
  cruza el 5 %" no se prueba. Nada pasa al reporte en vivo desde aquí.

## 8. Salidas
`research/int/int13_resultado.{json,md}` (español), entrada en `research/trial_log.md` con el número de pruebas (32 en
V1 + las mismas 32 en V2 como comprobación), código en `src/intl/int13.py` + `scripts/int13_corrida.py`, tests
sintéticos en `tests/test_intl_int13.py`.
