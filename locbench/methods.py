"""Localization methods compared here."""

from __future__ import annotations

import copy
import math
from collections import defaultdict
from dataclasses import replace

from spanloc.core import Localizer, RepoIndex, Weights, path_prior, tokenize

ENTITY_KINDS = ("function", "class")


def _rank_from_scores(index: RepoIndex, scores: dict[str, float], prior: bool) -> list[str]:
    items = []
    for eid, s in scores.items():
        ent = index.entities.get(eid)
        if ent is None or ent.kind not in ENTITY_KINDS or s <= 0:
            continue
        items.append((s * (path_prior(ent.path) if prior else 1.0), eid))
    items.sort(key=lambda x: (-x[0], x[1]))
    return [eid for _, eid in items]


def _files_from_entities(index: RepoIndex, ranked_scores: list[tuple[str, float]]) -> list[str]:
    per: dict[str, list[float]] = defaultdict(list)
    for eid, s in ranked_scores:
        p = index.entities[eid].path
        if len(per[p]) < 3:
            per[p].append(s)
    files = sorted(per.items(), key=lambda kv: (-(kv[1][0] + 0.25 * sum(kv[1][1:])), kv[0]))
    return [p for p, _ in files]


class FileBM25:
    """Whole-file BM25 baseline."""

    def __init__(self, files: list[tuple[str, str]], k1: float = 1.2, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tf: dict[str, dict[str, int]] = {}
        self.len: dict[str, int] = {}
        self.post: dict[str, list[str]] = defaultdict(list)
        for path, text in files:
            tf: dict[str, int] = defaultdict(int)
            toks = tokenize(path) + tokenize(text)
            for t in toks:
                tf[t] += 1
            self.tf[path], self.len[path] = tf, len(toks)
            for t in tf:
                self.post[t].append(path)
        self.n = max(1, len(self.tf))
        self.avg = sum(self.len.values()) / self.n or 1.0

    def rank(self, issue: str) -> list[str]:
        scores: dict[str, float] = defaultdict(float)
        for t in set(tokenize(issue)):
            post = self.post.get(t)
            if not post:
                continue
            idf = math.log(1 + (self.n - len(post) + 0.5) / (len(post) + 0.5))
            for p in post:
                f = self.tf[p][t]
                scores[p] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[p] / self.avg))
        return [p for p, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


def with_edges(index: RepoIndex, edges: list[tuple[str, str, str]]) -> RepoIndex:
    """Same index, different graph."""
    alt = copy.copy(index)
    alt.edges = [(s, d, t) for s, d, t in edges if s in index.entities and d in index.entities]
    alt._adj = None
    return alt


def run_methods(index: RepoIndex, issue: str, files: list[tuple[str, str]] | None = None,
                weights: Weights | None = None,
                alt_edges: list[tuple[str, str, str]] | None = None) -> dict[str, dict[str, list[str]]]:
    """Rank with every method variant."""
    w = weights or Weights()
    sig = Localizer(index, w).signals(issue)
    out: dict[str, dict[str, list[str]]] = {}

    def fused(name: str, wb: float = 0.0, wm: float = 0.0, ws: float = 0.0, wp: float = 0.0,
              prior: bool = True, signals: dict | None = None) -> None:
        s = signals or sig
        parts = {"bm25": wb, "mention": wm, "snippet": ws, "ppr": wp}
        keys = set().union(*(s.get(k, {}) for k, wt in parts.items() if wt))
        scores = {k: sum(wt * s.get(n, {}).get(k, 0.0) for n, wt in parts.items()) for k in keys}
        ranked = _rank_from_scores(index, scores, prior)
        # files use all entity kinds
        all_scored = sorted(((k, v * (path_prior(index.entities[k].path) if prior else 1.0))
                             for k, v in scores.items() if k in index.entities and v > 0),
                            key=lambda kv: (-kv[1], kv[0]))
        out[name] = {"entities": ranked, "files": _files_from_entities(index, all_scored)}

    fused("bm25", wb=1)
    fused("mention", wm=1)
    fused("snippet", ws=1)
    fused("ppr", wp=1)
    fused("bm25+mention", wb=w.bm25, wm=w.mention)
    fused("spanloc", w.bm25, w.mention, w.snippet, w.ppr)
    fused("spanloc-noprior", w.bm25, w.mention, w.snippet, w.ppr, prior=False)
    for name, change in (("spanloc-nosnippet", {"snippet": 0.0}), ("spanloc-nomember", {"member": 0.0}),
                         ("spanloc-v0.1", {"snippet": 0.0, "member": 0.0})):
        w2 = replace(w, **change)
        fused(name, w2.bm25, w2.mention, w2.snippet, w2.ppr, signals=Localizer(index, w2).signals(issue))
    # PPR with BM25 seeds only
    w_b = replace(w, mention=0.0, snippet=0.0, member=0.0)
    fused("bm25+ppr", wb=w.bm25, wp=w.ppr, signals=Localizer(index, w_b).signals(issue))
    if files is not None:
        out["file-bm25"] = {"entities": [], "files": FileBM25(files).rank(issue)}
    if alt_edges is not None:
        # propagate over competition graph
        alt_sig = Localizer(with_edges(index, alt_edges), w).signals(issue)
        fused("spanloc@their-graph", w.bm25, w.mention, w.snippet, w.ppr, signals=alt_sig)
    return out
