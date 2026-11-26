#!/bin/bash
# Actualización automática de financial_kb (la lanza launchd; ver docs/automatizacion.md).
#   scripts/actualizar.sh diario    -> make daily   (fuentes diarias + warehouse + régimen)
#   scripts/actualizar.sh semanal   -> make semanal (todas las fuentes + warehouse + régimen + auditoría + reporte)
#   scripts/actualizar.sh pendiente -> al encender el Mac (launchd RunAtLoad) y cada hora: lanza la que falte hoy,
#     y después los ciclos C1/M1/A1 perdidos hoy (scripts/recupera_gestores.sh).
#     launchd no recupera las citas perdidas con el Mac APAGADO (solo en reposo). Este modo mira las marcas
#     ~/financial_archive/logs/.hecho_diario y .hecho_semanal: si la semanal tiene más de 7 días -> semanal;
#     si no, si hoy es lun-sáb, ya son las 7:30 y la diaria de hoy no está hecha -> diaria; si no, nada.
# Deja el log en ~/financial_archive/logs/, apunta el resultado en obsidian/Proyecto/Actualizaciones.md
# y avisa con una notificación de macOS si alguna fuente falla o la auditoría encuentra algo crítico.
# Tras la actualización, otra notificación si hay ALERTAS FUERTES NUEVAS de flujos en «Mis activos» (src/report/alertas.py,
# docs/panel/alertas_v1.md; nunca la misma alerta dos veces). Desactivar: FIN_ALERTAS_NOTIFICAR=0 o
# {"notificar": false} en ~/financial_archive/config/alertas.json (fuera de git).
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
  else   # nada que actualizar: solo los ciclos C1/M1/A1 perdidos hoy (scripts/recupera_gestores.sh)
    bash "$REPO/scripts/recupera_gestores.sh" >> "$LOGDIR/$(date +%Y-%m-%d)_recupera.log" 2>&1; exit 0
  fi
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
# Lock huérfano (Mac apagado a la fuerza a mitad de una actualización: el trap no llega a borrarlo). Sin esto, nada
# volvía a actualizarse y el paper/E1/INT-11 esperaban a una actualización que no existe. La semanal dura < 2 h.
if [ -d "$LOCK" ] && [ -n "$(find "$LOCK" -maxdepth 0 -mmin +240 2>/dev/null)" ]; then
  echo "$(date) lock de más de 4 h (huérfano): lo quito" >> "$LOG"; rmdir "$LOCK" 2>/dev/null
fi
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date) ya hay una actualización en marcha; salgo" >> "$LOG"; exit 0
fi
trap 'rmdir "$LOCK"' EXIT

INICIO=$(date +%s)
make "$OBJ" >> "$LOG" 2>&1   # >>: conserva el aviso del lock huérfano (el log es nuevo en cada corrida)
RC=$?
DUR=$(( ($(date +%s) - INICIO) / 60 ))
# La semanal deja informes nuevos en obsidian/Reports y docs/data: commitearlos (solo esos, sin push) para que los
# registros en vivo que exigen árbol limpio (E1/B1′/B1 el día 3, INT-11 el día 20) no aborten (ensayo 17-nov).
[ "$MODO" = semanal ] && bash "$REPO/scripts/commit_informes.sh" "$REPO" >> "$LOG" 2>&1
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
# Alertas fuertes nuevas de flujos (descriptivas): el texto lo da Python (sin comillas dobles); vacío = nada nuevo
ALERTAS="$("$REPO/.venv/bin/python" -m src.report.alertas --notificar 2>>"$LOG" | tail -1)"
if [ -n "$ALERTAS" ]; then
  echo "$(date) alertas notificadas: $ALERTAS" >> "$LOG"
  /usr/bin/osascript -e "display notification \"$ALERTAS\" with title \"financial_kb · alertas\"" 2>/dev/null || true
fi
# Cuentas Alpaca PAPER (20-nov-2026): ya no hay espejo de B1/D1 (solo papel); las 3 cuentas las gestiona el agente
# (C1 …4JGR, M1 …ZFJX, A1 …X9F9), y cada ciclo apunta el estado final de sus órdenes del día anterior
# (`seguimiento_previo`). Aquí solo se deja en el log una foto de SOLO LECTURA de cada cuenta (valor, posiciones).
# Nunca afecta a la diaria; sin claves de un perfil no hace nada (docs/broker/alpaca.md §7).
for P in C1 M1 A1; do
  { echo "== $(date '+%F %T') estado $P"
    "$REPO/.venv/bin/python" -m src.broker.alpaca estado --perfil "$P"; } \
    >> "$LOGDIR/$(date +%Y-%m-%d)_alpaca.log" 2>&1 || true
done
# Diagnósticos automáticos (docs/panel/diagnosticos_v0.md): disparadores + nota con claude -p (tope 3/semana). Nunca
# afecta a la diaria ni a su código de salida (|| true; el exit de abajo es $RC de make). FIN_DIAG=0 lo apaga.
if [ "${FIN_DIAG:-1}" != 0 ]; then
  bash "$REPO/scripts/diagnostico.sh" >> "$LOGDIR/$(date +%Y-%m-%d)_diag.log" 2>&1 || true
fi
# Modo pendiente: tras la actualización recuperada, también los ciclos C1/M1/A1 perdidos hoy. Antes se suelta el
# cerrojo de la actualización (los gestores lo esperan hasta 30 min).
if [ -n "${RECUPERADA:-}" ]; then
  rmdir "$LOCK" 2>/dev/null; trap - EXIT
  bash "$REPO/scripts/recupera_gestores.sh" >> "$LOGDIR/$(date +%Y-%m-%d)_recupera.log" 2>&1 || true
fi
# Logs de más de 60 días fuera
find "$LOGDIR" -name '*.log' -mtime +60 -delete 2>/dev/null
exit $RC
