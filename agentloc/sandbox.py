"""Locked-down Docker tool sandbox."""

from __future__ import annotations

import os
import shlex
import subprocess
import uuid

IMAGE = "g4paper-sandbox:latest"
SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "submission", "agent", "skills", "spanloc")


class Sandbox:
    def __init__(self, repo_dir: str, image: str = IMAGE, cpus: float = 1.0, memory: str = "1g",
                 timeout: int = 30, max_output: int = 6000) -> None:
        self.repo_dir = os.path.abspath(repo_dir)
        self.image, self.cpus, self.memory = image, cpus, memory
        self.timeout, self.max_output = timeout, max_output
        self.name = f"g4paper-{uuid.uuid4().hex[:12]}"
        self.started = False

    def __enter__(self) -> "Sandbox":
        cmd = [
            "docker", "run", "-d", "--rm", "--name", self.name,
            "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=64m",
            "--cpus", str(self.cpus), "--memory", self.memory, "--pids-limit", "128",
            "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
            "-v", f"{self.repo_dir}:/workspace:ro",
            "-v", f"{SKILL_DIR}:/skills/spanloc:ro",
            "-w", "/workspace", self.image, "sleep", "infinity",
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        self.started = True
        return self

    def __exit__(self, *exc) -> None:
        if self.started:
            subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)
            self.started = False

    def run(self, command: str, timeout: int | None = None) -> str:
        """Run shell command, truncate output."""
        t = timeout or self.timeout
        try:
            proc = subprocess.run(
                ["docker", "exec", self.name, "timeout", str(t), "bash", "-c", command],
                capture_output=True, timeout=t + 10,
            )
            out = (proc.stdout + proc.stderr).decode("utf-8", "replace")
            if proc.returncode == 124:
                out += f"\n[command timed out after {t}s]"
        except subprocess.TimeoutExpired:
            out = f"[command timed out after {t}s]"
        if len(out) > self.max_output:
            half = self.max_output // 2
            out = out[:half] + f"\n[... {len(out) - self.max_output} characters omitted ...]\n" + out[-half:]
        return out or "(no output)"

    def read_file(self, filepath: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """Numbered inclusive line slice."""
        path = shlex.quote(filepath)
        s = max(1, int(start_line or 1))
        e = f"{int(end_line)}" if end_line else "$"
        return self.run(f"test -f {path} || {{ echo 'error: no such file: {filepath}'; exit 0; }}; "
                        f"awk 'NR>={s} && NR<={e} {{printf \"%6d  %s\\n\", NR, $0}}' {path}")

    def skill(self, script: str, args: list[str]) -> str:
        """Run a spanloc skill script."""
        if script not in ("locate.py", "outline.py"):
            return f"error: unknown script {script!r}; available: locate.py, outline.py"
        quoted = " ".join(shlex.quote(a) for a in args)
        return self.run(f"python -I /skills/spanloc/scripts/{script} {quoted}", timeout=60)
