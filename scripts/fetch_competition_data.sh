#!/usr/bin/env bash
# needs ~/.kaggle/kaggle.json; no redistribution
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/data/competition"
KAGGLE="$ROOT/.venv/bin/kaggle"
mkdir -p "$DEST"
"$KAGGLE" competitions files -c gemma-4-developer-agent | head -20
"$KAGGLE" competitions download -c gemma-4-developer-agent -p "$DEST"
cd "$DEST"
for z in *.zip; do
  # refuse unsafe archive paths
  if unzip -Z1 "$z" | grep -qE '(^/|(^|/)\.\.(/|$))'; then
    echo "refusing $z: unsafe paths"; exit 1
  fi
  unzip -q -o "$z" && rm "$z"
done
ls -la "$DEST" | head -30
