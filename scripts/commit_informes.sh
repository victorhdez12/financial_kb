#!/bin/bash
# Commitea SOLO los informes que deja la semanal (obsidian/Reports/*_semanal.md, *_signal.json y
# docs/data/audit_*_series.csv), sin push. Lo llama scripts/actualizar.sh al acabar la semanal.
# Motivo (ensayo del cierre de nov-2026, docs/int/ENSAYO_cierre_nov2026.md): esos ficheros quedaban sin commitear y
# E1/E1b, B1′, B1 (día 3) e INT-11 (día 20) exigen árbol limpio → abortaban todos los días hasta commitear a mano.
# No sube nada: el siguiente registro en vivo (o la verificación diaria) hace `push origin main` y lo lleva consigo.
# Solo en main; nunca toca el índice de otros ficheros (`git commit -- <rutas>`).
#   uso: scripts/commit_informes.sh [REPO]
set -u
REPO="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO" || exit 1
[ "$(git symbolic-ref --short -q HEAD)" = main ] || { echo "informes: no estoy en main; no commiteo"; exit 0; }
RUTAS=()
while IFS= read -r f; do
  case "$f" in
    obsidian/Reports/*_semanal.md | obsidian/Reports/*_signal.json | docs/data/audit_*_series.csv) RUTAS+=("$f") ;;
  esac
done < <(git -c core.quotepath=off status --porcelain --untracked-files=all -- obsidian/Reports docs/data \
           | grep -E '^(\?\?| M|M |A |AM) ' | cut -c4-)
[ ${#RUTAS[@]} -eq 0 ] && { echo "informes: nada que commitear"; exit 0; }
git add -- "${RUTAS[@]}" || exit 1
if git commit -q -m "Weekly reports (automatic): ${#RUTAS[@]} files

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- "${RUTAS[@]}"; then
  echo "informes: commiteados ${#RUTAS[@]} ficheros: ${RUTAS[*]}"
else
  echo "AVISO informes: commit fallido"; exit 1
fi
