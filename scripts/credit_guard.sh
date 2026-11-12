#!/usr/bin/env bash
# stop Modal apps near limit
set -uo pipefail
cd "$(dirname "$0")/.."
TH="${1:-29.50}"; EVERY="${2:-300}"
FLAG=experiments/costs/CREDIT_GUARD_TRIPPED
LOG=experiments/costs/credit_guard.log
MODAL=.venv/bin/modal
export MODAL_PROFILE="${MODAL_WORKSPACE:-shetu}"
echo "$(date '+%F %H:%M') guard v2 started: threshold \$$TH (month to date), every ${EVERY}s, pid $$" >> "$LOG"
while true; do
  read -r used billed metered < <("$MODAL" billing summary --json 2>/dev/null | .venv/bin/python -I -c '
import json, sys
try:
    d = json.load(sys.stdin)
    c = abs(float(d.get("adjustments", {}).get("credits", 0) or 0))
    b = float(d.get("billed_cost", 0) or 0)
    m = float(d.get("metered_cost", 0) or 0)
    print("%.2f %.2f %.2f" % (c, b, m))
except Exception:
    print("")
')
  if [ -n "${used:-}" ]; then
    echo "$(date '+%F %H:%M') credit used \$$used, billed \$$billed, metered \$$metered" >> "$LOG"
    if [ "$(awk -v u="$used" -v b="$billed" -v t="$TH" 'BEGIN {print (u >= t || b > 0) ? 1 : 0}')" = 1 ]; then
      printf 'Tripped %s: credit used $%s (threshold $%s), billed $%s.\nAll GPU work stopped; new runs are blocked until another Modal account is set up and this file is removed.\n' \
        "$(date '+%F %H:%M:%S')" "$used" "$TH" "$billed" > "$FLAG"
      cp "$FLAG" ../gemma-4-developer-agent/experiments/costs/CREDIT_GUARD_TRIPPED 2>/dev/null
      pkill -TERM -f "run_fix_all_conditions.sh"; pkill -TERM -f "run_fix_experiment.sh"
      pkill -TERM -f "swegemma eval"; pkill -TERM -f "agentloc.run"
      pkill -TERM -f "gemma-4-developer-agent/scripts/"
      sleep 5
      docker ps --filter ancestor=swebench-sandbox:latest -q | xargs -r docker rm -f >/dev/null 2>&1
      for app in $("$MODAL" app list --json 2>/dev/null | .venv/bin/python -I -c '
import json, sys
for a in json.load(sys.stdin):
    if a.get("state") in ("deployed", "running", "deploying", "ephemeral"):
        print(a["app_id"])
'); do
        "$MODAL" app stop -y "$app" >> "$LOG" 2>&1 && echo "$(date '+%F %H:%M') stopped app $app" >> "$LOG"
      done
      echo "$(date '+%F %H:%M') TRIPPED: runs killed, sandboxes removed, all Modal apps stopped" >> "$LOG"
      exit 0
    fi
  else
    echo "$(date '+%F %H:%M') WARNING: billing summary unreadable" >> "$LOG"
  fi
  sleep "$EVERY"
done
