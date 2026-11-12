"""Context variant vs original run."""

from __future__ import annotations

import argparse
import json
import os
import statistics

from locbench.competition import load_tasks
from locbench.fix_report import INFRA_RE, ROOT, boot, exact_mcnemar, load_condition, patch_touches_gold

CONDS = (("base", "H9a"), ("oracle_func", "H9b"))


def rate(rows: list[dict], pred) -> float:
    return sum(1 for r in rows if pred(r)) / max(1, len(rows))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="12b")
    ap.add_argument("--variant", default="nothoughts")
    args = ap.parse_args()
    tasks = {t["instance_id"]: t for t in load_tasks(os.path.join(ROOT, "data/competition"))}
    meta = json.load(open(os.path.join(ROOT, "data/variants/variants_meta.json")))
    cache: dict = {}
    summary: dict = {"model": args.model, "variant": args.variant, "conditions": {}}
    print(f"# Context management: gemma-4-{args.model}, original vs `{args.variant}` (pre-registered LOG 20:54)\n")
    print("| condition | run | resolved | context overflow | 10-min cap | empty patch | mean tool calls | "
          "median minutes | edits gold function | resolved if so |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    tests = []
    for cond, h in CONDS:
        orig = load_condition(args.model, cond)
        var = load_condition(args.model, cond, f"_{args.variant}")
        common = sorted(set(orig) & set(var))
        usable = [i for i in common if not any(INFRA_RE.search(str(d[i].get("error") or "")) for d in (orig, var))]
        fgold = [i for i in usable if meta[i]["gold"]["functions"]]
        out = {}
        for name, data in (("original", orig), (args.variant, var)):
            rs = [data[i] for i in usable]
            reach = [i for i in fgold if patch_touches_gold(data[i], tasks[i], meta[i]["gold"], cache)[1]]
            fix = sum(bool(data[i].get("resolved")) for i in reach)
            out[name] = {
                "n": len(rs), "resolved": sum(bool(r.get("resolved")) for r in rs),
                "context_overflow": rate(rs, lambda r: "ContextWindowExceeded" in str(r.get("error") or "")),
                "time_cap": rate(rs, lambda r: "session timeout" in str(r.get("error") or "")),
                "empty_patch": rate(rs, lambda r: not r.get("agent_patch_size")),
                "mean_tool_calls": statistics.mean(r.get("tool_calls", 0) for r in rs) if rs else 0.0,
                "median_minutes": statistics.median(r.get("duration_seconds", 0) / 60 for r in rs) if rs else 0.0,
                "reach": [len(reach), len(fgold)], "fix_given_reach": [fix, len(reach)]}
            o = out[name]
            print(f"| {cond} | {name} | {o['resolved']}/{o['n']} ({100 * o['resolved'] / max(1, o['n']):.1f}%) | "
                  f"{100 * o['context_overflow']:.0f}% | {100 * o['time_cap']:.0f}% | {100 * o['empty_patch']:.0f}% | "
                  f"{o['mean_tool_calls']:.1f} | {o['median_minutes']:.1f} | {len(reach)}/{len(fgold)} | "
                  f"{fix}/{len(reach)} |")
        diffs: dict[str, list[float]] = {}
        wins = losses = 0
        for i in usable:
            x, y = bool(var[i].get("resolved")), bool(orig[i].get("resolved"))
            wins += x and not y
            losses += y and not x
            diffs.setdefault(var[i]["repo"], []).append(float(x) - float(y))
        d = sum(v for vs in diffs.values() for v in vs) / max(1, len(usable))
        lo, hi = boot(diffs, cluster=False)
        out["test"] = {"hypothesis": h, "diff": d, "ci": [lo, hi], "variant_only": wins, "original_only": losses,
                       "p_exact_mcnemar": exact_mcnemar(wins, losses), "n": len(usable)}
        summary["conditions"][cond] = out
        tests.append((h, cond, d, lo, hi, wins, losses, exact_mcnemar(wins, losses), len(usable)))
    print("\n## Pre-registered tests (uncorrected, 2 comparisons; task-level bootstrap CI)\n")
    for h, cond, d, lo, hi, w, l, p, n in tests:
        print(f"- **{h}: {cond}, {args.variant} vs original** ({n} tasks): {100 * d:+.1f} pts [{100 * lo:+.1f}, "
              f"{100 * hi:+.1f}]; {args.variant}-only {w} vs original-only {l}, exact McNemar p = {p:.4f}")
    path = os.path.join(ROOT, "experiments/05_find_vs_fix", f"context_{args.model}_{args.variant}_summary.json")
    with open(path, "w") as fh:
        json.dump(summary, fh, indent=1)


if __name__ == "__main__":
    main()
