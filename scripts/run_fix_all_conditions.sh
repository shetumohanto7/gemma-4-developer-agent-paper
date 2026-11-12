#!/usr/bin/env bash
# run conditions concurrently, equal load
set -uo pipefail
cd "$(dirname "$0")/.."
MODEL_KEY="$1"; CONC="${2:-2}"
shift $(( $# < 2 ? $# : 2 ))
mkdir -p experiments/05_find_vs_fix/logs
PIDS=()
for COND in ${CONDS:-base spanloc oracle_file oracle_func}; do
  LOG="experiments/05_find_vs_fix/logs/fix_${MODEL_KEY}_${COND}${VARIANT:+_$VARIANT}${1:+_pilot}.driver.log"
  scripts/run_fix_experiment.sh "$MODEL_KEY" "$COND" "$CONC" "$@" > "$LOG" 2>&1 &
  PIDS+=($!)
  sleep 2
done
STATUS=0
for P in "${PIDS[@]}"; do wait "$P" || STATUS=1; done
echo "all conditions done $(date +%H:%M) status=$STATUS"
exit $STATUS
