#!/bin/bash
# C1 «Claude gestor» (docs/factors/C1_claude_gestor_spec.md v1.0; launchd com.financialkb.c1: 15:45 Madrid, lun-vie).
#
#   scripts/c1_gestor.sh                 ciclo del día (launchd): .venv/bin/python -m src.paper.c1 --auto
#                                        (sin research/paper/C1_ACTIVO no hace nada; con él: paquete → Claude → guardia →
#                                        órdenes PAPER → registro research/paper/decisiones_c1.jsonl → commit y push)
#   scripts/c1_gestor.sh explicar DIR    SOLO el explicador (lo llama src/paper/c1.py, que le pone el plazo de 10 min):
#                                        `claude -p` con el mandato como system prompt y DIR/prompt.txt (el paquete) por
#                                        la entrada estándar; escribe en stdout el JSON de `--output-format json`.
#
# El explicador NO tiene herramientas (--tools "": ni Bash, ni lectura/escritura de ficheros, ni web), ni MCP
# (--strict-mcp-config sin servidores), ni ajustes de usuario/proyecto (--restricted), ni sesión guardada; corre en DIR
# (fuera del repo) con un entorno mínimo SIN variables ALPACA_*/APCA_*: no puede leer ~/financial_archive/config/ ni
# hablar con Alpaca. Todo lo que sabe está en el paquete.
# Ensayo / tests: FIN_C1_CLAUDE (otro binario, p. ej. un claude FALSO), FIN_C1_MODELO (por defecto opus),
#   FIN_REPO, FIN_LOGDIR, FIN_NOTA, FIN_SIN_AVISOS=1.
set -u
REPO="${FIN_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
CLAUDE="${FIN_C1_CLAUDE:-$HOME/.local/bin/claude}"
MODELO="${FIN_C1_MODELO:-opus}"
MANDATO="$REPO/config/c1_mandato_v1.md"

if [ "${1:-}" = explicar ]; then
  DIR="${2:?falta DIR}"
  [ -f "$DIR/prompt.txt" ] && [ -f "$MANDATO" ] || { echo "falta $DIR/prompt.txt o el mandato" >&2; exit 2; }
  cd "$DIR" || exit 2
  exec /usr/bin/env -i HOME="$HOME" USER="${USER:-}" LOGNAME="${LOGNAME:-${USER:-}}" LANG="${LANG:-es_ES.UTF-8}" \
    TMPDIR="${TMPDIR:-/tmp}" PATH="/usr/bin:/bin:/usr/sbin:/sbin" \
    "$CLAUDE" -p --model "$MODELO" --output-format json --no-session-persistence \
      --restricted --tools "" --strict-mcp-config \
      --disallowedTools Bash Read Write Edit Glob Grep WebFetch WebSearch NotebookEdit Agent \
      --system-prompt "$(cat "$MANDATO")" < "$DIR/prompt.txt"
fi

LOGDIR="${FIN_LOGDIR:-$HOME/financial_archive/logs}"
NOTA="${FIN_NOTA:-$REPO/obsidian/Proyecto/Actualizaciones.md}"
LOG="$LOGDIR/$(date '+%Y-%m-%d_%H%M')_c1.log"
REG="research/paper/decisiones_c1.jsonl"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1
mkdir -p "$LOGDIR"
cd "$REPO" || exit 1

nota() {   # $1 = línea (mismo formato que scripts/paper_mensual.sh)
  [ -f "$NOTA" ] || return 0
  /usr/bin/python3 - "$NOTA" "- **$(date '+%Y-%m-%d %H:%M')** · C1${FIN_RECUPERADA:+ (recuperado)} · $1 · log \`$(basename "$LOG")\`" <<'PY'
import sys
p, linea = sys.argv[1], sys.argv[2]
s = open(p, encoding="utf-8").read()
marca = "<!-- entradas -->\n"
s = s.replace(marca, marca + linea + "\n", 1) if marca in s else s + "\n" + linea + "\n"
open(p, "w", encoding="utf-8").write(s)
PY
}
avisa() {
  [ "${FIN_SIN_AVISOS:-0}" = 1 ] && return 0
  /usr/bin/osascript -e "display notification \"$1\" with title \"financial_kb · C1\"" 2>/dev/null || true
}
restaura() {   # deja el registro como en HEAD si el intento falló a medias (los demás registros exigen árbol limpio)
  [ -n "$(git status --porcelain -- "$REG")" ] || return 0
  git reset -q -- "$REG" 2>/dev/null
  git checkout -q HEAD -- "$REG" 2>/dev/null || rm -f "$REG"
}

[ -f "$REPO/research/paper/C1_ACTIVO" ] || { echo "$(date) C1 no activado: nada que hacer" >> "$LOG"; exit 0; }
RAMA="$(git symbolic-ref --short -q HEAD)"
if [ "$RAMA" != main ]; then
  echo "el repo está en la rama '${RAMA:-HEAD suelta}', no en main: C1 no registra" >> "$LOG"
  nota "❌ el repo no está en main; C1 no opera hoy"
  exit 0
fi
# Un solo ciclo C1 a la vez: launchd y la recuperación (scripts/recupera_gestores.sh, desde el arranque horario)
# podrían coincidir y enviar órdenes dobles. Cerrojo huérfano (Mac apagado a mitad) de más de 90 min: se quita.
GLOCK="$LOGDIR/.gestor_c1.lock"
if [ -d "$GLOCK" ] && [ -n "$(find "$GLOCK" -maxdepth 0 -mmin +90 2>/dev/null)" ]; then rmdir "$GLOCK" 2>/dev/null; fi
if ! mkdir "$GLOCK" 2>/dev/null; then echo "$(date) ya hay un ciclo C1 en marcha; salgo" >> "$LOG"; exit 0; fi
trap 'rmdir "$GLOCK" 2>/dev/null' EXIT
# Esperar a tener red (hasta 10 min): el 25-nov M1 arrancó al despertar el Mac sin DNS y no registró.
if [ "${FIN_SIN_ESPERA_RED:-0}" != 1 ]; then
  for _ in $(seq 1 60); do curl -sS -o /dev/null --max-time 5 https://paper-api.alpaca.markets/ 2>/dev/null && break; sleep 10; done
fi
# no pisar la actualización diaria (reconstruye el warehouse y commitea su verificación)
for ((i = 0; i < ${FIN_ESPERA_LOCK_MIN:-30} * 2; i++)); do [ -d "$LOGDIR/.actualizar.lock" ] || break; sleep 30; done

/usr/bin/caffeinate -i .venv/bin/python -m src.paper.c1 --auto >> "$LOG" 2>&1   # sin reposo a mitad del ciclo
RC=$?
if [ $RC -eq 0 ]; then
  grep -q "registrada y subida" "$LOG" && nota "✅ C1: decisión del día registrada y subida"
else
  restaura
  # si el commit se hizo pero el push falló, se sube en el siguiente intento de cualquier registro
  MOTIVO=$(tail -1 "$LOG" | cut -c1-120)
  nota "❌ C1 no registrada (rc=$RC): $MOTIVO"
  avisa "C1: no se pudo registrar (rc=$RC). Mira el log _c1."
fi
find "$LOGDIR" -name '*_c1.log' -mtime +400 -delete 2>/dev/null
exit $RC
