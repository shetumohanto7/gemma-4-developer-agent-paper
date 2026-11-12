"""Second dev-split tuning grid."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
from collections import defaultdict
from functools import partial
from multiprocessing import Pool

import pandas as pd

from spanloc.core import RepoIndex, Weights, build_index, mention_scores, path_prior, tokenize
from locbench.gitsource import py_files_at
from locbench.gold import gold_locations
from locbench.metrics import gold_ranks
from locbench.tune import _norm_scores, line_table, snippet_scores

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

GRID = {
    "ppr": [0.3, 0.6],
    "snippet": [0.0, 1.0],
    "strip": [0, 1],
    "member": [0.0, 0.5, 1.0],
}


def member_expand(index: RepoIndex, mention: dict[str, float], bm25: dict[str, float],
                  weight: float) -> dict[str, float]:
    """Share class mentions with methods."""
    if weight <= 0:
        return dict(mention)
    children: dict[str, list[str]] = defaultdict(list)
    for e in index.entities.values():
        if e.parent and e.kind == "function":
            children[e.parent].append(e.id)
    out = dict(mention)
    for cid, m in mention.items():
        ent = index.entities.get(cid)
        if ent is None or ent.kind != "class" or m <= 0:
            continue
        kids = children.get(cid, [])
        lex = {k: bm25.get(k, 0.0) for k in kids}
        total = sum(lex.values())
        if total <= 0:
            continue
        for k, v in lex.items():
            if v > 0:
                out[k] = out.get(k, 0.0) + weight * m * v / total
    return out


def run_task(row: dict, repos: str) -> dict:
    git_dir = os.path.join(repos, row["repo"].replace("/", "__") + ".git")
    files = py_files_at(git_dir, row["base_commit"])
    index = build_index(files)
    gold = gold_locations(index, row["patch"])
    table = line_table(files)
    w0 = Weights()
    ranks: dict[str, dict] = {}
    for strip in GRID["strip"]:
        issue = HTML_COMMENT_RE.sub(" ", row["problem_statement"]) if strip else row["problem_statement"]
        bm25 = _norm_scores(index.bm25(tokenize(issue)))
        ment0 = mention_scores(index, issue, w0)
        snip = _norm_scores(snippet_scores(index, table, issue))
        bm25_top = sorted(bm25.items(), key=lambda kv: -kv[1])[: w0.seed_topk]
        for member, ws in itertools.product(GRID["member"], GRID["snippet"]):
            ment = _norm_scores(member_expand(index, ment0, bm25, member))
            seeds: dict[str, float] = defaultdict(float)
            for k, v in bm25_top:
                seeds[k] += v
            for k, v in ment.items():
                seeds[k] += v
            for k, v in snip.items():
                seeds[k] += ws * v
            ppr = _norm_scores(index.ppr(dict(seeds), alpha=0.35))
            for wp in GRID["ppr"]:
                keys = set(bm25) | set(ment) | set(snip) | set(ppr)
                scored = []
                for k in keys:
                    ent = index.entities.get(k)
                    if ent is None:
                        continue
                    s = (bm25.get(k, 0) + ment.get(k, 0) + ws * snip.get(k, 0) + wp * ppr.get(k, 0)) \
                        * path_prior(ent.path)
                    if s > 0:
                        scored.append((s, k, ent))
                scored.sort(key=lambda x: (-x[0], x[1]))
                ents = [k for _, k, e in scored if e.kind in ("function", "class")]
                per: dict[str, float] = {}
                for s, k, e in scored:
                    per.setdefault(e.path, s)
                cfg = f"ppr={wp},snippet={ws},strip={strip},member={member}"
                ranks[cfg] = {"functions": gold_ranks(ents, gold["functions"]),
                              "files": gold_ranks(list(per), gold["files"])}
    return {"instance_id": row["instance_id"], "repo": row["repo"], "gold": gold, "ranks": ranks,
            "has_html_comment": bool(HTML_COMMENT_RE.search(row["problem_statement"]))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verified", required=True)
    ap.add_argument("--lite", required=True)
    ap.add_argument("--repos", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    ver = pd.read_parquet(args.verified)
    lite_ids = set(pd.read_parquet(args.lite).instance_id)
    dev = ver[~ver.instance_id.isin(lite_ids)]
    done = set()
    if os.path.exists(args.out):
        done = {json.loads(l)["instance_id"] for l in open(args.out) if l.strip()}
    rows = [r for r in dev.to_dict("records") if r["instance_id"] not in done]
    print(f"dev split: {len(dev)} tasks; {len(rows)} to run", flush=True)
    with open(args.out, "a") as fh, Pool(args.workers, maxtasksperchild=8) as pool:
        for i, res in enumerate(pool.imap_unordered(partial(run_task, repos=args.repos), rows), 1):
            fh.write(json.dumps(res) + "\n")
            fh.flush()
            if i % 25 == 0:
                print(f"[{i}/{len(rows)}]", flush=True)


if __name__ == "__main__":
    main()
