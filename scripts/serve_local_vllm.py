"""Serve Gemma 4 on a local GPU with the scorer's vLLM build.

    python3 scripts/serve_local_vllm.py setup            # .venv-vllm from data/wheelhouse
    python3 scripts/serve_local_vllm.py download e4b     # weights into data/models/e4b
    python3 scripts/serve_local_vllm.py serve e4b        # http://127.0.0.1:8000

Same wheels, model list and vLLM flags as modal_app/vllm_server.py
(tests/test_serve_local.py checks the flags match).
"""

from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(ROOT, ".venv-vllm")
WHEELHOUSE = os.path.join(ROOT, "data", "wheelhouse")
EXTRA_PINS = ["huggingface_hub>=1.5,<2.0", "nvidia-cutlass-dsl==4.6.2", "cuda-bindings==12.9.4"]


def modal_constants() -> dict:
    src = open(os.path.join(ROOT, "modal_app", "vllm_server.py")).read()
    out = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("MODELS", "SERVING_WHEELS"):
                out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


def vllm_args(model: str, model_dir: str, host: str = "127.0.0.1", port: int = 8000) -> list[str]:
    served = modal_constants()["MODELS"][model][1]
    args = [
        "--model", model_dir, "--served-model-name", served,
        "--host", host, "--port", str(port),
        "--max-model-len", "32768", "--dtype", "auto", "--gpu-memory-utilization", "0.90",
        "--enable-auto-tool-choice", "--tool-call-parser", "gemma4",
        "--reasoning-parser", "gemma4",
        "--reasoning-config", json.dumps({"reasoning_start_str": "<|channel>", "reasoning_end_str": "<channel|>"}),
        "--no-scheduler-reserve-full-isl",
    ]
    if model == "12b":
        args += ["--hf-overrides", json.dumps({"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"})]
    return args


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def setup() -> None:
    wheels = modal_constants()["SERVING_WHEELS"]
    missing = [w for w in wheels if not os.path.exists(os.path.join(WHEELHOUSE, w))]
    if missing:
        sys.exit(f"missing in {WHEELHOUSE}: {', '.join(missing[:3])} ... (download the wheelhouse first)")
    run(["uv", "venv", "--seed", "--python", "3.12", VENV])
    pip = [os.path.join(VENV, "bin", "python"), "-m", "pip", "install"]
    # vLLM first, then exact pins
    run(pip + glob.glob(os.path.join(WHEELHOUSE, "vllm-0.19.1-*.whl")))
    run(pip + ["--no-deps", "--force-reinstall"]
        + [os.path.join(WHEELHOUSE, w) for w in wheels if not w.startswith("vllm-")])
    run(pip + EXTRA_PINS)


def download(model: str) -> None:
    repo = modal_constants()["MODELS"][model][0]
    from huggingface_hub import snapshot_download

    print(snapshot_download(repo, local_dir=os.path.join(ROOT, "data", "models", model)))


def serve(model: str, host: str, port: int) -> None:
    model_dir = os.path.join(ROOT, "data", "models", model)
    if not os.path.isdir(model_dir):
        sys.exit(f"no weights in {model_dir}; run: download {model}")
    env = dict(os.environ, VLLM_API_KEY=open(os.path.join(ROOT, ".secrets", "vllm_api_key")).read().strip())
    cmd = [os.path.join(VENV, "bin", "python"), "-m", "vllm.entrypoints.openai.api_server"]
    os.execve(cmd[0], cmd + vllm_args(model, model_dir, host, port), env)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["setup", "download", "serve"])
    ap.add_argument("model", nargs="?", choices=["e2b", "e4b", "12b"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if args.action != "setup" and not args.model:
        ap.error(f"{args.action} needs a model")
    if args.action == "setup":
        setup()
    elif args.action == "download":
        download(args.model)
    else:
        serve(args.model, args.host, args.port)


if __name__ == "__main__":
    main()
