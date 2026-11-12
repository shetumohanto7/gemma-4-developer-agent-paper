"""Analyse agentic-localization runs."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import Counter, defaultdict

INFRA = "model call failed"


def load(path: str) -> list[dict]:
    """Last non-infra row per key."""
    best: dict[tuple, dict] = {}
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            key = (r["instance_id"], r["condition"], r["seed"])
            prev = best.get(key)
            if prev is None or prev["error"].startswith(INFRA) or not r["error"].startswith(INFRA):
                best[key] = r
    return list(best.values())


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def boot(diffs_by_repo: dict[str, list[float]], n: int = 4000, seed: int = 0, cluster: bool = False):
    flat = [d for v in diffs_by_repo.values() for d in v]
    if not flat:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    stats = []
    repos = sorted(diffs_by_repo)
    for _ in range(n):
        if cluster:
            sample = [d for rp in (rng.choice(repos) for _ in repos) for d in diffs_by_repo[rp]]
        else:
            sample = [rng.choice(flat) for _ in flat]
        stats.append(sum(sample) / len(sample))
    stats.sort()
    return sum(flat) / len(flat), stats[int(0.025 * n)], stats[int(0.975 * n)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    args = ap.parse_args()
    rows = load(args.results)
    by = defaultdict(dict)
    for r in rows:
        by[(r["instance_id"], r["seed"])][r["condition"]] = r
    conds = [c for c in ("base", "skill", "inject") if any(c in v for v in by.values())]
    model = rows[0]["model"] if rows else "?"
    print(f"# Agentic localization: {model}, {len(by)} task-seeds, conditions {conds}\n")

    print("| condition | episodes | infra failures | function hit | lenient hit | file hit | "
          "median prompt tokens | mean tool calls | fallback parse | turn limit | no tool call | overflow |")
    print("|---" * 12 + "|")
    for c in conds:
        eps = [v[c] for v in by.values() if c in v]
        ok = [e for e in eps if not e["error"].startswith(INFRA)]
        n = len(ok) or 1
        toks = sorted(e["prompt_tokens"] for e in ok)
        err = Counter(e["error"] or "submitted" for e in ok)
        print(f"| {c} | {len(eps)} | {len(eps) - len(ok)} | {100 * sum(e['score']['func_hit'] for e in ok) / n:.1f}% | "
              f"{100 * sum(e['score']['func_hit_lenient'] for e in ok) / n:.1f}% | "
              f"{100 * sum(e['score']['file_hit'] for e in ok) / n:.1f}% | {statistics.median(toks) if toks else 0:.0f} | "
              f"{sum(e['turns'] for e in ok) / n:.1f} | {100 * sum(e['fallback_parse'] for e in ok) / n:.0f}% | "
              f"{100 * err['turn limit'] / n:.0f}% | {100 * err['no tool call'] / n:.0f}% | "
              f"{100 * err['context overflow'] / n:.0f}% |")

    print("\n## Paired tests against base (pre-registered H7a, H7b, H7c)\n")
    for c in [x for x in conds if x != "base"]:
        pairs = [(v["base"], v[c]) for v in by.values() if "base" in v and c in v
                 and not v["base"]["error"].startswith(INFRA) and not v[c]["error"].startswith(INFRA)]
        b = sum(1 for x, y in pairs if y["score"]["func_hit"] and not x["score"]["func_hit"])
        cc = sum(1 for x, y in pairs if x["score"]["func_hit"] and not y["score"]["func_hit"])
        hit_d, tok_d = defaultdict(list), defaultdict(list)
        for x, y in pairs:
            hit_d[x["repo"]].append(float(y["score"]["func_hit"]) - float(x["score"]["func_hit"]))
            tok_d[x["repo"]].append(y["prompt_tokens"] - x["prompt_tokens"])
        d, lo, hi = boot(hit_d)
        _, clo, chi = boot(hit_d, cluster=True)
        td, tlo, thi = boot(tok_d)
        _, tclo, tchi = boot(tok_d, cluster=True)
        print(f"- **{c} vs base** ({len(pairs)} pairs): function hit {100 * d:+.1f} pts "
              f"[{100 * lo:+.1f}, {100 * hi:+.1f}] (repo-clustered [{100 * clo:+.1f}, {100 * chi:+.1f}]); "
              f"discordant {c}-only {b} vs base-only {cc}, exact McNemar p = {exact_mcnemar(b, cc):.4f}")
        print(f"  prompt tokens per episode {td:+.0f} [{tlo:+.0f}, {thi:+.0f}] "
              f"(repo-clustered [{tclo:+.0f}, {tchi:+.0f}])")


if __name__ == "__main__":
    main()
