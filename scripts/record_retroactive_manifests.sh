#!/usr/bin/env bash
# manifests for pre-provenance runs
set -euo pipefail
cd "$(dirname "$0")/.."
P=(.venv/bin/python -I -m locbench.provenance)
D=experiments/03_swebench_generalization
R="Retroactive manifest (recorded 2026-10-23); the code fingerprint is the code at recording time."

"${P[@]}" record --name lb_public_analysis --started 2026-10-22T12:46:00+06:00 \
  --cmd ".venv/bin/python -I experiments/01_leaderboard_noise/analyze_public_lb.py data/kaggle_public/leaderboard_main_2026-10-22.json --out experiments/01_leaderboard_noise --write-anonymized experiments/01_leaderboard_noise/public_lb_2026-10-22_anonymized.json" \
  --outputs experiments/01_leaderboard_noise/public_lb_summary.json experiments/01_leaderboard_noise/public_lb_2026-10-22_anonymized.json \
  --note "$R Re-running on the anonymized snapshot gives an identical summary (checked 2026-10-22)."

"${P[@]}" record --name results_lite_v01 --started 2026-10-22T12:46:00+06:00 \
  --cmd ".venv/bin/python -I -m locbench.run_swebench --dataset data/swebench/SWE-bench_Lite/test.parquet --repos data/repos --out $D/results_lite_v01.jsonl --workers 6 [--exclude-repo matplotlib/matplotlib, then --repo matplotlib/matplotlib]" \
  --outputs $D/results_lite_v01.jsonl $D/summary_lite_v01.json $D/budget_lite_v01.json \
  --note "$R Produced by graphloc v0.1 (core.py 12:34:37, before the rename to spanloc). Reproduced exactly (300/300 tasks) by method spanloc-v0.1 in results_lite_v02.jsonl."

"${P[@]}" record --name tune_dev --started 2026-10-22T12:46:00+06:00 \
  --cmd ".venv/bin/python -I -m locbench.tune --verified data/swebench/SWE-bench_Verified/test.parquet --lite data/swebench/SWE-bench_Lite/test.parquet --repos data/repos --out $D/tune_dev.jsonl --workers 5 [--exclude-repo matplotlib/matplotlib, then all]" \
  --outputs $D/tune_dev.jsonl $D/tune_dev_report.md \
  --note "$R Grid 1 on the dev split (Verified minus Lite, 407 tasks)."

"${P[@]}" record --name tune2_dev --started 2026-10-22T13:15:37+06:00 \
  --cmd ".venv/bin/python -I -m locbench.tune2 --verified data/swebench/SWE-bench_Verified/test.parquet --lite data/swebench/SWE-bench_Lite/test.parquet --repos data/repos --out $D/tune2_dev.jsonl --workers 10" \
  --outputs $D/tune2_dev.jsonl $D/tune2_dev_report.md $D/tune2_marginals.md \
  --note "$R Grid 2; v0.2 selected by the rule logged at 13:15."

"${P[@]}" record --name results_lite_v02 --started 2026-10-22T13:36:46+06:00 \
  --cmd ".venv/bin/python -I -m locbench.run_swebench --dataset data/swebench/SWE-bench_Lite/test.parquet --repos data/repos --out $D/results_lite_v02.jsonl --workers 10" \
  --outputs $D/results_lite_v02.jsonl $D/summary_lite_v02.json $D/budget_lite_v02.json $D/h4_quoted_lines_lite.md \
  --note "$R spanloc v0.2 frozen (core.py sha256 6a4967b468fa9869...). Single held-out run."

"${P[@]}" record --name pilot_e4b_ollama --started 2026-10-22T14:20:00+06:00 \
  --cmd ".venv/bin/python -m agentloc.run --backend ollama --model gemma4:e4b-it-qat --ids psf__requests-2674,pallets__flask-4045,psf__requests-3362 --conditions base,skill,inject --temperature 0.6" \
  --outputs experiments/04_end_to_end/pilot_e4b.jsonl experiments/04_end_to_end/logs/pilot_e4b_ollama.log \
  --note "$R Pipeline pilot with Ollama 0.40.8 Q4_0, before the nudge/fallback fixes and the OpenAI client. Not used for inference."

"${P[@]}" record --name pilot_modal_e4b --started 2026-10-22T23:41:30+06:00 \
  --cmd ".venv/bin/python -m agentloc.run --backend openai --base-url https://shetu--g4paper-vllm-serve-e4b.us-east.modal.run --model gemma-4-e4b-it-qat-w4a16-ct --ids psf__requests-2674,pallets__flask-4045,psf__requests-3362 --conditions base,skill,inject --temperature 0.2 --workers 3" \
  --outputs experiments/04_end_to_end/pilot_modal_e4b.jsonl experiments/04_end_to_end/logs/pilot_modal_e4b.log \
  --note "$R GPU pipeline pilot (vLLM on Modal L4). Not used for inference."

"${P[@]}" record --name agentloc_lite_e4b_s0 --started 2026-10-22T23:50:33+06:00 \
  --cmd "AGENTLOC_TMP=data/tmp_agentloc .venv/bin/python -m agentloc.run --dataset data/swebench/SWE-bench_Lite/test.parquet --repos data/repos --backend openai --base-url https://shetu--g4paper-vllm-serve-e4b.us-east.modal.run --model gemma-4-e4b-it-qat-w4a16-ct --n 300 --seeds 0 --conditions base,skill,inject --temperature 0.2 --max-turns 20 --workers 8 --out experiments/04_end_to_end/agentloc_lite_e4b_s0.jsonl" \
  --outputs experiments/04_end_to_end/agentloc_lite_e4b_s0.jsonl experiments/04_end_to_end/logs/agentloc_lite_e4b_s0.log \
  --note "Recorded while running (launched before the manifest system existed). Files it uses (agentloc/agent.py, run.py, sandbox.py, spanloc/core.py, skill scripts) are unchanged since launch apart from manifest hooks added to run.py after launch. Pre-registration: LOG.md 22:38."

for n in lb_public_analysis results_lite_v01 tune_dev tune2_dev results_lite_v02 pilot_e4b_ollama pilot_modal_e4b; do
  "${P[@]}" finish --name "$n" --status finished
done
