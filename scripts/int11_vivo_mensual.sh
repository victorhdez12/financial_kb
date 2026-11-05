#!/bin/bash
# Registro mensual en vivo de INT-11 v3.1 (docs/int/INT11_fuente_bolsa_vivo.md §9; INT11_registro_vivo.md §2).
# Corre cada día a las 10:30 (y al encender); desde el día 20 emite una vez por mes, commitea y sube.
REPO="$HOME/Proyectos/financial_kb"
LOGDIR="$HOME/financial_archive/logs"
MES="$(date +%Y-%m)"
DIA="$(date +%d)"
cd "$REPO" || exit 1
mkdir -p "$LOGDIR"
NOTA="$REPO/obsidian/Proyecto/Actualizaciones.md"
avisa() { /usr/bin/osascript -e "display notification \"$1\" with title \"financial_kb · INT-11 vivo\"" 2>/dev/null || true; }
[ "$((10#$DIA))" -lt 20 ] && exit 0
[ -f "$LOGDIR/.int11_hecho_$MES" ] && exit 0
for _ in $(seq 1 60); do curl -sS -o /dev/null --max-time 5 https://api.stlouisfed.org/ 2>/dev/null && break; sleep 10; done
for _ in $(seq 1 120); do [ -d "$LOGDIR/.actualizar.lock" ] || break; sleep 30; done
LOG="$LOGDIR/$(date +%Y-%m-%d_%H%M)_int11vivo.log"
if .venv/bin/python -m scripts.int11_v3_hoy --registro > "$LOG" 2>&1 \
   && git add research/int/int11_v3_1_vivo \
   && git commit -q -m "INT-11 v3.1 live record $MES

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" >> "$LOG" 2>&1 \
   && git push -q origin main >> "$LOG" 2>&1; then
  touch "$LOGDIR/.int11_hecho_$MES"
  echo "- **$(date '+%Y-%m-%d %H:%M')** · INT-11 vivo · ✅ emisión $MES registrada y subida · log \`$(basename "$LOG")\`" >> "$NOTA"
else
  echo "- **$(date '+%Y-%m-%d %H:%M')** · INT-11 vivo · ❌ fallo (se reintenta mañana) · log \`$(basename "$LOG")\`" >> "$NOTA"
  avisa "Registro INT-11 fallido: mira el log; reintento mañana"
fi
find "$LOGDIR" -name '*_int11vivo.log' -mtime +400 -delete 2>/dev/null
exit 0
