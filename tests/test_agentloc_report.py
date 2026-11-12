"""Agentic report row selection."""

import json

from agentloc.report import exact_mcnemar, load


def _row(cond, error, hit):
    return {"instance_id": "t1", "condition": cond, "seed": 0, "error": error, "score": {"func_hit": hit}}


def test_rerun_replaces_infra_failure_but_not_a_real_result(tmp_path):
    p = tmp_path / "r.jsonl"
    rows = [_row("skill", "model call failed: Remote end closed connection", False),
            _row("skill", "", True),
            _row("base", "", False),
            _row("base", "model call failed: later glitch", False)]  # infra row never wins
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    kept = {r["condition"]: r for r in load(str(p))}
    assert kept["skill"]["error"] == "" and kept["skill"]["score"]["func_hit"] is True
    assert kept["base"]["error"] == ""


def test_exact_mcnemar():
    assert exact_mcnemar(0, 0) == 1.0
    assert abs(exact_mcnemar(10, 2) - 0.0386) < 1e-3
