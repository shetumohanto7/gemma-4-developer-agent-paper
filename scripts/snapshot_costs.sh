#!/usr/bin/env bash
# save Modal billing records
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MODAL_PROFILE="${MODAL_WORKSPACE:-shetu}"
OUT="$ROOT/experiments/costs"
TS="$(date +%Y-%m-%dT%H%M%S%z)"
mkdir -p "$OUT"
M="$ROOT/.venv/bin/modal"
"$M" billing report --start 2026-10-22 --resolution h --tz local --show-resources --json > "$OUT/billing_$TS.json"
"$M" billing report --start 2026-10-22 --resolution h --tz local --show-resources --csv > "$OUT/billing_$TS.csv"
"$M" billing summary > "$OUT/billing_$TS.summary.txt" 2>&1
"$ROOT/.venv/bin/python" -I - "$OUT/billing_$TS.json" <<'EOF'
import json, sys
from collections import defaultdict
d = json.load(open(sys.argv[1]))
rows = d if isinstance(d, list) else d.get("data", d.get("rows", []))
by_app, by_res, total = defaultdict(float), defaultdict(float), 0.0
for r in rows:
    cost = float(r.get("cost") or 0)
    by_app[r.get("description") or r.get("object_id") or "?"] += cost
    by_res[r.get("resource") or "?"] += cost
    total += cost
print(f"metered cost since 2026-10-22 (complete hours only): ${total:.4f}")
for k, v in sorted(by_app.items(), key=lambda kv: -kv[1]):
    print(f"  app {k}: ${v:.4f}")
for k, v in sorted(by_res.items(), key=lambda kv: -kv[1]):
    print(f"  resource {k}: ${v:.4f}")
EOF
echo "saved $OUT/billing_$TS.*"
