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

# P-E1 (registro en vivo, docs/int/E1_prerregistro_v1.md §11): independiente de ACTIVO; no se muestra en el reporte
if [ ! -f "$LOGDIR/.e1_hecho_$MES" ]; then
  if .venv/bin/python -m scripts.e1_vivo --auto --registrar > "$LOGDIR/$(date +%Y-%m-%d_%H%M)_e1.log" 2>&1; then
    touch "$LOGDIR/.e1_hecho_$MES"
  else
    avisa "E1: registro en vivo fallido (mira el log _e1); reintento mañana"
  fi
fi

# P-K1v (registro anual en vivo, docs/int/K1_vivo_prerregistro_v1.md): solo registra t ≥ 2026, una vez por año
ANIO="$(date +%Y)"
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
    if [ -n "$(git status --porcelain -- "$B1P_F")" ]; then
      git checkout -q HEAD -- "$B1P_F" 2>/dev/null || rm -f "$B1P_F"
    fi
    nota "❌ B1′ no registrada: $(tail -1 "$BLOG" | cut -c1-120) · se reintenta mañana"
    avisa "B1′: no se pudo registrar (mira el log _b1prima). Reintento mañana."
  fi
fi

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
  MOTIVO=$(tail -1 "$LOG" | cut -c1-120)
  nota "❌ no registrada (rc=$RC): $MOTIVO · se reintenta mañana"
  avisa "No se pudo registrar (rc=$RC): $MOTIVO. Reintento mañana."
fi
find "$LOGDIR" -name '*_paper.log' -mtime +400 -delete 2>/dev/null
exit $RC
