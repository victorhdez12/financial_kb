---
documento: Implementación de B1′ (docs/factors/B1prima_spec.md v1.0, congelada el 30-oct)
version: 1.0 (2026-11-05)
estado: código y coeficientes congelados; registro EN PARALELO a B1, desde el cierre de 2026-11-30, solo si existe
        research/paper/ACTIVO. Sin enganchar a launchd hasta que el usuario revise el commit de scripts/paper_mensual.sh.
---

# B1′: implementación

## 1. Condiciones de apertura (spec §2)
- **(a) C1 de P-DEV-INT12 establecido.** `research/int/int12_resultado.json` (procedencia `dec66c1`, árbol limpio,
  2026-10-30T13:17Z), `h1.contrastes.C1`: HAR frente a σ̂ 12 m, ganancia QLIKE **34,3 %** (1950-77: 43,3 %;
  1977-2004: 23,8 %), t = 4,38, p = 5,8·10⁻⁶, p Holm = 1,7·10⁻⁵, p bootstrap = 0,0005, `"veredicto": "establecido"`.
  (C2 y C3: no establecidos; por la spec no cambian B1′.)
- **(b) Aprobación del usuario del paso a código:** 5-nov-2026.

## 2. Qué hay
| pieza | fichero |
|---|---|
| medida, rasgos, calendario NYSE, previsión, regla, decisión en vivo | `src/paper/b1prima.py` |
| estimación única y congelación (puerta: árbol limpio; se niega si ya existe) | `scripts/b1prima_congelar.py` |
| parámetros congelados + sha256 + procedencia + huellas de los datos | `research/paper/b1prima_congelado.json` |
| decisión mensual (ensayo / `--auto` / `--registrar`) | `scripts/paper_decision_b1prima.py` |
| registro propio (inmutable; aún no existe) | `research/paper/decisiones_b1prima.jsonl` |
| tests (sintéticos + reproducibilidad con el warehouse) | `tests/test_b1prima.py` |

B1 (`src/paper/live.py`, `scripts/paper_decision.py`, `research/paper/decisiones.jsonl`, `sigma_star.json`,
`docs/factors/paper_trading.md`) **no se ha tocado**. El script de B1′ importa de `scripts/paper_decision.py` las reglas de
mes (`validar`, `cierre_objetivo`), sin modificarlas.

## 3. Parámetros congelados
Corrida `scripts/b1prima_congelar.py` en el commit `52a4627` (árbol limpio, 2026-11-05T13:23Z).
`sha256_parametros = 064ebd8c3662854099f4c2f2ead386b3ed69d93b064e05493d8aaea4c35cb6fd` (JSON canónico de β, Duan y σ*′
redondeados a 12 decimales; `cargar_congelado` lo comprueba antes de cada decisión y, si no cuadra, no decide).

- log(RV_{M+1} / n_{M+1}) = **−2,0087 + 0,0897 · lrv5 + 0,3227 · lrv21 + 0,3764 · lrv63**; Duan = **1,2896**;
  497 meses (orígenes 1963-07 … 2004-11; último objetivo 2004-12-31).
- **σ\*′ = 16,67 %** (mediana de σ̂′ en 1963-07 … 2004-12, 498 meses; dentro de muestra, declarado en la spec).
  Percentiles de σ̂′ en desarrollo: p5 8,4 %, p25 13,5 %, p75 19,8 %, p95 26,6 %. (σ\* de B1: 17,02 %.)
- Propiedad de la señal en desarrollo (sin rentabilidades, dentro de muestra): B1′ recortaría el **50 %** de los meses
  (RV media recortada 60,1 %) con **4,05 cambios al año**; B1 con su σ\*: 57 % y 1,83 cambios al año. **B1′ rota más del
  doble**: se verá en costes en vivo.

## 4. Ambigüedades y decisiones (lo más conservador o lo más literal)
1. **r_USD en desarrollo = `aqr_mkt_usa_d`, que es rendimiento en exceso sobre la letra**, no total ni de precio (es la
   serie de P-DEV-INT12, que la spec cita). En vivo es el precio del S&P 500 (FRED). La diferencia en r² diario es
   despreciable (letra ≈ 2·10⁻⁴ diario frente a σ ≈ 10⁻²), pero no es la misma serie: declarado, no corregido (seguir a
   INT-12 literalmente).
2. **Divisa diaria:** X = EUR por USD = DEM/USD de Frankfurt / 1,95583 hasta 1998-12-30 y 1 / EURUSD del BCE desde
   1999-01-04. El fixing se lleva al último conocido en cada sesión de EE. UU. (los movimientos de días sin sesión entran
   en la sesión siguiente; un festivo de divisa da movimiento cero ese día). Fixing (13:00/14:15 CET) y cierre de
   EE. UU. no son simultáneos: igual en desarrollo y en vivo.
3. **"Todos los meses 1963-07 … 2004-11"** = meses de origen; el objetivo del último es 2004-12 (≤ 2004). Los rasgos de
   1963-07 usan sesiones anteriores (63 días hacia atrás): solo como rasgos.
4. **Duan** forma parte de los parámetros congelados (es el HAR de P-DEV-INT12: previsión = n · exp(ajuste) · Duan).
5. **n del mes siguiente:** en la estimación y en σ\*′ hasta 2004-11, las sesiones observadas (el calendario NYSE
   realizado, como INT-12). Para el origen 2004-12 (σ\*′) y en vivo, `sesiones_nyse`: reglas de festivos de la NYSE
   (≥ 2005: Año Nuevo sin adelanto si cae en sábado, MLK, Presidents, Viernes Santo, Memorial, Juneteenth ≥ 2022, 4 de
   julio, Labor, Acción de Gracias, Navidad) y los cierres extraordinarios ya ocurridos. Comprobado: coincide con las
   sesiones de `SP500` de FRED en los 120 meses completos 2016-11 … 2026-10. Un cierre extraordinario futuro no anunciado
   no se puede prever (efecto: n sobra en 1 de ~21, σ̂′ ≈ +2,5 %).
6. **Falla cerrado** (spec §3): `SP500` o `ecb_eurusd_d` con último dato a más de 5 días del cierre; menos de 63
   rendimientos; **en los meses de la ventana de 63 sesiones (salvo el primero, parcial) menos sesiones de `SP500` que
   las del calendario NYSE** (interpretación de "meses que faltan" a escala diaria); falta el fichero congelado o su
   sha256 no cuadra.
7. **Arranque:** "el primer cierre de mes después de la aprobación" (5-nov) = **2026-11-30**. `--registrar` rechaza
   cierres anteriores (sin historia retroactiva); el cierre de octubre solo se ensaya.
8. **ACTIVO:** en B1 lo comprueba `paper_mensual.sh`; en B1′ lo comprueba además el propio script (`--registrar` sin
   `research/paper/ACTIVO` → código 6, no escribe). Peso previo: el último de su propio registro (70 % si está vacío).
9. Como B1, `--registrar` commitea y hace `push origin main` (la hora del commit en el remoto fecha la decisión). Mismo
   punto débil que B1: si el commit local sale y el push falla, el siguiente intento ve el mes "ya registrado" y no
   vuelve a subir (hay que hacer `git push` a mano). No se cambia para no divergir de B1.
10. **Huellas de datos:** el congelado guarda el sha256 de las series ≤ 2004 usadas. Si la fuente se revisa, el test de
    reproducibilidad falla (aviso), pero los parámetros **no** se re-estiman (spec: congelados).

## 5. Ensayo del cierre de 2026-10 (sin registrar)
`.venv/bin/python -m scripts.paper_decision_b1prima --cierre 2026-10-31`:

| | σ̂ | σ\* | RV bruta | pesos |
|---|---|---|---|---|
| B1 (registrada, `decisiones.jsonl`) | 10,69 % (12 meses) | 17,02 % | 70 % | 70/15/15 |
| B1′ (ensayo) | **14,67 %** (HAR; lrv5 −8,95, lrv21 −9,52, lrv63 −9,81; n nov = 20) | 16,67 % | 70 % | **70/15/15** |

Misma decisión. σ̂′ es mayor que σ̂ porque la volatilidad diaria reciente (sobre todo la última semana) es más alta que
la de los 12 meses; queda a 2 pp del umbral de recorte.

## 6. Automatización (pendiente de revisión del usuario)
El enganche a `scripts/paper_mensual.sh` va en un commit aparte (sin instalar nada nuevo en launchd: usa el job
`com.financialkb.paper` existente). Bloque independiente de B1, antes de la marca de B1: sin ACTIVO solo ensaya una vez al
mes; con ACTIVO registra (`--auto --registrar`) con su marca `.b1p_hecho_$MES`; si falla, avisa, deja el fichero de B1′
como estaba (para no ensuciar el árbol que necesita B1) y reintenta al día siguiente.

## 7. Pendiente
- Usuario: revisar el commit de `paper_mensual.sh`; crear `research/paper/ACTIVO` (sirve para B1 y B1′).
- Informe mensual de la spec §4 (σ̂ y σ̂′, pesos, rotación, costes, volatilidad realizada, caída; QLIKE de σ̂′ frente a σ̂
  mes a mes con la RV realizada del mes siguiente): no implementado aquí; prerregistrar su forma antes del primer dato.
