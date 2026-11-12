"""Reference passes, empty patch fails."""

import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "experiments/05_find_vs_fix")


def load(path):
    out = {}
    if os.path.exists(path):
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                out[r["instance_id"]] = r
    return out


envs = json.load(open(os.path.join(D, "envs.json")))
ref, empty = {}, {}
for key in envs["envs"]:
    ref |= load(os.path.join(D, "validity_v3", key, "reference", "task_results.jsonl"))
    empty |= load(os.path.join(D, "validity_v3", key, "empty", "task_results.jsonl"))
missing = sorted(set(envs["task_env"]) - set(ref) | {i for i, r in ref.items() if r.get("resolved") and i not in empty})
if missing:
    raise SystemExit(f"checks incomplete for {len(missing)} tasks, e.g. {missing[:5]}")
cat, by_repo, valid = Counter(), Counter(), []
for i in sorted(ref):
    r = bool(ref[i].get("resolved"))
    e = bool(empty[i].get("resolved")) if r else None
    cat[("reference passes" if r else "reference fails") + ", " +
        ("empty fails" if e is False else "empty passes" if e else "empty not run")] += 1
    if r and e is False:
        valid.append(i)
        by_repo[ref[i]["repo"]] += 1
repo_total = Counter(r["repo"] for r in ref.values())
open(os.path.join(D, "valid_task_ids.txt"), "w").write(" ".join(valid) + "\n")
lines = [f"# Valid tasks (environment v3): {len(valid)}/{len(ref)}", "",
         "| reference patch | empty patch | tasks |", "|---|---|---|"]
lines += [f"| {k.split(', ')[0]} | {k.split(', ')[1]} | {v} |" for k, v in sorted(cat.items())]
lines += ["", "By repository (valid / all): " +
          ", ".join(f"{k} {by_repo[k]}/{repo_total[k]}" for k in sorted(repo_total))]
open(os.path.join(D, "valid_tasks_summary.md"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
