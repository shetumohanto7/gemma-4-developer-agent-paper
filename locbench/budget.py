"""Localization success per token budget."""

from __future__ import annotations

import argparse
import json

BUDGETS = (500, 1000, 2000, 4000, 8000, 16000)
CHARS_PER_TOKEN = 4.0
N_ENTITY_CANDS = 100
N_FILE_CANDS = 30


class SpanSizer:
    """Character cost of line spans."""

    def __init__(self, files: list[tuple[str, str]]) -> None:
        self.offsets: dict[str, list[int]] = {}
        for path, text in files:
            offs = [0]
            for ln in text.splitlines(keepends=True):
                offs.append(offs[-1] + len(ln))
            self.offsets[path] = offs

    def chars(self, path: str, start: int = 1, end: int | None = None) -> int:
        offs = self.offsets.get(path)
        if not offs:
            return 0
        end = len(offs) - 1 if end is None else min(end, len(offs) - 1)
        return offs[end] - offs[max(start, 1) - 1]

    def record(self, index, ranked_entities: list[str], ranked_files: list[str]) -> dict:
        ents = []
        for eid in ranked_entities[:N_ENTITY_CANDS]:
            e = index.entities[eid]
            ents.append([e.path, e.start, e.end, self.chars(e.path, e.start, e.end)])
        return {"entities": ents, "files": [[p, self.chars(p)] for p in ranked_files[:N_FILE_CANDS]]}

    def gold_spans(self, index, gold_ids: list[str]) -> list[list]:
        return [[index.entities[g].path, index.entities[g].start, index.entities[g].end,
                 self.chars(index.entities[g].path, index.entities[g].start, index.entities[g].end)]
                for g in gold_ids if g in index.entities]


def _contains(span: tuple[str, int, int], gold: tuple[str, int, int]) -> bool:
    return span[0] == gold[0] and span[1] <= gold[1] and gold[2] <= span[2]


def read_cost_curve(cands: list[list], golds: list[list], file_level: bool) -> tuple[list[float], list[float]]:
    """Tokens until gold is read."""
    remaining = {i for i in range(len(golds))}
    spent, first, found_at = 0.0, float("inf"), [float("inf")] * len(golds)
    seen: list[tuple[str, int, int]] = []
    for c in cands:
        if file_level:
            path, chars = c
            span = (path, 0, 10**9)
        else:
            path, start, end, chars = c
            span = (path, start, end)
        if any(_contains(s, span) for s in seen):  # already read via enclosing span
            continue
        seen.append(span)
        spent += chars / CHARS_PER_TOKEN
        for i in list(remaining):
            g = golds[i]
            if _contains(span, (g[0], g[1], g[2])):
                found_at[i] = spent
                first = min(first, spent)
                remaining.discard(i)
        if not remaining:
            break
    return [first], [max(found_at) if found_at else float("inf")]


def summarize(rows: list[dict], budgets=BUDGETS) -> dict:
    out: dict[str, dict] = {}
    oracle_costs = []
    for r in rows:
        golds = r["gold"].get("function_spans") or []
        if golds:
            oracle_costs.append(sum(g[3] for g in golds) / CHARS_PER_TOKEN)
    for method in sorted({m for r in rows for m in r.get("cands", {})}):
        firsts, alls = [], []
        for r in rows:
            golds = r["gold"].get("function_spans") or []
            c = r.get("cands", {}).get(method)
            if not golds or c is None:
                continue
            file_level = not c["entities"]
            f, a = read_cost_curve(c["files"] if file_level else c["entities"], golds, file_level)
            firsts += f
            alls += a
        if not firsts:
            continue
        n = len(firsts)
        out[method] = {
            "n": n,
            "first_gold": {b: sum(1 for x in firsts if x <= b) / n for b in budgets},
            "all_gold": {b: sum(1 for x in alls if x <= b) / n for b in budgets},
            "median_tokens_first": sorted(firsts)[n // 2],
        }
    if oracle_costs:
        n = len(oracle_costs)
        out["oracle (gold spans only)"] = {
            "n": n, "first_gold": {b: sum(1 for x in oracle_costs if x <= b) / n for b in budgets},
            "all_gold": {b: sum(1 for x in oracle_costs if x <= b) / n for b in budgets},
            "median_tokens_first": sorted(oracle_costs)[n // 2]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--json")
    args = ap.parse_args()
    rows, seen = [], set()
    for p in args.results:
        for line in open(p):
            if line.strip():
                r = json.loads(line)
                if r["instance_id"] not in seen:
                    seen.add(r["instance_id"])
                    rows.append(r)
    s = summarize(rows)
    print(f"# Budgeted localization ({len(rows)} tasks; tokens = chars/{CHARS_PER_TOKEN:g})\n")
    for key, title in (("first_gold", "first gold function read"), ("all_gold", "all gold functions read")):
        print(f"## Success rate: {title} within B tokens\n")
        print("| method | " + " | ".join(f"B={b}" for b in BUDGETS) + " | median tokens to first gold |")
        print("|---" * (len(BUDGETS) + 2) + "|")
        for m, v in sorted(s.items(), key=lambda kv: -kv[1][key][4000]):
            med = v["median_tokens_first"]
            print(f"| {m} | " + " | ".join(f"{100 * v[key][b]:.1f}" for b in BUDGETS)
                  + f" | {'∞' if med == float('inf') else f'{med:.0f}'} |")
        print()
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(s, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
