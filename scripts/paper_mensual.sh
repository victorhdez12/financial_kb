#!/bin/bash
# Decisión mensual del paper trading (launchd com.financialkb.paper; docs/factors/paper_trading.md §3).
# Corre cada día a las 10:00 (y al encender el Mac). Desde el día 3 del mes intenta registrar la decisión del último
# fin de mes pasado (paper_decision.py --auto --registrar); si falla, avisa (notificación de macOS + línea en
# obsidian/Proyecto/Actualizaciones.md) y lo reintenta al día siguiente. Si ya está registrada, no hace nada.
# Mientras no exista research/paper/ACTIVO (lo crea el usuario al aprobar el primer ensayo) solo ensaya y avisa.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$HOME/financial_archive/logs"
NOTA="$REPO/obsidian/Proyecto/Actualizaciones.md"
LOG="$LOGDIR/$(date '+%Y-%m-%d_%H%M')_paper.log"
MES="$(date +%Y-%m)"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
mkdir -p "$LOGDIR"
cd "$REPO" || exit 1

[ "$(date +%-d)" -lt 3 ] && exit 0
[ -f "$LOGDIR/.paper_hecho_$MES" ] && exit 0

nota() {   # $1 = línea
  [ -f "$NOTA" ] || return 0
  /usr/bin/python3 - "$NOTA" "- **$(date '+%Y-%m-%d %H:%M')** · paper · $1 · log \`$(basename "$LOG")\`" <<'PY'
import sys
p, linea = sys.argv[1], sys.argv[2]
s = open(p, encoding="utf-8").read()
marca = "<!-- entradas -->\n"
s = s.replace(marca, marca + linea + "\n", 1) if marca in s else s + "\n" + linea + "\n"
open(p, "w", encoding="utf-8").write(s)
PY
}
avisa() { /usr/bin/osascript -e "display notification \"$1\" with title \"financial_kb · paper trading\"" 2>/dev/null || true; }

# esperar a la red y a que termine la actualización diaria (reconstruye el warehouse)
for _ in $(seq 1 60); do curl -sS -o /dev/null --max-time 5 https://api.stlouisfed.org/ 2>/dev/null && break; sleep 10; done
for _ in $(seq 1 120); do [ -d "$LOGDIR/.actualizar.lock" ] || break; sleep 30; done

if [ ! -f "$REPO/research/paper/ACTIVO" ]; then
  [ -f "$LOGDIR/.paper_ensayo_$MES" ] && exit 0
  if .venv/bin/python -m scripts.paper_decision --auto > "$LOG" 2>&1; then
    touch "$LOGDIR/.paper_ensayo_$MES"
    nota "🟡 ensayo listo, pendiente de aprobación (no registrado)"
    avisa "Ensayo del cierre listo: pendiente de tu aprobación"
  else
    nota "❌ ensayo fallido"; avisa "Ensayo fallido: mira el log"
  fi
  exit 0
fi

.venv/bin/python -m scripts.paper_decision --auto --registrar > "$LOG" 2>&1
RC=$?
if [ $RC -eq 0 ]; then
  touch "$LOGDIR/.paper_hecho_$MES"
  if grep -q "registrada y subida" "$LOG"; then nota "✅ decisión registrada y subida"; fi
else
  MOTIVO=$(tail -1 "$LOG" | cut -c1-120)
  nota "❌ no registrada (rc=$RC): $MOTIVO · se reintenta mañana"
  avisa "No se pudo registrar (rc=$RC): $MOTIVO. Reintento mañana."
fi
find "$LOGDIR" -name '*_paper.log' -mtime +400 -delete 2>/dev/null
exit $RC
