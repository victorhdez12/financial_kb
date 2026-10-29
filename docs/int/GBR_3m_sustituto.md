# GBR: sustituto del tipo a 3 meses de la OCDE (29-oct-2026)

**Problema.** La OCDE dejó de publicar el tipo a 3 meses de Reino Unido (`oecd_ir3m_gbr`, último dato 2026-02). El
termómetro de recesión en vivo (`src/report/termometro_vivo.py`) se quedaba sin curva 10a−3m para GBR («sin tipo a 3
meses desde 2026-02»).

## Fuente elegida y por qué

| candidata | serie | cobertura | ¿sirve? |
|---|---|---|---|
| Letras del Tesoro a 3 meses, BoE (IADB) | `IUMAJNB` → `boe_tbill3m_m` | 1975-01 – **2017-06** | **No**: el BoE dejó de publicarla en 2017-06 (la DMO dejó de publicar precios de referencia de las letras en julio de 2017; los resultados de subastas de la DMO están tras un captcha y no se pueden descargar de forma automática). Se ingesta solo como referencia. |
| **OIS (SONIA) a 3 meses, BoE (curvas de rendimiento)** | hoja «spot, short end», vencimiento 0,25 años, media mensual de los datos diarios → `boe_ois3m_m` | 2016-01 – último mes completo | **Sí: la usada.** Es un tipo a plazo de 3 meses, mirando hacia delante, como las letras y el interbancario, y la serie más pegada a la OCDE en el solape. |
| SONIA a un día, BoE (IADB) | `IUMASOIA` → `boe_sonia_m` | 1997-01 – último mes | No: es un tipo a un día; no anticipa los cambios de tipo y se separa más de la OCDE. Se ingesta para comparar. |

Ingesta: `src/ingest/boe_rates.py` (registrada en `config/sources.yaml`, id `boe_rates`, y en `INGEST` del Makefile;
no va en `INGEST_DAILY` porque la OCDE tampoco). Solo meses completos: se quita el mes del último dato diario (en curso)
y los meses con menos de 10 días. Datos en bruto en `$FIN_DATA_ROOT/raw/boe_rates/` (zips de curvas del BoE y CSV de la
IADB).

## Comparación con `oecd_ir3m_gbr` en el solape

Diferencia = OCDE − BoE, en puntos porcentuales; medias mensuales.

| serie BoE | solape | meses | dif. media | desv. típ. | correlación | máx. dif. absoluta |
|---|---|---|---|---|---|---|
| OIS 3 m (`boe_ois3m_m`) | 2016-01 – 2026-02 | 122 | +0,09 | 0,08 | 0,9991 | 0,58 (2020-04) |
| OIS 3 m | 2022-01 – 2026-02 | 50 | +0,08 | 0,06 | 0,9992 | 0,17 (2023-09) |
| **OIS 3 m, últimos 24 meses** | **2024-03 – 2026-02** | **24** | **+0,02** | **0,01** | **0,9999** | **0,04 (2024-08)** |
| letras 3 m (`boe_tbill3m_m`) | 1986-01 – 2017-06 | 378 | +0,45 | 0,36 | 0,9963 | 2,77 (2008-11) |
| SONIA a un día (`boe_sonia_m`) | 2024-03 – 2026-02 | 24 | −0,08 | 0,06 | 0,9935 | 0,20 (2024-10) |
| SONIA a un día | 1997-01 – 2026-02 | 350 | +0,23 | 0,29 | 0,9926 | 1,72 (2008-10) |

En los últimos dos años la OCDE y el OIS a 3 meses del BoE son prácticamente la misma serie (la OCDE parece usar ya un
tipo de mercado a 3 meses ligado a SONIA). Antes la OCDE de GBR iba por encima: era el interbancario (LIBOR), con prima de
crédito sobre las letras y el OIS, sobre todo en 2008 y en marzo-abril de 2020.

## Empalme en el termómetro en vivo

- **Solo en vivo.** El desarrollo (≤ 2004), el modelo, las rectas y las referencias congeladas no cambian; `boe_ois3m_m`
  no está en las familias de `src/intl/data.py` (`load_dev` la rechaza) y el termómetro la admite aparte
  (`SUSTITUTOS_3M`).
- **Desde el mes siguiente al último dato de la OCDE** (calculado con los datos ≤ fecha de corte: si la OCDE tenía el
  dato, no se empalma). Hoy: OCDE hasta 2026-02, BoE desde **2026-03**.
- **Nivel:** diferencia media OCDE − BoE de los últimos 24 meses de solape; se suma a la parte del BoE solo si es
  apreciable (|media| ≥ 0,05 pp). Hoy es +0,02 pp (desv. 0,01): **sin ajuste**. Con menos de 12 meses de solape no se
  empalma (sigue el aviso de serie cortada).
- **Fechas «as of»:** el sustituto usa el mismo retraso que la serie OCDE (media mensual de mercado, se conoce al cierre
  del mes).
- **Lo que se ve:** desaparece el aviso «sin tipo a 3 meses» de GBR y el informe lo declara en una nota por país:
  «GBR: tipo a 3 m: BoE OIS (SONIA) 3 m desde 2026-03 (empalme; sin ajuste de nivel: diferencia media OCDE − BoE +0.02 pp
  en 24 meses de solape 2024-03/2026-02, < 0.05 pp)». También en el JSON (`paises.GBR.empalmes`).
- **Resultado 2026-09-30** (`.venv/bin/python -m scripts.termometro_vivo`): GBR vuelve a tener curva 10a−3m (media 12 m)
  = 0,90 pp (percentil 77 frente a 1960-2004) y entra de nuevo en la difusión de curvas invertidas.

Tests sintéticos, sin red: `tests/test_termometro_vivo.py` (empalme sin y con ajuste, solo los últimos 24 meses, sin
cola o con poco solape no se empalma, no mira el futuro, no actúa si la OCDE sigue ni en desarrollo) y
`tests/test_boe_rates.py` (meses completos, fechas de la IADB).

**Pendiente / a vigilar:** si la OCDE vuelve a publicar GBR, el empalme se apaga solo (no hay cola). Si el OIS se separa
de la OCDE en un futuro solape, el umbral de 0,05 pp decide si se ajusta el nivel.
