"""Download checkpoints to Modal volume."""

from __future__ import annotations

import os

import modal

WORKSPACE = os.environ.get("MODAL_WORKSPACE", "shetu")
if modal.is_local() and os.environ.get("MODAL_PROFILE") != WORKSPACE:
    raise SystemExit(f"Refusing to run: export MODAL_PROFILE={WORKSPACE} (set MODAL_WORKSPACE first).")

REPOS = {  # W4A16 checkpoints, not gated
    "e2b": "google/gemma-4-E2B-it-qat-w4a16-ct",
    "e4b": "google/gemma-4-E4B-it-qat-w4a16-ct",
    "12b": "google/gemma-4-12B-it-qat-w4a16-ct",
}

image = modal.Image.debian_slim(python_version="3.12").pip_install("huggingface_hub[hf_xet]")
models_vol = modal.Volume.from_name("g4paper-models", create_if_missing=True)
app = modal.App("g4paper-weights")


@app.function(image=image, volumes={"/models": models_vol}, cpu=2, timeout=3600)
def download(model: str) -> str:
    from huggingface_hub import snapshot_download

    path = snapshot_download(REPOS[model], local_dir=f"/models/{model}")
    models_vol.commit()
    files = [os.path.join(d, f) for d, _, fs in os.walk(path) for f in fs if "/.cache/" not in os.path.join(d, f)]
    return f"{REPOS[model]} -> {path}: {len(files)} files, {sum(map(os.path.getsize, files)) / 1e9:.2f} GB"


@app.local_entrypoint()
def main(model: str = "e4b") -> None:
    print(download.remote(model))
