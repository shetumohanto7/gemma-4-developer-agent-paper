"""Dev-split fusion grid tuning."""

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

from spanloc.core import RepoIndex, Weights, build_index, path_prior, tokenize, mention_scores
from locbench.gitsource import py_files_at
from locbench.gold import gold_locations
from locbench.metrics import gold_ranks

FENCE_RE = re.compile(r"```[\w+-]*\n(.*?)```", re.S)
INLINE_RE = re.compile(r"`([^`\n]{12,200})`")
WS_RE = re.compile(r"\s+")
CODEISH_RE = re.compile(r"[=(\[.]")


def _norm(line: str) -> str:
    return WS_RE.sub(" ", line.strip())


def code_snippets(issue: str, max_snippets: int = 40) -> list[str]:
    """Code lines quoted in issue."""
    cands: list[str] = []
    for block in FENCE_RE.findall(issue):
        cands += block.splitlines()
    cands += INLINE_RE.findall(issue)
    cands += [ln for ln in issue.splitlines() if CODEISH_RE.search(ln)]
    out, seen = [], set()
    for c in cands:
        c = c.strip()
        if c.startswith((">>>", "...")):
            c = c[3:].strip()
        if c.startswith(("File \"", "Traceback", "#", "$", "pip ")):
            continue
        n = _norm(c)
        if 12 <= len(n) <= 200 and CODEISH_RE.search(n) and n not in seen:
            seen.add(n)
            out.append(n)
    return out[:max_snippets]


def line_table(files: list[tuple[str, str]]) -> dict[str, list[tuple[str, int]]]:
    table: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path, text in files:
        for i, ln in enumerate(text.splitlines(), 1):
            n = _norm(ln)
            if len(n) >= 12:
                table[n].append((path, i))
    return table


def snippet_scores(index: RepoIndex, table: dict, issue: str, max_hits: int = 3) -> dict[str, float]:
    per_file: dict[str, list] = defaultdict(list)
    for e in index.entities.values():
        if e.kind != "module":
            per_file[e.path].append(e)
    scores: dict[str, float] = defaultdict(float)
    for snip in code_snippets(issue):
        hits = table.get(snip, [])
        if not hits or len(hits) > max_hits:
            continue
        for path, ln in hits:
            enclosing = [e for e in per_file.get(path, []) if e.start <= ln <= e.end]
            target = max(enclosing, key=lambda e: e.start).id if enclosing else index.by_path.get(path)
            if target:
                scores[target] += 1.0 / len(hits) ** 0.5
    return scores


def _norm_scores(s: dict[str, float]) -> dict[str, float]:
    top = max(s.values()) if s else 0.0
    return {k: v / top for k, v in s.items()} if top > 0 else {}


GRID = {
    "ppr": [0.0, 0.3, 0.6, 1.0],
    "alpha": [0.2, 0.35, 0.5],
    "mention": [0.5, 1.0],
    "snippet": [0.0, 1.0, 2.0],
}


def run_task(row: dict, repos: str) -> dict:
    git_dir = os.path.join(repos, row["repo"].replace("/", "__") + ".git")
    files = py_files_at(git_dir, row["base_commit"])
    index = build_index(files)
    gold = gold_locations(index, row["patch"])
    issue = row["problem_statement"]
    w0 = Weights()
    bm25 = _norm_scores(index.bm25(tokenize(issue)))
    snip = _norm_scores(snippet_scores(index, line_table(files), issue))
    ment_raw = mention_scores(index, issue, w0)
    ment = _norm_scores(ment_raw)
    bm25_top = sorted(bm25.items(), key=lambda kv: -kv[1])[: w0.seed_topk]
    ranks: dict[str, dict] = {}
    ppr_cache: dict[tuple, dict] = {}
    for wp, alpha, wm, ws in itertools.product(*GRID.values()):
        seeds: dict[str, float] = defaultdict(float)
        for k, v in bm25_top:
            seeds[k] += v
        for k, v in ment.items():
            seeds[k] += wm * v
        for k, v in snip.items():
            seeds[k] += ws * v
        key = (alpha, wm, ws)
        if wp > 0 and key not in ppr_cache:
            ppr_cache[key] = _norm_scores(index.ppr(dict(seeds), alpha=alpha))
        ppr = ppr_cache.get(key, {}) if wp > 0 else {}
        if wp == 0 and alpha != GRID["alpha"][0]:
            continue  # alpha is irrelevant without propagation
        keys = set(bm25) | set(ment) | set(snip) | set(ppr)
        scored = []
        for k in keys:
            ent = index.entities.get(k)
            if ent is None:
                continue
            s = (bm25.get(k, 0) + wm * ment.get(k, 0) + ws * snip.get(k, 0) + wp * ppr.get(k, 0)) * path_prior(ent.path)
            if s > 0:
                scored.append((s, k, ent))
        scored.sort(key=lambda x: (-x[0], x[1]))
        ents = [k for _, k, e in scored if e.kind in ("function", "class")]
        per: dict[str, float] = {}
        for s, k, e in scored:
            per.setdefault(e.path, s)
        files_ranked = list(per)
        ranks[f"ppr={wp},alpha={alpha},mention={wm},snippet={ws}"] = {
            "functions": gold_ranks(ents, gold["functions"]), "files": gold_ranks(files_ranked, gold["files"])}
    return {"instance_id": row["instance_id"], "repo": row["repo"], "gold": gold, "ranks": ranks,
            "n_snippets": len(code_snippets(issue)), "snippet_hit": bool(snip)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verified", required=True)
    ap.add_argument("--lite", required=True)
    ap.add_argument("--repos", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--exclude-repo", action="append", default=[])
    args = ap.parse_args()
    ver = pd.read_parquet(args.verified)
    lite_ids = set(pd.read_parquet(args.lite).instance_id)
    dev = ver[~ver.instance_id.isin(lite_ids) & ~ver.repo.isin(args.exclude_repo)]
    done = set()
    if os.path.exists(args.out):
        done = {json.loads(l)["instance_id"] for l in open(args.out) if l.strip()}
    rows = [r for r in dev.to_dict("records") if r["instance_id"] not in done]
    print(f"dev split: {len(dev)} tasks (Verified minus Lite); {len(rows)} to run", flush=True)
    with open(args.out, "a") as fh, Pool(args.workers, maxtasksperchild=8) as pool:
        for i, res in enumerate(pool.imap_unordered(partial(run_task, repos=args.repos), rows), 1):
            fh.write(json.dumps(res) + "\n")
            fh.flush()
            if i % 25 == 0:
                print(f"[{i}/{len(rows)}]", flush=True)


if __name__ == "__main__":
    main()
