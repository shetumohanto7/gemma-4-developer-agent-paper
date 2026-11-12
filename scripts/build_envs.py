"""Per-task verification environments for the find-vs-fix experiment (environment v3, LOG.md 02:58).

The official harness unpacks one wheel set for every task and keeps, per distribution, the highest
compatible version present (swegemma 0.2.11 `_deduplicate_wheels`). Reference-patch checks showed two
consequences for local verification:

1. A wheel added for one repository changes another's tests: inline-snapshot's pytest plugin imports
   rich at startup, so rich's tests ran against the installed rich 15.0.0 instead of /workspace.
   Added wheels are therefore scoped to the repository whose own logs showed the missing module.
2. 57 of 67 fastapi checkouts declare a starlette range that excludes the newest wheel (1.6.0). For each
   package a checkout declares in [project].dependencies, wheels outside the declared range are left out,
   so the harness's own rule picks the newest version the checkout allows (what pip would install).

Each distinct wheel set becomes data/envs/<key>/ with tasks.jsonl (its tasks, unchanged) and wheels/
(hard links); key = first 12 hex of sha256 over the sorted wheel names. The harness finds the sandbox
setup through --snapshots-dir (data/competition/sandbox/setup.py). Record:
experiments/05_find_vs_fix/envs.json.

    .venv/bin/python -I scripts/build_envs.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tarfile
import tomllib
from collections import defaultdict

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "competition")
EXTRA = os.path.join(ROOT, "data", "competition_repaired", "wheels")
DST = os.path.join(ROOT, "data", "envs")
REPAIR = os.path.join(ROOT, "experiments", "05_find_vs_fix", "env_repair.json")
RECORD = os.path.join(ROOT, "experiments", "05_find_vs_fix", "envs.json")

# per-repo wheels, from logs
REPO_ADDITIONS = {
    "fastapi/fastapi": ["typing-inspection", "dirty-equals", "inline-snapshot", "asttokens", "executing"],
    "Textualize/rich": ["attrs"],
}
MARKER_ENV = {"python_version": "3.13", "python_full_version": "3.13.0", "sys_platform": "linux",
              "platform_system": "Linux", "platform_machine": "x86_64", "os_name": "posix",
              "implementation_name": "cpython", "platform_python_implementation": "CPython"}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def py313_compatible(filename: str) -> bool:
    """Mirrors swegemma's py313 check."""
    parts = filename[:-4].split("-")
    if not filename.endswith(".whl") or len(parts) < 5:
        return False
    py_tag, abi_tag = parts[-3], parts[-2]
    old = ("cp38", "cp39", "cp310", "cp311", "cp312")
    if abi_tag in old and py_tag in old:
        return False
    return abi_tag == "none" or "abi3" in abi_tag or "cp313" in py_tag


def name_version(filename: str) -> tuple[str, Version | None]:
    parts = filename[:-4].split("-")
    try:
        return norm(parts[0]), Version(parts[1])
    except InvalidVersion:
        return norm(parts[0]), None


def read_pyproject(instance_id: str) -> str | None:
    with tarfile.open(os.path.join(SRC, "snapshots", f"{instance_id}.tgz"), "r:*") as tar:
        for m in tar.getmembers():
            name = m.name[2:] if m.name.startswith("./") else m.name
            if m.isfile() and name == "pyproject.toml":
                return tar.extractfile(m).read().decode("utf-8", "replace")
    return None


def declared(pyproject: str | None) -> list[Requirement]:
    if not pyproject:
        return []
    out = []
    for dep in tomllib.loads(pyproject).get("project", {}).get("dependencies", []):
        try:
            req = Requirement(dep)
        except InvalidRequirement:
            continue
        if req.marker is None or req.marker.evaluate(MARKER_ENV):
            out.append(req)
    return out


def apply_declared(wheels: list[str], reqs: list[Requirement]) -> tuple[list[str], dict]:
    """Honor declared dependency ranges."""
    by_pkg: dict[str, list[str]] = defaultdict(list)
    for w in wheels:
        if py313_compatible(w):
            by_pkg[name_version(w)[0]].append(w)
    pins: dict[str, dict] = {}
    for req in reqs:
        cands = [w for w in by_pkg.get(norm(req.name), []) if name_version(w)[1] is not None]
        if not cands:
            continue
        newest = max(name_version(w)[1] for w in cands)
        if req.specifier.contains(newest, prereleases=True):
            continue
        keep = [w for w in cands if req.specifier.contains(name_version(w)[1], prereleases=True)]
        if not keep:  # unsatisfiable: keep harness choice
            pins[norm(req.name)] = {"declared": str(req.specifier), "newest": str(newest), "chosen": None}
            continue
        drop = set(cands) - set(keep)
        wheels = [w for w in wheels if w not in drop]
        pins[norm(req.name)] = {"declared": str(req.specifier), "newest": str(newest),
                                "chosen": str(max(name_version(w)[1] for w in keep)), "left_out": len(drop)}
    return wheels, pins


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    base = sorted(f for f in os.listdir(os.path.join(SRC, "wheels")) if f.endswith(".whl"))
    added = {norm(w["package"]): w for w in json.load(open(REPAIR))["added_wheels"]}
    for w in added.values():
        if sha256(os.path.join(EXTRA, w["filename"])) != w["sha256"]:
            raise SystemExit(f"sha256 mismatch: {w['filename']}")
    tasks = [json.loads(line) for line in open(os.path.join(SRC, "tasks.jsonl")) if line.strip()]
    envs: dict[str, dict] = {}
    task_env: dict[str, str] = {}
    for t in tasks:
        additions = [added[norm(p)]["filename"] for p in REPO_ADDITIONS.get(t["repo"], [])]
        wheels, pins = apply_declared(base + additions, declared(read_pyproject(t["instance_id"])))
        wheels = sorted(wheels)
        key = hashlib.sha256(("\n".join(wheels) + "\n").encode()).hexdigest()[:12]
        env = envs.setdefault(key, {"wheels": wheels, "repos": set(), "additions": additions,
                                    "pins": {}, "tasks": []})
        env["repos"].add(t["repo"])
        env["pins"] = {k: {kk: vv for kk, vv in v.items() if kk != "declared"} for k, v in pins.items()}
        env["tasks"].append(t)
        task_env[t["instance_id"]] = key
        t_pins = {k: v["declared"] for k, v in pins.items()}
        if t_pins:
            env.setdefault("declared", {})[t["instance_id"]] = t_pins
    os.makedirs(DST, exist_ok=True)
    for key, env in envs.items():
        d = os.path.join(DST, key)
        wd = os.path.join(d, "wheels")
        if os.path.isdir(wd):
            if sorted(os.listdir(wd)) != env["wheels"]:
                raise SystemExit(f"{wd} exists with a different wheel set; remove it first")
        else:
            os.makedirs(wd)
            for w in env["wheels"]:
                os.link(os.path.join(EXTRA if w in {a["filename"] for a in added.values()} else
                                     os.path.join(SRC, "wheels"), w), os.path.join(wd, w))
        with open(os.path.join(d, "tasks.jsonl"), "w") as fh:
            for t in env["tasks"]:
                fh.write(json.dumps(t) + "\n")
    record = {
        "rule": __doc__.split("\n\n")[1:3],
        "base_wheels": len(base),
        "repo_additions": {r: [added[norm(p)]["filename"] for p in ps] for r, ps in REPO_ADDITIONS.items()},
        "envs": {k: {"n_wheels": len(e["wheels"]), "repos": sorted(e["repos"]), "additions": e["additions"],
                     "pins": e["pins"], "declared": e.get("declared", {}),
                     "tasks": [t["instance_id"] for t in e["tasks"]]}
                 for k, e in sorted(envs.items(), key=lambda kv: -len(kv[1]["tasks"]))},
        "task_env": task_env,
    }
    with open(RECORD, "w") as fh:
        json.dump(record, fh, indent=1)
    for k, e in record["envs"].items():
        pins = ", ".join(f"{p} {v['chosen']}" for p, v in e["pins"].items()) or "no pins"
        print(f"{k}: {len(e['tasks']):3d} tasks, {e['n_wheels']} wheels, {'+'.join(e['repos'])}, {pins}")


if __name__ == "__main__":
    main()
