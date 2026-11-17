# Ensayo en seco del cierre de noviembre de 2026 (17-nov-2026)

Objetivo: que las primeras emisiones automáticas no fallen. Las fechas que se ensayan son: **1-dic**, 1.ª emisión de
«Verificación»; **3-dic**, 1.er registro en vivo de E1/E1b y B1/B1′ (cierre 2026-11-30, el primero de B1′). INT-11
(20-nov) ya se ensayó el 14-nov; aquí solo se comprueba que lo cambiado no lo rompe.
No se ha tocado ningún registro real, `~/financial_archive`, `main` ni el remoto. No se ha cambiado ningún modelo
congelado ni su sha256: `metodo.py` de verificación sigue en `0c453ee9…`, y los modelos E1/E1b, B1′ y K1 se comprobaron
al registrar.

## 1. Cómo se ha aislado

- **Copia del repo** (`git clone` de esta rama) en el scratchpad, en `main`, con un **remoto bare de prueba**. Ahí sí
  se commitea y se hace push, pero contra ese remoto. Su `.venv` y su `.env` son enlaces a los reales (solo lectura).
- **Warehouse**: la instantánea del 16-nov (`warehouse_snap_1611.duckdb`, construida el 16-nov a las 19:16). Para
  recorrer el camino de registro hacía falta una variante **sintética** (`wh_dic03.duckdb`): `built_at` = 3-dic 07:50,
  y `SP500` y `ecb_eurusd_d` alargados con un paseo aleatorio hasta el 30-nov. **Las cifras registradas en el ensayo
  son, por tanto, ficticias** (σ̂′ 18,9 % → B1′ 61,9 %); lo que se ha probado es el camino, no el valor.
- **Fechas**: `paper_mensual.sh` acepta ahora `FIN_HOY`/`FIN_AHORA` (como `int11_vivo_mensual.sh`). Los `.py` no tienen
  fecha inyectable, así que el día se simula con un `sitecustomize.py` que **no está en el repo** (`PYTHONPATH`): cambia
  `date.today()` y `datetime.now()` solo dentro de `src.*`, `scripts.*` y `__main__`. La primera versión parcheaba el
  módulo `datetime` entero y rompía pandas/dateutil, lo que daba segfault y `TypeError` con `relativedelta`.
- **Rutas**: `FIN_REPO`, `FIN_LOGDIR`, `FIN_NOTA`, `FIN_DATA_ROOT`, `FIN_VERIF_DIR` y `FIN_VERIF_RESUMEN` apuntan al
  scratchpad. La verificación se probó **sin** `FIN_VERIF_REGISTRO` (con esa variable no commitea), dentro de la copia,
  para ver el auto-commit de verdad. `FIN_SIN_AVISOS=1` evita las notificaciones de macOS.
- `actualizar.sh` no tiene fecha ni rutas inyectables. Se probó en un **repo de juguete** con un `Makefile` falso
  (`HOME` falso, así que los logs no van a `~/financial_archive`).

## 2. Calendario y lógica de fechas

| día | qué corre | condición | resultado del ensayo |
|---|---|---|---|
| dom 22-nov y 29-nov, 7:00 | semanal (`actualizar.sh semanal`) | launchd; al encender, `arranque` si tiene > 7 días | deja informes **sin commitear**, que bloqueaban el día 3 (F1). Arreglado |
| lun 30-nov | diaria; paper 10:00 | paper: día ≥ 3, pero las marcas de nov ya existen; E1 y B1′ con `--auto` ven el cierre 31-oct (< 30-nov) → rc 0 | no hace nada (correcto: noviembre aún no ha cerrado) |
| **mar 1-dic, 7:30** | diaria → `make verif` | regla 5 del método: periodo acabado y anterior publicado | **emite IPC, IPC subyacente, nóminas y paro de 2026-11**; PIB 2026-T4 espera (hacen falta los 3 meses del trimestre). Commit y push solo de `research/verif/vivo_v1.jsonl` |
| 1 y 2-dic | paper | día < 3 | sale sin hacer nada |
| **jue 3-dic, 10:00** | paper: E1/E1b → K1 → B1′ → B1 | día ≥ 3; warehouse construido después del 30-nov (E1); dato a ≤ 5 días del cierre (B1/B1′); `ACTIVO` | **registra los tres**. Cada commit lleva solo su fichero (`e1_vivo.jsonl` con 16 países; `decisiones_b1prima.jsonl`, 1.ª línea; `decisiones.jsonl`, 2.ª línea) y se sube. K1: «t = 2025, no toca» (primer registro ≈ 2027) |
| 4-dic y siguientes | paper | marcas `.e1/.b1p/.paper_hecho_2026-12` | solo K1 vuelve a mirar (es anual); nada más |
| dom 6-dic | semanal → sección 5f | — | 5f con B1 (oct y nov) y B1′ (nov): «sin meses valorables todavía», sin errores |
| dom 20-dic, 10:30 | INT-11 | día ≥ 20 | sin el arreglo F1, la semanal del mismo día dejaría el árbol sucio y la emisión abortaría |

**Recuperada al encender.**
- Diaria: el modo `pendiente` de `arranque` la lanza cualquier día de lunes a sábado después de las 7:30. La
  verificación va dentro, así que se emite igual, solo que más tarde.
  - Las variables se recalculan con `as_of(hoy − 1)`.
  - Si el Mac se enciende el día de una publicación después de las 12:00 UTC, la predicción queda *anulada* al puntuar.
  - Si el dato ya ha salido, no se emite nada para ese periodo («nunca se recupera»).
  - En diciembre esto no pasa el día 1: el IPC sale ≈ 10-dic y las nóminas el 4-dic.
- Paper: launchd lo lanza al cargar la sesión (`RunAtLoad`) y a las 10:00. Antes arrancaba a la vez que `arranque` y
  no esperaba a la diaria (F2).
- Si el Mac está apagado el 3-dic, el registro se hace el primer día de diciembre en que corra. El cierre sigue siendo
  el 30-nov: `--auto` siempre toma el último fin de mes pasado, y `validar` exige que no haya saltos.

## 3. Escenarios probados (copia del repo, 3-dic salvo que se diga)

| # | escenario | esperado | resultado |
|---|---|---|---|
| A | warehouse del 16-nov (sin datos del cierre) | E1 rc 6; B1′ y B1 «sin dato reciente para el cierre» | ✅ falla cerrado, sin escribir nada |
| B | warehouse sintético, árbol limpio | registra E1, B1′ y B1, y sube | ✅ 3 commits de un fichero cada uno; en sincronía con el remoto |
| G | se repite el mismo día (14:00) y el 4-dic | no registra de nuevo | ✅ |
| C | informes de la semanal del 29-nov sin commitear | E1, B1′ y B1 abortan («árbol de git sucio», rc 5) | ✅ abortan (confirmado F1); con `commit_informes.sh` registran |
| E | el commit falla (hook) a mitad del registro | el árbol queda limpio y se reintenta mañana | ❌ antes (F3) / ✅ ahora |
| F | el push falla (remoto inaccesible) | commit local; al día siguiente se sube | ❌ antes (F4: no se reintentaba) / ✅ ahora (`empuja_pendientes`) |
| D1 | 3-dic a las 7:05 (Mac encendido antes de la diaria) | no registra; lo hace la cita de las 10:00 | ✅ |
| D2 | `.actualizar.lock` presente | no registra | ✅ |
| D3 | repo en otra rama | no registra; nota | ✅ (antes commiteaba en esa rama y hacía `push origin main` sin ese commit) |
| D4 | 1 y 2-dic | nada | ✅ |
| V | verificación el 1-dic a las 7:40, con un fichero sin rastrear y otro **en el índice** | emite; el commit lleva solo `vivo_v1.jsonl`; lo ajeno sigue igual | ✅ 4 predicciones, `metodo_sha256` correcto, `emitida_utc` 06:40Z; `README.md` sigue en el índice y `no_rastreado.txt` sin tocar |
| I | INT-11 `FIN_INT11_ENSAYO=1 FIN_HOY=2026-11-20` sobre la copia (`env -i`) | «saldría» | ✅ 14 países, nada escrito |
| L | `actualizar.sh semanal` (juguete) con un lock de 5 h | quita el lock, corre y commitea solo los informes | ✅ |

Formato: las líneas registradas tienen los mismos campos que el código congelado.
- **B1′**: `cierre`, `sigma_hat_prima`, `f_varianza_mes`, `n_sesiones_mes_siguiente` = 22 (diciembre 2026, calendario
  NYSE), `rasgos`, `sha256_parametros` = `064ebd8c…`, `registrado`, `git_head`.
- **E1**: `p_L`, `p_A`, `p_L6`, `p_A6`, `modelos_sha256` = `227ffa8c…`, `modelos6_sha256` = `f627295e…`, `mes_dato`,
  `warehouse`.
- **Verificación**: los campos de `metodo_v1.md` §Registro.
- El informe 5f (`docs/factors/paper_informe_formato.md`) se genera con la 1.ª línea de B1′ sin errores.

## 4. Fallos encontrados y arreglos (rama `worktree-agent-ac434690b5a0f790c`)

- **F1 (grave): la semanal deja informes sin commitear.** Son `obsidian/Reports/<día>_semanal.md`, `_signal.json` y
  `docs/data/audit_<día>_series.csv`. Como E1/E1b, B1′, B1, K1 e INT-11 exigen árbol limpio, el 3-dic **los tres
  registros abortaban** (rc 5) y seguían abortando cada día hasta que se commitease a mano. Cada domingo vuelve a pasar,
  y el 20-dic (domingo) le tocaría a INT-11.
  - Arreglo: `scripts/commit_informes.sh`, al que llama `actualizar.sh` al acabar la semanal. Commitea **solo** esos
    patrones (`git commit -- <rutas>`), sin push, y solo en `main`.
  - No toca la regla congelada de INT-11 (árbol limpio salvo su carpeta): es la tercera opción frente a las dos que
    apuntaba la Bitácora del 14-nov.
  - Va en un commit aparte, **para que lo revises** (el repo es público y el `push` del siguiente registro subirá los
    informes, igual que cuando los commiteas tú).
- **F2: carrera al encender el Mac.** `paper_mensual.sh` comprobaba el lock justo cuando `arranque` aún no lo había
  creado (los dos esperan a la red), y antes de las 7:30 no había nada que esperar.
  - El 17-nov el paper corrió a las 07:19, con el Mac recién encendido. En diciembre habría leído el warehouse mientras
    se reconstruía y habría coincidido con el commit de la verificación.
  - Arreglo:
    - antes de las 7:30, de lunes a sábado y con la diaria pendiente, sale (lo hace la cita de las 10:00);
    - si la diaria toca, la espera hasta 60 min (como INT-11);
    - si después sigue habiendo una actualización en marcha, no registra ese día (antes seguía adelante a los 60 min).
- **F3: commit fallido a mitad.**
  - E1 no limpiaba nada: su fichero se quedaba en el índice.
  - B1′ hacía `git checkout HEAD -- f || rm -f f`. Con un fichero nuevo ya añadido al índice, eso deja `AD`
    (reproducido).
  - En los dos casos el árbol quedaba sucio y **E1, B1′ y B1 abortaban para siempre**.
  - Arreglo: la función `restaura` (`git reset` + `checkout`/`rm`) para los tres registros. Solo actúa si su fichero
    quedó sin commitear.
- **F4: push fallido.**
  - Lo que pasaba: el reintento veía «ya registrado», ponía la marca y **no volvía a subir**. Es el punto débil que ya
    anotaba `B1prima_implementacion.md` §4.9.
  - Arreglo: `empuja_pendientes`, que hace `push` si `main` va por delante de `origin/main`.
- **F5: fuera de `main`.** Los `.py` commiteaban en la rama actual y hacían `push origin main`, de modo que el registro
  se quedaba fuera de `main`. Arreglo: si el repo no está en `main`, no registra (como INT-11).
- **F6: lock huérfano.** Si el Mac se apaga a la fuerza a mitad de una actualización, `.actualizar.lock` se queda y ni
  la diaria ni la semanal vuelven a correr nunca. Arreglo: un lock de más de 4 h se quita (la semanal dura < 2 h).
- **Menores:**
  - `PYTHONUNBUFFERED=1`: con un traceback, el «motivo» de la nota era `}` (la salida estándar se vaciaba después).
  - `make >> $LOG` en lugar de `>`, para no borrar el aviso del lock huérfano.
  - La copia de `com.financialkb.paper.plist` (instalado, pero no estaba en `scripts/launchd/`).
  - `docs/automatizacion.md` al día.

Tests nuevos: `tests/test_paper_mensual.py`, 10 tests con un repo de juguete y un `python` falso (días 1-2, 7:05,
lock, rama, registro completo, informes, commit y push fallidos). Junto con los de INT-11, paper, B1′, informe,
verificación, E1 y K1: 68 tests OK. Los tests de B1′ y E1 leen el warehouse/archivo en solo lectura.

## 5. Observaciones (no cambiadas)

- **WTI del mes incompleto el 1-dic.** `DCOILWTICO` en FRED va con ≈ 5 días de retraso (el 16-nov llegaba al 11-nov).
  El puente del IPC general usará la media de noviembre **sin la última semana**, mientras que el retrospectivo usa
  meses completos. Es propio del método v1 congelado (regla 1: «lo publicado hasta el día anterior»), así que no se
  toca. Si se ve sesgo en vivo, sería materia de un v2.
- **El aviso de push es engañoso.** Con el push fallido, la nota dice «❌ no registrada» aunque el registro esté
  commiteado. Al día siguiente sale «⬆️ subidos commits pendientes».
- `int11_vivo_mensual.sh` tiene la misma ventana que F2 si el Mac se enciende **antes de las 7:30 de un día ≥ 20**:
  emite antes de la diaria, con los datos del día anterior. No se ha tocado: ya estaba ensayado y aprobado, y el
  warehouse se cambia de forma atómica.
- `restaura` devuelve un registro a HEAD si su intento falló y el fichero quedó modificado: no edites a mano un
  `.jsonl` de registro sin commitear.
- K1 escribe un log cada día (anual, «no toca»), igual que antes.

## 6. A mano, antes del 20-nov y del 30-nov

1. **No fusionar esta rama mientras corre `actualizar.sh`.** Hoy hay una semanal en marcha desde las 7:25, y bash lee
   el script mientras se ejecuta: cambiarlo debajo puede romper esa corrida. Hay que fusionar cuando no exista
   `~/financial_archive/logs/.actualizar.lock`.
2. **Antes del 20-nov (INT-11):** al acabar la semanal de hoy quedarán sin commitear
   `obsidian/Reports/2026-11-17_*` y `docs/data/audit_2026-11-17_series.csv`. Hay que commitearlos, a mano o con
   `bash scripts/commit_informes.sh` tras fusionar. El arreglo F1 solo actúa en las semanales siguientes.
3. Revisar y decidir el commit de F1 (auto-commit de informes). Si no lo quieres, la alternativa es commitear a mano
   cada domingo antes del día 3 y del día 20.
4. Dejar el checkout principal en `main` y con el árbol limpio el 1-dic y el 3-dic. `research/paper/ACTIVO` ya está.
5. Tener el Mac encendido o en reposo (no apagado) el 1-dic antes de las 12:00 UTC (13:00 en España). Si no, la
   verificación se emite al encender, pero más tarde.

## 7. Cómo repetirlo

Hay que clonar la rama en una carpeta temporal, con un remoto bare, y enlazar `.venv` y `.env`. Después:

```
FIN_REPO=<copia> FIN_LOGDIR=<tmp>/logs FIN_NOTA=<tmp>/nota.md FIN_DATA_ROOT=<tmp> FIN_HOY=2026-12-03 FIN_AHORA=1000 \
FIN_ESPERA_RED=0 FIN_ESPERA_DIARIO_MIN=0 FIN_ESPERA_LOCK_MIN=0 FIN_SIN_AVISOS=1 \
FIN_FAKE_NOW=2026-12-03T10:00 PYTHONPATH=<carpeta con el sitecustomize del §1> bash <copia>/scripts/paper_mensual.sh
```

Para la verificación, la misma copia con `FIN_FAKE_NOW=2026-12-01T07:40`, `FIN_VERIF_DIR` y `FIN_VERIF_RESUMEN` en
la carpeta temporal y `.venv/bin/python scripts/verif_registrar.py`. **Nunca con `FIN_FAKE_NOW` en el repo real.**
