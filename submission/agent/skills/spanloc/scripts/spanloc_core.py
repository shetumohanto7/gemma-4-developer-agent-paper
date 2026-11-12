"""Rank code entities for issues."""

from __future__ import annotations

import ast
import math
import os
import re
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Iterator

__all__ = [
    "Entity",
    "RepoIndex",
    "Localizer",
    "Weights",
    "build_index",
    "iter_python_files",
]

# Repository walking

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".tox", ".nox", ".venv", "venv", "env", "node_modules",
    "__pycache__", "build", "dist", "site-packages", ".eggs", ".mypy_cache",
    ".pytest_cache", ".ruff_cache",
}
MAX_FILE_BYTES = 1_500_000  # skip generated monsters


def iter_python_files(root: str) -> Iterator[tuple[str, str]]:
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
                with open(full, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            yield os.path.relpath(full, root).replace(os.sep, "/"), text


def module_name(path: str) -> str:
    """'src/pkg/mod.py' -> 'pkg.mod'."""
    p = path[:-3] if path.endswith(".py") else path
    parts = [x for x in p.split("/") if x]
    if parts and parts[0] in ("src", "lib") and len(parts) > 1:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else p.replace("/", ".")


TEST_RE = re.compile(r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_tests?\.py$|(^|/)conftest\.py$")
VENDOR_RE = re.compile(r"(^|/)(_?vendor(ed)?|extern(als)?|third_party|packages)(/|$)")
AUX_RE = re.compile(r"(^|/)(docs?|docs_src|examples?|benchmarks?|scripts|tutorials?)(/|$)")


def path_prior(path: str) -> float:
    """Down-weight tests, vendor, docs."""
    if TEST_RE.search(path) or VENDOR_RE.search(path):
        return 0.3
    if AUX_RE.search(path):
        return 0.5
    return 1.0


# Tokenization

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")

STOPWORDS = frozenset(
    """a an and are as at be but by for from has have i if in into is it its of on or
    that the their then there these this to was were will with we you your our not no
    can could should would may might do does did done so such than too very just also
    when where which while who what why how all any each some more most other only own
    same both few further once here out over under again up down off about above below
    between through during before after because until against been being am he she they
    them his her my me us one two use used using get got like want need see seems work
    works working issue bug error expected actual behavior behaviour example reproduce
    following code version python self cls def class return none true false import
    pass raise elif else try except finally lambda yield async await global nonlocal
    assert del with print str int float bool dict list tuple set object type args kwargs
    """.split()
)


def split_identifier(ident: str) -> list[str]:
    out: list[str] = []
    for part in ident.split("_"):
        if part:
            out.extend(m.lower() for m in CAMEL_RE.findall(part))
    return out


def tokenize(text: str) -> list[str]:
    toks: list[str] = []
    for ident in IDENT_RE.findall(text):
        low = ident.lower()
        subs = split_identifier(ident)
        if len(subs) > 1 and low not in STOPWORDS:
            toks.append(low)
        toks.extend(s for s in subs if len(s) > 1 and s not in STOPWORDS)
    return toks


# Entities and code graph

@dataclass
class Entity:
    id: str
    name: str
    kind: str
    path: str
    start: int              # 1-indexed, inclusive
    end: int
    signature: str = ""
    parent: str | None = None
    indent: int = -1
    tokens: list[str] = field(default_factory=list, repr=False)


# symmetric graph edge weights
EDGE_WEIGHTS = {"contains": 1.0, "calls": 1.0, "inherits": 0.7, "imports": 0.3}


class RepoIndex:
    """Entities, edges and BM25 index."""

    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.edges: list[tuple[str, str, str]] = []
        self.by_name: dict[str, list[str]] = defaultdict(list)
        self.by_path: dict[str, str] = {}
        self.lines: dict[str, list[tuple[str, int]]] = defaultdict(list)  # normalized line -> locations
        self.parse_failures: list[str] = []
        # BM25 state
        self._df: dict[str, int] = {}
        self._tf: dict[str, dict[str, int]] = {}
        self._len: dict[str, int] = {}
        self._avglen = 1.0
        self._postings: dict[str, list[str]] = defaultdict(list)
        self._adj: dict[str, list[tuple[str, float]]] | None = None

    def add(self, ent: Entity) -> None:
        if ent.id in self.entities:  # keep first redefinition
            return
        self.entities[ent.id] = ent
        self.by_name[ent.name].append(ent.id)
        if ent.kind == "module":
            self.by_path[ent.path] = ent.id

    def finalize(self) -> None:
        for eid, ent in self.entities.items():
            tf: dict[str, int] = defaultdict(int)
            for t in ent.tokens:
                tf[t] += 1
            self._tf[eid] = tf
            self._len[eid] = len(ent.tokens)
            for t in tf:
                self._postings[t].append(eid)
            ent.tokens = []
        n = max(1, len(self.entities))
        self._avglen = sum(self._len.values()) / n or 1.0
        self._df = {t: len(ids) for t, ids in self._postings.items()}

    def bm25(self, query_tokens: Iterable[str], k1: float = 1.2, b: float = 0.75) -> dict[str, float]:
        n = len(self.entities)
        qtf: dict[str, int] = defaultdict(int)
        for t in query_tokens:
            qtf[t] += 1
        scores: dict[str, float] = defaultdict(float)
        for t, qcount in qtf.items():
            post = self._postings.get(t)
            if not post:
                continue
            df = self._df[t]
            idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            qweight = 1.0 + math.log(qcount)
            for eid in post:
                f = self._tf[eid][t]
                denom = f + k1 * (1 - b + b * self._len[eid] / self._avglen)
                scores[eid] += qweight * idf * f * (k1 + 1) / denom
        return scores

    def adjacency(self) -> dict[str, list[tuple[str, float]]]:
        if self._adj is None:
            adj: dict[str, dict[str, float]] = defaultdict(dict)
            for s, d, typ in self.edges:
                if s == d or s not in self.entities or d not in self.entities:
                    continue
                w = EDGE_WEIGHTS.get(typ, 0.5)
                adj[s][d] = max(adj[s].get(d, 0.0), w)
                adj[d][s] = max(adj[d].get(s, 0.0), w)
            self._adj = {u: list(nb.items()) for u, nb in adj.items()}
        return self._adj

    def ppr(self, seeds: dict[str, float], alpha: float = 0.35, eps: float = 1e-5,
            max_pushes: int = 200_000) -> dict[str, float]:
        """Personalized PageRank by local push."""
        adj = self.adjacency()
        total = sum(v for v in seeds.values() if v > 0)
        if total <= 0:
            return {}
        residual: dict[str, float] = {u: v / total for u, v in seeds.items() if v > 0}
        p: dict[str, float] = defaultdict(float)
        wdeg = {}
        queue = list(residual)
        pushes = 0
        while queue and pushes < max_pushes:
            u = queue.pop()
            r = residual.get(u, 0.0)
            nbrs = adj.get(u)
            if u not in wdeg:
                wdeg[u] = sum(w for _, w in nbrs) if nbrs else 0.0
            if r <= eps * max(1.0, wdeg[u]):
                continue
            pushes += 1
            p[u] += alpha * r
            residual[u] = 0.0
            if not nbrs:
                p[u] += (1 - alpha) * r  # dangling: keep the mass
                continue
            spread = (1 - alpha) * r / wdeg[u]
            for v, w in nbrs:
                residual[v] = residual.get(v, 0.0) + spread * w
                if v not in wdeg:
                    nb = adj.get(v)
                    wdeg[v] = sum(x for _, x in nb) if nb else 0.0
                if residual[v] > eps * max(1.0, wdeg[v]):
                    queue.append(v)
        return p


class _Visitor(ast.NodeVisitor):
    """Collect entities for one file."""

    def __init__(self, index: RepoIndex, path: str, lines: list[str]) -> None:
        self.index = index
        self.path = path
        self.lines = lines
        self.mod = module_name(path)
        self.stack: list[Entity] = []
        self.imports: dict[str, str] = {}
        self.raw_calls: list[tuple[str, str, str | None]] = []
        self.raw_bases: list[tuple[str, str]] = []

    def _doc_tokens(self, node: ast.AST, name: str, signature: str) -> list[str]:
        toks = tokenize(name) * 3 + tokenize(signature) * 2
        doc = ast.get_docstring(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) else None
        if doc:
            toks += tokenize(doc[:2000])
        return toks

    def _body_tokens(self, node: ast.AST) -> list[str]:
        out: list[str] = []
        todo = list(ast.iter_child_nodes(node))
        while todo:
            n = todo.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(n, ast.Name):
                out.extend(tokenize(n.id))
            elif isinstance(n, ast.Attribute):
                out.extend(tokenize(n.attr))
            elif isinstance(n, ast.arg):
                out.extend(tokenize(n.arg))
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) < 200:
                out.extend(tokenize(n.value))
            todo.extend(ast.iter_child_nodes(n))
        return out

    def _calls(self, node: ast.AST, caller: str) -> None:
        todo = list(ast.iter_child_nodes(node))
        while todo:
            n = todo.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name):
                    self.raw_calls.append((caller, f.id, None))
                elif isinstance(f, ast.Attribute):
                    q = f.value.id if isinstance(f.value, ast.Name) else None
                    self.raw_calls.append((caller, f.attr, q))
            todo.extend(ast.iter_child_nodes(n))

    def _signature(self, node: ast.AST) -> str:
        line = self.lines[node.lineno - 1].strip() if 0 < node.lineno <= len(self.lines) else ""
        return line[:160]

    def visit_Module(self, node: ast.Module) -> None:
        mod = Entity(self.mod, self.mod.rsplit(".", 1)[-1], "module", self.path, 1,
                     max(1, len(self.lines)), signature=self.path)
        mod.tokens = tokenize(self.path) * 2 + self._doc_tokens(node, mod.name, "")
        # top-level statements join module
        for stmt in node.body:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                mod.tokens += self._body_tokens(stmt)
                self._calls(stmt, self.mod)
        self.index.add(mod)
        self.stack.append(mod)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            self.imports[(a.asname or a.name).split(".")[0]] = a.name
            self.index.edges.append((self.mod, a.name, "imports"))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = node.module or ""
        if node.level:
            pkg = self.mod.split(".")
            # __init__ is its own package
            if not self.path.endswith("__init__.py"):
                pkg = pkg[:-1]
            pkg = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
            base = ".".join(pkg + ([base] if base else []))
        for a in node.names:
            target = f"{base}.{a.name}" if base else a.name
            self.imports[a.asname or a.name] = target
            self.index.edges.append((self.mod, target, "imports"))

    def _visit_def(self, node: ast.AST, kind: str) -> None:
        parent = self.stack[-1]
        qual = f"{parent.id}.{node.name}"
        sig = self._signature(node)
        start = min([d.lineno for d in node.decorator_list] + [node.lineno])
        ent = Entity(qual, node.name, kind, self.path, start,
                     getattr(node, "end_lineno", node.lineno) or node.lineno, sig, parent.id,
                     indent=node.col_offset)
        ent.tokens = self._doc_tokens(node, node.name, sig)
        if kind == "class":
            for b in node.bases:
                bname = b.attr if isinstance(b, ast.Attribute) else b.id if isinstance(b, ast.Name) else None
                if bname:
                    self.raw_bases.append((qual, bname))
                    ent.tokens += tokenize(bname)
            # method names, not bodies
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    ent.tokens += tokenize(stmt.name)
                elif not isinstance(stmt, ast.ClassDef):
                    ent.tokens += self._body_tokens(stmt)
        else:
            ent.tokens += self._body_tokens(node)
            self._calls(node, qual)
        self.index.add(ent)
        self.index.edges.append((parent.id, qual, "contains"))
        self.stack.append(ent)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_def(node, "class")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_def(node, "function")

    visit_AsyncFunctionDef = visit_FunctionDef


def _resolve_references(index: RepoIndex, visitors: list[_Visitor], max_ambiguity: int = 3) -> None:
    ents = index.entities
    for vis in visitors:
        for caller, name, qual in vis.raw_calls:
            targets: list[str] = []
            if qual in ("self", "cls"):
                # method on the enclosing class
                cls_id = caller.rsplit(".", 1)[0]
                while cls_id and cls_id in ents and ents[cls_id].kind != "class":
                    cls_id = cls_id.rsplit(".", 1)[0] if "." in cls_id else ""
                cand = f"{cls_id}.{name}"
                if cand in ents:
                    targets = [cand]
            if not targets:
                imported = vis.imports.get(qual or name)
                if imported:
                    cand = f"{imported}.{name}" if qual else imported
                    if cand in ents:
                        targets = [cand]
            if not targets:
                same_mod = [e for e in index.by_name.get(name, ()) if e.startswith(vis.mod + ".")]
                cands = same_mod or index.by_name.get(name, [])
                if 0 < len(cands) <= max_ambiguity:
                    targets = list(cands)
            for t in targets:
                if ents[t].kind == "class":  # constructor: class and __init__
                    index.edges.append((caller, t, "calls"))
                    init = f"{t}.__init__"
                    if init in ents:
                        index.edges.append((caller, init, "calls"))
                elif ents[t].kind == "function":
                    index.edges.append((caller, t, "calls"))
        for cls, bname in vis.raw_bases:
            imported = vis.imports.get(bname)
            cands = [imported] if imported in ents else [
                e for e in index.by_name.get(bname, ()) if ents[e].kind == "class"]
            if 0 < len(cands) <= max_ambiguity:
                for t in cands:
                    index.edges.append((cls, t, "inherits"))


def build_index(files: Iterable[tuple[str, str]]) -> RepoIndex:
    """Parse files; never executes code."""
    index = RepoIndex()
    visitors: list[_Visitor] = []
    for path, text in files:
        for lineno, line in enumerate(text.splitlines(), 1):  # quoted-line lookup
            norm = _norm_line(line)
            if len(norm) >= MIN_SNIPPET_CHARS:
                index.lines[norm].append((path, lineno))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(text, filename=path)
        except (SyntaxError, ValueError, RecursionError):
            index.parse_failures.append(path)
            continue
        vis = _Visitor(index, path, text.splitlines())
        try:
            vis.visit(tree)
        except RecursionError:
            index.parse_failures.append(path)
            continue
        visitors.append(vis)
    _resolve_references(index, visitors)
    index.finalize()
    return index


# Mention extraction from issues

TRACE_RE = re.compile(r'File "([^"]+?\.py)", line (\d+), in ([A-Za-z_<][\w>]*)')
PATH_RE = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.py)\b")
DOTTED_RE = re.compile(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\b")
BACKTICK_RE = re.compile(r"`{1,3}([^`]+?)`{1,3}", re.S)
CAMEL_IDENT_RE = re.compile(r"\b([A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+|[A-Z]{2,}[a-z][A-Za-z0-9]*)\b")
SNAKE_IDENT_RE = re.compile(r"\b(_{0,2}[a-z][a-z0-9]*(?:_[a-z0-9]+)+_{0,2})\b")
CALL_IDENT_RE = re.compile(r"\b([A-Za-z_]\w*)\(")


@dataclass
class Weights:
    """Fusion weights; v0.2 adds two."""
    bm25: float = 1.0
    mention: float = 1.0
    ppr: float = 0.6
    snippet: float = 1.0         # quoted source lines (v0.2)
    member: float = 1.0          # class to methods (v0.2)
    seed_topk: int = 30
    alpha: float = 0.35          # PPR restart probability
    trace: float = 3.0
    path: float = 2.0
    dotted: float = 2.5
    backtick: float = 2.0
    plain: float = 1.0
    use_prior: bool = True


def extract_mentions(text: str) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {k: [] for k in ("trace", "path", "dotted", "backtick", "plain")}
    for path, _line, func in TRACE_RE.findall(text):
        out["trace"].append((f"{path}::{func}", 1.0))
    for p in PATH_RE.findall(text):
        out["path"].append((p, 1.0))
    code = " ".join(BACKTICK_RE.findall(text))
    for d in DOTTED_RE.findall(text):
        if not re.fullmatch(r"[\d.]+|[\w-]+\.(?:py|txt|md|rst|cfg|toml|json|yaml|yml|html|com|org|io)", d):
            out["dotted"].append((d, 1.0))
    seen: set[str] = set()
    for ident in IDENT_RE.findall(code) + CALL_IDENT_RE.findall(text):
        if ident.lower() not in STOPWORDS and len(ident) > 2 and ident not in seen:
            seen.add(ident)
            out["backtick"].append((ident, 1.0))
    for rx in (CAMEL_IDENT_RE, SNAKE_IDENT_RE):
        for ident in rx.findall(text):
            if ident not in seen:
                seen.add(ident)
                out["plain"].append((ident, 1.0))
    return out


def _match_paths(index: RepoIndex, mentioned: str) -> list[str]:
    """Resolve a mentioned file path."""
    m = mentioned.replace("\\", "/").lstrip("./")
    hits = []
    for p in index.by_path:
        for c in (p, p.split("/", 1)[1] if p.startswith(("src/", "lib/")) else None):
            if c and (m == c or m.endswith("/" + c) or c.endswith("/" + m)):
                hits.append(p)
                break
    return sorted(hits, key=len)


def mention_scores(index: RepoIndex, text: str, w: Weights) -> dict[str, float]:
    ents = index.entities
    scores: dict[str, float] = defaultdict(float)
    mentions = extract_mentions(text)

    def bump(ids: list[str], weight: float) -> None:
        if not ids:
            return
        share = weight / math.sqrt(len(ids))  # ambiguous names spread thin
        for eid in ids:
            scores[eid] += share

    for key, _ in mentions["trace"]:
        fpath, func = key.split("::")
        for p in _match_paths(index, fpath)[:3]:
            cands = [e for e in index.by_name.get(func, ()) if ents[e].path == p]
            bump(cands or [index.by_path[p]], w.trace)
    for p, _ in mentions["path"]:
        hits = _match_paths(index, p)
        if len(hits) <= 5:  # skip ambiguous bare filenames
            bump([index.by_path[q] for q in hits], w.path)
    for d, _ in mentions["dotted"]:
        parts = d.split(".")
        cands = [e for e in index.by_name.get(parts[-1], ()) if e.endswith("." + ".".join(parts[-2:])) or e == d]
        if not cands and len(parts) >= 2 and parts[0] not in ("self", "cls"):
            cands = [e for e in index.by_name.get(parts[-1], ())]
            weight = w.plain
        else:
            weight = w.dotted
        if len(cands) <= 20:
            bump(cands, weight)
    for ident, _ in mentions["backtick"]:
        cands = index.by_name.get(ident, [])
        if len(cands) <= 20:
            bump(cands, w.backtick)
    for ident, _ in mentions["plain"]:
        cands = index.by_name.get(ident, [])
        if len(cands) <= 20:
            bump(cands, w.plain)
    return scores


# v0.2: snippets, member expansion

FENCE_RE = re.compile(r"```[\w+-]*\n(.*?)```", re.S)
INLINE_CODE_RE = re.compile(r"`([^`\n]{12,200})`")
WS_RE = re.compile(r"\s+")
CODEISH_RE = re.compile(r"[=(\[.]")
MIN_SNIPPET_CHARS = 12


def _norm_line(line: str) -> str:
    return WS_RE.sub(" ", line.strip())


def code_snippets(issue: str, max_snippets: int = 40) -> list[str]:
    """Code-like lines in the issue."""
    cands: list[str] = []
    for block in FENCE_RE.findall(issue):
        cands += block.splitlines()
    cands += INLINE_CODE_RE.findall(issue)
    cands += [ln for ln in issue.splitlines() if CODEISH_RE.search(ln)]
    out, seen = [], set()
    for c in cands:
        c = c.strip()
        if c.startswith((">>>", "...")):
            c = c[3:].strip()
        if c.startswith(('File "', "Traceback", "#", "$", "pip ")):
            continue
        n = _norm_line(c)
        if MIN_SNIPPET_CHARS <= len(n) <= 200 and CODEISH_RE.search(n) and n not in seen:
            seen.add(n)
            out.append(n)
    return out[:max_snippets]


def snippet_scores(index: RepoIndex, issue: str, max_hits: int = 3) -> dict[str, float]:
    """Entities containing quoted source lines."""
    per_file: dict[str, list[Entity]] = defaultdict(list)
    for e in index.entities.values():
        if e.kind != "module":
            per_file[e.path].append(e)
    scores: dict[str, float] = defaultdict(float)
    for snip in code_snippets(issue):
        hits = index.lines.get(snip, [])
        if not hits or len(hits) > max_hits:
            continue
        for path, ln in hits:
            enclosing = [e for e in per_file.get(path, []) if e.start <= ln <= e.end]
            target = max(enclosing, key=lambda e: e.start).id if enclosing else index.by_path.get(path)
            if target:
                scores[target] += 1.0 / len(hits) ** 0.5
    return scores


def member_expand(index: RepoIndex, mention: dict[str, float], bm25: dict[str, float],
                  weight: float) -> dict[str, float]:
    """Spread class mentions to methods."""
    if weight <= 0:
        return dict(mention)
    children: dict[str, list[str]] = defaultdict(list)
    for e in index.entities.values():
        if e.parent and e.kind == "function":
            children[e.parent].append(e.id)
    out = dict(mention)
    for cid, m in mention.items():
        ent = index.entities.get(cid)
        if ent is None or ent.kind != "class" or m <= 0:
            continue
        lex = {k: bm25.get(k, 0.0) for k in children.get(cid, [])}
        total = sum(lex.values())
        if total <= 0:
            continue
        for k, v in lex.items():
            if v > 0:
                out[k] = out.get(k, 0.0) + weight * m * v / total
    return out


# Fusion

def _normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    top = max(scores.values())
    return {k: v / top for k, v in scores.items()} if top > 0 else {}


@dataclass
class Ranked:
    entity: Entity
    score: float
    parts: dict[str, float]


class Localizer:

    def __init__(self, index: RepoIndex, weights: Weights | None = None) -> None:
        self.index = index
        self.w = weights or Weights()

    def signals(self, issue: str) -> dict[str, dict[str, float]]:
        idx, w = self.index, self.w
        bm25 = _normalize(idx.bm25(tokenize(issue)))
        mention = _normalize(member_expand(idx, mention_scores(idx, issue, w), bm25, w.member))
        snippet = _normalize(snippet_scores(idx, issue)) if w.snippet > 0 else {}
        seeds: dict[str, float] = defaultdict(float)
        for eid, s in sorted(bm25.items(), key=lambda kv: -kv[1])[: w.seed_topk]:
            seeds[eid] += w.bm25 * s
        for eid, s in mention.items():
            seeds[eid] += w.mention * s
        for eid, s in snippet.items():
            seeds[eid] += w.snippet * s
        ppr = _normalize(idx.ppr(seeds, alpha=w.alpha)) if seeds else {}
        return {"bm25": bm25, "mention": mention, "snippet": snippet, "ppr": ppr}

    def rank(self, issue: str, kinds: tuple[str, ...] = ("function", "class", "module"),
             signals: dict[str, dict[str, float]] | None = None) -> list[Ranked]:
        sig = signals or self.signals(issue)
        w = self.w
        names = ("bm25", "mention", "snippet", "ppr")
        keys = set().union(*(sig.get(k, {}) for k in names))
        out: list[Ranked] = []
        for eid in keys:
            ent = self.index.entities.get(eid)
            if ent is None or ent.kind not in kinds:
                continue
            parts = {k: sig.get(k, {}).get(eid, 0.0) for k in names}
            score = (w.bm25 * parts["bm25"] + w.mention * parts["mention"] + w.snippet * parts["snippet"]
                     + w.ppr * parts["ppr"])
            if w.use_prior:
                score *= path_prior(ent.path)
            if score > 0:
                out.append(Ranked(ent, score, parts))
        out.sort(key=lambda r: (-r.score, r.entity.id))
        return out

    def rank_files(self, ranked: list[Ranked], top_per_file: int = 3) -> list[tuple[str, float]]:
        """Max score plus small bonus."""
        per: dict[str, list[float]] = defaultdict(list)
        for r in ranked:
            if len(per[r.entity.path]) < top_per_file:
                per[r.entity.path].append(r.score)
        files = [(p, s[0] + 0.25 * sum(s[1:])) for p, s in per.items()]
        files.sort(key=lambda x: (-x[1], x[0]))
        return files
