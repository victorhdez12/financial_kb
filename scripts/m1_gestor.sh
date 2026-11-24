#!/bin/bash
# M1 «Claude gestor macro» (docs/factors/M1_cartera_macro_spec.md v1.1; launchd com.financialkb.m1: 16:00 Madrid, lun-vie).
#
#   scripts/m1_gestor.sh     ciclo del día (launchd): .venv/bin/python -m src.paper.m1 --auto
#                            (sin research/paper/M1_ACTIVO no hace nada; con él: paquete + sombra → agente de solo
#                            lectura (src/paper/agente.py) → guardia con citas → órdenes PAPER → registros
#                            research/paper/decisiones_m1.jsonl y decisiones_m1_sombra.jsonl → commit y push;
#                            diario en obsidian/Carteras/M1/, fuera de git)
# El agente corre con un entorno mínimo SIN ALPACA_*/APCA_*, sin Bash, sin red, sin escritura, y solo lee carpetas
# enumeradas (nunca ~/financial_archive/config/). Pruebas: FIN_REPO, FIN_LOGDIR, FIN_NOTA, FIN_SIN_AVISOS=1.
set -u
REPO="${FIN_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
LOGDIR="${FIN_LOGDIR:-$HOME/financial_archive/logs}"
NOTA="${FIN_NOTA:-$REPO/obsidian/Proyecto/Actualizaciones.md}"
LOG="$LOGDIR/$(date '+%Y-%m-%d_%H%M')_m1.log"
REGS=("research/paper/decisiones_m1.jsonl" "research/paper/decisiones_m1_sombra.jsonl")
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1
mkdir -p "$LOGDIR"
cd "$REPO" || exit 1

nota() {   # $1 = línea (mismo formato que scripts/c1_gestor.sh)
  [ -f "$NOTA" ] || return 0
  /usr/bin/python3 - "$NOTA" "- **$(date '+%Y-%m-%d %H:%M')** · M1 · $1 · log \`$(basename "$LOG")\`" <<'PY'
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
  /usr/bin/osascript -e "display notification \"$1\" with title \"financial_kb · M1\"" 2>/dev/null || true
}
restaura() {   # deja los registros como en HEAD si el intento falló a medias
  for REG in "${REGS[@]}"; do
    [ -n "$(git status --porcelain -- "$REG")" ] || continue
    git reset -q -- "$REG" 2>/dev/null
    git checkout -q HEAD -- "$REG" 2>/dev/null || rm -f "$REG"
  done
}

[ -f "$REPO/research/paper/M1_ACTIVO" ] || { echo "$(date) M1 no activado: nada que hacer" >> "$LOG"; exit 0; }
RAMA="$(git symbolic-ref --short -q HEAD)"
if [ "$RAMA" != main ]; then
  echo "el repo está en la rama '${RAMA:-HEAD suelta}', no en main: M1 no registra" >> "$LOG"
  nota "❌ el repo no está en main; M1 no opera hoy"
  exit 0
fi
# no pisar la diaria ni el ciclo de C1 (15:45): esperan a que acaben
for ((i = 0; i < ${FIN_ESPERA_LOCK_MIN:-30} * 2; i++)); do [ -d "$LOGDIR/.actualizar.lock" ] || break; sleep 30; done
for ((i = 0; i < ${FIN_ESPERA_C1_MIN:-20} * 2; i++)); do pgrep -f "src.paper.c1 --auto" >/dev/null || break; sleep 30; done

.venv/bin/python -m src.paper.m1 --auto >> "$LOG" 2>&1
RC=$?
if [ $RC -eq 0 ]; then
  grep -q "registrada y subida" "$LOG" && nota "✅ M1: decisión del día y sombra registradas y subidas"
else
  restaura
  MOTIVO=$(tail -1 "$LOG" | cut -c1-120)
  nota "❌ M1 no registrada (rc=$RC): $MOTIVO"
  avisa "M1: no se pudo registrar (rc=$RC). Mira el log _m1."
fi
find "$LOGDIR" -name '*_m1.log' -mtime +400 -delete 2>/dev/null
exit $RC
