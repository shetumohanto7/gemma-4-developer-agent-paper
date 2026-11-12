"""Capture external reproducibility provenance."""

from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os
import platform
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "experiments", "provenance")
HF_MODELS = ["google/gemma-4-E2B-it-qat-w4a16-ct", "google/gemma-4-E4B-it-qat-w4a16-ct",
             "google/gemma-4-12B-it-qat-w4a16-ct"]
HF_DATASETS = ["princeton-nlp/SWE-bench_Lite", "princeton-nlp/SWE-bench_Verified"]


def sh(cmd: list[str], env: dict | None = None) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                              env={**os.environ, **(env or {})}).stdout.strip()
    except Exception as exc:  # noqa: BLE001 - best effort
        return f"<unavailable: {exc}>"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hf_sha(kind: str, repo: str) -> dict:
    url = f"https://huggingface.co/api/{kind}/{repo}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "provenance"}),
                                    timeout=60) as resp:
            info = json.load(resp)
        return {"sha": info.get("sha"), "lastModified": info.get("lastModified"),
                "gated": info.get("gated"), "license": (info.get("cardData") or {}).get("license")}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    today = dt.date.today().isoformat()
    venvs = {}
    for name in (".venv", ".venv-harness"):
        py = os.path.join(ROOT, name, "bin", "python")
        if os.path.exists(py):
            freeze = sh(["uv", "pip", "freeze", "--python", py])
            path = os.path.join(OUT, f"env_{name.strip('.')}_{today}.txt")
            with open(path, "w") as fh:
                fh.write(freeze + "\n")
            venvs[name] = {"python": sh([py, "-c", "import sys; print(sys.version.split()[0])"]),
                           "freeze_file": os.path.relpath(path, ROOT), "packages": len(freeze.splitlines())}
    prov = {
        "captured": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "machine": {"platform": platform.platform(), "machine": platform.machine(),
                    "cpu": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
                    "cores": os.cpu_count(),
                    "ram_gb": round(int(sh(["sysctl", "-n", "hw.memsize"]) or 0) / 2**30, 1),
                    "macos": sh(["sw_vers", "-productVersion"])},
        "python_envs": venvs,
        "docker": {"version": sh(["docker", "version", "--format", "{{.Server.Version}}"]),
                   "sandbox_image_id": sh(["docker", "image", "inspect", "g4paper-sandbox:latest",
                                           "--format", "{{.Id}}"]),
                   "sandbox_dockerfile_sha256": sha256(os.path.join(ROOT, "agentloc/docker/Dockerfile"))},
        "ollama_pilot": {"version": "0.40.8", "model": "gemma4:e4b-it-qat", "model_id": "ee6656371218",
                         "note": "pilot only (experiments/04_end_to_end/pilot_e4b.jsonl); models deleted 2026-10-22"},
        "harness_wheels": {os.path.basename(p): sha256(p)
                           for p in sorted(glob.glob(os.path.join(ROOT, "data/harness_wheels/*.whl")))},
        "serving": {
            "vllm_wheel": {"file": "vllm-0.19.1-cp38-abi3-manylinux_2_31_x86_64.whl",
                           "sha256": "73c69bafca24fbdad44690c44d6c6446514351e6f3cc9a6057cba05e66051310",
                           "source": "kaggle dataset metric/gemma-4-developer-agent-wheelhouse (v31)"},
            "transformers_wheel_sha256": "53f0ea8aa397e29244c2377ba981bcaf0c87adcf44fbdd447ef6306522afcacd",
            "gpu": "Modal, tensor_parallel_size 1: NVIDIA L4 (E2B, E4B), NVIDIA A100-40GB (12B fix runs, LOG.md 07:15)",
            "modal_app": f"g4paper-vllm (workspace {os.environ.get('MODAL_WORKSPACE', 'shetu')})",
            "modal_image_definition_sha256": sha256(os.path.join(ROOT, "modal_app/vllm_server.py")),
        },
        "models": {m: hf_sha("models", m) for m in HF_MODELS},
        "datasets": {d: hf_sha("datasets", d) for d in HF_DATASETS},
        "dataset_files": {os.path.relpath(p, ROOT): sha256(p)
                          for p in sorted(glob.glob(os.path.join(ROOT, "data/swebench/*/test.parquet")))},
        "swebench_repos": {os.path.basename(p): {"head": sh(["git", f"--git-dir={p}", "rev-parse", "HEAD"])}
                           for p in sorted(glob.glob(os.path.join(ROOT, "data/repos/*.git")))},
        "modal_apps": sh([os.path.join(ROOT, ".venv/bin/modal"), "app", "list", "--json"], {"MODAL_PROFILE": os.environ.get("MODAL_WORKSPACE", "shetu")}),
    }
    path = os.path.join(OUT, f"provenance_{today}.json")
    with open(path, "w") as fh:
        json.dump(prov, fh, indent=1)
    print(f"wrote {os.path.relpath(path, ROOT)}")
    for m, v in prov["models"].items():
        print(f"  {m}: revision {v.get('sha')}")


if __name__ == "__main__":
    main()
