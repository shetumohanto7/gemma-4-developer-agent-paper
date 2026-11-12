"""Verify reference patches via harness."""

import sys

from adk_eval_core.tracing import SessionTrace

import swegemma.evaluate as ev


async def _reference_patch_phase1(self, task, snapshot_path, task_index, total_tasks, **kwargs):
    return task.patch, None, SessionTrace()


ev.Evaluator._run_agent_sandbox = _reference_patch_phase1

from swegemma.cli import main  # noqa: E402  (import after the patch)

if __name__ == "__main__":
    sys.exit(main())
