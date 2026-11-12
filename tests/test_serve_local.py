import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import serve_local_vllm as local  # noqa: E402


def load_modal_app(monkeypatch):
    pytest.importorskip("modal")
    # pass the workspace guard
    monkeypatch.setenv("MODAL_WORKSPACE", "test")
    monkeypatch.setenv("MODAL_PROFILE", "test")
    monkeypatch.setenv("VLLM_API_KEY", "x")
    spec = importlib.util.spec_from_file_location("vllm_server", os.path.join(ROOT, "modal_app", "vllm_server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def without(args, *flags):
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
        elif a in flags:
            skip = True
        else:
            out.append(a)
    return out


@pytest.mark.parametrize("model", ["e2b", "e4b", "12b"])
def test_local_flags_match_modal(monkeypatch, model):
    remote = load_modal_app(monkeypatch).vllm_cmd(model)[3:]
    mine = local.vllm_args(model, "/x")
    assert without(mine, "--model", "--host", "--port") == without(remote, "--model", "--host", "--port")


def test_constants_and_pins_match(monkeypatch):
    mod = load_modal_app(monkeypatch)
    consts = local.modal_constants()
    assert consts["MODELS"] == mod.MODELS
    assert consts["SERVING_WHEELS"] == mod.SERVING_WHEELS
    src = open(os.path.join(ROOT, "modal_app", "vllm_server.py")).read()
    assert all(p in src for p in local.EXTRA_PINS)
