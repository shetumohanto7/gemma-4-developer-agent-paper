#!/usr/bin/env bash
# run one find-vs-fix condition
set -euo pipefail
cd "$(dirname "$0")/.."
[ -e experiments/costs/CREDIT_GUARD_TRIPPED ] && { cat experiments/costs/CREDIT_GUARD_TRIPPED; exit 1; }
MODEL_KEY="$1"; COND="$2"; CONC="${3:-3}"
shift $(( $# < 3 ? $# : 3 ))
ALIAS="gemma-4-${MODEL_KEY}-it-qat-w4a16-ct"
SERVE_KEY="${SERVE_KEY:-$MODEL_KEY}"
ENDPOINT="${VLLM_BASE_URL:-https://${MODAL_WORKSPACE:-shetu}--g4paper-vllm-serve-${SERVE_KEY}.us-east.modal.run}/v1"
VALID="experiments/05_find_vs_fix/valid_task_ids.txt"
[ -s "$VALID" ] || { echo "missing $VALID (run the validity checks first)"; exit 1; }
VSUF="${VARIANT:+_$VARIANT}"
if [ $# -gt 0 ]; then IDS=("$@"); RUN="fix_${MODEL_KEY}_${COND}${VSUF}${RUN_SUFFIX:-_pilot}"
else read -r -a IDS < "$VALID"; RUN="fix_${MODEL_KEY}_${COND}${VSUF}"; fi
OUT="experiments/05_find_vs_fix/$RUN"
mkdir -p "$OUT"

AGENT="data/fix_agents/${RUN}"
rm -rf "$AGENT" && mkdir -p "$AGENT"
cp -R submission/fix_agent_template/. "$AGENT/"
cp data/competition/sample_submission/prompts/system.md "$AGENT/prompts/system.md"
sed -i.bak "s/__MODEL_ALIAS__/${ALIAS}/" "$AGENT/agent.yaml" && rm "$AGENT/agent.yaml.bak"
case "${VARIANT:-}" in
  "") ;;
  nothoughts)
    sed -i.bak 's/include_thoughts: true/include_thoughts: false/' "$AGENT/configs/sampling.yaml" && rm "$AGENT/configs/sampling.yaml.bak"
    grep -q "include_thoughts: false" "$AGENT/configs/sampling.yaml" || { echo "variant not applied"; exit 1; } ;;
  *) echo "unknown VARIANT=$VARIANT"; exit 1 ;;
esac

# eval ignores eval_config; pass flags
read -r -a BUDGET < <(.venv-harness/bin/python -I -c 'import sys, yaml
e = yaml.safe_load(open(sys.argv[1]))["evaluation"]
print("--max-time-minutes", e["max_time_minutes"], "--max-tool-calls", e["max_tool_calls"],
      "--max-turns", e["max_turns"], "--timeout-seconds", e["timeout_seconds"])' "$AGENT/eval_config.yaml")
[ "${#BUDGET[@]}" -eq 8 ] || { echo "could not read the budget from $AGENT/eval_config.yaml"; exit 1; }

# one swegemma run per environment
.venv/bin/python -I - "${IDS[@]}" > "$OUT/env_groups.txt" <<'PY'
import json, sys
valid = set(open("experiments/05_find_vs_fix/valid_task_ids.txt").read().split())
env = json.load(open("experiments/05_find_vs_fix/envs.json"))["task_env"]
groups = {}
for i in sys.argv[1:]:
    if i not in valid:
        sys.exit(f"{i} is not a valid task")
    groups.setdefault(env[i], []).append(i)
for k, ids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    print(k, *ids)
PY

export OPENAI_BASE_URL="$ENDPOINT"
OPENAI_API_KEY="$(cat .secrets/vllm_api_key)"; export OPENAI_API_KEY
# wake GPU endpoint first
for _ in $(seq 60); do
  curl -s -o /dev/null -w '%{http_code}' -m 20 -H "Authorization: Bearer $OPENAI_API_KEY" "$ENDPOINT/models" | grep -q 200 && break
  sleep 10
done

P=(.venv/bin/python -I -m locbench.provenance)
NOTE="model=$ALIAS cond=$COND variant=${VARIANT:-none} serve=$SERVE_KEY endpoint=$ENDPOINT prompt_sha256=$(shasum -a 256 "$AGENT/prompts/system.md" | cut -c1-16) tasks=${#IDS[@]} envs=$(wc -l < "$OUT/env_groups.txt" | tr -d ' ') concurrency=$CONC budget=${BUDGET[*]}"
"${P[@]}" record --name "$RUN" --cmd "scripts/run_fix_experiment.sh $MODEL_KEY $COND $CONC${1:+ $*}" --note "$NOTE" >/dev/null
STATUS=finished
OUTPUTS=("$OUT/env_groups.txt")
while read -r KEY GROUP; do
  read -r -a G <<< "$GROUP"
  TASKS_DIR="data/fix_tasks/${RUN}/${KEY}"
  rm -rf "$TASKS_DIR" && mkdir -p "$TASKS_DIR/wheels"
  .venv/bin/python -I -c 'import json, sys
keep = {json.loads(l)["instance_id"] for l in open(sys.argv[2]) if l.strip()}
sys.stdout.writelines(l for l in open(sys.argv[1]) if l.strip() and json.loads(l)["instance_id"] in keep)' \
    "data/variants/tasks_${COND}.jsonl" "data/envs/$KEY/tasks.jsonl" > "$TASKS_DIR/tasks.jsonl"
  ln -f data/envs/"$KEY"/wheels/*.whl "$TASKS_DIR/wheels/"
  ln -sfn "$PWD/data/competition/sandbox" "$TASKS_DIR/sandbox"
  # one TMPDIR per wheel set
  export TMPDIR="$PWD/data/tmp_swegemma_$KEY"; mkdir -p "$TMPDIR"
  echo "$(date +%H:%M) env $KEY: ${#G[@]} tasks"
  .venv-harness/bin/swegemma eval --tasks "$TASKS_DIR/tasks.jsonl" --snapshots-dir data/competition/snapshots \
    --submission-dir "$AGENT" --results-dir "$OUT/$KEY" --sandbox docker --concurrency "$CONC" --display quiet \
    "${BUDGET[@]}" --task-ids "${G[@]}" > "$OUT/$KEY.log" 2>&1 < /dev/null || STATUS=failed
  OUTPUTS+=("$OUT/$KEY/summary.json" "$OUT/$KEY/task_results.jsonl" "$OUT/$KEY.log")
done < "$OUT/env_groups.txt"
"${P[@]}" finish --name "$RUN" --status "$STATUS" --outputs "${OUTPUTS[@]}"
echo "$RUN $STATUS $(date +%H:%M)"
