#!/usr/bin/env bash
# per-environment reference and empty checks
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=experiments/05_find_vs_fix/validity_v3
P=(.venv/bin/python -I -m locbench.provenance)
for ENV_DIR in data/envs/*/; do
  KEY=$(basename "$ENV_DIR")
  # one TMPDIR per wheel set
  export TMPDIR="$PWD/data/tmp_swegemma_$KEY"
  mkdir -p "$TMPDIR" "$OUT/$KEY"
  COMMON=(--tasks "${ENV_DIR}tasks.jsonl" --snapshots-dir data/competition/snapshots
          --submission-dir data/competition/sample_submission --sandbox docker --concurrency 2 --display quiet)
  echo "$(date +%H:%M) env $KEY: $(wc -l < "${ENV_DIR}tasks.jsonl" | tr -d ' ') tasks, reference"
  "${P[@]}" record --name "validity_v3_${KEY}_reference" --cmd "scripts/validate_gold.py eval ${COMMON[*]} --results-dir $OUT/$KEY/reference" --note "Reference patch must pass (env v3 $KEY)." >/dev/null
  .venv-harness/bin/python scripts/validate_gold.py eval "${COMMON[@]}" --results-dir "$OUT/$KEY/reference" > "$OUT/$KEY/reference.log" 2>&1
  "${P[@]}" finish --name "validity_v3_${KEY}_reference" --outputs "$OUT/$KEY/reference/task_results.jsonl" "$OUT/$KEY/reference.log" >/dev/null
  read -r -a PASSED <<< "$(.venv/bin/python -I -c 'import json,sys; print(" ".join(r["instance_id"] for r in map(json.loads, open(sys.argv[1])) if r.get("resolved")))' "$OUT/$KEY/reference/task_results.jsonl")"
  echo "$(date +%H:%M) env $KEY: reference passed ${#PASSED[@]}, empty patch"
  [ "${#PASSED[@]}" -eq 0 ] && continue
  "${P[@]}" record --name "validity_v3_${KEY}_empty" --cmd "swegemma eval --skip-agent-patch ${COMMON[*]} --results-dir $OUT/$KEY/empty --task-ids ${PASSED[*]}" --note "Empty patch must fail (env v3 $KEY)." >/dev/null
  .venv-harness/bin/swegemma eval --skip-agent-patch "${COMMON[@]}" --results-dir "$OUT/$KEY/empty" --task-ids "${PASSED[@]}" > "$OUT/$KEY/empty.log" 2>&1
  "${P[@]}" finish --name "validity_v3_${KEY}_empty" --outputs "$OUT/$KEY/empty/task_results.jsonl" "$OUT/$KEY/empty.log" >/dev/null
done
echo "validity checks v3 finished $(date +%H:%M)"
