#!/bin/bash
# Actualización automática de financial_kb (la lanza launchd; ver docs/automatizacion.md).
#   scripts/actualizar.sh diario    -> make daily   (fuentes diarias + warehouse + régimen)
#   scripts/actualizar.sh semanal   -> make semanal (todas las fuentes + warehouse + régimen + auditoría + reporte)
#   scripts/actualizar.sh pendiente -> al encender el Mac (launchd RunAtLoad): lanza la que falte hoy.
#     launchd no recupera las citas perdidas con el Mac APAGADO (solo en reposo). Este modo mira las marcas
#     ~/financial_archive/logs/.hecho_diario y .hecho_semanal: si la semanal tiene más de 7 días -> semanal;
#     si no, si hoy es lun-sáb, ya son las 7:30 y la diaria de hoy no está hecha -> diaria; si no, nada.
# Deja el log en ~/financial_archive/logs/, apunta el resultado en obsidian/Proyecto/Actualizaciones.md
# y avisa con una notificación de macOS si alguna fuente falla o la auditoría encuentra algo crítico.
set -u
MODO="${1:-diario}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$HOME/financial_archive/logs"
NOTA="$REPO/obsidian/Proyecto/Actualizaciones.md"
STAMP="$(date '+%Y-%m-%d_%H%M')"
LOG="$LOGDIR/${STAMP}_${MODO}.log"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
mkdir -p "$LOGDIR"
cd "$REPO" || exit 1

HOY="$(date +%Y-%m-%d)"
if [ "$MODO" = pendiente ]; then
  ULT_S="$(cat "$LOGDIR/.hecho_semanal" 2>/dev/null || echo 1970-01-01)"
  ULT_D="$(cat "$LOGDIR/.hecho_diario" 2>/dev/null || echo 1970-01-01)"
  DIAS_S=$(( ( $(date +%s) - $(date -j -f %Y-%m-%d "$ULT_S" +%s) ) / 86400 ))
  AHORA=$(date +%H%M); DOW=$(date +%u)   # 1 = lunes … 7 = domingo
  if [ "$DIAS_S" -gt 7 ] || { [ "$DOW" = 7 ] && [ "$AHORA" -ge 0700 ] && [ "$ULT_S" != "$HOY" ]; }; then MODO=semanal
  elif [ "$DOW" != 7 ] && [ "$AHORA" -ge 0730 ] && [ "$ULT_D" != "$HOY" ] && [ "$ULT_S" != "$HOY" ]; then MODO=diario
  else exit 0; fi
  LOG="$LOGDIR/${STAMP}_${MODO}.log"
  RECUPERADA=" (recuperada al encender)"
fi

# Esperar a tener red (hasta 10 min): al encender el Mac, la tarea recuperada arrancaba sin DNS y fallaban las
# primeras fuentes (semanal del 22-oct: fred_us, fred_extended, fed_yieldcurve, us_treasury, shiller_housing).
for _ in $(seq 1 60); do
  curl -sS -o /dev/null --max-time 5 https://api.stlouisfed.org/ 2>/dev/null && break
  sleep 10
done

case "$MODO" in
  diario)  OBJ=daily ;;
  semanal) OBJ=semanal ;;
  *) echo "uso: $0 diario|semanal|pendiente"; exit 2 ;;
esac

# Evita dos ejecuciones a la vez (la semanal puede tardar)
LOCK="$LOGDIR/.actualizar.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date) ya hay una actualización en marcha; salgo" >> "$LOG"; exit 0
fi
trap 'rmdir "$LOCK"' EXIT

INICIO=$(date +%s)
make "$OBJ" > "$LOG" 2>&1
RC=$?
DUR=$(( ($(date +%s) - INICIO) / 60 ))
# Marca de hecho (la usa el modo pendiente); la semanal también cubre la diaria
if [ $RC -eq 0 ]; then echo "$HOY" > "$LOGDIR/.hecho_$MODO"; [ "$MODO" = semanal ] && echo "$HOY" > "$LOGDIR/.hecho_diario"; fi

FALLOS=$(grep -o 'FALLO [a-z0-9_]*' "$LOG" | sed 's/FALLO //' | sort -u | tr '\n' ' ')
REGIMEN=$(grep -o 'now: .*' "$LOG" | tail -1 | sed 's/^now: //')
CRITICAS=""
if [ "$MODO" = semanal ]; then
  CSV="$REPO/docs/data/audit_$(date +%Y-%m-%d)_series.csv"
  [ -f "$CSV" ] && CRITICAS=$(grep -c ',CR[IÍ]TICA,' "$CSV" || true)
fi

if [ $RC -ne 0 ]; then ESTADO="❌ error (make rc=$RC)";
elif [ -n "$FALLOS" ] || { [ -n "$CRITICAS" ] && [ "$CRITICAS" != "0" ]; }; then ESTADO="⚠️ con avisos";
else ESTADO="✅ ok"; fi

# Nota en Obsidian (la crea si no existe; las entradas nuevas van arriba)
if [ ! -f "$NOTA" ]; then
  printf -- "---\ntipo: actualizaciones\n---\n\n# Actualizaciones automáticas\n\nLas escribe \`scripts/actualizar.sh\` (launchd). Ver [[Proyecto/Estado del proyecto]] y \`docs/automatizacion.md\`.\n\n<!-- entradas -->\n" > "$NOTA"
fi
LINEA="- **$(date '+%Y-%m-%d %H:%M')** · $MODO${RECUPERADA:-} · $ESTADO · ${DUR} min"
[ -n "$FALLOS" ] && LINEA="$LINEA · fuentes con fallo: $FALLOS"
[ -n "$CRITICAS" ] && LINEA="$LINEA · críticas en auditoría: $CRITICAS"
[ -n "$REGIMEN" ] && LINEA="$LINEA · régimen (informativo, no es señal de cartera): $REGIMEN"
LINEA="$LINEA · log \`$(basename "$LOG")\`"
/usr/bin/python3 - "$NOTA" "$LINEA" <<'PY'
import sys
p, linea = sys.argv[1], sys.argv[2]
s = open(p, encoding="utf-8").read()
marca = "<!-- entradas -->\n"
s = s.replace(marca, marca + linea + "\n", 1) if marca in s else s + "\n" + linea + "\n"
open(p, "w", encoding="utf-8").write(s)
PY

if [ "$ESTADO" != "✅ ok" ]; then
  /usr/bin/osascript -e "display notification \"$MODO: $ESTADO ${FALLOS}\" with title \"financial_kb\"" 2>/dev/null || true
fi
# Logs de más de 60 días fuera
find "$LOGDIR" -name '*.log' -mtime +60 -delete 2>/dev/null
exit $RC
