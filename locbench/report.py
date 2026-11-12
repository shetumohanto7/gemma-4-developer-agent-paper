"""Aggregate results into paper tables."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict

from locbench.metrics import KS_FILE, KS_FUNC, task_metrics

METHOD_ORDER = ["file-bm25", "bm25", "mention", "snippet", "bm25+mention", "ppr", "bm25+ppr",
                "spanloc-v0.1", "spanloc-nosnippet", "spanloc-nomember", "spanloc", "spanloc-noprior",
                "spanloc@their-graph",
                "graphloc", "graphloc-noprior"]  # legacy v0.1 names


def load(paths: list[str]) -> list[dict]:
    rows, seen = [], set()
    for p in paths:
        with open(p) as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    if r["instance_id"] not in seen:
                        seen.add(r["instance_id"])
                        rows.append(r)
    return rows


FILE_ONLY_METHODS = {"file-bm25"}  # file-only rankers


def task_ranks(r: dict, method: str, level: str) -> list | None:
    """Gold ranks; empty means miss."""
    if method not in r["ranks"]:
        return None
    gold = r["gold"]["files" if level == "files" else "functions"]
    if not gold:
        return None
    ranks = r["ranks"][method].get(level)
    if ranks is None:
        if level == "functions" and method in FILE_ONLY_METHODS:
            return None
        return [None] * len(gold)
    return ranks


def per_task(rows: list[dict], method: str, level: str) -> list[dict[str, float]]:
    ks = KS_FILE if level == "files" else KS_FUNC
    out = []
    for r in rows:
        ranks = task_ranks(r, method, level)
        if ranks is None:
            continue
        out.append(task_metrics(ranks, ks))
    return out


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def bootstrap_diff(rows: list[dict], a: str, b: str, level: str, metric: str,
                   n: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Paired task-level bootstrap."""
    ks = KS_FILE if level == "files" else KS_FUNC
    diffs = []
    for r in rows:
        ra, rb = task_ranks(r, a, level), task_ranks(r, b, level)
        if ra is None or rb is None:
            continue
        diffs.append(task_metrics(ra, ks)[metric] - task_metrics(rb, ks)[metric])
    if not diffs:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    boots = sorted(mean([rng.choice(diffs) for _ in diffs]) for _ in range(n))
    return mean(diffs), boots[int(0.025 * n)], boots[int(0.975 * n)]


def cluster_bootstrap_diff(rows: list[dict], a: str, b: str, level: str, metric: str,
                           n: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Bootstrap resampling whole repositories."""
    ks = KS_FILE if level == "files" else KS_FUNC
    by_repo: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        ra, rb = task_ranks(r, a, level), task_ranks(r, b, level)
        if ra is None or rb is None:
            continue
        by_repo[r["repo"]].append(task_metrics(ra, ks)[metric] - task_metrics(rb, ks)[metric])
    repos = sorted(by_repo)
    if not repos:
        return float("nan"), float("nan"), float("nan")
    point = mean([d for rp in repos for d in by_repo[rp]])
    rng = random.Random(seed)
    boots = []
    for _ in range(n):
        sample = [d for rp in (rng.choice(repos) for _ in repos) for d in by_repo[rp]]
        boots.append(mean(sample))
    boots.sort()
    return point, boots[int(0.025 * n)], boots[int(0.975 * n)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--json", help="write a machine-readable summary here")
    ap.add_argument("--baseline", default="bm25")
    ap.add_argument("--ours", default="spanloc")
    args = ap.parse_args()
    rows = load(args.results)
    methods = [m for m in METHOD_ORDER if any(m in r["ranks"] for r in rows)]
    summary: dict = {"n_tasks": len(rows), "methods": {}, "repos": dict(Counter(r["repo"] for r in rows))}

    n_func = sum(1 for r in rows if r["gold"]["functions"])
    print(f"# Localization results: {len(rows)} tasks ({n_func} with function-level gold)\n")
    print("## File level\n")
    cols = [f"acc@{k}" for k in KS_FILE] + ["mrr"]
    print("| method | " + " | ".join(cols) + " |")
    print("|---" * (len(cols) + 1) + "|")
    for m in methods:
        t = per_task(rows, m, "files")
        vals = {c: mean([x[c] for x in t]) for c in cols}
        summary["methods"].setdefault(m, {})["files"] = vals | {"n": len(t)}
        print(f"| {m} | " + " | ".join(f"{100 * vals[c]:.1f}" if c != "mrr" else f"{vals[c]:.3f}" for c in cols) + " |")

    print("\n## Function level (all gold functions/classes in top-k = acc; any = hit)\n")
    cols = [f"acc@{k}" for k in KS_FUNC] + [f"hit@{k}" for k in (1, 5, 10)] + ["mrr"]
    print("| method | " + " | ".join(cols) + " |")
    print("|---" * (len(cols) + 1) + "|")
    for m in methods:
        t = per_task(rows, m, "functions")
        if not t:
            continue
        vals = {c: mean([x[c] for x in t]) for c in cols}
        summary["methods"].setdefault(m, {})["functions"] = vals | {"n": len(t)}
        print(f"| {m} | " + " | ".join(f"{100 * vals[c]:.1f}" if c != "mrr" else f"{vals[c]:.3f}" for c in cols) + " |")

    print(f"\n## Paired bootstrap: {args.ours} minus {args.baseline} (95% CI, percentage points)\n")
    summary["paired"] = {}
    for level, metric in [("files", "acc@1"), ("files", "acc@5"), ("functions", "acc@5"),
                          ("functions", "acc@10"), ("functions", "hit@1")]:
        d, lo, hi = bootstrap_diff(rows, args.ours, args.baseline, level, metric)
        _, clo, chi = cluster_bootstrap_diff(rows, args.ours, args.baseline, level, metric)
        summary["paired"][f"{level}/{metric}"] = [d, lo, hi, clo, chi]
        print(f"- {level} {metric}: {100 * d:+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}] "
              f"(repo-clustered [{100 * clo:+.1f}, {100 * chi:+.1f}])")

    print(f"\n## Per repository ({args.ours}, function acc@10 / file acc@5)\n")
    by_repo = defaultdict(list)
    for r in rows:
        by_repo[r["repo"]].append(r)
    summary["per_repo"] = {}
    for repo, rs in sorted(by_repo.items(), key=lambda kv: -len(kv[1])):
        f = per_task(rs, args.ours, "functions")
        fl = per_task(rs, args.ours, "files")
        b = per_task(rs, args.baseline, "functions")
        summary["per_repo"][repo] = {"n": len(rs), "func_acc10": mean([x["acc@10"] for x in f]),
                                     "file_acc5": mean([x["acc@5"] for x in fl]),
                                     "baseline_func_acc10": mean([x["acc@10"] for x in b])}
        print(f"- {repo} (n={len(rs)}): func acc@10 {100 * summary['per_repo'][repo]['func_acc10']:.1f} "
              f"(baseline {100 * summary['per_repo'][repo]['baseline_func_acc10']:.1f}), "
              f"file acc@5 {100 * summary['per_repo'][repo]['file_acc5']:.1f}")

    print("\n## Graph distance from seeds to gold functions (hops, capped at 3)\n")
    summary["hops"] = {}
    for key in ("from_mentions", "from_bm25"):
        c = Counter()
        for r in rows:
            for h in r["hops"][key]:
                c["unreached" if h is None else str(h)] += 1
        tot = sum(c.values()) or 1
        summary["hops"][key] = {k: v / tot for k, v in c.items()}
        print(f"- {key}: " + ", ".join(f"{k}: {100 * c[k] / tot:.1f}%" for k in ["0", "1", "2", "3", "unreached"]))

    secs = [r["seconds"]["index"] + r["seconds"]["rank"] for r in rows]
    secs.sort()
    summary["seconds_median"] = secs[len(secs) // 2] if secs else None
    print(f"\nMedian index+rank time per task: {summary['seconds_median']:.2f}s; "
          f"max {secs[-1]:.2f}s" if secs else "")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(summary, fh, indent=1)


if __name__ == "__main__":
    main()
