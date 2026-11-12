"""Outline a Python file."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spanloc_cli import main  # noqa: E402

ap = argparse.ArgumentParser(add_help=False)
ap.add_argument("--file", default=None)
ns, rest = ap.parse_known_args()
path = ns.file or (rest[0] if rest else "")
sys.exit(main(["outline", path.replace("/workspace/", "", 1)]))
