#!/bin/bash
# Registro mensual en vivo de INT-11 v3.1 (docs/int/INT11_fuente_bolsa_vivo.md §9; INT11_registro_vivo.md §2).
# Corre cada día a las 10:30 (y al encender); desde el día 20 emite una vez por mes, commitea y sube.
#
# Robustez (ensayo en seco del 14-nov-2026):
#  - Si la emisión del mes YA existe (commit o push fallidos otro día), no se vuelve a emitir (el registro no se
#    sobrescribe y `registrar` abortaría todos los días): solo se reintenta el commit y/o el push.
#  - El commit lleva SOLO la carpeta del registro (`git commit -- <carpeta>`), aunque haya otras cosas en el índice.
#  - Antes de emitir se comprueba que el repo está en `main` y que el árbol está limpio fuera del registro; si no, se
#    anota el motivo concreto (y se avisa) sin lanzar el motor.
#  - Si hoy toca la actualización diaria (lun-sáb ≥ 7:30) y aún no está hecha, se espera a que termine (hasta 60 min),
#    para no leer el warehouse mientras se reconstruye (al despertar el Mac ambas tareas saltan a la vez).
#
# ENSAYO (no escribe nada en el repo ni en el registro; no commitea ni sube; no deja marcas):
#   FIN_INT11_ENSAYO=1 [FIN_HOY=AAAA-MM-DD] [FIN_REPO=…] [FIN_LOGDIR=…] [FIN_NOTA=…] bash scripts/int11_vivo_mensual.sh
#   (FIN_ESPERA_RED / FIN_ESPERA_DIARIO_MIN = 0 quitan las esperas de red y de la diaria; para los tests)
#   FIN_HOY simula el día (condición del día 20 y comprobación de fecha ± 3 días; los datos son los de hoy).
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO="${FIN_REPO:-$HOME/Proyectos/financial_kb}"
LOGDIR="${FIN_LOGDIR:-$HOME/financial_archive/logs}"
ENSAYO="${FIN_INT11_ENSAYO:-0}"
HOY="${FIN_HOY:-$(date +%Y-%m-%d)}"
MES="${HOY:0:7}"
DIA="${HOY:8:2}"
CARPETA="research/int/int11_v3_1_vivo"
ESPERA_DIARIO_MIN="${FIN_ESPERA_DIARIO_MIN:-60}"
cd "$REPO" || exit 1
mkdir -p "$LOGDIR"
NOTA="${FIN_NOTA:-$REPO/obsidian/Proyecto/Actualizaciones.md}"
[ "$ENSAYO" = 1 ] && [ -z "${FIN_NOTA:-}" ] && NOTA="$LOGDIR/int11vivo_ensayo_nota.md"
avisa() { [ "$ENSAYO" = 1 ] && return 0; /usr/bin/osascript -e "display notification \"$1\" with title \"financial_kb · INT-11 vivo\"" 2>/dev/null || true; }
nota() { echo "- **$(date '+%Y-%m-%d %H:%M')** · INT-11 vivo$([ "$ENSAYO" = 1 ] && echo ' (ENSAYO)') · $1 · log \`$(basename "$LOG")\`" >> "$NOTA"; }
[ "$((10#$DIA))" -lt 20 ] && exit 0
[ -f "$LOGDIR/.int11_hecho_$MES" ] && exit 0
for ((i = 0; i < ${FIN_ESPERA_RED:-60}; i++)); do curl -sS -o /dev/null --max-time 5 https://api.stlouisfed.org/ 2>/dev/null && break; sleep 10; done
# la diaria de hoy (lun-sáb desde las 7:30) antes que la emisión; nunca a la vez que una actualización en marcha
DOW="$(date -j -f %Y-%m-%d "$HOY" +%u 2>/dev/null || date +%u)"
for ((i = 0; i < ESPERA_DIARIO_MIN * 2; i++)); do
  [ "$DOW" != 7 ] && [ "$(date +%H%M)" -ge 0730 ] && [ "$(cat "$LOGDIR/.hecho_diario" 2>/dev/null)" != "$HOY" ] \
    && [ "$(cat "$LOGDIR/.hecho_semanal" 2>/dev/null)" != "$HOY" ] || break
  [ "$ENSAYO" = 1 ] && break
  sleep 30
done
for ((i = 0; i < 120; i++)); do [ -d "$LOGDIR/.actualizar.lock" ] || break; [ "$ENSAYO" = 1 ] && break; sleep 30; done
LOG="$LOGDIR/$(date +%Y-%m-%d_%H%M)_int11vivo$([ "$ENSAYO" = 1 ] && echo _ensayo).log"
: > "$LOG"
[ -d "$LOGDIR/.actualizar.lock" ] && echo "AVISO: hay una actualización en marcha (.actualizar.lock)" >> "$LOG"

if [ "$ENSAYO" = 1 ]; then
  .venv/bin/python -m scripts.int11_v3_hoy "$HOY" --ensayo --hoy="$HOY" >> "$LOG" 2>&1
  RC=$?
  if [ $RC -ne 0 ]; then nota "❌ ensayo: el motor falló (rc=$RC)"; elif grep -q "ABORTARÍA" "$LOG"; then
    nota "⚠️ ensayo: la emisión real abortaría ($(grep -A3 'ABORTARÍA' "$LOG" | tail -n +2 | tr '\n' ' '))"
  else nota "✅ ensayo: la emisión de $MES saldría (no se ha escrito nada)"; fi
  echo "ensayo: rc=$RC log=$LOG"
  exit 0
fi

RAMA="$(git symbolic-ref --short -q HEAD)"
if [ "$RAMA" != main ]; then
  echo "el repo está en la rama '${RAMA:-HEAD suelta}', no en main: no se emite" >> "$LOG"
  nota "❌ el repo no está en main (rama '${RAMA:-?}'); se reintenta mañana"; avisa "Registro INT-11: el repo no está en main"
  exit 0
fi
ARCHIVO="$CARPETA/$MES.json"
if [ ! -f "$ARCHIVO" ]; then
  AJENOS="$(git status --porcelain | grep -v " $CARPETA/" | grep -v " ${CARPETA}$")"
  if [ -n "$AJENOS" ]; then
    { echo "árbol de git sucio fuera del registro (commitea o descarta antes de emitir):"; echo "$AJENOS"; } >> "$LOG"
    nota "❌ árbol sucio fuera del registro ($(echo "$AJENOS" | wc -l | tr -d ' ') ficheros; commitea); se reintenta mañana"
    avisa "Registro INT-11: árbol de git sucio; commitea y se reintenta mañana"
    exit 0
  fi
  .venv/bin/python -m scripts.int11_v3_hoy --registro >> "$LOG" 2>&1 || {
    nota "❌ fallo del motor/registro (se reintenta mañana)"; avisa "Registro INT-11 fallido: mira el log; reintento mañana"
    exit 0; }
else
  echo "$ARCHIVO ya existe: no se re-emite; solo se reintenta commit/push" >> "$LOG"
fi
git add "$CARPETA" >> "$LOG" 2>&1
if [ -n "$(git status --porcelain -- "$CARPETA")" ]; then
  git commit -q -m "INT-11 v3.1 live record $MES

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- "$CARPETA" >> "$LOG" 2>&1 || {
    nota "❌ emisión $MES escrita pero el commit falló (se reintenta mañana)"; avisa "Registro INT-11: commit fallido"
    exit 0; }
fi
if git push -q origin main >> "$LOG" 2>&1; then
  touch "$LOGDIR/.int11_hecho_$MES"
  nota "✅ emisión $MES registrada y subida"
else
  nota "⚠️ emisión $MES registrada y commiteada, pero el push falló (se reintenta mañana)"
  avisa "Registro INT-11: emitido y commiteado; falta el push (reintento mañana)"
fi
find "$LOGDIR" -name '*_int11vivo*.log' -mtime +400 -delete 2>/dev/null
exit 0
