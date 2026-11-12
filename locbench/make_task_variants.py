"""Write find-vs-fix task variants."""

from __future__ import annotations

import argparse
import json
import os

from locbench.competition import load_tasks, snapshot_py_files
from locbench.gold import gold_locations
from spanloc.core import Localizer, Weights, build_index

HINTS = {
    "spanloc": ("\n\n---\nA localization tool ranked the code most likely to need changes "
                "(it may be wrong; verify before editing):\n{ranking}"),
    "oracle_file": "\n\n---\nHint: the fix for this issue belongs in {files}.",
    "oracle_func": "\n\n---\nHint: the fix for this issue belongs in {funcs}.",
}
CONDITIONS = ("base", "spanloc", "oracle_file", "oracle_func")


def ranking_text(index, issue: str, top: int = 8) -> str:
    loc = Localizer(index, Weights())
    lines = []
    for i, r in enumerate(loc.rank(issue, kinds=("function", "class"))[:top], 1):
        e = r.entity
        sig = e.signature if len(e.signature) <= 90 else e.signature[:87] + "..."
        lines.append(f"{i}. {e.path}:{e.start}-{e.end}  {sig}")
    return "\n".join(lines)


def variants_for(task: dict, files: list[tuple[str, str]]) -> tuple[dict[str, str], dict]:
    index = build_index(files)
    gold = gold_locations(index, task["patch"])
    issue = task["problem_statement"]
    gold_files = gold["files"] + gold["added_files"]
    funcs = []
    for g in gold["functions"]:
        e = index.entities[g]
        qual = g[len(index.entities[index.by_path[e.path]].id) + 1:]
        funcs.append(f"`{e.path}::{qual}` (lines {e.start}-{e.end})")
    if not funcs:  # fall back to file hint
        funcs = [f"`{p}`" for p in gold_files]
    out = {
        "base": issue,
        "spanloc": issue + HINTS["spanloc"].format(ranking=ranking_text(index, issue)),
        "oracle_file": issue + HINTS["oracle_file"].format(files=", ".join(f"`{p}`" for p in gold_files)),
        "oracle_func": issue + HINTS["oracle_func"].format(funcs=", ".join(funcs)),
    }
    return out, gold


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    tasks = load_tasks(args.data)
    os.makedirs(args.out, exist_ok=True)
    handles = {c: open(os.path.join(args.out, f"tasks_{c}.jsonl"), "w") for c in CONDITIONS}
    meta = {}
    for t in tasks:
        texts, gold = variants_for(t, snapshot_py_files(args.data, t["instance_id"]))
        for c in CONDITIONS:
            handles[c].write(json.dumps(dict(t, problem_statement=texts[c])) + "\n")
        meta[t["instance_id"]] = {"gold": gold, "hint_chars": {c: len(texts[c]) - len(texts["base"]) for c in CONDITIONS}}
    for h in handles.values():
        h.close()
    with open(os.path.join(args.out, "variants_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(f"wrote {len(tasks)} tasks x {len(CONDITIONS)} variants to {args.out}")


if __name__ == "__main__":
    main()
