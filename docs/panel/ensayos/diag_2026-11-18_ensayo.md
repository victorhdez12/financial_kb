---
tipo: diagnostico
fecha_evento: 2026-11-18
generado: 2026-11-19T08:42
prompt: v1
paquete: /Users/victorhdez12/financial_archive/diag/paquetes/2026-11-18/paquete.json
duracion_s: 68.8
coste_usd_estimado: 0.4326028
disparadores:
  - "ninguno (ensayo pedido a mano)"
---

> [!warning] Explicación posterior; no es señal de compra o venta.
> Las explicaciones «ex post» siempre suenan convincentes: aquí se separan los datos medidos (sección 1) de las hipótesis inferidas (sección 2).

# Ensayo 2026-11-18: caída de UnitedHealth, oro y mineras con la bolsa amplia casi plana

## 1. Qué ha pasado (datos)
- **Disparador:** ninguno. Es un ensayo forzado (`forzado: true`, sin disparos ni tipos). No saltó ninguna regla fija.
- **Mayor movimiento:** UnitedHealth (UNH) −10,21 % (−6,57 σ; percentil 0,3 de su historia), dato del 2026-11-18. Lleva −13,16 % en 5 sesiones.
- **Oro y mineras:** oro (ETF GLD) −3,2 % (−2,17 σ); Newmont −6,05 % (−2,4 σ); GDX −5,97 % (−2,12 σ). Todo del 2026-11-18. El oro lleva −6,57 % en 5 sesiones y está −31,2 % bajo su máximo de 52 semanas.
- **Energía:** XLE −3,27 % (−2,18 σ); WTI (CL=F) −3,2 % (−1,13 σ); Brent −1,28 % (−0,43 σ). La caída del WTI es mucho mayor que la del Brent. El paquete avisa de saltos en los cambios de contrato del WTI; si hubo uno ese día no está en el paquete.
- **Bolsa amplia:** S&P 500 (SPY) −0,31 % (−0,32 σ); Nasdaq 100 (QQQ) +0,39 % (+0,25 σ). Europa: VGK (sustituto del Euro Stoxx 50, en dólares) −1,29 % (−1,36 σ). Dólar frente al euro (sustituto del DXY) +0,19 % (+0,61 σ), así que el efecto divisa en VGK es pequeño.
- **Amplitud:** concentrada / mixta. De 10 sectores de EE. UU., 6 bajan y 4 suben. Las caídas grandes son energía (−2,18 σ) y salud (XLV −2,2 %, −1,98 σ); tecnología, comunicaciones, eléctricas e inmobiliario suben poco.
- **Agro/fitosanitarios:** Corteva −5,22 % (−1,19 σ; −31,14 % en 5 sesiones); FMC −6,21 % (−0,91 σ); MOO −1,06 % (−1,08 σ). Bayer −1,51 % (dato del 2026-11-17, 1 día de retraso).
- **Bonos, crédito y volatilidad:** TLT +0,84 % (+1,25 σ), dato del 2026-11-18. Con 1 día de retraso (dato del 2026-11-17): Tesoro 10 a en 5,10 % (−2 pb), tipo real 10 a en 2,89 % (−3 pb), diferencial high yield en 3,43 (+9 pb, +1,33 σ), VIX en 25,46 (+11,13 %, +1,02 σ; +30,83 % en 5 sesiones). El crédito y el VIX del día 18 no están en el paquete.
- **Correlaciones a 20 sesiones fuera de lo habitual:** oro–bolsa 0,32 (mediana desde 2007: 0,09; percentil 71). Oro–tipo real −0,05 (mediana −0,35; percentil 79): el oro se mueve hoy menos ligado a los tipos reales de lo normal. Bolsa–bonos largos −0,09 (mediana −0,33).
- **Calendario:** producción industrial y utilización de capacidad publicadas el 2026-11-17 (periodo octubre). Actas del FOMC (reunión del 27-28 de octubre) publicadas el 2026-11-18 a las 19:00 UTC. Informe de Estabilidad Financiera del BCE el 2026-11-18 a las 09:00 UTC. El calendario completo de bancos centrales no está en el paquete.

## 2. Hipótesis de causa (de más a menos probable)

### H1. Noticia propia de UnitedHealth que arrastra al sector salud — confianza: media
- **A favor:** UNH cae −6,57 σ y el S&P solo −0,32 σ: el golpe es muy concentrado. XLV (−1,98 σ) cae mucho menos que UNH, compatible con un arrastre por su peso en el ETF. Es una caída de las más grandes de la historia de UNH (percentil 0,3).
- **En contra:** la causa concreta no está en el paquete. Ningún titular del paquete habla de UNH ni de aseguradoras de salud. No se puede separar cuánto de la caída de XLV es UNH y cuánto es sector.
- **Qué la confirmaría o descartaría en los próximos días:** si UNH no recupera y XLV se estabiliza, apunta a algo propio de la empresa. Si XLV sigue cayendo sin UNH, el problema sería más sectorial.

### H2. Venta concentrada en materias primas (oro, mineras y petróleo) — confianza: media
- **A favor:** oro −2,17 σ, mineras −2,1 a −2,4 σ, XLE −2,18 σ y WTI −3,2 % el mismo día. El oro ya venía cayendo (−6,57 % en 5 sesiones; −31,2 % desde máximos). Las mineras caen casi el doble que el oro, como suele pasar cuando baja el metal.
- **En contra:** no hay causa clara en los datos. El dólar sube solo +0,19 % y el tipo real 10 a bajó 3 pb (dato del 17-nov), justo lo contrario de lo que suele presionar al oro. El posicionamiento especulativo en oro no era extremo (neto 27,8 % del interés abierto, percentil 61 histórico; COT del 2026-11-10, anterior al evento). En el petróleo, el Brent cae mucho menos que el WTI: parte del movimiento del WTI podría ser un cambio de contrato (no está en el paquete).
- **Qué la confirmaría o descartaría en los próximos días:** si el oro y GDX siguen bajando a 5 y 20 sesiones, la venta tendría continuidad. Un rebote rápido la acercaría a H4.

### H3. Aversión al riesgo moderada (Europa, crédito, volatilidad), quizá con las actas del FOMC o el informe de estabilidad del BCE de fondo — confianza: baja
- **A favor:** VGK −1,36 σ; TLT sube +1,25 σ (refugio en bonos largos); VIX +11,13 % y high yield +9 pb el día anterior (17-nov). El BCE publicó el 18-nov un comunicado sobre riesgos por valoraciones de IA, desequilibrios fiscales y tensiones geoeconómicas. Las actas del FOMC salieron el mismo día.
- **En contra:** el S&P apenas cae (−0,31 %) y el Nasdaq sube (+0,39 %): no es una huida general. La amplitud es mixta (6 de 10 sectores bajan). El VIX y el crédito del día 18 no están en el paquete. El contenido de las actas del FOMC no está en el paquete y no se sabe qué peso tuvieron.
- **Qué la confirmaría o descartaría en los próximos días:** si el diferencial high yield y el VIX siguen subiendo, ganaría peso. Si bajan, se descarta.

### H4. Ruido / sin causa común identificable — confianza: media
- **A favor:** no saltó ningún disparador; el día es un ensayo forzado. Fuera de UNH, ningún movimiento llega a −2,5 σ. Los movimientos grandes están en activos de alta volatilidad (GDX 52 %, Newmont 49,3 %, WTI 57,7 % anual). Varios grupos (UNH, oro, petróleo, agro) pueden tener causas distintas sin relación entre sí.
- **En contra:** la caída a la vez de oro, mineras, energía y Europa es más amplia de lo que sugiere el puro azar; el día cumple la regla de episodios oro + Europa.
- **Qué la confirmaría o descartaría en los próximos días:** si oro y S&P recuperan a 20 sesiones, como pasó de mediana en episodios parecidos, cuadra con ruido.

## 3. Qué dicen los modelos del proyecto (sin re-correr)
- **Régimen** (mes 2026-11-30, corte 2026-11-19): Goldilocks; crédito verde; liquidez neutral; deuda en expansión temprana. Igual que el mes anterior. Es mensual y va por detrás del mercado: un día no cambia un régimen.
- **Signal semanal** (asof 2026-11-17): crédito verde, liquidez escasa, nowcast agregado bajo. Ojo: la liquidez sale «escasa» aquí y «neutral» en el régimen mensual.
- **INT-11** (emitido el 2026-11-05, datos hasta el 2026-10-31, ventana dic-2026 a nov-2027): régimen dominante sobrecalentamiento (peso 0,6175; expansión 0,3825). Oro real a 12 meses: p5 −26,0 %, p50 −3,0 %, p95 +52,9 %; probabilidad de pérdida 57 %. Bolsa real: p5 −24,6 %, p50 +7,7 %, p95 +42,9 %; probabilidad de pérdida 35 %. Un día de −3,2 % en oro cabe de sobra en ese abanico, pero el modelo es a 12 meses y su calibración no está confirmada fuera de muestra. No sirve para juzgar un día.
- **E1:** sin registros todavía.
- **Episodios parecidos** (regla: oro ≤ −1,63 σ y Euro Stoxx 50 ≤ −1,02 σ el mismo día; el 18-nov la cumple con −2,17 σ y −1,36 σ). n = 80 (el paquete lista 30 fechas). Después de esos días:
  - Oro: a 5 sesiones mediana +0,39 % (54 % al alza frente a 55 % de todos los días); a 20 sesiones mediana +0,9 % (64 % al alza frente a 55 %).
  - Euro Stoxx 50: a 20 sesiones mediana +1,76 % (65 % al alza frente a 60 %).
  - S&P 500: a 20 sesiones mediana +1,84 % (70 % al alza frente a 66 %).
  - Son pocos episodios y solapados; la dispersión (p25–p75) es grande. No permite prever qué pasará ahora.
- **COT** (dato del 2026-11-10, anterior al evento): productores de oro, plata, WTI y gas natural en extremo alto histórico; fondos apalancados en Nasdaq-100 en extremo alto de 3 años (percentil 99). Es contexto, no causa demostrada.

## 4. Fuentes
Titulares de prensa y comunicados sin verificar uno a uno; no son datos propios. Ninguno explica la caída de UNH.
- Prensa (GDELT), sobre el día anterior (17-nov), no el 18: «Stock Market Today, Nov. 17: Stocks Slide on AI Chip and Tech Pressures, Salesforce Plummets 9 %» — https://www.fool.com/coverage/stock-market-today/2026/11/17/stock-market-today-nov-17-stocks-slide-on-ai-chip-and-tech-pressures-salesforce-plummets-9/
- Prensa (GDELT), notas de empresas mineras sin relación clara con el movimiento:
  - https://www.brantfordexpositor.ca/press-releases/newsfile/auro-intersects-679-9m-grading-0-44-g-t-au-and-0-14-copper-in-previously-untested-target-at-the-santa-barbara-gold-copper-project-ecuador/
  - https://www.brantfordexpositor.ca/press-releases/globe-newswire/massive-sulphide-discovery-at-the-rockley-project/
- Fed, actas del FOMC del 27-28 de octubre de 2026 (18-nov, 19:00 UTC): https://www.federalreserve.gov/newsevents/pressreleases/monetary20261118a.htm
- BCE, «Risks from AI valuations, fiscal imbalances and geoeconomic tensions weigh on financial stability outlook» (18-nov, 09:00 UTC): https://www.ecb.europa.eu//press/pr/date/2026/html/ecb.pr261118~83c5c60158.en.html
- BCE, Boris Vujčić: Financial Stability Review - November 2026 (18-nov): https://www.ecb.europa.eu//press/key/date/2026/html/ecb.sp261118~86f1e8147e.en.pdf
- BLS, Major Economic Indicators (18-nov): https://www.bls.gov/bls/

## 5. Comprobaciones automáticas
```json
[
  {"hipotesis": 1, "serie": "UNH", "direccion": "baja", "horizonte": 5, "que_significa": "UNH no recupera: el golpe propio de la empresa persiste"},
  {"hipotesis": 1, "serie": "XLV", "direccion": "sube", "horizonte": 20, "que_significa": "El sector salud se recupera: el problema era solo de UNH"},
  {"hipotesis": 2, "serie": "oro", "direccion": "baja", "horizonte": 5, "que_significa": "La venta de oro continúa en la semana siguiente"},
  {"hipotesis": 2, "serie": "GDX", "direccion": "baja", "horizonte": 20, "que_significa": "Las mineras de oro siguen cayendo a un mes"},
  {"hipotesis": 3, "serie": "hy_oas", "direccion": "sube", "horizonte": 5, "que_significa": "El diferencial high yield se amplía: más aversión al riesgo"},
  {"hipotesis": 3, "serie": "vix", "direccion": "sube", "horizonte": 5, "que_significa": "La volatilidad implícita sigue subiendo"},
  {"hipotesis": 4, "serie": "oro", "direccion": "sube", "horizonte": 20, "que_significa": "El oro recupera a un mes: el día fue ruido"},
  {"hipotesis": 4, "serie": "sp500", "direccion": "sube", "horizonte": 20, "que_significa": "La bolsa amplia sube a un mes, sin daño duradero"}
]
```
