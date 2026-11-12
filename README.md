# Finding vs. fixing for small Gemma 4 coding agents

Code and results for our entry to the Kaggle
[Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper).

The question we look at: when a small, offline Gemma 4 model fails to fix a bug, is the problem *finding* the
code to change or *fixing* it once it's found? We test this in four steps:

1. Budgeted localization offline, on SWE-bench Lite and the 129 public competition tasks.
2. Whether a localizer helps a 4-bit Gemma 4 E4B agent localize (900 episodes on SWE-bench Lite).
3. How much the agent's fix rate changes when it is handed the correct file or function, inside the official
   competition harness (E2B, E4B and 12B).
4. A look at how much the public leaderboard can actually resolve.

Along the way we built **spanloc**, a localizer that uses only the Python standard library
(BM25 + AST call graph + personalized PageRank), so it runs inside the competition sandbox.

All results are already in `experiments/`. You can check every number without rerunning anything, or follow
the steps below to rerun the whole thing.

## Layout

```
spanloc/        the localizer (stdlib only)
locbench/       localization benchmark: gold extraction, methods, metrics, runners, reports
agentloc/       agentic localization: agent loop, read-only Docker sandbox, report
modal_app/      vLLM serving on Modal, weight download, smoke test
submission/     agent skill (spanloc) and the agent template used for the fix runs
scripts/        data download, per-task environments, validity checks, fix runners, cost records
notebooks/      Kaggle reproduction notebook (CPU parts)
tests/          unit tests
experiments/
  LOG.md                         settings, pre-registrations and decisions, with timestamps
  01_leaderboard_noise/          public leaderboard resolution
  02_competition_localization/   129 public competition tasks
  03_swebench_generalization/    SWE-bench Lite (results) and Verified (tuning only)
  04_end_to_end/                 agentic localization with Gemma 4 E4B
  05_find_vs_fix/                validity checks, environments, fix runs with oracle locations
  manifests/ costs/ provenance/  one manifest per run, Modal billing, model and package versions
```

## What you need

- macOS or Linux, Python 3.13 and 3.12, [uv](https://docs.astral.sh/uv/), git, Docker.
  We ran everything on an Apple silicon Mac. Docker emulates `linux/amd64` for the harness image.
- About 25 GB of free disk space (21 GB of it is the competition data).
- For the competition parts: a Kaggle account that has joined the
  [main track](https://www.kaggle.com/competitions/gemma-4-developer-agent) (it holds the data) and an API token
  in `~/.kaggle/kaggle.json` (`chmod 600`).
- For the GPU parts (sections 4 to 6): a [Modal](https://modal.com) account, or your own Linux machine with an
  NVIDIA GPU (section 4, option B). On Modal all our GPU runs together cost about $27 of credit
  (`experiments/BUDGET.md`, `experiments/costs/`).

Competition data can't be redistributed, so it is never in this repository. You download it yourself into
`data/`, which git ignores.

## 0. Setup

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -e ".[analysis]" pytest modal
.venv/bin/python -m pytest -q tests/
```

## 1. Public leaderboard resolution (CPU, seconds)

The repository keeps an anonymized leaderboard snapshot (score and submission count only).

```bash
.venv/bin/python -I experiments/01_leaderboard_noise/analyze_public_lb.py \
  experiments/01_leaderboard_noise/public_lb_2026-10-22_anonymized.json --out /tmp/lb_check
```

## 2. Localization on SWE-bench (CPU)

```bash
mkdir -p data/swebench/SWE-bench_Lite data/swebench/SWE-bench_Verified
curl -L -o data/swebench/SWE-bench_Lite/test.parquet \
  https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite/resolve/main/data/test-00000-of-00001.parquet
curl -L -o data/swebench/SWE-bench_Verified/test.parquet \
  https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/resolve/main/data/test-00000-of-00001.parquet
scripts/fetch_swebench_repos.sh data/repos          # 12 bare clones, about 1.5 GB

# optional: tuning, on Verified tasks that are not in Lite
.venv/bin/python -I -m locbench.tune --verified data/swebench/SWE-bench_Verified/test.parquet \
  --lite data/swebench/SWE-bench_Lite/test.parquet --repos data/repos \
  --out experiments/03_swebench_generalization/tune_dev.jsonl --workers 8
.venv/bin/python -I -m locbench.tune_report experiments/03_swebench_generalization/tune_dev.jsonl

# main run on Lite (300 tasks), then the reports
D=experiments/03_swebench_generalization
.venv/bin/python -I -m locbench.run_swebench --dataset data/swebench/SWE-bench_Lite/test.parquet \
  --repos data/repos --out $D/results_lite_v02.jsonl --workers 8
.venv/bin/python -I -m locbench.report $D/results_lite_v02.jsonl --json $D/summary_lite_v02.json > $D/summary_lite_v02.md
.venv/bin/python -I -m locbench.budget $D/results_lite_v02.jsonl --json $D/budget_lite_v02.json > $D/budget_lite_v02.md
```

The frozen settings and the reason for each are in `experiments/LOG.md`.

## 3. Localization on the competition tasks (CPU)

```bash
scripts/fetch_competition_data.sh                   # into data/competition/
D=experiments/02_competition_localization
.venv/bin/python -I -m locbench.run_competition --data data/competition --out $D/results.jsonl --workers 3
.venv/bin/python -I -m locbench.report $D/results.jsonl --json $D/summary.json > $D/summary.md
.venv/bin/python -I -m locbench.budget $D/results.jsonl --json $D/budget.json > $D/budget.md
```

## 4. GPU endpoint (Modal or your own GPU)

Sections 5 and 6 need the competition's W4A16 Gemma 4 checkpoints served by an OpenAI-compatible vLLM
server. We used the scorer's exact vLLM build (0.19.1, from the competition wheelhouse) with the same flags in
both options below. Either way, first create one API key:

```bash
mkdir -p .secrets && python3 -c "import secrets; print(secrets.token_urlsafe(32))" > .secrets/vllm_api_key
```

### Option A: Modal (what we used)

The scripts read your workspace from `MODAL_WORKSPACE` and refuse to start unless `MODAL_PROFILE` matches it.

```bash
.venv/bin/modal token new                           # log in; the profile is named after your workspace
export MODAL_WORKSPACE=<your-workspace> MODAL_PROFILE=<your-workspace>
.venv/bin/modal secret create g4paper-vllm-key VLLM_API_KEY="$(cat .secrets/vllm_api_key)"

for m in e2b e4b 12b; do .venv/bin/modal run modal_app/weights.py --model $m; done
.venv/bin/modal deploy modal_app/vllm_server.py
for m in e2b e4b 12b-a100; do .venv/bin/python -I modal_app/smoke_test.py --model $m; done   # tool-call check

# optional, in a second terminal: stops all Modal apps before spend reaches $29.50
scripts/credit_guard.sh 29.50 300
```

E2B and E4B run on one L4, 12B on one A100-40GB. The endpoints scale to zero when idle. After each GPU
session, `scripts/snapshot_costs.sh` saves Modal's billing records to `experiments/costs/`. Leave
`VLLM_BASE_URL` unset with Modal; the later commands then build each model's URL from `MODAL_WORKSPACE`.

### Option B: your own GPU machine

You need Linux on x86_64 with an NVIDIA GPU and a CUDA 12 driver (the vLLM wheel is built for that), Python
3.12 and uv. 24 GB of GPU memory (L4, A10, RTX 4090) is enough for E2B and E4B; for 12B we used 40 GB, since
it also fits on an L4 but was too slow there for the harness time limit. `scripts/serve_local_vllm.py` installs
the same wheels and starts vLLM with the same flags as the Modal app (`tests/test_serve_local.py` checks this).

```bash
.venv/bin/kaggle datasets download metric/gemma-4-developer-agent-wheelhouse -p data/wheelhouse --unzip
python3 scripts/serve_local_vllm.py setup           # creates .venv-vllm
.venv/bin/python scripts/serve_local_vllm.py download e4b
python3 scripts/serve_local_vllm.py serve e4b       # keep running; serves one model at a time

# in another terminal
export VLLM_BASE_URL=http://127.0.0.1:8000
.venv/bin/python -I modal_app/smoke_test.py --model e4b
```

To switch models, stop the server and start `serve e2b` or `serve 12b`. If the GPU is on another machine, start
it with `--host 0.0.0.0` (the API key is still required) and point `VLLM_BASE_URL` at that machine.

## 5. Agentic localization (Gemma 4 E4B, 900 episodes)

```bash
docker build -t g4paper-sandbox:latest agentloc/docker
AGENTLOC_TMP=data/tmp_agentloc .venv/bin/python -m agentloc.run \
  --dataset data/swebench/SWE-bench_Lite/test.parquet --repos data/repos --backend openai \
  --base-url "${VLLM_BASE_URL:-https://$MODAL_WORKSPACE--g4paper-vllm-serve-e4b.us-east.modal.run}" \
  --model gemma-4-e4b-it-qat-w4a16-ct --n 300 --seeds 0 --conditions base,skill,inject \
  --temperature 0.2 --max-turns 20 --workers 8 --out experiments/04_end_to_end/agentloc_lite_e4b_s0.jsonl
.venv/bin/python -I -m agentloc.report experiments/04_end_to_end/agentloc_lite_e4b_s0.jsonl
```

## 6. Find vs. fix in the official harness

This part uses the competition's own harness (`swegemma`) and its sandbox image. We used wheelhouse version 31;
a newer version may behave differently.

With Modal, the fix scripts build each model's endpoint URL from `MODAL_WORKSPACE`. With your own GPU, keep
`VLLM_BASE_URL` set and run the commands for one model at a time, with that model being served.

```bash
# harness environment (Python 3.12)
[ -d data/wheelhouse ] || .venv/bin/kaggle datasets download metric/gemma-4-developer-agent-wheelhouse \
  -p data/wheelhouse --unzip
mkdir -p data/harness_wheels
cp data/wheelhouse/{swegemma,adk_submission,adk_eval_core,google_adk}-*.whl data/harness_wheels/
uv venv --python 3.12 .venv-harness
uv pip install --python .venv-harness/bin/python data/harness_wheels/*.whl "litellm==1.83.14"
docker build --platform linux/amd64 -f data/competition/docker/Dockerfile.sandbox \
  -t swebench-sandbox:latest data/competition/docker

# per-task environments and validity checks: the reference patch must pass, an empty patch must fail
.venv/bin/python -I scripts/repair_env.py typing-inspection dirty-equals attrs inline-snapshot asttokens executing
.venv/bin/python -I scripts/build_envs.py
scripts/run_validity_checks_v3.sh
.venv/bin/python -I scripts/compute_valid_tasks.py         # writes experiments/05_find_vs_fix/valid_task_ids.txt
.venv/bin/python -I -m locbench.make_task_variants --data data/competition --out data/variants

# fix runs: four conditions per model (base, spanloc, oracle_file, oracle_func), run together
scripts/run_fix_all_conditions.sh e4b 2
scripts/run_fix_all_conditions.sh e2b 2
SERVE_KEY=12b-a100 scripts/run_fix_all_conditions.sh 12b 2     # 12B needs the A100 endpoint

# 12B follow-up with earlier thoughts dropped from the history
CONDS="base oracle_func" VARIANT=nothoughts SERVE_KEY=12b-a100 scripts/run_fix_all_conditions.sh 12b 4

# reports (paired tests as pre-registered in LOG.md)
for m in e4b e2b 12b; do
  .venv/bin/python -I -m locbench.fix_report --model $m > experiments/05_find_vs_fix/fix_${m}_report.md
done
.venv/bin/python -I -m locbench.context_report --model 12b --variant nothoughts
```

## Reproducibility record

| What | Where |
|---|---|
| Settings, pre-registrations and decisions, timestamped | `experiments/LOG.md` |
| One manifest per run: command, code hashes, packages, times, output hashes | `experiments/manifests/*.json` |
| Run logs and per-task results | `experiments/0*/` |
| Modal billing (hourly, per app and resource) and the spend ledger | `experiments/costs/`, `experiments/BUDGET.md` |
| Model and dataset revisions, wheel hashes, sandbox image, package lists | `experiments/provenance/` |

The find-vs-fix episode traces, logs and patches are not included, because they quote the competition tasks,
which the rules don't allow us to redistribute. The per-task results and summaries are included, so
`locbench.fix_report --no-secondary` recomputes every resolved count and paired test; the patch-vs-gold columns
need the competition data and a rerun.

Every runner writes its manifest through `locbench.provenance`. After the runs we shortened code comments; the
code itself is unchanged, and `experiments/provenance/comment_trim_2026-11-12.json` maps the source hashes in
the manifests to the current files.

## Using spanloc on your own repository

```bash
.venv/bin/spanloc locate --repo /path/to/repo "TypeError in jsonable_encoder when ..."
.venv/bin/spanloc outline fastapi/routing.py --repo /path/to/repo
```

## Links

Competition
- [Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)
  ([rules](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/rules))
- [Main Track](https://www.kaggle.com/competitions/gemma-4-developer-agent), which hosts the task data
  ([data](https://www.kaggle.com/competitions/gemma-4-developer-agent/data),
  [rules](https://www.kaggle.com/competitions/gemma-4-developer-agent/rules))
- [Harness wheelhouse](https://www.kaggle.com/datasets/metric/gemma-4-developer-agent-wheelhouse)
  (`swegemma`, `adk-submission`, the scorer's vLLM build; we used version 31)

Models and data
- Gemma 4 W4A16 checkpoints: [E2B](https://huggingface.co/google/gemma-4-E2B-it-qat-w4a16-ct),
  [E4B](https://huggingface.co/google/gemma-4-E4B-it-qat-w4a16-ct),
  [12B](https://huggingface.co/google/gemma-4-12B-it-qat-w4a16-ct)
- [SWE-bench Lite](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite) and
  [SWE-bench Verified](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified)
- [Google ADK](https://github.com/google/adk-python), which the harness is built on

## How this was built

We built this project with an AI coding assistant (Claude Code). It wrote most of the code and scripts, ran the
experiments, kept the logs, and drafted and edited much of the text. I chose the research question, approved each
pre-registration, design change and GPU budget before the runs they governed, and reviewed the results and the
final writeup. `experiments/LOG.md` keeps the real timestamps of that work, which is why entries are often minutes
apart.

## License

Code is released under the Apache License 2.0 (see [LICENSE](LICENSE)). The competition data is not included and
remains under Kaggle's competition rules.
