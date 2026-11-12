"""Command-line interface: `spanloc locate` and `spanloc outline`.

Output is plain text sized for a small model's context window (~40 tokens per
candidate). Use --json for machine-readable output in experiments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

try:
    from .core import Localizer, Weights, build_index, iter_python_files
except ImportError:  # copied into skill scripts/
    from spanloc_core import Localizer, Weights, build_index, iter_python_files  # type: ignore


def _default_repo() -> str:
    """Sandbox mounts repo at /workspace."""
    return "/workspace" if os.path.isdir("/workspace/.git") else "."


def _read_issue(args: argparse.Namespace) -> str:
    if args.issue_file == "-":
        return sys.stdin.read()
    if args.issue_file:
        with open(args.issue_file, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    return " ".join(args.issue or [])


def cmd_locate(args: argparse.Namespace) -> int:
    issue = _read_issue(args)
    if not issue.strip():
        print("error: empty issue text; pass it as arguments, --issue-file PATH, or --issue-file - (stdin)")
        return 2
    t0 = time.time()
    index = build_index(iter_python_files(args.repo))
    loc = Localizer(index, Weights())
    ranked = loc.rank(issue, kinds=("function", "class"))
    files = loc.rank_files(loc.rank(issue))
    elapsed = time.time() - t0
    if args.json:
        json.dump({
            "entities": [{"id": r.entity.id, "path": r.entity.path, "start": r.entity.start,
                          "end": r.entity.end, "kind": r.entity.kind, "score": round(r.score, 4),
                          "parts": {k: round(v, 4) for k, v in r.parts.items()}} for r in ranked[: args.top]],
            "files": [{"path": p, "score": round(s, 4)} for p, s in files[: args.files]],
            "n_entities": len(index.entities), "seconds": round(elapsed, 2),
        }, sys.stdout, indent=1)
        print()
        return 0
    print(f"spanloc: ranked {len(index.entities)} code entities in {elapsed:.1f}s")
    print("Most likely edit locations (score  file:lines  definition):")
    for i, r in enumerate(ranked[: args.top], 1):
        e = r.entity
        sig = e.signature if len(e.signature) <= 90 else e.signature[:87] + "..."
        print(f"{i:2d}. {r.score:.2f}  {e.path}:{e.start}-{e.end}  {sig}")
    print("Most likely files: " + ", ".join(p for p, _ in files[: args.files]))
    print("Next: read_file the top candidates at the given lines; confirm before editing.")
    return 0


def cmd_outline(args: argparse.Namespace) -> int:
    target = args.file.lstrip("./")
    index = build_index((p, t) for p, t in iter_python_files(args.repo) if p == target)
    ents = sorted((e for e in index.entities.values() if e.kind != "module"), key=lambda e: e.start)
    if not ents:
        print(f"no Python definitions found in {args.file}")
        return 1
    for e in ents:
        depth = e.id.count(".") - index.entities[index.by_path[e.path]].id.count(".") - 1
        sig = e.signature if len(e.signature) <= 100 else e.signature[:97] + "..."
        print(f"{e.start:5d}-{e.end:<5d}{'  ' * depth}{sig}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="spanloc", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lo = sub.add_parser("locate", help="rank functions/classes/files for an issue")
    lo.add_argument("issue", nargs="*", help="issue text (or use --issue-file)")
    lo.add_argument("--repo", default=_default_repo(), help="repository root (default: /workspace if present, else .)")
    lo.add_argument("--issue-file", help="read issue text from a file, or '-' for stdin")
    lo.add_argument("--top", type=int, default=12)
    lo.add_argument("--files", type=int, default=6)
    lo.add_argument("--json", action="store_true")
    lo.set_defaults(func=cmd_locate)
    ou = sub.add_parser("outline", help="list a file's classes and functions with line ranges")
    ou.add_argument("file")
    ou.add_argument("--repo", default=_default_repo())
    ou.set_defaults(func=cmd_outline)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
