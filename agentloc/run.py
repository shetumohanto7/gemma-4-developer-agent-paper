"""Run agentic localization experiments."""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import pandas as pd

from agentloc.agent import OllamaClient, OpenAIClient, run_episode
from agentloc.sandbox import Sandbox
from locbench.provenance import finish_run, start_run
from spanloc.core import RepoIndex, build_index, iter_python_files
from locbench.gold import gold_locations

SCRATCH = os.environ.get("AGENTLOC_TMP", tempfile.gettempdir())


def materialize_swebench(repos: str, repo: str, commit: str) -> str:
    """Export commit tree to tempdir."""
    dest = tempfile.mkdtemp(prefix="agentloc-", dir=SCRATCH)
    git_dir = os.path.join(repos, repo.replace("/", "__") + ".git")
    archive = subprocess.run(["git", f"--git-dir={git_dir}", "archive", "--format=tar", commit],
                             capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", dest], input=archive, check=True)
    return dest


def resolve(index: RepoIndex, loc: str) -> tuple[str | None, str | None]:
    """Split location into path, entity."""
    loc = loc.strip().strip("`").replace(":", "::", 1) if "::" not in loc and ":" in loc else loc.strip().strip("`")
    path, _, qual = loc.partition("::")
    path = path.strip().lstrip("./").replace("/workspace/", "")
    files = [p for p in index.by_path if p == path or p.endswith("/" + path) or path.endswith("/" + p)]
    if not files:
        return None, None
    f = min(files, key=len)
    mod = index.by_path[f]
    qual = qual.strip().split("(")[0].strip()
    if not qual:
        return f, None
    eid = f"{mod}.{qual}"
    if eid in index.entities:
        return f, eid
    tail = [e for e in index.by_name.get(qual.split(".")[-1], []) if index.entities[e].path == f
            and e.endswith("." + qual)]
    return f, (tail[0] if tail else None)


def score(index: RepoIndex, gold: dict, submitted: list[str]) -> dict:
    files, ents = [], []
    for s in submitted:
        f, e = resolve(index, s)
        if f:
            files.append(f)
        if e:
            ents.append(e)
    gf, gfun = set(gold["files"]), set(gold["functions"])

    def covers(sub: str, g: str) -> bool:  # class covers its methods
        return sub == g or g.startswith(sub + ".")

    return {
        "file_hit": any(f in gf for f in files),
        "file_top1": bool(files) and files[0] in gf,
        "func_hit": any(e in gfun for e in ents),
        "func_hit_lenient": any(covers(e, g) for e in ents for g in gfun),
        "func_all": bool(gfun) and all(any(covers(e, g) for e in ents) for g in gfun),
        "resolved": len(ents), "n_submitted": len(submitted),
    }


def run_task(row: dict, args, client, conditions: list[str], seeds: list[int], done: set,
             lock: threading.Lock, pos: str) -> None:
    todo = [(c, s) for s in seeds for c in conditions if (row["instance_id"], c, s) not in done]
    if not todo:
        return
    repo_dir = materialize_swebench(args.repos, row["repo"], row["base_commit"])
    try:
        index = build_index(iter_python_files(repo_dir))
        gold = gold_locations(index, row["patch"])
        for cond, seed in todo:
            with Sandbox(repo_dir) as sb:
                ep = run_episode(sb, row["problem_statement"], client, condition=cond,
                                 max_turns=args.max_turns, seed=seed, temperature=args.temperature,
                                 think=args.think)
            res = {"instance_id": row["instance_id"], "repo": row["repo"], "condition": cond, "seed": seed,
                   "model": args.model, "backend": args.backend, "think": args.think,
                   "temperature": args.temperature, "gold": gold, "score": score(index, gold, ep.submitted),
                   **asdict(ep)}
            with lock:
                with open(args.out, "a") as fh:
                    fh.write(json.dumps(res) + "\n")
            print(f"[{pos}] {row['instance_id']} {cond} s{seed}: func_hit={res['score']['func_hit']} "
                  f"file_hit={res['score']['file_hit']} turns={ep.turns} {ep.seconds:.0f}s {ep.error}", flush=True)
    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--repos", required=True)
    ap.add_argument("--model", required=True, help="served model name (openai) or Ollama tag")
    ap.add_argument("--backend", choices=("openai", "ollama"), default="openai")
    ap.add_argument("--base-url", default="", help="OpenAI-compatible server, e.g. the Modal vLLM endpoint")
    ap.add_argument("--api-key-file", default=".secrets/vllm_api_key")
    ap.add_argument("--workers", type=int, default=1, help="tasks run in parallel (each in its own sandbox)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--ids", default="", help="comma-separated instance ids (overrides --n sampling)")
    ap.add_argument("--shard", default="", help="i/n: run every n-th task starting at i")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--conditions", default="base,skill,inject")
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--think", action="store_true", help="enable Gemma 4 thinking (harness default is on)")
    ap.add_argument("--run-name", default="", help="manifest name (default: output file stem)")
    ap.add_argument("--retry-infra-failures", action="store_true",
                    help="re-run episodes whose only recorded result is an infrastructure failure")
    args = ap.parse_args()
    run_name = args.run_name or os.path.splitext(os.path.basename(args.out))[0]
    start_run(run_name, sys.argv, params=vars(args))

    if args.backend == "openai":
        if not args.base_url:
            ap.error("--base-url is required for the openai backend")
        with open(args.api_key_file) as fh:
            client = OpenAIClient(args.base_url, args.model, fh.read().strip())
    else:
        client = OllamaClient(args.model)

    df = pd.read_parquet(args.dataset)
    ids = sorted(df.instance_id)
    random.Random(2026).shuffle(ids)
    sample = set(args.ids.split(",")) if args.ids else set(ids[: args.n])
    rows = [r for r in df.to_dict("records") if r["instance_id"] in sample]
    rows.sort(key=lambda r: ids.index(r["instance_id"]))
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        rows = rows[i::n]
    done = set()
    if os.path.exists(args.out):
        for line in open(args.out):
            if line.strip():
                r = json.loads(line)
                if args.retry_infra_failures and r["error"].startswith("model call failed"):
                    continue  # later success still counts
                done.add((r["instance_id"], r["condition"], r["seed"]))
    seeds = [int(s) for s in args.seeds.split(",")]
    conditions = args.conditions.split(",")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    lock = threading.Lock()
    status = "failed"
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_task, row, args, client, conditions, seeds, done, lock, f"{i}/{len(rows)}")
                       for i, row in enumerate(rows, 1)]
            for f in futures:
                f.result()  # surface worker exceptions
        status = "finished"
    finally:
        finish_run(run_name, status, outputs=[args.out])


if __name__ == "__main__":
    main()
