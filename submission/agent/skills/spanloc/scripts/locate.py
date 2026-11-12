"""Rank likely edit locations."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spanloc_cli import main  # noqa: E402

ap = argparse.ArgumentParser(add_help=False)
ap.add_argument("--query", default=None)
ap.add_argument("--top", type=int, default=12)
ns, rest = ap.parse_known_args()
text = " ".join(([ns.query] if ns.query else []) + rest)
sys.exit(main(["locate", "--top", str(ns.top), "--", text]))
