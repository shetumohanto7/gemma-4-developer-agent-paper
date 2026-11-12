"""Rank dev-split grid configs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from locbench.metrics import KS_FILE, KS_FUNC, task_metrics

DEFAULT = "ppr=0.6,alpha=0.35,mention=1.0,snippet=0.0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--default", default=DEFAULT, help="config string of the reference (v0.1) setting")
    args = ap.parse_args()
    default = args.default
    rows = [json.loads(l) for l in open(args.results) if l.strip()]
    agg: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for cfg, rk in r["ranks"].items():
            if r["gold"]["functions"]:
                m = task_metrics(rk["functions"], KS_FUNC)
                for k in ("acc@1", "acc@5", "acc@10", "hit@1", "mrr"):
                    agg[cfg]["f_" + k].append(m[k])
            if r["gold"]["files"]:
                m = task_metrics(rk["files"], KS_FILE)
                for k in ("acc@1", "acc@5"):
                    agg[cfg]["file_" + k].append(m[k])
    mean = {cfg: {k: sum(v) / len(v) for k, v in d.items()} for cfg, d in agg.items()}

    def changes(cfg: str) -> int:
        return sum(a != b for a, b in zip(cfg.split(","), default.split(",")))

    order = sorted(mean, key=lambda c: (-mean[c]["f_acc@10"], -mean[c]["f_hit@1"], changes(c)))
    n = len(agg[order[0]]["f_acc@10"])
    snip = sum(1 for r in rows if r.get("snippet_hit"))
    print(f"dev split: {len(rows)} tasks ({n} with function gold); quoted-line signal fired on {snip}\n")
    print("| rank | config | func acc@1 | acc@5 | acc@10 | hit@1 | mrr | file acc@1 | file acc@5 |")
    print("|---|---|---|---|---|---|---|---|---|")
    shown = order[: args.top] + ([default] if default not in order[: args.top] else [])
    for c in shown:
        v = mean[c]
        tag = " (reference)" if c == default else ""
        print(f"| {order.index(c) + 1} | {c}{tag} | {100 * v['f_acc@1']:.1f} | {100 * v['f_acc@5']:.1f} | "
              f"{100 * v['f_acc@10']:.1f} | {100 * v['f_hit@1']:.1f} | {v['f_mrr']:.3f} | "
              f"{100 * v['file_acc@1']:.1f} | {100 * v['file_acc@5']:.1f} |")
    best = order[0]
    print(f"\nselected by rule: {best}  (Δacc@10 vs default = "
          f"{100 * (mean[best]['f_acc@10'] - mean[default]['f_acc@10']):+.1f} pts)")


if __name__ == "__main__":
    main()
