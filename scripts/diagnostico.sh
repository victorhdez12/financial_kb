#!/bin/bash
# Diagnósticos automáticos («¿por qué ha pasado esto?»), docs/panel/diagnosticos_v0.md (v1.0 aprobada el 19-nov-2026).
# Lo llama scripts/actualizar.sh al final (con `|| true`: nunca afecta a la diaria). FIN_DIAG=0 lo apaga.
#   scripts/diagnostico.sh                         -> disparadores del día + nota con claude -p (tope 3/semana) + seguimiento
#   scripts/diagnostico.sh --fecha 2026-11-18 --forzar   -> ensayo de un día concreto (gasta cupo igual)
#   scripts/diagnostico.sh --sin-claude            -> solo paquetes de datos (sin IA)
# Claude (~/.local/bin/claude) corre con herramientas Read/Write limitadas al paquete y a UN fichero de
# obsidian/Diagnosticos/, sin Bash, sin web, sin ajustes de usuario/proyecto, 10 min como máximo (src/diag/explicador.py).
# Las notas NO se commitean (obsidian/Diagnosticos/*.md está en .gitignore). Si hay algo nuevo: aviso de macOS y se
# regenera el panel para que salga la tarjeta en «Hoy».
set -u
[ "${FIN_DIAG:-1}" = 0 ] && { echo "diagnósticos apagados (FIN_DIAG=0)"; exit 0; }
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 0
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PY="$REPO/.venv/bin/python"
echo "== $(date '+%F %T') diagnósticos $*"
SALIDA="$("$PY" -m src.diag.explicador "$@" 2>&1)"
RC=$?
echo "$SALIDA"
NUEVO="$(echo "$SALIDA" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}: |"nota": "/' | head -3 | tr '\n' ' ')"
if [ -n "$NUEVO" ]; then
  MSG="$(echo "$NUEVO" | tr -d '"\\' | cut -c1-200)"
  /usr/bin/osascript -e "display notification \"$MSG\" with title \"financial_kb · diagnóstico\"" 2>/dev/null || true
  "$PY" -m src.report.panel >/dev/null 2>&1 || echo "AVISO panel no regenerado"
fi
exit $RC
