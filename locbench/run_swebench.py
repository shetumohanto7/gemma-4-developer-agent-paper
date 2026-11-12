"""Localization on SWE-bench tasks."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import deque
from functools import partial
from multiprocessing import Pool

import pandas as pd

from spanloc.core import Localizer, RepoIndex, Weights, build_index
from locbench.budget import SpanSizer
from locbench.gitsource import py_files_at
from locbench.gold import gold_locations
from locbench.methods import run_methods
from locbench.metrics import gold_ranks
from locbench.provenance import finish_run, start_run


def hop_distances(index: RepoIndex, seeds: list[str], targets: list[str], max_hops: int = 3) -> list[int | None]:
    """BFS hops from seeds."""
    adj = index.adjacency()
    dist = {s: 0 for s in seeds if s in index.entities}
    q = deque(dist)
    while q:
        u = q.popleft()
        if dist[u] >= max_hops:
            continue
        for v, _w in adj.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return [dist.get(t) for t in targets]


def run_task(row: dict, repos: str) -> dict:
    t0 = time.time()
    git_dir = os.path.join(repos, row["repo"].replace("/", "__") + ".git")
    files = py_files_at(git_dir, row["base_commit"])
    t1 = time.time()
    index = build_index(files)
    t2 = time.time()
    gold = gold_locations(index, row["patch"])
    issue = row["problem_statement"]
    res = run_methods(index, issue, files=files)
    t3 = time.time()
    sig = Localizer(index, Weights()).signals(issue)
    mention_seeds = sorted(sig["mention"], key=lambda k: -sig["mention"][k])[:10]
    bm25_seeds = sorted(sig["bm25"], key=lambda k: -sig["bm25"][k])[:10]
    out = {
        "instance_id": row["instance_id"], "repo": row["repo"],
        "n_py_files": len(files), "n_entities": len(index.entities), "n_edges": len(index.edges),
        "parse_failures": len(index.parse_failures), "gold": gold,
        "seconds": {"read": round(t1 - t0, 2), "index": round(t2 - t1, 2), "rank": round(t3 - t2, 2)},
        "ranks": {}, "top": {},
        "hops": {
            "from_mentions": hop_distances(index, mention_seeds, gold["functions"]),
            "from_bm25": hop_distances(index, bm25_seeds, gold["functions"]),
        },
        "n_mention_seeds": len(sig["mention"]),
    }
    sizer = SpanSizer(files)
    out["gold"]["function_spans"] = sizer.gold_spans(index, gold["functions"])
    out["cands"] = {}
    for m, r in res.items():
        out["ranks"][m] = {
            "files": gold_ranks(r["files"], gold["files"]),
            "functions": gold_ranks(r["entities"], gold["functions"]) if r["entities"] else None,
        }
        out["top"][m] = {"files": r["files"][:10], "entities": r["entities"][:10]}
        out["cands"][m] = sizer.record(index, r["entities"], r["files"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--repos", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--repo", default="", help="only tasks from this owner/repo")
    ap.add_argument("--exclude-repo", action="append", default=[], help="skip tasks from this owner/repo")
    args = ap.parse_args()
    run_name = os.path.splitext(os.path.basename(args.out))[0]
    start_run(run_name, sys.argv, params=vars(args))

    df = pd.read_parquet(args.dataset)
    if args.repo:
        df = df[df.repo == args.repo]
    df = df[~df.repo.isin(args.exclude_repo)]
    done = set()
    if os.path.exists(args.out):
        with open(args.out) as fh:
            done = {json.loads(line)["instance_id"] for line in fh if line.strip()}
    rows = [r for r in df.to_dict("records") if r["instance_id"] not in done]
    if args.limit:
        rows = rows[: args.limit]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    print(f"{len(rows)} tasks to run ({len(done)} already done), {args.workers} workers", flush=True)
    t0 = time.time()
    with open(args.out, "a") as fh, Pool(args.workers, maxtasksperchild=8) as pool:
        for i, res in enumerate(pool.imap_unordered(partial(run_task, repos=args.repos), rows), 1):
            fh.write(json.dumps(res) + "\n")
            fh.flush()
            if i % 10 == 0 or i == len(rows):
                print(f"[{i}/{len(rows)}] {time.time() - t0:.0f}s  last={res['instance_id']}", flush=True)

    finish_run(run_name, "finished", outputs=[args.out])


if __name__ == "__main__":
    main()
