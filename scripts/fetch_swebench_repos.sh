#!/usr/bin/env bash
# bare-clone SWE-bench repos, no checkout
set -euo pipefail
DEST="${1:-$(dirname "$0")/../data/repos}"
mkdir -p "$DEST"
REPOS=(
  django/django sympy/sympy matplotlib/matplotlib scikit-learn/scikit-learn
  pytest-dev/pytest sphinx-doc/sphinx astropy/astropy psf/requests
  pylint-dev/pylint pydata/xarray mwaskom/seaborn pallets/flask
)
for r in "${REPOS[@]}"; do
  name="${r//\//__}.git"
  if [ -d "$DEST/$name" ]; then
    echo "skip $r (exists)"; continue
  fi
  ( git clone --quiet --bare --filter=blob:limit=1m "https://github.com/$r.git" "$DEST/$name" \
      && echo "done $r ($(du -sh "$DEST/$name" | cut -f1))" ) &
done
wait
