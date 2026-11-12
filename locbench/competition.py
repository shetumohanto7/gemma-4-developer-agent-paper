"""Main-track dataset loaders."""

from __future__ import annotations

import io
import json
import os
import tarfile
import zipfile

import numpy as np

from spanloc.core import MAX_FILE_BYTES, SKIP_DIRS


def load_tasks(data: str) -> list[dict]:
    candidates = [os.path.join(data, "tasks.jsonl"), os.path.join(data, "published", "tasks.jsonl")]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if path is None:
        raise FileNotFoundError(f"tasks.jsonl not found under {data}")
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _find(data: str, sub: str, name: str) -> str | None:
    for root in (data, os.path.join(data, "published")):
        p = os.path.join(root, sub, name)
        if os.path.exists(p):
            return p
    return None


def snapshot_py_files(data: str, instance_id: str) -> list[tuple[str, str]]:
    """Read snapshot .py files in-memory."""
    path = _find(data, "snapshots", f"{instance_id}.tgz")
    if path is None:
        raise FileNotFoundError(f"snapshot for {instance_id} not found")
    files: list[tuple[str, str]] = []
    with tarfile.open(path, "r:*") as tar:
        members = [m for m in tar.getmembers() if m.isfile() and m.name.endswith(".py")]
        names = [m.name.lstrip("./") for m in members]
        # strip common top-level directory
        tops = {n.split("/", 1)[0] for n in names if "/" in n}
        strip = len(tops) == 1 and all("/" in n for n in names)
        for m, n in zip(members, names):
            rel = n.split("/", 1)[1] if strip else n
            parts = rel.split("/")
            if any(p in SKIP_DIRS or p.endswith(".egg-info") for p in parts[:-1]) or m.size > MAX_FILE_BYTES:
                continue
            fh = tar.extractfile(m)
            if fh is not None:
                files.append((rel, fh.read().decode("utf-8", "replace")))
    files.sort()
    return files


def resource_stems(task: dict) -> list[str]:
    """Task-named, then commit-named stems."""
    return [task["instance_id"], f"{task['repo'].split('/')[-1]}_{task['base_commit']}"]


def _find_any(data: str, sub: str, stems: list[str], ext: str) -> str | None:
    for stem in stems:
        p = _find(data, sub, f"{stem}{ext}")
        if p:
            return p
    return None


def load_graph(data: str, task: dict) -> dict:
    path = _find_any(data, "graphs", resource_stems(task), ".json")
    if path is None:
        raise FileNotFoundError(f"graph for {task['instance_id']} not found")
    with open(path) as fh:
        g = json.load(fh)
    nodes = {n["id"]: n.get("text", "") for n in g.get("nodes", [])}
    raw_edges = g.get("edges", g.get("links", []))
    edges = [(e["source"], e["target"], e.get("type", "calls")) for e in raw_edges]
    return {"nodes": nodes, "edges": edges, "meta": g.get("graph", {})}


def load_embeddings(data: str, task: dict) -> tuple[list[str], np.ndarray]:
    """Node ids and L2-normalized matrix."""
    path = _find_any(data, "embeddings", resource_stems(task), ".npz")
    if path is None:
        raise FileNotFoundError(f"embeddings for {task['instance_id']} not found")
    ids, vecs = [], []
    with zipfile.ZipFile(path) as zf:  # read zip directly, no pickle
        for name in zf.namelist():
            arr = np.load(io.BytesIO(zf.read(name)), allow_pickle=False)
            ids.append(name[:-4] if name.endswith(".npy") else name)
            vecs.append(np.asarray(arr, dtype=np.float32).reshape(-1))
    mat = np.stack(vecs) if vecs else np.zeros((0, 256), np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return ids, mat / np.clip(norms, 1e-12, None)
