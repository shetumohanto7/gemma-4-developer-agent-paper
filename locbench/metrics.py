"""Acc@k, Hit@k, Rec@k, MRR."""

from __future__ import annotations

KS_FILE = (1, 3, 5, 10)
KS_FUNC = (1, 5, 10, 20)


def gold_ranks(ranked: list[str], gold: list[str]) -> list[int | None]:
    pos = {x: i + 1 for i, x in enumerate(ranked)}
    return [pos.get(g) for g in gold]


def task_metrics(ranks: list[int | None], ks: tuple[int, ...]) -> dict[str, float]:
    if not ranks:
        return {}
    found = [r for r in ranks if r is not None]
    m: dict[str, float] = {}
    for k in ks:
        m[f"acc@{k}"] = float(all(r is not None and r <= k for r in ranks))
        m[f"hit@{k}"] = float(any(r is not None and r <= k for r in ranks))
        m[f"rec@{k}"] = sum(1 for r in found if r <= k) / len(ranks)
    m["mrr"] = 1.0 / min(found) if found else 0.0
    return m
