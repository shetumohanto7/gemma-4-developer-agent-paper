#!/usr/bin/env bash
# reference must pass, empty fail
set -uo pipefail
cd "$(dirname "$0")/.."
WAIT_PID="${1:-}"
if [ -n "$WAIT_PID" ]; then while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 20; done; fi
OUT=experiments/05_find_vs_fix
# avoid stale swegemma wheel cache
WH=$(ls data/competition_repaired/wheels | shasum -a 256 | cut -c1-12)
export TMPDIR="$PWD/data/tmp_swegemma_$WH"
mkdir -p "$TMPDIR"
echo "wheels set $WH, TMPDIR=$TMPDIR"
COMMON=(--tasks data/competition_repaired/tasks.jsonl --snapshots-dir data/competition/snapshots
        --submission-dir data/competition/sample_submission --sandbox docker --concurrency 2 --display quiet)
P=(.venv/bin/python -I -m locbench.provenance)
"${P[@]}" record --name validity_reference_repaired --cmd "scripts/validate_gold.py eval ${COMMON[*]} --results-dir $OUT/validity_reference_repaired" --note "Reference patch must pass (repaired env)." >/dev/null
.venv-harness/bin/python scripts/validate_gold.py eval "${COMMON[@]}" --results-dir $OUT/validity_reference_repaired > $OUT/validity_reference_repaired.log 2>&1
"${P[@]}" finish --name validity_reference_repaired --outputs $OUT/validity_reference_repaired/task_results.jsonl $OUT/validity_reference_repaired.log
"${P[@]}" record --name validity_empty_repaired --cmd "swegemma eval --skip-agent-patch ${COMMON[*]} --results-dir $OUT/validity_empty_repaired" --note "Empty patch must fail (repaired env)." >/dev/null
.venv-harness/bin/swegemma eval --skip-agent-patch "${COMMON[@]}" --results-dir $OUT/validity_empty_repaired > $OUT/validity_empty_repaired.log 2>&1
"${P[@]}" finish --name validity_empty_repaired --outputs $OUT/validity_empty_repaired/task_results.jsonl $OUT/validity_empty_repaired.log
echo "validity checks finished $(date +%H:%M)"
