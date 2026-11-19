---
documento: Alpaca PAPER (cuenta simulada): datos en tiempo real y espejo de ejecución de B0/B1/B1′
version: 1.1 (2026-11-19)
estado: enganchado (§7). Tres cuentas paper: B1 …4JGR (perfil por defecto), B1′ …ZFJX (`_B1P`), B0 …X9F9 (`_B0`).
  Dry-run hasta el registro de dic-2026 (cierre de nov); órdenes paper desde ene-2027 (cierre de dic). Sin claves no hace nada.
---

# Alpaca paper: «testearnos con la bolsa en tiempo real»

> **NUNCA opera con dinero real.** El código solo habla con `https://paper-api.alpaca.markets` (trading simulado) y
> `https://data.alpaca.markets` (precios, solo lectura). Si en el `.env` o en el entorno aparece el endpoint real
> (`https://api.alpaca.markets`) o cualquier otro, **se niega** (`EndpointNoPermitido`) y sale con error; no hay forma de
> saltárselo con configuración. Test: `tests/test_alpaca.py::test_rechaza_endpoints_no_paper` y siguientes.

## 1. Qué hace
- `src/broker/alpaca.py`: reloj y calendario del mercado de EE. UU., cuenta y posiciones paper, último precio
  (instantánea: cotización, último trade, barra de 1 minuto, cierre anterior) y barras diarias, con el feed **IEX**
  gratuito. HTTP con `requests` y plazo **total** por petición (`src/ingest/_http.py`); sin redirecciones. No usa
  `alpaca-py` (no está instalado y no se ha instalado nada).
- `src/broker/espejo.py`: **espejo de ejecución**. Lee la última decisión registrada de B0, B1 o B1′ (solo lectura de
  `research/paper/decisiones.jsonl` y `decisiones_b1prima.jsonl`: **no los toca ni los sustituye**), traduce los pesos
  a ETFs (§4) y calcula las órdenes para llevar la cuenta paper a esos pesos. Con `--ejecutar` las envía a la cuenta
  paper, espera las ejecuciones y apunta precios y deslizamiento.
- `src/report/panel_alpaca.py`: `seccion_alpaca()` devuelve el HTML de la sección (mercado, valor de la cuenta,
  posiciones con peso actual y objetivo, espejo vs teórico). **No está conectada** a `src/report/panel.py`.

Para qué sirve: el paper teórico valora con cierres de mes, costes fijos (10 pb RV/RF, 20 pb oro) y fracciones
perfectas. El espejo mide lo que pasa al ejecutar de verdad (aunque en simulado): deslizamiento frente al precio en el
momento de la orden y frente al cierre del mes, redondeos de fracciones o acciones enteras, órdenes no ejecutadas,
rotación real. **No dice nada de la ventaja de B1 sobre B0** (`docs/factors/paper_trading.md` §5).

## 2. Crear la cuenta paper y las claves
1. Regístrate en <https://alpaca.markets> (basta con el correo; la cuenta paper no pide datos bancarios ni dinero).
2. En el panel web (app.alpaca.markets) elige la cuenta **Paper** (selector arriba a la izquierda; empieza con 100 000 $
   simulados, se puede reiniciar con otra cantidad).
3. En la página principal de la cuenta Paper, recuadro **API Keys** → *Generate New Keys*. Copia el *Key ID* (empieza
   por `PK…`) y el *Secret Key* (solo se ve una vez). Comprueba que el endpoint que muestra es
   `https://paper-api.alpaca.markets`. **No generes claves de la cuenta Live.**
4. Guarda las claves (§3). Prueba: `.venv/bin/python -m src.broker.alpaca estado`.

## 3. Dónde van las claves (fuera de git) y perfiles
Fichero `~/financial_archive/config/alpaca.env` (otra ruta: `FIN_ALPACA_ENV`), con permisos 600:

```bash
mkdir -p ~/financial_archive/config
touch ~/financial_archive/config/alpaca.env
chmod 600 ~/financial_archive/config/alpaca.env
open -e ~/financial_archive/config/alpaca.env     # o tu editor; NO pegues las claves en el chat ni en el repo
```

Contenido (una cuenta paper = una cartera; el sufijo es el perfil y, si es B0/B1/B1P, también la cartera):

```bash
# una cuenta paper por cartera (Alpaca permite varias cuentas paper, cada una con sus claves)
ALPACA_API_KEY_ID_B1=PK...
ALPACA_API_SECRET_KEY_B1=...
ALPACA_API_KEY_ID_B1P=PK...         # B1′
ALPACA_API_SECRET_KEY_B1P=...
# perfil por defecto (sin sufijo): tiene que declarar su cartera para poder ejecutar
# ALPACA_API_KEY_ID=PK...
# ALPACA_API_SECRET_KEY=...
# ALPACA_CARTERA=B0
```

- Las variables de entorno con el mismo nombre mandan sobre el fichero.
- Si el fichero es legible por otros (no 600) se avisa en cada uso.
- Las claves no salen nunca en logs, mensajes de error, panel ni en `espejo.jsonl`; el número de cuenta se muestra
  como `…1234`. `.gitignore` ignora `alpaca.env`, `*alpaca*.env` y `espejo.jsonl` por si acaso.
- **Varias cuentas paper:** en app.alpaca.markets, menú de la cuenta → *Open New Paper Account*; genera claves en cada
  una y ponlas con su sufijo. El espejo se niega a ejecutar una cartera en un perfil declarado para otra, y en una
  cuenta que ya recibió órdenes de otra cartera (huella del id de cuenta en `espejo.jsonl`).
- Sin claves: todo dice «Alpaca no configurado» y sale con 0.

## 4. Mapeo de tramos a ETFs (`config/alpaca_etfs.json`, versionado)
| tramo (spec) | instrumento tipo (`paper_trading.md` §4) | ETF del espejo | por qué | alternativa |
|---|---|---|---|---|
| RV | ETF UCITS MSCI World | **URTH** | mismo índice (MSCI World) | VT (incluye emergentes) |
| RF | deuda pública euro, duración ≈ 5 | **IEI** (Tesoro EE. UU. 3-7 a) | duración ≈ 4,5-5, la más próxima | IEF (7-10 a) |
| oro | ETC de oro físico | **GLD** | oro físico, el más líquido | IAU, GLDM |
| liquidez | (no hay tramo) | efectivo, colchón 0,5 % | absorbe deslizamiento y redondeos | — |

Diferencias declaradas: todo en USD; la RF es Tesoro de EE. UU., no Bund (otro tipo de interés y otra divisa). Por eso
el espejo **no** compara rentabilidades con el paper teórico, solo ejecución. Cambiar el mapeo = subir `version` del
fichero; cada línea de `espejo.jsonl` lleva la versión.

### 4 bis. S1 «rotación de sectores por régimen» (tercera cuenta, perfil `S1`; 2026-11-19)
- **S1 NO pasó el desarrollo** (`docs/factors/S1_resultado_desarrollo.md`: falla a, b y c). El código queda hecho por si
  el usuario decide llevarla como **observación**; no hay registro real ni enganche a launchd.
- Mapeo propio y versionado `config/alpaca_etfs_s1.json` (`s1-1.0`): núcleo `mkt` → VTI e industrias French → XLK, XLY,
  XRT, XLF, XLE, XLB, XLI, XLU, XLP, XLV, XLC (spec §6, con sus diferencias declaradas). B0/B1/B1′ siguen con
  `config/alpaca_etfs.json` sin cambios.
- Decisión mensual: `scripts/paper_decision_s1.py` (`src/paper/s1.py`): cuadrante de la fila `regime_monthly` del
  cierre (con corte = ese fin de mes), pesos 50 % mercado + 4 × 12,5 %; registro propio `research/paper/decisiones_s1.jsonl`
  con `opera` (true solo si cambió el cuadrante). Para registrar exige además `research/paper/S1_ACTIVO` (no existe) y
  cierre ≥ 2026-11-30.
- El espejo solo opera en S1 si la decisión dice `opera` o la cuenta no tiene aún posiciones de S1 (arranque); si no,
  deja derivar los pesos, como la regla. `ALPACA_API_KEY_ID_S1` / `ALPACA_API_SECRET_KEY_S1` en `alpaca.env`.
- Tests: `tests/test_s1_vivo.py` (mismo transporte simulado, sin red ni claves, registros reales intactos).

### 4 ter. C1 «Claude gestor» (perfil `C1`; 2026-11-19)
- Cuenta paper del 2.º usuario, claves `ALPACA_API_KEY_ID_C1` / `ALPACA_API_SECRET_KEY_C1`. No usa el mapeo de ETFs:
  opera lo que proponga Claude y valide la guardia (`docs/factors/C1_claude_gestor_spec.md` §3 y §6).
- Métodos nuevos del cliente, todos de **solo lectura** y en los mismos dos hosts: `contrato_opcion`
  (`/v2/options/contracts/…`), `historial_cartera` (`/v2/account/portfolio/history`), `instantaneas_opciones`
  (`/v1beta1/options/snapshots`, feed `indicative`) e `instantaneas_cripto` (`/v1beta3/crypto/us/snapshots`). Las
  órdenes de opciones y cripto usan el `enviar_orden` de siempre (mismo endpoint paper; opciones con
  `position_intent` buy_to_open / sell_to_close; cripto `gtc`). `activo("BTC/USD")` consulta `/v2/assets/BTCUSD`.
- C1 se niega a operar si el perfil declara otra cartera o si la cuenta ya recibió órdenes del espejo.

## 5. Comandos
```bash
.venv/bin/python -m src.broker.alpaca perfiles                 # qué perfiles hay (sin mostrar claves)
.venv/bin/python -m src.broker.alpaca estado [--perfil B1] [--json]   # mercado, cuenta, posiciones, precios IEX
.venv/bin/python -m src.broker.espejo --cartera B1 --dry-run    # (por defecto) calcula y apunta el plan, no envía
.venv/bin/python -m src.broker.espejo --cartera B1 --ejecutar   # envía a la cuenta PAPER y espera ejecuciones
.venv/bin/python -m src.broker.espejo --cartera B1P --cierre 2026-11-30 --dry-run
.venv/bin/python -m src.broker.espejo --seguimiento --perfil B1 # apunta ejecuciones que quedaron pendientes
```

Reglas de las órdenes:
- Mercado abierto y a ≥ 15 min del cierre → **órdenes de mercado** (`day`). Si no → **limit** a ± 0,5 % del precio de
  referencia (compra como máximo +0,5 %, venta como mínimo −0,5 %), que esperan a la apertura y caducan al cierre.
- Ventas primero; las compras se recortan para no gastar más que efectivo + ventas (las limit a su precio límite).
- **Fracciones** si Alpaca marca el activo como `fractionable` (4 decimales, hacia abajo); si no, acciones enteras.
  Orden mínima 10 $. Posiciones fuera del mapeo se venden enteras.
- No envía nada si hay órdenes abiertas en la cuenta. `client_order_id` = `espejo-<cartera>-<cierre>-<ETF>-<lado>-<n>`.
- Falla cerrado: sin precio de un ETF, pesos que no suman 1 o ETF no negociable → no calcula nada.

Registro `~/financial_archive/alpaca/espejo.jsonl` (fuera de git; `FIN_ALPACA_DIR`), una línea por evento:
`plan` (dry-run o ejecutado: pesos de la decisión, mercado, precios, cierre de la sesión del cierre de mes, posiciones
antes, órdenes, rotación y coste teórico), `orden` / `orden_rechazada` y `ejecucion` (precio medio, cantidad,
`deslizamiento_pb_vs_ref` frente al precio al enviar, `deslizamiento_pb_vs_cierre` frente al cierre IEX de la última
sesión ≤ fin de mes, que es el precio al que «opera» el paper teórico, y `coste_teorico_pb`). Positivo = peor.
El de «vs cierre» mezcla deslizamiento y lo que se movió el mercado entre el cierre y la orden (días): es el coste del
retraso de ejecución, que el paper teórico supone cero.

## 6. Límites (léelos antes de sacar conclusiones)
- **IEX ≠ todo el mercado:** el feed gratuito es solo la bolsa IEX (≈ 2-3 % del volumen de EE. UU.). Precios casi
  iguales a los consolidados en ETFs líquidos, pero el volumen, las barras de 1 min y el cierre «IEX» pueden diferir del
  oficial; en momentos de poca actividad la cotización IEX puede ser ancha o faltar (se usa el último trade).
- **Paper no simula bien la liquidez:** Alpaca rellena órdenes de mercado al precio de cotización disponible, sin
  impacto de mercado ni cola real; las limit se ejecutan cuando el precio las toca, sin posición en cola. Con 100 000 $
  en URTH/IEI/GLD el impacto real sería pequeño, pero el deslizamiento paper es **optimista**.
- No hay comisiones en Alpaca (EE. UU.), ni TER, ni divisa: el coste realista para un inversor en EUR con UCITS es otro.
- Los datos de Alpaca no entran en el warehouse ni en ningún modelo: es una comprobación lateral.
- Horario: mercado de EE. UU. (15:30-22:00 hora de Madrid); el calendario/festivos vienen de Alpaca (`/v2/clock`).

## 7. Automatización (INSTALADA 2026-11-19)
Hecho así (difiere de la propuesta de abajo en dos cosas): la fecha de inicio de ejecución está en el script
(`ALPACA_EJECUTA_DESDE="2027-01"`, mes en que corre `paper_mensual.sh`; `FIN_ALPACA_EJECUTAR=0/1` en el entorno manda),
y el `--seguimiento` de las 3 cuentas va al final de la diaria (`scripts/actualizar.sh`), no en `paper_mensual.sh`
(que no hace nada los días 1-2). Log: `~/financial_archive/logs/AAAA-MM-DD_alpaca.log`. Panel: sección al final de
«Mi cartera» (`FIN_PANEL_SIN_ALPACA=1` la apaga; los tests la apagan siempre). Tests: `tests/test_paper_mensual.py`
(`test_espejo_alpaca_*`) y `tests/test_alpaca.py::test_panel_engancha_alpaca_en_mi_cartera_y_se_puede_apagar`.

Propuesta original:
Enganche en `scripts/paper_mensual.sh` **después** de cada registro, en un bloque que no puede afectar a nada:
salida ignorada (`|| true`), sin `set -e`, sin tocar el código de salida del script, log propio y sin escribir en el
repo (el espejo escribe solo en `~/financial_archive/alpaca`). Solo dry-run hasta que exista `FIN_ALPACA_EJECUTAR=1`
(en el plist de launchd o en el entorno); el propio Python lo vuelve a comprobar con `--auto`.

```bash
# --- Espejo Alpaca PAPER (docs/broker/alpaca.md §7): nunca afecta a los registros ni a la diaria ---
espejo_alpaca() {   # $1 = cartera (B0 | B1 | B1P)
  local modo="--dry-run"; [ "${FIN_ALPACA_EJECUTAR:-0}" = 1 ] && modo="--ejecutar"
  .venv/bin/python -m src.broker.espejo --cartera "$1" $modo --auto \
    >> "$LOGDIR/$(date +%Y-%m-%d_%H%M)_alpaca.log" 2>&1 || true
}
```
y llamarlo así (solo cuando el registro de ese mes acaba de quedar hecho):
- tras `touch "$LOGDIR/.b1p_hecho_$MES"` → `espejo_alpaca B1P`
- tras `touch "$LOGDIR/.paper_hecho_$MES"` → `espejo_alpaca B1` (y `espejo_alpaca B0` si hay perfil B0)

Si no hay claves, cada llamada imprime «Alpaca no configurado» y sale con 0. Como el registro corre a las 10:00 (hora de
Madrid, mercado de EE. UU. cerrado), las órdenes serían limit ± 0,5 % que esperan a la apertura de las 15:30; las
ejecuciones se apuntan con `--seguimiento` (añadirlo a la diaria con `|| true` si se quiere). Para activarlo hay que
revisar y commitear el cambio de `paper_mensual.sh` (la regla de árbol limpio no cambia: el espejo no escribe en el
repo).

## 8. Tests
`tests/test_alpaca.py` (sin red: un transporte simulado; cualquier intento de red real falla el test): rechazo del
endpoint real (URL, fichero, entorno, perfil, cliente), que todas las llamadas van a paper/datos y con feed IEX, claves
ausentes, aviso de permisos, que las claves no salen en repr, errores, stdout/stderr, logs ni registro, horario de
mercado y tipo de orden, redondeos (fracciones, enteras, límites, mínimo), rebalanceo con ventas primero, recorte al
presupuesto, una cuenta = una cartera, dry-run sin envíos, `--auto` exige `FIN_ALPACA_EJECUTAR=1` y no repite, registro
de ejecución con deslizamiento, sin envíos con órdenes abiertas, y la sección del panel.
