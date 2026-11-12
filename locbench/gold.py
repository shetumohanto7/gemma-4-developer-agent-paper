"""Gold locations from a patch."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from spanloc.core import RepoIndex

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class FileEdit:
    status: str                                   # modified | added | deleted
    removed: list[int] = field(default_factory=list)
    insertions: list[tuple[int, int]] = field(default_factory=list)


def parse_patch(patch: str) -> dict[str, FileEdit]:
    files: dict[str, FileEdit] = {}
    cur: FileEdit | None = None
    src = dst = None
    old = 0
    prev = " "           # previous hunk line kind
    in_hunk = False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            cur, in_hunk = None, False
        elif line.startswith("--- ") and not in_hunk:
            s = line[4:].split("\t")[0].strip()
            src = None if s == "/dev/null" else s[2:] if s.startswith("a/") else s
        elif line.startswith("+++ ") and not in_hunk:
            d = line[4:].split("\t")[0].strip()
            dst = None if d == "/dev/null" else d[2:] if d.startswith("b/") else d
            status = "added" if src is None else "deleted" if dst is None else "modified"
            cur = files.setdefault(src or dst, FileEdit(status))
        elif line.startswith("@@") and cur is not None:
            m = HUNK_RE.match(line)
            old, prev, in_hunk = int(m.group(1)), " ", True
        elif in_hunk and cur is not None:
            if line.startswith("-"):
                if line[1:].strip():  # ignore deleted blank lines
                    cur.removed.append(old)
                old += 1
                prev = "-"
            elif line.startswith("+"):
                body = line[1:]
                if prev == " " and body.strip():
                    cur.insertions.append((old - 1, len(body) - len(body.lstrip())))
                    prev = "+"
                elif prev == " ":  # wait for non-blank content
                    pass
                else:
                    prev = prev if prev == "-" else "+"
            elif line.startswith("\\"):
                continue
            else:
                old += 1
                prev = " "
    return files


def _innermost(cands):
    return max(cands, key=lambda e: (e.start, -e.end)) if cands else None


def gold_locations(index: RepoIndex, patch: str) -> dict:
    """Gold files and entities."""
    edits = parse_patch(patch)
    per_file: dict[str, list] = {}
    for e in index.entities.values():
        per_file.setdefault(e.path, []).append(e)
    files, added, entities, unmapped = [], [], set(), 0
    for path, fe in edits.items():
        if fe.status == "added":
            added.append(path)
            continue
        files.append(path)
        ents = per_file.get(path, [])
        if not ents:
            unmapped += 1
            continue
        for ln in fe.removed:
            hit = _innermost([e for e in ents if e.start <= ln <= e.end])
            if hit:
                entities.add(hit.id)
            else:
                unmapped += 1
        for after, ind in fe.insertions:
            ln = max(after, 1)
            hit = _innermost([e for e in ents if e.start <= ln <= e.end and e.indent < ind])
            if hit:
                entities.add(hit.id)
            else:
                unmapped += 1
    kinds = {eid: index.entities[eid].kind for eid in entities}
    return {
        "files": sorted(files),
        "functions": sorted(e for e in entities if kinds[e] != "module"),
        "modules": sorted(e for e in entities if kinds[e] == "module"),
        "added_files": sorted(added),
        "unmapped": unmapped,
    }
