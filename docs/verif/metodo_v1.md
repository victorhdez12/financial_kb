# Verificación a corto plazo — método v1 (CONGELADO)

- **Congelado:** 2026-11-14, antes de la primera predicción en vivo (la primera ventana de emisión es el 2026-12-01).
- **Código:** `src/verif/metodo.py`
- **sha256 del método:** `0c453ee993bb524ac39ea2d1826367a22c797e4c62849a1d536e9f0deede0a8a`
  (cada predicción lo guarda; `tests/test_verif.py` falla si el fichero cambia sin cambiar este documento).
- Cualquier cambio de reglas, ventanas o variables = **método v2**, en otro fichero y otro registro. v1 no se toca.

## Por qué

El nowcast de la pestaña «Hoy» (INT-8b) es un percentil descriptivo: no da una cifra y no se puede comprobar en plazos
útiles. Aquí, en cambio, cada mes se apuesta una cifra concreta, con su intervalo, ANTES de que salga el dato oficial,
y semanas después se ve si se acertó. Es una prueba de honestidad del sistema de datos (vintages, calendario,
puntualidad), no un modelo de régimen.

## Qué se predice (EE. UU., primera publicación)

| variable | serie | qué es el dato | método v1 (fijado de antemano) |
|---|---|---|---|
| IPC general m/m | CPIAUCSL | % m/m del nivel desestacionalizado | MCO de 120 meses: m/m ~ m/m del mes anterior + Δlog % del precio medio mensual del WTI en el mes objetivo (puente con el petróleo, conocido al acabar el mes) |
| IPC subyacente m/m | CPILFESL | % m/m | AR(1) por MCO, 120 meses |
| Nóminas no agrícolas | PAYEMS | variación mensual (miles) | media de las 3 últimas variaciones publicadas |
| Tasa de paro | UNRATE | % | último valor + MCO (120 m) del cambio del paro sobre la Δlog % de la media mensual de peticiones de subsidio (ICSA) del mes objetivo (las semanas ya publicadas) |
| PIB real, avance | GDPC1 | % t/t anualizado | puente MCO (80 trimestres): PIB ~ nóminas + producción industrial, ambas como Δlog anualizada de medias trimestrales con los 3 meses publicados |

GDPNow de la Fed de Atlanta **no** se ingiere en el warehouse (atl_mpt es el *Market Probability Tracker*, no GDPNow),
por eso el PIB usa el puente con indicadores mensuales.

## Reglas comunes

1. **Datos:** solo lo publicado hasta el día anterior a la emisión, vintages ALFRED (`as_of(emisión − 1 día)`). El
   WTI no se revisa y se toma de `obs_latest`.
2. **Ventana:** 120 meses (80 trimestres) que acaban en el periodo anterior al objetivo, sin 2020-03..2021-06
   (2020T1..2021T2) por la covid.
3. **Intervalo del 80 %:** punto ± 1,2816·σ; σ = desviación típica de los residuos de la regresión (para las nóminas,
   raíz del error cuadrático medio de la propia regla en la ventana). Se estima con datos ya revisados, así que puede
   quedarse corto frente a la primera publicación: la cobertura lo dirá.
4. **Benchmarks ingenuos:** «último» = último valor publicado; «media 12 m» = media de los 12 últimos meses (4
   trimestres en el PIB).
5. **Emisión (una sola por variable y periodo):** el primer día en que (a) el periodo objetivo ha terminado, (b) el
   periodo anterior ya está publicado y (c) en el PIB, nóminas e industria del tercer mes del trimestre ya están
   publicadas. Si la regla no se cumple antes de la publicación, no hay predicción. Nunca se recupera a posteriori.
6. **Dato real:** primera publicación (vintage del día en que sale el periodo), transformada igual (m/m, variación,
   t/t anualizado) con ese mismo vintage.
7. **Validez en vivo:** se guarda la hora UTC de emisión; si es igual o posterior a las 12:00 UTC del día de
   publicación (las 8:30 ET son 12:30/13:30 UTC), la predicción queda **anulada** y no puntúa.

## Puntuación

Por variable: error = real − predicción; MAE, RMSE, sesgo; MAE de los dos benchmarks y su cociente («MAE / último» < 1 =
mejor que repetir el último dato); % de meses en que se gana a «último»; **cobertura del 80 %** (lo honesto ≈ 80 %).
El retrospectivo se resume sin los meses covid (y aparte con ellos).

## Registro

- `research/verif/vivo_v1.jsonl` — EN VIVO, append-only (`registro._anadir` se niega a repetir un id). Campos:
  id, variable, periodo, fecha de emisión, hora UTC, punto, inf80/sup80, σ, benchmarks, entradas, corte de datos, sha256.
- `research/verif/retrospectivo_v1.jsonl` — **RETROSPECTIVO, NO EN VIVO**: el mismo método aplicado a cada dato
  publicado desde 2015-01 con los vintages de entonces (pseudo-tiempo-real). Se puede regenerar (`--retro`).
- `research/verif/resumen_v1.json` — derivado; lo lee la pestaña «Verificación» del panel.
- Descarga diaria ligera de vintages recientes de FRED en `~/financial_archive/verif/cache/` (fuera de git). Sin la
  descarga del día no se emite nada (no se sabría si el dato ya salió).

Lo corre `scripts/verif_registrar.py` dentro de `make daily` (segundos, idempotente).

## Lo que esto NO es

- **No gasta el periodo bloqueado (≥ 2005) de los modelos de régimen:** el objetivo (el próximo dato mensual) y el
  método (medias, AR y puentes de una variable) son otros; no se mira ni se ajusta ningún modelo de régimen ni el
  motor INT-11 con estos datos.
- No es una señal de cartera. Los escenarios a 12 meses se verifican en sus propios registros congelados (E1/E1b, K1v,
  INT-11 v3.1, paper B0/B1/B1′).

## Retrospectivo 2015-01 → 2026-10 (calculado el 2026-11-14, tras congelar el método; sin covid)

| variable | n | MAE | MAE / último | MAE / media 12 m | cobertura 80 % |
|---|---|---|---|---|---|
| IPC general m/m | 124 | 0,16 pp | 0,70 | 0,82 | 83 % |
| IPC subyacente m/m | 124 | 0,09 pp | 0,91 | 1,10 | 70 % |
| Nóminas | 126 | 89 mil | 0,89 | 1,06 | 83 % |
| Paro | 125 | 0,11 pp | 1,04 | 0,35 | 85 % |
| PIB avance | 42 | 1,24 pp | 0,75 | 0,90 | 86 % |

Lectura: el puente con el petróleo (IPC general) y el puente del PIB ganan claramente a los dos ingenuos; el subyacente
y las nóminas ganan a «último» pero no a «media 12 m»; el paro no gana a «último» (el paseo aleatorio es muy difícil de
batir). El intervalo del subyacente es estrecho (70 %). **No se retoca nada por esto:** v1 queda como está y se mide en
vivo; una mejora sería v2, con su propio registro.
