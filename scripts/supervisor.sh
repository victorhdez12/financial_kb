#!/bin/bash
# Supervisor de carteras (docs/factors/supervisor_carteras_spec.md v1.0; launchd com.financialkb.supervisor: 8:00 diario).
#   scripts/supervisor.sh    .venv/bin/python -m src.paper.supervisor --registrar
#                            paquete (cuentas vía src/broker/alpaca.py, registros, diarios, logs) → límites duros en
#                            código (crean research/paper/C1_PARADA o M1_PARADA y avisan) → agente de solo lectura →
#                            informe en obsidian/Carteras/Supervisor/AAAA-MM-DD.md (fuera de git). Nunca opera.
# Pruebas: FIN_REPO, FIN_LOGDIR, FIN_NOTA, FIN_SIN_AVISOS=1.
set -u
REPO="${FIN_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
LOGDIR="${FIN_LOGDIR:-$HOME/financial_archive/logs}"
NOTA="${FIN_NOTA:-$REPO/obsidian/Proyecto/Actualizaciones.md}"
LOG="$LOGDIR/$(date '+%Y-%m-%d_%H%M')_supervisor.log"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1
mkdir -p "$LOGDIR"
cd "$REPO" || exit 1
[ -x .venv/bin/python ] || { echo "$(date) sin .venv: nada que hacer" >> "$LOG"; exit 0; }
# no pisar la actualización diaria (reconstruye el warehouse): espera a que acabe
for ((i = 0; i < ${FIN_ESPERA_LOCK_MIN:-30} * 2; i++)); do [ -d "$LOGDIR/.actualizar.lock" ] || break; sleep 30; done

.venv/bin/python -m src.paper.supervisor --registrar >> "$LOG" 2>&1
RC=$?
if [ $RC -ne 0 ] && [ -f "$NOTA" ]; then
  /usr/bin/python3 - "$NOTA" "- **$(date '+%Y-%m-%d %H:%M')** · Supervisor · ❌ sin informe del agente (rc=$RC) · log \`$(basename "$LOG")\`" <<'PY'
import sys
p, linea = sys.argv[1], sys.argv[2]
s = open(p, encoding="utf-8").read()
marca = "<!-- entradas -->\n"
s = s.replace(marca, marca + linea + "\n", 1) if marca in s else s + "\n" + linea + "\n"
open(p, "w", encoding="utf-8").write(s)
PY
fi
find "$LOGDIR" -name '*_supervisor.log' -mtime +400 -delete 2>/dev/null
exit $RC
