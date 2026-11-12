"""Build the Kaggle reproduction notebook."""

from __future__ import annotations

import json
import os

CELLS: list[tuple[str, str]] = [
    ("markdown", """# Finding Is Half the Fix? Reproduction notebook

Reproduces our Gemma 4 Developer Agent Paper Track entry from code and released result files:

1. **Localization on SWE-bench Lite** (300 tasks, 12 repositories), rerun on CPU: file and function Acc@k,
   ablations, and *budgeted localization* (success vs tokens of code read).
2. **Competition tasks** (129 public tasks), rerun on CPU when the competition data is attached.
3. **Public leaderboard resolution** (58 public tasks; best-of-n selection model).
4. **Agentic localization** (Gemma 4 E4B, 900 episodes) and **find vs fix** (oracle locations in the official
   harness): the pre-registered statistics, recomputed from the released per-episode results. Rerunning the
   episodes needs a GPU endpoint (see the repository README).

Settings are frozen in `experiments/LOG.md` (tuning used only SWE-bench Verified tasks that are not in Lite)."""),
    ("code", """import os, subprocess, sys, shutil
SRC = "/kaggle/input/spanloc-src"          # dataset containing this repository's source
WORK = "/kaggle/working/spanloc"
FULL = True                                  # False: 60-task Lite subset (~10 min)
if not os.path.exists(WORK):
    shutil.copytree(SRC, WORK, ignore=shutil.ignore_patterns("data", ".venv", "__pycache__"))
os.chdir(WORK)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", ".[analysis]", "pytest"], check=True)
subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/"], check=True)"""),
    ("markdown", "## 1. SWE-bench Lite: data and repositories (bare clones, blobs > 1 MB omitted)"),
    ("code", """import urllib.request
for ds in ("SWE-bench_Lite", "SWE-bench_Verified"):
    os.makedirs(f"data/swebench/{ds}", exist_ok=True)
    url = f"https://huggingface.co/datasets/princeton-nlp/{ds}/resolve/main/data/test-00000-of-00001.parquet"
    urllib.request.urlretrieve(url, f"data/swebench/{ds}/test.parquet")
subprocess.run(["bash", "scripts/fetch_swebench_repos.sh", "data/repos"], check=True)"""),
    ("code", """cmd = [sys.executable, "-I", "-m", "locbench.run_swebench", "--dataset", "data/swebench/SWE-bench_Lite/test.parquet",
       "--repos", "data/repos", "--out", "experiments/03_swebench_generalization/results_lite_repro.jsonl",
       "--workers", str(os.cpu_count())]
if not FULL:
    cmd += ["--limit", "60"]
subprocess.run(cmd, check=True)"""),
    ("code", """out = "experiments/03_swebench_generalization/results_lite_repro.jsonl"
print(subprocess.run([sys.executable, "-I", "-m", "locbench.report", out], capture_output=True, text=True).stdout)
print(subprocess.run([sys.executable, "-I", "-m", "locbench.budget", out], capture_output=True, text=True).stdout)"""),
    ("markdown", "## 2. Competition tasks (attach the competition data to run this part)"),
    ("code", """COMP = "/kaggle/input/gemma-4-developer-agent"
if os.path.exists(COMP):
    out = "experiments/02_competition_localization/results_repro.jsonl"
    subprocess.run([sys.executable, "-I", "-m", "locbench.run_competition", "--data", COMP, "--out", out,
                    "--workers", str(os.cpu_count())], check=True)
    print(subprocess.run([sys.executable, "-I", "-m", "locbench.report", out], capture_output=True, text=True).stdout)
else:
    print("competition data not attached; skipping")"""),
    ("markdown", "## 3. Public leaderboard resolution (anonymized snapshot of 2026-10-22: score and submission count only)"),
    ("code", """print(subprocess.run([sys.executable, "-I", "experiments/01_leaderboard_noise/analyze_public_lb.py",
                      "experiments/01_leaderboard_noise/public_lb_2026-10-22_anonymized.json", "--out", "/kaggle/working/lb"],
                     capture_output=True, text=True).stdout)"""),
    ("markdown", "## 4. Agentic localization and find vs fix (statistics from the released per-episode results)"),
    ("code", """print(subprocess.run([sys.executable, "-I", "-m", "agentloc.report",
                      "experiments/04_end_to_end/agentloc_lite_e4b_s0.jsonl"], capture_output=True, text=True).stdout)
for model in ("e2b", "e4b", "12b"):
    r = subprocess.run([sys.executable, "-I", "-m", "locbench.fix_report", "--model", model, "--no-secondary"],
                       capture_output=True, text=True)
    print(r.stdout or r.stderr)"""),
]


def build(path: str) -> None:
    nb = {"cells": [], "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                    "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    for i, (kind, src) in enumerate(CELLS):
        cell = {"cell_type": kind, "id": f"c{i:02d}", "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            cell.update({"execution_count": None, "outputs": []})
        nb["cells"].append(cell)
    with open(path, "w") as fh:
        json.dump(nb, fh, indent=1)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spanloc-reproduction.ipynb")
    build(out)
    print("wrote", out)
