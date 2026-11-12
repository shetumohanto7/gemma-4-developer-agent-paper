"""Public leaderboard resolution analysis."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict

BINS = [(1, 1), (2, 3), (4, 7), (8, 15), (16, 10_000)]


def trunc2(x: float) -> float:
    return math.floor(x * 100 + 1e-9) / 100


def consistent_ns(scores: set[float], lo: int = 20, hi: int = 200) -> list[int]:
    ok = []
    for n in range(lo, hi + 1):
        table = {trunc2(k / n) for k in range(n + 1)}
        if all(s in table for s in scores):
            ok.append(n)
    return ok


def binom_pmf(n: int, p: float) -> list[float]:
    return [math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1)]


def expected_max(pmf: list[float], m: int) -> float:
    """Expected best of m draws."""
    cdf, acc = [], 0.0
    for q in pmf:
        acc += q
        cdf.append(min(acc, 1.0))
    return sum(1 - cdf[k - 1] ** m for k in range(1, len(pmf)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", help="raw Kaggle leaderboard JSON or the anonymized [score, submissions] file")
    ap.add_argument("--out", default=".")
    ap.add_argument("--write-anonymized", help="save only [score, submission count] pairs to this path")
    args = ap.parse_args()
    d = json.load(open(args.snapshot))
    if "entries" in d:  # anonymized snapshot
        entries = [(float(s), int(c)) for s, c in d["entries"]]
    else:
        subs = {t["teamId"]: t["submissionCount"] for t in d["teams"]}
        entries = [(float(e["displayScore"]), subs.get(e["teamId"], 0)) for e in d["publicLeaderboard"]]
    if args.write_anonymized:
        with open(args.write_anonymized, "w") as fh:
            json.dump({"source": "kaggle.com/competitions/gemma-4-developer-agent public leaderboard",
                       "fetched": "2026-10-22", "fields": ["display_score", "submission_count"],
                       "entries": sorted([[f"{s:.2f}", c] for s, c in entries], key=lambda x: (-float(x[0]), x[1]))},
                      fh)
    scores = {s for s, _ in entries}
    ns = consistent_ns(scores)
    n = min(ns)
    lookup = {trunc2(k / n): k for k in range(n, -1, -1)}
    solved = [(lookup[s], c) for s, c in entries]

    lines = [f"# Public leaderboard resolution (snapshot: {os.path.basename(args.snapshot)})", ""]
    lines.append(f"- Teams on the public LB: {len(entries)}")
    lines.append(f"- Task counts N in [20, 200] consistent with all {len(scores)} distinct displayed scores: "
                 f"{ns[:10]}{' ...' if len(ns) > 10 else ''} -> N = {n} public tasks; one task = {100 / n:.2f} points")
    top = max(k for k, _ in solved)
    lines.append(f"- Best public score: {top}/{n} = {top / n:.3f}; teams at the max: "
                 f"{sum(1 for k, _ in solved if k == top)}")
    nz = sorted(k for k, _ in solved if k > 0)
    lines.append(f"- Median non-zero team: {nz[len(nz) // 2]}/{n}; zero-score teams: {sum(1 for k, _ in solved if k == 0)}")
    lines += ["", "## Solved public tasks by number of submissions", "",
              "| submissions | teams | median | p90 | max | binomial best-of-n bound (p = median single-submission rate) |",
              "|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for k, c in solved:
        for lo, hi in BINS:
            if lo <= c <= hi and k > 0:
                by[(lo, hi)].append((k, c))
    single = sorted(k for k, c in solved if c == 1 and k > 0)
    p0 = single[len(single) // 2] / n
    p_base = 10 / n  # leaderboard's dense mode
    rows_json = []
    for lo, hi in BINS:
        ks = sorted(k for k, _ in by[(lo, hi)])
        cs = sorted(c for _, c in by[(lo, hi)])
        if not ks:
            continue
        mc = cs[len(cs) // 2]
        bound = expected_max(binom_pmf(n, p0), mc)
        rows_json.append({"bin": [lo, hi], "teams": len(ks), "median": ks[len(ks) // 2],
                          "p90": ks[int(0.9 * len(ks))], "max": ks[-1], "median_subs": mc,
                          "binomial_best_of_n": bound})
        label = f"{lo}" if lo == hi else f"{lo}-{hi}" if hi < 10_000 else f"{lo}+"
        lines.append(f"| {label} (median {mc}) | {len(ks)} | {ks[len(ks) // 2]} | {ks[int(0.9 * len(ks))]} | "
                     f"{ks[-1]} | {bound:.1f} |")
    sd = math.sqrt(n * p_base * (1 - p_base))
    lines += ["", "## Selection-only null model at the leaderboard's modal score", "",
              f"For an agent solving each public task with probability p = {p_base:.3f} (10/{n}, the modal score), "
              f"a single run has SD <= {sd:.2f} tasks (binomial bound). Expected best public score after m "
              "identical re-submissions (upper bound; heterogeneity lowers it):", ""]
    for m in (1, 2, 5, 10, 20, 40):
        e = expected_max(binom_pmf(n, p_base), m)
        lines.append(f"- m = {m:2d}: {e:.1f}/{n} = {e / n:.3f}")
    hist = Counter(k for k, _ in solved)
    lines += ["", "## Histogram of solved public tasks", "", "| solved | teams |", "|---|---|"]
    lines += [f"| {k} | {hist[k]} |" for k in sorted(hist)]
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "public_lb_summary.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(args.out, "public_lb_summary.json"), "w") as fh:
        json.dump({"n_public_tasks": n, "consistent_ns": ns[:20], "bins": rows_json,
                   "histogram": dict(sorted(hist.items())), "p_single_median": p0, "p_modal": p_base}, fh, indent=1)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
