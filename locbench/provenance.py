"""Run manifests for reproducibility."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFESTS = os.path.join(ROOT, "experiments", "manifests")
CODE_DIRS = ("spanloc", "locbench", "agentloc", "modal_app", "submission/agent", "paper", "notebooks")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code_fingerprint() -> dict:
    """Hash result-affecting source files."""
    files = {}
    for d in CODE_DIRS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, d)):
            dirnames[:] = [x for x in dirnames if x not in ("__pycache__", "figures")]
            for f in sorted(filenames):
                if f.endswith((".py", ".md", ".yaml", ".yml", ".sh")):
                    p = os.path.join(dirpath, f)
                    files[os.path.relpath(p, ROOT)] = sha256(p)
    combined = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in sorted(files.items())).encode()).hexdigest()
    return {"combined": combined, "files": files}


def environment() -> dict:
    def run(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
        except Exception:  # noqa: BLE001 - provenance is best effort
            return ""

    freeze = run(["uv", "pip", "freeze", "--python", sys.executable]) or run([sys.executable, "-m", "pip", "freeze"])
    return {
        "python": sys.version.split()[0], "executable": sys.executable, "platform": platform.platform(),
        "machine": platform.machine(), "cpu_count": os.cpu_count(),
        "packages_sha256": hashlib.sha256(freeze.encode()).hexdigest(), "packages": freeze.splitlines(),
        "docker_sandbox_image": run(["docker", "image", "inspect", "g4paper-sandbox:latest", "--format",
                                     "{{.Id}}"]),
    }


def _path(name: str) -> str:
    return os.path.join(MANIFESTS, f"{name}.json")


def start_run(name: str, cmd: list[str] | str, params: dict | None = None, started: str | None = None,
              note: str = "") -> dict:
    os.makedirs(MANIFESTS, exist_ok=True)
    m = {
        "name": name, "status": "running",
        "started": started or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": cmd if isinstance(cmd, str) else " ".join(cmd), "params": params or {}, "note": note,
        "code": code_fingerprint(), "environment": environment(), "outputs": {},
    }
    with open(_path(name), "w") as fh:
        json.dump(m, fh, indent=1)
    return m


def finish_run(name: str, status: str = "finished", outputs: list[str] | None = None, extra: dict | None = None) -> dict:
    with open(_path(name)) as fh:
        m = json.load(fh)
    m["status"] = status
    m["finished"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    for p in outputs or list(m["outputs"]):
        ap = p if os.path.isabs(p) else os.path.join(ROOT, p)
        if os.path.exists(ap):
            with open(ap, "rb") as fh:
                lines = sum(1 for _ in fh)
            m["outputs"][os.path.relpath(ap, ROOT)] = {"sha256": sha256(ap), "bytes": os.path.getsize(ap),
                                                       "lines": lines}
    if extra:
        m.setdefault("extra", {}).update(extra)
    with open(_path(name), "w") as fh:
        json.dump(m, fh, indent=1)
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="action", required=True)
    r = sub.add_parser("record")
    r.add_argument("--name", required=True)
    r.add_argument("--cmd", required=True)
    r.add_argument("--started", default=None)
    r.add_argument("--outputs", nargs="*", default=[])
    r.add_argument("--note", default="")
    f = sub.add_parser("finish")
    f.add_argument("--name", required=True)
    f.add_argument("--status", default="finished")
    f.add_argument("--outputs", nargs="*", default=None)
    args = ap.parse_args()
    if args.action == "record":
        m = start_run(args.name, args.cmd, started=args.started, note=args.note)
        m["outputs"] = {o: {} for o in args.outputs}
        with open(_path(args.name), "w") as fh:
            json.dump(m, fh, indent=1)
        print(f"recorded {_path(args.name)} (code {m['code']['combined'][:16]})")
    else:
        m = finish_run(args.name, args.status, args.outputs)
        print(f"{args.name}: {m['status']}, outputs {list(m['outputs'])}")


if __name__ == "__main__":
    main()
