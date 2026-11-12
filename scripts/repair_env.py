"""Add missing test dependency wheels."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "competition")
DST = os.path.join(ROOT, "data", "competition_repaired")
RECORD = os.path.join(ROOT, "experiments", "05_find_vs_fix", "env_repair.json")


def latest_pure_wheel(pkg: str) -> dict:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=60) as resp:
        info = json.load(resp)
    version = info["info"]["version"]
    for f in info["urls"]:
        if f["packagetype"] == "bdist_wheel" and f["filename"].endswith(("-py3-none-any.whl", "-py2.py3-none-any.whl")):
            return {"package": pkg, "version": version, "filename": f["filename"], "url": f["url"],
                    "sha256": f["digests"]["sha256"]}
    raise SystemExit(f"no pure-Python wheel for {pkg} {version}")


def main() -> None:
    pkgs = sys.argv[1:]
    os.makedirs(os.path.join(DST, "wheels"), exist_ok=True)
    for name in os.listdir(os.path.join(SRC, "wheels")):  # hard links, originals untouched
        dst = os.path.join(DST, "wheels", name)
        if not os.path.exists(dst):
            os.link(os.path.join(SRC, "wheels", name), dst)
    for item in ("tasks.jsonl", "sandbox", "docker", "HARNESS_README.md"):
        link = os.path.join(DST, item)
        if not os.path.lexists(link):
            os.symlink(os.path.join(SRC, item), link)
    record = json.load(open(RECORD)) if os.path.exists(RECORD) else {"added_wheels": []}
    have = {w["filename"] for w in record["added_wheels"]}
    for pkg in pkgs:
        w = latest_pure_wheel(pkg)
        if w["filename"] in have:
            continue
        data = urllib.request.urlopen(w["url"], timeout=120).read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != w["sha256"]:
            raise SystemExit(f"sha256 mismatch for {w['filename']}")
        with open(os.path.join(DST, "wheels", w["filename"]), "wb") as fh:
            fh.write(data)
        record["added_wheels"].append({k: w[k] for k in ("package", "version", "filename", "sha256")})
        print(f"added {w['filename']} (sha256 {digest[:16]}... verified)")
    os.makedirs(os.path.dirname(RECORD), exist_ok=True)
    json.dump(record, open(RECORD, "w"), indent=1)
    print(f"{len(os.listdir(os.path.join(DST, 'wheels')))} wheels in {os.path.relpath(DST, ROOT)}/wheels")


if __name__ == "__main__":
    main()
