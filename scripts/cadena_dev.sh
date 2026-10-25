#!/bin/zsh
# Cadena de corridas de desarrollo tras la 6c (orden de M2 §6, M3 §5, pool §7; preparación en `claude/m3-prep`).
# Uso: zsh scripts/cadena_dev.sh [paso_desde]   (p. ej. `m3_long` para retomar; sin argumento empieza por m2_m1cmp)
# Cada corrida: --official, una pasada, árbol limpio; commit + push al acabar. Para al primer fallo, y si el placebo
# del pool da fuga o aviso (pool §5). Una corrida cortada a medias no registra nada: se vuelve a lanzar desde ella.
cd "$(dirname "$0")/.." || exit 1
LOG=research/trials/cadena_logs
mkdir -p $LOG
PY=.venv/bin/python
PASOS=(m2_m1cmp m2_sens m3_long m3_m1cmp m3_sens placebo_pool pool_dev pool_m1cmp pool_pesos_uno pool_pesos_excluir)
DESDE=${1:-m2_m1cmp}
(( ${PASOS[(Ie)$DESDE]} )) || { echo "paso desconocido: $DESDE"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "árbol sucio: commitea antes"; exit 1; }

commit() {
  git add -A research/ && git commit -q -m "$1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push -q origin main
  [ -z "$(git status --porcelain)" ] || { echo "ÁRBOL SUCIO tras $1"; git status --short; exit 1; }
}

placebo_ok() {
  $PY - <<'EOF'
import json, sys
d = json.load(open("research/trials/m2/placebo_pool.json"))
def walk(x):
    if isinstance(x, dict):
        return any((k in ("fuga_regla_0.02", "aviso_signo_o_t") and v is True) or walk(v) for k, v in x.items())
    return isinstance(x, list) and any(walk(v) for v in x)
sys.exit(1 if walk(d) else 0)
EOF
}

run() {
  echo "$(date -u +%H:%M:%S) INICIO $1"
  if [ "$1" = placebo_pool ]; then
    $PY -m src.models.pool_dev placebo pool > $LOG/$1.log 2>&1 || { echo "FALLO $1"; tail -5 $LOG/$1.log; commit "dev $1 FAILED (log)"; exit 1; }
    commit "pool placebo repeated with M2 v1.3 (whole pile)"
    placebo_ok || { echo "$(date -u +%H:%M:%S) PARADA: placebo del pool con fuga o aviso"; exit 2; }
    echo "$(date -u +%H:%M:%S) placebo OK"; return
  fi
  $PY -m src.models.harness --config config/harness/$1.yaml --official > $LOG/$1.log 2>&1 || { echo "$(date -u +%H:%M:%S) FALLO $1"; tail -5 $LOG/$1.log; commit "dev run $1 FAILED (log)"; exit 1; }
  echo "$(date -u +%H:%M:%S) FIN $1 $(grep -o '"run_id": "[^"]*"' $LOG/$1.log | tail -1)"
  commit "dev run $1 (official, one pass)"
}

for p in ${PASOS[${PASOS[(Ie)$DESDE]},-1]}; do run $p; done
echo "$(date -u +%H:%M:%S) CADENA COMPLETA"
