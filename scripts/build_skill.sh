#!/usr/bin/env bash
# copy spanloc into skill unchanged
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/submission/agent/skills/spanloc/scripts"
cp "$ROOT/spanloc/core.py" "$DEST/spanloc_core.py"
cp "$ROOT/spanloc/cli.py" "$DEST/spanloc_cli.py"
shasum -a 256 "$ROOT/spanloc/core.py" "$DEST/spanloc_core.py" "$ROOT/spanloc/cli.py" "$DEST/spanloc_cli.py"
