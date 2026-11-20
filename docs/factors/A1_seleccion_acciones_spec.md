---
documento: A1 «selección de acciones» — Claude elige acciones individuales con datos de la empresa y un freno macro (Alpaca PAPER)
version: 1.0 (2026-11-20) — mandato a1-v1 (`config/a1_mandato_v1.md`) + modo agente (§6); cambiarlo = nueva versión declarada.
estado: CONSTRUIDO (2026-11-20, rama del Constructor; pendiente del Validador), NO activado: faltan renombrar las claves
  `_D1`→`_A1`, configurar la cuenta (§7), declarar la reasignación D1→A1, `research/paper/A1_ACTIVO` y cargar el plist.
---

# A1: selección de acciones con datos de la empresa y freno macro

## 0. Qué es y qué no es
- Decisión del usuario (20-nov): no quiere dos cuentas paper que hagan lo mismo (B1 y D1 tenían las dos URTH/IEI/GLD
  70/15/15). Las tres cuentas las gestiona el agente, cada una con un estilo: **M1** macro de arriba abajo, **A1**
  selección de acciones (esta spec) y **C1** libre. B0, B1, B1′ y D1 siguen **solo en papel** (listón teórico).
- A1 elige **acciones individuales de EE. UU.** con fundamentales SEC XBRL, directivos (Form 4), institucionales
  (13F), participaciones (13D/13G), alertas de flujos y las fichas de «Mis activos». **Cuánta bolsa** lo acota un
  filtro macro mecánico (§4). Cada orden cita los datos de la empresa **y** la lectura macro.
- Cuenta paper …X9F9 (antes B0 y luego D1, reasignación declarada; §7), perfil `A1`. Hereda URTH/IEI/GLD: el agente
  decide el primer día qué hace con ellas (IEI es colchón; URTH y GLD solo se pueden vender).
- **Solo hacia delante.** **Previo escéptico declarado:** la mayoría de los gestores que eligen acciones no baten a su
  índice tras costes; la calidad XBRL del paquete es descriptiva y no se ha validado en este proyecto; y el filtro
  macro usa los mismos ajustes que la sombra de M1, cuyo antecedente (V1-V3, S1) no ganó con historia ≤ 2004.

## 1. Ciclo diario (misma infraestructura que C1 y M1)
- 21:00 Madrid (mercado abierto; después de C1 a las 20:30 y M1 a las 20:45: espera a que acaben). Paquete del día
  sin IA (§3) + `claude -p` de solo lectura con el **mandato a1-v1** → JSON de órdenes → guardia de C1 + guardia de
  A1 (§5) → cuenta PAPER del perfil `A1` (ventas primero) → registro `research/paper/decisiones_a1.jsonl` (una línea
  por día, inmutable, con `uso_citas`) y la línea de la sombra `research/paper/decisiones_a1_sombra.jsonl`; commit y
  push el mismo día. Exige `research/paper/A1_ACTIVO`, árbol limpio, claves `_A1`, cuenta de A1 y mercado abierto.
- Botón de parada `research/paper/A1_PARADA` (lo puede crear el supervisor). Puede no operar ningún día.

## 2. Mandato a1-v1 (texto fijo en `config/a1_mandato_v1.md`)
1. Objetivo: máxima rentabilidad ajustada por riesgo a largo plazo; caída máxima tolerable −35 % desde el máximo.
2. Universo: acciones de EE. UU. negociables en Alpaca con datos de empresa en el paquete (`universo_compra`: S&P 500
   actual + «Mis activos» + posiciones, con calidad XBRL calculable y sector); ETFs **solo como colchón** (SGOV, BIL,
   SHV, SHY, IEI). Sin cortos, sin apalancamiento, **sin opciones, sin cripto**.
3. Límites: 10-30 valores (30 lo impone la guardia; 10 es objetivo que vigila el supervisor), **máx. 10 % por valor,
   máx. 35 % por sector**, lo invertido fuera del colchón ≤ techo de bolsa del filtro macro (§4).
4. **Cita doble** en cada orden: `citas_empresa` ({fuente, dice}: `xbrl`, `form4`, `13f`, `flujos`, `alertas`,
   `ficha`, con datos hoy para ESE símbolo) y `citas_macro` ({modelo, dice}: `cuadrante`, `credito`, `liquidez`,
   `ciclo_deuda`, `e1`, `int11`, `diagnosticos`, `filtro_macro`, con salida hoy). Excepciones: colchón y venta de algo
   sin datos de empresa (URTH, GLD) solo cita macro. No operar: `citas_no_operar` macro. `lectura_macro` obligatoria.
5. Recibe la sombra (§4) como referencia; no tiene que seguirla.

## 3. Paquete del día (`src/paper/a1_paquete.py`, sin IA)
El de C1 (cuenta, precios, régimen, alertas, diagnósticos, panel, diario) más:
- `macro` (las mismas salidas que M1, con fecha) y `filtro_macro`; `macro_disponibles`;
- `candidatas` (`src/paper/a1_candidatas.py`): universo S&P 500 actual (`raw/sec_universe/sp500_ticker_start_end.csv`)
  + «Mis activos» + posiciones; de `raw/sec_bulk/companyfacts.zip` el último año fiscal (marco `CYAAAA`) de ingresos,
  beneficio y resultado operativo (y el anterior) y el último instante de activos/pasivos/patrimonio; sector por SIC
  (`submissions.zip`, mapa declarado aprox. GICS). Métricas: ROA, margen operativo (mismo año fiscal que los
  ingresos), crecimiento de ingresos y apalancamiento; **calidad** = media de percentiles (ROA↑, margen↑,
  crecimiento↑, apalancamiento↓), ≥ 3 de 4, año fiscal ≥ actual − 2. Detalle de las 60 mejores y fila compacta de todas.
  Caché por versión del zip (`~/financial_archive/a1/candidatas/`);
- `mis_activos`: XBRL de los últimos trimestres (`sec_fundamentales/hechos.json`), Form 4 de 12 meses (compras en
  mercado abierto y ventas sin plan 10b5-1), 13F (último trimestre frente al anterior), 13D/13G (últimos 5);
- `empresa_disponible`, `universo_compra`, `sectores`, `colchon` y `limites_a1` (los usa la guardia);
- `sombra` y `cierres_simulacion` (detalle + colchón + «Mis activos» + posiciones, para los ensayos sin cuenta).

## 4. Filtro macro y sombra teórica (`src/paper/a1_sombra.py`)
- **Filtro macro** (mecánico, lo aplica la guardia): techo de bolsa = base 90 %, suelo 30 %, techo 100 %, con los
  **mismos ajustes** que el paso 1 de la sombra de M1 (crédito ámbar −10 / rojo −25 pp; E1 > 30 % −15, > 50 % −30 pp;
  liquidez escasa −5 / abundante +5 pp; INT-11 P(pérdida) > 60 % −10, < 35 % +5 pp; G↑ +10, G↓ −10 pp). Sin dato,
  esa entrada no ajusta.
- **Sombra** (barata y mecánica, sin cuenta): cada mes (primera decisión del mes natural) la cesta = las **20 de mayor
  calidad XBRL** con máx. 7 por sector (35 % de 20), a partes iguales; peso total = techo del filtro de cada día; el
  resto en SGOV; colchón de efectivo 0,5 %. Valoración con la de M1 (cierre del día de la decisión, sesiones
  completas, 5 pb × Σ|Δw|, reequilibra si cambia el objetivo o un peso deriva ≥ 5 pp). Sirve de listón: A1 frente a
  su sombra dice si el criterio del agente añade algo a «comprar calidad a partes iguales con el mismo freno».

## 5. Guardia (`src/broker/a1_guardia.py`, en código)
- La de C1: solo `paper-api`, compras ≤ efectivo (sin apalancamiento), sin cortos, ≤ 20 órdenes, salida con el
  formato del mandato o no opera, parada.
- Por orden: `clase` ≠ `accion` (opciones, cripto) → rechazada; sin cita macro válida o sin cita de empresa válida
  (salvo las excepciones de §2.4) → rechazada; compra fuera del `universo_compra` y del colchón → rechazada.
- Por cartera (tras la de C1, en el orden propuesto; las ventas válidas del día se descuentan a su precio de
  referencia): compra que dejaría el valor > 10 % del valor de la cuenta, el sector > 35 %, más de 30 valores, una
  acción sin sector, o lo invertido fuera del colchón por encima del techo de bolsa → rechazada (su coste vuelve al
  efectivo). Nunca fuerza ventas si la cartera ya está por encima (por precio): lo vigila el supervisor.
- La guardia NO comprueba que lo citado sea verdad: lo revisa el supervisor (spec del supervisor §1.1).

## 6. Modo agente
Como M1 (`src/paper/agente.py`, rol `A1`): `claude -p` con Read/Grep/Glob sobre carpetas enumeradas (repo salvo
`research/paper` y `data/`; del archivo las subcarpetas de datos, nunca `config/` ni `raw/`), sin Bash, sin red, sin
escritura, sin claves en el entorno; no puede leer los diarios de C1 ni de M1. Diario `obsidian/Carteras/A1/AAAA-MM-DD.md`
(fuera de git; lo escribe Python con el texto del agente). Plazo 15 min; sin cupo: no opera y se anota. Coste: la
suscripción del usuario.

## 7. Cuenta y activación (lo hace el usuario tras el Validador)
1. Renombrar en `~/financial_archive/config/alpaca.env` las claves `_D1` → `_A1` (y las del perfil por defecto → `_C1`).
2. `.venv/bin/python -m scripts.configurar_cuentas --leer` y, si cuadra, `--aplicar`: …X9F9 `no_shorting=true`,
   `max_margin_multiplier=1`, opciones desactivadas (nivel 0).
3. Reinstalar el plist de D1 (ya sin `--ejecutar`) y, DESPUÉS, `.venv/bin/python -m scripts.reasignar_cuentas --escribir`
   (fila `reasignacion` D1→A1 en `espejo.jsonl`; las órdenes anteriores del espejo dejan de contar para A1).
4. Ensayo: `.venv/bin/python -m src.paper.a1` (sin registrar). Crear `research/paper/A1_ACTIVO` (commit) y cargar
   `scripts/launchd/com.financialkb.a1.plist`.

## 8. Evaluación
- Tabla «Competición»: A1 junto a C1 y M1 (cuentas) y a D1, la sombra de M1 y la sombra de A1 (teóricos diarios).
- `uso_citas` por día: qué fuentes de empresa y qué modelos macro cita cada orden (descriptivo).
- Supervisor: concentración (> 15 % en un valor salvo colchón y heredadas → parada), opciones o cripto en la cuenta
  (→ parada), número de valores, coherencia de las citas.
- Cambio de modelo de Claude: se anota (otro gestor desde ese día). Años, no meses, para concluir nada.

## 9. Construcción (2026-11-20)
| pieza | dónde |
|---|---|
| ciclo y registro | `src/paper/a1.py` (el ciclo de C1 con la cartera A1; gancho `post_validar` nuevo en `src/paper/c1.py`) |
| paquete | `src/paper/a1_paquete.py` |
| candidatas XBRL | `src/paper/a1_candidatas.py` |
| filtro macro y sombra | `src/paper/a1_sombra.py` (reutiliza `m1_sombra.bolsa` con base/suelo/techo propios y `valorar`) |
| guardia | `src/broker/a1_guardia.py` |
| mandato | `config/a1_mandato_v1.md` + `config/gestor_conocimiento_v1.md` |
| automatización (no instalada) | `scripts/a1_gestor.sh` + `scripts/launchd/com.financialkb.a1.plist` (21:00 lun-vie) |
| cuentas | `scripts/reasignar_cuentas.py`, `scripts/configurar_cuentas.py` |
| tests | `tests/test_a1.py` (sin red, sin claves, registros reales intactos) |
Declarado (lo que la decisión del usuario no fijaba): universo = S&P 500 actual; calidad XBRL de 4 métricas; mapa
SIC→sector; colchón SGOV/BIL/SHV/SHY/IEI; filtro macro base 90 %; sombra de 20 valores mensual; tope duro del
supervisor 15 % por valor; companyfacts.zip es del 7-oct-2026 (los 10-Q del 3T no están: hay que refrescarlo, §10).

## 10. Límites conocidos
- `companyfacts.zip`/`submissions.zip` se descargan a mano (`src/ingest/sec_bulk.py`); la calidad usa el último año
  fiscal completo, no los trimestres recientes. Fecha de los datos en `candidatas.fecha_datos`.
- Form 4, 13F y 13D/13G solo para los 10 valores de «Mis activos»; para el resto del universo la única fuente de
  empresa es XBRL. El 13F del último trimestre puede estar incompleto (presentaciones con hasta 45 días de retraso).
- El sector por SIC es aproximado (no es GICS).
