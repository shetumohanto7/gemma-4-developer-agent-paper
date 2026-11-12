"""Read files from bare repo."""

from __future__ import annotations

import subprocess

# stay under clone blob filter
MAX_BLOB_BYTES = 1_000_000


def py_files_at(git_dir: str, commit: str, max_bytes: int = MAX_BLOB_BYTES) -> list[tuple[str, str]]:
    ls = subprocess.run(
        ["git", f"--git-dir={git_dir}", "ls-tree", "-r", "-l", "-z", commit],
        capture_output=True, check=True,
    ).stdout.decode("utf-8", "replace")
    entries: list[tuple[str, str]] = []
    for rec in ls.split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        _mode, typ, sha, size = meta.split()
        if typ == "blob" and path.endswith(".py") and size != "-" and int(size) <= max_bytes:
            entries.append((path, sha))
    if not entries:
        return []
    out = subprocess.run(
        ["git", f"--git-dir={git_dir}", "cat-file", "--batch"],
        input="\n".join(sha for _, sha in entries).encode(), capture_output=True, check=True,
    ).stdout
    files: list[tuple[str, str]] = []
    pos = 0
    for path, _sha in entries:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].split()
        if len(header) < 3 or header[1] != b"blob":  # "<sha> missing"
            pos = nl + 1
            continue
        size = int(header[2])
        files.append((path, out[nl + 1: nl + 1 + size].decode("utf-8", "replace")))
        pos = nl + 1 + size + 1
    return files
