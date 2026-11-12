"""Serve Gemma 4 on Modal."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time

import modal

WORKSPACE = os.environ.get("MODAL_WORKSPACE", "shetu")
if modal.is_local() and os.environ.get("MODAL_PROFILE") != WORKSPACE:
    raise SystemExit(f"Refusing to run: export MODAL_PROFILE={WORKSPACE} (set MODAL_WORKSPACE first).")

APP_NAME = "g4paper-vllm"
MODELS = {
    "e2b": ("google/gemma-4-E2B-it-qat-w4a16-ct", "gemma-4-e2b-it-qat-w4a16-ct"),
    "e4b": ("google/gemma-4-E4B-it-qat-w4a16-ct", "gemma-4-e4b-it-qat-w4a16-ct"),
    "12b": ("google/gemma-4-12B-it-qat-w4a16-ct", "gemma-4-12b-it-qat-w4a16-ct"),
}
WHEELHOUSE = "https://www.kaggle.com/api/v1/datasets/download/metric/gemma-4-developer-agent-wheelhouse"
# scorer's pinned serving wheels
SERVING_WHEELS = [
    "vllm-0.19.1-cp38-abi3-manylinux_2_31_x86_64.whl",
    "transformers-5.13.1-py3-none-any.whl",
    "tokenizers-0.22.2-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    "compressed_tensors-0.15.0.1-py3-none-any.whl",
    "safetensors-0.8.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    "xgrammar-0.2.5.post1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl",
    "flashinfer_python-0.6.6-py3-none-any.whl",
    "flashinfer_cubin-0.6.6-py3-none-any.whl",
    "mistral_common-1.11.7-py3-none-any.whl",
    "llguidance-1.3.0-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    "outlines_core-0.2.11-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    "msgspec-0.21.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
    "apache_tvm_ffi-0.1.13.post3-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl",
    "quack_kernels-0.6.4-py3-none-any.whl",
    "openai_harmony-0.0.8-cp38-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    "nvidia_cudnn_frontend-1.18.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl",
    "gguf-0.19.0-py3-none-any.whl",
    "cbor2-6.1.4-cp312-cp312-manylinux_2_28_x86_64.whl",
    "ijson-3.5.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
    "pybase64-1.5.0-cp312-cp312-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl",
    "setproctitle-1.3.7-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl",
    "depyf-0.20.0-py3-none-any.whl",
    "lm_format_enforcer-0.11.3-py3-none-any.whl",
    "partial_json_parser-0.2.1.1.post7-py3-none-any.whl",
    "pydantic_extra_types-2.11.2-py3-none-any.whl",
    "pycountry-26.2.16-py3-none-any.whl",
    "diskcache-5.6.3-py3-none-any.whl",
    "interegular-0.3.3-py37-none-any.whl",
    "astor-0.8.1-py2.py3-none-any.whl",
    "loguru-0.7.3-py3-none-any.whl",
    "model_hosting_container_standards-0.1.16-py3-none-any.whl",
    "prometheus_fastapi_instrumentator-8.1.0-py3-none-any.whl",
    "opentelemetry_semantic_conventions_ai-0.5.1-py3-none-any.whl",
]
_fetch = " && ".join(f"curl -sSfL -A Mozilla/5.0 -o /tmp/wh/{w} {WHEELHOUSE}/{w} && sleep 1" for w in SERVING_WHEELS)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl")
    .run_commands(
        f"mkdir -p /tmp/wh && {_fetch}",
        "sha256sum /tmp/wh/vllm-*.whl /tmp/wh/transformers-*.whl",
        # vLLM first, then pins unresolved
        "pip install /tmp/wh/vllm-0.19.1-*.whl",
        "find /tmp/wh -name '*.whl' ! -name 'vllm-*' -print0 | xargs -0 pip install --no-deps --force-reinstall",
        "pip install 'huggingface_hub>=1.5,<2.0' 'nvidia-cutlass-dsl==4.6.2' 'cuda-bindings==12.9.4'",
        "pip check || true",
        "pip list 2>/dev/null | grep -i -E '^(vllm|transformers|tokenizers|xgrammar|torch|compressed-tensors|flashinfer-python) '",
        "python -c 'import vllm, transformers; print(vllm.__version__, transformers.__version__)'",
        "rm -rf /tmp/wh",
    )
    .env({"HF_HOME": "/models/hf"})
)
models_vol = modal.Volume.from_name("g4paper-models", create_if_missing=True)
api_key = modal.Secret.from_name("g4paper-vllm-key")  # holds VLLM_API_KEY

app = modal.App(APP_NAME)




def vllm_cmd(model: str) -> list[str]:
    _, served = MODELS[model]
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", f"/models/{model}", "--served-model-name", served,
        "--host", "0.0.0.0", "--port", "8000",
        "--max-model-len", "32768", "--dtype", "auto", "--gpu-memory-utilization", "0.90",
        "--enable-auto-tool-choice", "--tool-call-parser", "gemma4",
        "--reasoning-parser", "gemma4",
        "--reasoning-config", json.dumps({"reasoning_start_str": "<|channel>", "reasoning_end_str": "<channel|>"}),
        "--no-scheduler-reserve-full-isl",
        # API key via env only
    ]
    if not os.environ.get("VLLM_API_KEY"):
        raise RuntimeError("VLLM_API_KEY is not set; refusing to serve without auth")
    if model == "12b":
        cmd += ["--hf-overrides", json.dumps({"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"})]
    return cmd


def launch(model: str, startup_timeout: int = 870) -> None:
    """Start vLLM; fail fast."""
    proc = subprocess.Popen(vllm_cmd(model))
    deadline = time.time() + startup_timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"vLLM exited with code {proc.returncode} during startup")
        try:
            socket.create_connection(("127.0.0.1", 8000), timeout=1).close()
            return
        except OSError:
            time.sleep(2)
    proc.terminate()
    raise RuntimeError("vLLM did not start in time")


# scale to zero, one GPU
GPU_KW = dict(image=image, gpu="L4", volumes={"/models": models_vol}, secrets=[api_key],
              timeout=6 * 3600, scaledown_window=300, max_containers=1)


@app.function(**GPU_KW)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=8000, startup_timeout=900)
def serve_e4b() -> None:
    launch("e4b")


@app.function(**GPU_KW)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=8000, startup_timeout=900)
def serve_e2b() -> None:
    launch("e2b")


@app.function(**GPU_KW)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=8000, startup_timeout=900)
def serve_12b() -> None:
    launch("12b")


# 12B too slow on L4
@app.function(**(GPU_KW | {"gpu": "A100-40GB"}))
@modal.concurrent(max_inputs=64)
@modal.web_server(port=8000, startup_timeout=900)
def serve_12b_a100() -> None:
    launch("12b")
