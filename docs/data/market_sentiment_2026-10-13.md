# Mercado, crédito y sentimiento (2026-10-13)

Agente de datos "Mercado, crédito y sentimiento". Tres fuentes nuevas (`cftc_cot`, `cboe`, `fed_ebp`), una ampliación de `fred_us` (51 series) y un hueco documentado (ICI). Total: **237 series nuevas** (186 en fuentes nuevas + 51 en `fred_us`, que pasa de 1691 a 1742).

Scripts (idempotentes, `.venv/bin/python -m src.ingest.<fuente>`): `src/ingest/cftc_cot.py`, `cboe.py`, `fed_ebp.py` y `fred_us.py --only-ext` (modo nuevo que solo trae la lista `EXT` y la fusiona en el catálogo sin borrar nada). Raw intacto en `~/financial_archive/raw/<fuente>/`.

## Resumen por fuente

| fuente | series | frecuencia | cobertura | licencia |
|---|---|---|---|---|
| `cftc_cot` | 163 | semanal (martes "as of") | 1986-01-15 (legacy) / 2006-06-13 (TFF y disagregado) -> 2026-10-06 | dominio público EE. UU. (CFTC) |
| `cboe` | 20 | diaria | ver abajo, hasta 2026-10-12 | CBOE, descarga pública gratuita; uso personal, sin redistribución |
| `fed_ebp` | 3 | mensual | 1973-01 -> 2026-09 (645 obs.) | datos públicos del Fed Board; citar Gilchrist-Zakrajšek (2012) y Favara et al. (2016) |
| `fred_us` (ampliación) | 51 | D/W/M | ver abajo | FRED, uso personal/investigación |
| ICI | 0 | - | hueco | - |

## 1. CFTC Commitments of Traders (`cftc_cot`)

Descarga: zips históricos de `cftc.gov/files/dea/history/` (`deacot1986_2016` + anuales 2017-2026 para Legacy; `fin_fut_txt_2006_2016` + `fut_fin_txt_AAAA` para TFF; `fut_disagg_txt_hist_2006_2016` + `fut_disagg_txt_AAAA` para Disaggregated). Solo futuros (no "futuros y opciones"), columnas "All". El zip del año en curso se vuelve a bajar si tiene más de 20 h. Los contratos se identifican por **código CFTC**, no por nombre (el nombre y el mercado cambian dentro de un mismo código: IMM -> CME, "Long-term UST bonds" -> "Ultra", etc.; no es un empalme).

**Retardo (importante para point-in-time):** `date` es la fecha "as of" del martes. El informe se publica el **viernes a las 15:30 ET**, es decir, **+3 días** (+4 si hay festivo el lunes). Una serie CFTC no era conocida antes de `date + 3`. Está anotado en `transform_notes` de cada serie.

Series por mercado (prefijo `cftc_<slug>_`):
- Legacy (todos los mercados, 1986+): `oi` (open interest), `nc_net` (no comerciales largos - cortos, sin spreading), `nc_net_pct_oi`, `comm_net`.
- TFF (financieros, 2006-06+): `lev_net` (leveraged funds), `lev_net_pct_oi`, `am_net` (asset managers), `dealer_net`.
- Disaggregated (materias primas, 2006-06+): `mm_net` (managed money), `mm_net_pct_oi`, `prodmerc_net` (productor/comerciante).

| slug | contrato (código CFTC) | inicio legacy | notas |
|---|---|---|---|
| `sp500_emini` | E-mini S&P 500 (13874A) | 1997-09 | |
| `nasdaq_mini` | Nasdaq-100 mini (209742) | 1999-06 | |
| `ust2y`, `ust5y`, `ust10y`, `ust_bond` | UST 2a (042601), 5a (044601), 10a (043602), bono 30a (020601) | 1990-06 / 1988-05 / 1986-01 / 1986-01 | el 10a empieza como "6.5-10 year" |
| `ultra10y`, `ultra_bond` | Ultra 10a (043607), Ultra T-bond (020604) | 2016-03 / 2010-03 | |
| `eurodollar` | Eurodólar 3M (132741) | 1986-01 | **termina 2023-06-13** (cierre del contrato) |
| `sofr3m` | SOFR 3M (134741) | 2018-07 | continuación natural del eurodólar; **no se empalman** |
| `eur`, `jpy`, `gbp`, `chf` | Euro FX (099741), yen (097741), libra (096742), franco (092741) | 1986 / 1986 / 1988 / 1986 | EUR desde 1999 (antes ECU 1986, 10 obs.) |
| `dxy` | US Dollar Index (098662) | 1992-05 | |
| `gold`, `silver`, `copper` | COMEX (088691, 084691, 085692) | 1986 / 1986 / 1989 | |
| `wti` | WTI NYMEX (067651) | 1986-01 | |
| `natgas` | Gas natural NYMEX (023651) | 1990-04 | |
| `vix` | Futuros VIX CFE (1170E1) | 2004-07 | TFF desde 2006-08 |

Notas: sin tipos a 1 mes ni Fed Funds (no pedidos). No se incluyen opciones. Duplicados (código, fecha) entre ficheros: se queda el más reciente (0 detectados al final).

**Comprobaciones:**
- EUR no comerciales netos: **-226.560** el 2015-03-31 (mínimo de la serie; EUR "muy corto" en 2015: confirmado). Leveraged funds EUR en marzo 2015: -145k a -170k.
- Último dato: 2026-10-06 (publicado el 2026-10-09). Oro OI = 396.109 contratos; VIX no comerciales = -91.294; UST 10a leveraged funds = -2,14 M contratos (la base de la operación de base, coherente con los niveles recientes).
- S&P e-mini no comerciales a principios de 2008 = -118k (corto, plausible); WTI managed money en julio 2008 = +61k a +76k.

## 2. CBOE (`cboe`)

Índices diarios (cierre; `cdn.cboe.com/api/global/us_indices/daily_prices/<X>_History.csv`): `cboe_vix3m` (2009-09-18), `cboe_vix6m` (2008-01-02), `cboe_vix9d` (2011-01-04), `cboe_vix1d` (2022-05-13), `cboe_vvix` (2006-03-06), `cboe_skew` (1990-01-02), `cboe_vxn`, `cboe_rvx`, `cboe_ovx`, `cboe_gvz`, `cboe_vxeem`, `cboe_vxtlt`, `cboe_cor1m`, `cboe_cor3m` (2006-01-03). El VIX de 1990 ya estaba en FRED (`VIXCLS`): no se duplica.

Put/call (6 series, ratio puts/calls por volumen): `cboe_pc_total`, `_equity`, `_index` (2003-10-17 -> hoy), `_etp` (2006-11), `_vix` (2006-02), `_spx` (2010-07). Empalme anotado en `transform_notes`: los CSV de CBOE están **congelados en 2019-10-04**; desde 2019-10-07 se completan con el JSON diario `market_statistics/daily/<fecha>_daily_options` (guardado en `raw/cboe/pc_daily/`, incremental). Archivo vs. CSV actual en su solape (1410 días): diferencia media 0,011, máxima 0,21 (revisiones de CBOE). Sin huecos de más de 5 días. **Posible ruptura de nivel en `cboe_pc_spx`**: el CSV es SPX y el JSON es SPX+SPXW.

**Comprobaciones:** VIX3M máximo en marzo de 2020 = **72,98 (2020-03-18)** (>50 OK). VXV de FRED (`VXVCLS`) el mismo mes = 72,98. VVIX último = 85,93; máximo 207,59. SKEW máximo desde 2020 = 183,12 (2025-02-18). **Aviso:** las dos primeras observaciones del fichero VVIX (2006-03-06 = 71,73 y 2006-03-15 = 15,71) parecen glitches de arranque de CBOE; se conservan tal cual (raw intacto) y quedan anotadas en el catálogo. SKEW > 150 es un nivel alto sostenido en 2026 (155,06 el 2026-10-12), no es un error.

Hueco: CBOE no publica archivos históricos de `VOLQ`, `SDEX`, `TDEX` (403). El fichero `VXV_History.csv` devuelve 403 (el índice se llama ahora VIX3M); la historia previa a 2009 está en `fred_us/VXVCLS` (desde 2007-12-04).

## 3. Excess Bond Premium y GZ spread (`fed_ebp`)

URL: `https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv` (redirige a `/econres/notes/feds-notes/ebp_csv.csv`). Series: `fed_ebp_gz_spread` (pp), `fed_ebp_ebp` (pp), `fed_ebp_recession_prob` (probabilidad 0-1 de recesión implícita en el EBP). Mensual, fechas a inicio de mes, 1973-01 -> 2026-09.

**Comprobaciones:** EBP en 2008-09 -> 2009-01: 1,79; **3,41 (2008-10, máximo)**; 3,12; 3,32; 2,81 (alto, OK). GZ spread máximo = 7,84 (2008-11). Último EBP (2026-09) = -0,39, probabilidad de recesión 0,09.

**Point-in-time:** el EBP se estima con parámetros de muestra completa y el último mes se revisa. `fed_ebp_recession_prob` es una estimación derivada: no es un "lookahead" estricto, pero conviene tratar el EBP como solo aproximadamente PIT. El Fed lo publica con retardo de varias semanas.

## 4. FRED: 51 series nuevas en `fred_us`

Comprobadas contra `curated/*/_catalog.csv` (362 de `fred` + el resto): ninguna estaba. Lista `EXT` en `src/ingest/fred_us.py`.

- Materias primas y dólar (3, diarias): `DCOILBRENTEU` (1987-05-20 -> 2026-10-06; Brent 143,95 el 2008-07-03 y 9,12 el 2020-04-21: OK), `DTWEXAFEGS`, `DTWEXEMEGS` (2006-01 -> 2026-10-02; `DTWEXBGS` ya estaba).
- Volatilidad CBOE en FRED (7, diarias): `VXVCLS` (desde 2007-12; marzo 2020 máx. 72,98), `VXNCLS`, `RVXCLS`, `OVXCLS`, `GVZCLS`, `VXEEMCLS`, `VXDCLS`.
- Incertidumbre: `USEPUINDXD` (diaria), `USEPUINDXM` (mensual), desde 1985.
- Encuestas regionales de la Fed (SA, índices de difusión, mensuales): Empire State (11 series desde 2001-07: general actual y futura, nuevos pedidos, precios pagados/recibidos, empleo, envíos, pedidos pendientes, plazo de entrega, inventarios; `GACDISA066MSFRBNY` abril 2020 = -80,0), Philadelphia (12 series desde 1968-05: igual más precios pagados futuros; `GACDFSA066MSFRBPHI` enero 2009 = -31,1), Dallas Texas manufacturero (8 desde 2004-06) y de servicios TSSOS (3 desde 2007-01).
- `CFNAIMA3` (media móvil 3 meses del CFNAI; `CFNAI` ya estaba), `FRBKCLMCILA`/`FRBKCLMCIM` (Índice de Mercado Laboral del KC Fed, 1992+).
- Fondos monetarios semanales (Fed H.6, datos de ICI): `WRMFNS` (minoristas, 1980-02 -> 2026-08-31, 3.034 mm$) y `WIMFNS` (institucionales, **discontinuada en 2021-02-01**, 2.883 mm$). `MMMFFAQ027S` (trimestral Z.1) ya estaba en `fred_us`.

Series descartadas por ser versiones SA discontinuadas del mismo dato: `WRMFSL` y `WIMFSL`.

## Huecos

1. **ICI (ici.org):** todo el sitio devuelve "Access Denied" (Akamai) a clientes automatizados, incluidas las rutas de descarga de estadísticas semanales/mensuales (`/research/stats/flows`, `/mmf`). No hay descarga histórica estable accesible, y no se intenta saltar la protección. Sustitutos ya cargados: activos de fondos monetarios semanales (`WRMFNS`; `WIMFNS` hasta 2021) y trimestrales (`MMMFFAQ027S`), y los fondos de inversión de la Z.1 (`fed_z1`). **Faltan** los flujos semanales/mensuales por tipo de fondo (renta variable doméstica/mundial, bonos) y la emisión neta de ETF. Opción manual: descargar a mano los xls de ici.org y colocarlos en `raw/ici/`; o fuentes de pago (EPFR, Lipper).
2. **Encuestas de Richmond y Kansas City (manufactura):** no se encontraron en FRED (búsqueda por texto sin resultados). Se publican en richmondfed.org y kansascityfed.org (Excel); no se intentó el scraping de sus webs (pendiente si hace falta). El Empire, Philadelphia y Dallas sí están.
3. **Índice de sorpresas económicas (Citi):** de pago, no incluido.
4. **Put/call de CBOE:** sin historial antes de 2003-10; el JSON diario solo existe desde 2019-10-07 (los CSV se congelaron). Si CBOE cambia el JSON, hay que revisar `_daily_pc`.
5. **CFTC:** sin los informes "futuros + opciones combinados" ni "Supplemental/CIT". Hasta 2006 no hay desglose por tipo de trader (solo Legacy). Series de TFF de contratos nuevos (Ultra) empiezan en su lanzamiento.
6. **Futuros de VIX curva / MOVE:** MOVE de ICE (de pago); sin curva de futuros de VIX.

## Qué cambiar en `src/warehouse/build.py` (sin cambiarlo)

- **Carga:** nada obligatorio. El glob `curated/*/*.parquet` y los `_catalog.csv` recogen `cftc_cot`, `cboe` y `fed_ebp` y la ampliación de `fred_us`. Los ids son únicos globalmente (comprobado: los únicos duplicados son los 14 gemelos fred/alfred previos).
- **PIT:** los datos CFTC son un caso de "observado pero publicado con retardo". Si el warehouse llega a modelar disponibilidad, añadir una regla para `^cftc_` con retardo 3 días (viernes), y para `^fed_ebp_` una nota de revisión (retardo mensual y valores revisables). `fed_ebp_recession_prob` es una estimación a pie de muestra completa: valorar incluirlo en `PIT_RULES` como `lookahead` si se usa de predictor.
- **Categorías nuevas:** ninguna (se usan `markets`, `rates`, `fx`, `gold`, `commodities`, `credit`, `financial_conditions`, `growth`, `employment`, `money`).
- **Clasificador (`src/regime`):** las series CFTC (semanales) y de CBOE (diarias) necesitan los `MAX_STALE_DAYS` de su frecuencia si se conectan; el último CFTC (martes) llega cada viernes. `cftc_eurodollar_*` termina en 2023-06 por diseño: debe excluirse del control de obsolescencia (como `WIMFNS` y `cboe_vix1d`).
- **Auditoría:** pasar `src/audit` tras la carga. Posibles falsos positivos: `cboe_vvix` (dos primeras obs.), `cboe_pc_*` (ratios con picos genuinos) y `cftc_*_net` (negativos legítimos, que no son "negativos imposibles").
