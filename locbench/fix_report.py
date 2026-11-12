"""Analyse the find-vs-fix experiment."""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
from collections import defaultdict

from locbench.competition import load_tasks, snapshot_py_files
from locbench.gold import gold_locations, parse_patch
from spanloc.core import build_index

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONDS = ("base", "spanloc", "oracle_file", "oracle_func")
INFRA_RE = re.compile(r"APIConnection|RemoteDisconnected|ServiceUnavailable|Connection reset|InternalServerError"
                      r"|\b50[234]\b|ConnectTimeout|ReadTimeout", re.I)


def run_dir(model: str, cond: str, suffix: str = "") -> str:
    return os.path.join(ROOT, "experiments/05_find_vs_fix", f"fix_{model}_{cond}{suffix}")


def load_condition(model: str, cond: str, suffix: str = "") -> dict[str, dict]:
    """Condition rows, retries applied."""
    rows = {}
    paths = sorted(glob.glob(os.path.join(run_dir(model, cond, suffix), "*", "task_results.jsonl")))
    paths += sorted(glob.glob(os.path.join(run_dir(model, cond, suffix) + "_retry", "*", "task_results.jsonl")))
    for path in paths:
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                r["_dir"] = os.path.dirname(path)
                rows[r["instance_id"]] = r
    return rows


def exact_mcnemar(b: int, c: int) -> float:
    from math import comb
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def boot(diffs: dict[str, list[float]], cluster: bool, n: int = 4000, seed: int = 0) -> tuple[float, float]:
    flat = [d for v in diffs.values() for d in v]
    if not flat:
        return float("nan"), float("nan")
    rng, repos, stats = random.Random(seed), sorted(diffs), []
    for _ in range(n):
        sample = ([d for rp in (rng.choice(repos) for _ in repos) for d in diffs[rp]] if cluster
                  else [rng.choice(flat) for _ in flat])
        stats.append(sum(sample) / len(sample))
    stats.sort()
    return stats[int(0.025 * n)], stats[int(0.975 * n)]


def patch_touches_gold(row: dict, task: dict, gold: dict, index_cache: dict) -> tuple[bool, bool]:
    p = os.path.join(row["_dir"], "patches", f"{task['instance_id']}.patch")
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return False, False
    patch = open(p, errors="replace").read()
    touched_files = {f for f, e in parse_patch(patch).items()}
    file_hit = bool(touched_files & set(gold["files"]))
    if task["instance_id"] not in index_cache:
        index_cache[task["instance_id"]] = build_index(snapshot_py_files(os.path.join(ROOT, "data/competition"),
                                                                          task["instance_id"]))
    agent_funcs = set(gold_locations(index_cache[task["instance_id"]], patch)["functions"])
    return file_hit, bool(agent_funcs & set(gold["functions"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="e4b")
    ap.add_argument("--no-secondary", action="store_true", help="skip the patch-vs-gold analysis")
    ap.add_argument("--suffix", default="", help="run-name suffix, e.g. _pilot (pilot runs are not analysed)")
    args = ap.parse_args()
    data = {c: load_condition(args.model, c, args.suffix) for c in CONDS}
    summary: dict = {"model": args.model, "suffix": args.suffix, "conditions": {}, "tests": {}}
    present = [c for c in CONDS if data[c]]
    tasks, meta = {}, {}
    if not args.no_secondary:  # needs non-redistributed data
        tasks = {t["instance_id"]: t for t in load_tasks(os.path.join(ROOT, "data/competition"))}
        meta = json.load(open(os.path.join(ROOT, "data/variants/variants_meta.json")))
    common = sorted(set.intersection(*(set(data[c]) for c in present))) if present else []
    infra = {c: sorted(i for i in common if data[c][i].get("error") and INFRA_RE.search(str(data[c][i]["error"])))
             for c in present}
    usable = [i for i in common if not any(i in infra[c] for c in present)]
    print(f"# Find vs fix: gemma-4-{args.model}, {len(usable)} tasks in every condition "
          f"({len(common) - len(usable)} excluded for infrastructure errors)\n")
    print("| condition | resolved | empty patch | patch touches gold file | gold function | context overflow* "
          "| mean tool calls | median minutes |")
    print("|---|---|---|---|---|---|---|---|")
    cache: dict = {}
    touch: dict[str, dict[str, tuple[bool, bool]]] = {}
    for c in present:
        rs = [data[c][i] for i in usable]
        n = len(rs) or 1
        fh = fn = 0
        touch[c] = {}
        if not args.no_secondary:
            for i in usable:
                a, b = patch_touches_gold(data[c][i], tasks[i], meta[i]["gold"], cache)
                touch[c][i] = (a, b)
                fh += a
                fn += b
        mins = sorted(r.get("duration_seconds", 0) / 60 for r in rs)
        overflow = sum(1 for r in rs if "ContextWindowExceeded" in str(r.get("error") or ""))
        summary["conditions"][c] = {
            "n": len(rs), "resolved": sum(bool(r.get("resolved")) for r in rs),
            "empty_patch": sum(1 for r in rs if not r.get("agent_patch_size")),
            "touches_gold_file": None if args.no_secondary else fh,
            "touches_gold_function": None if args.no_secondary else fn,
            "context_overflow": overflow,
            "mean_tool_calls": sum(r.get("tool_calls", 0) for r in rs) / n,
            "median_minutes": mins[len(mins) // 2] if mins else 0.0}
        print(f"| {c} | {sum(bool(r.get('resolved')) for r in rs)}/{len(rs)} ({100 * sum(bool(r.get('resolved')) for r in rs) / n:.1f}%) | "
              f"{100 * sum(1 for r in rs if not r.get('agent_patch_size')) / n:.0f}% | "
              f"{'' if args.no_secondary else f'{100 * fh / n:.0f}%'} | {'' if args.no_secondary else f'{100 * fn / n:.0f}%'} | "
              f"{100 * overflow / n:.0f}% | "
              f"{sum(r.get('tool_calls', 0) for r in rs) / n:.1f} | {mins[len(mins) // 2] if mins else 0:.1f} |")
    print("\n*Exploratory, not pre-registered: the episode ended because the prompt outgrew the 32K window.")
    print("\n## Paired tests (pre-registered H8a-d)\n")
    for a, b, h in (("oracle_func", "base", "H8a"), ("oracle_file", "base", "H8b"), ("spanloc", "base", "H8c"),
                    ("oracle_func", "spanloc", "H8d")):
        if a not in present or b not in present:
            continue
        diffs = defaultdict(list)
        wins = losses = 0
        for i in usable:
            x, y = bool(data[a][i].get("resolved")), bool(data[b][i].get("resolved"))
            wins += x and not y
            losses += y and not x
            diffs[data[a][i]["repo"]].append(float(x) - float(y))
        d = sum(v for vs in diffs.values() for v in vs) / max(1, len(usable))
        lo, hi = boot(diffs, cluster=False)
        clo, chi = boot(diffs, cluster=True)
        summary["tests"][h] = {"a": a, "b": b, "diff": d, "ci": [lo, hi], "ci_clustered": [clo, chi],
                               "a_only": wins, "b_only": losses, "p_exact_mcnemar": exact_mcnemar(wins, losses)}
        print(f"- **{h}: {a} vs {b}**: {100 * d:+.1f} pts [{100 * lo:+.1f}, {100 * hi:+.1f}] "
              f"(repo-clustered [{100 * clo:+.1f}, {100 * chi:+.1f}]); {a}-only {wins} vs {b}-only {losses}, "
              f"exact McNemar p = {exact_mcnemar(wins, losses):.4f}")
    if any(infra.values()):
        print("\nInfrastructure-error exclusions:", {c: v for c, v in infra.items() if v})
    if not args.no_secondary and usable:  # declared before full data
        print("\n## Exploratory (declared before the data was complete; not pre-registered)\n")
        print("Find x fix: P(resolved | final patch edits a gold function / file) per condition. The function level "
              "counts only tasks with function-level gold.\n")
        print("| condition | edits gold function | resolved if so | resolved if not | edits gold file | resolved if so "
              "| resolved if not |")
        print("|---|---|---|---|---|---|---|")
        summary["exploratory"] = {"decomposition": {}, "by_repo": {}}
        for c in present:
            row, out = [], {}
            for level, k in (("function", 1), ("file", 0)):
                pool = [i for i in usable if level == "file" or meta[i]["gold"]["functions"]]  # function gold only
                hit = [i for i in pool if touch[c][i][k]]
                miss = [i for i in pool if not touch[c][i][k]]
                rh = sum(bool(data[c][i].get("resolved")) for i in hit)
                rm = sum(bool(data[c][i].get("resolved")) for i in miss)
                out[level] = {"edits_gold": len(hit), "resolved_if_edits": rh, "not_edits": len(miss),
                              "resolved_if_not": rm}
                row += [f"{len(hit)}/{len(pool)}", f"{rh}/{len(hit)}" if hit else "-",
                        f"{rm}/{len(miss)}" if miss else "-"]
            summary["exploratory"]["decomposition"][c] = out
            print(f"| {c} | " + " | ".join(row) + " |")
        repos = sorted({data[present[0]][i]["repo"] for i in usable})
        print("\nResolved by repository:\n")
        print("| condition | " + " | ".join(repos) + " |")
        print("|---|" + "---|" * len(repos))
        for c in present:
            cells = []
            for rp in repos:
                ids = [i for i in usable if data[c][i]["repo"] == rp]
                k = sum(bool(data[c][i].get("resolved")) for i in ids)
                summary["exploratory"]["by_repo"].setdefault(c, {})[rp] = [k, len(ids)]
                cells.append(f"{k}/{len(ids)}")
            print(f"| {c} | " + " | ".join(cells) + " |")
    summary["n_tasks"], summary["infra_excluded"] = len(usable), {c: v for c, v in infra.items() if v}
    out = os.path.join(ROOT, "experiments/05_find_vs_fix", f"fix_{args.model}{args.suffix}_summary.json")
    with open(out, "w") as fh_out:
        json.dump(summary, fh_out, indent=1)


if __name__ == "__main__":
    main()
