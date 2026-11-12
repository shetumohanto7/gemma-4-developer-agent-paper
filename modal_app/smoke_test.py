"""Smoke-test a Modal vLLM endpoint."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request

WORKSPACE = os.environ.get("MODAL_WORKSPACE", "shetu")
ENDPOINTS = {m: f"https://{WORKSPACE}--g4paper-vllm-serve-{m}.us-east.modal.run" for m in ("e2b", "e4b", "12b", "12b-a100")}
SERVED = {m: f"gemma-4-{m.split('-')[0]}-it-qat-w4a16-ct" for m in ENDPOINTS}
TOOLS = [{"type": "function", "function": {
    "name": "read_file", "description": "Read lines of a file.",
    "parameters": {"type": "object", "properties": {"filepath": {"type": "string"},
                                                     "start_line": {"type": "integer"}},
                   "required": ["filepath"]}}}]


def call(url: str, body: dict | None, key: str | None, timeout: int = 1200) -> tuple[int, dict | str]:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="e4b")
    args = ap.parse_args()
    base, served = os.environ.get("VLLM_BASE_URL") or ENDPOINTS[args.model], SERVED[args.model]
    key = open(".secrets/vllm_api_key").read().strip()

    t0 = time.time()
    status, models = call(f"{base}/v1/models", None, key)
    print(f"ready after {time.time() - t0:.0f}s (status {status}): {models if status != 200 else [m['id'] for m in models['data']]}")

    status, _ = call(f"{base}/v1/models", None, None)
    print(f"request without API key -> HTTP {status} (expect 401)")

    body = {"model": served, "temperature": 0.2, "max_tokens": 512, "tools": TOOLS, "tool_choice": "auto",
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": "Open the first 40 lines of src/app.py using the tool."}]}
    t1 = time.time()
    status, resp = call(f"{base}/v1/chat/completions", body, key)
    print(f"tool-call request: HTTP {status} in {time.time() - t1:.1f}s")
    if status == 200:
        msg = resp["choices"][0]["message"]
        print("  tool_calls:", json.dumps(msg.get("tool_calls"))[:300])
        print("  content:", (msg.get("content") or "")[:120], "| usage:", resp.get("usage"))

    body_think = dict(body, chat_template_kwargs={"enable_thinking": True}, thinking_token_budget=512)
    t2 = time.time()
    status, resp = call(f"{base}/v1/chat/completions", body_think, key)
    print(f"thinking request: HTTP {status} in {time.time() - t2:.1f}s")
    if status == 200:
        msg = resp["choices"][0]["message"]
        print("  reasoning chars:", len(msg.get("reasoning_content") or msg.get("reasoning") or ""),
              "| tool_calls:", bool(msg.get("tool_calls")), "| usage:", resp.get("usage"))


if __name__ == "__main__":
    main()
