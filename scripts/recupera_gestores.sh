#!/bin/bash
# Recupera los ciclos C1 / M1 / A1 que se hayan perdido HOY (Mac apagado, dormido o sin red a su hora).
# Lo llama `scripts/actualizar.sh pendiente` (launchd com.financialkb.arranque: al encender y cada hora).
#
# Para cada gestor con su <P>_ACTIVO: si hoy es lun-vie, ya pasó su hora (C1 15:45, M1 16:00, A1 16:15 Madrid),
# no son más de las 22:30, no hay línea de hoy en decisiones_<g>.jsonl y no hay un ciclo en marcha → lanza
# scripts/<g>_gestor.sh (el mismo que usa launchd). Seguro de repetir: `--auto` sale sin hacer nada si ya hay
# decisión de hoy o el mercado está cerrado, y el cerrojo .gestor_<g>.lock impide dos ciclos a la vez.
# Si el ciclo dice «mercado cerrado» (festivo, cierre anticipado o ya cerró), se apunta y no se reintenta hoy.
# Pruebas: FIN_REPO, FIN_LOGDIR, FIN_AHORA (HHMM), FIN_DOW (1-7), FIN_HOY (AAAA-MM-DD).
set -u
REPO="${FIN_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
LOGDIR="${FIN_LOGDIR:-$HOME/financial_archive/logs}"
HOY="${FIN_HOY:-$(date +%Y-%m-%d)}"
AHORA="${FIN_AHORA:-$(date +%H%M)}"
DOW="${FIN_DOW:-$(date +%u)}"
CERRADO="$LOGDIR/.mercado_cerrado"
cd "$REPO" || exit 1

[ "$DOW" -le 5 ] || exit 0
[ "$((10#$AHORA))" -le 2230 ] || exit 0
[ "$(cat "$CERRADO" 2>/dev/null)" = "$HOY" ] && exit 0

for PAR in "c1 1545" "m1 1600" "a1 1615"; do
  G="${PAR% *}"; H="${PAR#* }"; P="$(echo "$G" | tr a-z A-Z)"
  [ -f "research/paper/${P}_ACTIVO" ] || continue
  [ "$((10#$AHORA))" -ge "$((10#$H))" ] || continue
  # la fecha de la línea es su PRIMERA clave (src/paper/c1.py ciclo); una «fecha» anidada (p. ej. propuesta.fecha,
  # que escribe el agente) no cuenta como decisión de hoy
  hecho() { grep -q "^{\"fecha\": \"$HOY\"" "research/paper/decisiones_${G}.jsonl" 2>/dev/null; }
  hecho && continue
  [ -d "$LOGDIR/.gestor_${G}.lock" ] && { echo "$(date '+%F %T') $P: ciclo en marcha, no lo recupero"; continue; }
  echo "$(date '+%F %T') $P: sin decisión de hoy a las $AHORA → lanzo el ciclo"
  FIN_RECUPERADA=1 bash "$REPO/scripts/${G}_gestor.sh"
  echo "$(date '+%F %T') $P: rc=$?"
  ULT="$(ls -t "$LOGDIR"/*_"${G}".log 2>/dev/null | head -1)"
  # solo el aviso de main() («mercado cerrado (abre …): <G> no opera hoy, sin registro»), a principio de línea y sin
  # línea de hoy: el resumen o el diario del agente impresos en el log pueden decir «mercado cerrado» (festivo de mañana)
  if [ -n "$ULT" ] && ! hecho && grep -q "^mercado cerrado (abre " "$ULT"; then
    echo "$HOY" > "$CERRADO"; echo "$(date '+%F %T') mercado cerrado: no se reintenta hoy"; exit 0
  fi
done
exit 0
