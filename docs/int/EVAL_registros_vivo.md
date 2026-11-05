---
documento: Evaluación congelada de los cuatro registros prospectivos en vivo (P-E1, P-E1b, P-K1v, INT-11 v3.1)
version: 1.0 (2026-11-05) — código escrito y probado SOLO con datos sintéticos, ANTES de que exista ningún realizado
  (ningún registro tiene todavía una predicción con la ventana cerrada; los de E1 y K1 ni siquiera tienen líneas).
estado: PENDIENTE DE APROBACIÓN las resoluciones de §4 (todas elegidas de la forma más conservadora).
codigo: scripts/eval_e1_vivo.py · scripts/eval_k1_vivo.py · scripts/eval_int11_vivo.py · tests/test_eval_registros_vivo.py
---

# Evaluación de los registros en vivo

## 0. Regla común
- Cada script tiene dos modos:
  - **`--sintetico`**: inventa un registro y unos realizados. Comprueba que recupera una señal plantada y que, sin
    señal, no la encuentra. Es P4 de P-E1 §8.
  - **Real** (por defecto): lee el registro y se queda con las ventanas **cerradas por calendario**. Si no hay
    ninguna, imprime "sin ventanas cerradas", **no conecta al warehouse** (no lee ningún PIB, bolsa ni IPC ≥ 2005) y
    **no escribe nada**. Hoy (2026-11-05) los tres dicen eso.
- Cuando haya ventanas cerradas, el modo real exige el árbol de git limpio y guarda la procedencia: commit y hora UTC.
  Escribe una **revisión descriptiva** (`research/int/eval_*_vivo.json`, que se reescribe en cada corrida).
- Cuando se alcanza el umbral de eventos, escribe **un único fichero de veredicto** (`*_veredicto*.json`). Si ese
  fichero ya existe, se niega a reescribirlo.
- Coeficientes **congelados** y sin reajuste. El script comprueba el sha256 de los modelos y el de cada fila
  registrada. También comprueba que la p recalculada coincide con la registrada.
- `.venv/bin/python -m scripts.eval_{e1,k1,int11}_vivo [--sintetico] [--hoy AAAA-MM-DD]`.
- Tests: `tests/test_eval_registros_vivo.py`, 14 tests, solo con datos sintéticos (≈ 40 s). Para INT-11, la prueba de
  lectura usa un warehouse **inventado** en memoria.

## 1. P-E1 (12 m) y P-E1b (6 m) — `scripts/eval_e1_vivo.py`
- **Registro:** `research/int/e1_vivo.jsonl`. Usa p_L y p_A (12 m), p_L6 y p_A6 (6 m) y las 4 variables. Las filas
  "sin dato" no entran (por ejemplo, CAN sin confianza desde 2026-04).
- **Ventana cerrada (calendario):** el fin del trimestre que contiene M + h, más 75 días de retraso del PIB
  (`termometro.RETRASO_PIB`), tiene que ser ≤ hoy. Además, el fechado tiene que cubrir M y M + h, y M tiene que estar
  en riesgo (`int13.objetivo_e1`). Solo cuentan los orígenes ≥ 2026-11-30.
- **Objetivo realizado:** `int13.entradas_recesion` (el fechado trimestral del termómetro) sobre el PIB OCDE
  `oecd_gdpq_*`, en la última añada del warehouse, con `termometro_vivo._serie`. Después,
  `objetivo_e1(·, h)`: es el mismo objetivo que en el ajuste ≤ 2004. Se usa el PIB revisado a propósito (§2).
- **Métricas** (todas de `src/intl/e1.py`, con `evaluar(..., sin_2020=False)`):
  - **principal:** ΔAUC de A frente a L;
  - Δlog-loss y ΔBrier;
  - calibración de A;
  - **P1** (desplazamiento circular, k ∈ [24, T − 24]; da el p);
  - P2 (países permutados) y P3 (actividad de M − 24);
  - **M4** (quita las entradas en (M, M + 6] a 12 m y en (M, M + 3] a 6 m);
  - AUC con las p registradas;
  - ΔAUC **por episodio** y ΔAUC **sin cada episodio**.
- **Episodios nuevos:** se agrupan las entradas de todos los países posteriores al primer origen. Dos entradas a
  ≤ 6 meses son el mismo episodio (definición de `scripts/e1_potencia.episodios`). Si hay < 12, la salida es
  "DESCRIPTIVO (sin veredicto)".
- **Veredicto (§7), con ≥ 12 episodios:**
  - **REFUTADO** si ΔAUC ≤ 0 o Δlog-loss ≥ 0.
  - **CONFIRMADO** si se cumplen todas: (i) ΔAUC > 0 con p de P1 < 0,05; (ii) Δlog-loss < 0; (iii) pendiente de
    calibración de A en [0,5; 1,5]; (iv) la condición de episodios de §4 (E1-2).
  - En el resto: "ni refutado ni confirmado".
  - M4, P2 y P3 matizan el veredicto, pero no lo cambian.
- **Sintético** (16 países, 36 años, 14 episodios, PIB inventado):

  | caso | 12 m | 6 m |
  |---|---|---|
  | con la actividad 1 dt más baja en los 12 meses previos a cada entrada | ΔAUC +0,27, p P1 0,003, **CONFIRMADO** | ΔAUC +0,25, **CONFIRMADO** |
  | sin señal | ΔAUC −0,05, p P1 0,90, **REFUTADO** | **REFUTADO** |

  Sin señal, la actividad aleatoria con los coeficientes congelados solo añade ruido.

## 2. P-K1v — `scripts/eval_k1_vivo.py`
- **Registro:** `research/int/k1_vivo.jsonl`. Usa p_L y p_K de cada país y año t, para un inicio de crisis en t + 1.
- **Realizado:** y = 1 si t + 1 está en `scripts.k1_vivo.INICIOS_DESDE_2021`. Es la revisión anual de la enmienda 1
  §2, con la fuente y la prioridad de §4. La ventana está cerrada si t + 1 ≤ `INICIOS_REVISADOS_HASTA`.
- **Principal:** filas en riesgo y con dato, **sin** los inicios previos al registro (§4, K1-2).
- **Contraste:**
  - ΔAUC estratificada por país (`int6.auc_estrat`) con las p **registradas**;
  - p del placebo circular: Δ5 desplazado k años, con la misma k en todos los países, k ∈ [6, T − 6], y B1 sin mover
    (`int6.z_placebo`).
- **Descriptivo:**
  - Δlog-loss, ΔBrier, ΔAUC agrupada, calibración de K y bootstrap por años (`int6.boot`);
  - por país;
  - sensibilidades: con los inicios previos, con el episodio de EE. UU. de 2023 contado como inicio (B1 y "en riesgo"
    recalculados) y sin FIN ni NLD (puente con pendiente ≈ 1,5).
- **Umbral:** ≥ 20 inicios nuevos en el principal. Por debajo, solo descriptivo.
- **Sintético** (14 países, 70 años, 5 olas; el registro se hace en julio de t + 1, así que los inicios de enero a
  julio quedan como previos):

  | caso | inicios en el principal | ΔAUC estratificada | p placebo | veredicto |
  |---|---|---|---|---|
  | Δ5 + 15 pp los 3 años previos | 26 (23 previos excluidos) | +0,32 | 0,017 | **CONFIRMADO** |
  | sin señal | — | +0,07 | 0,50 | **NO CONFIRMADO** |

## 3. INT-11 v3.1 — `scripts/eval_int11_vivo.py`
- **Registro:** `research/int/int11_v3_1_vivo/AAAA-MM.json`, con la marca SERIE = `int11_v3_1`. El script comprueba
  el sha256 de cada emisión contra `indice.csv`. Usa `cuantiles_1_99` y `p_inflacion_5.p`.
- **Ventana cerrada:** hoy > fin de la ventana + 3 meses (el retraso de la principal de la bolsa).
- **Realizado:** se lee **una vez** por emisión y se guarda en `research/int/int11_v3_1_realizado/AAAA-MM.json`, que
  no se reescribe nunca (§5.6 de la fuente: AQR revisa la historia). Solo guarda el realizado derivado (A6) y el
  sha256 de las series leídas.
  - **bolsa:** `bolsa_vivo.leer_realizado`. La principal es AQR + FX de fin de mes; si le falta algún mes, se usa el
    respaldo OCDE + dividendo implícito, sin mezclarlas nunca. Se pasa a real con el IPC OCDE "media". JPN "con
    medias" solo como descriptivo (A4).
  - **inflación (K2):** media del IPC de la ventana / media de los 12 meses anteriores − 1 > 5 %.
  - **bonos, letras, vivienda, oro: PENDIENTE.** `INT11_registro_vivo.md` §3 solo esboza su medida ("índices de deuda
    pública o reconstrucción con tipos OCDE; vivienda: precios OCDE + alquiler imputado; oro en moneda local"). No
    fija ni la fuente, ni la construcción, ni el respaldo. **No se inventa:** hace falta un prerregistro de esas medidas
    antes de la primera ventana cerrada (≈ febrero de 2028).
- **Métricas** (bolsa):
  - cobertura p5-p95, con un IC por conglomerados de año de emisión;
  - por debajo y por encima del abanico;
  - PIT (deciles, KS);
  - CRPS aproximado por cuantiles;
  - por país;
  - **sensibilidad sin JPN** (§9 de la fuente).

  K2: Brier de M1 frente a M0 = 26,2 % y BSS con IC por años.

  Principal: emisiones de diciembre. Todas las emisiones, como descriptivo.
- **Sintético** (20 años de emisiones mensuales, 14 países, abanicos N(μ, σ)):

  | caso | cobertura (diciembre) | IC | K2 BSS | IC |
  |---|---|---|---|---|
  | abanico demasiado estrecho (realizado con 1,7 σ) + K2 informativa | 0,71 | [0,65; 0,76] | +0,24 | [0,17; 0,31] |
  | calibrado + K2 sin información | 0,91 | [0,88; 0,94] | −0,19 | — |

  En el primer caso se detectan las dos cosas; en el segundo, ninguna.

## 4. Ambigüedades resueltas (forma conservadora) — **para aprobar**
### P-E1 / P-E1b
| # | ambigüedad | resolución |
|---|---|---|
| E1-1 | Qué es un "episodio nuevo" (§11.2 no lo define) | Se agrupan las entradas de cualquier país; a ≤ 6 meses de la anterior es el mismo episodio (como `e1_potencia`). Solo cuentan los episodios con ≥ 1 fila positiva en la muestra principal evaluable (casos completos, en riesgo, cerrada). El umbral se aplica por separado a 12 m y a 6 m |
| E1-2 | Criterio (iv) "ΔAUC > 0 en la Gran Recesión **y** en la crisis del euro" no tiene análogo en vivo | Se exige ΔAUC > 0 en **los dos episodios nuevos con más eventos** por separado **y** ΔAUC > 0 al quitar **cualquier** episodio. ΔAUC de un episodio = sus positivos frente a todos los negativos |
| E1-3 | §11.7: los choques futuros se excluyen "solo si se declaran ANTES de ver la predicción" | Lista `CHOQUES_DECLARADOS` vacía. Una exclusión solo afecta a los orígenes **registrados después** de la fecha de la declaración. "Con choques" queda como sensibilidad |
| E1-4 | Cuándo está cerrado un origen y con qué añada del PIB | Calendario: fin del trimestre de M + h + 75 días. Además, el fechado tiene que cubrir M y M + h. Se usa la última añada del warehouse (§2: "PIB revisado a propósito"), con `built_at` en la salida. **No** se añade margen extra por revisiones: el veredicto llegará décadas después |
| E1-5 | Predicciones registradas o recalculadas | Se recalculan con las variables registradas y los coeficientes congelados, porque hacen falta para los placebos. Si alguna difiere en > 1e-4 de la registrada, aborta. La AUC con las p registradas se publica al lado |
| E1-6 | Revisiones intermedias frente al veredicto | Antes de 12 episodios: solo descriptivo, sin etiqueta. El veredicto se emite **una vez**, en la primera corrida con ≥ 12 episodios, y su fichero no se reescribe |
| E1-7 | P1 con pocos orígenes | Con T < 48 meses no hay k válida y p = 1 (sin evidencia) |
| E1-8 | Orden de §7 | La refutación se mira primero. Si ΔAUC ≤ 0 o Δlog-loss ≥ 0, el resultado es REFUTADO aunque el resto se cumpla |
| E1-9 | M4 a 6 m | Se quitan las filas con la entrada en (M, M + 3] (P-E1b §3) |

### P-K1v
| # | ambigüedad | resolución |
|---|---|---|
| K1-1 | De dónde sale el realizado | Solo de `INICIOS_DESDE_2021` / `INICIOS_REVISADOS_HASTA` de `scripts/k1_vivo.py` (la revisión anual de la enmienda 1 §2). El script de evaluación no lee ninguna base de crisis |
| K1-2 | "Inicio previo al registro" sin mes conocido. La marca del registro solo ve lo declarado al registrar, y al registrar t los inicios solo están revisados hasta t | Una fila positiva queda **fuera del principal** si tiene la marca, **o** si el mes del inicio (`FECHA_INICIO[(país, año)]`, que hay que declarar) es ≤ el mes del registro, **o** si ese mes no está declarado. Coste: como el registro se hace a mitad de t + 1, cerca de la mitad de los inicios pueden quedar fuera, y el umbral de 20 tarda más |
| K1-3 | El umbral de 20 inicios, ¿cuenta los previos? | No: solo los inicios del principal |
| K1-4 | p del placebo "como INT-6" (INT-6 publicó la z y el p de rangos) | p = **máx**(p de la z, p de rangos). k ∈ [6, T − 6]. Una k cuenta solo con ≥ 10 eventos y ≥ 10 no eventos (como `int6.evaluar`). Coeficientes congelados; B1 no se desplaza |
| K1-5 | Criterio de "confirmado" (§4 solo nombra el contraste) | Se exigen ΔAUC estratificada > 0 con p < 0,05, **y además** Δlog-loss < 0 y pendiente de calibración de K en [0,5; 1,5] (criterios iii y v de INT-6; el iv, por periodos, no se aplica). §4 no define "refutado": la salida es solo CONFIRMADO o NO CONFIRMADO |
| K1-6 | Sensibilidades de §2 | Se añaden tres: con los inicios previos; con USA 2023 como inicio (B1 recalculado y filas 2023-2027 de USA fuera de riesgo); sin FIN ni NLD. Todas son descriptivas |

### INT-11 v3.1
| # | ambigüedad | resolución |
|---|---|---|
| I-1 | Medida realizada en vivo de bonos, letras, vivienda y oro | **PENDIENTE** (§3). Hasta que haya un prerregistro, solo se evalúa la bolsa (y K2) |
| I-2 | Solape de las ventanas (§3: "conglomerados por año, o una emisión por año, la de diciembre, a decidir antes de evaluar") | **Principal = emisiones de diciembre**: ventanas de enero a diciembre, sin solape, como los años naturales de JST. Todas las emisiones van como descriptivo, con IC por conglomerados de año |
| I-3 | Cuándo se lee el realizado | Fin de la ventana + 3 meses (el retraso de la principal). El respaldo solo se usa si en ese momento a la principal le falta algún mes. Lo leído la primera vez queda fijo |
| I-4 | PIT y CRPS (P-INT11 v3 §5 no los calculaba en la fase D) | Se publican como **descriptivos**. PIT por interpolación en los percentiles 1-99; si el realizado cae fuera de p1 o p99, vale 0,005 o 0,995. CRPS ≈ 2 · media de la pérdida de cuantil (colas truncadas) |
| I-5 | Semáforo anual y contraste formal a 10 años | **PENDIENTE.** Las bandas de §3 ([79,7; 96,0] a 5 años, [82,7; 95,0] a 10) son del diseño v2, y no está claro a qué percentil corresponden. Hay que simular las de v3.1 por número de años y fijar la regla del contraste antes de ≈ 2031 (5 años) |
| I-6 | K2 | y = inflación "media" de la ventana > 5 % (equivale a log > log 1,05). p = `p_inflacion_5.p` (pertenencia suave). M0 = 0,262 |
| I-7 | Sensibilidad sin JPN (A4) | Cobertura y PIT de la bolsa en 13 países, al lado de la de 14. JPN "con medias", solo descriptivo |
| I-8 | Emisión alterada o país sin abanico | Si el sha256 no coincide con `indice.csv`, aborta. Los países con "sin datos suficientes" no entran |

## 5. Cuándo se puede correr (aproximado)
| registro | primera ventana cerrada | umbral del veredicto |
|---|---|---|
| E1-12 | origen 2026-11-30 → **≈ 2028-03-15** (PIB 2027T4 + 75 días) | ≥ 12 episodios: **≈ 30-45 años** (3,6 episodios por década → ≈ 2060) |
| E1b-6 | origen 2026-11-30 → **≈ 2027-09-13** (PIB 2027T2 + 75 días) | ≥ 12 episodios: ídem, ≈ 2060 |
| K1v | t = 2026 → inicio en 2027, cerrado cuando `INICIOS_REVISADOS_HASTA` ≥ 2027 (revisión antes de **junio de 2028**). Ojo: para registrar t = 2026 hay que subir antes `INICIOS_REVISADOS_HASTA` a 2026 | ≥ 20 inicios **en el principal**: con una ola cada 15-30 años en 14 países, y con ≈ la mitad de los inicios fuera por K1-2, **varias décadas** (≈ 2070-2090) |
| INT-11 v3.1 | 1.ª emisión prevista el 2026-11-20 (la carpeta aún no existe), ventana 2026-12 → 2027-11 → **2028-03-01**. 1.ª de diciembre (2026-12-20, ventana 2027) → **2028-04-01** | Sin umbral de veredicto: semáforo y contraste a 10 años PENDIENTES (I-5); 10 emisiones de diciembre ≈ 2037-2038 |

## 6. Lo que NO se ha hecho
- No se ha leído ningún dato ≥ 2005 como resultado, ni ningún realizado. Los modos reales se han corrido hoy, y los
  tres dicen "sin ventanas cerradas" sin abrir el warehouse.
- No se ha cambiado ningún registro, modelo congelado ni prerregistro.


## Aprobación (5-nov-2026)
El usuario aprobó las resoluciones de §4 tal como están ("sigue" tras la propuesta). Nota a vigilar: en K1 un inicio sin mes declarado cuenta como previo al registro; al declarar cada inicio anual, anotar el MES para no perderlo del principal.
