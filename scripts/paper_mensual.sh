#!/bin/bash
# Decisión mensual del paper trading (launchd com.financialkb.paper; docs/factors/paper_trading.md §3).
# Corre cada día a las 10:00 (y al encender el Mac). Desde el día 3 del mes intenta registrar la decisión del último
# fin de mes pasado (paper_decision.py --auto --registrar); si falla, avisa (notificación de macOS + línea en
# obsidian/Proyecto/Actualizaciones.md) y lo reintenta al día siguiente. Si ya está registrada, no hace nada.
# Mientras no exista research/paper/ACTIVO (lo crea el usuario al aprobar el primer ensayo) solo ensaya y avisa.
set -u
# Ensayo / tests (por defecto, el comportamiento de launchd; ver docs/int/ENSAYO_cierre_nov2026.md):
#   FIN_REPO, FIN_LOGDIR, FIN_NOTA      rutas alternativas (una copia del repo con remoto de prueba)
#   FIN_HOY=AAAA-MM-DD, FIN_AHORA=HHMM  día y hora simulados SOLO para la lógica de este script (marcas, día 3, espera
#                                       a la diaria). Los .py siguen usando la fecha real: en un ensayo hay que simularla
#                                       también allí (docs/int/ENSAYO_cierre_nov2026.md §1); nunca en el repo real.
#   FIN_ESPERA_RED, FIN_ESPERA_DIARIO_MIN, FIN_ESPERA_LOCK_MIN = 0 quitan esperas; FIN_SIN_AVISOS=1 sin notificaciones.
REPO="${FIN_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
LOGDIR="${FIN_LOGDIR:-$HOME/financial_archive/logs}"
NOTA="${FIN_NOTA:-$REPO/obsidian/Proyecto/Actualizaciones.md}"
HOY="${FIN_HOY:-$(date +%Y-%m-%d)}"
AHORA="${FIN_AHORA:-$(date +%H%M)}"
MES="${HOY:0:7}"
ANIO="${HOY:0:4}"
DIA="${HOY:8:2}"
LOG="$LOGDIR/$(date '+%Y-%m-%d_%H%M')_paper.log"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1   # el motivo de la nota es la última línea del log: sin esto, un traceback quedaba antes del JSON
mkdir -p "$LOGDIR"
cd "$REPO" || exit 1

# --- Espejo Alpaca PAPER: YA NO SE USA (decisión del usuario 20-nov-2026). B0, B1 y B1′ se registran SOLO EN PAPEL
# (listón teórico de la tabla «Competición»); sus cuentas pasaron a M1 (…ZFJX, 19-nov), A1 (…X9F9, antes B0 y D1) y
# C1 (…4JGR, antes B1), que gestiona el agente cada día (src/paper/{m1,a1,c1}.py). Este script no envía órdenes.
# El seguimiento de ejecuciones pendientes lo hace la diaria (scripts/actualizar.sh), no este script.

[ "$((10#$DIA))" -lt 3 ] && exit 0

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
avisa() {
  [ "${FIN_SIN_AVISOS:-0}" = 1 ] && return 0
  /usr/bin/osascript -e "display notification \"$1\" with title \"financial_kb · paper trading\"" 2>/dev/null || true
}
# Deja un registro como en HEAD si su intento falló a medias (escrito y quizá añadido al índice, sin commit): si no,
# el árbol queda sucio y E1, B1′ y B1 abortan todos los días (exigen árbol limpio). Si ya se commiteó, no hace nada.
restaura() {   # $1 = fichero del registro
  [ -n "$(git status --porcelain -- "$1")" ] || return 0
  git reset -q -- "$1" 2>/dev/null
  git checkout -q HEAD -- "$1" 2>/dev/null || rm -f "$1"
}
# Commits de registro que no llegaron al remoto (push fallido otro día; el reintento ve "ya registrado" y no sube).
empuja_pendientes() {
  [ -n "$(git rev-list origin/main..main 2>/dev/null)" ] || return 0
  if git push -q origin main >> "$LOG" 2>&1; then nota "⬆️ subidos commits de registro pendientes (push fallido antes)"; fi
}

# Esperar a la red y a que termine la actualización diaria (reconstruye el warehouse y su verificación commitea).
# Al encender el Mac launchd lanza a la vez esta tarea y `arranque`: sin esto se leía el warehouse a medio reconstruir
# y dos procesos podían commitear a la vez (ensayo del 17-nov). Retrasar el registro un día no cambia nada (el cierre
# siempre es el último fin de mes pasado).
for ((i = 0; i < ${FIN_ESPERA_RED:-60}; i++)); do curl -sS -o /dev/null --max-time 5 https://api.stlouisfed.org/ 2>/dev/null && break; sleep 10; done
DOW="$(date -j -f %Y-%m-%d "$HOY" +%u 2>/dev/null || date +%u)"   # 1 = lunes … 7 = domingo
diaria_pendiente() {
  [ "$DOW" != 7 ] && [ "$(cat "$LOGDIR/.hecho_diario" 2>/dev/null)" != "$HOY" ] \
    && [ "$(cat "$LOGDIR/.hecho_semanal" 2>/dev/null)" != "$HOY" ]
}
if diaria_pendiente && [ "$((10#$AHORA))" -lt 730 ]; then
  echo "$(date) antes de las 7:30 con la diaria de hoy pendiente: lo hará la cita de las 10:00" >> "$LOG"; exit 0
fi
for ((i = 0; i < ${FIN_ESPERA_DIARIO_MIN:-60} * 2; i++)); do diaria_pendiente || break; sleep 30; done
for ((i = 0; i < ${FIN_ESPERA_LOCK_MIN:-60} * 2; i++)); do [ -d "$LOGDIR/.actualizar.lock" ] || break; sleep 30; done
if [ -d "$LOGDIR/.actualizar.lock" ]; then
  echo "$(date) sigue una actualización en marcha (.actualizar.lock): reintento en la próxima cita" >> "$LOG"; exit 0
fi
# Los registros commitean y hacen `push origin main`: en otra rama el commit se quedaría fuera de main (como INT-11).
RAMA="$(git symbolic-ref --short -q HEAD)"
if [ "$RAMA" != main ]; then
  echo "el repo está en la rama '${RAMA:-HEAD suelta}', no en main: no se registra nada" >> "$LOG"
  nota "❌ el repo no está en main (rama '${RAMA:-?}'); E1/B1′/B1 se reintentan mañana"
  avisa "Paper/E1: el repo no está en main; reintento mañana"
  exit 0
fi

# P-E1 (registro en vivo, docs/int/E1_prerregistro_v1.md §11): independiente de ACTIVO; no se muestra en el reporte
if [ ! -f "$LOGDIR/.e1_hecho_$MES" ]; then
  if .venv/bin/python -m scripts.e1_vivo --auto --registrar > "$LOGDIR/$(date +%Y-%m-%d_%H%M)_e1.log" 2>&1; then
    touch "$LOGDIR/.e1_hecho_$MES"
  else
    restaura research/int/e1_vivo.jsonl
    avisa "E1: registro en vivo fallido (mira el log _e1); reintento mañana"
  fi
fi

# P-K1v (registro anual en vivo, docs/int/K1_vivo_prerregistro_v1.md): solo registra t ≥ 2026, una vez por año
if [ ! -f "$LOGDIR/.k1_hecho_$ANIO" ]; then
  KLOG="$LOGDIR/$(date +%Y-%m-%d_%H%M)_k1.log"
  if .venv/bin/python -m scripts.k1_vivo --registrar > "$KLOG" 2>&1; then
    # solo al registrar: "ya registrado" (t del año anterior aún vigente) no debe cerrar el año (Validador 2026-11-05)
    grep -q "registrado y subido" "$KLOG" && touch "$LOGDIR/.k1_hecho_$ANIO"
  else
    avisa "K1: registro en vivo fallido (mira el log _k1); reintento mañana"
  fi
fi

# B1′ EN PARALELO (docs/factors/B1prima_implementacion.md §6): su propio registro y sus marcas; no toca el de B1.
# Sin ACTIVO solo ensaya (una vez al mes). Si falla al registrar, deja decisiones_b1prima.jsonl como en HEAD para no
# ensuciar el árbol que B1 necesita limpio, avisa y se reintenta mañana.
B1P_F="research/paper/decisiones_b1prima.jsonl"
if [ ! -f "$LOGDIR/.b1p_hecho_$MES" ]; then
  BLOG="$LOGDIR/$(date +%Y-%m-%d_%H%M)_b1prima.log"
  if [ ! -f "$REPO/research/paper/ACTIVO" ]; then
    if [ ! -f "$LOGDIR/.b1p_ensayo_$MES" ]; then
      .venv/bin/python -m scripts.paper_decision_b1prima --auto > "$BLOG" 2>&1 && touch "$LOGDIR/.b1p_ensayo_$MES" \
        || avisa "B1′: ensayo fallido (mira el log _b1prima)"
    fi
  elif .venv/bin/python -m scripts.paper_decision_b1prima --auto --registrar > "$BLOG" 2>&1; then
    touch "$LOGDIR/.b1p_hecho_$MES"
    grep -q "registrada y subida" "$BLOG" && nota "✅ B1′: decisión registrada y subida"
  else
    restaura "$B1P_F"
    nota "❌ B1′ no registrada: $(tail -1 "$BLOG" | cut -c1-120) · se reintenta mañana"
    avisa "B1′: no se pudo registrar (mira el log _b1prima). Reintento mañana."
  fi
fi

empuja_pendientes

# la marca del paper solo corta el paper: E1/K1 se reintentan aunque la decisión del mes ya esté (Validador 2026-11-05)
[ -f "$LOGDIR/.paper_hecho_$MES" ] && exit 0

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
  restaura research/paper/decisiones.jsonl
  MOTIVO=$(tail -1 "$LOG" | cut -c1-120)
  nota "❌ no registrada (rc=$RC): $MOTIVO · se reintenta mañana"
  avisa "No se pudo registrar (rc=$RC): $MOTIVO. Reintento mañana."
fi
find "$LOGDIR" -name '*_paper.log' -mtime +400 -delete 2>/dev/null
exit $RC
