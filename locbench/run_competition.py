"""Localization on main-track tasks."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from functools import partial
from multiprocessing import Pool

from locbench.budget import SpanSizer
from locbench.competition import load_graph, load_tasks, snapshot_py_files
from locbench.gold import gold_locations
from locbench.methods import run_methods
from locbench.metrics import gold_ranks
from locbench.provenance import finish_run, start_run
from locbench.run_swebench import hop_distances
from spanloc.core import Localizer, Weights, build_index


def run_task(task: dict, data: str) -> dict:
    t0 = time.time()
    files = snapshot_py_files(data, task["instance_id"])
    index = build_index(files)
    t1 = time.time()
    gold = gold_locations(index, task["patch"])
    issue = task["problem_statement"]
    graph = load_graph(data, task)
    their_ids = set(graph["nodes"])
    ours = set(index.entities)
    our_edge_set = {(s, d) for s, d, _ in index.edges if s in ours and d in ours}
    their_edge_set = {(s, d) for s, d, _ in graph["edges"] if s in ours and d in ours}

    res = run_methods(index, issue, files=files, alt_edges=graph["edges"])
    t2 = time.time()
    sig = Localizer(index, Weights()).signals(issue)
    mention_seeds = sorted(sig["mention"], key=lambda k: -sig["mention"][k])[:10]
    bm25_seeds = sorted(sig["bm25"], key=lambda k: -sig["bm25"][k])[:10]
    sizer = SpanSizer(files)
    out = {
        "instance_id": task["instance_id"], "repo": task["repo"],
        "n_py_files": len(files), "n_entities": len(index.entities), "n_edges": len(index.edges),
        "parse_failures": len(index.parse_failures),
        "gold": gold | {"function_spans": sizer.gold_spans(index, gold["functions"])},
        "seconds": {"index": round(t1 - t0, 2), "rank": round(t2 - t1, 2)},
        "graph_agreement": {
            "their_nodes": len(their_ids), "our_entities": len(ours), "matched_nodes": len(their_ids & ours),
            "their_edges": len(graph["edges"]), "our_edges_resolved": len(our_edge_set),
            "their_edges_matched": len(their_edge_set), "edge_overlap": len(our_edge_set & their_edge_set),
            "edge_types": sorted({t for _, _, t in graph["edges"]}),
            "gold_functions_in_their_graph": sum(1 for g in gold["functions"] if g in their_ids),
            "unmatched_their_sample": sorted(their_ids - ours)[:5],
        },
        "ranks": {}, "top": {}, "cands": {},
        "hops": {"from_mentions": hop_distances(index, mention_seeds, gold["functions"]),
                 "from_bm25": hop_distances(index, bm25_seeds, gold["functions"])},
        "n_mention_seeds": len(sig["mention"]), "n_snippet_hits": len(sig["snippet"]),
        "has_hints": bool(task.get("hints_text")),
    }
    for m, r in res.items():
        out["ranks"][m] = {"files": gold_ranks(r["files"], gold["files"]),
                           "functions": gold_ranks(r["entities"], gold["functions"]) if r["entities"] else None}
        out["top"][m] = {"files": r["files"][:10], "entities": r["entities"][:10]}
        out["cands"][m] = sizer.record(index, r["entities"], r["files"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    run_name = os.path.splitext(os.path.basename(args.out))[0]
    start_run(run_name, sys.argv, params=vars(args))
    tasks = load_tasks(args.data)
    if args.limit:
        tasks = tasks[: args.limit]
    done = set()
    if os.path.exists(args.out):
        with open(args.out) as fh:
            done = {json.loads(line)["instance_id"] for line in fh if line.strip()}
    todo = [t for t in tasks if t["instance_id"] not in done]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    print(f"{len(todo)} tasks to run ({len(done)} done)", flush=True)
    with open(args.out, "a") as fh, Pool(args.workers, maxtasksperchild=8) as pool:
        for i, res in enumerate(pool.imap_unordered(partial(run_task, data=args.data), todo), 1):
            fh.write(json.dumps(res) + "\n")
            fh.flush()
            if i % 10 == 0 or i == len(todo):
                print(f"[{i}/{len(todo)}] last={res['instance_id']}", flush=True)
    finish_run(run_name, "finished", outputs=[args.out])


if __name__ == "__main__":
    main()
